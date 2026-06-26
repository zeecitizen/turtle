"""zee_feb11_tick_forensics.py — for each Zee Feb-11 entry/exit, examine tick stream
±N seconds around the moment. Build a feature signature that captures what HE was
reacting to, then we can replicate it.

Run with x64 python: C:\\Users\\zeesh\\AppData\\Local\\Python\\bin\\python.exe
"""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
sys.stdout.reconfigure(encoding="utf-8")

PARQ = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")

# Zee's 24 distinct setups — broker EET (UTC+2 winter)
ZEE = [
    ("01:32:19","buy",5045.07, "01:47:30",5045.94,  +7.32),
    ("01:59:04","buy",5042.17, "02:00:43",5042.96,  +6.65),
    ("02:09:38","sell",5040.68,"02:10:18",5039.29, +11.69),
    ("02:29:02","buy",5039.03, "02:30:28",5041.41, +20.01),
    ("16:49:07","buy",5047.93, "16:51:03",5049.96, +17.12),
    ("16:52:21","buy",5050.77, "16:52:27",5051.82,  +8.85),
    ("16:54:10","buy",5056.74, "16:54:20",5057.72,  +8.26),
    ("16:58:03","buy",5064.26, "16:58:27",5064.94,  +5.73),
    ("17:02:45","buy",5055.71, "17:03:51",5062.23, +54.93),
    ("17:36:11","buy",5056.53, "17:36:26",5056.92,  +3.29),
    ("17:36:13","buy",5057.05, "17:52:56",5058.77, +14.50),
    ("17:37:26","buy",5045.82, "17:40:02",5046.66,  +7.08),
    ("17:49:59","buy",5048.32, "17:52:33",5054.58, +52.78),
    ("18:24:18","buy",5059.26, "18:28:33",5060.27,  +8.51),
    ("18:41:50","buy",5078.10, "19:06:41",5077.93,  -1.43),
    ("19:08:59","sell",5083.28,"19:09:08",5082.35,  +7.82),
    ("19:11:05","sell",5083.39,"19:11:27",5083.02,  +3.11),
    ("19:11:51","sell",5083.79,"19:19:10",5081.77, +16.99),
    ("19:20:34","sell",5084.21,"19:20:40",5082.52, +14.21),
    ("19:26:06","sell",5089.16,"19:26:50",5087.43, +14.55),
    ("19:29:31","buy",5086.34, "19:39:03",5086.44,  +0.84),
    ("19:32:48","buy",5084.71, "19:37:34",5085.41,  +5.89),
    ("19:36:19","buy",5082.91, "19:37:19",5084.17, +10.60),
    ("19:38:39","buy",5083.28, "19:38:50",5084.59, +11.02),
    ("19:38:59","buy",5086.33, "19:39:03",5086.44,  +0.92),
    ("19:41:59","sell",5091.09,"19:42:54",5090.93,  +1.35),
    ("19:42:26","sell",5093.18,"19:42:40",5092.05,  +9.50),
]
print(f"Loading parquet ticks for Feb 11...")
df = pd.read_parquet(PARQ).sort_values("time_msc").reset_index(drop=True)
lo = int(datetime(2026,2,10,23,0,tzinfo=timezone.utc).timestamp()*1000)
hi = int(datetime(2026,2,12, 1,0,tzinfo=timezone.utc).timestamp()*1000)
df = df[(df["time_msc"] >= lo) & (df["time_msc"] <= hi)].reset_index(drop=True)
df["mid"] = (df["bid"] + df["ask"]) / 2
times = df["time_msc"].values
mids = df["mid"].values
bids = df["bid"].values; asks = df["ask"].values
print(f"  Feb 11 ticks: {len(df):,}\n")


def to_utc_ms(broker_hms):
    """Broker EET (UTC+2). Returns UTC ms timestamp on Feb 11."""
    hh, mm, ss = map(int, broker_hms.split(":"))
    dt_eet = datetime(2026,2,11,hh,mm,ss, tzinfo=timezone(timedelta(hours=2)))
    return int(dt_eet.timestamp() * 1000)


