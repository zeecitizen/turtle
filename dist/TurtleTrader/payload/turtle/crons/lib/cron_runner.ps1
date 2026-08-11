# crons/lib/cron_runner.ps1
# CLI facade over Write-NewsfeedEntry — called by claude_prompt crons at the END of their run.
# Claude invokes this as a shell command; it writes the newsfeed entry and exits.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File crons/lib/cron_runner.ps1 `
#     -CronId      "trading_analysis" `
#     -CronName    "Trading Analysis" `
#     -CronVersion "1.0.0" `
#     -StartedAtUtc "2026-04-20T07:30:00Z" `   # ISO8601 UTC — when Claude started the cron
#     -Status      "success" `
#     -Summary     "No structural drift. 23 signals today, WR on track." `
#     -Flags       "SPIKE_DAY" `                # comma-separated, or empty ""
#     -Actionable  "false" `
#     -Novel       "false" `
#     -ResultJson  '{"signals":23,"wr":0.25}'

param(
    [Parameter(Mandatory)][string]$CronId,
    [Parameter(Mandatory)][string]$CronName,
    [Parameter(Mandatory)][string]$CronVersion,
    [string]$StartedAtUtc = "",           # ISO8601 UTC; defaults to now if omitted
    [Parameter(Mandatory)]
    [ValidateSet("success","partial","error","aborted")]
    [string]$Status,
    [Parameter(Mandatory)][string]$Summary,
    [string]$Flags      = "",             # comma-separated flag codes, or ""
    [string]$Actionable = "false",
    [string]$Novel      = "false",
    [string]$ResultJson = "{}"
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\newsfeed_writer.ps1"

# Parse StartedAt
$startedAt = if ($StartedAtUtc -ne "") {
    [datetime]::Parse($StartedAtUtc).ToUniversalTime()
} else {
    [datetime]::UtcNow
}

# Parse flags
$flagArray = if ($Flags -ne "") {
    $Flags -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
} else { @() }

# Parse booleans
$actionableBool = $Actionable -eq "true"
$novelBool      = $Novel      -eq "true"

# Parse result JSON
$resultTable = @{}
try {
    $parsed = $ResultJson | ConvertFrom-Json
    $parsed.PSObject.Properties | ForEach-Object { $resultTable[$_.Name] = $_.Value }
} catch {
    $resultTable = @{ raw = $ResultJson; parse_error = $_.Exception.Message }
}

try {
    $entry = Write-NewsfeedEntry `
        -CronId      $CronId `
        -CronName    $CronName `
        -CronVersion $CronVersion `
        -StartedAt   $startedAt `
        -Status      $Status `
        -Summary     $Summary `
        -Result      $resultTable `
        -Flags       $flagArray `
        -Actionable  $actionableBool `
        -Novel       $novelBool

    Write-Host "NEWSFEED_WRITTEN: $($entry.entry_id)"
    exit 0
} catch {
    Write-Host "NEWSFEED_ERROR: $_"
    exit 1
}
