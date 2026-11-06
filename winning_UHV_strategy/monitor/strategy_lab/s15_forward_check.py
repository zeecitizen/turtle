"""s15_forward_check.py - Zee 2026-10-19 ("ok i agree"): the 15-min driver optimization was stopped by a PC restart at 15% (~1,500 passes).
Take its top N passes by Jan-Jun profit factor (opt_peek.py, read from the agents' logs) and run each on Jul 1 - Oct 16 - months the
search never judged on - in the MT5 Strategy Tester, random delay, $100k, 1 lot, on 7 rigs; plus plain v1.24 (= v1.23) as the yardstick.
The compare page's 10-month auto re-run is paused meanwhile (same rigs) and put back afterwards. Writes s15_forward.json.
    py s15_forward_check.py [N]
"""
import json
import queue
import random
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import axi_rig

HERE = Path(__file__).resolve().parent
EA = "Saad_strategy_15min"
RIGS = ["axi", "axi2", "axi3", "axi4", "axi5", "axi6", "axi7"]
API = "http://127.0.0.1:8772/api/year"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 30


def page(on=None):
    try:
        if on is None:
            return json.loads(urllib.request.urlopen(API, timeout=10).read())
        urllib.request.urlopen(urllib.request.Request(API, data=json.dumps({"auto": on}).encode(), method="POST",
                                                      headers={"Content-Type": "application/json"}), timeout=10).read()
    except Exception as e:
        print("page:", e, flush=True)
    return {}


subprocess.run([sys.executable, str(HERE / "opt_peek.py"), str(N)], cwd=HERE, capture_output=True)
top = json.load(open(HERE / "s15drv_peek.json"))
jobs = [("v1.23 / v1.24 defaults", {})] + [(f"pass PF {r['pf_jan_jun']:.2f}", {k: r[k] for k in r if k.startswith("Inp")}) for r in top]
t0 = time.time()
while page().get("running") and time.time() - t0 < 1800:
    time.sleep(10)
page(False)
print(f"page paused; {len(jobs)} runs on {len(RIGS)} rigs", flush=True)
q = queue.Queue()
for i, j in enumerate(jobs):
    q.put((i, j))
res, lock = {}, threading.Lock()


def worker(rig):
    axi_rig.kill_rig(rig)
    axi_rig.compile_ea(EA, rig=rig)
    while True:
        try:
            i, (name, p) = q.get_nowait()
        except queue.Empty:
            return
        s = {"InpMaxRiskUsd": "20", "InpLogCsv": "false"} if p else {"InpLogCsv": "false"}
        s.update({k: ("true" if v is True else "false" if v is False else str(v)) for k, v in p.items()})
        for a in range(3):
            r = axi_rig.run(EA, "XAUUSD_BB", "M15", s, frm="2026.07.01", to="2026.10.17", deposit=100000, rig=rig, tag="s15fwd", exec_mode=-1)
            if r.get("error") not in ("authorization failed", "no report"):
                break
            axi_rig.kill_rig(rig); time.sleep(3 + random.random() * 5)
        ts = r.get("trade_stats") or {}
        n, aw, al, net = ts.get("n") or 0, ts.get("avg_win") or 0, ts.get("avg_loss") or 0, r.get("net") or 0
        wr = 100 * ((net + n * -al) / (aw - al)) / n if n and aw - al else 0
        with lock:
            res[i] = {"name": name, "pass": p, "pf_jan_jun": top[i - 1]["pf_jan_jun"] if i else None, "net": net, "pf": float(r.get("pf") or 0),
                      "wr": wr, "n": n, "dd": r.get("dd"), "months": r.get("months"), "err": r.get("error")}
            json.dump([res[k] for k in sorted(res)], open(HERE / "s15_forward.json", "w"), indent=1)
            m = res[i]["months"] or {}
            print(f"[{len(res)}/{len(jobs)}] {name}: Jul-Oct net {net:+,.0f} PF {res[i]['pf']:.2f} WR {wr:.0f}% trades {n} | "
                  + " ".join(f"{k[5:]}:{v:+,.0f}" for k, v in m.items()), flush=True)


ths = []
for rig in RIGS:
    t = threading.Thread(target=worker, args=(rig,)); t.start(); ths.append(t); time.sleep(5)
[t.join() for t in ths]
page(True)
print("DONE - page auto re-run back on", flush=True)
