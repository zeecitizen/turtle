"""Run Saad_strategy_15min (v1.18 = v1.17 trades) with its per-trade CSV log on, or BarDump, on one rig.
    py run_saad_tradelog.py <rig> saad|bars <symbol> <from> <to> <tag>
Copies the CSV(s) from Common\\Files into testing/."""
import sys, time, shutil
from pathlib import Path
import axi_rig

rig, what, sym, frm, to, tag = sys.argv[1:7]
axi_rig.use(rig)
C = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
T = Path(r"C:\Users\zeesh\turtle\testing")
t0 = time.time()
if what == "saad":
    r = axi_rig.run("Saad_tradelog", sym, "M15", {"InpLots": 1.0, "InpLog": "false", "InpLogCsv": "true", "InpDraw": "false"},
                    frm=frm, to=to, exec_mode=200, tag=f"saadlog_{tag}", deposit=25000, timeout=7200)
    f = C / f"Saad15_trades_{sym}_88302_tester.csv"
    dst = T / f"saad_trades_{tag}.csv"
else:
    r = axi_rig.run("BarDump", sym, "M1", {"InpTag": int(tag)}, frm=frm, to=to, exec_mode=200, tag=f"bardump_{tag}", deposit=10000, timeout=7200)
    f = C / f"bardump_{tag}_M15.csv"
    dst = T / f"bars_M15_{tag}.csv"
print({k: r.get(k) for k in ("net", "trades", "wr", "quality", "secs", "error")})
if f.exists() and f.stat().st_mtime > t0:
    shutil.copy(f, dst); print("copied", dst.name, sum(1 for _ in open(dst)) - 1, "rows")
else:
    print("NO OUTPUT FILE", f)
