"""oanda_bridge.py — THE volume bridge (the 6-month missing piece).

Zee's UHV method runs on OANDA/TradingView volume. Blueberry MT5's tick-count volume
is a DIFFERENT metric (same candle, e.g. 01:30 UTC: MT5 vol 451 vs OANDA vol 2132), so
the MT5-fed detector never saw Zee's UHVs. This bridge pulls OANDA:BTCUSD M1 bars
(OHLC + the real volume) straight from the live TradingView chart via Chrome DevTools
Protocol (port 9222) and writes them to a CSV the detector reads.

TradingView internal path (reverse-engineered via CDP):
  window._exposed_chartWidgetCollection.activeChartWidget.value()
        .model().mainSeries().data().m_bars._items   ->  [{index, value:[t,o,h,l,c,vol]}]

Times are UNIX UTC (no timezone ambiguity). Run once (--once) or loop (--loop N).
Requires TradingView Desktop launched with --remote-debugging-port=9222 and the chart
on OANDA:BTCUSD, M1, with the Volume study (tradingview_launcher.bat).
"""
from __future__ import annotations
import argparse, asyncio, csv, json, sys, time, urllib.request
from pathlib import Path
import websockets

CDP_HTTP = "http://localhost:9222/json"
VMUL = 1
OUT = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/btc_m1.csv")
EXTRACT_JS = (
    "(function(){try{"
    "var b=window._exposed_chartWidgetCollection.activeChartWidget.value()"
    ".model().mainSeries().data().m_bars._items;"
    "return JSON.stringify(b.map(function(x){return x.value;}));"
    "}catch(e){return 'ERR '+e;}})()"
)


SYMBOL_JS = (
    "(function(){try{return window._exposed_chartWidgetCollection.activeChartWidget"
    ".value().model().mainSeries().symbolInfo().name;}catch(e){return '';}})()"
)


async def _page_symbol(url):
    """Ask a CDP page which symbol its active chart shows."""
    try:
        async with websockets.connect(url, max_size=None) as ws:
            await ws.send(json.dumps({"id": 9, "method": "Runtime.evaluate",
                                      "params": {"expression": SYMBOL_JS,
                                                 "returnByValue": True, "timeout": 6000}}))
            while True:
                m = json.loads(await ws.recv())
                if m.get("id") == 9:
                    return str(m.get("result", {}).get("result", {}).get("value") or "")
    except Exception:
        return ""


async def _ws_url_async():
    """BTC machine (2026-08-08): pick the TradingView tab whose ACTIVE CHART is
    Bitcoin — title matching is unreliable with two charts open, so we ask each page
    what it is showing. Async because it runs inside the pull's own event loop."""
    d = json.load(urllib.request.urlopen(CDP_HTTP, timeout=5))
    pages = [p for p in d if p.get("type") == "page" and p.get("webSocketDebuggerUrl")]
    for p in pages:
        sym = (await _page_symbol(p["webSocketDebuggerUrl"])).upper()
        if "BTC" in sym:
            return p["webSocketDebuggerUrl"]
    raise RuntimeError("no TradingView tab is showing a BTC chart on CDP :9222 — "
                       "open BTCUSD (OANDA feed), M1, with the Volume study")


async def _pull():
    url = await _ws_url_async()
    async with websockets.connect(url, max_size=None) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                  "params": {"expression": EXTRACT_JS, "returnByValue": True, "timeout": 12000}}))
        while True:
            m = json.loads(await ws.recv())
            if m.get("id") == 1:
                v = m.get("result", {}).get("result", {}).get("value")
                if not v or str(v).startswith("ERR"):
                    raise RuntimeError(f"extract failed: {v}")
                return json.loads(v)


def pull_and_write():
    bars = asyncio.run(_pull())
    bars = [b for b in bars if b and len(b) >= 6 and b[1]]   # valid rows
    # VOLUME UNITS (2026-08-08): a broker feed (Pepperstone/OANDA) gives whole tick
    # counts; an exchange feed (Binance) gives fractional BTC, where int() would
    # truncate almost every bar to ZERO and destroy the UHV signal outright. Detect
    # which we are looking at and scale only when we must — every rule is relative,
    # so the unit never matters, but the precision does.
    vmax = max((float(b[5]) for b in bars), default=0)
    global VMUL
    VMUL = 1000 if vmax < 100 else 1
    tmp = OUT.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_unix", "open", "high", "low", "close", "volume"])
        for t, o, h, l, c, vol in bars:
            # VOLUME PRECISION (2026-08-08): OANDA's BTCUSD is a CFD that closes with
            # forex on Friday, so the weekend feed comes from BINANCE:BTCUSDT — whose
            # volume is fractional BTC (0.22, 15.3). int() would truncate most bars to
            # ZERO and destroy the whole UHV signal. Store volume x1000 as an integer;
            # every rule in the strategy is RELATIVE, so the unit does not matter.
            w.writerow([int(t), o, h, l, c, int(round(float(vol) * VMUL))])
    tmp.replace(OUT)
    return len(bars), (int(bars[0][0]) if bars else 0), (int(bars[-1][0]) if bars else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="poll every N seconds (0 = once)")
    args = ap.parse_args()
    while True:
        try:
            n, t0, t1 = pull_and_write()
            from datetime import datetime, timezone
            f = datetime.fromtimestamp(t0, tz=timezone.utc).strftime("%m-%d %H:%M")
            l = datetime.fromtimestamp(t1, tz=timezone.utc).strftime("%m-%d %H:%M")
            print(f"[btc_bridge] wrote {n} OANDA M1 bars ({f} .. {l} UTC) -> {OUT.name}")
        except Exception as e:
            print(f"[btc_bridge] ERROR: {e}", file=sys.stderr)
        if args.loop <= 0:
            break
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
