//+------------------------------------------------------------------+
//|  VSISA.mq5 — Volume Spread Imbalance Shift Analysis               |
//|                                                                   |
//|  Sajid Ahmed's method, as inferred in LAWS_VSISA_INFER.md from     |
//|  Zee's LAWS_VSISA.md and the 22-part course transcripts.           |
//|                                                                   |
//|  THE WHOLE ENGINE IN FOUR LINES:                                   |
//|    1. a 2-BAR SETUP of 2-3 same-direction bars carrying big volume     |
//|       (effort) — somebody is transacting hard in one place;        |
//|    2. a REACTION bar closing the OTHER way — that names which side  |
//|       the big volume actually was (LAW 2);                         |
//|    3. that reaction arrives on LOW volume — the resting orders are  |
//|       GONE, which is the imbalance shift itself (LAW 3);           |
//|    4. enter on its close, stop a few points past its extreme,      |
//|       target a multiple of that risk (LAW 8).                      |
//|                                                                   |
//|  Everything else in the course ships as an input defaulting OFF so |
//|  it can be convicted on its own MT5 receipts rather than smuggled  |
//|  in. Per feedback_backtests_hallucinate_take_all_chances.          |
//|                                                                   |
//|  VOLUME — WHAT THIS EA ACTUALLY JUDGES. BarVolume() asks iRealVolume |
//|  first, but MEASURED over Feb-Aug 2026 on XAUUSD it got 0 reads from  |
//|  it and 8,006,496 tick-count fallbacks: the broker publishes no real  |
//|  volume for gold CFD, so EVERY judgement below is made on TICK COUNT. |
//|  That is defensible — it is the same number the teacher reads on his  |
//|  own retail terminal — but it is NOT exchange volume, and a later     |
//|  session must not assume it is. OnDeinit prints the split every run.  |
//|  (The old project_tester_volume_blind warning still stands for M1     |
//|  work: in NON-real-tick modes MT5 fakes tick_volume at ~4/bar. Under  |
//|  model 4 it is the true tick count, which is why this works at all.)  |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.16"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//--- money -----------------------------------------------------------------
// 0.15 LOTS - SHIPPED 2026-09-16 on Zee's call ("ok 0.15 lot adjustment"), and it is
// spending the headroom LAW 13 just created, not adding new risk on top of the old.
//
// v1.14 turned on the fake break, which cut drawdown from $905 to $586 - 5.9% of the $10k
// funded account he is heading for - while halving the income to $3,998. Raising the lot
// takes some of that income back inside the same 10% breach line:
//        0.10 lots   net $3,999   DD $586    5.9%
//        0.15 lots   net $5,999   DD $879    8.8%   <- HERE
//        0.20 lots   net $7,998   DD $1,172 11.7%   breaches
//
// THE HARD CEILING IS 0.17 LOTS on $10k. Drawdown scales linearly with size and nothing
// in the risk machinery changes it - that was settled in v1.12, where a tighter stop, a
// concurrency cap, a risk cap and a daily loss limit were all tested and none moved it.
// The 9-loss worst streak is unchanged; at 0.15 lots that run costs about $780.
input double InpLots        = 0.15;   // InpLots — lot size per ticket
input int    InpTickets     = 1;      // InpTickets — tickets per decision (basket)
input int    InpMagicNumber = 88201;  // InpMagicNumber — VSISA
// MAX OPEN / COOLDOWN LIFTED (2026-09-12). Zee: "remove the InpMaxOpen = 1 and
// cooldown for now." The funnel is why: over seven months 236 setups passed EVERY law
// and only 124 fired — 47% were thrown away while a trade was already running, refused
// by plumbing rather than by anything the strategy believes.
//
// TIGHTENED TO 2 — SHIPPED 2026-09-16 ON ZEE'S CALL ("ok ship InpMaxOpen=2").
// Detection runs once per CLOSED M5 bar and fires at most one decision per bar, so the rate
// limit is one entry per 5 minutes whatever this says; the ceiling only bounds how much can
// be open AT ONCE. At 10 that is ~$450 exposed if every position is open and wrong together;
// at 2 it is ~$90.
//
// THE PROFIT EVIDENCE IS THIN AND THIS SHIPPED ON RISK, NOT ON RETURN. Walk-forward:
//   Apr-Jun   +$4,004 DD $898   -- IDENTICAL to maxOpen=10; the cap never binds
//   Jul-Sep   +$4,192 DD $905   against +$4,004 DD $950, from removing FOUR trades
// One half is untouched and the other moves on four trades, so +$188 is not a result worth
// defending. What IS solid is that the cap costs nothing measurable in either half while
// cutting worst-case concurrent exposure five-fold — and on a funded account with a hard
// breach line, a free reduction in tail exposure is worth taking.
//
// Measured, the EA rarely holds more than three positions anyway: maxOpen 10, 5 and 3 return
// BYTE-IDENTICAL results over Apr-Sep. This binds only in the crowded moments, which are
// exactly the moments a breach line cares about.
input int    InpMaxOpen     = 2;      // InpMaxOpen — max concurrent decisions
// DAILY LOSS LIMIT (Zee, 2026-09-16: "if we use flat 0.2 .. can't we reduce the drawdown
// from 19%?"). Measured, the drawdown is not caused by concurrency — maxOpen 10, 5 and 3
// return IDENTICAL results, so the EA rarely holds more than three — nor by a few oversized
// stops. It is a RUN OF BAD DAYS: the worst drawdown at 0.20 lots is $1,587 spread over
// five sessions, 22-29 July, with single days of -$635, -$590, -$483 and -$477.
//
// A daily limit is the tool aimed at exactly that, and a funded account imposes one anyway
// (typically 5% = $500 on $10k). Stop opening new trades once the day's realised loss on
// this magic passes the line; open positions keep their own stops.
input double InpDayLossStop = 0.00;   // InpDayLossStop — stop opening for the day after this loss (0 = off)

//--- LAW 4: the 2-bar setup ----------------------------------------------------
// HOW LONG IS THE SETUP? HE COUNTS NOTHING — HE WAITS (2026-09-13).
// "we wait until the red reds keep appearing.. we wait until the reaction candle
// becomes bullish (blue).. IT COULD BE THREE OR MORE REDS". So the run is not a fixed
// 2 or 3; it is however many same-direction bars precede the turn. InpSetupBars is now
// only the fallback when auto is off.
//
// NOTE THIS REINSTATES DIRECTION. A run "until the reds stop" is meaningless unless the
// bars are reds, so auto mode requires each setup bar to close its own way regardless of
// InpStrictDir. His document defines the setup that way; removing direction earlier made
// the pattern something he never drew.
input bool   InpSetupAuto   = true;   // InpSetupAuto — count the run until the turn, don't fix it
input int    InpSetupMin    = 2;      // InpSetupMin — at least this many bars in the run
input int    InpSetupMax    = 10;     // InpSetupMax — stop counting back at this many
input int    InpSetupBars   = 2;      // InpSetupBars — fixed length, used only when auto is off
// THE BACKGROUND CAMPAIGN NEED NOT BE CONSECUTIVE (Zee, 2026-09-16):
// "the initial bullish/bearish candles need not be all consecutive to form the background
// campaign (yes we call it that).. several bullish candles with a single red candle in
// between them for example breaking the consecutive nature, again followed by a larger
// spread low volume engulfing reaction candle .. can be an entry"
//
// The run-counter broke at the FIRST bar closing the wrong way, so one contrary candle
// inside a campaign voided the whole thing — and the same rule then re-checked every bar
// and refused the setup outright. A campaign is an accumulation of effort over a stretch
// of bars, not an unbroken ribbon of one colour. This is the budget for odd bars inside
// it; the bar touching the reaction must still be ours, and the run may not end on one.
input int    InpSetupGaps   = 0;      // InpSetupGaps — contrary bars tolerated inside the campaign
// "the THIRD red candle with EVEN HIGHER VOLUME than previous two means: people are
// buying even more". Read literally that is "the bar nearest the turn is the loudest of
// the run" — which is what this requires. Not strict monotonicity: that would be a
// harder rule than he states and would break on one noisy bar mid-run.
// OFF — BIG IS THE RULE, RISING IS NOT (2026-09-14). Zee: "big volumes show increased
// transactions, i don't think we need in specific 'increasing' volumes, they can just be
// big (not incrementally increasing).." His diagram1 text describes a run that happened
// to rise (150, 200) but the REQUIREMENT is only that the volume is big — increased
// transactions means somebody is absorbing, whatever order the bars arrive in. Requiring
// a rising sequence was me reading a description as a rule; it refused 136 setups in
// September alone. Kept as an input so the stricter reading stays testable.
input bool   InpRisingVol   = false;  // InpRisingVol — require the bar nearest the turn to be loudest
// STRICT DIRECTION LIFTED (2026-09-12, Zee: "remove this condition"). It was the
// widest gate in the whole EA — 46,266 of 81,061 candidates, 57%, died here because
// BOTH 2-bar setup bars had to close the same way. His own 2-bar setup describes the
// SHAPE ("red down bars on big volume"), and demanding two perfect closes turns a
// description into a straitjacket: one bar closing a tick the wrong way voided the
// whole setup no matter how the volume looked.
input bool   InpStrictDir   = true;   // InpStrictDir — every setup bar must close its own way

//--- THE FEED (2026-09-11) -------------------------------------------------
// Zee, 2026-09-06: "we donot wish to use broker volume, we want to completely
// transition to OANDA volume taken from tradingview. any broker volume trades waste
// our time." VSISA v1.00 shipped reading BROKER TICK COUNT because the bridge was
// never wired in — an omission, not a decision. This is the Diamond's proven reader,
// ported verbatim.
//
// DEFAULT 0 ON PURPOSE, FOR NOW. All seven months of VSISA's receipts were earned on
// broker tick volume; OANDA coverage only begins 2026-08-05 (23 trading days), so the
// two cannot yet be compared over the same evidence. Flip this once the court says so.
input int    InpOandaVolume = 0;      // InpOandaVolume — 1 = judge on OANDA (TradingView) volume
input bool   InpOandaStrict = true;   // InpOandaStrict — a missing OANDA minute = no trade, never broker

