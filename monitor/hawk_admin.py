"""Admin operations on shano_hawk: kill all instances, dedupe, fix state, restart.

Usage:
    python hawk_admin.py status
    python hawk_admin.py dedupe
    python hawk_admin.py reset_pnl  # resync session_pnl with shano_status.py confirmed value
    python hawk_admin.py restart
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import psutil

HAWK_SCRIPT = Path(r"c:\Users\zeesh\Documents\GitHub\turtle\monitor\shano_hawk.py")
STATUS_SCRIPT = Path(r"c:\Users\zeesh\Documents\GitHub\turtle\monitor\shano_status.py")
STATE_FILE = Path(r"c:\Users\zeesh\Documents\GitHub\turtle\monitor\.shano_state.json")
PYTHON = Path(r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe")
CREATE_NO_WINDOW = 0x08000000


def find_hawks():
    pids = []
    for p in psutil.process_iter(['pid', 'cmdline']):
        try:
            cl = p.info['cmdline'] or []
            if any('shano_hawk' in str(x) for x in cl):
                pids.append(p.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return pids


def kill_all_hawks():
    killed = []
    for pid in find_hawks():
        try:
            p = psutil.Process(pid)
            p.terminate()
            try:
                p.wait(timeout=3)
            except psutil.TimeoutExpired:
                p.kill()
            killed.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return killed


def start_hawk():
    proc = subprocess.Popen(
        [str(PYTHON), str(HAWK_SCRIPT)],
        cwd=str(HAWK_SCRIPT.parent),
        creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.pid


def get_confirmed_pnl():
    out = subprocess.check_output([str(PYTHON), str(STATUS_SCRIPT)], text=True)
    return json.loads(out)


def cmd_status():
    print(f"Hawks alive: {find_hawks()}")
    s = get_confirmed_pnl()
    print(f"Confirmed today: ${s['today_realized']} ({s['trades_closed']} trades)")
    if STATE_FILE.exists():
        st = json.loads(STATE_FILE.read_text())
        print(f"State session_pnl=${st.get('session_pnl', 0)} wins={st.get('session_wins', 0)} "
              f"losses={st.get('session_losses', 0)} trades={st.get('session_trades', 0)}")


def cmd_dedupe():
    pids = find_hawks()
    if len(pids) <= 1:
        print(f"OK — only {len(pids)} hawk running")
        return
    killed = kill_all_hawks()
    print(f"Killed {len(killed)} hawks: {killed}")
    time.sleep(1)
    new = start_hawk()
    print(f"Started 1 fresh hawk: PID {new}")
    time.sleep(2)
    print(f"Hawks alive now: {find_hawks()}")


def cmd_reset_pnl():
    s = get_confirmed_pnl()
    correct = s["today_realized"]
    correct_count = s["trades_closed"]
    if not STATE_FILE.exists():
        print("STATE_FILE missing — nothing to reset")
        return
    st = json.loads(STATE_FILE.read_text())
    before = (st.get("session_pnl"), st.get("session_wins"), st.get("session_losses"), st.get("session_trades"))
    st["session_pnl"] = correct
    st["session_wins"] = correct_count
    st["session_losses"] = 0
    st["session_trades"] = correct_count
    STATE_FILE.write_text(json.dumps(st, indent=2))
    after = (st["session_pnl"], st["session_wins"], st["session_losses"], st["session_trades"])
    print(f"Reset session counters")
    print(f"  Before: pnl=${before[0]} W={before[1]} L={before[2]} trades={before[3]}")
    print(f"  After:  pnl=${after[0]} W={after[1]} L={after[2]} trades={after[3]}")


def cmd_restart():
    cmd_dedupe()


COMMANDS = {
    "status": cmd_status,
    "dedupe": cmd_dedupe,
    "reset_pnl": cmd_reset_pnl,
    "restart": cmd_restart,
}


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    cmd = args[0]
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}\n\n{__doc__}")
        sys.exit(1)
    COMMANDS[cmd]()


if __name__ == "__main__":
    main()
