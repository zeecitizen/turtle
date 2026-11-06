"""stack_net.py - greedy FORWARD STACKING of Turtle TV UHV's loss-cure settings on the "97.7%" setting, objective = TRAIN net $.

Zee 2026-11-06: "jaan fix each of these losses, as many as you can ... we're aggressively trying to achieve a 100% winrate on most days".
The setting loses ~$3.3 a trade on average, so cutting trades ALWAYS "helps" net. Therefore a move is ADMISSIBLE only if, on TRAIN:
    trades >= 600   and   WR >= the current stack's TRAIN WR + 0.05 points   and   net >= the current stack's TRAIN net + $200
($200 = about one average loss at 1 lot - my choice of "meaningful" for net; the WR margin is the real guard). Each step adds the admissible
move with the highest TRAIN net (ties: higher TRAIN WR, then more TRAIN trades); the search stops when nothing is admissible or after 8 steps.
TEST is scored on every run and reported, but never read by the choice.

Moves: every setting of the task's list (scan.py G["loss filters"] + the G["cause: ..."] groups; NOT the risk manager) at every value of its
scan.py grid (scan._values), a tuning knob only while its filter is on (scan._relevant) - re-tuning or switching off a chosen filter included.
TRAIN = entries before 2026-07-01 00:00 UTC (1782864000), TEST = from then on. Loss-free day = an FX day (17:00 NY -> 17:00 NY) with >= 1
trade and no losing trade, counted within each split (ALL counts all trades together; one FX day straddles the split).
Diagnostics per step: losses removed, $/trade, and the net gain BEYOND a random cut of the same number of trades at the stack's $/trade.

Python tick replay = HYPOTHESIS, NOT PROMOTED - only MT5's Strategy Tester or live fills promote (CLAUDE.md).
Run (Git Bash):  cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/stacks/net/stack_net.py
Outputs (this folder): run log on stdout, cache_<engine hash>.jsonl, steps.json, final_setting.json"""
import datetime as dt
import hashlib
import importlib.util
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))            # monitor/TurtleTVUHV
os.chdir(ROOT)
sys.path.insert(0, ROOT)

ENGINE_FILES = ("uhv_engine.py", "uhv_filters.py", "uhv_diamond.py", "scan.py", "sim.py")


