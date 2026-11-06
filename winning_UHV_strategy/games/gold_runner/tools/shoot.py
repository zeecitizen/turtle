"""tools/shoot.py - screenshots and scripted input through an ISOLATED headless Chrome.

NEVER use the debug Chrome on port 9222: it holds Zee's live PrimeXBT session (real money). This tool starts its own headless Chrome on
port 9333 with a throw-away profile in %TEMP%\\gg_headless and only ever talks to that one.

CLI:
  py tools/shoot.py URL OUT.png [--w 1600] [--h 900] [--wait 2.5] [--actions actions.json]
Python:
  from tools.shoot import shoot
  errs = shoot("http://127.0.0.1:8790/?fixture=open_profit", "out.png", w=1600, h=900, wait=2.5,
               actions=[{"wait": 1}, {"key": "Space", "hold": 0.6}, {"shot": "after_shoot.png"},
                        {"click": [800, 450]}, {"drag": [100, 700, 400, 650, 0.5]}, {"text": "CONFIRM"},
                        {"eval": "window.GG && GG.debug"}])
Returns (and prints) the console errors / uncaught exceptions seen while the page ran, plus eval results.
Each {"shot": path} writes an intermediate screenshot. Keys: any DOM key name ("Space", "KeyA", "Escape", "Enter", "ArrowLeft"...).
{"text": "..."} types into the focused element (Input.insertText: exact characters, capitals included).

Branching playthroughs (one long-lived page; same isolated Chrome on 9333):
  from tools.shoot import Page
  pg = Page("http://127.0.0.1:8792/", w=1600, h=900, wait=3)
  pg.key("Space", hold=0.6); pg.shot("a.png"); v = pg.eval("GG.debug.phase"); pg.type("CONFIRM"); errs = pg.errors(); pg.close()
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from cdpcore import CDPSession  # noqa: E402

PORT = 9333                                   # the isolated headless Chrome - never 9222
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = os.path.join(tempfile.gettempdir(), "gg_headless")

KEYS = {  # DOM code -> (key, windowsVirtualKeyCode)
    "Space": (" ", 32), "Enter": ("Enter", 13), "Escape": ("Escape", 27), "Tab": ("Tab", 9), "Backspace": ("Backspace", 8),
    "ArrowLeft": ("ArrowLeft", 37), "ArrowUp": ("ArrowUp", 38), "ArrowRight": ("ArrowRight", 39), "ArrowDown": ("ArrowDown", 40),
    "Backquote": ("`", 192),
}
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    KEYS["Key" + _c] = (_c.lower(), ord(_c))
for _d in "0123456789":
    KEYS["Digit" + _d] = (_d, ord(_d))


def _up():
    try:
        json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=2))
        return True
    except Exception:  # noqa: BLE001
        return False


def ensure_chrome():
    if _up():
        return
    os.makedirs(PROFILE, exist_ok=True)
    subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
                      "--no-first-run", "--no-default-browser-check", "--mute-audio", "--autoplay-policy=no-user-gesture-required",
                      "--window-size=1600,900", "about:blank"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
    for _ in range(50):
        if _up():
            return
        time.sleep(0.2)
    raise RuntimeError("headless Chrome did not come up on port %d" % PORT)


def _new_target(url):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?{url}", method="PUT")
    return json.load(urllib.request.urlopen(req, timeout=5))


def _close_target(tid):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/close/{tid}", timeout=5).read()
    except Exception:  # noqa: BLE001
        pass


def _listener(logs):
    def listen(method, p):
        if method == "Runtime.exceptionThrown":
            d = p.get("exceptionDetails", {})
            logs.append("EXCEPTION " + str(d.get("exception", {}).get("description") or d.get("text"))[:600])
        elif method == "Runtime.consoleAPICalled" and p.get("type") in ("error", "warning", "assert"):
            logs.append(p["type"].upper() + " " + " ".join(str(a.get("value", a.get("description", ""))) for a in p.get("args", []))[:600])
        elif method == "Log.entryAdded" and p.get("entry", {}).get("level") == "error":
            e = p["entry"]
            logs.append("LOG " + str(e.get("text"))[:400] + " " + str(e.get("url", ""))[:120])
    return listen


class Page:
    """One long-lived page on the isolated headless Chrome (port 9333 only), for playthroughs that branch on the game's state."""

    def __init__(self, url=None, w=1600, h=900, wait=2.5):
        ensure_chrome()
        self.target = _new_target("about:blank")
        self.s = CDPSession(self.target["webSocketDebuggerUrl"])
        self.logs = []
        self.s.on(_listener(self.logs))
        self.s.call("Runtime.enable")
        self.s.call("Log.enable")
        self.s.call("Page.enable")
        self.size(w, h)
        if url:
            self.goto(url, wait)

    def size(self, w, h):
        self.s.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)

    def goto(self, url, wait=2.5):
        self.s.call("Page.navigate", url=url)
        time.sleep(wait)

    def key_down(self, code):
        key, vk = KEYS.get(code, (code, 0))
        self.s.call("Input.dispatchKeyEvent", type="keyDown", key=key, code=code, windowsVirtualKeyCode=vk, text=key if len(key) == 1 else "")

    def key_up(self, code):
        key, vk = KEYS.get(code, (code, 0))
        self.s.call("Input.dispatchKeyEvent", type="keyUp", key=key, code=code, windowsVirtualKeyCode=vk)

    def key(self, code, hold=0.05):
        self.key_down(code)
        time.sleep(float(hold))
        self.key_up(code)

    def type(self, text):
        self.s.call("Input.insertText", text=str(text))

    def move(self, x, y):
        self.s.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)

    def click(self, x, y, hold=0.05):
        self.s.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
        self.s.call("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", clickCount=1)
        time.sleep(hold)
        self.s.call("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", clickCount=1)

    def drag(self, x1, y1, x2, y2, dur=0.4, steps=12, hold_end=0.0):
        self.s.call("Input.dispatchMouseEvent", type="mouseMoved", x=x1, y=y1)
        self.s.call("Input.dispatchMouseEvent", type="mousePressed", x=x1, y=y1, button="left", clickCount=1)
        for i in range(1, steps + 1):
            self.s.call("Input.dispatchMouseEvent", type="mouseMoved", x=x1 + (x2 - x1) * i / steps, y=y1 + (y2 - y1) * i / steps,
                        button="left", buttons=1)
            time.sleep(dur / steps)
        if hold_end:
            time.sleep(hold_end)
        self.s.call("Input.dispatchMouseEvent", type="mouseReleased", x=x2, y=y2, button="left", clickCount=1)

    def eval(self, js, timeout=10):
        try:
            return self.s.js(js, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            return "EVAL ERROR " + str(e)[:300]

    def shot(self, path, clip=None, scale=1.0):
        """clip = (x, y, w, h) in CSS px: a close-up (scale 2 = twice the pixels)"""
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        if not clip:
            return self.s.screenshot(path)
        import base64
        x, y, w, h = clip
        data = self.s.call("Page.captureScreenshot", timeout=20, format="png",
                           clip={"x": x, "y": y, "width": w, "height": h, "scale": scale})["data"]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        return path

    def errors(self, clear=False):
        out = list(self.logs)
        if clear:
            self.logs.clear()
        return out

    def close(self):
        try:
            self.s.close()
        finally:
            _close_target(self.target["id"])


def shoot(url, out=None, w=1600, h=900, wait=2.5, actions=None, keep=False):
    ensure_chrome()
    t = _new_target("about:blank")
    s = CDPSession(t["webSocketDebuggerUrl"])
    logs = []
    s.on(_listener(logs))
    try:
        s.call("Runtime.enable")
        s.call("Log.enable")
        s.call("Page.enable")
        s.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
        s.call("Page.navigate", url=url)
        time.sleep(wait)
        results = []
        for a in actions or []:
            if "wait" in a:
                time.sleep(float(a["wait"]))
            if "key" in a:
                code = a["key"]
                key, vk = KEYS.get(code, (code, 0))
                s.call("Input.dispatchKeyEvent", type="keyDown", key=key, code=code, windowsVirtualKeyCode=vk, text=key if len(key) == 1 else "")
                time.sleep(float(a.get("hold", 0.05)))
                s.call("Input.dispatchKeyEvent", type="keyUp", key=key, code=code, windowsVirtualKeyCode=vk)
            if "text" in a:
                s.call("Input.insertText", text=str(a["text"]))
            if "click" in a:
                x, y = a["click"][:2]
                hold = a["click"][2] if len(a["click"]) > 2 else 0.05
                s.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
                s.call("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", clickCount=1)
                time.sleep(hold)
                s.call("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", clickCount=1)
            if "drag" in a:
                x1, y1, x2, y2 = a["drag"][:4]
                dur = a["drag"][4] if len(a["drag"]) > 4 else 0.4
                s.call("Input.dispatchMouseEvent", type="mouseMoved", x=x1, y=y1)
                s.call("Input.dispatchMouseEvent", type="mousePressed", x=x1, y=y1, button="left", clickCount=1)
                n = 12
                for i in range(1, n + 1):
                    s.call("Input.dispatchMouseEvent", type="mouseMoved", x=x1 + (x2 - x1) * i / n, y=y1 + (y2 - y1) * i / n, button="left", buttons=1)
                    time.sleep(dur / n)
                s.call("Input.dispatchMouseEvent", type="mouseReleased", x=x2, y=y2, button="left", clickCount=1)
            if "eval" in a:
                try:
                    results.append(s.js(a["eval"]))
                except Exception as e:  # noqa: BLE001
                    results.append("EVAL ERROR " + str(e)[:300])
            if "shot" in a:
                s.screenshot(a["shot"])
        if out:
            s.screenshot(out)
        for line in logs:
            print(line)
        if results:
            print("eval results:", json.dumps(results, default=str)[:2000])
        return {"errors": logs, "results": results}
    finally:
        s.close()
        if not keep:
            _close_target(t["id"])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("--w", type=int, default=1600)
    ap.add_argument("--h", type=int, default=900)
    ap.add_argument("--wait", type=float, default=2.5)
    ap.add_argument("--actions")
    a = ap.parse_args()
    acts = json.load(open(a.actions)) if a.actions else None
    r = shoot(a.url, a.out, a.w, a.h, a.wait, acts)
    print(f"saved {a.out} · {len(r['errors'])} console errors")
