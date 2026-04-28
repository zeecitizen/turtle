# crons/jobs/_template.ps1
# Template for all script-type crons. Copy, rename, fill in the work section.
# DO NOT modify this file directly.
param()

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\newsfeed_writer.ps1"
. "$PSScriptRoot\..\lib\tz_helper.ps1"

$cronId      = 'my_cron_id'          # CHANGE: match manifest id
$cronName    = 'My Cron Name'        # CHANGE: match manifest name
$cronVersion = '1.0.0'               # CHANGE: match manifest version
$startedAt   = [datetime]::UtcNow

try {
    # ─── WORK SECTION ─────────────────────────────────────────────────────────
    # Do work here. Populate $result and $summary.

    $flags     = @()
    $actionable= $false
    $novel     = $false
    $result    = @{ placeholder = "replace with real data" }
    $summary   = "placeholder summary"

    # Example flag:
    # if ($someCondition) { $flags += 'ALERT_DOWN'; $actionable = $true }

    # ─── END WORK SECTION ─────────────────────────────────────────────────────

    Write-NewsfeedEntry `
        -CronId      $cronId `
        -CronName    $cronName `
        -CronVersion $cronVersion `
        -StartedAt   $startedAt `
        -Status      'success' `
        -Summary     $summary `
        -Result      $result `
        -Flags       $flags `
        -Actionable  $actionable `
        -Novel       $novel

    Write-Host "OK: $summary"
    exit 0
}
catch {
    Write-NewsfeedEntry `
        -CronId      $cronId `
        -CronName    $cronName `
        -CronVersion $cronVersion `
        -StartedAt   $startedAt `
        -Status      'error' `
        -Summary     "Failed: $($_.Exception.Message.Substring(0, [Math]::Min(150, $_.Exception.Message.Length)))" `
        -Result      @{} `
        -ErrorInfo   @{
            message   = $_.Exception.Message
            stack     = $_.ScriptStackTrace
            retriable = $true
        }
    Write-Host "ERROR: $_"
    exit 1
}
