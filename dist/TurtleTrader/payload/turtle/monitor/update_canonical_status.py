"""update_canonical_status.py — bump the investor-facing status card.

Reads:
  - monitor/strategy_lab/_canonical/results_fvg-none_10d.json   (latest canonical backtest)

Writes:
  - monitor/canonical_status.json                               (served by /api/canonical-status)

Run after each new canonical backtest cycle. Optionally pass --now, --next,
--monday text overrides.
"""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(r"C:/Users/zeesh/Documents/GitHub/turtle")
CANON_RESULTS = REPO / "monitor" / "strategy_lab" / "_canonical" / "results_fvg-none_10d.json"
OUT          = REPO / "monitor" / "canonical_status.json"

# Old EA — frozen comparison baseline (v2.59 / 1-week, 41 trades)
OLD_BASELINE = {"wr": 59.0, "trades": 41, "days": 7, "pf": 1.59, "net_points": 115.04}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--now",    type=str, default=None)
    ap.add_argument("--next",   dest="next_step", type=str, default=None)
    ap.add_argument("--monday", type=str, default=None)
    args = ap.parse_args()

    # Load existing for sensible defaults
    cur = {}
    if OUT.exists():
        try: cur = json.loads(OUT.read_text("utf-8"))
        except Exception: cur = {}

    # Pull latest canonical results
    canonical = cur.get("canonical", {})
    if CANON_RESULTS.exists():
        try:
            d = json.loads(CANON_RESULTS.read_text("utf-8"))
            canonical = {
                "wr": round(d.get("wr_pct", 0), 1),
                "trades": d.get("setups", 0),
                "days": d.get("days", 10),
                "pf": round(d.get("pf", 0), 2) if d.get("pf") != float("inf") else 9.99,
                "net_points": round(d.get("pnl_pts", 0), 2),
            }
        except Exception as e:
            print(f"results parse err: {e}")

    out = {
        "now":     args.now    or cur.get("now",    "Iterating on Zee's canonical UHV strategy."),
        "next":    args.next_step or cur.get("next", "MT5 Tester run + live deploy."),
        "monday":  args.monday or cur.get("monday", "Canonical EA live, WR target ≥ 70%."),
        "canonical": canonical,
        "old":      cur.get("old", OLD_BASELINE),
        "as_of":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
