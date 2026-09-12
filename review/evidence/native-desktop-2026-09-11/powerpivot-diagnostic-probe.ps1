param([string]$RequestsPath,[string]$OutPath,[int]$Limit=1)
$ErrorActionPreference='Stop'
$requests=Get-Content -LiteralPath $RequestsPath -Raw -Encoding UTF8 | ConvertFrom-Json
if($Limit -gt 0){$requests=@($requests | Where-Object {$_.card_id -eq 'SOC-002'} | Select-Object -First $Limit)}
$app=$null;$book=$null;$records=@()
try {
 $app=New-Object -ComObject Excel.Application
 $app.Visible=$false;$app.DisplayAlerts=$false;$app.EnableEvents=$false;$app.AutomationSecurity=3
 foreach($request in $requests){
  $book=$app.Workbooks.Add()
  $data=$book.Worksheets.Item(1);$data.Name='data'
  $result=$book.Worksheets.Add();$result.Name='result'
  $columns=@($request.schema.PSObject.Properties)
  $matrix=New-Object 'object[,]' ([Math]::Max(2,$request.rows.Count+1)),$columns.Count
  for($j=0;$j -lt $columns.Count;$j++){$matrix[0,$j]=$columns[$j].Name}
  for($i=0;$i -lt $request.rows.Count;$i++){
   for($j=0;$j -lt $columns.Count;$j++){
    $column=$columns[$j];$value=$request.rows[$i].($column.Name)
    if($null -eq $value){continue}
    switch($column.Value.type){
     'timestamp' {$matrix[($i+1),$j]=([DateTimeOffset]::Parse($value).UtcDateTime).ToOADate()}
     'number' {$matrix[($i+1),$j]=[double]$value}
     'boolean' {$matrix[($i+1),$j]=[bool]$value}
     default {$matrix[($i+1),$j]=[string]$value}
    }
   }
  }
  $data.Range($data.Cells.Item(1,1),$data.Cells.Item($matrix.GetLength(0),$columns.Count)).Value2=$matrix
  for($j=0;$j -lt $columns.Count;$j++){
   if($columns[$j].Value.type -eq 'timestamp'){$data.Columns.Item($j+1).NumberFormat='yyyy-mm-dd hh:mm:ss'}
  }
  $table=$data.ListObjects.Add(1,$data.Range($data.Cells.Item(1,1),$data.Cells.Item([Math]::Max(2,$request.rows.Count+1),$columns.Count)),[Type]::Missing,1)
  $table.Name='osms_input'
  $path=Join-Path ([IO.Path]::GetTempPath()) ('osms-powerpivot-'+[Guid]::NewGuid().ToString('N')+'.xlsx')
  $book.SaveAs($path,51)
  $connection=$book.Connections.Add2('osms_input','OSMS synthetic native audit fixture','WORKSHEET;'+$path,'osms_input',7,$true,$false)
  $book.Model.Refresh()
  $body=($request.query -split '(?m)^EVALUATE\s*$',2)[1]
  if(!$body){throw 'Expected generated EVALUATE query'}
  $names=@($request.expected.PSObject.Properties.Name)+@('evaluation_status','selected_records','invalid_records')
  $names=@($names | Select-Object -Unique);$actual=@{}
  for($i=0;$i -lt $names.Count;$i++){
   $name=$names[$i];$measureName='OSMS_'+$name
   $formula=$request.localized_measures.($name)
   $measure=$book.Model.ModelMeasures.Add($measureName,$book.Model.ModelTables.Item('osms_input'),$formula,$book.Model.ModelFormatGeneral)
   $result.Cells.Item($i+1,1).Value2=$name
   $result.Cells.Item($i+1,2).Formula='=CUBEVALUE("ThisWorkbookDataModel","[Measures].['+$measureName+']")'
  }
  $app.CalculateUntilAsyncQueriesDone();$app.CalculateFullRebuild()
  for($i=0;$i -lt $names.Count;$i++){
   $cell=$result.Cells.Item($i+1,2);$value=$cell.Value2
   if([string]$cell.Text -match '^#'){throw ('Native output error: '+$names[$i]+' '+$cell.Text)}
   if($value -ceq '__OSMS_NATIVE_BLANK__'){$value=$null}
   $actual[$names[$i]]=$value
  }
  $record=@{card_id=$request.card_id;case_id=$request.case_id;actual=$actual;engine_version=('Excel PowerPivot '+$app.Version+'.'+$app.Build);model_row_count=$book.Model.ModelTables.Item('osms_input').RecordCount}
  $records+=$record
  @{records=$records;completed=$false}|ConvertTo-Json -Depth 30|Set-Content -LiteralPath $OutPath -Encoding UTF8
  Write-Output ($request.card_id+' '+$request.case_id+' '+($actual|ConvertTo-Json -Compress))
  $book.Close($false);[void][Runtime.InteropServices.Marshal]::ReleaseComObject($book);$book=$null
 }
 @{records=$records;completed=$true}|ConvertTo-Json -Depth 30|Set-Content -LiteralPath $OutPath -Encoding UTF8
} catch {
 @{records=$records;completed=$false;error=$_.Exception.Message}|ConvertTo-Json -Depth 30|Set-Content -LiteralPath $OutPath -Encoding UTF8
 throw
} finally {
 if($null -ne $book){$book.Close($false);[void][Runtime.InteropServices.Marshal]::ReleaseComObject($book)}
 if($null -ne $app){$app.Quit();[void][Runtime.InteropServices.Marshal]::ReleaseComObject($app)}
}
