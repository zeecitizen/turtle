"""
UhvSweep AutoTrading Watchdog — alerts when the EA heartbeat goes stale.

Why: UhvSweepExhaustion writes uhv_sweep_state.json every ~5s while attached
and AutoTrading is enabled. If that file stops updating, one of three things
broke: (a) EA detached from chart, (b) MT5 AutoTrading toggled off,
(c) MT5 terminal crashed. All three need a human to fix — auto-toggling
AutoTrading via WM_COMMAND 32851 is unsafe because that message is a
*toggle*, not a setter, so blindly sending it could flip a healthy ON state
to OFF.

Behavior:
  * Polls heartbeat mtime every POLL_SECONDS
  * STALE_THRESHOLD: if mtime gap exceeds this, declare unhealthy
  * On first stale detection: WhatsApp alert + log
  * Re-alerts every REALERT_INTERVAL while still stale (prevents spam)
  * On recovery: log + WhatsApp "back online"
  * Tracks consecutive stale checks so a single missed write doesn't fire

Log: monitor/uhv_autotrade_watchdog.log
"""

from __future__ import annotations
import os
import sys
import time
import signal
import subprocess
from datetime import datetime
from pathlib import Path

HEARTBEAT_FILE = Path(
    os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")
) / "MetaQuotes" / "Terminal" / "Common" / "Files" / "uhv_sweep_state.json"

LOG_FILE = Path(__file__).parent / "uhv_autotrade_watchdog.log"
WHATSAPP_SCRIPT = Path(__file__).parent / "whatsapp_alert.py"

POLL_SECONDS       = 30
STALE_THRESHOLD    = 90      # mtime gap before declaring stale (EA writes every ~5s)
CONSECUTIVE_STALE  = 2       # require N consecutive stale polls before alerting
REALERT_INTERVAL   = 600     # re-send alert every 10min while stale
ZEE_CHAT           = "4915119175329@c.us"


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except OSError:
        pass


def heartbeat_age() -> float | None:
    """Returns seconds since last heartbeat, or None if file missing."""
    try:
        mtime = HEARTBEAT_FILE.stat().st_mtime
        return time.time() - mtime
    except FileNotFoundError:
        return None
    except OSError as e:
        log(f"stat failed: {e}")
        return None


def send_whatsapp(msg: str):
    """Fire-and-forget WhatsApp notification to Zee."""
    if not WHATSAPP_SCRIPT.exists():
        log("whatsapp_alert.py not found; alert skipped")
        return
    try:
        py = sys.executable
        # Use a minimal inline send via broadcast/_send_single to bypass argparse
        code = (
            "import sys; sys.path.insert(0, r'%s'); "
            "from whatsapp_alert import _send_single; "
            "_send_single(%r, %r)"
        ) % (str(WHATSAPP_SCRIPT.parent), msg, ZEE_CHAT)
        subprocess.Popen(
            [py, "-c", code],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except Exception as e:
        log(f"whatsapp dispatch failed: {e}")


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

    log(f"watchdog starting; heartbeat={HEARTBEAT_FILE}")
    log(f"poll={POLL_SECONDS}s stale_threshold={STALE_THRESHOLD}s realert={REALERT_INTERVAL}s")

    consecutive_stale = 0
    is_alerting = False
    last_alert_ts = 0.0
    seen_alive_once = False

    while not _should_stop:
        age = heartbeat_age()

        if age is None:
            consecutive_stale += 1
            log(f"heartbeat file missing (consecutive={consecutive_stale})")
        elif age > STALE_THRESHOLD:
            consecutive_stale += 1
            log(f"heartbeat stale: {age:.1f}s old (consecutive={consecutive_stale})")
        else:
            # Healthy
            if is_alerting:
                msg = (
                    f"UhvSweep watchdog: heartbeat restored ({age:.0f}s old). "
                    f"EA is writing state again."
                )
                log("heartbeat recovered; clearing alert state")
                send_whatsapp(msg)
                is_alerting = False
            if not seen_alive_once:
                log(f"first healthy heartbeat seen ({age:.1f}s old) — watchdog armed")
                seen_alive_once = True
            consecutive_stale = 0

        # Alert logic: only after we've seen the EA alive at least once
        # (otherwise we'd fire alerts when the watchdog starts before MT5)
        if seen_alive_once and consecutive_stale >= CONSECUTIVE_STALE:
            now = time.time()
            should_alert = (not is_alerting) or (now - last_alert_ts >= REALERT_INTERVAL)
            if should_alert:
                if age is None:
                    detail = "heartbeat file missing entirely"
                else:
                    detail = f"heartbeat {age:.0f}s old (>{STALE_THRESHOLD}s threshold)"
                msg = (
                    f"UhvSweep watchdog: EA NOT WRITING — {detail}. "
                    f"Check (1) chart has EA attached, (2) AutoTrading button is green, "
                    f"(3) MT5 terminal is running."
                )
                log(f"ALERT: {detail}")
                send_whatsapp(msg)
                is_alerting = True
                last_alert_ts = now

        time.sleep(POLL_SECONDS)

    log("watchdog exited")


if __name__ == "__main__":
    main()
