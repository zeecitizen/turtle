"""server.py - Golden Gravity: The $1 Heist - HTTP static files + Server-Sent Events + player actions (CONTRACT.md sections 3 and 6).

  python server.py --mode sim     [--port 8790] [--seed 7] [--speed 1.0]   synthetic market + simulated broker (default; all testing)
  python server.py --mode replay --file recordings/X.jsonl [--speed 1]     replays recorded frames; wooden rounds only
  python server.py --mode live    [--record]                               the PXTrader page on :9222 (REAL MONEY - Claude/Zee only)
  extras: --root DIR (rounds/ and state/ live there; tests use a temp dir), --host, --real-hours (sim/replay obey the real dead
          hours, weekend and session close)

  GET  /                      static/index.html            GET /static/* or /js/* /css/* ...   files from static/
  GET  /api/state             one snapshot (JSON)          GET /api/stream                    SSE: "snap" every 100 ms, "ev" events, ": hb" 1/s
  POST /api/act               {"action","nonce","sent_at","args"} -> {"accepted","why"}
  POST /api/settings          {"coin_oz"?, "stop_dist"?, "sound"?, "plain_line"?, "eject_words"?, "live_enabled"?, "confirm_word"?}
  GET  /api/rounds?limit=50   recent round summaries       GET /api/tallies                   GET /api/health

The server binds 127.0.0.1 only (it can move real money) and binds BEFORE the feed starts, so a busy port never leads to a second
attachment to the live page.

Cross-site guard (every /api/* request): the Host header must be 127.0.0.1:<port> or localhost:<port> (a DNS-rebinding page sends
its own host name), and every POST must be Content-Type application/json (a cross-site page cannot send that without a CORS
preflight, which this server never approves), carry no foreign Origin (Origin "null" included) and no Sec-Fetch-Site other than
same-origin. A refused request gets HTTP 403 and never reaches the engine.
"""
import argparse
import json
import os
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import engine
import admin  # noqa: E402

