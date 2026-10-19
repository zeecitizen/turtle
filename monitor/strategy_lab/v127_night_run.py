"""v127_night_run.py - Zee 2026-10-19 (06:40 PKT, going to sleep): "build an optimizer run and run the optimizer that runs for next ~8 hours
... put every single setting into it that can be tuned to make a better version of the v1.26 ... once u have sufficient data to improve
upon 1.26 -> build and compile the 1.27".

One unattended pipeline:
  1. pause the compare page's 10-month auto re-run (same rigs, RAM) and keep Windows awake
  2. MT5 GENETIC optimization of Saad_strategy_15min_betest (= v1.26 + the breakeven / lock / partial test inputs, all off) on rig axi:
     26 settings around v1.26's values, learn Jan 1 - Jun 30, score = net / max drawdown (InpOptScore 0), 0 below 60 trades
  3. every 30 min: progress + the best passes so far (decoded from the agents' logs) -> v127_status.json / the log
  4. at the deadline (or when MT5 finishes): stop it; take the top 40 Jan-Jun passes
  5. FORWARD check: each of them + v1.26 on Jul 1 - Oct 16 (never seen by the search), random delay, 7 rigs
  6. FULL YEAR: the best 8 forward passes + v1.26, twice each, random delay
  7. -> v127_night.json (everything) ; page auto re-run back on
Claude reads v127_night.json and builds v1.27 only if a pass beats v1.26 where it counts (Jul-Oct and the full year).
    py v127_night_run.py [hours_for_the_search]
"""
import ctypes
import glob
import json
import queue
import random
import re
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import axi_rig
import saad_optimize as so

HERE = Path(__file__).resolve().parent
EA = "Saad_strategy_15min_betest"
RIGS = ["axi", "axi2", "axi3", "axi4", "axi5", "axi6", "axi7"]
API = "http://127.0.0.1:8772/api/year"
HOURS = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
STATUS = HERE / "v127_status.json"
OUT = HERE / "v127_night.json"

# the search: (start, step, stop) around v1.26 (comment = v1.26's value). Max risk stays at or below Zee's $20 rule.
OPT = {
    "InpEmaFast": (10, 2, 22),        # 16
    "InpEmaSlow": (24, 4, 48),        # 32
    "InpWickMin": (0.35, 0.05, 0.55),  # 0.45
    "InpBodyMax": (0.5, 0.05, 0.7),    # 0.60
    "InpMinRangeAtr": (0.35, 0.1, 0.75),  # 0.55
    "InpLongRule": (0, 1, 2),         # 2
    "InpShortLine": (0, 1, 2),        # 1
    "InpTouchPips": (0, 1, 3),        # 1
    "InpBreakBars": (1, 1, 2),        # 1
    "InpBreakPips": (1, 1, 6),        # 3
    "InpMaxRiskUsd": (10, 2.5, 20),   # 20
    "InpSlAtrMult": (1.0, 0.2, 2.6),  # 1.6
    "InpChopEr": (0, 0.05, 0.2),      # 0
    "InpHtfMin": (0, 30, 60),         # 0
    "InpAdxMin": (15, 5, 40),         # 30
    "InpAtrMinUsd": (0, 1, 4),        # 0
    "InpAtrMaxUsd": (0, 5, 25),       # 0
    "InpSessFrom": (0, 2, 8),         # 0
    "InpSessTo": (18, 2, 24),         # 24
    "InpRangeLook": (5, 1, 10),       # 7
    "InpRangeLookS": (5, 1, 10),      # 7
    "InpBandOff": (0, 1, 1),          # 1
    "InpX1BeUsd": (0, 4, 12),         # 0
    "InpX1PartPct": (0, 0.25, 0.5),   # 0
    "InpX1LockAt": (0, 4, 12),        # 0
    "InpX1LockUsd": (2, 2, 6),        # (off)
}
V126 = {"InpEmaFast": 16, "InpEmaSlow": 32, "InpWickMin": 0.45, "InpBodyMax": 0.6, "InpMinRangeAtr": 0.55, "InpLongRule": 2, "InpShortLine": 1,
        "InpTouchPips": 1, "InpBreakBars": 1, "InpBreakPips": 3, "InpMaxRiskUsd": 20, "InpSlAtrMult": 1.6, "InpChopEr": 0, "InpHtfMin": 0, "InpAdxMin": 30,
        "InpAtrMinUsd": 0, "InpAtrMaxUsd": 0, "InpSessFrom": 0, "InpSessTo": 24, "InpRangeLook": 7, "InpRangeLookS": 7, "InpBandOff": 1, "InpX1BeUsd": 0,
        "InpX1PartPct": 0, "InpX1LockAt": 0, "InpX1LockUsd": 2}
