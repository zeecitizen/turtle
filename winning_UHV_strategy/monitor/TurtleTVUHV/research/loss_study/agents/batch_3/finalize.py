"""finalize.py - output.json -> output_final.json: code strings without docstrings (each re-exec'd alone and re-scored to prove the
numbers are unchanged) + batch_notes."""
import ast
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import api  # noqa: E402

D = json.load(open(os.path.join(HERE, "output.json"), encoding="utf-8"))
for r in D["rules"]:
    tree = ast.parse(r["code"])
    fn = tree.body[0]
    if fn.body and isinstance(fn.body[0], ast.Expr) and isinstance(getattr(fn.body[0], "value", None), ast.Constant) \
            and isinstance(fn.body[0].value.value, str):
        fn.body = fn.body[1:]
    code = ast.unparse(tree) + "\n"
    ns = {"np": np, "math": math}
    exec(code, ns)
    sc = api.score(ns["rule"])
    a, tr, te = sc["all"], sc["train"], sc["test"]
    assert (a["lift"], tr["lift"], te["lift"], a["losers_removed"], a["winners_removed"]) == \
        (r["lift_all"], r["lift_train"], r["lift_test"], r["losers_removed"], r["winners_removed"]), r["rule_id"]
    r["code"] = code

IDEA = {
    "fri_late20": "Friday from 20:00 UTC (the last hour before the weekly close).",
    "fri_late19": "Friday from 19:00 UTC.",
    "fri_late18": "Friday from 18:00 UTC.",
    "fri_late16": "Friday from 16:00 UTC.",
    "fri_late14": "Friday from 14:00 UTC.",
    "slip_20": "The fill is 2+ pips beyond the UHV level (spike or blown spread).",
    "slip_15": "The fill is 1.5+ pips beyond the UHV level.",
    "slip_10": "The fill is 1.0+ pip beyond the UHV level.",
    "slip_08": "The fill is 0.8+ pip beyond the UHV level.",
    "rollover_2045_2200": "Every day 20:45-22:00 UTC (the daily rollover: spread blow-out, dead tape).",
    "rollover_2100_2200": "Every day 21:00-22:00 UTC.",
    "session_close19": "Friday from 19:00 UTC or every day 20:45-22:00 UTC.",
    "bigfig_ahead08": "A 100-pip round number 0-0.8 pip beyond the level in the trade direction.",
    "bigfig_ahead15": "A 100-pip round number 0-1.5 pips beyond the level.",
    "bigfig_ahead20": "A 100-pip round number 0-2.0 pips beyond the level.",
    "fig20_ahead10": "A 20-pip round number 0-1.0 pip beyond the level.",
    "low_vol60_40": "Mean tick volume of the last 60 closed candles < 40.",
    "struct_broken_2p": "The retracement went 2+ pips beyond the camel's opposite swing (camHV[k] for sells, camLV[k] for buys).",
}
for r in D["rules"]:
    if r["rule_id"] in IDEA:
        r["idea"] = IDEA[r["rule_id"]]

