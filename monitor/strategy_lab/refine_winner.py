"""Targeted refinement around the top variants from the broad sweep."""
from filter_backtester import StratConfig, run_strategy, summarize, load_probes, fmt_summary

rows = load_probes()
print(f"Refining winner — {len(rows)} probes\n")

configs = []

# Refine trail params around the K winner (trail 12/4)
for tt in [8, 10, 12, 14, 16, 20]:
    for td in [2, 3, 4, 5]:
        configs.append(StratConfig(
            name=f"trail={tt}/{td}",
            probeConfirm=0.45, fearIdeal=50, trailTrigger=tt, trailDrop=td,
            postBigLossCooldown=1, dailyBigLossHalt=2,
        ))

# Refine cooldown values
for n in [0, 1, 2, 3, 5]:
    for h in [1, 2, 3, 4]:
        configs.append(StratConfig(
            name=f"postLoss={n}/halt={h} (trail 12/4)",
            probeConfirm=0.45, fearIdeal=50, trailTrigger=12, trailDrop=4,
            postBigLossCooldown=n, dailyBigLossHalt=h,
        ))

# Aggressive variants pushing trail wider
configs.append(StratConfig(
    name="WIDE trail=20/5 + postLoss=1 + halt=2",
    probeConfirm=0.45, fearIdeal=50, trailTrigger=20, trailDrop=5,
    postBigLossCooldown=1, dailyBigLossHalt=2,
))
configs.append(StratConfig(
    name="TIGHT trail=6/2 + postLoss=1 + halt=2",
    probeConfirm=0.45, fearIdeal=50, trailTrigger=6, trailDrop=2,
    postBigLossCooldown=1, dailyBigLossHalt=2,
))
# What if we also halt at 2 + flipSkip=2 + wide trail
configs.append(StratConfig(
    name="COMBO trail=12/4 + halt=2 + postLoss=1 + flip=2",
    probeConfirm=0.45, fearIdeal=50, trailTrigger=12, trailDrop=4,
    postBigLossCooldown=1, dailyBigLossHalt=2, directionFlipSkip=2,
))
configs.append(StratConfig(
    name="COMBO trail=14/4 + halt=2 + postLoss=2 + flip=2",
    probeConfirm=0.45, fearIdeal=50, trailTrigger=14, trailDrop=4,
    postBigLossCooldown=2, dailyBigLossHalt=2, directionFlipSkip=2,
))

results = []
for cfg in configs:
    sim, _ = run_strategy(rows, cfg)
    s = summarize(sim)
    s["worst_day"] = min(s["daily"].values(), default=0)
    s["best_day"] = max(s["daily"].values(), default=0)
    s["name"] = cfg.name
    results.append(s)

print("Sorted by total P&L:")
print()
for r in sorted(results, key=lambda x: -x["total"])[:20]:
    daily = " | ".join(f"{d}:${p:+.0f}" for d, p in sorted(r["daily"].items()))
    both_pos = "*BOTH+*" if r["worst_day"] > 0 else ""
    print(f"  {r['name']:<48}  fired={r['fired']:>3}  WR={r['wr']:>5.1f}%  total=${r['total']:+8.2f}  worst=${r['worst_day']:+7.2f}  daily=[{daily}]  {both_pos}")

print()
print("Sorted by worst-day P&L (regime robustness):")
print()
for r in sorted(results, key=lambda x: -x["worst_day"])[:15]:
    daily = " | ".join(f"{d}:${p:+.0f}" for d, p in sorted(r["daily"].items()))
    both_pos = "*BOTH+*" if r["worst_day"] > 0 else ""
    print(f"  {r['name']:<48}  worst=${r['worst_day']:+7.2f}  total=${r['total']:+8.2f}  WR={r['wr']:>5.1f}%  daily=[{daily}]  {both_pos}")
