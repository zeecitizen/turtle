"""serve_setup_labels.py — local HTTP server for the setup labelling UI.

Serves setups.html + PNGs, and provides /api/labels GET/POST for Zee + Shano's
comments to be saved to zee_labels.json.

Run:
    py monitor/serve_setup_labels.py

Then open http://127.0.0.1:8765/setups.html in browser.
"""
from __future__ import annotations
import json, sys, os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"c:/Users/zeesh/Documents/GitHub/turtle/monitor/setup_labels")
LABELS_FILE = ROOT / "zee_labels.json"
# 2026-08-24, Zee: "is there a way that i annotate setups on tradingview chart and you
# read them from there? that would help you gauge what i think is the method."
# TradingView refused: anonymous charts are read-only and its sign-in will not run in a
# debug-enabled browser. So the marks are made on HIS OWN OANDA candles instead, and
# this file is what the grader reads. One entry per setup HE marks — the three anchors
# the laws actually turn on, not a rectangle someone has to interpret.
MARKS_FILE = ROOT / "zee_marks.json"
PORT = 8765


def load_labels():
    if LABELS_FILE.exists():
        try: return json.loads(LABELS_FILE.read_text(encoding="utf-8"))
        except Exception: return {}
    return {}


def save_labels(d):
    LABELS_FILE.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def load_marks():
    if MARKS_FILE.exists():
        try:
            return json.loads(MARKS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_marks(rows):
    MARKS_FILE.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a, **kw):
        pass  # quiet

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/" or path == "":
            path = "/setups.html"
        if path == "/api/labels":
            return self._json(load_labels())
        if path == "/api/marks":
            return self._json(load_marks())
        # serve static
        fp = ROOT / path.lstrip("/")
        if fp.exists() and fp.is_file():
            mime = "text/html" if fp.suffix == ".html" else (
                "image/png" if fp.suffix == ".png" else
                "application/json" if fp.suffix == ".json" else
                "application/octet-stream")
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(fp.stat().st_size))
            self.end_headers()
            with open(fp, "rb") as f:
                self.wfile.write(f.read())
            return
        self.send_error(404)

    def do_POST(self):
        if self.path == "/api/marks":
            n = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(n).decode("utf-8", errors="replace"))
            except Exception:
                return self.send_error(400)
            marks = load_marks()
            if data.get("delete"):
                marks = [m for m in marks if m.get("id") != data["delete"]]
                save_marks(marks)
                return self._json({"ok": True, "deleted": data["delete"], "total": len(marks)})
            need = ("origin", "uhv", "breakout")
            if not all(k in data for k in need):
                return self._json({"ok": False, "error": "need origin, uhv and breakout"})
            mark = {k: data[k] for k in need}
            mark["side"] = data.get("side", "buy")
            mark["note"] = data.get("note", "")
            mark["id"] = "{}-{}".format(mark["side"], mark["breakout"])
            marks = [m for m in marks if m.get("id") != mark["id"]] + [mark]
            marks.sort(key=lambda m: m["breakout"])
            save_marks(marks)
            return self._json({"ok": True, "saved": mark["id"], "total": len(marks)})
        if self.path != "/api/labels":
            return self.send_error(404)
        n = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(n).decode("utf-8", errors="replace")
        try:
            data = json.loads(body)
        except Exception:
            return self.send_error(400)
        idx = str(data.get("idx"))
        who = str(data.get("who", "zee")).lower()
        label = str(data.get("label", ""))
        if who not in ("zee", "shano"):
            who = "zee"
        labels = load_labels()
        if idx not in labels:
            labels[idx] = {}
        labels[idx][who] = label
        save_labels(labels)
        return self._json({"ok": True, "saved": {idx: {who: label[:30] + "..." if len(label)>30 else label}}})

    def _json(self, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    addr = ("0.0.0.0", PORT)
    httpd = ThreadingHTTPServer(addr, Handler)
    url = f"http://127.0.0.1:{PORT}/setups.html"
    print(f"Setup labeller running at {url}")
    print(f"LAN access: http://192.168.x.x:{PORT}/setups.html")
    print(f"Labels saved to: {LABELS_FILE}")
    print("\nCtrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
        httpd.shutdown()


if __name__ == "__main__":
    main()
