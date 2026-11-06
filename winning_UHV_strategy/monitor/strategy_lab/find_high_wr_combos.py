"""Comprehensive filter combo sweep — find configurations hitting 88%+ WR."""
from unified_backtester import Config, run, fmt

scenarios = [
    Config(name="baseline (Shano pure)"),
    Config(name="baseline (claude-tuned 0.45/12/4/50)",
           probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50),

    # ── Single filters on claude-tuned base ──
    Config(name="hour-narrow only", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True),
    Config(name="trend filter only", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           trendFilter=True),
    Config(name="MFE dead-zone skip only", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipMfeDeadZone=True),
    Config(name="fast-confirm skip only", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipFastConfirm=True),
    Config(name="prior-chop skip (>=2)", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipPriorChop=2),
    Config(name="prior-chop skip (>=3)", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipPriorChop=3),
    Config(name="whipsaw skip", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipPriorLossOpposite=True),

    # ── 2-filter combos ──
    Config(name="hour + trend", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True),
    Config(name="hour + MFE-dead-zone", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, skipMfeDeadZone=True),
    Config(name="hour + fast-confirm", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, skipFastConfirm=True),
    Config(name="hour + chop>=2", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, skipPriorChop=2),
    Config(name="hour + chop>=3", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, skipPriorChop=3),
    Config(name="hour + whipsaw", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, skipPriorLossOpposite=True),
    Config(name="trend + chop>=2", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           trendFilter=True, skipPriorChop=2),
    Config(name="trend + whipsaw", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           trendFilter=True, skipPriorLossOpposite=True),
    Config(name="MFE + fast-confirm", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipMfeDeadZone=True, skipFastConfirm=True),

    # ── 3-filter combos ──
    Config(name="hour + trend + MFE", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, skipMfeDeadZone=True),
    Config(name="hour + trend + fast", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, skipFastConfirm=True),
    Config(name="hour + trend + chop>=2", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, skipPriorChop=2),
    Config(name="hour + trend + chop>=3", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, skipPriorChop=3),
    Config(name="hour + trend + whipsaw", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, skipPriorLossOpposite=True),
    Config(name="hour + MFE + fast-confirm", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, skipMfeDeadZone=True, skipFastConfirm=True),
    Config(name="trend + MFE + fast-confirm", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           trendFilter=True, skipMfeDeadZone=True, skipFastConfirm=True),

    # ── 4+filter combos ──
    Config(name="hour + trend + MFE + fast", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, skipMfeDeadZone=True, skipFastConfirm=True),
    Config(name="hour + trend + MFE + chop>=2", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, skipMfeDeadZone=True, skipPriorChop=2),
    Config(name="hour + trend + MFE + whipsaw", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, skipMfeDeadZone=True, skipPriorLossOpposite=True),
    Config(name="hour + trend + chop>=2 + whipsaw", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, skipPriorChop=2, skipPriorLossOpposite=True),
    Config(name="ALL FIVE filters", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, skipMfeDeadZone=True, skipFastConfirm=True,
           skipPriorChop=2),
    Config(name="ALL SIX filters (whipsaw too)", probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, skipMfeDeadZone=True, skipFastConfirm=True,
           skipPriorChop=2, skipPriorLossOpposite=True),

    # ── More aggressive: confirm-speed window ──
    Config(name="hour + trend + min-confirm-8s",
           probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, minConfirmSpeedSec=8),
    Config(name="hour + trend + min-confirm-15s (slow only)",
           probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50,
           skipBadHours=True, trendFilter=True, minConfirmSpeedSec=15),

    # ── Fearideal variants on top of best filters ──
    Config(name="hour + trend + chop>=2 (fi=35)",
           probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=35,
           skipBadHours=True, trendFilter=True, skipPriorChop=2),
    Config(name="hour + trend + chop>=2 (fi=70)",
           probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=70,
           skipBadHours=True, trendFilter=True, skipPriorChop=2),
]

print(f"Running {len(scenarios)} scenarios...")
print()
results = []
for c in scenarios:
    r = run(c)
    results.append(r)

# Sort by WR descending (need at least 5 fires to be meaningful)
print("=" * 180)
print("SORTED BY WIN RATE (min 5 fires)")
print("=" * 180)
qualified = [r for r in results if r["fired"] >= 5]
for r in sorted(qualified, key=lambda x: -x["wr"]):
    print(fmt(r))

print()
print("=" * 180)
print("SORTED BY TOTAL P&L (min 5 fires)")
print("=" * 180)
for r in sorted(qualified, key=lambda x: -x["total"]):
    print(fmt(r))

print()
print(">>> WR >= 88% AND fired >= 10 (target zone) <<<")
target = [r for r in results if r["wr"] >= 88 and r["fired"] >= 10]
if target:
    for r in sorted(target, key=lambda x: -x["total"]):
        print(fmt(r))
else:
    print("None hit 88%+ with 10+ fires. Top WRs:")
    for r in sorted(qualified, key=lambda x: -x["wr"])[:5]:
        print(fmt(r))
