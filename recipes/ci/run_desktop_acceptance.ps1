# SPDX-License-Identifier: MIT
# Run from the frozen candidate checkout on an authorized Windows test host.
param(
    [ValidateSet('all','audit-critical')][string]$Scope = 'audit-critical',
    [ValidateSet('excel','dax')][string[]]$Engine = @('excel','dax'),
    [string]$Server,
    [string]$TomAssembly,
    [string]$AdomdAssembly
)
$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'A native Windows test host is required' }
if ('dax' -in $Engine -and (!$Server -or !(Test-Path -LiteralPath $TomAssembly) -or !(Test-Path -LiteralPath $AdomdAssembly))) {
    throw 'DAX requires an authorized local Analysis Services instance and installed TOM/ADOMD assembly paths'
}
function Invoke-CheckedPython([string[]]$Arguments) {
    & python -X utf8 @Arguments
    if ($LASTEXITCODE -ne 0) { throw ('Python verification failed: '+$Arguments[0]) }
}
Invoke-CheckedPython @('recipes/gen_recipes.py','--emit-candidates','--out','recipes/out')
Invoke-CheckedPython @('tools/desktop_acceptance.py','--bundle','recipes/out','--scope',$Scope,'--plan-only','--out','recipes/out/desktop-case-manifest.json')
$plan = Get-Content -LiteralPath 'recipes/out/desktop-case-manifest.json' -Raw | ConvertFrom-Json
$cards = ($plan.cases.card_id | Sort-Object -Unique) -join ','
foreach ($nativeEngine in $Engine) {
    $arguments = @('recipes/ci/desktop_runner.py','--bundle','recipes/out','--engine',$nativeEngine,'--cards',$cards)
    if ($nativeEngine -eq 'dax') { $arguments += @('--server',$Server,'--tom-assembly',$TomAssembly,'--adomd-assembly',$AdomdAssembly) }
    Invoke-CheckedPython $arguments
    Invoke-CheckedPython @('tools/desktop_acceptance.py','--bundle','recipes/out','--scope',$Scope,'--engine',$nativeEngine,'--report',('recipes/out/profile-report-desktop-'+$nativeEngine+'.json'),'--out',('recipes/out/desktop-acceptance-'+$nativeEngine+'.json'))
}
Write-Output 'Requested native scope passed. Retain original reports, candidate commit, host/runtime details and actual verifier record.'
