"""oanda_tables_backfill.py — rebuild the EA-facing OANDA tables from the PERMANENT
history archive (2026-08-23).

oanda_m1.csv is a rolling ~5,000-minute window: his own chart expires after ~3.5
days. oanda_archiver.py keeps every finished bar in strategy_lab/oanda_m1_history.csv;
this pours that archive into the two files the EA actually reads, merging (never
overwriting) with what is already there:

    Common\\Files\\oanda_vol.csv    server-time,volume
    Common\\Files\\oanda_bars.csv   server-time,open,high,low,close,volume

Blueberry server = UTC+3 (established by close-price alignment over 233 bars).

    py monitor/oanda_tables_backfill.py
"""
import csv
import datetime as dt
import pathlib
import sys

COMMON = pathlib.Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
HIST = pathlib.Path(__file__).parent / "strategy_lab" / "oanda_m1_history.csv"
LIVE = COMMON / "oanda_m1.csv"
VOL_F = COMMON / "oanda_vol.csv"
BARS_F = COMMON / "oanda_bars.csv"
OFFSET = dt.timedelta(hours=3)


def _load_existing(path, nfields):
    keep = {}
    try:
        for ln in path.read_text(encoding="ascii", errors="ignore").splitlines():
            p = ln.split(",", 1)
            if len(p) == 2 and len(p[1].split(",")) == nfields:
                keep[p[0]] = p[1]
    except FileNotFoundError:
        pass
    return keep


def main():
    vol = _load_existing(VOL_F, 1)
    bars = _load_existing(BARS_F, 5)
    before = (len(vol), len(bars))

    seen = set()
    for src in (HIST, LIVE):
        if not src.exists():
            continue
        for r in csv.DictReader(src.open(encoding="utf-8", errors="replace")):
            u = r.get("time_unix")
            if not u or u in seen:
                continue
            seen.add(u)
            srv = dt.datetime.fromtimestamp(int(u), dt.UTC).replace(tzinfo=None) + OFFSET
            key = f"{srv:%Y.%m.%d %H:%M}"
            # keep-first: OANDA restates settled volume on re-pull, so whatever the
            # tables already hold for a minute is the value every past court used.
            if key not in vol:
                vol[key] = str(int(float(r["volume"])))
            if key not in bars:
                bars[key] = (f"{float(r['open'])},{float(r['high'])},"
                             f"{float(r['low'])},{float(r['close'])},"
                             f"{int(float(r['volume']))}")

    VOL_F.write_text("".join(f"{k},{vol[k]}\n" for k in sorted(vol)), encoding="ascii")
    BARS_F.write_text("".join(f"{k},{bars[k]}\n" for k in sorted(bars)), encoding="ascii")
    print(f"  oanda_vol.csv   {before[0]:>6} -> {len(vol):>6} rows")
    print(f"  oanda_bars.csv  {before[1]:>6} -> {len(bars):>6} rows")
    days = sorted({k[:10] for k in bars})
    print("  candle days:", ", ".join(days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
