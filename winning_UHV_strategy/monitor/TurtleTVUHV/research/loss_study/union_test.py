"""union_test.py - Zee 2026-11-06: "if some of these remove like 25-46 losers ... if we can cut them all out then who cares for how many trades
we take". Applies every filter tested so far (his October + March ideas), one by one and then ALL TOGETHER (a trade is skipped if ANY filter
skips it), and prints trades left, losses left and the win rate - the format he asked for. Run: py research/loss_study/union_test.py"""
import api
import zee_march_rules as Z

PIP = api.PIP


def close(t, A):
    return 74700 <= t["t_in"] % 86400 <= 76500


def structure(t, A):
    hs, ls = A.pivots(t["k"], 1, 120)
    if len(hs) < 2 or len(ls) < 2:
        return False
    if t["side"] > 0:
        return not (hs[-1][1] > hs[-2][1] and ls[-1][1] > ls[-2][1])
    return not (ls[-1][1] < ls[-2][1] and hs[-1][1] < hs[-2][1])


def sr3(t, A):
    k = t["k"]
    lo, hi = float(A.l[k - 59:k + 1].min()), float(A.h[k - 59:k + 1].max())
    return (t["fill"] - lo) < 3 * PIP if t["side"] < 0 else (hi - t["fill"]) < 3 * PIP


def range2(t, A):
    k = t["k"]
    rg = float(A.h[k - 9:k + 1].max() - A.l[k - 9:k + 1].min())
    return A.atr[k] > 0 and rg < 2.0 * A.atr[k]


RULES = [("market close", close), ("structure (no HH+HL / LL+LH)", structure), ("near support/resistance 3 pips", sr3),
         ("ranging (10 bars < 2 ATR)", range2), ("uptrend begun (fresh break)", lambda t, A: Z.fresh_break(t, A, 5, 2)),
         ("broke 5 highs", lambda t, A: Z.broke_many_highs(t, A, 5, 8)), ("exhausted 4+ humps", lambda t, A: Z.exhausted(t, A, 4)),
         ("deep retracement", Z.deep_retrace), ("5-min trend against", Z.htf5_against)]

T = api.TRADES
n0 = len(T); L0 = sum(1 for t in T if not t["win"])
print(f"{'':34s} {'trades left':>12s} {'losses left':>12s} {'win rate':>9s}")
print(f"{'ALL TRADES (no filter)':34s} {n0:12d} {L0:12d} {100 * (n0 - L0) / n0:8.2f}%")
skip_any = [False] * n0
for name, f in RULES:
    s = [bool(f(api._blind(t), api.A)) for t in T]
    left = [t for t, x in zip(T, s) if not x]
    ll = sum(1 for t in left if not t["win"])
    print(f"{'only: ' + name:34s} {len(left):12d} {ll:12d} {100 * (len(left) - ll) / max(len(left), 1):8.2f}%")
    skip_any = [a or b for a, b in zip(skip_any, s)]
    lu = [t for t, x in zip(T, skip_any) if not x]
    lul = sum(1 for t in lu if not t["win"])
    print(f"{'   -> all filters so far together':34s} {len(lu):12d} {lul:12d} {100 * (len(lu) - lul) / max(len(lu), 1):8.2f}%")
