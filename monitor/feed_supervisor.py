"""feed_supervisor.py — restart a dead feed instead of noticing it died.

2026-08-10, third stall in three days. Gold went 253 minutes stale straight through the
Sunday reopen, then 137 minutes again while the overnight work ran. Each time the fix
was the same: kill it, start it, watch it come back in seconds.

The watchdog added on 08-09 printed a warning. The self-heal added at 03:30 made the
process exit on six dead polls. Both were improvements and neither is enough, because
NOTHING WAS LISTENING for the exit — a bridge that dies cleanly is still a bridge that
is dead, and the health checks all say ALIVE because the file exists.

So this one does the only thing that actually helps: it checks the age of the output
file and, if the market should be open and the file has stopped moving, it restarts the
bridge itself.

    py monitor/feed_supervisor.py            # check once
    py monitor/feed_supervisor.py --loop 120 # supervise
"""
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PY = r"C:/Users/zeesh/AppData/Local/Programs/Python/Python313-arm64/python.exe"
ROOT = Path(__file__).parent.parent
COMMON = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")

FEEDS = [
    # name,      output file,      script,                       stale after (s)
    ("gold", COMMON / "oanda_m1.csv", ROOT / "monitor/oanda_bridge.py", 600),
    ("btc",  COMMON / "btc_m1.csv",   ROOT / "BTCUSD/binance_bridge.py", 600),
    # 2026-08-10: the BRAIN can hang too, and did — oanda_live_matcher sat alive but
    # silent for 2.6 days while gold traded. Every health check said ALIVE because the
    # process existed. It writes a heartbeat now, and this watches the heartbeat rather
    # than the process. A daemon is only alive if it is producing something.
    ("brain", COMMON / "matcher_heartbeat.txt",
     ROOT / "monitor/oanda_live_matcher.py", 900),
]


def web_alive():
    """claudezeeshan.com is served by dashboard/claude_trader/server.js on port 3457.

    2026-08-11: it was dead for a day and the site answered 502, because I killed every
    node process matching "server.js" to restart the dashboard — and there are TWO of
    them. dashboard/server.js (port 3456) came back; claude_trader/server.js (3457),
    which is the one the Cloudflare tunnel actually points at, did not.

    Zee's standing rule is that every meaningful change must be visible on
    claudezeeshan.com, so a dead 3457 makes all of it invisible. This restarts it.
    """
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:3457/", timeout=8)
        return True
    except Exception:
        pass
    print("[super] web: port 3457 DOWN (claudezeeshan.com would 502) — restarting", flush=True)
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Start-Process -WindowStyle Hidden -FilePath 'node' "
                    "-ArgumentList 'server.js' -WorkingDirectory "
                    f"'{ROOT / 'dashboard' / 'claude_trader'}'"],
                   capture_output=True, timeout=30)
    time.sleep(8)
    try:
        urllib.request.urlopen("http://localhost:3457/", timeout=8)
        print("[super] web: back up", flush=True)
        return True
    except Exception:
        print("[super] web: STILL DOWN — needs a look", flush=True)
        return False


def gold_market_open(now=None):
    """Gold sleeps from Friday 21:00 UTC to Sunday 21:00 UTC.

    Without this the supervisor would fight the weekend every two minutes, and a log
    full of false alarms is how the real one gets missed.
    """
    n = now or datetime.now(timezone.utc)
    wd, hh = n.weekday(), n.hour            # Mon=0 .. Sun=6
    if wd == 5:
        return False                         # Saturday
    if wd == 4 and hh >= 21:
        return False                         # Friday evening
    if wd == 6 and hh < 21:
        return False                         # Sunday before the reopen
    return True


def running(script_name):
    ps = ("Get-CimInstance Win32_Process -Filter \"Name like 'py%'\" | "
          f"Where-Object {{ $_.CommandLine -match '{script_name}' }} | "
          "Measure-Object | Select-Object -ExpandProperty Count")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=25)
        return int((r.stdout or "0").strip() or 0)
    except Exception:
        return 0


def restart(script):
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name like 'py%'\" | "
                    f"Where-Object {{ $_.CommandLine -match '{script.name}' }} | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }"],
                   capture_output=True, timeout=30)
    time.sleep(1)
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Start-Process -WindowStyle Hidden -FilePath '{PY}' "
                    f"-ArgumentList '-u','{script}','--loop','20' -WorkingDirectory '{ROOT}'"],
                   capture_output=True, timeout=30)


def check():
    web_alive()
    for name, out, script, limit in FEEDS:
        if name == "gold" and not gold_market_open():
            print(f"[super] {name}: market closed — not watching")
            continue
        age = (time.time() - os.path.getmtime(out)) / 60 if out.exists() else 9999
        alive = running(script.name)
        if age * 60 > limit:
            print(f"[super] {name}: {age:.0f} min stale (procs={alive}) — RESTARTING", flush=True)
            restart(script)
            time.sleep(12)
            new = (time.time() - os.path.getmtime(out)) / 60 if out.exists() else 9999
            print(f"[super] {name}: now {new:.1f} min old "
                  f"{'✓ recovered' if new * 60 < limit else '✗ STILL DEAD'}", flush=True)
        else:
            print(f"[super] {name}: {age:.1f} min old · ok (procs={alive})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0)
    a = ap.parse_args()
    while True:
        try:
            check()
        except Exception as e:
            print(f"[super] ERROR: {e}", flush=True)
        if not a.loop:
            break
        time.sleep(a.loop)
