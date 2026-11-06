"""backtest_s1_diagnose.py — WHY does S1 fire 0 live trades?

Replicates S1Trader.mq5's EXACT live BUY cascade on the 13 real-tick days' M5 bars
and counts how many setups survive EACH filter stage. The stage where the count
collapses to ~0 is the culprit. (The harness that "validated" S1 never modeled the
big-spread climax filter — prime suspect.)

Live cascade (S1Trader.mq5 TryS1BuySignal):
  1 green bo            5 breakout: bo.c>uhv.h AND bo.o<=uhv.h
  2 uptrend (>2.0/24)   6 sweep: a bar after uhv dipped < uhv.low
  3 retracement reds    7 H1 FVG tapped in retracement
  4 UHV = top-vol red
  4b BIG-SPREAD: uhv.range >= 1.3 x avg range of prior 10 bars  <-- suspect

Run:  py backtest_s1_diagnose.py
"""
import sys, glob
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")
from backtest_v349_multiday import load_m1_merged, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day
from backtest_setups import find_h1_fvgs
from backtest_s1_uhv_breakout import h1_bull_tapped_in

TREND_LB, TREND_TH = 24, 2.0
RETRACE_LB = 15
SPREAD_MULT, SPREAD_AVG = 1.3, 10
H1_FVG_LB = 50


def h1_bull_tapped(h1_bull, m5, idxs):
    """Use the PROVEN tap check from the validated S1 harness (time-aware,
    gap_low/gap_high keys)."""
    return h1_bull_tapped_in(h1_bull, m5, list(idxs))


def diagnose(m5, h1_bull, c):
    """Walk M5 bars as the live EA does; tally survivors per stage into counter c."""
    start = max(TREND_LB, RETRACE_LB + SPREAD_AVG) + 2
    for i in range(start, len(m5)):
        bo = m5[i]
        c["bars"] += 1
        if bo["close"] <= bo["open"]:           continue
        c["1_green"] += 1
        if bo["close"] - m5[i - TREND_LB]["close"] <= TREND_TH:  continue
        c["2_uptrend"] += 1
        reds = [j for j in range(i - RETRACE_LB, i) if j >= SPREAD_AVG and m5[j]["close"] < m5[j]["open"]]
        if not reds:                            continue
        c["3_reds"] += 1
        uhv = max(reds, key=lambda j: m5[j]["vol"])
        c["4_uhv"] += 1
        # 4b big-spread climax
        rng = m5[uhv]["high"] - m5[uhv]["low"]
        avg = sum(m5[j]["high"] - m5[j]["low"] for j in range(uhv - SPREAD_AVG, uhv)) / SPREAD_AVG
        if not (avg > 0 and rng >= SPREAD_MULT * avg):  continue
        c["4b_bigspread"] += 1
        uhv_h, uhv_l = m5[uhv]["high"], m5[uhv]["low"]
        # 5 breakout
        if not (bo["close"] > uhv_h and bo["open"] <= uhv_h):  continue
        c["5_breakout"] += 1
        # 6 sweep
        if not any(m5[k]["low"] < uhv_l for k in range(uhv + 1, i + 1)):  continue
        c["6_sweep"] += 1
        # 7 H1 FVG tapped in retracement window [oldest red .. i]
        if not h1_bull_tapped(h1_bull, m5, list(range(min(reds), i + 1))):  continue
        c["7_h1fvg"] += 1
        c["SIGNAL"] += 1


def main():
    bars = load_m1_merged()
    days = group_bars_by_day(bars)
    h1 = aggregate_to_tf(bars, 60)
    fvgs = find_h1_fvgs(h1)
    h1_bull = [f for f in fvgs if f.get("side") == "bullish"]
    tick_days = sorted(Path(p).stem.split("_")[-1] for p in glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    c = dict.fromkeys(["bars", "1_green", "2_uptrend", "3_reds", "4_uhv",
                       "4b_bigspread", "5_breakout", "6_sweep", "7_h1fvg", "SIGNAL"], 0)
    nd = 0
    for d in tick_days:
        if d not in days or len(days[d]) < 60:
            continue
        diagnose(aggregate_to_tf(days[d], 5), h1_bull, c)
        nd += 1
    print(f"S1 live-cascade diagnosis over {nd} days, {len(h1_bull)} bullish H1 FVGs\n")
    order = ["bars", "1_green", "2_uptrend", "3_reds", "4_uhv", "4b_bigspread",
             "5_breakout", "6_sweep", "7_h1fvg", "SIGNAL"]
    prev = None
    for k in order:
        v = c[k]
        drop = "" if prev is None or prev == 0 else f"  (kept {100*v/prev:4.0f}% of prev)"
        print(f"  {k:<14} {v:>6}{drop}")
        prev = v
    print(f"\n  => {c['SIGNAL']} signals / {nd} days = {c['SIGNAL']/max(nd,1):.2f} per day "
          f"(BUY side only; SELL mirrors)")
    # also show big-spread OFF, to isolate its effect
    c2 = dict.fromkeys(c, 0)
    global SPREAD_MULT
    keep = SPREAD_MULT; SPREAD_MULT = 0.0
    for d in tick_days:
        if d in days and len(days[d]) >= 60:
            diagnose(aggregate_to_tf(days[d], 5), h1_bull, c2)
    SPREAD_MULT = keep
    print(f"  with big-spread filter OFF: {c2['SIGNAL']} signals "
          f"({c2['SIGNAL']/max(nd,1):.2f}/day) — the filter's true cost")


if __name__ == "__main__":
    main()
