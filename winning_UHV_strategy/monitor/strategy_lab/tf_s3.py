"""tf_s3.py — S3 (Liquidity Sweep) M1 vs M5 on native bars, live-ish params, tick-replay."""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import (aggregate_to_tf, group_bars_by_day, stats,
                                       detect_s3_teacher)
from backtest_s1_uhv_breakout import replay_ticks_both, load_ticks, COMMON

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

def s3_mirror(bars, tf_min, sl_buf=5.0, trend_th=2.0, trend_lb=24):
    sigs = []; fired = set()
    for idx in range(35, len(bars)):
        s = detect_s3_teacher(bars, idx, [], sl_buf, trend_th, trend_lb, require_h1_fvg=False)
        if s and s["ref_red_t"] not in fired:
            sigs.append({"side": +1, "sl": s["sl"], "tp": s["tp"],
                         "fire_time": s["wicking_t"] + timedelta(minutes=tf_min)})
            fired.add(s["ref_red_t"])
    return sigs

def run(bars_all, tickdays, tf_min, label):
    days = group_bars_by_day(bars_all); perday = {}; allt = []; nsig = 0
    for day in sorted(days):
        if day not in tickdays: continue
        db = days[day]; bars = aggregate_to_tf(db, tf_min) if tf_min > 1 else db
        if len(bars) < 35: continue
        sigs = s3_mirror(bars, tf_min)
        if not sigs: continue
        nsig += len(sigs)
        t = replay_ticks_both(load_ticks(tickdays[day]), sigs, 0.01, 100.0)
        allt += t; perday[day] = sum(x["pnl"] for x in t)
    r = stats(allt); dtr = sorted(perday); cut = dtr[len(dtr)//2] if len(dtr) >= 4 else None
    tr = sum(v for d, v in perday.items() if cut and d < cut)
    oos = sum(v for d, v in perday.items() if cut and d >= cut)
    if not r: print(f"  {label:<12} sigs={nsig} no trades"); return
    print(f"  {label:<12} sigs={nsig:>3}  n={r['n']:>3}  WR={r['pwin']*100:>4.0f}%  "
          f"avgW=${r['w_avg']:>4.1f} avgL=${r['l_avg']:>4.1f}  TOT=${r['total']:>+7.1f}  "
          f"(TRAIN ${tr:+.0f} / OOS ${oos:+.0f})  {'OK' if r['total']>0 else 'BAD'}", flush=True)

bars = load_native()
tickdays = {Path(p).stem.split("_")[-1]: p for p in glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))}
print(f"S3 — native bars, buy-only peak-TP, 0.01 lots, {len(tickdays)} tick-days\n")
run(bars, tickdays, 5, "S3 @ M5")
run(bars, tickdays, 1, "S3 @ M1")