def slice_ticks(t_ms, before_s, after_s):
    lo = t_ms - before_s * 1000
    hi = t_ms + after_s * 1000
    i0 = np.searchsorted(times, lo, side="left")
    i1 = np.searchsorted(times, hi, side="right")
    return i0, i1


def entry_features(t_ms, side, ent_px):
    """Look at -60s..+5s around entry."""
    i_lo, i_at = slice_ticks(t_ms, 60, 0)
    if i_at - i_lo < 5: return None
    # last 60s window
    w_mids = mids[i_lo:i_at]
    # 10s velocity right before entry
    i_10, _ = slice_ticks(t_ms, 10, 0)
    if i_at - i_10 < 2: return None
    v10 = mids[i_at - 1] - mids[i_10]
    # 3s velocity right before entry
    i_3, _ = slice_ticks(t_ms, 3, 0)
    v3 = mids[i_at - 1] - mids[i_3] if (i_at - i_3) >= 2 else 0.0
    # 60s range
    rng60 = w_mids.max() - w_mids.min()
    # 60s direction (close - open)
    dir60 = w_mids[-1] - w_mids[0]
    # Was there a recent extreme (high/low) and did price sweep & reverse?
    # Find -60s high & low and where they happened
    hi60_idx = int(np.argmax(w_mids))
    lo60_idx = int(np.argmin(w_mids))
    # Tick density (ticks/sec) — proxy for "intensity"
    tps = (i_at - i_lo) / 60.0
    # Spread at entry
    spr = asks[i_at - 1] - bids[i_at - 1]
    # Where is entry vs the 60s high/low?
    entry_pct = (mids[i_at - 1] - w_mids.min()) / max(0.01, rng60)  # 0=at low, 1=at high
    # Is entry trying to BREAK 60s high (buy) or low (sell)?
    if side == "buy":
        brk = mids[i_at - 1] >= w_mids.max() - 0.05
        sweep_recent = lo60_idx > hi60_idx  # low came AFTER high → sweep down → reverse
    else:
        brk = mids[i_at - 1] <= w_mids.min() + 0.05
        sweep_recent = hi60_idx > lo60_idx
    return {
        "v3": v3, "v10": v10, "dir60": dir60, "rng60": rng60,
        "tps": tps, "spr": spr, "entry_pct": entry_pct,
        "brk": brk, "sweep_recent": sweep_recent,
    }


def exit_features(open_ms, close_ms, side, ent_px, exit_px):
    """Look at the path from entry to exit."""
    i_at_open = np.searchsorted(times, open_ms, side="left")
    i_at_close = np.searchsorted(times, close_ms, side="left")
    if i_at_close <= i_at_open: return None
    path = mids[i_at_open:i_at_close+1]
    bids_p = bids[i_at_open:i_at_close+1]
    asks_p = asks[i_at_open:i_at_close+1]
    dur = (times[i_at_close] - times[i_at_open]) / 1000.0
    if side == "buy":
        peak_idx = int(np.argmax(bids_p))
        trough_idx = int(np.argmin(bids_p))
        peak_pnl = bids_p[peak_idx] - ent_px
        trough_pnl = bids_p[trough_idx] - ent_px
        # giveback from peak to exit
        gb = bids_p[peak_idx] - exit_px
    else:
        peak_idx = int(np.argmin(asks_p))
        trough_idx = int(np.argmax(asks_p))
        peak_pnl = ent_px - asks_p[peak_idx]
        trough_pnl = ent_px - asks_p[trough_idx]
        gb = exit_px - asks_p[peak_idx]
    peak_sec = (times[i_at_open + peak_idx] - times[i_at_open]) / 1000.0
    trough_sec = (times[i_at_open + trough_idx] - times[i_at_open]) / 1000.0
    return {"dur": dur, "peak_pnl": peak_pnl, "trough_pnl": trough_pnl,
            "peak_sec": peak_sec, "trough_sec": trough_sec, "gb": gb}