//--- LAW 5: what "big" means, relative to recent bars -----------------------
// LOOKBACK IS A PLATEAU, NOT A PEAK. Over seven months: 30->$3284, 45->$3385,
// 60->$3377, 75->$3050, 90->$3196, 105->$2948. Adjacent settings swing ~$300, so the
// $249 by which 60 beats 100 is noise, not signal. With net indistinguishable the
// choice falls to the standing goal (project_goal_winrate: fewer losing trades at
// FIXED geometry) — and 100 delivers 34% WR / PF 1.94 / 120 trades against 60's
// 31% / 1.83 / 153, on identical geometry. Change this line to 60 for ~7% more net
// and three points less win rate; both are validated.
// TEN BARS, NOT A HUNDRED (2026-09-12). Zee: "the 100-bar maximum.. that's alot of
// bars to check from.. we can just check the last 10 bars." It also matches what he
// actually does by eye — he compares a candle to the handful around it, not to eight
// hours of history. Smaller window = smaller maximum = the loudness test is far easier
// to satisfy, so this loosens the EA considerably on its own.
// 24 HOURS, BECAUSE HE SAYS 24 HOURS (2026-09-13). LAWS_VSISA.md, "Three bar
// formation": "Ultra high volume -> is this volume abnormal? compare it to let's say
// 24 hour volume". On M5 that is 288 bars. It had been 10 (fifty minutes), which let a
// bar qualify as the session's climax for being the loudest of the last three-quarters
// of an hour — the term "ultra high volume" stopped meaning anything.
// THE YARDSTICK IS THE CURRENT SWING (2026-09-13). Zee: "i think the 24 hour was for
// 1D chart.. on 5 min chart we can just see the current swing." That is how the eye
// actually does it — is this the loudest bar of THIS leg? — and it is self-scaling: a
// fast leg gets a short window, a slow grind a long one, with no magic bar count.
//
// The swing is measured back to the last pivot AGAINST the setup: for a buy (the setup
// bars are falling) that is the most recent swing HIGH, i.e. where this down-leg began.
// InpVolLookback survives as the cap and as the fallback when window mode is 0.
input int    InpVolWindow   = 1;      // InpVolWindow — 0 = fixed bar count · 1 = the current swing
input int    InpSwingPivot  = 3;      // InpSwingPivot — bars each side that define a pivot
input int    InpSwingMin    = 10;     // InpSwingMin — never judge on fewer bars than this
input int    InpVolLookback = 200;    // InpVolLookback — fixed count, and the cap on a swing
input int    InpBigMode     = 1;      // InpBigMode — 0 EVERY 2-bar setup bar loud · 1 only the loudest
input double InpBigPct      = 0.80;   // InpBigPct — 2-bar setup volume >= this x lookback max
input double InpBigAvg      = 1.20;   // InpBigAvg — ...and >= this x lookback average

//--- LAW 3: the low-volume reaction. THE TRIGGER. --------------------------
input int    InpQuietRef    = 0;      // InpQuietRef — 0 quiet vs the SETUP · 1 quiet vs lookback AVERAGE
input double InpLowVolPct   = 1.00;   // InpLowVolPct — reaction volume <= this x the reference
input double InpMinVolPct   = 0.00;   // InpMinVolPct — reaction volume >= this x the reference (0 = no floor)
input double InpBodyFrac    = 0.35;   // InpBodyFrac — reaction body >= this x its own range
// "a LARGER SPREAD low volume engulfing reaction candle" — the reaction that ends a gapped
// campaign is described as a big one, not merely a bar that closed the other way.
input double InpReactSpread = 0.00;   // InpReactSpread — reaction range >= this x avg range (0 = off)
// POSITION SIZING BY REACTION SPREAD (Zee, 2026-09-16: "yes let's let it do position
// sizing. test"). InpReactSpread as a GATE halves the trade count and takes net from
// $8,010 to $4,363 — the wide reactions are worth more per trade but there are not enough
// of them to live on. Sizing keeps every setup and pays attention to the good ones.
//
// The grading, measured per trade and CONSISTENT IN BOTH walk-forward halves:
//   spread < 1.20x avg   $23.66 / $26.24   (the ordinary setups)
//   spread >= 1.20x      $26.12 / $30.61
//   spread >= 1.60x      $43.16 / $33.41   (on 26 and 36 trades - thin)
// Tier 0 exists so risk can be TAKEN OFF the ordinary setups instead of only added to the
// good ones; on a funded account that is the difference between a bigger edge and a breach.
input bool   InpSizeBySpread = false; // InpSizeBySpread — scale lots by the reaction's spread
input double InpSizeT1      = 1.20;   // InpSizeT1 — spread x avg for tier 1
input double InpSizeT2      = 1.60;   // InpSizeT2 — spread x avg for tier 2
input double InpSizeM0      = 1.00;   // InpSizeM0 — lot multiplier below tier 1
input double InpSizeM1      = 1.50;   // InpSizeM1 — lot multiplier at tier 1
input double InpSizeM2      = 2.00;   // InpSizeM2 — lot multiplier at tier 2
// MODE 2 (Zee, 2026-09-16): "what if the no-supply is itself a reaction candle?"
// He is right, and it answers my objection that the test cannot filter the entry. Mode 1
// waits for a CONFIRMING bar after the test, which costs two bars of drift and was measured
// at $18.63 a trade against the base setup's $24.88. If the quiet test bar is itself the
// reaction — a low-volume bar closing against the move — then it IS the entry bar, and the
// trade is taken at its close, at a better price, with no bar wasted waiting.
input int    InpConfirmMode = 0;      // InpConfirmMode — 0 enter on reaction · 1 TEST + confirm bar · 2 enter ON the test
input double InpTestVolPct  = 0.90;   // InpTestVolPct — the test bar's volume <= this x the LAW 3 reference
// DIAGRAM 11 is explicit that the test bar CLOSES AGAINST the trade: "the next bar is
// again red (after the blue surprisingly) -> this is testing -> WE CALL IT THE NO SUPPLY
// TEST". The first cut only required the bar not to break the setup extreme, so a bar
// closing UP could serve as the "test" of a buy — which is not a test of supply at all.
input bool   InpTestRed     = false;  // InpTestRed — the test bar must close AGAINST the trade
// THE NO-SUPPLY TEST AS AN ADDED CONFIRMATION, NOT A GATE (Zee, 2026-09-15):
// "maybe the no-supply test is not working as a gate, but its something that acts as a
// strong confirmation right? so can we test it as an addition?"
//
// He is right that InpConfirmMode was the wrong use of it. That mode DELAYS the entry two
// bars and so replaces the trade rather than confirming it. But the test cannot filter the
// entry either, because it happens AFTER it — at entry time the test bar does not exist.
//
// What it CAN do is judge a trade already open, which is his law used forwards:
// "if in case on no supply test it were big volume it would mean sustained buying" — for a
// BUY, a loud bar closing back down means the supply never left, so the setup has failed
// and there is no reason to wait for the stop. That is a strictly post-entry decision and
// it is what this tests.
// LAW 10 — THE RETRACEMENT, at last (Zee, 2026-09-15):
// "if we miss such a breakout on low volume, then we wait for a retracement to the same low
// where we initially got to when the red candle's happened giving way to bullish move. that
// retracement low when it touches the low line of the missed setup is also a valid setup ..
// infact sometimes it can touch several times (increasing the strength of the upcoming move)"
//
// His document has said this from the start — "Never chase the market. Always catch the
// market on a retracement" — and the audit has carried it as NOT IMPLEMENTED since day one.
// This is it: every setup the detector sees leaves a LEVEL behind at the low the move began
// from, and a later touch of that level is its own entry, with the stop hung off the level
// rather than off a fresh candle.
input bool   InpRetrace     = false;  // InpRetrace — re-enter when price returns to a past setup's level
input int    InpRetraceBars = 60;     // InpRetraceBars — how long a level stays live
input int    InpRetraceTol  = 30;     // InpRetraceTol — points either side that count as a touch
input int    InpRetraceMin  = 1;      // InpRetraceMin — touches required before entering (his "several times")
input int    InpRetraceMax  = 2;      // InpRetraceMax — entries allowed per level
// THE TOUCH MUST ARRIVE ON NO SUPPLY. The first cut entered on price alone — it touched
// the line, it closed back, we bought — and that is not this method at all: every other
// entry in this EA is a VOLUME judgement, and a price-only re-entry throws away the one
// thing the strategy reads. Measured, that version lost $9.46 a trade over 409 trades
// while the base setups made $13.35. This asks the retest to be QUIET, which is the same
// question Law 3 asks of the reaction: if supply had really gone, the retest is cheap.
input double InpRetraceQuiet = 0.00;  // InpRetraceQuiet — touch bar volume <= this x avg (0 = no volume test)
input double InpTestExit    = 0.00;   // InpTestExit — close if the TEST bar is louder than this x avg (0 = off)
input int    InpTestWindow  = 3;      // InpTestWindow — only watch this many bars after entry
input int    InpTestAvgBars = 20;     // InpTestAvgBars — bars in the volume average the test is judged against
input bool   InpEngulf      = false;  // InpEngulf — reaction must engulf the last 2-bar setup bar

