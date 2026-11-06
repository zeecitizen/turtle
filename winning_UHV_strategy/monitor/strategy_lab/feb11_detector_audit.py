"""feb11_detector_audit.py — do our detectors fire where Zee's hands fired?

Zee, 2026-08-10 04:00: "build them all... bring me answers without me having to
intervene."

The June taxonomy reconstructed his +EUR835 day from the broker statement and named
FIVE strategies plus one universal gate. We only ever built one of the five, without
the gate. This audits each detector against the THIRTEEN entries that taxonomy
timestamped — the only known-good setups in existence for this method.

DOCTRINE: this file counts DETECTIONS, never P&L. Python may generate a hypothesis;
only MT5's Strategy Tester may promote one (see CLAUDE.md, first section). Nothing
here is evidence that anything is profitable — only evidence about whether a detector
sees what Zee saw.
"""
import csv
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BARS = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/tester_xau_feb11.csv")

# Zee's own entries, timestamped in the June taxonomy from his broker statement.
ZEE = [
    ("01:59:04", "buy",  "NSND"),          ("02:09:38", "sell", "UHV+SWEEP+MOM"),
    ("02:29:02", "buy",  "NSND+MOM"),      ("16:49:07", "buy",  "UHV+MOM"),
    ("17:02:45", "buy",  "TAPE"),          ("17:36:13", "buy",  "UHV"),
    ("17:37:26", "buy",  "SWEEP"),         ("17:49:59", "buy",  "UHV"),
    ("19:08:59", "sell", "SWEEP"),         ("19:11:51", "sell", "UHV+SWEEP+MOM"),
    ("19:20:34", "sell", "UHV+SWEEP+MOM"), ("19:26:06", "sell", "UHV"),
    ("19:38:39", "buy",  "TAPE"),
]


def load():
    rows = list(csv.DictReader(BARS.open(encoding="utf-8")))
    o = [float(x["open"]) for x in rows]
    h = [float(x["high"]) for x in rows]
    l = [float(x["low"]) for x in rows]
    c = [float(x["close"]) for x in rows]
    v = [int(x["volume"]) for x in rows]
    t = [int(x["time_unix"]) for x in rows]
    return t, o, h, l, c, v


# ─────────── the universal gate ───────────
def rng60(h, l, i, n=60):
    """'the tape is moving NOW' — this minute's range against the last hour's."""
    if i < n:
        return 0.0
    base = statistics.mean(h[k] - l[k] for k in range(i - n, i))
    return (h[i] - l[i]) / base if base > 0 else 0.0


# ─────────── the four mechanizable strategies ───────────
def is_momentum(o, h, l, c, i, n=20):
    """Lesson: big-bodied candle in trend direction. body/range >= .55 AND >= 1.5x avg."""
    if i < n:
        return None
    body = abs(c[i] - o[i])
    rng = h[i] - l[i]
    if rng <= 0 or body / rng < 0.55:
        return None
    avg = statistics.mean(abs(c[k] - o[k]) for k in range(i - n, i))
    if avg <= 0 or body < 1.5 * avg:
        return None
    return "buy" if c[i] > o[i] else "sell"


def is_sweep(h, l, c, i, n=20):
    """Liquidity sweep: wick BEYOND the recent extreme, close back INSIDE it."""
    if i < n:
        return None
    hi = max(h[i - n:i])
    lo = min(l[i - n:i])
    if h[i] > hi and c[i] < hi:
        return "sell"          # swept the highs and fell back -> stop-hunt above
    if l[i] < lo and c[i] > lo:
        return "buy"           # swept the lows and closed back -> stop-hunt below
    return None


def find_uhv(h, l, c, v, i, look=20, mult=1.3):
    """The loudest recent bar — the climax whose extreme becomes the trigger."""
    if i < look + 2:
        return None
    lo, hi = i - look, i - 1
    j = max(range(lo, hi + 1), key=lambda k: v[k])
    base = statistics.mean(v[k] for k in range(lo, hi + 1))
    if base <= 0 or v[j] < mult * base:
        return None
    return j


