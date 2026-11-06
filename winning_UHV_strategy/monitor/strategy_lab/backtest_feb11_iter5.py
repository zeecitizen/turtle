"""backtest_feb11_iter5.py — capture Zee's Feb-11 style: HIGH-FREQUENCY on the broker feed.

Prior iters 1-4 (2026-05-12) mechanized the FVG->sweep->momentum pattern and LOST money
(-$4054), blocked by (a) tick-level entries and (b) an OANDA feed that didn't match
Zee's broker. Iter 5 fixes both: run on the BROKER tick feed (shano_ticks_*.csv) and at
M1 (the fast TF Zee actually traded) instead of S3's cautious M5.

Lesson-10 final pattern == S3's liquidity-sweep detector. So iter 5 = the SAME validated
S3 detector, dropped to M1 (higher frequency), replayed on real broker ticks, testing:
  - fixed TP/SL scalp exits (sweep), and
  - a SCRATCH exit (Zee's style: bail fast if not in profit -> his -$1.32 avg loss)
with a walk-forward split. The one question: is the high-frequency M1 version net
profitable on Zee's actual feed? (BUY side first, like detect_s3; SELL is a follow-up.)

Run:  py backtest_feb11_iter5.py
"""
import sys, glob
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, detect_signals
from backtest_setups import find_h1_fvgs

CONTRACT = 100.0
LOTS = 0.10
# M1-scaled detector params (vs S3's M5: 24 bars=2h -> 120 M1 bars; peak 10->30)
TREND_LB, TREND_TH = 120, 2.0
PEAK_LB = 30
SL_BUF = 2.0
REQUIRE_FVG = True   # H1 FVG (lesson: higher-TF FVG)


def replay_fixed(ticks, sigs, tp_pts, sl_pts, scratch_secs=None):
    """BUY-only. Enter at next tick's ask after fire_time. Fixed TP/SL in price-pts.
    scratch_secs: if set, bail at market once this many seconds pass without being
    in profit (Zee's 'scratch at first sign of trouble')."""
    ppp = LOTS * CONTRACT
    done = []
    it = iter(sorted(sigs, key=lambda x: x["fire_time"]))
    pend = next(it, None)
    units = []
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            if bid <= u["e"] - sl_pts:
                u["pnl"] = -sl_pts * ppp; done.append(u); units.remove(u); continue
            if bid >= u["e"] + tp_pts:
                u["pnl"] = tp_pts * ppp; done.append(u); units.remove(u); continue
            if scratch_secs is not None and (t - u["open_t"]).total_seconds() >= scratch_secs and bid < u["e"]:
                u["pnl"] = (bid - u["e"]) * ppp; u["scr"] = 1; done.append(u); units.remove(u); continue
        while pend is not None and t >= pend["fire_time"]:
            if len(units) < 2:
                units.append({"e": ask, "open_t": t})
            pend = next(it, None)
    if ticks:
        last = ticks[-1]
        for u in units:
            u["pnl"] = (last["bid"] - u["e"]) * ppp; done.append(u)
    return done


def stat(trades):
    n = len(trades)
    if not n: return "n=0"
    w = [x["pnl"] for x in trades if x["pnl"] > 0]
    l = [x["pnl"] for x in trades if x["pnl"] < 0]
    tot = sum(x["pnl"] for x in trades)
    wr = len(w) / (len(w) + len(l)) if (w or l) else 0
    return (f"n={n:>4}  WR={wr:.2f}  W=${(sum(w)/len(w) if w else 0):>5.1f}  "
            f"L=${(-sum(l)/len(l) if l else 0):>5.1f}  TOTAL=${tot:>+9.1f}")


def main():
    bars = load_m1_merged()
    days_b = group_bars_by_day(bars)
    h1 = aggregate_to_tf(bars, 60)
    fvgs = find_h1_fvgs(h1)
    cache = {}
    for tf in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        d = Path(tf).stem.split("_")[-1]
        if d not in days_b or len(days_b[d]) < 200:   # need a full M1 day
            continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[d] = {"m1": days_b[d], "ticks": ticks}
    days = sorted(cache)
    mid = len(days) // 2
    print(f"FEB-11 ITER 5 — S3 liquidity-sweep pattern at M1 on BROKER ticks — "
          f"{len(days)} days, {LOTS} lots, BUY-only\n")

    # signal frequency at M1
    sig_by_day = {}
    for d in days:
        sig_by_day[d] = detect_signals(cache[d]["m1"], fvgs, SL_BUF, TREND_TH,
                                       TREND_LB, REQUIRE_FVG, PEAK_LB, 1)
    nsig = sum(len(s) for s in sig_by_day.values())
    print(f"M1 signals: {nsig} over {len(days)} days = {nsig/len(days):.1f}/day "
          f"(vs S3-on-M5 ~0.4/day, vs Zee Feb-11 ~manual 60-100/day)\n")

    print(f"{'exit':<26}{'ALL':<46}{'OOS (test half)'}")
    configs = [
        ("fixed TP$5 / SL$3", dict(tp_pts=5.0, sl_pts=3.0)),
        ("fixed TP$3 / SL$3 (1:1)", dict(tp_pts=3.0, sl_pts=3.0)),
        ("fixed TP$8 / SL$4", dict(tp_pts=8.0, sl_pts=4.0)),
        ("scratch TP$5/SL$5/30s", dict(tp_pts=5.0, sl_pts=5.0, scratch_secs=30)),
        ("scratch TP$8/SL$6/60s", dict(tp_pts=8.0, sl_pts=6.0, scratch_secs=60)),
    ]
    for lbl, kw in configs:
        allt, testt = [], []
        for k, d in enumerate(days):
            tr = replay_fixed(cache[d]["ticks"], sig_by_day[d], **kw)
            allt += tr
            if k >= mid: testt += tr
        print(f"{lbl:<26}{stat(allt):<46}{stat(testt)}")


if __name__ == "__main__":
    main()
