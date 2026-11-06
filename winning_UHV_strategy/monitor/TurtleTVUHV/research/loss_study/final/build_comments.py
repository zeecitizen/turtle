"""build_comments.py - writes claude_loss_comments.json: every one of the 172 losses of the 97.7% setting with Claude's chart comment (the eight
analysts' comments, merged), a cause from ONE fixed taxonomy, and which final rules skip it - filled by RUNNING rules_final.py on the blind
trade, not copied from the analysts' rule_ids (they used their own rule sets and criteria; their flag is kept as analyst_*).

Fields per loss:
  id, batch, side, entry_utc, entry_ny, exit ('stop' / 'weekly-close flatten'), pnl_usd_1lot, stop_pips, trigger_spread_pips
  comment                      the analyst's chart reading (Claude subagent), verbatim
  cause / cause_class          one of the 8 classes below (cause = readable label); cause_detail = the analyst's free text
  avoidable_before_entry       True only if rule_combined skips it (a proven, pre-entry rule)
  removed_by                   ACCEPTED final rules (and rule_combined) that skip it
  mt5_candidates_that_skip_it  rules selective alone but NOT proven beyond rule_combined (rules_final.CANDIDATES)
  rejected_rules_that_skip_it  rules that fail the strict bar (rules_final.REJECTED) - listed for transparency, not as fixes
  verdict                      Claude's one-paragraph conclusion for this loss
  analyst_avoidable_before_entry / analyst_rule_ids   the batch analyst's own call
Python tick replay = HYPOTHESIS, NOT PROMOTED. Run: py research/loss_study/final/build_comments.py"""
import collections
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(HERE)
sys.path.insert(0, LS)
sys.path.insert(0, HERE)
import api  # noqa: E402
import rules_final as R  # noqa: E402

SRC = {1: "agents/batch_1/final_output.json", 2: "agents/batch_2/payload.json", 3: "agents/batch_3/output_final.json",
       5: "agents/batch_5/final_output.json", 6: "agents/batch_6/payload.json", 7: "agents/batch_7/structured_output.json",
       8: "agents/batch_8/payload.json"}
LABEL = {"weekly_close": "market close (Friday / weekly close)",
         "rollover_dead_book": "daily rollover / dead book (incl. the Sunday open)",
         "news_spike": "news / spike",
         "bad_fill": "bad fill (latency spike / stop-run tick)",
         "support_resistance": "into support / resistance",
         "counter_structure": "counter-structure / camel misread",
         "exhausted_move": "exhausted move / climax",
         "no_separator_chop": "chop / dead range / no separator"}
