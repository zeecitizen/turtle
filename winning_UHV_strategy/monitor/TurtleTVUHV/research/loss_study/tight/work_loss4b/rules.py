"""rules.py (work_loss4b) - cures designed from the tight losses 1019-171329-S and 1023-145031-B (charts + their PrimeXBT ticks).
Python tick replay = HYPOTHESIS, NOT PROMOTED (CLAUDE.md). Only MT5's Strategy Tester (or live fills) may promote any of this.

A rule is rule(t, A) -> True = SKIP. Bar rules read only bars <= t["k"] and the setup fields of t. EXTENDED-FIELD rules (marked) read
tickfeats.json (built by tickfeats.py / tickfeats2.py from ticks STRICTLY BEFORE the breakout tick - what the EA sees when it decides),
looked up by t["id"], like rule_trigger_spread in ../../final/rules_final.py.

THE 'GENERALISES' BAR (written BEFORE any rule was scored): on secure OR base, WR after > WR before on BOTH train and test, with at least
2 losses removed in EACH half of that stack. A rule that only fixes the tight / zee100 losses is memorisation.

THRESHOLDS fixed in advance from the two losses (no tuning on the scores):
  1019-171329-S: bid pinned ON the level ~25 s (at_30 = 9), 3 separate approaches in the last minute (cyc_60 = 3), broke by 0.1 pip,
                 moved 0.1 pip in the last 5 s (vel_5 = 0.1). 1023-145031-B: at_30 = 9, cyc_60 = 3, vel_5 = 0.2.
  their six winning twins: cyc_60 = 1 (all six), vel_5 0.0-0.5.
Run: py rules.py   (asserts every trade id resolves in tickfeats.json, then prints api_tight.report for every rule + the bar check)

VERDICTS (2026-11-06; raw output in rules_report.txt, stats.txt, geometry.txt, engine_spread.txt):
  The literal pre-written bar (WR direction) is met by rule_tested_level, rule_pinned_bid, rule_choppy30 and rule_wide_spread. That bar
  turned out too weak (randomly removing trades meets it in roughly 1 case of 4 per stack), so stats.py adds the strict per-half check:
  lift + binomial p on secure and on base_g (base with the setting's own rollover + 1.0-pip guards applied). Every one of the four fails it:
    rule_tested_level  base test +0.01 pts; base_g test x1.23 (p 0.36), x0.86 without 1019/1023; secure train x0.97 -> NOT generalising
    rule_pinned_bid    base train +0.01 pts; base_g train x1.12 (p 0.44), test x1.31 without 1019/1023 (p 0.34) -> NOT generalising
    rule_choppy30      secure x1.26 (p 0.21) / x1.09 (p 0.49) while cutting 57% of trades; base_g x0.95 / x1.11 -> memorisation
    rule_wide_spread   train-only: its base test removals are rollover / >= 1-pip spikes the setting already blocks (base_g test 0L/11W,
                       secure test 0 trades). Engine (InpUhvMaxTrigSpread 0.5): secure 30 -> 12 L, -$2,976 -> -$0; tight 4 -> 3 L;
                       zee100 0 L, 308 -> 241 trades - ALL in Mar-Jun; Jul-Nov identical. A regime switch for MT5, not a cure.
  rule_creep_in and rule_grind fail even the literal bar. NO GENERALISING CURE from these two losses. NOT PROMOTED."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
_TF = json.load(open(os.path.join(HERE, "tickfeats.json"), encoding="utf-8"))


def _tf(t, key):
    return _TF[t["id"]][key]                      # a KeyError would be swallowed by api_tight.score as 'keep' - main() asserts coverage


# ------------------------------------------------------------------ from the tick story (EXTENDED FIELD: ticks strictly before the break)

def rule_tested_level(t, A):
    """EXTENDED FIELD. The level was approached 3+ separate times in the last 60 s (the bid came to it, backed off >= 0.2 pip, came back):
    a defended level - 1019-171329-S and 1023-145031-B both 3, all six twins 1."""
    return _tf(t, "cyc_60") >= 3


def rule_pinned_bid(t, A):
    """EXTENDED FIELD. The bid printed exactly ON the level 9+ times in the last 30 s before the break: absorption at the level (both
    losses 9; the twins 1, 1, 2, 5, 19, 2)."""
    return _tf(t, "at_30") >= 9


def rule_creep_in(t, A):
    """EXTENDED FIELD. No push: the bid moved <= 0.2 pip towards the level in the last 5 s before the break - it crept through instead of
    arriving with speed (losses 0.1 / 0.2; twins 0.4, 0.5, 0.4, 0.1, 0.0, 0.5)."""
    return _tf(t, "vel_5") <= 0.2


def rule_grind(t, A):
    """EXTENDED FIELD. The whole story of both losses: a defended level (3+ approaches in 60 s) AND a creeping break (<= 0.2 pip in 5 s)."""
    return _tf(t, "cyc_60") >= 3 and _tf(t, "vel_5") <= 0.2


# ------------------------------------------------------------------ bar / setup-field rules

def rule_choppy30(t, A):
    """MEMORISATION CONTROL. A fast 16-bar leg inside a directionless 30-bar window (ER of the last 30 closes < 0.2): all 4 tight losses
    have ER30 0.02-0.17 (a swing across a box, arriving at its far edge). Chosen BECAUSE it holds the 4 - expected not to generalise."""
    k = t["k"]
    cc = A.c[k - 30:k + 1]
    p = float(np.abs(np.diff(cc)).sum())
    return (abs(float(cc[-1] - cc[0])) / p if p > 0 else 0.0) < 0.2


def rule_wide_spread(t, A):
    """MECHANISM BENCHMARK. Spread at the breakout tick >= 0.5 pip (the setting's guard is 1.0): with a 0.1-pip target the price must
    first travel the spread, so the random-walk loss chance is ~(spread + 0.1) / (stop + 0.1). = InpUhvMaxTrigSpread 0.5 in the engine."""
    return t["trig_spread_pips"] >= 0.5 - 1e-9


RULES = (rule_tested_level, rule_pinned_bid, rule_creep_in, rule_grind, rule_choppy30, rule_wide_spread)


def bar_check(rule):
    """the 'generalises' bar + zee100 cost, from api_tight.score"""
    import api_tight as api
    out, ok_any = [], False
    for st in ("secure", "base"):
        r = api.score(rule, st)
        tr, te = r["train"], r["test"]
        ok = tr["wr_after"] > tr["wr_before"] and te["wr_after"] > te["wr_before"] and tr["losses_removed"] >= 2 and te["losses_removed"] >= 2
        ok_any |= ok
        out.append(f"{st}: tr -{tr['losses_removed']}L/-{tr['winners_removed']}W te -{te['losses_removed']}L/-{te['winners_removed']}W {'PASS' if ok else 'fail'}")
    z = api.score(rule, "zee100")["all"]
    out.append(f"zee100 winners removed {z['winners_removed']} of {z['trades']}")
    return ok_any, " | ".join(out)


def main():
    import api_tight as api
    missing = [t["id"] for st in ("tight", "secure", "base") for t in api.STACKS[st] if t["id"] not in _TF]
    assert not missing, f"{len(missing)} trade ids missing from tickfeats.json, e.g. {missing[:3]}"
    for st in ("tight", "secure", "base"):                       # every rule must run without an exception on every trade
        for t in api.STACKS[st]:
            for rule in RULES:
                rule(api._blind(t), api.A)
    print("tickfeats coverage OK, 0 exceptions. Python replay = HYPOTHESIS, NOT PROMOTED.", flush=True)
    for rule in RULES:
        api.report(rule, rule.__name__)
        ok, line = bar_check(rule)
        print(f"    literal_bar={ok}  ({line})  [too weak - see VERDICTS / stats.txt]", flush=True)


if __name__ == "__main__":
    main()
