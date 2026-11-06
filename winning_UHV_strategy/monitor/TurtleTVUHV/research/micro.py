"""micro.py - three microstructure gates for 2026-10-25 05-58-25 (Zee 2026-10-28: "implement this fully and test it in the MT5 strategy tester").
Every feature is CAUSAL (only ticks / candles before the entry) and defined exactly as the EA computes it (Saad_strategy_15min v1.38):
  DTW   the mid-price path of the 15 minutes before the entry, 32 time steps, turned the trade's way, scaled to its range; toxic score =
        share of losers among its 20 nearest training paths (DTW, Sakoe-Chiba band 4)
  VPIN  tick test on the mid of the last 25,000 ticks, buckets of 500 ticks: VPIN = mean |up-down|/500 over 50 buckets;
        flow = (up-down)/(up+down) of the last 10 buckets, turned the trade's way
  HMM   Gaussian HMM (diagonal) on M15 candles: log return, log std of tick-to-tick mid changes, (fast EMA - slow EMA)/ATR;
        forward filter only (no smoothing); toxic state = the state where training trades lost most often
Train 2023-2025 (entries before 2026-01-01), test 2026 (the MT5 year). Writes the EA's model files to MT5's Common\\Files.
Tester-family screen = hypothesis; the MT5 run decides."""
import json, os, sys
os.environ.setdefault("NUMBA_CPU_NAME", "generic")          # as sim_full: the ARM build of LLVM crashes on the native CPU model
import numpy as np
from numba import njit
sys.path.insert(0, os.path.dirname(__file__))
from _load import *

T26 = 1767225600                                        # 2026-01-01 00:00 (data clock)
COMMON = r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files"
NP, BAND, K = 32, 4, 20
VB, VN, VF = 500, 50, 10
HERE = os.path.dirname(__file__)

T = np.memmap(os.path.join(HERE, "..", "simdata", "m15_tick_raw_t.bin"), dtype=np.float64, mode="r")
B = np.memmap(os.path.join(HERE, "..", "simdata", "m15_tick_raw_bid.bin"), dtype=np.float64, mode="r")
A = np.memmap(os.path.join(HERE, "..", "simdata", "m15_tick_raw_ask.bin"), dtype=np.float64, mode="r")


# ------------------------------------------------------------------ DTW
def path(te, sd):
    a, b = np.searchsorted(T, [te - 900, te], side="right")
    if b - a < 2:
        return None
    t = np.asarray(T[a:b]); m = (np.asarray(B[a:b]) + np.asarray(A[a:b])) / 2
    g = te - 900 + 900 * (np.arange(NP) + 1) / NP
    ix = np.clip(np.searchsorted(t, g, side="right") - 1, 0, len(t) - 1)
    x = sd * (m[ix] - m[ix[0]])
    r = x.max() - x.min()
    return x / r if r > 0 else x * 0


