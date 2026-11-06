"""
Shano Strategy Lab — variant tester, runs analytical what-ifs against
the EA's recent trade history and surfaces variants that would have
out-performed the live config.

Usage:
    python lab.py                  # run all variants, append to results.json + RESULTS.md
    python lab.py --variants V1,V3 # run only listed variants
    python lab.py --propose        # ask Claude to propose 3 NEW variants based on last results
    python lab.py --apply BEST     # write the best-EV variant to live shano_config.json

The lab does NOT run live trades. It evaluates "what would each variant have
done given today's live data" by reasoning over:
  - EA's history field (closed trades with timestamp/lots/pnl)
  - shano_live.json's today_main_wins/losses + week stats
  - turtle_fills.csv if available

Each variant is a partial config override + an exit-policy override class.
The simulator estimates "would the new exit policy have closed this trade
earlier/later?" using a peak-recovery model:
  * trades that exited at -fearIdeal: assume actual loss could have been
    bounded at variant.fearIdeal instead.
  * trades that exited at -washout: same.
  * trades that exited at trail: estimate impact of variant trail params.
  * recovery rate (R) is the % of "would-have-been-fearIdeal" trades that
    actually came back to a small win — calibrated from historical data.

Limitations: this is analytical, not tick-by-tick. Treat results as a
SCREEN — apply the top variant to live, monitor for an hour, ratify.
"""

from __future__ import annotations
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Callable

LAB_DIR = Path(__file__).parent
MON_DIR = LAB_DIR.parent
LIVE_JSON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_live.json")
CONFIG_JSON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_config.json")
RESULTS_JSON = LAB_DIR / "results.json"
RESULTS_MD = LAB_DIR / "RESULTS.md"
HISTORY_LOG = LAB_DIR / "history.jsonl"


# ──────────────────────────────────────────────────────────────────
#  Variant definitions
# ──────────────────────────────────────────────────────────────────
@dataclass
class Variant:
    id: str
    name: str
    rationale: str
    overrides: dict          # partial config dict
    # recovery model assumption: of trades that hit -fearIdeal, what fraction
    # would have eventually recovered if held longer? (0.0 = none, 1.0 = all)
    recovery_rate: float = 0.50
    # if recovered, what's the avg outcome? (typical small win)
    recovered_pnl: float = 5.0


VARIANTS: list[Variant] = [
    Variant(
        id="V0_baseline",
        name="Baseline (current live)",
        rationale="Current live config — establishes what we're beating",
        overrides={},
    ),
    Variant(
        id="V1_tightCut",
        name="Tight loss cut: fearIdeal=25",
        rationale="Today's three -$72 losses suggest -$70 is too wide for current regime. "
                  "Shano herself said -$10 cut in early interview. Test sharper cut.",
        overrides={"fearIdeal": 25.0},
        recovery_rate=0.40,
    ),
    Variant(
        id="V2_holdLonger",
        name="Hold longer: fearIdeal=120, washout=200",
        rationale="Shano's actual stated rule (later interview): wait for losing trade "
                  "to come back, no time limit. Push fearIdeal back so trades can recover.",
        overrides={"fearIdeal": 120.0, "fearWashout": 200.0},
        recovery_rate=0.75,
    ),
    Variant(
        id="V3_fastTrail",
        name="Fast trail capture: trigger=4, drop=1",
        rationale="Win avg is only $24 — trail is too patient. Capture more small wins "
                  "by triggering trail at +$4 (was $8) and exiting on $1 drop (was $2).",
        overrides={"trailTrigger": 4.0, "trailDrop": 1.0},
    ),
    Variant(
        id="V4_letRunners",
        name="Let runners run: trigger=15, drop=4",
        rationale="The +$92 win shows big runs exist. Wider trail captures them.",
        overrides={"trailTrigger": 15.0, "trailDrop": 4.0},
    ),
    Variant(
        id="V5_stricterProbe",
        name="Stricter probe confirm: 1.20",
        rationale="Many probes failing at -$3 means probe filter is too loose. "
                  "Require stronger signal (probe to +$1.20 instead of +$0.58) before main.",
        overrides={"probeConfirm": 1.20},
    ),
    Variant(
        id="V6_noBurst",
        name="No bursting: maxBurst=1",
        rationale="Two -$72 losses at same timestamp = burst overstaying its welcome. "
                  "Disable bursting, take isolated trades only.",
        overrides={"maxBurst": 1},
    ),
    Variant(
        id="V7_combo_tight",
        name="Combo: tightCut + fastTrail",
        rationale="Compress R:R on both sides. Smaller wins more often, smaller losses less often.",
        overrides={"fearIdeal": 25.0, "trailTrigger": 4.0, "trailDrop": 1.0},
        recovery_rate=0.40,
    ),
    Variant(
        id="V8_combo_patient",
        name="Combo: holdLonger + letRunners + stricterProbe",
        rationale="Fewer trades, higher quality, hold for big moves.",
        overrides={"fearIdeal": 120.0, "fearWashout": 200.0, "trailTrigger": 15.0,
                   "trailDrop": 4.0, "probeConfirm": 1.20},
        recovery_rate=0.75,
    ),
    Variant(
        id="V9_smallSize",
        name="Smaller main size: probeFail=2.0 + main 0.20 (via override)",
        rationale="Half-size mains halve the dollar damage of any loss. "
                  "Lets us test the strategy's edge without account-killing draws.",
        overrides={"overrideLots": 0.20, "probeFail": 2.0},
    ),
]


