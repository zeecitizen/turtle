"""build_output.py - turns final.json into the exact StructuredOutput payload (payload.json): corrected comments, cause labels,
avoidable_before_entry (true only where a GOOD/EXCELLENT rule removes the loss), docstring-free code re-verified by exec + api.score,
and the verdict string carrying the api.report numbers."""
import ast
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, LS)
import api  # noqa: E402

F = json.load(open(os.path.join(HERE, "final.json"), encoding="utf-8"))
notes = json.load(open(os.path.join(HERE, "notes.json"), encoding="utf-8"))

# ---- corrections after checking the outcome fields (advisor check 2)
notes["0714-113128-S"] = notes["0714-113128-S"].replace(
    "The market rallied straight to 1.1409; the stop filled with heavy slippage (-447$).",
    "The market rallied straight to 1.1409 within 30 min; 58 min after entry (about 12:30 UTC) the exit printed at 1.14400, 24 pips "
    "THROUGH the 1.14161 stop (-447$) - a gap consistent with a 12:30 UTC US data release (mid-month, CPI-like timing).")
notes["0706-140003-S"] = notes["0706-140003-S"].replace(
    "Mon 14:00:03 UTC (19:00 PKT) = 3 seconds after the US ISM Services PMI (10:00 ET, 3rd business day of July).",
    "Mon 14:00:03 UTC (19:00 PKT) = 3 seconds after 14:00 UTC, consistent with the US ISM Services release (10:00 ET, 3rd business "
    "day of July) - my reconstruction, not verified from a calendar.").replace(
    "into the release volatility: rallied to 1.1420 and on to the stop.",
    "and the market rallied 9 pips in 25 min to 1.1420; the stop was reached 3.2 h later at the stop price (no spike through it), so the "
    "clock is circumstantial here and the capitulation-low context matters as much.")
notes["0702-122937-S"] += " (Checked: the stop filled 27 s after entry, 1.9 pips through, i.e. at 12:30:04 UTC.)"
NEWS_NOTE = (" Avoidable in principle with an economic calendar (MQL5 CalendarValueHistory), but the clock-only proxy I could test "
             "(news_us_90s) is not selective on the train half (1 loser), so no tested rule removes it.")
for i in ("0702-122937-S", "0706-140003-S", "0715-132937-S"):
    notes[i] += NEWS_NOTE

CAUSE = {
    "0618-155020-B": "counter-structure (micro camel) - coin-flip",
    "0619-172628-S": "Friday afternoon / thin tape, weekend close",
    "0625-042616-B": "into resistance (multi-tested ceiling), thin Asia",
    "0629-060500-S": "counter-structure (micro camel at top of impulse)",
    "0629-221042-B": "market close (dead reopen hour, empty book)",
    "0701-115428-B": "into resistance (retest of broken range floor)",
    "0702-003706-S": "exhausted trend into support",
    "0702-122937-S": "news/spike (NFP 12:30 UTC)",
    "0703-040928-S": "holiday-thin tape, counter-structure - coin-flip",
    "0703-183524-B": "Friday close + wide spread (fill 1.3 pip over level)",
    "0706-004622-B": "into resistance (multi-tested ceiling)",
    "0706-140003-S": "news (14:00 UTC print) after capitulation low",
    "0708-213443-S": "market close (empty book, gap fill)",
    "0709-202905-S": "market close (pre-close thin tape)",
    "0714-113128-S": "counter-structure (climax V-reversal) + gap at 12:30",
    "0714-230041-S": "thin tape after reopen / chop",
    "0715-132937-S": "counter-trend into support, NYSE-open second",
    "0723-050736-B": "into resistance (triple top)",
    "0728-145636-S": "counter-structure (momentum burst sold)",
    "0730-074758-S": "into support (stalled base) - coin-flip",
    "0730-114430-S": "into support (double bottom, weak UHV)",
    "0731-170115-S": "Friday afternoon",
}

CLOCK_PROXY = ("; CLOCK PROXY: outside 20:00-23:00 UTC thin10<20 removes 26 trades and 0 losers - the empty book is the market reason "
               "behind the close/reopen effect, not an independent signal; its 11 losers sit on 8 days, train on 3 (4 from one Good-Friday "
               "3 April close cluster)")


def strip_doc(src):
    tree = ast.parse(src)
    fn = tree.body[0]
    if fn.body and isinstance(fn.body[0], ast.Expr) and isinstance(getattr(fn.body[0], "value", None), ast.Constant) \
            and isinstance(fn.body[0].value.value, str):
        fn.body = fn.body[1:] or [ast.Pass()]
    return ast.unparse(tree) + "\n"


rules_out, bad = [], 0
for r in F["rules"]:
    code = strip_doc(r["code"])
    ns = {"np": np, "math": math}
    exec(code, ns)                                                       # noqa: S102  (our own source)
    s = api.score(ns["rule"])
    ok = (s["all"]["lift"] == r["lift_all"] and s["train"]["lift"] == r["lift_train"] and s["test"]["lift"] == r["lift_test"]
          and s["all"]["losers_removed"] == r["losers_removed"] and s["all"]["winners_removed"] == r["winners_removed"])
    bad += (not ok)
    v = r["verdict"]
    if r["rule_id"].startswith("thin10_abs") or r["rule_id"] in ("thin30_abs20", "thin30_abs30", "thin5_abs20", "thin_any_abs"):
        if v.startswith("GOOD") or v.startswith("EXCELLENT"):
            v += CLOCK_PROXY
    rules_out.append({"rule_id": r["rule_id"], "idea": r["idea"], "code": code, "lift_all": r["lift_all"], "lift_train": r["lift_train"],
                      "lift_test": r["lift_test"], "losers_removed": r["losers_removed"], "winners_removed": r["winners_removed"],
                      "verdict": v + " | " + r["report"]})

losses_out = []
for L in F["losses"]:
    losses_out.append({"id": L["id"], "comment": notes[L["id"]], "cause": CAUSE[L["id"]],
                       "avoidable_before_entry": bool(L["rule_ids"]), "rule_ids": L["rule_ids"]})

batch_notes = open(os.path.join(HERE, "batch_notes.txt"), encoding="utf-8").read().strip()
payload = {"losses": losses_out, "rules": rules_out, "batch_notes": batch_notes}
json.dump(payload, open(os.path.join(HERE, "payload.json"), "w", encoding="utf-8"), indent=None, ensure_ascii=False)
json.dump(notes, open(os.path.join(HERE, "notes.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("rules", len(rules_out), "re-verify mismatches", bad, "losses", len(losses_out), "chars", len(json.dumps(payload, ensure_ascii=False)))