@njit(cache=True)
def dtw(a, b, w):
    n = a.shape[0]; D = np.full((n + 1, n + 1), 1e18); D[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(max(1, i - w), min(n, i + w) + 1):
            c = abs(a[i - 1] - b[j - 1])
            D[i, j] = c + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    return D[n, n]


@njit(cache=True)
def knn_score(q, P, L, k, w, skip):
    d = np.empty(P.shape[0])
    for i in range(P.shape[0]):
        d[i] = 1e18 if i == skip else dtw(q, P[i], w)
    o = np.argsort(d)[:k]
    return L[o].mean()


# ------------------------------------------------------------------ VPIN
def vpin(te, sd):
    b = np.searchsorted(T, te, side="right"); a = b - VB * VN - 1
    if a < 0:
        return np.nan, np.nan
    m = (np.asarray(B[a:b]) + np.asarray(A[a:b])) / 2
    d = np.sign(np.diff(m))
    for i in range(1, len(d)):                          # tick test: no change = the previous tick's side
        if d[i] == 0:
            d[i] = d[i - 1]
    d = d.reshape(VN, VB)
    up = (d > 0).sum(1); dn = (d < 0).sum(1)
    v = (np.abs(up - dn) / VB).mean()
    f = (up[-VF:].sum() - dn[-VF:].sum()) / max(1, up[-VF:].sum() + dn[-VF:].sum())
    return v, sd * f


# ------------------------------------------------------------------ HMM (diagonal Gaussian, Baum-Welch + forward filter)
@njit(cache=True)
def _bar_tickstd(T, B, A, t15):
    n = t15.shape[0]; out = np.zeros(n); k = 0; nt = T.shape[0]
    while k < nt and T[k] < t15[0]:
        k += 1
    for j in range(n):
        end = t15[j] + 900
        s = 0.0; s2 = 0.0; c = 0; prev = -1.0
        while k < nt and T[k] < end:
            m = (B[k] + A[k]) * 0.5
            if prev > 0:
                d = m - prev; s += d; s2 += d * d; c += 1
            prev = m; k += 1
        out[j] = np.sqrt(max(s2 / c - (s / c) ** 2, 0.0)) if c > 1 else 0.0
    return out


def bar_features(D, ef, es):
    fn = os.path.join(HERE, "micro_tickstd.npy")
    if os.path.exists(fn):
        ts = np.load(fn)
    else:
        ts = _bar_tickstd(np.asarray(T), np.asarray(B), np.asarray(A), D["t15"].astype(np.float64)); np.save(fn, ts)
    c = D["c15"]; atr = D["atr"]
    r = np.r_[0, np.diff(np.log(c))]
    lv = np.log(ts + 1e-4)
    disp = np.where(atr > 0, (ef - es) / np.where(atr > 0, atr, 1), 0)
    return np.c_[r, lv, disp]


def _logN(X, mu, var):
    return -0.5 * (np.log(2 * np.pi * var)[None] + (X[:, None, :] - mu[None]) ** 2 / var[None]).sum(-1)


def hmm_fit(X, S, it=60, seed=1):
    rng = np.random.default_rng(seed); n = len(X)
    mu = X[rng.choice(n, S, replace=False)]; var = np.tile(X.var(0), (S, 1)); A_ = np.full((S, S), 0.1 / (S - 1)); np.fill_diagonal(A_, 0.9); pi = np.full(S, 1 / S)
    for _ in range(it):
        le = _logN(X, mu, var); mx = le.max(1, keepdims=True); e = np.exp(le - mx)
        al = np.zeros((n, S)); c = np.zeros(n)
        al[0] = pi * e[0]; c[0] = al[0].sum(); al[0] /= c[0]
        for t in range(1, n):
            al[t] = (al[t - 1] @ A_) * e[t]; c[t] = al[t].sum(); al[t] /= c[t]
        be = np.ones((n, S))
        for t in range(n - 2, -1, -1):
            be[t] = (A_ @ (e[t + 1] * be[t + 1])) / c[t + 1]
        g = al * be; g /= g.sum(1, keepdims=True)
        xi = np.zeros((S, S))
        for t in range(n - 1):
            z = al[t][:, None] * A_ * (e[t + 1] * be[t + 1])[None]; xi += z / z.sum()
        pi = g[0]; A_ = xi / xi.sum(1, keepdims=True)
        w = g.sum(0); mu = (g.T @ X) / w[:, None]
        var = np.maximum((g.T @ (X ** 2)) / w[:, None] - mu ** 2, 1e-6)
    return pi, A_, mu, var


def hmm_filter(X, pi, A_, mu, var):
    le = _logN(X, mu, var); mx = le.max(1, keepdims=True); e = np.exp(le - mx)
    al = np.zeros((len(X), len(pi))); al[0] = pi * e[0]; al[0] /= al[0].sum()
    for t in range(1, len(X)):
        al[t] = (al[t - 1] @ A_) * e[t]; al[t] /= al[t].sum()
    return al


# ------------------------------------------------------------------ main
def gate_eval(name, veto, p, te):
    tr_, ts_ = te < T26, te >= T26
    def s(m):
        q = p[m]; return f"{m.sum():4d} tr {100 * (q > 0).mean():5.1f}% {q.sum():+10,.0f}"
    kt, kv = ~veto & tr_, ~veto & ts_
    print(f"{name:44s} TRAIN base {s(tr_)} | kept {s(kt)} (vetoed {(veto & tr_).sum()}, of them losers {((veto & tr_) & (p <= 0)).sum()})"
          f" || 2026 base {s(ts_)} | kept {s(kv)} (vetoed {(veto & ts_).sum()}, losers {((veto & ts_) & (p <= 0)).sum()})", flush=True)


if __name__ == "__main__":
    tr, st = trades()
    D = sim.data("m15"); t15 = D["t15"]
    ef, es = sim.emas(int(INP["InpEmaFast"]), int(INP["InpEmaSlow"]), "m15")
    p = tr[:, 6]; te = tr[:, 1]; sd = tr[:, 0]; L = (p <= 0).astype(np.float64); TR = te < T26
    print(f"trades {len(p)}: train {TR.sum()} ({int(L[TR].sum())} losers), 2026 {(~TR).sum()} ({int(L[~TR].sum())} losers)")

    # DTW
    Pth = np.array([path(a, b) if path(a, b) is not None else np.zeros(NP) for a, b in zip(te, sd)])
    Ptr, Ltr = Pth[TR], L[TR]; CT = np.cumsum(TR)
    sc = np.array([knn_score(Pth[i], Ptr, Ltr, K, BAND, int(CT[i] - 1) if TR[i] else -1) for i in range(len(p))])
    for th in (0.1, 0.15, 0.2, 0.25, 0.3):
        gate_eval(f"DTW: veto if >= {th:.0%} of 20 nearest lost", sc >= th, p, te)
    # VPIN
    V = np.array([vpin(a, b) for a, b in zip(te, sd)]); v, f = V[:, 0], V[:, 1]
    q = {x: np.nanpercentile(v[TR], x) for x in (80, 90, 95)}
    for x, qv in q.items():
        for ft in (0.0, 0.05, 0.1):
            gate_eval(f"VPIN >= p{x} ({qv:.3f}) & flow <= -{ft}", (v >= qv) & (f <= -ft), p, te)
    # HMM
    X = bar_features(D, ef, es); fit_m = (t15 < T26) & (np.arange(len(t15)) > 300)
    mu0, sd0 = X[fit_m].mean(0), X[fit_m].std(0); Z = (X - mu0) / sd0
    jb = np.searchsorted(t15, te, "right") - 2
    best = None
    for S in (3, 4):
        pi, A_, mu, var = hmm_fit(Z[fit_m][::1], S)
        al = hmm_filter(Z, pi, A_, mu, var)
        st_ = al[jb].argmax(1)
        lr = [(L[TR & (st_ == s_)].mean() if (TR & (st_ == s_)).sum() else 0, int((TR & (st_ == s_)).sum())) for s_ in range(S)]
        tox = int(np.argmax([x[0] if x[1] >= 30 else 0 for x in lr]))
        print(f"HMM {S} states: train loss rate / trades per state {[(round(100 * a, 1), b) for a, b in lr]} -> toxic state {tox}")
        for th in (0.5, 0.75, 0.9):
            gate_eval(f"HMM{S}: veto if P(state {tox}) > {th}", al[jb, tox] > th, p, te)
        if best is None or S == 3:
            best = (S, pi, A_, mu, var, tox)
    np.savez(os.path.join(HERE, "micro_feats.npz"), sc=sc, v=v, f=f, Pth=Pth, L=L, TR=TR, p=p, te=te, sd=sd, mu0=mu0, sd0=sd0)
    json.dump({"hmm": {"S": best[0], "pi": best[1].tolist(), "A": best[2].tolist(), "mu": best[3].tolist(), "var": best[4].tolist(), "tox": best[5],
                       "mu0": mu0.tolist(), "sd0": sd0.tolist()}}, open(os.path.join(HERE, "micro_model.json"), "w"), indent=1)
