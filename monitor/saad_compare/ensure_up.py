"""ensure_up.py - bring the Saad compare page (http://127.0.0.1:8772) up, and keep it up.

Zee 2026-10-16: "if the server etc is not running. the page doesnot goto not opening ... how will we respawn it? maybe
create a python startup script that can be called on computer restart by claude to bring things up"

A browser cannot show anything at 127.0.0.1:8772 while nothing listens there, so the page cannot start itself.
This script is the one entry point - safe to run any number of times:

    py ensure_up.py              # start server.py if the port is down (no console window), wait until it answers
    py ensure_up.py --open       # ... and open the page in the browser   (start_compare_page.bat does this)
    py ensure_up.py --watch      # stay running, restart the server within 20 s if it ever dies
    py ensure_up.py --install    # start "--watch" at every Windows logon (Startup folder entry), and start it now
    py ensure_up.py --uninstall  # remove the logon entry
    py ensure_up.py --status     # print whether the page and the live candle bridge are running

The live candle bridge (tv_bars_bridge.py --live) is NOT started here: it needs TradingView open on
BLUEBERRY:XAUUSD 1 min, and only matters while Saad_strategy_1min trades live (start_tv_bars_bridge.bat).
"""
import argparse
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
PORT = 8772
URL = f"http://127.0.0.1:{PORT}/"
PYW = Path(sys.executable).with_name("pythonw.exe")
LOG = HERE / "server.log"
STARTUP = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "saad_compare_page.vbs"
NO_WINDOW = 0x08000000 | 0x00000008          # CREATE_NO_WINDOW | DETACHED_PROCESS


def up():
    try:
        with urllib.request.urlopen(URL + "api/state", timeout=3) as r:
            return r.status == 200
    except Exception:
        # busy (a long MT5 run holds the lock but still answers) or down: fall back to "is the port open"
        with socket.socket() as s:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", PORT)) == 0


def start():
    if up():
        return False
    exe = PYW if PYW.exists() else Path(sys.executable)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} starting server.py\n")
    log = open(LOG, "a", encoding="utf-8")
    subprocess.Popen([str(exe), str(HERE / "server.py")], cwd=str(HERE), stdout=log, stderr=log,
                     stdin=subprocess.DEVNULL, creationflags=NO_WINDOW, close_fds=True)
    for _ in range(40):
        time.sleep(0.5)
        if up():
            return True
    raise SystemExit(f"server.py did not come up on {URL} - see {LOG}")


def watch(every=20):
    while True:
        try:
            if start():
                print(f"{time.strftime('%H:%M:%S')} restarted {URL}", flush=True)
        except SystemExit as e:
            print(e, flush=True)
        time.sleep(every)


def bridge_running():
    cmd = ("Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | Where-Object { $_.CommandLine -like '*tv_bars_bridge*--live*' } "
           "| Select-Object -ExpandProperty ProcessId")
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=60).stdout.strip()


def install():
    exe = PYW if PYW.exists() else Path(sys.executable)
    # a .vbs runs pythonw with no window flashing at logon
    STARTUP.write_text(f'CreateObject("WScript.Shell").Run """{exe}"" ""{Path(__file__).resolve()}"" --watch", 0, False\r\n', encoding="utf-8")
    subprocess.Popen([str(exe), str(Path(__file__).resolve()), "--watch"], cwd=str(HERE), creationflags=NO_WINDOW, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"installed: {STARTUP}\nthe watcher is running now and will start at every logon -> {URL}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for a in ("open", "watch", "install", "uninstall", "status"):
        ap.add_argument("--" + a, action="store_true")
    a = ap.parse_args()
    if a.uninstall:
        STARTUP.unlink(missing_ok=True)
        print(f"removed {STARTUP} (a watcher already running keeps going until logoff)")
    elif a.install:
        install()
    elif a.status:
        print(f"page {URL}: {'UP' if up() else 'DOWN'}")
        print(f"logon entry: {'installed' if STARTUP.exists() else 'not installed'} ({STARTUP})")
        b = bridge_running()
        print(f"live candle bridge: {'running, pid ' + b.split()[0] if b else 'not running (start_tv_bars_bridge.bat, only for live trading)'}")
    elif a.watch:
        watch()
    else:
        print(f"{URL}: {'started' if start() else 'already up'}")
        if a.open:
            webbrowser.open(URL)