so.FROM, so.TO, so.FORWARD = "2026.01.01", "2026.10.17", "2026.07.01"
so.JOBS["v127"] = {"ea": EA, "sets": "", "period": "M15", "algo": 2, "forward": True, "delay": 0,
                   "fixed": {"InpOptScore": "0", "InpOptMinTrades": "60", "InpLogCsv": "false", "InpLog": "false"}, "opt": OPT}


def log(s):
    print(f"{datetime.now():%H:%M:%S} {s}", flush=True)


def page(on=None):
    try:
        if on is None:
            return json.loads(urllib.request.urlopen(API, timeout=10).read())
        urllib.request.urlopen(urllib.request.Request(API, data=json.dumps({"auto": on}).encode(), method="POST",
                                                      headers={"Content-Type": "application/json"}), timeout=10).read()
    except Exception as e:
        log(f"page: {e}")
    return {}


def keep_awake():
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)    # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    except Exception as e:
        log(f"keep-awake: {e}")


# ── decoding the running search from the agents' logs (the .opt cache is only written at the end) ──
src = (axi_rig.SRC / f"{EA}.mq5").read_text(encoding="utf-8", errors="ignore")
ORDER = [m.group(1) for m in re.finditer(r"^input\s+\w+\s+(\w+)\s*=", src, re.M) if m.group(1) in OPT]
VALS = {k: [round(a + i * s, 6) for i in range(int(round((b - a) / s)) + 1)] for k, (a, s, b) in OPT.items()}


def decode(pid):
    out, rest = {}, pid
    for k in ORDER:
        n = len(VALS[k])
        out[k] = VALS[k][rest % n]
        rest //= n
    return out


def passes(t0):
    start = datetime.fromtimestamp(t0)
    got, checked, ok = {}, 0, 0
    for f in glob.glob(r"C:\mt5_rig_axi\Tester\Agent-*\logs\*.log"):
        day = Path(f).stem
        if day < start.strftime("%Y%m%d"):
            continue
        init = None
        for line in open(f, encoding="utf-16", errors="ignore"):
            parts = line.split("\t")
            if day == start.strftime("%Y%m%d") and len(parts) > 2 and parts[2][:8] < start.strftime("%H:%M:%S"):
                continue
            m = re.search(r"SL (\d+) pips, max risk \$([\d.]+), ER ([\d.]+)/\d+, hours (\d+)-(\d+)", line)
            if m:
                init = (float(m.group(2)), float(m.group(3)), int(m.group(4)), int(m.group(5)))
                continue
            m = re.search(r"Tester\s+(\d+) OnTester result ([-\d.e+]+)", line)
            if m:
                pid, score = int(m.group(1)), float(m.group(2))
                if init:
                    d = decode(pid)
                    checked += 1
                    ok += (round(d["InpMaxRiskUsd"], 2), round(d["InpChopEr"], 2), d["InpSessFrom"], d["InpSessTo"]) == (round(init[0], 2), round(init[1], 2), init[2], init[3])
                got[pid] = score
                init = None
    return got, checked, ok


def effective(p):
    """the settings that change trading (a lock amount without a lock trigger does nothing)"""
    q = dict(p)
    if q["InpX1LockAt"] == 0:
        q["InpX1LockUsd"] = 0
    return json.dumps(q, sort_keys=True)


def progress():
    try:
        t = open(r"C:\mt5_rig_axi\logs\%s.log" % datetime.now().strftime("%Y%m%d"), encoding="utf-16", errors="ignore").read()
        p = re.findall(r"processing (\d+) %", t)
        return int(p[-1]) if p else 0
    except Exception:
        return -1


def status(t0, phase):
    got, checked, ok = passes(t0)
    top = sorted(((s, pid) for pid, s in got.items() if s > -1e8), reverse=True)[:5]
    st = {"at": datetime.now().strftime("%H:%M"), "phase": phase, "progress_pct": progress(), "passes": len(got), "decode_checked": checked,
          "decode_ok": ok, "top": [{"score": s, **{k: v for k, v in decode(pid).items() if v != V126.get(k)}} for s, pid in top]}
    STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")
    log(f"STATUS {phase}: {st['progress_pct']}% | {len(got)} passes (decode {ok}/{checked}) | best net/DD Jan-Jun: " +
        ", ".join(f"{t['score']:.2f}" for t in st["top"]))
    return got


