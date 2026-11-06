"""Run bread_lab on one rig.   py run_lab.py <rig> <tag> <from> <to> [tp] [sl]   -> testing/bread_lab_<tag>.csv"""
import sys, shutil, time
from pathlib import Path
import axi_rig
rig, tag, frm, to = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
tp = sys.argv[5] if len(sys.argv) > 5 else "1.0"; sl = sys.argv[6] if len(sys.argv) > 6 else "6.0"
axi_rig.use(rig)
t0 = time.time()
r = axi_rig.run("bread_lab", "XAUUSD_TK", "M1", {"InpLabTag": tag, "InpLabTp": tp, "InpLabSl": sl, "V_InpVerbose": "false"},
                frm=frm, to=to, exec_mode=200, tag=f"lab_{tag}", deposit=100000, timeout=7200)
src = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files") / f"bread_lab_{tag}.csv"
dst = Path(r"C:\Users\zeesh\turtle\testing") / f"bread_lab_{tag}.csv"
if src.exists() and src.stat().st_mtime >= t0:
    shutil.copy(src, dst); print("lab", tag, "rows", sum(1 for _ in open(dst)) - 1, "secs", round(time.time() - t0), "net", r.get("net"))
else:
    print("lab", tag, "NO FILE", r.get("error"), r.get("trades"))
