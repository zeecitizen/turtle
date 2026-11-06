"""build_payload.py (batch_8) - assembles the batch's final answer (losses + rules + notes) from loss_comments_b8.json and final_rules.json,
writes payload.json, then RE-EXECS every rule's code string from payload.json in a fresh {np, math} namespace and asserts api.score
reproduces the lifts / counts written in the payload. Run from research/loss_study:  py agents/batch_8/build_payload.py"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, LS)
import api  # noqa: E402

IDEA = {
    "fri_after_16ny": "Friday after 16:00 New York (last hour of the week): a round still open at the 16:58 NY weekly close is force-closed at a loss.",
    "fri_after_15ny": "Friday after 15:00 New York (last 2 hours of the week).",
    "fri_after_14ny": "Friday after 14:00 New York (last 3 hours): liquidity drains into the weekend and slow rounds hit the weekly close.",
    "fri_after_13ny": "Friday after 13:00 New York (last 4 hours of the week).",
    "fri_after_12ny": "Friday after 12:00 New York.",
    "fri_after_08ny": "The whole Friday US session (from 08:00 NY): US data at 08:30 NY (NFP, PCE...) plus the afternoon drain into the weekly close. Catches more at a lower lift.",
    "last_15min_of_week": "Friday 16:45-17:00 New York: the last 15 minutes before the weekly close - the round cannot finish.",
    "rollover_mon_thu": "Sun-Thu 16:45-18:00 New York (20:45-22:00 UTC in summer), incl. Sunday's weekly-open hour: the daily rollover - spreads blow out, book is thin, a break is a quote wobble.",
    "close_and_rollover": "THE CLOCK RULE: Friday after 14:00 NY OR the daily rollover 16:45-18:00 NY (Sun-Thu). New York time, so it follows US DST.",
    "fri14_beyond_noclose_band": "fri_after_14ny minus the engine's existing InpUhvNoClose band (20:45-21:15 UTC daily, off in this setting): what it adds beyond the switch Zee has.",
    "rollover_beyond_noclose_band": "rollover_mon_thu minus the existing 20:45-21:15 UTC band.",
    "last15_beyond_noclose_band": "last_15min_of_week minus the existing 20:45-21:15 UTC band (only winter-time weeks can differ).",
    "clock_beyond_noclose_band": "close_and_rollover minus the existing 20:45-21:15 UTC band: the clock rule's contribution beyond the switch Zee already has.",
    "sunday_open": "Sunday evening New York (first hours after the weekly open, thin book). From batch 8: 10-04 23:03 UTC buy.",
    "pre_us_data": "The 30 minutes before 08:30 New York on weekdays (US data). From batch 8: 10-02 NFP sell, 10-30 buy 6 min before 08:30 NY.",
    "pre_us_data_10": "The 10 minutes before 08:30 New York on weekdays.",
    "nfp_window": "First Friday of the month 08:00-09:30 New York (payrolls) - the calendar-correct version of pre_us_data; day-of-month by integer civil-date maths.",
    "big_figure_ahead": "The UHV level is <= 1.0 pip short of a big figure (1.1200, 1.1300) in the trade direction: the break must push through the figure's resting orders to make 0.1 pip + spread. From batch 8: 10-26 15:59 buy 1.11999 under 1.1200 (5 candles capped at 1.1200).",
    "big_figure_ahead_15": "big_figure_ahead widened to 1.5 pips.",
    "big_figure_ahead_fill05": "A big figure <= 0.5 pip in front of the FILL.",
    "big_figure_beyond_clock": "big_figure_ahead on trades the clock rule does not already skip: its own contribution.",
    "ten_pip_line_ahead": "Any 10-pip line <= 0.3 pip in front of the level.",
    "half_figure_ahead": "A half figure (x.xx50, not a big figure) <= 1 pip in front of the level.",
    "fill_overshoot_15": "The fill came > 1.5 pips beyond the level (buy: spread + 0.3 s jump; sell: the jump) - a blown-out spread or a spike. Implementable as max order deviation.",
    "fill_overshoot_10": "fill_overshoot at 1.0 pip.",
    "fill_overshoot_20": "fill_overshoot at 2.0 pips.",
    "fill_overshoot_beyond_clock": "fill_overshoot_15 on trades the clock rule does not already skip.",
    "fill_overshoot20_beyond_clock": "fill_overshoot_20 on trades the clock rule does not already skip.",
    "ceiling_just_ahead": "Double top / bottom right in front of the entry: a p=2 swing high (buy) / low (sell) of the last 60 bars within -0.2..+0.6 pip of the level (batch 8: 10-01, 10-08, 10-26 07:48 buys under equal highs).",
    "hump_needs_hh": "Zee's camel fix as a skip filter, pivot version: last two p=1 swing highs AND lows must step with the trade (HH+HL buy / LH+LL sell).",
    "hump_camel_replay": "Zee's camel fix as a skip filter, exact camel replay (600 bars to k): the latest completed hump must be a higher low AND a higher high (buy) / lower low AND lower high (sell). Batch 8: 10-07 06:31 and 10-15 08:58 green humps with lower highs.",
    "counter_trend_60": "A fresh x1 camel against the hour: price moved > 10 pips against the trade over the last 60 bars.",
    "mature_trend": "Six or more humps of the trade's colour in a row (an old trend; batch 8: 10-02 RED x5, 10-13 RED x4).",
    "quiet_hour": "Median tick volume of the last 60 bars < 40 (a dead market; batch 8: 10-04, 10-12, 10-13).",
    "uhv_is_last_candle": "The UHV is the last closed candle (k == ku): a one-candle 'retracement' (batch 8: 10-02 17:19 sell after a hammer).",
    "shallow_retracement": "UHV level < 0.8 pip from the retracement extreme: a microscopic pullback (batch 8: 10-12 07:37 buy, 0.4 pip).",
    "clock_bigfig_overshoot": "close_and_rollover OR big_figure_ahead OR fill_overshoot_15 - everything selective from batch 8 together.",
}

VERDICT = {
    "fri_after_16ny": "EXCELLENT (but 8 of its 11 losers are forced weekly-close exits, why=8: depends on the MT5 EA flattening at the close like the sim)",
    "fri_after_15ny": "EXCELLENT (11 of 14 losers are weekly-close exits)",
    "fri_after_14ny": "EXCELLENT (14 of 18 losers are weekly-close exits; beyond the existing 20:45-21:15 UTC band it fails test, 1.46 - see fri14_beyond_noclose_band)",
    "fri_after_13ny": "GOOD (17 of 22 losers are weekly-close exits)",
    "fri_after_12ny": "GOOD (17 of 24 losers are weekly-close exits)",
    "fri_after_08ny": "GOOD (catches 6 of batch 8's 22 losses incl. both US-data Fridays; 20 of 36 losers are weekly-close exits)",
    "last_15min_of_week": "EXCELLENT (tiny n, 8L/14W; already inside the engine's 20:45-21:15 UTC band in summer time)",
    "rollover_mon_thu": "GOOD (all 8 removed losers are real 20-pip stop-outs, why=1)",
    "close_and_rollover": "EXCELLENT (the recommended clock rule; 12 of its 26 losers are stop-outs, 14 weekly-close exits)",
    "fri14_beyond_noclose_band": "NOT SELECTIVE (beyond the existing band: test 1.46)",
    "rollover_beyond_noclose_band": "GOOD (5 losers, all stop-outs; small n)",
    "last15_beyond_noclose_band": "NOT SELECTIVE (no trades beyond the band in this data; under winter time the UTC band misses the close by an hour)",
    "clock_beyond_noclose_band": "GOOD (what the clock rule adds beyond the existing band: 15 losers, 3.59/2.82)",
    "sunday_open": "NOT SELECTIVE",
    "pre_us_data": "NOT SELECTIVE (1.57/1.99 - needs a real news calendar)",
    "pre_us_data_10": "NOT SELECTIVE",
    "nfp_window": "NOT SELECTIVE (3 losers, insufficient n; train 1.75)",
    "big_figure_ahead": "GOOD (raw; beyond the clock only 4L/79W at 1.99/1.88 - fragile: 7 losers, found after ~50 grid variants)",
    "big_figure_ahead_15": "NOT SELECTIVE (train 1.73)",
    "big_figure_ahead_fill05": "GOOD (4 losers only - small n, overlaps big_figure_ahead)",
    "big_figure_beyond_clock": "NOT SELECTIVE (borderline 1.99/1.88)",
    "ten_pip_line_ahead": "NOT SELECTIVE (train 1.80)",
    "half_figure_ahead": "NOT SELECTIVE",
    "fill_overshoot_15": "EXCELLENT (raw; but 7 of its 11 losers sit in the clock windows - beyond the clock 3L/45W at 1.80/4.77)",
    "fill_overshoot_10": "NOT SELECTIVE (train 1.99)",
    "fill_overshoot_20": "EXCELLENT (raw, 8 losers; beyond the clock only 3 losers)",
    "fill_overshoot_beyond_clock": "NOT SELECTIVE (3 losers, train 1.80)",
    "fill_overshoot20_beyond_clock": "NOT SELECTIVE (3 losers, insufficient n)",
    "ceiling_just_ahead": "NOT SELECTIVE (0.94 - equal highs ahead are as common in winners)",
    "hump_needs_hh": "NOT SELECTIVE (0.97)",
    "hump_camel_replay": "NOT SELECTIVE (1.05; a skip filter cannot score the detector change itself - that needs the engine + MT5)",
    "counter_trend_60": "NOT SELECTIVE (0.66 - counter-trend entries lose LESS)",
    "mature_trend": "NOT SELECTIVE (test 1.05)",
    "quiet_hour": "NOT SELECTIVE (train 1.73; the quiet-market effect vanishes once the clock windows are removed)",
    "uhv_is_last_candle": "NOT SELECTIVE (1.03)",
    "shallow_retracement": "NOT SELECTIVE (0.66)",
    "clock_bigfig_overshoot": "GOOD (3.26/3.87, 33 losers - almost all of it is the clock)",
}

NOTES = (
    "HYPOTHESIS ONLY - NOT PROMOTED. Python tick replay; per CLAUDE.md only MT5's Strategy Tester (or live fills) may promote any of this. "
    "Lift and loss/win counts only, no win-rate or $ claims.\n"
    "WHAT I SAW: all 22 charts + 44 twins. None of the 22 ever moved the 0.1 pip + spread the target needs (that is what a loss is here); "
    "19 were full stop-outs and 3 forced weekly-close exits. The fill was the extreme of the next ~20 pips, so these are failed "
    "breakouts at the first tick. Read by eye, they look like double tops/floors, "
    "lower-high green humps, counter-structure x1 camels, climax re-tests and dead tapes. Every one of those ideas, coded and scored "
    "across all 7,626 trades, sits at lift 0.66-1.1: the twins carry the same picture. That covers equal highs/lows ahead, Zee's HH+HL "
    "camel fix (pivot and exact camel-replay versions), counter-trend, mature trend, shallow retracement, UHV = last candle, quiet market, "
    "breakout-minute pace and dip, efficiency ratio, spike nearby, and volume ratios. Two more were tested in pandas only: re-entry at the "
    "same level as an earlier trade within 15-120 min (about 1.0), and loss clustering after a recent loss (1.0-1.3).\n"
    "WHAT SEPARATES: THE CLOCK. close_and_rollover (Friday after 14:00 New York OR Sun-Thu 16:45-18:00 New York) removes 26L/258W, lift "
    "4.06 (train 4.14 / test 4.23).\n"
    "RECOMMENDATION, in order: (1) The engine already has a switch, InpUhvNoClose (20:45-21:15 UTC). It is OFF in this setting (absent "
    "from the saved inputs). It should be redefined in New York time: the UTC band has been an hour early since US DST ended on 1 Nov, "
    "because the weekly close and rollover moved to ~22:00 UTC. (2) Beyond that band, the clock rule adds 15L/195W (train 3.59 / test "
    "2.82). (3) The Friday>=14:00 NY part alone fails test beyond the band (1.46). The rollover part holds: 5L/45W (2.84/7.40), all real "
    "stop-outs. (4) 14 of the 18 Friday>=14 NY losers are FORCED weekly-close exits (why=8, partial losses), not stops. The Friday rule's "
    "value therefore depends on the MT5 EA flattening at the weekly close the way the sim does.\n"
    "SECONDARY (fragile): big_figure_ahead (level <= 1 pip short of 1.1200/1.1300...) scores 7L/83W at 2.53/4.99. Beyond the clock it is "
    "4L/79W at 1.99/1.88, found after ~50 grid variants, so it is a market-sensible hypothesis, not a result. fill_overshoot_15/20 (fill "
    "> 1.5/2 pips past the level) looks EXCELLENT raw but is mostly rollover spreads in disguise: beyond the clock only 3 losers.\n"
    "BATCH 8: 2 losses are pure market close (10-09, 10-16), caught by EXCELLENT rules. 1 is the big figure (10-26 15:59). 4 more are "
    "caught only by the weaker fri_after_08ny (GOOD 2.21/2.88): the NFP sell on 10-02, the post-NFP sell on 10-02, the forced close on "
    "10-23, and the pre-08:30-NY buy on 10-30. 15 are not caught by anything selective, and I say so plainly in each comment.\n"
    "REGIME NOTE: the loss rate was ~4% in Mar-May, when the buy fill-over-level (spread proxy) was ~0.7 pip, and ~1.5% in Jun-Nov at "
    "~0.2 pip. A 0.1-pip target is that sensitive to the broker spread, which is exactly why the MT5 run with real spreads decides.\n"
    "Files (agents/batch_8/): rules.py (every rule, self-contained), verify_rules.py (exec + score each rule's own source), "
    "build_payload.py, final_rules.json, payload.json, loss_comments_b8.json, features.py / features2.py (blind feature tables used for "
    "the search)."
)


def main():
    comments = json.load(open(os.path.join(HERE, "loss_comments_b8.json"), encoding="utf-8"))
    rules = json.load(open(os.path.join(HERE, "final_rules.json"), encoding="utf-8"))
    losses = [{"id": c["id"], "comment": c["comment"], "cause": c["cause"], "avoidable_before_entry": c["avoidable_before_entry"],
               "rule_ids": c["rule_ids"]} for c in comments]
    rows = []
    for r in rules:
        s = r["score"]
        a, tr, te = s["all"], s["train"], s["test"]
        rows.append({"rule_id": r["rule_id"], "idea": IDEA[r["rule_id"]], "code": r["code"], "lift_all": a["lift"], "lift_train": tr["lift"],
                     "lift_test": te["lift"], "losers_removed": a["losers_removed"], "winners_removed": a["winners_removed"],
                     "verdict": VERDICT[r["rule_id"]]})
        assert VERDICT[r["rule_id"]].split(" (")[0] in ("GOOD", "EXCELLENT", "NOT SELECTIVE"), r["rule_id"]
    payload = {"losses": losses, "rules": rows, "batch_notes": NOTES}
    json.dump(payload, open(os.path.join(HERE, "payload.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    # re-verify from payload.json itself
    P = json.load(open(os.path.join(HERE, "payload.json"), encoding="utf-8"))
    for row in P["rules"]:
        ns = {"np": np, "math": math}
        exec(row["code"], ns)
        sc = api.score(ns["rule"])
        assert sc["all"]["lift"] == row["lift_all"] and sc["train"]["lift"] == row["lift_train"] and sc["test"]["lift"] == row["lift_test"], row["rule_id"]
        assert sc["all"]["losers_removed"] == row["losers_removed"] and sc["all"]["winners_removed"] == row["winners_removed"], row["rule_id"]
    print("payload.json OK:", len(P["losses"]), "losses,", len(P["rules"]), "rules re-verified from their own code strings")


if __name__ == "__main__":
    main()
