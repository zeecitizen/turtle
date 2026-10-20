"""scan.py - "Scan the levers" over EVERY setting (Zee 2026-10-21: "can you include every single setting that we have in the Scan the levers. so i keep
pressing trade this for that until we're done gaining everything we can from all the settings on earth we have").

From the exit on the research bench (the settings on screen + the bench's changes), every setting the EA has - the lines, the candle, the location,
the trigger, the filters, the range boxes (each box), the stop, the exit and the 27 Exit Lab settings - is moved a few steps either way, one at a time,
and each move is run on the data. Only settings that can act are tried (e.g. the sweep settings only with the sweep entry). Sizing (lots, risk %) is
left to Mission Control. The runs are spread over the CPU's cores (a pool of worker processes kept alive).
Python tester numbers: hypotheses until MT5 confirms them ("Check in MT5" after applying)."""
import concurrent.futures as cf
import multiprocessing as mp
import os
import time

os.environ.setdefault("NUMBA_CPU_NAME", "generic")

# (kind, lo, hi, step) | ("enum", [values]) | ("list", [values]) | "bool"; (group, ...)
G = {
    "the lines": {"InpEmaFast": ("int", 3, 60, 1), "InpEmaSlow": ("int", 10, 200, 2)},
    "the candle": {"InpWickMin": ("num", 0.1, 0.9, 0.05), "InpBodyMax": ("num", 0.1, 0.9, 0.05), "InpNoseMax": ("num", 0.0, 0.6, 0.05),
                   "InpMaruBody": ("num", 0.3, 0.95, 0.05), "InpHamRatio": ("num", 1.0, 5.0, 0.25), "InpHamNose": ("num", 0.1, 0.9, 0.05),
                   "InpMinRangeAtr": ("num", 0.0, 1.5, 0.05), "InpUsePin": "bool", "InpMarubozu": "bool", "InpHammer": "bool", "InpStar": "bool",
                   "InpPinDir": "bool", "InpPinColor": "bool"},
    "where": {"InpTouchPips": ("num", 0, 10, 0.5), "InpTouchMode": ("enum", [0, 1]), "InpLongRule": ("enum", [0, 1, 2]), "InpShortLine": ("enum", [0, 1, 2]),
              "InpLongExitAbove": "bool", "InpSkipBothEma": "bool"},
    "the trigger": {"InpBreakBars": ("int", 1, 6, 1), "InpBreakPips": ("int", 0, 20, 1), "InpTrigBid": "bool", "InpEntryMode": ("enum", [0, 1, 2]),
                    "InpRetestFrac": ("num", 0.1, 0.9, 0.1), "InpRetestBars": ("int", 1, 8, 1), "InpSweepPips": ("int", 0, 30, 2), "InpSweepBars": ("int", 1, 8, 1),
                    "InpSweepEntry": ("enum", [0, 1]), "InpSweepSlPips": ("int", 0, 40, 5)},
    "filters": {"InpAdxMin": ("int", 0, 50, 1), "InpAdxPeriod": ("int", 7, 28, 1), "InpAtrMinUsd": ("num", 0, 10, 0.5), "InpAtrMaxUsd": ("num", 0, 40, 2),
                "InpSessFrom": ("int", 0, 23, 1), "InpSessTo": ("int", 1, 24, 1), "InpSkipDow": ("enum", [-1, 1, 2, 3, 4, 5]), "InpNoNewMins": ("int", 0, 240, 15),
                "InpChopEr": ("num", 0, 0.5, 0.05), "InpChopErLook": ("int", 4, 40, 2), "InpHtfMin": ("enum", [0, 60, 240, 1440]), "InpHtfEma": ("int", 10, 100, 5),
                "InpTrendAlign": "bool", "InpPriceSide": "bool", "InpSlopePips": ("num", 0, 40, 2.5), "InpSlopeLook": ("int", 2, 20, 1),
                "InpEmaGapPips": ("num", 0, 40, 2.5), "InpMaxSpreadPts": ("int", 0, 100, 10), "InpGapCancel": "bool", "InpCoolBars": ("int", 0, 16, 1),
                "InpBuys": "bool", "InpSells": "bool", "InpMaxPos": ("int", 1, 4, 1), "InpReplace": "bool", "InpExtraDir": ("enum", [0, 1, 2]),
                "InpDayLossUsd": ("int", 0, 10000, 250), "InpDayTargetUsd": ("int", 0, 20000, 500), "InpDayLossPct": ("num", 0, 10, 0.5)},
    "range boxes": {"InpRangeLook": ("int", 3, 30, 1), "InpRangeLookS": ("int", 3, 30, 1), "InpBandOff": ("enum", [0, 1])},
    "the stop": {"InpSlMode": ("enum", [0, 1, 2]), "InpSlAtrMult": ("num", 0.5, 5, 0.1), "InpSlPips": ("int", 0, 100, 5), "InpSlUsd": ("num", 1, 30, 1),
                 "InpMaxRiskUsd": ("num", 0, 60, 1)},
    "the exit": {"InpExitMode": ("enum", [0, 1, 2]), "InpCloseLossMins": ("list", [0, 1, 3, 5, 10, 15, 30, 60]), "InpFixTpPips": ("list", [0, 20, 40, 60, 80, 100, 150, 200])},
    "v1.23 exits": {"InpLongExit": ("enum", [0, 1]), "InpLongTpPips": ("int", 0, 50, 5), "InpShortTpPips": ("int", 0, 50, 5), "InpMinTpPips": ("int", 0, 60, 5),
                    "InpMaxTpPips": ("int", 0, 300, 25), "InpSwingPivot": ("int", 1, 6, 1), "InpSwingLook": ("int", 20, 200, 10), "InpBeUsd": ("num", 0, 20, 1),
                    "InpLongTouch": ("enum", [0, 1]), "InpLongTrailUsd": ("num", 0.5, 10, 0.5), "InpLongResTp": "bool", "InpLongResTp1": "bool", "InpResTp1Ride": "bool",
                    "InpShortTouch": ("enum", [0, 1]), "InpTrailStepUsd": ("num", 0, 5, 0.5), "InpShortTrailUsd": ("num", 0.5, 10, 0.5), "InpBeTpPct": ("num", 0, 1, 0.05),
                    "InpTrail": "bool", "InpTrailSide": ("enum", [0, 1, 2]), "InpRide": "bool", "InpTrailMode": ("enum", [0, 1, 2]), "InpTrailN": ("int", 1, 10, 1),
                    "InpTrailPips": ("int", 5, 100, 5), "InpTrailAtr": ("num", 0.5, 5, 0.25), "InpTrailStart": ("int", 0, 100, 5), "InpRideLock": ("enum", [0, 1, 2]),
                    "InpLockPips": ("int", 0, 50, 5), "InpLockAtUsd": ("num", 0, 20, 1), "InpLockUsd": ("num", 0, 10, 0.5), "InpMaxBars": ("int", 0, 96, 4),
                    "InpPartialPct": ("num", 0, 0.9, 0.1), "InpTp1Be": "bool"},
}
GROUP = {k: g for g, d in G.items() for k in d}
SPEC = {k: v for d in G.values() for k, v in d.items()}


