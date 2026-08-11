# bootstrap/lib/step_launch_mt5.ps1
# Ensures MT5 terminal64.exe is running.
# If already running: success. If not: attempt to launch.

function Invoke-StepLaunchMT5 {
    $mt5Exe = "C:\Program Files\MetaTrader 5\terminal64.exe"

    # Already running?
    $proc = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
    if ($proc) {
        return @{ success = $true; summary = "MT5 already running (PID $($proc.Id))" }
    }

    # Find executable
    if (-not (Test-Path $mt5Exe)) {
        # Try common alternate locations
        $candidates = @(
            "C:\Program Files\MetaTrader 5\terminal64.exe",
            "C:\MT5\terminal64.exe",
            "$env:LOCALAPPDATA\Programs\MetaTrader 5\terminal64.exe"
        )
        $mt5Exe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    }

    if (-not $mt5Exe) {
        return @{ success = $false; reason = "terminal64.exe not found — install MT5 first" }
    }

    try {
        Start-Process $mt5Exe
        # Wait up to 15s for the process to appear
        $waited = 0
        do {
            Start-Sleep -Milliseconds 500
            $waited += 500
            $proc = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
        } while (-not $proc -and $waited -lt 15000)

        if ($proc) {
            return @{ success = $true; summary = "MT5 launched (PID $($proc.Id))" }
        } else {
            return @{ success = $false; reason = "MT5 process didn't appear within 15s after launch" }
        }
    }
    catch {
        return @{ success = $false; reason = "Failed to launch MT5: $($_.Exception.Message)" }
    }
}
