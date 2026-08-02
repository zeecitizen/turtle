"""s3_h1trend_test.py — test the night's #1 lead: gate S3 buys on H1 trend.
Live ledger showed the M5 24-bar trend flagged 'uptrend' for losing buys in a
downtrend. Hypothesis: requiring H1 trend UP at signal time blocks counter-trend
losers. Backtest on 12d real ticks; current-best S3 config (M5 FVG, SL=$2).
"""
import sys, glob
from datetime import timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats, find_h1_fvgs
from ea_mirror_validate import s3_ea_mirror
from backtest_s1_uhv_breakout import replay_ticks_both

CONTRACT = 100.0


def h1_trend_up(h1, t, lookback):
    """Last completed H1 bar before t: close > close[lookback bars earlier]?"""
    prior = [b for b in h1 if b["time"] + timedelta(minutes=60) <= t]
    if len(prior) <= lookback: return None
    return prior[-1]["close"] - prior[-1-lookback]["close"]


def rpt(label, trades):
    r = stats(trades)
    if not r: print(f"  {label:<34} no trades"); return None
    ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
    pos = "OK " if r["total"] > 0 else "BAD"
    print(f"  {label:<34} n={r['n']:>3} WR={r['pwin']*100:>4.1f}% "
          f"TOT=${r['total']:>+8.1f} EV=${ev:+6.2f} {pos}")
    return r


def main():
    print("Loading 12d...")
    bars = load_m1_merged()
    days_bars = group_bars_by_day(bars)
    h1 = aggregate_to_tf(bars, 60)
    m5_fvgs = find_h1_fvgs(aggregate_to_tf(bars, 5))  # current S3 = M5 FVG
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

    def run(h1_lb=None):
        trades = []
        for day, c in cache.items():
            sigs = s3_ea_mirror(c["m5"], sl_buf=2.0, h1_fvgs=m5_fvgs, require_fvg=True)
            for s in sigs: s["side"] = +1
            if h1_lb is not None:
                sigs = [s for s in sigs
                        if (lambda d: d is not None and d > 0)(h1_trend_up(h1, s["fire_time"], h1_lb))]
            if sigs:
                trades.extend(replay_ticks_both(c["ticks"], sigs, 0.10, CONTRACT))
        return trades

    print("="*78)
    print("  S3 (M5-FVG, SL=$2) — H1 trend-up gate sweep")
    print("="*78)
    rpt("baseline (no H1 gate)", run(None))
    for lb in [1, 2, 3, 6]:
        rpt(f"require H1 close>close[-{lb}] (up)", run(lb))


if __name__ == "__main__":
    main()
