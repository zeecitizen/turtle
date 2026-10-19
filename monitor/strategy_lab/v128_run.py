"""v128_run.py - Zee 2026-10-19 21:50 PKT: "run the optimizer on v1.27 and include only the features which are expected to make a difference
(based on our work of past 48 hours).. i want to see if the optimizer can find out a better version". = v127_night_run.py with a FOCUSED search
on Saad_strategy_15min v1.27 (12 settings that mattered; left out: breakeven / lock / partial / fixed targets / trend filter / chop / sessions /
2-candle breaks / range lookbacks - they only hurt or did nothing). Same pipeline: watchdog, Jan-Jun learn, Jul-Oct + full-year checks.

Original notes (v127_night_run.py, Zee 2026-10-19 06:40 PKT, going to sleep): "build an optimizer run and run the optimizer that runs for next ~8 hours
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
EA = "Saad_strategy_15min"          # v1.27
RIGS = ["axi", "axi2", "axi3", "axi4", "axi5", "axi6", "axi7"]
API = "http://127.0.0.1:8772/api/year"
HOURS = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
# 2026-10-19 07:54: the MT5 terminal crashed after ~1,090 passes ("crashlog generated"). Restarts: an absolute deadline (HH:MM) and the
# time the FIRST search started, so the passes of every attempt are read from the agents' logs together (pass number = the settings).
DEADLINE = sys.argv[2] if len(sys.argv) > 2 else None
SINCE = sys.argv[3] if len(sys.argv) > 3 else None
STATUS = HERE / "v128_status.json"
OUT = HERE / "v128_run.json"

# the search: (start, step, stop) around v1.26 (comment = v1.26's value). Max risk stays at or below Zee's $20 rule.
OPT = {                                # (start, step, stop) around v1.27 (comment = v1.27's value)
    "InpEmaFast": (12, 2, 20),         # 16
    "InpEmaSlow": (24, 4, 40),         # 32
    "InpWickMin": (0.25, 0.05, 0.5),   # 0.45
    "InpBodyMax": (0.5, 0.05, 0.7),    # 0.60
    "InpNoseMax": (0.25, 0.05, 0.45),  # 0.35
    "InpMinRangeAtr": (0.35, 0.1, 0.65),  # 0.55
    "InpLongRule": (0, 1, 2),          # 2
    "InpBreakPips": (2, 1, 5),         # 3
    "InpMaxRiskUsd": (14, 2, 20),      # 20 (Zee's rule: at most $20)
    "InpSlAtrMult": (1.2, 0.2, 2.2),   # 1.6
    "InpAdxMin": (22, 2, 36),          # 30
    "InpBandOff": (0, 1, 1),           # 1 (stand aside)
}
V126 = {"InpEmaFast": 16, "InpEmaSlow": 32, "InpWickMin": 0.45, "InpBodyMax": 0.6, "InpNoseMax": 0.35, "InpMinRangeAtr": 0.55, "InpLongRule": 2,
        "InpBreakPips": 3, "InpMaxRiskUsd": 20, "InpSlAtrMult": 1.6, "InpAdxMin": 30, "InpBandOff": 1}     # = v1.27 (name kept for the shared code)
so.FROM, so.TO, so.FORWARD = "2026.01.01", "2026.10.17", "2026.07.01"
so.JOBS["v128"] = {"ea": EA, "sets": "", "period": "M15", "algo": 2, "forward": True, "delay": 0,
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
                    ok += (round(d["InpMaxRiskUsd"], 2), 0.0, 0, 24) == (round(init[0], 2), round(init[1], 2), init[2], init[3])
                got[pid] = score
                init = None
    return got, checked, ok


def effective(p):
    return json.dumps(p, sort_keys=True)


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
                                tag=f"v128_{rig}", exec_mode=-1)
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
    now = datetime.now()
    t0 = datetime.strptime(now.strftime("%Y-%m-%d ") + SINCE, "%Y-%m-%d %H:%M").timestamp() if SINCE else time.time()
    deadline = datetime.strptime(now.strftime("%Y-%m-%d ") + DEADLINE, "%Y-%m-%d %H:%M").timestamp() if DEADLINE else time.time() + HOURS * 3600
    log(f"logs read from {datetime.fromtimestamp(t0):%H:%M}, search until {datetime.fromtimestamp(deadline):%H:%M}")
    nxt = time.time() + 1800
    finished, attempt = False, 0
    while time.time() < deadline - 600 and not finished:
        attempt += 1
        started = time.time()
        log(f"search attempt {attempt}")
        th = threading.Thread(target=so.start, args=("v128",), daemon=True)
        th.start()
        last_n, last_change = len(passes(t0)[0]), time.time()
        while th.is_alive() and time.time() < deadline:
            time.sleep(60)
            keep_awake()
            n = len(passes(t0)[0])
            if n != last_n:
                last_n, last_change = n, time.time()
            try:
                crashed = "crashlog generated" in open(r"C:\mt5_rig_axi\logs\%s.log" % datetime.now().strftime("%Y%m%d"), encoding="utf-16", errors="ignore").read().split("automatic testing started")[-1]
            except Exception:
                crashed = False
            if crashed or time.time() - last_change > 900:
                log(f"WATCHDOG: {'MT5 crashed' if crashed else 'no new passes for 15 min'} -> restarting the search")
                axi_rig.kill_rig("axi")
                time.sleep(20)
                break
            if time.time() >= nxt:
                status(t0, f"searching (attempt {attempt})")
                nxt += 1800
        if th.is_alive() and time.time() >= deadline:
            break
        th.join(timeout=60)
        # MT5 ending by itself within the time (not a crash, not killed): the genetic search converged
        finished = not th.is_alive() and time.time() - started > 900 and time.time() < deadline and progress() >= 99
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
    log(f"FORWARD check: {len(cands)} passes + v1.27 on Jul 1 - Oct 16")
    jobs = [("v1.27", {})] + [(f"c{i:02d}", {k: str(v) for k, v in c["p"].items()}) for i, c in enumerate(cands)]
    fwd = run_many(jobs, "2026.07.01", "2026.10.17")
    for i, c in enumerate(cands):
        c["fwd"] = fwd.get(f"c{i:02d}")
    ok = [c for c in cands if c["fwd"] and c["fwd"]["net"] > 0]
    best = sorted(ok, key=lambda c: -c["fwd"]["net_dd"])[:8]
    log(f"FULL YEAR: {len(best)} best forward passes + v1.27, twice each")
    jobs = []
    for rep in (1, 2):
        jobs.append((f"v1.27 #{rep}", {}))
        for c in best:
            jobs.append((f"c{cands.index(c):02d} #{rep}", {k: str(v) for k, v in c["p"].items()}))
    yr = run_many(jobs, "2026.01.01", "2026.10.17")
    for c in cands:
        c["year"] = [yr.get(f"c{cands.index(c):02d} #{r}") for r in (1, 2)] if c in best else None
        c["diff_vs_v127"] = {k: (V126.get(k), v) for k, v in c["p"].items() if v != V126.get(k)}
    out = {"started": datetime.fromtimestamp(t0).strftime("%Y-%m-%d %H:%M"), "search_finished_by_mt5": finished, "passes": len(got),
           "opt": OPT, "v127_fwd": fwd.get("v1.27"), "v127_year": [yr.get("v1.27 #1"), yr.get("v1.27 #2")], "candidates": cands}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    page(bool(was))
    log(f"DONE -> {OUT.name} | page auto re-run back to {was}")


if __name__ == "__main__":
    main()
