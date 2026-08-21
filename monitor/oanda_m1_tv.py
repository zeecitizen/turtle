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
TV_TO_SERVER = timedelta(hours=-2)
TV_TO_UTC = timedelta(hours=-5)
N_BARS = 2000


def cycle():
    from tvDatafeed import TvDatafeed, Interval
    tv = TvDatafeed()
    d = tv.get_hist(symbol="XAUUSD", exchange="OANDA",
                    interval=Interval.in_1_minute, n_bars=N_BARS)
    if d is None or not len(d):
        print("[M1-TV] pull returned nothing", flush=True)
        return 0
    lines = ["time_unix,open,high,low,close,volume\n"]
    newest = None
    for ts, r in d.iterrows():
        utc = ts.to_pydatetime() + TV_TO_UTC
        newest = utc
        lines.append(f"{calendar.timegm(utc.timetuple())},{float(r['open'])},"
                     f"{float(r['high'])},{float(r['low'])},{float(r['close'])},"
                     f"{int(r['volume'])}\n")
    tmp = M1_F.with_suffix(".tmp")
    tmp.write_text("".join(lines), encoding="utf-8")
    tmp.replace(M1_F)                       # atomic: readers never see a half file

    # the same bars, server-time keyed, for the EA
    blines = []
    for ts, r in d.iterrows():
        srv = ts.to_pydatetime() + TV_TO_SERVER
        blines.append(f"{srv:%Y.%m.%d %H:%M},{float(r['open'])},{float(r['high'])},"
                      f"{float(r['low'])},{float(r['close'])},{int(r['volume'])}\n")
    btmp = BARS_F.with_suffix(".tmp")
    btmp.write_text("".join(blines), encoding="ascii")
    btmp.replace(BARS_F)
    age = (time.time() - calendar.timegm(newest.timetuple())) / 60.0
    print(f"[M1-TV] {len(d)} bars -> oanda_m1.csv · newest {newest:%Y-%m-%d %H:%M} UTC "
          f"({age:.1f} min old)", flush=True)
    return len(d)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    cycle()
