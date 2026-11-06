"""build_payload.py - the workflow's structured answer (rules with exact source + the exact api_tight.report line, per-loss comments),
assembled from rules.py, report_lines.txt and per_loss.json so nothing is retyped. Writes payload.json."""
import inspect
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import rules as RL  # noqa: E402

IDEA = {
    "rule_range_bound120": "RANGE: skip when the last 120 closed candles span < 9.2 ATR (base-train 20th pct; engine twin InpUhvSafeRangeAtr=9.2 + "
                           "InpUhvSafeRangeBars=120). Best on secure (engine 98.66->99.00%, train 97.92->98.50, test 99.32->99.46) and significant on "
                           "secure train (lift 2.10, p=0.029) and base train (1.40, p=0.041), BUT base test lift 0.81 (0.66 beyond the existing guards, "
                           "WR 98.60->98.53), tight 99.44->99.28, secure-test lift 1.76 (p=0.24) is below the random control's 2.55, and its O/E trend "
                           "is noise against both random-entry nulls (perm p 0.21 / 0.96). FAILS: does not travel to the base test half.",
    "rule_extended_run120": "EXTENSION: skip when the level is > 19.2 pips beyond the 2-hour opposite extreme (base-train 80th pct). Its family "
                            "(run120 / mv60 / pos120) had the only significant O/E dose-response against the +-90-min null (run120 p=0.003 after 141 "
                            "features) - and it VANISHED against the path-free other-days null (best feature p=0.14): random entries placed inside the "
                            "same run-up won because of it. Raw lifts: secure 0.90 / 1.07, base 1.25 / 0.89 (0.96 / 0.90 beyond guards). FAILS.",
    "rule_with_move60": "MOMENTUM EXTENSION: skip when the last 60 closes moved > 8.1 pips with the trade (base-train 80th pct). Nudges the win rate up in "
                        "all four cells (secure +0.13, base +0.10) but no cell is significant (p 0.17-0.48), the secure gain is below the random-20% "
                        "control (+0.18), and beyond the existing guards base train lift drops to 0.82 (WR 96.64->96.49). FAILS.",
    "rule_congested_level": "DOUBLE / TRIPLE TOP: skip when >= 6 confirmed 3-bar swing extremes (older than the UHV, last 240 bars) sit within 1 pip of "
                            "the level (base-train 80th pct). The charts' commonest story (0309, 0414, 0526, 1019, 1023 ...), but the winning twins show "
                            "the same picture (0309-075007-B, 1023-141514-B bought the very same tops and won). Lifts secure 1.23 / 1.28, base 0.84 / "
                            "1.13 (0.87 / 0.88 beyond guards). FAILS.",
    "rule_news_clock": "NEWS CLOCK (no calendar): skip breakout ticks at minute :56-:03 or :25-:30. Lifts all four cells (secure 98.66->99.05, base "
                       "97.74->97.96) BUT the windows were picked from the 30 losses' own timestamps (data-snooped); different sub-windows carry different "
                       "cells (:25-:30 only in train - secure 4.3%, base 5.4%; :56-:03 only in base test 2.4% vs 1.2%, flat in base train); secure test "
                       "gains +0.02 (lift 1.09); beyond the existing guards the base lifts are 1.13 / 1.16 (p=0.26 / 0.31). Its only significant cell "
                       "(secure train, p=0.015) is the one it was read from. FAILS as a rule; a real economic calendar (MQL5 CalendarValueHistory) is "
                       "the proper test of 0831-140012-S / 1002-121909-S / 0527-123600-B.",
    "rule_chop120": "CHOP: skip when the efficiency ratio of the last 120 closes < 0.031 (base-train 20th pct). Secure lifts 1.60 / 1.21 (n.s.), base "
                    "1.06 / 0.80 (1.03 / 0.74 beyond guards; base test WR 98.60->98.53). FAILS.",
    "rule_wide_spread_now": "SPREAD vs ITS OWN HOUR: skip when the breakout spread is > 0.05 pip above the 60-candle median per-minute spread (sim sp1; "
                            "regime-free across the June spread cut 0.55 -> 0.14 pip). Mechanically sound (the bid must climb spread + 0.1 pip to win) "
                            "and base lifts 1.81 (p=0.005) / 1.34 - but that lift is entirely the rollover hour and >= 1-pip spreads the secure setting "
                            "already blocks (beyond them 1.22 / 0.74), and on secure it does nothing (0.92 / 1.14; secure train WR 97.92->97.90). FAILS.",
    "control_random20": "CONTROL, not a rule: a pseudo-random 20% skip (crc32 of the id). Secure 98.66->98.84 and secure-test lift 2.55 (p=0.074) by luck "
                        "alone - the noise floor any rule must beat with 30 losses; base 97.74->97.57.",
}
lines = {}
for ln in open(os.path.join(HERE, "report_lines.txt"), encoding="utf-8"):
    nm = ln.split("|")[0].strip()
    if "|" in ln and nm in IDEA:
        lines[nm] = ln.rstrip("\n")
out = {"rules": [{"name": r.__name__, "idea": IDEA[r.__name__], "code": inspect.getsource(r), "report_line": lines[r.__name__],
                  "generalises": False} for r in RL.RULES],
       "per_loss": json.load(open(os.path.join(HERE, "per_loss.json"), encoding="utf-8"))}
assert len(out["rules"]) == 8 and all(x["report_line"] for x in out["rules"]) and len(out["per_loss"]) == 30
json.dump(out, open(os.path.join(HERE, "payload.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(out["rules"]))