# ──────────────────────────────────────────────────────────────────
#  Trade replay
# ──────────────────────────────────────────────────────────────────
def load_live() -> dict:
    if not LIVE_JSON.exists():
        return {}
    try:
        return json.loads(LIVE_JSON.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def load_baseline_config() -> dict:
    if not CONFIG_JSON.exists():
        return {}
    try:
        return json.loads(CONFIG_JSON.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def classify_trade(trade: dict, baseline_cfg: dict) -> str:
    """Classify the closure reason from pnl + lots."""
    pnl = trade.get("pnl", 0)
    lots = trade.get("lots", 0)
    if lots <= 0.02:  # probe
        if pnl <= -baseline_cfg.get("probeFail", 3.0) + 0.5:
            return "probe_fail"
        if pnl > 0:
            return "probe_confirm_or_close"
        return "probe_close_with_main"
    # main trade
    fearIdeal = baseline_cfg.get("fearIdeal", 35.0)
    fearWashout = baseline_cfg.get("fearWashout", 180.0)
    trailTrigger = baseline_cfg.get("trailTrigger", 8.0)
    if pnl <= -fearWashout * 0.85:
        return "main_washout"
    if pnl <= -fearIdeal * 0.85:
        return "main_fearIdeal"
    if pnl > 0:
        return "main_trail_win"
    return "main_small_loss"


def apply_variant(trade: dict, variant: Variant, baseline_cfg: dict) -> float:
    """Return what the variant's PNL would have been for this trade.

    Models:
      * if main trade hit -fearIdeal under baseline:
          variant might cut earlier (smaller loss) or hold longer (recovery odds).
      * if main trade hit washout: variant might cut earlier.
      * if main trade was a trail win: scale by trail-param ratio.
      * probe trades: applied probeConfirm/probeFail changes proportionally.
    """
    pnl = trade.get("pnl", 0)
    lots = trade.get("lots", 0)
    cls = classify_trade(trade, baseline_cfg)

    base_fI = baseline_cfg.get("fearIdeal", 35.0)
    base_fW = baseline_cfg.get("fearWashout", 180.0)
    base_tT = baseline_cfg.get("trailTrigger", 8.0)
    base_tD = baseline_cfg.get("trailDrop", 2.0)

    var_cfg = {**baseline_cfg, **variant.overrides}
    var_fI = var_cfg.get("fearIdeal", base_fI)
    var_fW = var_cfg.get("fearWashout", base_fW)
    var_tT = var_cfg.get("trailTrigger", base_tT)
    var_tD = var_cfg.get("trailDrop", base_tD)
    var_lots_override = var_cfg.get("overrideLots", 0.0)

    # apply size scaling for main trades
    size_ratio = 1.0
    if lots > 0.02 and var_lots_override > 0:
        size_ratio = var_lots_override / max(lots, 0.01)

    if cls == "main_fearIdeal":
        # Original loss was capped at -fearIdeal. Variant could:
        #   - cut tighter: definite -var_fI loss
        #   - hold longer: recovery_rate chance of recovered_pnl, else -var_fI
        if var_fI <= base_fI * 0.95:
            # tighter cut — guaranteed smaller loss (in $ terms)
            return -var_fI * size_ratio
        elif var_fI >= base_fI * 1.10:
            # holding longer
            recovered = variant.recovery_rate * variant.recovered_pnl
            not_recovered = (1 - variant.recovery_rate) * (-var_fI)
            return (recovered + not_recovered) * size_ratio
        else:
            # similar — pass through (scaled)
            return pnl * size_ratio

    if cls == "main_washout":
        # variant fearWashout
        if var_fW < base_fW:
            return -var_fW * size_ratio
        return pnl * size_ratio

    if cls == "main_trail_win":
        # peak likely > pnl + base_tD. with tighter trail (var_tT < base_tT)
        # we'd capture similar but exit slightly earlier (less ideal exit).
        # with wider trail (var_tT > base_tT), we'd exit later (potentially better,
        # but risk of trail not engaging at all).
        if var_tT < base_tT * 0.80:
            # fast trail: assume we capture ~70% of the win (exit earlier)
            return max(var_tT, pnl * 0.7) * size_ratio
        elif var_tT > base_tT * 1.30:
            # wide trail: 60% chance of better exit (+$3), 40% chance trail never engages
            return (0.6 * (pnl + 3) + 0.4 * pnl * 0.6) * size_ratio
        return pnl * size_ratio

    if cls == "main_small_loss":
        return pnl * size_ratio

    # probe trades
    if cls == "probe_fail":
        var_pf = var_cfg.get("probeFail", baseline_cfg.get("probeFail", 3.0))
        return -var_pf
    if cls == "probe_confirm_or_close":
        # higher probeConfirm = fewer mains, but probe outcome similar
        return pnl
    return pnl


# ──────────────────────────────────────────────────────────────────
#  Run a variant
# ──────────────────────────────────────────────────────────────────
def run_variant(variant: Variant, history: list, baseline_cfg: dict) -> dict:
    main_trades = [t for t in history if t.get("lots", 0) > 0.02]
    probes = [t for t in history if t.get("lots", 0) <= 0.02]

    actual_main = sum(t["pnl"] for t in main_trades)
    actual_probe = sum(t["pnl"] for t in probes)
    actual_total = actual_main + actual_probe

    sim_main = sum(apply_variant(t, variant, baseline_cfg) for t in main_trades)
    sim_probe = sum(apply_variant(t, variant, baseline_cfg) for t in probes)
    sim_total = sim_main + sim_probe

    main_wins = [t for t in main_trades if t["pnl"] > 0]
    main_losses = [t for t in main_trades if t["pnl"] <= 0]
    sim_main_pnls = [apply_variant(t, variant, baseline_cfg) for t in main_trades]
    sim_wins = [p for p in sim_main_pnls if p > 0]
    sim_losses = [p for p in sim_main_pnls if p <= 0]

    return {
        "id": variant.id,
        "name": variant.name,
        "rationale": variant.rationale,
        "overrides": variant.overrides,
        "actual_total": round(actual_total, 2),
        "sim_total": round(sim_total, 2),
        "delta": round(sim_total - actual_total, 2),
        "actual_main_pnl": round(actual_main, 2),
        "sim_main_pnl": round(sim_main, 2),
        "actual_probe_pnl": round(actual_probe, 2),
        "sim_probe_pnl": round(sim_probe, 2),
        "main_count": len(main_trades),
        "main_actual_wins": len(main_wins),
        "main_sim_wins": len(sim_wins),
        "main_avg_actual_win": round(sum(t["pnl"] for t in main_wins) / max(len(main_wins), 1), 2),
        "main_avg_sim_win": round(sum(sim_wins) / max(len(sim_wins), 1), 2),
        "main_avg_actual_loss": round(sum(t["pnl"] for t in main_losses) / max(len(main_losses), 1), 2),
        "main_avg_sim_loss": round(sum(sim_losses) / max(len(sim_losses), 1), 2),
    }


# ──────────────────────────────────────────────────────────────────
#  Persistence
# ──────────────────────────────────────────────────────────────────
def write_results(results: list, baseline_cfg: dict, history: list):
    snap = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "baseline_config": baseline_cfg,
        "history_size": len(history),
        "history_window": [
            history[-1].get("time", "?") if history else "?",
            history[0].get("time", "?") if history else "?",
        ],
        "results": results,
    }
    RESULTS_JSON.write_text(json.dumps(snap, indent=2), encoding="utf-8")

    with HISTORY_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snap) + "\n")

    write_markdown(snap)