//--- LAW 8: geometry -------------------------------------------------------
// WHICH CANDLE THE STOP HANGS FROM (2026-09-12). His LAWS_VSISA.md is explicit:
// "Stop loss 2-3 pips below the bullish blue candle" — the REACTION candle, the blue
// one we enter on. The EA had been measuring from the lowest low of ALL THREE bars, and
// since the setup bars ARE the down-move their lows sit far below, every stop came out
// systematically too wide: the two live trades risked 526 and 876 points. That single
// reference error changed the R multiple of every trade in every test.
// Mode 0 is his specification. Mode 1 is the old behaviour, kept only so the two can be
// compared honestly rather than swapped on faith.
input int    InpStopRef     = 0;      // InpStopRef — 0 = below the REACTION candle (his spec) · 1 = whole setup
// 80 POINTS = 8 GOLD PIPS (2026-09-15). Zee, reading the charts: "some trades could have
// been saved if the stop loss was a bit more relaxed". Measured, and he was right — going
// from 30 to 180 removes 17 losing trades in Apr-Jun and 10 in Jul-Sep, and EVERY buffer
// value beat 30 on both halves. 80 is chosen rather than the maximum because the halves
// disagree about the best value (Apr-Jun wants 180, Jul-Sep wants 80), which is noise;
// what they agree on is that 30 is too tight. It is also defensible as HIS number: the
// teacher gives "3 to 8 pips" in Part 10, and Axi gold spread is ~9 points, so a 30-point
// stop sat barely 3x the spread where ordinary noise reaches it.
// 120 POINTS = 12 GOLD PIPS (2026-09-15). Zee: "i want you to try a still wider stop
// than 8 pips.. see what it does" - and 120 is a genuine INTERIOR peak, better than 80
// in BOTH halves (+$3,621/+$1,741 vs +$2,471/+$1,651) with 160 and 200 both worse.
// Past 200 it collapses: Jul-Sep turns negative at 250 and 350, because the target moves
// out with the stop (2.0R) so a wider stop needs a proportionally bigger move to win,
// and fewer setups clear the 900-point risk cap at all.
// Still defensible against his "3 to 8 pips": that is FX majors with ~1-point spreads,
// and Axi gold spreads ~9 points, so 12 pips here is proportionally tighter than 8 there.
input int    InpSlBufPts    = 120;    // InpSlBufPts — points beyond the reaction candle (12 pips)
input int    InpMinSlPts    = 60;     // InpMinSlPts — floor, so spread cannot eat the stop
input int    InpMaxSlPts    = 900;    // InpMaxSlPts — refuse setups whose risk is absurd
// 5.0R — SHIPPED 2026-09-15 ON ZEE'S CALL. "SL should not be tied to TP. SL can be below
// the first reaction candle's low .. and TP can be very high up until 1:7 .. can you test
// this?" Then, on the result: "ship 5.0".
//
// I HAD THIS WRONG, and the error is worth keeping. I swept the R ladder only to 2.5R,
// found it worse than 2.0R, and called 2.0R the optimum. 2.0R is a LOCAL peak: the curve
// dips at 2.5R and climbs to a second, higher one.
//
//     2.0R  43% WR  +$5,502  DD $946     <- the old default
//     3.0R  32% WR  +$4,624              <- the dip that fooled me
//     4.0R  27% WR  +$6,374  DD $1,014   breaches a 10% funded limit
//     5.0R  25% WR  +$8,153  DD $950     <- HERE
//     6.0R  22% WR  +$8,744  DD $1,322   breaches
//
// +48% profit for IDENTICAL drawdown, and the only rung under a 10% limit. It walks
// forward better than anything else tested: Apr-Jun +$4,022, Jul-Sep +$3,988 — the two
// halves within 1% of each other, beating the old default on BOTH and doubling the unseen
// one (+$3,621 / +$1,741).
//
// NOTHING ABOUT THE RISK CHANGED. Same 322 setups, same structural stop, same average loss
// (-$57.35 at every rung). Only the winners run: avg win +$279.62 against 2.0R's +$114.99.
// That is what decoupling the target from the stop actually buys.
//
// THE COST, so no future session mistakes it for free: win rate 43% -> 25%, and the worst
// losing streak goes 11 -> 15. Targets below 0.75R were tested too and every one buys win
// rate with money: 0.20R reaches 82% and LOSES at every stop width, because at 0.2:1
// break-even needs 83.3%. The H1 trend filter does NOT rescue the win rate here — at 5.0R
// it halves the profit and leaves WR at 24%; its benefit was specific to 2.0R.
input double InpTargetR     = 5.0;    // InpTargetR — TP as a multiple of risk
// TARGET DECOUPLED FROM STOP (Zee, 2026-09-15). He asked whether a wider stop would have
// saved the 14 Sep 04:10 trade. It would not — because at a fixed R multiple the target
// travels outward with the stop, so widening moves the finish line away exactly as fast
// as it moves the stop. That trade needed a 361pt buffer to survive and its 2R target
// then sat at 4358.80, above the 4355.51 high of the next 24 hours. Holding the target
// STILL rescued it (400pt buffer, original target, hit at 1.37R).
//
// So the target gets its own rule:
//   mode 0  R multiple of the stop            — the coupled original
//   mode 1  a fixed distance in points        — same target whatever the stop does
//   mode 2  the swing origin, i.e. the level the leg came FROM — structural, and the
//           one the method actually implies: a retracement is finished when price is
//           back where the move began.
input int    InpTargetMode  = 0;      // InpTargetMode — 0 R-multiple · 1 fixed points · 2 swing origin
input int    InpTargetPts   = 300;    // InpTargetPts — TP distance for mode 1
input double InpTgtMinR     = 0.50;   // InpTgtMinR — refuse if the target is nearer than this in R
input double InpTgtMaxR     = 0.00;   // InpTgtMaxR — cap the target at this R (0 = uncapped)
// BREAKEVEN OFF (2026-09-15). It was CUTTING WINNERS: price reaches 1R, the stop jumps
// to entry, price dips back to entry and closes flat - then runs on to 2R without us.
// Measured at 2.0R with the corrected stop: OFF gives +$2,471/+$1,651 against ON at
// +$962/+$1,199, nearly double AND a higher win rate (44% vs 31%), consistent in both
// halves. Note this REVERSES an earlier finding made on the old build, where the stop
// was measured from the whole setup and breakeven did help - the correction changed it.
input double InpBreakEvenR  = 0.0;    // InpBreakEvenR — >0: move stop to entry at this R
// THE RATCHET (Zee, 2026-09-16): "if 0.75R is reached we breakeven to 0.75R / if 1R is
// reached we breakeven to 1R / if 2R is reached we breakeven to 2R / if XR is reached we
// breakeven to XR".
//
// This is NOT InpBreakEvenR. That one moves the stop to ENTRY and then stops caring, so a
// trade that reaches 4R and reverses still closes at zero. This climbs with the trade and
// never gives the level back: reach 2R and 2R is banked, whatever happens after.
//
// WHY IT IS WORTH TESTING AT 5.0R. Of the 65 losing trades Jan-Sep, FOUR ran past 4R before
// being stopped for a full loss - 20 May peaked 4.80R, 11 Sep 4.77R, 3 Jun 4.61R, 17 Mar
// 4.02R - and another three passed 3R. At 2.0R the old breakeven was measured as actively
// destructive (+$962/+$1,199 with it on against +$2,471/+$1,651 off) because it cut winners
// early. The journey to 5R is far longer, so the same test has to be run again here.
//
// The ladder is start, start+step, start+2*step ... and the stop locks to the highest rung
// price has actually reached. It never moves backwards.
input double InpRatchetStart = 0.00;  // InpRatchetStart — first R rung that gets locked (0 = off)
input double InpRatchetStep  = 0.25;  // InpRatchetStep — spacing of the rungs above it

//--- LAW 6: the wick override (default OFF) --------------------------------
// "since the fourth bullish blue candle has still somewhat bigger volume .. if there
// were no lower wick we wouldn't buy immediately, we would wait .. and here we see a
// lower wick". The wick is how he judges a reaction that is NOT quiet enough — mode 2.
input int    InpWickMode    = 2;      // InpWickMode — 0 off · 1 require · 2 override big volume
input double InpWickFrac    = 0.35;   // InpWickFrac — wick >= this x the bar's range

//--- LAW 7: anomaly, tiny spread on huge volume (default OFF) --------------
input bool   InpAnomaly     = false;  // InpAnomaly — 2-bar setup's last bar must be a spread anomaly
input double InpAnomalyMax  = 0.70;   // InpAnomalyMax — its range <= this x recent average range
// THE CAP BAR (LAWS_VSISA diagrams 4, 6, 7 — added 2026-09-15). This is the Base Case
// Example A finally written down, and Zee states it four separate times:
//   d4 (buy):  "small candle with big volume shows that big demand came that caps the
//              market and not letting the market going down"
//   d6 (sell): "next candle is small blue with a large volume -> supply was hit -> this
//              small candle means agressive selling happened which didnot let the price move"
//   d7 (sell): "next blue candle has low height / spread but volume is bigger .. this
//              shows end of rising market -> supply orders hit -> price capped"
// The signature is BOTH ON THE SAME BAR: huge effort, no result. InpAnomaly already had
// the small-spread half; this is the big-volume half, which was missing entirely —
// and with InpBigMode=1 only ONE bar of the run had to be loud, so the capped bar
// itself could be quiet and the pattern he draws would never be required.
input double InpCapVol      = 0.00;   // InpCapVol — the last setup bar's volume >= this x avg (0 = off)
// THE REACTION MUST CLOSE AT ITS EXTREME (diagrams 7 and 8).
//   d7: "closing of reaction candle's body is strong bearish -> so we will sell"
//   d8: "top wick on reaction candle + strong bearish closing (on the low the closing
//        of candle happened)"
// InpBodyFrac only asks that the BODY is large; it cannot tell a bar that closed on its
// low from one that closed mid-range with a long wick each side. This asks where the
// close actually sits in the bar's range, which is what he points at.
input double InpCloseLoc    = 0.00;   // InpCloseLoc — reaction close in this top/bottom fraction (0 = off)
// EFFORT PER UNIT OF RESULT (LAWS_VSISA diagram 9 — added 2026-09-15). This is the Base
// Case stated properly at last. Zee picks TWO CANDLES OF THE SAME SPREAD and reads the
// difference in their volume: "let's take the forth blue candle, and the seventh blue
// candle -> both has same spread (height of candle body). 4th -> volume low -> low
// supply. 7th -> supply hit so a big volume."
//
// Holding spread constant and comparing volume IS volume-per-range. That is why the
// v1.03 cap bar failed: InpAnomaly demands a small ABSOLUTE range, which is rare and
// throws away every large bar that is also working hard. Normalising by range keeps
// them, and asks the only question he actually asks — how much volume did this bar
// spend for the distance it travelled?
input double InpEffortMin   = 0.00;   // InpEffortMin — last setup bar's vol/range >= this x avg (0 = off)

