"""node_keepalive.py — Auto-restart dashboard Node.js if it dies.

Runs every minute via Windows Task Scheduler. Checks if http://localhost:3457
responds within 3 seconds. If not, kills any zombie node.exe with server.js
in its command line and relaunches a fresh hidden Node process.

Designed to be silent on the happy path (just appends to .keepalive.log).
On restart, logs the event + writes a single-line marker for the dashboard
status card.
"""
import sys, os, subprocess, time, json
from pathlib import Path
from urllib import request as urlreq
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")

SERVER_PORT = 3457
SERVER_URL  = f"http://localhost:{SERVER_PORT}/api/status"   # cheap, fast endpoint
SERVER_DIR  = r"C:\Users\zeesh\Documents\GitHub\turtle\dashboard\claude_trader"
LOG         = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\.keepalive.log")
LATEST      = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\.keepalive_latest.json")
TIMEOUT_SEC = 3


def log_line(msg: str):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        ts = datetime.now(timezone.utc).isoformat()
        f.write(f"{ts} {msg}\n")


def server_alive() -> bool:
    try:
        urlreq.urlopen(SERVER_URL, timeout=TIMEOUT_SEC).read(100)
        return True
    except Exception:
        return False


def kill_zombies():
    """Kill any node.exe processes running server.js."""
    try:
        # Use WMIC to find node.exe processes with server.js in cmdline
        out = subprocess.run(
            ["wmic", "process", "where",
             "(name='node.exe' and commandline like '%server.js%')",
             "get", "processid", "/format:value"],
            capture_output=True, text=True, timeout=10,
        ).stdout
        pids = [line.split("=")[1].strip()
                for line in out.splitlines() if line.startswith("ProcessId=") and line.split("=")[1].strip()]
        for p in pids:
            subprocess.run(["taskkill", "/F", "/PID", p],
                           capture_output=True, timeout=5)
        if pids:
            log_line(f"killed zombie node.exe PIDs: {pids}")
        time.sleep(2)
    except Exception as e:
        log_line(f"kill_zombies failed: {e}")


def start_node():
    """Launch hidden node server.js."""
    # DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP so it survives our exit
    DETACHED = 0x00000008
    NEW_GRP  = 0x00000200
    creationflags = DETACHED | NEW_GRP
    try:
        # Use 'node' from PATH; SERVER_DIR is the cwd
        subprocess.Popen(
            ["node", "server.js"],
            cwd=SERVER_DIR,
            creationflags=creationflags,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        log_line("started node server.js")
        return True
    except Exception as e:
        log_line(f"start_node failed: {e}")
        return False


def write_latest(state: str, detail: str = ""):
    LATEST.parent.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps({
        "now_utc": datetime.now(timezone.utc).isoformat(),
        "state": state,           # "ok" or "restarted" or "down"
        "detail": detail,
    }, indent=2))


def main():
    if server_alive():
        write_latest("ok", "node responding on :3457")
        return 0

    # Server is down — restart it
    log_line("server NOT responding — restarting")
    kill_zombies()
    if not start_node():
        write_latest("down", "start_node failed")
        return 1

    # Verify it came back
    for _ in range(15):   # 15 × 1s = 15s max
        time.sleep(1)
        if server_alive():
            write_latest("restarted", "node restarted successfully")
            log_line("server BACK online")
            return 0

    write_latest("down", "node restarted but not responding")
    log_line("server STILL down after restart")
    return 2


if __name__ == "__main__":
    sys.exit(main())
