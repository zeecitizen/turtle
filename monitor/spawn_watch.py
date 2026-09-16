"""spawn_watch.py — catch whatever keeps flashing a console window, and name its parent.

Zee, 2026-09-17: "there's a black window that comes and goes.. vanishes and rebuilds again
and again. its cloudflared.exe.. the command prompt is empty it says nothing" — and then,
after the first fix: "its repeatedly flashing still no".

The problem with chasing this by hand is that the evidence disappears. A window that lives
under a second leaves nothing behind: `tasklist` every 15s misses it, the daemon log only
records what the DAEMON did, and by the time anyone looks the process is gone. Two separate
hunts here found nothing — one 60s sample at 1Hz and one 90s watch at 4Hz, both clean, with
cloudflared's pid unchanged for twenty minutes.

So instead of looking harder, leave a trap. This polls the process table ~4x a second and
appends one line for every NEW process matching the watch list, together with the parent
that started it — which is the only fact that actually identifies the culprit. It costs
almost nothing and it can sit there for hours.

    py monitor/spawn_watch.py                 # watch cloudflared, log to monitor/
    py monitor/spawn_watch.py --match wt.exe  # watch something else
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

LOG = Path(__file__).parent / "spawn_watch.log"
PS = ["powershell", "-NoProfile", "-Command",
      "Get-CimInstance Win32_Process | "
      "Select-Object ProcessId,ParentProcessId,Name,CommandLine | "
      "ForEach-Object { \"$($_.ProcessId)|$($_.ParentProcessId)|$($_.Name)|$($_.CommandLine)\" }"]


def snap() -> dict:
    try:
        out = subprocess.run(PS, capture_output=True, text=True,
                             errors="replace", timeout=25).stdout
    except Exception:
        return {}
    procs = {}
    for line in out.splitlines():
        p = line.split("|", 3)
        if len(p) < 3:
            continue
        try:
            procs[int(p[0])] = (int(p[1]), p[2], p[3] if len(p) > 3 else "")
        except ValueError:
            continue
    return procs


def note(msg: str) -> None:
    line = "[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", default="cloudflared",
                    help="substring to watch for in the name or command line")
    ap.add_argument("--minutes", type=float, default=0,
                    help="0 = run until killed")
    args = ap.parse_args()
    want = args.match.lower()

    note("spawn_watch started — watching for %r" % want)
    prev = snap()
    if not prev:
        note("WARNING: could not read the process table; is powershell available?")
    t0 = time.time()
    seen = 0
    while args.minutes <= 0 or (time.time() - t0) < args.minutes * 60:
        cur = snap()
        if not cur:
            time.sleep(1)
            continue
        for pid, (ppid, name, cmd) in cur.items():
            if pid in prev:
                continue
            if want not in name.lower() and want not in cmd.lower():
                continue
            seen += 1
            par = prev.get(ppid) or cur.get(ppid)
            note("NEW %s pid=%d" % (name, pid))
            note("      cmd        : %s" % cmd[:160])
            note("      PARENT     : pid=%d %s" % (ppid, par[1] if par else "?"))
            note("      parent cmd : %s" % ((par[2] if par else "")[:160]))
        prev = cur
        time.sleep(0.25)
    note("spawn_watch finished — %d spawn(s) recorded" % seen)


if __name__ == "__main__":
    main()
