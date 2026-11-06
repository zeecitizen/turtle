"""export.py - batch 6 deliverable builder. For every rule in rules.py: takes its source, renames the function to `rule`, exec()s it in a
clean namespace {np, math}, scores THAT with api.score and checks it equals the direct score; computes the verdict (GOOD: lift >= 2 on
train AND test and >= 4 losers; EXCELLENT: lift >= 4 on both); and for every batch-6 loss lists the GOOD/EXCELLENT rules that remove it.
Writes final.json next to this file.  py agents/batch_6/export.py"""
import inspect
import json
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, LS)
sys.path.insert(0, HERE)
import api  # noqa: E402
import rules  # noqa: E402

FILL = "uses t['fill'] (0.3 s after the trigger tick): implementable as a max-deviation / limit on the order, not as a pre-trade filter"
IDEA = {
    "rule_ceiling_tests2": "level already refused: 2+ swing points within 0.5 pip of the level in 60 bars and no close beyond it (multi-tested ceiling/floor)",
    "rule_close_2015_2230_minus_known": "20:15-22:30 UTC (thin hours around PrimeXBT's 21:00 close and the dead reopen hour), excluding the shipped 20:45-21:15 window = its increment",
    "rule_close_20_2130_minus_known": "20:00-21:30 UTC excluding the shipped 20:45-21:15 window",
    "rule_env3_union_minus_known": "env3_union (Friday>=18 / thin10<20 / fill 1.2+ pip beyond) outside the shipped close window",
    "rule_exhausted_adx60": "extended trend: ADX >= 60 at the last closed bar",
    "rule_exhausted_sell_stk3": "sells after 3+ red humps in a row (late trend)",
    "rule_exhausted_stk4": "late trend: 4+ humps of the trade colour in a row",
    "rule_exhausted_stk5": "late trend: 5+ humps of the trade colour in a row (0702-003706-S was RED x5, ADX 74)",
    "rule_friday_after15": "Friday from 15:00 UTC (weekend-close liquidity drain)",
    "rule_friday_after16": "Friday from 16:00 UTC",
    "rule_friday_after1630": "Friday from 16:30 UTC",
    "rule_friday_after16_minus_known": "Friday from 16:00 UTC outside the shipped close window (increment)",
    "rule_friday_after17": "Friday from 17:00 UTC (catches 0619-172628-S, 0703-183524-B, 0731-170115-S)",
    "rule_friday_after17_minus_known": "Friday from 17:00 UTC outside the shipped close window (increment)",
    "rule_friday_after18": "Friday from 18:00 UTC = the last 3 h before the weekend close (summer time): thin book, rounds left open are force-closed at the weekend (why 8)",
    "rule_friday_after18_minus_known": "Friday from 18:00 UTC outside the shipped close window (increment)",
    "rule_friday_after19": "Friday from 19:00 UTC",
    "rule_friday_any": "any Friday",
    "rule_impulse_against_10b_4atr": "the last 10 closed bars moved 4+ ATR against the trade (sell into a sharp rally / buy into a sharp drop)",
    "rule_news_1230_1400_only": "within 120 s before / 60 s after 12:30 or 14:00 UTC (US data prints in summer)",
    "rule_news_any_halfhour_2m": "within 120 s before / 60 s after any :00/:30 between 06:00 and 19:00 UTC",
    "rule_news_us_90s": "within 90 s before / 30 s after 12:30, 13:30 or 14:00 UTC (NFP 0702-122937-S, ISM 0706-140003-S, NYSE open 0715-132937-S)",
    "rule_overshoot_brk_0p3": "the breakout minute already printed 0.3+ pip beyond the level at the trigger (gap tick) - known at the trigger",
    "rule_overshoot_brk_0p4": "as above, 0.4+ pip",
    "rule_overshoot_brk_0p6": "as above, 0.6+ pip: a gap tick through the level in an empty book - known at the trigger",
    "rule_overshoot_fill_0p8": "fill 0.8+ pip beyond the level (wide spread / gap). " + FILL,
    "rule_overshoot_fill_1p2": "fill 1.2+ pip beyond the level (wide spread / gap; 0703-183524-B paid 1.3 pip, 0708-213443-S 1.3 pip). " + FILL,
    "rule_overshoot_fill_1p5": "fill 1.5+ pip beyond the level. " + FILL,
    "rule_overshoot_fill_2p0": "fill 2.0+ pip beyond the level. " + FILL,
    "rule_shallow_retrace_0p5": "the retracement is < 0.5 pip deep (no real pullback; 0714-230041-S had 0.2 pip)",
    "rule_spread_buy_1p0": "BUYS only: fill (ask) minus the breakout minute's bid high so far >= 1.0 pip = the spread at the trigger. " + FILL,
    "rule_thin10_abs15": "empty book: the last 10 closed bars average < 15 ticks/min",
    "rule_thin10_abs18": "empty book: the last 10 closed bars average < 18 ticks/min",
    "rule_thin10_abs20": "empty book: the last 10 closed bars average < 20 ticks/min (no counter-ticks, wide spread; 0708-213443-S had 5.5, 0709-202905-S 14)",
    "rule_thin10_abs20_minus_known": "thin10 < 20 outside the shipped close window (increment)",
    "rule_thin10_abs22": "the last 10 closed bars average < 22 ticks/min",
    "rule_thin10_abs25_minus_known": "thin10 < 25 outside the shipped close window (increment)",
    "rule_thin10_abs30": "the last 10 closed bars average < 30 ticks/min",
    "rule_thin10_abs35": "the last 10 closed bars average < 35 ticks/min",
    "rule_thin10_rel_day25": "the last 10 bars below 25% of the 24-hour average volume (relative thinness)",
    "rule_thin10_rel_day45": "the last 10 bars below 45% of the 24-hour average volume",
    "rule_thin30_abs20": "empty book: the last 30 closed bars average < 20 ticks/min",
    "rule_thin30_abs30": "the last 30 closed bars average < 30 ticks/min",
    "rule_thin30_abs50": "the last 30 closed bars average < 50 ticks/min",
    "rule_thin30_rel_day25": "the last 30 bars below 25% of the 24-hour average volume",
    "rule_thin5_abs20": "the last 5 closed bars average < 20 ticks/min",
    "rule_thin_rel60": "the 30-bar average below 60% of the 240-bar average",
    "rule_weak_uhv_085": "the 'UHV' is quieter than 0.85x the 30-bar average volume",
    "rule_weak_uhv_abs25": "the UHV candle has < 25 ticks",
    "rule_weak_uhv_abs30": "the UHV candle has < 30 ticks (a 'loudest' candle in a dead tape is not ultra-high volume)",
    "rule_weak_uhv_abs40": "the UHV candle has < 40 ticks",
}