//--- LAW 13: fake break of a recent extreme -- ON, SHIPPED 2026-09-16 -------
// Zee's own tier-3 case, from his document: "case 3. 2 bar setup + fake break of this
// support + forms a wick + closing again inside support .. (strongest)". It was built
// early, tested OFF on the OLD build, and never re-examined after the stop and swing
// corrections. Re-tested at the 1:5 geometry it is THE BEST FILTER ON THIS PROJECT.
//
// Walk-forward, per trade -- and note it holds at EVERY sweep length, which is a plateau,
// not a spike. Every filter that failed this year (cap bar, volume floor, close location,
// effort-per-range, quiet retracement) was good at ONE setting and worthless at its
// neighbours. This is the opposite:
//        off       25% WR $23.66  |  24% WR $28.21
//        20 bars   33%    $45.40  |  31%    $51.46
//        30 bars   34%    $48.76  |  32%    $54.50   <- SHIPPED
//        50 bars   38%    $57.65  |  31%    $59.39
//
// WHAT IT BUYS: win rate 25% -> 33%, and the worst losing streak 15 -> 9. Drawdown falls
// from $905 to $586. Zee turned it on for the streak: "its hard to psychologically bear
// losses."
//
// WHAT IT COSTS, and this is not free: it refuses 75% of setups (318 -> 78), so at 0.10
// lots the net falls from $8,196 to $3,991. Per unit of drawdown it is WORSE than leaving
// it off (6.81 against 9.06) -- a bigger lot with the filter off earns more for the same
// risk. It is a deliberate trade of income for bearability, not an upgrade.
input bool   InpFakeBreak   = true;   // InpFakeBreak — 2-bar setup must sweep a recent extreme
input int    InpSweepLook   = 30;     // InpSweepLook — bars defining that extreme

//--- LAW 9: higher-timeframe trend (default OFF) ---------------------------
// H1 TREND FILTER OFF (2026-09-12, Zee: "remove"). Worth recording what this costs,
// because the seven-month court liked it: with it ON the EA made the SAME money on
// HALF the trades and seven more points of win rate (34% vs 27%). Off, it trades far
// more and wins less often for about the same net. His call; the receipt stands.
input int    InpTrendTF     = 0;      // InpTrendTF — 0 off · 15 = M15 · 60 = H1
input int    InpTrendBars   = 20;     // InpTrendBars — bars of slope on that timeframe

//--- LAW 11: session (default open) ----------------------------------------
input int    InpSessFrom    = 0;      // InpSessFrom — broker hour, inclusive
input int    InpSessTo      = 24;     // InpSessTo — broker hour, exclusive

//--- housekeeping ----------------------------------------------------------
input int    InpCoolBars    = 0;      // InpCoolBars — bars to wait after a decision (0 = none)
input bool   InpBuys        = true;   // InpBuys — allow long setups
input bool   InpSells       = true;   // InpSells — allow short setups
input bool   InpVerbose     = true;   // InpVerbose — print every fire line

//--- state -----------------------------------------------------------------
datetime g_last_bar = 0;
datetime g_last_fire = 0;
int      g_cool     = 0;
int      g_fires    = 0;

// THE FUNNEL. v1.00 fired zero trades over five days of real M5 ticks and the report
// could not say why — "no trades" looks identical whether the 2-bar setup never formed or
// the reaction was never quiet enough. These count the bar at which each candidate
// died, and OnDeinit prints them, so a tightening can be aimed instead of guessed.
int g_seen = 0, g_rej_dir = 0, g_rej_loud = 0, g_rej_rise = 0, g_rej_anom = 0;
int g_rej_fake = 0, g_rej_react = 0, g_rej_body = 0, g_rej_quiet = 0, g_rej_trend = 0;
int g_rej_test = 0;
double g_swing_px = 0.0;  // price the leg STARTED from - the structural target (mode 2)
double g_eff_avg = 0.0;   // average volume-per-point-of-range over the swing (diagram 9)
double g_react_ratio = 0.0;  // the reaction bar's range / average range - drives sizing
#define VSISA_MAXLVL 64
double   g_lvl_px[VSISA_MAXLVL];      // LAW 10: the low a past setup turned from
int      g_lvl_side[VSISA_MAXLVL];
datetime g_lvl_t[VSISA_MAXLVL];
int      g_lvl_touch[VSISA_MAXLVL];
int      g_lvl_fired[VSISA_MAXLVL];
int      g_lvl_n = 0;
int      g_retrace_fires = 0;
int g_rej_tgt = 0;        // candidates refused because the structural target was too near
int g_rej_cap = 0;        // refused: the last setup bar was not the capped, loud one
int g_rej_loc = 0;        // refused: the reaction did not close at its own extreme
int g_last_span = 0;      // bars in the yardstick on the last judgement, for the log
long g_rv_hit = 0, g_rv_miss = 0, g_ov_hit = 0;

// HOW CLOSE DID WE GET. A funnel says which gate rejected; these say by how much, which
// is the difference between "loosen this threshold a little" and "this law never
// happens on M5 gold at all". Also proves the volume feed is populated — a max of 0
// would mean iRealVolume is empty and every ratio in this file is meaningless.
long   g_vmax_seen = 0;
double g_best_loud = 0;    // best (weakest 2-bar setup bar / lookback max) reached
double g_best_quiet = 999; // lowest (reaction vol / 2-bar setup vol) reached

//+------------------------------------------------------------------+
//| Bar accessors                                                     |
//+------------------------------------------------------------------+
double bHigh(int k)  { return iHigh (_Symbol, PERIOD_CURRENT, k); }
double bLow(int k)   { return iLow  (_Symbol, PERIOD_CURRENT, k); }
double bOpen(int k)  { return iOpen (_Symbol, PERIOD_CURRENT, k); }
double bClose(int k) { return iClose(_Symbol, PERIOD_CURRENT, k); }
double bRange(int k) { return bHigh(k) - bLow(k); }
double bBody(int k)  { return MathAbs(bClose(k) - bOpen(k)); }
bool   bUp(int k)    { return bClose(k) > bOpen(k); }
bool   bDown(int k)  { return bClose(k) < bOpen(k); }

datetime g_ov_t[];
long     g_ov_v[];
int      g_ov_n = 0;
int      g_ov_miss = 0;          // lookups that fell back to broker volume
datetime g_ov_miss_bar = 0;      // last bar already reported, so one line per bar
datetime g_ov_newest = 0;        // newest minute in the table (freshness telemetry)

void LoadOandaVol() {
   g_ov_n = 0;
   // RETRY (2026-08-21): the writer swaps this file atomically every 60 s, and a
   // read landing inside that swap failed outright — one bar silently on broker
   // volume, logged at 21:46:02. Five quick attempts cover the swap window.
   int h = INVALID_HANDLE;
   for (int _try = 0; _try < 5 && h == INVALID_HANDLE; _try++) {
      h = FileOpen("oanda_vol.csv", FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON |
                                FILE_SHARE_READ | FILE_SHARE_WRITE);
      if (h == INVALID_HANDLE && !MQLInfoInteger(MQL_TESTER)) Sleep(40);
   }
   if (h == INVALID_HANDLE) {
      Print("[VSISA] OANDA volume requested but oanda_vol.csv not found — using broker volume");
      return;
   }
   ArrayResize(g_ov_t, 8192); ArrayResize(g_ov_v, 8192);
   while (!FileIsEnding(h)) {
      string ln = FileReadString(h);
      int c = StringFind(ln, ",");
      if (c <= 0) continue;
      datetime t = StringToTime(StringSubstr(ln, 0, c));
      long v = (long)StringToInteger(StringSubstr(ln, c + 1));
      if (t <= 0) continue;
      if (g_ov_n >= ArraySize(g_ov_t)) {
         ArrayResize(g_ov_t, g_ov_n + 4096); ArrayResize(g_ov_v, g_ov_n + 4096);
      }
      g_ov_t[g_ov_n] = t; g_ov_v[g_ov_n] = v; g_ov_n++;
   }
   FileClose(h);
   g_ov_newest = (g_ov_n > 0) ? g_ov_t[g_ov_n - 1] : 0;
   PrintFormat("[VSISA] OANDA volume table loaded: %d minutes (newest %s)",
               g_ov_n, TimeToString(g_ov_newest, TIME_DATE | TIME_MINUTES));
}

long OandaVolAt(datetime t) {          // binary search the sorted table
   int lo = 0, hi = g_ov_n - 1;
   while (lo <= hi) {
      int mid = (lo + hi) / 2;
      if (g_ov_t[mid] == t) return g_ov_v[mid];
      if (g_ov_t[mid] < t) lo = mid + 1; else hi = mid - 1;
   }
   return -1;
}

// ── THE TABLE IS PER-MINUTE; THE CHART NEED NOT BE (2026-09-08) ──────────────────
// Zee: "what if we test our EA on the OANDA, on the 5 minute timeframe instead of 1
// minute. maybe that one is much better due to having a stable trend."
//
// oanda_vol.csv holds ONE ROW PER MINUTE. OandaVolAt(iTime(...)) therefore returns the
// volume of the bar's FIRST MINUTE ONLY. On M1 that is the whole bar and correct; on M5
// it is about a fifth of it — and since every UHV test is a comparison BETWEEN bars,
// each reading a different fifth, the entire ranking would be wrong while every number
// still looked plausible. An M5 court run on that would have answered his question with
// noise.
//
// A bar's volume is the SUM of the minutes it spans. Under strict mode a single missing
// minute voids the whole bar: half a candle of his volume is not his candle.
long OandaVolSpan(datetime t, int mins) {
   if (mins <= 1) return OandaVolAt(t);
   long sum = 0;
   for (int m = 0; m < mins; m++) {
      long v = OandaVolAt(t + m * 60);
      if (v <= 0) {
         if (InpOandaStrict) return -1;   // an incomplete candle is not his candle
         continue;
      }
      sum += v;
   }
   return (sum > 0) ? sum : -1;
}


