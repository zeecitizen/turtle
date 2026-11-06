"""s1_video2_backtest.py — test the two S1 gaps the teacher's VSA Selling-Climax
video (Scenario 3) revealed:
  1. SL at the "definite low" (lowest low of the shakeout between UHV and breakout)
     instead of UHV.low - fixed buffer.
  2. Climax bar must be a BIG-SPREAD candle (large range), not just highest volume.

Baseline = current live S1 (H1 FVG, SL=UHV.low-$2, TP=$7.5, BUY+SELL).
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_setups import find_h1_fvgs
from backtest_s1_uhv_breakout import (is_uptrend, is_downtrend,
                                       h1_bull_tapped_in, h1_bear_tapped_in,
                                       replay_ticks_both)

CONTRACT = 100.0


def avg_range(m5, idx, n=10):
    js = range(max(0, idx - n), idx)
    rs = [m5[j]["high"] - m5[j]["low"] for j in js]
    return sum(rs) / len(rs) if rs else 0


def detect_buy(m5, idx, h1_bull, tp_points=7.5, sl_buf=2.0,
               retrace_lb=15, sl_mode="uhv", big_spread=False, spread_mult=1.3,
               low_vol_break=False):
    bo = m5[idx]
    if bo["close"] <= bo["open"]: return None
    if not is_uptrend(m5, idx): return None
    start = max(0, idx - retrace_lb)
    red_idxs = [j for j in range(start, idx) if m5[j]["close"] < m5[j]["open"]]
    if not red_idxs: return None
    uhv_idx = max(red_idxs, key=lambda j: m5[j]["vol"])
    uhv = m5[uhv_idx]
    if bo["close"] <= uhv["high"]: return None
    if bo["open"]  >  uhv["high"]: return None
    # Scenario-3 sweep: some bar after UHV dipped below UHV.low
    swept = [j for j in range(uhv_idx + 1, idx + 1) if m5[j]["low"] < uhv["low"]]
    if not swept: return None
    if not h1_bull_tapped_in(h1_bull, m5, range(start, idx + 1)): return None
    # TEACHER: big-spread climax bar
    if big_spread:
        if (uhv["high"] - uhv["low"]) < spread_mult * avg_range(m5, uhv_idx):
            return None
    # TEACHER scenario-2: breakout candle volume < climax bar volume
    if low_vol_break and bo["vol"] >= uhv["vol"]:
        return None
    entry = bo["close"]
    # SL placement
    if sl_mode == "uhv":
        sl = uhv["low"] - sl_buf
    else:  # definite low = lowest low across uhv..idx (the whole shakeout)
        def_low = min(m5[j]["low"] for j in range(uhv_idx, idx + 1))
        sl = def_low - sl_buf
    tp = entry + tp_points
    return {"fire_time": bo["time"] + timedelta(minutes=5), "side": +1,
            "sl": sl, "tp": tp, "ref": uhv["time"],
            "uhv_level": uhv["high"], "bo_time": bo["time"]}


def detect_sell(m5, idx, h1_bear, tp_points=7.5, sl_buf=2.0,
                retrace_lb=15, sl_mode="uhv", big_spread=False, spread_mult=1.3,
                low_vol_break=False):
    bo = m5[idx]
    if bo["close"] >= bo["open"]: return None
    if not is_downtrend(m5, idx): return None
    start = max(0, idx - retrace_lb)
    green_idxs = [j for j in range(start, idx) if m5[j]["close"] > m5[j]["open"]]
    if not green_idxs: return None
    uhv_idx = max(green_idxs, key=lambda j: m5[j]["vol"])
    uhv = m5[uhv_idx]
    if bo["close"] >= uhv["low"]: return None
    if bo["open"]  <  uhv["low"]: return None
    swept = [j for j in range(uhv_idx + 1, idx + 1) if m5[j]["high"] > uhv["high"]]
    if not swept: return None
    if not h1_bear_tapped_in(h1_bear, m5, range(start, idx + 1)): return None
    if big_spread:
        if (uhv["high"] - uhv["low"]) < spread_mult * avg_range(m5, uhv_idx):
            return None
    if low_vol_break and bo["vol"] >= uhv["vol"]:
        return None
    entry = bo["close"]
    if sl_mode == "uhv":
        sl = uhv["high"] + sl_buf
    else:
        def_high = max(m5[j]["high"] for j in range(uhv_idx, idx + 1))
        sl = def_high + sl_buf
    tp = entry - tp_points
    return {"fire_time": bo["time"] + timedelta(minutes=5), "side": -1,
            "sl": sl, "tp": tp, "ref": uhv["time"],
            "uhv_level": uhv["low"], "bo_time": bo["time"]}


def run(cache, h1_bull, h1_bear, **kw):
    trades = []
    for day, c in cache.items():
        m5 = c["m5"]; fired = set(); sigs = []
        for idx in range(30, len(m5)):
            for det, fv in [(detect_buy, h1_bull), (detect_sell, h1_bear)]:
                s = det(m5, idx, fv, **kw)
                if s and s["ref"] not in fired:
                    sigs.append(s); fired.add(s["ref"])
        if sigs:
            trades.extend(replay_ticks_both(c["ticks"], sigs, 0.10, CONTRACT))
    return trades


def rpt(label, trades):
    r = stats(trades)
    if not r:
        print(f"  {label:<46} no trades"); return None
    ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
    pos = "OK " if r["total"] > 0 else "BAD"
    print(f"  {label:<46} n={r['n']:>3} WR={r['pwin']*100:>4.1f}% "
          f"TOT=${r['total']:>+8.1f} EV=${ev:+6.2f} {pos}")
    return r


def main():
    print("Loading 12d...")
    bars = load_m1_merged()
    days_bars = group_bars_by_day(bars)
    allf = find_h1_fvgs(aggregate_to_tf(bars, 60))
    h1_bull = [f for f in allf if f["side"] == "bullish"]
    h1_bear = [f for f in allf if f["side"] == "bearish"]
    cache = {}
    for tf in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[day] = {"m5": aggregate_to_tf(db, 5), "ticks": ticks}
    print(f"  {len(cache)} days\n")

    print("="*88)
    print("  S1 video-2 tests (H1 FVG, TP=$7.5, BUY+SELL)")
    print("="*88)
    rpt("baseline (SL=UHV.low-$2)",
        run(cache, h1_bull, h1_bear, sl_mode="uhv", sl_buf=2.0, big_spread=False))
    rpt("SL at DEFINITE LOW -$2 (teacher)",
        run(cache, h1_bull, h1_bear, sl_mode="definite", sl_buf=2.0, big_spread=False))
    rpt("SL definite low -$0.5",
        run(cache, h1_bull, h1_bear, sl_mode="definite", sl_buf=0.5, big_spread=False))
    rpt("+ BIG-SPREAD climax (1.3x avg range)",
        run(cache, h1_bull, h1_bear, sl_mode="uhv", sl_buf=2.0, big_spread=True, spread_mult=1.3))
    rpt("+ BIG-SPREAD (1.5x)",
        run(cache, h1_bull, h1_bear, sl_mode="uhv", sl_buf=2.0, big_spread=True, spread_mult=1.5))
    rpt("DEFINITE-LOW SL + BIG-SPREAD (full teacher)",
        run(cache, h1_bull, h1_bear, sl_mode="definite", sl_buf=2.0, big_spread=True, spread_mult=1.3))
    print()
    rpt("BIG-SPREAD + LOW-VOL breakout (scen-2)",
        run(cache, h1_bull, h1_bear, sl_mode="uhv", sl_buf=2.0, big_spread=True, spread_mult=1.3, low_vol_break=True))
    rpt("LOW-VOL breakout only (no big-spread)",
        run(cache, h1_bull, h1_bear, sl_mode="uhv", sl_buf=2.0, big_spread=False, low_vol_break=True))


if __name__ == "__main__":
    main()
