"""final_checks.py (work_redteam) - the remaining red-team checks. Python tick replay = HYPOTHESIS, NOT PROMOTED.
 1. zee100 exit reasons / holding; how close the tight + secure losses came to the target (best pips after the fill)
 2. near misses: share of trades that dipped to -0.25 R / -0.5 R, and how many of those went on to the stop, per stack
 3. random-entry null on the same PrimeXBT ticks: 0.1-pip target, 21-pip stop, 0.3 s latency, ask/bid fills (numba)
 4. the three logged steps re-read per half on the harness stacks (dropped vs kept loss rate)
 5. the other saved setting from today that the verdict did not mention (2026-11-06 13-00-00, RiskMgr 4)
 6. doctrine.python_says for the zee100 setting (the only sanctioned way to report a Python win rate)
Run: cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/tight/work_redteam/final_checks.py"""
import contextlib
import datetime as dt
import io
import json
import os
import sys
from zoneinfo import ZoneInfo

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
ROOT = r"C:/Users/zeesh/turtle/monitor/TurtleTVUHV"
sys.path.insert(0, ROOT)
sys.path.insert(0, r"C:/Users/zeesh/turtle/monitor")
HERE = os.path.dirname(os.path.abspath(__file__))
TIGHT = os.path.dirname(HERE)
import numpy as np  # noqa: E402
from numba import njit  # noqa: E402
from scipy.stats import fisher_exact  # noqa: E402

import uhv_engine as U  # noqa: E402

SPLIT = 1782864000
PIP = 1e-4
SAVED = os.path.join(ROOT, "settings", "saved")


def inp(fn):
    return json.load(open(os.path.join(SAVED, fn + ".json"), encoding="utf-8"))["inputs"]


SET = {"zee100": inp("2026-11-06 07-33-17"), "tight": inp("2026-11-06 09-00-00"), "secure": inp("2026-11-06 09-10-00"),
       "base": inp("2026-11-05 05-45-38")}
RR = {}
for nm, x in SET.items():
    rows, _, _ = U.simulate(x)
    RR[nm] = rows
    print(f"{nm}: rows {len(rows)}, ghost rows (col10=1): {int((rows[:, 10] == 1).sum())}")
R = {nm: r[r[:, 10] == 0] for nm, r in RR.items()}

print("\n== 1. exits")
z = R["zee100"]
why, cnt = np.unique(z[:, 13], return_counts=True)
print("zee100 exit reason codes (5 = target):", dict(zip(why.astype(int).tolist(), cnt.tolist())),
      "| hold s: median", round(float(np.median(z[:, 4] - z[:, 1])), 1), "max", round(float((z[:, 4] - z[:, 1]).max())))
for nm in ("tight", "secure"):
    r = R[nm]
    L = r[r[:, 6] <= 0]
    sl_p = np.abs(L[:, 2] - L[:, 3]) / PIP
    best_p = L[:, 15] * sl_p
    print(f"{nm} losses: best move after fill (pips): " + ", ".join(f"{b:+.1f}" for b in best_p)
          + f" | exit codes {sorted(set(L[:, 13].astype(int).tolist()))}")

print("\n== 2. near misses (deepest dip before the result, R = stop distance)")
for nm in ("zee100", "tight", "secure", "base"):
    r = R[nm]
    w = r[:, 16]
    loss = r[:, 6] <= 0
    tr = r[:, 1] < SPLIT
    for d in (-0.25, -0.5):
        reach = w <= d + 1e-9
        nr, nl = int(reach.sum()), int((reach & loss).sum())
        s = []
        for h, m in (("train", tr), ("test", ~tr)):
            a, b = int((reach & m).sum()), int((reach & loss & m).sum())
            s.append(f"{h} {b}/{a}")
        print(f"  {nm:7s} dipped to {d:+.2f}R: {nr:5d} of {len(r)} ({100 * nr / len(r):.1f}%), went on to lose {nl} "
              f"({100 * nl / max(nr, 1):.0f}%)  [{', '.join(s)}]")
zr = int((z[:, 16] <= -0.25).sum())
for p in (0.15, 0.25, 0.35):
    e = zr * p / (1 - p)
    print(f"  if zee100's dippers went on to lose at {int(p * 100)}% like the stacks: expected {e:.1f} losses in 308 -> "
          f"{100 * e / 308:.2f}% loss rate; P(0 of {zr} | {p}) = {(1 - p) ** zr:.4f}")

print("\n== 3. random-entry null (same ticks, same geometry)")
S, TK = U._setups(U.det_file(SET["zee100"]))
T, B, A = TK["t"], TK["bid"], TK["ask"]


@njit(cache=False)
def play(T, B, A, starts, sides, lat, tp, sl, hold):
    out = np.zeros(len(starts), dtype=np.int8)
    for n in range(len(starts)):
        i = np.searchsorted(T, starts[n] + lat)
        if i >= len(T) or T[i] - starts[n] > 60.0:
            out[n] = 9
            continue
        if A[i] - B[i] >= 1.0e-4 - 1e-9:
            out[n] = 8
            continue
        s = sides[n]
        f = np.float64(A[i]) if s > 0 else np.float64(B[i])
        res = 0
        for j in range(i, len(T)):
            if T[j] - starts[n] > hold:
                break
            px = np.float64(B[j]) if s > 0 else np.float64(A[j])
            m = (px - f) * s / 1e-4
            if m <= -sl:
                res = -1
                break
            if m >= tp - 1e-3:
                res = 1
                break
        out[n] = res
    return out


