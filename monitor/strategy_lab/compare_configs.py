"""
compare_configs.py — compare MT5 Strategy Tester HTML reports across
days and configurations. Designed for Zee's morning workflow:
  1. Run MT5 Strategy Tester for v3.30 on 5 dates
  2. Apply v3.40 patch, re-run on same 5 dates
  3. Run this script to compare per-day, per-config

Place reports in monitor/strategy_lab/tester_runs/ with filename pattern:
  <config>_<YYYY-MM-DD>.html
  e.g. v3.30_2026-02-11.html
       v3.40_2026-02-11.html

The script auto-discovers all reports and pivots to a side-by-side view.

Output: per-config and per-day summary; total deltas.
"""
from __future__ import annotations
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

RUNS_DIR = Path(__file__).parent / "tester_runs"

REPORT_PATTERN = re.compile(r"(v\d+\.\d+)_(\d{4}-\d{2}-\d{2})\.html$", re.IGNORECASE)


def parse_report(path: Path):
    """Return dict with: total_trades, wins, losses, net_pnl, profit_factor,
    max_drawdown, exit_reasons (Counter)."""
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-16-le")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    plain = re.sub(r"<[^>]+>", " ", text)
    plain = re.sub(r"\s+", " ", plain)

    # Parse deals
    deal_re = re.compile(r"(\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2})\s+(\d+)\s+XAUUSD\s+(buy|sell)\s+(in|out)\s+(\d+\.?\d*)\s+(\d+\.\d+)", re.IGNORECASE)
    exit_re = re.compile(r"(\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2})\s+(\d+)\s+XAUUSD\s+(buy|sell)\s+out\s+(\d+\.?\d*)\s+(\d+\.\d+)\s+\d+\s+\d+\.\d+\s+\d+\.\d+\s+(-?\d+\.\d+)\s+([\d ]+\.\d+)\s+(\S+)", re.IGNORECASE)

    entries = [d for d in deal_re.findall(plain) if d[3] == "in"]
    exits   = exit_re.findall(plain)
    exits_by_id = {int(e[1]) - 1: float(e[5]) for e in exits}

    pnls = []
    for d in entries:
        pnl = exits_by_id.get(int(d[1]), 0)
        pnls.append(pnl)

    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    net = sum(pnls)
    # Max drawdown
    equity = 0; peak_eq = 0; max_dd = 0
    for p in pnls:
        equity += p
        peak_eq = max(peak_eq, equity)
        dd = peak_eq - equity
        max_dd = max(max_dd, dd)
    # Profit factor
    gp = sum(wins); gl = abs(sum(losses))
    pf = gp / gl if gl > 0 else float("inf")

    return {
        "n": len(pnls),
        "wins": len(wins), "losses": len(losses),
        "net": net,
        "avg_win": statistics.mean(wins) if wins else 0,
        "avg_loss": statistics.mean(losses) if losses else 0,
        "best": max(pnls, default=0),
        "worst": min(pnls, default=0),
        "wr": len(wins) / len(pnls) * 100 if pnls else 0,
        "pf": pf if pf != float("inf") else 999,
        "max_dd": max_dd,
    }


def main():
    if not RUNS_DIR.exists():
        print(f"Reports dir doesn't exist yet: {RUNS_DIR}")
        print()
        print("Setup workflow (for Zee morning):")
        print("  1. Create directory:")
        print(f"     mkdir -p {RUNS_DIR}")
        print()
        print("  2. Run MT5 Strategy Tester for v3.30 baseline on:")
        print("       2026-02-11 (already validated +$165)")
        print("       2026-04-22 (random recent)")
        print("       2026-05-01 (random recent)")
        print("       2026-05-08 (random recent)")
        print()
        print("  3. Save each as HTML named:")
        print("       v3.30_2026-02-11.html")
        print("       v3.30_2026-04-22.html")
        print("       ... etc")
        print()
        print("  4. Apply v3.40 patch (see v3_40_proposed_patch.md), recompile,")
        print("     re-run Strategy Tester on the same 4 dates, save as:")
        print("       v3.40_2026-02-11.html  etc.")
        print()
        print("  5. Run: py monitor/strategy_lab/compare_configs.py")
        print()
        print("Output: side-by-side WR, net P&L, drawdown, profit factor.")
        sys.exit(0)

    # Discover reports
    runs = defaultdict(dict)  # date → config → stats
    for f in RUNS_DIR.glob("*.html"):
        m = REPORT_PATTERN.match(f.name)
        if not m:
            print(f"  (skip non-matching: {f.name})")
            continue
        config, date = m.group(1).lower(), m.group(2)
        stats = parse_report(f)
        runs[date][config] = stats
        print(f"  Loaded: {config} on {date}: {stats['n']} trades, WR {stats['wr']:.1f}%, net ${stats['net']:+.2f}")

    if not runs:
        print("\nNo matching reports found.")
        sys.exit(0)

    # Find all configs present
    all_configs = sorted({c for date_runs in runs.values() for c in date_runs})
    print(f"\nConfigs: {', '.join(all_configs)}")
    print()

    # Per-day comparison
    print(f"{'date':<12}", end="")
    for c in all_configs:
        print(f"{c+' WR':<8} {c+' net':<11} {c+' DD':<8}  ", end="")
    print()
    print("-" * (12 + 30 * len(all_configs)))

    totals = {c: {"net": 0, "wins": 0, "losses": 0, "n": 0} for c in all_configs}
    for date in sorted(runs):
        print(f"{date}  ", end="")
        for c in all_configs:
            s = runs[date].get(c)
            if not s:
                print(f"{'(none)':<28}  ", end="")
                continue
            print(f"{s['wr']:<7.1f}% ${s['net']:<+9.2f} ${s['max_dd']:<6.0f}  ", end="")
            totals[c]["net"] += s["net"]
            totals[c]["wins"] += s["wins"]
            totals[c]["losses"] += s["losses"]
            totals[c]["n"] += s["n"]
        print()

    print()
    print("TOTALS:")
    for c in all_configs:
        t = totals[c]
        n = t["n"]; w = t["wins"]; l = t["losses"]
        wr = w / n * 100 if n else 0
        print(f"  {c}: {n} trades total  {w}W / {l}L  WR {wr:.1f}%  Net ${t['net']:+.2f}")

    if len(all_configs) == 2:
        c1, c2 = all_configs
        delta = totals[c2]["net"] - totals[c1]["net"]
        print(f"\n  Delta ({c2} - {c1}): ${delta:+.2f}")


if __name__ == "__main__":
    main()