def write_markdown(snap: dict):
    lines = []
    lines.append(f"# Strategy Lab Results")
    lines.append(f"")
    lines.append(f"_Last run: {snap['ts']}_  ")
    lines.append(f"_History window: {snap['history_window'][0]} → {snap['history_window'][1]}_  ")
    lines.append(f"_Trades analyzed: {snap['history_size']}_")
    lines.append(f"")
    lines.append(f"## Variants ranked by simulated total P&L")
    lines.append(f"")
    lines.append(f"| Rank | Variant | Δ vs actual | Sim total | Sim main | Sim wins/loss avg |")
    lines.append(f"|------|---------|-------------|-----------|----------|-------------------|")
    sorted_results = sorted(snap["results"], key=lambda r: -r["sim_total"])
    for i, r in enumerate(sorted_results):
        lines.append(
            f"| {i+1} | **{r['name']}** | {r['delta']:+.2f} | {r['sim_total']:+.2f} | "
            f"{r['sim_main_pnl']:+.2f} | +{r['main_avg_sim_win']:.1f} / {r['main_avg_sim_loss']:.1f} |"
        )
    lines.append(f"")
    lines.append(f"## Top variant detail")
    if sorted_results:
        top = sorted_results[0]
        lines.append(f"")
        lines.append(f"**{top['name']}**  ")
        lines.append(f"Rationale: {top['rationale']}")
        lines.append(f"")
        lines.append(f"```json")
        lines.append(json.dumps(top["overrides"], indent=2))
        lines.append(f"```")
        lines.append(f"")
        lines.append(f"Apply with: `python lab.py --apply {top['id']}`")
    lines.append(f"")
    lines.append(f"## Baseline config (live)")
    lines.append(f"```json")
    lines.append(json.dumps(snap["baseline_config"], indent=2))
    lines.append(f"```")
    RESULTS_MD.write_text("\n".join(lines), encoding="utf-8")


