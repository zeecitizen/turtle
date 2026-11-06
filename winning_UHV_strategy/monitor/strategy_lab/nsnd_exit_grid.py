"""nsnd_exit_grid.py — the NS/ND entries are Zee's; the exit is the variable. Find it.

The first honest run of backtest_nsnd_lessons.py came back 24.4% WR and -$724 over 17 days, and
the gates he calls quality markers (a real UHV before the candle, an FVG tapped) each made it
WORSE, not better. That combination is the signature of a good entry wearing a bad exit:
[[exit-is-the-edge]] — "83% of entries were always good; the tight stop and capped exit were the
whole problem."

Two specific suspicions worth testing rather than arguing about:

  1. The stop is TOO TIGHT to survive M1 noise. His stop sits just under a candle that is by
     definition tiny, so risk is often half a point — on gold M1 the next wick takes it out
     whether or not he was right about direction. He is watching the tape and can re-enter; a
     bot cannot.
  2. The structural high is TOO FAR to be a realistic first target. [[ns-nd-profitable-config]]
     found this same pattern paid +$580/12d with a FIXED $12 target and a 1-pip stop — a
     completely different exit from the one lesson 07 describes for a human.

So: hold the entries exactly as the lessons define them, and sweep the exit. Fixed targets,
stop multiples of the pattern's own risk, and a give-back trail. Whatever wins here is what
goes live — and if nothing does, that is the finding and it gets reported as one.
"""
from __future__ import annotations
import sys, glob, os
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))

from screener_canonical_uhv_m1 import build_m1     # noqa: E402
import nsnd_detector as NS                         # noqa: E402

COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
LOTS = 0.10
USD_PT = 100 * LOTS
SPREAD_PT = 0.20


def collect_signals():
    """Every NS/ND entry across every tick day, with the bars needed to walk it forward."""
    out = []
    for f in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        day = os.path.basename(f)[12:22]
        try:
            bars = build_m1([Path(f)])
        except Exception:
            continue
        if len(bars) < 60:
            continue
        taken_until = -1
        for i in range(5, len(bars)):
            if i <= taken_until:
                continue
            s = NS.detect_any(bars, True, i)
            if s:
                out.append((day, bars, s))
                taken_until = i + 3          # let the next one breathe; re-checked per-exit below
    return out


def walk_R(bars, s, sl_mult, be_at_R, tp_R):
    """Zee's exit: stop at the no-supply low, breakeven at be_at_R, target tp_R x risk."""
    risk = abs(s.entry - s.sl) * sl_mult
    if risk <= 0:
        return 0.0, s.brk_i
    be_armed = False
    for k in range(s.brk_i + 1, len(bars)):
        b = bars[k]
        fav = (b.h - s.entry) if s.side == "BUY" else (s.entry - b.l)
        adv = (s.entry - b.l) if s.side == "BUY" else (b.h - s.entry)
        if be_armed and adv >= 0:            # stop is at entry - scratched, not a loss
            return 0.0, k
        if not be_armed and adv >= risk:     # stop first, always
            return -risk, k
        if fav >= tp_R * risk:
            return tp_R * risk, k
        if not be_armed and fav >= be_at_R * risk:
            be_armed = True
    last = bars[-1].c
    return ((last - s.entry) if s.side == "BUY" else (s.entry - last)), len(bars) - 1


def score_R(sigs, sl_mult, be_at_R, tp_R):
    net = 0.0; w = l = 0
    for _d, bars, s in sigs:
        pts, _k = walk_R(bars, s, sl_mult, be_at_R, tp_R)
        usd = (pts - SPREAD_PT) * USD_PT
        net += usd; w += usd > 0; l += usd <= 0
    return net, w, l


def walk(bars, s, sl_mult, tp_pts, trail_arm, trail_give):
    """One exit policy, walked bar by bar. Stop wins ties."""
    risk = abs(s.entry - s.sl)
    sl = (s.entry - risk * sl_mult) if s.side == "BUY" else (s.entry + risk * sl_mult)
    tp = (s.entry + tp_pts) if s.side == "BUY" else (s.entry - tp_pts)
    peak = 0.0
    for k in range(s.brk_i + 1, len(bars)):
        b = bars[k]
        fav = (b.h - s.entry) if s.side == "BUY" else (s.entry - b.l)
        adv = (s.entry - b.l) if s.side == "BUY" else (b.h - s.entry)
        if adv >= risk * sl_mult:                       # stop first, always
            return -risk * sl_mult, k
        if tp_pts and fav >= tp_pts:
            return tp_pts, k
        peak = max(peak, fav)
        if trail_arm and peak >= trail_arm:
            close_p = (b.c - s.entry) if s.side == "BUY" else (s.entry - b.c)
            if peak - close_p >= trail_give:
                return close_p, k
    last = bars[-1].c
    return ((last - s.entry) if s.side == "BUY" else (s.entry - last)), len(bars) - 1


def score(sigs, sl_mult, tp_pts, trail_arm, trail_give):
    net = 0.0
    w = l = 0
    for _day, bars, s in sigs:
        pts, _k = walk(bars, s, sl_mult, tp_pts, trail_arm, trail_give)
        usd = (pts - SPREAD_PT) * USD_PT
        net += usd
        w += usd > 0
        l += usd <= 0
    return net, w, l


if __name__ == "__main__":
    print("  collecting NS/ND entries from tick-built M1 bars ...")
    sigs = collect_signals()
    days = len({d for d, _, _ in sigs})
    print(f"  {len(sigs)} entries across {days} days\n")

    rows = []
    # his own exit, then progressively less fragile versions of it
    for sl_mult in (1.0, 2.0, 3.0, 4.0, 6.0):
        for tp_pts, arm, give in ((0, 0, 0),        # structural / run-forever
                                  (1.2, 0, 0), (2.0, 0, 0), (3.0, 0, 0),
                                  (5.0, 0, 0), (8.0, 0, 0), (12.0, 0, 0),
                                  (0, 3.0, 1.5), (0, 5.0, 3.0), (0, 8.0, 4.0)):
            net, w, l = score(sigs, sl_mult, tp_pts, arm, give)
            label = (f"SL {sl_mult:.0f}R  " +
                     (f"TP {tp_pts:>4.1f}pt" if tp_pts else
                      (f"trail {arm:.0f}/{give:.1f}" if arm else "run to structure")))
            rows.append((net, label, w, l))

    # Zee's written exit: breakeven at 1R, hold to 1:2 or 1:3
    for sl_mult in (1.0, 1.5, 2.0, 3.0):
        for be_at, tp_R in ((1.0, 2.0), (1.0, 3.0), (0.5, 2.0), (1.5, 3.0), (99, 2.0), (99, 3.0)):
            net, w, l = score_R(sigs, sl_mult, be_at, tp_R)
            be = "no BE" if be_at > 10 else f"BE@{be_at}R"
            rows.append((net, f"SL {sl_mult:.1f}R  {be} -> {tp_R:.0f}R", w, l))

    rows.sort(reverse=True)
    print("   net$      W/L     WR     policy")
    print("  " + "-" * 56)
    for net, label, w, l in rows:
        wr = w / max(w + l, 1) * 100
        flag = "  <-- best" if (net, label, w, l) == rows[0] else ""
        print(f"  {net:+9.2f}  {w:3d}/{l:<3d}  {wr:5.1f}%  {label}{flag}")
    print(f"\n  ({LOTS} lots, {SPREAD_PT}pt spread charged per trade, "
          f"{len(sigs)} entries / {days} days)")
