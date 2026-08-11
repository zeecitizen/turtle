# ================================================================
#  Turtle Trader — MT5 Window Screenshot
#  Tries to capture just the MT5 window, falls back to full screen
#  Usage: powershell -File screenshot.ps1
#         powershell -File screenshot.ps1 -OutPath "C:\tmp\mt5.png"
# ================================================================

param(
    [string]$OutPath = "C:\tmp\mt5_monitor.png"
)

# Ensure output directory exists
$dir = Split-Path $OutPath
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }

Add-Type -AssemblyName System.Drawing, System.Windows.Forms

# Windows API for window rect + foreground focus
Add-Type @"
using System;
using System.Drawing;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    public struct RECT { public int Left, Top, Right, Bottom; }
}
"@

# Find MT5 process
$mt5 = Get-Process | Where-Object {
    $_.MainWindowTitle -like "*MetaTrader*" -or
    $_.MainWindowTitle -like "*Blueberry*" -or
    $_.ProcessName -like "*terminal*"
} | Select-Object -First 1

$captured = $false

if ($mt5 -and $mt5.MainWindowHandle -ne [IntPtr]::Zero) {
    try {
        # Restore + bring to front
        [Win32]::ShowWindow($mt5.MainWindowHandle, 9) | Out-Null   # SW_RESTORE
        [Win32]::SetForegroundWindow($mt5.MainWindowHandle) | Out-Null
        Start-Sleep -Milliseconds 400

        $rect = New-Object Win32+RECT
        [Win32]::GetWindowRect($mt5.MainWindowHandle, [ref]$rect) | Out-Null
        $w = $rect.Right  - $rect.Left
        $h = $rect.Bottom - $rect.Top

        if ($w -gt 100 -and $h -gt 100) {
            $bmp = New-Object System.Drawing.Bitmap($w, $h)
            $g   = [System.Drawing.Graphics]::FromImage($bmp)
            $g.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bmp.Size)
            $bmp.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
            $g.Dispose(); $bmp.Dispose()
            Write-Host "MT5 window captured ($w x $h) → $OutPath"
            $captured = $true
        }
    } catch {
        Write-Host "Window capture failed: $_"
    }
}

if (-not $captured) {
    # Full screen fallback
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
    $g   = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen(0, 0, 0, 0, $bmp.Size)
    $bmp.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    Write-Host "Full screen captured ($($screen.Width) x $($screen.Height)) → $OutPath"
}
