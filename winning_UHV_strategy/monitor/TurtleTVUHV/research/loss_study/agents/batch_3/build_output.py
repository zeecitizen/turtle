"""build_output.py - the batch_3 deliverable: my comment on every loss + every tested rule with its api.score numbers -> output.json."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, "rules_scored.json")))
HITS = json.load(open(os.path.join(HERE, "loss_rule_hits.json")))
C = {
    "0407-071138-S": ("counter-structure / into fresh low", False,
        "From 10:41 to 11:44 PKT the market climbed from 1.1530 to 1.1545 in clean higher lows. The camel turned RED x1 only on the "
        "two-candle drop at 12:05-12:06 (1.15424 to 1.15365, 176 and 143 ticks). The 12:07-12:10 bounce printed the green UHV (12:09, "
        "110 ticks, H 1.15406 / L 1.15381). The sell fired on its low at 1.15380, only 1.6 pips above the fresh 12:06/12:07 double low "
        "(1.15365/1.15368), with 60 ticks already traded in the breakout minute. The 1-pip target needed the bid near 1.1537, right into "
        "that double low. Buyers defended it and the 90-minute uptrend resumed. Twin 0407-070500-S sold the same first red hump 6 minutes "
        "earlier, from the top of the drop (box 18), and won. Twin 0407-100924-S sold inside a mature RED x4 trend. What I can see (first "
        "red hump against a 90-minute uptrend, sell 1.6 pips above a fresh double low) is common among winners: near_fresh_extreme x0.91, "
        "counter_trend60 x0.86. Not avoidable with anything measurable."),
    "0408-075606-B": ("into support/resistance (triple top at the 1.1700 big figure)", True,
        "After the 11:44 top (1.1708) price fell to 1.1679 (12:13), then recovered in higher lows. At 12:46, 12:52 and 12:54 PKT it "
        "printed highs of 1.16996, 1.16997 and 1.17000: a triple top sitting on the 1.1700 big figure. The red UHV (12:55, 161 ticks, high "
        "1.16990) triggered the buy at ask 1.16999, so the take-profit (bid 1.17000) was exactly that triple-top high and round number. "
        "The bid never printed 1.17000 and price slid 20 pips. Twin 0408-075005-B bought 3 pips below the ceiling (level 1.16970) and had "
        "room. Twin 0408-064551-B bought 2 pips under the 1.1708 double top and only just won. Visible before entry: the 100-pip figure "
        "sat 1.0 pip beyond the level. bigfig_ahead10 removes it (x2.34 train / x4.66 test, 7 losers), but that rule is fragile. It is "
        "selective only at the 1.0-pip threshold, this level sits exactly on that edge (float32 level), and beyond the session rules it "
        "drops to x1.90/x1.83."),
    "0409-062811-S": ("exhausted trend", False,
        "A 90-minute grind lower (1.1667 to 1.1654, four red humps, ADX 52) ended with a steep 9-pip leg from 11:13 to 11:26 to 1.16541. "
        "The first bounce candle (11:27, green, 86 ticks) became the UHV, and the sell broke its low at 1.16553, 1.2 pips above the fresh "
        "low. That is selling the fourth leg of an old trend at its extreme, and price reversed 13 pips within 30 minutes. The twins were "
        "quiet Asian-range sells (box 16 and box 20) and won. Across all trades this exhaustion profile wins at the base rate: the "
        "exhaustion rule (ADX >= 40, 60-bar move >= 3 ATR with the trade, level in the bottom quarter of the 60-bar range) is x1.72 on "
        "train and x0.78 on test. Not avoidable with what I measured."),
    "0409-110305-S": ("into support/resistance (spring below a range)", False,
        "Price ranged at 1.1673-1.1679 for 90 minutes. Then one red candle at 16:00 PKT (160 ticks, the loudest of the session) stabbed "
        "to 1.16695, below the range floor. The 16:01 green candle answered with 139 ticks (the UHV), and the sell broke its low at "
        "1.16714, 2 pips above the stab. That is a spring or stop-run: the loudest selling candle could not hold new lows and met almost "
        "equal buying (ADX 70 from the spike). Price rallied 13 pips to 1.1683. Both twins sold the first lower high after an 18:38 top, "
        "not a fresh low. On the chart a skilled reader distrusts this sell, but the data does not confirm selling the fresh low after a "
        "spike: exhaustion x1.72/x0.78, near_fresh_extreme x0.91."),
    "0410-122837-S": ("news/spike (12:30 UTC release) into a range floor", False,
        "A 90-minute range at 1.1710-1.1718. Its floor near 1.1710 held at 16:40, 17:04, 17:11 and 17:24 PKT (low 1.17093). Two green "
        "candles off the 17:24 low formed the UHV (17:27, 93 ticks), and the sell broke it at 1.17108 with 80 ticks already in the "
        "breakout minute. That was the fourth test of the floor, and 90 seconds before the 12:30 UTC US data slot (Friday 10 April). From "
        "17:29 to 17:35 price spiked up 15 pips. Twin 0410-122231-S sold the first break of the same floor 6 minutes earlier (box 20) and "
        "won before the spike. An economic calendar would have flagged this; the bars cannot. 12:25-12:35 UTC windows are not selective "
        "over all days (x0.84 train / x1.91 test, because most days have no release), and repeated floor tests are flat (retest_floor "
        "x1.06/x0.99)."),
    "0413-064826-S": ("exhausted trend (climactic sell-off)", False,
        "Price slid from the 11:08 high (1.1695), then broke hard from 11:35 to 11:45: 12 pips down on rising volume (180 ticks at 11:44) "
        "to 1.16775. Two tiny candles at the low and the 11:46-11:47 green candles (UHV 122 ticks) came before the sell at 1.16782, under "
        "1 pip above the capitulation low. Price V-reversed to 1.1692. Twin 0413-060302-S sold a quiet range; twin 0413-074313-S sold the "
        "first pullback from a top. Same verdict as 0409-062811-S: the climax-low profile (ADX 53, 60-bar move 4.3 ATR, level at the "
        "60-bar low) is not selective (exhaustion x0.78 on test)."),
    "0413-120919-S": ("into support/resistance (double-bottom retest)", False,
        "An 18-pip decline from the 16:38 top (1.1699) reached 1.1681 at 17:00 on swelling volume (220 ticks). A 17:02 spike back to "
        "1.1687 was sold down to 1.16803 at 17:06, a marginal new low. The green 17:07-17:08 candles (UHV 150 ticks) then gave this sell at "
        "1.16825, 2.2 pips above the double bottom (1.1681/1.1680). Twin 0413-120523-S sold the same decline at 17:05 (1.16819) and won, "
        "because the 17:06 marginal new low paid its pip. The second sell into the same floor had no new low left, and price rose to "
        "1.1690. A second attempt into a fresh double bottom does not measure as selective: retest_floor x1.06/x0.99, near_fresh_extreme "
        "x0.91."),
    "0413-182648-S": ("chop/range (sell inside a bull flag)", False,
        "A 13-pip rally from 21:56 to 22:20 PKT (1.1724 to 1.1737) was followed by an hour-long flat flag at 1.1733-1.1738 (ADX 13.6, ATR "
        "0.95 pip). The RED x2 camel came from 1-3-pip noise humps inside the flag. The sell broke the UHV (23:24, 133 ticks) at 1.17353, "
        "mid-flag. At 23:28-23:30 the flag broke up to the 1.1756 stop. Twins 0413-174446-S and 0413-174205-S sold the same flag 40 "
        "minutes earlier and won. The visible warning (a sell against the hour's trend in a no-trend flag) is not selective: ADX bins are "
        "flat (ADX < 17.7 is x0.73/x0.65), counter_trend60 x0.86."),
    "0414-025520-S": ("chop/range (dead Asian tape, stale UHV)", False,
        "Dead Asian tape at 02:55 UTC: ATR 0.51 pip, bars of 10-30 ticks. The UHV (07:40 PKT, green, 120 ticks) was the bounce off the "
        "07:36 low (1.1756). The retracement then drifted sideways for 15 minutes, and the sell broke the UHV low at 1.17580 only at 07:55, "
        "14 candles after the UHV (box 20). No follow-through came; price drifted up and later ran to the stop. Twin 0413-223802-S (03:38 "
        "PKT) had the same thin Asian tape and won. Stale UHVs and low-ATR Asian trades are not selective (stale_uhv x1.16/x0.76, "
        "low_atr_asia x1.32/x0.78), and the 60-bar mean volume (55 ticks) is above the dead-tape threshold."),
    "0414-082354-S": ("into support/resistance (origin of the prior impulse)", False,
        "From the 12:08 spike top (1.1796) and a 12:40 lower high (1.1792), price bled 17 pips over 50 minutes back to 1.1775, where the "
        "11:55 rally had started. Volume faded on the way down (70-110 ticks). The UHV (13:21, 83 ticks) gave a sell at 1.17757, 0.9 pip "
        "above the 13:20 low. That is selling a tired drift into the base of the previous impulse; price bounced 9 pips to 1.1784. Twin "
        "0414-120951-S sold the low of a collapse at 17:09 and won. Selling into old support or a fresh low is not selective "
        "(near_fresh_extreme x0.92/x0.99)."),
    "0416-045923-B": ("counter-structure (dead pre-London tape, micro-hump camel)", True,
        "A 90-minute downtrend (1.1817 to 1.1808, lower highs) on a dying pre-London tape at 04:59 UTC: 40-60 ticks a bar, ATR 0.61 pip. "
        "The GREEN x1 camel came from a sub-1-pip micro hump at 09:50-09:55 PKT. The UHV was 14 candles old (09:45, 66 ticks). The buy "
        "broke above the 7-candle high (box 20) at 1.18107, against the hour's trend; price never paid the pip and slid to 1.1803. Twin "
        "0416-041424-B was the same pattern 45 minutes earlier and won by a hair. The visible difference is volume: a 60-bar mean of 38 "
        "ticks against the twin's 56. low_vol60_40 removes this loss but not the twin (x2.06 train / x2.57 test stand-alone). Weak case, "
        "though: once the session rules are applied, low volume adds only x1.24/x1.44."),
    "0417-084606-S": ("camel misread (stale red camel in a vertical rally)", False,
        "A steady uptrend from 12:16 PKT (1.1775) accelerated into a vertical 8-pip run from 13:39 to 13:45 (137-159 ticks). The camel was "
        "RED only because of a 2.4-pip micro hump at 13:34-13:38 (high 1.17847, low 1.17823). The retracement, which was the rally itself, "
        "went 6.5 pips above that hump's high, so the down-structure was already broken. The sell broke the 13:45 green UHV's low at "
        "1.17900, near the top of the 7-candle range (box 3), into higher highs; price climbed to 1.1796. Twin 0417-040531-S sold a rally "
        "only after it had topped and rolled over. The chart says skip; the data says no. Even the corrected structure test "
        "(struct_broken_colour: retracement 2+ pips beyond the colour-setting hump, read from the camel state at that hump's redraw) is "
        "x1.05/x0.79, and micro_hump_flip is x1.11/x1.63."),
    "0417-183109-B": ("market close (late Friday)", True,
        "Friday evening chop at 1.1785-1.1797. Price spiked to the range top (1.1797) at 23:26 PKT for the second time (after 22:52) and "
        "was rejected by a sharp red candle at 23:28. The buy came off the red UHV (23:29, 139 ticks) at 1.17936, 4 pips under the "
        "rejected top, at 18:31 UTC on Friday. Price fell 20 pips into the weekly close. Twins 0417-180551-B and 0417-171505-B bought the "
        "same range earlier and won. Visible before entry: Friday after 17:00 UTC, the window where an unpaid trade has hours of thin tape "
        "and the forced 20:58 close ahead. fri_late17 x4.05/x3.87, session_close x3.80/x3.73, fri_17_19 x2.76/x2.75."),
    "0417-205800-B": ("market close", True,
        "Entered at Friday 20:58 UTC, two minutes before the weekly close. The fill was 2.6 pips above the level (the closing spread was "
        "blown out), and the position was force-closed at 20:58 for -2.6 pips (-$26). The market reopened 25 pips lower (1.1738). This is "
        "not a setup failure but a close-window execution. Every close and spread rule removes it: fri_late20 x8.93/x9.41, "
        "rollover_2045_2200 x4.96/x7.34, slip_20 x6.38/x6.81."),
    "0421-151800-B": ("counter-structure (dead-cat bounce into resistance)", False,
        "A failed 19:43 PKT spike to 1.1776 turned into a 27-pip collapse from 19:45 to 20:03 (1.1773 to 1.1748) on the session's heaviest "
        "volume (300+ ticks). The 20:03-20:16 dead-cat bounce built two small green humps (GREEN x2). The buy broke the red UHV (20:16, 254 "
        "ticks) at 1.17597, into the 19:49-19:55 shelf (1.1758-1.1761) where the collapse had paused, now resistance. The bounce died "
        "there and price fell to 1.1741. Twin 0421-150927-B bought the same bounce 3 pips lower at 20:09 and won. A bounce camel against a "
        "big opposite leg is not selective (counter_trend60 x0.80/x1.00)."),
    "0423-140702-S": ("news/spike (after the 14:00 UTC data slot, choppy range)", False,
        "Seven minutes after the 14:00 UTC data slot, in a wide, choppy range (1.1683-1.1697, ATR 2.95 pips). The red humps came from "
        "whipsaws, while the bigger lows were rising (18:12 PKT 1.1683, 19:03 1.1687). The sell broke the green UHV (19:05, 223 ticks) at "
        "1.16912, mid-range (box 9), and price ripped 16 pips up to 1.1707. Both twins sold the same afternoon's range and won. Neither "
        "the time slot (13:55-14:05 UTC: x0.85 train / x1.70 test) nor range position or touches are selective."),
    "0423-164516-B": ("counter-structure (slow bounce into resistance)", False,
        "After the 20:28 PKT high (1.1715) the market made lower highs (1.1708, 1.1705) and a 21:12 low at 1.1698. A slow, low-volume "
        "recovery from 21:12 to 21:44 (80-110 ticks) printed two micro green humps (smaller leg 0.7 pip). The buy broke above the "
        "7-candle high (box 20) at 1.17053, straight into the 20:45-20:55 breakdown shelf (1.1704-1.1707). Price collapsed 22 pips at "
        "22:00. Twin 0423-162143-B bought the 21:12 low itself and won. Same family as 0421-151800-B; not selective (counter_trend60 "
        "x0.86; GREEN x2 so micro_hump_flip does not apply, and it is x1.11/x1.63 anyway)."),
    "0424-095824-S": ("into support/resistance (third test of a floor)", False,
        "The 1.1684-1.1686 floor held at 14:30, 14:36 and 14:50 PKT with rising lows while volume faded. The sell broke the UHV (14:56, 93 "
        "ticks) at 1.16859 on the third test of the floor; price rallied 10 pips. Twin 0424-092540-S sold the identical level 33 minutes "
        "earlier, on the first test, and won. The third test of a floor does not measure as selective (retest_floor x1.06/x0.99)."),
    "0424-183049-S": ("market close (late Friday)", True,
        "Late Friday (18:30 UTC), a thin range at 1.1711-1.1721 with rising lows (23:03 PKT 1.1711, 23:12 1.1712, 23:24 1.1712). The sell "
        "broke a 9-candle-old UHV (23:21, 93 ticks) at 1.17136. The pip never came, price drifted up to 1.1719, and the trade was "
        "force-closed at the 20:58 UTC weekly close for -5.6 pips (-$56). Twins 0424-175730-S and 0424-173838-S sold the same range at "
        "17:38-17:57 UTC and won, and they also fall inside fri_late17. The rule removes the window, not the pattern. Visible before "
        "entry: Friday after 17:00 UTC. fri_late17 x4.05/x3.87, session_close x3.80/x3.73."),
    "0426-222526-S": ("chop/range (Sunday-open thin tape, unfinished gap fill)", True,
        "85 minutes after the Sunday open, which gapped 25 pips down from Friday's 1.1722 to 1.1697. The first 30 minutes traded under 20 "
        "ticks a bar; the gap half-filled to 1.1710 by 02:55 PKT, then went flat. The sell broke a 48-tick UHV (03:24) at 1.17055, against "
        "the unfinished gap fill, on a 60-bar mean of 29 ticks. The tape kept lifting toward the gap and later reached the stop. Both twins "
        "(03:03 and 03:18) sold the same tape and won, so nothing separates this loss from its twins. The rule skips the whole dead "
        "session instead: low_vol60_30 x3.02/x2.40 stand-alone, inside liquidity_guard; sunday_open alone is only x1.18/x1.21."),
    "0427-150215-B": ("camel misread (micro-hump flip right after a collapse)", False,
        "A 19:52 PKT spike to 1.1748 collapsed 15 pips in four minutes (19:53-19:57) on 270-290 ticks a bar. The UHV is the collapse "
        "candle itself (19:56, 288 ticks, high 1.17366). The camel turned GREEN x1 on a micro higher low three minutes later (19:56 "
        "1.17329, 19:59 1.17349: a 4.8-pip hump right after a 15-pip red hump). The buy broke the collapse candle's high at 1.17372, a "
        "reversal bet against a fresh liquidation; price stayed heavy and ran to the stop. Twins 0427-142021-B and 0427-140548-B bought "
        "slow pullbacks in a quieter tape. The colour-hump structure break is exactly 2.0 pips, on the edge of struct_broken_colour (not "
        "flagged), and that rule is x1.05/x0.79 anyway. Not avoidable with anything measurable."),
}
NOTE = {
    "fri_late14": "GOOD. Friday from 14:00 UTC; the 14:00-17:00 slice alone is about x1.2 to x1.4, so start at 17:00.",
    "fri_late16": "GOOD.",
    "fri_late17": "GOOD. Outside the existing 20:45-21:15 window: x3.41 train / x1.61 test (14L).",
    "fri_late18": "EXCELLENT. Lift climbs monotonically from 14h to 20h on both halves; mostly the close window on test.",
    "fri_late19": "EXCELLENT. Outside 20:45-21:15: x4.25 / x0.00 (6L, all train).",
    "fri_late20": "EXCELLENT (mostly the existing close window).",
    "fri_17_19": "GOOD. The 17:00-19:00 slice alone holds (x2.76/x2.75), so the 17:00 start is not riding on the close.",
    "rollover_2045_2200": "EXCELLENT. Daily rollover; outside the old 20:45-21:15 example window: x4.06 / x6.92 (6L).",
    "rollover_2100_2200": "EXCELLENT (6L).",
    "rollover_2115_2200": "EXCELLENT. Only the part of the rollover hour the old window misses (6L).",
    "session_close": "GOOD, the core recommendation. Friday from 17:00 UTC or daily 20:45-22:00 UTC. Outside the old window: x3.31 / x2.62 (19L).",
    "session_close19": "EXCELLENT. The tighter Friday start.",
    "session_slip20": "GOOD. session_close plus a fill 2+ pips past the level; the best simple combination (33L for 350W, WR 98.08%).",
    "slip_12": "GOOD. Overlaps the close windows: outside session_close only 4L/77W.",
    "slip_15": "EXCELLENT stand-alone, but only 3 losers outside session_close (x1.86 / x4.77). Live: a max-deviation price limit "
               "(ask <= level + 1.5 pips buy, bid >= level - 1.5 pips sell).",
    "slip_20": "EXCELLENT stand-alone; 3L/20W outside session_close (x4.25 / x7.95).",
    "slip_10": "NOT SELECTIVE on train (x1.99): borderline.",
    "slip_08": "NOT SELECTIVE on train (x1.55).",
    "low_vol60_30": "GOOD stand-alone, but NOT SELECTIVE beyond session_close + slip_15 (4L/142W, x1.62 / x0.79): its lift came from the close windows.",
    "low_vol60_40": "GOOD stand-alone (barely); beyond session + slip x1.24 / x1.44.",
    "bigfig_ahead10": "GOOD on paper, FRAGILE: 7 losers; train lift >= 2 only at the 1.0-pip cutoff (0.8 gives x2.18 with 5L, 1.5 gives "
                      "x1.65); outside liquidity_guard x1.90 / x1.83.",
    "bigfig_ahead08": "GOOD on paper (5L), same fragility.",
    "bigfig_ahead15": "NOT SELECTIVE (train x1.65).",
    "bigfig_ahead20": "NOT SELECTIVE.",
    "fig50_ahead10": "NOT SELECTIVE: 50-pip numbers add nothing; the effect is only at 100-pip figures.",
    "fig20_ahead10": "NOT SELECTIVE.",
    "liquidity_guard": "GOOD. session_close + slip_15 + low_vol60_30. Most of its lift is session_close; prefer session_slip20.",
    "liquidity_guard_bigfig": "GOOD (adds the fragile big-figure piece).",
    "liquidity_guard_strict": "GOOD.",
    "late_ny": "NOT SELECTIVE (x1.87 / x1.70). Only its 20:45-22:00 part is hot.",
    "sunday_open": "NOT SELECTIVE (x1.18 / x1.21): the Sunday session alone is not hot; the dead-tape volume is what matters.",
    "struct_broken": "NOT SELECTIVE. Also mis-measures sells: camHV[k] is often the retracement's own high (see struct_broken_colour).",
    "struct_broken_2p": "NOT SELECTIVE.",
    "struct_broken_colour": "NOT SELECTIVE. Corrected version (colour hump as known at its redraw bar): still x1.05 / x0.79.",
    "micro_hump_flip": "NOT SELECTIVE.",
    "exhaustion": "NOT SELECTIVE. Hot on train only (x1.72); x0.78 on test. 48 ADX / trend / position combos tried, none hold on test.",
    "near_fresh_extreme": "NOT SELECTIVE. Selling right above the fresh low is what winners do too (removes 20 of the tagged).",
    "counter_trend60": "NOT SELECTIVE.",
    "stale_uhv": "NOT SELECTIVE.",
    "retest_floor": "NOT SELECTIVE.",
    "low_atr_asia": "NOT SELECTIVE.",
    "tiny_last_bar": "NOT SELECTIVE (x1.34 / x1.31).",
}


def verdict_key(o):
    return {"EXCELLENT": 0, "GOOD": 1}.get(o["verdict_auto"], 2)


rules_out = []
for o in sorted(S, key=lambda o: (verdict_key(o), -(o["lift_all"] or 0))):
    doc = (o["doc"] or "").replace("\n", " ")
    doc = " ".join(doc.split())
    rules_out.append({
        "rule_id": o["rule_id"],
        "idea": doc or NOTE.get(o["rule_id"], o["rule_id"]),
        "code": o["code"],
        "lift_all": o["lift_all"], "lift_train": o["lift_train"], "lift_test": o["lift_test"],
        "losers_removed": o["losers_removed"], "winners_removed": o["winners_removed"],
        "verdict": NOTE.get(o["rule_id"], o["verdict_auto"]) +
                   f" | api.report: train {o['train_LW'][0]}L/{o['train_LW'][1]}W, test {o['test_LW'][0]}L/{o['test_LW'][1]}W, "
                   f"WR after {o['wr_after']}%, net {o['net']:+,.0f}$ at 1 lot",
    })
    assert rules_out[-1]["verdict"].startswith(o["verdict_auto"]), o["rule_id"]
losses = [{"id": i, "comment": c[2], "cause": c[0], "avoidable_before_entry": c[1], "rule_ids": HITS[i]["selective"]} for i, c in C.items()]
for x in losses:
    assert (len(x["rule_ids"]) > 0) == x["avoidable_before_entry"], x["id"]
json.dump({"losses": losses, "rules": rules_out}, open(os.path.join(HERE, "output.json"), "w"), indent=1)
print(len(losses), "losses;", len(rules_out), "rules;", sum(1 for x in losses if x["avoidable_before_entry"]), "avoidable")
