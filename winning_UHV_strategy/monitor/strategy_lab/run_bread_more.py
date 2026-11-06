"""bread_winner v1.03: can it trade MORE often? Same EA, same geometry (0.12 lots, TP $1, SL $8), more shots per day
and more scouts. MT5 on XAUUSD_TK real ticks, scored by Pakistan day from the EA's own shot log.
    py run_bread_more.py <rig> <variant@per[rnd]> ...      results -> testing/bread_more_runs.jsonl"""
import json, os, sys, time, zlib, shutil
from pathlib import Path
import axi_rig
from run_shot import PERIODS, pkt_stats

V = {"base": {}}
for n in (2, 3, 5, 10, 99): V[f"max{n}"] = {"InpShotMax": n}
V["max99_saad"] = {"InpShotMax": 99, "InpTrig": 167, "InpUseSaad": "true"}            # + Saad scout (trigger 2)
V["max99_pulse"] = {"InpShotMax": 99, "InpTrig": 173}                                  # + PULSE (trigger 8)
V["max99_all"] = {"InpShotMax": 99, "InpTrig": 175, "InpUseSaad": "true"}              # every scout
V["max99_pb"] = {"InpShotMax": 99, "InpPbFrom": -1}                                    # pullbacks allowed all day
V["rand99"] = {"InpShotMax": 99, "InpTrig": 16, "InpRandDir": 1}                      # control: coin flip, same geometry
axi_rig.use(sys.argv[1])
for name in sys.argv[2:]:
    var, per = name.split("@")
    rnd = per.endswith("rnd"); per0 = per[:-3] if rnd else per
    tag = zlib.crc32(f"more_{name}".encode()) % 100000
    frm, to = PERIODS[per0]
    for _ in range(3):
        r = axi_rig.run("bread_winner", "XAUUSD_TK", "M1", {"InpShotLog": "true", "InpShotTag": tag, **V[var]}, frm=frm, to=to,
                        exec_mode=-1 if rnd else 200, tag=f"bread_more_{var}_{per}", deposit=10000, timeout=3600)
        if "error" not in r and r.get("trades", 0) > 0: break
        time.sleep(15)
    src = Path(os.path.expandvars(r"%APPDATA%")) / "MetaQuotes" / "Terminal" / "Common" / "Files" / f"bread_shots_{tag}.csv"
    dst = Path(r"C:\Users\zeesh\turtle\testing") / f"bread_more_{var}_{per}.csv"
    try:
        shutil.copy(src, dst); pk = pkt_stats(dst, frm, to)
    except Exception as e:
        print(f"{name}: no shot log ({e}) {r.get('error')}", flush=True); continue
    ts = r.get("trade_stats", {})
    with open(Path(r"C:\Users\zeesh\turtle\testing\bread_more_runs.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"variant": var, "per": per, "sets": V[var], "pkt_days": pk, "net": r.get("net"), "dd": r.get("dd"), "trade_stats": ts}) + "\n")
    print(f"{name}: shots {pk['shots']} ({pk['shots'] / pk['weekdays']:.1f}/day) WR {pk['wr']}% | net {pk['net']} ({pk['per_day']}/day) | "
          f"bread days {pk['bread_pct']}% red {pk['red']} | worst day {pk['worst']} | DD {r.get('dd')} | avg win {ts.get('avg_win')} loss {ts.get('avg_loss')}", flush=True)
