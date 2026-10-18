"""saad15_selftune.py - a self-tuner for Saad_strategy_15min v1.23: beam search over a tree of settings, pruned across time folds,
final choice by an ensemble vote, proven on months it never saw.

Zee 2026-10-18 (Task 7): "Build a self-tuner for the 15 min ea called saad_strategy_15min version 1.23 (a self-tuner that works to
optimize the best set of settings by doing pruning on a branched tree ensemble, kind of like AI pruning!)"

    py saad15_selftune.py              # the whole tree (~1 h on 6 rigs), writes saad15_selftune_out.json / .md
    py saad15_selftune.py --holdout-only best.json

HOW IT WORKS
  The tree: the settings are grouped into LEVELS (EMAs -> setup candle -> stop -> exits -> filters). Each node is a complete
  setting set; a node branches into every combination of the next level's candidate values.
  Pruning (successive halving across TIME FOLDS): all branches of a level are tested on fold 1 (Jan-Feb); the worse half is cut;
  the survivors run fold 2 (Mar-Apr); the worse half is cut again; and so on through fold 4 (Jul-Aug). A branch survives only by
  being good in month after month - a lucky streak in one fold cannot carry it. The best BEAM survivors seed the next level.
  Score of a fold = net / max drawdown (profit per dollar of pain); a fold with fewer than MIN_TRADES trades scores 0.
  The ensemble: the best survivors of the whole tree vote on every setting (weighted by their score); the consensus set and the
  single best set are then run on the HOLD-OUT (Sep 1 - Oct 17), months no branch was ever judged on, with random delay.
Every number is a real MT5 Strategy Tester run on Blueberry's real ticks (XAUUSD_BB). Nothing here is a Python simulation.
"""
import itertools
import json
import queue
import random
import sys
import threading
import time
from pathlib import Path

import axi_rig

EA = "Saad_strategy_15min"
SYMBOL, PERIOD = "XAUUSD_BB", "M15"
RIGS = ["axi2", "axi3", "axi4", "axi5", "axi6", "axi7"]
FOLDS = [("2026.01.01", "2026.03.01"), ("2026.03.01", "2026.05.01"), ("2026.05.01", "2026.07.01"), ("2026.07.01", "2026.09.01")]
HOLDOUT = ("2026.09.01", "2026.10.17")
BEAM = 4
MIN_TRADES = 15
OUT = Path(__file__).with_name("saad15_selftune_out.json")
MD = Path(__file__).with_name("saad15_selftune_out.md")

# the tree: each level = the settings it branches on and their candidate values (v1.23 defaults are always among them)
LEVELS = [
    ("EMAs", {"InpEmaFast": ["5", "7", "9", "12", "14"], "InpEmaSlow": ["30", "40", "50", "60", "70"]}),
    ("setup candle", {"InpWickMin": ["0.35", "0.45", "0.55"], "InpBodyMax": ["0.45", "0.60"], "InpMinRangeAtr": ["0.35", "0.55", "0.75"]}),
    ("stop", {"InpSlPips": ["25", "35", "45"], "InpMaxRiskUsd": ["10", "15", "20"]}),
    ("exits", {"InpPartialPct": ["0.5", "0.75", "0.95"], "InpBeTpPct": ["0.6", "0.75", "0.9"], "InpLongTrailUsd": ["1", "2", "3"]}),
    ("filters", {"InpChopEr": ["0", "0.06", "0.11", "0.16"], "InpBreakPips": ["1", "2", "4"]}),
]
BASE = {"InpLots": "1"}

_lock = threading.Lock()
_cache = {}


def _key(sets, fold):
    return json.dumps([sorted(sets.items()), fold])


def run_one(rig, sets, fold, delay=0):
    for attempt in range(4):
        r = axi_rig.run(EA, SYMBOL, PERIOD, sets, frm=fold[0], to=fold[1], deposit=100000, rig=rig, tag="selftune", exec_mode=delay)
        if r.get("error") not in ("authorization failed", "no report"):
            break
        axi_rig.kill_rig(rig)
        time.sleep(3 + random.random() * 5)
    ts = r.get("trade_stats") or {}
    n, aw, al, net = ts.get("n") or 0, ts.get("avg_win") or 0, ts.get("avg_loss") or 0, r.get("net") or 0
    dd = float(str(r.get("dd") or "0").split("(")[0].replace(" ", "") or 0)
    wr = 100 * ((net + n * -al) / (aw - al)) / n if n and aw - al else 0
    score = 0.0 if n < MIN_TRADES else net / max(dd, 500.0)
    return {"net": net, "dd": dd, "n": n, "wr": wr, "pf": r.get("pf"), "score": score, "err": r.get("error")}


def evaluate(jobs, delay=0):
    """jobs: list of (id, sets, fold) -> {id: result}; 6 rigs in parallel, results cached."""
    out, q = {}, queue.Queue()
    for j in jobs:
        k = _key(j[1], j[2]) + str(delay)
        if k in _cache:
            out[j[0]] = _cache[k]
        else:
            q.put(j)

    def worker(rig):
        while True:
            try:
                jid, sets, fold = q.get_nowait()
            except queue.Empty:
                return
            res = run_one(rig, sets, fold, delay)
            with _lock:
                _cache[_key(sets, fold) + str(delay)] = res
                out[jid] = res
    ts = []
    for rig in RIGS:
        t = threading.Thread(target=worker, args=(rig,))
        t.start()
        ts.append(t)
        time.sleep(4)
    [t.join() for t in ts]
    return out


