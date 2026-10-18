"""Set the TradingView Saad indicator to the V1 'all best drivers' settings (Zee 2026-10-18, 5-min chart).
Snapshot first (by position + by name) so it can be restored."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_compare")
import server  # noqa: E402

HERE = Path(__file__).resolve().parent
st = server.tv_eval(server.JS_STUDY)
names = server.pine_inputs()
assert "error" not in st, st
assert st["symbol"].startswith("BLUEBERRY"), st["symbol"]
assert len(names) == len(st["values"]), (len(names), len(st["values"]))
snap = dict(zip(names, st["values"]))
out = HERE.parent / f"saad_snapshot_2026-10-18_m5_before_v1.json"
json.dump({"symbol": st["symbol"], "res": st["res"], "values": st["values"], "by_name": snap}, open(out, "w"), indent=1)
print("snapshot", out, st["symbol"], st["res"])

V1 = {"iFast": 10, "iSlow": 20, "iBreakP": 3, "iEr": 0.3, "htReq": "1 hour", "htEma": 70,
      "iSlMode": "ATR x from the entry", "iSlAtrM": 2, "tpMode": "Fibonacci extension of the setup candle", "tpFib": 200,
      "iPartial": 0.75, "iBePct": 0.75, "iMaxRisk": 10, "coolN": 0, "reOn": False,
      "xPick": "Off - use the TP1 METHOD and AFTER TP1 settings below"}
for s in ("B", "S"):
    for b in range(21):
        V1[f"rp{s}{b:02d}"] = True
changed = []
for k, v in V1.items():
    if k not in names:
        print("NOT ON CHART:", k); continue
    if snap[k] != v:
        server.set_input(st["id"], names.index(k), v)
        changed.append((k, snap[k], v))
time.sleep(4)
now = dict(zip(names, server.tv_eval(server.JS_STUDY)["values"]))
bad = [(k, now[k], v) for k, v in V1.items() if k in now and now[k] != v]
for k, a, b in changed:
    print(f"  {k}: {a} -> {b}")
print("changed", len(changed), "| mismatches after read-back:", bad)
