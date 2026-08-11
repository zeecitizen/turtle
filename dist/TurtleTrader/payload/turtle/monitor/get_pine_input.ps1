# get_pine_input.ps1 — Look up a Pine input by name, return index + current value from alert
# Usage: powershell -ExecutionPolicy Bypass -File monitor\get_pine_input.ps1 -Name iExHSL
#        powershell -ExecutionPolicy Bypass -File monitor\get_pine_input.ps1 -Name iExHSL -LivePineVersion 189.0

param(
    [Parameter(Mandatory)][string]$Name,
    [string]$LivePineVersion = ""
)

$mapPath = Join-Path $PSScriptRoot "..\pine\inputs_map.json"
if (-not (Test-Path $mapPath)) {
    Write-Error "inputs_map.json not found at: $mapPath"
    exit 1
}

$map = Get-Content $mapPath -Raw | ConvertFrom-Json

# Version guard
if ($LivePineVersion -ne "" -and $LivePineVersion -ne $map.pine_version) {
    Write-Error "VERSION MISMATCH: map is for v$($map.pine_version), live alert is v$LivePineVersion. Indices may have shifted. Update inputs_map.json first."
    exit 2
}

$inp = $map.inputs.$Name
if (-not $inp) {
    $available = ($map.inputs.PSObject.Properties.Name | Sort-Object) -join ", "
    Write-Error "Unknown input name: '$Name'. Available: $available"
    exit 1
}

Write-Host "Name:    $Name"
Write-Host "Index:   $($inp.index)"
Write-Host "Type:    $($inp.type)"
Write-Host "Default: $($inp.default)"
Write-Host "Desc:    $($inp.desc)"
if ($inp.minval) { Write-Host "Minval:  $($inp.minval)" }
if ($inp.step)   { Write-Host "Step:    $($inp.step)" }
Write-Host ""
Write-Host "To read live value: check alert_list output for $($inp.index)"
Write-Host "To set (via Claude): indicator_set_inputs(entity_id='B8A8LH', inputs={'$($inp.index)': <value>})"
