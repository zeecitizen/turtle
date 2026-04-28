# launch_tv.ps1 - Standalone wrapper around step_launch_tv.ps1
# Callable directly from startup.bat or any script.

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\lib\step_launch_tv.ps1"

$result = Invoke-StepLaunchTV
if ($result.success) {
    Write-Host "[TV] OK: $($result.summary)"
    exit 0
} else {
    Write-Host "[TV] FAIL: $($result.reason)"
    exit 1
}
