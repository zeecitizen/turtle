# run_rig.ps1 - compile + run one Strategy Tester pass on the portable Prime XBT test copy.
#   powershell -File mt5\run_rig.ps1 -Ea RandomTouch -Inputs "InpTargetUSD=1;InpExtraBars=1" -Exec -1
# Never touches the live terminal: C:\mt5_rig_pxbt is a separate portable copy with its own
# data folder. Exec: -1 random delay, 0 no delay, N = fixed N ms. Model 4 = real ticks.
param(
  [string]$Ea = "RandomTouch",
  [string]$Inputs = "",
  [int]$Exec = -1,
  [string]$From = "2026.09.28",
  [string]$To = "2026.10.08",
  [string]$Symbol = "XAUUSDp",
  [string]$Grep = "RANDOMTOUCH",
  [string]$Rig = "C:\mt5_rig_pxbt"   # C:\mt5_rig_bb = Blueberry
)
$rig = $Rig
Copy-Item "C:\Users\zeesh\turtle\mt5\$Ea.mq5" "$rig\MQL5\Experts\$Ea.mq5" -Force
$c = Start-Process "$rig\MetaEditor64.exe" -ArgumentList "/portable", "/compile:`"$rig\MQL5\Experts\$Ea.mq5`"", "/log:`"$rig\compile.log`"" -Wait -PassThru
$res = (Get-Content "$rig\compile.log" -Encoding Unicode | Select-String "Result:").Line
if ($res -notmatch "0 errors") { Get-Content "$rig\compile.log" -Encoding Unicode | Select-String "error"; exit 1 }
$ti = ""
if ($Inputs) {
  $ti = "[TesterInputs]`r`n"
  foreach ($kv in $Inputs.Split(";")) { $k, $v = $kv.Split("="); $ti += "$k=$v||$v||0||$v||N`r`n" }
}
$ini = "[Tester]`r`nExpert=$Ea`r`nSymbol=$Symbol`r`nPeriod=M1`r`nModel=4`r`nFromDate=$From`r`nToDate=$To`r`nDeposit=10000`r`nCurrency=USD`r`nLeverage=1:500`r`nExecutionMode=$Exec`r`nOptimization=0`r`nReport=${Ea}_report`r`nReplaceReport=1`r`nShutdownTerminal=1`r`nVisual=0`r`n$ti"
Set-Content "$rig\run.ini" $ini -Encoding Unicode
$p = Start-Process "$rig\terminal64.exe" -ArgumentList "/portable", "/config:`"$rig\run.ini`"" -PassThru
if (-not $p.WaitForExit(1800000)) { "timeout"; exit 2 }
$lg = Get-ChildItem "$rig\Tester\logs" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Get-Content $lg.FullName -Encoding Unicode | Select-String $Grep | Select-Object -Last 4 | ForEach-Object { ($_.Line -split "\t")[-1] }