def _relevant(k, cur):
    """only settings that can act with the others as they are"""
    g = lambda n: str(cur.get(n, ""))  # noqa: E731
    f = lambda n: float(cur.get(n, 0) or 0)  # noqa: E731
    if k in ("InpRetestFrac", "InpRetestBars"):
        return g("InpEntryMode") == "1"
    if k in ("InpSweepPips", "InpSweepBars", "InpSweepEntry", "InpSweepSlPips"):
        return g("InpEntryMode") == "2"
    if k == "InpSlAtrMult":
        return g("InpSlMode") == "1"
    if k == "InpSlPips":
        return g("InpSlMode") == "0"
    if k == "InpSlUsd":
        return g("InpSlMode") == "2"
    if k == "InpChopErLook":
        return f("InpChopEr") > 0
    if k == "InpHtfEma":
        return f("InpHtfMin") > 0
    if k == "InpSlopeLook":
        return f("InpSlopePips") > 0
    if k in ("InpReplace", "InpExtraDir"):
        return f("InpMaxPos") > 1
    if GROUP.get(k) == "v1.23 exits":
        return g("InpExitMode") == "0"
    return True


def _fmt(kind, v):
    if kind == "int":
        return str(int(round(v)))
    return f"{round(v, 4):g}"


def _values(spec, cur):
    """a few steps either side of the value on screen, plus 'off' (0) for the settings where 0 switches them off"""
    if spec == "bool":
        return ["false" if str(cur).lower() == "true" else "true"]
    kind = spec[0]
    if kind in ("enum", "list"):
        return [str(v) for v in spec[1] if str(v) != str(cur).strip()]
    lo, hi, st = spec[1], spec[2], spec[3]
    try:
        c = float(cur)
    except ValueError:
        return []
    out = []
    for d in (-4, -2, -1, 1, 2, 4):
        v = round((c + d * st) / st) * st
        if lo - 1e-9 <= v <= hi + 1e-9:
            out.append(_fmt(kind, v))
    if lo <= 0 < c:
        out.append(_fmt(kind, 0))
    return [v for v in dict.fromkeys(out) if abs(float(v) - c) > 1e-9]


