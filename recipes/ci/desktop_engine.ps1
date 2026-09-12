# SPDX-License-Identifier: MIT
# Execute a disposable fixture in installed Microsoft Excel or local Analysis Services.
param([Parameter(Mandatory=$true)][string]$RequestPath)
$ErrorActionPreference = 'Stop'
$request = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$result = $null
if ($request.engine -eq 'excel') {
    $app = $null; $book = $null
    try {
        $app = New-Object -ComObject Excel.Application
        $app.Visible = $false; $app.DisplayAlerts = $false; $app.EnableEvents = $false
        $app.AutomationSecurity = 3
        $book = $app.Workbooks.Open($request.workbook, 0, $false)
        $app.CalculateFullRebuild()
        $deadline = (Get-Date).AddSeconds(90)
        while ($app.CalculationState -ne 0) {
            if ((Get-Date) -gt $deadline) { throw 'Excel recalculation timed out' }
            Start-Sleep -Milliseconds 100
        }
        $outputs = @{}
        foreach ($property in $request.output_rows.PSObject.Properties) {
            $cell = $book.Worksheets.Item('result').Cells.Item([int]$property.Value, 2)
            $value = $cell.Value2
            if ([string]$cell.Text -match '^#') { $value = [string]$cell.Text }
            if ($app.Evaluate('ISNA(result!B'+[string]$property.Value+')')) { $value = '#N/A' }
            $outputs[$property.Name] = $value
            [void][Runtime.InteropServices.Marshal]::ReleaseComObject($cell)
        }
        # Verify a save/reopen does not silently change the delivered calculation.
        $book.Save(); $book.Close($false); $book = $null
        $book = $app.Workbooks.Open($request.workbook, 0, $true)
        $app.CalculateFullRebuild()
        $deadline = (Get-Date).AddSeconds(90)
        while ($app.CalculationState -ne 0) {
            if ((Get-Date) -gt $deadline) { throw 'Excel reopen recalculation timed out' }
            Start-Sleep -Milliseconds 100
        }
        foreach ($property in $request.output_rows.PSObject.Properties) {
            $cell = $book.Worksheets.Item('result').Cells.Item([int]$property.Value, 2)
            $value = $cell.Value2
            if ([string]$cell.Text -match '^#') { $value = [string]$cell.Text }
            if ($app.Evaluate('ISNA(result!B'+[string]$property.Value+')')) { $value = '#N/A' }
            if ($value -cne $outputs[$property.Name]) { throw ('Save/reopen mismatch: '+$property.Name) }
            [void][Runtime.InteropServices.Marshal]::ReleaseComObject($cell)
        }
        $result = @{ engine_version = [string]$app.Version + '.' + [string]$app.Build; outputs = $outputs }
    } finally {
        if ($null -ne $book) { $book.Close($false); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($book) }
        if ($null -ne $app) { $app.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app) }
    }
} elseif ($request.engine -eq 'dax') {
    if ($request.server -notmatch '^(localhost|127\.0\.0\.1)(:\d+)?$') { throw 'A disposable local Analysis Services instance is required' }
    Add-Type -Path $request.tom_assembly
    Add-Type -Path $request.adomd_assembly
    $server = New-Object Microsoft.AnalysisServices.Tabular.Server
    $db = $null; $connection = $null
    try {
        $server.Connect('Data Source='+$request.server)
        $db = New-Object Microsoft.AnalysisServices.Tabular.Database
        $db.Name = 'osms_test_'+[Guid]::NewGuid().ToString('N'); $db.ID = $db.Name
        $db.CompatibilityLevel = 1500
        $db.Model = New-Object Microsoft.AnalysisServices.Tabular.Model
        $db.Model.Culture = 'en-US'
        # Preserve case-distinct source values before EXACT evaluates them.
        # The default VertiPaq dictionary can merge prod/PROD on import.
        $db.Model.Collation = 'Latin1_General_100_BIN2'
        $server.Databases.Add($db); $db.Update([Microsoft.AnalysisServices.UpdateOptions]::ExpandFull)
        foreach ($definition in $request.tables) {
            $table = New-Object Microsoft.AnalysisServices.Tabular.Table
            $table.Name = $definition.name
            foreach ($columnDefinition in $definition.columns) {
                $column = New-Object Microsoft.AnalysisServices.Tabular.CalculatedTableColumn
                $column.Name = $columnDefinition.name; $column.SourceColumn = '['+$columnDefinition.name+']'
                $column.DataType = [Enum]::Parse([Microsoft.AnalysisServices.Tabular.DataType], $columnDefinition.type)
                $column.IsDataTypeInferred = $false; $column.IsNameInferred = $false
                $table.Columns.Add($column)
            }
            $source = New-Object Microsoft.AnalysisServices.Tabular.CalculatedPartitionSource
            $source.Expression = $definition.expression
            $partition = New-Object Microsoft.AnalysisServices.Tabular.Partition
            $partition.Name = $definition.name; $partition.Source = $source
            $table.Partitions.Add($partition); $db.Model.Tables.Add($table)
        }
        $db.Model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
        [void]$db.Model.SaveChanges()
        $connection = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection
        $connection.ConnectionString = 'Data Source='+$request.server+';Initial Catalog='+$db.Name
        $connection.Open()
        $command = $connection.CreateCommand(); $command.CommandText = $request.query; $command.CommandTimeout = 90
        $reader = $command.ExecuteReader(); $rows = @()
        while ($reader.Read()) {
            $row = @{}
            for ($i=0; $i -lt $reader.FieldCount; $i++) {
                $name = $reader.GetName($i) -replace '^\[|\]$', ''
                if ($reader.IsDBNull($i)) { $row[$name] = $null } else { $row[$name] = $reader.GetValue($i) }
            }
            $rows += $row
        }
        $reader.Close(); $result = @{ engine_version=[string]$server.Version; rows=$rows }
    } finally {
        if ($null -ne $connection) { $connection.Close(); $connection.Dispose() }
        if ($null -ne $db -and $db.Name -match '^osms_test_[0-9a-f]{32}$') { $db.Drop() }
        $server.Disconnect()
    }
} else { throw 'Unknown native desktop engine' }
$result | ConvertTo-Json -Depth 20 -Compress | Set-Content -LiteralPath $request.response_path -Encoding UTF8
