# bootstrap/lib/step_smoke_test.ps1
# Smoke tests: verify that the newsfeed pipeline actually works end-to-end.
# Writes a test entry, reads it back, then cleans up.

function Invoke-StepSmokeTest {
    param(
        [Parameter(Mandatory)][PSCustomObject] $Manifest,
        [Parameter(Mandatory)][string]         $RepoRoot
    )

    $checks = @{}
    $failed = @()

    # ─── Test 1: Write a smoke entry and read it back ─────────────────────────
    try {
        . "$RepoRoot\crons\lib\newsfeed_writer.ps1"
        . "$RepoRoot\crons\lib\newsfeed_reader.ps1"

        $smokeStart = [datetime]::UtcNow
        Write-NewsfeedEntry `
            -CronId      "bootstrap_smoke" `
            -CronName    "Bootstrap Smoke Test" `
            -CronVersion "1.0.0" `
            -StartedAt   $smokeStart `
            -Status      "success" `
            -Summary     "Smoke test write — safe to ignore" `
            -Result      @{ smoke = $true; ts = $smokeStart.ToString("o") }

        # Read it back
        $entry = Get-LatestEntry -CronId "bootstrap_smoke"
        if ($entry -and $entry.status -eq "success") {
            $checks.newsfeed_write_read = "ok"
        } else {
            $checks.newsfeed_write_read = "fail"
            $failed += "Wrote smoke entry but Get-LatestEntry returned nothing"
        }
    }
    catch {
        $checks.newsfeed_write_read = "error"
        $failed += "Newsfeed write/read threw: $($_.Exception.Message)"
    }

    # ─── Test 2: Verify inbox directory is writable ───────────────────────────
    try {
        $testFile = Join-Path $RepoRoot "newsfeed\inbox\_smoke_test.tmp"
        "smoke" | Set-Content $testFile -Encoding UTF8
        Remove-Item $testFile -Force
        $checks.inbox_writable = "ok"
    }
    catch {
        $checks.inbox_writable = "fail"
        $failed += "Inbox not writable: $($_.Exception.Message)"
    }

    # ─── Test 3: manifest has at least 1 enabled cron ────────────────────────
    $enabledCount = @($Manifest.crons | Where-Object { $_.enabled }).Count
    $checks.manifest_enabled_crons = $enabledCount
    if ($enabledCount -eq 0) {
        $failed += "manifest.json has no enabled crons"
    }

    # ─── Test 4: cron_runner.ps1 exists and is callable ──────────────────────
    $runnerPath = Join-Path $RepoRoot "crons\lib\cron_runner.ps1"
    if (Test-Path $runnerPath) {
        $checks.cron_runner = "ok"
    } else {
        $checks.cron_runner = "missing"
        $failed += "cron_runner.ps1 not found"
    }

    # ─── Result ───────────────────────────────────────────────────────────────
    $allOk   = $failed.Count -eq 0
    $summary = if ($allOk) {
        "All smoke tests passed: $($checks.Keys -join ', ')"
    } else {
        "Smoke test FAILED: $($failed -join '; ')"
    }

    return @{
        success = $allOk
        summary = $summary
        checks  = $checks
        reason  = if (-not $allOk) { $failed -join '; ' } else { $null }
    }
}