def moves(inputs, lab, labspec):
    """every move: (group, setting, from, to, sets-delta, lab-delta, label)"""
    out = []
    for k, spec in SPEC.items():
        if k not in inputs or not _relevant(k, inputs):
            continue
        for v in _values(spec, inputs[k]):
            out.append({"group": GROUP[k], "key": k, "label": k[3:], "from": str(inputs[k]), "to": v, "sets": {k: v}, "lab": {}})
    for side, key in (("BUY", "InpBandsB"), ("SELL", "InpBandsS")):         # every range box, ticked / unticked
        s = str(inputs.get(key, "1" * 21)).ljust(21, "1")[:21]
        for b in range(21):
            t = s[:b] + ("0" if s[b] == "1" else "1") + s[b + 1:]
            nm = f"{side} box {'>100%' if b == 20 else f'{b * 5}-{b * 5 + 5}%'}"
            out.append({"group": "range boxes", "key": key, "label": nm, "from": "on" if s[b] == "1" else "off", "to": "off" if s[b] == "1" else "on",
                        "sets": {key: t}, "lab": {}})
    if str(inputs.get("InpExitMode")) in ("1", "2"):                       # the Exit Lab settings (EA v1.30 InpX*), from the bench's exit
        import exitlab
        L = dict(labspec or {})
        g = lambda f, d=0.0: float(L.get(f, exitlab.DEFAULT.get(f, d)))  # noqa: E731
        for f, x in exitlab.FIELDS.items():
            if f == "pess" or (x.get("show") and not _show(x["show"], L)):
                continue
            cur = g(f)
            if x["t"] == "sel":
                vals = [o for o, _ in x["opts"] if o != int(cur)]
            elif x["t"] == "bool":
                vals = [0 if cur else 1]
            else:
                grid = exitlab.GRID.get(f)
                if isinstance(grid, dict):
                    grid = grid.get(int(g("tgt" if f == "tgt_k" else "tr")))
                if not grid:
                    continue
                vals = [float(v) for v in _values(("num",) + tuple(grid), cur)]
                if f in ("p1_r", "p2_r", "be_r", "lock_r", "max_bars", "stale_bars", "adx_exit", "fri_hour", "fb_buf", "cx_buf", "tr_act", "tr_buf") and cur == 0:
                    lo, hi, st = grid
                    vals = [float(_fmt("num", v)) for v in (lo, lo + 2 * st, lo + 4 * st) if v <= hi]
            for v in vals:
                d = {f: v}
                if f == "tgt" and v >= 2 and "tgt_k" not in L:
                    d["tgt_k"] = 2.0
                if f == "tr" and v >= 1 and "tr_k" not in L:
                    d["tr_k"] = 2.0
                out.append({"group": "Exit Lab", "key": f, "label": "X: " + x["label"], "from": f"{cur:g}", "to": f"{v:g}", "sets": {}, "lab": d})
    return out


