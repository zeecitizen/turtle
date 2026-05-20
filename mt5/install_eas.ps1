# ===================================================================
# install_eas.ps1 - Auto-install Shano EAs into all MT5 terminals
# ===================================================================
# Copies TurtleTradeLogger.mq5 + ShanoExitManager.mq5 to every MT5
# terminal's MQL5\Experts\ folder, then compiles them.
#
# Crash-safe: every step is wrapped in try/catch.
# Reports what worked and what didn't, then exits cleanly.
# ===================================================================

$ErrorActionPreference = "Continue"

$RepoRoot   = "C:\Users\zeesh\Documents\GitHub\turtle"
$SourceDir  = Join-Path $RepoRoot "mt5"
$LogFile    = Join-Path $SourceDir "install_eas.log"

$EAs = @(
    "TurtleTradeLogger.mq5",
    "ShanoExitManager.mq5",
    "ShanoTickLogger.mq5",
    "UhvNativeTrader.mq5",
    "UhvSweepExhaustion.mq5",
    "UhvSweepDiag.mq5",
    "S3Trader.mq5",
    "S1Trader.mq5",
    "BtcS3M30Trader.mq5",
    "NsndTrader.mq5",
    "ExportFeb11Bars.mq5",
    "ExportRecentBars.mq5"
)

$failures   = @()
$successes  = @()

function Log($msg) {
    $line = "[$(Get-Date -Format 'HH:mm:ss')] $msg"
    Write-Host $line
    try { Add-Content -Path $LogFile -Value $line -ErrorAction SilentlyContinue } catch {}
}

function Report-Failure($what, $why) {
    $script:failures += [PSCustomObject]@{ What = $what; Why = $why }
    Log "  [SKIP] ${what}: ${why}"
}

function Report-Success($what) {
    $script:successes += $what
    Log "  [OK]   $what"
}

Log "===================================================="
Log "Shano EA Installer starting"
Log "===================================================="

# --- Step 1: Validate source files ---
$sourceMissing = $false
foreach ($ea in $EAs) {
    $src = Join-Path $SourceDir $ea
    if (-not (Test-Path $src)) {
        Report-Failure "Source file: $ea" "Not found at $src"
        $sourceMissing = $true
    }
}
if ($sourceMissing) {
    Log "ERROR: Source files missing - cannot continue"
    Log "Make sure both .mq5 files exist in $SourceDir"
    exit 0
}

# --- Step 2: Find MT5 terminal folders ---
$mt5Root = Join-Path $env:APPDATA "MetaQuotes\Terminal"
$terminals = @()

if (-not (Test-Path $mt5Root)) {
    Report-Failure "MT5 detection" "No $mt5Root folder - MT5 may not be installed"
} else {
    try {
        $terminals = Get-ChildItem -Path $mt5Root -Directory -ErrorAction Stop | Where-Object {
            $_.Name -match '^[0-9A-F]{32}$' -and (Test-Path (Join-Path $_.FullName "MQL5\Experts"))
        }
    } catch {
        Report-Failure "MT5 terminal scan" "$_"
    }
}

if ($terminals.Count -eq 0) {
    Report-Failure "MT5 terminals" "No terminal folders found with MQL5\Experts directory"
    Log ""
    Log "==== SUMMARY ===="
    Log "Could not find any MT5 installation. Skipping copy + compile."
    Log "Install MT5 first, run it once to create the terminal data folder, then re-run."
    Log "================="
    exit 0
}

Log "Found $($terminals.Count) MT5 terminal(s)"

# --- Step 3: Find MetaEditor for compilation ---
$editorPaths = @(
    "C:\Program Files\MetaTrader 5\metaeditor64.exe",
    "C:\Program Files (x86)\MetaTrader 5\metaeditor64.exe",
    "C:\Program Files\Blueberry Markets MetaTrader 5\metaeditor64.exe",
    "C:\Program Files (x86)\Blueberry Markets MetaTrader 5\metaeditor64.exe",
    "C:\Program Files\BlueberryMarkets MetaTrader 5\metaeditor64.exe"
)
$metaEditor = $null
foreach ($p in $editorPaths) {
    try {
        if (Test-Path $p -ErrorAction SilentlyContinue) {
            $metaEditor = $p
            break
        }
    } catch {}
}

