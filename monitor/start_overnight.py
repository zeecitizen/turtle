"""Start the overnight watchdog stack.

1. Restart Sheriff with the new dashboard + EA-staleness checks
2. Launch Patriarch (watches Sheriff itself)
3. Verify both alive
"""

import subprocess
import time
from pathlib import Path

import psutil

PY = r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"
DIR = Path(__file__).parent
SHERIFF = DIR / "sheriff_hawk.py"
PATRIARCH = DIR / "patriarch.py"
CREATE_NO_WINDOW = 0x08000000


def kill_named(keyword: str) -> list[int]:
    killed = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            cl = p.info["cmdline"] or []
            if any(keyword in str(x) for x in cl):
                p.terminate()
                try:
                    p.wait(timeout=3)
                except psutil.TimeoutExpired:
                    p.kill()
                killed.append(p.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return killed


def find_named(keyword: str) -> list[int]:
    pids = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            cl = p.info["cmdline"] or []
            if any(keyword in str(x) for x in cl):
                pids.append(p.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return pids


# 1. Restart Sheriff
killed = kill_named("sheriff_hawk")
print(f"killed sheriff PIDs: {killed}")
time.sleep(1)

subprocess.Popen(
    [PY, str(SHERIFF), "--loop"],
    cwd=str(DIR),
    creationflags=CREATE_NO_WINDOW,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    close_fds=True,
)
time.sleep(2)
print(f"sheriff alive: {find_named('sheriff_hawk')}")

# 2. Launch Patriarch (kill any old, then spawn fresh)
killed_pat = kill_named("patriarch")
print(f"killed patriarch PIDs: {killed_pat}")
time.sleep(1)

subprocess.Popen(
    [PY, str(PATRIARCH)],
    cwd=str(DIR),
    creationflags=CREATE_NO_WINDOW,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    close_fds=True,
)
time.sleep(2)
print(f"patriarch alive: {find_named('patriarch')}")

# 3. Final state
print("\n=== Final state ===")
print(f"sheriff:   {find_named('sheriff_hawk')}")
print(f"patriarch: {find_named('patriarch')}")
print(f"shano hawk: {find_named('shano_hawk')}")
