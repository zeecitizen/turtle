"""canary_prep.py - look-ahead audit of uhv_filters._prep()'s arrays (the pivots, the camel hump count 'stk', the 5-minute index 'end5').
For ~40 cut points m: rebuild _prep on the data CUT at m bars (indices 0..m-1) and on the data with every bar >= m REPLACED by a random walk;
the arrays must match the full-data arrays wherever they are supposed to be known:
  stk[i], end5[i]          for i <= m-1      (known once bar i has closed)
  lastH[i], lastL[i]       for i <= m-2      (a pivot AT i needs bar i+1; lastH[m-1] MAY differ - that is the 1-bar confirmation lag, and
                                               seeing it differ proves the test can see the future)
Also: the camel index - for every setup the engine sends to the filters, the setup's side (the Diamond camel at bar k) must equal
sign(stk[k]); compare with stk[k-1] / stk[k+1] (an off-by-one would match better there).  Output: out_prep.json"""
import time, json
from _common import *          # noqa: F401,F403
import numpy as np
import sim, uhv_filters
from datetime import datetime, timezone

t0 = time.time()
D = sim.data("year1")
full = {k: np.asarray(D[k]) for k in ("t1", "o1", "h1", "l1", "c1", "v1", "atr")}
clear_caches()
F = {k: np.array(v) for k, v in uhv_filters._prep(full).items() if k != "key"}
n = len(full["t1"])
t = full["t1"].astype(np.int64)
rng = np.random.default_rng(11)
cuts = list(rng.integers(500, n - 5, 30))
for d in ("2026-03-08 07:00", "2026-11-01 06:00", "2026-11-02 22:10"):     # DST start / end
    ts = datetime.strptime(d, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()
    cuts.append(int(np.searchsorted(t, ts)))
gaps = np.where(np.diff(t) > 60)[0]
cuts += [int(g + 1) for g in gaps[::40][:8]] + [int(g + 2) for g in gaps[::50][:4]]     # right after a gap
res = {"cuts": len(cuts), "trunc": {"stk_bad": 0, "end5_bad": 0, "lastH_bad": 0, "lastL_bad": 0, "lastH_lag_at_m-1": 0, "lastL_lag_at_m-1": 0},
       "perturb": {"stk_bad": 0, "end5_bad": 0, "lastH_bad": 0, "lastL_bad": 0, "lastH_lag_at_m-1": 0, "lastL_lag_at_m-1": 0}}
for m in cuts:
    m = int(m)
    for mode in ("trunc", "perturb"):
        if mode == "trunc":
            Dm = {k: v[:m] for k, v in full.items()}
        else:
            Dm = {k: v.copy() for k, v in full.items()}
            L = n - m
            c0 = full["c1"][m - 1]
            cpath = c0 + np.cumsum(rng.normal(0, 3e-4, L))
            op = np.r_[c0, cpath[:-1]]
            Dm["o1"][m:] = op; Dm["c1"][m:] = cpath
            Dm["h1"][m:] = np.maximum(op, cpath) + rng.uniform(0, 6e-4, L)
            Dm["l1"][m:] = np.minimum(op, cpath) - rng.uniform(0, 6e-4, L)
            Dm["v1"][m:] = rng.integers(0, 600, L)
        clear_caches()
        P = uhv_filters._prep(Dm)
        r = res[mode]
        r["stk_bad"] += int((P["stk"][:m] != F["stk"][:m]).sum())
        r["end5_bad"] += int((P["end5"][:m] != F["end5"][:m]).sum())
        r["lastH_bad"] += int((P["lastH"][:m - 1] != F["lastH"][:m - 1]).sum())
        r["lastL_bad"] += int((P["lastL"][:m - 1] != F["lastL"][:m - 1]).sum())
        r["lastH_lag_at_m-1"] += int(P["lastH"][m - 1] != F["lastH"][m - 1])
        r["lastL_lag_at_m-1"] += int(P["lastL"][m - 1] != F["lastL"][m - 1])
print("prep truncation / perturbation:", json.dumps(res))

# ---- the camel index: side of each setup (the Diamond camel at k) vs sign(stk[k + d])
calls, secs, cnt = record_calls({})
stk = F["stk"]
agree = {}
for dlt in (-2, -1, 0, 1, 2):
    a = [int(np.sign(stk[c["k"] + dlt]) == c["side"]) for c in calls]
    agree[f"k{dlt:+d}"] = round(float(np.mean(a)), 4)
bad0 = [c for c in calls if int(np.sign(stk[c["k"]])) != c["side"]]
res["camel_side_vs_sign_stk"] = agree
res["camel_mismatch_at_k"] = len(bad0)
res["camel_mismatch_first_ts"] = [datetime.fromtimestamp(c["ts"], timezone.utc).strftime("%Y-%m-%d %H:%M:%S") for c in bad0[:10]]
print("camel side == sign(stk[k+d]):", agree, " mismatches at k:", len(bad0), res["camel_mismatch_first_ts"])

# ---- end5 stride: how often does end - 5*i land on a bar that does NOT close a 5-minute candle (gaps make the stride wrong)
off = {"Htf5N=12,mode1": 0, "Htf5N=12,mode2": 0, "Htf5N=50,mode2": 0}
tot = {k: 0 for k in off}
for c in calls:
    e = int(F["end5"][c["k"]])
    for key, cntn in (("Htf5N=12,mode1", 12), ("Htf5N=12,mode2", 36), ("Htf5N=50,mode2", 150)):
        if e - 5 * (cntn - 1) < 0:
            continue
        idx = np.array([e - 5 * i for i in range(cntn)])
        tot[key] += 1
        off[key] += int((((t[idx] + 60) % 300) != 0).any())
res["end5_misaligned_share"] = {k: round(off[k] / max(tot[k], 1), 4) for k in off}
res["end5_misaligned_calls"] = off
print("calls whose 5-min series includes a non-5-min-close bar:", res["end5_misaligned_share"])
res["secs"] = round(time.time() - t0, 1)
json.dump(res, open(os.path.join(HERE, "out_prep.json"), "w"), indent=1)
