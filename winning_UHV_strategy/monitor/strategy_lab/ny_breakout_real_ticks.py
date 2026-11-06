"""NY Session Breakout — test if range (London session 07:00-12:00 UTC) breakout at NY open works.
Same mechanics as London Breakout but range = London session, breakout starts at NY open."""
import pandas as pd, numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_ny_breakout_results.json")
LOTS = 0.30; COMMISSION = 7.0 * LOTS

print("[LOAD]...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
dt = pd.to_datetime(df["time_msc"], unit="ms", utc=True)
df["date_str"] = dt.dt.strftime("%Y-%m-%d")
df["mins_utc"] = dt.dt.hour * 60 + dt.dt.minute

day_data = {}
for date_str, sub in df.groupby("date_str", sort=True):
    day_data[date_str] = {
        "bid": sub["bid"].to_numpy(), "ask": sub["ask"].to_numpy(),
        "mins": sub["mins_utc"].to_numpy(),
    }

def simulate_day(d, range_start_min, range_end_min, breakout_start_min, day_close_min,
                 tp_mult, sl_mult):
    mins, bid, ask = d["mins"], d["bid"], d["ask"]
    rm = (mins >= range_start_min) & (mins < range_end_min)
    if rm.sum() < 50: return None
    r_high = float(bid[rm].max()); r_low = float(bid[rm].min())
    r_range = r_high - r_low
    if r_range < 0.05: return None
    bm = (mins >= breakout_start_min) & (mins < day_close_min)
    if bm.sum() < 50: return None
    bbid = bid[bm]; bask = ask[bm]
    above = bbid > r_high; below = bbid < r_low
    fa = int(np.argmax(above)) if above.any() else len(bbid)
    fb = int(np.argmax(below)) if below.any() else len(bbid)
    if fa >= len(bbid) and fb >= len(bbid): return None
    if fa < fb:
        bd = 1; bo = fa; bp = float(bask[bo])
    else:
        bd = -1; bo = fb; bp = float(bbid[bo])
    sl_off = sl_mult * r_range; tp_off = tp_mult * r_range
    sl = bp - sl_off if bd == 1 else bp + sl_off
    tp = bp + tp_off if bd == 1 else bp - tp_off
    rb = bbid[bo:]; ra = bask[bo:]
    if bd == 1:
        sh = rb <= sl; th = rb >= tp
    else:
        sh = ra >= sl; th = ra <= tp
    sf = int(np.argmax(sh)) if sh.any() else len(rb)
    tf = int(np.argmax(th)) if th.any() else len(rb)
    if tf < sf: ex = tp; rs = "TP"
    elif sf < len(rb): ex = sl; rs = "SL"
    else:
        ex = float(rb[-1]) if bd == 1 else float(ra[-1])
        rs = "TIME"
    pnl_pts = (ex - bp) if bd == 1 else (bp - ex)
    pnl = pnl_pts * 100 * LOTS - COMMISSION
    return {"side": "buy" if bd == 1 else "sell", "range_pts": round(r_range*100, 1),
            "entry": round(bp, 2), "sl": round(sl, 2), "tp": round(tp, 2),
            "exit": round(ex, 2), "exit_reason": rs, "pnl": round(pnl, 2)}

def backtest(cfg):
    trades = []
    for date_str, d in day_data.items():
        r = simulate_day(d, **cfg)
        if r: r["date"] = date_str; trades.append(r)
    return trades

def stats(trades):
    if not trades: return {"n": 0}
    arr = np.array([t["pnl"] for t in trades])
    wins = arr[arr > 0]; losses = arr[arr < 0]
    eq = arr.cumsum(); dd = float((np.maximum.accumulate(eq) - eq).max())
    return {"n": len(arr), "wr": round(100*len(wins)/len(arr),2),
            "pf": round(float(wins.sum()/-losses.sum()),2) if len(losses) and losses.sum() else None,
            "net": round(float(arr.sum()),2), "avg": round(float(arr.mean()),2),
            "max_dd": round(dd, 2)}

# === SWEEP ===
# Try multiple range/breakout window combos for NY session
# NY open conventionally 13:00 UTC (9 AM ET / 8 AM CT for futures)
# Pre-NY is 07:00-12:00 UTC (London session)
SWEEP = []
for range_start, range_end, breakout_start in [
    (7*60,  12*60, 12*60),   # London session range, NY pre-open break
    (7*60,  13*60, 13*60),   # London + 1h, formal NY open
    (8*60,  13*60, 13*60),   # London core, formal NY
    (10*60, 13*60, 13*60),   # late London / pre-NY tight range
    (11*60, 13*60, 13*60),   # 2h tight pre-NY range
    (0*60,  13*60, 13*60),   # FULL overnight + London = NY breakout
]:
    for tp_mult in [1.0, 1.5, 2.0, 2.5]:
        for sl_mult in [0.5, 0.75, 1.0]:
            SWEEP.append({
                "range_start_min": range_start, "range_end_min": range_end,
                "breakout_start_min": breakout_start, "day_close_min": 21*60,
                "tp_mult": tp_mult, "sl_mult": sl_mult,
            })

print(f"[SWEEP] {len(SWEEP)} configs", flush=True)
results = []
for i, cfg in enumerate(SWEEP):
    trades = backtest(cfg)
    s = stats(trades); s.update(cfg); s["trades"] = trades
    results.append(s)

ok = [r for r in results if r.get("n", 0) >= 30]
ok.sort(key=lambda r: r["net"], reverse=True)

print(f"\n=== TOP 12 NY BREAKOUT (n>=30) ===", flush=True)
print(f"{'rng':>10} {'bo':>3} {'tp':>4} {'sl':>4} | {'n':>3} {'wr%':>5} {'pf':>5} {'net$':>10} {'dd':>8}", flush=True)
for r in ok[:12]:
    rg = f"{r['range_start_min']//60:02d}-{r['range_end_min']//60:02d}"
    bo = f"{r['breakout_start_min']//60:02d}"
    print(f"{rg:>10} {bo:>3} {r['tp_mult']:>4.1f} {r['sl_mult']:>4.2f} | {r['n']:>3} {r['wr']:>5.1f} {str(r['pf']):>5} {r['net']:>10.2f} {r['max_dd']:>8.2f}", flush=True)

# Train/test split on best
print(f"\n=== TRAIN/TEST SPLIT ON TOP 6 ===", flush=True)
print(f"{'rng':>10} {'bo':>3} {'tp':>4} {'sl':>4} | {'tr_n':>4} {'tr_wr':>5} {'tr_pf':>5} {'tr_net':>9} || {'te_n':>4} {'te_wr':>5} {'te_pf':>5} {'te_net':>9}", flush=True)
train_test = []
for r in ok[:6]:
    trades = r["trades"]
    all_dates = sorted(set(t["date"] for t in trades))
    if not all_dates: continue
    cutoff = all_dates[int(len(all_dates) * 0.75)]
    trn = [t for t in trades if t["date"] < cutoff]
    tst = [t for t in trades if t["date"] >= cutoff]
    s_trn = stats(trn) if trn else {"n":0}
    s_tst = stats(tst) if tst else {"n":0}
    rg = f"{r['range_start_min']//60:02d}-{r['range_end_min']//60:02d}"
    bo = f"{r['breakout_start_min']//60:02d}"
    print(f"{rg:>10} {bo:>3} {r['tp_mult']:>4.1f} {r['sl_mult']:>4.2f} | {s_trn['n']:>4} {s_trn.get('wr',0):>5.1f} {str(s_trn.get('pf')):>5} {s_trn.get('net',0):>9.2f} || {s_tst['n']:>4} {s_tst.get('wr',0):>5.1f} {str(s_tst.get('pf')):>5} {s_tst.get('net',0):>9.2f}", flush=True)
    train_test.append({"config": {k:v for k,v in r.items() if k != "trades"},
                       "train": s_trn, "test": s_tst})

best = ok[0] if ok else None
if best:
    cfg_only = {k: v for k, v in best.items() if k != "trades"}
    print(f"\n=== BEST OVERALL ===", flush=True)
    print(json.dumps(cfg_only, indent=2, default=str), flush=True)

doc = {
    "started": datetime.now(timezone.utc).isoformat(),
    "best": {k: v for k, v in best.items() if k != "trades"} if best else None,
    "top12": [{k: v for k, v in r.items() if k != "trades"} for r in ok[:12]],
    "train_test": train_test,
}
OUT_J.write_text(json.dumps(doc, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
