"""freq_grow.py - give a high-WR saved setting MORE trades at (almost) the same win rate (Zee 2026-10-31: "i want to find out if we make it trade
more at the same or similar winrate ... ideally we'd like atleast one trade per day or at max once per two days").
Start: a saved setting (default "2026-10-30 23-08-23", 399 trades, 99.7%). Target, stop and exits stay as saved; only entry filters move.
Moves LOOSEN only (no tightening, so the search cannot hunt single losers): one threshold step toward off, an extra session hour, the
skipped weekday back, star / both EMA lines, one entry box / EA range box (kelt, va, vwap, asia, ib) / hour ticked back on; break bars and
break pips may move either way (they shift which entry fires). Score J = trading days - LAMBDA x losers (Zee asked for days, not a
second trade on a day that already trades). A move is taken only if J rises in BOTH halves (2023-24, 2025-26) on its own.
Greedy, best move first, LAMBDA lowered in phases (50, 30, 20, 12, 8 days per loser) -> a frontier of trading days vs win rate.
Overview tester (sim.simulate, m15 2023 -> now) = hypothesis; MT5 on an M15 chart promotes.

    py research/freq_grow.py ["2026-10-30 23-08-23"]
"""
import json, sys, time, numpy as np
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view")
import server, sim, rbox