CLASS = """
0306-084826-B support_resistance  0306-102926-B bad_fill            0306-212806-B weekly_close        0309-043015-S counter_structure
0309-080004-B support_resistance  0310-004311-B exhausted_move      0310-055001-S support_resistance  0310-141312-S support_resistance
0311-001150-S counter_structure   0311-135106-S news_spike          0312-062215-S counter_structure   0312-172306-B no_separator_chop
0313-195816-B weekly_close        0316-052008-B counter_structure   0316-132404-S counter_structure   0316-163307-S support_resistance
0316-200548-B rollover_dead_book  0317-062554-S exhausted_move      0318-120215-B support_resistance  0318-205350-S rollover_dead_book
0318-230007-S counter_structure   0319-022714-B support_resistance  0319-072453-B support_resistance  0319-155047-S support_resistance
0319-184909-S news_spike          0320-143152-S exhausted_move      0320-194940-S counter_structure   0322-214022-S rollover_dead_book
0322-233112-B exhausted_move      0324-165033-B support_resistance  0324-201018-S news_spike          0324-205001-S rollover_dead_book
0325-011150-B no_separator_chop   0325-132000-B counter_structure   0326-120509-S exhausted_move      0331-222340-S rollover_dead_book
0402-040451-B support_resistance  0403-204101-S weekly_close        0403-204417-S weekly_close        0403-205318-S weekly_close
0403-205500-B weekly_close        0406-143818-B support_resistance  0406-183009-B exhausted_move      0407-071138-S counter_structure
0408-075606-B support_resistance  0409-062811-S exhausted_move      0409-110305-S support_resistance  0410-122837-S news_spike
0413-064826-S exhausted_move      0413-120919-S support_resistance  0413-182648-S no_separator_chop   0414-025520-S no_separator_chop
0414-082354-S support_resistance  0416-045923-B counter_structure   0417-084606-S counter_structure   0417-183109-B weekly_close
0417-205800-B weekly_close        0421-151800-B counter_structure   0423-140702-S news_spike          0423-164516-B counter_structure
0424-095824-S support_resistance  0424-183049-S weekly_close        0426-222526-S rollover_dead_book  0427-150215-B counter_structure
0428-085748-B counter_structure   0428-132716-S counter_structure   0429-032518-B no_separator_chop   0429-162638-B support_resistance
0501-063713-S news_spike          0501-161803-B weekly_close        0504-035759-B exhausted_move      0504-193208-B support_resistance
0505-051831-S support_resistance  0506-114136-B support_resistance  0508-170307-S weekly_close        0511-120949-S exhausted_move
0512-195506-B support_resistance  0513-071801-B counter_structure   0514-070500-B support_resistance  0514-125507-B support_resistance
0514-213120-B rollover_dead_book  0515-041219-B no_separator_chop   0515-173859-B weekly_close        0518-010308-S support_resistance
0519-124205-B support_resistance  0519-151057-S exhausted_move      0521-184100-B no_separator_chop   0522-142204-S exhausted_move
0522-192405-B weekly_close        0526-111253-B support_resistance  0526-155742-S support_resistance  0527-123601-B news_spike
0528-060001-S counter_structure   0529-012744-B support_resistance  0529-094113-S counter_structure   0602-024909-S no_separator_chop
0602-144644-B support_resistance  0603-051526-B no_separator_chop   0604-074634-S exhausted_move      0605-061830-S support_resistance
0605-132528-B counter_structure   0608-094151-S exhausted_move      0610-231702-S support_resistance  0612-153531-B support_resistance
0615-152117-B counter_structure   0617-205108-S rollover_dead_book  0618-132315-S support_resistance  0618-155020-B counter_structure
0619-172628-S weekly_close        0625-042616-B support_resistance  0629-060500-S counter_structure   0629-221042-B rollover_dead_book
0701-115428-B support_resistance  0702-003706-S exhausted_move      0702-122937-S news_spike          0703-040928-S counter_structure
0703-183524-B weekly_close        0706-004622-B support_resistance  0706-140003-S news_spike          0708-213443-S rollover_dead_book
0709-202905-S rollover_dead_book  0714-113128-S counter_structure   0714-230041-S rollover_dead_book  0715-132937-S counter_structure
0723-050736-B support_resistance  0728-145636-S counter_structure   0730-074758-S support_resistance  0730-114430-S support_resistance
0731-170115-S weekly_close        0804-172345-S counter_structure   0807-083652-S no_separator_chop   0807-205630-S weekly_close
0812-151608-B counter_structure   0813-223116-S rollover_dead_book  0814-155646-B support_resistance  0820-213103-S rollover_dead_book
0821-130310-B counter_structure   0827-133401-B exhausted_move      0828-205744-B weekly_close        0831-140013-S news_spike
0902-131622-S news_spike          0904-131422-S news_spike          0908-165924-S support_resistance  0911-180812-B support_resistance
0914-213535-B rollover_dead_book  0918-162342-S counter_structure   0918-204909-B weekly_close        0923-111835-B counter_structure
0925-113553-B bad_fill            0929-030326-B counter_structure   1001-061805-B support_resistance  1002-121910-S news_spike
1002-133626-S counter_structure   1004-230306-B rollover_dead_book  1006-101510-S support_resistance  1007-013110-B counter_structure
1007-091004-B counter_structure   1008-064604-B support_resistance  1009-205809-S weekly_close        1012-023747-B no_separator_chop
1013-043630-S support_resistance  1015-035806-B counter_structure   1016-205727-B weekly_close        1019-171329-S support_resistance
1023-145031-B weekly_close        1026-024856-B exhausted_move      1026-105900-B support_resistance  1026-172601-B exhausted_move
1027-163522-B support_resistance  1030-122421-B news_spike          1102-003016-S counter_structure   1104-082902-S counter_structure
"""
CLS = dict(zip(CLASS.split()[0::2], CLASS.split()[1::2]))
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ------------------------------------------------------------------------------------------ the analysts' comments, all 172
ana = {}
for b, f in SRC.items():
    for x in json.load(open(os.path.join(LS, f), encoding="utf-8"))["losses"]:
        ana[x["id"]] = dict(x, batch=b)
for x in json.load(open(os.path.join(HERE, "batch4_comments.json"), encoding="utf-8")):
    ana[x["id"]] = dict(x, batch=4)
LOSSES = [t for t in api.TRADES if not t["win"]]
ids = {t["id"] for t in LOSSES}
assert len(LOSSES) == 172 and set(ana) == ids, (len(LOSSES), len(set(ana) ^ ids))
assert set(CLS) == ids and all(c in LABEL for c in CLS.values()), set(CLS) ^ ids


def fires(rule, t):
    try:
        return bool(rule(api._blind(t), api.A))
    except Exception:                                       # noqa: BLE001 (a rule that cannot judge keeps the trade - same as api.score)
        return False


