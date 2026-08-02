"""zee_feb11_ea_v4_tick.py — TICK-LEVEL simulation on Feb 11.

The parquet feed has a ~$17 absolute-price offset vs Zee's broker, BUT:
  - Relative moves (peaks, retracements, spikes) are identical across gold brokers
  - P&L is always (exit_px - entry_px) — invariant under uniform offset
  - The tick TIMESTAMPS and SHAPES are real

So: build M1 bars from parquet ticks → detect setups on those bars → enter at next
tick after bar-close → manage with REAL tick-level peak-trail and circuit breaker.

If this hits 90%+ WR on Feb 11 with realistic exit logic, it tells us Zee's day was
ACHIEVABLE by a machine with right detector+exit. Then we validate on April-May real
broker ticks.

Run with x64 python that has pyarrow.
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

# === EA params ===
TREND_LB = 30; RETRO = 12
TRAIL_ARM = 1.5
TRAIL_GIVEBACK = 0.50      # tick-level can be much tighter
SKIM_CAP = 10.0
MAX_LOSS = 1.60
MAX_HOLD_SEC = 600         # 10 minute max hold
SCRATCH_SEC = 120          # if not profit after 2 minutes, scratch
SCRATCH_AT = 0.0
COST = 0.20
ER_GATE = 0.10

print("Loading parquet ticks for Feb 11...")
df = pd.read_parquet(PARQ).sort_values("time_msc").reset_index(drop=True)
lo = int(datetime(2026, 2, 10, 23, 0, tzinfo=timezone.utc).timestamp() * 1000)
hi = int(datetime(2026, 2, 12, 1, 0, tzinfo=timezone.utc).timestamp() * 1000)
df = df[(df["time_msc"] >= lo) & (df["time_msc"] <= hi)].reset_index(drop=True)
print(f"  {len(df):,} ticks loaded for Feb 11 window")
df["mid"] = (df["bid"] + df["ask"]) / 2

# Build M1 bars from ticks
print("Building M1 bars from ticks...")
df["m1_key"] = (df["time_msc"] // 60_000).astype(np.int64)
g = df.groupby("m1_key", sort=True)
m1_df = g.agg(
    o=("mid", "first"), h=("mid", "max"), l=("mid", "min"), c=("mid", "last"),
    v=("mid", "count"),
    t_start_ms=("time_msc", "min"), t_end_ms=("time_msc", "max"),
).reset_index(drop=True)
m1_df["dt"] = pd.to_datetime(m1_df["t_start_ms"], unit="ms", utc=True)
# Restrict to Feb 11 in UTC for output
m1_df["utc_date"] = m1_df["dt"].dt.date
print(f"  {len(m1_df)} M1 bars built\n")

m1 = m1_df.to_dict("records")
N = len(m1)
times = df["time_msc"].values
bids = df["bid"].values
asks = df["ask"].values
mids = df["mid"].values


def trend_dir(i):
    if i < TREND_LB: return 0
    W = m1[i - TREND_LB:i]
    h = TREND_LB // 2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0


def er_at(i):
    if i < TREND_LB: return 0.0
    closes = [b["c"] for b in m1[i - TREND_LB:i + 1]]
    net = abs(closes[-1] - closes[0])
    path = sum(abs(closes[k] - closes[k-1]) for k in range(1, len(closes)))
    return net / path if path > 1e-9 else 0.0


def setup(i, side):
    if i < TREND_LB + 5 or i + 1 >= N: return None
    bar = m1[i]; prev = m1[i-1]; prev2 = m1[i-2]; prev3 = m1[i-3]
    W = m1[i - TREND_LB:i + 1]
    R = m1[i - RETRO:i + 1]
    L3 = [prev, prev2, prev3]
    L5 = m1[i - 5:i]
    avgv = sum(b["v"] for b in W) / len(W)
    avgbody = sum(abs(b["c"] - b["o"]) for b in W) / len(W)
    avgr = sum(b["h"] - b["l"] for b in W) / len(W)
    td = trend_dir(i)
    er = er_at(i)

    if er < ER_GATE: return None
    last3_net = bar["c"] - m1[i-3]["c"]
    if side == "buy":
        if not (td == +1 or last3_net >= 3.0): return None
    else:
        if not (td == -1 or last3_net <= -3.0): return None

    hits = []

    # [A] UHV pullback
    if side == "buy":
        reds = [b for b in R if b["c"] < b["o"]]
        if reds:
            uhv = max(reds, key=lambda b: b["v"])
            if uhv["v"] >= 1.3 * avgv:
                if bar["l"] <= uhv["h"] + 0.2 and bar["c"] > uhv["h"]:
                    hits.append("UHV")
    else:
        grns = [b for b in R if b["c"] > b["o"]]
        if grns:
            uhv = max(grns, key=lambda b: b["v"])
            if uhv["v"] >= 1.3 * avgv:
                if bar["h"] >= uhv["l"] - 0.2 and bar["c"] < uhv["l"]:
                    hits.append("UHV")

    # [B] Big-bar continuation: trend-dir momentum in last 3 + not reversed
    if side == "buy":
        had_big = any(b["c"] > b["o"] and (b["c"] - b["o"]) >= 2.0 for b in L3)
        not_reversed = bar["c"] >= bar["o"] - 0.5
        if had_big and not_reversed: hits.append("CONT")
    else:
        had_big = any(b["c"] < b["o"] and (b["o"] - b["c"]) >= 2.0 for b in L3)
        not_reversed = bar["c"] <= bar["o"] + 0.5
        if had_big and not_reversed: hits.append("CONT")

    # [C] Sweep then close back
    prior = m1[i - 30:i - 2]
    if prior:
        if side == "buy":
            prior_lo = min(b["l"] for b in prior)
            if any(b["l"] < prior_lo and b["c"] > prior_lo for b in [m1[i-1], bar]):
                hits.append("SWP")
        else:
            prior_hi = max(b["h"] for b in prior)
            if any(b["h"] > prior_hi and b["c"] < prior_hi for b in [m1[i-1], bar]):
                hits.append("SWP")

    return hits if hits else None


def simulate_tick(t_signal_ms, side):
    """Enter at first tick after t_signal_ms. Manage tick-by-tick."""
    k0 = int(np.searchsorted(times, t_signal_ms, side="left"))
    if k0 >= len(times): return None
    entry_px = asks[k0] if side == "buy" else bids[k0]
    entry_ms = times[k0]
    peak = 0.0; armed = False
    for k in range(k0, len(times)):
        t = times[k]; bid = bids[k]; ask = asks[k]
        if (t - entry_ms) > MAX_HOLD_SEC * 1000:
            cur = (bid - entry_px) if side == "buy" else (entry_px - ask)
            return (cur - COST, t, "EOH")
        if side == "buy":
            cur = bid - entry_px
        else:
            cur = entry_px - ask
        # Skim
        if cur >= SKIM_CAP:
            return (cur - COST, t, "SKIM")
        # Update peak (= max MFE seen)
        peak = max(peak, cur)
        if peak >= TRAIL_ARM: armed = True
        # Trail
        if armed:
            if cur <= peak - TRAIL_GIVEBACK:
                return (cur - COST, t, "TRAIL")
        # Circuit breaker
        if cur <= -MAX_LOSS:
            return (-MAX_LOSS - COST, t, "CB")
        # Scratch
        if (t - entry_ms) > SCRATCH_SEC * 1000 and peak < TRAIL_ARM and cur <= SCRATCH_AT:
            return (cur - COST, t, "SCRATCH")
    cur = (bids[-1] - entry_px) if side == "buy" else (entry_px - asks[-1])
    return (cur - COST, times[-1], "EOD")


# Run on Feb 11 UTC only
feb11_d = datetime(2026, 2, 11).date()
fills = []
for i in range(N):
    if m1[i]["utc_date"] != feb11_d: continue
    for side in ("buy", "sell"):
        h = setup(i, side)
        if not h: continue
        # Fire at end of current bar (t_end_ms)
        result = simulate_tick(m1[i]["t_end_ms"] + 1, side)
        if result is None: continue
        pnl, exit_ms, why = result
        fills.append({
            "t": pd.to_datetime(m1[i]["t_start_ms"], unit="ms", utc=True),
            "side": side, "pnl": pnl, "why": why, "patterns": ",".join(h),
        })

n = len(fills)
w = sum(1 for f in fills if f["pnl"] > 0)
l = sum(1 for f in fills if f["pnl"] <= 0)
tot = sum(f["pnl"] for f in fills)
avgw = sum(f["pnl"] for f in fills if f["pnl"] > 0) / max(1, w)
avgl = sum(f["pnl"] for f in fills if f["pnl"] <= 0) / max(1, l)
print(f"=== FEB 11 v4 TICK RESULTS ===")
print(f"  Fills: {n}   Wins: {w}   Losses: {l}   WR: {100*w/max(1,n):.0f}%")
print(f"  NET:    ${tot:+.2f}    avgW ${avgw:+.2f}    avgL ${avgl:+.2f}")
print(f"  TARGET: 65W/4L (94% WR), NET +$835, avgW +$12.93, avgL -$1.32\n")
print(f"  {'pattern':<10} {'fires':>5} {'wins':>5} {'WR%':>5} {'NET$':>8}")
all_p = set()
for f in fills: all_p |= set(f["patterns"].split(","))
for p in sorted(all_p):
    sub = [f for f in fills if p in f["patterns"].split(",")]
    nn = len(sub); ww = sum(1 for x in sub if x["pnl"] > 0)
    print(f"  {p:<10} {nn:>5} {ww:>5} {100*ww/max(1,nn):>4.0f}% {sum(x['pnl'] for x in sub):>+8.2f}")

# Coverage of Zee's setups — convert Zee EET to UTC by -2h
ZEE_UTC = []
for hm, sd in [
    ("01:32","buy"),("01:59","buy"),("02:09","sell"),("02:29","buy"),
    ("16:49","buy"),("16:52","buy"),("16:54","buy"),("16:58","buy"),
    ("17:02","buy"),("17:36","buy"),("17:37","buy"),("17:49","buy"),
    ("18:24","buy"),("18:41","buy"),("19:08","sell"),("19:11","sell"),
    ("19:20","sell"),("19:26","sell"),("19:29","buy"),("19:32","buy"),
    ("19:36","buy"),("19:38","buy"),("19:41","sell"),("19:42","sell"),
]:
    hh, mm = map(int, hm.split(":"))
    utc_h = (hh - 2) % 24
    ZEE_UTC.append((utc_h * 60 + mm, sd))
matched = 0
for tmin, sd in ZEE_UTC:
    for f in fills:
        fm = f["t"].hour * 60 + f["t"].minute
        if f["side"] == sd and abs(fm - tmin) <= 3:
            matched += 1; break
print(f"\n  Captured Zee setups: {matched} / 24 (±3 min same side, UTC-aligned)")

# Tail of fills
print(f"\n  Last 20 fills:")
print(f"  {'entry_t':>10} {'side':>4} {'pnl':>7} {'why':<10} {'patterns':<15}")
for f in fills[-20:]:
    print(f"  {f['t'].strftime('%H:%M:%S'):>10} {f['side']:>4} {f['pnl']:>+7.2f} {f['why']:<10} {f['patterns']:<15}")
