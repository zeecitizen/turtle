"""absorption_test.py — backtest the teacher's ABSORPTION CANDLE setup
(video ddvZYdA2ETo). Distinct from our reversal setups: it's a CONTINUATION
breakout of a prior resistance with a low-volume momentum candle.

Rules (BUY, uptrend):
  - resistance = highest high of the prior N M5 bars (the peak price topped at)
  - res_vol = highest volume among those resistance bars
  - breakout bar (bo): close > resistance AND open <= resistance (fresh break)
  - momentum: upper wick <= wick_frac of range (no big rejection)
  - low-volume: bo.vol < res_vol (supply absorbed)
  - entry bo.close; SL = min low of last sl_lookback bars - buf; TP = R x risk
SELL mirror for downtrend. Backtest on 12d real ticks.
"""
import sys, glob
from datetime import timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_s1_uhv_breakout import is_uptrend, is_downtrend, replay_ticks_both

CONTRACT = 100.0


def detect(m5, idx, side, res_lb=12, sl_lb=6, wick_frac=0.25, rr=2.0, sl_buf=2.0):
    bo = m5[idx]
    zone = range(max(0, idx-res_lb), idx)   # prior bars (exclude bo)
    if len(zone) < 3: return None
    rng = bo["high"]-bo["low"]
    if rng <= 0: return None
    body = abs(bo["close"]-bo["open"])
    if body <= 0: return None
    res_vol = max(m5[j]["vol"] for j in zone)
    if side > 0:
        if not is_uptrend(m5, idx): return None
        resistance = max(m5[j]["high"] for j in zone)
        if not (bo["close"] > resistance and bo["open"] <= resistance): return None
        if bo["close"] <= bo["open"]: return None
        upper_wick = bo["high"]-max(bo["open"],bo["close"])
        if upper_wick/rng > wick_frac: return None
        if bo["vol"] >= res_vol: return None
        sl = min(m5[j]["low"] for j in range(max(0,idx-sl_lb), idx+1)) - sl_buf
        risk = bo["close"]-sl
        if risk <= 0: return None
        tp = bo["close"] + rr*risk
    else:
        if not is_downtrend(m5, idx): return None
        support = min(m5[j]["low"] for j in zone)
        if not (bo["close"] < support and bo["open"] >= support): return None
        if bo["close"] >= bo["open"]: return None
        lower_wick = min(bo["open"],bo["close"])-bo["low"]
        if lower_wick/rng > wick_frac: return None
        if bo["vol"] >= res_vol: return None
        sl = max(m5[j]["high"] for j in range(max(0,idx-sl_lb), idx+1)) + sl_buf
        risk = sl-bo["close"]
        if risk <= 0: return None
        tp = bo["close"] - rr*risk
    return {"fire_time": bo["time"]+timedelta(minutes=5), "side": side, "sl": sl, "tp": tp}


def rpt(label, trades):
    r = stats(trades)
    if not r: print(f"  {label:<40} no trades"); return None
    ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
    pos = "OK " if r["total"] > 0 else "BAD"
    print(f"  {label:<40} n={r['n']:>3} WR={r['pwin']*100:>4.1f}% "
          f"TOT=${r['total']:>+8.1f} EV=${ev:+6.2f} {pos}")
    return r


def main():
    print("Loading 12d...")
    bars = load_m1_merged()
    days_bars = group_bars_by_day(bars)
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

    def run(side_set, rr=2.0, res_lb=12, wick=0.25):
        trades = []
        for day, c in cache.items():
            m5 = c["m5"]; sigs = []; last = None
            for idx in range(30, len(m5)):
                if m5[idx]["time"] == last: continue
                for s in side_set:
                    sig = detect(m5, idx, s, res_lb=res_lb, wick_frac=wick, rr=rr)
                    if sig: sigs.append(sig); last = m5[idx]["time"]; break
            if sigs: trades.extend(replay_ticks_both(c["ticks"], sigs, 0.10, CONTRACT))
        return trades

    print("="*80)
    print("  ABSORPTION breakout (continuation) — 12d real ticks")
    print("="*80)
    rpt("BUY only, RR=2, res_lb=12", run([+1], rr=2.0))
    rpt("BUY only, RR=1", run([+1], rr=1.0))
    rpt("BUY+SELL, RR=2", run([+1,-1], rr=2.0))
    rpt("BUY only, RR=2, res_lb=20", run([+1], rr=2.0, res_lb=20))
    rpt("BUY only, RR=2, tight wick 0.15", run([+1], rr=2.0, wick=0.15))


if __name__ == "__main__":
    main()


def walk_forward():
    """Train/test split on the tight-wick config."""
    bars = load_m1_merged()
    days_bars = group_bars_by_day(bars)
    cache = {}
    for tf in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[day] = {"m5": aggregate_to_tf(db, 5), "ticks": ticks}
    ds = sorted(cache.keys()); mid = len(ds)//2
    def run_days(days, wick):
        trades = []
        for day in days:
            m5 = cache[day]["m5"]; sigs=[]; last=None
            for idx in range(30, len(m5)):
                if m5[idx]["time"]==last: continue
                sig = detect(m5, idx, +1, res_lb=12, wick_frac=wick, rr=2.0)
                if sig: sigs.append(sig); last=m5[idx]["time"]
            if sigs: trades.extend(replay_ticks_both(cache[day]["ticks"], sigs, 0.10, CONTRACT))
        return trades
    print("\n  WALK-FORWARD tight-wick(0.15) BUY RR=2:")
    rpt("  TRAIN (6d)", run_days(ds[:mid], 0.15))
    rpt("  TEST  (6d OOS)", run_days(ds[mid:], 0.15))


if __name__ == "__main__":
    walk_forward()
