"""chain_after_selftune.py - 2026-10-19: one MT5 job at a time (an optimizer's 8 agents + the page's 6 rigs run the 15.6 GB laptop out
of memory). Waits for the 15-min self-tuner (selftune.out "SELFTUNE DONE"), lets the compare page finish the 10-month batch it starts
when its auto re-run comes back, then - with that auto re-run paused - runs Zee's 15-min driver optimization (saad15_driver_search.py),
then the paused M5 defended search (saad_m5_defended_search.py), then switches the page's auto re-run back on. Log: chain.out"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "http://127.0.0.1:8772/api/year"


def log(s):
    print(time.strftime("%H:%M:%S"), s, flush=True)


def year_state():
    try:
        return json.loads(urllib.request.urlopen(API, timeout=10).read())
    except Exception:
        return {}


def year_auto(on):
    try:
        urllib.request.urlopen(urllib.request.Request(API, data=json.dumps({"auto": on}).encode(), method="POST",
                                                      headers={"Content-Type": "application/json"}), timeout=10).read()
    except Exception as e:
        log(f"page: {e}")


while "SELFTUNE DONE" not in (HERE / "selftune.out").read_text(encoding="utf-8", errors="ignore"):
    time.sleep(30)
log("self-tuner done; letting the page's 10-month batch run")
time.sleep(20)                                   # the page's watcher needs two 2-s polls to start a batch
t0 = time.time()
while year_state().get("running") and time.time() - t0 < 1800:
    time.sleep(10)
year_auto(False)
time.sleep(5)
log(f"page idle (running={year_state().get('running')}), auto re-run paused")
try:
    for script in ("saad15_driver_search.py", "saad_m5_defended_search.py"):
        log(f"start {script}")
        r = subprocess.run([sys.executable, str(HERE / script)], cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        (HERE / (Path(script).stem + ".out")).write_text(r.stdout + r.stderr, encoding="utf-8")
        log(f"done {script} (exit {r.returncode})")
finally:
    year_auto(True)
    log("CHAIN DONE - page auto re-run back on")