def apply_variant_to_live(variant_id: str):
    variant = next((v for v in VARIANTS if v.id == variant_id), None)
    if not variant:
        print(f"  [ERR] variant {variant_id} not found")
        return False
    cfg = load_baseline_config()
    if not cfg:
        print("  [ERR] could not read live config")
        return False
    cfg.update(variant.overrides)
    CONFIG_JSON.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"  [OK] applied {variant.id} to live config: {variant.overrides}")
    return True


# ──────────────────────────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", help="comma-separated variant ids (default: all)")
    ap.add_argument("--apply", help="apply variant id to live config")
    ap.add_argument("--list", action="store_true", help="list variants")
    args = ap.parse_args()

    if args.list:
        for v in VARIANTS:
            print(f"  {v.id:20s} {v.name}")
            print(f"  {'':22s}{v.rationale}")
            print()
        return 0

    if args.apply:
        return 0 if apply_variant_to_live(args.apply) else 1

    live = load_live()
    history = live.get("history", [])
    baseline_cfg = load_baseline_config()

    if not history:
        print("  [WARN] no trade history in shano_live.json — lab cannot evaluate")
        return 1

    selected = VARIANTS
    if args.variants:
        ids = set(args.variants.split(","))
        selected = [v for v in VARIANTS if v.id in ids]

    print(f"  running {len(selected)} variants over {len(history)} trades...")
    results = [run_variant(v, history, baseline_cfg) for v in selected]
    write_results(results, baseline_cfg, history)
    print(f"  results -> {RESULTS_MD}")
    print(f"")
    sorted_results = sorted(results, key=lambda r: -r["sim_total"])
    print(f"  Top 3 variants:")
    for r in sorted_results[:3]:
        print(f"    {r['id']:20s} sim={r['sim_total']:+7.2f}  delta={r['delta']:+7.2f}  {r['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
