"""test_feb11_m1.py — run M1 tuned config on Feb 11+12 only (Zee's verified day)."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab")

# Import + monkey-patch the M1 screener
import screener_canonical_uhv_m1 as m1
m1.BREAKOUT_VOL_MAX_RATIO = 0.85
m1.SL_BUFFER = 1.50
m1.HARD_TREND = True

# Override TP to fixed 3.0
orig_detect = m1.detect
def detect_with_fixed_tp(bars):
    fires = orig_detect(bars)
    for f in fires:
        # Replace TP with fixed-distance from entry
        if f.side == "BUY":
            f.tp = round(f.entry + 3.0, 2)
        else:
            f.tp = round(f.entry - 3.0, 2)
    return fires
m1.detect = detect_with_fixed_tp

# Load ONLY Feb 11+12 CSVs explicitly
csvs = [
    Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/shano_ticks_2026-02-11.csv"),
    Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/shano_ticks_2026-02-12.csv"),
]
bars = m1.build_m1(csvs)
print(f"Built {len(bars)} M1 bars from {bars[0].t} to {bars[-1].t}")
fires = m1.detect(bars)
print(f"Detected {len(fires)} M1 fires on Feb 11+12 (tuned soft-vrat-only config)")

# Simulate
wins = losses = open_ = 0
pnl_total = 0.0
per_day = {}
for s in fires:
    sim = m1.simulate(s, bars)
    out = sim["outcome"]
    pnl = sim["pnl_usd"] or 0
    day = s.open_t[:10]
    per_day.setdefault(day, [0, 0, 0.0])
    per_day[day][0 if out == "WIN" else (1 if out == "LOSS" else 2)] += 1
    if out == "WIN": wins += 1; pnl_total += pnl
    elif out == "LOSS": losses += 1; pnl_total += pnl
    else: open_ += 1
    if pnl: per_day[day][2] += pnl

print()
print("PER DAY:")
for day, (w, l, p) in sorted(per_day.items()):
    closed = w + l
    wr = 100*w/closed if closed else 0
    print(f"  {day}: {w}W/{l}L (open: {0 if closed==len([f for f in fires if f.open_t.startswith(day)]) else len([f for f in fires if f.open_t.startswith(day)]) - closed}) WR={wr:.0f}% PNL={p:+.2f}pts")

closed = wins + losses
wr = (wins / closed * 100) if closed else 0
print(f"\nTOTAL: {len(fires)} fires, {wins}W/{losses}L (open {open_}), WR={wr:.1f}%, PNL={pnl_total:+.2f}pts")
print(f"At 0.10 lots: ${pnl_total*10:+.2f}")
print()
print("ZEE'S ACTUAL Feb 11 = 65W/4L = 94.2% WR, +$835/day (manual trading)")
