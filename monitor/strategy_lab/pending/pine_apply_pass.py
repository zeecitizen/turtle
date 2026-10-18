"""Put one MT5 optimizer pass on the TradingView indicator: every trading setting = the EA's own defaults (what the optimizer kept fixed),
then the pass's values. Chart-only rules the EA does not have are switched off; display settings are left alone. Snapshot first.
    py pine_apply_pass.py <EA> <pass json> [--apply]      (without --apply: print the plan only)
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_compare")
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\strategy_lab")
import server  # noqa: E402
import axi_rig  # noqa: E402

ea, pas = sys.argv[1], json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
dfl = axi_rig.ea_defaults(ea)
dfl.update({k: str(v) for k, v in pas.items()})
st = server.tv_eval(server.JS_STUDY)
names = server.pine_inputs()
assert len(names) == len(st["values"]) and st["symbol"].startswith("BLUEBERRY"), (len(names), len(st["values"]), st["symbol"])
cur = dict(zip(names, st["values"]))


def num(v):
    v = float(v)
    return int(v) if v.is_integer() else v


want, skipped = {}, []
for pv, e in server.DIRECT.items():
    if e not in dfl:
        skipped.append(f"{pv} ({e}: not in {ea})")
        continue
    v = dfl[e]
    want[pv] = v.lower() == "true" if isinstance(cur.get(pv), bool) else num(v) if isinstance(cur.get(pv), (int, float)) else v
for pv, (e, m) in server.CHOICES.items():
    if e in dfl:
        inv = {str(x): lbl for lbl, x in m.items()}
        if str(num(dfl[e])) in inv or dfl[e] in inv:
            want[pv] = inv.get(str(num(dfl[e])), inv.get(dfl[e]))
# what the EA does not have = off on the chart
want.update({"tpMode": "Normal: BUY = touch of the other EMA · SELL = last swing low", "xPick": "Off - use the TP1 METHOD and AFTER TP1 settings below",
             "reOn": False, "coolN": 0, "enMode": "Wick break (EA)", "htReq": {"0": "Off", "5": "5 min", "15": "15 min", "30": "30 min", "60": "1 hour", "240": "4 hour"}[str(num(dfl["InpHtfMin"]))]})
for pv, off, _ in server.NOT_IN_EA:
    want[pv] = off
for s in ("B", "S"):
    for b in range(21):
        want[f"rp{s}{b:02d}"] = True                 # the 15-min EA has no range filter
want["enMode"] = {"0": "Wick break (EA)"}.get(str(num(dfl.get("InpEntryMode", "0"))), want["enMode"])
if "InpTrailGapUsd" not in dfl:
    want["pkGap"] = 0                                # chart-only trail gap: the 15-min EA has none
want.pop("iLots", None)                              # keep the chart's lot size (PF / win rate do not depend on it)
plan = [(k, cur.get(k), v) for k, v in want.items() if k in cur and cur[k] != v and not (isinstance(v, (int, float)) and not isinstance(v, bool)
                                                                                      and isinstance(cur[k], (int, float)) and abs(float(cur[k]) - float(v)) < 1e-9)]
print(f"{st['symbol']} {st['res']} min | {len(plan)} settings to change | EA inputs with no chart setting: {skipped}")
for k, a, b in plan:
    print(f"  {k}: {a} -> {b}")
missing = [e for e in pas if e not in set(server.DIRECT.values()) | {c[0] for c in server.CHOICES.values()} | {"InpEntryMode"}]
print("pass settings the chart cannot show:", missing)
if "--apply" in sys.argv:
    snap = Path(__file__).resolve().parent.parent / f"saad_snapshot_{time.strftime('%Y-%m-%d_%H%M')}_before_pass.json"
    json.dump({"symbol": st["symbol"], "res": st["res"], "values": st["values"], "by_name": cur}, open(snap, "w"), indent=1)
    for k, a, b in plan:
        server.set_input(st["id"], names.index(k), b)
    time.sleep(5)
    now = dict(zip(names, server.tv_eval(server.JS_STUDY)["values"]))
    print("snapshot", snap, "| mismatches after read-back:", [(k, now[k], b) for k, a, b in plan if now[k] != b])
