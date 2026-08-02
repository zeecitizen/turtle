"""zee_feb11_exit_only.py — ISOLATE the exit. Use Zee's exact 24 entries (time + side),
fire entries at those exact moments on parquet tick stream, manage with various EXIT
configs. P&L is invariant under broker offset (relative price deltas).

If Zee-style peak-trail + scratch + no hard SL replicates 65W/4L on his 24 entries → the
EA exit model is the constraint. If not → his exits don't mechanize and we need a
different exit model.

Run with x64 python (parquet).
"""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

PARQ = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")

# Zee's 27 distinct entries (he had 69 fills clustered into these — we treat as 1 trade each)
ZEE = [
    ("01:32:19","buy"), ("01:59:04","buy"), ("02:09:38","sell"), ("02:29:02","buy"),
    ("16:49:07","buy"), ("16:52:21","buy"), ("16:54:10","buy"), ("16:58:03","buy"),
    ("17:02:45","buy"), ("17:36:11","buy"), ("17:36:13","buy"), ("17:37:26","buy"),
    ("17:49:59","buy"), ("18:24:18","buy"), ("18:41:50","buy"), ("19:08:59","sell"),
    ("19:11:05","sell"),("19:11:51","sell"),("19:20:34","sell"),("19:26:06","sell"),
    ("19:29:31","buy"), ("19:32:48","buy"), ("19:36:19","buy"), ("19:38:39","buy"),
    ("19:38:59","buy"), ("19:41:59","sell"),("19:42:26","sell"),
]
COST = 0.20

print("Loading parquet Feb 11 ticks...")
df = pd.read_parquet(PARQ).sort_values("time_msc").reset_index(drop=True)
lo = int(datetime(2026,2,10,23,0,tzinfo=timezone.utc).timestamp()*1000)
hi = int(datetime(2026,2,12, 1,0,tzinfo=timezone.utc).timestamp()*1000)
df = df[(df["time_msc"]>=lo)&(df["time_msc"]<=hi)].reset_index(drop=True)
print(f"  {len(df):,} ticks")
times = df["time_msc"].values
bids  = df["bid"].values
asks  = df["ask"].values


def to_utc_ms(broker_hms):
    """Broker EET (UTC+2) → UTC ms timestamp on Feb 11."""
    hh, mm, ss = map(int, broker_hms.split(":"))
    dt_eet = datetime(2026,2,11,hh,mm,ss, tzinfo=timezone(timedelta(hours=2)))
    return int(dt_eet.timestamp() * 1000)


def run_exits(trail_arm, trail_gb, skim_cap, scratch_sec, scratch_at, max_loss, max_hold_sec):
    """For each Zee entry, simulate exit policy and return list of $P&L."""
    pnls = []
    details = []
    for broker_t, side in ZEE:
        ms = to_utc_ms(broker_t)
        k0 = int(np.searchsorted(times, ms, side="left"))
        if k0 >= len(times): continue
        entry_px = asks[k0] if side == "buy" else bids[k0]
        entry_ms = times[k0]
        peak = 0.0; armed = False
        exit_reason = "EOD"; exit_pnl = 0.0
        for k in range(k0, min(k0 + 200000, len(times))):
            t = times[k]; bid = bids[k]; ask = asks[k]
            if side == "buy":
                cur = bid - entry_px
            else:
                cur = entry_px - ask
            if (t - entry_ms) > max_hold_sec * 1000:
                exit_pnl = cur; exit_reason = "EOH"; break
            if cur >= skim_cap:
                exit_pnl = cur; exit_reason = "SKIM"; break
            peak = max(peak, cur)
            if peak >= trail_arm: armed = True
            if armed and cur <= peak - trail_gb:
                exit_pnl = cur; exit_reason = "TRAIL"; break
            if cur <= -max_loss:
                exit_pnl = cur; exit_reason = "CB"; break
            if (t - entry_ms) > scratch_sec * 1000 and peak < trail_arm and cur <= scratch_at:
                exit_pnl = cur; exit_reason = "SCRATCH"; break
        exit_pnl -= COST
        pnls.append(exit_pnl)
        details.append((broker_t, side, exit_pnl, exit_reason, peak))
    return pnls, details


# Sweep some exit configs
print(f"\nSweeping exit configs on Zee's 27 entries (target: 24W+/3L−, +$25-35/trade avg):")
print(f"  {'arm':>5} {'gb':>5} {'skim':>5} {'scr_s':>6} {'scr_$':>6} {'CB':>5} {'hold_s':>7} | "
      f"{'n':>3} {'W':>3} {'L':>3} {'WR%':>5} {'NET$':>7} {'avgW':>6} {'avgL':>6}")
configs = [
    (1.5, 0.5, 12.0,  60, 0.0, 1.6, 600),
    (1.5, 0.8, 12.0,  60, 0.0, 1.6, 600),
    (2.0, 1.0, 15.0, 120, 0.0, 1.6, 900),
    (2.5, 1.0, 15.0, 120, 0.0, 2.0, 900),
    (3.0, 1.5, 20.0, 180, 0.0, 2.0, 1200),
    (1.5, 0.5,  8.0,  30, 0.5, 1.6, 300),  # tight skim
    (1.0, 0.4, 10.0,  60, 0.2, 1.6, 600),  # very tight trail
]
best = None
for cfg in configs:
    pnls, _ = run_exits(*cfg)
    n = len(pnls); w = sum(1 for p in pnls if p > 0); l = n - w
    tot = sum(pnls)
    avgw = sum(p for p in pnls if p>0)/max(1,w)
    avgl = sum(p for p in pnls if p<=0)/max(1,l)
    print(f"  {cfg[0]:>5.1f} {cfg[1]:>5.1f} {cfg[2]:>5.1f} {cfg[3]:>6} {cfg[4]:>6.1f} {cfg[5]:>5.1f} {cfg[6]:>7} | "
          f"{n:>3} {w:>3} {l:>3} {100*w/n:>4.0f}% {tot:>+7.2f} {avgw:>+6.2f} {avgl:>+6.2f}")
    if best is None or tot > best[0]:
        best = (tot, cfg, pnls)

print(f"\n=== BEST CONFIG: arm={best[1][0]}, gb={best[1][1]}, skim={best[1][2]}, "
      f"scr_s={best[1][3]}, scr_at={best[1][4]}, CB={best[1][5]}, hold={best[1][6]} → NET ${best[0]:+.2f} ===")
pnls, details = run_exits(*best[1])
print(f"\n  Per-trade with best config:")
print(f"  {'time':>9} {'side':>4} {'pnl':>7} {'why':<10} {'peak':>7}")
for d in details:
    print(f"  {d[0]:>9} {d[1]:>4} {d[2]:>+7.2f} {d[3]:<10} {d[4]:>+7.2f}")

# Compare to Zee actual
zee_pnls = [+7.32, +6.65, +11.69, +20.01, +17.12, +8.85, +8.26, +5.73, +54.93,
            +3.29, +14.50, +7.08, +52.78, +8.51, -1.43, +7.82, +3.11, +16.99,
            +14.21, +14.55, +0.84, +5.89, +10.60, +11.02, +0.92, +1.35, +9.50]
print(f"\nZee actual avg/trade: ${sum(zee_pnls)/len(zee_pnls):+.2f} (one fill each; he did multi-fill clusters)")
print(f"Zee total at avg-of-fills view: ${sum(zee_pnls):+.2f}  WR {sum(1 for p in zee_pnls if p>0)*100/len(zee_pnls):.0f}%")
