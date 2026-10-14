"""Daily ONE-SHOT policy search v2: triggers + per-trigger filters + PKT window (hypothesis stage).
Census shots = real MT5 positions (0.11 lots, TP $1, SL $6). A policy takes, per weekday, the FIRST shot that passes
its trigger's filter inside the window. Ranked on both halves; the winner goes to a real MT5 one-shot run."""
import itertools
import numpy as np, pandas as pd
from pathlib import Path

T = Path(r"C:\Users\zeesh\turtle\testing")
HOL = {"2026-04-03"}


def weekdays(a, b):
    d, out = pd.Timestamp(a), []
    while d < pd.Timestamp(b):
        if d.weekday() < 5 and str(d.date()) not in HOL: out.append(d.date())
        d += pd.Timedelta(days=1)
    return out


def load(name, remap=None):
    d = pd.read_csv(T / f"bread_shots_{name}_full.csv")
    d["t"] = pd.to_datetime(d.pkt_time, format="%Y.%m.%d %H:%M")
    d["hr"] = d.t.dt.hour + d.t.dt.minute / 60
    d["day"] = d.t.dt.date
    if remap: d["trig"] = d.trig.map(remap).fillna(d.trig)
    return d


A = pd.concat([load("census_dsv"), load("census_vA_big60", {3: 7})], ignore_index=True).sort_values("t")
A["win"] = A.net > 0
# per-trigger filter menu (thresholds = round numbers near the census quartiles)
FILT = {
    1: {"none": lambda g: g, "with4h": lambda g: g[g.er_net >= 11.5], "er38": lambda g: g[g.er >= 0.38], "ny": lambda g: g[g.hr >= 17]},
    2: {"none": lambda g: g, "ny": lambda g: g[g.hr >= 17.25], "novs": lambda g: g[g.vs_age > 587]},
    3: {"none": lambda g: g, "fade": lambda g: g[(g.er_net <= -2) & (g.er_net >= -40)], "fade12": lambda g: g[(g.er_net <= -12) & (g.er_net >= -25)]},
    7: {"none": lambda g: g, "fade": lambda g: g[(g.er_net <= -2) & (g.er_net >= -40)]},
}
NAMES = {1: "DIA", 2: "SAAD", 3: "VS", 7: "VSlo"}
HALF = {"Jan": weekdays("2026-01-06", "2026-07-01"), "Jul": weekdays("2026-07-01", "2026-10-08")}


def score(sub):
    out = {}
    for k, days in HALF.items():
        first = sub[sub.day.isin(days)].groupby("day").head(1).set_index("day").net
        v = [first.get(d) for d in days]
        shots = [x for x in v if x is not None]
        out[k] = (len(shots), sum(x >= 10 for x in shots), sum(x < 0 for x in shots), round(sum(shots), 1))
    return out


rows = []
for trigs in [(1,), (3,), (7,), (1, 3), (1, 7), (2, 3), (2, 7), (1, 2, 3), (1, 2, 7), (1, 3, 7), (1, 2, 3, 7)]:
    menus = [list(FILT[t].items()) for t in trigs]
    for combo in itertools.product(*menus):
        parts = [f(A[A.trig == t]) for t, (_, f) in zip(trigs, combo)]
        base = pd.concat(parts).sort_values("t")
        for h0, h1 in [(0, 24), (6, 24), (9, 24), (12, 24), (14, 24), (16, 24), (17, 24)]:
            sub = base[(base.hr >= h0) & (base.hr < h1)]
            s = score(sub)
            rows.append({"policy": " + ".join(f"{NAMES[t]}:{n}" for t, (n, _) in zip(trigs, combo)), "win": f"{h0}-{h1}",
                         "J_shots": s["Jan"][0], "J_bread": s["Jan"][1], "J_red": s["Jan"][2], "J_net": s["Jan"][3],
                         "O_shots": s["Jul"][0], "O_bread": s["Jul"][1], "O_red": s["Jul"][2], "O_net": s["Jul"][3]})
R = pd.DataFrame(rows)
R["bread"] = R.J_bread + R.O_bread; R["red"] = R.J_red + R.O_red; R["net"] = R.J_net + R.O_net
R["bread_pct"] = (100 * R.bread / 196).round(1)
R["score"] = R.bread - 3 * R.red
ok = R[(R.J_net > 0) & (R.O_net > 0)]
print(f"{len(R)} policies; {len(ok)} profitable in both halves")
print("\nTOP 25 by bread - 3 x red (both halves profitable):")
print(ok.sort_values("score", ascending=False).head(25).to_string(index=False))
print("\nTOP 10 by fewest red days with >= 100 bread days:")
print(ok[ok.bread >= 100].sort_values(["red", "bread"], ascending=[True, False]).head(10).to_string(index=False))
R.to_csv(T / "bread_policy2_grid.csv", index=False)
