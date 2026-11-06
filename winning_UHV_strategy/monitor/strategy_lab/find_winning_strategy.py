"""
find_winning_strategy.py — exhaustive search for filters that turn the
strategy profitable on bad days. Tests user's hypothesis: "big losses come
in clusters; if we filter those, the small wins compound."

Runs 50+ strategy configurations and ranks them by:
  - Total P&L
  - Worst-day P&L (proxy for "survives bad days")
  - WR

Outputs:
  - probe_research_results.json (machine-readable)
  - probe_research_report.md (human-readable, with rankings)
"""

from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
from filter_backtester import (
    StratConfig, run_strategy, summarize, load_probes, fmt_summary,
)

LAB_DIR = Path(__file__).parent
RESULTS_JSON = LAB_DIR / "probe_research_results.json"
REPORT_MD = LAB_DIR / "probe_research_report.md"


def all_configs():
    """Generate the full list of strategy configurations to test."""
    out = []

    # ── Tier 1: Baselines (no filters) ──
    out.append(StratConfig(name="A0 baseline pc=.45 fi=50 (CURRENT LIVE)", probeConfirm=0.45, fearIdeal=50))
    out.append(StratConfig(name="A1 baseline pc=.58 fi=70 (ORIGINAL)", probeConfirm=0.58, fearIdeal=70))
    out.append(StratConfig(name="A2 pc=.45 fi=70", probeConfirm=0.45, fearIdeal=70))
    out.append(StratConfig(name="A3 pc=.45 fi=35", probeConfirm=0.45, fearIdeal=35))

    # ── Tier 2: Single filters on top of current baseline ──
    for n in [1, 2, 3]:
        out.append(StratConfig(
            name=f"B postBigLoss skip {n} (fi=50)",
            probeConfirm=0.45, fearIdeal=50,
            postBigLossCooldown=n,
        ))
    for m in [2, 3, 4]:
        out.append(StratConfig(
            name=f"C dailyBigLossHalt after {m} (fi=50)",
            probeConfirm=0.45, fearIdeal=50,
            dailyBigLossHalt=m,
        ))
    for n in [2, 3, 4]:
        out.append(StratConfig(
            name=f"D consecLossSkip after {n} (fi=50)",
            probeConfirm=0.45, fearIdeal=50,
            consecLossSkip=n,
        ))
    for k in [2, 3]:
        out.append(StratConfig(
            name=f"E directionFlipSkip after {k} same-dir wins",
            probeConfirm=0.45, fearIdeal=50,
            directionFlipSkip=k,
        ))
    for n in [2, 3]:
        out.append(StratConfig(
            name=f"F burstPositionMax {n} (after burst of N wins)",
            probeConfirm=0.45, fearIdeal=50,
            burstPositionMax=n,
        ))

    # ── Tier 3: Combinations on baseline ──
    out.append(StratConfig(
        name="G postLoss=1 + dailyHalt=2",
        probeConfirm=0.45, fearIdeal=50,
        postBigLossCooldown=1, dailyBigLossHalt=2,
    ))
    out.append(StratConfig(
        name="G postLoss=2 + dailyHalt=2",
        probeConfirm=0.45, fearIdeal=50,
        postBigLossCooldown=2, dailyBigLossHalt=2,
    ))
    out.append(StratConfig(
        name="G postLoss=1 + dailyHalt=3",
        probeConfirm=0.45, fearIdeal=50,
        postBigLossCooldown=1, dailyBigLossHalt=3,
    ))
    out.append(StratConfig(
        name="H postLoss=1 + flipSkip=2",
        probeConfirm=0.45, fearIdeal=50,
        postBigLossCooldown=1, directionFlipSkip=2,
    ))
    out.append(StratConfig(
        name="I postLoss=1 + dailyHalt=2 + flipSkip=2",
        probeConfirm=0.45, fearIdeal=50,
        postBigLossCooldown=1, dailyBigLossHalt=2, directionFlipSkip=2,
    ))

    # ── Tier 4: filters with tighter fearIdeal ──
    for fi in [25, 35, 50]:
        out.append(StratConfig(
            name=f"J fi={fi} + postLoss=1 + dailyHalt=2",
            probeConfirm=0.45, fearIdeal=fi,
            postBigLossCooldown=1, dailyBigLossHalt=2,
        ))

    # ── Tier 5: trail tuning + filters ──
    for tt, td in [(4, 1.5), (5, 2.0), (6, 2.0), (10, 3.0), (12, 4.0)]:
        out.append(StratConfig(
            name=f"K trail={tt}/{td} + postLoss=1 + dailyHalt=2 (fi=50)",
            probeConfirm=0.45, fearIdeal=50, trailTrigger=tt, trailDrop=td,
            postBigLossCooldown=1, dailyBigLossHalt=2,
        ))

    # ── Tier 6: probeConfirm tuning + best filters ──
    for pc in [0.30, 0.40, 0.45, 0.50, 0.58, 0.70]:
        out.append(StratConfig(
            name=f"L pc={pc} + postLoss=1 + dailyHalt=2 (fi=50)",
            probeConfirm=pc, fearIdeal=50,
            postBigLossCooldown=1, dailyBigLossHalt=2,
        ))

    # ── Tier 7: aggressive — multiple compounding filters ──
    out.append(StratConfig(
        name="M aggressive: fi=35 + postLoss=2 + dailyHalt=2 + flipSkip=2",
        probeConfirm=0.45, fearIdeal=35,
        postBigLossCooldown=2, dailyBigLossHalt=2, directionFlipSkip=2,
    ))
    out.append(StratConfig(
        name="N defensive: fi=25 + postLoss=2 + dailyHalt=2 + flipSkip=2",
        probeConfirm=0.45, fearIdeal=25,
        postBigLossCooldown=2, dailyBigLossHalt=2, directionFlipSkip=2,
    ))
    out.append(StratConfig(
        name="O ultra: trail=5/1.5 + fi=35 + postLoss=2 + dailyHalt=2",
        probeConfirm=0.45, fearIdeal=35, trailTrigger=5, trailDrop=1.5,
        postBigLossCooldown=2, dailyBigLossHalt=2,
    ))

    return out


