"""Verify bread_winner on its OWN defaults (only the shot log switched on, which does not trade).
    py verify_bread.py <rig> <per> <exec>      per: full | tune | julo   exec: 200 or -1 (random delay)"""
import json, os, sys, time, shutil, zlib
from pathlib import Path
import axi_rig
from run_shot import PERIODS, pkt_stats

rig, per, ex = sys.argv[1], sys.argv[2], int(sys.argv[3])
axi_rig.use(rig)
tag = zlib.crc32(f"verify_{per}_{ex}".encode()) % 100000
frm, to = PERIODS[per]
t0 = time.time()
for _ in range(3):
    r = axi_rig.run("bread_winner", "XAUUSD_TK", "M1", {"InpShotLog": "true", "InpShotTag": tag}, frm=frm, to=to, exec_mode=ex,
                    tag=f"bread_verify_{per}_{ex}", deposit=10000, timeout=3600)
    if "error" not in r and r.get("trades", 0) > 0: break
    time.sleep(15)
src = Path(os.path.expandvars(r"%APPDATA%")) / "MetaQuotes" / "Terminal" / "Common" / "Files" / f"bread_shots_{tag}.csv"
dst = Path(r"C:\Users\zeesh\turtle\testing") / f"bread_verify_{per}_{'rand' if ex < 0 else ex}.csv"
shutil.copy(src, dst)
pk = pkt_stats(dst, *PERIODS[per])
r["pkt_days"] = pk
with open(Path(r"C:\Users\zeesh\turtle\testing\bread_verify_runs.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps({k: v for k, v in r.items() if k != "daily"} | {"per": per, "exec": ex}) + "\n")
print(f"bread_winner {per} exec {ex}: PKT weekdays {pk['weekdays']} | shots {pk['shots']} WR {pk['wr']}% | BREAD {pk['bread']} ({pk['bread_pct']}%) | "
      f"red {pk['red']} | empty {pk['empty']} | net {pk['net']} ({pk['per_day']}/day) | worst day {pk['worst']} | max DD {r.get('dd')}", flush=True)