// iRealVolume, NOT iVolume. See the header — in the tester iVolume is a constant and
// every ratio in this file would silently become 1.0.
long BarVolume(int k) {
   if (InpOandaVolume == 1 && g_ov_n > 0) {
      long ov = OandaVolSpan(iTime(_Symbol, PERIOD_CURRENT, k),
                             (int)(PeriodSeconds() / 60));
      if (ov > 0) { g_ov_hit++; return ov; }
   }
   // NO SILENT FALLBACK UNDER STRICT MODE. Reaching here with OANDA requested means the
   // table lacks this bar; handing back the broker's number would decide a setup on a
   // feed Zee does not read. -1 propagates and VolWhole() refuses the setup outright.
   if (InpOandaVolume == 1 && InpOandaStrict) return -1;

   long rv = iRealVolume(_Symbol, PERIOD_CURRENT, k);
   if (rv > 0) { g_rv_hit++; return rv; }
   // WHICH NUMBER IS ACTUALLY BEING JUDGED. On an exchange-traded symbol iRealVolume is
   // contracts; on a CFD the broker often publishes none and this line quietly hands
   // back the TICK COUNT instead. Both are defensible proxies — the teacher reads his
   // own terminal's tick volume — but they are not the same number, and a strategy
   // built on "volume" must be able to say which one it saw. OnDeinit prints the split.
   g_rv_miss++;
   return iVolume(_Symbol, PERIOD_CURRENT, k);
}

//+------------------------------------------------------------------+
//| LAW 5 — "big" is relative to the recent past, never a band        |
//|                                                                   |
//| Part 1: "these bands are misleading... compare with the big volumes|
//| of the previous two or three days". So the yardstick is a rolling  |
//| window, and a bar is loud when it stands up against BOTH the peak  |
//| and the average of that window — peak alone lets a merely-average  |
//| bar through on a quiet stretch, average alone lets a mid-sized bar |
//| through next to a genuine climax.                                  |
//+------------------------------------------------------------------+
// How many bars back does the CURRENT SWING run? Walks back from `from` looking for the
// pivot that started this leg — a bar whose high (buy) or low (sell) stands clear of
// InpSwingPivot bars on each side. Clamped so a missing pivot cannot return 3 bars or
// the whole chart.
int SwingLen(int from, int side) {
   int cap = MathMax(InpSwingMin + 1, InpVolLookback);
   for (int k = from + InpSwingPivot; k < from + cap; k++) {
      bool piv = true;
      for (int q = 1; q <= InpSwingPivot && piv; q++) {
         if (side > 0) {                       // buy: the leg began at a swing HIGH
            if (bHigh(k) <= bHigh(k - q) || bHigh(k) <= bHigh(k + q)) piv = false;
         } else {                              // sell: at a swing LOW
            if (bLow(k) >= bLow(k - q) || bLow(k) >= bLow(k + q)) piv = false;
         }
      }
      if (!piv) continue;
      int len = k - from + 1;
      if (len < InpSwingMin) continue;         // too short to judge anything by
      return len;
   }
   return cap;                                  // no pivot found — fall back to the cap
}

bool VolStats(int from, long &vmax, double &vavg, double &ravg, int side) {
   vmax = 0; vavg = 0; ravg = 0;
   int span = (InpVolWindow == 1) ? SwingLen(from, side) : InpVolLookback;
   g_last_span = span;
   int n = 0;
   // THE LEG ORIGIN. This loop already walks back to the pivot that began the move, so
   // the extreme it passes IS the level price retraced from - mode 2's target.
   g_swing_px = (side > 0) ? -1.0 : 1e18;
   double eff = 0.0; int neff = 0;
   for (int k = from; k < from + span; k++) {
      long v = BarVolume(k);
      double r = bRange(k);
      if (side > 0) { if (bHigh(k) > g_swing_px) g_swing_px = bHigh(k); }
      else          { if (bLow(k)  < g_swing_px) g_swing_px = bLow(k);  }
      if (v <= 0) continue;
      if (r > 0) { eff += (double)v / r; neff++; }
      if (v > vmax) vmax = v;
      vavg += (double)v;
      ravg += r;
      n++;
   }
   // Half the window is enough to judge by; less than that and we are at the very
   // start of the data with no "recent past" to compare against, so stand down.
   // UNDER STRICT OANDA THE WINDOW MUST BE WHOLE. Skipping absent minutes would quietly
   // shrink the yardstick every setup is measured against — the same feed-mixing one
   // level down that InpOandaStrict exists to prevent.
   if (InpOandaVolume == 1 && InpOandaStrict && n < span) return false;
   if (n < span / 2 || n < 5 || vmax <= 0) return false;
   vavg /= n;
   ravg /= n;
   g_eff_avg = (neff > 0) ? eff / neff : 0.0;
   return true;
}

//+------------------------------------------------------------------+
//| LAW 9 — higher-timeframe trend, OFF by default                    |
//| Returns +1 up, -1 down, 0 flat/unknown.                           |
//+------------------------------------------------------------------+
int TrendDir() {
   if (InpTrendTF <= 0) return 0;
   ENUM_TIMEFRAMES tf = (InpTrendTF == 15) ? PERIOD_M15
                      : (InpTrendTF == 30) ? PERIOD_M30
                      : (InpTrendTF == 60) ? PERIOD_H1 : PERIOD_H4;
   int n = MathMax(3, InpTrendBars);
   double now  = iClose(_Symbol, tf, 1);
   double then = iClose(_Symbol, tf, n);
   if (now == 0 || then == 0) return 0;
   if (now > then) return 1;
   if (now < then) return -1;
   return 0;
}

bool InSession() {
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   if (InpSessFrom <= InpSessTo) return (t.hour >= InpSessFrom && t.hour < InpSessTo);
   return (t.hour >= InpSessFrom || t.hour < InpSessTo);   // window wrapping midnight
}

int OpenDecisions() {
   int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) n++;
   }
   return n;
}

