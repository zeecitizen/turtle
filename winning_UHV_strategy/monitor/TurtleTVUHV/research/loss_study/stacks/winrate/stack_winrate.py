"""stack_winrate.py - greedy FORWARD STACKING of Turtle TV UHV's loss-cure settings on the "97.7%" setting (2026-11-05 05-45-38).

Zee 2026-11-06: "we're aggressively trying to achieve a 100% winrate on most days now". This search asks: stacking the loss-study settings one at
a time, how high can the TRAIN win rate go while the stack keeps at least 600 TRAIN trades?

  universe   every setting of scan.G["loss filters"] and every scan.G["cause: ..."] group, at every value of its scan.py grid (scan._values);
             a filter's tuning knob only while that filter is on (scan._relevant - the scanner's own rule). Bools are written "1" / "0".
  scoring    uhv_engine.simulate(base + stack + move): real rows (rows[:, 10] == 0), a loss = rows[:, 6] < 0, entry time rows[:, 1].
             TRAIN = entries before 2026-07-01 00:00 UTC (1782864000), TEST = from then on. A loss-free day = an FX day (17:00 New York to
             17:00 New York) with >= 1 trade and no losing trade; "% loss-free" uses a FIXED denominator = the days the BASE traded in that half
             (83 TRAIN / 92 TEST / 175 ALL), so a day the stack does not trade never counts as clean.
  objective  maximise the TRAIN win rate (exact fraction), only moves keeping >= 600 TRAIN trades; ties -> more TRAIN trades -> key / value.
             A move is taken only if it adds >= 0.05 WR points; at most 8 steps. TEST is scored for every candidate and NEVER used to choose.
  guards     the bare base is re-simulated before every step and must give 7631 / 172 / -25,525.97 and the setups file must be unchanged
             (the engine is being edited live); file hashes, the exact grid and the knob map are written into results.json after every step.

Python tick replay = a HYPOTHESIS. Nothing here is promoted until MT5's Strategy Tester or live fills confirm it.
Run (Git Bash):  cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/stacks/winrate/stack_winrate.py
Verify later:    ... stack_winrate.py --verify     (re-runs the base and the final stack in a fresh process with the engine on disk now)"""
import datetime as dt
import hashlib
import json
import math
import os
import sys
import time
from zoneinfo import ZoneInfo

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))          # monitor/TurtleTVUHV
sys.path.insert(0, ROOT)
import numpy as np  # noqa: E402

import uhv_engine as U  # noqa: E402
import scan as SC  # noqa: E402

BASE_FILE = os.path.join(ROOT, "settings", "saved", "2026-11-05 05-45-38.json")
SETUPS_JSON = os.path.join(ROOT, "simdata", "uhv_setups.json")
RESULTS = os.path.join(HERE, "results.json")
FINAL_SETTING = os.path.join(HERE, "final_setting.json")
SPLIT = 1782864000                    # 2026-07-01 00:00 UTC
MIN_TRAIN = 600
MARGIN = 0.05                         # WR points on TRAIN
MAX_STEPS = 8
EXPECT_BASE = (7631, 172, -25525.97)
NY = ZoneInfo("America/New_York")
GROUPS = ["loss filters"] + [g for g in SC.G if g.startswith("cause: ")]
KEYS = [k for g in GROUPS for k in SC.G[g]]
GRID = {k: SC.SPEC[k] for k in KEYS}
KNOB = {"InpUhvSRLook": "InpUhvSRPips", "InpUhvRangeBars": "InpUhvRangeAtr", "InpUhvFreshSwings": "InpUhvFreshBreak",
        "InpUhvBrokeLook": "InpUhvBrokeHighs", "InpUhvHtf5N": "InpUhvHtf5", "InpUhvSRAheadLook": "InpUhvSRAhead", "InpUhvFigStep": "InpUhvBigFig",
        "InpUhvCounterBars": "InpUhvCounterAtr", "InpUhvRunBars": "InpUhvRunPips", "InpUhvNewsMins": "InpUhvNewsNY", "InpUhvSpikeBars": "InpUhvSpikeAtr"}
DEF = {k: U.UHV_DEFAULTS[k][0] for k in KEYS}


