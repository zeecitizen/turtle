# bootstrap/bootstrap.ps1
# Idempotent bootstrap for the full Turtle Trader stack.
# Each phase checks current state before acting. Re-run is always safe.
# Writes a newsfeed entry for each phase (cron_id: "bootstrap").
#
# Design deviation from NEWSFEED_ARCHITECTURE.md:
#   - type:script crons registered to Windows Task Scheduler (not CronCreate)
#   - type:claude_prompt crons written to pending_session_crons.json for Claude to register via CronCreate
#   - manifest.json (not .yaml) since PowerShell has no native YAML parser

param(
    [switch]$SkipTV,      # skip TradingView launch (use if TV already up)
    [switch]$SkipMT5,     # skip MT5 launch
    [switch]$SkipSmoke,   # skip Phase 7 smoke test
    [switch]$Verbose
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$REPO_ROOT   = (Resolve-Path "$PSScriptRoot\..").Path
$BOOTSTRAP_START = [datetime]::UtcNow

. "$REPO_ROOT\crons\lib\newsfeed_writer.ps1"

$PHASE_DURATIONS = @{}

function Write-Phase {
    param([string]$Phase, [string]$Message, [string]$Status = "info")
    $color = switch ($Status) { "ok" {"Green"} "warn"{"Yellow"} "fail"{"Red"} default{"Cyan"} }
    Write-Host "  [Phase $Phase] $Message" -ForegroundColor $color
}

function Complete-Phase {
    param([string]$PhaseId, [string]$Label, [datetime]$PhaseStart, [string]$Summary, [string[]]$Flags=@())
    $ms = [int]([datetime]::UtcNow - $PhaseStart).TotalMilliseconds
    $PHASE_DURATIONS[$PhaseId] = $ms
    Write-NewsfeedEntry `
        -CronId      "bootstrap" `
        -CronName    "Bootstrap" `
        -CronVersion "1.0.0" `
        -StartedAt   $PhaseStart `
        -Status      "success" `
        -Summary     "Phase $PhaseId ($Label): $Summary [${ms}ms]" `
        -Result      @{ phase = $PhaseId; label = $Label; duration_ms = $ms } `
        -Flags       $Flags
    Write-Phase $PhaseId "$Label done (${ms}ms)" "ok"
}

function Fail-Phase {
    param([string]$PhaseId, [string]$Label, [datetime]$PhaseStart, [string]$Reason)
    Write-NewsfeedEntry `
        -CronId      "bootstrap" `
        -CronName    "Bootstrap" `
        -CronVersion "1.0.0" `
        -StartedAt   $PhaseStart `
        -Status      "error" `
        -Summary     "Phase $PhaseId ($Label) FAILED: $Reason" `
        -Result      @{ phase = $PhaseId; label = $Label; reason = $Reason } `
        -ErrorInfo   @{ message = $Reason; stack = $null; retriable = $true }
    Write-Host "  [Phase $PhaseId] FAILED: $Reason" -ForegroundColor Red
    throw "Bootstrap halted at Phase $PhaseId ($Label): $Reason"
}

# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Turtle Trader Bootstrap" -ForegroundColor Cyan
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') UTC" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ─── PHASE 0: Preflight ───────────────────────────────────────────────────────
Write-Phase "0" "Preflight" "info"
$p0Start = [datetime]::UtcNow

# Verify in repo root
if (-not (Test-Path "$REPO_ROOT\crons\manifest.json")) {
    throw "Not in repo root or manifest.json missing. Expected: $REPO_ROOT\crons\manifest.json"
}

# Create required directories
$dirs = @(
    "$REPO_ROOT\newsfeed\inbox",
    "$REPO_ROOT\newsfeed\archive",
    "$REPO_ROOT\newsfeed\artifacts",
    "$REPO_ROOT\crons\state"
)
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

# Load manifest
$manifest = Get-Content "$REPO_ROOT\crons\manifest.json" -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $manifest.crons) { Fail-Phase "0" "Preflight" $p0Start "manifest.json has no crons array" }
$enabledCrons = @($manifest.crons | Where-Object { $_.enabled })
Write-Phase "0" "Manifest loaded: $($enabledCrons.Count) enabled crons" "info"
Complete-Phase "0" "Preflight" $p0Start "dirs ok, manifest loaded ($($enabledCrons.Count) crons)"

# ─── PHASE 1: Mark orphaned runs as aborted ───────────────────────────────────
Write-Phase "1" "Orphan sweep" "info"
$p1Start = [datetime]::UtcNow

$inboxDir  = "$REPO_ROOT\newsfeed\inbox"
$orphans   = Get-ChildItem $inboxDir -Filter "*.json" -ErrorAction SilentlyContinue |
             Where-Object { $_.Name -notlike "*.tmp" } |
             ForEach-Object {
                 try { $e = Get-Content $_.FullName -Raw -Encoding UTF8 | ConvertFrom-Json; if (-not $e.finished_at) { $e } } catch { }
             } | Where-Object { $_ }

