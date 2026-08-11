# crons/lib/newsfeed_reader.ps1
# Exports: Get-LatestEntry, Get-RecentEntries, Get-Entries,
#          Invoke-NewsfeedConsolidation, Update-LatestMarkdown, Get-ClaudeBriefing
# Dot-source: . "$PSScriptRoot\..\lib\newsfeed_reader.ps1"

$_NF_READER_ROOT = $PSScriptRoot

function _NF_GetPaths {
    $repoRoot = (Resolve-Path "$_NF_READER_ROOT\..\..\").Path
    @{
        RepoRoot    = $repoRoot
        NewsfeedDir = Join-Path $repoRoot "newsfeed"
        InboxDir    = Join-Path $repoRoot "newsfeed\inbox"
        ArchiveDir  = Join-Path $repoRoot "newsfeed\archive"
        IndexPath   = Join-Path $repoRoot "newsfeed\INDEX.json"
        LatestMd    = Join-Path $repoRoot "newsfeed\LATEST.md"
        ManifestPath= Join-Path $repoRoot "crons\manifest.json"
    }
}

function _NF_ReadEntry([string]$path) {
    if (-not (Test-Path $path)) { return $null }
    try { Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { $null }
}

function _NF_AllInboxEntries {
    $p = _NF_GetPaths
    Get-ChildItem -Path $p.InboxDir -Filter "*.json" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notlike "*.tmp" } |
        ForEach-Object { _NF_ReadEntry $_.FullName } |
        Where-Object { $_ -ne $null }
}

function _NF_AllArchiveEntries([string[]]$days) {
    $p = _NF_GetPaths
    $files = if ($days) {
        $days | ForEach-Object { Join-Path $p.ArchiveDir "$_.jsonl" }
    } else {
        Get-ChildItem -Path $p.ArchiveDir -Filter "*.jsonl" -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty FullName
    }
    foreach ($f in $files) {
        if (Test-Path $f) {
            Get-Content $f -Encoding UTF8 | Where-Object { $_ -ne '' } |
                ForEach-Object { try { $_ | ConvertFrom-Json } catch { } }
        }
    }
}

# ─── Public API ──────────────────────────────────────────────────────────────

function Get-LatestEntry {
    param([Parameter(Mandatory)][string]$CronId)
    $p = _NF_GetPaths
    # Fast path: INDEX.json
    if (Test-Path $p.IndexPath) {
        try {
            $idx = Get-Content $p.IndexPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $hit = $idx.PSObject.Properties[$CronId]
            if ($hit) { return $hit.Value }
        } catch { }
    }
    # Fallback: scan inbox + today's archive
    $today = [datetime]::UtcNow.ToString("yyyy-MM-dd")
    $all   = @(_NF_AllInboxEntries) + @(_NF_AllArchiveEntries @($today))
    $all | Where-Object { $_.cron_id -eq $CronId } |
           Sort-Object { $_.started_at } |
           Select-Object -Last 1
}

function Get-RecentEntries {
    param(
        [int]$Count = 20,
        [datetime]$SinceUtc = ([datetime]::UtcNow.AddHours(-24))
    )
    $today     = [datetime]::UtcNow.ToString("yyyy-MM-dd")
    $yesterday = [datetime]::UtcNow.AddDays(-1).ToString("yyyy-MM-dd")
    $all = @(_NF_AllInboxEntries) + @(_NF_AllArchiveEntries @($today, $yesterday))
    $all | Where-Object {
            try { [datetime]::Parse($_.started_at) -ge $SinceUtc } catch { $false }
          } |
          Sort-Object { $_.started_at } -Descending |
          Select-Object -First $Count
}

function Get-Entries {
    param(
        [string]  $CronId,
        [string]  $Status,
        [string[]]$Flags,
        [datetime]$SinceUtc,
        [datetime]$UntilUtc,
        [int]     $Limit = 100
    )
    $daysNeeded = @([datetime]::UtcNow.ToString("yyyy-MM-dd"))
    if ($SinceUtc) {
        $d = $SinceUtc
        while ($d -le [datetime]::UtcNow) {
            $daysNeeded += $d.ToString("yyyy-MM-dd")
            $d = $d.AddDays(1)
        }
    }
    $daysNeeded = $daysNeeded | Select-Object -Unique

    $all = @(_NF_AllInboxEntries) + @(_NF_AllArchiveEntries $daysNeeded)
    $all | Where-Object {
        if ($CronId -and $_.cron_id -ne $CronId) { return $false }
        if ($Status -and $_.status -ne $Status)   { return $false }
        if ($Flags)  {
            $entryFlags = @($_.flags)
            foreach ($f in $Flags) { if ($f -notin $entryFlags) { return $false } }
        }
        if ($SinceUtc) {
            try { if ([datetime]::Parse($_.started_at) -lt $SinceUtc) { return $false } } catch { return $false }
        }
        if ($UntilUtc) {
            try { if ([datetime]::Parse($_.started_at) -gt $UntilUtc) { return $false } } catch { return $false }
        }
        return $true
    } | Sort-Object { $_.started_at } -Descending | Select-Object -First $Limit
}

function Invoke-NewsfeedConsolidation {
    $p     = _NF_GetPaths
    $today = [datetime]::UtcNow.Date

    $inboxFiles = Get-ChildItem -Path $p.InboxDir -Filter "*.json" -ErrorAction SilentlyContinue |
                  Where-Object { $_.Name -notlike "*.tmp" }

    $byDay = @{}
    foreach ($f in $inboxFiles) {
        try {
            $entry = _NF_ReadEntry $f.FullName
            if (-not $entry) { continue }
            $entryDate = [datetime]::Parse($entry.started_at).ToUniversalTime().Date
            # Keep today's entries in inbox (still hot)
            if ($entryDate -ge $today) { continue }
            $key = $entryDate.ToString("yyyy-MM-dd")
            if (-not $byDay[$key]) { $byDay[$key] = @() }
            $byDay[$key] += @{ file = $f.FullName; entry = $entry }
        } catch { }
    }

    foreach ($day in $byDay.Keys) {
        $archiveFile = Join-Path $p.ArchiveDir "$day.jsonl"
        # Read existing archive entry_ids to avoid duplicates
        $existingIds = @{}
        if (Test-Path $archiveFile) {
            Get-Content $archiveFile -Encoding UTF8 | Where-Object { $_ } |
                ForEach-Object { try { $e = $_ | ConvertFrom-Json; $existingIds[$e.entry_id] = $true } catch { } }
        }
        $toAppend = $byDay[$day] | Where-Object { -not $existingIds[$_.entry.entry_id] }
        if ($toAppend) {
            $toAppend | Sort-Object { $_.entry.started_at } | ForEach-Object {
                ($_.entry | ConvertTo-Json -Depth 10 -Compress) |
                    Add-Content -Path $archiveFile -Encoding UTF8
            }
        }
        # Delete inbox files that are now archived
        $byDay[$day] | ForEach-Object { Remove-Item -Path $_.file -Force -ErrorAction SilentlyContinue }
    }

    Write-Host "Consolidation: moved $($byDay.Values | ForEach-Object { $_.Count } | Measure-Object -Sum | Select-Object -ExpandProperty Sum) entries from inbox to archive"
}

function Update-LatestMarkdown {
    $p   = _NF_GetPaths
    $now = [datetime]::UtcNow

    # Load manifest for cron list
    $cronDefs = @()
    if (Test-Path $p.ManifestPath) {
        try {
            $mf = Get-Content $p.ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $cronDefs = @($mf.crons | Where-Object { $_.enabled })
        } catch { }
    }

    # Get latest per cron
    $rows = foreach ($cron in $cronDefs) {
        $latest = Get-LatestEntry -CronId $cron.id
        if ($latest) {
            $ago = [int]($now - [datetime]::Parse($latest.finished_at)).TotalMinutes
            $statusIcon = switch ($latest.status) {
                'success' { 'OK' }
                'partial' { 'WARN' }
                'error'   { 'ERR' }
                'aborted' { 'ABRT' }
                default   { '?' }
            }
            [ordered]@{ cron=$cron.name; ago="${ago}m ago"; status=$statusIcon; summary=$latest.summary }
        } else {
            [ordered]@{ cron=$cron.name; ago="Never"; status="--"; summary="(awaiting first run)" }
        }
    }

    # Flags raised today
    $todayStart = $now.Date
    $todayEntries = Get-RecentEntries -Count 500 -SinceUtc $todayStart
    $flagLines = $todayEntries |
        Where-Object { @($_.flags).Count -gt 0 } |
        Sort-Object { $_.finished_at } |
        ForEach-Object {
            $t = [datetime]::Parse($_.finished_at).ToString("HH:mm")
            $fs = ($_.flags -join ', ')
            "- $t UTC ``$($_.cron_id)`` → ``$fs``"
        }

    # Recent entries (last 10)
    $recentLines = (Get-RecentEntries -Count 10) | ForEach-Object {
        $t = [datetime]::Parse($_.finished_at).ToString("HH:mm")
        $icon = switch ($_.status) { 'success'{'OK'} 'partial'{'WARN'} 'error'{'ERR'} default{'?'} }
        "### [$t UTC] $($_.cron_name) $icon`n$($_.summary)"
    }

    # Render
    $tableRows = $rows | ForEach-Object { "| $($_.cron) | $($_.ago) | $($_.status) | $($_.summary) |" }
    $md = @"
# Turtle Trader Newsfeed — Latest

_Generated $($now.ToString("yyyy-MM-dd HH:mm")) UTC_

## Active crons ($($cronDefs.Count))

| Cron | Last ran | Status | Summary |
|------|----------|--------|---------|
$($tableRows -join "`n")

## Flags raised today

$(if ($flagLines) { $flagLines -join "`n" } else { "_None_" })

## Recent entries (last 10)

$($recentLines -join "`n`n")
"@
    $md | Out-File -FilePath $p.LatestMd -Encoding UTF8
    Write-Host "LATEST.md updated."
}

function Get-ClaudeBriefing {
    param([int]$MaxTokensApprox = 1000)

    $p   = _NF_GetPaths
    $now = [datetime]::UtcNow

    # Load manifest
    $cronDefs = @()
    if (Test-Path $p.ManifestPath) {
        try {
            $mf = Get-Content $p.ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $cronDefs = @($mf.crons | Where-Object { $_.enabled })
        } catch { }
    }

    $lines = @("Turtle newsfeed as of $($now.ToString('yyyy-MM-dd HH:mm')) UTC:", "", "Last from each cron:")
    foreach ($cron in $cronDefs) {
        $latest = Get-LatestEntry -CronId $cron.id
        if ($latest) {
            $ago  = [int]($now - [datetime]::Parse($latest.finished_at)).TotalMinutes
            $icon = switch ($latest.status) { 'success'{'OK'} 'partial'{'WARN'} 'error'{'ERR'} default{'?'} }
            $lines += "* $($cron.name) (${ago}m ago, $icon): $($latest.summary)"
        } else {
            $lines += "* $($cron.name): (never run)"
        }
    }

    # Flags in last 24h
    $since24h    = $now.AddHours(-24)
    $flagEntries = Get-Entries -SinceUtc $since24h -Limit 200 |
                   Where-Object { @($_.flags).Count -gt 0 }
    $lines += @("", "Flags raised in last 24h:")
    if ($flagEntries) {
        foreach ($e in $flagEntries | Sort-Object { $_.finished_at }) {
            $t  = [datetime]::Parse($e.finished_at).ToString("HH:mm")
            $fs = $e.flags -join ', '
            $lines += "* $t $($e.cron_id) $fs -- $($e.summary)"
        }
    } else { $lines += "* None" }

    # Error crons
    $errCrons = $cronDefs | Where-Object {
        $l = Get-LatestEntry -CronId $_.id
        $l -and $l.status -eq 'error'
    } | ForEach-Object { $_.id }
    $lines += ""
    $lines += "Crons with errors in last run: $(if ($errCrons) { $errCrons -join ', ' } else { 'none' })"

    # Overdue crons (not run in >2x schedule)
    $lines += "Crons not run recently: $(
        ($cronDefs | Where-Object {
            $l = Get-LatestEntry -CronId $_.id
            -not $l
        } | ForEach-Object { $_.id }) -join ', ' | Where-Object { $_ }
        if (-not $_) { 'none' }
    )"

    $briefing = $lines -join "`n"

    # Rough token cap (4 chars ~ 1 token)
    $charCap = $MaxTokensApprox * 4
    if ($briefing.Length -gt $charCap) {
        $briefing = $briefing.Substring(0, $charCap) + "`n... (truncated)"
    }

    return $briefing
}
