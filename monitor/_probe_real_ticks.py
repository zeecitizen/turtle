"""Verify Blueberry serves historical real ticks for Strategy Tester."""
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
import sys, io

OUT = open(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\_real_ticks_probe.txt", "w", encoding="utf-8")
def p(*args):
    line = " ".join(str(a) for a in args)
    OUT.write(line + "\n"); OUT.flush()
    print(line, flush=True)

if not mt5.initialize(timeout=15000):
    p(f"[FAIL] mt5.initialize() failed: {mt5.last_error()}")
    sys.exit(1)

info = mt5.terminal_info()
acct = mt5.account_info()
p(f"Terminal: {info.company} / build {info.build}")
p(f"Account:  {acct.login} ({acct.company}, {acct.server})")
p(f"Path:     {info.data_path}")
p()

sym = "XAUUSD"
si = mt5.symbol_info(sym)
if si is None:
    p(f"[FAIL] symbol {sym} not found")
    mt5.shutdown(); sys.exit(1)

p(f"Symbol info — {sym}:")
p(f"  digits={si.digits}, point={si.point}, spread={si.spread}")
p(f"  trade_tick_value={si.trade_tick_value}, trade_contract_size={si.trade_contract_size}")
p()

now = datetime.now(timezone.utc)
p(f"Probing real-tick history for {sym} (now={now.strftime('%Y-%m-%d %H:%M UTC')}):")
p()

windows = [(1,"1d"),(3,"3d"),(7,"7d"),(14,"14d"),(30,"30d"),(60,"60d"),(90,"90d"),(180,"180d"),(365,"365d")]
for days, label in windows:
    frm = now - timedelta(days=days)
    to  = now - timedelta(days=days-1) if days > 0 else now
    ticks = mt5.copy_ticks_range(sym, frm, to, mt5.COPY_TICKS_ALL)
    if ticks is None or len(ticks) == 0:
        p(f"  T-{label:>4} ({frm.strftime('%Y-%m-%d')} -> {to.strftime('%Y-%m-%d')}): 0 ticks")
    else:
        first = datetime.fromtimestamp(ticks[0]['time'], tz=timezone.utc)
        last  = datetime.fromtimestamp(ticks[-1]['time'], tz=timezone.utc)
        bid_first = ticks[0]['bid']; ask_first = ticks[0]['ask']
        spread_pts = (ask_first - bid_first) / si.point
        p(f"  T-{label:>4} ({frm.strftime('%Y-%m-%d %H:%M')}): {len(ticks):>8} ticks | first {first.strftime('%H:%M:%S')} bid={bid_first} ask={ask_first} sprd={spread_pts:.0f}pts")

p()
p("Probing total tick range (full history available locally):")
year_ago = now - timedelta(days=365)
total = mt5.copy_ticks_range(sym, year_ago, now, mt5.COPY_TICKS_ALL)
if total is not None and len(total):
    first = datetime.fromtimestamp(total[0]['time'], tz=timezone.utc)
    last  = datetime.fromtimestamp(total[-1]['time'], tz=timezone.utc)
    span_days = (last - first).days
    p(f"  TOTAL: {len(total):,} ticks | {first.strftime('%Y-%m-%d')} -> {last.strftime('%Y-%m-%d')} ({span_days} days)")
    bidask_diffs = (total['ask'] - total['bid']) / si.point
    import statistics
    p(f"  Spread (pts): min={bidask_diffs.min():.0f} median={statistics.median(bidask_diffs):.0f} max={bidask_diffs.max():.0f}")
else:
    p("  No ticks found in last 365 days")

mt5.shutdown()
