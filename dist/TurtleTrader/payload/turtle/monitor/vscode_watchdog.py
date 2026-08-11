"""
VSCode Watchdog — relaunches VS Code when it dies.

Why: VSCode auto-applies pending updates by closing the app. If you're
away from the keyboard, you come back to a closed editor. This daemon
detects that and brings it back.

Behavior:
  * Polls every 15s for any Code.exe process
  * "Sees" VSCode at least once before it's allowed to relaunch
    (avoids forcing VSCode open if you've never started it this session)
  * After Code.exe disappears, waits GRACE_SECONDS to let updates settle,
    then relaunches with the last workspace
  * Cooldown of RELAUNCH_COOLDOWN seconds between relaunches —
    prevents thrashing if the launch itself fails repeatedly
  * Shuts down cleanly on SIGTERM

Log: monitor/vscode_watchdog.log
"""

from __future__ import annotations
import os
import sys
import time
import subprocess
import signal
from datetime import datetime
from pathlib import Path

VSCODE_EXE = r"C:\Program Files\Microsoft VS Code\Code.exe"
DEFAULT_WORKSPACE = r"C:\Users\zeesh\Documents\GitHub\turtle"
LOG_FILE = Path(__file__).parent / "vscode_watchdog.log"

POLL_SECONDS = 15
GRACE_SECONDS = 30          # wait this long after VSCode dies before relaunch (let updates settle)
RELAUNCH_COOLDOWN = 300     # min seconds between relaunch attempts


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except OSError:
        pass


def vscode_running() -> bool:
    try:
        import psutil
    except ImportError:
        log("psutil missing — cannot detect VSCode; idling")
        return True  # fail-safe: pretend it's running so we don't spawn

    for proc in psutil.process_iter(["name"]):
        try:
            if (proc.info.get("name") or "").lower() == "code.exe":
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def launch_vscode() -> bool:
    if not Path(VSCODE_EXE).exists():
        log(f"vscode exe not found at {VSCODE_EXE}; cannot relaunch")
        return False

    args = [VSCODE_EXE]
    if Path(DEFAULT_WORKSPACE).exists():
        args.append(DEFAULT_WORKSPACE)

    # DETACHED_PROCESS replaces CREATE_NO_WINDOW (2026-05-05 fix):
    # CREATE_NO_WINDOW caused Code.exe launcher stub to detect "headless" context
    # and exit before spawning Electron children. DETACHED_PROCESS detaches without
    # blocking GUI startup — child outlives this watchdog.
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    try:
        proc = subprocess.Popen(
            args,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        log(f"relaunched VSCode (pid {proc.pid}) with workspace {DEFAULT_WORKSPACE}")
        return True
    except Exception as e:
        log(f"relaunch failed: {e}")
        return False


_should_stop = False


def _handle_term(_sig, _frm):
    global _should_stop
    _should_stop = True
    log("received SIGTERM; shutting down")


def main():
    if sys.platform == "win32":
        try:
            signal.signal(signal.SIGTERM, _handle_term)
            signal.signal(signal.SIGINT, _handle_term)
        except Exception:
            pass

    log(f"vscode watchdog starting; poll={POLL_SECONDS}s grace={GRACE_SECONDS}s cooldown={RELAUNCH_COOLDOWN}s")

    seen_running = False
    last_relaunch_ts = 0.0
    death_first_seen_ts: float | None = None

    while not _should_stop:
        try:
            running = vscode_running()
        except Exception as e:
            log(f"poll failed: {e}")
            time.sleep(POLL_SECONDS)
            continue

        if running:
            if not seen_running:
                log("VSCode detected — watchdog now armed")
                seen_running = True
            death_first_seen_ts = None
        else:
            if seen_running:
                # VSCode was up, now isn't
                if death_first_seen_ts is None:
                    death_first_seen_ts = time.time()
                    log(f"VSCode disappeared; grace period starts ({GRACE_SECONDS}s)")
                else:
                    waited = time.time() - death_first_seen_ts
                    if waited >= GRACE_SECONDS:
                        cooldown_left = RELAUNCH_COOLDOWN - (time.time() - last_relaunch_ts)
                        if cooldown_left > 0:
                            log(f"cooldown active ({int(cooldown_left)}s remaining) — skipping relaunch")
                        else:
                            if launch_vscode():
                                last_relaunch_ts = time.time()
                                # don't re-arm seen_running until the new instance is detected
                                death_first_seen_ts = None
            # if !seen_running and !running, watchdog stays disarmed (initial state)

        time.sleep(POLL_SECONDS)

    log("watchdog exited")


if __name__ == "__main__":
    main()
