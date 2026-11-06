"""HOLDOUT version of wr_combine.py: every pick judged on 2023-24 only; 2025-26 is never looked at while choosing.
Raise the win rate of 2026-10-25 05-58-25 with EA filters only (target/stop/exits fixed), m15 2023->now, Overview engine.
Greedy: add the change that lifts WR most while net >= KEEP x base, both halves profitable, trades >= 60% of base. Saves the best steps."""
import json, sys, time, numpy as np
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view")
import server, sim
SV = r"C:\Users\zeesh\turtle\monitor\saad_view\settings\saved"
S = json.load(open(SV + r"\2026-10-25 05-58-25.json"))
BASE = dict(S["inputs"])
KEEP = float(sys.argv[1]) if len(sys.argv) > 1 else 0.8


def run(sets):
    inp = server.full_inputs({**BASE, **sets})
    tr, _, _ = sim.simulate(inp, ds="m15")
    t = np.array([x for x in tr if x[10] == 0]); p = t[:, 6]; te = t[:, 1]
    eq = np.cumsum(p); dd = (np.maximum.accumulate(eq) - eq).max(); w = p[p > 0]; l = p[p <= 0]
    m = 1735689600   # 2025-01-01: halves 2023-24 / 2025-26
    a_, b_ = p[te < m], p[te >= m]
    return dict(wr1=round(100 * (a_ > 0).mean(), 2), wr2=round(100 * (b_ > 0).mean(), 2), n1=len(a_), n=len(p), wr=round(100 * len(w) / len(p), 2), net=round(p.sum()), worst=round(p.min()), dd=round(dd),
                pf=round(w.sum() / max(1, -l.sum()), 3), avg_loss=round(l.mean()) if len(l) else 0, h1=round(p[te < m].sum()), h2=round(p[te >= m].sum()))


CANDS = []
for v in (2, 2.5, 3, 4): CANDS.append({"InpAtrMinUsd": v})
for v in (4, 5, 6, 7, 8, 9, 10): CANDS.append({"InpSessFrom": v})
for v in (17, 18, 19, 20): CANDS.append({"InpSessTo": v})
for v in (-1, 1, 3, 4, 5): CANDS.append({"InpSkipDow": v})
for v in (0.08, 0.11, 0.15): CANDS.append({"InpChopEr": v})
for v in (15, 20, 25): CANDS.append({"InpAdxMin": v})
for m in (60, 240):
    for e in (20, 50): CANDS.append({"InpHtfMin": m, "InpHtfEma": e})
CANDS += [{"InpTrendAlign": "true"}, {"InpPriceSide": "true"}]
for v in (1, 3, 5):
    for k in (5, 12): CANDS.append({"InpSlopePips": v, "InpSlopeLook": k})
for v in (12, 15): CANDS.append({"InpMaxSpreadPts": v})
for v in (10, 15, 20): CANDS.append({"InpEmaGapPips": v})
for v in (1.0, 1.2): CANDS.append({"InpMinRangeAtr": v})
for v in (6, 8): CANDS.append({"InpBreakPips": v})
for v in (2, 4, 8): CANDS.append({"InpCoolBars": v})
CANDS.append({"InpDayLossPct": 1})
for side in ("InpBandsB", "InpBandsS"):        # untick one more entry box
    for i in range(21):
        CANDS.append({side: ("BAND", i)})


for h in range(24):                              # v1.37 InpHours: untick one entry hour
    CANDS.append({"InpHours": ("BAND", h)})
import rbox                                       # Turtle TV range-box families: untick one box
for k, _, _, lab in rbox.FAM:
    for sd in "BS":
        for b in range(len(lab)):
            CANDS.append({f"TvBox_{k}_{sd}": ("BAND", b, len(lab))})


def apply(cur, c):
    out = dict(cur)
    for k, v in c.items():
        if isinstance(v, tuple):
            n = v[2] if len(v) > 2 else (24 if k == "InpHours" else 21)
            s = list(str(out.get(k, BASE.get(k, "")) or "").ljust(n, "1")[:n])
            if s[v[1]] == "0": return None
            s[v[1]] = "0"; out[k] = "".join(s)
        else:
            out[k] = str(v)
    return out


base = run({}); print("BASE", base, flush=True)
cur, cur_s, steps = {}, base, []
for rnd in range(8):
    trials = [(c, apply(cur, c)) for c in CANDS]; trials = [(c, s) for c, s in trials if s is not None and s != cur]
    with ThreadPoolExecutor(6) as ex: res = list(ex.map(lambda cs: run(cs[1]), trials))
    ok = [(r, c, s) for (c, s), r in zip(trials, res)
          if r["h1"] >= KEEP * base["h1"] and r["n1"] >= 0.6 * base["n1"] and r["wr1"] > cur_s["wr1"] + 0.05]     # chosen on 2023-24 ONLY
    if not ok: print("no further improvement", flush=True); break
    ok.sort(key=lambda z: (-z[0]["wr1"], -z[0]["h1"]))
    r, c, s = ok[0]; cur, cur_s = s, r
    steps.append({"add": {k: (f"untick box {v[1]}" if isinstance(v, tuple) else v) for k, v in c.items()}, "sets": dict(s), "stats": r})
    print(f"step {rnd + 1}: {steps[-1]['add']} -> {r}", flush=True)
json.dump({"base": base, "keep": KEEP, "steps": steps}, open(rf"C:\Users\zeesh\turtle\monitor\saad_view\research\wr_holdout_{KEEP}.json", "w"), indent=1)
