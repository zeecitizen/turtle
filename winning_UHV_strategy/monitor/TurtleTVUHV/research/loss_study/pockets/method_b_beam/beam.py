"""beam.py - METHOD B: greedy rule-list BEAM SEARCH for small RISKY POCKETS that hold most of the losses (Zee 2026-11-06:
"10% risky trades zone -> here the angel only cuts some of them ... 80% non-risky trades (no angel) -> there's no cut on these trades ...
isolate the risky zones further by breaking them down into chunks").

Data: ../features.csv (one row per trade of the 97.7% base setting; 32 decision-time features; outcome columns win/pnl/half are NEVER inputs).
Pockets are chosen on TRAIN (Mar-Jun) only; TEST (Jul-Nov) is evaluated untouched.

Design (frozen before any test outcome was looked at):
  * conditions = intervals of each feature between cut points (train quantiles 5,10,20..90,95% as midpoints between distinct values, plus a few
    natural cuts), two-sided intervals and one-sided thresholds; ny_hour / weekday also wrap-around windows (e.g. Asia 19:00-02:59 NY).
    spread_pips gets ONLY the natural cuts 1.0 / 2.0 pips: its raw level is a DATA-FEED marker (0.5-0.6 pip until 2026-06-09, 0.0-0.2 after).
    ny_min_of_day is dropped (same information as ny_hour); weekday is re-ordered as a trading week (Sun=0 .. Fri=5).
  * the feed switch (first 0.0-0.2-pip breakout on 2026-06-09) splits train into two regimes with very different loss rates (~4.0% vs ~1.1%).
    PRIMARY score = losses in pocket - K x EXPECTED losses, expected = each trade's own feed-regime train loss rate (so a pocket cannot score
    by merely selecting the old, lossier feed / a time period). K = 3 (pocket must beat 3x its expected rate), fixed from round 1.
    SECONDARY (comparison only) = plain base rate for every trade.
  * beam search: depth <= 3 conditions (each feature at most once), beam width 100, penalty 1 loss per extra condition, min support 1% of
    train trades, losses from >= 5 distinct days and no single day > 1/3 of the pocket's losses (losses cluster by day).
  * greedy rule list: best pocket, remove its trades, search again; stop at 6 pockets, union >= 20% of train trades, or no positive score.
  * nulls: the WHOLE procedure re-run on train outcomes permuted WITHIN each feed regime - circular shift (primary: keeps the day clustering)
    and iid shuffle. Null-trained pockets are also applied to TEST with the real test outcomes.
Python result = HYPOTHESIS, NOT PROMOTED (CLAUDE.md). Run: cd .../pockets && py method_b_beam/beam.py [--nperm 200]"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
POCK = os.path.dirname(HERE)
MON = os.path.abspath(os.path.join(POCK, "..", "..", "..", ".."))          # .../monitor (doctrine.py)
sys.path.insert(0, MON)

ap = argparse.ArgumentParser()
ap.add_argument("--nperm", type=int, default=200)
ap.add_argument("--nperm_sens", type=int, default=0)
ap.add_argument("--seed", type=int, default=20261106)
ap.add_argument("--tag", default="")
ap.add_argument("--no_sens", action="store_true")
args = ap.parse_args()

# ----------------------------------------------------------------------------------------------------------------------------- data
D = pd.read_csv(os.path.join(POCK, "features.csv"))
D["tw_day"] = (D["weekday"] + 1) % 7                                         # trading week: Sun=0 Mon=1 .. Fri=5
SWITCH_ID = D.loc[(D.id.str[:4] == "0609") & (D.spread_pips <= 0.25), "id"].min()
D["newfeed"] = (D.id >= SWITCH_ID).astype(int)
TR = (D.half == "train").to_numpy()
TE = (D.half == "test").to_numpy()
Y = (1 - D.win.to_numpy()).astype(np.int8)                                  # 1 = loss
DAYS = D.id.str[:4].to_numpy()
_, DAYC = np.unique(DAYS, return_inverse=True)
REG = D.newfeed.to_numpy()

EXCLUDE = {"id", "win", "pnl", "half", "weekday", "ny_min_of_day", "newfeed", "tw_day"}
FEATS = [c for c in D.columns if c not in EXCLUDE] + ["tw_day"]
QS = [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
NAT = {
    "side": [0.0], "struct_with": [0.5], "humps": [1.5, 2.5, 3.5, 4.5, 6.5], "box": [5.5, 10.5, 15.5, 19.5],
    "bars_since_uhv": [1.5, 2.5, 3.5, 5.5, 10.5], "gap_pips": [0.15, 0.25, 0.45, 0.95], "spread_pips": [0.95, 1.95],
    "fig_ahead_pips": [4.95, 9.95, 19.95, 89.95, 94.95], "er16": [0.15, 0.30, 0.45], "adx": [20.0, 25.0, 40.0],
    "last_body_dir": [0.0], "ny_hour": [1.5, 2.5, 6.5, 7.5, 11.5, 15.5, 16.5, 17.5, 18.5, 19.5], "tw_day": [0.5, 1.5, 2.5, 3.5, 4.5],
}
NAT_ONLY = {"side", "struct_with", "spread_pips", "ny_hour", "tw_day"}
WRAP = {"ny_hour", "tw_day"}
INTF = {"humps", "box", "bars_since_uhv", "ny_hour", "tw_day"}
DAYNAME = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def mid_cuts(x, qs):
    u = np.unique(x)
    out = set()
    for q in qs:
        v = np.quantile(x, q)
        i = np.searchsorted(u, v, side="right") - 1
        if 0 <= i < len(u) - 1:
            out.add(round(float(u[i] + u[i + 1]) / 2, 6))
    return out


conds = []
for f in FEATS:
    x = D.loc[TR, f].to_numpy(float)
    cuts = set(NAT.get(f, []))
    if f not in NAT_ONLY:
        cuts |= mid_cuts(x, QS)
    cuts = sorted(c for c in cuts if x.min() <= c < x.max())
    edges = [None] + cuts + [None]
    for i in range(len(edges)):
        for j in range(i + 1, len(edges)):
            if i == 0 and j == len(edges) - 1:
                continue
            conds.append(dict(f=f, lo=edges[i], hi=edges[j], wrap=False))
    if f in WRAP:
        for a in cuts:
            for b in cuts:
                if b < a:
                    conds.append(dict(f=f, lo=a, hi=b, wrap=True))         # x > a  OR  x <= b


def cmask(c, X):
    x = X[c["f"]]
    if c["wrap"]:
        return (x > c["lo"]) | (x <= c["hi"])
    m = np.ones(len(x), bool)
    if c["lo"] is not None:
        m &= x > c["lo"]
    if c["hi"] is not None:
        m &= x <= c["hi"]
    return m


def fmt(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def ctext(c):
    f, lo, hi, w = c["f"], c["lo"], c["hi"], c["wrap"]
    if f == "side":
        return "side == buy" if lo is not None else "side == sell"
    if f == "struct_with":
        return "struct_with == 1" if lo is not None else "struct_with == 0"
    if f in INTF:
        a = None if lo is None else int(math.floor(lo)) + 1
        b = None if hi is None else int(math.floor(hi))
        nm = (lambda v: DAYNAME[v]) if f == "tw_day" else (lambda v: str(v))
        fn = "weekday" if f == "tw_day" else f
        if w:
            return f"({fn} >= {nm(a)} or {fn} <= {nm(b)})"
        if a is None:
            return f"{fn} <= {nm(b)}"
        if b is None:
            return f"{fn} >= {nm(a)}"
        return f"{fn} == {nm(a)}" if a == b else f"{nm(a)} <= {fn} <= {nm(b)}"
    if w:
        return f"({f} > {fmt(lo)} or {f} <= {fmt(hi)})"
    if lo is None:
        return f"{f} <= {fmt(hi)}"
    if hi is None:
        return f"{f} > {fmt(lo)}"
    return f"{fmt(lo)} < {f} <= {fmt(hi)}"


X = {f: D[f].to_numpy(float) for f in FEATS}
C_all = np.stack([cmask(c, X) for c in conds])                              # n_cond x N_all
NTR = int(TR.sum())
NMIN = int(math.ceil(0.01 * NTR))
# drop conditions that can never be a pocket (train support < 1%) and duplicates of an earlier condition's train mask
keep, seen = [], set()
for i in range(len(conds)):
    m = C_all[i, TR]
    s = int(m.sum())
    if s < NMIN or s == NTR:
        continue
    h = np.packbits(m).tobytes()
    if h in seen:
        continue
    seen.add(h)
    keep.append(i)
conds = [conds[i] for i in keep]
C_all = C_all[keep]
GRP = np.array([FEATS.index(c["f"]) for c in conds])
Bb = C_all[:, TR]
Bf = Bb.astype(np.float32)
ALLOWED = {"onesided": np.array([(c["lo"] is None or c["hi"] is None) and not c["wrap"] for c in conds])}
y_tr = Y[TR]
reg_tr = REG[TR]
day_tr = DAYC[TR]
print(f"{len(D)} trades: train {NTR} ({int(y_tr.sum())} losses), test {int(TE.sum())} ({int(Y[TE].sum())} losses); "
      f"feed switch at {SWITCH_ID}; {len(FEATS)} features -> {len(conds)} distinct base conditions; min support {NMIN}", flush=True)


# ----------------------------------------------------------------------------------------------------------------------------- search
def expected(y, cfg):
    if cfg["score"] == "plain":
        return np.full(len(y), y.mean(), np.float32)
    pe = np.zeros(len(y), np.float32)
    for r in (0, 1):
        idx = reg_tr == r
        pe[idx] = y[idx].mean()
    return pe


def beam_round(y, pe, R, cfg):
    k, nmin, B, pen, T = cfg["k"], cfg["nmin"], cfg["beam"], cfg["pen"], cfg["topT"]
    idxL = np.flatnonzero((y == 1) & R)
    if len(idxL) == 0:
        return None, 0
    ud, dinv = np.unique(day_tr[idxL], return_inverse=True)
    DL = np.zeros((len(idxL), len(ud)), np.float32)
    DL[np.arange(len(idxL)), dinv] = 1
    BL = Bf[:, idxL]
    parents = [dict(rule=(), groups=frozenset(), mask=R.copy(), n=int(R.sum()))]
    best, ncand = None, 0
    for depth in range(1, cfg["depth"] + 1):
        M = np.stack([p["mask"] for p in parents], axis=1).astype(np.float32)
        n = Bf @ M
        L = BL @ M[idxL]
        E = Bf @ (M * pe[:, None])
        S = L - k * E
        valid = n >= nmin
        if cfg.get("allowed") is not None:
            valid &= ALLOWED[cfg["allowed"]][:, None]
        for pi, p in enumerate(parents):
            if p["groups"]:
                valid[np.isin(GRP, list(p["groups"])), pi] = False
            valid[n[:, pi] >= p["n"] - 0.5, pi] = False                      # a condition must cut something
        ncand += int(valid.sum())
        Sv = np.where(valid, S, -np.inf)
        flat = np.argsort(-Sv, axis=None, kind="stable")[:T]
        flat = flat[np.isfinite(Sv.ravel()[flat])]
        if len(flat) == 0:
            break
        ci, pi = np.unravel_index(flat, Sv.shape)
        memb = (BL[ci] > 0) & (M[idxL][:, pi].T > 0)
        cnt = memb.astype(np.float32) @ DL
        nd = (cnt > 0).sum(1)
        mx = cnt.max(1) if cnt.shape[1] else np.zeros(len(ci))
        Lc = memb.sum(1)
        ok_beam = nd >= cfg["min_days"]
        ok_sel = ok_beam & (mx <= Lc * cfg["max_day_share"] + 1e-9)
        sel = np.flatnonzero(ok_sel)
        if len(sel):
            t = sel[0]
            sc = float(Sv[ci[t], pi[t]]) - pen * (depth - 1)
            if best is None or sc > best["pscore"]:
                best = dict(rule=parents[pi[t]]["rule"] + (int(ci[t]),), n=int(n[ci[t], pi[t]]), L=int(Lc[t]),
                            E=float(E[ci[t], pi[t]]), score=float(Sv[ci[t], pi[t]]), pscore=sc, days=int(nd[t]), maxday=int(mx[t]))
        if depth == cfg["depth"]:
            break
        newp, seen_ = [], set()
        for t in np.flatnonzero(ok_beam):
            m = Bb[ci[t]] & parents[pi[t]]["mask"]
            h = np.packbits(m).tobytes()
            if h in seen_:
                continue
            seen_.add(h)
            newp.append(dict(rule=parents[pi[t]]["rule"] + (int(ci[t]),), groups=parents[pi[t]]["groups"] | {int(GRP[ci[t]])},
                             mask=m, n=int(m.sum())))
            if len(newp) >= B:
                break
        parents = newp
        if not parents:
            break
    if best is not None:
        m = R.copy()
        for c in best["rule"]:
            m &= Bb[c]
        best["mask"] = m
    return best, ncand


def greedy(y, cfg):
    pe = expected(y, cfg)
    N = len(y)
    R = np.ones(N, bool)
    pockets, ncand = [], 0
    for _ in range(cfg["max_pockets"]):
        best, nc = beam_round(y, pe, R, cfg)
        ncand += nc
        if best is None or best["pscore"] <= 0:
            break
        pockets.append(best)
        R &= ~best["mask"]
        if (~R).sum() >= cfg["budget"] * N:
            break
    return pockets, ncand


def rule_mask(rule, half_mask):
    m = np.ones(int(half_mask.sum()), bool)
    for c in rule:
        m &= C_all[c, half_mask]
    return m


def half_stats(rules, half_mask, y=None):
    """standalone + incremental stats of each rule and the union, on one half (y defaults to the real outcomes)."""
    yy = Y[half_mask] if y is None else y
    dd = DAYC[half_mask]
    N, Ltot = len(yy), int(yy.sum())
    covered = np.zeros(N, bool)
    out = []
    for rule in rules:
        m = rule_mask(rule, half_mask)
        inc = m & ~covered
        covered |= m
        ns, ls = int(m.sum()), int(yy[m].sum())
        ni, li = int(inc.sum()), int(yy[inc].sum())
        nu, lu = N - int(covered.sum()), Ltot - int(yy[covered].sum())
        out.append(dict(
            n=ns, share=ns / N, L=ls, Lshare=ls / max(Ltot, 1), rate=ls / max(ns, 1), loss_days=int(len(np.unique(dd[m & (yy == 1)]))),
            untouched_wr_alone=1 - (Ltot - ls) / max(N - ns, 1),
            n_inc=ni, L_inc=li, rate_inc=li / max(ni, 1),
            cum_share=1 - nu / N, cum_L=Ltot - lu, cum_Lshare=(Ltot - lu) / max(Ltot, 1), cum_untouched_wr=1 - lu / max(nu, 1)))
    nu, lu = N - int(covered.sum()), Ltot - int(yy[covered].sum())
    union = dict(n=int(covered.sum()), share=float(covered.mean()), L=Ltot - lu, Lshare=(Ltot - lu) / max(Ltot, 1),
                 rate=(Ltot - lu) / max(int(covered.sum()), 1), untouched_n=nu, untouched_L=lu, untouched_wr=1 - lu / max(nu, 1),
                 base_rate=Ltot / N, base_wr=1 - Ltot / N, N=N, Ltot=Ltot)
    return out, union


def perm_within(y, rng, mode):
    yp = y.copy()
    for r in (0, 1):
        idx = np.flatnonzero(reg_tr == r)
        if len(idx) < 2:
            continue
        if mode == "shift":
            m = len(idx)
            s = int(rng.integers(int(0.1 * m), int(0.9 * m) + 1))
            yp[idx] = np.roll(y[idx], s)
        else:
            yp[idx] = rng.permutation(y[idx])
    return yp


def summarize_run(pockets, y):
    """train-side statistics of one greedy run (under its own outcomes y) + test-side stats with the real test outcomes."""
    rules = [p["rule"] for p in pockets]
    _, utr = half_stats(rules, TR, y)
    _, ute = half_stats(rules, TE)
    return dict(k=len(pockets), S=float(sum(p["score"] for p in pockets)), tr_share=utr["share"], tr_L=utr["L"],
                tr_Lshare=utr["Lshare"], tr_rate=utr["rate"], tr_unt_wr=utr["untouched_wr"],
                te_share=ute["share"], te_L=ute["L"], te_Lshare=ute["Lshare"], te_rate=ute["rate"], te_unt_wr=ute["untouched_wr"],
                te_lift=(ute["rate"] / ute["base_rate"]) if ute["n"] else 0.0)


BASE_CFG = dict(score="regime", k=3.0, nmin=NMIN, beam=100, pen=1.0, topT=3000, depth=3, min_days=5, max_day_share=1 / 3,
                max_pockets=6, budget=0.20)

# ----------------------------------------------------------------------------------------------------------------------------- real run
t0 = time.time()
pockets, ncand = greedy(y_tr, BASE_CFG)
t_run = time.time() - t0
rules = [p["rule"] for p in pockets]
st_tr, u_tr = half_stats(rules, TR)
st_te, u_te = half_stats(rules, TE)
BASE_TR, BASE_TE, BASE_ALL = u_tr["base_rate"], u_te["base_rate"], float(Y.mean())
print(f"\nPRIMARY run: {len(pockets)} pockets, {ncand:,} candidate rules scored, {t_run:.1f}s", flush=True)
rows = []
for i, (p, a, b) in enumerate(zip(pockets, st_tr, st_te)):
    txt = " and ".join(ctext(conds[c]) for c in p["rule"])
    drift = b["share"] / a["share"] if a["share"] else float("nan")
    rows.append(dict(i=i + 1, rule=txt, rule_idx=list(p["rule"]), search={k_: v for k_, v in p.items() if k_ not in ("mask", "rule")},
                     train=a, test=b, coverage_drift=drift, drift_flag=bool(drift > 2 or drift < 0.5)))
    print(f"  P{i+1}: {txt}\n      search: n={p['n']} L={p['L']} E={p['E']:.2f} O/E={p['L']/max(p['E'],1e-9):.2f} score={p['score']:.2f} "
          f"loss-days={p['days']} maxday={p['maxday']}")
    for nm, s, base, lt in (("train", a, BASE_TR, u_tr["Ltot"]), ("test ", b, BASE_TE, u_te["Ltot"])):
        print(f"      {nm}: {100*s['share']:5.2f}% of trades ({s['n']}), losses {s['L']}/{lt} ({100*s['Lshare']:.1f}%), rate "
              f"{100*s['rate']:.2f}% = {s['rate']/base:.2f}x half base, {s['rate']/BASE_ALL:.2f}x 2.26%; untouched WR alone "
              f"{100*s['untouched_wr_alone']:.2f}% | incremental n={s['n_inc']} L={s['L_inc']} | cumulative {100*s['cum_share']:.1f}% of "
              f"trades, {s['cum_L']} losses, untouched WR {100*s['cum_untouched_wr']:.2f}%  [loss-days {s['loss_days']}]")
    if rows[-1]["drift_flag"]:
        print(f"      ** coverage drift: test share / train share = {drift:.2f}")
for nm, u in (("TRAIN", u_tr), ("TEST ", u_te)):
    need = max(0, int(math.ceil(u["Ltot"] - 0.007 * (u["N"] - u["n"]))))
    print(f"  UNION {nm}: {100*u['share']:.1f}% of trades ({u['n']}/{u['N']}), {u['L']}/{u['Ltot']} losses ({100*u['Lshare']:.1f}%), "
          f"pocket rate {100*u['rate']:.2f}% ({u['rate']/u['base_rate']:.2f}x half base); untouched {u['untouched_n']} trades, "
          f"{u['untouched_L']} losses, WR {100*u['untouched_wr']:.2f}% (base {100*u['base_wr']:.2f}%); bar 99.3% needs >= {need} losses "
          f"in the pockets at this coverage")
nte, Lte, nu = u_te["N"], u_te["Ltot"], u_te["n"]
rnd_mean = Lte * nu / nte
rnd_sd = math.sqrt(nu * (Lte / nte) * (1 - Lte / nte) * (nte - nu) / max(nte - 1, 1))
print(f"  random {100*u_te['share']:.1f}% subset of test would hold {rnd_mean:.1f} +/- {rnd_sd:.1f} losses (hypergeometric)", flush=True)

# ----------------------------------------------------------------------------------------------------------------------------- nulls
rng = np.random.default_rng(args.seed)
real_sum = summarize_run(pockets, y_tr)
nulls = {}
for mode in ("shift", "shuffle"):
    res = []
    t1 = time.time()
    for b in range(args.nperm):
        yp = perm_within(y_tr, rng, mode)
        pk, _ = greedy(yp, BASE_CFG)
        res.append(summarize_run(pk, yp))
        if (b + 1) % 25 == 0:
            print(f"  null {mode}: {b+1}/{args.nperm} ({time.time()-t1:.0f}s)", flush=True)
    nulls[mode] = res

STATS = ("S", "tr_L", "tr_Lshare", "tr_rate", "tr_unt_wr", "te_L", "te_lift", "te_unt_wr")


def pctl(stat, res):
    v = np.array([r[stat] for r in res])
    x = real_sum[stat]
    return dict(real=x, null_mean=float(v.mean()), null_p95=float(np.quantile(v, 0.95)), null_max=float(v.max()),
                p=(1 + int((v >= x - 1e-12).sum())) / (1 + len(v)))


null_report = {}
for mode, res in nulls.items():
    if not res:
        continue
    null_report[mode] = {s: pctl(s, res) for s in STATS}
    null_report[mode]["n_runs"] = len(res)
    null_report[mode]["null_k_mean"] = float(np.mean([r["k"] for r in res]))
    null_report[mode]["null_tr_share_mean"] = float(np.mean([r["tr_share"] for r in res]))
    null_report[mode]["null_te_share_mean"] = float(np.mean([r["te_share"] for r in res]))
    print(f"\nNULL ({mode}, within feed regime, {len(res)} runs of the full greedy search):")
    for s in STATS:
        q = null_report[mode][s]
        print(f"   {s:10s} real {q['real']:.4f} | null mean {q['null_mean']:.4f} p95 {q['null_p95']:.4f} max {q['null_max']:.4f} | p = {q['p']:.3f}")
    print(f"   null pockets/run {null_report[mode]['null_k_mean']:.2f}, null train coverage {100*null_report[mode]['null_tr_share_mean']:.1f}%, "
          f"null test coverage {100*null_report[mode]['null_te_share_mean']:.1f}%", flush=True)

# ----------------------------------------------------------------------------------------------------------------------------- sensitivity
SENS = {} if args.no_sens else {
    "K1.5": dict(BASE_CFG, k=1.5), "K2": dict(BASE_CFG, k=2.0), "K4": dict(BASE_CFG, k=4.0),
    "minsup2%": dict(BASE_CFG, nmin=int(math.ceil(0.02 * NTR))), "depth2": dict(BASE_CFG, depth=2),
    "plain_K3": dict(BASE_CFG, score="plain"), "plain_K2": dict(BASE_CFG, score="plain", k=2.0),
    "no_day_rule": dict(BASE_CFG, min_days=1, max_day_share=1.0),
    "onesided": dict(BASE_CFG, allowed="onesided"), "onesided_K2": dict(BASE_CFG, allowed="onesided", k=2.0),
    "depth2_minsup2%": dict(BASE_CFG, depth=2, nmin=int(math.ceil(0.02 * NTR))),
    "depth2_minsup2%_K2": dict(BASE_CFG, depth=2, nmin=int(math.ceil(0.02 * NTR)), k=2.0),
    "onesided_depth2_minsup3%_K2": dict(BASE_CFG, allowed="onesided", depth=2, nmin=int(math.ceil(0.03 * NTR)), k=2.0),
}
sens = {}
if SENS:
    print("\nSENSITIVITY (reported, never chosen from; train -> test union):")
for nm, cfg in SENS.items():
    pk, nc = greedy(y_tr, cfg)
    rr = [p["rule"] for p in pk]
    _, a = half_stats(rr, TR)
    _, b = half_stats(rr, TE)
    srow = dict(cfg=dict(cfg), n_pockets=len(pk), ncand=nc, rules=[" and ".join(ctext(conds[c]) for c in r) for r in rr], train=a, test=b)
    if args.nperm_sens:
        res = []
        for _ in range(args.nperm_sens):
            yp = perm_within(y_tr, rng, "shift")
            pk2, _ = greedy(yp, cfg)
            res.append(summarize_run(pk2, yp))
        rs = summarize_run(pk, y_tr)
        srow["null_shift"] = {s: dict(real=rs[s], null_mean=float(np.mean([r[s] for r in res])),
                                      p=(1 + sum(r[s] >= rs[s] - 1e-12 for r in res)) / (1 + len(res))) for s in ("S", "tr_L", "te_L", "te_lift")}
    sens[nm] = srow
    extra = (f" | null-shift p(S)={srow['null_shift']['S']['p']:.3f} p(teL)={srow['null_shift']['te_L']['p']:.3f}"
             if args.nperm_sens else "")
    print(f"  {nm:12s} {len(pk)} pockets | train {100*a['share']:.1f}% trades, {a['L']}/{a['Ltot']} losses, untouched WR "
          f"{100*a['untouched_wr']:.2f}% | test {100*b['share']:.1f}% trades, {b['L']}/{b['Ltot']} losses, untouched WR "
          f"{100*b['untouched_wr']:.2f}% (base {100*b['base_wr']:.2f}%){extra}", flush=True)
    for r in srow["rules"]:
        print(f"       - {r}")

# ----------------------------------------------------------------------------------------------------------------------------- doctrine + save
from doctrine import python_says  # noqa: E402

print()
python_says("TEST untouched zone (pockets skipped), Method B primary", win_pct=100 * u_te["untouched_wr"], need_pct=99.3)
python_says("TRAIN untouched zone (pockets skipped), Method B primary", win_pct=100 * u_tr["untouched_wr"], need_pct=99.3)

out = dict(
    method="B rule-list beam search", switch_id=SWITCH_ID, n_conditions=len(conds), features=FEATS, cfg=BASE_CFG, ncand_real=ncand,
    base=dict(train=BASE_TR, test=BASE_TE, all=BASE_ALL,
              train_feed_rates={("new" if r else "old"): float(y_tr[reg_tr == r].mean()) for r in (0, 1)},
              train_feed_n={("new" if r else "old"): int((reg_tr == r).sum()) for r in (0, 1)},
              train_feed_L={("new" if r else "old"): int(y_tr[reg_tr == r].sum()) for r in (0, 1)}),
    pockets=rows, union=dict(train=u_tr, test=u_te), random_test_yardstick=dict(mean=rnd_mean, sd=rnd_sd),
    real_summary=real_sum, null=null_report, null_runs=nulls, sensitivity=sens)
tag = ("_" + args.tag) if args.tag else ""
with open(os.path.join(HERE, f"results{tag}.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
print(f"\nsaved {os.path.join(HERE, f'results{tag}.json')}  (hypothesis, NOT PROMOTED)")
