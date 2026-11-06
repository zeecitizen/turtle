"""loss_comments_b8.py - batch 8's own reading of each loss (written from the charts + the 40-candle cards). Writes loss_comments_b8.json.
Times are PKT (UTC+5) unless marked NY (New York) or UTC."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
C = [
    ("1001-061805-B", "into resistance (flat-top flag after a spike)", False, [],
     "Thu 1 Oct, 11:18 PKT. At 11:00-11:02 PKT a spike lifted EUR/USD 7 pips (1.1318 to 1.1325) on 251/190/154-tick candles. Then price went flat "
     "for 16 minutes in a 2-pip box (1.1323-1.1325), topping at 1.13250-1.13252 five times (11:08, 11:11, 11:12, 11:13, 11:14). The UHV was the "
     "11:15 red candle at 111 ticks, no louder than the candles around it. The retracement was only 1.6 pips (extreme 1.13229), and the buy "
     "filled at 1.13248: 0.2-0.4 pip under that ceiling, the sixth test of it, with the camel just turned GREEN x1. That fill was the high of "
     "the next 73 minutes. The flag broke down and ran to the stop at 1.1304. What was visible before entry: a flat-topped flag after a spike, "
     "and a buy right under equal highs. It does not separate. Both twins (10:43 and 10:48 buys at 1.13207-09) also bought within 0.5 pip of "
     "small tops (10:38 high 1.13212), and both won. As a rule, 'swing high 0-0.6 pip ahead' (ceiling_just_ahead) removes 96 losers and 4,434 "
     "winners (lift 0.94). No selective rule catches this one."),
    ("1002-121910-S", "news spike (NFP) + selling a hammer bounce", True, ["fri_after_08ny"],
     "Fri 2 Oct, 17:19 PKT (08:19 New York). This was US payrolls (NFP) day, and the entry came 11 minutes before the 08:30 NY release. Price "
     "had fallen for an hour from 1.1243 (16:44) to 1.12209 (17:17), camel RED x5, so the trend was old. The 17:17 candle was a hammer: low "
     "1.12209, close 1.12244, a 3.5-pip lower wick. The UHV was the next candle, green, at 17:18 with 209 ticks. So the 'retracement' was a "
     "one-candle bounce off the low, and the sell at 1.12232 sat 2.3 pips above a fresh rejection low. At 17:30 PKT the NFP spike went "
     "straight through the stop to 1.1260, filling 1.5R past it for -323$. Twins: 18:13 PKT sold after the NFP spike had faded, and 15:44 PKT "
     "sold 3 pips above an earlier low; both won. Visible before entry: the scheduled 08:30 NY data and the hammer bounce. Only "
     "fri_after_08ny (GOOD, 2.21/2.88) catches it. A generic 'last 30 min before 08:30 NY' rule is not selective (1.57/1.99), and the "
     "first-Friday NFP window has only 3 losers in 9 months."),
    ("1002-133626-S", "counter-structure after news", True, ["fri_after_08ny"],
     "Fri 2 Oct, 18:36 PKT (09:36 NY), one hour after NFP. The release spiked EUR/USD from 1.1222 to 1.1261 at 17:30 PKT. Price then held the "
     "gains with higher lows (1.1237 at 17:40, 1.12423 at 18:22) and made a new high, 1.12643, at 18:01. Small humps inside that bullish "
     "post-news structure gave a RED x1 camel. The UHV was the 18:35 green candle (307 ticks), and the sell broke its low at 1.12461, 3.8 pips "
     "above the 18:22 higher low. The post-NFP buying kept going to 1.1280 by 19:05, and the stop was hit. Twins: 19:23 and 19:33 PKT sold "
     "even higher in the same uptrend and won (+1). So 'counter-trend after news' does not separate (counter_trend_60 lift 0.66). Only "
     "fri_after_08ny (GOOD) catches it."),
    ("1004-230306-B", "thin Sunday-open market, lower highs", False, [],
     "Sun 4 Oct 23:03 UTC (Mon 04:03 PKT), about 2 hours after the weekly open. Volume was 4-72 ticks a minute (03:58 had 4 ticks) and ATR "
     "1.0 pip. Price spiked down to 1.1249 at 03:01 and recovered to 1.12611 at 03:50. It then rolled over with lower highs: 1.12603 (03:59), "
     "1.12598 (04:00), 1.12586 (04:01). The UHV was the 04:02 red candle (70 ticks). The buy at 1.12583 broke that tiny candle inside a "
     "falling micro-structure, 2.8 pips under the 03:50 top, camel GREEN x1. Price drifted down for 2 hours to the stop. The twins (Mon "
     "08:22 and 09:16 PKT) were V-recoveries in a liquid pre-London market. Visible before entry: a thin Sunday book and lower highs. But "
     "Sunday trades as a group lose at only 1.14x base (train 5L/185W, test 5L/195W), so this is not selective."),
    ("1006-101510-S", "into support (range floor)", False, [],
     "Tue 6 Oct, 15:15 PKT, London afternoon, inside a 90-minute range of 1.1240-1.1249. Price made a higher high of 1.12485 at 15:07, then fell "
     "to 1.12412-1.12413 at 15:12-15:13. The UHV (green, 15:00 PKT, 178 ticks) was 15 bars old, and its low of 1.12413 matched that shelf. "
     "The sell at 1.12412 was the third touch of 1.1241 in three minutes and only 1.2 pips above the range floor (1.12400 at 14:47). Range "
     "box 19 means it sold at the bottom of the last 7 candles; camel RED x1, just flipped. The floor held: price rotated back to 1.1248 and "
     "reached the stop after 87 minutes. Twins: 13:24 sold 1.12273 at an earlier shelf and 17:06 sold into an uptrend; both won. So "
     "'selling onto a floor' shows up in the winners too (ceiling_just_ahead 0.94). No selective rule catches it."),
    ("1007-013110-B", "camel misread (micro hump against the hour)", False, [],
     "Wed 7 Oct, 06:31 PKT (01:31 UTC, Tokyo session). Price ground lower for 90 minutes, from 1.1255 (05:01) to 1.12426 (06:24), with lower "
     "highs all the way: 1.1253, 1.1252, 1.1250, 1.1248, 1.1247. The 06:21 breakdown candle (129 ticks) was the UHV. The camel flipped GREEN "
     "x1 on a 0.6-pip higher low (1.12426 at 06:24, then 1.12432 at 06:29). The buy at 1.12449 traded that micro hump against the hour's "
     "trend. There was no follow-through, and it bled to the stop over 4.8 hours. The twins (01:37 and 11:50 PKT range buys) won. A lower "
     "high plus a green hump is exactly Zee's camel complaint. But as a skip filter the HH+HL camel test is not selective "
     "(hump_camel_replay 1.09/1.01), and neither is counter-trend (0.66)."),
    ("1007-091004-B", "buying a bear flag under a big figure", False, [],
     "Wed 7 Oct, 14:10 PKT, London morning. A sharp sell-off at 12:52 PKT (600+ tick candles, 1.1208 to 1.1181) was followed by a corrective "
     "rally on falling volume (from 600 down to 100-140 ticks). The rally made higher lows (1.1180, 1.1189, 1.1194) up to 1.12036 at 14:02, "
     "about 75% of the drop. The 14:05-14:08 pullback produced the UHV (14:08, 113 ticks). The buy at 1.11989 bought that bear flag with the "
     "big figure 1.1200 only 1.1 pips above the fill. The flag broke down and reached the stop in 2.6 hours. Twins (18:06 and 18:50 PKT "
     "range buys in the NY session) won. Visible before entry: a corrective, low-volume rally under a big figure after a liquidation. But "
     "this level was 1.5 pips short of the figure, and the big-figure rule only becomes selective within 1.0 pip; widened to 1.5 pips it "
     "fails on train (1.73/3.58)."),
    ("1008-064604-B", "into resistance (double top)", False, [],
     "Thu 8 Oct, 11:46 PKT. A V-recovery from 1.1191 (11:07) climbed back to 1.12047 (11:41), a second top level with the 11:20 high "
     "(~1.1204), i.e. a double top. The UHV was the 11:43 red candle (90 ticks). The break came 2 ticks into the 11:46 minute: buy 1.12033, "
     "1.4 pips under the double top, after a 1-pip pullback (extreme 1.12023). The top held, and price slid 20 pips in 20 minutes. Twins: "
     "12:29 bought 1.11961 just under the 12:24 high, and 10:14 bought at the top of a slow uptrend; both won. The double top was visible, "
     "but having equal highs just ahead is as common in winners (lift 0.94)."),
    ("1009-205809-S", "market close", True,
     ["fri_after_16ny", "fri_after_15ny", "fri_after_14ny", "fri_after_13ny", "fri_after_12ny", "fri_after_08ny", "last_15min_of_week",
      "close_and_rollover", "big_figure_ahead", "big_figure_ahead_fill05", "clock_bigfig_overshoot"],
     "Fri 9 Oct, 20:58 UTC (01:58 PKT Sat), two minutes before the weekly close at 16:58 NY. The final minutes were noisy (100-200 tick "
     "candles falling from 1.12045 to 1.12003). The sell broke the low of the 01:57 green candle at 1.12003, 0.3 pip above the 1.1200 big "
     "figure. The engine closed it at the weekly close for -24$. The market reopened about 12 pips lower, so the trade would have won, but "
     "nobody can hold through the weekend on a 0.1-pip target. The twins were Friday-evening sells 1-2 hours earlier that had time to work. "
     "Clearly avoidable: last_15min_of_week (16x) and fri_after_14/15/16ny (EXCELLENT) catch it, and so does big_figure_ahead."),
    ("1012-023747-B", "dead market (chop), microscopic retracement", False, [],
     "Mon 12 Oct, 07:37 PKT (late Tokyo). The tape was dead: ATR 0.58 pip, 38-81 ticks a minute, candles of 0.3-0.8 pip. Price drifted from "
     "1.1217 (06:10) down to 1.1211 with lower highs (1.12149 at 07:03, 1.12139 at 07:30). The 'retracement' was 0.4 pip deep (extreme "
     "1.12123 against level 1.12127), and the GREEN x2 camel came from 1-pip humps. The buy at 1.12131 needed spread + 0.1 pip from a market "
     "that was not moving. It drifted 6 pips lower and reached the stop 5.5 hours later. Twins: 07:03 bought 1.12146 in the same zone, and "
     "06:11 bought at the top of a rally; both won. Shallow-retracement (0.66) and quiet-hour (1.73/2.77) rules are not selective."),
    ("1013-043630-S", "into support (old grind, third probe of the floor)", False, [],
     "Tue 13 Oct, 09:36 PKT, between Tokyo and London. ATR was 0.61 pip, 22-60 ticks a minute, in a 6-pip descending channel over 90 minutes "
     "(1.1176 to 1.11705), camel RED x4. The low printed 1.11705 at 09:33. The UHV was the 09:34-35 bounce (44 ticks), and the sell at "
     "1.11711 sat 0.6 pip above that fresh low, the third probe of the 1.1170-1.1172 floor. The floor held for 25 minutes, then London "
     "buying from 10:00 PKT took price to the stop. Twins: 09:26 and 09:09 sold 1.11720/1.11725 on the same floor and won by trickling 0.3 "
     "pip lower. The floor and the age of the trend were both visible, but neither separates (ceiling_just_ahead 0.94; mature_trend test "
     "1.05)."),
    ("1015-035806-B", "camel misread (green hump with a lower high)", False, [],
     "Thu 15 Oct, 08:58 PKT. A 26-pip rally (1.1215 to 1.1241 at 07:58) reversed to 1.1223 at 08:26. The bounce made a LOWER high of 1.12332 "
     "at 08:45 and pulled back to 1.12276 at 08:53. The camel called it GREEN x1 because the 08:53 low was above the 08:26 low. That is a "
     "higher low under a lower high, exactly Zee's 'a green hump needs both' case. The UHV was 08:57 (130 ticks, the loudest of the "
     "pullback), and the buy at 1.12297 broke it mid-range after the peak. Price fell steadily to 1.1218 and the stop. Twins: 08:34 bought "
     "1.12268 in the same pullback, under the same lower-high structure, and won; 07:40 also won. So the visible flaw is shared by its own "
     "twin, and as a filter the HH+HL camel test is not selective (1.05). The detector change itself can only be judged by the engine and "
     "MT5."),
    ("1016-205727-B", "market close (spread blow-out into the close)", True,
     ["fri_after_16ny", "fri_after_15ny", "fri_after_14ny", "fri_after_13ny", "fri_after_12ny", "fri_after_08ny", "last_15min_of_week",
      "close_and_rollover", "fill_overshoot_15", "clock_bigfig_overshoot"],
     "Fri 16 Oct, 20:57 UTC, three minutes before the weekly close, after an hour in a 1-pip box (1.1237-1.1240). The buy filled at 1.12406, "
     "1.5 pips above the 1.12391 level, because the spread blew out into the close. The engine closed it at 16:58 NY for -23$. The market "
     "reopened 20 pips lower on Monday, so holding would have been a full loss. Twin 1016-205040-B (20:50 UTC) bought 1.12388 and scraped "
     "+1 just before the close. Clearly avoidable: last_15min_of_week, fri_after_14/15/16ny and fill_overshoot_15 all catch it."),
    ("1019-171329-S", "into support (higher-low floor)", False, [],
     "Mon 19 Oct, 22:13 PKT, NY afternoon. After a drop to 1.1202 at 21:02 PKT, price built higher lows (1.1205, then 1.12068 at 21:48, then "
     "1.12067 at 22:09) under highs near 1.1213: a rising floor at 1.1207. The UHV was the 22:10 green candle (97 ticks). The sell at "
     "1.12071 came 0.4 pip above the 22:09 low, the third test of the 1.1207 floor in 25 minutes. Twin 22:08 had sold 1.12073 at the same "
     "floor and won by 0.1 pip. This one came after the floor had just bounced, went nowhere, and rose to the stop over 9.7 hours. Visible "
     "before entry: a higher-low floor right under the sell. It is not separable: the winning twin had the same structure, and re-entries "
     "at the same level lose at the base rate (pandas test, about 1.0)."),
    ("1023-145031-B", "market close (forced exit after six hours of chop)", True, ["fri_after_08ny"],
     "Fri 23 Oct, 19:50 PKT (10:50 NY), in a 1.5-hour range of 1.1194-1.1208 with tops at 1.12078 (19:07) and 1.12065 (19:15). The UHV was "
     "the 19:47 red candle (194 ticks), and the buy at 1.12059 (box 20) sat 0.6 pip under the 19:15 top. The fill was the high of the next "
     "six hours: price chopped below it until the weekly close forced it out at -40$. Twin 19:15 bought 1.12060, the same level, and won; "
     "19:07 also won. The range top was visible, but it shows up in winners too. fri_after_08ny (GOOD) catches it. On a Friday after 08:00 "
     "NY, a round that does not pay quickly gets closed at the weekly close."),
    ("1026-024856-B", "exhausted leg (buying the spike high)", False, [],
     "Mon 26 Oct, 07:48 PKT, Tokyo session. Price climbed for 1.5 hours from 1.1217 to 1.12266 (07:44), camel GREEN x3, the last 6 pips in "
     "12 minutes (from 1.12204 at 07:32). The 07:46 red candle (92 ticks) was the UHV, and the breakout minute already had 85 ticks, almost "
     "as loud as the UHV. The buy at 1.12263 was 0.3 pip under the 07:44 spike high, buying the top of an extended leg. Price rolled over to "
     "1.1220 and the stop. Twins: 07:09 bought 1.12240 at the then-high (won after 30 minutes), and 06:57 also won. Not separable with what "
     "I measured: box, room-to-high and equal highs all score about 1.0."),
    ("1026-105900-B", "into resistance (big figure 1.1200)", True, ["big_figure_ahead", "big_figure_ahead_fill05", "clock_bigfig_overshoot"],
     "Mon 26 Oct, 15:59 PKT. A clean downtrend ran from 1.1216 (14:29) to 1.11967 (15:52) with lower highs, and the camel flipped GREEN x1 on "
     "a small hump at the low. The UHV (15:50, 150 ticks) had its high at 1.11996, 0.4 pip under the 1.1200 big figure. The five candles "
     "before the entry (15:54-15:58) all topped at 1.11996-1.12001, so the figure was capping price. The buy at 1.11999 needed the figure to "
     "break. It did not, and the downtrend resumed to the stop. Twins: 15:31 bought 1.12043 and 13:05 bought 1.12066, with no big figure "
     "within reach, and both won. big_figure_ahead (GOOD raw, 2.53/4.99, 7 losers) and big_figure_ahead_fill05 catch it. Outside the clock "
     "windows the big-figure effect is borderline (1.99/1.88), so treat it as a hypothesis for MT5."),
    ("1026-172601-B", "exhausted trend (re-test of a climax high)", False, [],
     "Mon 26 Oct, 22:26 PKT. A 1.5-hour uptrend from 1.1176 to 1.1195 ended with a vertical leg, 1.1183 to 1.11953 (22:10-22:19) on "
     "250-tick candles: a climax. The first red candle after the peak (22:20, 144 ticks) was the UHV. After a 2-pip pullback, the buy at "
     "1.11954 was 0.1 pip above the 22:19 peak, a re-test of the climax high with camel GREEN x3. It never ticked higher and ground down to "
     "the stop over 3 hours. Twins: 22:05 bought before the leg, and 19:54 bought under a double top at 1.1187; both won. Visible before "
     "entry: buying the re-test of a climactic high. Not separable: mature_trend scores 1.93/1.05, and a big-bar-nearby (spike) test is not "
     "selective."),
    ("1027-163522-B", "into resistance (broken support re-tested from below)", False, [],
     "Tue 27 Oct, 21:35 PKT. A range of 1.1141-1.1146 (20:05-21:00) broke down at 21:01 to 1.11361 (21:17). The recovery climbed 8 pips back "
     "to 1.11442, right into the underside of the old range. The UHV (21:33, 96 ticks) and the buy at 1.11447 were the first touch of "
     "broken support from below, camel GREEN x1 from the recovery hump. The old range bottom held as resistance, and price fell to the stop "
     "over 4.2 hours. Twins: 20:30 bought 1.11441, the same price, while it was still support, and 19:37 also won. Broken support turning "
     "into resistance was visible, but bar-based tests of 'level inside recently broken structure' were not selective."),
    ("1030-122421-B", "news spike (US data at 08:30 NY)", True, ["fri_after_08ny"],
     "Fri 30 Oct, 17:24 PKT (08:24 NY), six minutes before the 08:30 NY data. Price had slid from 1.12035 (16:12) with lower highs; the "
     "camel flipped GREEN x1 on a small hump, and the buy at 1.11937 sat mid-range (box 9). At 08:30 NY the release broke EUR/USD 20 pips "
     "lower in 25 minutes, hitting the stop. Twins: the 16:59 and 16:42 PKT buys in the same downtrend won, with no release pending. Visible "
     "before entry: the scheduled data minute. fri_after_08ny (GOOD) catches it. Without a calendar, the generic pre-data window is not "
     "selective (1.57/1.99)."),
    ("1102-003016-S", "counter-structure in a thin market", False, [],
     "Mon 2 Nov, 05:30 PKT (Sun 19:30 NY, US winter time since 1 Nov), the first hours of the week, 14-99 ticks a minute. Since 04:51 price "
     "had built higher lows (1.11554, then 1.1157, 1.11605, 1.11621) up to 1.1164 at 05:19. The UHV was the 05:18 green candle (99 ticks), "
     "12 bars before the entry. The sell at 1.11605 broke its low after a slow sag: against the rising lows, on a RED x2 camel carried over "
     "from earlier humps. Price bounced from the fill and climbed to the stop. Twins: 11:10 and 13:19 PKT sold counter-trend into a "
     "stronger uptrend and won. Visible before entry: higher lows under a sell, and a thin book. Neither 'Sunday' (1.14) nor counter-trend "
     "(0.66) is selective."),
    ("1104-082902-S", "counter-structure (selling the bounce in a bull flag)", False, [],
     "Wed 4 Nov, 13:29 PKT, London morning. An uptrend from 1.1222 to 1.1247 (12:13-13:04 PKT) went into a 1.1237-1.1244 consolidation. At "
     "13:23 a sell at 1.12398 won (the twin). Price then dipped to 1.12370 (13:25) and bounced back to 1.12417 (13:28). The UHV was that "
     "13:28 green bounce candle (207 ticks). The sell at 1.12403 was 3.3 pips above the fresh 13:25 low, inside a bullish consolidation, at "
     "a level the twin had already used. Price broke upward to the stop (1.1258 by 13:52). The bounce and the uptrend were visible, but the "
     "repeat-level idea does not generalise (same-level re-entries lose at the base rate), and the 10-pip line just ahead (1.1240) is not "
     "selective on train (1.80)."),
]

if __name__ == "__main__":
    out = [{"id": i, "cause": c, "avoidable_before_entry": a, "rule_ids": r, "comment": m} for i, c, a, r, m in C]
    json.dump(out, open(os.path.join(HERE, "loss_comments_b8.json"), "w", encoding="utf-8"), indent=1)
    print(len(out), "comments written")
