"""stats.py (work_loss4b) - the strict diagnostic for every rule in rules.py: per stack and half, trades removed, losses removed, the
half's own loss rate, lift (loss rate among the removed / the half's loss rate) and a one-sided binomial p-value P(X >= losses removed).
Adds base_g = base with the tight setting's own guards applied (no entries 16:45-17:45 New York, breakout spread < 1.0 pip), so a rule is
judged where it would actually act. Also re-scores the tick rules WITHOUT the two hypothesis-generating losses.
Python replay = HYPOTHESIS, NOT PROMOTED."""
import datetime as dt
import os
import sys
from math import comb
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import api_tight as api  # noqa: E402
import rules as R  # noqa: E402

NY = ZoneInfo("America/New_York")
MINE = {"1019-171329-S", "1023-145031-B"}


def guarded(t):
    d = dt.datetime.fromtimestamp(t["t_dec"], NY)
    m = d.hour * 60 + d.minute
    return not (16 * 60 + 45 <= m < 17 * 60 + 45) and t["trig_spread_pips"] < 1.0 - 1e-9


def binom_sf(k, n, p):
    if k <= 0:
        return 1.0
    return max(0.0, 1.0 - sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k)))


STK = {"secure": api.STACKS["secure"], "base_g": [t for t in api.STACKS["base"] if guarded(t)]}


def diag(rule, drop=()):
    out = []
    for st, T in STK.items():
        T = [t for t in T if t["id"] not in drop]
        for part, f in (("tr", lambda t: t["t_dec"] < api.SPLIT), ("te", lambda t: t["t_dec"] >= api.SPLIT)):
            S = [t for t in T if f(t)]
            n, L = len(S), sum(1 for t in S if not t["win"])
            rem = [t for t in S if rule(api._blind(t), api.A)]
            nr, Lr = len(rem), sum(1 for t in rem if not t["win"])
            p0 = L / max(n, 1)
            lift = (Lr / nr) / p0 if nr and p0 else 0.0
            wa = 100 * (1 - (L - Lr) / max(n - nr, 1)); wb = 100 * (1 - p0)
            out.append(f"{st}-{part}: -{Lr}L/-{nr - Lr}W of {n}/{L}L lift x{lift:.2f} p={binom_sf(Lr, nr, p0):.3f} WR {wb:.2f}->{wa:.2f}")
    return " | ".join(out)


if __name__ == "__main__":
    for st, T in STK.items():
        tr = [t for t in T if t["t_dec"] < api.SPLIT]; te = [t for t in T if t["t_dec"] >= api.SPLIT]
        print(f"{st}: {len(T)} trades {sum(not t['win'] for t in T)} L | train {len(tr)}/{sum(not t['win'] for t in tr)}L | test {len(te)}/{sum(not t['win'] for t in te)}L")
    for rule in R.RULES:
        print(f"{rule.__name__:18s} {diag(rule)}")
    print("--- tick rules without the two hypothesis-generating losses (1019-171329-S, 1023-145031-B):")
    for rule in (R.rule_tested_level, R.rule_pinned_bid, R.rule_grind):
        print(f"{rule.__name__:18s} {diag(rule, MINE)}")