def is_uhv_break(o, h, l, c, v, i):
    """UHV breakout: this bar CLOSES beyond the climax bar's extreme, right colour."""
    j = find_uhv(h, l, c, v, i)
    if j is None:
        return None
    if c[i] > h[j] and c[i] > o[i]:
        return "buy"
    if c[i] < l[j] and c[i] < o[i]:
        return "sell"
    return None


def is_nsnd_break(o, h, l, c, v, i, n=20):
    """No-supply / no-demand: a DEAD bar, then the next bar breaks its extreme."""
    if i < n + 1:
        return None
    k = i - 1                                        # the dead bar
    rng_k = h[k] - l[k]
    avg_r = statistics.mean(h[x] - l[x] for x in range(i - n, i))
    avg_v = statistics.mean(v[x] for x in range(i - n, i))
    if avg_r <= 0 or avg_v <= 0:
        return None
    dead = rng_k < 0.8 * avg_r and v[k] < avg_v and v[k] < min(v[i - 4:i - 1] or [v[k] + 1])
    if not dead:
        return None
    if c[i] > h[k]:
        return "buy"
    if c[i] < l[k]:
        return "sell"
    return None


DETECTORS = {
    "UHV":      lambda o, h, l, c, v, i: is_uhv_break(o, h, l, c, v, i),
    "SWEEP":    lambda o, h, l, c, v, i: is_sweep(h, l, c, i),
    "NSND":     lambda o, h, l, c, v, i: is_nsnd_break(o, h, l, c, v, i),
    "MOMENTUM": lambda o, h, l, c, v, i: is_momentum(o, h, l, c, i),
}


def main():
    t, o, h, l, c, v = load()
    idx = {x: i for i, x in enumerate(t)}

    # ── 1. how often does each detector speak at all? ──
    fires = {k: [] for k in DETECTORS}
    gate_ok = 0
    for i in range(60, len(t)):
        if rng60(h, l, i) >= 1.20:
            gate_ok += 1
        for name, fn in DETECTORS.items():
            s = fn(o, h, l, c, v, i)
            if s:
                fires[name].append((i, s))
    print(f"FEB 11 · {len(t):,} bars · {gate_ok} minutes ({gate_ok/len(t)*100:.0f}%) pass the gate\n")
    print("DETECTIONS ACROSS THE DAY            all      gated (rng60>=1.20)")
    for name, f in fires.items():
        g = [x for x in f if rng60(h, l, x[0]) >= 1.20]
        print(f"   {name:10s} {len(f):18,d} {len(g):16,d}")

    # ── 2. THE REAL TEST: does anything fire on Zee's own minutes? ──
    print("\nZEE'S OWN ENTRIES — what did our detectors see at that minute?")
    print(f"   {'time':9s} {'his':5s} {'taxonomy':16s} {'gate':6s} detectors that fired")
    hit = 0
    for hhmm, side, tag in ZEE:
        hh, mm, ss = (int(x) for x in hhmm.split(":"))
        key = int(datetime(2026, 2, 11, hh, mm, tzinfo=timezone.utc).timestamp())
        i = idx.get(key)
        if i is None:
            continue
        g = rng60(h, l, i)
        got = []
        for name, fn in DETECTORS.items():
            # a human fires within the minute; allow the bar itself or the one before
            for k in (i, i - 1):
                s = fn(o, h, l, c, v, k)
                if s == side:
                    got.append(name)
                    break
        if got:
            hit += 1
        print(f"   {hhmm} {side:5s} {tag:16s} {g:5.2f}{'✓' if g >= 1.20 else '✗'}  "
              f"{', '.join(got) if got else '— nothing —'}")
    print(f"\n   COVERAGE: {hit}/{len(ZEE)} of Zee's entries had at least one detector agree.")


if __name__ == "__main__":
    main()
