"""Pull today's live MT5 deals and compare to backtest predictions."""
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
import json, sys
from pathlib import Path

if not mt5.initialize(timeout=15000):
    print(f"[FAIL] mt5.initialize: {mt5.last_error()}"); sys.exit(1)

now = datetime.now(timezone.utc)
today_start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc)

# Pull all deals from today
deals = mt5.history_deals_get(today_start, now)
if deals is None:
    print(f"[FAIL] history_deals_get: {mt5.last_error()}"); mt5.shutdown(); sys.exit(1)

print(f"=== LIVE MT5 DEALS — today UTC ({today_start.strftime('%Y-%m-%d')}) ===")
print(f"total deals: {len(deals)}")

# Filter to XAUUSD entries (deal type 0=BUY, 1=SELL, entry=0=open, 1=close)
xau = [d for d in deals if "XAUUSD" in (d.symbol or "")]
print(f"XAUUSD deals: {len(xau)}\n")

opens = [d for d in xau if d.entry == 0]   # opening
closes = [d for d in xau if d.entry == 1]  # closing

# Group by lot size
probes_open = [d for d in opens if abs(d.volume - 0.01) < 0.005]
mains_open  = [d for d in opens if abs(d.volume - 0.01) >= 0.005]

print(f"=== OPENS ===")
print(f"  Probes (0.01):  {len(probes_open)}")
print(f"  Mains  (>=0.02): {len(mains_open)}")
print()
print(f"=== ALL OPENS (chronological) ===")
for d in sorted(opens, key=lambda x: x.time_msc):
    t = datetime.fromtimestamp(d.time_msc / 1000, tz=timezone.utc)
    side = "BUY" if d.type == 0 else "SELL"
    print(f"  {t.strftime('%H:%M:%S')} | {side:>4} {d.volume:>5.2f} @ {d.price:>8.2f} | ticket={d.ticket} | comment='{d.comment}'")

print()
print(f"=== ALL CLOSES (chronological) ===")
for d in sorted(closes, key=lambda x: x.time_msc):
    t = datetime.fromtimestamp(d.time_msc / 1000, tz=timezone.utc)
    side = "BUY" if d.type == 0 else "SELL"
    print(f"  {t.strftime('%H:%M:%S')} | {side:>4} {d.volume:>5.2f} @ {d.price:>8.2f} | P&L=${d.profit:>+7.2f} | comment='{d.comment}'")

# Also pull current open positions
positions = mt5.positions_get(symbol="XAUUSD")
print(f"\n=== STILL OPEN ({len(positions or [])} positions) ===")
for p in positions or []:
    t = datetime.fromtimestamp(p.time / 1000 if p.time > 1e10 else p.time, tz=timezone.utc) if p.time > 0 else None
    side = "BUY" if p.type == 0 else "SELL"
    print(f"  ticket={p.ticket} {side} {p.volume:.2f} @ {p.price_open:.2f} | floating ${p.profit:+.2f} | comment='{p.comment}'")

# Compare to backtest
print(f"\n=== BACKTEST PREDICTIONS for today ===")
bt = json.loads(Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_shanozee_live_3day.json").read_text())
today_str = today_start.strftime("%Y-%m-%d")
day = bt.get("by_day", {}).get(today_str, {})
print(f"  trades predicted: {day.get('n', 0)}")
print(f"  net: ${day.get('net', 0)}")
print(f"  WR: {day.get('wr', 0)}%")

# Per-trade detail from CSV
import csv
csv_p = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_shanozee_live_3day_trades.csv")
if csv_p.exists():
    print(f"\n=== BACKTEST trades for today ===")
    with open(csv_p) as f:
        for row in csv.DictReader(f):
            if row.get("date") == today_str:
                print(f"  {row.get('ts')} | {row.get('side')} | outcome={row.get('outcome')} | exit={row.get('exit_reason','-')} | total=${row.get('total_pnl')}")

# Summary
print(f"\n=== COMPARISON ===")
print(f"  Live probes opened:    {len(probes_open)}")
print(f"  Live mains opened:     {len(mains_open)}")
print(f"  Backtest mains:        {day.get('n', 0)} (we don't track probe-only in stats)")
print(f"  Match? {'YES' if len(mains_open) == day.get('n', 0) else 'NO — backtest is wrong or filter mismatch'}")

mt5.shutdown()