def idea_of(name, fn):
    if name in IDEA:
        return IDEA[name]
    d = (fn.__doc__ or "").strip().replace("\n", " ")
    d = re.sub(r"\s+", " ", d)
    return d or name


def verdict(r):
    tr, te, a = r["train"], r["test"], r["all"]
    lt, le, nl = tr["lift"] or 0, te["lift"] or 0, a["losers_removed"]
    if nl >= 4 and lt >= 4 and le >= 4:
        v = "EXCELLENT"
    elif nl >= 4 and lt >= 2 and le >= 2:
        v = "GOOD"
    else:
        why = []
        if nl < 4:
            why.append(f"only {nl} losers")
        if lt < 2:
            why.append(f"train x{lt} ({tr['losers_removed']}L)")
        if le < 2:
            why.append(f"test x{le} ({te['losers_removed']}L)")
        v = "NOT SELECTIVE (" + ", ".join(why) + ")"
    if tr["losers_removed"] < 2 or te["losers_removed"] < 2:
        v += " [<2 losers in one half: thin evidence]"
    return v


def line(r, name):
    a, tr, te = r["all"], r["train"], r["test"]
    return (f"{name}: removes {a['removed']} (losers {a['losers_removed']} / winners {a['winners_removed']})  loss rate among removed "
            f"{a['loss_rate_removed']}% vs base {a['base_loss_rate']}%  lift x{a['lift']} | train x{tr['lift']} ({tr['losers_removed']}L/"
            f"{tr['winners_removed']}W)  test x{te['lift']} ({te['losers_removed']}L/{te['winners_removed']}W) | WR {a['wr_after']}%  net "
            f"{a['net_change_usd_1lot']:+,.0f}$ | Zee's 22: {r['tagged_out']}")


if __name__ == "__main__":
    B = json.load(open(os.path.join(LS, "batch_6.json"), encoding="utf-8"))
    byid = {t["id"]: t for t in api.TRADES}
    notes = json.load(open(os.path.join(HERE, "notes.json"), encoding="utf-8"))
    names = [n for n, f in inspect.getmembers(rules, inspect.isfunction) if n.startswith("rule_")]
    out_rules, good_fns = [], {}
    mism = 0
    for n in names:
        fn = getattr(rules, n)
        src = inspect.getsource(fn)
        code = re.sub(r"^def " + re.escape(n) + r"\(", "def rule(", src, count=1)
        ns = {"np": np, "math": math}
        exec(code, ns)                                                   # noqa: S102  (our own source)
        r_exec = api.score(ns["rule"])
        r_dir = api.score(fn)
        same = json.dumps(r_exec, sort_keys=True) == json.dumps(r_dir, sort_keys=True)
        mism += (not same)
        v = verdict(r_exec)
        rid = n[len("rule_"):]
        out_rules.append({"rule_id": rid, "idea": idea_of(n, fn), "code": code, "lift_all": r_exec["all"]["lift"],
                          "lift_train": r_exec["train"]["lift"], "lift_test": r_exec["test"]["lift"],
                          "losers_removed": r_exec["all"]["losers_removed"], "winners_removed": r_exec["all"]["winners_removed"],
                          "verdict": v, "report": line(r_exec, rid), "exec_matches_direct": same})
        if v.startswith("GOOD") or v.startswith("EXCELLENT"):
            good_fns[rid] = ns["rule"]
        print(f"{'OK ' if same else 'MISMATCH '}{v[:60]:60s} {line(r_exec, rid)[:200]}")
    losses = []
    for L in B["losses"]:
        t = api._blind(byid[L["id"]])
        hit = [rid for rid, f in good_fns.items() if f(t, api.A)]
        losses.append({"id": L["id"], "comment": notes[L["id"]], "rule_ids": hit})
    json.dump({"rules": out_rules, "losses": losses}, open(os.path.join(HERE, "final.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("exec/direct mismatches:", mism)
    for L in losses:
        print(L["id"], L["rule_ids"])