out = []
for t in sorted(LOSSES, key=lambda z: z["t_in"]):
    a = ana[t["id"]]
    d, m = R.ny_clock(t["t_in"])
    ny = f"{DOW[d]} {int(m // 60):02d}:{int(m % 60):02d} NY"
    exit_ = "stop" if t["why"] == 1 else "weekly-close flatten" if t["why"] == 8 else f"exit code {t['why']}"
    acc = [r.__name__ for r in R.ACCEPTED if fires(r, t)]
    comb = fires(R.rule_combined, t)
    removed_by = acc + (["rule_combined"] if comb else [])
    cand = [r.__name__ for r in R.CANDIDATES if fires(r, t)]
    rej = [r.__name__ for r in R.REJECTED if fires(r, t)]
    spr = R._trigger_spread(t["id"])
    # ---- Claude's verdict for this loss
    if comb:
        v = (f"AVOIDABLE before entry: rule_rollover_ny skips it - it was entered {ny}, inside the 16:45-17:45 New York rollover window "
             f"(from 15 minutes before the 17:00 NY rollover to 45 minutes after it), where the spread blows out and the 0.1-pip target becomes a "
             f"multi-pip one.")
        if t["why"] == 8:
            v += (f" This loss was the engine's weekly-close flatten ({t['pnl']:+.0f}$), not a stop: in MT5 the EA may hold it over the weekend "
                  f"instead, so its real outcome is unknown - but the entry itself should not happen.")
    elif cand:
        why_c = {"rule_trigger_spread": f"its breakout tick had a {spr:.1f}-pip spread (>= 1.0)",
                 "rule_friday_close_ny": "it was entered in Friday's last hour before the weekly flatten",
                 "rule_empty_book": "the last 10 candles averaged under 20 ticks a minute"}
        v = ("Not avoidable with a PROVEN rule. MT5 candidates would skip it (" + "; ".join(f"{c}: {why_c[c]}" for c in cand) + "), "
             "but none of them holds beyond the rollover guard on both halves of the data, so treat that as a hypothesis for MT5, not a fix.")
        if t["why"] == 8:
            v += f" It was the engine's weekly-close flatten ({t['pnl']:+.0f}$), not a stop."
    else:
        v = ("Not avoidable before entry with anything measured. "
             + (f"Rules that would skip it ({', '.join(rej)}) remove winners at about the same rate, so they are not fixes. " if rej else "")
             + "Its winning twins showed the same picture minutes apart; with a 0.1-pip target the result is decided by the first ticks "
               "after the fill, which no candle before the entry can see. The protection here is size and the stop geometry, not a filter.")
        if t["why"] == 8:
            v += f" It was the engine's weekly-close flatten ({t['pnl']:+.0f}$), not a stop."
    if a.get("avoidable_before_entry") and not comb:
        v += (" (The batch analyst marked it avoidable via " + ", ".join(a.get("rule_ids") or []) + "; in the merged re-score the part of "
              "those rules that reaches this trade - beyond the 16:45-17:45 NY window - fails the strict bar on its own: a wider clock window, "
              "a Friday window, a fill/spread or thin-tape cut, each adding losers in one half only or on too few days.)")
    out.append({"id": t["id"], "batch": a["batch"], "side": "BUY" if t["side"] > 0 else "SELL",
                "entry_utc": dt.datetime.fromtimestamp(t["t_in"], dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "entry_ny": ny, "exit": exit_, "pnl_usd_1lot": round(t["pnl"], 1), "stop_pips": t["stop_pips"], "trigger_spread_pips": spr,
                "comment": a["comment"], "cause": LABEL[CLS[t["id"]]], "cause_class": CLS[t["id"]], "cause_detail": a["cause"],
                "avoidable_before_entry": comb, "removed_by": removed_by, "mt5_candidates_that_skip_it": cand,
                "rejected_rules_that_skip_it": rej, "verdict": v,
                "analyst_avoidable_before_entry": bool(a.get("avoidable_before_entry")), "analyst_rule_ids": a.get("rule_ids") or []})
json.dump(out, open(os.path.join(HERE, "claude_loss_comments.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

n_av = sum(o["avoidable_before_entry"] for o in out)
cc = collections.Counter(o["cause"] for o in out)
cc_av = collections.Counter(o["cause"] for o in out if o["avoidable_before_entry"])
print(f"wrote {len(out)} losses; avoidable before entry (rule_combined) {n_av}, unavoidable {len(out) - n_av}")
print("cause counts (avoidable in brackets):")
for k, v in cc.most_common():
    print(f"   {v:3d}  [{cc_av.get(k, 0):2d}]  {k}")
print("analyst said avoidable:", sum(o["analyst_avoidable_before_entry"] for o in out),
      "| agree:", sum(o["analyst_avoidable_before_entry"] == o["avoidable_before_entry"] for o in out))
print("MT5 candidates catch (beyond rule_combined):", sum(1 for o in out if o["mt5_candidates_that_skip_it"] and not o["avoidable_before_entry"]))
json.dump({"cause_counts": dict(cc), "cause_counts_avoidable": dict(cc_av), "avoidable": n_av, "unavoidable": len(out) - n_av},
          open(os.path.join(HERE, "comment_summary.json"), "w", encoding="utf-8"), indent=1)
