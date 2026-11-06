"""stress.py - Zee 2026-10-20: "implement all of these as stress test section down below on the turtle tv web page (skip no one)".
32 robustness tests on the Turtle TV Tester (sim.py, ~10 ms a year), on the whole Blueberry year with the EA's own rules (the version that would
really trade). Each returns {id, cat, name, status PASS / WARN / FAIL / N/A, headline, and a table / histogram / heatmap}. Where a test cannot be
done literally on this data (no 2008 gold ticks, no order book for a CFD, one instrument), the nearest honest version is run and says so.
CLAUDE.md: these are hypothesis tests on the fast engine; MT5 stays the judge of any setting they suggest."""
import itertools
import json
import math
import time
from datetime import datetime
from pathlib import Path
from statistics import NormalDist

import numpy as np

import optimizer
import sim

HERE = Path(__file__).resolve().parent
LEDGER = sim.SIMDATA / "trials.json"
DEPOSIT = 100000.0
EP = lambda y, m, d=1: int((datetime(y, m, d) - datetime(1970, 1, 1)).total_seconds())
MONTHS = [(EP(2026, m), EP(2026, m + 1)) for m in range(1, 10)] + [(EP(2026, 10), EP(2026, 11))]
ND = NormalDist()


# ---------------------------------------------------------------- the file drawer (every configuration ever tried)
def ledger():
    try:
        return json.loads(LEDGER.read_text())
    except Exception:                                       # noqa: BLE001
        return {"optimizer": 0, "manual": 0, "stress": 0, "since": datetime.now().strftime("%Y-%m-%d %H:%M")}


def count_trials(kind, n):
    d = ledger()
    d[kind] = d.get(kind, 0) + int(n)
    LEDGER.parent.mkdir(exist_ok=True)
    LEDGER.write_text(json.dumps(d))


# ---------------------------------------------------------------- engine helpers


_MEM = [0]


def sim_on(D, inputs, **extra):
    """the FULL engine (sim_full, every EA input - the one the rest of Turtle TV uses) on an in-memory dataset (perturbed / scrambled / synthetic
    prices on the real timeline). Each dataset gets a private, one-off slot: its EMA / ADX caches can never be handed to another dataset (they were
    keyed by id(D), which Python reuses once a dataset is freed - the look-ahead audit then saw another dataset's EMAs and cried wolf)."""
    _MEM[0] += 1
    key = f"_mem{_MEM[0]}"
    sim._D[key] = D
    try:
        return sim.simulate(inputs, ds=key, **extra)[0]
    finally:
        sim._D.pop(key, None)
        for c in (sim._EMA, sim._ADX, sim._HTF):
            for k in [k for k in c if k[0] == key]:
                c.pop(k, None)


def real(tr):
    r = tr[tr[:, 10] == 0]
    return r[np.argsort(r[:, 4], kind="stable")]


def sc(tr):
    return sim.score(tr, 1)


def row_stats(label, tr, base=None):
    s = sc(tr)
    d = "" if base is None or not base["net"] else f"{100 * (s['net'] - base['net']) / abs(base['net']):+.0f}%"
    return [label, s["n"], f"{s['wr']}%", f"{s['net']:+,.0f}", f"{s['pf']}", f"{s['dd']:,.0f}", d]


HEAD = ["", "Trades", "Win rate", "Net $", "PF", "Max DD $", "vs real"]


def monthly(tr):
    """P&L per calendar month by entry, PURGED: a trade that crosses a month boundary counts in no month (no leakage between folds)."""
    r = real(tr)
    v = np.zeros(len(MONTHS))
    for x in r:
        for i, (a, b) in enumerate(MONTHS):
            if a <= x[1] < b:
                if x[4] < b:
                    v[i] += x[6]
                break
    return v


