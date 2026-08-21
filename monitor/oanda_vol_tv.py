"""oanda_vol_tv.py — oanda_vol.csv straight from TradingView's websocket.

Zee 2026-08-20: "cant you just take the volume from tradingview like you were
taking it from blueberry" — exactly right. Blueberry's volume arrives through a
client that holds its own connection (MT5). This is the same thing for TradingView:
tvDatafeed speaks its websocket directly, so there is NO browser in the chain.

Replaces oanda_vol_from_m1.py, which had to keep a Chrome tab alive and issue a
Page.reload every 45s because TradingView's rendered chart loads its bars once and
never streams (measured: it sat 3h24m stale while the bridge faithfully re-exported
the same 306 rows). That whole dependency is gone here — no Chrome, no CDP, no
reload, nothing to keep visible, nothing to close by accident.

Writes ONLY Common\\Files\\oanda_vol.csv. It does not touch oanda_m1.csv: that file
belongs to oanda_bridge.py and feeds the cockpit, and it stays that way.

TIMEBASE — the part that fails silently if it is wrong.
tvDatafeed returns NAIVE LOCAL time (verified: its 16:09 bar is the same candle as
Blueberry's 02:09 server bar on a UTC-7 machine). The EA's lookup is an exact-match
binary search against iTime(), which is BROKER SERVER time, so:

    server = tv_naive_local  ->  UTC (subtract the machine's utcoffset)  ->  +3h

Established by close-price alignment over 396 bars: +10h gave mean |diff| 0.1032
while every other shift landed between 5.17 and 10.81. The local part is computed
at runtime, NOT hardcoded, so DST or a machine move cannot quietly shift every key
by an hour and send ZeeUHV back to broker volume without anyone noticing.

Usage:
    python monitor/oanda_vol_tv.py             # one cycle
    python monitor/oanda_vol_tv.py --loop 30   # keep the EA's table fresh
"""
from __future__ import annotations
import argparse
import logging
import os
import sys
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

BROKER_UTC_OFFSET = timedelta(hours=3)      # Blueberry = UTC+3 (verified by alignment)

_COMMON = Path(os.environ.get("APPDATA", r"C:/Users/zeesh/AppData/Roaming")) / \
          "MetaQuotes" / "Terminal" / "Common" / "Files"
VOL_OUT = _COMMON / "oanda_vol.csv"


def _local_to_server(t: datetime) -> datetime:
    """tvDatafeed's naive local timestamp -> broker server time.

    utcoffset() is read per call so a DST change is picked up on the next cycle
    instead of silently offsetting every key by an hour.
    """
    off = datetime.now().astimezone().utcoffset() or timedelta(0)
    return t - off + BROKER_UTC_OFFSET


def pull(n_bars=5000):
    from tvDatafeed import TvDatafeed, Interval
    tv = TvDatafeed()
    d = tv.get_hist(symbol="XAUUSD", exchange="OANDA",
                    interval=Interval.in_1_minute, n_bars=n_bars)
    if d is None or not len(d):
        return []
    rows = {}
    for ts, r in d.iterrows():
        rows[_local_to_server(ts.to_pydatetime())] = int(r["volume"])
    return [(t, rows[t]) for t in sorted(rows)]


def write_vol(rows):
    """Sorted ascending, ASCII, no header — LoadOandaVol() binary-searches this."""
    if not rows:
        return 0
    VOL_OUT.write_text("".join(f"{t:%Y.%m.%d %H:%M},{v}\n" for t, v in rows),
                       encoding="ascii")
    return len(rows)


def cycle():
    rows = pull()
    n = write_vol(rows)
    if n:
        newest, vol = rows[-1]
        server_now = datetime.utcnow() + BROKER_UTC_OFFSET
        age = (server_now - newest).total_seconds() / 60
        print(f"[VOL-TV] {n} minutes -> oanda_vol.csv · newest server "
              f"{newest:%Y.%m.%d %H:%M} (vol {vol}, {age:.1f} min old)", flush=True)
    else:
        print("[VOL-TV] pull returned nothing", flush=True)
    return n


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="seconds between cycles")
    a = ap.parse_args()
    while True:
        try:
            cycle()
        except Exception as e:
            print(f"[VOL-TV] error: {e}", flush=True)
        if not a.loop:
            break
        time.sleep(a.loop)
