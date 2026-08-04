"""nsnd_overnight_study.py — the honest question about No Supply / No Demand, answered with data.

Zee, 2026-08-04, going to sleep: *"our initial testing failed ... now we're trying out a new ns
nd method.. i'm not sure if we'll make it this time even.. to be honest i've lost hope."*

He has earned that scepticism. So this run is not built to make NS/ND look good — it is built to
find out whether it can be made to work at all, and to say so plainly either way in the morning.

There is one uncomfortable number driving it. With every gate from his lessons enforced, the
pattern fired **7 times in 37 tick-days**. Even at a perfect win rate and 2.8:1, that is roughly
$110 a month at 0.10 lots. A setup that rare cannot be validated (n is too small to ever trust)
and cannot pay for anything. So the real question is not "does the strict form win" but:

    WHICH gate is doing the filtering, and is there a looser form that fires often enough to
    measure while still being his method rather than a different one wearing its name?

The suspicion is my implementation, not his teaching. Two gates are mine to blame:

  * the FVG test demands price tap a 3-candle gap on M1 — on a one-minute chart those gaps are
    small and frequent, and "tapped" is a far sharper condition than a man drawing a grey box
    with his eyes and saying "close enough".
  * the proximity tolerance (0.6 x the UHV's range) is a number I invented to encode his "above,
    below, in between". He never gave a distance.

So each gate is swept independently, with the exit held fixed, and reported as: how many trades,
what win rate, what net. Then the reverse — the best few configurations get the exit swept too.

The rules that came from his mouth in the lessons are NOT swept: dead volume under half of each
of the previous two, sweep by wick, break by body, breakout volume above the no-supply candle's,
and the four failure modes. Those are the method. Everything swept here is a number I chose,
and every one of them is a place I could have been wrong.

Output: monitor/strategy_lab/_nsnd_overnight.md — for him to read with tea, not for me to
summarise flatteringly.
"""
from __future__ import annotations
import sys, glob, os, pickle, itertools, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))

from screener_canonical_uhv_m1 import build_m1     # noqa: E402
import nsnd_detector as NS                         # noqa: E402

COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
CACHE = HERE / "_nsnd_bars.pkl"
OUT = HERE / "_nsnd_overnight.md"
LOTS = 0.10
USD_PT = 100 * LOTS
SPREAD_PT = 0.20


def load_days():
    """Build M1 bars from every tick file once, then cache — 404 MB is too slow to re-read."""
    if CACHE.exists():
        with CACHE.open("rb") as f:
            return pickle.load(f)
    days = {}
    for f in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        day = os.path.basename(f)[12:22]
        try:
            bars = build_m1([Path(f)])
        except Exception:
            continue
        if len(bars) >= 60:
            days[day] = bars
    with CACHE.open("wb") as f:
        pickle.dump(days, f)
    return days


def walk(bars, s, sl_mult=3.0, tp_R=4.0):
    """Fixed reference exit while gates are swept, so the gates are what is being measured."""
    risk = abs(s.entry - s.sl) * sl_mult
    if risk <= 0:
        return 0.0
    for k in range(s.brk_i + 1, len(bars)):
        b = bars[k]
        fav = (b.h - s.entry) if s.side == "BUY" else (s.entry - b.l)
        adv = (s.entry - b.l) if s.side == "BUY" else (b.h - s.entry)
        if adv >= risk:                       # stop first, always — never flatter the fill
            return -risk
        if fav >= tp_R * risk:
            return tp_R * risk
    last = bars[-1].c
    return (last - s.entry) if s.side == "BUY" else (s.entry - last)


def run(days, *, vol_frac, rng_frac, near_tol, uhv_mult, fvg, sweep_win,
        sl_mult=3.0, tp_R=4.0):
    """One configuration across every day. Returns (n, wins, net_usd, n_days)."""
    NS.NS_VOL_FRAC = vol_frac
    NS.NS_MAX_RANGE_FRAC = rng_frac
    NS.NS_NEAR_UHV_TOL = near_tol
    NS.UHV_VOL_MULT = uhv_mult
    NS.SWEEP_WINDOW = sweep_win
    n = w = 0
    net = 0.0
    hit_days = set()
    for day, bars in days.items():
        taken_until = -1
        for i in range(5, len(bars)):
            if i <= taken_until:
                continue
            s = NS.detect_any(bars, fvg, i)
            if not s:
                continue
            pts = walk(bars, s, sl_mult, tp_R)
            usd = (pts - SPREAD_PT) * USD_PT
            net += usd
            n += 1
            w += usd > 0
            hit_days.add(day)
            taken_until = i + 1
    return n, w, net, len(hit_days)


DEFAULTS = dict(vol_frac=0.50, rng_frac=0.70, near_tol=0.60,
                uhv_mult=1.30, fvg=True, sweep_win=8)

SWEEPS = {
    "dead-volume threshold (his 'half se bhi kam')": ("vol_frac", [0.40, 0.50, 0.60, 0.75, 0.90]),
    "how small the candle must be":                  ("rng_frac", [0.50, 0.70, 0.90, 1.10, 99.0]),
    "distance allowed from the UHV lines (MINE)":    ("near_tol", [0.30, 0.60, 1.00, 2.00, 99.0]),
    "how much the UHV must tower":                   ("uhv_mult", [1.00, 1.15, 1.30, 1.60]),
    "FVG tap required":                              ("fvg",      [True, False]),
    "bars allowed between candle and breakout":      ("sweep_win", [4, 8, 12, 20]),
}


def main():
    t0 = time.time()
    days = load_days()
    lines = ["# NS/ND overnight study — 2026-08-04",
             "",
             f"Built M1 bars from **{len(days)} tick-days**. Exit held fixed at "
             f"SL 3R / TP 4R, {LOTS} lots, {SPREAD_PT}pt spread charged per trade, so that "
             f"what moves between rows is the GATE, not the exit.",
             "",
             "Baseline = every gate as Zee's lessons state them.", ""]

    n, w, net, nd = run(days, **DEFAULTS)
    lines += [f"**Baseline: {n} trades over {nd} days · {w}W/{n-w}L · "
              f"{(w/n*100 if n else 0):.0f}% WR · net ${net:+.2f}**", ""]
    print(f"  baseline: {n} trades, {net:+.2f}")

    for title, (key, values) in SWEEPS.items():
        lines += [f"## {title}", "", "| value | trades | days | WR | net $ |", "|---|---|---|---|---|"]
        for v in values:
            cfg = dict(DEFAULTS); cfg[key] = v
            n, w, net, nd = run(days, **cfg)
            wr = (w / n * 100) if n else 0
            mark = "  ← current" if v == DEFAULTS[key] else ""
            lines.append(f"| {v}{mark} | {n} | {nd} | {wr:.0f}% | {net:+.2f} |")
            print(f"    {key}={v}: {n} trades, {net:+.2f}")
        lines.append("")

    lines += ["", f"_run took {(time.time()-t0)/60:.1f} min_"]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  written -> {OUT}")


if __name__ == "__main__":
    main()
