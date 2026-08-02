"""Volume-source diagnostic — investigate Zee's hypothesis that MT5 volume
is wrong/different from TradingView.

Without TV Desktop running we can't directly compare. But we CAN check:
  1. Does Blueberry MT5 iVolume() match the actual tick count from
     shano_ticks_2026-06-19.csv? (sanity check: same broker)
  2. For each EA-fired UHV, was it actually the highest-vol bar in the
     surrounding 5-10 bar window? (internal consistency)
  3. What's the volume distribution like? Are UHVs really "ultra"?
"""
import sys, re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
TERMINAL = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8")

# ── 1. Compute M1 bar tick counts directly from shano_ticks_2026-06-19.csv ──
print("=== Computing M1 tick volumes from raw tick CSV ===")
csv = COMMON / "shano_ticks_2026-06-19.csv"
bar_ticks = Counter()
bar_high = {}
bar_low = {}
with open(csv) as f:
    f.readline()
    for line in f:
        try:
            t, bid, ask = line.strip().split(",")
            dt = datetime.strptime(t, "%Y.%m.%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
            minute_key = dt.strftime("%H:%M")
            bar_ticks[minute_key] += 1
            mid = (float(bid) + float(ask)) / 2
            bar_high[minute_key] = max(bar_high.get(minute_key, mid), mid)
            bar_low[minute_key]  = min(bar_low.get(minute_key, mid), mid)
        except Exception:
            continue

print(f"  Total ticks: {sum(bar_ticks.values()):,}")
print(f"  Total minutes: {len(bar_ticks)}")
print(f"  Avg ticks/min: {sum(bar_ticks.values())/len(bar_ticks):.0f}")
counts = sorted(bar_ticks.values())
print(f"  Median: {counts[len(counts)//2]}, p90: {counts[int(len(counts)*0.9)]}, p99: {counts[int(len(counts)*0.99)]}, max: {max(counts)}")

# ── 2. Read EA-claimed UHV volumes from log ──
print()
print("=== EA-claimed UHV volumes from log (broker GMT+2 = UTC-2 conversion) ===")
log = sorted((TERMINAL / "MQL5/Logs").glob("20260619*.log"))[-1]
with open(log, "rb") as f:
    content = f.read().decode("utf-16le", errors="ignore")

# Extract trigger lines with timestamp + uhv_shift + uhv_vol
trigger_re = re.compile(
    r"(\d{2}:\d{2}:\d{2})\.(\d+)\s+S1Trader[^\n]*S1 (BUY|SELL) LIVE TRIGGER[^\n]*"
    r"uhv_shift=(\d+)\s+\(vol=(\d+)\)"
)
fill_re = re.compile(r"(\d{2}:\d{2}:\d{2})\.(\d+)\s+S1Trader[^\n]*\[FILLED\]")

# Get unique fires (paired with FILLED) — broker times
fills = list(fill_re.finditer(content))
triggers = list(trigger_re.finditer(content))
events = []
for f in fills:
    last_tr = None
    for tr in triggers:
        if tr.start() < f.start(): last_tr = tr
        else: break
    if not last_tr: continue
    # broker time → UTC (subtract 2 hours)
    h, m, s = map(int, last_tr.group(1).split(":"))
    utc_h = (h - 2) % 24
    events.append({
        "broker_t": last_tr.group(1),
        "utc_t":  f"{utc_h:02d}:{m:02d}",
        "side": last_tr.group(3),
        "uhv_shift": int(last_tr.group(4)),
        "uhv_vol_ea": int(last_tr.group(5)),
    })
print(f"  Unique fires: {len(events)}")

# ── 3. For each fire, map to the UHV bar's actual tick count from CSV ──
print()
print("=== EA's vol vs CSV-computed vol for each UHV bar ===")
print(f"  {'utc_t':>5s}  {'side':>4s}  {'shift':>5s}  {'ea_vol':>6s}  {'csv_vol':>7s}  {'ratio':>5s}  match?")

matches = mismatches = 0
diffs = []
for e in events:
    # Map: broker_t (HH:MM:SS) - shift minutes = UHV's broker time
    h, m, s = map(int, e["broker_t"].split(":"))
    total_min = h*60 + m
    uhv_total = total_min - e["uhv_shift"]
    uhv_broker_t = f"{uhv_total // 60:02d}:{uhv_total % 60:02d}"
    uhv_utc_t = f"{(uhv_total // 60 - 2) % 24:02d}:{uhv_total % 60:02d}"
    csv_vol = bar_ticks.get(uhv_utc_t, 0)
    if csv_vol == 0:
        # Bar not in CSV (might be outside coverage)
        continue
    ratio = e["uhv_vol_ea"] / csv_vol if csv_vol > 0 else 0
    matched = abs(ratio - 1.0) < 0.05  # within 5%
    if matched: matches += 1
    else: mismatches += 1
    diffs.append((csv_vol, e["uhv_vol_ea"]))
    print(f"  {e['utc_t']}  {e['side']:>4s}  {e['uhv_shift']:>5d}  {e['uhv_vol_ea']:>6d}  {csv_vol:>7d}  {ratio:>5.2f}  {'✓' if matched else '✗'}")

print()
print(f"  Matched (within 5%): {matches}/{matches+mismatches}")

# ── 4. Was EA's UHV actually the highest vol in its window? ──
print()
print("=== Was EA-flagged UHV actually the LOCAL MAX vol bar? ===")
sorted_minutes = sorted(bar_ticks.keys())
for e in events[:15]:
    h, m, s = map(int, e["broker_t"].split(":"))
    total_min = h*60 + m
    uhv_total = total_min - e["uhv_shift"]
    uhv_utc_t = f"{(uhv_total // 60 - 2) % 24:02d}:{uhv_total % 60:02d}"
    if uhv_utc_t not in bar_ticks: continue
    # Look at +/- 5 bars around UHV
    if uhv_utc_t not in sorted_minutes: continue
    idx = sorted_minutes.index(uhv_utc_t)
    win = sorted_minutes[max(0, idx-5) : idx+6]
    vols = [(t, bar_ticks[t]) for t in win]
    max_t, max_v = max(vols, key=lambda x: x[1])
    uhv_v = bar_ticks[uhv_utc_t]
    is_max = (max_t == uhv_utc_t)
    print(f"  UTC {uhv_utc_t} EA_UHV_vol={uhv_v}  window_max@{max_t}={max_v}  {'✓ local max' if is_max else '✗ NOT max (off by '+str(max_v-uhv_v)+')'}")
