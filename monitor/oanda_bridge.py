"""oanda_bridge.py — THE volume bridge (the 6-month missing piece).

Zee's UHV method runs on OANDA/TradingView volume. Blueberry MT5's tick-count volume
is a DIFFERENT metric (same candle, e.g. 01:30 UTC: MT5 vol 451 vs OANDA vol 2132), so
the MT5-fed detector never saw Zee's UHVs. This bridge pulls OANDA:XAUUSD M1 bars
(OHLC + the real volume) straight from the live TradingView chart via Chrome DevTools
Protocol (port 9222) and writes them to a CSV the detector reads.

TradingView internal path (reverse-engineered via CDP):
  window._exposed_chartWidgetCollection.activeChartWidget.value()
        .model().mainSeries().data().m_bars._items   ->  [{index, value:[t,o,h,l,c,vol]}]

Times are UNIX UTC (no timezone ambiguity). Run once (--once) or loop (--loop N).
Requires TradingView Desktop launched with --remote-debugging-port=9222 and the chart
on OANDA:XAUUSD, M1, with the Volume study (tradingview_launcher.bat).
"""
from __future__ import annotations
import argparse, asyncio, csv, json, sys, time, urllib.request
from pathlib import Path
import websockets

CDP_HTTP = "http://localhost:9222/json"
OUT = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_m1.csv")
EXTRACT_JS = (
    "(function(){try{"
    "var b=window._exposed_chartWidgetCollection.activeChartWidget.value()"
    ".model().mainSeries().data().m_bars._items;"
    "return JSON.stringify(b.map(function(x){return x.value;}));"
    "}catch(e){return 'ERR '+e;}})()"
)
# which symbol is the chart on? written next to the CSV so consumers can VERIFY they are
# reading the instrument they expect (XAUUSD thresholds on BTC data would be catastrophic).
SYMBOL_JS = (
    "(function(){try{"
    "return window._exposed_chartWidgetCollection.activeChartWidget.value()"
    ".model().mainSeries().symbolInfo().full_name;"
    "}catch(e){return 'ERR '+e;}})()"
)
SYMBOL_FILE = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_m1.symbol")


def _ws_url():
    d = json.load(urllib.request.urlopen(CDP_HTTP, timeout=5))
    for p in d:
        if p.get("type") == "page" and "Forex" in p.get("title", ""):
            return p["webSocketDebuggerUrl"]
    raise RuntimeError("TradingView chart page not found on CDP :9222")


async def _pull():
    url = _ws_url()
    async with websockets.connect(url, max_size=None) as ws:
        out = {}
        for mid, expr, key in ((1, EXTRACT_JS, "bars"), (2, SYMBOL_JS, "symbol")):
            await ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate",
                                      "params": {"expression": expr, "returnByValue": True, "timeout": 12000}}))
            while True:
                m = json.loads(await ws.recv())
                if m.get("id") == mid:
                    v = m.get("result", {}).get("result", {}).get("value")
                    if not v or str(v).startswith("ERR"):
                        raise RuntimeError(f"{key} extract failed: {v}")
                    out[key] = json.loads(v) if key == "bars" else v
                    break
        return out["bars"], out["symbol"]


def pull_and_write(out_path=None):
    bars, symbol = asyncio.run(_pull())
    bars = [b for b in bars if b and len(b) >= 6 and b[1]]   # valid rows
    dest = Path(out_path) if out_path else OUT
    tmp = dest.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_unix", "open", "high", "low", "close", "volume"])
        for t, o, h, l, c, vol in bars:
            w.writerow([int(t), o, h, l, c, vol])          # keep float volume (crypto = BTC units)
    tmp.replace(dest)
    # symbol marker so consumers can VERIFY they read the instrument they expect
    dest.with_suffix(".symbol").write_text(symbol, encoding="ascii")
    return len(bars), (int(bars[0][0]) if bars else 0), (int(bars[-1][0]) if bars else 0), symbol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="poll every N seconds (0 = once)")
    ap.add_argument("--out", default=None, help="output CSV (default oanda_m1.csv)")
    args = ap.parse_args()
    while True:
        try:
            n, t0, t1, sym = pull_and_write(args.out)
            from datetime import datetime, timezone
            f = datetime.fromtimestamp(t0, tz=timezone.utc).strftime("%m-%d %H:%M")
            l = datetime.fromtimestamp(t1, tz=timezone.utc).strftime("%m-%d %H:%M")
            print(f"[bridge] {sym}: wrote {n} M1 bars ({f} .. {l} UTC) -> {Path(args.out).name if args.out else OUT.name}")
        except Exception as e:
            print(f"[oanda_bridge] ERROR: {e}", file=sys.stderr)
        if args.loop <= 0:
            break
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
