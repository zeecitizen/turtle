"""vsisa_sep_ticks.py — turn OUR recorded September ticks into one file MT5 can load.

Zee, 2026-09-09: *"but blueberry MT5 already exports tick data.. can u check if that file
exists?"* — it does, and he was right that September was testable after all. MT5's own
`XAUUSD/202609.tkc` is a 1,784-byte empty stub in both terminals, but `ShanoTickLogger`
has been writing `shano_ticks_YYYY-MM-DD.csv` to Common\\Files all along: real bid/ask,
~285,000 rows a day.

WHY THIS IS A REAL TEST AND NOT A SIMULATION. The existing CustomSymbolImport builds a
custom symbol from BARS and then synthesises four ticks per bar — fine for a volume
study, useless when the question is which of stop or target was touched first. These are
the actual recorded ticks, so the intrabar path and the real spread both survive, and the
Strategy Tester walks the same prices the broker actually printed.

VOLUME: the CSV's own `volume` column is 0 (gold CFD publishes none), so MT5 will count
ticks per bar and that becomes tick_volume. That is EXACTLY the metric VSISA already
judges on everywhere else — measured, not assumed: iRealVolume returned 0 reads and the
tick-count fallback 8,006,496 over the Feb-Aug court. So September is judged on the same
number as the seven months it was validated on.

TIME: `ts_broker` is already broker/server time, and MT5 datetimes in the tester are
server time, so the stamps are parsed as naive and treated as UTC. Converting would shift
every bar by three hours and silently move every setup.

    py monitor/strategy_lab/vsisa_sep_ticks.py
    py monitor/strategy_lab/vsisa_sep_ticks.py --glob "shano_ticks_2026-08-*.csv"
"""
from __future__ import annotations

import argparse
import calendar
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")


def epoch_ms(stamp: str, ms: str) -> int:
    """'2026.09.08 01:00:07' + '0' -> epoch milliseconds, broker time read AS UTC."""
    d, t = stamp.split(" ")
    y, mo, dy = (int(x) for x in d.split("."))
    hh, mm, ss = (int(x) for x in t.split(":"))
    base = calendar.timegm((y, mo, dy, hh, mm, ss, 0, 0, 0))
    try:
        return base * 1000 + int(ms)
    except ValueError:
        return base * 1000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default="shano_ticks_2026-09-*.csv")
    ap.add_argument("--out", default="vsisa_ticks.csv")
    args = ap.parse_args()

    files = sorted(COMMON.glob(args.glob))
    if not files:
        sys.exit("[ticks] nothing matched %s in %s" % (args.glob, COMMON))

    out = COMMON / args.out
    n = bad = 0
    last = 0
    print("[ticks] %d source files" % len(files), flush=True)
    with open(out, "w", encoding="ascii", newline="") as w:
        w.write("time_msc,bid,ask\n")
        for f in files:
            got = 0
            with open(f, "r", encoding="ascii", errors="replace") as r:
                first = True
                for line in r:
                    if first:
                        first = False
                        if "ts_broker" in line:
                            continue
                    p = line.rstrip("\n").split(",")
                    if len(p) < 4:
                        bad += 1
                        continue
                    try:
                        t = epoch_ms(p[0], p[1])
                        bid = float(p[2])
                        ask = float(p[3])
                    except (ValueError, IndexError):
                        bad += 1
                        continue
                    if bid <= 0 or ask <= 0 or ask < bid:
                        bad += 1
                        continue
                    # CustomTicksReplace REJECTS a stream that goes backwards in time.
                    # The logger rotates at midnight and rows within a second share a
                    # stamp, so ties are nudged forward rather than dropped.
                    if t < last:
                        bad += 1
                        continue
                    if t == last:
                        t = last + 1
                    last = t
                    w.write("%d,%.3f,%.3f\n" % (t, bid, ask))
                    n += 1
                    got += 1
            print("   %-32s %8d ticks" % (f.name, got), flush=True)

    mb = out.stat().st_size / 1e6
    print("\n[ticks] wrote %d ticks (%.1f MB) -> %s" % (n, mb, out))
    print("[ticks] skipped %d malformed/out-of-order rows" % bad)
    if n:
        print("[ticks] span %d -> %d (epoch ms, broker time as UTC)"
              % (int(open(out).readlines()[1].split(",")[0]), last))


if __name__ == "__main__":
    main()
