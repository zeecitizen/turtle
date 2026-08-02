"""snap.py — one command: live chart screenshot + market state, instantly.

Zee 2026-08-02: *"screenshot capture ka script baar baar likhnay ki jaga aik callable
script bana lo… jab screenshot chahiay direct THA kar k mil jaey"* — capturing through the
MCP round-trip and then hunting for a new timestamped filename was costing ~1 minute per
look. This grabs the frame straight off the TradingView CDP socket and always writes the
SAME path, so the follow-up is a plain Read with no filename to parse.

    $PY monitor/snap.py            # BTC: capture + scan + armed state
    $PY monitor/snap.py XAU        # gold
    $PY monitor/snap.py BTC bare   # capture only, no market state

Then just:  Read  monitor/setup_labels/live.png
"""
from __future__ import annotations
import asyncio, base64, json, sys, urllib.request
from pathlib import Path
import websockets

OUT = Path(__file__).parent / "setup_labels" / "live.png"
CDP = "http://localhost:9222/json"


def _ws():
    for p in json.load(urllib.request.urlopen(CDP, timeout=5)):
        if p.get("type") == "page" and ("Forex" in p.get("title", "") or "tradingview" in p.get("url", "").lower()):
            return p["webSocketDebuggerUrl"]
    raise RuntimeError("TradingView page not found on CDP :9222 — see CLAUDE_REALTIME_EA.md §6")


async def _shot(clip_to_chart=True):
    async with websockets.connect(_ws(), max_size=None) as ws:
        mid = [0]

        async def send(method, params=None):
            mid[0] += 1
            await ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
            while True:
                m = json.loads(await ws.recv())
                if m.get("id") == mid[0]:
                    return m.get("result", {})

        params = {"format": "png"}
        if clip_to_chart:
            # crop to the chart canvas so the screenshot is all candles, no sidebars
            r = await send("Runtime.evaluate", {"expression": (
                "(function(){var c=document.querySelector('canvas');if(!c)return '';"
                "var b=c.getBoundingClientRect();"
                "return JSON.stringify({x:b.x,y:b.y,width:b.width,height:b.height});})()"),
                "returnByValue": True})
            box = r.get("result", {}).get("value")
            if box:
                b = json.loads(box)
                if b["width"] > 200 and b["height"] > 150:
                    params["clip"] = {**b, "scale": 1}
        res = await send("Page.captureScreenshot", params)
        return base64.b64decode(res["data"])


def snap():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(asyncio.run(_shot()))
    return OUT


if __name__ == "__main__":
    market = (sys.argv[1] if len(sys.argv) > 1 else "BTC").upper()
    bare = len(sys.argv) > 2 and sys.argv[2] == "bare"
    try:
        p = snap()
        print(f"[snap] {p}  ({p.stat().st_size // 1024} KB)  -> Read this path")
    except Exception as e:
        print(f"[snap] FAILED: {e}")
        sys.exit(1)
    if bare:
        sys.exit(0)
    # market state in the same call, so one command tells the whole story
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        import claude_judge as J
        s = J.scan(market)
        if isinstance(s, dict) and s.get("status") == "PENDING":
            print(f"[scan] *** PENDING {s['side']} @ {s['entry']} *** — judge it now "
                  f"(strength {s['strength']}, brk_body {s['brk_body']}, uhv_vol {s['uhv_vol']})")
            print(f"       chart: monitor/setup_labels/pending_setup.png")
        elif isinstance(s, dict) and s.get("error"):
            print(f"[scan] ERROR: {s['error']}")
        else:
            print("[scan] no completed setup")
            n = J.near(market)
            if n.get("armed"):
                for c in n["candidates"]:
                    print(f"[near] ARMED {c['side']}: breakout level {c['breakout_level']} · "
                          f"price {c['price_now']} · {c['distance']} away · "
                          f"UHV {c['uhv_time']} vol {c['uhv_vol']} body {c['uhv_body_ratio']} · "
                          f"{c['bars_since_uhv']} bars ago")
            elif n.get("error"):
                print(f"[near] ERROR: {n['error']}")
            else:
                print(f"[near] nothing armed · price {n.get('price')}")
    except Exception as e:
        print(f"[state] unavailable: {e}")
