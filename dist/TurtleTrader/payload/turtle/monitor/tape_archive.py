"""tape_archive.py — keep every real bar we ever see, so the tester never runs short.

Zee, 2026-08-10: "the data we have as feb11 ticks, we cannot reliably reproduce the
1M bars from that tick data. that's inaccurate like the python simulation. maybe we
can test on real life bars / ticks gathered from the real market on recent days...
and use Feb11 as our GOAL."

He is right, and the numbers agree: Feb-11's rebuilt bars carry a median volume of 263
(a tick COUNT from one logger) while our live OANDA feed carries 515 (real traded
volume). They are different measurements, so every volume rule — UHV, no-supply,
breakout-volume — means something different on each. Feb 11 cannot judge this strategy.
It can only be the goal.

The live bridge already writes the truth to oanda_m1.csv, but only a 300-bar window;
everything older is overwritten and lost. That is why we keep having 1.6 days of real
gold to test on. This appends every new bar to a permanent archive instead, so the
tester's ground gets bigger every day we run.

    py monitor/tape_archive.py             # fold in whatever the bridge has now
    py monitor/tape_archive.py --loop 60   # daemon
    py monitor/tape_archive.py --export    # write tester_xau_real.csv for MT5 import
"""
import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
LIVE = COMMON / "oanda_m1.csv"                 # the bridge's rolling 300-bar window
ARCHIVE = Path(__file__).with_name("tape_archive_xau.csv")
EXPORT = COMMON / "tester_xau_real.csv"        # what CustomSymbolImport reads
HEAD = ["time_unix", "open", "high", "low", "close", "volume"]


def read(p):
    if not p.exists():
        return {}
    out = {}
    for r in csv.DictReader(p.open(encoding="utf-8", errors="ignore")):
        try:
            out[int(r["time_unix"])] = [r["open"], r["high"], r["low"], r["close"], r["volume"]]
        except Exception:
            continue
    return out


def write(p, rows):
    tmp = p.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEAD)
        for t in sorted(rows):
            w.writerow([t] + rows[t])
    tmp.replace(p)


def fold():
    """Add whatever the bridge is showing to the permanent record.

    The newest bar is deliberately skipped: it is still forming, and a half-built
    candle stored as if it were finished is the kind of quiet lie that took us three
    days to find in the feeds last week.
    """
    live = read(LIVE)
    if not live:
        print("[archive] live feed empty — nothing to fold")
        return 0, 0
    newest = max(live)
    live.pop(newest, None)

    arc = read(ARCHIVE)
    before = len(arc)
    arc.update(live)
    write(ARCHIVE, arc)
    added = len(arc) - before
    if arc:
        a = datetime.fromtimestamp(min(arc), tz=timezone.utc)
        b = datetime.fromtimestamp(max(arc), tz=timezone.utc)
        span = (b - a).total_seconds() / 86400
        print(f"[archive] +{added:4d} new · {len(arc):,} bars · "
              f"{a:%m-%d %H:%M} .. {b:%m-%d %H:%M} UTC · {span:.1f} days of REAL gold")
    return added, len(arc)


def export():
    """Hand the archive to MT5 in the shape CustomSymbolImport expects."""
    arc = read(ARCHIVE)
    if len(arc) < 200:
        print(f"[archive] only {len(arc)} bars — too thin to export yet")
        return
    write(EXPORT, arc)
    a = datetime.fromtimestamp(min(arc), tz=timezone.utc)
    b = datetime.fromtimestamp(max(arc), tz=timezone.utc)
    print(f"[archive] exported {len(arc):,} bars -> {EXPORT.name}")
    print(f"          {a:%Y-%m-%d %H:%M} .. {b:%Y-%m-%d %H:%M} UTC")
    print("          drag CustomSymbolImport with InpCsv=tester_xau_real.csv, "
          "InpNewSymbol=XAUUSD_REAL")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="fold every N seconds (0 = once)")
    ap.add_argument("--export", action="store_true", help="write the MT5 import file")
    a = ap.parse_args()
    if a.export:
        export()
    else:
        while True:
            try:
                fold()
            except Exception as e:
                print(f"[archive] ERROR: {e}", flush=True)
            if not a.loop:
                break
            time.sleep(a.loop)