if (-not $metaEditor) {
    try {
        $found = Get-ChildItem -Path "C:\Program Files","C:\Program Files (x86)" -Recurse -Filter "metaeditor64.exe" -ErrorAction SilentlyContinue -Force | Select-Object -First 1
        if ($found) { $metaEditor = $found.FullName }
    } catch {}
}

if ($metaEditor) {
    Log "MetaEditor: $metaEditor"
} else {
    Report-Failure "MetaEditor detection" "metaeditor64.exe not found - will copy but not auto-compile"
    Log "  Compile manually: open MetaEditor (F4 in MT5), find each .mq5, press F7"
}

# --- Step 4: Process each terminal ---
$defaultTplSrc = Join-Path $SourceDir "configs\default.tpl"

foreach ($term in $terminals) {
    $expertsDir = Join-Path $term.FullName "MQL5\Experts"
    Log ""
    Log "Terminal: $($term.Name)"
    Log "  Path: $expertsDir"

    if (-not (Test-Path $expertsDir)) {
        Report-Failure "Terminal $($term.Name)" "Experts directory missing"
        continue
    }

    # Install default chart template (auto-attaches UhvSweepExhaustion on every new XAUUSD M1 chart)
    if (Test-Path $defaultTplSrc) {
        $tplDir = Join-Path $term.FullName "MQL5\Profiles\Templates"
        $tplDst = Join-Path $tplDir "default.tpl"
        try {
            if (-not (Test-Path $tplDir)) {
                New-Item -ItemType Directory -Path $tplDir -Force -ErrorAction Stop | Out-Null
            }
            Copy-Item -Path $defaultTplSrc -Destination $tplDst -Force -ErrorAction Stop
            Report-Success "Installed default.tpl -> $($term.Name)"
        } catch {
            Report-Failure "Install default.tpl -> $($term.Name)" "$_"
        }
    }

    foreach ($ea in $EAs) {
        $src = Join-Path $SourceDir $ea
        $dst = Join-Path $expertsDir $ea

        # Copy file
        $copied = $false
        try {
            Copy-Item -Path $src -Destination $dst -Force -ErrorAction Stop
            Report-Success "Copied $ea -> $($term.Name)"
            $copied = $true
        } catch {
            Report-Failure "Copy $ea -> $($term.Name)" "$_"
            continue
        }

        # Compile
        if ($copied -and $metaEditor) {
            $compileLog = $dst -replace '\.mq5$', '.compile.log'
            $ex5        = $dst -replace '\.mq5$', '.ex5'

            try { Remove-Item -Path $ex5 -ErrorAction SilentlyContinue } catch {}

            $compileArgs = @(
                "/compile:`"$dst`"",
                "/log:`"$compileLog`""
            )
            try {
                $proc = Start-Process -FilePath $metaEditor -ArgumentList $compileArgs `
                    -PassThru -Wait -WindowStyle Hidden -ErrorAction Stop
                if (Test-Path $ex5) {
                    Report-Success "Compiled $ea"
                } else {
                    Report-Failure "Compile $ea" "No .ex5 produced (check $compileLog)"
                }
            } catch {
                Report-Failure "Compile $ea" "$_"
            }
        }
    }
}

# --- Final report ---
Log ""
Log "===================================================="
Log "INSTALL SUMMARY"
Log "===================================================="
Log "Successes: $($successes.Count)"
Log "Failures:  $($failures.Count)"

if ($failures.Count -gt 0) {
    Log ""
    Log "Things that didn't work (script kept going):"
    foreach ($f in $failures) {
        Log "  - $($f.What)"
        Log "      Reason: $($f.Why)"
    }
}

Log ""
Log "===================================================="
Log "MANUAL STEPS REMAINING in MT5 (GUI required):"
Log "===================================================="
Log "  1. In MT5: press Ctrl+N to open Navigator panel"
Log "  2. Right-click 'Expert Advisors' -> Refresh"
Log "  3. Drag TurtleTradeLogger onto an XAUUSD chart"
Log "  4. Drag ShanoExitManager onto a separate XAUUSD chart (1min)"
Log "  5. ShanoExitManager input dialog - verify:"
Log "       InpSymbolFilter = XAUUSD"
Log "       InpSellOnly     = true"
Log "       InpProbeConfirm = 0.58"
Log "       InpProbeFail    = 3.00"
Log "  6. Click AutoTrading button in MT5 toolbar (must be GREEN)"
Log "  7. Each EA chart should show a smiley face icon"
Log ""
exit 0
