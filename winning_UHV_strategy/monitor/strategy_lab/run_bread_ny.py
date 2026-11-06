"""bread_winner + a New York 8:00-8:45 AM momentum trigger (research copy mt5/bread_nymom.mq5), scored like
verify_bread.py: by PAKISTAN day from the EA's own shot log (a 'bread day' ends >= $10; every weekday counts).
    py run_bread_ny.py <rig> <variant@per> ...      results -> testing/bread_ny_runs.jsonl"""
import json, os, sys, time, zlib, shutil
from pathlib import Path
import axi_rig
from run_shot import PERIODS, pkt_stats

V = {"base37": {"InpTrig": 37},                                                   # = bread_winner v1.02 (control)
     "ny1": {"InpTrig": 128, "InpNyMode": 1, "InpNyCtx": "true"},                 # PULSE minute, trend side + context
     "ny2": {"InpTrig": 128, "InpNyMode": 2, "InpNyBody": 60, "InpNyAtr": 1.5},   # BURST minute, its own way
     "ny3": {"InpTrig": 128, "InpNyMode": 3, "InpNyBody": 60, "InpNyAtr": 1.0},   # the M15 candle, its own way
     "combo1": {"InpTrig": 165, "InpNyMode": 1, "InpNyCtx": "true"},
     "combo2": {"InpTrig": 165, "InpNyMode": 2, "InpNyBody": 60, "InpNyAtr": 1.5},
     "combo3": {"InpTrig": 165, "InpNyMode": 3, "InpNyBody": 60, "InpNyAtr": 1.0}}
axi_rig.use(sys.argv[1])
for name in sys.argv[2:]:
    var, per = name.split("@")
    tag = zlib.crc32(f"ny_{name}".encode()) % 100000
    frm, to = PERIODS[per]
    for _ in range(3):
        r = axi_rig.run("bread_nymom", "XAUUSD_TK", "M1", {"InpShotLog": "true", "InpShotTag": tag, **V[var]}, frm=frm, to=to, exec_mode=200,
                        tag=f"bread_ny_{var}_{per}", deposit=10000, timeout=3600)
        if "error" not in r and r.get("trades", 0) > 0: break
        time.sleep(20)
    src = Path(os.path.expandvars(r"%APPDATA%")) / "MetaQuotes" / "Terminal" / "Common" / "Files" / f"bread_shots_{tag}.csv"
    dst = Path(r"C:\Users\zeesh\turtle\testing") / f"bread_ny_{var}_{per}.csv"
    try:
        shutil.copy(src, dst)
        pk = pkt_stats(dst, frm, to)
    except Exception as e:
        print(f"{name}: no shot log ({e})", flush=True); continue
    with open(Path(r"C:\Users\zeesh\turtle\testing\bread_ny_runs.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"variant": var, "per": per, "pkt_days": pk, "net": r.get("net"), "dd": r.get("dd")}) + "\n")
    print(f"{name}: BREAD {pk['bread']}/{pk['weekdays']} ({pk['bread_pct']}%) | red {pk['red']} | empty {pk['empty']} | shots {pk['shots']} WR {pk['wr']}% | "
          f"net {pk['net']} ({pk['per_day']}/day) | worst day {pk['worst']} | DD {r.get('dd')}", flush=True)
