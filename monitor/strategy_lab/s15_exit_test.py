"""s15_exit_test.py - Zee 2026-10-19 "ok test it": Saad_strategy_15min v1.25 InpExitMode on the full year in MT5 (XAUUSD_BB M15, real ticks,
$100k, 1 lot, v1.23 settings). 0 = v1.23 exits, 1 = next EMA beyond the entry, 2 = close back across the slow EMA. Plus mode 0 without delay
(must equal v1.24: +$127,425.40 / 1,257 deals). The compare page's auto re-run is paused meanwhile. Writes s15_exit_test.json."""
import json
import random
import threading
import time
import urllib.request
from pathlib import Path

import axi_rig

HERE = Path(__file__).resolve().parent
API = "http://127.0.0.1:8772/api/year"
RUNS = [("mode 0, no delay (= v1.24?)", "0", 0, "axi"), ("v1.23 exits (mode 0)", "0", -1, "axi2"),
        ("next EMA beyond the entry (mode 1)", "1", -1, "axi3"), ("close back across the slow EMA (mode 2)", "2", -1, "axi4")]


def page(on=None):
    try:
        if on is None:
            return json.loads(urllib.request.urlopen(API, timeout=10).read())
        urllib.request.urlopen(urllib.request.Request(API, data=json.dumps({"auto": on}).encode(), method="POST",
                                                      headers={"Content-Type": "application/json"}), timeout=10).read()
    except Exception as e:
        print("page:", e, flush=True)
    return {}


t0 = time.time()
while page().get("running") and time.time() - t0 < 1800:
    time.sleep(10)
was = page().get("auto", True)
page(False)
res = {}


def one(name, mode, delay, rig):
    axi_rig.kill_rig(rig)
    axi_rig.compile_ea("Saad_strategy_15min", rig=rig)
    for a in range(3):
        r = axi_rig.run("Saad_strategy_15min", "XAUUSD_BB", "M15", {"InpExitMode": mode, "InpLogCsv": "false"}, frm="2026.01.01", to="2026.10.17",
                        deposit=100000, rig=rig, tag=f"exit{mode}_{delay}", exec_mode=delay)
        if r.get("error") not in ("authorization failed", "no report"):
            break
        axi_rig.kill_rig(rig); time.sleep(3 + random.random() * 5)
    ts = r.get("trade_stats") or {}
    n, aw, al, net = ts.get("n") or 0, ts.get("avg_win") or 0, ts.get("avg_loss") or 0, r.get("net") or 0
    wr = 100 * ((net + n * -al) / (aw - al)) / n if n and aw - al else 0
    mo = r.get("months") or {}
    res[name] = {"mode": mode, "delay": delay, "net": net, "pf": r.get("pf"), "wr_trades": wr, "n": n, "deals": r.get("trades"), "dd": r.get("dd"),
                 "months": mo, "days": r.get("day_stats"), "h1": sum(v for k, v in mo.items() if k <= "2026.06"), "h2": sum(v for k, v in mo.items() if k >= "2026.07"),
                 "err": r.get("error")}
    print(f"{name}: net {net:+,.2f} PF {r.get('pf')} WR {wr:.1f}% trades {n} deals {r.get('trades')} DD {r.get('dd')} | Jan-Jun {res[name]['h1']:+,.0f} "
          f"Jul-Oct {res[name]['h2']:+,.0f} | " + " ".join(f"{k[5:]}:{v:+,.0f}" for k, v in mo.items()), flush=True)


ths = []
for x in RUNS:
    th = threading.Thread(target=one, args=x); th.start(); ths.append(th); time.sleep(5)
[th.join() for th in ths]
json.dump(res, open(HERE / "s15_exit_test.json", "w"), indent=1)
page(bool(was))
print("DONE", flush=True)
