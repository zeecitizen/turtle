"""bloom_test.py — Zee's prescription: kill the trend gate + tight SL + wide TP for amplified R:R."""
from __future__ import annotations
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab")
import screener_canonical_uhv_m1 as m1

# Test grid: SL × TP combos with NO TREND GATE
CONFIGS = [
    (1.0, 3.0, "SL1-TP3 (3R)"),
    (0.5, 2.5, "SL0.5-TP2.5 (5R)"),
    (1.0, 5.0, "SL1-TP5 (5R)"),
    (0.5, 3.0, "SL0.5-TP3 (6R)"),
    (1.5, 4.5, "SL1.5-TP4.5 (3R)"),
    (1.0, 2.0, "SL1-TP2 (2R)"),
]

m1.HARD_TREND = False  # KILL the trend gate
m1.UHV_BODY_MIN = 0.50
m1.BREAKOUT_VOL_MAX_RATIO = 0.75
m1.MOM_THRESH = 0.65
m1.MIN_BREAKOUT_PENETRATION = 0.30

csvs = sorted(Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files").glob("shano_ticks_2026-*.csv"))[-7:]
bars = m1.build_m1(csvs)
print(f"Loaded {len(bars)} M1 bars")
print(f"\nNO TREND GATE + canonical body/vol/momentum/penetration gates intact")
print(f"Sweeping SL × TP combos for best $ at 0.10 lots:\n")

for sl_pts, tp_pts, tag in CONFIGS:
    m1.SL_BUFFER = sl_pts
    fires = m1.detect(bars)
    # Override TP with fixed pts
    for f in fires:
        if f.side == "BUY": f.tp = round(f.entry + tp_pts, 2)
        else: f.tp = round(f.entry - tp_pts, 2)

    wins = losses = open_ = 0; pnl_pts = 0.0
    for f in fires:
        sim = m1.simulate(f, bars)
        out = sim["outcome"]
        p = sim["pnl_usd"] or 0
        if out == "WIN": wins += 1; pnl_pts += p
        elif out == "LOSS": losses += 1; pnl_pts += p
        else: open_ += 1
    closed = wins + losses
    wr = (wins / closed * 100) if closed else 0
    pos = sum(s["pnl_usd"] for s in [m1.simulate(f, bars) for f in fires] if s["pnl_usd"] and s["pnl_usd"] > 0)
    neg = sum(s["pnl_usd"] for s in [m1.simulate(f, bars) for f in fires] if s["pnl_usd"] and s["pnl_usd"] < 0)
    pf = (pos / abs(neg)) if neg < 0 else float("inf")
    usd_at_10 = pnl_pts * 10
    fpd = len(fires) / 7
    print(f"  {tag:22s} fires={len(fires):3d} ({fpd:.1f}/d) W={wins:3d}/L={losses:3d} WR={wr:5.1f}% PF={pf if pf!=float('inf') else 99.99:5.2f} pts={pnl_pts:+8.2f}  $@0.10={usd_at_10:+9.2f}  $/day@0.10={usd_at_10/7:+8.2f}")
