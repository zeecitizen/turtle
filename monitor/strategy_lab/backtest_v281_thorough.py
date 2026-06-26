"""backtest_v281_thorough.py — Thorough v2.81 backtest on 25 days of tick data.

Simulates the EXACT v2.81 EA logic:
  - Entry: canonical UHV M1 (v2.79 gates: UhvBody>=0.50, BreakoutVol<=0.75, etc.)
  - SL: entry - 2.0pt (canonical wide)
  - TP: entry + 1.0pt (InpTPPoints=1.0)
  - Trail: arms when peak >= 1.0pt, exits on 0.5pt pullback from peak

ALSO tests 3 variants to understand the TP/Trail interaction:
  1. v2.81 as-shipped (TP=1.0)
  2. v2.81-trail-only (TP=10pt = no effective TP, trail does everything)
  3. v2.81-dynamic-TP (TP=2pt = SL-equivalent for 1:1 R:R)
"""
from __future__ import annotations
import sys, csv
from pathlib import Path
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab")
import screener_canonical_uhv_m1 as m1

m1.HARD_TREND = False
m1.UHV_BODY_MIN = 0.50
m1.BREAKOUT_VOL_MAX_RATIO = 0.75
m1.MOM_THRESH = 0.65
m1.MIN_BREAKOUT_PENETRATION = 0.30

CSV_DIR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
csvs = sorted(CSV_DIR.glob("shano_ticks_2026-*.csv"))
print(f"Loading {len(csvs)} tick CSVs spanning {csvs[0].name} to {csvs[-1].name}")

bars = m1.build_m1(csvs)
print(f"Built {len(bars):,} M1 bars")
fires = m1.detect(bars)
print(f"Detected {len(fires)} M1 fires across {len(csvs)} days")

ticks = []
for p in csvs:
    with p.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts = row.get("ts_broker") or row.get("ts") or row.get("t")
            if not ts: continue
            if "." in ts.split(" ", 1)[-1]: ts = ts.rsplit(".", 1)[0]
            try: dt = datetime.strptime(ts, "%Y.%m.%d %H:%M:%S")
            except ValueError: continue
            try:
                bid = float(row["bid"]); ask = float(row["ask"])
            except (KeyError, ValueError): continue
            ticks.append((dt, bid, ask))
ticks.sort()
print(f"Loaded {len(ticks):,} ticks")

LOTS = 0.30
USD_PER_PT = LOTS * 100   # 1pt at 0.30 lots = $30
SL_PT = 2.0               # canonical SL distance
TRAIL_LOCK_PT = 1.0       # v2.81 InpTrailLockPts
TRAIL_REV_PT = 0.5        # v2.81 InpTrailRevPts


