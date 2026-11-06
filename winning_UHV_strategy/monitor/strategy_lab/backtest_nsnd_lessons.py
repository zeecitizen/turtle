"""backtest_nsnd_lessons.py — does Zee's No Supply / No Demand actually pay, on real ticks?

Built 2026-08-04 the same hour the detector was, because a detector that has not been tested on
P&L is a story. [[validate-profitability-not-capture]]: high capture with a negative balance is
an entry-edge problem wearing a win rate as a disguise — and the NS/ND line has burned us before
that exact way ([[nsnd-native-revival]]: the failure was a DATA bug, and the only thing that
settled it was rebuilding bars from the tick files themselves).

So: M1 bars are built FROM the tick CSVs, never paired with a separately-exported bar file
([[dont-overdoubt-validated-strategies]]). Fills are walked forward tick-honest at bar
resolution — stop first when a bar straddles both levels, so nothing here flatters itself.

What it prints is the only thing that matters: net dollars, per day, at a real lot size.
"""
from __future__ import annotations
import sys, glob, os
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from screener_canonical_uhv_m1 import Bar, build_m1     # noqa: E402
import nsnd_detector as NS                              # noqa: E402

COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
LOTS = 0.10                 # results scale linearly; 0.01 is what the $100 account trades
USD_PER_PT = 100 * LOTS     # gold: 1 point = $10 at 0.10 lots
SPREAD = 0.20               # charged once, on entry, so nothing is free


def walk(bars, sig):
    """Follow the trade forward bar by bar. Stop wins ties — never assume the good fill."""
    for k in range(sig.brk_i + 1, len(bars)):
        b = bars[k]
        if sig.side == "BUY":
            if b.l <= sig.sl:
                return sig.sl - sig.entry, "SL", k
            if b.h >= sig.tp:
                return sig.tp - sig.entry, "TP", k
        else:
            if b.h >= sig.sl:
                return sig.entry - sig.sl, "SL", k
            if b.l <= sig.tp:
                return sig.entry - sig.tp, "TP", k
    last = bars[-1].c
    return ((last - sig.entry) if sig.side == "BUY" else (sig.entry - last)), "OPEN", len(bars) - 1


def run(require_fvg=False, require_uhv=False, verbose=True):
    files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    tot = wins = losses = 0
    net = 0.0
    per_day = []

    for f in files:
        day = os.path.basename(f).replace("shano_ticks_", "").replace(".csv", "")
        try:
            bars = build_m1([Path(f)])
        except Exception:
            continue
        if len(bars) < 60:
            continue

        d_net = 0.0
        d_n = 0
        taken_until = -1
        for i in range(5, len(bars)):
            if i <= taken_until:                    # one trade at a time, like a human
                continue
            s = NS.detect_any(bars, require_fvg, i)
            if not s:
                continue
            if require_uhv and not s.big_opposite_volume:
                continue
            pts, how, exit_i = walk(bars, s)
            usd = pts * USD_PER_PT - SPREAD * USD_PER_PT
            net += usd
            d_net += usd
            tot += 1
            d_n += 1
            wins += usd > 0
            losses += usd <= 0
            taken_until = exit_i

        if d_n:
            per_day.append((day, d_n, d_net))

    if verbose:
        gate = ("FVG " if require_fvg else "") + ("UHV " if require_uhv else "") or "no extra gates"
        print(f"\n  === NS/ND — {gate} — {LOTS} lots ===")
        for day, n, d in per_day:
            print(f"    {day}   {n:3d} trades   ${d:+9.2f}")
        wr = (wins / tot * 100) if tot else 0
        print(f"\n    {tot} trades over {len(per_day)} days   {wins}W/{losses}L  {wr:.1f}% WR")
        print(f"    NET  ${net:+.2f}   ({net/max(len(per_day),1):+.2f}/day)")
    return tot, wins, net, len(per_day)


if __name__ == "__main__":
    print("  building M1 bars from tick files (never from a separate bar export)")
    for fvg, uhv in ((False, False), (False, True), (True, False), (True, True)):
        run(require_fvg=fvg, require_uhv=uhv)