SV = r"C:\Users\zeesh\turtle\monitor\saad_view\settings\saved"
NAME = sys.argv[1] if len(sys.argv) > 1 else "2026-10-30 23-08-23"
S0 = {k: str(v) for k, v in json.load(open(SV + "\\" + NAME + ".json"))["inputs"].items()}
MODE = __import__("os").environ.get("MODE", "loosen")    # "tighten": the same search from a frequent setting toward a higher win rate
OUT = rf"C:\Users\zeesh\turtle\monitor\saad_view\research\freq_grow_{NAME.replace(' ', '_')}{'' if MODE == 'loosen' else '_' + MODE}.json"
D = sim.data("m15")
DAYS = np.unique((D["t15"] // 86400)[(((D["t15"] // 86400) + 4) % 7 >= 1) & (((D["t15"] // 86400) + 4) % 7 <= 5)])
MID = 1735689600                                  # 2025-01-01: halves 2023-24 / 2025-26
PHASES = [50, 30, 20, 12, 8] if MODE == "loosen" else [8, 12, 20, 30, 50]   # trading days one more loser must buy (tighten: a removed loser is worth)
EA_BOX = ("kelt", "va", "vwap", "asia", "ib")    # the range-box families EA v1.38 has (TvBox_*); the other five are tester-only
LOOSE = {                                         # values from tight to loose; a move = one step looser (Zee wants MORE trades: loosen only)
    "InpEmaGapPips": [30, 27.5, 25, 22.5, 20, 17.5, 15, 12.5, 10, 7.5, 5, 2.5, 0],
    "InpChopEr": [0.12, 0.1, 0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 0],
    "InpAtrMinUsd": [3, 2.5, 2, 1.75, 1.5, 1.25, 1, 0.75, 0.5, 0],
    "InpAtrMaxUsd": [3, 4, 5, 6, 8, 10, 0],
    "InpMinRangeAtr": [1.1, 1.0, 0.9, 0.85, 0.8, 0.75, 0.7, 0.6, 0.5, 0],
    "InpMaxSpreadPts": [12, 15, 18, 20, 25, 30, 40, 0],
    "InpTouchPips": [1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 6],
    "InpBodyMax": [0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6],
    "InpWickMin": [0.5, 0.4, 0.35, 0.3, 0.25, 0.2],
    "InpNoseMax": [0, 0.05, 0.1, 0.15, 0.2],
    "InpMaruBody": [0.7, 0.65, 0.6, 0.55, 0.5, 0.45],
    "InpHamRatio": [3, 2.75, 2.5, 2.25, 2, 1.75, 1.5],
    "InpHamNose": [0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    "InpSessFrom": list(range(12, -1, -1)),
    "InpSessTo": list(range(12, 25)),
    "InpAdxMin": [25, 20, 15, 10, 0],
}
SHIFT = {"InpBreakBars": [3, 4, 5, 6, 7, 8], "InpBreakPips": [1, 2, 3, 4, 5, 6, 8]}    # neither looser nor tighter: they move which entry fires
CHOICE = {"InpSkipDow": "-1", "InpStar": "true", "InpLongRule": "2", "InpShortLine": "2", "InpBandOff": "0", "InpMaxPos": "2"}
BITS = {"InpBandsB": 21, "InpBandsS": 21, "InpHours": 24, **{f"TvBox_{k}_{s}": len(lab) for k, _, _, lab in rbox.FAM if k in EA_BOX for s in "BS"}}
CACHE = {}


def run(cur):
    key = tuple(sorted(cur.items()))
    if key not in CACHE:
        tr, _, _ = sim.simulate(server.full_inputs(cur), ds="m15")
        CACHE[key] = np.array([x for x in tr if x[10] == 0])
    return CACHE[key]


def met(t):
    p = t[:, 6]; h1 = t[:, 1] < MID
    eq = np.cumsum(p); w = p[p > 0]; l = p[p <= 0]
    dd = float((np.maximum.accumulate(eq) - eq).max()) if len(p) else 0.0
    td = np.unique(t[:, 1] // 86400); g = np.diff(np.searchsorted(DAYS, td))
    return dict(n=len(p), L=int((p <= 0).sum()), n1=int(h1.sum()), L1=int((p[h1] <= 0).sum()), n2=int((~h1).sum()), L2=int((p[~h1] <= 0).sum()),
                wr=round(100 * (p > 0).mean(), 2), wr1=round(100 * (p[h1] > 0).mean(), 2), wr2=round(100 * (p[~h1] > 0).mean(), 2),
                net=round(float(p.sum())), dd=round(dd), pf=round(float(w.sum() / max(1.0, -l.sum())), 3), worst=round(float(p.min())),
                avg_loss=round(float(l.mean())) if len(l) else 0, full_stops=int((p < -4000).sum()),
                days=len(td), days1=int((td < MID // 86400).sum()), days2=int((td >= MID // 86400).sum()),
                gap_med=float(np.median(g)), gap_p90=float(np.percentile(g, 90)), gap_max=int(g.max()))


def moves(cur):
    if MODE == "tighten":
        return moves_tight(cur)
    out = []
    for k, g in LOOSE.items():
        v = float(cur.get(k, "0")); i = int(np.argmin([abs(v - x) for x in g]))
        if i + 1 < len(g):
            out.append((f"{k} {cur.get(k)}->{g[i + 1]}", {k: str(g[i + 1])}))
    for k, g in SHIFT.items():
        v = float(cur.get(k, "0")); i = int(np.argmin([abs(v - x) for x in g]))
        for j in (i - 1, i + 1):
            if 0 <= j < len(g):
                out.append((f"{k} {cur.get(k)}->{g[j]}", {k: str(g[j])}))
    for k, c in CHOICE.items():
        if cur.get(k) != c:
            out.append((f"{k} {cur.get(k)}->{c}", {k: c}))
    for k, n in BITS.items():
        s = (cur.get(k) or "1" * n).ljust(n, "1")[:n]
        for b in range(n):
            if s[b] == "0":
                out.append((f"{k} box {b} on", {k: s[:b] + "1" + s[b + 1:]}))
    return out


TIGHT_CHOICE = {"InpSkipDow": ["1", "2", "3", "4", "5"], "InpStar": ["false"], "InpLongRule": ["0", "1"], "InpShortLine": ["0", "1"],
                "InpBandOff": ["1"], "InpMaxPos": ["1"]}


def moves_tight(cur):
    """one step tighter anywhere (a threshold toward strict, a weekday skipped, one box / hour unticked); break bars / pips either way"""
    out = []
    for k, g in LOOSE.items():
        v = float(cur.get(k, "0")); i = int(np.argmin([abs(v - x) for x in g]))
        if i > 0:
            out.append((f"{k} {cur.get(k)}->{g[i - 1]}", {k: str(g[i - 1])}))
    for k, g in SHIFT.items():
        v = float(cur.get(k, "0")); i = int(np.argmin([abs(v - x) for x in g]))
        for j in (i - 1, i + 1):
            if 0 <= j < len(g):
                out.append((f"{k} {cur.get(k)}->{g[j]}", {k: str(g[j])}))
    for k, ch in TIGHT_CHOICE.items():
        for c in ch:
            if cur.get(k) != c and not (k == "InpSkipDow" and cur.get(k, "-1") != "-1"):
                out.append((f"{k} {cur.get(k)}->{c}", {k: c}))
    for k, n in BITS.items():
        s = (cur.get(k) or "1" * n).ljust(n, "1")[:n]
        for b in range(n):
            if s[b] == "1" and s.count("1") > 1:
                out.append((f"{k} box {b} off", {k: s[:b] + "0" + s[b + 1:]}))
    return out


def J(m, lam, h=""):
    return m["days" + h] - lam * m["L" + h]


if __name__ == "__main__":
    cur = dict(S0)
    m0 = met(run(cur)); cm = m0
    print("START", NAME, m0, flush=True)
    steps, keep = [], []
    t0 = time.time()
    with ThreadPoolExecutor(int(__import__('os').environ.get('THREADS', '6'))) as ex:
        for lam in PHASES:
            for it in range(40):
                mv = [(lab, {**cur, **ch}) for lab, ch in moves(cur)]
                res = list(ex.map(lambda x: met(run(x[1])), mv))
                ok = []
                for (lab, s), m in zip(mv, res):
                    d, d1, d2 = J(m, lam) - J(cm, lam), J(m, lam, "1") - J(cm, lam, "1"), J(m, lam, "2") - J(cm, lam, "2")
                    if d > 0 and d1 > 0 and d2 > 0:                  # must help in BOTH halves on its own
                        ok.append((d, m["n"], m["net"], lab, s, m))
                if not ok:
                    break
                ok.sort(key=lambda z: (-z[0], -z[1], -z[2]))
                d, _, _, lab, cur, cm = ok[0]
                steps.append({"lambda": lam, "move": lab, "dJ": round(d, 1), **cm})
                print(f"[{time.time() - t0:6.0f}s] L{lam:<5} {lab:42s} n {cm['n']:4d} L {cm['L']:3d} wr {cm['wr']:6.2f} ({cm['wr1']:.2f}/{cm['wr2']:.2f}) "
                      f"days {cm['days']:4d} gap {cm['gap_med']:.0f}/{cm['gap_p90']:.0f}/{cm['gap_max']} net {cm['net']:8,d} dd {cm['dd']:6,d}", flush=True)
                json.dump({"start": NAME, "m0": m0, "steps": steps, "keep": keep, "cur": cur}, open(OUT, "w"), indent=1)
            keep.append({"lambda": lam, "metrics": cm, "inputs": dict(cur)})
            print(f"=== phase LAMBDA {lam} done: {cm}", flush=True)
            json.dump({"start": NAME, "m0": m0, "steps": steps, "keep": keep, "cur": cur}, open(OUT, "w"), indent=1)
