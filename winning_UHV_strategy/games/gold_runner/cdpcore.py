"""cdpcore.py - threaded Chrome DevTools Protocol session + access to PXTrader 2.0's own WebSocket(s).

Chrome must run with --remote-debugging-port=9222 on a dedicated --user-data-dir (Chrome 136+ refuses remote debugging on the default
profile); games/gold_runner/chrome_profile is that profile. The PrimeXBT page stays open and logged in: it is the session holder.

  sess = CDPSession.attach()                 # the primexbt.com page target
  sess.on(lambda method, params: ...)        # every CDP event (Network.webSocketFrameReceived / Sent ...)
  sess.call("Network.enable")
  px = PageSockets(sess); px.acquire()      # finds the page's live WebSocket objects (Runtime.queryObjects)
  px.send(sock_index, {"type": "REQUEST", "rid": 900001, "action": "time", "body": {}})
"""
import itertools
import json
import threading
import time
import urllib.request

import websocket

PORT = 9222


def targets(port=PORT):
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5))


def pxbt_target(port=PORT):
    for t in targets(port):
        if t.get("type") == "page" and "primexbt.com" in t.get("url", ""):
            return t
    return None


class CDPError(RuntimeError):
    pass


class CDPSession:
    """One CDP websocket to one page target, with a reader thread: calls are matched by id, events go to listeners."""

    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=10, enable_multithread=True)
        self.ws.settimeout(None)
        self._ids = itertools.count(1)
        self._pending = {}
        self._lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._listeners = []
        self.alive = True
        self.closed_reason = None
        self._t = threading.Thread(target=self._reader, name="cdp-reader", daemon=True)
        self._t.start()

    @classmethod
    def attach(cls, port=PORT):
        t = pxbt_target(port)
        if not t:
            raise CDPError("no primexbt.com page is open in the debug Chrome")
        return cls(t["webSocketDebuggerUrl"])

    def on(self, fn):
        self._listeners.append(fn)
        return fn

    def off(self, fn):
        if fn in self._listeners:
            self._listeners.remove(fn)

    def _reader(self):
        while self.alive:
            try:
                raw = self.ws.recv()
            except Exception as e:                       # noqa: BLE001  (socket closed, Chrome gone)
                self.alive = False
                self.closed_reason = str(e)[:200]
                break
            if not raw:
                continue
            try:
                m = json.loads(raw)
            except ValueError:
                continue
            if "id" in m:
                with self._lock:
                    slot = self._pending.pop(m["id"], None)
                if slot:
                    slot[1] = m
                    slot[0].set()
            elif "method" in m:
                for fn in list(self._listeners):
                    try:
                        fn(m["method"], m.get("params", {}))
                    except Exception:                    # noqa: BLE001  a listener must never kill the reader
                        pass
        with self._lock:                                 # wake every waiter
            for slot in self._pending.values():
                slot[1] = {"error": {"message": "CDP connection closed: " + str(self.closed_reason)}}
                slot[0].set()
            self._pending.clear()

    def call(self, method, timeout=10, **params):
        if not self.alive:
            raise CDPError("CDP connection closed: " + str(self.closed_reason))
        i = next(self._ids)
        ev = threading.Event()
        slot = [ev, None]
        with self._lock:
            self._pending[i] = slot
        with self._send_lock:
            self.ws.send(json.dumps({"id": i, "method": method, "params": params}))
        if not ev.wait(timeout):
            with self._lock:
                self._pending.pop(i, None)
            raise TimeoutError(f"CDP {method} timed out after {timeout}s")
        m = slot[1]
        if "error" in m:
            raise CDPError(f"{method}: {m['error']}")
        return m.get("result", {})

    def js(self, expression, timeout=10):
        r = self.call("Runtime.evaluate", timeout=timeout, expression=expression, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            raise CDPError("js: " + str(d.get("exception", {}).get("description") or d.get("text"))[:400])
        return r.get("result", {}).get("value")

    def screenshot(self, path):
        import base64
        data = self.call("Page.captureScreenshot", timeout=20, format="png")["data"]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        return path

    def close(self):
        self.alive = False
        try:
            self.ws.close()
        except Exception:                                # noqa: BLE001
            pass


class PageSockets:
    """The page's own WebSocket objects, found with Runtime.queryObjects(WebSocket.prototype) and kept in window.__gg_socks.
    Each socket gets a tag; a message listener counts what each one receives so the trading socket can be identified."""

    INSTALL = r"""function () {
        const socks = this.filter(w => w && w.readyState === 1);
        window.__gg_socks = socks;
        window.__gg_rx = window.__gg_rx || {};
        socks.forEach((w, i) => {
            if (w.__gg_tag === undefined) {
                w.__gg_tag = i;
                w.addEventListener('message', (e) => {
                    const s = typeof e.data === 'string' ? e.data : '';
                    const m = s.match(/"action":"([^"]+)"/);
                    const k = i + ':' + (m ? m[1] : '?');
                    window.__gg_rx[k] = (window.__gg_rx[k] || 0) + 1;
                });
            }
        });
        return socks.map((w, i) => ({ i, url: w.url, state: w.readyState, protocol: w.protocol }));
    }"""

    def __init__(self, sess):
        self.sess = sess
        self.info = []

    def acquire(self):
        proto = self.sess.call("Runtime.evaluate", expression="WebSocket.prototype")["result"]["objectId"]
        arr = self.sess.call("Runtime.queryObjects", prototypeObjectId=proto)["objects"]["objectId"]
        r = self.sess.call("Runtime.callFunctionOn", objectId=arr, functionDeclaration=self.INSTALL, returnByValue=True)
        self.info = r.get("result", {}).get("value") or []
        return self.info

    def received_counts(self):
        return self.sess.js("window.__gg_rx || {}")

    def send(self, index, msg):
        """send one JSON frame on the page's socket number `index` (as listed by acquire())"""
        payload = json.dumps(json.dumps(msg))
        ok = self.sess.js(f"(() => {{ const w = (window.__gg_socks || [])[{int(index)}]; if (!w || w.readyState !== 1) return false; w.send({payload}); return true; }})()")
        if not ok:
            raise CDPError(f"page socket {index} is not open - re-acquire")
        return True
