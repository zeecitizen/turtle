"""s1_video2_walk_forward.py — OOS-validate the S1 video-2 improvements
(big-spread climax + definite-low SL) before deploying. Train 6d / test 6d.
"""
import sys, glob
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_setups import find_h1_fvgs
from backtest_s1_uhv_breakout import replay_ticks_both
from s1_video2_backtest import detect_buy, detect_sell

CONTRACT = 100.0


def run(cache, days, h1_bull, h1_bear, **kw):
    trades = []
    for day in days:
        if day not in cache: continue
        m5 = cache[day]["m5"]; fired = set(); sigs = []
        for idx in range(30, len(m5)):
            for det, fv in [(detect_buy, h1_bull), (detect_sell, h1_bear)]:
                s = det(m5, idx, fv, **kw)
                if s and s["ref"] not in fired:
                    sigs.append(s); fired.add(s["ref"])
        if sigs:
            trades.extend(replay_ticks_both(cache[day]["ticks"], sigs, 0.10, CONTRACT))
    return trades


def line(label, trades):
    r = stats(trades)
    if not r: print(f"    {label:<40} no trades"); return None
    ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
    pos = "OK " if r["total"] > 0 else "BAD"
    print(f"    {label:<40} n={r['n']:>3} WR={r['pwin']*100:>4.1f}% "
          f"TOT=${r['total']:>+8.1f} EV=${ev:+6.2f} {pos}")
    return r


def main():
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
    ds = sorted(cache.keys()); mid = len(ds)//2
    train, test = ds[:mid], ds[mid:]
    print(f"{len(cache)} days. TRAIN {train[0]}..{train[-1]} | TEST {test[0]}..{test[-1]}\n")

    configs = [
        ("baseline (UHV SL, no spread)", dict(sl_mode="uhv", sl_buf=2.0, big_spread=False)),
        ("definite-low SL", dict(sl_mode="definite", sl_buf=2.0, big_spread=False)),
        ("big-spread 1.3x", dict(sl_mode="uhv", sl_buf=2.0, big_spread=True, spread_mult=1.3)),
        ("full teacher (def-low + big-spread)", dict(sl_mode="definite", sl_buf=2.0, big_spread=True, spread_mult=1.3)),
    ]
    print("="*64); print("  TRAIN (6d)"); print("="*64)
    tr = {lbl: line(lbl, run(cache, train, h1_bull, h1_bear, **kw)) for lbl, kw in configs}
    print("\n"+"="*64); print("  TEST (6d, OUT-OF-SAMPLE)"); print("="*64)
    te = {lbl: line(lbl, run(cache, test, h1_bull, h1_bear, **kw)) for lbl, kw in configs}

    print("\n"+"="*64); print("  VERDICT (OOS test totals vs baseline)"); print("="*64)
    base = te["baseline (UHV SL, no spread)"]
    base_tot = base["total"] if base else 0
    for lbl, _ in configs:
        r = te[lbl]
        if not r: print(f"  {lbl}: no test trades"); continue
        ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
        delta = r["total"] - base_tot
        verdict = "HOLDS" if (r["total"]>0 and ev>0) else "weak"
        print(f"  {lbl:<40} OOS=${r['total']:>+7.1f} (Δ vs base ${delta:>+6.1f}) EV=${ev:+.2f} {verdict}")


if __name__ == "__main__":
    main()
