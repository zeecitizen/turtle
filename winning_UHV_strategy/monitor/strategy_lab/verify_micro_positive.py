"""verify_micro_positive.py — Zee's claim: EVERY UHV breakout goes positive before negative.

For each canonical M1 fire (no-trend-gate config = the 16 fires we found), walk the
TICK data from the fire moment forward and measure:
  - Max favorable excursion (MFE) in points
  - Max adverse excursion (MAE) in points
  - Did MFE happen BEFORE MAE?

If 95%+ of fires hit at least +0.5pt favorable BEFORE going -0.5pt adverse, Zee is right
and we can build a micro-scalp strategy: enter on breakout, exit at first +1pt or instant
reversal-tick.
"""
from __future__ import annotations
import sys, csv
from pathlib import Path
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab")
import screener_canonical_uhv_m1 as m1

m1.HARD_TREND = False  # no-trend bloom config
m1.UHV_BODY_MIN = 0.50
m1.BREAKOUT_VOL_MAX_RATIO = 0.75
m1.MOM_THRESH = 0.65
m1.MIN_BREAKOUT_PENETRATION = 0.30

CSV_DIR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
csvs = sorted(CSV_DIR.glob("shano_ticks_2026-*.csv"))[-7:]
bars = m1.build_m1(csvs)
print(f"Loaded {len(bars)} M1 bars")
fires = m1.detect(bars)
print(f"Detected {len(fires)} M1 fires (no trend gate)")

# Load raw ticks (bid/ask per timestamp) for the 7-day window
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

# Analyse each fire
results = []
for f in fires:
    open_dt = datetime.strptime(f.open_t, "%Y-%m-%d %H:%M")
    # Find first tick after open_t (entry moment)
    entry_idx = None
    for j, (t, b, a) in enumerate(ticks):
        if t > open_dt:
            entry_idx = j; break
    if entry_idx is None: continue
    entry_price = ticks[entry_idx][2] if f.side == "BUY" else ticks[entry_idx][1]  # ask for BUY, bid for SELL
    # Walk ticks for 120 seconds (or 200 ticks max)
    mfe = 0.0  # max favorable
    mae = 0.0  # max adverse
    mfe_t = mfe_tick = mae_tick = None
    cap_until = ticks[entry_idx][0] + timedelta(seconds=120)
    for k in range(entry_idx, min(entry_idx + 500, len(ticks))):
        t, b, a = ticks[k]
        if t > cap_until: break
        cur_price = b if f.side == "BUY" else a  # bid if BUY (where you'd close), ask if SELL
        delta = (cur_price - entry_price) if f.side == "BUY" else (entry_price - cur_price)
        if delta > mfe:
            mfe = delta; mfe_tick = k
        if delta < -mae:
            mae = -delta; mae_tick = k
    # Compute: did MFE happen BEFORE MAE?
    mfe_first = (mfe_tick is not None and mae_tick is not None and mfe_tick <= mae_tick) or (mae_tick is None and mfe_tick is not None)
    results.append(dict(side=f.side, open_t=f.open_t, entry=round(entry_price, 2),
                        mfe=round(mfe, 2), mae=round(mae, 2), mfe_first=mfe_first))

print(f"\n{'side':5s} {'open_t':18s} {'entry':>8s}  {'MFE':>6s}  {'MAE':>6s}  MFE first?")
for r in results:
    print(f"  {r['side']:4s} {r['open_t']:18s} {r['entry']:7.2f}  {r['mfe']:+5.2f}  {r['mae']:+5.2f}  {'✓' if r['mfe_first'] else '✗'}")

# Tally
positive_first = sum(1 for r in results if r["mfe"] >= 0.1)
mfe_05 = sum(1 for r in results if r["mfe"] >= 0.5)
mfe_1   = sum(1 for r in results if r["mfe"] >= 1.0)
mfe_2   = sum(1 for r in results if r["mfe"] >= 2.0)
mfe_first_ct = sum(1 for r in results if r["mfe_first"])

print(f"\n=== ZEE'S CLAIM TEST ===")
print(f"  Total fires:               {len(results)}")
print(f"  Got at least +0.1pt MFE:   {positive_first}  ({100*positive_first/len(results):.0f}%)")
print(f"  Got at least +0.5pt MFE:   {mfe_05}  ({100*mfe_05/len(results):.0f}%)")
print(f"  Got at least +1.0pt MFE:   {mfe_1}  ({100*mfe_1/len(results):.0f}%)")
print(f"  Got at least +2.0pt MFE:   {mfe_2}  ({100*mfe_2/len(results):.0f}%)")
print(f"  MFE happened BEFORE MAE:   {mfe_first_ct}  ({100*mfe_first_ct/len(results):.0f}%)")
print()
print(f"=== MICRO-SCALP SIMULATION (TP @ +0.5pt, hard-SL @ -1pt) ===")
wins = sum(1 for r in results if r["mfe"] >= 0.5 and (not r["mfe_first"] or r["mae"] < 1.0))
# More precise: TP would trigger if MFE >= 0.5pt happens before MAE >= 1pt
strict_wins = sum(1 for r in results if r["mfe_first"] and r["mfe"] >= 0.5)
print(f"  Wins (MFE>=0.5 hits before SL>=1pt): {strict_wins}  ({100*strict_wins/len(results):.0f}%)")
