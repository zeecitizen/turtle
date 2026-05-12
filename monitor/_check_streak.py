"""Show all XAUUSD deals from 12:50 UTC to now, grouped by strategy."""
import MetaTrader5 as mt5
from datetime import datetime, timezone

mt5.initialize(timeout=15000)
now = datetime.now(timezone.utc)
since = now.replace(hour=12, minute=50, second=0, microsecond=0)
deals = mt5.history_deals_get(since, now)
xau = sorted([d for d in (deals or []) if "XAUUSD" in (d.symbol or "")], key=lambda d: d.time_msc)
print(f"All XAUUSD deals 12:50 -> {now.strftime('%H:%M')} UTC: {len(xau)}")
print()
for d in xau:
    t = datetime.fromtimestamp(d.time_msc/1000, tz=timezone.utc).strftime("%H:%M:%S")
    et = "OPEN" if d.entry == 0 else "CLOSE"
    side = "BUY" if d.type == 0 else "SELL"
    print(f"  {t}  {et:>5}  pid={d.position_id}  {side} {d.volume:.2f}  px={d.price}  pnl=${d.profit:+.2f}  mg={d.magic}  comment={d.comment!r}")

# Also show open positions
pos = mt5.positions_get(symbol="XAUUSD") or []
print(f"\nCurrently open: {len(pos)}")
for p in pos:
    side = "BUY" if p.type == 0 else "SELL"
    t_open = datetime.fromtimestamp(p.time, tz=timezone.utc).strftime("%H:%M:%S")
    print(f"  ticket={p.ticket} opened={t_open} {side} {p.volume} @ {p.price_open} floating=${p.profit:+.2f} comment={p.comment!r} magic={p.magic}")
mt5.shutdown()