def _hash():
    h = hashlib.sha1()
    for f in ENGINE_FILES:
        with open(os.path.join(ROOT, f), "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()[:10]


H0 = _hash()
import uhv_engine as U  # noqa: E402
import scan  # noqa: E402
if _hash() != H0:
    sys.exit("engine files changed while importing - run again")
_spec = importlib.util.spec_from_file_location("doctrine", os.path.join(os.path.dirname(ROOT), "doctrine.py"))
doctrine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(doctrine)

NY = ZoneInfo("America/New_York")
SPLIT = 1782864000                                   # 2026-07-01 00:00 UTC: TRAIN before, TEST from
BASE_FILE = os.path.join(ROOT, "settings", "saved", "2026-11-05 05-45-38.json")
MIN_TRAIN, WR_MARGIN, NET_MARGIN, MAX_STEPS = 600, 0.05, 200.0, 8
SETTINGS = ["InpUhvNoClose", "InpUhvMaxTrigSpread", "InpUhvStruct", "InpUhvSRPips", "InpUhvSRLook", "InpUhvSRAhead", "InpUhvSRAheadLook",
            "InpUhvBigFig", "InpUhvFigStep", "InpUhvRangeAtr", "InpUhvRangeBars", "InpUhvFreshBreak", "InpUhvFreshSwings", "InpUhvBrokeHighs",
            "InpUhvBrokeLook", "InpUhvMaxHumps", "InpUhvMinHumps", "InpUhvDeepRet", "InpUhvHtf5", "InpUhvHtf5N", "InpUhvCounterAtr",
            "InpUhvCounterBars", "InpUhvFriCutNY", "InpUhvRunPips", "InpUhvRunBars", "InpUhvLoudBrk", "InpUhvMinTicks", "InpUhvSunOpenMins",
            "InpUhvNewsNY", "InpUhvNewsMins", "InpUhvSpikeAtr", "InpUhvSpikeBars", "InpUhvHoliday", "InpUhvMinAtrPips", "InpUhvMaxGapPips"]
PARENT = {"InpUhvSRLook": "InpUhvSRPips", "InpUhvRangeBars": "InpUhvRangeAtr", "InpUhvFreshSwings": "InpUhvFreshBreak",
          "InpUhvBrokeLook": "InpUhvBrokeHighs", "InpUhvHtf5N": "InpUhvHtf5", "InpUhvSRAheadLook": "InpUhvSRAhead", "InpUhvFigStep": "InpUhvBigFig",
          "InpUhvCounterBars": "InpUhvCounterAtr", "InpUhvRunBars": "InpUhvRunPips", "InpUhvNewsMins": "InpUhvNewsNY",
          "InpUhvSpikeBars": "InpUhvSpikeAtr"}
GROUPS = ["loss filters"] + [g for g in scan.G if g.startswith("cause:")]
GRID = {k: spec for g in GROUPS for k, spec in scan.G[g].items() if k in SETTINGS}
_extra = sorted(k for g in GROUPS for k in scan.G[g] if k not in SETTINGS)
_missing = [k for k in SETTINGS if k not in GRID]
if _missing:
    sys.exit(f"settings missing from scan.py's grids: {_missing}")

RAW = json.load(open(BASE_FILE, encoding="utf-8"))
BASE = dict(RAW["inputs"])
for _k, (_d, _) in U.UHV_DEFAULTS.items():          # the loss-cure settings are not in the saved base: their defaults (all off)
    BASE.setdefault(_k, _d)


def canon(v):
    s = str(v).strip().lower()
    if s in ("true", "false"):
        return 1.0 if s == "true" else 0.0
    try:
        return float(s)
    except ValueError:
        return s


def eff(stack):
    """the stack's entries that differ from the base"""
    return {k: v for k, v in sorted(stack.items()) if canon(v) != canon(BASE.get(k, ""))}


def clean(stack):
    """eff() without tuning knobs whose filter is off (they cannot act)"""
    e = eff(stack)
    full = dict(BASE, **stack)
    return {k: v for k, v in e.items() if k not in PARENT or canon(full.get(PARENT[k], "0")) not in (0.0, "")}


def ckey(stack):
    return json.dumps(sorted((k, str(canon(v))) for k, v in eff(stack).items()))


_OFF = {}


def fxday(ts):
    """the FX day (17:00 New York -> 17:00 New York) of each UTC timestamp, as a day number: New York local time + 7 h"""
    ts = np.asarray(ts, dtype=np.float64)
    hrs = (ts // 3600).astype(np.int64)
    u, inv = np.unique(hrs, return_inverse=True)
    off = np.empty(len(u))
    for i, h in enumerate(u):                        # US DST switches on whole UTC hours, so one offset per UTC hour is exact
        h = int(h)
        if h not in _OFF:
            _OFF[h] = dt.datetime.fromtimestamp(h * 3600, NY).utcoffset().total_seconds()
        off[i] = _OFF[h]
    return ((ts + off[inv] + 7 * 3600) // 86400).astype(np.int64)


def stats(r):
    n = int(len(r))
    if n == 0:
        return dict(n=0, L=0, wr=0.0, net=0.0, npt=0.0, days=0, clean=0, clean_pct=0.0, avg_win=0.0, avg_loss=0.0)
    p = r[:, 6]
    loss = p < 0
    fd = fxday(r[:, 1])
    days, bad = np.unique(fd), np.unique(fd[loss])
    L = int(loss.sum())
    return dict(n=n, L=L, wr=100.0 * (n - L) / n, net=float(p.sum()), npt=float(p.sum()) / n, days=int(len(days)),
                clean=int(len(days) - len(bad)), clean_pct=100.0 * (len(days) - len(bad)) / len(days),
                avg_win=float(p[~loss].mean()) if (~loss).any() else 0.0, avg_loss=float(p[loss].mean()) if loss.any() else 0.0)


def run(stack):
    tr, _, cnt = U.simulate(dict(BASE, **stack))
    r = tr[tr[:, 10] == 0]
    res = {"train": stats(r[r[:, 1] < SPLIT]), "test": stats(r[r[:, 1] >= SPLIT]), "all": stats(r),
           "cnt": {k: int(v) for k, v in cnt.items()}}
    return res, r


CACHE_FILE = os.path.join(HERE, f"cache_{H0}.jsonl")
CACHE = {}
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                d = json.loads(line)
                CACHE[d["key"]] = d["res"]


def evaluate(stack):
    key = ckey(stack)
    if key in CACHE:
        return CACHE[key], True
    t0 = time.time()
    res, _ = run(stack)
    res["secs"] = round(time.time() - t0, 2)
    CACHE[key] = res
    with open(CACHE_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"key": key, "stack": eff(stack), "res": res}) + "\n")
    return res, False


def moves(stack):
    cur = dict(BASE, **stack)
    out = []
    for k in SETTINGS:
        if not scan._relevant(k, cur):
            continue
        for v in scan._values(GRID[k], cur[k]):
            out.append((k, v))
    return out


def admissible(c, cur):
    t, ct = c["train"], cur["train"]
    why = []
    if t["n"] < MIN_TRAIN:
        why.append(f"train trades {t['n']} < {MIN_TRAIN}")
    if t["wr"] < ct["wr"] + WR_MARGIN - 1e-9:
        why.append(f"WR {t['wr'] - ct['wr']:+.3f} pts < +{WR_MARGIN}")
    if t["net"] < ct["net"] + NET_MARGIN - 1e-9:
        why.append(f"net {t['net'] - ct['net']:+,.0f} < +{NET_MARGIN:,.0f}")
    return not why, "; ".join(why)


def rank(c):
    return (c["train"]["net"], c["train"]["wr"], c["train"]["n"])


def delta(a, b):
    return {"trades": b["n"] - a["n"], "losses_removed": a["L"] - b["L"], "wr": round(b["wr"] - a["wr"], 4),
            "clean_pct": round(b["clean_pct"] - a["clean_pct"], 3), "net": round(b["net"] - a["net"], 2), "npt": round(b["npt"] - a["npt"], 4),
            "excess_over_random_cut": round((b["net"] - a["net"]) + (a["n"] - b["n"]) * a["npt"], 2)}


def fmt(s):
    return (f"{s['n']:5d} tr {s['L']:4d} L  WR {s['wr']:6.2f}%  clean days {s['clean']:3d}/{s['days']:3d} ({s['clean_pct']:5.1f}%)  "
            f"net {s['net']:>10,.0f} ({s['npt']:+.2f}/tr)")


def rnd(s):
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}


