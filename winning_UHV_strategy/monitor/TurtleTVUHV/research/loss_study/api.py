"""api.py - the scoring harness for loss-fix rules (research/loss_study). A rule is a Python function

    def rule(t, A) -> bool          # True = SKIP this trade

  t  one trade, WITHOUT its outcome: id, side (+1 buy / -1 sell), t_in (UTC s), k (index of the last CLOSED candle before the entry),
     kb (= k + 1, the entry minute), ku (the UHV candle's index), level, extreme, fill, stop, stop_pips, uhv_v, brk_ticks_so_far,
     brk_lo_so_far, brk_hi_so_far, box, camEff (camel side at k: +1 green / -1 red / 0), camStk (humps in a row, signed)
  A  per-bar arrays, all indexed like k:  A.t A.o A.h A.l A.c A.v (tick volume) A.atr A.adx (in price units for atr)
     A.camEff A.camStk A.camT (+1 last swing was a high, -1 a low) A.camHV / A.camLV / A.camL0V (the camel's last high, last low, the low
     before) and A.humps (rows: b0, v0, bh, vh, b1, v1, tr(+1 green / -1 red / 0), known_at_bar) - a hump is usable only if known_at_bar <= k.
     Helpers: A.pivots(k, p=1, look=120) -> (highs, lows) confirmed swing points [(bar, price)] up to k (no future), A.humps_known(k)
     PIP = 0.0001.  A rule must read ONLY bars <= k (and the setup fields above). Reading k+1 or later, or any outcome, is cheating.

score(rule) / report(rule, name): over every trade of the 97.7% setting - how many winners and losers the rule removes, the loss rate among
the removed (vs the base 2.3%: a useful rule removes losers at many times the base rate), the same on the train half (Mar-Jun) and test half
(Jul-Nov), the net change at 1 lot, and how many of Zee's 22 commented losses it removes. A rule is only worth shipping if its loss rate
among removed trades is well above base on BOTH halves."""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PIP = 1e-4
SPLIT = 1782864000          # 2026-07-01 00:00 UTC
OUTCOME = ("pnl", "win", "t_out", "exit", "why", "best_R", "worst_R")


class Arrays:
    def __init__(self):
        z = np.load(os.path.join(HERE, "arrays.npz"))
        for k in z.files:
            setattr(self, k, z[k])
        self.PIP = PIP

    def pivots(self, k, p=1, look=120):
        h, l = self.h, self.l
        hs, ls = [], []
        for j in range(max(p, k - look), k - p + 1):
            if all(h[j] >= h[j - d] and h[j] >= h[j + d] for d in range(1, p + 1)):
                hs.append((j, float(h[j])))
            if all(l[j] <= l[j - d] and l[j] <= l[j + d] for d in range(1, p + 1)):
                ls.append((j, float(l[j])))
        return hs, ls

    def humps_known(self, k):
        H = self.humps
        return H[H[:, 7] <= k] if len(H) else H


A = Arrays()
TRADES = json.load(open(os.path.join(HERE, "trades.json"), encoding="utf-8"))
_C = os.path.join(os.path.dirname(os.path.dirname(HERE)), "settings", "loss_comments.json")
TAGGED = [(v["trade"]["entry_time"], v["trade"]["side"]) for v in json.load(open(_C, encoding="utf-8")).values()] if os.path.exists(_C) else []


def _blind(t):
    return {k: v for k, v in t.items() if k not in OUTCOME}


def score(rule):
    base = {"all": [0, 0, 0.0], "train": [0, 0, 0.0], "test": [0, 0, 0.0]}      # [n, losses, net]
    out = {"all": [0, 0, 0.0], "train": [0, 0, 0.0], "test": [0, 0, 0.0]}
    tagged_out = 0
    for t in TRADES:
        half = "train" if t["t_in"] < SPLIT else "test"
        for part in ("all", half):
            base[part][0] += 1; base[part][1] += (not t["win"]); base[part][2] += t["pnl"]
        try:
            skip = bool(rule(_blind(t), A))
        except Exception:                                   # noqa: BLE001  (a rule that cannot judge a trade keeps it)
            skip = False
        if skip:
            for part in ("all", half):
                out[part][0] += 1; out[part][1] += (not t["win"]); out[part][2] += t["pnl"]
            if not t["win"] and any(abs(t["t_in"] - tt) < 3 and sd == t["side"] for tt, sd in TAGGED):
                tagged_out += 1
    res = {"tagged_out": tagged_out}
    for part in ("all", "train", "test"):
        n, L, net = base[part]; on, oL, onet = out[part]
        res[part] = {"trades": n, "losses": L, "base_loss_rate": round(100 * L / max(n, 1), 2), "removed": on, "losers_removed": oL,
                     "winners_removed": on - oL, "loss_rate_removed": round(100 * oL / on, 2) if on else None,
                     "lift": round((oL / on) / (L / n), 2) if on and L else None, "net_change_usd_1lot": round(-onet, 0),
                     "wr_after": round(100 * (n - on - (L - oL)) / max(n - on, 1), 2)}
    return res


def report(rule, name=""):
    r = score(rule)
    a, tr, te = r["all"], r["train"], r["test"]
    print(f"{name:28s} removes {a['removed']:5d} (losers {a['losers_removed']:3d} / winners {a['winners_removed']:5d})  loss rate among removed "
          f"{a['loss_rate_removed']}% vs base {a['base_loss_rate']}%  lift x{a['lift']}  | train x{tr['lift']} ({tr['losers_removed']}L/{tr['winners_removed']}W)"
          f"  test x{te['lift']} ({te['losers_removed']}L/{te['winners_removed']}W)  | WR {a['wr_after']}%  net {a['net_change_usd_1lot']:+,.0f}$"
          f"  | Zee's 22: {r['tagged_out']}")
    return r


if __name__ == "__main__":
    n = len(TRADES); L = sum(1 for t in TRADES if not t["win"])
    print(f"{n} trades, {L} losses ({100 * L / n:.2f}%); tagged {len(TAGGED)}")
    report(lambda t, A: (t["t_in"] % 86400) >= 74700 and (t["t_in"] % 86400) <= 76500, "example: daily close 20:45-21:15")
