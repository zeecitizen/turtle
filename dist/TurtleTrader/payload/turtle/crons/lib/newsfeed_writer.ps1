# crons/lib/newsfeed_writer.ps1
# Exports: Write-NewsfeedEntry
# Dot-source this in every cron job: . "$PSScriptRoot\..\lib\newsfeed_writer.ps1"

$_NF_WRITER_ROOT = $PSScriptRoot

function Write-NewsfeedEntry {
    param(
        [Parameter(Mandatory)][string]   $CronId,
        [Parameter(Mandatory)][string]   $CronName,
        [Parameter(Mandatory)][string]   $CronVersion,
        [Parameter(Mandatory)][datetime] $StartedAt,
        [Parameter(Mandatory)]
        [ValidateSet('success','partial','error','aborted')]
        [string]   $Status,
        [Parameter(Mandatory)][string]   $Summary,
        [Parameter(Mandatory)][hashtable]$Result,
        [string[]] $Flags      = @(),
        [bool]     $Actionable = $false,
        [bool]     $Novel      = $false,
        [hashtable]$ErrorInfo  = $null
    )

    $repoRoot    = (Resolve-Path "$_NF_WRITER_ROOT\..\..\").Path
    $newsfeedDir = Join-Path $repoRoot "newsfeed"
    $inboxDir    = Join-Path $newsfeedDir "inbox"
    $stateDir    = Join-Path $repoRoot "crons\state"
    $indexPath   = Join-Path $newsfeedDir "INDEX.json"

    # Ensure directories exist
    foreach ($dir in @($inboxDir, $stateDir)) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }

    # Truncate summary if over 200 chars
    if ($Summary.Length -gt 200) {
        $Summary = $Summary.Substring(0, 197) + "..."
        if ($Flags -notcontains 'SUMMARY_TRUNCATED') { $Flags = $Flags + 'SUMMARY_TRUNCATED' }
    }

    # Validate Status (belt-and-suspenders over ValidateSet)
    if ($Status -notin @('success','partial','error','aborted')) {
        throw "Invalid Status '$Status'. Must be: success, partial, error, aborted"
    }

    # Check result size
    $resultJson = $Result | ConvertTo-Json -Depth 10 -Compress
    if ($resultJson.Length -gt 64000) {
        throw "Result object is $($resultJson.Length) bytes (limit 64000). Write large artifacts to newsfeed/artifacts/<entry_id>/ and reference paths in result."
    }

    # Load/increment run_number (atomic via tmp+rename)
    $stateFile = Join-Path $stateDir "$CronId.json"
    $stateTmp  = "$stateFile.tmp"
    $runNumber = 1
    if (Test-Path $stateFile) {
        try {
            $st = Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
            $runNumber = [int]$st.run_number + 1
        } catch {
            $runNumber = 1
        }
    }
    @{ run_number = $runNumber; cron_id = $CronId; updated_at = [datetime]::UtcNow.ToString("o") } |
        ConvertTo-Json -Compress |
        Out-File -FilePath $stateTmp -Encoding UTF8 -NoNewline
    Move-Item -Path $stateTmp -Destination $stateFile -Force

    # Get prev_entry_id from INDEX cache
    $prevEntryId = $null
    if (Test-Path $indexPath) {
        try {
            $idx = Get-Content $indexPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $prev = $idx.PSObject.Properties[$CronId]
            if ($prev) { $prevEntryId = $prev.Value.entry_id }
        } catch { }
    }

    # Build entry_id: compact ISO8601 + cron_id + zero-padded run
    $finishedAt = [datetime]::UtcNow
    $tsCompact  = $StartedAt.ToUniversalTime().ToString("yyyy-MM-ddTHHmmss.fffZ")
    $runPadded  = $runNumber.ToString("00000")
    $entryId    = "${tsCompact}_${CronId}_${runPadded}"

    # Construct entry
    $entry = [ordered]@{
        entry_id     = $entryId
        cron_id      = $CronId
        cron_name    = $CronName
        cron_version = $CronVersion
        run_number   = $runNumber
        prev_entry_id= $prevEntryId
        started_at   = $StartedAt.ToUniversalTime().ToString("o")
        finished_at  = $finishedAt.ToString("o")
        duration_ms  = [int]($finishedAt - $StartedAt).TotalMilliseconds
        status       = $Status
        summary      = $Summary
        flags        = $Flags
        actionable   = $Actionable
        novel        = $Novel
        result       = $Result
        error        = $ErrorInfo
    }
    $entryJson = $entry | ConvertTo-Json -Depth 10 -Compress

    # Write atomically to inbox (tmp -> rename)
    $inboxFile = Join-Path $inboxDir "$entryId.json"
    $inboxTmp  = "$inboxFile.tmp"
    $entryJson | Out-File -FilePath $inboxTmp -Encoding UTF8 -NoNewline
    Move-Item -Path $inboxTmp -Destination $inboxFile -Force

    # Update INDEX.json with retry (INDEX is a cache; inbox is source of truth)
    $maxRetries = 5
    for ($i = 0; $i -lt $maxRetries; $i++) {
        try {
            $indexTmp   = "$indexPath.tmp"
            $indexTable = @{}
            if (Test-Path $indexPath) {
                $existing = Get-Content $indexPath -Raw -Encoding UTF8 | ConvertFrom-Json
                $existing.PSObject.Properties | ForEach-Object { $indexTable[$_.Name] = $_.Value }
            }
            $indexTable[$CronId] = [ordered]@{
                entry_id   = $entryId
                summary    = $Summary
                status     = $Status
                flags      = $Flags
                finished_at= $finishedAt.ToString("o")
            }
            $indexTable | ConvertTo-Json -Depth 4 -Compress |
                Out-File -FilePath $indexTmp -Encoding UTF8 -NoNewline
            Move-Item -Path $indexTmp -Destination $indexPath -Force
            break
        } catch {
            if ($i -lt $maxRetries - 1) {
                Start-Sleep -Milliseconds 50
            } else {
                Write-Warning "INDEX.json update failed after $maxRetries retries: $_. Inbox entry is authoritative."
            }
        }
    }

    return $entry
}
