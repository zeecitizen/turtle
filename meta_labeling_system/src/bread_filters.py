"""Which readings separate winning shots from losing ones - in BOTH halves (hypothesis stage).
Input: census shot logs (every trigger fired, each a real MT5 position, readings logged at entry)."""
import sys
import numpy as np, pandas as pd
from pathlib import Path

T = Path(r"C:\Users\zeesh\turtle\testing")
names = sys.argv[1:] or ["census_dsv"]
d = pd.concat([pd.read_csv(T / f"bread_shots_{n}_full.csv").assign(src=n) for n in names], ignore_index=True)
d["t"] = pd.to_datetime(d.pkt_time, format="%Y.%m.%d %H:%M")
d["hr"] = d.t.dt.hour + d.t.dt.minute / 60
d["h1"] = d.t < "2026-07-01"
d["win"] = d.net > 0
d["trend_ok"] = (d.px_e50 > 0) & (d.e9_e50 > 0)
d["vs_agree"] = d.vs_dir > 0
FE = ["er", "px_e50", "e9_e50", "e50_slope", "vs_age", "hr", "er_net", "regime"]
for trig, g in d.groupby("trig"):
    print(f"\n===== trigger {trig}: {len(g)} shots, WR {100 * g.win.mean():.1f}% (Jan-Jun {100 * g[g.h1].win.mean():.1f}%, Jul-Oct {100 * g[~g.h1].win.mean():.1f}%) net {g.net.sum():.0f}")
    rows = []
    for f in FE:
        try:
            q = pd.qcut(g[f], 4, duplicates="drop")
        except Exception:
            continue
        for lvl, gg in g.groupby(q, observed=True):
            a, b = gg[gg.h1], gg[~gg.h1]
            rows.append((f, str(lvl), len(gg), 100 * gg.win.mean(), 100 * a.win.mean() if len(a) else np.nan, 100 * b.win.mean() if len(b) else np.nan, gg.net.sum()))
    for f in ["trend_ok", "vs_agree"]:
        for lvl, gg in g.groupby(f):
            a, b = gg[gg.h1], gg[~gg.h1]
            rows.append((f, str(lvl), len(gg), 100 * gg.win.mean(), 100 * a.win.mean() if len(a) else np.nan, 100 * b.win.mean() if len(b) else np.nan, gg.net.sum()))
    R = pd.DataFrame(rows, columns=["feature", "bucket", "n", "wr", "wr_JanJun", "wr_JulOct", "net"]).round(1)
    print(R.to_string(index=False))