$orphanCount = ($orphans | Measure-Object).Count
foreach ($orphan in $orphans) {
    Write-Phase "1" "Marking aborted: $($orphan.entry_id)" "warn"
    Write-NewsfeedEntry `
        -CronId      $orphan.cron_id `
        -CronName    $orphan.cron_name `
        -CronVersion $orphan.cron_version `
        -StartedAt   ([datetime]::Parse($orphan.started_at)) `
        -Status      "aborted" `
        -Summary     "Aborted on bootstrap sweep (process killed before finished_at written)" `
        -Result      @{ original_entry_id = $orphan.entry_id }
}
Complete-Phase "1" "Orphan sweep" $p1Start "marked $orphanCount orphaned runs as aborted"

# ─── PHASE 2: Consolidate old inbox ──────────────────────────────────────────
Write-Phase "2" "Inbox consolidation" "info"
$p2Start = [datetime]::UtcNow
. "$REPO_ROOT\crons\lib\newsfeed_reader.ps1"
Invoke-NewsfeedConsolidation
Complete-Phase "2" "Consolidation" $p2Start "inbox consolidated"

# ─── PHASE 3: MT5 ────────────────────────────────────────────────────────────
Write-Phase "3" "MT5" "info"
$p3Start = [datetime]::UtcNow

if ($SkipMT5) {
    Write-Phase "3" "MT5 skipped (--SkipMT5)" "warn"
    Complete-Phase "3" "MT5" $p3Start "skipped by flag"
} else {
    . "$PSScriptRoot\lib\step_launch_mt5.ps1"
    $mt5Result = Invoke-StepLaunchMT5
    if (-not $mt5Result.success) { Fail-Phase "3" "MT5" $p3Start $mt5Result.reason }
    Complete-Phase "3" "MT5" $p3Start $mt5Result.summary
}

# ─── PHASE 4: TradingView with CDP ───────────────────────────────────────────
Write-Phase "4" "TradingView CDP" "info"
$p4Start = [datetime]::UtcNow

if ($SkipTV) {
    Write-Phase "4" "TV skipped (--SkipTV)" "warn"
    Complete-Phase "4" "TradingView" $p4Start "skipped by flag"
} else {
    . "$PSScriptRoot\lib\step_launch_tv.ps1"
    $tvResult = Invoke-StepLaunchTV
    if (-not $tvResult.success) { Fail-Phase "4" "TradingView" $p4Start $tvResult.reason }
    Complete-Phase "4" "TradingView" $p4Start $tvResult.summary
}

# ─── PHASE 5: EA verification ────────────────────────────────────────────────
Write-Phase "5" "EA verification" "info"
$p5Start = [datetime]::UtcNow
. "$PSScriptRoot\lib\step_verify_ea.ps1"
$eaResult = Invoke-StepVerifyEA
# EA missing is degraded mode, not fatal
Complete-Phase "5" "EA verify" $p5Start $eaResult.summary ($eaResult.flags)

# ─── PHASE 6: Register crons ─────────────────────────────────────────────────
Write-Phase "6" "Cron registration" "info"
$p6Start = [datetime]::UtcNow
. "$PSScriptRoot\lib\step_register_crons.ps1"
$cronResult = Invoke-StepRegisterCrons -Manifest $manifest -RepoRoot $REPO_ROOT
Complete-Phase "6" "Cron registration" $p6Start $cronResult.summary

# ─── PHASE 7: Smoke test ─────────────────────────────────────────────────────
Write-Phase "7" "Smoke test" "info"
$p7Start = [datetime]::UtcNow

if ($SkipSmoke) {
    Write-Phase "7" "Smoke test skipped (--SkipSmoke)" "warn"
    Complete-Phase "7" "Smoke test" $p7Start "skipped by flag"
} else {
    . "$PSScriptRoot\lib\step_smoke_test.ps1"
    $smokeResult = Invoke-StepSmokeTest -Manifest $manifest -RepoRoot $REPO_ROOT
    if (-not $smokeResult.success) { Fail-Phase "7" "Smoke test" $p7Start $smokeResult.reason }
    Complete-Phase "7" "Smoke test" $p7Start $smokeResult.summary
}

# ─── PHASE 8: Regenerate LATEST.md + report ──────────────────────────────────
Write-Phase "8" "LATEST.md" "info"
$p8Start = [datetime]::UtcNow
Update-LatestMarkdown
$totalMs = [int]([datetime]::UtcNow - $BOOTSTRAP_START).TotalMilliseconds

$phaseSummary = ($PHASE_DURATIONS.Keys | Sort-Object | ForEach-Object { "P$_=$($PHASE_DURATIONS[$_])ms" }) -join ' '
Write-NewsfeedEntry `
    -CronId      "bootstrap" `
    -CronName    "Bootstrap" `
    -CronVersion "1.0.0" `
    -StartedAt   $BOOTSTRAP_START `
    -Status      "success" `
    -Summary     "Bootstrap complete in ${totalMs}ms. $phaseSummary" `
    -Result      @{ total_ms = $totalMs; phases = $PHASE_DURATIONS }

# ─── Phase 9: Claude session prompt (optional) ────────────────────────────────
$pendingPath = "$REPO_ROOT\crons\pending_session_crons.json"
if (Test-Path $pendingPath) {
    $pending = Get-Content $pendingPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host ""
    Write-Host "─── Claude session crons pending registration ───────────────" -ForegroundColor Yellow
    Write-Host "  Open Claude Code and say: initialize monitoring" -ForegroundColor Yellow
    Write-Host "  This will register $($pending.crons.Count) session cron(s) via CronCreate." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Bootstrap complete: ${totalMs}ms" -ForegroundColor Green
Write-Host "  See newsfeed/LATEST.md for current stack status." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

# Print top of LATEST.md
$latestMd = "$REPO_ROOT\newsfeed\LATEST.md"
if (Test-Path $latestMd) {
    (Get-Content $latestMd -Encoding UTF8 | Select-Object -First 25) -join "`n" | Write-Host
}
