"""vsisa_validate.py — one VSISA configuration, across SEVEN months of real ticks.

The sweep finds what fitted August. This asks whether the same numbers hold in February,
March, April, May, June and July — months the configuration was never tuned on. A
variant that only pays in the month it was chosen in is a curve fit, and the only way to
see that is to run it somewhere else.

Per feedback_validate_profitability_not_capture: full P&L over many days of real ticks,
never a win rate on the window that produced the setting.

The rig holds XAUUSD real ticks from 2026-02-02. September is a 1,784-byte stub (empty)
— asking for September silently returns a zero-trade result that looks like a refusal,
so the span stops at 2026-09-01.

ONE LAUNCH, NOT SEVEN. The tester log settles how to spend time here:

    Environment synchronized in 0:08:55.959. Test passed in 0:00:00.441

Nine minutes of that is loading tick history and it is paid once per LAUNCH, whatever
the window length; simulating the month itself costs under half a second. Seven monthly
launches would spend an hour of synchronisation to buy four seconds of testing. So the
whole span runs as a single pass and the per-day results are grouped by month afterwards
in Python, where it is free.

    py monitor/strategy_lab/vsisa_validate.py --inputs "InpBigMode=1 InpClusterBars=2"
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from mt5_headless import live_is_safe, sync_experts  # noqa: E402
from trend_lab import stage  # noqa: E402
from vsisa_court import build, run_arm  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SPAN = ("2026.02.02", "2026.09.01")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default="", help="space separated Inp=value")
    ap.add_argument("--label", default="config")
    ap.add_argument("--period", default="M5")
    ap.add_argument("--from", dest="frm", default=SPAN[0])
    ap.add_argument("--to", dest="to", default=SPAN[1])
    ap.add_argument("--deposit", type=int, default=50000)
    ap.add_argument("--delay", type=int, default=163)
    ap.add_argument("--model", type=int, default=4)
    args = ap.parse_args()

    inputs = args.inputs.split()

    live_is_safe()
    stage()
    sync_experts()
    if not build():
        sys.exit(1)

    print("[val] %s | %s | %s -> %s" % (args.label, args.period, args.frm, args.to),
          flush=True)
    print("      %s" % (" ".join(inputs) or "(defaults)"), flush=True)

    r = run_arm(args.label, inputs, args.frm, args.to, args.period,
                args.deposit, args.delay, args.model, 500)
    if not r:
        sys.exit("[val] no report")

    by_month = defaultdict(float)
    days_in = defaultdict(int)
    for d, v in r["day"].items():
        by_month[d[:7]] += v
        days_in[d[:7]] += 1

    print()
    print("=== %s — %s real ticks, %s to %s ==="
          % (args.label, args.period, args.frm, args.to))
    print("%-9s %12s %8s %10s" % ("month", "net", "days", "net/day"))
    print("-" * 42)
    for m in sorted(by_month):
        n, dd = by_month[m], days_in[m]
        print("%-9s %12.2f %8d %10.2f" % (m, n, dd, n / max(1, dd)))
    print("-" * 42)
    tot = sum(by_month.values())
    w, l = r["wins"], r["losses"]
    print("%-9s %12.2f %8d %10.2f"
          % ("TOTAL", tot, len(r["day"]), tot / max(1, len(r["day"]))))
    print()
    print("trades %d · %dW/%dL · win rate %.0f%%"
          % (w + l, w, l, 100.0 * w / max(1, w + l)))
    green = sum(1 for v in by_month.values() if v > 0)
    print("green months: %d/%d   green days: %d/%d"
          % (green, len(by_month),
             sum(1 for v in r["day"].values() if v > 0), len(r["day"])))
    # A configuration that only pays in the month it was chosen in is a curve fit.
    # This line is the one that says so, out loud, before anybody gets excited.
    if by_month and green <= len(by_month) / 2.0:
        print()
        print("*** MOST MONTHS LOSE — this is a fit to the tuning window, not a strategy.")


if __name__ == "__main__":
    main()
