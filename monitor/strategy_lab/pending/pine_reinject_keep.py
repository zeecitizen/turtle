"""Re-inject pine/saad_15min.pine without losing the chart's settings: snapshot every setting by position (names from the version
in git HEAD, so NEW inputs added at the end are fine), inject, put every old setting back by name. The page's 10-month auto re-run
is paused meanwhile and put back the way it WAS (2026-10-19: forcing it on started 6 rigs beside a running optimizer)."""
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_compare")
import server  # noqa: E402

ROOT = Path(r"C:\Users\zeesh\turtle")
API = "http://127.0.0.1:8772/api/year"


def year_auto(on=None):
    try:
        if on is None:
            return json.loads(urllib.request.urlopen(API, timeout=10).read()).get("auto")
        urllib.request.urlopen(urllib.request.Request(API, data=json.dumps({"auto": on}).encode(), method="POST",
                                                      headers={"Content-Type": "application/json"}), timeout=10).read()
    except Exception as e:
        print("page:", e)


was = year_auto()
year_auto(False)
try:
    old_src = subprocess.run(["git", "show", "HEAD:pine/saad_15min.pine"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    old_names = re.findall(r"^(\w+)\s*=\s*input\.", old_src, re.M)
    st = server.tv_eval(server.JS_STUDY)
    assert len(old_names) == len(st["values"]), (len(old_names), len(st["values"]))
    before = dict(zip(old_names, st["values"]))
    json.dump({"symbol": st["symbol"], "res": st["res"], "values": st["values"], "by_name": before},
              open(ROOT / "monitor/strategy_lab/pending/pre_reinject_snapshot.json", "w"), indent=1)
    try:
        server.tv("pine", "open", "Saad Strategy v3.20")
    except RuntimeError as e:            # 2026-10-19: editor already docked open on the right -> "Could not open"; inject_pine checks the script itself
        print("pine open:", str(e)[-120:])
    time.sleep(3)
    r = subprocess.run([sys.executable, str(ROOT / "pine/inject_pine.py"), str(ROOT / "pine/saad_15min.pine"), "--force"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    print(r.stdout[-1500:], r.stderr[-800:])
    time.sleep(6)
    names = server.pine_inputs()
    st2 = server.tv_eval(server.JS_STUDY)
    assert len(names) == len(st2["values"]), ("chart has", len(st2["values"]), "file has", len(names))
    now = dict(zip(names, st2["values"]))
    moved = [k for k in old_names if now.get(k) != before[k]]
    for k in moved:
        server.set_input(st2["id"], names.index(k), before[k])
    time.sleep(4)
    final = dict(zip(names, server.tv_eval(server.JS_STUDY)["values"]))
    print("settings moved by the inject:", moved, "| still different:", [k for k in old_names if final.get(k) != before[k]],
          "| new settings:", {k: final[k] for k in names if k not in before})
finally:
    if was is not None:
        year_auto(bool(was))
