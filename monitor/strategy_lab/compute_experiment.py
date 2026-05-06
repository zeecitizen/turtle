"""compute_experiment.py — uses unified_backtester to run real filter-aware
backtests against an experiment's stored params + filter flags.

Called via POST /api/shadow/<id>/compute (server.js dispatches to this).

Usage:
    python compute_experiment.py <experiment_id>

Reads:
  experiments/<id>.json  — params + filter flags
Writes:
  experiments/<id>_results.json — full backtest results

Replaces the older clipping-based simulator with proper tick-replay.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path
from datetime import datetime

LAB_DIR = Path(__file__).parent
EXP_DIR = LAB_DIR / "experiments"

sys.path.insert(0, str(LAB_DIR))
from unified_backtester import Config, run as ub_run


def load_experiment(exp_id: str) -> dict:
    p = EXP_DIR / f"{exp_id}.json"
    if not p.exists():
        raise FileNotFoundError(f"experiment not found: {exp_id}")
    return json.loads(p.read_text(encoding="utf-8"))


def compute(exp_id: str) -> dict:
    exp = load_experiment(exp_id)
    p = exp.get("params", {})

    cfg = Config(
        name=exp.get("name", exp_id),
        probeConfirm=float(p.get("probeConfirm", 0.58)),
        probeFail=float(p.get("probeFail", 3.0)),
        probeLots=float(p.get("probeLots", 0.01)),
        trailTrigger=float(p.get("trailTrigger", 8.0)),
        trailDrop=float(p.get("trailDrop", 2.0)),
        fearIdeal=float(p.get("fearIdeal", 70.0)),
        mainLots=float(p.get("mainLots", 0.40)),
        skipBadHours=bool(p.get("skipBadHours", False)),
        trendFilter=bool(p.get("trendFilter", False)),
        skipMfeDeadZone=bool(p.get("skipMfeDeadZone", False)),
        skipFastConfirm=bool(p.get("skipFastConfirm", False)),
        skipPriorChop=int(p.get("skipPriorChop", 0)),
        skipPriorLossOpposite=bool(p.get("skipPriorLossOpposite", False)),
        minConfirmSpeedSec=int(p.get("minConfirmSpeedSec", 0)),
        maxConfirmSpeedSec=int(p.get("maxConfirmSpeedSec", 0)),
        requireWithTrend=bool(p.get("requireWithTrend", False)),
        trendTfMinutes=int(p.get("trendTfMinutes", 1)),
        uhvFilter=bool(p.get("uhvFilter", False)),
        uhvLookback=int(p.get("uhvLookback", 20)),
    )

    result = ub_run(cfg)

    # Translate to the JSON shape the dashboard expects (matches what frontend reads)
    metrics = {
        "fired": result["fired"],
        "skipped_no_confirm": result["skipped_no_confirm"],
        "skipped_filtered": result["skipped_filtered"],
        "wins": result["wins"],
        "losses": result["losses"],
        "big_losses": result["big_losses"],
        "actual_confirmed_058": result["fired"] + result["skipped_filtered"],  # how many would confirm
        "would_confirm_at_threshold": result["fired"] + result["skipped_filtered"],
        "extra_confirms_vs_058": result["skipped_filtered"],  # surface filter effect
        "actual_total_pnl": None,  # historical comparison not relevant in this view
        "sim_main_total_pnl": result["total"],
        "missed_potential_pnl": 0,
        "sim_win_rate_pct": result["wr"],
        "sim_avg_win": result["avg_win"],
        "sim_avg_loss": result["avg_loss"],
        "max_loss": result["max_loss"],
        "daily": result["daily"],
    }

    return {
        "experiment_id": exp_id,
        "name": exp.get("name", exp_id),
        "params": p,
        "computed_at": datetime.now().isoformat(timespec="seconds"),
        "n_probes_analyzed": result["fired"] + result["skipped_filtered"] + result["skipped_no_confirm"],
        "metrics": metrics,
        "engine": "unified_backtester (full tick-replay with filter logic)",
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: compute_experiment.py <id>"}))
        return 1
    exp_id = sys.argv[1]
    try:
        result = compute(exp_id)
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e)}))
        return 1
    except Exception as e:
        import traceback
        print(json.dumps({"error": f"compute failed: {e}", "trace": traceback.format_exc()}))
        return 1

    out_path = EXP_DIR / f"{exp_id}_results.json"
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
