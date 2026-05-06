"""afternoon_retune.py — re-tune Shano-Zee params on latest 172-probe dataset.

The original Shano-Zee was tuned on 04-29 + 04-30 morning data.
Now we have 04-30 afternoon data too (live trades incl. 2 fearIdeal hits).
Find the config that best survives the live afternoon chop.
"""
from __future__ import annotations
import sys
from pathlib import Path

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import Config, run, fmt


def show(label, **kwargs):
    cfg = Config(name=label, **kwargs)
    r = run(cfg)
    print(f"  {label:<60}fired={r['fired']:<3}WR={r['wr']:>5.1f}%  total=${r['total']:+8.2f}  big_L={r['big_losses']}  max_L=${r['max_loss']:+7.2f}  daily={r['daily']}")
    return r


COMMON = dict(probeConfirm=0.45, trailTrigger=12, trailDrop=4,
              skipBadHours=True, trendFilter=True, skipFastConfirm=True, trendTfMinutes=2)

print("=" * 180)
print("CURRENT LIVE — Shano-Zee (lots=0.70, fearI=$80, UHV on)")
print("=" * 180)
show("CURRENT LIVE: lots=0.70 fearI=$80 UHV20", **COMMON, fearIdeal=80, mainLots=0.70, uhvFilter=True, uhvLookback=20)
show("CURRENT no UHV: lots=0.70 fearI=$80", **COMMON, fearIdeal=80, mainLots=0.70)

print()
print("=" * 180)
print("LOT SIZE SWEEP — UHV ON, fearI=$80")
print("=" * 180)
for lots in [0.30, 0.40, 0.50, 0.60, 0.70, 0.80]:
    show(f"lots={lots:.2f}", **COMMON, fearIdeal=80, mainLots=lots, uhvFilter=True, uhvLookback=20)

print()
print("=" * 180)
print("FEARIDEAL SWEEP — UHV ON, lots=0.70")
print("=" * 180)
for fi in [40, 50, 60, 70, 80, 100, 120]:
    show(f"fearI=${fi}", **COMMON, fearIdeal=fi, mainLots=0.70, uhvFilter=True, uhvLookback=20)

print()
print("=" * 180)
print("UHV LOOKBACK SWEEP — lots=0.70, fearI=$80")
print("=" * 180)
for lb in [10, 15, 20, 25, 30, 40]:
    show(f"UHV lookback={lb}", **COMMON, fearIdeal=80, mainLots=0.70, uhvFilter=True, uhvLookback=lb)

print()
print("=" * 180)
print("BEST COMBOS — try lower lots + lower fearI to make fearIdeals smaller")
print("=" * 180)
for lots in [0.40, 0.50]:
    for fi in [50, 60, 70]:
        show(f"lots={lots} fearI=${fi}", **COMMON, fearIdeal=fi, mainLots=lots, uhvFilter=True, uhvLookback=20)
    print()

print("=" * 180)
print("ABLATION — what if we drop UHV entirely?")
print("=" * 180)
for lots in [0.40, 0.50, 0.70]:
    for fi in [50, 70, 80]:
        show(f"NO UHV: lots={lots} fearI=${fi}", **COMMON, fearIdeal=fi, mainLots=lots)
    print()
