"""stack_search.py - greedy FORWARD STACKING of the loss-cure settings for LOSS-FREE DAYS (research/loss_study/stacks/cleandays).

Zee 2026-11-06: "we're aggressively trying to achieve a 100% winrate on most days now". Objective: maximise the TRAIN share of loss-free
days (FX days 17:00 NY -> 17:00 NY with >= 1 trade and no losing trade, divided by the TRAIN days that still have a trade), subject to
  * TRAIN days with a trade >= 70% of the BASE's TRAIN trading days (83 -> at least 59), and
  * TRAIN trades >= 400.
TRAIN = entries before 2026-07-01 00:00 UTC; TEST = from then on. Moves are chosen on TRAIN only; TEST is printed for each step but never
used to choose.

Each step tries every move: each setting of scan.py's G["loss filters"] and G["cause: ..."] groups at each value of its grid (scan._values),
a tuning knob only while its filter is on (scan._relevant) - on the base + the stack so far, in the engine itself (uhv_engine.simulate:
freed slots and one-position blocking are real). The best feasible move (highest TRAIN loss-free share; ties -> higher TRAIN WR, then
more TRAIN trades, then the move listed first) is added if it lifts the TRAIN loss-free share by >= 1.0 point; else the search stops.
At most 8 steps. Every result is cached in cache.json (atomic writes), so a killed run resumes.

Python tick replay = HYPOTHESIS. Only MT5 or live fills promote (CLAUDE.md, monitor/doctrine.py).
Run:  cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/stacks/cleandays/stack_search.py"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import uhv_engine as U  # noqa: E402
import scan  # noqa: E402

GROUPS = ["loss filters"] + [g for g in scan.G if g.startswith("cause:")]
KEYS = [k for g in GROUPS for k in scan.G[g]]
MIN_COVER = 0.70
MIN_TRADES = 400
MARGIN = 1.0                 # points of TRAIN loss-free-day share a step must add
MAX_STEPS = 8
CACHE_F = os.path.join(HERE, "cache.json")
RESULTS_F = os.path.join(HERE, "results.json")
PARTS = ("n", "L", "wr", "net", "days", "clean", "clean_pct")

B = C.base_inputs()
cache = json.load(open(CACHE_F, encoding="utf-8")) if os.path.exists(CACHE_F) else {}
_dirty = [0]


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def same(a, b):
    fa, fb = _f(a), _f(b)
    if fa is not None and fb is not None:
        return abs(fa - fb) < 1e-12
    sa, sb = str(a).strip().lower(), str(b).strip().lower()
    alias = {"true": "1", "false": "0"}
    return alias.get(sa, sa) == alias.get(sb, sb)


def norm(changes):
    return {k: v for k, v in changes.items() if not same(v, B.get(k, "0"))}


def ckey(changes):
    return json.dumps(sorted(norm(changes).items()))


def save_cache(force=False):
    _dirty[0] += 1
    if force or _dirty[0] >= 10:
        tmp = CACHE_F + f".{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, separators=(",", ":"))
        os.replace(tmp, CACHE_F)
        _dirty[0] = 0


def run(changes):
    k = ckey(changes)
    if k in cache:
        return cache[k]
    rows, _, cnt = U.simulate(dict(B, **changes))
    s = C.score(rows)
    rec = {p: {q: s[p][q] for q in PARTS} for p in ("train", "test", "all")}
    rec["n_loss_keys"] = len(s["loss_keys"])
    cache[k] = rec
    save_cache()
    return rec


def fmt(x):
    return f"{x['n']} / {x['L']} / {x['wr']:.2f}% / {x['clean_pct']:.1f}% ({x['clean']}/{x['days']}) / {x['net']:+,.0f}"


def main():
    t_start = time.time()
    base = run({})
    base_days = base["train"]["days"]
    min_days = MIN_COVER * base_days

    def feasible(rec):
        return rec["train"]["days"] >= min_days - 1e-9 and rec["train"]["n"] >= MIN_TRADES

    def obj(rec):
        return (rec["train"]["clean_pct"], rec["train"]["wr"], rec["train"]["n"])

    print(f"BASE  TRAIN {fmt(base['train'])}  |  TEST {fmt(base['test'])}  |  ALL {fmt(base['all'])}", flush=True)
    print(f"constraints: TRAIN days with a trade >= {min_days:.1f} (70% of {base_days}), TRAIN trades >= {MIN_TRADES}; margin {MARGIN} pt", flush=True)
    stack, cur, steps, history = {}, base, [], []
    for step in range(1, MAX_STEPS + 1):
        full = dict(B, **stack)
        cands, t0 = [], time.time()
        for k in KEYS:
            if not scan._relevant(k, full):
                continue
            for v in scan._values(scan.SPEC[k], full.get(k, "0")):
                mv = dict(stack); mv[k] = v
                rec = run(mv)
                cands.append({"key": k, "value": v, "rec": rec, "feasible": feasible(rec)})
        save_cache(force=True)
        order = sorted(range(len(cands)), key=lambda i: (obj(cands[i]["rec"]), -i), reverse=True)
        feas = [cands[i] for i in order if cands[i]["feasible"]]
        infeas = [cands[i] for i in order if not cands[i]["feasible"]]
        print(f"\n=== step {step}: {len(cands)} moves in {time.time() - t0:.0f}s; stack so far {norm(stack)}", flush=True)
        print("  top feasible moves (TRAIN objective; TEST shown, never used):", flush=True)
        for c in feas[:12]:
            r = c["rec"]
            print(f"    {c['key']}={c['value']:<6s} TRAIN {fmt(r['train'])}  TEST {fmt(r['test'])}", flush=True)
        if infeas and obj(infeas[0]["rec"]) > (obj(feas[0]["rec"]) if feas else (-1, -1, -1)):
            r = infeas[0]["rec"]
            print(f"  best INFEASIBLE (floor binds): {infeas[0]['key']}={infeas[0]['value']} TRAIN {fmt(r['train'])}  TEST {fmt(r['test'])}", flush=True)
        history.append({"step": step, "stack_before": norm(stack),
                        "candidates": [{"key": c["key"], "value": c["value"], "feasible": c["feasible"],
                                        "train": c["rec"]["train"], "test": c["rec"]["test"]} for c in (cands[i] for i in order)]})
        if not feas:
            print("  no feasible move - stop", flush=True)
            break
        best = feas[0]
        gain = best["rec"]["train"]["clean_pct"] - cur["train"]["clean_pct"]
        if gain < MARGIN - 1e-9:
            print(f"  best move {best['key']}={best['value']} adds only {gain:+.2f} pt of TRAIN loss-free days (< {MARGIN}) - stop", flush=True)
            break
        stack[best["key"]] = best["value"]
        cur = best["rec"]
        steps.append({"step": step, "setting": best["key"], "value": best["value"], "gain_pt": round(gain, 3),
                      "train": cur["train"], "test": cur["test"], "all": cur["all"], "stack": norm(stack)})
        print(f"  ADD {best['key']}={best['value']}  (+{gain:.2f} pt)  ->  TRAIN {fmt(cur['train'])}  |  TEST {fmt(cur['test'])}", flush=True)
        with open(RESULTS_F, "w", encoding="utf-8") as f:
            json.dump({"base": base, "steps": steps, "final_stack": norm(stack), "history": history, "done": False}, f, indent=1)
    final = run(stack)
    out = {"base": base, "steps": steps, "final_stack": norm(stack), "final": final, "history": history, "done": True,
           "constraints": {"min_train_days": min_days, "base_train_days": base_days, "min_train_trades": MIN_TRADES, "margin_pt": MARGIN},
           "secs": round(time.time() - t_start, 1)}
    with open(RESULTS_F, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    save_cache(force=True)
    print(f"\nFINAL stack {norm(stack)}", flush=True)
    for p in ("train", "test", "all"):
        print(f"  {p.upper():5s} {fmt(final[p])}   (base {fmt(base[p])})", flush=True)
    print(f"done in {time.time() - t_start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
