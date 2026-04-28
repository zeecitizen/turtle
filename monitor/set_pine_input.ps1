# set_pine_input.ps1 — Resolve a Pine input name to its index and print the MCP call needed
# Does NOT call MCP directly (Claude must do that). Use as a safety layer to avoid
# writing wrong in_XX indices manually.
#
# Usage: powershell -ExecutionPolicy Bypass -File monitor\set_pine_input.ps1 -Name iExHSL -Value 10
#        powershell -ExecutionPolicy Bypass -File monitor\set_pine_input.ps1 -Name iExHSL -Value 10 -LivePineVersion 189.0

param(
    [Parameter(Mandatory)][string]$Name,
    [Parameter(Mandatory)]$Value,
    [string]$LivePineVersion = "",
    [string]$EntityId = "B8A8LH"
)

$mapPath = Join-Path $PSScriptRoot "..\pine\inputs_map.json"
if (-not (Test-Path $mapPath)) {
    Write-Error "inputs_map.json not found at: $mapPath"
    exit 1
}

$map = Get-Content $mapPath -Raw | ConvertFrom-Json

# Version guard — fail loudly on mismatch, never silently guess
if ($LivePineVersion -ne "" -and $LivePineVersion -ne $map.pine_version) {
    Write-Error ""
    Write-Error "VERSION MISMATCH — REFUSING TO PROCEED"
    Write-Error "  Map pine_version : $($map.pine_version)"
    Write-Error "  Live pine_version: $LivePineVersion"
    Write-Error "  Indices may have shifted since map was built. Update inputs_map.json first."
    exit 2
}

$inp = $map.inputs.$Name
if (-not $inp) {
    $available = ($map.inputs.PSObject.Properties.Name | Sort-Object) -join ", "
    Write-Error "Unknown input name: '$Name'"
    Write-Error "Available: $available"
    exit 1
}

# Type validation
$ok = $true
switch ($inp.type) {
    "int"   { if ($Value -notmatch '^-?\d+$') { Write-Error "Type mismatch: '$Name' is int, got '$Value'"; $ok = $false } }
    "float" { if ($Value -notmatch '^-?\d+(\.\d+)?$') { Write-Error "Type mismatch: '$Name' is float, got '$Value'"; $ok = $false } }
    "bool"  { if ($Value -notin @("true","false","0","1")) { Write-Error "Type mismatch: '$Name' is bool, got '$Value'"; $ok = $false } }
}
if (-not $ok) { exit 1 }

# Minval check
if ($inp.minval -and [double]$Value -lt [double]$inp.minval) {
    Write-Error "Value $Value is below minval $($inp.minval) for '$Name'"
    exit 1
}

Write-Host ""
Write-Host "Input resolved:"
Write-Host "  Name  : $Name"
Write-Host "  Index : $($inp.index)"
Write-Host "  Value : $Value (was default: $($inp.default))"
Write-Host "  Desc  : $($inp.desc)"
Write-Host ""
Write-Host "Paste this into Claude to apply:"
Write-Host "  indicator_set_inputs(entity_id='$EntityId', inputs={'$($inp.index)': $Value})"
Write-Host ""
Write-Host "WARNING: This prints the call — it does NOT apply it. Claude must execute the MCP call."
