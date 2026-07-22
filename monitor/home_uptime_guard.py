"""home_uptime_guard.py — MODULE 4 of the autopilot state machine.

Keeps https://claudezeeshan.com ALWAYS UP, even if the rest of the system failed.
Runs independently (hidden, no console window). Every cycle it:
  1. ensures the node dashboard server is listening on :3457 (else starts it),
  2. ensures cloudflared (tunnel zee-claude) is running (else starts it),
  3. periodically verifies the PUBLIC url resolves; if local is up but public is
     down, restarts cloudflared,
  4. writes monitor/.home_uptime_status.json (dashboard can show it) and, on a
     confirmed unrecoverable outage, monitor/.home_down_alert so Claude is INFORMED.

Launch hidden (no CMD flash):
    pythonw.exe monitor/home_uptime_guard.py
or via the Autopilot_Boot scheduled task at logon.
"""
from __future__ import annotations
import json, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:/Users/zeesh/Documents/GitHub/turtle")
NODE_CWD = REPO / "dashboard" / "claude_trader"
NODE_SERVER = "server.js"
CLOUDFLARED = r"C:/Program Files (x86)/cloudflared/cloudflared"
CF_CONFIG = r"C:/Users/zeesh/.cloudflared/config.yml"
LOCAL_URL = "http://localhost:3457/"
PUBLIC_URL = "https://claudezeeshan.com/"
STATUS_FILE = REPO / "monitor" / ".home_uptime_status.json"
ALERT_FILE = REPO / "monitor" / ".home_down_alert"
LOG_FILE = REPO / "monitor" / ".home_uptime_guard.log"

CHECK_EVERY_SEC = 30
PUBLIC_CHECK_EVERY = 6           # check public URL every 6th cycle (~3 min)
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
FLAGS = CREATE_NO_WINDOW | DETACHED_PROCESS


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg):
    line = f"{now()}  {msg}\n"
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def http_ok(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (home-guard)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


def proc_running(name):
    try:
        out = subprocess.run(["tasklist", "/fi", f"imagename eq {name}"],
                             capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        return name.lower() in out.stdout.lower()
    except Exception:
        return False


def start_node():
    try:
        subprocess.Popen(["node", NODE_SERVER], cwd=str(NODE_CWD),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=FLAGS, close_fds=True)
        log("started node dashboard server on :3457")
        return True
    except Exception as e:
        log(f"FAILED to start node: {e}")
        return False


def start_cloudflared():
    try:
        subprocess.Popen([CLOUDFLARED, "tunnel", "--config", CF_CONFIG, "run"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=FLAGS, close_fds=True)
        log("started cloudflared tunnel zee-claude")
        return True
    except Exception as e:
        log(f"FAILED to start cloudflared: {e}")
        return False


def write_status(local_up, cf_up, public_up, recovered):
    try:
        STATUS_FILE.write_text(json.dumps({
            "checked_utc": now(),
            "local_3457": local_up,
            "cloudflared": cf_up,
            "public_site": public_up,
            "recovered_this_cycle": recovered,
        }, indent=2), encoding="utf-8")
    except Exception:
        pass


def main():
    log("home_uptime_guard started")
    cycle = 0
    while True:
        cycle += 1
        recovered = False

        # 1. local node server
        local_up = http_ok(LOCAL_URL, timeout=5)
        if not local_up:
            log("local :3457 DOWN — restarting node")
            start_node(); recovered = True
            time.sleep(4)
            local_up = http_ok(LOCAL_URL, timeout=5)

        # 2. cloudflared process
        cf_up = proc_running("cloudflared.exe")
        if not cf_up:
            log("cloudflared DOWN — restarting")
            start_cloudflared(); recovered = True
            time.sleep(6)
            cf_up = proc_running("cloudflared.exe")

        # 3. public URL (periodic)
        public_up = None
        if cycle % PUBLIC_CHECK_EVERY == 0:
            public_up = http_ok(PUBLIC_URL, timeout=12)
            if not public_up and local_up:
                # local is fine but the edge can't reach us → cloudflared stale
                log("public DOWN but local UP — restarting cloudflared")
                try:
                    subprocess.run(["taskkill", "/f", "/im", "cloudflared.exe"],
                                   capture_output=True, creationflags=CREATE_NO_WINDOW)
                except Exception:
                    pass
                time.sleep(2)
                start_cloudflared(); recovered = True
                time.sleep(8)
                public_up = http_ok(PUBLIC_URL, timeout=12)

        write_status(local_up, cf_up, public_up, recovered)

        # 4. alert flag if still unrecoverable
        down = (not local_up) or (not cf_up) or (public_up is False)
        if down:
            try:
                ALERT_FILE.write_text(json.dumps({
                    "at_utc": now(), "local_up": local_up, "cf_up": cf_up,
                    "public_up": public_up,
                    "msg": "HOME DOWN — guard could not fully recover. Claude: investigate.",
                }), encoding="utf-8")
            except Exception:
                pass
            log(f"STILL DOWN: local={local_up} cf={cf_up} public={public_up}")
        else:
            if ALERT_FILE.exists():
                try: ALERT_FILE.unlink()
                except Exception: pass

        time.sleep(CHECK_EVERY_SEC)


if __name__ == "__main__":
    main()