D["batch_notes"] = (
    "Batch 3 = 21 losses from 7-27 Apr 2026 (all in the train half) + 42 twins. I opened every chart and wrote my own read of each loss, "
    "then built a feature table for all 7,626 trades from bars <= k only (about 70 features: time, volume, ATR/ADX, room to N-bar "
    "extremes, extension, trend, position in range, camel structure, touches, breakout-minute stats, spread proxy, round numbers, day "
    "levels, spike stats), binned every feature by train and test half, and scored 42 rules with api.report. "
    "MAIN FINDING: the only independent selective signal is the clock. session_close (skip Friday from 17:00 UTC + every day 20:45-22:00 UTC) "
    "removes 30L/330W, lift x3.80 train / x3.73 test (x3.31 / x2.62 even outside the existing 20:45-21:15 example window). session_slip20 "
    "(+ skip when the fill is already 2+ pips past the UHV level) removes 33L/350W, x3.84 / x3.90, WR 97.74% -> 98.08%. Both slices "
    "hold on their own: Fri 17-19h x2.76/x2.75, rollover 21:15-22:00 x4.06/x6.92. "
    "slip (fill beyond level) and low 60-bar volume look strong stand-alone (slip_15 x4.25/x9.54, low_vol60_30 x3.02/x2.40), but they "
    "mostly re-detect the close windows: beyond session_close slip adds only 3 losers, and low volume beyond session + slip is x1.62/x0.79 "
    "(nothing). bigfig_ahead10 (a 100-pip figure 0-1 pip past the level, the 1.1700 triple-top loss) is x2.34/x4.66 on 7 losers but fragile "
    "(selective only at the 1.0-pip cutoff; x1.90/x1.83 beyond the guard). "
    "EVERY chart-structure idea from my chart reading is NOT SELECTIVE (lift about 1 on both halves): selling right above the fresh low / "
    "buying under the fresh high (x0.91), exhaustion after a strong ADX leg (x1.72 train, x0.78 test; 48 ADX/trend/position combos tried, "
    "none hold on test), structure already broken (x1.04; plus a corrected version that reads the colour-setting hump from the camel state at "
    "its redraw bar, because camHV[k] is often the retracement's own high: x1.05/x0.79), micro-hump camel flips, bounce camel against the "
    "60-bar trend (x0.86), stale UHV, repeated tests of a floor, recent swing at the take-profit price, low-ATR Asia, news minutes "
    "12:30/14:00 UTC without a calendar. "
    "Out-of-sample check: a gradient-boosting model and a logistic regression trained on Mar-Jun over all ~70 features score test AUC 0.51 "
    "/ 0.60 on all trades (the 0.60 comes from the session/slip features) and 0.53 / 0.53 outside the session/slip trades. So the ~130 "
    "normal-hours losses cannot be told apart from winners at entry with anything measured here. 6 of my 21 losses are avoidable before "
    "entry (3 late-Friday, 1 Sunday-open dead tape, the 1.1700 big-figure buy, 1 dead pre-London tape via low_vol60_40); 15 are not. "
    "rule_ids lists only GOOD/EXCELLENT rules that remove the loss, found by running every rule on the blinded trade; non-selective flags are "
    "in agents/batch_3/loss_rule_hits.json. "
    "CAVEATS (hypotheses for MT5, not results; Python never promotes): (1) 20 of the 21 exit-code-8 losses are force-closes at Friday 20:58 "
    "UTC. If the MT5 EA does not flatten at that time, those trades end differently (held through the weekend gap, or win later); check this "
    "in the Strategy Tester before trusting the Friday lift. The rollover-hour spread blow-out comes from real ticks and is less exposed. "
    "(2) DST: the windows are fixed in UTC, but the NY rollover and weekly close move about 1 hour later in UTC after 1 Nov; the live version "
    "should be defined in New York time (17:00 NY close), and this data cannot validate the winter offset. (3) fill is the price after "
    "latency, so a slip rule cannot be evaluated at the break tick: live, implement it as a max-deviation / limit price on the order "
    "(ask <= level + 2 pips for buys, bid >= level - 2 pips for sells). (4) The api's tagged column was counted against 22 entries in early "
    "runs and 35 in the final export (loss_comments.json was updated at 05:14 during this session; I did not read it), so tagged counts in "
    "results_log.txt cannot be compared across runs. (5) The train half loses 3.36% vs 1.40% on test, and the buy-side fill-minus-level "
    "(about the spread) fell from about 0.5-0.6 pip to 0.2-0.3: the required favourable move (spread + 0.1 pip) shrank, which likely "
    "explains the base-rate drop. The strategy's loss rate looks spread-driven, worth an MT5 spread-stress run. "
    "Files: agents/batch_3/rules.py (all rules), results_log.txt (every api.report line), rules_scored.json, output_final.json, "
    "features.py + feat2-5.py, bins.py, overlap.py."
)
json.dump(D, open(os.path.join(HERE, "output_final.json"), "w", encoding="utf-8"), indent=1)
print("ok", len(D["losses"]), "losses", len(D["rules"]), "rules", len(json.dumps(D)), "bytes")
