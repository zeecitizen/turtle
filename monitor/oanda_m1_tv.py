"""oanda_m1_tv.py — the CANDLES from TradingView, not the broker.

Zee 2026-08-21: "can we ensure that the candles and volume are taken from
tradingview, not broker.. as we're making all decisions on tradingview, only using
broker blueberry to place trades (click buy / sell button)."

Volume already came from OANDA (oanda_vol.csv, written by oanda_vol_tv.py). The
CANDLES did not: oanda_m1.csv was produced by the CDP bridge, which died with the
Aug-14 MSIX break, so it sat 22 h stale and every reader — trend_eyes, the anatomy
panel, the humps chart, the line diagram — silently fell back to the terminal's
BROKER bars. The eye and the hand were the same feed again without anyone saying so.

This writes oanda_m1.csv from the same websocket that feeds oanda_vol.csv, so ONE
source (TradingView/OANDA) drives every decision surface. Blueberry keeps its only
job: filling the orders.

File shape is the legacy one every reader already understands:
    time_unix,open,high,low,close,volume      (time_unix = TRUE UTC epoch)
TradingView hands OANDA bars in UTC+5; UTC = tv_time - 5 h.
"""
from __future__ import annotations
import calendar, sys, time
from datetime import timedelta
from pathlib import Path

COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
M1_F = COMMON / "oanda_m1.csv"
# the EA-facing table: SERVER-time keyed (what iTime() hands the EA), full OHLCV.
# 2026-08-21, Zee: "the chart candles, the volume everything is on OANDA, we finally
# goto blueberry just to press the buy button and obviously then it buys at the
# blueberry price" — so the EA may JUDGE on these bars while every order still
# fills, and every stop/target is measured, at Blueberry's own price.
BARS_F = COMMON / "oanda_bars.csv"
BROKER_UTC_OFFSET = timedelta(hours=3)      # Blueberry = UTC+3


def _local_to_utc(t):
    """tvDatafeed hands back NAIVE LOCAL time. Zainab established this in
    oanda_vol_tv.py and — the important part — reads the machine's utcoffset at
    RUNTIME so a DST change or a machine move cannot silently shift every key by an
    hour. This file hardcoded -5h/-2h (correct only on a UTC+5 box); same lesson,
    same cure."""
    from datetime import datetime as _dt
    off = _dt.now().astimezone().utcoffset() or timedelta(0)
    return t - off


def _local_to_server(t):
    return _local_to_utc(t) + BROKER_UTC_OFFSET
N_BARS = 5000
N_BARS_FAST = 150      # routine cycle: just enough to carry the newest minutes


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

def cycle(fast=False):
    """fast=True pulls only the newest minutes. 2026-08-24: the EA waits for the
    forming candle to appear before it will judge the one before it, so the pull's
    latency IS the EA's entry latency — it went 40 s late and entered 1:17 after the
    signal. History comes from the archive, not from re-pulling 5,000 bars every
    cycle."""
    from tvDatafeed import TvDatafeed, Interval
    tv = TvDatafeed()
    d = tv.get_hist(symbol="XAUUSD", exchange="OANDA",
                    interval=Interval.in_1_minute,
                    n_bars=(N_BARS_FAST if fast else N_BARS))
    if d is None or not len(d):
        print("[M1-TV] pull returned nothing", flush=True)
        return 0
    lines = ["time_unix,open,high,low,close,volume\n"]
    newest = None
    for ts, r in d.iterrows():
        utc = _local_to_utc(ts.to_pydatetime())
        newest = utc
        lines.append(f"{calendar.timegm(utc.timetuple())},{float(r['open'])},"
                     f"{float(r['high'])},{float(r['low'])},{float(r['close'])},"
                     f"{int(r['volume'])}\n")
    tmp = M1_F.with_suffix(".tmp")
    tmp.write_text("".join(lines), encoding="utf-8")
    _swap(tmp, M1_F)                       # atomic: readers never see a half file

    # the same bars, server-time keyed, for the EA.
    # MERGES with what is already on disk (2026-08-23) — the identical fix
    # oanda_vol.csv got on Aug 21, which this file never received. The pull is a
    # ROLLING ~5,000 minutes (~3.5 days), so overwriting silently expired his own
    # chart: Aug 17 was in the volume table but already gone from the bars table.
    # BasedOnLaws judges the WHOLE setup on these candles, so every dropped day is
    # a day his laws can never be tried on again. History is the asset.
    keep = {}
    try:
        for ln in BARS_F.read_text(encoding="ascii", errors="ignore").splitlines():
            p = ln.split(",", 1)
            if len(p) == 2:
                keep[p[0]] = p[1]
    except FileNotFoundError:
        pass
    # SETTLED MINUTES ARE IMMUTABLE — same rule as oanda_vol.csv. Prices were stable
    # in the measurement that found this (0 revisions) while volume was not (38 in one
    # cycle), but the volume field lives in this table too and a court cannot compare
    # arms across a chart that rewrites itself. Only the newest few minutes may move.
    # mutable BY THE CLOCK, not by position in the pull — over a closed weekend the
    # last row of the pull would otherwise stay editable forever (see oanda_vol_tv).
    from datetime import datetime as _dtc
    now_srv = _dtc.utcnow() + BROKER_UTC_OFFSET
    mutable = {f"{_local_to_server(ts.to_pydatetime()):%Y.%m.%d %H:%M}"
               for ts in d.index
               if (now_srv - _local_to_server(ts.to_pydatetime())).total_seconds() < 180}
    for ts, r in d.iterrows():
        k = f"{_local_to_server(ts.to_pydatetime()):%Y.%m.%d %H:%M}"
        if k in keep and k not in mutable:
            continue
        keep[k] = (f"{float(r['open'])},{float(r['high'])},"
                   f"{float(r['low'])},{float(r['close'])},{int(r['volume'])}")
    btmp = BARS_F.with_suffix(".tmp")
    btmp.write_text("".join(f"{k},{keep[k]}\n" for k in sorted(keep)), encoding="ascii")
    _swap(btmp, BARS_F)
    age = (time.time() - calendar.timegm(newest.timetuple())) / 60.0
    print(f"[M1-TV] {len(d)} bars -> oanda_m1.csv · newest {newest:%Y-%m-%d %H:%M} UTC "
          f"({age:.1f} min old)", flush=True)
    return len(d)


if __name__ == "__main__":
    import sys as _sys
    _fast = "--fast" in _sys.argv
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    cycle(fast=_fast)