NY = ZoneInfo("America/New_York")


def ok_time(ts):
    d = dt.datetime.fromtimestamp(ts, NY)
    m = d.hour * 60 + d.minute
    return not (16 * 60 + 45 <= m < 17 * 60 + 45)


rng = np.random.default_rng(11)
idx = rng.integers(0, len(T) - 1, 60000)
st_ = np.asarray(T)[idx].astype(np.float64)
keep = np.array([ok_time(x) for x in st_])
st_ = st_[keep][:40000]
sd = rng.choice(np.array([-1, 1]), len(st_))
o = play(T, B, A, st_, sd, 0.3, 0.1, 21.0, 86400.0)
mk = (o == 1) | (o == -1)
v, tv = o[mk], st_[mk]
print(f"  (a) random tick + random side, n {len(v)}: WR {100 * np.mean(v == 1):.2f}%  (train {100 * np.mean(v[tv < SPLIT] == 1):.2f}%, "
      f"test {100 * np.mean(v[tv >= SPLIT] == 1):.2f}%)")
zt, zs = z[:, 1] - 0.3, z[:, 0].astype(np.int64)
rep = 60
off = rng.uniform(5 * 60, 90 * 60, len(zt) * rep) * rng.choice(np.array([-1, 1]), len(zt) * rep)
st2 = np.repeat(zt, rep) + off
sd2 = np.repeat(zs, rep)
keep = np.array([ok_time(x) for x in st2])
st2, sd2 = st2[keep], sd2[keep]
o2 = play(T, B, A, st2, sd2, 0.3, 0.1, 21.0, 86400.0)
m2 = (o2 == 1) | (o2 == -1)
v2, t2 = o2[m2], st2[m2]
print(f"  (b) zee100's side, 5-90 min from its own entries, n {len(v2)}: WR {100 * np.mean(v2 == 1):.2f}%  "
      f"(train {100 * np.mean(v2[t2 < SPLIT] == 1):.2f}%, test {100 * np.mean(v2[t2 >= SPLIT] == 1):.2f}%)")

print("\n== 4. the three logged steps per half (harness secure stack, post hoc)")
Ts = json.load(open(os.path.join(TIGHT, "trades_secure.json"), encoding="utf-8"))


def cmp(label, drop):
    for h, f in (("train", lambda t: t["t_dec"] < SPLIT), ("test", lambda t: t["t_dec"] >= SPLIT)):
        S_ = [t for t in Ts if f(t)]
        D = [t for t in S_ if drop(t)]
        K = [t for t in S_ if not drop(t)]
        dl = sum(not t["win"] for t in D)
        kl = sum(not t["win"] for t in K)
        p = fisher_exact([[dl, len(D) - dl], [kl, len(K) - kl]], alternative="greater")[1]
        print(f"  {label:26s} {h}: dropped {dl}/{len(D)} = {100 * dl / max(len(D), 1):.2f}%  kept {kl}/{len(K)} = "
              f"{100 * kl / max(len(K), 1):.2f}%  (one-sided Fisher p {p:.2f})")


cmp("ER min 0.15 -> 0.30", lambda t: t["er16"] < 0.30)
Ts = [t for t in Ts if t["er16"] >= 0.30]
cmp("then humps max 5 -> 3", lambda t: t["humps"] > 3)
Ts = [t for t in Ts if t["humps"] <= 3]
cmp("then ER max 0.45 -> 0.35", lambda t: t["er16"] >= 0.35)

print("\n== 5. the other saved setting from today (not in the verdict)")
for fn in ("2026-11-06 13-00-00",):
    rows, _, _ = U.simulate(inp(fn))
    r = rows[rows[:, 10] == 0]
    for h, m in (("all", np.ones(len(r), bool)), ("train", r[:, 1] < SPLIT), ("test", r[:, 1] >= SPLIT)):
        p = r[m, 6]
        L = int((p <= 0).sum())
        print(f"  {fn} {h}: {len(p)} trades / {L} losses / WR {100 * (1 - L / max(len(p), 1)):.2f}% / net {p.sum():+.2f}")

print("\n== 6. doctrine")
from doctrine import python_says  # noqa: E402

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    python_says("zee100 = 2026-11-06 07-33-17, engine 308 trades / 0 losses (break-even 99.3% at the engine's $1.44 average win)",
                win_pct=100.0, need_pct=99.3)
    python_says("zee100, break-even if every win is exactly +0.1 pip ($1.00)", win_pct=100.0, need_pct=99.5)
    python_says("zee100 out-of-sample estimate (neighbourhood / walk-forward), about 99%", win_pct=99.0, need_pct=99.3)
print(buf.getvalue())