def _show(cond, L):
    import exitlab
    v = lambda f: float(L.get(f, exitlab.DEFAULT.get(f, 0)))  # noqa: E731
    for o in cond.split("||"):
        ok = True
        for a in o.split("&&"):
            for op in (">=", "<=", "==", ">", "<"):
                if op in a:
                    f, c = a.split(op)
                    x, c = v(f.strip()), float(c)
                    ok = ok and {">=": x >= c, "<=": x <= c, "==": x == c, ">": x > c, "<": x < c}[op]
                    break
        if ok:
            return True
    return False


# ---------------------------------------------------------------- the runs, spread over the cores
_POOL = None


def _winit():
    os.environ.setdefault("NUMBA_CPU_NAME", "generic")


def _pool():
    global _POOL
    if _POOL is None:
        n = max(2, min(6, (os.cpu_count() or 4) - 2))
        _POOL = cf.ProcessPoolExecutor(max_workers=n, mp_context=mp.get_context("spawn"), initializer=_winit)
    return _POOL


def evaluate(task):
    """one run (in a worker): inputs, ds, lab, sets, window -> the numbers"""
    import exitlab
    inputs, ds, lab, sets, window = task
    inp = dict(inputs, **sets)
    if lab and str(inp.get("InpExitMode")) not in ("1", "2"):
        inp["InpExitMode"] = "1"
    _, real, oe = exitlab.run(inp, ds, lab=lab or None)
    s = exitlab.stats(real, window, open_end=oe)
    return {"train": s["train"]["net"], "test": s["test"]["net"], "net": s["total"], "wr": s["all"]["wr"], "pf": s["all"]["pf"], "dd": s["all"]["dd"],
            "n": s["all"]["n"], "stuck": s["stuck"]}


def run_all(job, inputs, ds, lab, sets, window):
    base_in = dict(inputs, **(sets or {}))
    labfull = dict(lab or {})
    mv = moves(base_in, lab, labfull)
    job.total = len(mv) + 1
    job.phase = f"warming up {min(6, (os.cpu_count() or 4) - 2)} lab assistants (worker processes)"
    tasks = [(inputs, ds, labfull or None, dict(sets or {}), window)]
    for m in mv:
        tasks.append((inputs, ds, dict(labfull, **m["lab"]) if (labfull or m["lab"]) else None, dict(sets or {}, **m["sets"]), window))
    results = [None] * len(tasks)
    t0 = time.time()
    try:
        pool = _pool()
        futs = {pool.submit(evaluate, t): i for i, t in enumerate(tasks)}
        for f in cf.as_completed(futs):
            if job._stop:
                for g in futs:
                    g.cancel()
                break
            results[futs[f]] = f.result()
            job.progress += 1
            i = futs[f]
            job.phase = f"{mv[i - 1]['group']}: {mv[i - 1]['label']} → {mv[i - 1]['to']}" if i else "the exit on the bench"
    except Exception as e:                                       # noqa: BLE001  (no pool on this machine: one core)
        job.phase = f"one core ({e})"
        for i, t in enumerate(tasks):
            if job._stop:
                break
            if results[i] is None:
                results[i] = evaluate(t)
                job.progress += 1
    now = results[0]
    out = []
    for m, r in zip(mv, results[1:]):
        if r:
            out.append(dict(m, r=r))
    return {"now": now, "moves": out, "seconds": round(time.time() - t0, 1), "n": len(mv)}
