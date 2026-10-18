"""m1def_forward_check.py - Zee 2026-10-18: "do the forward check yourself". Read every pass of the defended M1 genetic search from MT5's
optimization cache (Jan-Jun results), take the top N by profit factor, and run each on Jul 1 - Oct 16 (months the search never judged on)
in the MT5 Strategy Tester on 6 rigs in parallel. Writes m1def_forward.json (+ the cache decode m1def_passes.json).

    py m1def_forward_check.py [N]
"""
import glob
import json
import os
import queue
import random
import struct
import sys
import threading
import time
from pathlib import Path

import axi_rig

HERE = Path(__file__).resolve().parent
P = [('int', 'InpEmaFast'), ('int', 'InpEmaSlow'), ('double', 'InpBreakPips'), ('double', 'InpSlPips'), ('double', 'InpMaxRiskUsd'), ('double', 'InpBeTpPct'),
     ('double', 'InpChopEr'), ('int', 'InpSessFrom'), ('int', 'InpSessTo'), ('int', 'InpHtfIdx'), ('int', 'InpHtfEma'), ('int', 'InpEntryMode'), ('int', 'InpSlMode'),
     ('double', 'InpSlAtrMult'), ('double', 'InpPartialPct'), ('int', 'InpTpMode'), ('double', 'InpCostGateX'), ('bool', 'InpHardTp'), ('double', 'InpAdxMin'),
     ('double', 'InpAtrMinUsd'), ('double', 'InpAtrMaxUsd'), ('double', 'InpTpFixUsd'), ('double', 'InpTpFibPct')]
RIGS = ["axi2", "axi3", "axi4", "axi5", "axi6", "axi7"]


def decode():
    f = max(glob.glob(r"C:\mt5_rig_axi\Tester\cache\Saad_strategy_1min.XAUUSD_BB.M1.20260101.20260701.41.*.opt"), key=os.path.getmtime)
    b = open(f, "rb").read()[38002:]
    out, seen = [], set()
    for i in range(len(b) // 472):
        r = b[i * 472:(i + 1) * 472]
        d = lambda k: struct.unpack("<d", r[4 + 8 * k:12 + 8 * k])[0]
        q = lambda k: struct.unpack("<q", r[4 + 8 * k:12 + 8 * k])[0]
        p = {n: (q(29 + j) if t in ("int", "bool") else round(d(29 + j), 4)) for j, (t, n) in enumerate(P)}
        key = json.dumps(p, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append({"pf_h1": d(21), "pf_raw": d(17), "payoff_h1": d(16), "dd_h1": d(13), "p": p})
    return out


def main(N=150):
    passes = decode()
    json.dump(passes, open(HERE / "m1def_passes.json", "w"))
    top = sorted([x for x in passes if x["pf_h1"] > 0], key=lambda x: -x["pf_h1"])[:N]
    base = dict(json.load(open(HERE / "saad_opt_base_sets_m1def.json")), InpOptScore="4", InpOptMinTrades="1")
    q = queue.Queue()
    for i, x in enumerate(top):
        q.put((i, x))
    res = {}
    lock = threading.Lock()

    def worker(rig):
        axi_rig.compile_ea("Saad_strategy_1min", rig=rig)
        while True:
            try:
                i, x = q.get_nowait()
            except queue.Empty:
                return
            s = dict(base)
            s.update({k: ("true" if v else "false") if k == "InpHardTp" else str(v) for k, v in x["p"].items()})
            for a in range(3):
                r = axi_rig.run("Saad_strategy_1min", "XAUUSD_BB", "M1", s, frm="2026.07.01", to="2026.10.17", deposit=100000, rig=rig, tag="fwdchk", exec_mode=-1)
                if r.get("error") not in ("authorization failed", "no report"):
                    break
                axi_rig.kill_rig(rig); time.sleep(3 + random.random() * 5)
            ts = r.get("trade_stats") or {}; ds = r.get("day_stats") or {}
            n, aw, al, net = ts.get("n") or 0, ts.get("avg_win") or 0, ts.get("avg_loss") or 0, r.get("net") or 0
            wr = 100 * ((net + n * -al) / (aw - al)) / n if n and aw - al else 0
            with lock:
                res[i] = dict(x, net_h2=net, wr_h2=wr, pf_h2=float(r.get("pf") or 0), n_h2=n, green_h2=ds.get("green"), red_h2=ds.get("red"), months_h2=r.get("months"), err=r.get("error"))
                json.dump([res[k] for k in sorted(res)], open(HERE / "m1def_forward.json", "w"), indent=1)
                print(f"[{len(res)}/{len(top)}] H1 PF {x['pf_h1']:.2f} -> Jul-Oct PF {res[i]['pf_h2']:.2f} net {net:+,.0f} WR {wr:.1f}% trades {n}", flush=True)
    ts = []
    for rig in RIGS:
        t = threading.Thread(target=worker, args=(rig,)); t.start(); ts.append(t); time.sleep(5)
    [t.join() for t in ts]
    print("done", len(res))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 150)
