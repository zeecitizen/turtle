"""oanda_volume_bridge.py — TradingView's OANDA volume, straight into the machine.

Zee 2026-08-20: "can you try getting volume from tradingview.. we want to use
concretely the volume from OANDA inside Tradingview" — because his eye, his 146
labels and his Feb-11 all read OANDA volume, while the EA reads Blueberry's
tick-count. MEASURED DISAGREEMENT: the two feeds crown a DIFFERENT loudest candle
in 46.4% of rolling 8-bar windows. That is not cosmetic — it is the heart of the
strategy.

What this does, every cycle:
  1. pulls OANDA:XAUUSD M1 from TradingView's websocket (tvDatafeed, no CDP — this
     also HEALS the oanda_m1.csv feed that died on Aug 14 when TV went MSIX),
  2. writes Common/Files/oanda_vol.csv  — server_time,volume  (the EA's lookup),
  3. rewrites Common/Files/oanda_m1.csv — the legacy feed shape (time_unix,ohlcv),
  4. appends to monitor/oanda_vol_archive.csv — the growing history, so future
     courts can one day replay OANDA volume over months instead of 4 days.

TIMEBASE (verified by close-price alignment, mean |diff| 0.13): TradingView returns
OANDA bars in UTC+5; MT5 server is UTC+3. server_time = tv_time - 2h. The CSV is
keyed in SERVER time because that is what iTime() hands the EA.
"""
from __future__ import annotations
import sys, time
from datetime import timedelta
from pathlib import Path

COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
VOL_F = COMMON / "oanda_vol.csv"
M1_F = COMMON / "oanda_m1.csv"
ARCHIVE = Path(__file__).parent / "oanda_vol_archive.csv"
TV_TO_SERVER = timedelta(hours=-2)


def pull(n_bars=5000):
    from tvDatafeed import TvDatafeed, Interval
    tv = TvDatafeed()
    d = tv.get_hist(symbol="XAUUSD", exchange="OANDA",
                    interval=Interval.in_1_minute, n_bars=n_bars)
    if d is None or not len(d):
        return []
    out = []
    for ts, r in d.iterrows():
        srv = ts.to_pydatetime() + TV_TO_SERVER
        out.append((srv, float(r["open"]), float(r["high"]), float(r["low"]),
                    float(r["close"]), float(r["volume"])))
    return out


def write_all(rows):
    if not rows:
        return 0
    # 1. the EA's lookup table — server time, volume
    VOL_F.write_text(
        "".join(f"{t:%Y.%m.%d %H:%M},{int(v)}\n" for t, o, h, l, c, v in rows),
        encoding="ascii")
    # 2. the legacy feed shape (trend_eyes / matcher / humps read this)
    import calendar
    lines = ["time_unix,open,high,low,close,volume\n"]
    for t, o, h, l, c, v in rows:
        # legacy file stores TRUE UTC epoch (server = UTC+3)
        utc = t - timedelta(hours=3)
        lines.append(f"{calendar.timegm(utc.timetuple())},{o},{h},{l},{c},{int(v)}\n")
    M1_F.write_text("".join(lines), encoding="utf-8")
    # 3. the growing archive (dedup by server minute)
    seen = set()
    if ARCHIVE.exists():
        for ln in ARCHIVE.read_text(encoding="ascii", errors="ignore").splitlines():
            seen.add(ln.split(",")[0])
    add = [f"{t:%Y.%m.%d %H:%M},{int(v)}\n" for t, o, h, l, c, v in rows
           if f"{t:%Y.%m.%d %H:%M}" not in seen]
    if add:
        with ARCHIVE.open("a", encoding="ascii") as f:
            f.writelines(add)
    return len(rows)


def cycle():
    rows = pull()
    n = write_all(rows)
    if n:
        newest = rows[-1][0]
        print(f"[OANDA-VOL] {n} bars · newest server {newest:%Y-%m-%d %H:%M} "
              f"· vol {int(rows[-1][5])} -> oanda_vol.csv + oanda_m1.csv", flush=True)
    else:
        print("[OANDA-VOL] pull returned nothing", flush=True)
    return n


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    loop = "--loop" in sys.argv
    while True:
        try:
            cycle()
        except Exception as e:
            print(f"[OANDA-VOL] error: {e}", flush=True)
        if not loop:
            break
        time.sleep(60)