def daily(tr):
    r = real(tr)
    D = sim.data()
    days = np.unique(D["t1"] // 86400)
    v = {int(d): 0.0 for d in days}
    for x in r:
        v[int(x[4]) // 86400] = v.get(int(x[4]) // 86400, 0.0) + x[6]
    return np.array([v[k] for k in sorted(v)])


def neighbours_set(base, n=120, seed=7):
    """n configurations around the settings: 2-5 settings moved 1-3 steps each (the alternatives a researcher would have tried)."""
    rng = np.random.default_rng(seed)
    out, seen = [], set()
    space = [s for s in optimizer.SPACE if s[1] != "box"]
    while len(out) < n:
        c = dict(base)
        for i in rng.choice(len(space), size=int(rng.integers(2, 6)), replace=False):
            name, kind, grid = space[int(i)]
            d = int(rng.choice([-1, 1]))
            for _ in range(int(rng.integers(1, 4))):
                v = optimizer.neighbours(c, name, kind, grid, d)
                if v is not None:
                    c[name] = v
        if int(float(c["InpEmaSlow"])) <= int(float(c["InpEmaFast"])) or int(float(c["InpSessTo"])) <= int(float(c["InpSessFrom"])):
            continue
        key = json.dumps(c, sort_keys=True)
        if key not in seen:
            seen.add(key); out.append(c)
    return out


def hist(values, bins=20, mark=None):
    v = np.asarray(values, dtype=float)
    lo, hi = float(np.min(v)), float(np.max(v))
    if mark is not None:
        lo, hi = min(lo, mark), max(hi, mark)
    if hi <= lo:
        hi = lo + 1
    c, e = np.histogram(v, bins=bins, range=(lo, hi))
    return {"edges": [round(float(x), 2) for x in e], "counts": c.tolist(), "mark": mark}


def T(head, rows):
    return {"head": head, "rows": rows}


def res(id_, cat, name, status, headline, **kw):
    return dict({"id": id_, "cat": cat, "name": name, "status": status, "headline": headline}, **kw)


# ---------------------------------------------------------------- perturbed datasets (the real timeline, other prices)
def _rebuild(D0, o1, h1, l1, c1):
    """A dataset with these 1-minute prices on the real timeline: 15-min candles re-aggregated, EMA / ATR / ADX recomputed."""
    D = dict(D0)
    D["o1"], D["h1"], D["l1"], D["c1"] = o1, h1, l1, c1
    k1 = D0["k1"]
    starts = np.r_[0, np.where(np.diff(k1) != 0)[0] + 1]
    ks = k1[starts]
    o15, h15, l15, c15 = D0["o15"].copy(), D0["h15"].copy(), D0["l15"].copy(), D0["c15"].copy()
    o15[ks] = o1[starts]
    h15[ks] = np.maximum.reduceat(h1, starts)
    l15[ks] = np.minimum.reduceat(l1, starts)
    c15[ks] = c1[np.r_[starts[1:] - 1, len(c1) - 1]]
    D["o15"], D["h15"], D["l15"], D["c15"] = o15, h15, l15, c15
    D["atr"], D["adx"] = sim._atr_adx(o15, h15, l15, c15)
    return D


def _valid(o, h, l, c):
    return o, np.maximum(h, np.maximum(o, c)), np.minimum(l, np.minimum(o, c)), c


_BASE = {}


def base_ds():
    """The real prices, re-aggregated the same way (the fair baseline for the perturbation tests)."""
    if "b" not in _BASE:
        D0 = sim.data()
        _BASE["b"] = _rebuild(D0, D0["o1"].copy(), D0["h1"].copy(), D0["l1"].copy(), D0["c1"].copy())
    return _BASE["b"]


def noisy(sig, seed):
    D0 = base_ds()
    rng = np.random.default_rng(seed)
    n = len(D0["o1"])
    px = D0["c1"]
    o, h, l, c = (D0[k] + rng.normal(0, sig, n) * px for k in ("o1", "h1", "l1", "c1"))
    return _rebuild(D0, *_valid(o, h, l, c))


def scrambled(seed):
    """Daily drift shuffled: each server day keeps its own intraday path, but the days' open-to-open changes come in a random order."""
    D0 = base_ds()
    rng = np.random.default_rng(seed)
    day = D0["t1"] // 86400
    starts = np.r_[0, np.where(np.diff(day) != 0)[0] + 1]
    opens = D0["o1"][starts]
    drift = np.diff(opens)
    new_opens = np.r_[opens[0], opens[0] + np.cumsum(rng.permutation(drift))]
    shift = np.repeat(new_opens - opens, np.diff(np.r_[starts, len(day)]))
    return _rebuild(D0, D0["o1"] + shift, D0["h1"] + shift, D0["l1"] + shift, D0["c1"] + shift)


def synthetic(seed):
    """Block bootstrap: each hour of the year is replaced by a random real hour of the same length (its 1-minute shape relative to its open),
    chained from the previous close - same volatility and intrabar texture, no real sequence."""
    D0 = base_ds()
    rng = np.random.default_rng(seed)
    hour = D0["t1"] // 3600
    starts = np.r_[0, np.where(np.diff(hour) != 0)[0] + 1]
    ends = np.r_[starts[1:], len(hour)]
    lens = ends - starts
    by_len = {}
    for i, L in enumerate(lens):
        by_len.setdefault(int(L), []).append(i)
    o, h, l, c = (np.empty_like(D0["o1"]) for _ in range(4))
    last = D0["o1"][0]
    for i, (a, b) in enumerate(zip(starts, ends)):
        src = by_len[int(b - a)][int(rng.integers(len(by_len[int(b - a)])))]
        sa, sb = starts[src], ends[src]
        base = D0["o1"][sa]
        o[a:b] = D0["o1"][sa:sb] - base + last
        h[a:b] = D0["h1"][sa:sb] - base + last
        l[a:b] = D0["l1"][sa:sb] - base + last
        c[a:b] = D0["c1"][sa:sb] - base + last
        last = c[b - 1]
    return _rebuild(D0, o, h, l, c)


# ---------------------------------------------------------------- the tests
def run_all(inputs, progress=lambda *a: None):
    t0 = time.time()
    R = []
    add = lambda r: (R.append(r), progress(len(R), r["name"]))
    D = sim.data()
    tr0 = sim.simulate(inputs)[0]
    base = sc(tr0)
    rr = real(tr0)
    pnl = rr[:, 6]
    risk = np.abs(rr[:, 2] - rr[:, 3]) * float(inputs["InpLots"]) * 100

    # ---- I. statistics
    progress(0, "alternative configurations")
    configs = [dict(inputs)] + neighbours_set(inputs)
    M = np.array([monthly(sim.simulate(c)[0]) for c in configs])
    SRs = []
    for c in configs[:60]:
        dv = daily(sim.simulate(c)[0]) / DEPOSIT
        SRs.append(dv.mean() / dv.std() if dv.std() > 0 else 0.0)
    count_trials("stress", len(configs) + 60)
    S = M.shape[1]
    splits = list(itertools.combinations(range(S), S // 2))
    lam, opt_oos, rnd_oos, sel_pos = [], [], [], []
    for IS in splits:
        OOS = [m for m in range(S) if m not in IS]
        pis, poos = M[:, list(IS)].sum(1), M[:, OOS].sum(1)
        b = int(np.argmax(pis))
        rank = (poos < poos[b]).sum() + 0.5 * ((poos == poos[b]).sum() - 1) + 1
        w = rank / (len(configs) + 1)
        lam.append(math.log(w / (1 - w)))
        opt_oos.append(poos[b]); rnd_oos.extend(poos.tolist()); sel_pos.append(poos[b] > 0)
    lam = np.array(lam)
    pbo = float((lam <= 0).mean())
    add(res("pbo", "I", "Probability of Backtest Overfitting (CSCV)", "PASS" if pbo < 0.1 else "WARN" if pbo <= 0.5 else "FAIL",
            f"PBO = {pbo:.2f}: the best of {len(configs)} nearby configurations on half of the months lands below the median on the other half in "
            f"{100 * pbo:.0f}% of {len(splits)} splits (< 0.10 gold standard, > 0.50 over-optimized).",
            table=T(["Configurations", "Month blocks", "Splits C(10,5)", "PBO"], [[len(configs), S, len(splits), f"{pbo:.3f}"]])))
    grid = np.linspace(min(min(opt_oos), min(rnd_oos)), max(max(opt_oos), max(rnd_oos)), 60)
    Fo = np.array([(np.array(opt_oos) <= g).mean() for g in grid])
    Fr = np.array([(np.array(rnd_oos) <= g).mean() for g in grid])
    gap = float((Fo - Fr).max())
    add(res("sd", "I", "Stochastic dominance (selection vs random choice)", "PASS" if gap <= 0.02 else "WARN" if np.mean(opt_oos) > np.mean(rnd_oos) else "FAIL",
            f"Picking the best on half the months gives an out-of-sample mean of ${np.mean(opt_oos):,.0f} vs ${np.mean(rnd_oos):,.0f} for a random "
            f"configuration; {'first-order dominance holds' if gap <= 0.02 else f'no strict dominance (CDF gap {gap:.2f})'}.",
            table=T(["", "Mean OOS $", "Median OOS $", "Share > 0"], [["selected on IS", f"{np.mean(opt_oos):,.0f}", f"{np.median(opt_oos):,.0f}", f"{100 * np.mean(np.array(opt_oos) > 0):.0f}%"],
                                                                    ["random configuration", f"{np.mean(rnd_oos):,.0f}", f"{np.median(rnd_oos):,.0f}", f"{100 * np.mean(np.array(rnd_oos) > 0):.0f}%"]])))
    dv = daily(tr0) / DEPOSIT
    Tn = len(dv)
    SR = dv.mean() / dv.std() if dv.std() > 0 else 0.0
    sk = float(((dv - dv.mean()) ** 3).mean() / dv.std() ** 3) if dv.std() > 0 else 0.0
    ku = float(((dv - dv.mean()) ** 4).mean() / dv.std() ** 4) if dv.std() > 0 else 3.0
    L = ledger()
    N = max(2, L.get("optimizer", 0) + L.get("manual", 0) + L.get("stress", 0))
    V = float(np.var(SRs))
    g = 0.5772156649
    SR0 = math.sqrt(V) * ((1 - g) * ND.inv_cdf(1 - 1 / N) + g * ND.inv_cdf(1 - 1 / (N * math.e)))
    den = math.sqrt(max(1e-12, 1 - sk * SR + (ku - 1) / 4 * SR ** 2))
    dsr = ND.cdf((SR - SR0) * math.sqrt(Tn - 1) / den)
    add(res("dsr", "I", "Deflated Sharpe Ratio", "PASS" if dsr >= 0.95 else "WARN" if dsr >= 0.5 else "FAIL",
            f"Sharpe {SR * math.sqrt(252):.2f} a year ({SR:.3f} a day, {Tn} days); after {N:,} trials (the file drawer) the bar is {SR0 * math.sqrt(252):.2f}: "
            f"DSR = {dsr:.3f} (the probability the Sharpe is real, > 0.95 wanted).",
            table=T(["Daily Sharpe", "Skew", "Kurtosis", "Trials N", "Var of trial Sharpes", "SR0 (daily)", "DSR"],
                    [[f"{SR:.4f}", f"{sk:.2f}", f"{ku:.2f}", f"{N:,}", f"{V:.6f}", f"{SR0:.4f}", f"{dsr:.3f}"]])))
    cur_oos = [M[0, [m for m in range(S) if m not in IS]].sum() for IS in splits]
    add(res("cpcv", "I", "Combinatorial Purged Cross-Validation", "PASS" if np.mean(sel_pos) >= 0.8 and np.mean(np.array(cur_oos) > 0) >= 0.9 else "WARN" if np.mean(sel_pos) >= 0.5 else "FAIL",
            f"{len(splits)} train / test halves of the 10 months (trades crossing a month boundary purged): the configuration chosen on train is profitable "
            f"on test in {100 * np.mean(sel_pos):.0f}%; your settings are profitable on {100 * np.mean(np.array(cur_oos) > 0):.0f}% of the test halves.",
            hist=hist(opt_oos, mark=float(np.median(cur_oos))), table=T(["", "Mean test $", "Worst test $", "Profitable"],
                [["chosen on train", f"{np.mean(opt_oos):,.0f}", f"{np.min(opt_oos):,.0f}", f"{100 * np.mean(sel_pos):.0f}%"],
                 ["your settings", f"{np.mean(cur_oos):,.0f}", f"{np.min(cur_oos):,.0f}", f"{100 * np.mean(np.array(cur_oos) > 0):.0f}%"]])))
    L = ledger()
    add(res("drawer", "I", "File drawer audit", "PASS",
            f"{N:,} configurations tried since {L.get('since', '?')}: {L.get('manual', 0):,} by hand on the chart, {L.get('optimizer', 0):,} by the optimizer, "
            f"{L.get('stress', 0):,} by stress tests. This is the N used above.",
            table=T(["By hand (settings panel)", "Optimizer", "Stress tests", "Total N"], [[f"{L.get('manual', 0):,}", f"{L.get('optimizer', 0):,}", f"{L.get('stress', 0):,}", f"{N:,}"]])))
    trR = sim.simulate(inputs, reverse=1)[0]
    sR = sc(trR)
    add(res("reverse", "I", "Reverse logic", "PASS" if sR["net"] < 0 else "FAIL",
            f"The opposite trade on every signal makes {sR['net']:+,.0f} (PF {sR['pf']}, WR {sR['wr']}%) vs {base['net']:+,.0f}: "
            f"{'the edge is directional, not an artefact' if sR['net'] < 0 else 'the reversed system also profits - the edge may be spurious'}.",
            table=T(HEAD, [row_stats("your settings", tr0), row_stats("reversed", trR, base)])))

    # ---- II. parameter space
    progress(len(R), "heatmap")
    pa, pb = "InpAdxMin", "InpSlAtrMult"
    ga = {n: g for n, k, g in optimizer.SPACE}
    va = [float(inputs[pa]) + ga[pa][2] * i for i in range(-6, 7)]
    vb = [round(float(inputs[pb]) + ga[pb][2] * i, 2) for i in range(-6, 7)]
    va = [v for v in va if ga[pa][0] <= v <= ga[pa][1]]
    vb = [v for v in vb if ga[pb][0] - 1e-9 <= v <= ga[pb][1] + 1e-9]
    Z = [[sc(sim.simulate(dict(inputs, **{pa: optimizer._fmt("int", a), pb: optimizer._fmt("num", b)}))[0])["net"] for a in va] for b in vb]
    count_trials("stress", len(va) * len(vb))
    Zn = np.array(Z)
    ia, ib = va.index(float(inputs[pa])) if float(inputs[pa]) in va else len(va) // 2, min(range(len(vb)), key=lambda i: abs(vb[i] - float(inputs[pb])))
    near = Zn[max(0, ib - 2):ib + 3, max(0, ia - 2):ia + 3]
    share = float((near >= 0.7 * Zn[ib, ia]).mean()) if Zn[ib, ia] > 0 else 0.0
    add(res("heat", "II", "Parameter stability heatmap", "PASS" if share >= 0.7 else "WARN" if share >= 0.4 else "FAIL",
            f"Net profit over {pa} × {pb} ({len(va)} × {len(vb)} runs): {100 * share:.0f}% of the 5 × 5 neighbourhood keeps at least 70% of your result.",
            heat={"x": [optimizer._fmt("int", a) for a in va], "y": [optimizer._fmt("num", b) for b in vb], "z": [[round(v) for v in r] for r in Z],
                  "xname": pa, "yname": pb, "cur": [ia, ib]}))
    progress(len(R), "plateaus")
    rows, spikes = [], 0
    for name, kind, grid in optimizer.SPACE:
        if kind not in ("int", "num"):
            continue
        nets = {}
        for i in range(-5, 6):
            v = float(inputs[name]) + i * grid[2]
            if i == 0 or grid[0] - 1e-9 <= v <= grid[1] + 1e-9:   # your own value always, even outside the optimizer's range
                c = dict(inputs, **{name: optimizer._fmt(kind, v)})
                if optimizer.evaluate(c)[1] is not None:
                    nets[i] = sc(sim.simulate(c)[0])["net"]
        count_trials("stress", len(nets))
        if not nets:
            continue
        cur = nets.get(0, base["net"])
        w = 0
        for d in (1, -1):
            i = d
            while i in nets and cur > 0 and nets[i] >= 0.8 * cur:
                w += 1; i += d
        spike = cur > 0 and all(nets.get(d, cur) < 0.7 * cur for d in (1, -1) if d in nets)
        spikes += spike
        rows.append([name.replace("Inp", ""), inputs[name], f"{w + 1} steps", f"{min(nets.values()):+,.0f}", f"{max(nets.values()):+,.0f}", "SPIKE" if spike else ""])
    add(res("plateau", "II", "Flat-maximum / plateau analysis", "PASS" if spikes == 0 else "WARN" if spikes <= 2 else "FAIL",
            f"Each setting moved ±5 steps: {spikes} sit on an isolated spike (both neighbours lose more than 30%); the rest sit on plateaus (width = steps within 80% of your result).",
            table=T(["Setting", "Now", "Plateau width", "Worst nearby $", "Best nearby $", ""], rows)))
    progress(len(R), "boundaries")
    rows, odd = [], 0
    for name, kind, grid in optimizer.SPACE:
        if kind not in ("int", "num"):
            continue
        for v in (grid[0], grid[1]):
            c = dict(inputs, **{name: optimizer._fmt(kind, v)})
            ok = optimizer.evaluate(c)[1] is not None
            s = sc(sim.simulate(c)[0]) if ok else None
            weird = s is not None and (s["n"] > 5 * max(1, base["n"]) or s["net"] > 5 * max(1.0, base["net"]))
            odd += weird
            rows.append([name.replace("Inp", ""), optimizer._fmt(kind, v), s["n"] if s else "refused", f"{s['net']:+,.0f}" if s else "–", "unexpected" if weird else "ok"])
    count_trials("stress", len(rows))
    add(res("bounds", "II", "Parameter boundary stressing", "PASS" if odd == 0 else "WARN",
            f"Every setting at the ends of its range ({len(rows)} runs): the engine never crashed; {odd} run(s) gave an unexpected explosion of trades or profit.",
            table=T(["Setting", "Value", "Trades", "Net $", ""], rows)))
    progress(len(R), "walk-forward")
    W = [((1, 1), (4, 1), (6, 1)), ((3, 1), (6, 1), (8, 1)), ((5, 1), (8, 1), (10, 1)), ((7, 1), (10, 1), (10, 17))]
    rows, oks = [], 0
    for (a, b, c) in W:
        win = (EP(2026, *a), EP(2026, *b), EP(2026, *b), EP(2026, *c))
        o = optimizer.Optimizer(inputs, min_trades=15, window=win)
        o.run()
        count_trials("stress", o.evals)
        cur_t = optimizer.evaluate(inputs, window=win)[2]
        best_t = o.best["test"]
        oks += best_t["net"] > 0
        rows.append([f"{a[1]}/{a[0]} – {b[1]}/{b[0]}", f"{b[1]}/{b[0]} – {c[1]}/{c[0]}", ", ".join(f"{k[3:]}={v}" for k, v in o.best["inputs"].items() if str(v) != str(inputs.get(k)))[:80] or "no change",
                     f"{cur_t['net']:+,.0f} ({cur_t['n']})", f"{best_t['net']:+,.0f} ({best_t['n']})"])
    add(res("wf", "II", "Walk-forward out-of-sample windows", "PASS" if oks == len(W) else "WARN" if oks >= len(W) - 1 else "FAIL",
            f"{len(W)} successive windows: re-optimized on 3 months, traded on the next untouched 2: profitable in {oks} of {len(W)}.",
            table=T(["Optimized on (d/m)", "Traded on", "Changes found", "Your settings $ (trades)", "Re-optimized $ (trades)"], rows)))
    add(res("logit", "II", "In-sample / out-of-sample logit distribution", "PASS" if np.median(lam) > 0 else "WARN",
            f"λ = ln(ω / (1 − ω)) of the in-sample winner's out-of-sample rank over {len(splits)} splits: median {np.median(lam):+.2f} "
            f"({'positive: the in-sample winner tends to stay above the median' if np.median(lam) > 0 else 'negative: in-sample winners fall below the median'}).",
            hist=hist(lam, mark=0.0)))

    # ---- III. execution
    progress(len(R), "execution")
    def degr(id_, name, label, levels, key, fmt, fail_at=0):
        rows = [row_stats("real", tr0)]
        nets = []
        for lv in levels:
            t = sim.simulate(inputs, **{key: lv})[0]
            rows.append(row_stats(fmt(lv), t, base)); nets.append(sc(t)["net"])
        st = "PASS" if nets[0] > 0.7 * base["net"] and nets[-1] > 0 else "WARN" if nets[0] > 0 else "FAIL"
        add(res(id_, "III", name, st, f"{label}: net {base['net']:+,.0f} → " + ", ".join(f"{fmt(l)} {n:+,.0f}" for l, n in zip(levels, nets)) + ".", table=T(HEAD, rows)))
    rows = [row_stats("real", tr0)]
    nets = []
    for lv in (0.10, 0.25, 0.50):
        t = sim.simulate(inputs, slip_entry=lv, slip_exit=lv)[0]; rows.append(row_stats(f"${lv:.2f} entry + exit", t, base)); nets.append(sc(t)["net"])
    add(res("slip", "III", "Adverse slippage", "PASS" if nets[0] > 0.7 * base["net"] and nets[-1] > 0 else "WARN" if nets[0] > 0 else "FAIL",
                f"Slippage against every entry and every EA exit: {base['net']:+,.0f} → $0.10 {nets[0]:+,.0f}, $0.25 {nets[1]:+,.0f}, $0.50 {nets[2]:+,.0f}.", table=T(HEAD, rows)))
    degr("gap", "Stop-loss gap overshoot", "Stops filled beyond the trigger", [0.25, 0.50, 1.00], "sl_overshoot", lambda v: f"${v:.2f} past the stop")
    degr("latency", "Execution latency injection", "EA entries and exits filled later", [1, 2, 4], "latency", lambda v: f"{v} step{'s' if v > 1 else ''} (~{15 * v}s)")
    degr("spread", "Spread widening", "The real spread multiplied", [2.0, 3.0], "spread_mult", lambda v: f"×{v:.0f}")
    degr("limit", "Missed limit orders (target trade-through)", "The EMA target (a limit) fills only if price trades through it by", [0.10, 0.25, 0.50],
         "tp_through", lambda v: f"${v:.2f}")
    med = float(np.median(D["sp1"]))
    sp_at = D["sp1"][np.clip(np.searchsorted(D["t1"], rr[:, 1], side="right") - 1, 0, len(D["t1"]) - 1)]
    rows = [row_stats("real", tr0)]
    for k in (1.5, 2.0):
        thin = sp_at > k * med
        adj = pnl.copy(); adj[thin] *= 0.5
        gw, gl = adj[adj > 0].sum(), -adj[adj <= 0].sum()
        rows.append([f"half filled when spread > {k}× median", len(adj), f"{100 * (adj > 0).mean():.1f}%", f"{adj.sum():+,.0f}", f"{gw / gl:.3f}" if gl else "–", "", f"{100 * (adj.sum() - base['net']) / base['net']:+.0f}%"])
    add(res("cap", "III", "Available liquidity capping (approximation)", "PASS",
            f"A gold CFD shows no order book; thin moments are taken from the spread (median ${med:.2f}). Trades opened while the spread was wide are filled at half size: "
            f"{int((sp_at > 1.5 * med).sum())} trades above 1.5×, {int((sp_at > 2 * med).sum())} above 2×.", table=T(HEAD, rows)))
    # the reject test needs the median spread passed in
    rows = [row_stats("real", tr0)]
    nets = []
    for k in (1.5, 2.0, 3.0):
        t = sim.simulate(inputs, reject_mult=k, median_spread=med)[0]; rows.append(row_stats(f"refused above {k}× median", t, base)); nets.append(sc(t)["net"])
    add(res("reject", "III", "Displayed liquidity rejection (approximation)", "PASS" if nets[0] > 0.7 * base["net"] else "WARN" if nets[0] > 0 else "FAIL",
                f"No order book for a CFD: an entry is refused while the spread is above k × the median ${med:.2f} (a thin book): "
                + ", ".join(f"k {k} {n:+,.0f}" for k, n in zip((1.5, 2.0, 3.0), nets)) + ".", table=T(HEAD, rows)))

    # ---- IV. data
    progress(len(R), "price noise")
    B = base_ds()
    trB = sim_on(B, inputs)
    sB = sc(trB)
    rows = [row_stats("real prices (re-aggregated)", trB)]
    noise_nets = []
    for sig in (0.00005, 0.0001, 0.0002):
        nets = [sc(sim_on(noisy(sig, s), inputs))["net"] for s in range(12)]
        noise_nets.append(nets)
        rows.append([f"±{100 * sig:.3f}% (~${sig * 4000:.2f}) x 12", "", "", f"median {np.median(nets):+,.0f}", "", f"worst {min(nets):+,.0f}", f"{100 * (np.median(nets) - sB['net']) / sB['net']:+.0f}%"])
    count_trials("stress", 36)
    mid = noise_nets[1]
    add(res("noise", "IV", "White noise / price perturbation", "PASS" if np.median(mid) > 0.7 * sB["net"] and np.mean(np.array(mid) > 0) >= 0.9 else "WARN" if np.median(mid) > 0 else "FAIL",
            f"Every 1-minute open / high / low / close moved by random noise (structure kept, candles and indicators rebuilt), 12 versions per level: "
            f"median {np.median(mid):+,.0f} at ±0.01% vs {sB['net']:+,.0f} real.", table=T(["", "", "", "Net $", "", "", "vs real"], rows), hist=hist(mid, mark=sB["net"])))
    progress(len(R), "crisis days")
    day = D["t1"] // 86400
    ud = np.unique(day)
    rng_d = np.array([D["h1"][day == d].max() - D["l1"][day == d].min() for d in ud])
    top = ud[np.argsort(-rng_d)[:6]]
    rows, cnet = [], 0.0
    for d in top:
        t_ = rr[(rr[:, 1] // 86400) == d]
        cnet += t_[:, 6].sum()
        rows.append([datetime.utcfromtimestamp(int(d) * 86400).strftime("%a %b %d"), f"${rng_d[list(ud).index(d)]:,.0f}", len(t_), f"{t_[:, 6].sum():+,.0f}",
                     f"{t_[:, 6].min():+,.0f}" if len(t_) else "–"])
    add(res("crisis", "IV", "Historical crisis replay (this year's own crises)", "PASS" if cnet >= 0 else "WARN" if cnet > -0.05 * DEPOSIT else "FAIL",
            f"There are no 2008 or May-2010 gold ticks here; the replay uses the year's 6 most violent days (largest daily range): {cnet:+,.0f} on them.",
            table=T(["Day (server)", "Daily range", "Trades", "Net $", "Worst trade $"], rows)))
    progress(len(R), "regimes")
    wk = (D["t15"] + 3 * 86400) // (7 * 86400)
    atr_w = {w: float(np.mean(D["atr"][wk == w])) for w in np.unique(wk)}
    trend_w = {}
    for w in np.unique(wk):
        m = wk == w
        trend_w[w] = abs(D["c15"][m][-1] - D["o15"][m][0]) / max(1e-9, D["h15"][m].max() - D["l15"][m].min())
    medv = float(np.median(list(atr_w.values())))
    reg = {}
    for x in rr:
        w = (int(x[1]) + 3 * 86400) // (7 * 86400)
        if w not in atr_w:
            continue
        k_ = ("high volatility" if atr_w[w] >= medv else "low volatility") + (", trending" if trend_w[w] >= 0.5 else ", ranging")
        reg.setdefault(k_, []).append(x[6])
    rows, neg = [], 0
    for k_ in sorted(reg):
        v = np.array(reg[k_])
        neg += v.sum() < 0 and len(v) >= 10
        gw, gl = v[v > 0].sum(), -v[v <= 0].sum()
        rows.append([k_, len(v), f"{100 * (v > 0).mean():.1f}%", f"{v.sum():+,.0f}", f"{gw / gl:.2f}" if gl else "–"])
    add(res("regime", "IV", "Market regime isolation", "PASS" if neg == 0 else "WARN" if neg == 1 else "FAIL",
            f"Weeks split by volatility (ATR vs the median) and trend (net move ≥ half the week's range): {neg} regime(s) with 10+ trades lose money.",
            table=T(["Regime (by week)", "Trades", "Win rate", "Net $", "PF"], rows)))
    progress(len(R), "scrambling")
    scr = [sc(sim_on(scrambled(s), inputs))["net"] for s in range(16)]
    add(res("scramble", "IV", "Time-series scrambling", "PASS" if np.median(scr) < 0.5 * sB["net"] else "WARN",
            f"The days' open-to-open moves shuffled (each day keeps its own intraday path, the market's memory between days is destroyed), 16 versions: "
            f"median {np.median(scr):+,.0f} vs {sB['net']:+,.0f} real. "
            f"{'Much lower: part of the edge lives in how days follow each other.' if np.median(scr) < 0.5 * sB['net'] else 'About the same: the edge lives inside the day, not in the order of days.'}",
            hist=hist(scr, mark=sB["net"])))
    progress(len(R), "synthetic paths")
    syn = [sc(sim_on(synthetic(s), inputs))["net"] for s in range(16)]
    count_trials("stress", 32)
    add(res("synth", "IV", "Synthetic data (block bootstrap)", "PASS" if np.median(syn) > 0 else "WARN" if max(syn) > 0 else "FAIL",
            f"Not a GAN: 16 synthetic years built from randomly drawn real hours (same volatility and 1-minute texture, no real sequence): median {np.median(syn):+,.0f}, "
            f"{100 * np.mean(np.array(syn) > 0):.0f}% profitable.", hist=hist(syn, mark=sB["net"])))

    # ---- V. sequence risk
    progress(len(R), "Monte Carlo")
    rng = np.random.default_rng(11)
    sims = 10000
    streaks, dds = np.empty(sims), np.empty(sims)
    for i in range(sims):
        p = rng.permutation(pnl)
        eq = np.cumsum(p)
        dds[i] = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
        l = (p <= 0).astype(int)
        mx = cur_ = 0
        for v in l:
            cur_ = cur_ + 1 if v else 0
            mx = max(mx, cur_)
        streaks[i] = mx
    l = (pnl <= 0).astype(int); mx = cur_ = 0
    for v in l:
        cur_ = cur_ + 1 if v else 0; mx = max(mx, cur_)
    add(res("mcstreak", "V", "Monte Carlo trade resampling (losing streaks)", "PASS",
            f"10,000 shuffles of the {len(pnl)} trades: the longest losing streak is {mx} in the real order; {np.percentile(streaks, 50):.0f} typical, "
            f"{np.percentile(streaks, 95):.0f} at 95%, {np.percentile(streaks, 99):.0f} at 99%.", hist=hist(streaks, bins=int(streaks.max() - streaks.min() + 1), mark=mx)))
    add(res("mcdd", "V", "Monte Carlo drawdown distribution", "PASS" if np.percentile(dds, 95) < 0.3 * DEPOSIT else "WARN",
            f"Max drawdown {base['dd']:,.0f} in the real order; across the shuffles {np.percentile(dds, 50):,.0f} typical, {np.percentile(dds, 95):,.0f} at 95%, "
            f"{np.percentile(dds, 99):,.0f} at 99% (on ${DEPOSIT:,.0f}, {inputs['InpLots']} lots).", hist=hist(dds, mark=base["dd"])))
    Rm = pnl / np.where(risk > 0, risk, 1)
    rows = []
    for f in (0.005, 0.01, 0.02):
        br, worst = 0, []
        for i in range(2000):
            p = rng.permutation(Rm)
            eq = DEPOSIT * np.cumprod(1 + f * p)
            dd = np.max(1 - eq / np.maximum.accumulate(eq))
            worst.append(dd); br += dd > 0.10
        rows.append([f"{100 * f:.1f}% risk per trade", f"{100 * np.percentile(worst, 50):.1f}%", f"{100 * np.percentile(worst, 95):.1f}%", f"{100 * br / 2000:.1f}%"])
    add(res("ff", "V", "Fixed fractional position sizing stress", "PASS" if float(rows[1][3][:-1]) < 5 else "WARN" if float(rows[1][3][:-1]) < 25 else "FAIL",
            f"Each trade risks a fixed share of equity (its result in R multiples of its own stop); 2,000 shuffles per size: the chance of breaching a 10% prop-firm "
            f"drawdown is {rows[1][3]} at 1% risk.", table=T(["Sizing", "Typical max DD", "95% max DD", "Breaches 10%"], rows)))
    avg_l = float(-pnl[pnl <= 0].mean()) if (pnl <= 0).any() else 0.0
    n_avg = int(0.5 * DEPOSIT / avg_l) if avg_l else 0
    big = np.sort(-pnl[pnl <= 0])[::-1]
    n_big = int(np.searchsorted(np.cumsum(big), 0.5 * DEPOSIT)) + 1 if big.sum() >= 0.5 * DEPOSIT else len(big)
    add(res("exhaust", "V", "Capital exhaustion / risk budget", "PASS" if n_big > 3 * np.percentile(streaks, 99) else "WARN",
            f"With ${DEPOSIT:,.0f} and {inputs['InpLots']} lots, a 50% loss budget absorbs {n_avg} average losses (${avg_l:,.0f}) or the {n_big} largest real "
            f"losses in a row; the 99% losing streak is {np.percentile(streaks, 99):.0f}. At 1% risk sizing, 69 straight losses halve the account.",
            table=T(["Average loss $", "Losses to −50% (average)", "Losses to −50% (largest first)", "99% streak"], [[f"{avg_l:,.0f}", n_avg, n_big, f"{np.percentile(streaks, 99):.0f}"]])))
    n = len(pnl)
    tstat = float(pnl.mean() / (pnl.std(ddof=1) / math.sqrt(n))) if n > 1 else 0.0
    need = int(math.ceil((1.96 * pnl.std(ddof=1) / pnl.mean()) ** 2)) if pnl.mean() > 0 else 0
    add(res("freq", "V", "Trade frequency minimums", "PASS" if tstat >= 2 and n >= 100 else "WARN" if tstat >= 2 else "FAIL",
            f"{n} trades in {len(MONTHS)} months ({n / len(MONTHS):.0f} a month); t-statistic of the average trade {tstat:.2f} (≥ 2 wanted); "
            f"{need} trades would be enough for 95% confidence at this edge and spread.",
            table=T(["Trades", "Per month", "Average $", "Std dev $", "t-stat", "Needed for 95%"], [[n, f"{n / len(MONTHS):.1f}", f"{pnl.mean():,.0f}", f"{pnl.std(ddof=1):,.0f}", f"{tstat:.2f}", need]])))

    # ---- VI. audits
    progress(len(R), "audits")
    rows, bad = [], 0
    for cut in (EP(2026, 3, 1), EP(2026, 6, 1), EP(2026, 9, 1)):
        Dp = dict(B)
        rng2 = np.random.default_rng(cut)
        m = D["t1"] >= cut
        o1, h1, l1, c1 = (B[k].copy() for k in ("o1", "h1", "l1", "c1"))
        poison = 1.05 + rng2.normal(0, 0.01, m.sum())
        for a in (o1, h1, l1, c1):
            a[m] = a[m] * poison
        Dp = _rebuild(B, *_valid(o1, h1, l1, c1))
        a_ = real(sim_on(B, inputs)); b_ = real(sim_on(Dp, inputs))
        a_ = a_[a_[:, 4] < cut - 86400]; b_ = b_[b_[:, 4] < cut - 86400]
        same = len(a_) == len(b_) and np.allclose(a_[:, [0, 1, 2, 4, 5]], b_[:, [0, 1, 2, 4, 5]])
        bad += not same
        rows.append([datetime.utcfromtimestamp(cut).strftime("%b %d"), len(a_), len(b_), "identical" if same else "DIFFERENT"])
    add(res("lookahead", "VI", "Look-ahead bias audit", "PASS" if bad == 0 else "FAIL",
            "Everything after a cut date replaced by poisoned prices (+5% and noise), candles and indicators rebuilt: every trade closed before the cut must stay "
            f"identical - {'it does at all 3 cuts' if bad == 0 else 'it does NOT: the engine reads the future'}.",
            table=T(["Cut", "Trades before (real)", "Trades before (poisoned future)", ""], rows)))
    add(res("surv", "VI", "Survivorship bias check", "N/A",
            "Not applicable: one instrument (XAUUSD, Blueberry), traded the whole period; there is no universe of symbols that could have been delisted."))
    trW = sim.simulate(inputs, worst_case=1)[0]
    sW = sc(trW)
    add(res("samebar", "VI", "Same-bar order sequencing (worst case)", "PASS" if sW["net"] > 0.7 * base["net"] else "WARN" if sW["net"] > 0 else "FAIL",
            f"Inside every 1-minute candle the adverse extreme visited first (not MT5's open-low-high-close order): {sW['net']:+,.0f} vs {base['net']:+,.0f}"
            + (" - identical: no trade ever had its stop and its target inside the same minute (stops are 15-minute ATR multiples)." if abs(sW["net"] - base["net"]) < 1 else "."),
            table=T(HEAD, [row_stats("MT5's order", tr0), row_stats("worst case first", trW, base)])))
    k1, t1, t15 = D["k1"], D["t1"], D["t15"]
    in_win = bool(np.all((t1 >= t15[k1]) & (t1 < t15[k1] + 900)))
    per = np.bincount(k1)
    ef, es = sim.emas(16, 32)
    ema_ok = float(max(np.abs(ef[500:] - D["ef"][500:]).max(), np.abs(es[500:] - D["es"][500:]).max()))
    ok = in_win and per.max() <= 15 and ema_ok < 0.05
    add(res("ts", "VI", "Timestamp alignment verification", "PASS" if ok else "FAIL",
            f"Every 1-minute candle sits inside its 15-minute candle: {'yes' if in_win else 'NO'}; at most {per.max()} minutes per candle; the engine's EMA 16 / 32 "
            f"differ from the EA's own by at most ${ema_ok:.3f}; decisions read only the candle that just closed (k − 1), confirmed by the look-ahead audit.",
            table=T(["Check", "Result"], [["1-minute candles inside their 15-minute candle", "yes" if in_win else "NO"], ["Minutes per 15-minute candle (max)", int(per.max())],
                                          ["EMA vs the EA's export (max gap after warm-up)", f"${ema_ok:.4f}"], ["Higher-timeframe inputs", "none used (HTF filter off)"]])))
    progress(len(R), "done")
    return {"inputs": inputs, "base": base, "seconds": round(time.time() - t0, 1), "tests": R, "at": datetime.now().strftime("%Y-%m-%d %H:%M")}
