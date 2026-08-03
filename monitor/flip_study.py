"""flip_study.py — would fewer trend flips have made more money?

Zee 2026-08-03, after watching the trend reverse three times in five minutes: *"pattern
recognition se pata lagayen ke kitni baar agar aapne wahan trend flip pe flip na kiya hota
ya kiya hota to setup successful hota. Ye probabilities ka hi to khel hai."*

He is right that this is answerable rather than arguable. The swing scale is the one knob
that decides how often the trend flips: a small scale calls every wiggle a turn, a large one
waits. So sweep the scale, and for every scale replay the same detector over the same bars,
keep only the setups whose side agreed with the trend at that moment, and score each one on
what price actually did next.

Scoring is deliberately blunt and broker-like: from the entry, did price travel TARGET in
favour before it travelled STOP against? No trailing, no discretion — the same question asked
identically at every scale, so the comparison is about the flips and nothing else.
"""
from __future__ import annotations
import csv, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_entry_review_m5 as B          # noqa: E402
import lifecycle_state as LS               # noqa: E402

TARGET = 3.0      # points in favour  (roughly the TP these trades were reaching)
STOP = 3.0        # points against    (the broker SL the EA actually sets)
HORIZON = 45      # bars to wait for one of them; after that it is a no-decision


def load_iso(path, limit=None):
    """The long history uses time_iso; claude_judge.load_bars only knows time_unix."""
    bars = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            bars.append(B.Bar(datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S"),
                              float(r["open"]), float(r["high"]), float(r["low"]),
                              float(r["close"]), float(r["tick_volume"])))
    bars.sort(key=lambda b: b.t)
    return bars[-limit:] if limit else bars


def outcome(bars, i, side, entry):
    """Did TARGET arrive before STOP? +1 win, -1 loss, 0 undecided inside the horizon."""
    for j in range(i + 1, min(i + 1 + HORIZON, len(bars))):
        b = bars[j]
        if side == "BUY":
            if b.l <= entry - STOP:   return -1
            if b.h >= entry + TARGET: return +1
        else:
            if b.h >= entry + STOP:   return -1
            if b.l <= entry - TARGET: return +1
    return 0


def run(bars, frac, k=1.0):
    """Replay every setup at this swing scale and score it."""
    B.UHV_BODY_MIN = 0.0; B.MIN_ORIGIN_BREAK = 0.0; B.ER_MIN = 0.0
    B.TREND_MIN_HUMP = 0.5 * k; B.TREND_DOM = 0.0     # the swing rule decides, not the hump
    sigs = B.detect_full(bars)
    flips, last_dir = 0, None
    taken = []
    for s in sigs:
        i = s["i"]
        if i < 120 or i >= len(bars) - HORIZON:
            continue
        window = bars[:i + 1]
        seg = window[-60:]
        rng = max(b.h for b in seg) - min(b.l for b in seg)
        hi, ln = LS._pivots(window, min_leg=max(1.0, frac * rng))
        if len(hi) < 2 or len(ln) < 2:
            continue
        # the newest swing decides — Zee's rule, the one under test
        if (hi[-1] if hi else -1) > (ln[-1] if ln else -1):
            h1, h2 = bars[hi[-2]].h, bars[hi[-1]].h
            d = "up" if h2 > h1 else "down" if h2 < h1 else None
        else:
            l1, l2 = bars[ln[-2]].l, bars[ln[-1]].l
            d = "up" if l2 > l1 else "down" if l2 < l1 else None
        if d is None:
            continue
        if d != last_dir:
            flips += 1; last_dir = d
        if {"up": "BUY", "down": "SELL"}[d] != s["side"]:
            continue
        taken.append(outcome(bars, i, s["side"], s["entry"]))
    w = sum(1 for t in taken if t > 0)
    l = sum(1 for t in taken if t < 0)
    u = sum(1 for t in taken if t == 0)
    net = (w * TARGET - l * STOP)
    return {"frac": frac, "flips": flips, "trades": len(taken), "win": w, "loss": l,
            "undecided": u, "wr": (w / (w + l) * 100) if (w + l) else 0.0,
            "net_pts": net}


if __name__ == "__main__":
    src = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/rev_eng_m1.csv")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    bars = load_iso(src, n)
    print(f"  {len(bars)} bars   {bars[0].t:%Y-%m-%d %H:%M} -> {bars[-1].t:%Y-%m-%d %H:%M}")
    print(f"  scoring: +{TARGET} before -{STOP}, {HORIZON} bars to decide\n")
    print(f"  {'scale':>6} {'flips':>7} {'trades':>7} {'win':>5} {'loss':>5} "
          f"{'undec':>6} {'WR%':>6} {'net pts':>9}")
    rows = []
    for frac in (0.06, 0.10, 0.14, 0.19, 0.25, 0.32, 0.40):
        r = run(bars, frac)
        rows.append(r)
        print(f"  {r['frac']:>6.2f} {r['flips']:>7} {r['trades']:>7} {r['win']:>5} "
              f"{r['loss']:>5} {r['undecided']:>6} {r['wr']:>6.1f} {r['net_pts']:>9.1f}")
    best = max(rows, key=lambda r: r["net_pts"])
    print(f"\n  sabse behtar scale {best['frac']}  ->  {best['flips']} flips, "
          f"WR {best['wr']:.1f}%, net {best['net_pts']:+.1f} pts")
