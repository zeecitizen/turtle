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
# how many of the newest minutes in a pull may still be updated; older ones are
# settled and immutable (see write_vol's note on upstream volume restatements)
SETTLE_AFTER = 3


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
    """Sorted ascending, ASCII, no header — LoadOandaVol() binary-searches this.

    MERGES with what is already on disk (2026-08-21). Overwriting with the newest
    5,000 minutes silently DESTROYED history: a merged Aug-17 table was wiped by the
    next cycle, and the Diamond test then ran on a day with 0% OANDA coverage in one
    arm and 89.9% in another — mixing feeds inside one comparison, which makes the
    'quieter breakout' test trivially true (OANDA ~1,500/min vs broker ~450/min).
    History is the asset here: every minute kept is a minute the court can use.

    SETTLED MINUTES ARE IMMUTABLE (2026-08-23). Measured: one bridge cycle revised
    38 already-settled minutes, some DAYS old — 2026.08.18 17:06 went 1841 -> 1810,
    19:41 went 536 -> 477. OANDA restates its own tick counts on re-pull. Volume is
    what the UHV law ranks on, so a restatement can crown a different loudest candle
    and change a backtest's answer: Aug 18 gave 1 trade in one run and 0 in the next,
    and a seven-day total drifted +258.80 -> +224.10 with the same binary and set.
    So only the newest few minutes may be updated (they may still have been forming
    when we first saw them); everything older keeps the FIRST value we ever recorded.
    A court cannot compare arms across a chart that rewrites itself."""
    if not rows:
        return 0
    keep = {}
    try:
        for ln in VOL_OUT.read_text(encoding="ascii", errors="ignore").splitlines():
            p = ln.split(",")
            if len(p) == 2:
                keep[p[0]] = p[1]
    except FileNotFoundError:
        pass
    mutable = {f"{t:%Y.%m.%d %H:%M}" for t, _ in rows[-SETTLE_AFTER:]}
    revised = 0
    for t, v in rows:
        k = f"{t:%Y.%m.%d %H:%M}"
        if k in keep and k not in mutable:
            if keep[k] != str(v):
                revised += 1
            continue                        # settled: the first value we saw stands
        keep[k] = str(v)
    if revised:
        print(f"[VOL-TV] ignored {revised} upstream revisions to settled minutes",
              flush=True)
    tmp = VOL_OUT.with_suffix(".tmp")
    tmp.write_text("".join(f"{k},{keep[k]}\n" for k in sorted(keep)), encoding="ascii")
    _swap(tmp, VOL_OUT)                     # atomic; readers never see a half file
    return len(keep)


def _swap(tmp, dst, tries=6):
    """Atomic swap that tolerates a reader holding the file (MT5 opens it every M1
    bar). Windows raises PermissionError if the target is locked at that instant;
    retrying beats losing the cycle."""
    import time as _t
    for i in range(tries):
        try:
            tmp.replace(dst)
            return True
        except PermissionError:
            _t.sleep(0.12)
    return False

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