print("=== ENTRY FORENSICS (−60s..0s before each entry) ===")
print(f"{'broker':>9} {'side':>4} {'entry':>8}  {'v3':>6} {'v10':>6} {'dir60':>6} {'rng60':>5} "
      f"{'tps':>4} {'ent%':>5} {'brk':>4} {'swp':>4}")
ent_data = []
for broker_t, side, ent, *rest in ZEE:
    ms = to_utc_ms(broker_t)
    f = entry_features(ms, side, ent)
    if not f: continue
    ent_data.append((side, f))
    print(f"{broker_t:>9} {side:>4} {ent:>8.2f}  {f['v3']:>+6.2f} {f['v10']:>+6.2f} {f['dir60']:>+6.2f} "
          f"{f['rng60']:>5.2f} {f['tps']:>4.1f} {f['entry_pct']:>5.2f} {str(f['brk'])[0]:>4} {str(f['sweep_recent'])[0]:>4}")

print(f"\n=== EXIT FORENSICS (per trade) ===")
print(f"{'broker':>9} {'side':>4} {'dur':>5} {'peakUSD':>8} {'trough':>8} {'pkSec':>6} {'trSec':>6} {'giveback':>10}")
exit_data = []
for broker_t, side, ent, close_t, exit_px, _ in ZEE:
    ms_open = to_utc_ms(broker_t)
    ms_close = to_utc_ms(close_t)
    if ms_close < ms_open: ms_close += 86400000
    f = exit_features(ms_open, ms_close, side, ent, exit_px)
    if not f: continue
    exit_data.append((side, f))
    print(f"{broker_t:>9} {side:>4} {f['dur']:>5.0f} {f['peak_pnl']:>+8.2f} {f['trough_pnl']:>+8.2f} "
          f"{f['peak_sec']:>6.0f} {f['trough_sec']:>6.0f} {f['gb']:>+10.2f}")

print(f"\n=== ENTRY PATTERN SUMMARY ===")
buys = [f for s,f in ent_data if s=="buy"]
sells = [f for s,f in ent_data if s=="sell"]
print(f"  {'metric':<20}{'BUY (n=' + str(len(buys)) + ')':>22}{'SELL (n=' + str(len(sells)) + ')':>22}")
for key in ["v3","v10","dir60","rng60","tps","entry_pct"]:
    bv = np.mean([f[key] for f in buys]) if buys else 0
    sv = np.mean([f[key] for f in sells]) if sells else 0
    print(f"  {key:<20}{bv:>+22.3f}{sv:>+22.3f}")
for key in ["brk", "sweep_recent"]:
    bv = sum(1 for f in buys if f[key]) / max(1, len(buys))
    sv = sum(1 for f in sells if f[key]) / max(1, len(sells))
    print(f"  {key+' (% true)':<20}{bv*100:>21.0f}%{sv*100:>21.0f}%")

print(f"\n=== EXIT PATTERN SUMMARY ===")
all_e = [f for _,f in exit_data]
wins = [f for _,f in exit_data if f["peak_pnl"] > 0 and f["gb"] < f["peak_pnl"]]
losses = [f for _,f in exit_data if f["peak_pnl"] <= 0.5]
print(f"  All: n={len(all_e)} mean dur {np.mean([f['dur'] for f in all_e]):.0f}s "
      f"mean peakUSD ${np.mean([f['peak_pnl'] for f in all_e]):+.2f} "
      f"mean trough ${np.mean([f['trough_pnl'] for f in all_e]):+.2f}")
print(f"  Winners (peak>0): n={len(wins)} mean peak ${np.mean([f['peak_pnl'] for f in wins]):+.2f}, "
      f"mean peak-at-sec={np.mean([f['peak_sec'] for f in wins]):.0f}, "
      f"mean giveback to exit ${np.mean([f['gb'] for f in wins]):+.2f}")
print(f"  Scratches (peak<=$0.5): n={len(losses)} mean dur {np.mean([f['dur'] for f in losses]):.0f}s "
      f"mean trough ${np.mean([f['trough_pnl'] for f in losses]):+.2f}")
