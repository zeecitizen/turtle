"""build_payload.py - assembles the batch-2 result (loss comments + every rule with its harness scores and verdict) into payload.json,
the exact object returned to the orchestrator. Scores come from final_scores.json (verify_final.py: each rule string exec'd standalone and
scored with api.score); rule_ids per loss come from the same exec'd rules (batch_losses_caught)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, "final_scores.json"), encoding="utf-8"))

VERDICT = {
    "B2-R1-rollover": "EXCELLENT (4.15 train / 5.25 test, 19 losers). The one strong, simple, market-reasoned fix: spreads blow out and liquidity vanishes around the 17:00 NY rollover, and the 0.1-pip target must pay the spread first.",
    "B2-R1b-rollover-beyond-known": "GOOD (3.17 / 3.46, 8 losers) - the NEW part beyond the already known 20:45-21:15 band (engine InpUhvNoClose). Widen that band to 20:30-22:00 UTC.",
    "B2-R2-buy-spread-2p": "EXCELLENT standalone (6.47 / 8.94, 7 losers), but buys only, the test half rests on 16 trades, and outside the rollover/Friday-evening hours it keeps only 3 losers (15 trades) - below the 4-loser floor there. Keep as a safety valve on top of R1, not as an edge of its own.",
    "B2-R2b-buy-spread-1.2p": "GOOD standalone (2.75 / 12.77, 11 losers); outside the session it fails on train (R2c 1.75). Threshold 2 pips (R2) is the cleaner one.",
    "B2-R2c-buy-spread-1.2p-beyond-session": "NOT SELECTIVE on train (1.75 / 10.22, 5 losers): the spread effect outside the session lives in the Mar-May wide-spread regime only.",
    "B2-R3-camel-old-8": "EXCELLENT by the letter (6.27 / 4.77, 5 losers in 34 trades) but FRAGILE: the test half has 1 loser in 15 trades. Market reason is sound (8+ same-coloured humps = a mature trend, the last UHV is often the climax); needs MT5 + more months before trusting.",
    "B2-R3b-camel-old-7": "GOOD (3.92 / 2.10, 6 losers); also 3.22 / 2.10 outside the rollover. Same fragility: 1 test loser. Shows the effect is not knife-edge at 8.",
    "B2-R3c-camel-old-8-beyond-rollover": "EXCELLENT by the letter outside the rollover (4.96 / 4.77, 4 losers) - fragile, 1 test loser.",
    "B2-R4-combined": "EXCELLENT (4.45 / 5.54, 26 losers of 172, 210 winners removed). Recommended package for an MT5 test: R1 OR R2 OR R3.",
    "B2-R4b-spread-or-old-beyond-rollover": "EXCELLENT increment (5.32 / 7.15, 7 losers in 48 trades): what R2 + R3 add once R1 is in place.",
    "B2-R5-news-spike-8x": "GOOD standalone (2.60 / 3.19, 14 losers) but REDUNDANT: outside the rollover it is 1.65 / 2.19 (R5b).",
    "B2-R5b-news-spike-beyond-rollover": "NOT SELECTIVE (1.65 train / 2.19 test).",
    "B2-R6-dead-market": "GOOD standalone (3.02 / 2.40, 12 losers) but REDUNDANT - a proxy for the rollover / holiday hours: outside the session it is 1.44 / 0.77 (R6b).",
    "B2-R6b-dead-market-beyond-session": "NOT SELECTIVE (1.44 / 0.77).",
    "B2-R7-volume-dryup": "GOOD standalone (2.63 / 2.42, 5 losers) but REDUNDANT: outside the session it removes 60 trades with 1 loser (R7b).",
    "B2-R7b-volume-dryup-beyond-session": "NOT SELECTIVE (1.35 / 0.00, 1 loser).",
    "B2-R8-friday-after-20": "EXCELLENT standalone (8.93 / 9.41, 11 losers) but fully inside R1: Friday 20:00-20:30 UTC beyond R1 = 24 trades, 0 losers. Not needed once R1 is on.",
    "B2-R8b-friday-after-19-beyond-rollover": "NOT SELECTIVE (2.41 / 0.00, 3 losers): the Friday effect is the rollover itself.",
    "B2-R9-rollover-2200-2230": "NOT SELECTIVE (2.18 / 0.00, 3 losers): do not extend R1 past 22:00 UTC.",
    "B2-X1-zee-camel-hh": "NOT SELECTIVE (1.10 / 0.96): as an after-the-fact filter, requiring a higher high on the latest hump removes 2,619 trades at the base loss rate. (A detector change could still behave differently - this only tests it as a filter.)",
    "B2-X2-camel-thin-margin": "NOT SELECTIVE (0.94 / 1.10).",
    "B2-X3-under-prior-high": "NOT SELECTIVE (1.10 / 0.99): buying just under resistance is not worse here (buying at a fresh 40/90-candle high is even slightly safer).",
    "B2-X4-rejection-wick": "NOT SELECTIVE (0.92 / 0.95).",
    "B2-X5-stale-uhv": "NOT SELECTIVE (1.13 / 0.78).",
    "B2-X6-level-retested": "NOT SELECTIVE (1.41 / 1.48).",
    "B2-X7-loud-breakout": "NOT SELECTIVE - near miss (1.79 / 2.04, 8 losers).",
    "B2-X7b-loud-breakout-0.91": "NOT SELECTIVE in practice: 2.22 / 2.36 (8 losers) passes by the letter, but the 0.91 cut was picked from the data and 0.90 fails (X7 1.79 / 2.04) - knife-edge, do not ship.",
    "B2-R1c-rollover-ny-time": "GOOD, near EXCELLENT (3.82 / 5.72, 18 losers): the same rollover effect in New York time; the fixed-UTC R1 scores slightly higher on train (4.15) because of one winter-time loser, 0306-212806-B (21:28 UTC = 16:28 New York, two minutes before the NY window opens). Either form works; NY time is the principled one for the EA.",
    "B2-X8-climax-counter-uhv": "NOT SELECTIVE (1.05 / 0.94).",
    "B2-X9-extended-move": "NOT SELECTIVE (1.60 / 1.05).",
    "B2-X10-against-2h-drift": "NOT SELECTIVE (0.88 / 1.03).",
    "B2-X11-round-number-ahead": "NOT SELECTIVE (1.33 / 2.06).",
    "B2-X12-hump-lower-high": "NOT SELECTIVE (1.63 / 1.30).",
}

GOOD = {"B2-R1-rollover", "B2-R1c-rollover-ny-time", "B2-R1b-rollover-beyond-known", "B2-R2-buy-spread-2p", "B2-R2b-buy-spread-1.2p", "B2-R3-camel-old-8",
        "B2-R3b-camel-old-7", "B2-R3c-camel-old-8-beyond-rollover", "B2-R4-combined", "B2-R4b-spread-or-old-beyond-rollover",
        "B2-R5-news-spike-8x", "B2-R6-dead-market", "B2-R7-volume-dryup", "B2-R8-friday-after-20"}

LOSS = {
    "0319-022714-B": ("unavoidable / triple top", False,
        "BUY 1.14907 at 07:27 PKT (02:27 UTC, Tokyo). A 20-pip impulse at 07:05-07:08 (1.1472 to 1.1490, 548 and 451 ticks) was followed by a 20-minute stall in a 4-pip box (1.1487-1.1491). Volume faded to 72-140 ticks while price kept probing 1.1490-1.1491 (07:15 1.14897, 07:19 1.14904, 07:20 high 1.14911, 07:24-25 1.14898). The UHV was a tiny red 07:25 candle (112 ticks, 0.9 pip, opened at its high). This was the fourth probe of 1.1490 and the third buy there in 9 minutes. The fill was 0.4 pip under the 07:20 high with a 0.9-pip spread, so the bid needed +1 pip straight into the triple top; the box later broke down to 1.1484. Twins 07:18 and 07:24 were the same setup in the same box (same retracement extreme 1.14871, GREEN camel) and each won by a single tick. Nothing pre-entry separates them: under-prior-high (X3 1.10/0.99), rejection wick (X4) and extended move (X9) all score at base rate. A coin flip at a tired top."),
    "0319-072453-B": ("unavoidable / double top", False,
        "BUY 1.14697 at 12:24 PKT (07:24 UTC, London open). After a 14-pip flush at 12:01-12:03 and a V-recovery (626 ticks at 12:08), price made a higher low at 1.14614 (12:11) and pushed to 1.14751 at 12:18, just under the 11:20 high of ~1.1476: a double top. Two strong red candles followed; the UHV was 12:23 (308 ticks, 3.7 pips, opened at its high and closed near its low). The buy fired when price reclaimed that open (1.14692) with the breakout minute already 81% as loud as the UHV, so this was a fight, not a quiet breakout; price rolled over and hit the stop at 13:06 PKT. Twin 12:14 (same GREEN x1 camel, breakout at 69% of the UHV) bought the higher low and won, as did twin 11:39. The difference (buying under a double top versus buying a higher low) does not hold up as a rule: loud breakout X7 is 1.79/2.04 and room-to-high X3 is 1.10/0.99."),
    "0319-155047-S": ("into support / round number", False,
        "SELL 1.15036 at 20:50 PKT (15:50 UTC, the London 16:00 fix). A 35-pip decline from 1.1538 (20:05) reached the 1.1500 round number and the 19:28 low. Between 20:37 and 20:49 it printed lows of 1.15003, 1.15004, 1.14984, 1.14997 and 1.15007, a multiply-tested floor, with volume rising to 385-388 ticks: absorption. The UHV at 20:49 was a full green marubozu (open = low 1.15035, close = high 1.15060, 310 ticks). The sell was a retest of that candle's open with the breakout minute 87% as loud as the UHV, and price ran up through the stop by 21:03 PKT. Twin 20:42 sold the first touch of the same floor (breakout only 8% of its UHV) and won; twin 20:36 sold higher up and won. The visible differences (fourth test of a round-number floor, loud breakout, bullish climax candle) all fail as rules: climax-counter-UHV X8 1.05/0.94, round number X11 1.33/2.06, loud breakout X7 1.79/2.04."),
    "0319-184909-S": ("news spike after entry", False,
        "SELL 1.15560 at 23:49 PKT (18:49 UTC). A 36-pip rally (21:44-22:30, 1.1524 to 1.1560) went flat in a 10-pip box (1.1550-1.1567) for 80 minutes, with volume sinking to 100-130. The RED x3 camel came from tiny lower lows inside the box (1.15532, 1.15506, 1.15530). The UHV was a small green 23:47 candle (110 ticks), and the sell sat in the middle of the box against the 2-hour rally. Within 8 minutes a vertical rally ran the stop (23:57 PKT) and carried on to 1.1615 by 00:10 PKT, about 55 pips; nothing on the chart announced it. Twins 23:14 and 23:07 sold the same box (RED x1) with the same 2-hour drift against them (mv120 -31 and -36 pips) and won. The against-the-drift rule is at base rate (X10 0.88/1.03). Unavoidable."),
    "0320-143152-S": ("exhausted trend (camel x8)", True,
        "SELL 1.15258 at 19:31 PKT (14:31 UTC, Friday). A 32-pip staircase decline from 18:01 (1.1566) had produced the 8th consecutive red hump (RED x8, ADX 51). At the bottom, 19:30 printed a bullish engulfing UHV (406 ticks, open = low 1.15258, close 1.15294 near its high): buyers stepping in. The sell was a retest of that open with the breakout minute 94% as loud as the UHV, and price turned up. Twins 19:24 (RED x6, whose 19:23 UHV was also a full green marubozu) and 19:07 (RED x3) won in the same leg 7 and 24 minutes earlier, so the candle shape does not separate them. What does separate them, and was visible at entry, is the camel's age: x8 versus x6 and x3. R3 (abs(camStk) >= 8: 6.27/4.77, 5 losers in 34 trades) and R4b catch it. Fragile: only 1 test-half loser."),
    "0320-194940-S": ("camel misread (double bottom)", False,
        "SELL 1.15532 at 00:49 PKT (19:49 UTC, Friday evening). Price made a 1.1547 double bottom (23:57 at 1.15475, 00:37-00:38 at 1.15470) and a W-rally from 1.1547 to 1.15597 (00:38-00:44). The camel lagged the turn: its latest hump at entry was the dip into the second bottom (00:32 low 1.15511, 00:33, 00:38 low 1.15470, a 4.1-pip lower low), so it still said RED x1. The 00:38 low was in fact a double bottom with the 23:57 low (1.15475, 0.5 pip apart), and the rally off it had not yet confirmed a swing low. The UHV was the 00:44 impulse candle (288 ticks, spike to 1.15597). The sell fired on the pullback to its open (1.15535) five minutes later, and the rally resumed. The trade was force-closed at the last tick before the weekly close (20:58 UTC) at -17.5 pips. Twin 00:06 had the same structure (RED x1 from the dip into the FIRST bottom, 23:57) and won; twin 22:55 won. So the twins contradict any camel rule here: thin-margin camel fails (X2 0.94/1.10), and Friday 19:00-20:30 UTC beyond the rollover fails too (R8b 2.41/0.00)."),
    "0322-214022-S": ("weekly open gap / dead market", True,
        "SELL 1.15389 at 02:40 PKT (21:40 UTC Sunday, the first hour of the week). Friday closed at 1.1571 and the week opened with a gap down to 1.1537, followed by 30 minutes of 3-30-tick candles. The UHV was a 30-tick green candle at 02:37; the 60-candle average was 57 ticks and the last 3 candles carried 23% of it. Selling the low of a fresh gap in a vacuum: the gap filled 17 pips up to 1.1555 by 03:10. Twins at 06:30 and 06:52 PKT Monday (Asia, 220+ ticks a minute) won. The separator is the clock: R1 catches it, and so does the new part of R1 beyond the known 20:45-21:15 band (R1b 3.17/3.46); dry-up R7 also catches it."),
    "0322-233112-B": ("mature camel + wide spread at a box top", True,
        "BUY 1.15648 at 04:31 PKT (23:31 UTC Sunday night). After the gap fill (1.1537 to 1.1564), price sat in a 7-pip box (1.1557-1.1564) for 30 minutes with a GREEN x7 camel and ADX 18. The buy fired at the box top, a new 40-candle high, and paid 1.2 pips of spread (fill 1.15648 against level 1.15636), so the bid needed +1.3 pips with ATR 1.6. The box held and price slid back 5 pips. Twin 04:22 bought the same box top 9 minutes earlier with GREEN x5 and a 0.9-pip spread, and won; twin 03:31 won. The differences are the camel age (7 versus 5 and 2) and the spread. R3b (abs(camStk) >= 7: 3.92/2.10, and 3.22/2.10 outside the rollover) catches it; the 1.2-pip spread rule misses by a float hair. Avoidable, but fragile (1 test-half loser behind the camel-age rule)."),
    "0324-165033-B": ("second attempt at a double top, stale UHV", False,
        "BUY 1.15890 at 21:50 PKT (16:50 UTC). Price had been in a 22-pip range (1.1575-1.1597) for 90 minutes with lower highs (20:30 1.1597, 21:27 1.1592). The UHV was a red 21:35 candle (262 ticks), 15 candles old at entry. Its level 1.15884 had already been tagged at 21:45 (high 1.15885) and rejected, so the 21:50 break was the second attempt at the same high: a double top. It failed, and price collapsed 33 pips to 1.1557 by 22:05. Twins 22:12 (capitulation reversal, UHV 569 ticks) and 21:09 won. Stale UHV (X5 1.13/0.78), level retested (X6 1.41/1.48) and Zee's higher-high camel (X1, which removes it too) all score at base rate."),
    "0324-201018-S": ("calm before a news spike", False,
        "SELL 1.15829 at 01:10 PKT (20:10 UTC). Price sat in a dead 5.4-pip box for 40 minutes (ATR 0.96), and volume collapsed in the last candles to 51, 53, 56, 38, 36 and 15 ticks (last 3 = 24% of the 60-candle average): the calm before the storm. Five minutes after the entry, a 45-pip spike up (20:15-20:25 UTC) ran the stop. Twins 00:42 (RED x5, normal volume) and 01:41 (after the spike) won. The dry-up was visible and R7 catches it (2.63/2.42 overall), but outside the rollover hours that rule removes 60 trades with this single loser (R7b 1.35/0.00), so it is not a reliable pre-entry filter. The spike itself could not be known."),
    "0324-205001-S": ("rollover hour / dead market", True,
        "SELL 1.16033 at 01:50 PKT (20:50 UTC), 10 minutes before the 21:00 UTC rollover, in a volatile 15-pip chop (ATR 5.5) after the 45-pip spike at 01:15-01:25. Price barely moved in the visible window, and volume went to ~0 at 02:00 PKT. The stop (1.16260) was only reached at 05:10 PKT (00:10 UTC), 3h20m later, when the post-spike rally resumed: the trade sat through the dead rollover hour without ever making 0.1 pip plus the spread. Twins 00:26 and 00:23 (before the spike, normal hours) won. The separator is the clock: R1 catches it (it is also inside the already known 20:45-21:15 band)."),
    "0325-011150-B": ("no separator (stale UHV)", False,
        "BUY 1.16245 at 06:11 PKT (01:11 UTC, Tokyo). After a top at 1.16305 (05:39), price declined. The UHV was the heavy red 06:00 candle of the drop (338 ticks, open 1.16231, high 1.16236, close 1.16209), followed by a 10-minute base at 1.1618-1.1622. The buy hit the UHV high 11 candles later with no follow-through, slid to 1.1617, and stopped out later. Twin 05:41 bought the top area with a 1-candle-old UHV and won; twin 09:19 had a 12-candle-old UHV and also won. So UHV age does not separate them (X5 1.13/0.78). Nothing pre-entry does."),
    "0325-132000-B": ("buy inside a downtrend range (weak camel)", False,
        "BUY 1.15906 at 18:20:00 PKT (13:20 UTC). A 25-pip decline from 1.1613 (17:12) turned into a 1.1586-1.1599 range. The GREEN x1 camel came from a one-minute hump with a 0.2-pip higher low (18:16 1.15867, 18:17, 18:18 1.15869), effectively a double bottom inside a downtrend. The level 1.15899 had already been touched by the 18:15 and 18:19 candles (1.15901). The trade fired on the very first tick of 18:20 (1 breakout tick), and the downtrend resumed to 1.1573 by 18:50. Twin 17:53 (same range, GREEN x1) won, as did twin 19:25. Thin-margin camel (X2), level retested (X6 1.41/1.48) and against-the-2h-drift (X10) are all at base rate."),
    "0326-120509-S": ("exhausted trend + stopping volume (camel x9)", True,
        "SELL 1.15245 at 17:05 PKT (12:05 UTC). A 40-pip staircase decline from 15:36 had reached RED x9 (ADX 47). Over the last 7 candles the lows stopped falling (1.15232, 1.15231, 1.15228, 1.15221, 1.15233) while volume climbed to the highest of the whole leg (198, 186, 213, 183, 220): stopping volume at the bottom. The UHV (green 17:04, 220 ticks) was the loudest candle of the 90-minute leg. The sell broke its low and price turned up. Twins 16:56 (RED x7) and 16:46 (RED x4) won in the same leg. The camel's age (x9) separates it: R3 (abs(camStk) >= 8) and R4b catch it. Fragile: only 1 test-half loser."),
    "0331-222340-S": ("post-rollover dead zone", False,
        "SELL 1.15535 at 03:23 PKT (22:23 UTC). This was the post-rollover dead zone: candles of 0-5 ticks from 02:08 to 02:50 PKT, a 60-candle average of 23 ticks, and one 6-pip spike at 02:58 (12x the median candle). The UHV had 40 ticks and was 9 candles old, and the sell came inside a 7.9-pip box; the stop went later as Asia woke up. Twins 01:56 (20:56 UTC, also thin) and 05:45 won. R5 (news spike) and R6 (dead market) catch it, but outside the session neither is selective (R5b 1.65/2.19, R6b 1.44/0.77), and extending R1 to 22:30 fails on test (R9 2.18/0.00). It sits at the edge of the rollover effect; not reliably avoidable."),
    "0402-040451-B": ("buying the retest of a broken range floor", False,
        "BUY 1.15421 at 09:04 PKT (04:04 UTC). After 90 minutes in a 6-pip range (1.1543-1.1549), price broke down at 08:47-08:56 on rising volume. The UHV (red 08:56, 200 ticks, the loudest in 80 minutes) was the breakdown candle itself. The buy at its high (1.15414) was a retest from below of the broken range floor (1.1544), old support turned resistance, and the decline continued. The GREEN x1 camel came from a 4-minute micro-hump at the low (08:57 1.15375, 09:01 high 1.15406, 09:01 low 1.15379: a 0.4-pip higher low) whose high sat 5.4 pips under the previous hump high. Twins 11:44 and 11:53 bought V-recoveries with higher highs and won. Even so, neither hump lower high (X12 1.63/1.30) nor Zee's higher-high fix (X1 1.10/0.96) separates losers in general."),
    "0403-204101-S": ("holiday + weekly close vacuum", True,
        "SELL 1.14876 at 01:41 PKT (20:41 UTC, Good Friday, 19 minutes before the weekly close). Candles carried 1-25 ticks, price slid 27 pips through a vacuum, and the UHV had 19 ticks. The 1-tick breakout filled and was stopped in the same second at 1.15508: the ask was already 36 pips beyond the stop (-632, three normal stops). Twins at 20:55 and 19:34 PKT on the same holiday, hours earlier with 50-85-tick UHVs, won. The separator is the clock: R1 catches it, but only thanks to the 20:30 start, since the known 20:45 band misses it; R8, R5 and R6 catch it too."),
    "0403-204417-S": ("holiday + weekly close vacuum", True,
        "SELL 1.14766 at 01:44 PKT (20:44 UTC, Good Friday). The same vacuum, 3 minutes later: the bid gapped 9.8 pips through the level (fill 1.14766 against level 1.14864), the stop distance became 55 pips, and it was stopped in the same second at 1.15585 because the ask was already 27 pips beyond the stop (-819). Twins 19:19 and 17:30 PKT (the NFP release) won. Caught by R1 (only thanks to the 20:30 start, one minute before the known band), R8, R5 and R6."),
    "0403-205318-S": ("holiday + weekly close vacuum (camel x8)", True,
        "SELL 1.14770 at 01:53 PKT (20:53 UTC, Good Friday, 7 minutes before the weekly close). RED x8, a 14-tick UHV, and the fill came 3.1 pips above the level; it was stopped in the same second at 1.15578, 56 pips beyond the stop (-808). Twins 16:39 and 16:34 PKT won in the same holiday market hours earlier. Caught by R1, R3, R5, R6 and R8."),
    "0403-205500-B": ("holiday + weekly close spread spike", True,
        "BUY 1.15622 at 01:55 PKT (20:55 UTC, Good Friday, 5 minutes before the weekly close). The buy filled 79 pips above its level (1.15622 against 1.14829): a pure spread spike, with a 108-pip stop distance. It was force-closed at the weekly close 4 minutes later at -52.5 pips (-525). Twins 22:53 and 22:36 PKT (calm holiday evening, 1.0-1.9-pip spreads) won. Caught by R1, R2 (spread >= 2 pips), R5, R6 and R8."),
    "0406-143818-B": ("buy under an upthrust, wide holiday spread", False,
        "BUY 1.15700 at 19:38 PKT (14:38 UTC, Easter Monday). An uptrend from 18:08 (1.1549) peaked at 19:35, when a candle spiked to 1.15715 and closed at 1.15674: an upthrust with a 60% upper wick, i.e. supply. The buy broke the UHV high (1.15687) and filled 1.3 pips above it (the holiday spread), 1.5 pips under the upthrust high. The bid needed +1.4 pips into that supply; instead price fell 23 pips. Twins 18:54 (same structure under the 18:30 high, 0.9-pip spread) and 20:39 won. The 1.3-pip spread was visible and R2b (spread >= 1.2: 2.75/12.77) catches it, but outside the session that rule fails on train (R2c 1.75/10.22), and the upthrust/rejection-wick rule is at base rate (X4 0.92/0.95). Not reliably avoidable."),
    "0406-183009-B": ("buy at the top of a no-demand rally", False,
        "BUY 1.15519 at 23:30 PKT (18:30 UTC). A 12-pip rally from 23:05 to 23:23 (1.1540 to 1.15524) came on falling volume (330 ticks at 23:10, 145 at 23:23): no demand. The UHV was red 23:24 (165 ticks); after a 4-pip dip, the buy filled at 1.15519, 0.5 pip under the 23:23 high. The GREEN x1 camel rested on a 0.1-pip higher low (23:25 1.15485, 23:27 1.15486) right after a red hump. The high held, price slid 8 pips, and the stop went later. Twins 23:08 and 22:54 bought earlier and lower in the same range and won. The visible signs (just under the prior high, an extended 30-candle move, a level already reached twice) do not separate losers in the data: X3 1.10/0.99, X9 1.60/1.05, X6 1.41/1.48."),
}

rules_out = []
for s in S:
    a, tr, te = s["score"]["all"], s["score"]["train"], s["score"]["test"]
    rules_out.append({"rule_id": s["rule_id"], "idea": s["idea"], "code": s["code"], "lift_all": a["lift"], "lift_train": tr["lift"],
                      "lift_test": te["lift"], "losers_removed": a["losers_removed"], "winners_removed": a["winners_removed"],
                      "verdict": VERDICT[s["rule_id"]]})
caught = {}
for s in S:
    if s["rule_id"] in GOOD:
        for i in s["batch_losses_caught"]:
            caught.setdefault(i, []).append(s["rule_id"])
losses_out = []
for i, (cause, avoid, comment) in LOSS.items():
    losses_out.append({"id": i, "comment": comment, "cause": cause, "avoidable_before_entry": avoid, "rule_ids": caught.get(i, [])})
NOTES = (
    "PYTHON HYPOTHESIS ONLY - nothing here is promoted until MT5 (or live fills) confirms it; the net $ figures api.report prints are not evidence. "
    "The harness also ignores one-position blocking: skipping a trade can free a later setup that this trade list never shows. "
    "MAIN FINDING: with a 0.1-pip target a trade wins as soon as price moves the spread + 0.1 pip, so a loss is a breakout that never moved even that far. "
    "In this batch, what separates losers from their twins is WHEN (the NY 17:00 rollover, the Good Friday weekly close, the Sunday open) and the SPREAD paid, "
    "not chart structure. The spread regime explains the half split: median buy spread (ask fill - bid level) was 0.7 pip in Mar-May (loss rate 3.3-5.2% a month) "
    "and 0.2 pip in Jun-Nov (0.8-2.4%), which is why train base is 3.36% and test 1.40%. "
    "RECOMMENDED FOR AN MT5 TEST: B2-R4 = rollover 20:30-22:00 UTC (01:30-03:00 PKT) OR buy spread >= 2 pips OR abs(camStk) >= 8: removes 236 trades, 26 losers, "
    "lift 4.45 train / 5.54 test. The NEW part beyond the already known 20:45-21:15 band (InpUhvNoClose): R1b 3.17/3.46 (8 losers) and R4b 5.32/7.15 (7 losers). "
    "The rollover is 17:00 New York: a DST-aware NY-time version (16:30-18:00 NY, B2-R1c) scores 3.82/5.72 with 18 losers - implement it in NY time in the EA. "
    "CAUTION: the thresholds (the 20:30/22:00 window edges, picked from 30-minute bins over ALL trades; the 2-pip spread cut; the camStk 8 cut) were chosen with both halves in view, so the test-half lifts are a consistency check, not a clean holdout - MT5 on new months is the real test. "
    "rule_ids CONVENTION: rule_ids lists every GOOD/EXCELLENT rule that removes the loss; avoidable_before_entry is true only when a rule is still selective in the slice where it catches that loss (0324-201018-S, 0331-222340-S and 0406-143818-B are removed by R7 / R5+R6 / R2b only through their non-session part, which is not selective, so they stay avoidable=false). "
    "REDUNDANT: dead market, volume dry-up, news spike and Friday rules are GOOD alone but are proxies of the rollover (outside it: 1.44/0.77, 1.35/0.00, 1.65/2.19, 0 losers). "
    "FRAGILE: the camel-age rule (R3/R3b/R3c) rests on 1 test-half loser; the spread rule is buys only (a sell fills at the bid, so its spread is invisible here), "
    "its fill lands 0.3 s after the break (live: use ask-bid at the breakout tick), and its test half has 16 trades. "
    "FAILED (all scored through api.report): every chart-structure idea from the 22 charts - Zee's camel higher-high fix as a filter (1.10/0.96 on 2,619 trades), "
    "thin camel margin, buying under a prior high, rejection wick / upthrust, stale UHV, level re-tested, climax counter-UHV at support, extended move, against the "
    "2-hour drift, round number ahead, hump lower high. Near misses: loud breakout >= 90% of the UHV (1.79/2.04), round number (1.33/2.06). "
    "LOSSES: 9 of 22 avoidable before entry by a selective rule - 6 by the clock (0322-214022-S Sunday open, 0324-205001-S rollover, the four 0403 Good Friday "
    "weekly-close trades, which alone cost 2,784 $ = about 12 normal losses; 0403-204101-S and 0403-204417-S are caught only because R1 starts at 20:30, not 20:45) "
    "and 3 by camel age (0320-143152-S x8, 0326-120509-S x9, 0322-233112-B x7; fragile). The other 13 look like their winning twins at the entry - "
    "same camel, same box, same UHV shape, often minutes apart in the same leg - and no tested rule separates them. "
    "Own bug caught and fixed: X8's range-position test was first inverted; re-scored after the fix (1.05/0.94). "
    "The 'Zee's 22' counts drifted by 1-2 between runs because the comments file was being updated while I worked (I did not read it). "
    "Files: agents/batch_2/rules.py (47 rule functions, every idea tried), final_rules.py (the 33 standalone rule strings returned here), "
    "verify_final.py (execs each string in a fresh namespace and scores it with api.score), final_scores.json, build_payload.py, payload.json."
)
payload = {"losses": losses_out, "rules": rules_out, "batch_notes": NOTES}
json.dump(payload, open(os.path.join(HERE, "payload.json"), "w", encoding="utf-8"), indent=1)
print(len(losses_out), "losses,", len(rules_out), "rules")
for L in losses_out:
    print(L["id"], L["avoidable_before_entry"], L["rule_ids"])
