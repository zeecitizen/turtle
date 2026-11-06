"""assemble.py - build final_output.json (the StructuredOutput payload) from results_all.json (api.report numbers),
codes.json (standalone rule code), hits_all.json (which rules skip each batch loss) and loss_comments_batch1.json."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
res = json.load(open(os.path.join(HERE, "results_all.json"), encoding="utf-8"))
codes = json.load(open(os.path.join(HERE, "codes.json"), encoding="utf-8"))
hits = json.load(open(os.path.join(HERE, "hits_all.json"), encoding="utf-8"))
com = json.load(open(os.path.join(HERE, "loss_comments_batch1.json"), encoding="utf-8"))

IDEA = {
    "rule_time_or_spread": "Time windows + a fill-based buy-spread guard: skip NY 16:00-18:00 (rollover hours) OR Friday after 13:00 NY (last 4 h of the week) OR a BUY whose fill (ask) is >= 1.5 pips above the breakout bid (blown-out spread).",
    "rule_rollover_2h": "Skip the hour before and the hour after the 17:00 New York rollover (spreads blow out, liquidity vanishes; on Fridays it is the forced weekly close).",
    "rule_friday_last4h": "Skip Friday entries after 13:00 New York: London has gone home and any trade not at its 0.1-pip target is flattened at 16:58 NY - it cannot wait out a dip.",
    "rule_time_windows": "OR of rule_rollover_2h and rule_friday_last4h.",
    "rule_buy_spread_1p5": "BUY with a blown-out spread: fill (ask) - breakout bid (brk_hi_so_far) >= 1.5 pips; the 0.1-pip target needs the bid to climb over the whole spread. Buys only (a sell fills at the bid, its spread is not in the setup fields).",
    "rule_slip_1p5": "Symmetric: fill >= 1.5 pips beyond the UHV level in the trade direction (spread for buys, jump through the level for sells).",
    "rule_example_utc_close": "Comparison only: the api.py docstring example, 20:45-21:15 UTC (not mine).",
    "rule_rollover_tight": "Sensitivity variant of the rollover window: NY 16:30-18:00.",
    "rule_friday_last3h": "Sensitivity variant of the Friday window: after 14:00 NY (4 h was chosen a priori; reported, not cherry-picked).",
    "rule_friday_last6h": "Sensitivity variant of the Friday window: after 11:00 NY (London close).",
    "rule_buy_spread_1p0": "Sensitivity variant: buy spread >= 1.0 pip.",
    "rule_buy_spread_2p0": "Sensitivity variant: buy spread >= 2.0 pips.",
    "rule_time_or_slip": "Keeper variant using the symmetric slip instead of the buy spread (adds sells that jumped through the level).",
    "rule_thin_hour": "Dead market: last hour's tick volume < 40% of the last 10 hours' average.",
    "rule_thin_hour_resid": "rule_thin_hour on trades outside the time windows (is it more than the clock?).",
    "rule_small_uhv": "The UHV candle has < 50 ticks (thin market).",
    "rule_small_uhv_resid": "rule_small_uhv outside the time windows.",
    "rule_brk_ratio_0p9": "The breakout minute already has >= 90% of the UHV's ticks (the 'quieter breakout' is barely quieter).",
    "rule_dead_last_bar": "The last closed candle's range < 0.35 ATR (dead candle before the breakout).",
    "rule_dead_last_bar_resid": "rule_dead_last_bar outside the time windows.",
    "rule_sell_slip_1p5": "Sells only: breakout bid >= 1.5 pips through the level.",
    "rule_us_news_windows": "Scheduled US data: NY 08:20-08:40 or 09:50-10:10 (0311-135106-S was hit by a 10:00 NY spike).",
    "rule_sr_at_fill": "Chart idea: sell into an older swing low / buy into an older swing high (p=2 pivot, 180 bars, before the UHV) within 0.3 pip of the fill.",
    "rule_impulse_bar_against": "Chart idea: fading an impulse - a bar among the last 3 closed with range >= 2.5 ATR and body against the trade.",
    "rule_fresh_flip_after_opp": "Chart idea: first hump of a new colour after >= 3 opposite humps (camel micro-flip inside an older trend).",
    "rule_structure_against": "Chart idea: last two p=2 swing highs AND lows both against the trade.",
    "rule_exhausted_streak": "Chart idea: mature trend, >= 6 same-colour humps in a row.",
    "rule_trend_against_120": "Chart idea: price moved >= 12 ATR against the trade over the last 120 candles.",
    "rule_extended_at_extreme": "Chart idea: entering at the 60-candle extreme after a >= 20-pip run (buy the top of a run / sell the bottom of a slide).",
    "rule_uhv_last_bar": "Chart idea: the UHV is the last closed candle (breakout in the very next minute).",
    "rule_old_uhv": "Chart idea: the UHV candle is >= 10 minutes old at the breakout.",
    "rule_top_of_hour": "Chart idea: breakout in minute :00 of an hour (session opens / scheduled releases).",
    "rule_deep_retracement": "Chart idea: retracement extreme >= 5 pips beyond the level (stop >= 24 pips).",
}
FILLNOTE = " - reads t['fill'], which the engine takes 0.3 s AFTER the trigger tick (InpUhvLatency): live it can only be an eject on a bad fill (costs the spread), not a skip; 41 of slip_1p5's 79 catches had a normal trigger-tick spread (latency spikes). Clean pre-entry version = trigger-tick spread, see trigger_spread.txt"
NOTE = {
    "rule_time_windows": "GOOD - THE CLEAN KEEPER: pre-entry, clock only (rollover hours + Friday's last 4 h); stable across all window variants tried",
    "rule_rollover_2h": "GOOD - half of the clean keeper",
    "rule_friday_last4h": "GOOD - half of the clean keeper (4 h chosen a priori; test x3.87 just under EXCELLENT)",
    "rule_time_or_spread": "GOOD - best numbers, but its spread part" + FILLNOTE,
    "rule_time_or_slip": "GOOD - weaker than rule_time_or_spread (the sell-slip part adds 30 winners, 0 losers); its slip part" + FILLNOTE,
    "rule_buy_spread_1p5": "EXCELLENT by the numbers but only 7 losers (2 in the test half)" + FILLNOTE,
    "rule_slip_1p5": "EXCELLENT by the numbers (11 losers, 4 in test)" + FILLNOTE,
    "rule_buy_spread_2p0": "EXCELLENT by the numbers (7 losers, 2 in test) - sensitivity variant" + FILLNOTE,
    "rule_buy_spread_1p0": "GOOD by the numbers but regime-dependent (buy fill-spread fell from ~0.5 to ~0.1 pip in June: train x2.42 vs test x13.75)" + FILLNOTE,
    "rule_rollover_tight": "GOOD - sensitivity variant of the rollover window (train x3.82 just under EXCELLENT)",
    "rule_friday_last3h": "EXCELLENT - sensitivity variant; the 4 h window was chosen a priori (not cherry-picked)",
    "rule_friday_last6h": "GOOD - sensitivity variant (London-close start)",
    "rule_example_utc_close": "EXCELLENT - the api.py harness example (20:45-21:15 UTC), NOT a batch_1 finding; listed for comparison (during US DST it sits inside the rollover window)",
    "rule_thin_hour": "NOT SELECTIVE - redundant with the time windows: raw x2.43/x2.85 passes the bar, but outside the windows only x1.42/x2.01 (rule_thin_hour_resid); do not ship separately",
    "rule_dead_last_bar": "NOT SELECTIVE - redundant with the time windows: raw x2.40/x3.76 passes, but outside the windows only x1.12/x1.91 (rule_dead_last_bar_resid); threshold came from a tail scan; do not ship separately",
    "rule_sell_slip_1p5": "NOT SELECTIVE - 2 losers, test x0.00",
}

ORDER = ["rule_time_windows", "rule_rollover_2h", "rule_friday_last4h", "rule_time_or_spread", "rule_buy_spread_1p5", "rule_slip_1p5",
         "rule_buy_spread_2p0", "rule_buy_spread_1p0", "rule_rollover_tight", "rule_friday_last3h", "rule_friday_last6h", "rule_time_or_slip",
         "rule_example_utc_close", "rule_thin_hour", "rule_thin_hour_resid", "rule_dead_last_bar", "rule_dead_last_bar_resid", "rule_small_uhv",
         "rule_small_uhv_resid", "rule_brk_ratio_0p9", "rule_sell_slip_1p5", "rule_us_news_windows", "rule_sr_at_fill", "rule_impulse_bar_against",
         "rule_fresh_flip_after_opp", "rule_structure_against", "rule_exhausted_streak", "rule_trend_against_120", "rule_extended_at_extreme",
         "rule_uhv_last_bar", "rule_old_uhv", "rule_top_of_hour", "rule_deep_retracement"]


def verdict(name):
    r = res[name]
    lt, le, L = r["train"]["lift"] or 0, r["test"]["lift"] or 0, r["all"]["losers_removed"]
    base = "EXCELLENT" if (min(lt, le) >= 4 and L >= 4) else "GOOD" if (min(lt, le) >= 2 and L >= 4) else "NOT SELECTIVE"
    v = NOTE.get(name, base)
    assert v.split(" - ")[0].split(" by ")[0].strip() in ("GOOD", "EXCELLENT", "NOT SELECTIVE"), (name, v)
    return base, v


PRINTED = {}
for ln in open(os.path.join(HERE, "results_all.txt"), encoding="utf-8"):
    if ln.strip():
        PRINTED[ln.split()[0]] = " ".join(ln.split())
rules_out, selective = [], set()
for name in ORDER:
    r = res[name]
    base, v = verdict(name)
    if v.startswith(("GOOD", "EXCELLENT")) and name not in ("rule_example_utc_close", "rule_buy_spread_1p0"):
        selective.add(name)
    a, tr, te = r["all"], r["train"], r["test"]
    line = (f"api.report: removes {a['removed']} (losers {a['losers_removed']} / winners {a['winners_removed']}) loss rate among removed "
            f"{a['loss_rate_removed']}% vs base {a['base_loss_rate']}% lift x{a['lift']} | train x{tr['lift']} ({tr['losers_removed']}L/{tr['winners_removed']}W) "
            f"test x{te['lift']} ({te['losers_removed']}L/{te['winners_removed']}W) | WR {a['wr_after']}% net {a['net_change_usd_1lot']:+,.0f}$ (Python, NOT PROMOTED) "
            f"| Zee's 22: {r['tagged_out']} | crashes {r['crashes']} look-ahead diffs {r['lookahead_diffs']}")
    line = "api.report printed: " + PRINTED[name] + "  (net = Python tick replay, NOT PROMOTED)"
    rules_out.append({"rule_id": name, "idea": IDEA[name] + "  [" + line + "]", "code": codes[name], "lift_all": a["lift"], "lift_train": tr["lift"],
                      "lift_test": te["lift"], "losers_removed": a["losers_removed"], "winners_removed": a["winners_removed"], "verdict": v})

losses_out = []
for lid, c in com.items():
    rid = [x for x in hits["losses"][lid] if x in selective]
    losses_out.append({"id": lid, "comment": c["comment"], "cause": c["cause"], "avoidable_before_entry": bool(c["avoidable"]), "rule_ids": rid})
NOTES = open(os.path.join(HERE, "batch_notes.txt"), encoding="utf-8").read().strip()
json.dump({"losses": losses_out, "rules": rules_out, "batch_notes": NOTES}, open(os.path.join(HERE, "final_output.json"), "w", encoding="utf-8"), indent=1)
print("selective:", sorted(selective))
for x in losses_out:
    print(f"{x['id']:16s} avoidable={x['avoidable_before_entry']!s:5s} {x['rule_ids']}  | all hits: {hits['losses'][x['id']]}")
