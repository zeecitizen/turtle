"""Ship-verify VSISA_Pullbacks v1.00 - the NEW binary must reproduce the sweep.
Expected: 1,864 trades, +$28,757, 42% WR, $3,340 DD, halves 5.73 / 3.45."""
import sys, subprocess, re
sys.path.insert(0,'monitor/strategy_lab'); sys.stdout.reconfigure(encoding='utf-8')
import vsisa_lab as V
from vsisa_lab import stats, SHIPPED, PY as PYEXE, SWEEP
def run_pb(over,frm,to):
    cfg=dict(SHIPPED); cfg.update({k:str(v) for k,v in over.items()})
    out=subprocess.run([PYEXE,str(SWEEP),"--backtest","--from",frm,"--to",to,"--model","4",
                        "--ea","VSISA_Pullbacks",
                        "--inputs"," ".join("%s=%s"%kv for kv in cfg.items())],
                       capture_output=True,text=True,errors="replace").stdout
    m=re.findall(r"AXI_bt_\d+",out); return m[-1] if m else None
PB={"InpBigAvg":"1.10","InpBigPct":"0.70","InpLowVolPct":"5.00","InpFakeBreak":"false",
    "InpTrendTF":"0","InpRatchetStart":"1.50","InpFadePct":"0.70","InpFadeLook":"5",
    "InpMagicNumber":"88202"}
for tag,w in (("FULL",V.FULL),("H1",V.H1),("H2",V.H2)):
    r=run_pb(PB,*w); s=stats(r) if r else None
    print("%-5s %s"%(tag,("n %4d  net %+8.0f  wr %2.0f%%  dd %6.0f  ratio %5.2f"
          %(s['n'],s['net'],s['wr'],s['dd'],s['ratio'])) if s else "NO TRADES"),flush=True)
print("expect FULL n 1864 net +28757 wr 42% dd 3340 ratio 8.61 | halves 5.73 / 3.45")
