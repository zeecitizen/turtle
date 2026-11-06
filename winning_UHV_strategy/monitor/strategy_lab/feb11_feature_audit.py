"""feb11_feature_audit.py — what actually separates Zee's entries from noise?

Zee, 2026-08-10 04:00: "build them all... bring me answers."

The June taxonomy's 'universal gate' (rng60_norm >= 1.20) was refuted tonight: his
entries score 1.04 against a random-moment median of 1.02. That failure had one cause
worth not repeating — features were fitted to his entries with no null baseline, so
anything that "looked like a pattern" survived.

So this audit does it the other way round. Every candidate feature is measured BOTH at
his 13 known entries AND at 400 random moments of the same day. A feature only counts
if the two distributions actually differ.

DOCTRINE: this counts and describes; it never simulates P&L. Python may generate a
hypothesis, only MT5 may promote one (CLAUDE.md, first section).
"""
import bisect
import csv
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

C = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
TICKS = C / "shano_ticks_2026-02-11.csv"
BARS = C / "tester_xau_feb11.csv"

ZEE = [("01:59:04", "buy"), ("02:09:38", "sell"), ("02:29:02", "buy"),
       ("16:49:07", "buy"), ("17:02:45", "buy"), ("17:36:13", "buy"),
       ("17:37:26", "buy"), ("17:49:59", "buy"), ("19:08:59", "sell"),
       ("19:11:51", "sell"), ("19:20:34", "sell"), ("19:26:06", "sell"),
       ("19:38:39", "buy")]


def load():
    T, B = [], []
    with TICKS.open(encoding="utf-8", errors="ignore") as f:
        next(f)
        for line in f:
            try:
                ts, bid, _ = line.rstrip("\n").split(",")
                d = datetime.strptime(ts[:19], "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
                T.append(d.timestamp())
                B.append(float(bid))
            except Exception:
                continue
    rows = list(csv.DictReader(BARS.open(encoding="utf-8")))
    bt = [int(x["time_unix"]) for x in rows]
    bo = [float(x["open"]) for x in rows]
    bh = [float(x["high"]) for x in rows]
    bl = [float(x["low"]) for x in rows]
    bc = [float(x["close"]) for x in rows]
    bv = [int(x["volume"]) for x in rows]
    return T, B, bt, bo, bh, bl, bc, bv


class Tape:
    def __init__(self):
        self.T, self.B, self.bt, self.bo, self.bh, self.bl, self.bc, self.bv = load()
        self.bi = {t: i for i, t in enumerate(self.bt)}

    def seg(self, t, win):
        a = bisect.bisect_left(self.T, t - win)
        b = bisect.bisect_right(self.T, t)
        return self.B[a:b]

    def bar_at(self, t):
        return self.bi.get(int(t) - int(t) % 60)

    # ─── candidate features, each answering one plain question ───
    def f_move60(self, t, side):
        """how far has price travelled in the last minute, in the trade's favour?"""
        s = self.seg(t, 60)
        if len(s) < 5:
            return None
        d = s[-1] - s[0]
        return d if side == "buy" else -d

    def f_pullback(self, t, side):
        """is he entering AGAINST the last few minutes — buying a dip, selling a pop?"""
        i = self.bar_at(t)
        if i is None or i < 5:
            return None
        d = self.bc[i - 1] - self.bc[i - 5]
        return -d if side == "buy" else d          # positive = he is fading the move

    def f_pos_in_range(self, t, side):
        """where in the last hour's range is he buying? 0 = at the low, 1 = at the high"""
        i = self.bar_at(t)
        if i is None or i < 60:
            return None
        hi = max(self.bh[i - 60:i]); lo = min(self.bl[i - 60:i])
        if hi <= lo:
            return None
        p = (self.bc[i - 1] - lo) / (hi - lo)
        return p if side == "buy" else 1 - p        # low value = buying low / selling high

    def f_prev_vol(self, t, side):
        """was the minute before his entry LOUD or QUIET, against the last 20?"""
        i = self.bar_at(t)
        if i is None or i < 21:
            return None
        avg = statistics.mean(self.bv[i - 21:i - 1])
        return self.bv[i - 1] / avg if avg > 0 else None

    def f_prev_colour(self, t, side):
        """did he buy after a RED minute / sell after a GREEN one? 1 = yes, 0 = no"""
        i = self.bar_at(t)
        if i is None or i < 2:
            return None
        red = self.bc[i - 1] < self.bo[i - 1]
        return 1.0 if (red if side == "buy" else not red) else 0.0

    def f_velocity(self, t, side):
        """ticks per second in the last minute — is the market busy right now?"""
        s = self.seg(t, 60)
        return len(s) / 60.0 if s else None

    def f_swept(self, t, side):
        """did the last 5 minutes poke BEYOND the prior hour's extreme and come back?"""
        i = self.bar_at(t)
        if i is None or i < 65:
            return None
        hi = max(self.bh[i - 65:i - 5]); lo = min(self.bl[i - 65:i - 5])
        if side == "buy":
            return 1.0 if min(self.bl[i - 5:i]) < lo <= self.bc[i - 1] else 0.0
        return 1.0 if max(self.bh[i - 5:i]) > hi >= self.bc[i - 1] else 0.0


FEATURES = [
    ("move in last 60s (favour)", "f_move60",      "$"),
    ("fading the last 5 min",     "f_pullback",    "$"),
    ("position in hour range",    "f_pos_in_range", " "),
    ("prev-minute volume ratio",  "f_prev_vol",    "x"),
    ("prev minute counter-colour", "f_prev_colour", " "),
    ("tick velocity (ticks/s)",   "f_velocity",    " "),
    ("swept an extreme",          "f_swept",       " "),
]


def main():
    tp = Tape()
    print(f"ticks {len(tp.T):,} · bars {len(tp.bt):,}\n")

    zt = []
    for hhmm, side in ZEE:
        h, m, s = (int(x) for x in hhmm.split(":"))
        zt.append((datetime(2026, 2, 11, h, m, s, tzinfo=timezone.utc).timestamp(), side))

    # null baseline: random moments of the SAME day, same side mix
    random.seed(11)
    lo, hi = tp.T[0] + 4000, tp.T[-1] - 200
    null = [(lo + random.random() * (hi - lo), random.choice(["buy", "sell"])) for _ in range(400)]

    print(f"{'feature':30s} {'HIS 13':>12s} {'random 400':>12s} {'separation':>12s}")
    print("-" * 70)
    rows = []
    for label, fn, unit in FEATURES:
        f = getattr(tp, fn)
        a = [x for x in (f(t, s) for t, s in zt) if x is not None]
        b = [x for x in (f(t, s) for t, s in null) if x is not None]
        if len(a) < 5 or len(b) < 50:
            continue
        ma, mb = statistics.median(a), statistics.median(b)
        sd = statistics.pstdev(b) or 1e-9
        z = (ma - mb) / sd                       # how many null-sigmas apart the medians are
        rows.append((abs(z), label, ma, mb, z, unit))
    for _, label, ma, mb, z, unit in sorted(rows, reverse=True):
        flag = "  <<< SEPARATES" if abs(z) >= 0.60 else ""
        print(f"{label:30s} {ma:11.2f}{unit} {mb:11.2f}{unit} {z:+11.2f}σ{flag}")
    print("\nσ = how far his median sits from the random median, in random-population "
          "standard deviations.\nAnything under ~0.6σ with n=13 is noise, not a pattern.")


if __name__ == "__main__":
    main()
