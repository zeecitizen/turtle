"""fire_more_test.py — explore relaxations to fire MORE probes without breaking WR.

Tests:
  1. Lower probeConfirm: 0.45 → 0.40, 0.35, 0.30
  2. Relax skipBadHours (drop 04-06 OR 21-23 only)
  3. Drop skipFastConfirm
  4. Drop trendFilter (let all directions fire)
  5. Multi-relaxations
"""
from __future__ import annotations
import sys
from pathlib import Path

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import Config, run, fmt

scenarios = [
    # Base
    Config(name="WINNING (hour+trend+fast, 0.45)",
           probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, skipFastConfirm=True),

    # Lower probeConfirm
    Config(name="winning + probeConfirm 0.40",
           probeConfirm=0.40, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, skipFastConfirm=True),
    Config(name="winning + probeConfirm 0.35",
           probeConfirm=0.35, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, skipFastConfirm=True),
    Config(name="winning + probeConfirm 0.30",
           probeConfirm=0.30, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, skipFastConfirm=True),

    # Drop one filter
    Config(name="DROP fast-confirm (hour+trend only)",
           probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True),
    Config(name="DROP trend (hour+fast only)",
           probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, skipFastConfirm=True),
    Config(name="DROP hour (trend+fast only)",
           probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           trendFilter=True, skipFastConfirm=True),

    # Lower confirm + drop fast (wider window)
    Config(name="0.40 + hour+trend (no fast skip)",
           probeConfirm=0.40, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True),
    Config(name="0.35 + hour+trend (no fast skip)",
           probeConfirm=0.35, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True),
]

print("=" * 180)
for c in scenarios:
    print(fmt(run(c)))