def norm(v):
    s = str(v).strip().lower()
    if s == "true":
        return "1"
    if s == "false":
        return "0"
    try:
        return f"{float(s):g}"
    except ValueError:
        return s


def sha1(path):
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def setups_sig():
    st = os.stat(SETUPS_JSON)
    return {"size": st.st_size, "mtime": st.st_mtime}


def load_base():
    B = dict(json.load(open(BASE_FILE, encoding="utf-8"))["inputs"])
    for k, d in U.UHV_DEFAULTS.items():                     # the base was saved before the loss filters existed: fill their defaults (off)
        B.setdefault(k, d[0])
    return B


BASE = load_base()


# ------------------------------------------------------------------ scoring
_DAYC = {}


def fxday(ts):
    """the FX day (17:00 NY -> 17:00 NY) labelled by its closing date; constant within a UTC hour (NY offsets and DST jumps are whole hours)"""
    h = int(ts // 3600)
    d = _DAYC.get(h)
    if d is None:
        d = (dt.datetime.fromtimestamp(h * 3600, NY) + dt.timedelta(hours=7)).strftime("%Y-%m-%d")
        _DAYC[h] = d
    return d


DENOM = {}                            # the base's trading days per half (set from the base run)


def half(r, part):
    p = r[:, 6]
    n, L = int(len(p)), int((p < 0).sum())
    days = {}
    for ts, x in zip(r[:, 1], p):
        d = fxday(ts)
        days[d] = days.get(d, False) or bool(x < 0)
    lfd = sum(1 for v in days.values() if not v)
    den = DENOM.get(part) or max(len(days), 1)
    return {"n": n, "L": L, "wr": (100.0 * (n - L) / n) if n else 0.0, "net": round(float(p.sum()), 2), "days": len(days), "lfd": lfd,
            "lfd_pct": 100.0 * lfd / den, "lfd_pct_traded": (100.0 * lfd / len(days)) if days else 0.0, "den": den}


def score(tr):
    r = tr[tr[:, 10] == 0]
    m = r[:, 1] < SPLIT
    return {"train": half(r[m], "train"), "test": half(r[~m], "test"), "all": half(r, "all")}


def binom_le(L, n, p):
    """P(X <= L), X ~ Binomial(n, p): how likely this few losses are if the stack had the base loss rate"""
    if n <= 0:
        return 1.0
    if p <= 0:
        return 1.0
    lp, lq = math.log(p), math.log1p(-p)
    tot = 0.0
    for x in range(0, L + 1):
        tot += math.exp(math.lgamma(n + 1) - math.lgamma(x + 1) - math.lgamma(n - x + 1) + x * lp + (n - x) * lq)
    return min(1.0, tot)


def fmt(h):
    return (f"{h['n']} / {h['L']} / {h['wr']:.2f}% / {h['lfd_pct']:.1f}% ({h['lfd']} of {h['den']} days; {h['days']} traded) / "
            f"{'-' if h['net'] < 0 else '+'}${abs(h['net']):,.0f}")


# ------------------------------------------------------------------ moves and the cache
def is_on(stack, k):
    return SC._f(norm(stack.get(k, DEF[k]))) > 0


def eff_key(stack):
    cur = {k: norm(stack.get(k, DEF[k])) for k in KEYS}
    for kn, f in KNOB.items():
        if SC._f(cur[f]) <= 0:
            cur[kn] = norm(DEF[kn])
    parts = [f"{k}={cur[k]}" for k in KEYS if cur[k] != norm(DEF[k])]
    return "|".join(parts) or "BASE"


def apply(stack, k, v):
    s = dict(stack)
    if norm(v) == norm(DEF[k]):
        s.pop(k, None)
    else:
        s[k] = norm(v)
    for kn, f in KNOB.items():                                # a knob of a filter that is off does nothing: drop it
        if not is_on(s, f):
            s.pop(kn, None)
    return s


def candidates(stack):
    cur = dict(BASE, **stack)
    out = []
    for k in KEYS:
        if not SC._relevant(k, cur):
            continue
        spec = GRID[k]
        if spec == "bool":
            vals = ["0"] if SC._f(norm(cur[k])) > 0.5 else ["1"]
        else:
            vals = [norm(v) for v in SC._values(spec, cur[k])]
        for v in dict.fromkeys(vals):
            if v != norm(cur[k]):
                out.append((k, v))
    return out


ENGINE_FILES = ["uhv_engine.py", "uhv_filters.py", "uhv_diamond.py", "uhv_ticks.py", "sim.py", "scan.py"]
HASHES = {f: sha1(os.path.join(ROOT, f)) for f in ENGINE_FILES}
_ck = hashlib.sha1((HASHES["uhv_engine.py"] + HASHES["uhv_filters.py"] + HASHES["uhv_diamond.py"] + sha1(BASE_FILE)
                    + json.dumps(setups_sig())).encode()).hexdigest()[:10]
CACHE_FILE = os.path.join(HERE, f"cache_{_ck}.json")
CACHE = json.load(open(CACHE_FILE, encoding="utf-8")) if os.path.exists(CACHE_FILE) else {}
_dirty = [0]


def save_cache():
    tmp = CACHE_FILE + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(CACHE, f, separators=(",", ":"))
    os.replace(tmp, CACHE_FILE)
    _dirty[0] = 0


def run(stack):
    key = eff_key(stack)
    if key in CACHE:
        return CACHE[key], True
    t0 = time.time()
    tr, _, cnt = U.simulate(dict(BASE, **stack))
    st = score(tr)
    st["secs"] = round(time.time() - t0, 2)
    st["cnt"] = {k: int(v) for k, v in cnt.items()}
    CACHE[key] = st
    _dirty[0] += 1
    if _dirty[0] >= 20:
        save_cache()
    return st, False


def check_base(sig0):
    """the bare base, never from the cache: the engine / setups must not have changed under us"""
    tr, _, _ = U.simulate(dict(BASE))
    r = tr[tr[:, 10] == 0]
    got = (int(len(r)), int((r[:, 6] < 0).sum()), round(float(r[:, 6].sum()), 2))
    sig = setups_sig()
    if got != EXPECT_BASE or sig != sig0:
        raise SystemExit(f"STOP: the base no longer reproduces (got {got}, expected {EXPECT_BASE}; setups file {sig} vs {sig0}) - the engine "
                         f"or the data changed during the search; results so far are in {RESULTS}")
    return got


def obj_key(st, k="", v=""):
    """sort key, best first: TRAIN win rate (exact fraction), then more TRAIN trades, then name / value for a deterministic order"""
    tr = st["train"]
    return (-((tr["n"] - tr["L"]) / tr["n"]) if tr["n"] else 1.0, -tr["n"], k, v)


def slim(h):
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in h.items()}


