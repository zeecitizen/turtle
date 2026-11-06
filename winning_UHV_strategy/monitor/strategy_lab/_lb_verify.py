"""Self-contained London Breakout best-config verify + train/test."""
import pandas as pd, numpy as np
from pathlib import Path

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
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

def simulate_day(d, asian_start_min=0, asian_end_min=420, london_start_min=420,
                 day_close_min=1260, tp_mult=1.0, sl_mult=1.0):
    mins, bid, ask = d["mins"], d["bid"], d["ask"]
    am = (mins >= asian_start_min) & (mins < asian_end_min)
    if am.sum() < 50: return None
    a_high = float(bid[am].max()); a_low = float(bid[am].min())
    a_range = a_high - a_low
    range_pts = a_range * 100
    lm = (mins >= london_start_min) & (mins < day_close_min)
    if lm.sum() < 50: return None
    lbid = bid[lm]; lask = ask[lm]
    above = lbid > a_high; below = lbid < a_low
    fa = int(np.argmax(above)) if above.any() else len(lbid)
    fb = int(np.argmax(below)) if below.any() else len(lbid)
    if fa >= len(lbid) and fb >= len(lbid): return None
    if fa < fb:
        bd = 1; bo = fa; bp = float(lask[bo])
    else:
        bd = -1; bo = fb; bp = float(lbid[bo])
    sl_off = sl_mult * a_range; tp_off = tp_mult * a_range
    sl = bp - sl_off if bd == 1 else bp + sl_off
    tp = bp + tp_off if bd == 1 else bp - tp_off
    rb = lbid[bo:]; ra = lask[bo:]
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
    return {"side": "buy" if bd == 1 else "sell", "range_pts": round(range_pts, 1),
            "entry": round(bp, 2), "sl": round(sl, 2), "tp": round(tp, 2),
            "exit": round(ex, 2), "exit_reason": rs, "pnl": round(pnl, 2)}

trades = []
for date_str in sorted(day_data):
    r = simulate_day(day_data[date_str])
    if r: r["date"] = date_str; trades.append(r)

print(f"\nTotal trades: {len(trades)}\n")
print(f"{'date':>10} {'side':>4} {'rng_pts':>7} {'entry':>8} {'sl':>8} {'tp':>8} {'exit':>8} {'reason':>6} {'pnl$':>9}")
for t in trades[:25]:
    print(f"{t['date']:>10} {t['side']:>4} {t['range_pts']:>7.1f} {t['entry']:>8} {t['sl']:>8} {t['tp']:>8} {t['exit']:>8} {t['exit_reason']:>6} {t['pnl']:>9.2f}")

arr = np.array([t["pnl"] for t in trades])
print(f"\nAll: n={len(arr)} net=${arr.sum():.2f} avg=${arr.mean():.2f} min=${arr.min():.2f} max=${arr.max():.2f}")

by_r = {}
for t in trades: by_r.setdefault(t["exit_reason"], []).append(t["pnl"])
for r, p in by_r.items():
    print(f"  {r}: n={len(p)} avg=${np.mean(p):.2f} sum=${np.sum(p):.2f}")

ranges = np.array([t["range_pts"] for t in trades])
print(f"\nAsian range (pts): min={ranges.min():.0f} median={np.median(ranges):.0f} mean={ranges.mean():.0f} max={ranges.max():.0f}")

# Train/test split (first 75% / last 25% of dates)
all_dates = sorted(set(t["date"] for t in trades))
split_idx = int(len(all_dates) * 0.75)
test_start = all_dates[split_idx]
trn = [t for t in trades if t["date"] < test_start]
tst = [t for t in trades if t["date"] >= test_start]
def stx(arr):
    if not arr: return None
    a = np.array([t["pnl"] for t in arr])
    w = a[a > 0]; l = a[a < 0]
    eq = a.cumsum(); dd = float((np.maximum.accumulate(eq) - eq).max())
    return {"n": len(a), "wr": round(100*len(w)/len(a),2),
            "pf": round(float(w.sum()/-l.sum()),2) if len(l) and l.sum() else None,
            "net": round(float(a.sum()),2), "avg": round(float(a.mean()),2),
            "max_dd": round(dd,2)}
print(f"\nTrain (cutoff at {test_start}):")
print(f"  {stx(trn)}")
print(f"Test:")
print(f"  {stx(tst)}")