//+------------------------------------------------------------------+
//| The setup.  side = +1 buy, -1 sell.                               |
//|                                                                   |
//| Bar indices are set by InpConfirmMode (see below); the 2-bar setup sits |
//| behind the reaction, oldest last. The whole judgement is made on    |
//| CLOSED bars only — a forming bar's volume is a fraction of what it |
//| will end as, and comparing it to a finished bar is the classic way |
//| to invent a signal that evaporates on the next tick.               |
//+------------------------------------------------------------------+
bool Detect(int side, double &sl_level, string &why) {
   int nb = MathMax(2, MathMin(3, InpSetupBars));

   // THE RUN, COUNTED NOT ASSUMED. He waits for the turn: "it could be three or more
   // reds". So walk back from the bar before the reaction while the bars keep closing
   // the setup's way, and let THAT be the setup. Direction is mandatory here — a run
   // "until the reds stop" has no meaning if the bars need not be red.
   int rr = (InpConfirmMode == 1) ? 3 : ((InpConfirmMode == 2) ? 2 : 1);
   if (InpSetupAuto) {
      int run = 0, gaps = 0, lastOurs = 0;
      for (int k = rr + 1; k <= rr + MathMax(InpSetupMin, InpSetupMax); k++) {
         bool ours = (side > 0) ? bDown(k) : bUp(k);
         if (!ours) {
            // The bar touching the reaction must be ours, and the budget is finite.
            if (k == rr + 1 || gaps >= InpSetupGaps) break;
            gaps++;
            run++;
            continue;
         }
         run++;
         lastOurs = run;                 // never let the campaign END on a contrary bar
      }
      run = lastOurs;
      if (run < MathMax(2, InpSetupMin)) { g_rej_dir++; return false; }
      nb = run;
   }

   // WHERE THE REACTION BAR SITS.
   // Mode 0 is his aggressive entry — Part 9: "I take an aggressive entry, my entry is
   // right here" — the reaction bar IS the entry bar, so it is bar 1.
   // Mode 1 is his confirmed entry — Part 9: "after this they did a testing, we call it
   // a NO SUPPLY TEST... if the test has small volume you should wait for the next bar
   // to be bullish, then the setup is confirmed." That costs two bars, so the reaction
   // sits at bar 3 with the test at bar 2 and the confirming bar at bar 1.
   int r = (InpConfirmMode == 1) ? 3 : ((InpConfirmMode == 2) ? 2 : 1);  // the REACTION bar
   int c0 = r + 1;                              // index of the newest 2-BAR SETUP bar
   int need = c0 + nb + InpVolLookback + 2;
   if (Bars(_Symbol, PERIOD_CURRENT) < need + InpVolLookback) return false;

   long vmax; double vavg, ravg;
   if (!VolStats(c0 + nb, vmax, vavg, ravg, side)) return false;
   g_seen++;
   if (vmax > g_vmax_seen) g_vmax_seen = vmax;

   //--- LAW 4: the 2-bar setup runs AGAINST the trade we are about to take.
   // Buying needs the effort to have been on the way DOWN (bars closing down);
   // that is where the absorbed selling sits.
   long vsum = 0, vmin_setup = 0;
   double worst_loud = 1.0, best_loud_bar = 0.0;
   double ext = (side > 0) ? bLow(c0) : bHigh(c0);
   int dirGaps = 0;
   for (int q = 0; q < nb; q++) {
      int k = c0 + q;
      if (InpStrictDir || InpSetupAuto) {
         bool ours = (side > 0) ? bDown(k) : bUp(k);
         if (!ours) {
            // Spend the same gap budget the run-counter used, instead of refusing outright.
            if (dirGaps >= InpSetupGaps) { g_rej_dir++; return false; }
            dirGaps++;
         }
      }
      long v = BarVolume(k);
      if (v <= 0) return false;

      // LAW 5, two readings of the same sentence. Zee wrote "these volumes will be
      // that SESSION'S HIGHEST VOLUMES" (plural — mode 0, every bar stands up against
      // the rolling peak). Part 8 says "the BIGGEST volume is here", singular — mode 1,
      // one standout bar carries the 2-bar setup while the rest need only beat the average.
      // Mode 0 is the literal reading and is tested first; mode 1 exists because three
      // consecutive bars each at 70% of a rolling maximum may simply never happen.
      double loud = (double)v / (double)vmax;
      if (q == 0 || loud < worst_loud) worst_loud = loud;
      if (loud > best_loud_bar) best_loud_bar = loud;
      if (InpBigMode == 0 && (double)v < InpBigPct * (double)vmax) {
         if (worst_loud > g_best_loud) g_best_loud = worst_loud;
         g_rej_loud++; return false;
      }
      if ((double)v < InpBigAvg * vavg) { g_rej_loud++; return false; }

      // LAW 4 — optional: the effort must ESCALATE. Part 4: the second bar's volume
      // higher than the first, the third "even higher than the previous two".
      // HIS SENSE OF RISING: the bar nearest the turn (q == 0, index c0) must be the
      // loudest of the whole run — "the third red candle with even higher volume than
      // previous two".
      if (InpRisingVol && q > 0 && v >= BarVolume(c0)) { g_rej_rise++; return false; }
      vsum += v;
      if (vmin_setup == 0 || v < vmin_setup) vmin_setup = v;
      if (side > 0) ext = MathMin(ext, bLow(k));
      else          ext = MathMax(ext, bHigh(k));
   }
   double vsetup = (double)vsum / nb;
   if (InpBigMode == 1 && best_loud_bar < InpBigPct) {
      if (best_loud_bar > g_best_loud) g_best_loud = best_loud_bar;
      g_rej_loud++; return false;
   }
   double reach = (InpBigMode == 1) ? best_loud_bar : worst_loud;
   if (reach > g_best_loud) g_best_loud = reach;

   //--- LAW 7: anomaly — the last 2-bar setup bar spends huge volume for tiny spread.
   if (InpAnomaly) {
      if (ravg <= 0) return false;
      if (bRange(c0) > InpAnomalyMax * ravg) { g_rej_anom++; return false; }
   }
   // ...and the other half of the same candle: the effort that bought nothing.
   if (InpCapVol > 0.0) {
      if (vavg <= 0) return false;
      if ((double)BarVolume(c0) < InpCapVol * vavg) { g_rej_cap++; return false; }
   }

   // DIAGRAM 9: the same bar judged the way he judges it - volume against distance.
   if (InpEffortMin > 0.0) {
      double rc = bRange(c0);
      if (rc <= 0 || g_eff_avg <= 0) return false;
      if (((double)BarVolume(c0) / rc) < InpEffortMin * g_eff_avg) { g_rej_cap++; return false; }
   }

   //--- LAW 13: the fake break. The 2-bar setup must take out a recent extreme, and the
   // reaction must close back INSIDE it — Zee's tier-3 "strongest" case.
   if (InpFakeBreak) {
      double lvl = (side > 0) ? bLow(c0 + nb) : bHigh(c0 + nb);
      for (int k = c0 + nb; k < c0 + nb + InpSweepLook; k++) {
         if (side > 0) lvl = MathMin(lvl, bLow(k));
         else          lvl = MathMax(lvl, bHigh(k));
      }
      if (side > 0) {
         if (ext >= lvl)       { g_rej_fake++; return false; }  // never swept the low
         if (bClose(r) <= lvl) { g_rej_fake++; return false; }  // no close back inside
      } else {
         if (ext <= lvl)       { g_rej_fake++; return false; }
         if (bClose(r) >= lvl) { g_rej_fake++; return false; }
      }
   }

   //--- LAW 2: the reaction names the side.
   if (side > 0 && !bUp(r))   { g_rej_react++; return false; }
   if (side < 0 && !bDown(r)) { g_rej_react++; return false; }

   // Part 15: "its closing is strongly bullish". A doji that happens to close a tick
   // up is not a reaction, so the body has to carry the bar.
   double rng1 = bRange(r);
   if (rng1 <= 0) return false;
   if (bBody(r) < InpBodyFrac * rng1) { g_rej_body++; return false; }

   g_react_ratio = (ravg > 0) ? (rng1 / ravg) : 0.0;

   // "a LARGER SPREAD low volume engulfing reaction candle"
   if (InpReactSpread > 0.0) {
      if (ravg <= 0) return false;
      if (rng1 < InpReactSpread * ravg) { g_rej_body++; return false; }
   }

   // WHERE the close sits, not just how big the body is.
   if (InpCloseLoc > 0.0) {
      double loc = (side > 0) ? (bClose(r) - bLow(r)) / rng1
                              : (bHigh(r) - bClose(r)) / rng1;
      if (loc < InpCloseLoc) { g_rej_loc++; return false; }
   }

   if (InpEngulf) {
      if (side > 0 && bClose(r) <= bHigh(c0)) return false;
      if (side < 0 && bClose(r) >= bLow(c0))  return false;
   }

   //--- LAW 3: THE TRIGGER. The reaction must arrive on LOW volume.
   // Part 15: "the lower the volume on it, the stronger the signal. If a big volume
   // comes, SKIP it, wait more." So this is a veto, not a score.
   long v1 = BarVolume(r);
   if (v1 <= 0) return false;
   // WHICH "LOW" DOES HE MEAN? Mode 0 reads it as low RELATIVE TO THE CLIMAX just
   // seen — the collapse he draws on the chart. Mode 1 reads it as low for this market
   // generally, i.e. below the recent average. Volume is strongly autocorrelated, so
   // the bar right after three loud bars is itself usually loud: the two-day probe
   // never got below 0.83x 2-bar setup. Mode 1 exists because if that holds over a month,
   // mode 0 is not a strict rule — it is an impossible one, and the distinction is
   // worth a receipt rather than a guess.
   double vref = (InpQuietRef == 1) ? vavg : vsetup;
   double qr = (double)v1 / MathMax(1.0, vref);
   if (qr < g_best_quiet) g_best_quiet = qr;
   bool quiet = ((double)v1 <= InpLowVolPct * vref);

   //--- THE FLOOR (Zee, 2026-09-15). He asked whether a reaction sitting too CLOSE to
   // the selling volume is what fails. Measured over 305 joined fires it is not: the
   // winners' median ratio is 0.856 and the losers' 0.865 — no separation. What the
   // same data does show, in BOTH walk-forward halves independently, is the opposite
   // end: the quietest fifth (below 0.76x) is the WORST group on the book — 36% WR and
   // $6.40 a trade against $27 in the middle band. A reaction that dead is not a
   // stronger imbalance, it is nobody turning up, and the move does not follow through.
   // So the shape is a BAND, not a ceiling. This is the floor; it is OFF by default
   // until it survives out-of-sample.
   if (InpMinVolPct > 0.0 && (double)v1 < InpMinVolPct * vref) { g_rej_quiet++; return false; }

   //--- LAW 6: the wick. On a big-volume bar a wick against the move says the volume
   // was aggression that WON, not absorption that is still sitting there — which is
   // the one case the teacher says not to wait on.
   double upper = bHigh(r) - MathMax(bOpen(r), bClose(r));
   double lower = MathMin(bOpen(r), bClose(r)) - bLow(r);
   bool wick = (side > 0) ? (lower >= InpWickFrac * rng1)
                          : (upper >= InpWickFrac * rng1);

   if (InpWickMode == 1 && !wick) { g_rej_quiet++; return false; }  // require outright
   if (!quiet) {
      // Part 6: "in the case of aggressive selling, even if a big volume comes, you
      // don't wait — you enter here." Mode 2 is that exception, and ONLY that.
      if (!(InpWickMode == 2 && wick)) { g_rej_quiet++; return false; }
   }

   //--- THE NO-SUPPLY TEST (InpConfirmMode = 1).
   // Part 9: "after this they did a testing — we call it a NO SUPPLY TEST. If the test
   // has a small volume you should wait for the next bar to be bullish, then the setup
   // is confirmed. A big volume on the test would have meant sustained buying."
   //
   // So the test bar must (a) probe BACK toward the 2-bar setup, (b) do it on volume lower
   // than the reaction's, and (c) FAIL to take out the setup extreme — a test that
   // breaks the low is not a test, it is the setup being wrong. Then the bar after it
   // has to close our way, which is the actual entry bar.
   if (InpConfirmMode == 1 || InpConfirmMode == 2) {
      int tb = (InpConfirmMode == 1) ? 2 : 1;      // the TEST bar
      long vt = BarVolume(tb);
      if (vt <= 0) { g_rej_test++; return false; }
      // MEASURED AGAINST THE CLIMAX, NOT AGAINST THE REACTION. The first cut of this
      // compared the test bar to the reaction bar — but LAW 3 has already forced the
      // reaction to be quiet, so that asked the test to be quieter than something
      // already quiet. It rejected 100% of setups: 48 sweep passes over seven months
      // fired ZERO trades. Every "small volume" the teacher names is small next to the
      // effort that came before it, so the test uses the same reference as LAW 3.
      if ((double)vt > InpTestVolPct * vref) { g_rej_test++; return false; }
      if (InpTestRed) {
         bool against = (side > 0) ? bDown(tb) : bUp(tb);
         if (!against) { g_rej_test++; return false; }
      }
      // A test that BREAKS the setup extreme is not a test, it is the setup being wrong.
      if (side > 0) { if (bLow(tb)  <= ext) { g_rej_test++; return false; } }
      else          { if (bHigh(tb) >= ext) { g_rej_test++; return false; } }

      // Mode 1 alone waits for the bar AFTER the test to close our way. Mode 2 treats the
      // test as the reaction itself and enters on it, so there is nothing further to wait for.
      if (InpConfirmMode == 1) {
         if (side > 0) {
            if (!bUp(1))                { g_rej_test++; return false; }
            if (bClose(1) <= bClose(2)) { g_rej_test++; return false; }
         } else {
            if (!bDown(1))              { g_rej_test++; return false; }
            if (bClose(1) >= bClose(2)) { g_rej_test++; return false; }
         }
      }
   }

   //--- LAW 9 (off by default)
   int td = TrendDir();
   if (td != 0 && td != side) { g_rej_trend++; return false; }

   //--- LAW 8: the stop. `ext` above is the SETUP's extreme and is still what the
   // fake-break and no-supply tests need, so the stop gets its own reference.
   double sref;
   if (InpStopRef == 0)
      sref = (side > 0) ? bLow(r) : bHigh(r);          // his spec: the reaction candle
   else
      sref = (side > 0) ? MathMin(ext, bLow(r))        // the old, wider behaviour
                        : MathMax(ext, bHigh(r));
   if (InpConfirmMode == 1 || InpConfirmMode == 2) {
      // whatever happened after the reaction, the stop has to sit outside everything the
      // setup has already defended - mode 1 has test+confirm, mode 2 has the test alone
      int deep = (InpConfirmMode == 1) ? 2 : 1;
      for (int k = 1; k <= deep; k++) {
         if (side > 0) sref = MathMin(sref, bLow(k));
         else          sref = MathMax(sref, bHigh(k));
      }
   }
   double buf = InpSlBufPts * _Point;
   sl_level = (side > 0) ? sref - buf : sref + buf;

   why = StringFormat("setup %d bars vol %.0f | swing %d bars (max %d avg %.0f) | "
                      "reaction vol %d = %.2fx%s%s",
                      nb, vsetup, g_last_span, (int)vmax, vavg, (int)v1,
                      (double)v1 / MathMax(1.0, vsetup),
                      quiet ? " QUIET" : " LOUD",
                      wick ? " +wick" : "");

   // LAW 10: leave the level behind. The "low line" is the lowest point the pattern
   // reached before it turned - the setup's own extreme or the reaction's, whichever is
   // further - because that is the line he draws and retraces back to.
   if (InpRetrace) {
      double line = (side > 0) ? MathMin(ext, bLow(r)) : MathMax(ext, bHigh(r));
      AddLevel(side, line);
   }
   return true;
}

