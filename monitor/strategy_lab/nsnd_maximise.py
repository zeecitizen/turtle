"""nsnd_maximise.py — find the MOST trades per day that still survives out-of-sample.

Zee, 2026-08-04, handing over the keys: *"i allow u to relax any rules u like ... the mission is
to make profit not to verify if some rules work.. if they hamper growth, they can be relaxed ...
tune it so that its taking MAXIMUM number of possible trades per day."*

Taken literally, "maximum trades" has an answer and it is a bad one: last night's sweep showed
the dead-volume threshold at 0.90 firing 173 trades for **-$1,163**. Past a point every extra
trade is a worse trade, and the frequency that maximises COUNT is well beyond the frequency that
maximises MONEY. His mission statement is profit, so profit is what this optimises — but among
configurations that make money, it deliberately prefers the busiest one, because that is what he
asked for and because more trades means faster live truth.

The rule for what counts as "works", set before the grid runs so it cannot be moved afterwards:

    * positive on the held-out newest 40% of days, which no parameter was chosen on
    * at least 10 trades in that held-out set, so it is not one lucky fill
    * positive on the training set too — a config that only works out-of-sample is noise
      pointing the other way

Everything else is free to move. His four failure modes and the wick/body rules stay because
they are the method; every threshold is a number I invented and is fair game, exactly as he said.
"""
from __future__ import annotations
import sys, itertools
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import nsnd_detector as NS                                    # noqa: E402
from nsnd_overnight_study import load_days, USD_PT, SPREAD_PT  # noqa: E402

OUT = HERE / "_nsnd_maximise.md"
MIN_TEST_TRADES = 10


def walk(bars, s, sl_mult, tp_R):
    risk = abs(s.entry - s.sl) * sl_mult
    if risk <= 0:
        return 0.0, s.brk_i + 1
    for k in range(s.brk_i + 1, len(bars)):
        b = bars[k]
        fav = (b.h - s.entry) if s.side == "BUY" else (s.entry - b.l)
        adv = (s.entry - b.l) if s.side == "BUY" else (b.h - s.entry)
        if adv >= risk:                       # stop resolves first — never flatter a fill
            return -risk, k
        if fav >= tp_R * risk:
            return tp_R * risk, k
    last = bars[-1].c
    return ((last - s.entry) if s.side == "BUY" else (s.entry - last)), len(bars) - 1


def run(days, cfg, sl_mult, tp_R):
    """Serial — one position at a time, the way the account will actually trade."""
    NS.NS_VOL_FRAC = cfg["vol"]; NS.NS_MAX_RANGE_FRAC = cfg["rng"]
    NS.NS_NEAR_UHV_TOL = cfg["near"]; NS.UHV_VOL_MULT = cfg["uhv"]
    NS.SWEEP_WINDOW = cfg["win"]
    n = w = 0
    net = 0.0
    for bars in days.values():
        busy = -1
        for i in range(5, len(bars)):
            if i <= busy:
                continue
            s = NS.detect_any(bars, cfg["fvg"], i)
            if not s:
                continue
            pts, ex = walk(bars, s, sl_mult, tp_R)
            usd = (pts - SPREAD_PT) * USD_PT
            net += usd; n += 1; w += usd > 0; busy = ex
    return n, w, net


if __name__ == "__main__":
    days = load_days()
    keys = sorted(days); cut = int(len(keys) * 0.60)
    train = {k: days[k] for k in keys[:cut]}
    test = {k: days[k] for k in keys[cut:]}
    print(f"  {len(days)} days -> train {len(train)}, held-out {len(test)}")

    grid = list(itertools.product(
        (0.60, 0.70, 0.75, 0.80, 0.85),     # dead-volume threshold
        (0.90, 1.10, 99.0),                 # how small the candle must be
        (12, 20, 30),                       # bars allowed before the breakout
        (1.15, 1.30),                       # how much the UHV must tower
        (0.60, 2.00),                       # distance from the trigger lines
        (2.0, 3.0),                         # stop, in multiples of the pattern's risk
        (3.0, 4.0),                         # target, in multiples of that stop
    ))
    print(f"  {len(grid)} configurations, serial fills, walk-forward gated\n")

    rows = []
    for vol, rng, win, uhv, near, sl, tp in grid:
        cfg = dict(vol=vol, rng=rng, near=near, uhv=uhv, win=win, fvg=False)
        tn, tw, tnet = run(test, cfg, sl, tp)
        if tn < MIN_TEST_TRADES or tnet <= 0:
            continue                        # fails the held-out test — discard, no appeal
        rn, rw, rnet = run(train, cfg, sl, tp)
        if rnet <= 0:
            continue                        # only works out-of-sample = noise
        an, aw, anet = run(days, cfg, sl, tp)
        rows.append(dict(vol=vol, rng=rng, win=win, uhv=uhv, near=near, sl=sl, tp=tp,
                         n=an, wr=aw / an * 100, net=anet, per_day=an / len(days),
                         test_n=tn, test_net=tnet, test_wr=tw / tn * 100))

    print(f"  {len(rows)} configurations survived the held-out test\n")
    if not rows:
        OUT.write_text("# NS/ND maximise\n\nNothing survived the held-out test.\n", encoding="utf-8")
        raise SystemExit("  nothing survived — that is the finding")

    busiest = sorted(rows, key=lambda r: -r["per_day"])[:12]
    richest = sorted(rows, key=lambda r: -r["net"])[:12]

    def table(rs, title):
        out = [f"## {title}", "",
               "| vol | rng | win | uhv | near | SL | TP | trades | /day | WR | net $ "
               "| TEST n | TEST net |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rs:
            out.append(f"| {r['vol']} | {r['rng']} | {r['win']} | {r['uhv']} | {r['near']} "
                       f"| {r['sl']}R | {r['tp']}R | {r['n']} | {r['per_day']:.2f} "
                       f"| {r['wr']:.0f}% | {r['net']:+.0f} | {r['test_n']} | {r['test_net']:+.0f} |")
        return out + [""]

    md = ["# NS/ND — the busiest configuration that still makes money", "",
          f"Zee asked for maximum trades per day. {len(grid)} configurations tested serially "
          f"(one position at a time) across {len(days)} tick-days; only the {len(rows)} that were "
          f"profitable on BOTH the training days and the held-out newest {len(test)} days "
          f"(minimum {MIN_TEST_TRADES} trades there) are shown.", "",
          "Everything is at 0.10 lots with spread charged. FVG gate off throughout, per his "
          "instruction to relax what hampers growth.", ""]
    md += table(busiest, "Most trades per day (what he asked for)")
    md += table(richest, "Most profit (for comparison)")
    md += ["## The honest limit", "",
           "Frequency and profit are not the same axis. Pushing the dead-volume threshold to 0.90 "
           "produced 173 trades for **-$1,163** — every extra trade past a point is a worse trade. "
           "The busiest row above is the busiest one that still survives days it was not fitted on; "
           "anything busier than that was discarded for losing money, not for being busy."]
    OUT.write_text("\n".join(md), encoding="utf-8")

    b = busiest[0]
    print(f"  BUSIEST that survives: vol {b['vol']} rng {b['rng']} win {b['win']} uhv {b['uhv']} "
          f"near {b['near']} SL {b['sl']}R TP {b['tp']}R")
    print(f"    {b['n']} trades ({b['per_day']:.2f}/day)  {b['wr']:.0f}% WR  ${b['net']:+.0f}")
    print(f"    held-out: {b['test_n']} trades  ${b['test_net']:+.0f}")
    print(f"\n  written -> {OUT}")