def successive_halving(cands, log):
    """cands: {cid: sets}. Run fold by fold, cut the worse half after each. -> sorted [(mean score, cid, per-fold results)]"""
    alive = list(cands)
    hist = {c: [] for c in cands}
    for fi, fold in enumerate(FOLDS):
        res = evaluate([(c, cands[c], fold) for c in alive])
        for c in alive:
            hist[c].append(res[c])
        mean = lambda c: sum(x["score"] for x in hist[c]) / len(hist[c])
        alive.sort(key=mean, reverse=True)
        keep = max(BEAM, (len(alive) + 1) // 2) if fi < len(FOLDS) - 1 else len(alive)
        log(f"    fold {fi + 1} {fold[0]}-{fold[1]}: {len(alive)} branches tested, best mean score {mean(alive[0]):.2f}, keeping {keep}")
        alive = alive[:keep]
    return sorted(((sum(x["score"] for x in hist[c]) / len(FOLDS), c, hist[c]) for c in alive), reverse=True)


def main(log=print):
    for rig in RIGS:
        axi_rig.compile_ea(EA, rig=rig)
    defaults = axi_rig.ea_defaults(EA)
    beam = [dict(BASE)]
    tree, survivors = [], []
    for lname, params in LEVELS:
        cands = {}
        for node in beam:
            for combo in itertools.product(*params.values()):
                sets = dict(node, **dict(zip(params, combo)))
                cid = json.dumps(sorted(sets.items()))
                cands[cid] = sets
        log(f"  level '{lname}': {len(beam)} parent(s) x {len(list(itertools.product(*params.values())))} branches = {len(cands)} candidates")
        ranked = successive_halving(cands, log)
        tree.append({"level": lname, "candidates": len(cands),
                     "top": [{"score": s, "sets": cands[c], "folds": h} for s, c, h in ranked[:BEAM * 2]]})
        survivors += [(s, cands[c]) for s, c, h in ranked[:BEAM]]
        beam = [cands[c] for s, c, h in ranked[:BEAM]]
        json.dump({"tree": tree}, open(OUT, "w"), indent=1)
    # the ensemble: the best survivors vote on every tuned setting, weighted by their score
    survivors.sort(key=lambda x: -x[0])
    voters = [v for v in survivors if v[0] > 0][:8] or survivors[:8]
    tuned = sorted({k for _, p in LEVELS for k in p})
    consensus = dict(BASE)
    for k in tuned:
        w = {}
        for s, sets in voters:
            v = sets.get(k, defaults.get(k))
            w[v] = w.get(v, 0) + max(s, 0.01)
        consensus[k] = max(w, key=w.get)
    best = voters[0][1]
    log("  hold-out (never judged on), random delay:")
    finals = {"v1.23 defaults": dict(BASE), "best single branch": best, "ensemble consensus": consensus}
    ho = evaluate([(n, s, HOLDOUT) for n, s in finals.items()], delay=-1)
    yr = evaluate([(n, s, ("2026.01.01", "2026.10.17")) for n, s in finals.items()], delay=-1)
    for n in finals:
        log(f"    {n:20} hold-out Sep-Oct: net {ho[n]['net']:+,.0f} WR {ho[n]['wr']:.1f}% PF {ho[n]['pf']} DD {ho[n]['dd']:,.0f} | full year: net {yr[n]['net']:+,.0f} WR {yr[n]['wr']:.1f}% PF {yr[n]['pf']}")
    result = {"tree": tree, "voters": voters, "consensus": consensus, "best": best, "holdout": ho, "year": yr,
              "changed_vs_defaults": {k: (defaults.get(k), consensus[k]) for k in consensus if str(defaults.get(k)) != str(consensus[k])}}
    json.dump(result, open(OUT, "w"), indent=1)
    lines = ["# Saad_strategy_15min v1.23 - self-tuner result (tree search, pruned across time folds, ensemble vote)", "",
             f"Blueberry XAUUSD_BB M15, MT5 Strategy Tester real ticks. Folds (pruning): {', '.join(a + '-' + b for a, b in FOLDS)}. "
             f"Hold-out (never used to choose): {HOLDOUT[0]} - {HOLDOUT[1]}. Beam {BEAM}, min {MIN_TRADES} trades a fold, score = net / max drawdown.", "",
             "| Setting set | Hold-out net | Hold-out WR | PF | Full-year net | Full-year WR | PF |", "|---|---|---|---|---|---|---|"]
    for n in finals:
        lines.append(f"| {n} | {ho[n]['net']:+,.0f} | {ho[n]['wr']:.1f}% | {ho[n]['pf']} | {yr[n]['net']:+,.0f} | {yr[n]['wr']:.1f}% | {yr[n]['pf']} |")
    lines += ["", "## Ensemble consensus vs v1.23 defaults", "", "| Setting | v1.23 | consensus |", "|---|---|---|"]
    for k, (a, b) in result["changed_vs_defaults"].items():
        lines.append(f"| {k} | {a} | **{b}** |")
    lines += ["", "## The tree, level by level (best surviving branches)", ""]
    for lv in tree:
        lines.append(f"### {lv['level']} - {lv['candidates']} branches")
        for t in lv["top"][:4]:
            lines.append(f"- score {t['score']:.2f}: " + ", ".join(f"{k}={v}" for k, v in t["sets"].items() if k != "InpLots") +
                         " | folds net: " + " / ".join(f"{f['net']:+,.0f}" for f in t["folds"]))
        lines.append("")
    MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"  written {OUT.name} and {MD.name}")
    return result


if __name__ == "__main__":
    main()
