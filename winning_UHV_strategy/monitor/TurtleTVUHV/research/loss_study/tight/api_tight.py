"""api_tight.py - scoring harness for cures of the angel's secure zones (research/loss_study/tight). A rule is

    def rule(t, A) -> bool        # True = SKIP

  t = one trade at DECISION time (the breakout tick), no outcome: id, side (+1/-1), t_dec (UTC s), k (last closed candle before the breakout
      minute), kb, ku (UHV candle), level, extreme, uhv_v, brk_ticks, brk_lo, brk_hi, brk_bid, trig_spread_pips, box, humps (camel humps of
      the trade's colour in a row at k), er16 (efficiency ratio of the last 16 closes), atr_pips
  A = per-bar arrays from ../arrays.npz: A.t A.o A.h A.l A.c A.v A.atr A.adx (index like k). Read ONLY bars <= t["k"].
score(rule, stack) for stack in "tight" (2-3 humps, ER 0.30-0.45: 714 tr / 4 L), "zee100" (Zee's 2026-11-06 07-33-17: ER 0.30-0.35: 308 tr /
0 L), "secure" (2-5 humps, ER 0.15-0.45: 2237 tr / 30 L), "base" (no risk manager: 7626 tr / 172 L): trades / losses removed and the win rate
after, all and by half (train = before 2026-07-01, test = after). A real cure removes losses on SEVERAL stacks and both halves, not just the 4.
Note: post-hoc (a skipped trade does not free its slot for another setup as the engine would) - confirm finalists in the engine."""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SPLIT = 1782864000
OUTCOME = ("win", "pnl", "fill", "stop", "t_out", "exit", "best_R", "worst_R")


class _A:
    def __init__(self):
        z = np.load(os.path.join(os.path.dirname(HERE), "arrays.npz"))
        for k in ("t", "o", "h", "l", "c", "v", "atr", "adx"):
            setattr(self, k, z[k])


A = _A()
STACKS = {}
for nm in ("tight", "secure", "base"):
    p = os.path.join(HERE, f"trades_{nm}.json")
    if os.path.exists(p):
        STACKS[nm] = json.load(open(p, encoding="utf-8"))
if "tight" in STACKS:
    STACKS["zee100"] = [t for t in STACKS["tight"] if 0.30 <= t["er16"] < 0.35]


def _blind(t):
    return {k: v for k, v in t.items() if k not in OUTCOME}


def score(rule, stack="tight"):
    T = STACKS[stack]
    res = {}
    for part, f in (("all", lambda t: True), ("train", lambda t: t["t_dec"] < SPLIT), ("test", lambda t: t["t_dec"] >= SPLIT)):
        S = [t for t in T if f(t)]
        n = len(S); L = sum(1 for t in S if not t["win"])
        out = []
        for t in S:
            try:
                if rule(_blind(t), A):
                    out.append(t)
            except Exception:                                    # noqa: BLE001
                pass
        oL = sum(1 for t in out if not t["win"])
        res[part] = {"trades": n, "losses": L, "removed": len(out), "losses_removed": oL, "winners_removed": len(out) - oL,
                     "wr_before": round(100 * (1 - L / max(n, 1)), 2), "wr_after": round(100 * (1 - (L - oL) / max(n - len(out), 1)), 2)}
    return res


def report(rule, name=""):
    line = [f"{name:30s}"]
    for st in ("tight", "zee100", "secure", "base"):
        if st not in STACKS:
            continue
        r = score(rule, st)
        a, tr, te = r["all"], r["train"], r["test"]
        line.append(f"{st}: -{a['losses_removed']}L/-{a['winners_removed']}W WR {a['wr_before']}->{a['wr_after']} (tr {tr['wr_before']}->{tr['wr_after']}, te {te['wr_before']}->{te['wr_after']})")
    print(" | ".join(line), flush=True)


if __name__ == "__main__":
    for nm, T in STACKS.items():
        print(nm, len(T), "trades", sum(1 for t in T if not t["win"]), "losses")
    report(lambda t, A: t["er16"] >= 0.35, "example: ER16 >= 0.35")
