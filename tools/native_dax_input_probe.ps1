# SPDX-License-Identifier: MIT
param([Parameter(Mandatory=$true)][string]$RequestPath,
      [Parameter(Mandatory=$true)][string]$OutPath)
$ErrorActionPreference='Stop'
$request=Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if($request.engine -ne 'dax' -or $request.server -notmatch '^(localhost|127\.0\.0\.1):\d+$'){
    throw 'A local native DAX request is required'
}
$root=Split-Path $PSScriptRoot -Parent
$engine=Join-Path $root 'recipes\ci\desktop_engine.ps1'
Add-Type -Path $request.tom_assembly
$connection=New-Object Microsoft.AnalysisServices.Tabular.Server
try{
    $connection.Connect('Data Source='+$request.server)
    $version=[string]$connection.Version
}finally{$connection.Disconnect();$connection.Dispose()}
$record=@{engine_version=$version;outcome='error';started_at=[DateTime]::UtcNow.ToString('o')}
try{
    & $engine -RequestPath $RequestPath | Out-Null
    $record.outcome='evaluated'
    $record.result=Get-Content -LiteralPath $request.response_path -Raw -Encoding UTF8 | ConvertFrom-Json
}catch{
    $inner=$_.Exception
    $types=@()
    while($null -ne $inner){
        $types+=$inner.GetType().FullName
        $inner=$inner.InnerException
    }
    $record.exception_types=$types
    $record.native_error=$_.Exception.Message
    $record.failing_operation=$_.InvocationInfo.Line.Trim()
    $record.server_errors=@($_.Exception.InnerException.Errors | ForEach-Object {
        @{error_code=$_.ErrorCode;description=$_.Description}
    })

    # Only a server-side rejection of model values is a qualifying ingestion result.
    # Missing libraries, connection problems or malformed query syntax remain errors.
    if($types -contains 'Microsoft.AnalysisServices.OperationException' -and
       $_.InvocationInfo.Line -match '\$db\.Model\.SaveChanges\('){
        $record.outcome='native_model_input_rejected'
    }
    if($types -contains 'Microsoft.AnalysisServices.AdomdClient.AdomdErrorResponseException' -and
       ($record.native_error -match '(?is)berechnete Tabelle.*osms_input.*keine Daten.*Zeilen.*Fehler' -or
        $record.native_error -match '(?is)calculated table.*osms_input.*does not hold any data.*rows.*error')){
        $record.outcome='native_model_input_rejected_at_query'
    }

}
$record.completed_at=[DateTime]::UtcNow.ToString('o')
$record | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $OutPath -Encoding UTF8
