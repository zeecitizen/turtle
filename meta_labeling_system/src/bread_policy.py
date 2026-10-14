"""Daily ONE-SHOT policy search over the MT5 census shots (hypothesis stage; the winner must pass a real one-shot MT5
run). Census = bread_winner_shot with InpShotMax 99: every trigger fired every time, each a real MT5 position with
the shot geometry (0.11 lots, TP $1, SL $6). A policy = (triggers, PKT window, filters) -> per day the FIRST
qualifying shot. Scored per weekday: bread (>= $10), red, net, separately for Jan-Jun and Jul-Oct."""
import itertools, datetime as dt
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


def load(name, trig_map=None):
    d = pd.read_csv(T / f"bread_shots_{name}_full.csv")
    d["t"] = pd.to_datetime(d.pkt_time, format="%Y.%m.%d %H:%M")
    d["hr"] = d.t.dt.hour + d.t.dt.minute / 60
    d["day"] = d.t.dt.date
    if trig_map: d["trig"] = d.trig.map(trig_map).fillna(d.trig)
    return d


dsv = load("census_dsv")                          # 1 Diamond, 2 Saad (ctx), 3 VSISA raw
vl = load("census_v_late", {3: 5})                # 5 = VSISA after its ML
sn = load("census_s_noctx", {2: 6})               # 6 = Saad without context
ALL = pd.concat([dsv, vl, sn], ignore_index=True).sort_values("t")
ALL["win"] = ALL.net > 0
NAMES = {1: "DIA", 2: "SAADctx", 3: "VSraw", 5: "VSml", 6: "SAADraw"}
print("census:", ALL.groupby("trig").agg(n=("win", "size"), wr=("win", "mean"), net=("net", "sum")).rename(index=NAMES).round(3).to_string())

HALVES = {"Jan-Jun": (weekdays("2026-01-06", "2026-07-01"), "2026-07-01"), "Jul-Oct": (weekdays("2026-07-01", "2026-10-08"), None)}


def evaluate(sub, days):
    first = sub.groupby("day").head(1).set_index("day").net
    v = [first.get(d) for d in days]
    shots = [x for x in v if x is not None]
    n = len(days)
    return {"days": n, "shots": len(shots), "bread": sum(x >= 10 for x in shots), "red": sum(x < 0 for x in shots),
            "net": round(sum(shots), 1), "wr": round(100 * np.mean([x > 0 for x in shots]), 1) if shots else 0}


rows = []
trig_sets = [(1,), (3,), (5,), (2,), (1, 3), (1, 5), (1, 2), (2, 3), (1, 2, 3), (1, 2, 5), (3, 5), (1, 3, 5), (1, 2, 3, 5)]
for ts in trig_sets:
    base = ALL[ALL.trig.isin(ts)]
    for h0 in (0, 6, 9, 10, 11, 12, 13, 14, 15, 16, 16.5, 17, 18, 18.5):
        for h1 in (20, 22, 24):
            if h1 <= h0: continue
            sub = base[(base.hr >= h0) & (base.hr < h1)]
            r = {"trigs": "+".join(NAMES[x] for x in ts), "win": f"{h0}-{h1}"}
            for k, (days, _) in HALVES.items():
                e = evaluate(sub[sub.day.isin(days)], days)
                for kk, vv in e.items(): r[f"{k[:3]}_{kk}"] = vv
            r["bread_both"] = r["Jan_bread"] + r["Jul_bread"]; r["red_both"] = r["Jan_red"] + r["Jul_red"]
            r["net_both"] = r["Jan_net"] + r["Jul_net"]
            rows.append(r)
R = pd.DataFrame(rows)
R["score"] = R.bread_both - 3 * R.red_both
cols = ["trigs", "win", "Jan_shots", "Jan_wr", "Jan_bread", "Jan_red", "Jan_net", "Jul_shots", "Jul_wr", "Jul_bread", "Jul_red", "Jul_net", "bread_both", "red_both", "net_both", "score"]
print("\nTOP by bread days - 3 x red days (Jan-Jun 125 weekdays, Jul-Oct 71):")
print(R.sort_values("score", ascending=False)[cols].head(25).to_string(index=False))
print("\nTOP by net, both halves positive:")
print(R[(R.Jan_net > 0) & (R.Jul_net > 0)].sort_values("net_both", ascending=False)[cols].head(15).to_string(index=False))
R.to_csv(T / "bread_policy_grid.csv", index=False)