def write_results(R):
    tmp = RESULTS + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(R, f, indent=1)
    os.replace(tmp, RESULTS)


# ------------------------------------------------------------------ the search
def main():
    t_start = time.time()
    for kn, f in KNOB.items():                                # the knob map must be the scanner's own
        assert kn in KEYS and f in KEYS, (kn, f)
        assert not SC._relevant(kn, dict(BASE)), f"{kn} acts with {f} off?"
        assert SC._relevant(kn, dict(BASE, **{f: "1"})), f"{kn} does not act with {f} on?"
    for k in KEYS:
        assert k in U.UHV_DEFAULTS, k
        if k not in KNOB:
            assert SC._relevant(k, dict(BASE)), k
    sig0 = setups_sig()
    got = check_base(sig0)
    base_tr, _, _ = U.simulate(dict(BASE))
    rb = base_tr[base_tr[:, 10] == 0]
    mb = rb[:, 1] < SPLIT
    for part, rr in (("train", rb[mb]), ("test", rb[~mb]), ("all", rb)):
        DENOM[part] = len({fxday(ts) for ts in rr[:, 1]})
    base = score(base_tr)
    p0 = {"train": base["train"]["L"] / base["train"]["n"], "test": base["test"]["L"] / base["test"]["n"]}
    print(f"BASE {got}: TRAIN {fmt(base['train'])}\n     TEST  {fmt(base['test'])}\n     ALL   {fmt(base['all'])}", flush=True)
    print(f"universe: {len(KEYS)} settings in {GROUPS}; cache {os.path.basename(CACHE_FILE)} ({len(CACHE)} entries)", flush=True)
    R = {"script": os.path.abspath(__file__), "started": dt.datetime.now().isoformat(timespec="seconds"),
         "objective": f"maximise TRAIN win rate with >= {MIN_TRAIN} TRAIN trades; step only if +{MARGIN} WR points; max {MAX_STEPS} steps",
         "doctrine": "Python tick replay = HYPOTHESIS, not promoted; MT5 Strategy Tester or live fills promote. TEST never used to choose.",
         "base_file": BASE_FILE, "split_utc": SPLIT, "engine_hashes": HASHES, "setups_json": sig0, "cache_file": CACHE_FILE,
         "groups": GROUPS, "grid": {k: GRID[k] for k in KEYS}, "knob_map": KNOB, "defaults": DEF,
         "loss_free_day": "FX day 17:00 NY -> 17:00 NY with >= 1 trade and no losing trade; lfd_pct = loss-free days / the BASE's trading days "
                          "in that half (fixed denominator); lfd_pct_traded = loss-free days / days the stack traded",
         "base": {p: slim(base[p]) for p in ("train", "test", "all")}, "steps": [], "candidates": {}, "stop_reason": None}
    write_results(R)
    stack, cur = {}, base
    for step in range(1, MAX_STEPS + 1):
        check_base(sig0)
        cands = candidates(stack)
        print(f"\n=== step {step}: {len(cands)} candidate moves on stack {stack or '{}'} (TRAIN WR now {cur['train']['wr']:.3f}%)", flush=True)
        res = []
        for i, (k, v) in enumerate(cands, 1):
            s2 = apply(stack, k, v)
            st, hit = run(s2)
            res.append((k, v, s2, st))
            tr_, te_ = st["train"], st["test"]
            print(f"  [{step}] {i:3d}/{len(cands)} {k}={v:<6s} TRAIN {tr_['n']:5d}/{tr_['L']:3d} {tr_['wr']:7.3f}%  lfd {tr_['lfd']:3d}  |  TEST "
                  f"{te_['n']:5d}/{te_['L']:3d} {te_['wr']:7.3f}%  lfd {te_['lfd']:3d}  {'(cache)' if hit else str(st.get('secs')) + 's'}", flush=True)
        save_cache()
        res.sort(key=lambda x: obj_key(x[3], x[0], x[1]))
        feas = [x for x in res if x[3]["train"]["n"] >= MIN_TRAIN]
        R["candidates"][str(step)] = [{"k": k, "v": v, "train": slim(st["train"]), "test": slim(st["test"]), "feasible": st["train"]["n"] >= MIN_TRAIN}
                                      for k, v, _, st in res]
        print(f"  top feasible (TRAIN >= {MIN_TRAIN}):", flush=True)
        for k, v, _, st in feas[:8]:
            print(f"     {k}={v:<6s} TRAIN {fmt(st['train'])}   TEST {fmt(st['test'])}", flush=True)
        if not feas:
            R["stop_reason"] = f"step {step}: no move keeps >= {MIN_TRAIN} TRAIN trades"
            write_results(R)
            break
        k, v, s2, st = feas[0]
        gain = st["train"]["wr"] - cur["train"]["wr"]
        if gain < MARGIN - 1e-9:
            R["stop_reason"] = (f"step {step}: the best feasible move ({k}={v}) adds only {gain:+.3f} TRAIN WR points (< {MARGIN}); "
                                f"stack frozen after {step - 1} steps")
            print("  STOP:", R["stop_reason"], flush=True)
            write_results(R)
            break
        prev = cur
        stack, cur = s2, st
        entry = {"step": step, "setting": k, "value": v, "stack": dict(stack), "train": slim(st["train"]), "test": slim(st["test"]),
                 "all": slim(st["all"]), "train_wr_gain": round(gain, 4), "test_wr_change": round(st["test"]["wr"] - prev["test"]["wr"], 4),
                 "test_wr_vs_base": round(st["test"]["wr"] - base["test"]["wr"], 4),
                 "test_p_vs_base_rate": binom_le(st["test"]["L"], st["test"]["n"], p0["test"]),
                 "train_str": fmt(st["train"]), "test_str": fmt(st["test"]), "all_str": fmt(st["all"]),
                 "n_candidates": len(res), "n_feasible": len(feas),
                 "runner_ups": [{"k": a, "v": b, "train_wr": round(c["train"]["wr"], 4), "train_n": c["train"]["n"]} for a, b, _, c in feas[1:6]]}
        R["steps"].append(entry)
        print(f"  >>> TAKE {k}={v}: TRAIN WR {gain:+.3f} -> {fmt(st['train'])}\n      TEST {fmt(st['test'])} (change {entry['test_wr_change']:+.3f}, "
              f"vs base {entry['test_wr_vs_base']:+.3f}, binomial p {entry['test_p_vs_base_rate']:.3g})", flush=True)
        write_results(R)
    else:
        R["stop_reason"] = f"reached the {MAX_STEPS}-step cap"
    final = cur
    R["final"] = {"stack": dict(stack), "inputs_changed": dict(stack), "train": slim(final["train"]), "test": slim(final["test"]),
                  "all": slim(final["all"]), "train_str": fmt(final["train"]), "test_str": fmt(final["test"]), "all_str": fmt(final["all"]),
                  "test_p_vs_base_rate": binom_le(final["test"]["L"], final["test"]["n"], p0["test"]),
                  "train_p_vs_base_rate": binom_le(final["train"]["L"], final["train"]["n"], p0["train"])}
    R["engine_hashes_at_end"] = {f: sha1(os.path.join(ROOT, f)) for f in ENGINE_FILES}
    R["engine_changed_during_run"] = R["engine_hashes_at_end"] != HASHES
    R["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    R["minutes"] = round((time.time() - t_start) / 60, 1)
    write_results(R)
    out = dict(json.load(open(BASE_FILE, encoding="utf-8")))
    out["name"] = "2026-11-05 05-45-38 + winrate stack (loss study, greedy, TRAIN-chosen)"
    out["inputs"] = dict(BASE, **stack)
    out["changed"] = dict(stack)
    out["result"] = {"n": final["all"]["n"], "net": final["all"]["net"], "wr": round(final["all"]["wr"], 2), "losses": final["all"]["L"]}
    out["note"] = "Python tick replay (Turtle TV UHV) = hypothesis, NOT promoted. Chosen on TRAIN (Mar 6 - Jun 30) only. See results.json."
    with open(FINAL_SETTING, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"\nSTOP REASON: {R['stop_reason']}\nFINAL STACK {stack}\n  TRAIN {fmt(final['train'])}\n  TEST  {fmt(final['test'])}\n  ALL   "
          f"{fmt(final['all'])}\n  TEST binomial p vs base rate {R['final']['test_p_vs_base_rate']:.3g}\n  engine changed during run: "
          f"{R['engine_changed_during_run']}\n  {R['minutes']} min", flush=True)


def verify():
    """a fresh process: the base and the final stack with the engine on disk NOW, against what results.json recorded"""
    R = json.load(open(RESULTS, encoding="utf-8"))
    sig0 = setups_sig()
    check_base(sig0)
    base_tr, _, _ = U.simulate(dict(BASE))
    rb = base_tr[base_tr[:, 10] == 0]
    mb = rb[:, 1] < SPLIT
    for part, rr in (("train", rb[mb]), ("test", rb[~mb]), ("all", rb)):
        DENOM[part] = len({fxday(ts) for ts in rr[:, 1]})
    stack = R["final"]["stack"]
    tr, _, _ = U.simulate(dict(BASE, **stack))
    st = score(tr)
    ok = all(st[p]["n"] == R["final"][p]["n"] and st[p]["L"] == R["final"][p]["L"] and abs(st[p]["net"] - R["final"][p]["net"]) < 0.01
             for p in ("train", "test", "all"))
    print("engine hashes now == at run start:", {f: sha1(os.path.join(ROOT, f)) == R["engine_hashes"][f] for f in ENGINE_FILES})
    for p in ("train", "test", "all"):
        print(f"  {p.upper():5s} now {fmt(st[p])}\n        recorded {R['final'][p + '_str']}")
    print("REPRODUCES" if ok else "DOES NOT REPRODUCE")
    R["verify"] = {"at": dt.datetime.now().isoformat(timespec="seconds"), "reproduces": ok,
                   "hashes_now": {f: sha1(os.path.join(ROOT, f)) for f in ENGINE_FILES}}
    write_results(R)


if __name__ == "__main__":
    if "--verify" in sys.argv:
        verify()
    else:
        main()
