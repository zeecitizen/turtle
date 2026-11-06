"""nsnd_walk_forward.py — OOS-validate NSND changes before deploy:
  1. M15-only FVG (vs current M15+H1)
  2. asymmetric TP: smaller TP for sells (gold bullish bias, sells reverse fast)
Train 6d / test 6d.
"""
import sys, glob
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_s1_uhv_breakout import replay_ticks_both
from nsnd_fvg_tf_test import nsnd_signals

CONTRACT = 100.0


def run(cache, days, specs, **kw):
    trades = []
    for day in days:
        if day not in cache: continue
        sigs = nsnd_signals(cache[day]["m1"], specs, **kw)
        if sigs:
            trades.extend(replay_ticks_both(cache[day]["ticks"], sigs, 0.10, CONTRACT))
    return trades


def line(label, trades):
    r = stats(trades)
    if not r: print(f"    {label:<42} no trades"); return None
    ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
    pos = "OK " if r["total"] > 0 else "BAD"
    print(f"    {label:<42} n={r['n']:>3} WR={r['pwin']*100:>4.1f}% "
          f"TOT=${r['total']:>+8.1f} EV=${ev:+6.2f} {pos}")
    return r


def main():
    bars = load_m1_merged()
    days_bars = group_bars_by_day(bars)
    tf = {"M15": aggregate_to_tf(bars,15), "H1": aggregate_to_tf(bars,60)}
    cache = {}
    for tfp in sorted(glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))):
        day = Path(tfp).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 30: continue
        ticks = load_ticks(tfp)
        if len(ticks) < 100: continue
        cache[day] = {"m1": db, "ticks": ticks}
    ds = sorted(cache.keys()); mid = len(ds)//2
    train, test = ds[:mid], ds[mid:]
    print(f"{len(cache)} days. TRAIN {train[0]}..{train[-1]} | TEST {test[0]}..{test[-1]}\n")

    m15h1 = [(tf["M15"],15),(tf["H1"],60)]
    m15   = [(tf["M15"],15)]
    configs = [
        ("baseline M15+H1, TP=$12 both", m15h1, dict(tp_usd=12.0)),
        ("M15-only, TP=$12 both",        m15,   dict(tp_usd=12.0)),
        ("M15-only, sell TP=$6",         m15,   dict(tp_usd=12.0, sell_tp_usd=6.0)),
        ("M15-only, sell TP=$8",         m15,   dict(tp_usd=12.0, sell_tp_usd=8.0)),
    ]
    print("="*66); print("  TRAIN (6d)"); print("="*66)
    for lbl, specs, kw in configs: line(lbl, run(cache, train, specs, **kw))
    print("\n"+"="*66); print("  TEST (6d, OOS)"); print("="*66)
    te = {lbl: line(lbl, run(cache, test, specs, **kw)) for lbl, specs, kw in configs}

    print("\n"+"="*66); print("  VERDICT"); print("="*66)
    base = te["baseline M15+H1, TP=$12 both"]
    bt = base["total"] if base else 0
    for lbl, _, _ in configs:
        r = te[lbl]
        if not r: continue
        ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
        d = r["total"]-bt
        v = "HOLDS" if (r["total"]>0 and ev>0) else "weak"
        print(f"  {lbl:<42} OOS=${r['total']:>+7.1f} (Δ ${d:>+6.1f}) EV=${ev:+.2f} {v}")


if __name__ == "__main__":
    main()
