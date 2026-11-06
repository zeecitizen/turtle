"""cdp.py - a minimal Chrome DevTools Protocol client for PXTrader 2.0 (PrimeXBT web). Chrome must run with --remote-debugging-port=9222
on its own --user-data-dir (Chrome 136+ refuses debugging on the default profile). Used for the Golden Gravity P0 feasibility check:
find the page's quote stream, map the order panel, time an open -> close round trip. Nothing here places an order unless told to."""
import json, sys, time, urllib.request
import websocket

PORT = 9222


def pages():
    return [p for p in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")) if p.get("type") == "page"]


def pxbt_page():
    for p in pages():
        if "primexbt.com" in p.get("url", ""):
            return p
    return None


class CDP:
    def __init__(self, page):
        self.ws = websocket.create_connection(page["webSocketDebuggerUrl"], suppress_origin=True)
        self.ws.settimeout(10)
        self.n = 0
        self.events = []

    def call(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})
            if "method" in m:
                self.events.append(m)

    def js(self, expr):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"].get("text", "js error"))
        return r["result"].get("value")

    def listen(self, seconds):
        """collect events (after Network.enable) for a while"""
        t0 = time.time(); out = []
        self.ws.settimeout(1)
        while time.time() - t0 < seconds:
            try:
                m = json.loads(self.ws.recv())
            except websocket.WebSocketTimeoutException:
                continue
            if "method" in m:
                out.append(m)
        self.ws.settimeout(10)
        return out


if __name__ == "__main__":
    p = pxbt_page()
    print("pages:", [x["url"][:80] for x in pages()])
    if not p:
        sys.exit("no primexbt page open")
    c = CDP(p)
    print("title:", c.js("document.title"), "| url:", c.js("location.href"))
