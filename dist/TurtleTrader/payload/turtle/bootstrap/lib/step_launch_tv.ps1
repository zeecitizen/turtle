# bootstrap/lib/step_launch_tv.ps1
# Ensures TradingView Desktop is running with CDP enabled on port 9222.
# If CDP already reachable: success. If Chrome/TV process exists but no CDP: warn.
# If nothing: launch with --remote-debugging-port=9222.

function Invoke-StepLaunchTV {
    # 1. Is CDP already up?
    $cdpOk = Test-TvCdp
    if ($cdpOk) {
        return @{ success = $true; summary = "TV CDP already reachable (localhost:9222)" }
    }

    # 2. Is a Chrome/TV process running without CDP?
    $tvProc = Get-Process -Name "chrome","tradingview" -ErrorAction SilentlyContinue |
              Where-Object { $_.MainWindowTitle -match "TradingView" } |
              Select-Object -First 1
    if ($tvProc) {
        # Running but no CDP - likely launched without flag. Warn but dont fail.
        return @{
            success = $false
            reason  = "TradingView appears running (PID $($tvProc.Id)) but CDP not reachable. " +
                      "Close TV and re-run bootstrap, or use -SkipTV if session is already active."
        }
    }

    # 3a. Try UWP/AppX activation first (Microsoft Store version)
    $appxPkg = Get-AppxPackage -Name "TradingView.Desktop" -ErrorAction SilentlyContinue
    if ($appxPkg) {
        $appId = "TradingView.Desktop_n534cwy3pjxzj!TradingView.Desktop"
        try {
            Start-Process "shell:AppsFolder\$appId" -ArgumentList "--remote-debugging-port=9222"
            $waited = 0
            do {
                Start-Sleep -Milliseconds 1000
                $waited += 1000
                $cdpOk = Test-TvCdp
            } while (-not $cdpOk -and $waited -lt 30000)
            if ($cdpOk) {
                return @{ success = $true; summary = "TV (UWP) launched with CDP on 9222" }
            }
        } catch {}
    }

    # 3b. Fallback: traditional desktop installer .exe
    $tvExe = Find-TradingViewExe
    if (-not $tvExe) {
        return @{
            success = $false
            reason  = "TradingView Desktop not found (no AppX, no installer .exe)."
        }
    }

    try {
        Start-Process $tvExe -ArgumentList "--remote-debugging-port=9222"
        # Wait up to 20s for CDP to come up
        $waited = 0
        do {
            Start-Sleep -Milliseconds 1000
            $waited += 1000
            $cdpOk = Test-TvCdp
        } while (-not $cdpOk -and $waited -lt 20000)

        if ($cdpOk) {
            return @{ success = $true; summary = "TV launched with CDP (localhost:9222)" }
        } else {
            return @{ success = $false; reason = "TV launched but CDP not reachable after 20s - may still be loading" }
        }
    }
    catch {
        return @{ success = $false; reason = "Failed to launch TV: $($_.Exception.Message)" }
    }
}

function Test-TvCdp {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:9222/json/version" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        return $resp.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Find-TradingViewExe {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\TradingView\TradingView.exe",
        "$env:ProgramFiles\TradingView\TradingView.exe",
        "$env:LOCALAPPDATA\TradingView\TradingView.exe"
    )
    $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($found) { return $found }

    # Try UWP/AppX install (Microsoft Store version)
    try {
        $pkg = Get-AppxPackage -Name "TradingView.Desktop" -ErrorAction SilentlyContinue
        if ($pkg) {
            $appxExe = Join-Path $pkg.InstallLocation "TradingView.exe"
            if (Test-Path $appxExe) { return $appxExe }
            $hunt = Get-ChildItem -Path $pkg.InstallLocation -Filter "*TradingView*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($hunt) { return $hunt.FullName }
        }
    } catch {}

    # Chrome PWA fallback (last resort)
    $chrome = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    return $chrome
}