def run_all():
    rows = load_probes()
    print(f"Loaded {len(rows)} probes from {rows[0].get('entry_time','?')[:10]} to {rows[-1].get('entry_time','?')[:10]}")
    print()

    configs = all_configs()
    results = []
    for cfg in configs:
        sim_results, no_confirm = run_strategy(rows, cfg)
        s = summarize(sim_results)
        # Also compute worst-day for ranking
        worst_day = min((p for p in s["daily"].values()), default=0)
        best_day = max((p for p in s["daily"].values()), default=0)
        s["worst_day"] = worst_day
        s["best_day"] = best_day
        s["config"] = {
            "name": cfg.name,
            "probeConfirm": cfg.probeConfirm,
            "fearIdeal": cfg.fearIdeal,
            "trailTrigger": cfg.trailTrigger,
            "trailDrop": cfg.trailDrop,
            "postBigLossCooldown": cfg.postBigLossCooldown,
            "directionFlipSkip": cfg.directionFlipSkip,
            "dailyBigLossHalt": cfg.dailyBigLossHalt,
            "consecLossSkip": cfg.consecLossSkip,
            "burstPositionMax": cfg.burstPositionMax,
        }
        results.append(s)
        print(fmt_summary(cfg.name, s))

    # Save JSON
    RESULTS_JSON.write_text(json.dumps({
        "computed_at": datetime.now().isoformat(timespec="seconds"),
        "n_probes": len(rows),
        "results": results,
    }, indent=2), encoding="utf-8")

    # Generate report
    write_report(results, len(rows))
    print(f"\nReport: {REPORT_MD}")


def write_report(results, n_probes):
    lines = []
    lines.append(f"# Strategy Research Report")
    lines.append(f"")
    lines.append(f"_Computed: {datetime.now().isoformat(timespec='seconds')}_")
    lines.append(f"_Probes analyzed: {n_probes}_")
    lines.append(f"")

    # Top by total
    lines.append(f"## Top 10 by total P&L")
    lines.append(f"")
    lines.append(f"| Rank | Strategy | Fired | WR% | Total | Worst day | Best day | Big losses |")
    lines.append(f"|------|----------|-------|-----|-------|-----------|----------|------------|")
    for i, r in enumerate(sorted(results, key=lambda x: -x["total"])[:10]):
        lines.append(
            f"| {i+1} | {r['config']['name']} | {r['fired']} | {r['wr']:.1f} | "
            f"${r['total']:+.2f} | ${r['worst_day']:+.2f} | ${r['best_day']:+.2f} | {r['big_losses']} |"
        )
    lines.append(f"")

    # Top by worst-day (regime robustness)
    lines.append(f"## Top 10 by worst-day P&L (regime robustness)")
    lines.append(f"")
    lines.append(f"| Rank | Strategy | Worst day | Total | WR% |")
    lines.append(f"|------|----------|-----------|-------|-----|")
    for i, r in enumerate(sorted(results, key=lambda x: -x["worst_day"])[:10]):
        lines.append(
            f"| {i+1} | {r['config']['name']} | ${r['worst_day']:+.2f} | "
            f"${r['total']:+.2f} | {r['wr']:.1f} |"
        )
    lines.append(f"")

    # Compare baseline vs best
    base = next((r for r in results if "CURRENT LIVE" in r["config"]["name"]), results[0])
    best_total = max(results, key=lambda x: x["total"])
    best_worst = max(results, key=lambda x: x["worst_day"])

    lines.append(f"## Headline comparison")
    lines.append(f"")
    lines.append(f"| Metric | Baseline (current live) | Best total | Best worst-day |")
    lines.append(f"|--------|-------------------------|------------|----------------|")
    lines.append(f"| Strategy | {base['config']['name']} | {best_total['config']['name']} | {best_worst['config']['name']} |")
    lines.append(f"| Total P&L | ${base['total']:+.2f} | ${best_total['total']:+.2f} | ${best_worst['total']:+.2f} |")
    lines.append(f"| Worst day | ${base['worst_day']:+.2f} | ${best_total['worst_day']:+.2f} | ${best_worst['worst_day']:+.2f} |")
    lines.append(f"| WR | {base['wr']:.1f}% | {best_total['wr']:.1f}% | {best_worst['wr']:.1f}% |")
    lines.append(f"| Trades fired | {base['fired']} | {best_total['fired']} | {best_worst['fired']} |")
    lines.append(f"| Big losses | {base['big_losses']} | {best_total['big_losses']} | {best_worst['big_losses']} |")
    lines.append(f"")

    # All results table
    lines.append(f"## All variants (sorted by total)")
    lines.append(f"")
    lines.append(f"| Strategy | Fired | Skipped | WR% | Total | Worst day | Big losses |")
    lines.append(f"|----------|-------|---------|-----|-------|-----------|------------|")
    for r in sorted(results, key=lambda x: -x["total"]):
        lines.append(
            f"| {r['config']['name']} | {r['fired']} | {r['skipped']} | {r['wr']:.1f} | "
            f"${r['total']:+.2f} | ${r['worst_day']:+.2f} | {r['big_losses']} |"
        )

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run_all()
