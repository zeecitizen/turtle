"""Patriarch — minimal watchdog that watches Sheriff.

Sheriff watches everything else, but if Sheriff itself dies, no one revives it.
Patriarch is a tiny loop with one job: poll for sheriff_hawk.py every 60 seconds,
and if it's missing, launch it again. Patriarch must be small and bulletproof.

Crash budget: zero. Failure modes:
- psutil import error → skip cycle, retry
- subprocess.Popen error → log, skip cycle
- All other errors → catch, log, continue

Logs to monitor/patriarch.log (rotating monthly basis manually).
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

PYTHON = r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"
SCRIPT_DIR = Path(__file__).parent
SHERIFF = SCRIPT_DIR / "sheriff_hawk.py"
LOG = SCRIPT_DIR / "patriarch.log"
CHECK_INTERVAL = 60  # seconds

CREATE_NO_WINDOW = 0x08000000


def log(msg: str):
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n"
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    try:
        print(line.rstrip(), flush=True)
    except Exception:
        pass


def is_sheriff_alive() -> bool:
    try:
        import psutil
        for p in psutil.process_iter(["cmdline"]):
            try:
                cl = p.info["cmdline"] or []
                if any("sheriff_hawk" in str(x) for x in cl):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    except Exception as e:
        log(f"is_sheriff_alive: psutil error {e}, assuming alive")
        return True  # Conservative: don't spawn duplicates on uncertainty


def start_sheriff():
    if not SHERIFF.exists():
        log(f"sheriff_hawk.py missing at {SHERIFF}")
        return False
    try:
        subprocess.Popen(
            [PYTHON, str(SHERIFF), "--loop"],
            cwd=str(SCRIPT_DIR),
            creationflags=CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        log("Sheriff RELAUNCHED by Patriarch")
        return True
    except Exception as e:
        log(f"start_sheriff failed: {e}")
        return False


def main():
    log("=== Patriarch starting ===")
    log(f"Watching sheriff_hawk every {CHECK_INTERVAL}s")
    misses = 0
    while True:
        try:
            if is_sheriff_alive():
                if misses > 0:
                    log(f"Sheriff back alive (was missing {misses} cycles)")
                misses = 0
            else:
                misses += 1
                log(f"Sheriff DEAD (cycle {misses}) — relaunching")
                start_sheriff()
                time.sleep(5)  # give it a moment to spawn
        except Exception as e:
            log(f"main loop error: {e}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