//+------------------------------------------------------------------+
//| Fire                                                              |
//+------------------------------------------------------------------+
void Fire(int side, double sl_level, string why) {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double entry = (side > 0) ? ask : bid;
   double risk  = MathAbs(entry - sl_level);

   // The floor exists because his 2-3 pips are FX pips on a pair whose spread is a
   // fraction of gold's. A stop narrower than the spread is not a tight stop, it is a
   // guaranteed loss on entry.
   double minr = InpMinSlPts * _Point;
   double maxr = InpMaxSlPts * _Point;
   if (risk < minr) {
      risk = minr;
      sl_level = (side > 0) ? entry - risk : entry + risk;
   }
   if (risk > maxr) {
      if (InpVerbose)
         PrintFormat("[VSISA] refused: risk %.0f pts > cap %d", risk / _Point, InpMaxSlPts);
      return;
   }

   double tp = 0.0;
   if (InpTargetMode == 1) {
      double d = InpTargetPts * _Point;
      tp = (side > 0) ? entry + d : entry - d;
   } else if (InpTargetMode == 2) {
      tp = g_swing_px;                       // the level the leg came FROM
   } else if (InpTargetR > 0) {
      tp = (side > 0) ? entry + InpTargetR * risk : entry - InpTargetR * risk;
   }

   // GUARDS for the decoupled modes. Once the target stops being a multiple of the
   // stop it can land anywhere - on the wrong side of entry, or so close that the
   // spread eats it. Reward is measured in R purely so the two bounds read in the same
   // unit as everything else; it does not re-couple the target to the stop.
   if (tp > 0.0 && InpTargetMode != 0) {
      double reward = (side > 0) ? (tp - entry) : (entry - tp);
      if (reward <= 0.0 || reward < InpTgtMinR * risk) {
         g_rej_tgt++;
         if (InpVerbose)
            PrintFormat("[VSISA] refused: target %.2f is %.2fR from entry %.2f (min %.2fR)",
                        tp, reward / MathMax(risk, _Point), entry, InpTgtMinR);
         return;
      }
      if (InpTgtMaxR > 0.0 && reward > InpTgtMaxR * risk) {
         reward = InpTgtMaxR * risk;
         tp = (side > 0) ? entry + reward : entry - reward;
      }
   }

   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   sl_level = NormalizeDouble(sl_level, dg);
   if (tp > 0) tp = NormalizeDouble(tp, dg);

   // SIZE BY THE GRADE OF THE REACTION, not by conviction in general.
   double lots = InpLots;
   if (InpSizeBySpread) {
      double m = InpSizeM0;
      if      (g_react_ratio >= InpSizeT2) m = InpSizeM2;
      else if (g_react_ratio >= InpSizeT1) m = InpSizeM1;
      lots = InpLots * m;
      double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      double lo = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      double hi = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
      if (st > 0) lots = MathFloor(lots / st + 0.5) * st;
      if (lo > 0) lots = MathMax(lo, lots);
      if (hi > 0) lots = MathMin(hi, lots);
   }

   int n = MathMax(1, InpTickets);
   int placed = 0;
   for (int i = 0; i < n; i++) {
      string tag = StringFormat("vsisa_%d_%d", g_fires, i);
      bool ok = (side > 0) ? trade.Buy (lots, _Symbol, 0, sl_level, tp, tag)
                           : trade.Sell(lots, _Symbol, 0, sl_level, tp, tag);
      if (ok) placed++;
   }
   if (placed == 0) {
      if (InpVerbose) PrintFormat("[VSISA] send failed: %d %s", trade.ResultRetcode(),
                                  trade.ResultRetcodeDescription());
      return;
   }
   g_fires++;
   g_cool = InpCoolBars;
   g_last_fire = iTime(_Symbol, PERIOD_CURRENT, 0);

   if (InpVerbose)
      PrintFormat("[VSISA] #%d %s %.2f lots @ %.2f SL %.2f (%.0f pts) TP %.2f (%.1fR) | spread %.2fx | %s",
                  g_fires, (side > 0) ? "BUY" : "SELL", lots, entry, sl_level,
                  risk / _Point, tp,
                  (tp > 0 ? MathAbs(tp - entry) / MathMax(risk, _Point) : 0.0),
                  g_react_ratio, why);
}

//+------------------------------------------------------------------+
//| Breakeven — LAW 8's optional half                                 |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| THE RATCHET — lock the highest R rung the trade has reached.       |
//+------------------------------------------------------------------+
void RatchetCheck() {
   if (InpRatchetStart <= 0.0 || InpRatchetStep <= 0.0) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;

      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      long   type = PositionGetInteger(POSITION_TYPE);

      // The ORIGINAL risk, which the ratchet has usually already eaten into, so it is
      // rebuilt from the target rather than from the live stop.
      double risk = 0.0;
      if (tp > 0 && InpTargetR > 0)
         risk = MathAbs(tp - open) / InpTargetR;
      if (risk <= 0.0 && sl > 0) risk = MathAbs(open - sl);
      if (risk <= 0.0) continue;

      double px = (type == POSITION_TYPE_BUY)
                ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double gained = ((type == POSITION_TYPE_BUY) ? (px - open) : (open - px)) / risk;
      if (gained < InpRatchetStart) continue;

      // highest rung actually reached
      double rungs = MathFloor((gained - InpRatchetStart) / InpRatchetStep);
      double lock  = InpRatchetStart + rungs * InpRatchetStep;
      if (lock <= 0.0) continue;

      double want = (type == POSITION_TYPE_BUY) ? open + lock * risk
                                                : open - lock * risk;
      want = NormalizeDouble(want, _Digits);
      // never backwards, and never through the market
      if (type == POSITION_TYPE_BUY  && (want <= sl || want >= px)) continue;
      if (type == POSITION_TYPE_SELL && (want >= sl || want <= px)) continue;
      trade.PositionModify(tk, want, tp);
   }
}

void BreakEvenCheck() {
   if (InpBreakEvenR <= 0) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;

      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      if (sl == 0) continue;
      long   type = PositionGetInteger(POSITION_TYPE);
      double risk = MathAbs(open - sl);
      if (risk <= 0) continue;

      double px = (type == POSITION_TYPE_BUY)
                ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double gained = (type == POSITION_TYPE_BUY) ? (px - open) : (open - px);
      if (gained < InpBreakEvenR * risk) continue;

      // already at or past breakeven — nothing to do
      if (type == POSITION_TYPE_BUY  && sl >= open) continue;
      if (type == POSITION_TYPE_SELL && sl <= open) continue;
      trade.PositionModify(tk, NormalizeDouble(open, _Digits), tp);
   }
}