def simulate(tp_pt: float, label: str) -> dict:
    """Simulate v2.81 exit logic with a given TP. Returns aggregate stats + per-trade list."""
    results = []
    for f in fires:
        open_dt = datetime.strptime(f.open_t, "%Y-%m-%d %H:%M")
        entry_idx = None
        for j, (t, b, a) in enumerate(ticks):
            if t > open_dt:
                entry_idx = j; break
        if entry_idx is None: continue
        entry_price = ticks[entry_idx][2] if f.side == "BUY" else ticks[entry_idx][1]
        # Walk forward up to 30 minutes (longer horizon for trail to play out)
        cap_until = ticks[entry_idx][0] + timedelta(seconds=1800)
        peak = 0.0
        trail_armed = False
        exit_price = None
        exit_reason = None
        exit_t = None
        for k in range(entry_idx, min(entry_idx + 5000, len(ticks))):
            t, b, a = ticks[k]
            if t > cap_until:
                exit_price = b if f.side == "BUY" else a
                exit_reason = "timeout"
                exit_t = t
                break
            cur_price = b if f.side == "BUY" else a
            delta = (cur_price - entry_price) if f.side == "BUY" else (entry_price - cur_price)
            # Update peak
            if delta > peak: peak = delta
            # Check broker TP
            if delta >= tp_pt:
                exit_price = entry_price + tp_pt if f.side == "BUY" else entry_price - tp_pt
                exit_reason = "TP"
                exit_t = t
                break
            # Check broker SL
            if delta <= -SL_PT:
                exit_price = entry_price - SL_PT if f.side == "BUY" else entry_price + SL_PT
                exit_reason = "SL"
                exit_t = t
                break
            # Check trail arm
            if peak >= TRAIL_LOCK_PT:
                trail_armed = True
            # Trail exit
            if trail_armed and (peak - delta) >= TRAIL_REV_PT:
                exit_price = cur_price
                exit_reason = "trail"
                exit_t = t
                break
        if exit_price is None:
            continue
        final_delta = (exit_price - entry_price) if f.side == "BUY" else (entry_price - exit_price)
        pnl_usd = final_delta * USD_PER_PT
        results.append({"side": f.side, "open_t": f.open_t, "entry": entry_price,
                         "exit": exit_price, "delta_pt": final_delta, "peak_pt": peak,
                         "pnl_usd": pnl_usd, "exit_reason": exit_reason})
    # Tally
    wins = [r for r in results if r["pnl_usd"] > 0]
    losses = [r for r in results if r["pnl_usd"] <= 0]
    total = sum(r["pnl_usd"] for r in results)
    by_reason = {}
    for r in results:
        by_reason.setdefault(r["exit_reason"], []).append(r["pnl_usd"])
    return dict(label=label, results=results, n=len(results), wins=len(wins),
                losses=len(losses), wr=100*len(wins)/len(results) if results else 0,
                net=total, ev=total/len(results) if results else 0,
                by_reason=by_reason)


# Run 3 scenarios
scenarios = [
    simulate(1.0, "v2.81 as-shipped (TP=1.0pt, trail-1.0/0.5)"),
    simulate(10.0, "v2.81 trail-only  (TP=10.0pt → trail does all)"),
    simulate(2.0, "v2.81 wider-TP     (TP=2.0pt, trail-1.0/0.5)"),
]

print(f"\n=== BACKTEST RESULTS — {len(fires)} fires across {len(csvs)} days at {LOTS} lots ===\n")
for s in scenarios:
    print(f"╔══ {s['label']} ═══")
    print(f"║ Trades:   {s['n']}")
    print(f"║ Wins:     {s['wins']}   Losses: {s['losses']}   WR: {s['wr']:.1f}%")
    print(f"║ NET P&L:  ${s['net']:+,.2f}")
    print(f"║ EV/trade: ${s['ev']:+.2f}")
    print(f"║ Exit reason breakdown:")
    for reason, pnls in sorted(s['by_reason'].items()):
        n = len(pnls); total = sum(pnls); avg = total/n if n else 0
        print(f"║   {reason:8s}  {n:3d} trades  total ${total:+8,.2f}  avg ${avg:+6.2f}")
    print(f"╚══════════════════════════════════════════════════")
    print()

# Project to 7-day window for direct comparison with v2.79 backtest (+$319/7d)
best = max(scenarios, key=lambda s: s["net"])
days = 25
per_day = best["net"] / days
print(f"╔══ HOSPITAL PROJECTION ═══")
print(f"║ Best scenario: {best['label']}")
print(f"║ Total backtest net:  ${best['net']:+,.2f}  over {days} active days")
print(f"║ Avg per day:         ${per_day:+,.2f}")
print(f"║ Per 7-day comparison: ${per_day*7:+,.2f}  (vs v2.79 baseline +$319)")
print(f"║ Days to $1080 target: {1080/per_day:.1f} days (if positive)")
print(f"╚══════════════════════════════════════════════════")

# Save full trade list for the best scenario
out = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/_canonical/v281_trade_list.csv")
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["side","open_t","entry","exit","delta_pt","peak_pt","pnl_usd","exit_reason"])
    w.writeheader()
    for r in best['results']: w.writerow(r)
print(f"\nFull trade list saved: {out}")
