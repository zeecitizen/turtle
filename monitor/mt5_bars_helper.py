"""mt5_bars_helper.py — print XAUUSD M1 bars from the RUNNING terminal as CSV.

Usage:  python mt5_bars_helper.py <lo_iso_utc> <hi_iso_utc> <broker_utc_offset_h>
Output: one "unix_utc,open,high,low,close,volume" line per bar, times in TRUE UTC.

Exists because forensic_chart.py runs under the GUI's ARM64 interpreter, where the
MetaTrader5 wheel does not exist — so the terminal query happens in this x64
subprocess instead (2026-08-17). The terminal always holds full M1 history for its
own symbol, which makes it the bar source of last resort when the OANDA rolling
window has moved on and the tape archive's writer is down.
"""
import sys
from datetime import datetime, timedelta, timezone

lo = datetime.fromisoformat(sys.argv[1])
hi = datetime.fromisoformat(sys.argv[2])
off = timedelta(hours=int(sys.argv[3]))          # broker clock = UTC + off

import MetaTrader5 as mt5

if not mt5.initialize():
    sys.exit(1)
try:
    # the module speaks server-time-rendered-as-UTC in both directions
    rates = mt5.copy_rates_range("XAUUSD", mt5.TIMEFRAME_M1,
                                 (lo + off).replace(tzinfo=timezone.utc),
                                 (hi + off).replace(tzinfo=timezone.utc))
    for r in (rates if rates is not None else []):
        t_utc = int(r["time"]) - int(off.total_seconds())
        vol = int(r["real_volume"]) or int(r["tick_volume"])
        print(f"{t_utc},{r['open']},{r['high']},{r['low']},{r['close']},{vol}")
finally:
    mt5.shutdown()
