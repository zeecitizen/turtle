"""lifecycle.py - Trade Lifecycle tree (Zee 2026-10-27: "shows as a tree multiple paths the trade can take under the current
settings ... buttons to prune/cut a part of the tree (essentially disabling that exit) ... tell what each branch does to the trade").
Before the entry: setups found and what the filters rejected. After it: one branch per way a trade ended (the tester's exit
reason), each split into winners and losers. Pruning a branch re-runs the tester with that exit switched off (sim.simulate(prune=)),
and every live branch carries a forecast: what cutting it does to the money, and where its trades would end instead.
Tester hypotheses only - a pruned exit has no EA input unless EA_CUT names one; MT5 decides."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import dexlab
import exitlab
import sim

WHY = exitlab.WHY
KIND = {1: "loss", 2: "target", 3: "cut", 4: "cut", 5: "target", 6: "protect", 7: "protect", 8: "cut", 9: "target", 11: "target",
        12: "cut", 13: "cut", 14: "cut", 15: "cut", 16: "cut", 17: "cut"}
SKIP_LABEL = {"no_break": "no breakout of the range", "risk": "stop too wide (max risk)", "adx": "ADX filter", "atr_band": "ATR band filter",
              "band_skip": "band skip", "gap": "gap cancel", "spread_reject": "spread too wide"}
# the EA input that switches this exit off for real (so a cut can become a setting); None = test only, no EA switch yet
EA_CUT = {9: {"InpXTgt": "1"}, 8: {"InpXMaxBars": "0"}, 13: {"InpXStaleBars": "0"}, 14: {"InpXAdxExit": "0"}, 15: {"InpXFriHour": "0"},
          16: {"InpXDecayBars": "0"}, 17: {"InpXLpR": "0"}, 12: {"InpXCx": "0"}, 11: {"InpXP1R": "0", "InpXP2R": "0"}}
_CACHE = {}
_LOCK = threading.Lock()


def _f(inputs, k, d=0.0):
    try:
        return float(inputs.get(k, d))
    except (TypeError, ValueError):
        return d


def explain(r, inputs):
    """what this exit is, in the words of the current settings"""
    tg = {2: "R multiple", 3: "x ATR", 4: "$"}.get(int(_f(inputs, "InpXTgt")), "")
    cx = ["", "close across the fast EMA", "close across the slow EMA", "EMA cross", "opposite signal", "engulfing candle",
          "N candles against"][min(6, int(_f(inputs, "InpXCx")))]
    sl = ["pips beyond the setup candle", "ATR multiple", "$ from the entry"][min(2, int(_f(inputs, "InpSlMode")))]
    return {
        1: f"The initial stop-loss was hit ({sl}). The full planned loss: the trade was wrong and nothing closed it earlier.",
        2: "Price reached the next EMA beyond the entry (exit mode 1's target).",
        3: f"A completed candle closed back across the {int(_f(inputs, 'InpEmaSlow', 32))} EMA: the move failed, the trade closes at the "
           "market. Usually small or medium losses - it fires BEFORE the stop would.",
        4: "The day-close loss cut closed it at the end of the day.",
        5: "The take-profit level was reached.",
        6: "A trailing / locked stop above the entry was hit: profit given back is capped.",
        7: "The stop had moved to the entry (breakeven) and was hit: a scratch trade.",
        8: f"Held the maximum time ({int(_f(inputs, 'InpXMaxBars'))} candles) and closed at the market.",
        9: f"The Exit Lab target was reached: {_f(inputs, 'InpXTgtK'):g} {tg} from the entry. Always a winner - it only fires in profit.",
        11: "A partial close at a profit level (only part of the position).",
        12: f"The close-based exit fired ({cx}).",
        13: f"No progress after {int(_f(inputs, 'InpXStaleBars'))} candles: closed as a dead trade.",
        14: "ADX faded below the exit level: the trend died.",
        15: "Friday close: out before the weekend.",
        16: "The decay stop: after N candles the stop was pulled towards the entry and was hit.",
        17: "The loss cut: part of the trade closed while in loss.",
    }.get(r, WHY.get(r, f"exit {r}"))


def _real(tr):
    return [x for x in tr if x[10] == 0]


def _run(inputs, ds, chart, prune):
    k = json.dumps([inputs, ds, chart, sorted(prune)], sort_keys=True)
    with _LOCK:
        if k in _CACHE:
            return _CACHE[k]
    tr, _setups, st = sim.simulate(inputs, ds=ds, chart=chart, prune=tuple(sorted(prune)))
    out = (_real(tr), st)
    with _LOCK:
        if len(_CACHE) > 300:
            _CACHE.clear()
        _CACHE[k] = out
    return out


def _branch(rows):
    p = np.array([x[6] for x in rows]); w = p > 0
    mins = np.array([(x[4] - x[1]) / 60.0 for x in rows])
    return {"n": int(len(p)), "net": round(float(p.sum())), "wr": round(100 * float(w.mean()), 1) if len(p) else 0,
            "avg": round(float(p.mean())) if len(p) else 0, "avg_win": round(float(p[w].mean())) if w.any() else 0,
            "avg_loss": round(float(p[~w].mean())) if (~w).any() else 0, "worst": round(float(p.min())) if len(p) else 0,
            "best": round(float(p.max())) if len(p) else 0, "mins": round(float(np.median(mins)), 1) if len(p) else 0,
            "mfe": round(float(np.mean([x[15] for x in rows])), 2) if rows else 0, "mae": round(float(np.mean([x[16] for x in rows])), 2) if rows else 0,
            "wins": {"n": int(w.sum()), "net": round(float(p[w].sum()))}, "losses": {"n": int((~w).sum()), "net": round(float(p[~w].sum()))},
            # the branch's trades for its sub-branches on the page: side, minutes held, pnl, best / worst move ($ of price), entry hour (UTC)
            "trades": [[int(x[0]), round((x[4] - x[1]) / 60.0, 1), round(float(x[6])), round(float(x[15]), 2), round(float(x[16]), 2),
                        int((x[1] // 3600) % 24)] for x in rows]}


def _fate(rows, other):
    """where the trades of a branch end when that exit is cut: matched on side + entry time in the other run"""
    idx = {(int(x[0]), int(x[1])): x for x in other}
    went, gone = {}, {"n": 0, "net": 0.0}
    for x in rows:
        y = idx.get((int(x[0]), int(x[1])))
        if y is None:
            gone["n"] += 1; gone["net"] += float(x[6])
            continue
        g = went.setdefault(int(y[13]), {"n": 0, "net": 0.0, "was": 0.0})
        g["n"] += 1; g["net"] += float(y[6]); g["was"] += float(x[6])
    fate = [{"r": r, "why": WHY.get(r, str(r)), "n": v["n"], "net": round(v["net"]), "was": round(v["was"])}
            for r, v in sorted(went.items(), key=lambda z: -z[1]["n"])]
    return fate, {"n": gone["n"], "net": round(gone["net"])}


def tree(inputs, ds="year1", mode="ea", pruned=()):
    chart = mode == "chart"
    pruned = sorted({int(r) for r in pruned})
    window = exitlab.window_of(ds, inputs)[0]
    rows, st = _run(inputs, ds, chart, pruned)
    base_rows, _ = _run(inputs, ds, chart, []) if pruned else (rows, st)
    stats, base = dexlab.stats(rows, window), dexlab.stats(base_rows, window)
    for s in (stats, base):
        if s:
            s.pop("eq", None)
    by = {}
    for x in rows:
        by.setdefault(int(x[13]), []).append(x)
    live = sorted(by, key=lambda r: -len(by[r]))
    with ThreadPoolExecutor(max_workers=5) as pool:
        alt = dict(zip(live, pool.map(lambda r: _run(inputs, ds, chart, pruned + [r]), live)))
    branches = []
    for r in live:
        b = _branch(by[r])
        a_rows = alt[r][0]
        a = dexlab.stats(a_rows, window) if a_rows else None
        fate, gone = _fate(by[r], a_rows)
        imp = None
        if a and stats:
            a.pop("eq", None)
            imp = {"net": a["net"] - stats["net"], "wr": round(a["wr"] - stats["wr"], 1), "worst": a["worst"] - stats["worst"],
                   "dd": a["dd"] - stats["dd"], "n": a["n"] - stats["n"], "after": a}
        branches.append({"r": r, "why": WHY.get(r, str(r)), "kind": KIND.get(r, "cut"), "text": explain(r, inputs), **b,
                         "share": round(100.0 * b["n"] / max(1, len(rows)), 1), "impact": imp, "fate": fate, "gone": gone,
                         "ea_cut": EA_CUT.get(r), "verdict": _verdict(r, b, imp, fate)})
    cut = [{"r": r, "why": WHY.get(r, str(r)), "text": explain(r, inputs), "ea_cut": EA_CUT.get(r)} for r in pruned]
    skips = [{"k": k, "label": SKIP_LABEL[k], "n": int(st.get(k, 0))} for k in SKIP_LABEL if st.get(k, 0)]
    return {"ds": ds, "pruned": pruned, "cut": cut, "stats": stats, "base": base, "branches": branches,
            "setups": int(st.get("setups", 0)), "skips": skips, "entries": len(rows), "open_at_end": int(st.get("open_at_end", 0))}


def _verdict(r, b, imp, fate):
    """one line of judgement for the branch: cut or keep, and why, from the forecast"""
    if not imp:
        return "No forecast: cutting it leaves no trades."
    d = imp["net"]
    if r == 1:
        return (f"NEVER CUT IN REAL TRADING: with no stop a trade can lose without limit. The forecast ({d:+,}) only shows how these "
                "few trades happened to end on this data - one bad gap wipes that out.")
    moved = sorted(fate, key=lambda f: f["net"] - f["was"])
    worst_dest = moved[0] if moved else None
    if d > 0:
        return (f"CUT CANDIDATE: cutting it adds {d:+,} - its trades do better under the other exits"
                + (f" (mostly ending as '{fate[0]['why']}')" if fate else "") + ". Check the worst loss and MT5 before trusting it.")
    if b["avg"] < 0 and worst_dest:
        return (f"KEEP - LOSS LIMITER: its trades lose on average, but cut it and they lose MORE ({d:+,}). "
                f"{worst_dest['n']} of them would end as '{worst_dest['why']}' instead.")
    if b["avg"] > 0:
        return f"KEEP - PROFIT TAKER: it banks the winners; cutting it costs {d:+,} as those trades give profit back."
    return f"KEEP: cutting it costs {d:+,}."
