"""tf_m1_vs_m5.py — does S1 trade more AND stay profitable on M1 vs M5?
Today the M5 engines took ~0 trades through London+NY. Test the SAME S1 detector
+ live params on NATIVE bars (latest_for_claude.csv) at M5 vs M1, tick-replayed,
walk-forward. Validate profitability, not just more trades.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_s1_uhv_breakout import s1_mirror, find_h1_fvgs, replay_ticks_both, load_ticks, COMMON

def load_native(fn="latest_for_claude.csv"):
    bars = []
    for r in csv.DictReader(open(COMMON / fn)):
        try:
            bars.append({"time": datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S"),
                         "open": float(r["open"]), "high": float(r["high"]),
                         "low": float(r["low"]), "close": float(r["close"]),
                         "vol": int(r["tick_volume"])})
        except Exception: pass
    bars.sort(key=lambda b: b["time"]); return bars

KW = dict(sl_buf=2.0, tp_points=7.5, do_buy=True, do_sell=True, require_fvg=False, require_sweep=True)

def run(bars_all, h1_bull, h1_bear, tickdays, tf_min, label):
    days = group_bars_by_day(bars_all)
    perday = {}; allt = []; nsig = 0
    for day in sorted(days):
        if day not in tickdays: continue
        db = days[day]
        bars = aggregate_to_tf(db, tf_min) if tf_min > 1 else db
        if len(bars) < 35: continue
        sigs = s1_mirror(bars, h1_bull, h1_bear, **KW)
        for s in sigs:   # detector hardcodes bo.time+5min; re-point to this TF's next-bar open
            s["fire_time"] = s["fire_time"] - timedelta(minutes=5) + timedelta(minutes=tf_min)
        if not sigs: continue
        nsig += len(sigs)
        t = replay_ticks_both(load_ticks(tickdays[day]), sigs, 0.01, 100.0)
        allt += t; perday[day] = sum(x["pnl"] for x in t)
    r = stats(allt)
    dtr = sorted(perday); cut = dtr[len(dtr)//2] if len(dtr) >= 4 else None
    tr = sum(v for d, v in perday.items() if cut and d < cut)
    oos = sum(v for d, v in perday.items() if cut and d >= cut)
    if not r: print(f"  {label:<12} sigs={nsig}  no trades"); return
    print(f"  {label:<12} sigs={nsig:>3}  n={r['n']:>3}  WR={r['pwin']*100:>4.0f}%  "
          f"avgW=${r['w_avg']:>4.1f} avgL=${r['l_avg']:>4.1f}  TOT=${r['total']:>+7.1f}  "
          f"(TRAIN ${tr:+.0f} / OOS ${oos:+.0f})  {'OK' if r['total']>0 else 'BAD'}", flush=True)

bars = load_native()
h1 = aggregate_to_tf(bars, 60); fv = find_h1_fvgs(h1)
hb = [f for f in fv if f["side"] == "bullish"]; he = [f for f in fv if f["side"] == "bearish"]
tickdays = {Path(p).stem.split("_")[-1]: p for p in glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))}
print(f"S1 — native bars, live params (FVG off, sweep on), 0.01 lots, {len(tickdays)} tick-days\n")
run(bars, hb, he, tickdays, 5, "S1 @ M5")
run(bars, hb, he, tickdays, 1, "S1 @ M1")
