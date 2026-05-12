"""Diagnose why all 19:10+ trades are SELL with mixed P&L pattern."""
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta

mt5.initialize(timeout=15000)

# Use MT5 server time as anchor
tick = mt5.symbol_info_tick("XAUUSD")
mt5_now = datetime.fromtimestamp(tick.time, tz=timezone.utc)
print(f"MT5 server time: {mt5_now}")
print(f"Current bid: {tick.bid}, ask: {tick.ask}")

# Today's deals
today_start = datetime(mt5_now.year, mt5_now.month, mt5_now.day, tzinfo=timezone.utc)
deals = mt5.history_deals_get(today_start, mt5_now + timedelta(hours=2))
xau = sorted([d for d in (deals or []) if "XAUUSD" in (d.symbol or "")], key=lambda d: d.time_msc)
print(f"\nToday total XAUUSD deals: {len(xau)}")

# Pair opens with closes
pairs = {}
for d in xau:
    if d.position_id == 0: continue
    if d.position_id not in pairs: pairs[d.position_id] = {}
    if d.entry == 0: pairs[d.position_id]["open"] = d
    elif d.entry == 1: pairs[d.position_id]["close"] = d

print(f"\n=== Position pairs from 19:00 onwards ===")
print(f"{'pid':>10} {'open_t':>8} {'close_t':>8} {'side':>4} {'open_px':>8} {'close_px':>8} {'price_move':>10} {'pnl':>8} {'open_cmt':>22} {'close_cmt':>30}")
for pid, p in sorted(pairs.items(), key=lambda x: x[1].get("open", x[1].get("close")).time_msc):
    if "open" not in p or "close" not in p: continue
    o = p["open"]; c = p["close"]
    if o.time_msc < (today_start + timedelta(hours=19)).timestamp() * 1000: continue
    o_t = datetime.fromtimestamp(o.time_msc/1000, tz=timezone.utc).strftime("%H:%M:%S")
    c_t = datetime.fromtimestamp(c.time_msc/1000, tz=timezone.utc).strftime("%H:%M:%S")
    side = "BUY" if o.type == 0 else "SELL"
    move = c.price - o.price  # actual price movement
    open_cmt = (o.comment or "")[:22]
    close_cmt = (c.comment or "")[:30]
    print(f"  {pid:>10} {o_t:>8} {c_t:>8} {side:>4} {o.price:>8.2f} {c.price:>8.2f} {move:>+10.2f} ${c.profit:>+7.2f} {open_cmt:>22} {close_cmt:>30}")

# Check today's price extremes (Asian range)
asian_start = today_start
asian_end = today_start + timedelta(hours=7)
ticks = mt5.copy_ticks_range("XAUUSD", asian_start, asian_end, mt5.COPY_TICKS_ALL)
if ticks is not None and len(ticks) > 0:
    a_high = float(ticks["bid"].max())
    a_low = float(ticks["bid"].min())
    print(f"\nAsian range (00:00-07:00 UTC): high={a_high} low={a_low} width={(a_high-a_low)*100:.0f}pts")

# Check london session price action
london_start = today_start + timedelta(hours=7)
london_ticks = mt5.copy_ticks_range("XAUUSD", london_start, mt5_now + timedelta(hours=1), mt5.COPY_TICKS_ALL)
if london_ticks is not None and len(london_ticks) > 0:
    l_high = float(london_ticks["bid"].max())
    l_low = float(london_ticks["bid"].min())
    print(f"London session (07:00-now): high={l_high} low={l_low}")
    # Find first above and below Asian range
    import numpy as np
    bids = london_ticks["bid"]
    above = bids > a_high
    below = bids < a_low
    if above.any():
        first_above_idx = int(np.argmax(above))
        first_above_time = datetime.fromtimestamp(london_ticks[first_above_idx]["time_msc"]/1000, tz=timezone.utc).strftime("%H:%M:%S")
        print(f"First UPSIDE break (>{a_high}): {first_above_time} at idx {first_above_idx}")
    else:
        print(f"NO upside break of {a_high}")
    if below.any():
        first_below_idx = int(np.argmax(below))
        first_below_time = datetime.fromtimestamp(london_ticks[first_below_idx]["time_msc"]/1000, tz=timezone.utc).strftime("%H:%M:%S")
        print(f"First DOWNSIDE break (<{a_low}): {first_below_time} at idx {first_below_idx}")
    else:
        print(f"NO downside break of {a_low}")

mt5.shutdown()
