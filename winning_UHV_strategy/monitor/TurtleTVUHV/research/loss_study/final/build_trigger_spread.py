"""build_trigger_spread.py - an EXTENDED FIELD for the loss-fix rules: the spread (ask - bid, in pips) of the breakout tick itself, i.e. the
first tick whose bid crosses the UHV level - the moment the entry is DECIDED. No future information (the fill comes 0.3 s later). The
harness's trade fields (t) do not carry it, so it is read from the engine's own tick file here and written WITHOUT any outcome column to
trigger_spread_by_id.csv (id, spr_trig_pips). Re-implements agents/batch_1/trigger_spread.py and checks it against that file.
Python hypothesis - NOT PROMOTED until MT5. Run: py research/loss_study/final/build_trigger_spread.py"""
import csv
import json
import os
import sys

import numpy as np

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(LS))
sys.path.insert(0, ROOT)
import uhv_engine as U  # noqa: E402

inp = json.load(open(os.path.join(ROOT, "settings", "saved", "2026-11-05 05-45-38.json"), encoding="utf-8"))["inputs"]
S, TK = U._setups(U.det_file(inp))
S = U._instant_setups(TK, float(inp.get("InpUhvPreBreak") or 0), U.det_file(inp))
st = np.array([s["t"] for s in S])
T, B, AS = TK["t"], TK["bid"], TK["ask"]
trades = json.load(open(os.path.join(LS, "trades.json"), encoding="utf-8"))
rows, bad = [], 0
for t in trades:
    j = int(np.searchsorted(st, t["t_in"] + 1e-6)) - 1
    s = S[j]
    if not (0 <= t["t_in"] - s["t"] < 30) or s["side"] != t["side"] or abs(s["level"] - t["level"]) > 1e-7:
        bad += 1
    i = int(np.searchsorted(T, s["t"])); k = i
    while k < len(T) and T[k] == T[i] and B[k] != s["bc"]:     # the breakout tick: same timestamp, bid = the crossing bid
        k += 1
    if k >= len(T) or T[k] != T[i]:
        k = i
    rows.append((t["id"], round(float(AS[k] - B[k]) / 1e-4, 4)))
with open(os.path.join(HERE, "trigger_spread_by_id.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["id", "spr_trig_pips"]); w.writerows(rows)
print(f"wrote {len(rows)} rows, setup-match problems {bad}")
ref = os.path.join(LS, "agents", "batch_1", "trigger_spread.csv")
if os.path.exists(ref):
    old = {r["id"]: float(r["spr_trig"]) for r in csv.DictReader(open(ref, encoding="utf-8"))}
    diff = [(i, v, old.get(i)) for i, v in rows if old.get(i) is None or abs(old[i] - v) > 1e-3]
    print(f"vs batch_1 trigger_spread.csv: {len(diff)} differences", diff[:5])
