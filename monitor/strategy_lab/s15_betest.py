"""s15_betest.py - Zee 2026-10-19: breakeven / partial-at-TP1 tests on v1.26 (test copy Saad_strategy_15min_betest, all off = v1.26)."""
import json, random, threading, time, urllib.request
from pathlib import Path
import axi_rig
EA = "Saad_strategy_15min_betest"; API = "http://127.0.0.1:8772/api/year"
RUNS = [("v1.26 as it is", {}), ("BE at +$3", {"InpX1BeUsd": "3"}), ("BE at +$5", {"InpX1BeUsd": "5"}), ("BE at +$8", {"InpX1BeUsd": "8"}),
        ("BE at 50% of the way", {"InpX1BePct": "0.5"}), ("BE at 75% of the way", {"InpX1BePct": "0.75"}),
        ("partial 50% at TP1, rest trails $2", {"InpX1PartPct": "0.5", "InpX1TrailUsd": "2"}),
        ("partial 50% at TP1, rest trails $4", {"InpX1PartPct": "0.5", "InpX1TrailUsd": "4"}),
        ("partial 75% at TP1, rest trails $2", {"InpX1PartPct": "0.75", "InpX1TrailUsd": "2"}),
        ("BE 75% + partial 50%, trail $2", {"InpX1BePct": "0.75", "InpX1PartPct": "0.5", "InpX1TrailUsd": "2"})]
RIGS = ["axi", "axi2", "axi3", "axi4", "axi5", "axi6", "axi7"]
def page(on=None):
    try:
        if on is None: return json.loads(urllib.request.urlopen(API, timeout=10).read())
        urllib.request.urlopen(urllib.request.Request(API, data=json.dumps({"auto": on}).encode(), method="POST", headers={"Content-Type": "application/json"}), timeout=10).read()
    except Exception as e: print("page", e)
    return {}
t0 = time.time()
while page().get("running") and time.time() - t0 < 1800: time.sleep(10)
was = page().get("auto", True); page(False)
import queue
q = queue.Queue(); [q.put(r) for r in RUNS]; res = {}
def worker(rig):
    axi_rig.kill_rig(rig); axi_rig.compile_ea(EA, rig=rig)
    while True:
        try: name, s = q.get_nowait()
        except queue.Empty: return
        for a in range(3):
            r = axi_rig.run(EA, "XAUUSD_BB", "M15", dict(s, InpLogCsv="false"), frm="2026.01.01", to="2026.10.17", deposit=100000, rig=rig, tag=f"betest_{rig}", exec_mode=-1)
            if r.get("error") not in ("authorization failed", "no report"): break
            axi_rig.kill_rig(rig); time.sleep(3 + random.random() * 5)
        ts = r.get("trade_stats") or {}; n, aw, al, net = ts.get("n") or 0, ts.get("avg_win") or 0, ts.get("avg_loss") or 0, r.get("net") or 0
        wr = 100 * ((net + n * -al) / (aw - al)) / n if n and aw - al else 0
        mo = r.get("months") or {}
        res[name] = dict(net=net, pf=r.get("pf"), wr=wr, n=n, dd=r.get("dd"), months=mo)
        print(f"{name}: net {net:+,.0f} PF {r.get('pf')} WR {wr:.1f}% trades {n} DD {r.get('dd')} | red " + " ".join(f"{k[5:]}:{v/1000:+.1f}k" for k, v in mo.items() if v < 0), flush=True)
ths = [threading.Thread(target=worker, args=(g,)) for g in RIGS]
for th in ths: th.start(); time.sleep(5)
for th in ths: th.join()
json.dump(res, open(Path(__file__).with_name("s15_betest.json"), "w"), indent=1); page(bool(was)); print("DONE")
