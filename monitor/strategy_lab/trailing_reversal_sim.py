"""trailing_reversal_sim.py — Zee's "catch the 100%" mandate.

Strategy:
  - Enter at breakout
  - Track PEAK favorable excursion tick-by-tick
  - When price retraces from peak by REVERSAL_THRESHOLD → exit at current price
  - Lock in whatever positive we have (or accept tiny loss if reversal hit before any positive)
  - Hard SL only as safety net (e.g., -1.5pt absolute)

If 100% of fires go positive at some point (verified), and we exit AT THE PEAK -
some-tiny-reversal, we should capture 95-100% as winners.

Verifies: REVERSAL_THRESHOLD × MIN_PROFIT_LOCK combos.
"""
from __future__ import annotations
import sys, csv
from pathlib import Path
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab")
import screener_canonical_uhv_m1 as m1

m1.HARD_TREND = False
m1.UHV_BODY_MIN = 0.30  # loose, matches v2.64
m1.BREAKOUT_VOL_MAX_RATIO = 0.75
m1.MOM_THRESH = 0.65
m1.MIN_BREAKOUT_PENETRATION = 0.30

CSV_DIR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
csvs = sorted(CSV_DIR.glob("shano_ticks_2026-*.csv"))[-7:]
bars = m1.build_m1(csvs)
fires = m1.detect(bars)
# Override neighbor-peak check (we set it false in EA — replicate here)
# Actually find_uhv_buy/sell already use the loose body min. Re-call detect now that UHV_BODY_MIN=0.30
print(f"Detected {len(fires)} fires (UHV body 0.30, no trend, no neighbor-peak in v2.64)")

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
print(f"Loaded {len(ticks)} ticks")


def sim_reversal(fire, reversal_pts, min_lock_pts, hard_sl_pts, timeout_s):
    """
    Walk ticks from entry. Track peak favorable excursion.
    Exit logic:
      - If reached >= min_lock_pts and price drops reversal_pts from peak → exit at current
      - If price drops hard_sl_pts below entry → exit at -hard_sl_pts
      - If timeout → exit at current pnl
    """
    open_dt = datetime.strptime(fire.open_t, "%Y-%m-%d %H:%M")
    entry_idx = None
    for j, (t, b, a) in enumerate(ticks):
        if t > open_dt: entry_idx = j; break
    if entry_idx is None: return None
    entry = ticks[entry_idx][2] if fire.side == "BUY" else ticks[entry_idx][1]
    peak = 0.0  # max favorable so far
    cap = ticks[entry_idx][0] + timedelta(seconds=timeout_s)
    for k in range(entry_idx, min(entry_idx + 2000, len(ticks))):
        t, b, a = ticks[k]
        if t > cap:
            # exit at current price
            cur = b if fire.side == "BUY" else a
            delta = (cur - entry) if fire.side == "BUY" else (entry - cur)
            return ("TIMEOUT", round(delta, 3))
        cur = b if fire.side == "BUY" else a
        delta = (cur - entry) if fire.side == "BUY" else (entry - cur)
        if delta > peak: peak = delta
        # Hard SL safety
        if delta <= -hard_sl_pts:
            return ("HARDSL", -hard_sl_pts)
        # Reversal exit (only after min lock reached)
        if peak >= min_lock_pts and (peak - delta) >= reversal_pts:
            return ("REVERSAL_EXIT", round(delta, 3))
    return ("EOD", round(peak, 3))


GRID = [
    # (reversal_pts, min_lock_pts, hard_sl_pts, timeout_s, tag)
    (0.10, 0.10, 1.5, 60,  "rev0.1/lock0.1/sl1.5"),
    (0.10, 0.20, 1.5, 60,  "rev0.1/lock0.2/sl1.5"),
    (0.15, 0.20, 1.5, 60,  "rev0.15/lock0.2"),
    (0.15, 0.30, 1.5, 60,  "rev0.15/lock0.3"),
    (0.20, 0.30, 1.5, 60,  "rev0.2/lock0.3"),
    (0.20, 0.50, 1.5, 60,  "rev0.2/lock0.5"),
    (0.30, 0.50, 1.5, 60,  "rev0.3/lock0.5"),
    (0.30, 0.70, 1.5, 60,  "rev0.3/lock0.7"),
    (0.50, 0.50, 1.5, 60,  "rev0.5/lock0.5"),
    (0.50, 1.00, 2.0, 90,  "rev0.5/lock1.0/sl2"),
    (0.20, 0.10, 1.0, 30,  "ultra-fast"),
]

print(f"\n{'config':30s} {'W':>3s}/{'L':>3s}/{'TO':>3s}  WR    avg+    avg-   net pts   $@0.10   $@1.0/day")
for rev, lock, sl, to, tag in GRID:
    W = L = TO = HARDSL = 0
    pos = []
    neg = []
    for f in fires:
        res = sim_reversal(f, rev, lock, sl, to)
        if res is None: continue
        out, pnl = res
        if out == "REVERSAL_EXIT":
            if pnl > 0: W += 1; pos.append(pnl)
            else: L += 1; neg.append(pnl)
        elif out == "HARDSL":
            L += 1; neg.append(-sl); HARDSL += 1
        else:  # TIMEOUT or EOD
            TO += 1
            if pnl > 0: pos.append(pnl)
            else: neg.append(pnl)
    closed = W + L
    wr = W / closed * 100 if closed else 0
    avg_pos = (sum(pos) / len(pos)) if pos else 0
    avg_neg = (sum(neg) / len(neg)) if neg else 0
    net = sum(pos) + sum(neg)
    usd_at_10 = net * 10
    usd_at_1lot_per_day = net * 100 / 7
    print(f"  {tag:30s} {W:3d}/{L:3d}/{TO:3d}  {wr:4.0f}%  {avg_pos:+5.2f}  {avg_neg:+5.2f}  {net:+7.2f}   {usd_at_10:+7.2f}  {usd_at_1lot_per_day:+8.2f}")

print(f"\nNote: timeout cases included in net P&L but not in W/L (they exit at price-at-timeout, peak ignored).")
