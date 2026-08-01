"""compare_volume_feeds.py — which BTC feed gives the best UHV signal?

Our edge is the UHV: a volume SPIKE that stands out from its neighbours. A feed is only
useful if its volume has real variance (spike/median ratio) and isn't quantised or stale.
Pulls the CURRENT TradingView chart's M1 bars via CDP and reports:
  median vol, spike ratio (p95/median), % zero/flat bars, price movement.
Usage: switch the chart symbol, then run this; repeat per candidate feed.
"""
from __future__ import annotations
import asyncio, json, statistics as st, sys, urllib.request
import websockets

CDP = "http://localhost:9222/json"
BARS_JS = ("(function(){try{var b=window._exposed_chartWidgetCollection.activeChartWidget.value()"
           ".model().mainSeries().data().m_bars._items;"
           "return JSON.stringify(b.map(function(x){return x.value;}));}catch(e){return 'ERR '+e;}})()")
SYM_JS = ("(function(){try{return window._exposed_chartWidgetCollection.activeChartWidget.value()"
          ".model().mainSeries().symbolInfo().full_name;}catch(e){return 'ERR '+e;}})()")


def _ws():
    for p in json.load(urllib.request.urlopen(CDP, timeout=5)):
        if p.get("type") == "page" and "Forex" in p.get("title", ""):
            return p["webSocketDebuggerUrl"]
    raise RuntimeError("TV page not found on :9222")


async def _ev(expr, mid):
    async with websockets.connect(_ws(), max_size=None) as ws:
        await ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate",
                                  "params": {"expression": expr, "returnByValue": True, "timeout": 12000}}))
        while True:
            m = json.loads(await ws.recv())
            if m.get("id") == mid:
                return m.get("result", {}).get("result", {}).get("value")


def main():
    sym = asyncio.run(_ev(SYM_JS, 1))
    raw = asyncio.run(_ev(BARS_JS, 2))
    if not raw or str(raw).startswith("ERR"):
        print(f"{sym}: extract failed ({raw})"); return
    bars = [b for b in json.loads(raw) if b and len(b) >= 6 and b[1]]
    if len(bars) < 30:
        print(f"{sym}: only {len(bars)} bars"); return
    recent = bars[-300:]
    vols = [float(b[5]) for b in recent]
    rng = [float(b[2]) - float(b[3]) for b in recent]
    med = st.median(vols) or 1e-9
    p95 = sorted(vols)[int(len(vols) * 0.95)]
    flat = sum(1 for r in rng if r <= 0) / len(rng) * 100
    zero = sum(1 for v in vols if v <= 0) / len(vols) * 100
    print(f"\n=== {sym}  ({len(recent)} M1 bars) ===")
    print(f"  price       : {float(recent[-1][4]):,.2f}   median M1 range: {st.median(rng):.2f}")
    print(f"  volume      : median {med:.4g}   p95 {p95:.4g}   max {max(vols):.4g}")
    print(f"  SPIKE RATIO : p95/median = {p95/med:.2f}x   max/median = {max(vols)/med:.2f}x   <-- UHV detectability")
    print(f"  dead bars   : {flat:.0f}% zero-range, {zero:.0f}% zero-volume   <-- higher = worse/stale")
    print(f"  distinct vols: {len(set(vols))}/{len(vols)}   <-- low = quantised/fake")


if __name__ == "__main__":
    main()
