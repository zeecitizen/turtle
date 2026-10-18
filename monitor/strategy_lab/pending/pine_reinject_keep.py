"""Re-inject pine/saad_15min.pine without losing the chart's settings (code-only change, no new inputs):
pause the page's 10-month auto re-run, snapshot every setting by position, inject, put back anything that moved, resume."""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_compare")
import server  # noqa: E402

ROOT = Path(r"C:\Users\zeesh\turtle")


def year_auto(on):
    req = urllib.request.Request("http://127.0.0.1:8772/api/year", data=json.dumps({"auto": on}).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


year_auto(False)
try:
    st = server.tv_eval(server.JS_STUDY)
    names = server.pine_inputs()
    assert len(names) == len(st["values"]), (len(names), len(st["values"]))
    before = dict(zip(names, st["values"]))
    json.dump({"symbol": st["symbol"], "res": st["res"], "values": st["values"], "by_name": before},
              open(ROOT / "monitor/strategy_lab/pending/pre_reinject_snapshot.json", "w"), indent=1)
    server.tv("pine", "open", "Saad Strategy v3.20")
    time.sleep(3)
    r = subprocess.run([sys.executable, str(ROOT / "pine/inject_pine.py"), str(ROOT / "pine/saad_15min.pine"), "--force"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    print(r.stdout[-1500:], r.stderr[-800:])
    time.sleep(6)
    st2 = server.tv_eval(server.JS_STUDY)
    now = dict(zip(names, st2["values"]))
    moved = [k for k in names if now.get(k) != before[k]]
    for k in moved:
        server.set_input(st2["id"], names.index(k), before[k])
    time.sleep(4)
    final = dict(zip(names, server.tv_eval(server.JS_STUDY)["values"]))
    print("settings moved by the inject:", moved, "| still different:", [k for k in names if final.get(k) != before[k]])
finally:
    year_auto(True)
