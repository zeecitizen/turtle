"""map_batch.py - for each batch-4 loss (and its two winning twins): which r_* rules skip it, plus the facts used in the comments.
Run from research/loss_study."""
import inspect
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import api  # noqa: E402
import rules  # noqa: E402

A = api.A
PIP = api.PIP
B = json.load(open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "batch_4.json"), encoding="utf-8"))
byid = {t["id"]: t for t in api.TRADES}
RULES = [(n, f) for n, f in inspect.getmembers(rules, inspect.isfunction) if n.startswith("r_")]


def facts(t):
    k, s = t["k"], t["side"]
    atr = A.atr[k]
    hs, ls = A.pivots(k, 1, 30)
    lev = t["level"]
    if s < 0:
        near = [round((lev - p) / PIP, 1) for b, p in ls if b < t["ku"] and (lev - p) / PIP >= -0.05]
    else:
        near = [round((p - lev) / PIP, 1) for b, p in hs if b < t["ku"] and (p - lev) / PIP >= -0.05]
    return {
        "utc": f"{(t['t_in'] % 86400) / 3600:05.2f}", "dow": int(((t["t_in"] // 86400) + 4) % 7),
        "spread_buy": round((t["fill"] - t["brk_hi_so_far"]) / PIP, 1) if s > 0 else None,
        "jump": round((t["fill"] - lev) * s / PIP, 1), "secs": round(t["t_in"] - float(A.t[t["kb"]]), 1),
        "brk/uhv": round(t["brk_ticks_so_far"] / t["uhv_v"], 2), "ext90_atr": round((A.c[k] - A.c[k - 90]) * s / atr, 1),
        "nearest_prior_swing_beyond_pips": min(near) if near else None, "atr_p": round(atr / PIP, 2),
        "med10": int(np.median(A.v[k - 9:k + 1])), "camStk": t["camStk"],
    }


def hits(t):
    tb = api._blind(t)
    return [n for n, f in RULES if f(tb, A)]


tw_count = {n: 0 for n, _ in RULES}
for i, L in enumerate(B["losses"]):
    t = byid[L["id"]]
    print(f"LOSS {L['id']}  {L['entry_pkt']} PKT  {facts(t)}")
    print(f"    rules: {hits(t)}")
    for w in B["twins"][2 * i:2 * i + 2]:
        tw = byid[w["id"]]
        h = hits(tw)
        for n in h:
            tw_count[n] += 1
        print(f"    twin {w['id']}  {facts(tw)}  rules: {h}")
print("\ntwins skipped per rule (of 44):", {n: c for n, c in tw_count.items() if c})
loss_count = {n: sum(1 for L in B["losses"] if n in hits(byid[L["id"]])) for n, _ in RULES}
print("batch losses skipped per rule (of 22):", {n: c for n, c in loss_count.items() if c})
