# install.ps1 - install Claude EA as a proper Windows application.
#
# PyInstaller has no ARM64 wheel, so instead of a packaged .exe this registers the app the
# way Windows actually surfaces software: a Start-menu entry, a desktop shortcut, an
# optional run-at-logon task, and an uninstaller. Same result for the user, and it works on
# this machine today.
#
#   Install :  powershell -ExecutionPolicy Bypass -File gui\install.ps1
#   Remove  :  powershell -ExecutionPolicy Bypass -File gui\install.ps1 -Uninstall
#   No autostart:  ... -File gui\install.ps1 -NoAutoStart

param([switch]$Uninstall, [switch]$NoAutoStart)

$ErrorActionPreference = "Stop"
$AppName   = "Turtle Desktop"
$Repo      = Split-Path -Parent $PSScriptRoot
$Gui       = Join-Path $PSScriptRoot "claude_ea_gui.py"
$Icon      = Join-Path $PSScriptRoot "turtle.ico"
$StartDir  = Join-Path ([Environment]::GetFolderPath('Programs')) $AppName
$Desktop   = [Environment]::GetFolderPath('Desktop')
$TaskName  = "TurtleDesktop_AutoStart"

function Find-Pythonw {
    $c = @(
        "C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\pythonw.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\pythonw.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe"
    )
    foreach ($p in $c) { if (Test-Path $p) { return $p } }
    $g = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($g) { return $g.Source }
    throw "pythonw.exe not found - install Python 3.12+ first."
}

function New-Shortcut($Path, $Target, $ArgStr, $WorkDir, $Desc) {
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut($Path)
    $s.TargetPath = $Target
    $s.Arguments = $ArgStr
    $s.WorkingDirectory = $WorkDir
    $s.Description = $Desc
    if (Test-Path $Icon) { $s.IconLocation = $Icon }
    $s.Save()
}

# --------------------------- uninstall ---------------------------
if ($Uninstall) {
    Write-Host "Removing $AppName ..." -ForegroundColor Yellow
    if (Test-Path $StartDir) { Remove-Item $StartDir -Recurse -Force }
    foreach ($d in @((Join-Path $Desktop "$AppName.lnk"),
                     (Join-Path ([Environment]::GetFolderPath('Startup')) "$AppName.lnk"))) {
        if (Test-Path $d) { Remove-Item $d -Force }
    }
    $ErrorActionPreference = "Continue"
    cmd /c "schtasks /Delete /TN $TaskName /F" 2>&1 | Out-Null
    Write-Host "Uninstalled. (Your repo and data were not touched.)" -ForegroundColor Green
    exit 0
}

# --------------------------- preflight ---------------------------
Write-Host "`n  Installing $AppName" -ForegroundColor Cyan
Write-Host "  ================================`n"

if (-not (Test-Path $Gui)) { throw "GUI not found at $Gui - run this from the repo." }
$Pythonw = Find-Pythonw
Write-Host "  [ok] python : $Pythonw"

$Py = $Pythonw -replace "pythonw\.exe$", "python.exe"
$missing = @()
foreach ($m in @("tkinter", "websockets", "matplotlib")) {
    & $Py -c "import $m" 2>$null
    if ($LASTEXITCODE -ne 0) { $missing += $m }
}
if ($missing.Count -gt 0) {
    Write-Host "  [!!] missing modules: $($missing -join ', ')" -ForegroundColor Yellow
    Write-Host "       fix with:  `"$Py`" -m pip install $($missing -join ' ')" -ForegroundColor Yellow
} else {
    Write-Host "  [ok] dependencies present"
}

# --------------------------- shortcuts ---------------------------
New-Item -ItemType Directory -Force -Path $StartDir | Out-Null
New-Shortcut (Join-Path $StartDir "$AppName.lnk") $Pythonw "`"$Gui`"" $Repo "Turtle Desktop - vision-driven trading"
New-Shortcut (Join-Path $StartDir "Turtle Desktop Playbook.lnk") (Join-Path $Repo "CLAUDE_REALTIME_EA.md") "" $Repo "The playbook Claude reads to resume trading"
New-Shortcut (Join-Path $Desktop "$AppName.lnk") $Pythonw "`"$Gui`"" $Repo "Turtle Desktop - vision-driven trading"
Write-Host "  [ok] Start menu entry : $StartDir"
Write-Host "  [ok] Desktop shortcut"

# ------------------- run at logon (survives power cuts) -------------------
if (-not $NoAutoStart) {
    # Scheduled Tasks need elevation; the per-user Startup folder does not. Same effect:
    # the panel comes back by itself after a power cut, a restart, or a re-login.
    $StartupDir = [Environment]::GetFolderPath('Startup')
    New-Shortcut (Join-Path $StartupDir "$AppName.lnk") $Pythonw "`"$Gui`"" $Repo "Turtle Desktop (auto-start)"
    Write-Host "  [ok] auto-start registered (Startup folder, no admin needed)"
    Write-Host "       -> after a power cut or restart the panel comes back by itself"
} else {
    Write-Host "  [--] auto-start skipped (-NoAutoStart)"
}

# --------------------------- uninstaller ---------------------------
New-Shortcut (Join-Path $StartDir "Uninstall $AppName.lnk") "powershell.exe" `
    "-ExecutionPolicy Bypass -File `"$PSCommandPath`" -Uninstall" $Repo "Remove Claude EA"

Write-Host "`n  Done. Find `"$AppName`" in the Start menu (or on your desktop).`n" -ForegroundColor Green
