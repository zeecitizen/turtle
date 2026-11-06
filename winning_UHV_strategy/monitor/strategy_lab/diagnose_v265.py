"""diagnose_v265.py — what's still blocking us from Feb 11 frequency?"""
from __future__ import annotations
import sys
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab")

import screener_canonical_uhv_m1 as m1

# v2.65 LIVE config
m1.UHV_BODY_MIN = 0.30
m1.BREAKOUT_VOL_MAX_RATIO = 0.75
m1.MOM_THRESH = 0.65
m1.MIN_BREAKOUT_PENETRATION = 0.30
m1.HARD_TREND = False

# Patch find_uhv to skip neighbor-peak (matches v2.64 InpRequireUhvNeighborPeak=false)
orig_find_uhv_buy  = m1.find_uhv_buy
orig_find_uhv_sell = m1.find_uhv_sell
def find_uhv_buy_no_peak(bars, origin, end):
    cands = []
    for i in range(origin, min(end, len(bars) - 1)):
        b = bars[i]
        if not b.is_bear: continue
        if b.body_ratio < m1.UHV_BODY_MIN: continue
        cands.append(i)
    if not cands: return None
    return max(cands, key=lambda x: bars[x].v)
def find_uhv_sell_no_peak(bars, origin, end):
    cands = []
    for i in range(origin, min(end, len(bars) - 1)):
        b = bars[i]
        if not b.is_bull: continue
        if b.body_ratio < m1.UHV_BODY_MIN: continue
        cands.append(i)
    if not cands: return None
    return max(cands, key=lambda x: bars[x].v)
m1.find_uhv_buy  = find_uhv_buy_no_peak
m1.find_uhv_sell = find_uhv_sell_no_peak

csvs = sorted(Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files").glob("shano_ticks_2026-*.csv"))[-7:]
bars = m1.build_m1(csvs)
print(f"Loaded {len(bars)} M1 bars (7 days)")

reasons = Counter()
passed = 0
considered = 0
used_uhvs = set()

for i in range(m1.TREND_BARS + 3, len(bars)):
    for side in ("BUY", "SELL"):
        considered += 1
        origin = (m1.find_retracement_origin_buy(bars, i) if side == "BUY"
                  else m1.find_retracement_origin_sell(bars, i))
        if origin is None:
            reasons["1-no-retracement-origin"] += 1
            continue
        uhv = (m1.find_uhv_buy(bars, origin, i + 1) if side == "BUY"
               else m1.find_uhv_sell(bars, origin, i + 1))
        if uhv is None:
            reasons["2-no-uhv (body<0.30 or no candidate colour)"] += 1
            continue
        if uhv in used_uhvs:
            reasons["3-uhv-already-used (1-fire-per-UHV lockout)"] += 1
            continue
        # Breakout
        brk = None
        body_fail = vol_fail = pen_fail = found_any = False
        for k in range(uhv + 1, min(uhv + m1.RETRACE_MAX_LEN + 1, len(bars))):
            b = bars[k]
            if side == "BUY":
                if not b.is_bull: continue
                if b.c <= bars[uhv].h: continue
                if (b.c - bars[uhv].h) < m1.MIN_BREAKOUT_PENETRATION: pen_fail = True; continue
                if b.v >= bars[uhv].v * m1.BREAKOUT_VOL_MAX_RATIO: vol_fail = True; continue
                if b.body_ratio < m1.MOM_THRESH: body_fail = True; continue
                brk = k; break
            else:
                if not b.is_bear: continue
                if b.c >= bars[uhv].l: continue
                if (bars[uhv].l - b.c) < m1.MIN_BREAKOUT_PENETRATION: pen_fail = True; continue
                if b.v >= bars[uhv].v * m1.BREAKOUT_VOL_MAX_RATIO: vol_fail = True; continue
                if b.body_ratio < m1.MOM_THRESH: body_fail = True; continue
                brk = k; break
        if brk is None:
            if body_fail: reasons["4a-breakout-body<0.65"] += 1
            elif vol_fail: reasons["4b-breakout-vol>=0.75*uhv"] += 1
            elif pen_fail: reasons["4c-breakout-penetration<0.30pt"] += 1
            else: reasons["4z-breakout-other"] += 1
            continue
        used_uhvs.add(uhv)
        passed += 1

print(f"\nConsidered: {considered}")
print(f"Passed all gates: {passed}  ({passed/7:.1f}/day target was Feb 11 ~65/day)")
print(f"\nREMAINING BLOCKERS (v2.65 config):")
for k, v in reasons.most_common():
    pct = 100 * v / considered
    print(f"  {k:55s} {v:7d}  ({pct:5.1f}%)")
