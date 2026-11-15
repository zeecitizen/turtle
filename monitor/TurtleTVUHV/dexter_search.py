"""dexter_search.py - Dexter's Lab strategy search (Zee 2026-10-26: "high win rate + lower worst loss ... USE turtle to find
the best strategy"). Starts from a saved setting, sweeps every stop / exit lever one at a time with the Turtle TV tester,
then climbs: applies the move that most improves net per dollar of worst loss (both halves still profitable, net kept at
>= half the start), and sweeps again. Every result is the tester's - a hypothesis until MT5 runs it.
py dexter_search.py ["saved name"] [rounds]   -> simdata/dexter_search.json (progress in simdata/dexter_search.log)"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "monitor" / "strategy_lab"))
import axi_rig  # noqa: E402
import optimizer  # noqa: E402
import sim  # noqa: E402

OUT = HERE / "simdata" / "dexter_search.json"
LOG = HERE / "simdata" / "dexter_search.log"
DS = "m15"

LEVERS = [                                                      # (label, {settings}) - each one is a move from the current setting
    *[(f"stop ${v}", {"InpSlMode": "2", "InpSlUsd": str(v)}) for v in (10, 15, 20, 25, 30, 35)],
    *[(f"ATR stop x{v}", {"InpSlMode": "1", "InpSlAtrMult": str(v)}) for v in (1.0, 1.5, 2.0, 2.5, 3.0)],
    *[(f"loss cap ${v}", {"InpXLossCap": str(v)}) for v in (8, 12, 16, 20, 25, 30)],
    *[(f"target ${v}", {"InpXTgt": "4", "InpXTgtK": str(v)}) for v in (5, 8, 12, 16, 20, 35)],
    *[(f"target {v}R", {"InpXTgt": "2", "InpXTgtK": str(v)}) for v in (0.5, 1.0, 1.5, 2.0, 3.0)],
    *[(f"partial at {v}R", {"InpXP1R": str(v)}) for v in (0, 0.5, 1.0, 1.5, 2.0)],
    ("partial then breakeven", {"InpXP1Be": "true"}),
    *[(f"breakeven at {v}R", {"InpXBeR": str(v)}) for v in (0.5, 1.0, 1.5)],
    *[(f"lock every {v}R", {"InpXLockR": str(v)}) for v in (0.5, 1.0)],
    *[(f"trail from {v}R", {"InpXTrAct": str(v)}) for v in (0.5, 1.0, 2.5)],
    *[(f"time stop {v} candles", {"InpXMaxBars": str(v)}) for v in (4, 8, 16, 32)],
    *[(f"no progress {v} candles", {"InpXStaleBars": str(v)}) for v in (4, 8, 16)],
    *[(f"stop decay {b} candles to {r}R", {"InpXDecayBars": str(b), "InpXDecayR": str(r)}) for b in (4, 8, 16) for r in (-0.5, 0)],
    *[(f"cut half at -{v}R", {"InpXLpR": str(v), "InpXLpFrac": "0.5"}) for v in (0.5, 0.75)],
    *[(f"fixed TP {v} pips", {"InpFixTpPips": str(v)}) for v in (20, 40, 80, 150)],
]


def log(msg):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + msg + "\n")


def stats(tr, window):
    a0, a1, b0, b1 = window
    rows = [x for x in tr if x[10] == 0]
    if not rows:
        return None
    t = np.array([x[1] for x in rows]); p = np.array([x[6] for x in rows]); to = np.array([x[4] for x in rows])
    eq = np.cumsum(p[np.argsort(to)]); dd = float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max())
    streak = cur = 0
    for v in p[np.argsort(to)]:
        cur = cur + 1 if v <= 0 else 0; streak = max(streak, cur)
    w = p > 0
    half = lambda m: round(float(p[m].sum()))                    # noqa: E731
    return {"n": int(len(p)), "net": round(float(p.sum())), "wr": round(100 * float(w.mean()), 1),
            "pf": round(float(p[w].sum() / -p[~w].sum()), 2) if (~w).any() and p[~w].sum() < 0 else None,
            "avg_win": round(float(p[w].mean())) if w.any() else 0, "avg_loss": round(float(p[~w].mean())) if (~w).any() else 0,
            "worst": round(float(p.min())), "dd": round(dd), "streak": int(streak),
            "train": half((t >= a0) & (t < a1)), "test": half((t >= b0) & (t < b1))}


def score(s, floor):
    """net per dollar of worst loss; out of the running when a half loses or net falls under the floor"""
    if not s or s["train"] <= 0 or s["test"] <= 0 or s["net"] < floor:
        return -1e18
    return s["net"] / max(abs(s["worst"]), 500.0)


def run(name, rounds=5):
    LOG.write_text("", encoding="utf-8")
    d = json.loads((HERE / "settings" / "saved" / f"{name}.json").read_text(encoding="utf-8"))
    cur = dict(axi_rig.ea_defaults("Saad_strategy_15min_view"), **d["inputs"])
    window = optimizer.Optimizer(cur, ds=DS).window
    ev = lambda inp: stats(sim.simulate(inp, ds=DS)[0], window)          # noqa: E731
    base = ev(cur)
    floor = 0.5 * base["net"]
    log(f"start {name}: {base}")
    out = {"start": name, "ds": DS, "window": window, "base": base, "rounds": [], "all": []}
    path, best_s, changed = [], score(base, floor), {}
    for rnd in range(1, rounds + 1):
        moves = [(lab, m) for lab, m in LEVERS if any(str(cur.get(k)) != v for k, v in m.items())]
        def one(mv):
            lab, m = mv
            s = ev(dict(cur, **m))
            return {"move": lab, "sets": m, "stats": s, "score": score(s, floor)}
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=5) as ex:
            res = list(ex.map(one, moves))
        res.sort(key=lambda r: r["score"], reverse=True)
        out["all"] += [{"round": rnd, "after": list(path), **r} for r in res]
        top = res[0]
        log(f"round {rnd}: {len(moves)} moves in {time.time() - t0:.0f}s; best {top['move']} -> {top['stats']}")
        out["rounds"].append({"round": rnd, "best": top, "current_score": best_s})
        OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
        if top["score"] <= best_s:
            log("no move improves the score: stop")
            break
        cur.update(top["sets"]); path.append(top["move"]); best_s = top["score"]; changed.update(top["sets"])
        out["final"] = {"path": list(path), "stats": top["stats"], "inputs_changed": dict(changed)}
        OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    log("done")
    return out


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "2026-10-26 01-48-34", int(sys.argv[2]) if len(sys.argv) > 2 else 5)
