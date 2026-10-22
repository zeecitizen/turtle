"""scan.py - "Scan every setting" (Zee 2026-10-21: "can you include every single setting that we have in the Scan the levers. so i keep pressing trade this
for that until we're done gaining everything we can from all the settings on earth we have").

From the research bench (the settings on screen + the bench's changes + the bench's Exit Lab exit), every setting the EA has - the lines, the candle,
the location, the trigger, the filters, each range box, the stop, the exit and the 27 Exit Lab settings (EA v1.30 InpX*) - is moved a few steps either
way, one at a time, and each move runs on the data AS EA SETTINGS (the bench's Exit Lab exit too: InpX*, exactly what MT5 runs). Only settings that can
act are tried (e.g. the sweep settings only with the sweep entry, the fallback only in exit mode 1 without a target). Sizing (lots, risk %) is left to
Mission Control. The runs go to a few worker processes (kept while in use, shut after 10 idle minutes).
Python tester numbers: hypotheses until MT5 confirms them ("Check in MT5" after applying)."""
import concurrent.futures as cf
import multiprocessing as mp
import os
import threading
import time

os.environ.setdefault("NUMBA_CPU_NAME", "generic")

# (kind, lo, hi, step) | ("enum", [values]) | ("list", [values]) | "bool"
G = {
    "the lines": {"InpEmaFast": ("int", 3, 60, 1), "InpEmaSlow": ("int", 10, 200, 2)},
    "the candle": {"InpWickMin": ("num", 0.1, 0.9, 0.05), "InpBodyMax": ("num", 0.1, 0.9, 0.05), "InpNoseMax": ("num", 0.0, 0.6, 0.05),
                   "InpMaruBody": ("num", 0.3, 0.95, 0.05), "InpHamRatio": ("num", 1.0, 5.0, 0.25), "InpHamNose": ("num", 0.1, 0.9, 0.05),
                   "InpMinRangeAtr": ("num", 0.0, 1.5, 0.05), "InpUsePin": "bool", "InpMarubozu": "bool", "InpHammer": "bool", "InpStar": "bool",
                   "InpPinDir": "bool", "InpPinColor": "bool"},
    "where": {"InpTouchPips": ("num", 0, 10, 0.5), "InpTouchMode": ("enum", [0, 1]), "InpLongRule": ("enum", [0, 1, 2]), "InpShortLine": ("enum", [0, 1, 2]),
              "InpLongExitAbove": "bool", "InpSkipBothEma": "bool"},
    "the trigger": {"InpBreakBars": ("int", 1, 6, 1), "InpBreakPips": ("num", 0, 20, 1), "InpTrigBid": "bool", "InpEntryMode": ("enum", [0, 1, 2]),
                    "InpRetestFrac": ("num", 0.1, 0.9, 0.1), "InpRetestBars": ("int", 1, 8, 1), "InpSweepPips": ("num", 0, 30, 2), "InpSweepBars": ("int", 1, 8, 1),
                    "InpSweepEntry": ("enum", [0, 1]), "InpSweepSlPips": ("num", 0, 40, 5)},
    "filters": {"InpAdxMin": ("num", 0, 50, 1), "InpAdxPeriod": ("int", 7, 28, 1), "InpAtrMinUsd": ("num", 0, 10, 0.5), "InpAtrMaxUsd": ("num", 0, 40, 2),
                "InpSessFrom": ("int", 0, 23, 1), "InpSessTo": ("int", 1, 24, 1), "InpSkipDow": ("enum", [-1, 1, 2, 3, 4, 5]), "InpNoNewMins": ("int", 0, 240, 15),
                "InpChopEr": ("num", 0, 0.5, 0.05), "InpChopErLook": ("int", 4, 40, 2), "InpHtfMin": ("enum", [0, 15, 30, 60, 240]), "InpHtfEma": ("int", 10, 100, 5),
                "InpTrendAlign": "bool", "InpPriceSide": "bool", "InpSlopePips": ("num", 0, 40, 2.5), "InpSlopeLook": ("int", 2, 20, 1),
                "InpEmaGapPips": ("num", 0, 40, 2.5), "InpMaxSpreadPts": ("int", 0, 100, 10), "InpGapCancel": "bool", "InpCoolBars": ("int", 0, 16, 1),
                "InpBuys": "bool", "InpSells": "bool", "InpMaxPos": ("int", 1, 4, 1), "InpReplace": "bool", "InpExtraDir": ("enum", [0, 1, 2]),
                "InpDayLossUsd": ("num", 0, 10000, 250), "InpDayTargetUsd": ("num", 0, 20000, 500), "InpDayLossPct": ("num", 0, 10, 0.5)},
    "range boxes": {"InpRangeLook": ("int", 3, 30, 1), "InpRangeLookS": ("int", 3, 30, 1), "InpBandOff": ("enum", [0, 1])},
    "the stop": {"InpSlMode": ("enum", [0, 1, 2]), "InpSlAtrMult": ("num", 0.5, 5, 0.1), "InpSlPips": ("num", 0, 100, 5), "InpSlUsd": ("num", 1, 30, 1),
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
# Exit Lab settings that are off (0): where switching them on starts
STARTERS = {"p1_r": [0.5, 1, 1.5, 2], "p2_r": [1.5, 2, 3], "be_r": [0.5, 1, 1.5, 2], "lock_r": [0.5, 1, 2], "max_bars": [4, 8, 16, 32], "stale_bars": [4, 8, 16],
            "adx_exit": [15, 20, 25], "fri_hour": [18, 20, 21], "fb_buf": [0.1, 0.25, 0.5], "cx_buf": [0.1, 0.25, 0.5], "tr_act": [0.5, 1, 2], "tr_buf": [0.5, 1, 2],
            "cx_after": [1, 2, 4], "be_off": [0.05, 0.1, 0.25], "lcap": [10, 15, 20, 30], "lp_r": [0.25, 0.5, 0.75], "dc_bars": [4, 8, 16]}


def _f(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _relevant(k, cur):
    """only settings that can act with the others as they are (the same conditions as the EA's code)"""
    g = lambda n: str(cur.get(n, "")).strip()  # noqa: E731
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
        return _f(cur.get("InpChopEr")) > 0
    if k == "InpHtfEma":
        return _f(cur.get("InpHtfMin")) > 0
    if k == "InpSlopeLook":
        return _f(cur.get("InpSlopePips")) > 0
    if k in ("InpReplace", "InpExtraDir"):
        return _f(cur.get("InpMaxPos")) > 1
    if GROUP.get(k) == "v1.23 exits":
        return g("InpExitMode") == "0"
    return True


def _valid(cur):
    """combinations that cannot trade: the slow EMA not above the fast one, a session that ends before it starts"""
    return _f(cur.get("InpEmaSlow")) > _f(cur.get("InpEmaFast")) and _f(cur.get("InpSessTo")) > _f(cur.get("InpSessFrom"))


def _fmt(kind, v):
    if kind == "int":
        return str(int(round(v)))
    return f"{round(v, 4):g}"


def _values(spec, cur):
    """a few steps either side of the value on screen, plus 'off' (0) for the settings where 0 switches them off"""
    if spec == "bool":
        return ["false" if str(cur).strip().lower() == "true" else "true"]
    kind = spec[0]
    if kind in ("enum", "list"):
        return [str(v) for v in spec[1] if abs(_f(v, 1e9) - _f(cur, -1e9)) > 1e-9]
    lo, hi, st = spec[1], spec[2], spec[3]
    try:
        c = float(cur)
    except (TypeError, ValueError):
        return []
    out = []
    for d in (-4, -2, -1, 1, 2, 4):
        v = round((c + d * st) / st) * st
        if lo - 1e-9 <= v <= hi + 1e-9:
            out.append(_fmt(kind, v))
    if lo <= 0 < c:
        out.append(_fmt(kind, 0))
    return [v for v in dict.fromkeys(out) if abs(float(v) - c) > 1e-9]


def lab_sets(labfull):
    """the bench's Exit Lab exit as the EA's own settings (InpX*) - what MT5 runs"""
    import sim_full
    out = {}
    for f, k in sim_full.XFIELDS.items():
        if f in labfull:
            v = _f(labfull[f])
            out[k] = ("true" if v else "false") if f == "p1_be" else _fmt("num", v)
    return out


# the broker's real gold spread (Blueberry ticks, 2026): 10th percentile 14 points, median 19. A spread limit below this never lets an EA trade
# live (the tester's clamped export spread did, which is how a limit of 10 looked great and took no trades in MT5)
SPREAD_FLOOR = 15


def moves(base_in, labfull, trust=None):
    """every move from the bench: {group, key, label, from, to, sets (EA settings for the page), lab (the bench form for the page), xs (InpX for the run), trust}"""
    import exitlab
    trust = trust or {}
    out = []
    for k, spec in SPEC.items():
        if k not in base_in or not _relevant(k, base_in):
            continue
        for v in _values(spec, base_in[k]):
            if k == "InpMaxSpreadPts" and 0 < _f(v) < SPREAD_FLOOR:
                continue                                                # the broker never meets it: no trades live
            if k == "InpWickMin" and 1 - _f(base_in.get("InpBodyMax")) - _f(base_in.get("InpNoseMax")) >= _f(v):
                continue                                                # a pin's lower wick is already at least 1 - body - nose: this value changes nothing
            if not _valid(dict(base_in, **{k: v})):
                continue
            out.append({"group": GROUP[k], "key": k, "label": k[3:], "from": str(base_in[k]), "to": v, "sets": {k: v}, "lab": {}, "xs": {},
                        "trust": trust.get(k, "")})
    for side, key in (("BUY", "InpBandsB"), ("SELL", "InpBandsS")):         # every range box, ticked / unticked
        s = str(base_in.get(key, "1" * 21)).ljust(21, "1")[:21]
        for b in range(21):
            t = s[:b] + ("0" if s[b] == "1" else "1") + s[b + 1:]
            nm = f"{side} box {'>100%' if b == 20 else f'{b * 5}-{b * 5 + 5}%'}"
            out.append({"group": "range boxes", "key": key, "label": nm, "from": "on" if s[b] == "1" else "off", "to": "off" if s[b] == "1" else "on",
                        "sets": {key: t}, "lab": {}, "xs": {}, "trust": ""})
    mode = str(base_in.get("InpExitMode", "")).strip()
    if mode in ("1", "2"):                                                  # the Exit Lab settings (EA v1.30 InpX*) act in exit modes 1-2
        L = dict(exitlab.DEFAULT, **(labfull or {}))
        g = lambda f: _f(L.get(f, 0))  # noqa: E731
        for f, x in exitlab.FIELDS.items():
            if f == "pess" or (x.get("show") and not _show(x["show"], L)):
                continue
            if f in ("fb", "fb_buf", "fb_n") and (mode != "1" or g("tgt") != 0):
                continue                                                    # the fallback exists only in exit mode 1 without a lab target
            cur = g(f)
            names = {}
            if x["t"] == "sel":
                vals = [float(o) for o, _ in x["opts"] if o != int(cur)]
                names = {float(o): nm for o, nm in x["opts"]}
            elif x["t"] == "bool":
                vals = [0.0 if cur else 1.0]
                names = {0.0: "off", 1.0: "on"}
            elif cur == 0 and f in STARTERS:
                vals = [float(v) for v in STARTERS[f]]
            else:
                grid = exitlab.GRID.get(f)
                if isinstance(grid, dict):
                    grid = grid.get(int(g("tgt" if f == "tgt_k" else "tr")))
                if not grid:
                    continue
                vals = [float(v) for v in _values(("num",) + tuple(grid), cur)]
            for v in vals:
                d = {f: v}
                xs = lab_sets(dict(L, **d))
                out.append({"group": "Exit Lab", "key": f, "label": "X: " + x["label"], "from": names.get(cur, f"{cur:g}"), "to": names.get(v, f"{v:g}"),
                            "sets": {}, "lab": d, "xs": xs, "trust": ""})
    return out


def _show(cond, L):
    v = lambda f: _f(L.get(f, 0))  # noqa: E731
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


# ---------------------------------------------------------------- the runs, on a few worker processes
WORKERS = max(2, min(4, (os.cpu_count() or 4) - 2))
_POOL, _LOCK, _USED = None, threading.Lock(), [0.0]


def _winit():
    os.environ.setdefault("NUMBA_CPU_NAME", "generic")
    threading.Thread(target=_watch_parent, args=(os.getppid(),), daemon=True).start()


def _watch_parent(ppid):
    """a worker leaves when its server is gone (a killed server would otherwise leave ~340 MB orphans behind on Windows)"""
    if os.name != "nt":
        while True:
            time.sleep(3)
            if os.getppid() != ppid:
                os._exit(0)
    import ctypes
    k32 = ctypes.windll.kernel32
    while True:
        time.sleep(3)
        h = k32.OpenProcess(0x00100000, False, ppid)               # SYNCHRONIZE
        if not h:
            os._exit(0)
        gone = k32.WaitForSingleObject(h, 0) == 0                 # WAIT_OBJECT_0: the server has exited
        k32.CloseHandle(h)
        if gone:
            os._exit(0)


def _pool():
    global _POOL
    with _LOCK:
        if _POOL is None:
            _POOL = cf.ProcessPoolExecutor(max_workers=WORKERS, mp_context=mp.get_context("spawn"), initializer=_winit)
            threading.Thread(target=_reaper, daemon=True).start()
        _USED[0] = time.time()
        return _POOL


def _drop_pool():
    global _POOL
    with _LOCK:
        if _POOL is not None:
            try:
                _POOL.shutdown(wait=False, cancel_futures=True)
            except Exception:                                    # noqa: BLE001
                pass
            _POOL = None


def _reaper():
    """the workers hold the data in memory (~340 MB each): let them go after 10 idle minutes"""
    while True:
        time.sleep(60)
        with _LOCK:
            if _POOL is None:
                return
            idle = time.time() - _USED[0] > 600
        if idle:
            _drop_pool()
            return


def evaluate(task):
    """one run (in a worker): EA settings over the data -> the numbers (L = the loss side for the loss cutter, Lh = the same per half, days = day by day)"""
    import exitlab
    import losslab
    inputs, ds, sets, window = task
    _, real, oe = exitlab.run(dict(inputs, **sets), ds)               # the Exit Lab exit comes in as InpX* settings, exactly as the EA reads it
    s = exitlab.stats(real, window, open_end=oe)
    a0, a1, b0, b1 = window
    p, t = real[:, 6], real[:, 1]
    return {"train": s["train"]["net"], "test": s["test"]["net"], "net": s["total"], "wr": s["all"]["wr"], "pf": s["all"]["pf"], "dd": s["all"]["dd"],
            "n": s["all"]["n"], "stuck": s["stuck"], "L": losslab.loss_stats(p),
            "Lh": [losslab.loss_stats(p[(t >= a0) & (t < a1)]), losslab.loss_stats(p[(t >= b0) & (t < b1)])], "days": losslab.day_stats(real)}


def _sig(sets, lab):
    """what a move changes, comparable between moves: short numbers as numbers ("15" = "15.0"), everything else as text - the range-box
    strings ("111110010100001010111") are 21-digit words, not numbers (as floats, different boxes would look the same)"""
    def v(x):
        s = str(x).strip().lower()
        if len(s) <= 12:
            try:
                return round(float(s), 6)
            except ValueError:
                pass
        return s
    return (tuple(sorted((k, v(x)) for k, x in sets.items())), tuple(sorted((k, v(x)) for k, x in lab.items())))


def data_moves(props, base_in, labfull, trust, have):
    """the loss autopsy's proposals -> moves. One that the scan already makes gets the autopsy's reason instead of a twin;
    one that changes nothing, cannot trade or cannot act is dropped."""
    import exitlab
    L = dict(exitlab.DEFAULT, **(labfull or {}))
    index = {_sig(m["sets"], m["lab"]): m for m in have}
    out = []
    for pr in props:
        sets = {k: (v if isinstance(v, str) else _fmt("int" if SPEC.get(k, ("num",))[0] == "int" else "num", float(v))) for k, v in (pr.get("sets") or {}).items()}
        lab = {k: float(v) for k, v in (pr.get("lab") or {}).items()}
        if sets and all(_sig({k: base_in.get(k)}, {}) == _sig({k: v}, {}) for k, v in sets.items()):
            continue                                             # already the bench's values
        if lab and all(abs(_f(L.get(k)) - v) < 1e-9 for k, v in lab.items()):
            continue
        if sets and not _valid(dict(base_in, **sets)):
            continue
        if any(k not in base_in for k in sets):
            continue
        if any(not _relevant(k, dict(base_in, **sets)) for k in sets):
            continue
        sig = _sig(sets, lab)
        if sig in index:                                         # the scan's own move: give it the reason
            index[sig]["why"] = pr.get("why", "")
            index[sig]["data"] = True
            continue
        m = {"group": pr.get("group", "the stop"), "key": next(iter(sets or lab)), "label": pr.get("label", ""), "from": str(pr.get("from", "")),
             "to": str(pr.get("to", "")), "sets": sets, "lab": lab, "xs": lab_sets(dict(L, **lab)) if lab else {},
             "trust": trust.get(next(iter(sets)), "") if sets else "", "why": pr.get("why", ""), "data": True}
        index[sig] = m
        out.append(m)
    return out


def run_all(job, inputs, ds, lab, sets, window, focus=None):
    import exitlab
    import sim_full
    if not lab:                                                  # no bench form sent: the exit in the settings themselves (InpX*)
        lab = {k: v for k, v in (sim_full.lab_from_inputs(dict(inputs, **(sets or {}))) or {}).items() if k != "pess"}
    labfull = {k: v for k, v in dict(exitlab.DEFAULT, **lab).items() if k != "pess"}
    base_sets = dict(sets or {}, **lab_sets(labfull))            # the bench as EA settings: the same numbers MT5 would run
    base_in = dict(inputs, **base_sets)
    trust = exitlab.ea_trust()
    mv = moves(base_in, labfull, trust)
    aut = None
    if focus == "loss":                                          # the loss cutter: read the bench's own trades, add the moves they point to
        import losslab
        import sim
        job.phase = "the loss autopsy: reading every trade on the bench"
        tr, setups, _ = sim.simulate(base_in, ds=ds)
        aut = losslab.autopsy(tr[tr[:, 10] == 0], setups, sim.data(ds), base_in, labfull)
        mv += data_moves(aut.pop("proposals"), base_in, labfull, trust, mv)
    job.total = len(mv) + 1
    job.phase = f"warming up {WORKERS} lab assistants"
    tasks = [(inputs, ds, base_sets, window)] + [(inputs, ds, dict(base_sets, **m["sets"], **m["xs"]), window) for m in mv]
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
            i = futs[f]
            results[i] = f.result()
            job.progress += 1
            job.phase = f"{mv[i - 1]['group']}: {mv[i - 1]['label']} → {mv[i - 1]['to']}" if i else "the exit on the bench"
        _USED[0] = time.time()
    except Exception as e:                                       # noqa: BLE001  (a broken pool: drop it, finish on this core, a fresh pool next time)
        _drop_pool()
        job.phase = f"finishing on one core ({type(e).__name__})"
        for i, t in enumerate(tasks):
            if job._stop:
                break
            if results[i] is None:
                results[i] = evaluate(t)
                job.progress += 1
    now = results[0]
    out = [dict({k: v for k, v in m.items() if k != "xs"}, r=r) for m, r in zip(mv, results[1:]) if r]
    return {"now": now, "moves": out, "seconds": round(time.time() - t0, 1), "n": len(mv), "stopped": now is None or len(out) < len(mv),
            "focus": focus or "", "autopsy": aut}
