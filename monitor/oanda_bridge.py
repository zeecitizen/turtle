"""oanda_bridge.py — THE volume bridge (the 6-month missing piece).

Zee's UHV method runs on OANDA/TradingView volume. Blueberry MT5's tick-count volume
is a DIFFERENT metric (same candle, e.g. 01:30 UTC: MT5 vol 451 vs OANDA vol 2132), so
the MT5-fed detector never saw Zee's UHVs. This bridge pulls OANDA:XAUUSD M1 bars (OHLC + volume) straight from the live
TradingView chart via Chrome DevTools Protocol (port 9222) and writes them to a CSV the
detector reads.

CORRECTION, 2026-08-13. This was described for months as "the real volume". IT IS NOT.
XAUUSD is OTC with no central exchange, so NO retail broker publishes traded volume —
both feeds report a TICK COUNT, meaning how many price updates arrived. OANDA's is denser
(median ~500 against Blueberry's ~200) because OANDA aggregates 20+ interbank feeds, not
because it measures something different in kind.

Why the denser feed is still the right one for this method: the rules are RELATIVE — the
loudest bar in the retracement, and a breakout quieter than it. A denser feed resolves
those comparisons more finely, so the bar it calls "loudest" is a better estimate of where
activity actually concentrated. Zee's teacher specified OANDA volume and that stands.

The real hazard is NOT a threshold mismatch — we use no absolute volume threshold
anywhere. It is that two feeds can disagree about WHICH bar was loudest. Measured: of 10
live entries the EA made on Blueberry bars, our OANDA archive agrees with only ONE. Same
minute, different answer about where the UHV sat.

TradingView internal path (reverse-engineered via CDP):
  window._exposed_chartWidgetCollection.activeChartWidget.value()
        .model().mainSeries().data().m_bars._items   ->  [{index, value:[t,o,h,l,c,vol]}]

Times are UNIX UTC (no timezone ambiguity). Run once (--once) or loop (--loop N).
Requires TradingView Desktop launched with --remote-debugging-port=9222 and the chart
on OANDA:XAUUSD, M1, with the Volume study (tradingview_launcher.bat).
"""
from __future__ import annotations
import argparse, asyncio, csv, json, os, sys, time, urllib.request
from pathlib import Path
import websockets

CDP_HTTP = "http://localhost:9222/json"
# MT5's Common\Files, resolved per-machine (2026-08-20) — see trend_eyes.CF.
_COMMON = Path(os.environ.get("APPDATA", r"C:/Users/zeesh/AppData/Roaming")) / \
          "MetaQuotes" / "Terminal" / "Common" / "Files"
OUT = _COMMON / "oanda_m1.csv"
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
    """SYMBOL-AWARE (2026-08-08): this bridge used to grab whatever the 'Forex' tab
    was showing. The moment Zee switched that chart to Bitcoin to set up the BTC
    machine, GOLD's own feed filled with BTC prices (64941 where 4340 belongs) — the
    gold ghost was one candle away from trading Bitcoin data on a gold chart. Now the
    bridge asks each page what it is showing and accepts only XAU."""
    d = json.load(urllib.request.urlopen(CDP_HTTP, timeout=5))
    pages = [p for p in d if p.get("type") == "page" and p.get("webSocketDebuggerUrl")]
    for p in pages:
        if "XAU" in (await _page_symbol(p["webSocketDebuggerUrl"])).upper():
            return p["webSocketDebuggerUrl"]
    raise RuntimeError("no TradingView tab is showing an XAUUSD chart on CDP :9222")


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
    tmp = OUT.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_unix", "open", "high", "low", "close", "volume"])
        for t, o, h, l, c, vol in bars:
            w.writerow([int(t), o, h, l, c, int(vol)])
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
            print(f"[oanda_bridge] wrote {n} OANDA M1 bars ({f} .. {l} UTC) -> {OUT.name}")
        except Exception as e:
            print(f"[oanda_bridge] ERROR: {e}", file=sys.stderr)
        if args.loop <= 0:
            break
        time.sleep(args.loop)


_STALL = {"last": None, "n": 0}


def _selfheal(edge):
    """A feed that dies quietly is worse than one that crashes: every health check
    still says ALIVE. Tonight gold sat 4 hours stale straight through the Sunday
    reopen. Six dead polls in a row now ends the process so the supervisor (or the
    next startup.bat) restarts it clean, instead of pretending to work."""
    import os, sys as _s
    if edge and edge == _STALL["last"]:
        _STALL["n"] += 1
        if _STALL["n"] >= 6:
            print("[oanda_bridge] FATAL: newest bar has not advanced in 6 polls — "
                  "exiting so a fresh process can take over", flush=True)
            os._exit(3)
    else:
        _STALL["n"] = 0
    _STALL["last"] = edge


if __name__ == "__main__":
    main()
