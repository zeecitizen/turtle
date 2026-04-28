# bootstrap/lib/step_register_crons.ps1
# Registers type:script crons to Windows Task Scheduler.
# Writes pending_session_crons.json for type:claude_prompt crons (Claude registers those via CronCreate).

function Invoke-StepRegisterCrons {
    param(
        [Parameter(Mandatory)][PSCustomObject] $Manifest,
        [Parameter(Mandatory)][string]         $RepoRoot
    )

    $registered  = @()
    $skipped     = @()
    $failed      = @()
    $pending     = @()

    $scriptCrons = @($Manifest.crons | Where-Object { $_.enabled -and $_.type -eq 'script' })
    $promptCrons = @($Manifest.crons | Where-Object { $_.enabled -and $_.type -eq 'claude_prompt' })

    # ─── Task Scheduler: script crons ────────────────────────────────────────
    foreach ($cron in $scriptCrons) {
        $taskName = "TurtleTrader_$($cron.id)"
        $scriptPath = Join-Path $RepoRoot $cron.script

        if (-not (Test-Path $scriptPath)) {
            $failed += "$($cron.id) (script not found: $($cron.script))"
            continue
        }

        # Check if task already exists with matching schedule
        $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($existing) {
            # Verify trigger still matches — if not, delete and re-register
            $existingTrigger = ($existing.Triggers | Select-Object -First 1).RepetitionInterval
            # Simple idempotency check: task exists, assume correct
            $skipped += $cron.id
            continue
        }

        try {
            $action  = New-ScheduledTaskAction `
                -Execute "powershell.exe" `
                -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""

            # Parse cron schedule → Task Scheduler trigger
            $trigger = Convert-CronToTrigger -Schedule $cron.schedule

            $settings = New-ScheduledTaskSettingsSet `
                -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
                -MultipleInstances IgnoreNew `
                -StartWhenAvailable

            $principal = New-ScheduledTaskPrincipal `
                -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
                -LogonType Interactive `
                -RunLevel Highest

            Register-ScheduledTask `
                -TaskName  $taskName `
                -Action    $action `
                -Trigger   $trigger `
                -Settings  $settings `
                -Principal $principal `
                -Force `
                -ErrorAction Stop | Out-Null

            $registered += $cron.id
        }
        catch {
            $failed += "$($cron.id): $($_.Exception.Message.Substring(0,[Math]::Min(80,$_.Exception.Message.Length)))"
        }
    }

    # ─── pending_session_crons.json: claude_prompt crons ─────────────────────
    $pendingPath = Join-Path $RepoRoot "crons\pending_session_crons.json"
    if ($promptCrons.Count -gt 0) {
        $pendingObj = @{
            generated_at = [datetime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
            note         = "Claude: register these via CronCreate when user says 'initialize monitoring'"
            crons        = @($promptCrons | ForEach-Object {
                @{
                    id       = $_.id
                    name     = $_.name
                    schedule = $_.schedule
                    prompt   = $_.prompt_file
                    type     = "claude_prompt"
                }
            })
        }
        $pendingObj | ConvertTo-Json -Depth 5 |
            Set-Content -Path $pendingPath -Encoding UTF8
        $pending += $promptCrons | ForEach-Object { $_.id }
    } elseif (Test-Path $pendingPath) {
        Remove-Item $pendingPath -Force  # no prompt crons → clean up stale file
    }

    # ─── Summary ─────────────────────────────────────────────────────────────
    $parts = @()
    if ($registered) { $parts += "registered: $($registered -join ', ')" }
    if ($skipped)    { $parts += "already-registered: $($skipped -join ', ')" }
    if ($pending)    { $parts += "pending (claude_prompt): $($pending -join ', ')" }
    if ($failed)     { $parts += "FAILED: $($failed -join '; ')" }

    $summary = if ($parts) { $parts -join ' | ' } else { "no crons to register" }

    return @{
        success    = ($failed.Count -eq 0)
        summary    = $summary
        registered = $registered
        skipped    = $skipped
        pending    = $pending
        failed     = $failed
    }
}

# ─── Helper: map cron schedule expression → ScheduledTask trigger ────────────
function Convert-CronToTrigger {
    param([string]$Schedule)

    switch -Regex ($Schedule.Trim()) {
        '^\* \* \* \* \*$' {
            # Every minute
            $t = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 1) -Once -At (Get-Date)
            return $t
        }
        '^\*/(\d+) \* \* \* \*$' {
            $mins = [int]$Matches[1]
            $t = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes $mins) -Once -At (Get-Date)
            return $t
        }
        '^(\d+) (\d+) \* \* \*$' {
            # Daily at HH:MM (UTC approximation — Task Scheduler uses local time)
            $minute = [int]$Matches[1]
            $hour   = [int]$Matches[2]
            # Convert UTC hour to local time for the trigger
            $utcTime   = [datetime]::Today.AddHours($hour).AddMinutes($minute)
            $localTime = [System.TimeZoneInfo]::ConvertTimeFromUtc($utcTime, [System.TimeZoneInfo]::Local)
            return New-ScheduledTaskTrigger -Daily -At $localTime
        }
        default {
            # Fallback: every 15 minutes
            Write-Warning "Unknown cron schedule '$Schedule' — defaulting to 15-minute interval"
            return New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 15) -Once -At (Get-Date)
        }
    }
}
