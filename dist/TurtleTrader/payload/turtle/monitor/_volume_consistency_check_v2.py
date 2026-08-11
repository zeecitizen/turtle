"""Redo the volume consistency check with PROPER scope.
v1 compared EA's UHV against ±5min window — but ±5min includes post-breakout
bars, which obviously have higher volume. Wrong comparison.

v2 compares EA's UHV against bars in the RETRACEMENT PORTION only — bars from
retracement origin (or 10 bars back) up to but NOT INCLUDING the breakout bar.
"""
import sys, re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
TERMINAL = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/DBE9B8B347D025DD139E103EE3B63FD8")

# Tick counts per UTC HH:MM
csv = COMMON / "shano_ticks_2026-06-19.csv"
bar_ticks = Counter()
bar_color = {}    # 'R' or 'G' based on first/last tick mid-price (rough heuristic)
bar_o = {}; bar_c = {}
with open(csv) as f:
    f.readline()
    for line in f:
        try:
            t, bid, ask = line.strip().split(",")
            dt = datetime.strptime(t, "%Y.%m.%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
            key = dt.strftime("%H:%M")
            mid = (float(bid)+float(ask))/2
            bar_ticks[key] += 1
            if key not in bar_o: bar_o[key] = mid
            bar_c[key] = mid
        except Exception:
            continue
for k in bar_o:
    bar_color[k] = 'R' if bar_c[k] < bar_o[k] else ('G' if bar_c[k] > bar_o[k] else '-')

# Read EA log fires
log = sorted((TERMINAL / "MQL5/Logs").glob("20260619*.log"))[-1]
with open(log, "rb") as f:
    content = f.read().decode("utf-16le", errors="ignore")

trigger_re = re.compile(
    r"(\d{2}:\d{2}:\d{2})\.(\d+)\s+S1Trader[^\n]*S1 (BUY|SELL) LIVE TRIGGER[^\n]*"
    r"uhv_shift=(\d+)\s+\(vol=(\d+)\)"
)
fill_re = re.compile(r"(\d{2}:\d{2}:\d{2})\.(\d+)\s+S1Trader[^\n]*\[FILLED\]")
fills = list(fill_re.finditer(content))
triggers = list(trigger_re.finditer(content))
events = []
for f in fills:
    last_tr = None
    for tr in triggers:
        if tr.start() < f.start(): last_tr = tr
        else: break
    if not last_tr: continue
    h, m, _ = map(int, last_tr.group(1).split(":"))
    events.append({
        "broker_t": last_tr.group(1),
        "side": last_tr.group(3),
        "uhv_shift": int(last_tr.group(4)),
        "uhv_vol_ea": int(last_tr.group(5)),
        "entry_h": h, "entry_m": m,
    })

sorted_mins = sorted(bar_ticks.keys())
print(f"=== PROPER-SCOPE diagnostic: EA's UHV vs max-vol in retracement window ===")
print(f"{'utc_t':>5s}  {'side':>4s}  {'shift':>5s}  {'ea_vol':>6s}  "
      f"{'csv_vol':>7s}  {'retr_max_t':>10s}  {'retr_max_v':>10s}  {'retr_max_color':>14s}  ok?")

ok_count = 0
total = 0
for e in events:
    # broker → utc minute key (broker = UTC+2)
    entry_total_m = e["entry_h"] * 60 + e["entry_m"]
    uhv_total_m   = entry_total_m - e["uhv_shift"]
    uhv_utc_h = (uhv_total_m // 60 - 2) % 24
    uhv_utc_t = f"{uhv_utc_h:02d}:{uhv_total_m % 60:02d}"
    if uhv_utc_t not in bar_ticks: continue

    # Retracement-scope: 10 bars BEFORE the UHV (inclusive) — typical retracement length
    # The EA scans up to InpRetraceLookback bars back from current. That includes UHV.
    # The proper "is UHV the max within reds[] (retracement)" check requires looking
    # at bars from uhv to (uhv + N) back, considering only RED bars (for BUY) / GREEN (for SELL).
    expected_color = 'R' if e["side"] == "BUY" else 'G'
    scope_bars = []
    if uhv_utc_t in sorted_mins:
        u_idx = sorted_mins.index(uhv_utc_t)
        # Look at bars from UHV going BACKWARD to retracement origin
        for back in range(0, 11):
            idx2 = u_idx - back
            if idx2 < 0: break
            mt = sorted_mins[idx2]
            if bar_color.get(mt) == expected_color:
                scope_bars.append((mt, bar_ticks[mt], bar_color[mt]))

    if not scope_bars:
        continue

    # Find max-vol bar in scope (matching expected color)
    max_bar = max(scope_bars, key=lambda x: x[1])
    is_match = (max_bar[0] == uhv_utc_t)
    csv_vol_at_uhv = bar_ticks[uhv_utc_t]
    if is_match: ok_count += 1
    total += 1
    print(f"  {uhv_utc_t}  {e['side']:>4s}  {e['uhv_shift']:>5d}  {e['uhv_vol_ea']:>6d}  "
          f"{csv_vol_at_uhv:>7d}  {max_bar[0]:>10s}  {max_bar[1]:>10d}  {max_bar[2]:>14s}  {'✓' if is_match else '✗'}")

print()
print(f"=== VERDICT (proper scope, color-matched): {ok_count}/{total} EA picks ARE the max ===")
if total > 0:
    rate = 100 * ok_count / total
    if rate >= 80:
        print(f"  EA's UHV picker is mostly CORRECT ({rate:.0f}% match)")
        print(f"  My earlier 'broken picker' claim was a flawed diagnostic.")
    else:
        print(f"  EA still misses local max {100-rate:.0f}% of the time within proper scope.")