STATIC = os.path.join(HERE, "static")
MIME = {
    ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8", ".map": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    ".svg": "image/svg+xml", ".ico": "image/x-icon",
    ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf",
    ".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg",
}
PLACEHOLDER = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Golden Gravity - server up</title>
<style>body{background:#1a1410;color:#ffcc33;font:15px Georgia,serif;padding:2em}pre{color:#f6efdc;font:12px monospace;white-space:pre-wrap}</style>
</head><body><h1>Golden Gravity: the server is up</h1><p>static/index.html is not there yet (the frontend is still being built).
This page shows the live snapshot stream.</p><pre id="s">waiting for /api/stream ...</pre>
<script>const es=new EventSource('/api/stream');es.addEventListener('snap',e=>{const s=JSON.parse(e.data);
document.getElementById('s').textContent=JSON.stringify({t:s.t,mode:s.mode,phase:s.phase,quote:s.quote,feed:s.feed,
shutters:s.market.shutters,limits:s.limits,round:s.round&&{x:s.round.x,value:s.round.value_text,anvil:s.round.anvil}},null,1)});</script>
</body></html>"""


class GameServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False          # on Windows a leftover instance could otherwise silently share the port
    request_queue_size = 64

    def __init__(self, addr, handler, hz=10):
        super().__init__(addr, handler)
        self.engine = None
        self.hz = max(1.0, float(hz or 10))
        self.stopping = False
        self.clients = 0
        self._clients_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = "GoldenGravity/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):          # quiet: the engine logs what matters
        pass

    # ---------------------------------------------------------------------------------------------------------------- plumbing
    def _send(self, code, body, ctype="application/json; charset=utf-8", head_only=False):
        data = body if isinstance(body, (bytes, bytearray)) else str(body).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if not head_only:
                self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            self.close_connection = True

    def _json(self, obj, code=200):
        if isinstance(obj, str):
            return self._send(code, obj)
        return self._send(code, json.dumps(engine.sanitize(obj), separators=(",", ":"), allow_nan=False))

    def _engine(self):
        eng = self.server.engine
        if eng is None:
            self._json({"error": "starting"}, 503)
        return eng

    # ---------------------------------------------------------------------------------------------------------------- cross-site guard
    def _allowed_hosts(self):
        port = self.server.server_address[1]
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        bound = str(self.server.server_address[0] or "").lower()
        if bound and bound not in ("0.0.0.0", "::", ""):
            hosts.add(f"{bound}:{port}" if ":" not in bound else f"[{bound}]:{port}")
        return hosts

    def _guard(self, post):
        """None when the request may reach the engine, else the reason it is refused (CSRF / DNS rebinding)."""
        host = (self.headers.get("Host") or "").strip().lower()
        hosts = self._allowed_hosts()
        if host not in hosts:
            return "host"
        if not post:
            return None
        ctype = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if ctype != "application/json":
            return "content_type"
        origin = self.headers.get("Origin")
        if origin is not None and origin.strip().lower().rstrip("/") not in {"http://" + h for h in hosts}:
            return "origin"
        sfs = self.headers.get("Sec-Fetch-Site")
        if sfs is not None and sfs.strip().lower() != "same-origin":
            return "cross_site"
        return None

    def _refuse(self, why, post):
        """403 for a request the guard refused; the body (if any) is drained and the connection closed."""
        if post:
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = 0
            if 0 < n <= 65536:
                try:
                    self.rfile.read(n)
                except OSError:
                    pass
        self.close_connection = True
        srv = self.server
        key = (why, self.command)
        seen = getattr(srv, "_refused_seen", None)
        if seen is None:
            seen = srv._refused_seen = {}
        now = time.time()
        if now - seen.get(key, 0.0) > 30.0:
            seen[key] = now
            print(f"[server] refused a {self.command} to {urllib.parse.urlsplit(self.path).path} ({why}): "
                  f"not from this game's own page", flush=True)
        return self._json({"accepted": False, "ok": False, "why": f"forbidden: {why}", "settings": None}, 403)

    def _read_json(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > 65536:
            return None
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    # ---------------------------------------------------------------------------------------------------------------- routes
    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        path = u.path
        if path.startswith("/api/"):
            why = self._guard(post=False)
            if why:
                return self._refuse(why, post=False)
        if path == "/api/stream":
            return self._stream()
        if path.startswith("/api/"):
            eng = self._engine()
            if eng is None:
                return None
            qs = urllib.parse.parse_qs(u.query)
            try:
                if path == "/api/state":
                    return self._json(eng.snapshot_json())
                if path == "/api/rounds":
                    try:
                        limit = int((qs.get("limit") or ["50"])[0])
                    except ValueError:
                        limit = 50
                    return self._json(eng.rounds_list(limit, (qs.get("mode") or [None])[0]))
                if path == "/api/tallies":
                    return self._json(eng.tallies())
                if path == "/api/admin":
                    return self._json(self._admin_view(eng))
                if path == "/api/health":
                    bars = (eng.fs or {}).get("bars") or []
                    return self._json({"ok": True, "mode": eng.mode, "book": eng.book_impl, "clients": self.server.clients,
                                       "phase": eng.phase, "t": time.time(), "bars_n": len(bars),
                                       "bars_tail": [list(b) for b in bars[-8:]]})   # the newest 1-minute bars (the last one forming)
            except Exception as e:  # noqa: BLE001
                return self._json({"error": f"{type(e).__name__}: {engine.scrub(e)}"}, 500)
            return self._json({"error": "not found"}, 404)
        return self._static(path)

    def do_HEAD(self):
        path = urllib.parse.urlsplit(self.path).path
        if path.startswith("/api/"):
            if self._guard(post=False):
                self.close_connection = True
                return self._send(403, b"", head_only=True)
            return self._send(200, b"", head_only=True)
        return self._static(path, head_only=True)

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        why = self._guard(post=True)
        if why:
            return self._refuse(why, post=True)
        eng = self._engine()
        if eng is None:
            return None
        body = self._read_json()
        try:
            if path == "/api/act":
                if not isinstance(body, dict):
                    return self._json({"accepted": False, "why": "bad_json"})
                return self._json(eng.act(body))
            if path == "/api/settings":
                if not isinstance(body, dict):
                    return self._json({"ok": False, "why": "bad_json", "settings": None})
                return self._json(eng.update_settings(body))
            if path == "/api/admin":                   # save the admin page (applies on the next build / Apply)
                data, why = admin.clean(body)
                if why:
                    return self._json({"ok": False, "why": why})
                admin.save(state_dir_of(self.server.root), data)
                return self._json({"ok": True, "admin": self._admin_view(eng)})
            if path == "/api/admin/apply":             # rebuild the feed + engine for the saved symbol, never during a round
                return self._json(self._admin_apply(eng))
        except Exception as e:  # noqa: BLE001
            return self._json({"accepted": False, "ok": False, "why": f"error: {type(e).__name__}"}, 500)
        return self._json({"error": "not found"}, 404)

    def _admin_view(self, eng):
        data = admin.load(state_dir_of(self.server.root))
        return {"admin": data, "fields": admin.FIELDS, "running": {"symbol": eng.cfg.get("symbol"), "mode": eng.mode, "phase": eng.phase,
                "price_dp": engine.PX_DP, "coin": eng.cfg.get("coin_oz")}}

    def _admin_apply(self, eng):
        srv = self.server
        with getattr(srv, "_rebuild_lock", threading.Lock()):
            if eng.phase not in ("lobby", "settled"):
                return {"ok": False, "why": "finish the round first (the game is " + str(eng.phase) + ")"}
            try:
                new = build_engine(srv.args, srv.root)
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "why": f"could not build: {type(e).__name__}: {engine.scrub(e)}"}
            srv.engine = None
            try:
                eng.stop()
            except Exception:  # noqa: BLE001
                pass
            srv.engine = new
            new.start()
            print(f"[server] rebuilt from the admin page: {new.cfg.get('symbol')}", flush=True)
            return {"ok": True, "admin": self._admin_view(new)}

    def _static(self, path, head_only=False):
        if path == "/favicon.ico":
            return self._send(204 if not head_only else 200, b"", "image/x-icon", head_only)
        if path in ("", "/"):
            path = "/index.html"
        if path in ("/admin", "/admin/"):
            path = "/admin.html"
        rel = urllib.parse.unquote(path).lstrip("/")
        if rel.startswith("static/"):
            rel = rel[len("static/"):]
        full = os.path.normpath(os.path.join(STATIC, rel))
        root = os.path.normpath(STATIC)
        if not (full == root or full.startswith(root + os.sep)):
            return self._send(403, b"forbidden", "text/plain; charset=utf-8", head_only)
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.isfile(full):
            if os.path.normpath(full) == os.path.join(root, "index.html"):
                return self._send(200, PLACEHOLDER, "text/html; charset=utf-8", head_only)
            return self._send(404, b"not found", "text/plain; charset=utf-8", head_only)
        ctype = MIME.get(os.path.splitext(full)[1].lower(), "application/octet-stream")
        try:
            with open(full, "rb") as f:
                data = f.read()
        except OSError:
            return self._send(404, b"not found", "text/plain; charset=utf-8", head_only)
        return self._send(200, data, ctype, head_only)

    # ---------------------------------------------------------------------------------------------------------------- SSE
    def _sse(self, event, data):
        self.wfile.write(f"event: {event}\ndata: {data}\n\n".encode("utf-8"))
        self.wfile.flush()

    def _stream(self):
        eng = self._engine()
        if eng is None:
            return None
        self.close_connection = True
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
        except OSError:
            return None
        with self.server._clients_lock:
            self.server.clients += 1
        period = 1.0 / self.server.hz
        seq = eng.seq
        try:
            self.wfile.write(b"retry: 1000\n\n")
            self._sse("snap", eng.snapshot_json())
            t = time.monotonic()
            next_snap, next_hb = t + period, t + 1.0
            while not self.server.stopping:
                if self.server.engine is not eng:          # rebuilt from the admin page: the page reconnects to the new one
                    break
                wait = max(0.0, min(next_snap, next_hb) - time.monotonic())
                evs, seq = eng.events_since(seq, wait)
                for ev in evs:
                    self._sse("ev", json.dumps(ev, separators=(",", ":"), allow_nan=False))
                now = time.monotonic()
                if now >= next_snap:
                    try:
                        snap = eng.snapshot_json()
                    except Exception as e:  # noqa: BLE001 - a bad snapshot must not kill the stream
                        print(f"[server] snapshot error: {type(e).__name__}: {engine.scrub(e)}", flush=True)
                        snap = None
                    if snap is not None:
                        self._sse("snap", snap)
                    next_snap += period
                    if next_snap < now:
                        next_snap = now + period
                if now >= next_hb:
                    self.wfile.write(b": hb\n\n")
                    self.wfile.flush()
                    next_hb = now + 1.0
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError, ValueError):
            pass                                     # the client went away (10053 / 10054 on Windows): just stop this stream
        finally:
            with self.server._clients_lock:
                self.server.clients -= 1
        return None


def state_dir_of(root):
    return os.path.join(root or os.path.dirname(os.path.abspath(engine.__file__)), "state")


def build_engine(args, root):
    """The feed + engine for the symbol saved on the admin page (state/admin.json laid over config.json)."""
    adm = admin.load(state_dir_of(root))
    cfg = engine.load_config(overrides=admin.overrides(adm))
    engine.configure_price(int(cfg.get("price_dp", 2)))
    import feeds                                     # every feed rounds to the symbol's grid - the live one too (EUR/USD: 5 decimals)
    feeds.configure_price(int(cfg.get("price_dp", 2)))
    feed = engine.make_feed(args.mode, seed=args.seed, speed=args.speed, file=args.file, record=args.record, config=cfg)
    eng = engine.Engine(feed, cfg=admin.overrides(adm), root=root, seed=args.seed, real_hours=True if args.real_hours else None)
    print(f"[server] symbol {cfg.get('symbol')} (profile {adm['active']}, price grid {cfg.get('price_dp', 2)} decimals, one coin = {cfg.get('coin_oz')})", flush=True)
    return eng


def main(argv=None):
    ap = argparse.ArgumentParser(description="Golden Gravity: The $1 Heist - game server")
    ap.add_argument("--mode", choices=["sim", "replay", "live"], default="sim")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--host", default=None)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--file", default=None, help="replay: recordings/X.jsonl")
    ap.add_argument("--record", action="store_true", help="live: record the feed to recordings/ (socket URLs stripped)")
    ap.add_argument("--root", default=None, help="directory holding rounds/ and state/ (default: next to server.py)")
    ap.add_argument("--real-hours", action="store_true", help="sim/replay: obey the real dead hours, weekend and session close")
    args = ap.parse_args(argv)

    cfg = engine.load_config()
    port = args.port or int(cfg.get("port", 8790))
    host = args.host or cfg.get("host", "127.0.0.1")
    if args.mode == "live" and os.environ.get("GG_FORBID_LIVE"):
        print("[server] --mode live refused: GG_FORBID_LIVE is set", flush=True)
        return 2
    try:
        httpd = GameServer((host, port), Handler, hz=cfg.get("snapshot_hz", 10))
    except OSError as e:
        print(f"[server] cannot listen on {host}:{port} ({e}). Is the game already running? Nothing was started.", flush=True)
        return 1
    root = os.path.abspath(args.root) if args.root else None
    if root:
        os.makedirs(root, exist_ok=True)
    httpd.args, httpd.root = args, root
    try:
        eng = build_engine(args, root)
    except SystemExit:
        httpd.server_close()
        raise
    except Exception as e:  # noqa: BLE001
        httpd.server_close()
        print(f"[server] could not build the {args.mode} feed: {type(e).__name__}: {engine.scrub(e)}", flush=True)
        return 1
    httpd.engine = eng
    eng.start()
    banner = {"live": "LIVE - REAL MONEY (PrimeXBT). The kill switch is K.", "sim": "SIM - synthetic market, simulated broker, pretend money.",
              "replay": "REPLAY - recorded frames, wooden rounds only."}[args.mode]
    print(f"[server] Golden Gravity on http://{host}:{port}/  mode={args.mode}  {banner}", flush=True)
    print(f"[server] rounds -> {eng.rounds_dir}   state -> {eng.state_dir}   shadow book: {eng.book_impl}", flush=True)
    try:
        httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("[server] stopping", flush=True)
    finally:
        httpd.stopping = True
        try:
            eng.stop()
        finally:
            httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