//+------------------------------------------------------------------+
int OnInit() {
   if (InpOandaVolume == 1) LoadOandaVol();
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(30);
   // KEEP THIS STRING IN STEP WITH #property version — the Diamond's banner said
   // v1.14 for nine versions and nobody could tell from a log which build was live.
   // THE BANNER MUST DESCRIBE THE BUILD THAT IS RUNNING. It was still announcing
   // "2-bar setup 2 bars" after the run became self-counting, and said nothing about
   // the swing window or which candle the stop hangs from - the three things that
   // actually changed. A banner that misreports the build is worse than no banner.
   PrintFormat("[VSISA] v1.16 - setup %s | vol vs %s | big>=%.2fxmax/%.2fxavg | "
               "reaction<=%.2fx %s | stop %s +%dpts (floor %d cap %d) | TP %.1fR BE %.1fR "
               "| trendTF %d wick %d confirm %d anomaly %d fake %d | feed %s "
               "| %.2f lots x%d | magic %d",
               InpSetupAuto ? StringFormat("AUTO %d-%d bars", InpSetupMin, InpSetupMax)
                            : StringFormat("fixed %d bars", InpSetupBars),
               (InpVolWindow == 1) ? StringFormat("SWING (pivot %d min %d cap %d)",
                                                  InpSwingPivot, InpSwingMin, InpVolLookback)
                                   : StringFormat("last %d bars", InpVolLookback),
               InpBigPct, InpBigAvg,
               InpLowVolPct, (InpQuietRef == 1) ? "avg" : "setup",
               (InpStopRef == 0) ? "under REACTION candle" : "under whole setup",
               InpSlBufPts, InpMinSlPts, InpMaxSlPts,
               InpTargetR, InpBreakEvenR,
               InpTrendTF, InpWickMode, InpConfirmMode, (int)InpAnomaly, (int)InpFakeBreak,
               (InpOandaVolume == 1) ? (InpOandaStrict ? "OANDA-STRICT" : "OANDA")
                                     : "BROKER-TICKS",
               InpLots, InpTickets, InpMagicNumber);

   // WHICH NUMBER IS THIS BROKER ACTUALLY GIVING US (2026-09-12).
   // Zee moved VSISA to Axi because "AXI volume happens to be more accurate on the
   // VSISA strategy". Whether that is true is a FACT ABOUT THE FEED, and it is knowable
   // in one line at startup instead of guessed: on Blueberry iRealVolume returned 0 for
   // gold CFD on every one of 8,006,496 reads, so the strategy silently ran on tick
   // count. This says out loud which one Axi hands back, on the symbol actually attached.
   {
      long rv = 0, tv = 0; int probed = 0;
      for (int k = 1; k <= 20; k++) {
         long r = iRealVolume(_Symbol, PERIOD_CURRENT, k);
         long t = iVolume(_Symbol, PERIOD_CURRENT, k);
         if (t > 0) { rv += r; tv += t; probed++; }
      }
      if (probed == 0)
         Print("[VSISA] FEED PROBE: no bars yet — check again once history loads");
      else if (rv > 0)
         PrintFormat("[VSISA] FEED PROBE on %s: REAL VOLUME available (%d bars: real %I64d "
                     "vs tick %I64d). BarVolume() will judge on REAL volume.",
                     _Symbol, probed, rv, tv);
      else
         PrintFormat("[VSISA] FEED PROBE on %s: no real volume (%d bars, tick total "
                     "%I64d). BarVolume() falls back to TICK COUNT, same as Blueberry.",
                     _Symbol, probed, tv);
   }

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   PrintFormat("[VSISA] stopped, %d decisions taken", g_fires);
   // The funnel, widest gate first. Whichever line eats the candidates is the law to
   // aim a variant at — guessing which one is what cost the first five-day run.
   PrintFormat("[VSISA] FUNNEL candidates %d | dir %d | not loud %d | not rising %d | "
               "anomaly %d | fake %d | reaction %d | body %d | not quiet %d | test %d "
               "| trend %d | FIRED %d",
               g_seen, g_rej_dir, g_rej_loud, g_rej_rise, g_rej_anom, g_rej_fake,
               g_rej_react, g_rej_body, g_rej_quiet, g_rej_test, g_rej_trend, g_fires);
   PrintFormat("[VSISA] FUNNEL target-too-near %d | cap-bar %d | close-loc %d",
               g_rej_tgt, g_rej_cap, g_rej_loc);
   PrintFormat("[VSISA] VOLUME SOURCE OANDA %I64d | iRealVolume %I64d | broker tick "
               "count %I64d — %s", g_ov_hit, g_rv_hit, g_rv_miss,
               (g_ov_hit > 0 && g_rv_miss == 0 && g_rv_hit == 0)
                   ? "ALL OANDA (his feed)"
                   : ((g_ov_hit == 0 && g_rv_hit == 0)
                      ? "EVERY judgement used BROKER TICK COUNT" : "MIXED"));
   PrintFormat("[VSISA] REACH loudest lookback max %d | best 2-bar setup/max %.2f "
               "(need %.2f) | best reaction/2-bar setup %.2f (need %.2f)",
               (int)g_vmax_seen, g_best_loud, InpBigPct,
               (g_best_quiet > 900 ? -1.0 : g_best_quiet), InpLowVolPct);
}

void AddLevel(int side, double px) {
   if (g_lvl_n >= VSISA_MAXLVL) {           // drop the oldest to make room
      for (int k = 1; k < g_lvl_n; k++) {
         g_lvl_px[k-1] = g_lvl_px[k];   g_lvl_side[k-1]  = g_lvl_side[k];
         g_lvl_t[k-1]  = g_lvl_t[k];    g_lvl_touch[k-1] = g_lvl_touch[k];
         g_lvl_fired[k-1] = g_lvl_fired[k];
      }
      g_lvl_n--;
   }
   g_lvl_px[g_lvl_n]    = px;
   g_lvl_side[g_lvl_n]  = side;
   g_lvl_t[g_lvl_n]     = iTime(_Symbol, PERIOD_CURRENT, 0);
   g_lvl_touch[g_lvl_n] = 0;
   g_lvl_fired[g_lvl_n] = 0;
   g_lvl_n++;
}

void DropLevel(int i) {
   for (int k = i + 1; k < g_lvl_n; k++) {
      g_lvl_px[k-1] = g_lvl_px[k];   g_lvl_side[k-1]  = g_lvl_side[k];
      g_lvl_t[k-1]  = g_lvl_t[k];    g_lvl_touch[k-1] = g_lvl_touch[k];
      g_lvl_fired[k-1] = g_lvl_fired[k];
   }
   g_lvl_n--;
}

//+------------------------------------------------------------------+
//| LAW 10 — price comes back to a level a setup already turned from. |
//| A touch that CLOSES BACK on the right side is the entry; touches  |
//| accumulate, so InpRetraceMin can demand the "several times" he    |
//| says makes the move stronger.                                     |
//+------------------------------------------------------------------+
void RetraceCheck() {
   if (!InpRetrace || g_lvl_n == 0) return;
   datetime now = iTime(_Symbol, PERIOD_CURRENT, 0);
   int ps = (int)PeriodSeconds();
   if (ps <= 0) return;
   double tol = InpRetraceTol * _Point;
   double buf = InpSlBufPts * _Point;

   for (int i = g_lvl_n - 1; i >= 0; i--) {
      int age = (int)((now - g_lvl_t[i]) / ps);
      if (age > InpRetraceBars || g_lvl_fired[i] >= InpRetraceMax) { DropLevel(i); continue; }
      if (age < 1) continue;                       // not the setup's own bar

      double lvl = g_lvl_px[i];
      bool touched, held;
      if (g_lvl_side[i] > 0) { touched = (bLow(1)  <= lvl + tol); held = (bClose(1) > lvl); }
      else                   { touched = (bHigh(1) >= lvl - tol); held = (bClose(1) < lvl); }
      if (!touched) continue;

      g_lvl_touch[i]++;                            // count it even if it did not hold
      if (!held || g_lvl_touch[i] < InpRetraceMin) continue;

      // No supply on the retest, or it is just a price touch.
      if (InpRetraceQuiet > 0.0) {
         double av = AvgVolN(InpTestAvgBars);
         long   vt = BarVolume(1);
         if (av <= 0 || vt <= 0) continue;
         if ((double)vt > InpRetraceQuiet * av) continue;
      }
      if (OpenDecisions() >= InpMaxOpen) continue;

      double sl = (g_lvl_side[i] > 0) ? lvl - buf : lvl + buf;
      g_retrace_fires++;
      g_react_ratio = 0.0;       // a level touch has no reaction bar to grade
      Fire(g_lvl_side[i], sl,
           StringFormat("RETRACE touch %d of level %.2f (set %d bars ago)",
                        g_lvl_touch[i], lvl, age));
      g_lvl_fired[i]++;
   }
}

double AvgVolN(int n) {
   double a = 0; int c = 0;
   for (int k = 1; k <= n; k++) {
      long v = BarVolume(k);
      if (v > 0) { a += (double)v; c++; }
   }
   return (c > 0) ? a / c : 0.0;
}

//+------------------------------------------------------------------+
//| The no-supply test, applied to a trade that is ALREADY OPEN.      |
//| Runs once per closed bar. Called from the new-bar block.          |
//+------------------------------------------------------------------+
void TestExitCheck() {
   if (InpTestExit <= 0.0) return;
   double av = AvgVolN(InpTestAvgBars);
   if (av <= 0) return;
   long v1 = BarVolume(1);
   if (v1 <= 0) return;
   if ((double)v1 < InpTestExit * av) return;      // not a loud test - nothing to say

   datetime now = iTime(_Symbol, PERIOD_CURRENT, 0);
   int      ps  = (int)PeriodSeconds();
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;

      long type = PositionGetInteger(POSITION_TYPE);
      // The test closes AGAINST the trade - that is what makes it a test of supply.
      bool against = (type == POSITION_TYPE_BUY) ? bDown(1) : bUp(1);
      if (!against) continue;

      datetime ot = (datetime)PositionGetInteger(POSITION_TIME);
      if (ps <= 0) continue;
      int bars = (int)((now - ot) / ps);
      if (bars < 1 || bars > InpTestWindow) continue;

      if (trade.PositionClose(tk) && InpVerbose)
         PrintFormat("[VSISA] no-supply test FAILED %d bar(s) in: test vol %I64d >= %.2fx avg %.0f - closing #%I64u",
                     bars, v1, InpTestExit, av, tk);
   }
}

//+------------------------------------------------------------------+
//| Has today's realised loss on this magic passed the line?           |
//+------------------------------------------------------------------+
bool DayLossHit() {
   if (InpDayLossStop <= 0.0) return false;
   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime d0 = StructToTime(dt);
   if (!HistorySelect(d0, now + 60)) return false;

   double p = 0.0;
   int nd = HistoryDealsTotal();
   for (int i = 0; i < nd; i++) {
      ulong tk = HistoryDealGetTicket(i);
      if (tk == 0) continue;
      if (HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol) continue;
      if (HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagicNumber) continue;
      if (HistoryDealGetInteger(tk, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      p += HistoryDealGetDouble(tk, DEAL_PROFIT)
         + HistoryDealGetDouble(tk, DEAL_COMMISSION)
         + HistoryDealGetDouble(tk, DEAL_SWAP);
   }
   return (p <= -InpDayLossStop);
}

void OnTick() {
   BreakEvenCheck();
   RatchetCheck();

   // One decision per closed bar. Everything this EA judges is a finished bar, so
   // running the detector on every tick would only re-answer the same question.
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (t == g_last_bar) return;
   g_last_bar = t;

   TestExitCheck();
   RetraceCheck();

   if (DayLossHit()) return;
   if (g_cool > 0) { g_cool--; return; }
   if (!InSession()) return;
   if (OpenDecisions() >= InpMaxOpen) return;

   double sl = 0;
   string why = "";
   if (InpBuys  && Detect(+1, sl, why)) { Fire(+1, sl, why); return; }
   if (InpSells && Detect(-1, sl, why)) { Fire(-1, sl, why); return; }
}
//+------------------------------------------------------------------+