def result_block(r):
    """the saved-setting 'result' block (the server's fields) for these trades"""
    p = r[:, 6]
    eq = np.cumsum(p[np.argsort(r[:, 4], kind="stable")])
    dd = float((np.maximum.accumulate(np.r_[0.0, eq])[1:] - eq).max()) if len(eq) else 0.0
    gw, gl = float(p[p > 0].sum()), float(-p[p < 0].sum())
    n, L = len(p), int((p < 0).sum())
    return {"n": int(n), "net": round(float(p.sum()), 2), "pf": round(gw / gl, 3) if gl > 0 else None, "wr": round(100 * (n - L) / max(n, 1), 2),
            "avg_loss": round(float(p[p < 0].mean()), 2) if L else 0.0, "worst_loss": round(float(p.min()), 2) if n else 0.0,
            "dd": round(dd, 2), "ret_dd": (float(p.sum()) / dd) if dd > 0 else None}


def main():
    t_start = time.time()
    print(f"engine hash {H0} ({', '.join(ENGINE_FILES)}); cache {os.path.basename(CACHE_FILE)} with {len(CACHE)} runs", flush=True)
    print(f"rule: TRAIN trades >= {MIN_TRAIN}, TRAIN WR >= current + {WR_MARGIN} pts, TRAIN net >= current + ${NET_MARGIN:,.0f}; "
          f"rank by TRAIN net; max {MAX_STEPS} steps", flush=True)
    if _extra:
        print(f"note: scan.py groups also hold {_extra} - not in the task's list, not searched", flush=True)

    # step 0: the base must reproduce the saved 97.7% result exactly (the added defaults are all off)
    base_res, base_rows = run({})
    a = base_res["all"]
    assert a["n"] == 7631 and a["L"] == 172 and abs(a["net"] - (-25525.97)) < 0.05, f"base does not reproduce: {a}"
    rb = result_block(base_rows)
    print(f"BASE reproduces the saved setting: {a['n']} trades, {a['L']} losses, net {a['net']:,.2f}; result block {rb}", flush=True)
    nyd = [(dt.datetime.fromtimestamp(x, NY) + dt.timedelta(hours=7)).strftime("%Y-%m-%d") for x in base_rows[:, 1]]
    mine = fxday(base_rows[:, 1])
    assert all(dt.datetime.fromtimestamp(int(d) * 86400, dt.timezone.utc).strftime("%Y-%m-%d") == s for d, s in zip(mine, nyd)), "FX-day mismatch"
    print("FX-day labels match cause_settings_eval.nyday on all base trades", flush=True)

    stack = {}
    cur, _ = evaluate(stack)
    print(f"step 0 BASE   TRAIN {fmt(cur['train'])}\n              TEST  {fmt(cur['test'])}\n              ALL   {fmt(cur['all'])}", flush=True)
    steps = [{"step": 0, "setting": None, "value": None, "stack": {}, "train": rnd(cur["train"]), "test": rnd(cur["test"]), "all": rnd(cur["all"])}]
    log = {"objective": "maximise TRAIN net $ subject to TRAIN WR rising >= 0.05 pts per step, TRAIN net rising >= $200, TRAIN trades >= 600",
           "base_file": BASE_FILE, "split_utc": SPLIT, "engine_hash": H0, "grid": {k: GRID[k] for k in SETTINGS},
           "rule": {"min_train": MIN_TRAIN, "wr_margin": WR_MARGIN, "net_margin": NET_MARGIN, "max_steps": MAX_STEPS}, "steps": steps}
    stop_reason = f"reached {MAX_STEPS} steps"
    for step in range(1, MAX_STEPS + 1):
        cands = moves(stack)
        print(f"\n=== step {step}: {len(cands)} moves on top of {eff(stack) or 'the base'}", flush=True)
        results = []
        for i, (k, v) in enumerate(cands, 1):
            s2 = dict(stack, **{k: v})
            res, hit = evaluate(s2)
            ok, why = admissible(res, cur)
            results.append((k, v, res, ok, why))
            t = res["train"]
            print(f"  [{step}.{i:3d}/{len(cands)}] {k[6:]:>14s}={v:<6s} TRAIN {t['n']:5d} tr {t['L']:4d} L WR {t['wr']:6.2f}% "
                  f"clean {t['clean_pct']:5.1f}% net {t['net']:>9,.0f}  {'ADMISSIBLE' if ok else ''}{' (cache)' if hit else ''}", flush=True)
        adm = sorted([x for x in results if x[3]], key=lambda x: rank(x[2]), reverse=True)
        rej = sorted([x for x in results if not x[3]], key=lambda x: rank(x[2]), reverse=True)
        cand_tab = [[k, v, x["train"]["n"], x["train"]["L"], round(x["train"]["wr"], 3), round(x["train"]["net"], 1),
                     round(x["train"]["clean_pct"], 2), ok, why] for k, v, x, ok, why in results]
        if not adm:
            stop_reason = f"step {step}: no admissible move among {len(cands)}"
            print(f"\nSTOP - {stop_reason}. Best TRAIN net among the rejected:", flush=True)
            for k, v, x, _, why in rej[:5]:
                print(f"     {k}={v}: TRAIN {fmt(x['train'])}  - {why}", flush=True)
            log["stop_candidates"] = cand_tab
            break
        k, v, res, _, _ = adm[0]
        prev = cur
        stack = dict(stack, **{k: v})
        cur = res
        rec = {"step": step, "setting": k, "value": v, "stack": eff(stack), "train": rnd(cur["train"]), "test": rnd(cur["test"]),
               "all": rnd(cur["all"]), "delta": {"train": delta(prev["train"], cur["train"]), "test": delta(prev["test"], cur["test"])},
               "moves_tried": len(cands), "admissible": len(adm),
               "runners_up": [{"setting": k2, "value": v2, "train": rnd(x2["train"]), "test": rnd(x2["test"])} for k2, v2, x2, _, _ in adm[1:6]],
               "best_rejected": [{"setting": k2, "value": v2, "train": rnd(x2["train"]), "why": w2} for k2, v2, x2, _, w2 in rej[:5]],
               "candidates": cand_tab}
        steps.append(rec)
        dtr, dte = rec["delta"]["train"], rec["delta"]["test"]
        print(f"\n>>> step {step} ADDS {k}={v}  ({len(adm)} admissible of {len(cands)})", flush=True)
        print(f"    TRAIN {fmt(cur['train'])}\n          d trades {dtr['trades']:+d}, losses removed {dtr['losses_removed']:+d}, WR {dtr['wr']:+.3f}, "
              f"clean {dtr['clean_pct']:+.1f} pts, net {dtr['net']:+,.0f}, beyond a random cut {dtr['excess_over_random_cut']:+,.0f}", flush=True)
        print(f"    TEST  {fmt(cur['test'])}\n          d trades {dte['trades']:+d}, losses removed {dte['losses_removed']:+d}, WR {dte['wr']:+.3f}, "
              f"clean {dte['clean_pct']:+.1f} pts, net {dte['net']:+,.0f}, beyond a random cut {dte['excess_over_random_cut']:+,.0f}", flush=True)
        print(f"    ALL   {fmt(cur['all'])}", flush=True)
        for k2, v2, x2, _, _ in adm[1:4]:
            print(f"    runner-up {k2}={v2}: TRAIN {fmt(x2['train'])}", flush=True)
        log["stop_reason"] = None
        with open(os.path.join(HERE, "steps.json"), "w", encoding="utf-8") as fh:
            json.dump(log, fh, indent=1)
    log["stop_reason"] = stop_reason

    # the final stack, re-run fresh (no cache), knobs of switched-off filters dropped
    final = clean(stack)
    res2, rows2 = run(final)
    for part in ("train", "test", "all"):
        for f in ("n", "L", "net", "clean", "days"):
            assert abs(res2[part][f] - cur[part][f]) < 1e-6, f"fresh re-run differs on {part}.{f}: {res2[part][f]} vs {cur[part][f]}"
    print(f"\nfresh re-run of the final stack {final} reproduces the cached numbers", flush=True)
    rb2 = result_block(rows2)
    log.update(final_stack=final, final={p: rnd(res2[p]) for p in ("train", "test", "all")}, final_result=rb2,
               base={p: rnd(base_res[p]) for p in ("train", "test", "all")}, base_result=rb, minutes=round((time.time() - t_start) / 60, 1))
    with open(os.path.join(HERE, "steps.json"), "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=1)
    setting = {"name": "97.7% + net-stack (loss study, greedy, chosen on TRAIN Mar-Jun) - Python hypothesis, NOT PROMOTED",
               "inputs": dict(RAW["inputs"], **final), "changed": dict(RAW.get("changed", {}), **final), "ds": RAW.get("ds", "year1"),
               "mode": RAW.get("mode", "ea"), "result": rb2, "lab": {}, "lab_describe": "",
               "research": {"script": os.path.abspath(__file__), "objective": log["objective"], "stack_order": [[s["setting"], s["value"]] for s in steps[1:]],
                            "train": rnd(res2["train"]), "test": rnd(res2["test"]), "all": rnd(res2["all"]), "engine_hash": H0,
                            "note": "Python tick replay: a hypothesis. Only MT5's Strategy Tester or live fills promote."}}
    with open(os.path.join(HERE, "final_setting.json"), "w", encoding="utf-8") as fh:
        json.dump(setting, fh, indent=1)

    print("\n" + "=" * 150, flush=True)
    print(f"{'step':>4s} {'setting=value':32s} | {'TRAIN trades/L/WR/clean%/net':54s} | {'TEST trades/L/WR/clean%/net':54s}")
    for s in steps:
        mv = "BASE" if s["step"] == 0 else f"+ {s['setting']}={s['value']}"
        t, e = s["train"], s["test"]
        print(f"{s['step']:4d} {mv:32s} | {t['n']:5d} {t['L']:4d} {t['wr']:6.2f}% {t['clean_pct']:5.1f}% {t['net']:>10,.0f} ({t['npt']:+.2f}) | "
              f"{e['n']:5d} {e['L']:4d} {e['wr']:6.2f}% {e['clean_pct']:5.1f}% {e['net']:>10,.0f} ({e['npt']:+.2f})")
    print(f"stop: {stop_reason}")
    for p in ("train", "test", "all"):
        print(f"FINAL {p.upper():5s} {fmt(res2[p])}   (base {fmt(base_res[p])})")
    print(f"final result block (ALL): {rb2}")
    be = 100 * abs(res2["all"]["avg_loss"]) / (abs(res2["all"]["avg_loss"]) + res2["all"]["avg_win"]) if res2["all"]["avg_loss"] else None
    doctrine.python_says("net-stack, ALL trades (Python tick replay)", win_pct=res2["all"]["wr"], need_pct=be)
    print(f"done in {(time.time() - t_start) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
