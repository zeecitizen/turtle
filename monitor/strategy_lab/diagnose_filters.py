"""diagnose_filters.py — for every potential setup on last 7d of M1 ticks, log which gate killed it.
Tally up the rejections by gate so we can see what's choking the strategy the most.
"""
from __future__ import annotations
import sys
from pathlib import Path
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab")

import screener_canonical_uhv_m1 as m1

# Apply v2.62 strict canonical params
m1.UHV_BODY_MIN = 0.50
m1.BREAKOUT_VOL_MAX_RATIO = 0.75
m1.MOM_THRESH = 0.65
m1.MIN_BREAKOUT_PENETRATION = 0.30
m1.HARD_TREND = True

# Load last 7 days
csvs = sorted(Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files").glob("shano_ticks_2026-*.csv"))[-7:]
bars = m1.build_m1(csvs)
print(f"Loaded {len(bars)} M1 bars")

reasons = Counter()
passed = 0
considered = 0

for i in range(m1.TREND_BARS + 3, len(bars)):
    for side in ("BUY", "SELL"):
        considered += 1
        # Trend
        trend_ok = m1.trend_uptrend(bars, i) if side == "BUY" else m1.trend_downtrend(bars, i)
        if m1.HARD_TREND and not trend_ok:
            reasons["1-trend(HHHL)"] += 1
            continue
        # Origin
        origin = (m1.find_retracement_origin_buy(bars, i) if side == "BUY"
                  else m1.find_retracement_origin_sell(bars, i))
        if origin is None:
            reasons["2-no-retracement-origin"] += 1
            continue
        # UHV
        uhv = (m1.find_uhv_buy(bars, origin, i + 1) if side == "BUY"
               else m1.find_uhv_sell(bars, origin, i + 1))
        if uhv is None:
            reasons["3-no-uhv (body<0.50 OR not neighbor-peak OR not retracement-max)"] += 1
            continue
        # Sweep (soft — log but don't reject)
        sweep_ok = (m1.sweep_ok_buy(bars, uhv, i + 1) if side == "BUY"
                    else m1.sweep_ok_sell(bars, uhv, i + 1))
        if not sweep_ok:
            reasons["4-no-sweep (soft)"] += 1
        # Breakout — check each sub-gate individually
        brk = None
        body_fail = vol_fail = pen_fail = colour_fail = found_any = False
        for k in range(uhv + 1, min(uhv + m1.RETRACE_MAX_LEN + 1, len(bars))):
            b = bars[k]
            if side == "BUY":
                if not b.is_bull: colour_fail = True; continue
                if b.c <= bars[uhv].h: continue   # not crossed yet
                if (b.c - bars[uhv].h) < m1.MIN_BREAKOUT_PENETRATION: pen_fail = True; continue
                if b.v >= bars[uhv].v * m1.BREAKOUT_VOL_MAX_RATIO: vol_fail = True; continue
                if b.body_ratio < m1.MOM_THRESH: body_fail = True; continue
                brk = k; found_any = True; break
            else:
                if not b.is_bear: colour_fail = True; continue
                if b.c >= bars[uhv].l: continue
                if (bars[uhv].l - b.c) < m1.MIN_BREAKOUT_PENETRATION: pen_fail = True; continue
                if b.v >= bars[uhv].v * m1.BREAKOUT_VOL_MAX_RATIO: vol_fail = True; continue
                if b.body_ratio < m1.MOM_THRESH: body_fail = True; continue
                brk = k; found_any = True; break
        if brk is None:
            if body_fail and not (vol_fail or pen_fail):
                reasons["5a-breakout-body<0.65"] += 1
            elif vol_fail and not (body_fail or pen_fail):
                reasons["5b-breakout-vol>=0.75*uhv"] += 1
            elif pen_fail:
                reasons["5c-breakout-penetration<0.30pt"] += 1
            elif colour_fail and not (body_fail or vol_fail or pen_fail):
                reasons["5d-no-correct-colour-breakout"] += 1
            else:
                reasons["5z-breakout-other (multiple gates)"] += 1
            continue
        passed += 1

print(f"\nConsidered: {considered} (each bar × side)")
print(f"Passed all gates: {passed}")
print(f"\nGATE REJECTION TALLY (biggest blocker first):")
for k, v in reasons.most_common():
    pct = 100 * v / considered
    print(f"  {k:55s} {v:7d}  ({pct:5.1f}%)")
