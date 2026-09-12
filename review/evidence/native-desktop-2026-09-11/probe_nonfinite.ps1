param([string]$RequestsPath,[string]$OutPath)
$ErrorActionPreference='Stop'
$requests=Get-Content -LiteralPath $RequestsPath -Raw -Encoding UTF8|ConvertFrom-Json
$records=@();$app=$null;$book=$null
try{
 $app=New-Object -ComObject Excel.Application;$app.Visible=$false;$app.DisplayAlerts=$false;$app.EnableEvents=$false;$app.AutomationSecurity=3
 foreach($request in $requests){
  foreach($kind in @('NaN','PositiveInfinity','NegativeInfinity')){
   $book=$app.Workbooks.Open($request.workbook,0,$false)
   $value=switch($kind){'NaN'{[double]::NaN};'PositiveInfinity'{[double]::PositiveInfinity};'NegativeInfinity'{[double]::NegativeInfinity}}
   $record=@{card_id=$request.card_id;input_kind=$kind;input_field=$request.field;input_is_nonfinite=[double]::IsNaN($value)-or[double]::IsInfinity($value);engine_version=($app.Version+'.'+$app.Build)}
   $cell=$book.Worksheets.Item('data').Cells.Item(2,[int]$request.column)
   $matrix=New-Object 'object[,]' 1,1;$matrix[0,0]=$value
   $written=$false
   try{$cell.Value2=$matrix;$written=$true}catch{$record.status='native_input_rejected';$record.native_error=$_.Exception.Message;$record.evaluation_performed=$false}
   if($written){
    $app.CalculateFullRebuild()
    $deadline=(Get-Date).AddSeconds(90)
    while($app.CalculationState-ne 0){if((Get-Date)-gt$deadline){throw 'Native calculation timed out'};Start-Sleep -Milliseconds 100}
    $outCell=$book.Worksheets.Item('result').Cells.Item([int]$request.result_row,2)
    $isNA=[bool]$app.Evaluate('ISNA(result!B'+$request.result_row+')')
    $record.evaluation_performed=$true;$record.actual_output=if($isNA){'#N/A'}else{[string]$outCell.Text}
    $record.status=if($isNA){'native_score_blocked'}else{'fail'}
   }
   $records+=$record;Write-Output ($request.card_id+' '+$kind+' '+$record.status)
   $book.Close($false);[void][Runtime.InteropServices.Marshal]::ReleaseComObject($book);$book=$null
  }
 }
 $failed=@($records|Where-Object{$_.status-eq'fail'}).Count
 @{engine='excel';kind='native_ieee_input_probe';records=$records;passed=($records.Count-$failed);failed=$failed;completed_at=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json -Depth 10|Set-Content -LiteralPath $OutPath -Encoding UTF8
 if($failed){throw 'A nonfinite native input did not block a numeric score'}
}finally{if($null-ne$book){$book.Close($false)};if($null-ne$app){$app.Quit();[void][Runtime.InteropServices.Marshal]::ReleaseComObject($app)}}
