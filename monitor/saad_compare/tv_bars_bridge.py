"""tv_bars_bridge.py - the TradingView chart's closed 1-min candles -> MT5 Common\\Files\\tv_bars_XAUUSD.csv

Zee 2026-10-16: "the only way we can succeed is to sync both mt5 with tradingview. so find a way. i can't miss out on
entries i've spent entire day tuning on tradingview"

Saad_strategy_1min v1.04 with InpBarSource=1 reads this file instead of its own MT5 candles, so it sees the very
candles the indicator sees (same setups, same entry band, same lock / trail candles). Orders still fill on MT5.

    py tv_bars_bridge.py --export      # all the history the chart can load (for the Strategy Tester / compare page)
    py tv_bars_bridge.py --live        # keep appending each closed candle (run beside the EA on a live chart)

Times are written in broker server time = UTC+3 while New York is on summer time, UTC+2 otherwise
(Blueberry and Axi: the day closes at 5 pm New York). The chart must be on the 1-minute timeframe.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import server  # noqa: E402  (tv_eval: the TradingView CDP bridge)

COMMON = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "Common" / "Files"
CHART = "window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model().mainSeries()"
JS_BARS = """(() => { const b = %s.bars(); const out = [];
 for (let i = Math.max(b.firstIndex(), b.lastIndex() - %d); i <= b.lastIndex(); i++) { const v = b.valueAt(i); if (v) out.push([v[0], v[1], v[2], v[3], v[4]]); }
 const c = window.TradingViewApi.activeChart(); return JSON.stringify({sym: c.symbol(), res: c.resolution(), bars: out}); })()"""


def _nth_sunday(y, m, n):
    d = datetime(y, m, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def server_time(epoch):
    """UTC epoch -> broker server time (New York close = 00:00): UTC+3 in US summer time, else UTC+2."""
    u = datetime.fromtimestamp(epoch, timezone.utc).replace(tzinfo=None)
    start = _nth_sunday(u.year, 3, 2) + timedelta(hours=7)    # 2 am EST = 07:00 UTC
    end = _nth_sunday(u.year, 11, 1) + timedelta(hours=6)     # 2 am EDT = 06:00 UTC
    return u + timedelta(hours=3 if start <= u < end else 2)


def line(b):
    return f"{server_time(b[0]):%Y.%m.%d %H:%M},{b[1]:.2f},{b[2]:.2f},{b[3]:.2f},{b[4]:.2f}\n"


def read_bars(n):
    d = server.tv_eval(JS_BARS % (CHART, n))
    if str(d.get("res")) != "1":
        raise RuntimeError(f"the chart is on {d.get('sym')} {d.get('res')} - switch it to 1 minute")
    return d["sym"], d["bars"]


def closed(bars):
    now = time.time()
    return [b for b in bars if b[0] + 60 <= now]       # the forming candle is not written


def export(out, more=15):
    for _ in range(more):                               # ask the chart for older history
        server.tv_eval(f"(() => {{ {CHART}.requestMoreData(2000); return '1'; }})()")
        time.sleep(2.5)
    sym, bars = read_bars(10 ** 6)
    bars = closed(bars)
    # merge, never shrink: the chart only holds what it has loaded right now (it once left the file starting 13 Oct
    # 16:52 after the chart's first trade). Older candles stay; candles the chart still has are replaced by its values.
    rows = {}
    if out.exists():
        for ln in out.read_text(encoding="ascii", errors="ignore").splitlines():
            if len(ln.split(",")) >= 5:
                rows[ln[:16]] = ln + "\n"
    for b in bars:
        s = line(b)
        rows[s[:16]] = s
    out.write_text("".join(rows[k] for k in sorted(rows)), encoding="ascii")
    ks = sorted(rows)
    print(f"{sym}: {len(bars)} closed candles from the chart, file now {len(rows)} ({ks[0]} .. {ks[-1]} server time) -> {out}")
    return sym, len(rows)


def live(out, every=2.0):
    last = 0
    if out.exists():
        tail = out.read_text(encoding="ascii").strip().splitlines()[-1:]
        if tail:
            st = datetime.strptime(tail[0][:16], "%Y.%m.%d %H:%M")
            for h in (3, 2):                              # server time -> UTC epoch
                e = (st - timedelta(hours=h)).replace(tzinfo=timezone.utc).timestamp()
                if server_time(e) == st:
                    last = e
                    break
    print(f"live -> {out} (every {every}s, Ctrl+C to stop)")
    while True:
        try:
            sym, bars = read_bars(30)
            new = [b for b in closed(bars) if b[0] > last]
            if new:
                with open(out, "a", encoding="ascii") as f:
                    f.write("".join(line(b) for b in new))
                last = new[-1][0]
                print(f"{datetime.now():%H:%M:%S} {sym} +{len(new)} candle(s), last {server_time(last):%H:%M} server", flush=True)
        except Exception as e:                           # TradingView busy / reloading: try again
            print(f"{datetime.now():%H:%M:%S} {e}", flush=True)
        time.sleep(every)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--file", default=str(COMMON / "tv_bars_XAUUSD.csv"))
    a = ap.parse_args()
    out = Path(a.file)
    if a.export or not a.live:
        export(out)
    if a.live:
        live(out)