def run_many(jobs, frm, to):
    """jobs: [(name, sets)] -> {name: result}, on all rigs, random delay"""
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    res, lock = {}, threading.Lock()

    def worker(rig):
        axi_rig.kill_rig(rig)
        axi_rig.compile_ea(EA, rig=rig)
        while True:
            try:
                name, s = q.get_nowait()
            except queue.Empty:
                return
            for a in range(3):
                r = axi_rig.run(EA, "XAUUSD_BB", "M15", dict(s, InpLogCsv="false", InpLog="false"), frm=frm, to=to, deposit=100000, rig=rig,
                                tag=f"v127_{rig}", exec_mode=-1)
                if r.get("error") not in ("authorization failed", "no report"):
                    break
                axi_rig.kill_rig(rig); time.sleep(3 + random.random() * 5)
            ts = r.get("trade_stats") or {}
            n, aw, al, net = ts.get("n") or 0, ts.get("avg_win") or 0, ts.get("avg_loss") or 0, r.get("net") or 0
            wr = 100 * ((net + n * -al) / (aw - al)) / n if n and aw - al else 0
            dd = float(str(r.get("dd") or "0").split("(")[0].replace(" ", "") or 0)
            with lock:
                res[name] = {"net": net, "pf": float(r.get("pf") or 0), "wr": wr, "n": n, "dd": dd, "net_dd": net / dd if dd else 0,
                             "months": r.get("months"), "err": r.get("error")}
                log(f"   {name}: net {net:+,.0f} PF {res[name]['pf']:.2f} WR {wr:.0f}% n {n} DD {dd:,.0f}")
    ths = [threading.Thread(target=worker, args=(g,)) for g in RIGS]
    for th in ths:
        th.start(); time.sleep(4)
    for th in ths:
        th.join()
    return res


def main():
    keep_awake()
    was = page().get("auto", True)
    t1 = time.time()
    while page().get("running") and time.time() - t1 < 1800:
        time.sleep(10)
    page(False)
    log(f"page auto re-run paused (was {was}); search: {len(OPT)} settings, {HOURS} h, order {ORDER}")
    t0 = time.time()
    th = threading.Thread(target=so.start, args=("v127",), daemon=True)
    th.start()
    deadline = t0 + HOURS * 3600
    nxt = t0 + 1800
    while th.is_alive() and time.time() < deadline:
        time.sleep(30)
        keep_awake()
        if time.time() >= nxt:
            status(t0, "searching")
            nxt += 1800
    finished = not th.is_alive()
    time.sleep(20)
    got = status(t0, "search finished by MT5" if finished else "search stopped at the deadline")
    if th.is_alive():
        axi_rig.kill_rig("axi")
        time.sleep(15)
        got = status(t0, "search stopped at the deadline")
    # top 40 distinct (effective) passes by the Jan-Jun score
    seen, cands = set(), []
    for s, pid in sorted(((s, pid) for pid, s in got.items() if s > -1e8), reverse=True):
        p = decode(pid)
        e = effective(p)
        if e in seen:
            continue
        seen.add(e)
        cands.append({"pass": pid, "score_jan_jun": s, "p": p})
        if len(cands) == 40:
            break
    log(f"FORWARD check: {len(cands)} passes + v1.26 on Jul 1 - Oct 16")
    jobs = [("v1.26", {})] + [(f"c{i:02d}", {k: str(v) for k, v in c["p"].items()}) for i, c in enumerate(cands)]
    fwd = run_many(jobs, "2026.07.01", "2026.10.17")
    for i, c in enumerate(cands):
        c["fwd"] = fwd.get(f"c{i:02d}")
    ok = [c for c in cands if c["fwd"] and c["fwd"]["net"] > 0]
    best = sorted(ok, key=lambda c: -c["fwd"]["net_dd"])[:8]
    log(f"FULL YEAR: {len(best)} best forward passes + v1.26, twice each")
    jobs = []
    for rep in (1, 2):
        jobs.append((f"v1.26 #{rep}", {}))
        for c in best:
            jobs.append((f"c{cands.index(c):02d} #{rep}", {k: str(v) for k, v in c["p"].items()}))
    yr = run_many(jobs, "2026.01.01", "2026.10.17")
    for c in cands:
        c["year"] = [yr.get(f"c{cands.index(c):02d} #{r}") for r in (1, 2)] if c in best else None
        c["diff_vs_v126"] = {k: (V126.get(k), v) for k, v in c["p"].items() if v != V126.get(k) and not (k == "InpX1LockUsd" and c["p"]["InpX1LockAt"] == 0)}
    out = {"started": datetime.fromtimestamp(t0).strftime("%Y-%m-%d %H:%M"), "search_finished_by_mt5": finished, "passes": len(got),
           "opt": OPT, "v126_fwd": fwd.get("v1.26"), "v126_year": [yr.get("v1.26 #1"), yr.get("v1.26 #2")], "candidates": cands}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    page(bool(was))
    log(f"DONE -> {OUT.name} | page auto re-run back to {was}")


if __name__ == "__main__":
    main()
