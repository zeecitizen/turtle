"""nsnd_walkforward.py — is the +$2,160 real, or did I just find the shape of 37 days of noise?

The overnight sweep threw up one loud number: relaxing the dead-volume threshold from 0.50 to
0.60 took NS/ND from 8 trades / +$132 to **30 trades / +$2,161**. Three other single-variable
relaxations were positive too (drop the FVG gate, widen the sweep window, tighten the proximity).

That is exactly the moment this project has got wrong before. [[v299-92pct-backtest-caveats]]:
*"210 combinations ... at a 5% significance level, ~10 will appear significant by pure chance on
noise data."* Picking the best value from each sweep and stacking them is the textbook way to
manufacture a beautiful curve that dies the day it goes live — and Zee has already paid for that
lesson nine times over.

So before anyone touches a live account with this, two tests it can fail:

  1. **Combination.** Do the winners survive being used together, or were they each winning on
     the same handful of trades?
  2. **Walk-forward.** Fit on the OLDEST 60% of days, measure on the NEWEST 40% the fitting never
     saw. A parameter that only works in-sample is a parameter that does not work.

If the out-of-sample half is negative, the honest morning message is "this fails too" — and that
is a perfectly good outcome to hand him, because it costs nothing compared to finding out live.
"""
from __future__ import annotations
import sys, pickle, itertools
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import nsnd_detector as NS                         # noqa: E402
from nsnd_overnight_study import load_days, run, DEFAULTS, LOTS   # noqa: E402

OUT = HERE / "_nsnd_walkforward.md"


def split(days, frac=0.60):
    keys = sorted(days)
    cut = int(len(keys) * frac)
    return ({k: days[k] for k in keys[:cut]}, {k: days[k] for k in keys[cut:]})


def line(days, label, **cfg):
    n, w, net, nd = run(days, **cfg)
    wr = (w / n * 100) if n else 0
    per = net / nd if nd else 0
    return (f"| {label} | {n} | {nd} | {wr:.0f}% | {net:+.2f} | {per:+.2f} |", n, net)


if __name__ == "__main__":
    days = load_days()
    train, test = split(days)
    print(f"  {len(days)} days -> train {len(train)}  test {len(test)}")

    # the single-variable winners from the overnight sweep
    CANDIDATES = {
        "baseline (his lessons, literally)":       dict(DEFAULTS),
        "dead-vol 0.60":                            dict(DEFAULTS, vol_frac=0.60),
        "dead-vol 0.75":                            dict(DEFAULTS, vol_frac=0.75),
        "no FVG gate":                              dict(DEFAULTS, fvg=False),
        "sweep window 20":                          dict(DEFAULTS, sweep_win=20),
        "dead-vol 0.60 + window 20":                dict(DEFAULTS, vol_frac=0.60, sweep_win=20),
        "dead-vol 0.60 + no FVG":                   dict(DEFAULTS, vol_frac=0.60, fvg=False),
        "dead-vol 0.60 + window 20 + no FVG":       dict(DEFAULTS, vol_frac=0.60, sweep_win=20,
                                                         fvg=False),
        "everything relaxed (0.75 + 20 + no FVG)":  dict(DEFAULTS, vol_frac=0.75, sweep_win=20,
                                                         fvg=False),
    }

    md = ["# NS/ND walk-forward — 2026-08-04", "",
          f"The overnight sweep found relaxations worth up to +$2,161. This asks whether any of "
          f"them survive being (a) combined and (b) measured on days the choice never saw.", "",
          f"**Train** = oldest {len(train)} tick-days.  **Test** = newest {len(test)}, held out.",
          "", f"Exit fixed at SL 3R / TP 4R, {LOTS} lots, spread charged. ", ""]

    for name, cfg in CANDIDATES.items():
        md += [f"## {name}", "",
               "| set | trades | days | WR | net $ | $/day |", "|---|---|---|---|---|---|"]
        l_all, n_all, net_all = line(days, "all 37 days", **cfg)
        l_tr, n_tr, net_tr = line(train, "train", **cfg)
        l_te, n_te, net_te = line(test, "**TEST (unseen)**", **cfg)
        md += [l_all, l_tr, l_te, ""]
        verdict = ("PASSES out-of-sample" if net_te > 0 and n_te >= 3 else
                   "fails out-of-sample" if n_te >= 3 else
                   f"inconclusive — only {n_te} test trades")
        md += [f"→ **{verdict}**", ""]
        print(f"  {name:42s} all {n_all:3d}/{net_all:+9.2f}   test {n_te:3d}/{net_te:+9.2f}  {verdict}")

    md += ["", "## How to read this", "",
           "A row that is large on the full sample but negative or empty on TEST is a row that "
           "found the shape of the past, not an edge. Only a configuration that is positive on "
           "the held-out days with enough trades to mean anything is worth putting in front of "
           "a live account — and even then, live receipts outrank every number here."]
    OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"\n  written -> {OUT}")
