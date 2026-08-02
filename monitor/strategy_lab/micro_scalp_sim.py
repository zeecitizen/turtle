"""micro_scalp_sim.py — tick-level walk: did TP hit before SL?

For each fire, walk tick-by-tick from entry moment. EXIT at first threshold:
  - +TP_PTS favorable → WIN
  - −SL_PTS adverse → LOSS
  - timeout (60s) → OPEN
"""
from __future__ import annotations
import sys, csv
from pathlib import Path
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab")
import screener_canonical_uhv_m1 as m1

m1.HARD_TREND = False
m1.UHV_BODY_MIN = 0.50
m1.BREAKOUT_VOL_MAX_RATIO = 0.75
m1.MOM_THRESH = 0.65
m1.MIN_BREAKOUT_PENETRATION = 0.30

CSV_DIR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
csvs = sorted(CSV_DIR.glob("shano_ticks_2026-*.csv"))[-7:]
bars = m1.build_m1(csvs)
fires = m1.detect(bars)
print(f"Detected {len(fires)} fires (no trend gate)")

# Load ticks
ticks = []
for p in csvs:
    with p.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts = row.get("ts_broker") or row.get("ts") or row.get("t")
            if not ts: continue
            if "." in ts.split(" ", 1)[-1]: ts = ts.rsplit(".", 1)[0]
            try: dt = datetime.strptime(ts, "%Y.%m.%d %H:%M:%S")
            except ValueError: continue
            try:
                bid = float(row["bid"]); ask = float(row["ask"])
            except (KeyError, ValueError): continue
            ticks.append((dt, bid, ask))
ticks.sort()

# Test grid of TP × SL × timeout
GRID = [
    (0.3, 0.5, 60, "scalp-0.3/0.5"),
    (0.3, 1.0, 60, "scalp-0.3/1.0"),
    (0.5, 0.5, 60, "scalp-0.5/0.5"),
    (0.5, 1.0, 60, "scalp-0.5/1.0"),
    (0.5, 1.5, 60, "scalp-0.5/1.5"),
    (1.0, 1.0, 60, "scalp-1.0/1.0"),
    (1.0, 1.5, 60, "scalp-1.0/1.5"),
    (1.0, 2.0, 60, "scalp-1.0/2.0"),
    (1.5, 1.5, 60, "scalp-1.5/1.5"),
    (2.0, 2.0, 60, "scalp-2.0/2.0"),
    (3.0, 1.5, 120, "scalp-3.0/1.5-2min"),
]

def simulate_tick(fire, tp_pts, sl_pts, timeout_s):
    open_dt = datetime.strptime(fire.open_t, "%Y-%m-%d %H:%M")
    entry_idx = None
    for j, (t, b, a) in enumerate(ticks):
        if t > open_dt: entry_idx = j; break
    if entry_idx is None: return None
    entry = ticks[entry_idx][2] if fire.side == "BUY" else ticks[entry_idx][1]
    cap = ticks[entry_idx][0] + timedelta(seconds=timeout_s)
    for k in range(entry_idx, min(entry_idx + 2000, len(ticks))):
        t, b, a = ticks[k]
        if t > cap: return ("OPEN", 0)
        cur = b if fire.side == "BUY" else a  # close at bid for BUY, ask for SELL
        delta = (cur - entry) if fire.side == "BUY" else (entry - cur)
        if delta >= tp_pts: return ("WIN", tp_pts)
        if delta <= -sl_pts: return ("LOSS", -sl_pts)
    return ("OPEN", 0)

print(f"\n=== TICK-LEVEL SIM, {len(fires)} fires, last 7d ===")
print(f"  {'config':22s} {'W':>3s}/{'L':>3s}/{'OP':>3s}  WR    PF      net_pts    $@0.10   $/day")
for tp, sl, to, tag in GRID:
    W = L = O = 0
    net = 0.0
    pos_sum = neg_sum = 0.0
    for f in fires:
        res = simulate_tick(f, tp, sl, to)
        if res is None: continue
        outcome, pnl = res
        if outcome == "WIN": W += 1; net += pnl; pos_sum += pnl
        elif outcome == "LOSS": L += 1; net += pnl; neg_sum += pnl
        else: O += 1
    closed = W + L
    wr = W / closed * 100 if closed else 0
    pf = (pos_sum / abs(neg_sum)) if neg_sum < 0 else float("inf")
    pf_s = f"{pf:5.2f}" if pf != float("inf") else "  inf"
    print(f"  {tag:22s} {W:3d}/{L:3d}/{O:3d}  {wr:4.0f}% {pf_s}  {net:+7.2f}    {net*10:+8.2f}  {net*10/7:+7.2f}")
