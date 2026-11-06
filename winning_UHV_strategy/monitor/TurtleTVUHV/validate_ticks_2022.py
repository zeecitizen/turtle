"""validate_ticks_2022.py - checks the 2022-2026 Blueberry tick file: order, prices, spreads, duplicates, per-year counts, big gaps.
Writes simdata/validate_ticks_2022.json.  py validate_ticks_2022.py"""
import json, sys
from pathlib import Path
import pandas as pd, numpy as np
SRC = Path("C:/Users/zeesh/turtle/data_15min_2015_onwards_xauusd/XAUUSD_202201030100_202610232021.csv")
OUT = Path(__file__).resolve().parent / "simdata" / "validate_ticks_2022.json"
res = {"file": str(SRC), "rows": 0, "bad_bid_ask": 0, "ask_below_bid": 0, "out_of_order": 0, "exact_duplicates": 0,
       "per_year": {}, "max_spread_pts": 0.0, "spread_gt_200pts": 0, "gaps_over_1h": [], "first": None, "last": None}
prev_t = None; prev_key = None; last_day = None
for ch in pd.read_csv(SRC, sep="\t", usecols=[0, 1, 2, 3], chunksize=5_000_000, dtype={"<DATE>": str, "<TIME>": str}):
    d = pd.to_datetime(ch["<DATE>"] + " " + ch["<TIME>"], format="%Y.%m.%d %H:%M:%S.%f", errors="coerce")
    bad_dt = int(d.isna().sum())
    t = (d - pd.Timestamp("1970-01-01")).dt.total_seconds().to_numpy()
    b = ch["<BID>"].to_numpy(np.float64); a = ch["<ASK>"].to_numpy(np.float64)
    n = len(ch); res["rows"] += n
    if res["first"] is None: res["first"] = str(d.iloc[0])
    res["last"] = str(d.iloc[-1])
    res["bad_bid_ask"] += int(((b <= 0) | (a <= 0) | np.isnan(b) | np.isnan(a) | bad_dt).sum())
    res["ask_below_bid"] += int((a < b).sum())
    sp = (a - b) / 0.01
    res["max_spread_pts"] = max(res["max_spread_pts"], float(np.nanmax(sp)) if n else 0.0)
    res["spread_gt_200pts"] += int((sp > 200).sum())
    dt = np.diff(t, prepend=(prev_t if prev_t is not None else t[0]))
    res["out_of_order"] += int((dt < 0).sum())
    big = np.where(dt > 3600)[0]
    for k in big[:20]:
        if len(res["gaps_over_1h"]) < 200:
            res["gaps_over_1h"].append([str(d.iloc[k - 1] if k else prev_key), str(d.iloc[k])])
    key = np.char.add(np.char.add(ch["<DATE>"].to_numpy().astype(str), " "), ch["<TIME>"].to_numpy().astype(str)) if False else None
    yrs = d.dt.year.to_numpy()
    for y in np.unique(yrs):
        res["per_year"][str(int(y))] = res["per_year"].get(str(int(y)), 0) + int((yrs == y).sum())
    # exact duplicates: same timestamp, bid and ask as the previous tick
    same_t = np.r_[False, (t[1:] == t[:-1]) & (b[1:] == b[:-1]) & (a[1:] == a[:-1])]
    res["exact_duplicates"] += int(same_t.sum())
    prev_t = t[-1]; prev_key = d.iloc[-1]
    print(res["rows"], flush=True)
res["verdict"] = "OK" if (res["bad_bid_ask"] == 0 and res["ask_below_bid"] == 0 and res["out_of_order"] == 0) else "PROBLEMS"
OUT.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
print("done", res["verdict"], res["rows"], flush=True)
