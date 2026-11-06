"""Score BOTH live EAs against the 5% DAILY rule - never measured before tonight."""
import sys, subprocess, re
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
import vsisa_lab as V
from vsisa_lab import SHIPPED, PY as PYEXE, SWEEP
from daily_dd import report as dreport
def run(over,ea=None):
    cfg=dict(SHIPPED); cfg.update({k:str(v) for k,v in over.items()})
    cmd=[PYEXE,str(SWEEP),"--backtest","--from",V.FULL[0],"--to",V.FULL[1],"--model","4"]
    if ea: cmd+=["--ea",ea]
    cmd+=["--inputs"," ".join("%s=%s"%kv for kv in cfg.items())]
    out=subprocess.run(cmd,capture_output=True,text=True,errors="replace").stdout
    m=re.findall(r"AXI_bt_\d+",out); return m[-1] if m else None
V124={"InpBigAvg":"1.10","InpBigPct":"0.70"}
PB={"InpBigAvg":"1.10","InpBigPct":"0.70","InpLowVolPct":"5.00","InpFakeBreak":"false",
    "InpTrendTF":"0","InpRatchetStart":"1.50","InpFadePct":"0.70","InpFadeLook":"5",
    "InpMagicNumber":"88202"}
print("THE 5% DAILY RULE on a 10K funded account (limit $500 intraday equity fall)\n")
a=run(V124); print("v1.24 report",a)
if a: dreport("VSISA v1.24 @0.28",a)
b=run(PB,"VSISA_Pullbacks"); print("pullback report",b)
if b: dreport("Pullbacks v1.00 @0.28",b)
