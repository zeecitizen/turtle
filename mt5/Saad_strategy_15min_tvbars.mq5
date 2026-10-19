//+------------------------------------------------------------------+
//| Saad_strategy_15min.mq5  v1.00 (15-MINUTE variant of Saad v4.03)|
//| Built from mt5/RULES_EMA_SAAD.md. EMA 9 + EMA 50.                |
//|                                                                  |
//| v4.00 (2026-10-12) ports the TradingView indicator               |
//| pine/saad_strategy.pine (v4 engine) so the EA trades what the    |
//| chart shows:                                                     |
//|  * setup candles: pin bar (any direction - the EMA decides),     |
//|    marubozu, hammer / shooting star                              |
//|  * LONG: rule (on the 9 EMA, exit at the 50 EMA) and/or inverse  |
//|    (on the 50 EMA, exit at the 9 EMA); exit when a candle CLOSES |
//|    at the exit EMA (or touches it)                               |
//|  * SHORT: on the 50 / 9 / either EMA; TP = last support at least |
//|    InpMinTpPips below the entry                                  |
//|  * break of the high / low within InpBreakBars candles           |
//|  * SL InpSlPips beyond the candle; skip if risk > InpMaxRiskUsd  |
//|  * "let winners run": when the TP is reached the stop is locked  |
//|    InpLockPips short of it and a trailing stop takes over        |
//|  * a waiting setup is cancelled across the daily close / weekend |
//|  * longs whose exit EMA is below / too close to the entry have   |
//|    no TP: trailing stop from the entry (or exit on a close below)|
//| Tuning switches (all off at the chart's settings): more than one |
//| position, newer setup replaces the waiting one, daily stop /     |
//| target, per-candle-type and per-line switches, trend / slope /   |
//| EMA-gap / price-side filters, spread filter, max TP distance.    |
//|                                                                  |
//| M15 VARIANT (2026-10-11): the same engine as Saad_strategy v4.03 |
//| with five defaults rescaled for 15-minute candles - see          |
//| VERSION_HISTORY "Saad_strategy_15min v1.00". Attach on M15 only.   |
//| v4.02 defaults = the MT5 court winner (2026-10-11/12, Axi real    |
//| ticks Jan 1-Oct 8, 3 random-delay runs each): break +2 pips, SL  |
//| 30, ATR x2.0 trail after the TP, lock exactly at the TP, no new  |
//| trades after +$150 in a day. The rest = Zee's chart settings.    |
//| 1 gold pip = 10 points ($0.10). Hours are broker server hours.   |
//+------------------------------------------------------------------+
#property copyright "turtle"
#property version   "1.27"
#property strict

#include <Trade/Trade.mqh>
#resource "\\Indicators\\SaadEMAs.ex5"   // v1.22: EMA 9 (blue) + EMA 50 (red) drawn thick, embedded: no separate install
// v1.27 (Zee 2026-10-19: "keep nose 0.35"): InpNoseMax 0.20 -> 0.35 - every other v1.26 setting unchanged. MT5 full year: nose 0.30-0.45
//       all +$244-248k, PF 2.74-2.79, DD $28.3k (v1.26 +$211k, PF 2.52, DD $35k); about $24k of the gain is one trade (Mar 31 BUY)
// v1.26 (Zee 2026-10-19: "make our chart setup PF 2.53 be the next version of saad_ea_15min"): the chart setup as DEFAULTS -
// EMA 16/32, break 3, ATR stop 1.6x, ADX 30, no chop / max risk, next-EMA exit, range boxes + stand aside, 2 lots.
// Built from the TEST copy (Zee 2026-10-19: "take the current settings from tradingview and test them in MT5 on saad_ea_15min (just test, if
// implementation needed make a test copy)"): Saad_strategy_15min v1.25 + the indicator's TOP / BOTTOM range boxes and its "Stand aside
// while it would have run" (a ghost trade: same stop and exit, no order, no new trade until it ends). TEST - never attach to an account.
// v1.25 (Zee 2026-10-19: "ok test it"): InpExitMode - the indicator's two chart-only TP1 METHODs as EA exits (OFF by default, = v1.24)
// v1.24 (Zee 2026-10-19: "run the optimizer for 15 min to saad_strategy_15min on all settings that u think made the most effect"):
//       the 1-min EA's ATR band + ADX gate and its OnTester optimizer score - ALL OFF by default, trading identical to v1.23
// v1.23 (Zee): EMA touch tolerance 1 pip ($0.10) - a candle within 10 cents of the EMA counts as on it (MT5: +$8.8k full year, both halves, random delay +$7.5k)
// v1.22 (Zee): the two EMAs it trades on are drawn on the chart when attached - EMA 9 thick blue, EMA 50 thick red (InpShowEmas)
// v1.21 (Zee): EXIT label and SETUP label text in black; the TP1 labels in blue (InpExitTextColor / InpSetupTextColor / InpTpTextColor)
// v1.20 (Zee): stop-loss text in black (InpSlTextColor); the stop LINES stay red
// v1.19 (Zee): chart text colour by side - everything about a LONG in dark green, about a SHORT in red
// v1.18 (Zee): every trade's comment names the EA + version, so the account history shows where it came from
// TEST tvbars (Zee 2026-10-20: "ok, make the EA read TradingView's own candles, and give me MT5 result for Aug,Sept, Oct"): v1.27 with
//       every decision on the CHART's 15-min candles (bridge file from monitor/saad_compare/tv_bars_bridge.py): the chart's candle clock
//       (Monday 01:01), EMAs, ATR, ADX (MT5's formula on the chart's candles) and range boxes; the chart's candle decides breaks / stops
//       the two feeds disagree on by cents; no setup on a candle that closed while a trade was open. TEST - never attach to an account.
#define EA_COMMENT "Saad15 tvbars"

//--- the two lines
input int    InpEmaFast     = 16;      // InpEmaFast
input int    InpEmaSlow     = 32;     // InpEmaSlow
input bool   InpShowEmas    = true;   // InpShowEmas — draw the two EMAs on the chart: EMA 9 thick blue, EMA 50 thick red

//--- ① setup candle
input double InpWickMin     = 0.45;   // InpWickMin — pin: long wick >= this x range [v1.13: 0.35->0.45]
input double InpBodyMax     = 0.6;   // InpBodyMax — pin: body <= this x range
input double InpNoseMax     = 0.35;   // InpNoseMax — pin: short wick <= this x range [v1.27: 0.20 -> 0.35]
input bool   InpPinDir      = false;  // InpPinDir — pin must point the trade way (false = any pin, the EMA decides)
input bool   InpPinColor    = false;  // InpPinColor — pin body must close the trade way too: LONG green, SHORT red (with InpPinDir)
input bool   InpUsePin      = true;   // InpUsePin — accept pin bars
input bool   InpMarubozu    = true;   // InpMarubozu — accept a marubozu
input double InpMaruBody    = 0.53;   // InpMaruBody — marubozu: body >= this x range [v1.09: 0.70->0.50, Zee; 0.35-0.55 plateau] [v1.14: 0.50->0.53]
input bool   InpHammer      = true;   // InpHammer — accept hammers (LONG)
input bool   InpStar        = true;   // InpStar — accept shooting stars (SHORT)
input double InpHamRatio    = 2.5;    // InpHamRatio — hammer: long wick >= this x body [v1.13: 3->2.5]
input double InpHamNose     = 0.5;   // InpHamNose — hammer: opposite wick <= this x range
input double InpMinRangeAtr = 0.55;   // InpMinRangeAtr — candle range >= this x ATR(14) (0 = off) [v1.14: 0.50->0.55]

//--- ① on the EMA
input int    InpLongRule    = 2;      // InpLongRule — 0 on 9 EMA exit 50 (rules) · 1 on 50 exit 9 (inverse) · 2 both
input int    InpShortLine   = 1;      // InpShortLine — 0 the 50 EMA (rules) · 1 the 9 EMA · 2 either [M15: 2->1, SHORT setups on the 9 EMA]
input int    InpTouchMode   = 0;      // InpTouchMode — 0 candle touches the EMA · 1 wick touches, body on the trade side
input double InpTouchPips   = 1;      // InpTouchPips — touch tolerance [v1.23: 0->1; 1-3 pips plateau, 4+ worse]
input bool   InpLongExitAbove = false;// InpLongExitAbove — LONG only when its exit EMA is above the candle

//--- ② break · ③ entry
input int    InpBreakBars   = 1;      // InpBreakBars — the high/low must break within this many candles [M15: 2->1, one 15-min candle = three 5-min ones]
input double InpBreakPips   = 3;      // InpBreakPips — break must clear the high/low by this many pips [v4.02: 0->2, MT5 court]
input bool   InpTrigBid     = true;   // InpTrigBid — LONG break judged on the BID like the chart (false = the ASK, a real buy stop)

//--- ④ stop · ⑤ target
input double InpSlPips      = 31;     // InpSlPips — stop beyond the candle [v4.02: 34->30] [v1.13: 30->35, real-tick court + Jul-Oct holdout]
input double InpMaxRiskUsd  = 20;    // InpMaxRiskUsd — skip if the stop is more than this $ of price away (0 = off) [M15: 9->15; 14-18 plateau, 9 skips 2/3 of M15 setups]
input int    InpLongExit    = 1;      // InpLongExit — 0 a candle touches the exit EMA · 1 a candle CLOSES at / beyond it
input double InpLongTpPips  = 0;      // InpLongTpPips — LONG: take profit this many pips before the EMA
input int    InpSwingPivot  = 3;      // InpSwingPivot — SHORT "last support" = swing low with this many candles each side
input int    InpSwingLook   = 100;    // InpSwingLook — candles back to search for the support [M15: 300->100 candles = 25 hours]
input double InpShortTpPips = 0;      // InpShortTpPips — SHORT: take profit this many pips before the support
input double InpMinTpPips   = 5;      // InpMinTpPips — TP at least this far from the entry
input double InpMaxTpPips   = 0;      // InpMaxTpPips — skip a SHORT whose support is further than this (0 = off)

//--- ⑥ breakeven
input double InpBeUsd       = 0.0;    // InpBeUsd — stop to entry once price moved this $ (0 = off)
input int    InpNoNewMins   = 0;      // InpNoNewMins — no new setups / entries this many minutes before the day's close (0 = off) [v1.03 30; v1.05 OFF, Zee: costs ~$11k at 1 lot]
input int    InpCloseLossMins = 3;    // InpCloseLossMins — this many minutes before the close: shut trades in loss, keep winners (0 = off) [v1.03, Zee]
input int    InpLongTouch   = 1;      // InpLongTouch — LONG at the exit EMA: 1 on a TOUCH trail $X below the market + TP at the last resistance (Zee 2026-10-12) · 0 old exit
input double InpLongTrailUsd = 2;   // InpLongTrailUsd — ...the trailing stop's distance below the market, $ of price [v1.07: 3->2, Zee]
input bool   InpLongResTp   = true;   // InpLongResTp — ...and aim for the next liquidity: TP2 = last resistance, then TP3 = the one beyond (watched by the EA; the exit is the trail)
input bool   InpLongResTp1  = false;  // InpLongResTp1 — LONG whose exit EMA is below / too close to the entry: TP1 = the next resistance above the entry (false = no TP, trail from entry) [v1.11 Zee; v1.12 OFF: -$70k on real ticks (trailing from entry is better)]
input bool   InpResTp1Ride  = true;   // InpResTp1Ride — with InpLongResTp1: also trail from the entry (2xATR) until that resistance is reached
input int    InpShortTouch  = 1;      // InpShortTouch — SHORT at the support (TP1): 1 trail $X above the market + TP2/TP3 = the supports below (Zee 2026-10-12) · 0 old (lock + ATR trail)
input double InpTrailStepUsd = 0;     // InpTrailStepUsd — widen the $ trail by this much at each TP reached after TP1 (TP2 +1x, TP3 +2x ...; 0 = fixed)
input double InpShortTrailUsd = 2;  // InpShortTrailUsd — ...the trailing stop's distance above the market, $ of price [v1.07: 3->2, Zee]
input double InpBeTpPct     = 0.75;   // InpBeTpPct — CTC: stop to entry once price covered this share of the way to the TP (0 = off) [v1.02, Zee]

//--- ⑦ trailing
input bool   InpTrail       = true;   // InpTrail — use a trailing stop
input int    InpTrailSide   = 2;      // InpTrailSide — 0 LONG only · 1 SHORT only · 2 both
input bool   InpRide        = true;   // InpRide — let winners run: trail from the TP instead of exiting
input int    InpTrailMode   = 2;      // InpTrailMode — 0 low/high of last N candles · 1 X pips behind best · 2 ATR x behind best [v4.02: 0->2 ATR]
input int    InpTrailN      = 6;      // InpTrailN — N candles
input double InpTrailPips   = 30;     // InpTrailPips — X pips
input double InpTrailAtr    = 2;    // InpTrailAtr — ATR multiple [v4.02: 1.3->2.0; 1.75-2.5 plateau]
input double InpTrailStart  = 0;      // InpTrailStart — without ride: start trailing after this many pips of profit
input int    InpRideLock    = 0;      // InpRideLock — when the TP is reached lock the stop at: 0 the TP · 1 the entry · 2 don't lock
input double InpLockPips    = 0;      // InpLockPips — lock this many pips short of the TP [v4.02: 2->0]

//--- ✖ filters
input double InpChopEr      = 0;   // InpChopEr — skip if the efficiency ratio is below this (0 = off) [v1.14: 0.10->0.11]
input int    InpChopErLook  = 16;     // InpChopErLook — efficiency ratio length
input int    InpSessFrom    = 0;      // InpSessFrom — broker hour, inclusive (Axi UTC+3; 0/24 = all day)
input int    InpSessTo      = 24;     // InpSessTo — broker hour, exclusive
input bool   InpGapCancel   = true;   // InpGapCancel — cancel a waiting setup across the daily close / weekend
input int    InpHtfMin      = 0;      // InpHtfMin — higher-timeframe trend filter: 0 off · 15 / 30 / 60 / 240 minutes (trade only with that timeframe's trend)
input int    InpHtfEma      = 90;     // InpHtfEma — the HTF trend EMA (LONG: HTF close above it and it is rising; SHORT the opposite)
input bool   InpTrendAlign  = false;  // InpTrendAlign — LONG only if EMA9 > EMA50, SHORT only if EMA9 < EMA50
input bool   InpPriceSide   = false;  // InpPriceSide — LONG only if the close is above the 50 EMA, SHORT below
input double InpSlopePips   = 0;      // InpSlopePips — the 50 EMA must move this many pips the trade's way...
input int    InpSlopeLook   = 5;      // InpSlopeLook — ...over this many candles (0 pips = off)
input double InpEmaGapPips  = 0;      // InpEmaGapPips — skip if the 9 and 50 EMA are closer than this (0 = off)
input double InpMaxSpreadPts = 0;     // InpMaxSpreadPts — skip an entry while the spread is wider (0 = off)
input int    InpSkipDow     = -1;     // InpSkipDow — no new setups on this weekday (0 Sun .. 6 Sat; -1 none)

//--- v4.01 tuning: geometry
input double InpLockAtUsd   = 0;      // InpLockAtUsd — once price moved this $ the trade's way... (0 = off; VSISA's one-lock ratchet)
input double InpLockUsd     = 0;      // InpLockUsd — ...lock the stop this $ beyond the entry
input double InpFixTpPips   = 0;      // InpFixTpPips — fixed take profit for both sides, no ride (0 = the rules' targets)
input int    InpMaxBars     = 0;      // InpMaxBars — close a trade still open after this many candles (0 = off)
input int    InpCoolBars    = 0;      // InpCoolBars — after a losing trade, no new setups for this many candles (0 = off)

//--- tuning: more trades / daily guard
input int    InpMaxPos      = 1;      // InpMaxPos — positions open at the same time
input bool   InpReplace     = false;  // InpReplace — a newer setup replaces the one waiting for its break
input int    InpExtraDir    = 0;      // InpExtraDir — extra positions (InpMaxPos > 1): 0 any side · 1 only the SAME side as the open one · 2 only the OPPOSITE side
input double InpDayLossUsd  = 0;      // InpDayLossUsd — no new trades today once the day lost this $ (0 = off)
input double InpDayTargetUsd = 0;     // InpDayTargetUsd — no new trades today once the day made this $ (0 = off) [v4.02: 0->150 at 0.10 lots] [M15: 150->0]

//--- v1.12 variants (all off = v1.11 behaviour)
input int    InpEntryMode   = 0;      // InpEntryMode — 0 market on the break · 1 after the break wait for a dip (retest) · 2 liquidity sweep of the candle's low/high, then enter
input double InpRetestFrac  = 0.5;    // InpRetestFrac — mode 1: dip to this share back into the setup candle (0 = retest of the broken high/low, 0.5 = its middle, 1 = its far end)
input int    InpRetestBars  = 2;      // InpRetestBars — mode 1: candles to wait for the dip after the break
input double InpSweepPips   = 0;      // InpSweepPips — mode 2: price must trade this far beyond the setup candle's low (LONG) / high (SHORT)
input int    InpSweepBars   = 3;      // InpSweepBars — mode 2: candles allowed for the sweep and the entry
input int    InpSweepEntry  = 0;      // InpSweepEntry — mode 2: 0 enter when price reclaims the candle's low/high · 1 enter on the break of the candle's far end after the sweep
input double InpSweepSlPips = 10;     // InpSweepSlPips — mode 2: stop this many pips beyond the sweep's extreme
input int    InpSlMode      = 1;      // InpSlMode — 0 InpSlPips beyond the setup candle · 1 InpSlAtrMult x ATR from the entry · 2 InpSlUsd from the entry
input double InpSlAtrMult   = 1.6;    // InpSlAtrMult — stop mode 1
input double InpSlUsd       = 5.0;    // InpSlUsd — stop mode 2, $ of price
input double InpPartialPct  = 0.5;    // InpPartialPct — close this share of the position at TP1 (0 = off) [v1.16: 0 -> 0.5, Zee's rule]
input bool   InpTp1Be       = true;   // InpTp1Be — at TP1 the rest of the position's stop is never worse than the entry (breakeven) [v1.16, Zee's rule]
input double InpRiskPct     = 0;      // InpRiskPct — size each trade to risk this % of equity (0 = fixed InpLots)
input double InpMinLotRiskPct = 0;    // InpMinLotRiskPct — with InpRiskPct: skip a trade when even the minimum lot would risk more than this % of equity (0 = take it at the minimum lot)
input double InpMaxLots     = 50;     // InpMaxLots — upper limit for InpRiskPct sizing
input int    InpModBackoffSec = 3;   // InpModBackoffSec — after the broker refuses a stop change, wait this many seconds before trying again (60 s when the market is closed)
input double InpDayLossPct  = 0;      // InpDayLossPct — no new trades today after losing this % of the day's starting equity (0 = off)

//--- trading
input double InpLots        = 2;   // InpLots — lot size [v1.17: 0.10 -> 1, Zee]
input bool   InpBuys        = true;   // InpBuys — allow longs
input bool   InpSells       = true;   // InpSells — allow shorts
input int    InpPipPts      = 10;     // InpPipPts — points per pip (gold 10)
input int    InpMagicNumber = 88309;  // InpMagicNumber — Saad_strategy [M15 variant: own magic, can run beside the M5 EA]
input bool   InpVerbose     = false;  // InpVerbose — print every decision
input bool   InpDraw        = true;   // InpDraw — labels on the chart (visual tester + live): setups, entries, stop moves, exits
input bool   InpLog         = true;   // InpLog — print every trade event to the Experts tab (live + visual tester)
input bool   InpLogCsv      = true;   // InpLogCsv — one CSV row per closed trade in Common\Files (live + visual tester)
input color  InpLongColor   = clrGreen; // InpLongColor — chart text/marks for LONG setups and trades (Zee: dark green)
input color  InpShortColor  = clrRed;   // InpShortColor — chart text/marks for SHORT setups and trades
input color  InpSetupTextColor = clrBlack; // InpSetupTextColor — the "SETUP LONG/SHORT: ..." label text (Zee: black); its box and break line keep the side colour
input color  InpTpTextColor = clrBlue;   // InpTpTextColor — the TP1 labels ("TP1: touch of the 50 EMA", "TP ... (last support)", "TP1 ... (next resistance)"; Zee: blue)
input color  InpExitTextColor = clrBlack; // InpExitTextColor — the "EXIT #n ... $" label (Zee: black; was green/red by profit)
input color  InpSlTextColor = clrBlack; // InpSlTextColor — stop-loss TEXT (the "SL price" label and stop-move notes; Zee: black). Lines stay red
input bool   InpDrawSkips   = false;   // InpDrawSkips — also label setups that were skipped (no break, risk, no support, choppy)
// v1.24 (from Saad_strategy_1min v1.39) - all OFF by default
input int    InpAdxPeriod   = 14;     // InpAdxPeriod — ADX length for InpAdxMin
input double InpAdxMin      = 30;      // InpAdxMin — trade only when ADX (last closed candle) is at least this (0 = off; 20-25 = trending)
input double InpAtrMinUsd   = 0;      // InpAtrMinUsd — volatility gate: trade only when ATR(14) of the last closed candle is at least $X (0 = off)
input double InpAtrMaxUsd   = 0;      // InpAtrMaxUsd — ...and at most $X (0 = off)
input int    InpOptScore    = 0;      // InpOptScore — tester only, MT5 optimizer score (OptimizationCriterion 6): 0 net / max drawdown · 2 win rate of whole trades · 3 worst month · 4 win rate always · 5 profit factor
input int    InpOptMinTrades = 100;   // InpOptMinTrades — tester only: fewer whole trades than this scores below every real result (score 5: 0)
// v1.25 (Zee 2026-10-19: "ok test it" - the indicator's TP1 METHOD "Next EMA beyond the entry", which lifted every month on the chart)
// chart-test: the indicator's TOP / BOTTOM FILTER (range boxes)
input int    InpRangeLook   = 7;      // InpRangeLook - BUY: range of the last N closed candles (low = 0%, high = 100%)
input int    InpRangeLookS  = 7;      // InpRangeLookS - SELL: range of the last N closed candles (high = 0%, low = 100%)
input string InpBandsB      = "111110010100001010111"; // InpBandsB - BUY boxes 0-5% ... 95-100%, over 100% (1 = trade, 0 = unticked)
input string InpBandsS      = "111111100010001001110"; // InpBandsS - SELL boxes
input int    InpBandOff     = 1;      // InpBandOff - an entry in an unticked box: 0 skip it (take the next setup) · 1 STAND ASIDE while it would have run (ghost trade)
input int    InpExitMode    = 1;      // InpExitMode — 0 the v1.23 exits (TP1 = EMA / support, partial, trail) · 1 NEXT EMA BEYOND THE ENTRY: close ALL when price touches the nearer EMA beyond the entry (picked at entry from the live EMAs; none beyond -> out after a candle closes back across the fast EMA) · 2 no target: out after a candle CLOSES back across the slow EMA. Modes 1-2: no partial, no breakeven, no trailing - the first stop stays
// TEST tvbars (Zee 2026-10-20) - the TradingView chart's own candles
input int    InpBarSource   = 1;      // InpBarSource - 0 MT5's own candles (= v1.27) · 1 the TradingView chart's candles (Common\Files\InpTvFile, written by monitor/saad_compare/tv_bars_bridge.py)
input string InpTvFile      = "auto"; // InpTvFile - the chart's closed candles in broker server time "YYYY.MM.DD HH:MM,open,high,low,close" · auto = tv_bars_XAUUSD_M15.csv on M15
input int    InpTvWaitSec   = 20;     // InpTvWaitSec - live: wait up to N s after a candle closes for the chart's candle to arrive
input bool   InpTvVerdict   = true;   // InpTvVerdict - when the two feeds disagree by cents the CHART's candle decides, at the next open: it broke the level and MT5 did not -> enter; MT5 broke it and the chart did not -> out; it went through the stop / reached the target EMA and MT5's ticks did not -> out. A stand-aside ghost is judged on the chart's candles
input double InpChartSpread = 0.17;   // InpChartSpread - the chart's fixed spread ($ of price), for its SELL stop / target checks
input datetime InpTvStepFrom = D'2026.10.12 01:01'; // InpTvStepFrom - the chart's first candle WITH 1-minute data inside (server time; the indicator's event table shows it). Before it the chart judges a candle in one step, so a ghost is not ended inside its entry candle
input bool   InpNoEntryExitBar = true; // InpNoEntryExitBar - a setup candle that CLOSED while a trade (or a stand-aside ghost) was still open is ignored, like the chart (busy at that candle's close)
input bool   InpBlindEntryBar = false; // InpBlindEntryBar - DIAGNOSTIC ONLY (never live): before InpTvStepFrom see the entry candle only at its close, like the chart without 1-minute data - no stop at the broker, no exit and no day-close check until the entry candle has closed
input bool   InpLongEmaAbove = true;  // InpLongEmaAbove - exit mode 1: a BUY banks the touch of its target EMA only while that EMA is still ABOVE the entry, like the chart (v1.27 also closed a BUY at the EMA after it had sunk below the entry, at a small loss)

CTrade   trade;
int      hFast = INVALID_HANDLE, hSlow = INVALID_HANDLE, hAtr = INVALID_HANDLE, hHtf = INVALID_HANDLE, hAdx = INVALID_HANDLE;
int      g_skipAdx = 0, g_skipVol = 0;   // v1.24
// chart-test: the ghost trade of "stand aside"
int      g_ck = -1;   // range bucket of this entry (0-20, BUY; +21 SELL) for the trade comment
int      g_gSide = 0, g_gNxE = 0, g_gExitE = 50, g_ghosts = 0, g_bandSkips = 0;
double   g_gEntry = 0, g_gSl = 0, g_gTp = 0;
bool     g_gNoTp = false;
double   g_gBrk = 0; datetime g_gBar = 0;   // TEST tvbars: the ghost's break level (0 = a late entry) and its entry candle
double   g_brk = 0;                         // TEST tvbars: the break level of the entry being made
double   g_enC = 0, g_bidC = 0;             // TEST tvbars: the CHART's entry price (ask / bid) of the entry being made
bool     g_busyAtClose = false;             // TEST tvbars: a trade / ghost was still open when the last candle closed
datetime g_gTime = 0;
ENUM_TIMEFRAMES g_htf = PERIOD_CURRENT;
datetime g_lastBar = 0;

// the setup waiting for its break
int      g_pSide = 0;
double   g_pHigh = 0, g_pLow = 0;
int      g_pLeft = 0;
int      g_pExit = 50;           // long: which EMA is its exit
// v1.12: entry armed after the break (mode 1) / sweep tracking (mode 2)
int      g_aSide = 0;            // mode 1: waiting for the dip
double   g_aLevel = 0, g_aHigh = 0, g_aLow = 0;
int      g_aLeft = 0, g_aExit = 50;
bool     g_swept = false;        // mode 2: the setup candle's low/high has been swept
double   g_sweepExt = 0;
double   g_dayStartEq = 0; int g_dayKey = -1;
datetime g_modBlockUntil = 0; int g_modFails = 0;
int      g_skipDip = 0, g_skipSweep = 0, g_skipMinLot = 0, g_dayLossStop = 0, g_partials = 0;

// per-position state
struct PosState { ulong ticket; int side; double entry; double tp; int exitE; bool noTp; bool ride; datetime entryTime; double best; bool usdTrail; double tpNext; int tpStage; bool resTp1;
                  string setup; double sl0; double risk; string tp1; datetime tp1At; string tps; datetime ctcAt; int moves; double mfe;
                  int num; double slNow; datetime slFrom; string why; int nxE; double brk; datetime bar; double enC; double pendSl; bool pendClose; };   // v1.25 nxE: 9 / 50 the EMA to touch, -1 none beyond (close back across the fast), -2 close back across the slow, 0 v1.23 exits
PosState g_pos[];

int g_ctc = 0, g_skipClose = 0, g_closeLoss = 0;
int g_setups = 0, g_entries = 0, g_skipBreak = 0, g_skipGap = 0, g_skipRisk = 0, g_skipSup = 0, g_chop = 0,
    g_busy = 0, g_rides = 0, g_lockFail = 0, g_dayStop = 0, g_filtered = 0;

double Pip() { return InpPipPts * _Point; }
double Buf(int h, int s) { double v[1]; return CopyBuffer(h, 0, s, 1, v) == 1 ? v[0] : 0.0; }
// ---- TEST tvbars: the TradingView chart's own candles (bridge code from Saad_strategy_1min v1.39) ----
datetime tvT[]; double tvO[], tvH[], tvL[], tvC[], tvEF[], tvES[], tvA[], tvX[];
bool     g_useTv = false;          // this candle has chart candles behind it (else MT5's own candles)
bool     g_tvStale = false;        // no new chart candle: the chart takes no step either
int      g_tvN = 0, g_tvEnd = -1;  // g_tvEnd = index of the last CLOSED chart candle (shift 1)
uint     g_tvReadMs = 0;
double   g_open0 = 0;              // the bid at the chart candle's first tick = its open
int      g_late = 0;               // 1 while entering at this open on the chart's break of the PREVIOUS candle (InpTvVerdict)
double   g_lateBid = 0;            // ...the price the chart entered at (bid)
int      g_vLate = 0, g_vNoBrk = 0, g_vStop = 0, g_vTp = 0, g_gChart = 0;
string TvFile() { if (InpTvFile != "auto") return InpTvFile; int m = PeriodSeconds() / 60; return m == 1 ? "tv_bars_XAUUSD.csv" : StringFormat("tv_bars_XAUUSD_M%d.csv", m); }
bool TvLoad()
{
   g_tvReadMs = GetTickCount();
   int fh = FileOpen(TvFile(), FILE_READ | FILE_CSV | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE, ',');
   if (fh == INVALID_HANDLE) return false;
   int n = 0, cap = MathMax(ArraySize(tvT), 1024);
   ArrayResize(tvT, cap); ArrayResize(tvO, cap); ArrayResize(tvH, cap); ArrayResize(tvL, cap); ArrayResize(tvC, cap);
   while (!FileIsEnding(fh)) {
      string ts = FileReadString(fh);
      if (FileIsLineEnding(fh) || FileIsEnding(fh)) continue;
      double o = FileReadNumber(fh), h = FileReadNumber(fh), l = FileReadNumber(fh), c = FileReadNumber(fh);
      while (!FileIsLineEnding(fh) && !FileIsEnding(fh)) FileReadString(fh);
      datetime bt = StringToTime(ts);
      if (bt <= 0 || o <= 0 || h <= 0 || l <= 0 || c <= 0 || (n > 0 && bt <= tvT[n - 1])) continue;   // a half-written or repeated line
      if (n >= cap) { cap *= 2; ArrayResize(tvT, cap); ArrayResize(tvO, cap); ArrayResize(tvH, cap); ArrayResize(tvL, cap); ArrayResize(tvC, cap); }
      tvT[n] = bt; tvO[n] = o; tvH[n] = h; tvL[n] = l; tvC[n] = c; n++;
   }
   FileClose(fh);
   g_tvN = n;
   int m = MathMax(n, 1);
   ArrayResize(tvEF, m); ArrayResize(tvES, m); ArrayResize(tvA, m); ArrayResize(tvX, m);
   double af = 2.0 / (InpEmaFast + 1), as = 2.0 / (InpEmaSlow + 1), ak = 2.0 / (InpAdxPeriod + 1), trs = 0, pdi = 0, ndi = 0, adx = 0;
   double tr[]; ArrayResize(tr, m);
   for (int i = 0; i < n; i++) {
      tvEF[i] = i == 0 ? tvC[0] : tvEF[i - 1] + af * (tvC[i] - tvEF[i - 1]);              // ta.ema: seeded with the first close
      tvES[i] = i == 0 ? tvC[0] : tvES[i - 1] + as * (tvC[i] - tvES[i - 1]);
      tr[i] = i == 0 ? tvH[0] - tvL[0] : MathMax(tvH[i], tvC[i - 1]) - MathMin(tvL[i], tvC[i - 1]);   // ta.tr(true)
      trs += tr[i]; if (i >= 14) trs -= tr[i - 14];
      tvA[i] = trs / MathMin(i + 1, 14);                                                     // ta.sma(tr, 14) = MT5 iATR
      // the indicator's mtAdx() = MT5's iADX on the chart's candles: +DM / -DM as a share of the true range, EMA-smoothed, DX EMA-smoothed
      double pdm = 0, ndm = 0;
      if (i > 0) {
         pdm = MathMax(tvH[i] - tvH[i - 1], 0); ndm = MathMax(tvL[i - 1] - tvL[i], 0);
         if (pdm > ndm) ndm = 0; else if (ndm > pdm) pdm = 0; else { pdm = 0; ndm = 0; }
      }
      double pd = tr[i] != 0 ? 100 * pdm / tr[i] : 0, nd = tr[i] != 0 ? 100 * ndm / tr[i] : 0;
      pdi = i == 0 ? pd : pdi + ak * (pd - pdi);
      ndi = i == 0 ? nd : ndi + ak * (nd - ndi);
      double s = pdi + ndi, dx = s != 0 ? 100 * MathAbs(pdi - ndi) / s : 0;
      adx = i == 0 ? dx : adx + ak * (dx - adx);
      tvX[i] = adx;
   }
   return n > 0;
}
// TradingView starts a week's first 15-min candles at the session open (Monday 01:01, 01:16 ...) while MT5's run 01:00, 01:15 ...:
// the EA's "current candle" opens when the CHART's candle closes. No chart candle for too long (bridge stopped) -> MT5's clock.
datetime CurBar()
{
   datetime mt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (InpBarSource != 1 || g_tvN == 0 || PeriodSeconds() <= 60) return mt;
   int P = PeriodSeconds(), warm = MathMin(InpEmaSlow * 2 + 19, g_tvN - 1);
   datetime now = TimeCurrent();
   if (!MQLInfoInteger(MQL_TESTER) && now >= tvT[g_tvN - 1] + 2 * P && GetTickCount() - g_tvReadMs >= 1000) TvLoad();   // live: the next candle is due
   int lo = 0, hi = g_tvN - 1, r = -1;
   while (lo <= hi) { int k = (lo + hi) / 2; if (tvT[k] + P <= now) { r = k; lo = k + 1; } else hi = k - 1; }
   if (r < warm) return mt;
   datetime tb = tvT[r] + P;
   if (MQLInfoInteger(MQL_TESTER) ? now > tvT[g_tvN - 1] + 2 * P : now - tb > P + InpTvWaitSec && mt > tb) return mt;
   return tb;
}
// the last chart candle that closed before the candle opening at `bar`
void TvSync(datetime bar)
{
   int lo = 0, hi = g_tvN - 1, r = -1;
   while (lo <= hi) { int k = (lo + hi) / 2; if (tvT[k] <= bar - PeriodSeconds()) { r = k; lo = k + 1; } else hi = k - 1; }
   g_tvEnd = r;
}
// live: the chart's candle that just closed has arrived (or we waited long enough)
bool TvReady(datetime bar)
{
   if (InpBarSource != 1) { g_useTv = false; return true; }
   if (g_tvN == 0 || tvT[g_tvN - 1] < bar - PeriodSeconds()) {
      if (!MQLInfoInteger(MQL_TESTER) && GetTickCount() - g_tvReadMs >= 1000) TvLoad();
   }
   static int lastEnd = -2;
   TvSync(bar);
   // before the chart's first candles (+ warm-up), or after the file ends in the tester, the EA uses MT5's own candles
   int warm = MathMin(InpEmaSlow * 2 + 19, g_tvN - 1);
   g_useTv = g_tvN > 0 && warm >= 0 && bar - PeriodSeconds() >= tvT[warm] && (!MQLInfoInteger(MQL_TESTER) || bar - PeriodSeconds() <= tvT[g_tvN - 1]);
   if (!g_useTv) { g_tvStale = false; lastEnd = g_tvEnd; return true; }
   g_tvStale = g_tvEnd < 0 || g_tvEnd == lastEnd;
   if (g_tvEnd >= 0 && tvT[g_tvEnd] >= bar - PeriodSeconds()) { lastEnd = g_tvEnd; return true; }
   if (MQLInfoInteger(MQL_TESTER)) { lastEnd = g_tvEnd; return true; }   // the file is complete; a missing chart candle stays missing
   if (TimeCurrent() - bar < InpTvWaitSec) return false;
   lastEnd = g_tvEnd;
   if (!g_tvStale) return true;
   static datetime warned = 0;
   if (warned != bar) { warned = bar; PrintFormat("[SAAD-15min-tv] WARNING: no TradingView candle for %s after %d s - is tv_bars_bridge.py running? Setups paused until it is back (last %s)",
                                                  TimeToString(bar - PeriodSeconds()), InpTvWaitSec, g_tvEnd >= 0 ? TimeToString(tvT[g_tvEnd]) : "none"); }
   return true;
}
int    TvI(int s) { int i = g_tvEnd - s + 1; return i >= 0 && i <= g_tvEnd ? i : -1; }
double BOpen(int s)  { if (s <= 0) return g_useTv && g_open0 > 0 ? g_open0 : iOpen(_Symbol, PERIOD_CURRENT, 0); if (!g_useTv) return iOpen(_Symbol, PERIOD_CURRENT, s); int i = TvI(s); return i < 0 ? 0 : tvO[i]; }
double BHigh(int s)  { if (!g_useTv || s <= 0) return iHigh(_Symbol, PERIOD_CURRENT, s);  int i = TvI(s); return i < 0 ? 0 : tvH[i]; }
double BLow(int s)   { if (!g_useTv || s <= 0) return iLow(_Symbol, PERIOD_CURRENT, s);   int i = TvI(s); return i < 0 ? 0 : tvL[i]; }
double BClose(int s) { if (!g_useTv || s <= 0) return iClose(_Symbol, PERIOD_CURRENT, s); int i = TvI(s); return i < 0 ? 0 : tvC[i]; }
datetime BTime(int s){ if (s == 0) return CurBar(); if (!g_useTv || s < 0) return iTime(_Symbol, PERIOD_CURRENT, s);  int i = TvI(s); return i < 0 ? 0 : tvT[i]; }
double Atr(int s)    { if (!g_useTv) return Buf(hAtr, s); int i = TvI(MathMax(s, 1)); return i < 0 ? 0 : tvA[i]; }
double Adx(int s)    { if (!g_useTv) return hAdx == INVALID_HANDLE ? 0 : Buf(hAdx, s); int i = TvI(MathMax(s, 1)); return i < 0 ? 0 : tvX[i]; }
double EmaX(int fast, int s)
{
   if (!g_useTv) return Buf(fast ? hFast : hSlow, s);
   int i = TvI(s > 0 ? s : 1 + g_late); if (i < 0) return 0;
   double e = fast ? tvEF[i] : tvES[i];
   if (s > 0) return e;
   double a = 2.0 / ((fast ? InpEmaFast : InpEmaSlow) + 1);              // the forming candle: the chart's emaLive, at the bid
   return e + a * ((g_late > 0 ? g_lateBid : SymbolInfoDouble(_Symbol, SYMBOL_BID)) - e);
}
double Ema(int which, int s) { return EmaX(which == 9 ? 1 : 0, s); }
// the chart's live EMA of the forming candle at price px (its emaLive(n, bid))
double EmaAt(int which, double px)
{
   if (!g_useTv) return Ema(which, 0);
   int i = TvI(1 + g_late); if (i < 0) return 0;
   bool fast = which == 9;
   double e = fast ? tvEF[i] : tvES[i], a = 2.0 / ((fast ? InpEmaFast : InpEmaSlow) + 1);
   return e + a * (px - e);
}
bool BlindNow() { return InpBlindEntryBar && g_useTv && CurBar() < InpTvStepFrom; }   // diagnostic: the chart has no 1-minute data here
double ChartSpr() { return InpChartSpread > 0 ? InpChartSpread : SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID); }
// the chart's candle that just closed reached a "next EMA" target (the indicator's thresholds: LONG bid >= the live EMA, SELL ask <= it)
bool ChartTouched(int sd, int nxE, double en)
{
   double a = 2.0 / ((nxE == 9 ? InpEmaFast : InpEmaSlow) + 1), ep = Ema(nxE, 2);
   if (ep <= 0) return false;
   if (sd > 0) return BHigh(1) >= (InpLongEmaAbove ? MathMax(ep, ep + (en - ep) / a + 0.001) : ep);
   return BLow(1) <= ep - ChartSpr() / (1 - a);
}
bool   TrailOn(int side) { return InpTrail && (InpTrailSide == 2 || (side > 0 && InpTrailSide == 0) || (side < 0 && InpTrailSide == 1)); }

int g_hEmas = INVALID_HANDLE;
void EmasShow()   // v1.22: same candles and periods the EA trades on, so the lines are exactly its lines
{
   if (!InpShowEmas || (MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE))) return;
   if (ChartIndicatorGet(0, 0, "SaadEMAs") != INVALID_HANDLE) return;   // already on the chart
   g_hEmas = iCustom(_Symbol, PERIOD_CURRENT, "::Indicators\\SaadEMAs.ex5", PERIOD_CURRENT, InpEmaFast, InpEmaSlow);
   if (g_hEmas == INVALID_HANDLE || !ChartIndicatorAdd(0, 0, g_hEmas)) PrintFormat("[SAAD] could not draw the EMAs (error %d)", GetLastError());
}

int OnInit()
{
   EmasShow();
   hFast = iMA(_Symbol, PERIOD_CURRENT, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
   hSlow = iMA(_Symbol, PERIOD_CURRENT, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   hAtr  = iATR(_Symbol, PERIOD_CURRENT, 14);
   if (InpAdxMin > 0) { hAdx = iADX(_Symbol, PERIOD_CURRENT, InpAdxPeriod); if (hAdx == INVALID_HANDLE) return INIT_FAILED; }   // v1.24
   if (InpHtfMin > 0) {
      g_htf = InpHtfMin == 15 ? PERIOD_M15 : InpHtfMin == 30 ? PERIOD_M30 : InpHtfMin == 60 ? PERIOD_H1 : InpHtfMin == 240 ? PERIOD_H4 : PERIOD_M15;
      hHtf = iMA(_Symbol, g_htf, InpHtfEma, 0, MODE_EMA, PRICE_CLOSE);
      if (hHtf == INVALID_HANDLE) return INIT_FAILED;
   }
   if (hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE || hAtr == INVALID_HANDLE) return INIT_FAILED;
   if (InpBarSource == 1) {
      if (!TvLoad()) PrintFormat("[SAAD-15min-tv] WARNING: no chart candles in Common\\Files\\%s - trading on MT5's own candles until they appear", TvFile());
      else PrintFormat("[SAAD-15min-tv] chart candles: %d, %s -> %s (server time)", g_tvN, TimeToString(tvT[0]), TimeToString(tvT[g_tvN - 1]));
   }
   trade.SetExpertMagicNumber(InpMagicNumber);
   if (MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)) trade.LogLevel(LOG_LEVEL_ERRORS);   // v1.12: agent logs were 381-866 MB
   PrintFormat("[SAAD-15min] tvbars (v1.27 on the chart's candles) %s | stops level %d pts, freeze %d pts, spread now %d pts | SL %.0f pips, max risk $%.2f, ER %.2f/%d, hours %d-%d, trail %s N%d ride %s, maxPos %d",
               _Symbol, (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL),
               (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD), InpSlPips, InpMaxRiskUsd, InpChopEr, InpChopErLook, InpSessFrom, InpSessTo,
               InpTrail ? "on" : "off", InpTrailN, InpRide ? "on" : "off", InpMaxPos);
   datetime e = SessionEnd(TimeCurrent());
   PrintFormat("[SAAD] day close for %s: %s (no new trades %d min before; losers shut %d min before)", _Symbol,
               e == 0 ? "none found (no daily break)" : TimeToString(e), InpNoNewMins, InpCloseLossMins);
   return INIT_SUCCEEDED;
}

// v1.24: the optimizer's score (OptimizationCriterion 6 = "Custom max"), as in Saad_strategy_1min. Tester only - never runs live.
int g_posN = 0, g_posW = 0;
void PositionStats()                      // whole trades: a position's TP1 partial + its rest = one trade
{
   g_posN = 0; g_posW = 0;
   if (!HistorySelect(0, TimeCurrent() + 86400)) return;
   ulong ids[]; double pn[];
   int nd = HistoryDealsTotal();
   for (int d = 0; d < nd; d++) {
      ulong tk = HistoryDealGetTicket(d);
      if (HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagicNumber) continue;
      ulong pid = (ulong)HistoryDealGetInteger(tk, DEAL_POSITION_ID);
      double v = HistoryDealGetDouble(tk, DEAL_PROFIT) + HistoryDealGetDouble(tk, DEAL_COMMISSION) + HistoryDealGetDouble(tk, DEAL_SWAP);
      int k = -1;
      for (int j = ArraySize(ids) - 1; j >= 0; j--) if (ids[j] == pid) { k = j; break; }
      if (k < 0) { k = ArraySize(ids); ArrayResize(ids, k + 1); ArrayResize(pn, k + 1); ids[k] = pid; pn[k] = 0; }
      pn[k] += v;
   }
   g_posN = ArraySize(ids);
   for (int j = 0; j < g_posN; j++) if (pn[j] > 0) g_posW++;
}

double WorstMonth()                       // the worst calendar month's net (a month without trades = 0)
{
   if (!HistorySelect(0, TimeCurrent() + 86400)) return 0;
   double m[]; int k0 = -1;
   int nd = HistoryDealsTotal();
   for (int d = 0; d < nd; d++) {
      ulong tk = HistoryDealGetTicket(d);
      if (HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagicNumber) continue;
      MqlDateTime t; TimeToStruct((datetime)HistoryDealGetInteger(tk, DEAL_TIME), t);
      int k = t.year * 12 + t.mon;
      if (k0 < 0) k0 = k;
      int i = k - k0;
      if (i < 0) continue;
      if (i >= ArraySize(m)) { int o = ArraySize(m); ArrayResize(m, i + 1); for (int j = o; j <= i; j++) m[j] = 0; }
      m[i] += HistoryDealGetDouble(tk, DEAL_PROFIT) + HistoryDealGetDouble(tk, DEAL_COMMISSION) + HistoryDealGetDouble(tk, DEAL_SWAP);
   }
   if (ArraySize(m) == 0) return -1e9;
   double w = m[0];
   for (int i = 1; i < ArraySize(m); i++) w = MathMin(w, m[i]);
   return w;
}

double OnTester()
{
   double net = TesterStatistics(STAT_PROFIT), dd = TesterStatistics(STAT_EQUITY_DD), n = TesterStatistics(STAT_TRADES);
   if (InpOptScore == 4) { PositionStats(); return g_posN > 0 ? 100.0 * g_posW / g_posN : 0; }
   if (InpOptScore == 5) { PositionStats(); return g_posN < InpOptMinTrades ? 0 : TesterStatistics(STAT_PROFIT_FACTOR); }
   if (InpOptScore == 3) {
      if (n < InpOptMinTrades) return -1e9 + n;
      return WorstMonth() + 0.05 * net;
   }
   if (InpOptScore == 2) {
      PositionStats();
      if (g_posN < InpOptMinTrades) return -1e9 + g_posN;
      if (net <= 0) return net / 1000.0 - 100.0;
      return 100.0 * g_posW / g_posN;
   }
   if (n < InpOptMinTrades) return -1e9 + n;
   if (net <= 0) return net / 1000.0;
   return net / MathMax(dd, 1.0);
}

void OnDeinit(const int reason)
{
   if (reason != REASON_CHARTCHANGE && reason != REASON_PARAMETERS) ChartIndicatorDelete(0, 0, "SaadEMAs");
   if (InpAdxMin > 0 || InpAtrMinUsd > 0 || InpAtrMaxUsd > 0) PrintFormat("[SAAD] v1.24 gates: ADX %d, volatility %d", g_skipAdx, g_skipVol);
   PrintFormat("[SAAD] chart-test: stand-aside ghosts %d, unticked-box skips %d", g_ghosts, g_bandSkips);
   PrintFormat("[SAAD] tvbars: the chart's candle decided - late entries %d, no break on the chart %d, stops %d, targets %d, ghosts ended %d", g_vLate, g_vNoBrk, g_vStop, g_vTp, g_gChart);
   PrintFormat("[SAAD] v1.12: refused stop changes %d | no dip %d, no sweep %d, min-lot too risky %d, day loss stops %d, partial closes %d", g_modFails, g_skipDip, g_skipSweep, g_skipMinLot, g_dayLossStop, g_partials);
   PrintFormat("[SAAD] CTC breakevens %d | day close: setups dropped %d, losing trades shut %d", g_ctc, g_skipClose, g_closeLoss);
   PrintFormat("[SAAD] setups %d, entries %d | skipped: no break %d, gap %d, risk %d, no support %d, choppy %d, filters %d, busy %d, day guard %d | rides %d, lock refused %d",
               g_setups, g_entries, g_skipBreak, g_skipGap, g_skipRisk, g_skipSup, g_chop, g_filtered, g_busy, g_dayStop, g_rides, g_lockFail);
}

//--- ① shape of closed bar s: +1 bullish, -1 bearish, 2 pin whose side the EMA decides, 0 none
int g_kind = 0;   // 1 pin, 2 hammer/star, 3 marubozu
int Shape(int s)
{
   g_kind = 0;
   double o = BOpen(s), c = BClose(s);
   double h = BHigh(s), l = BLow(s);
   double rng = h - l;
   if (rng <= 0) return 0;
   if (InpMinRangeAtr > 0 && rng < InpMinRangeAtr * Atr(s)) return 0;
   double body = MathAbs(c - o), up = h - MathMax(o, c), lo = MathMin(o, c) - l;
   bool pinBull = body <= InpBodyMax * rng && lo >= InpWickMin * rng && up <= InpNoseMax * rng;
   bool pinBear = body <= InpBodyMax * rng && up >= InpWickMin * rng && lo <= InpNoseMax * rng;
   bool isPin = pinBull || pinBear;
   bool hamBull = !isPin && lo >= InpHamRatio * body && lo > 0 && up <= InpHamNose * rng;
   bool hamBear = !isPin && up >= InpHamRatio * body && up > 0 && lo <= InpHamNose * rng;
   bool maru = !isPin && !hamBull && !hamBear && body >= InpMaruBody * rng;
   if (isPin) {
      if (!InpUsePin) return 0;
      g_kind = 1;
      if (!InpPinDir) return 2;
      if (InpPinColor && (pinBull ? c < o : c > o)) return 0;   // body against the trade's direction
      return pinBull ? +1 : -1;
   }
   if (hamBull) { if (!InpHammer) return 0; g_kind = 2; return +1; }
   if (hamBear) { if (!InpStar)   return 0; g_kind = 2; return -1; }
   if (maru)    { if (!InpMarubozu) return 0; g_kind = 3; return c > o ? +1 : -1; }
   return 0;
}

bool OnLine(int s, double e, int side)
{
   double o = BOpen(s), c = BClose(s);
   double h = BHigh(s), l = BLow(s);
   double tol = InpTouchPips * Pip();
   if (e <= 0) return false;
   if (InpTouchMode == 0) return l - tol <= e && h + tol >= e;
   return side > 0 ? (l - tol <= e && MathMin(o, c) >= e) : (h + tol >= e && MathMax(o, c) <= e);
}

// the most recent confirmed swing low below `below`
double LastSupport(double below)
{
   int p = InpSwingPivot;
   for (int i = 1 + p; i < 1 + p + InpSwingLook; i++) {
      double l = BLow(i);
      if (l <= 0) break;
      if (l >= below) continue;
      bool piv = true;
      for (int k = 1; k <= p && piv; k++)
         if (BLow(i - k) <= l || BLow(i + k) < l) piv = false;
      if (piv) return l;
   }
   return 0.0;
}

// the most recent confirmed swing high above `above` (the "next liquidity" for a LONG)
double LastResistance(double above)
{
   int p = InpSwingPivot;
   for (int i = 1 + p; i < 1 + p + InpSwingLook; i++) {
      double h = BHigh(i);
      if (h <= 0) break;
      if (h <= above) continue;
      bool piv = true;
      for (int k = 1; k <= p && piv; k++)
         if (BHigh(i - k) >= h || BHigh(i + k) > h) piv = false;
      if (piv) return h;
   }
   return 0.0;
}

bool Choppy()
{
   if (InpChopEr <= 0) return false;
   double net = MathAbs(BClose(1) - BClose(InpChopErLook + 1));
   double path = 0;
   for (int i = 1; i <= InpChopErLook; i++)
      path += MathAbs(BClose(i) - BClose(i + 1));
   return path <= 0 || net / path < InpChopEr;
}


//--- the day's close, from the broker's trading sessions for this symbol (covers the Friday close too)
datetime SessionEnd(datetime now)
{
   MqlDateTime d; TimeToStruct(now, d);
   long sec = d.hour * 3600 + d.min * 60 + d.sec;
   datetime day0 = now - (datetime)sec;
   datetime from, to;
   for (uint k = 0; k < 10; k++) {
      if (!SymbolInfoSessionTrade(_Symbol, (ENUM_DAY_OF_WEEK)d.day_of_week, k, from, to)) break;
      long f = (long)from % 86400, t = (long)to; if (t > 86400) t = t % 86400; if (t == 0) t = 86400;
      if (sec >= f && sec < t) {
         // a session running to 24:00 that the next day continues at 00:00 is not a close
         if (t == 86400) {
            datetime f2, t2; MqlDateTime n; TimeToStruct(day0 + 86400, n);
            if (SymbolInfoSessionTrade(_Symbol, (ENUM_DAY_OF_WEEK)n.day_of_week, 0, f2, t2) && (long)f2 % 86400 == 0) return 0;
         }
         return day0 + (datetime)t;
      }
   }
   return 0;
}
int MinsToClose() { datetime e = SessionEnd(TimeCurrent()); return e == 0 ? 100000 : (int)((e - TimeCurrent()) / 60); }

//--- chart labels (like the TradingView indicator). Plain text: MT5 shows no emoji.
int      g_obj = 0, g_num = 0;
string   g_pDesc = "";            // the waiting setup, for its labels
datetime g_pTime = 0;
bool Drawing() { return InpDraw && (!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_VISUAL_MODE)); }
string ObjName() { return StringFormat("SAAD_%d", g_obj++); }
bool LogOn() { return InpLog && (!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_VISUAL_MODE) || InpVerbose); }
void Log(string msg) { if (LogOn()) Print("[SAAD-15min] ", msg); }
string Ts(datetime t) { return t == 0 ? "" : TimeToString(t, TIME_DATE | TIME_SECONDS); }
string Px(double v) { return v == 0 ? "" : DoubleToString(v, _Digits); }
// one row per closed trade: Common\Files\Saad15_trades_<symbol>_<magic>[_tester].csv
void CsvRow(string row)
{
   if (!InpLogCsv || (MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE))) return;
   string fn = StringFormat("Saad15_trades_%s_%d%s.csv", _Symbol, InpMagicNumber, MQLInfoInteger(MQL_TESTER) ? "_tester" : "");
   int h = FileOpen(fn, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ);
   if (h == INVALID_HANDLE) { Print("[SAAD-15min] cannot write ", fn, " error ", GetLastError()); return; }
   if (FileSize(h) == 0)
      FileWriteString(h, "num,symbol,side,setup,entry_time,entry,sl_initial,risk_usd,tp1_rule,tp1_time,tp_levels,ctc_time,"
                         "sl_moves,best_price,sl_final,exit_time,exit,exit_reason,profit,commission,swap,net\r\n");
   FileSeek(h, 0, SEEK_END);
   FileWriteString(h, row + "\r\n");
   FileClose(h);
}
void DText(datetime t, double price, string txt, color c, int size = 8, ENUM_ANCHOR_POINT anc = ANCHOR_LEFT_LOWER, string tip = "")
{
   if (!Drawing()) return;
   string n = ObjName();
   ObjectCreate(0, n, OBJ_TEXT, 0, t, price);
   ObjectSetString(0, n, OBJPROP_TEXT, txt);
   ObjectSetString(0, n, OBJPROP_FONT, "Arial");
   ObjectSetInteger(0, n, OBJPROP_FONTSIZE, size);
   ObjectSetInteger(0, n, OBJPROP_COLOR, c);
   ObjectSetInteger(0, n, OBJPROP_ANCHOR, anc);
   ObjectSetString(0, n, OBJPROP_TOOLTIP, tip == "" ? txt : tip);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
}
void DLine(datetime t1, double p1, datetime t2, double p2, color c, ENUM_LINE_STYLE st = STYLE_SOLID, int w = 1, string tip = "")
{
   if (!Drawing()) return;
   string n = ObjName();
   ObjectCreate(0, n, OBJ_TREND, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, n, OBJPROP_COLOR, c);
   ObjectSetInteger(0, n, OBJPROP_STYLE, st);
   ObjectSetInteger(0, n, OBJPROP_WIDTH, w);
   ObjectSetInteger(0, n, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
   if (tip != "") ObjectSetString(0, n, OBJPROP_TOOLTIP, tip);
}
void DBox(datetime t1, double p1, datetime t2, double p2, color c)
{
   if (!Drawing()) return;
   string n = ObjName();
   ObjectCreate(0, n, OBJ_RECTANGLE, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, n, OBJPROP_COLOR, c);
   ObjectSetInteger(0, n, OBJPROP_FILL, false);
   ObjectSetInteger(0, n, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, n, OBJPROP_BACK, true);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
}
void DArrow(datetime t, double price, int side)
{
   if (!Drawing()) return;
   string n = ObjName();
   ObjectCreate(0, n, side > 0 ? OBJ_ARROW_BUY : OBJ_ARROW_SELL, 0, t, price);
   ObjectSetInteger(0, n, OBJPROP_COLOR, side > 0 ? InpLongColor : InpShortColor);
   ObjectSetInteger(0, n, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
}
// a label placed `lvl` x ATR away from the candle (above when up=true) with an arrow pointing back to (t, price)
void Callout(datetime t, double price, bool up, double lvl, string txt, color c, int size = 9, string tip = "")
{
   if (!Drawing()) return;
   double a = Atr(1); if (a <= 0) a = 10 * Pip();
   double ty = up ? price + lvl * a : price - lvl * a;
   string n = ObjName();
   ObjectCreate(0, n, OBJ_ARROWED_LINE, 0, t, ty, t, price);
   ObjectSetInteger(0, n, OBJPROP_COLOR, c);
   ObjectSetInteger(0, n, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, n, OBJPROP_BACK, true);
   DText(t, ty, txt, c, size, up ? ANCHOR_LOWER : ANCHOR_UPPER, tip);
}
// a skipped setup: grey note under (long) / over (short) its candle
void DSkip(int side, string why)
{
   Log("SKIP: " + why + " | " + g_pDesc);
   if (!InpDrawSkips || g_pTime == 0) return;
   double off = 2 * Pip();
   Callout(g_pTime, side > 0 ? g_pLow - off : g_pHigh + off, side < 0, 1.0, "skip: " + why, clrGray, 7, "skipped: " + why + " | " + g_pDesc);
}
// the stop moved: end the old segment, start a new one
void SlMoved(int i, double newSl, string note)
{
   g_pos[i].moves++;
   if (note != "" && StringFind(note, "trail") != 0) Log(StringFormat("#%d SL %s -> %s (%s)", g_pos[i].num, Px(g_pos[i].slNow), Px(newSl), note));
   if (!Drawing()) { g_pos[i].slNow = newSl; return; }
   datetime now = TimeCurrent();
   DLine(g_pos[i].slFrom, g_pos[i].slNow, now, g_pos[i].slNow, g_pos[i].ride ? clrOrange : clrRed, STYLE_DASH, 2);
   g_pos[i].slNow = newSl; g_pos[i].slFrom = now;
   if (note != "") DText(now, newSl, note, InpSlTextColor, 7, g_pos[i].side > 0 ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER);
}
// the position is gone: label its exit from the closing deal
void DrawExit(PosState &p)
{
   if (!(Drawing() || LogOn() || InpLogCsv) || !HistorySelectByPosition(p.ticket)) return;
   double px = 0, pnl = 0, prof = 0, comm = 0, swp = 0; datetime t = 0; long reason = -1;
   for (int k = HistoryDealsTotal() - 1; k >= 0; k--) {
      ulong d = HistoryDealGetTicket(k);
      comm += HistoryDealGetDouble(d, DEAL_COMMISSION);          // entry + exit commission
      if (HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      px = HistoryDealGetDouble(d, DEAL_PRICE); t = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
      prof += HistoryDealGetDouble(d, DEAL_PROFIT); swp += HistoryDealGetDouble(d, DEAL_SWAP);
      reason = HistoryDealGetInteger(d, DEAL_REASON);
   }
   if (t == 0) return;
   pnl = prof + comm + swp;
   string why = p.why;
   if (reason == DEAL_REASON_SL)
      why = p.usdTrail ? StringFormat("trailing stop ($%.0f) after TP%d", p.side > 0 ? InpLongTrailUsd : InpShortTrailUsd, p.tpStage - 1) : MathAbs(p.slNow - p.entry) < _Point ? "breakeven (CTC)"
          : (p.ride || (p.side > 0 ? p.slNow > p.entry : p.slNow < p.entry)) ? "trailing stop" : "stop loss";
   else if (reason == DEAL_REASON_TP) why = p.side > 0 ? "TP (last resistance)" : "TP (last support)";
   else if (why == "") why = "closed";
   Log(StringFormat("EXIT #%d %s %s @ %s | entry %s | %s | best %s | SL moves %d | net %s%.2f (profit %.2f, commission %.2f, swap %.2f)",
                    p.num, p.side > 0 ? "BUY" : "SELL", Ts(t), Px(px), Px(p.entry), why, Px(p.mfe), p.moves,
                    pnl >= 0 ? "+" : "-", MathAbs(pnl), prof, comm, swp));
   string setupCsv = p.setup; StringReplace(setupCsv, ",", ";");
   string tp1Csv = p.tp1; StringReplace(tp1Csv, ",", ";");
   CsvRow(StringFormat("%d,%s,%s,%s,%s,%s,%s,%.2f,%s,%s,%s,%s,%d,%s,%s,%s,%s,%s,%.2f,%.2f,%.2f,%.2f",
                       p.num, _Symbol, p.side > 0 ? "BUY" : "SELL", setupCsv, Ts(p.entryTime), Px(p.entry), Px(p.sl0), p.risk,
                       tp1Csv, Ts(p.tp1At), p.tps, Ts(p.ctcAt), p.moves, Px(p.mfe), Px(p.slNow), Ts(t), Px(px), why,
                       prof, comm, swp, pnl));
   DLine(p.slFrom, p.slNow, t, p.slNow, p.ride ? clrOrange : clrRed, STYLE_DASH, 2);
   DLine(p.entryTime, p.entry, t, px, pnl >= 0 ? clrLime : clrRed, STYLE_DOT, 1);
   color c = InpExitTextColor;
   string txt = StringFormat("EXIT #%d %s %s$%.2f", p.num, why, pnl >= 0 ? "+" : "-", MathAbs(pnl));
   Callout(t, px, p.side > 0, 4.0, txt, c, 10,
         StringFormat("#%d %s  entry %.2f -> exit %.2f  (%s)  %s$%.2f", p.num, p.side > 0 ? "BUY" : "SELL", p.entry, px, why,
                      pnl >= 0 ? "+" : "-", MathAbs(pnl)));
}

//--- positions
int FindPos(ulong t) { for (int i = 0; i < ArraySize(g_pos); i++) if (g_pos[i].ticket == t) return i; return -1; }

void SyncPos()
{
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--)
      if (!PositionSelectByTicket(g_pos[i].ticket)) {
         DrawExit(g_pos[i]);
         for (int j = i; j < ArraySize(g_pos) - 1; j++) g_pos[j] = g_pos[j + 1];
         ArrayResize(g_pos, ArraySize(g_pos) - 1);
      }
   // positions opened before a restart: adopt with default state
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if (FindPos(t) >= 0) continue;
      PosState p;
      p.ticket = t; p.side = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
      p.entry = PositionGetDouble(POSITION_PRICE_OPEN); p.tp = PositionGetDouble(POSITION_TP);
      p.exitE = 50; p.noTp = p.side > 0; p.ride = TrailOn(p.side); p.entryTime = (datetime)PositionGetInteger(POSITION_TIME); p.best = p.entry;
      p.num = ++g_num; p.slNow = PositionGetDouble(POSITION_SL); p.slFrom = p.entryTime; p.why = ""; p.usdTrail = false; p.tpNext = 0; p.tpStage = 1; p.resTp1 = false; p.setup = ""; p.sl0 = p.slNow; p.risk = 0; p.tp1 = ""; p.tp1At = 0; p.tps = ""; p.ctcAt = 0; p.moves = 0; p.mfe = 0;
      p.nxE = InpExitMode == 2 ? -2 : 0; p.brk = 0; p.bar = 0; p.enC = p.entry; p.pendSl = 0; p.pendClose = false;
      int n = ArraySize(g_pos); ArrayResize(g_pos, n + 1); g_pos[n] = p;
   }
}

bool ModifySl(ulong t, double sl)
{
   if (!PositionSelectByTicket(t)) return false;
   bool buy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double lvl = MathMax((double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL)) * _Point;
   sl = NormalizeDouble(sl, _Digits);
   if (buy ? sl >= bid - lvl : sl <= ask + lvl) return false;     // too close: the broker would refuse it
   if (TimeCurrent() < g_modBlockUntil) return false;             // v1.12: backing off after a refused modify
   if (trade.PositionModify(t, sl, PositionGetDouble(POSITION_TP))) return true;
   uint rc = trade.ResultRetcode();
   // market closed / trade disabled: wait a minute; anything else (invalid stops, requote...): wait a few seconds
   g_modBlockUntil = TimeCurrent() + ((rc == TRADE_RETCODE_MARKET_CLOSED || rc == TRADE_RETCODE_TRADE_DISABLED) ? 60 : InpModBackoffSec);
   g_modFails++;
   return false;
}

// TP reached: ride (lock + trail) or close. Returns true when the position was closed.
bool TpReached(int i, double tpLv)
{
   if (TrailOn(g_pos[i].side) && InpRide) {
      g_pos[i].ride = true; g_rides++;
      string note = "TP reached -> trailing";
      if (InpRideLock != 2 && PositionSelectByTicket(g_pos[i].ticket)) {
         double cur = PositionGetDouble(POSITION_SL);
         double lock = InpRideLock == 0 ? (g_pos[i].side > 0 ? tpLv - InpLockPips * Pip() : tpLv + InpLockPips * Pip()) : g_pos[i].entry;
         bool better = g_pos[i].side > 0 ? lock > cur : (cur == 0 || lock < cur);
         if (better) {
            if (ModifySl(g_pos[i].ticket, lock)) { SlMoved(i, lock, ""); note += StringFormat(", SL locked %.2f", lock); }
            else { g_lockFail++; note += " (lock refused: too close)"; }
         }
      }
      Callout(TimeCurrent(), tpLv, g_pos[i].side > 0, 1.5, note, g_pos[i].side > 0 ? InpLongColor : InpShortColor, 8);
      return false;
   }
   g_pos[i].why = g_pos[i].side > 0 ? StringFormat("%d EMA (TP)", g_pos[i].exitE) : "TP (last support)";
   return trade.PositionClose(g_pos[i].ticket);
}

// v1.12: bank part of the position at TP1
void PartialAtTp1(int i)
{
   if (InpPartialPct <= 0 || !PositionSelectByTicket(g_pos[i].ticket)) return;
   double vol = PositionGetDouble(POSITION_VOLUME), step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double part = MathFloor(vol * InpPartialPct / step) * step;
   if (part >= mn && vol - part >= mn - 1e-9 && trade.PositionClosePartial(g_pos[i].ticket, NormalizeDouble(part, 2))) {
      g_partials++;
      Log(StringFormat("#%d TP1: closed %.2f of %.2f lots", g_pos[i].num, part, vol));
   }
}

// LONG: a candle touched the exit EMA -> trail $X below the market and aim for the last resistance
void LongTouched(int i, double bid)
{
   PartialAtTp1(i);
   g_pos[i].ride = true; g_pos[i].usdTrail = true; g_rides++;
   if (!PositionSelectByTicket(g_pos[i].ticket)) return;
   double cur = PositionGetDouble(POSITION_SL);
   double sl = NormalizeDouble(MathMax(cur, bid - InpLongTrailUsd), _Digits);
   if (InpTp1Be && g_pos[i].entry < bid) sl = NormalizeDouble(MathMax(sl, g_pos[i].entry), _Digits);
   double res = InpLongResTp ? LastResistance(bid + InpMinTpPips * Pip()) : 0;
   double lvl = MathMax((double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL)) * _Point;
   if (sl >= bid - lvl) sl = cur;
   if (sl != cur && ModifySl(g_pos[i].ticket, sl)) SlMoved(i, sl, "");
   g_pos[i].tpNext = res; g_pos[i].tpStage = 2; g_pos[i].tp1At = TimeCurrent();
   g_pos[i].tps = res > 0 ? "TP2 " + Px(res) : "TP2 none";
   Log(StringFormat("#%d TP1: %s @ %s (entry %s, +$%.2f) | SL -> %s ($%.2f trail) | TP2 %s",
                    g_pos[i].num, g_pos[i].resTp1 ? "resistance " + Px(g_pos[i].tp) + " reached" : StringFormat("%d EMA touched", g_pos[i].exitE), Px(bid), Px(g_pos[i].entry), bid - g_pos[i].entry, Px(sl), InpLongTrailUsd,
                    res > 0 ? Px(res) + " (last resistance)" : "none above"));
   string note = StringFormat("TP1: %s -> trail $%.2f below%s", g_pos[i].resTp1 ? "resistance reached" : StringFormat("%d EMA touched", g_pos[i].exitE), InpLongTrailUsd,
                              res > 0 ? StringFormat(", TP2 %.2f (last resistance)", res) : ", no resistance above");
   Callout(TimeCurrent(), bid, true, 1.5, note, InpLongColor, 8);
   if (res > 0) DLine(TimeCurrent(), res, TimeCurrent() + 8 * PeriodSeconds(), res, clrLime, STYLE_DASH, 1, "TP2: last resistance");
}

// SHORT: the support (TP1) reached -> trail $X above the market, aim for the next support (TP2)
void ShortTouched(int i, double bid)
{
   PartialAtTp1(i);
   g_pos[i].ride = true; g_pos[i].usdTrail = true; g_rides++;
   if (!PositionSelectByTicket(g_pos[i].ticket)) return;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double cur = PositionGetDouble(POSITION_SL);
   double sl = NormalizeDouble(cur > 0 ? MathMin(cur, ask + InpShortTrailUsd) : ask + InpShortTrailUsd, _Digits);
   if (InpTp1Be && g_pos[i].entry > ask) sl = NormalizeDouble(MathMin(sl, g_pos[i].entry), _Digits);
   double lvl = MathMax((double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL)) * _Point;
   if (sl <= ask + lvl) sl = cur;
   if (sl != cur && ModifySl(g_pos[i].ticket, sl)) SlMoved(i, sl, "");
   double sup = LastSupport(bid - InpMinTpPips * Pip());
   g_pos[i].tpNext = sup; g_pos[i].tpStage = 2; g_pos[i].tp1At = TimeCurrent();
   g_pos[i].tps = sup > 0 ? "TP2 " + Px(sup) : "TP2 none";
   Log(StringFormat("#%d TP1: support reached @ %s (entry %s, +$%.2f) | SL -> %s ($%.2f trail) | TP2 %s",
                    g_pos[i].num, Px(bid), Px(g_pos[i].entry), g_pos[i].entry - bid, Px(sl), InpShortTrailUsd,
                    sup > 0 ? Px(sup) + " (next support)" : "none below"));
   string note = StringFormat("TP1: support reached -> trail $%.2f above%s", InpShortTrailUsd,
                              sup > 0 ? StringFormat(", TP2 %.2f (next support)", sup) : ", no support below");
   Callout(TimeCurrent(), bid, false, 1.5, note, InpShortColor, 8);
   if (sup > 0) DLine(TimeCurrent(), sup, TimeCurrent() + 8 * PeriodSeconds(), sup, clrLime, STYLE_DASH, 1, "TP2: next support");
}

// TPn reached: label it and draw the next target
void NextTpLabel(int i, double was)
{
   int sd = g_pos[i].side;
   double nx = g_pos[i].tpNext;
   g_pos[i].tps += StringFormat(" > TP%d %s", g_pos[i].tpStage, nx > 0 ? Px(nx) : "none");
   Log(StringFormat("#%d TP%d %s reached -> TP%d %s", g_pos[i].num, g_pos[i].tpStage - 1, Px(was), g_pos[i].tpStage,
                    nx > 0 ? Px(nx) : "none (riding the trailing stop)"));
   string note = StringFormat("TP%d %.2f reached -> %s", g_pos[i].tpStage - 1, was,
                              nx > 0 ? StringFormat("TP%d %.2f (%s)", g_pos[i].tpStage, nx, sd > 0 ? "next resistance" : "next support")
                                     : "no further level: riding the trailing stop");
   Callout(TimeCurrent(), was, sd > 0, 1.5, note, sd > 0 ? InpLongColor : InpShortColor, 8);
   if (nx > 0) DLine(TimeCurrent(), nx, TimeCurrent() + 8 * PeriodSeconds(), nx, clrLime, STYLE_DASH, 1, StringFormat("TP%d", g_pos[i].tpStage));
}

// tick by tick: target touches
void ManageTick()
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask0 = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (g_pos[i].pendClose) {            // TEST tvbars: the chart's verdict could not close it (market closed) - every 5 s until it can
         static datetime retryAt = 0;
         if (TimeCurrent() >= retryAt && !trade.PositionClose(g_pos[i].ticket)) retryAt = TimeCurrent() + 5;
         continue;
      }
      if (g_pos[i].pendSl > 0) {           // TEST tvbars diagnostic: blind inside the entry candle; its stop goes in at the next candle's open
         if (g_pos[i].bar >= CurBar()) continue;
         double ps = g_pos[i].pendSl;
         if (g_pos[i].side > 0 ? bid <= ps : ask0 >= ps) { g_pos[i].why = "stop (the candle opened beyond it)"; g_pos[i].pendSl = 0; trade.PositionClose(g_pos[i].ticket); continue; }
         if (!ModifySl(g_pos[i].ticket, ps)) continue;
         g_pos[i].pendSl = 0;
      }
      g_pos[i].mfe = g_pos[i].side > 0 ? MathMax(g_pos[i].mfe, bid) : (g_pos[i].mfe == 0 ? ask0 : MathMin(g_pos[i].mfe, ask0));
      if (g_pos[i].nxE != 0) {             // v1.25 exit modes: no lock, breakeven, partial or trail
         if (g_pos[i].nxE > 0) {
            double e = Ema(g_pos[i].nxE, 0);
            if (g_pos[i].side > 0 ? bid >= e && (!InpLongEmaAbove || e > g_pos[i].enC) : ask0 <= e) {
               g_pos[i].why = StringFormat("%d EMA touched (next EMA beyond the entry)", g_pos[i].nxE == 9 ? InpEmaFast : InpEmaSlow);
               trade.PositionClose(g_pos[i].ticket);
            }
         }
         continue;
      }
      if (InpLockAtUsd > 0 && PositionSelectByTicket(g_pos[i].ticket)) {
         double moved = g_pos[i].side > 0 ? bid - g_pos[i].entry : g_pos[i].entry - ask0;
         double want = g_pos[i].entry + g_pos[i].side * InpLockUsd, cur = PositionGetDouble(POSITION_SL);
         if (moved >= InpLockAtUsd && (g_pos[i].side > 0 ? want > cur + _Point : (cur == 0 || want < cur - _Point)) && ModifySl(g_pos[i].ticket, want)) SlMoved(i, want, "lock");
      }
      if (InpMaxBars > 0 && TimeCurrent() - g_pos[i].entryTime >= InpMaxBars * PeriodSeconds()) { g_pos[i].why = "time exit"; trade.PositionClose(g_pos[i].ticket); continue; }
      if (InpBeTpPct > 0 && !g_pos[i].ride && PositionSelectByTicket(g_pos[i].ticket)) {
         // the TP this trade is heading for: the support (SHORT), the exit EMA now (LONG), or a fixed TP
         double tpRef = g_pos[i].side < 0 || InpFixTpPips > 0 ? g_pos[i].tp
                      : (g_pos[i].noTp ? 0 : g_pos[i].resTp1 ? g_pos[i].tp : Ema(g_pos[i].exitE, 0) - InpLongTpPips * Pip());
         double dist = g_pos[i].side > 0 ? tpRef - g_pos[i].entry : g_pos[i].entry - tpRef;
         double cur = PositionGetDouble(POSITION_SL);
         bool atEntry = g_pos[i].side > 0 ? cur >= g_pos[i].entry : (cur > 0 && cur <= g_pos[i].entry);
         if (tpRef > 0 && dist > 0 && !atEntry) {
            double moved = g_pos[i].side > 0 ? bid - g_pos[i].entry : g_pos[i].entry - ask0;
            if (moved >= InpBeTpPct * dist && ModifySl(g_pos[i].ticket, g_pos[i].entry)) {
               g_ctc++; g_pos[i].ctcAt = TimeCurrent();
               SlMoved(i, g_pos[i].entry, StringFormat("CTC: %d%% of TP -> SL to entry", (int)MathRound(InpBeTpPct * 100)));
            }
         }
      }
      if (InpFixTpPips > 0) continue;
      if (g_pos[i].usdTrail && PositionSelectByTicket(g_pos[i].ticket)) {
         // after TP1: the stop follows the market $X away, never back
         int sd = g_pos[i].side;
         double dist = (sd > 0 ? InpLongTrailUsd : InpShortTrailUsd) + InpTrailStepUsd * MathMax(0, g_pos[i].tpStage - 2);
         double want = NormalizeDouble(sd > 0 ? bid - dist : ask0 + dist, _Digits), cur = PositionGetDouble(POSITION_SL);
         if ((sd > 0 ? want >= cur + 10 * _Point : (cur == 0 || want <= cur - 10 * _Point)) && ModifySl(g_pos[i].ticket, want)) {
            g_pos[i].slNow = want;      // drawn as one line at the exit, not a step per tick
            g_pos[i].moves++;
         }
         // the next liquidity reached: aim for the one beyond (TP2 -> TP3 -> ...)
         if (g_pos[i].tpNext > 0 && (sd > 0 ? bid >= g_pos[i].tpNext : bid <= g_pos[i].tpNext)) {
            double was = g_pos[i].tpNext;
            g_pos[i].tpStage++;
            g_pos[i].tpNext = sd > 0 ? LastResistance(was + InpMinTpPips * Pip()) : LastSupport(was - InpMinTpPips * Pip());
            NextTpLabel(i, was);
         }
         continue;
      }
      if (InpLongTouch == 1 && g_pos[i].side > 0 && (!g_pos[i].ride || g_pos[i].resTp1) && !g_pos[i].noTp) {
         double tgt = g_pos[i].resTp1 ? g_pos[i].tp : Ema(g_pos[i].exitE, 0) - InpLongTpPips * Pip();
         if (tgt > g_pos[i].entry && bid >= tgt) { LongTouched(i, bid); continue; }
      }
      if (g_pos[i].ride) continue;
      if (g_pos[i].side < 0) {
         // SHORT that will ride: no TP at the broker, so watch the support here (chart price = bid)
         if (g_pos[i].tp > 0 && InpShortTouch == 1 && bid <= g_pos[i].tp) { ShortTouched(i, bid); continue; }
         if (g_pos[i].tp > 0 && TrailOn(-1) && InpRide && bid <= g_pos[i].tp) TpReached(i, g_pos[i].tp);
      } else if (!g_pos[i].noTp && InpLongExit == 0) {
         double tgt = Ema(g_pos[i].exitE, 0) - InpLongTpPips * Pip();
         if (tgt > g_pos[i].entry && bid >= tgt) TpReached(i, tgt);
      }
   }
}

// candle close: close-mode exits, trailing, breakeven
void ManageBar()
{
   double c1 = BClose(1), h1 = BHigh(1), l1 = BLow(1);
   datetime t1 = BTime(1);
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      ulong t = g_pos[i].ticket;
      if (!PositionSelectByTicket(t)) continue;
      int side = g_pos[i].side;
      double sl = PositionGetDouble(POSITION_SL);
      if (g_pos[i].nxE != 0) {                      // v1.25: -1 close back across the fast EMA, -2 across the slow
         int ce = g_pos[i].nxE == -1 ? 9 : g_pos[i].nxE == -2 ? 50 : 0;
         if (ce > 0 && g_pos[i].entryTime < t1 && (side > 0 ? c1 < Ema(ce, 1) : c1 > Ema(ce, 1))) {   // chart-test: not on the entry candle's own close (indicator)
            g_pos[i].why = StringFormat("closed back across the %d EMA", ce == 9 ? InpEmaFast : InpEmaSlow);
            trade.PositionClose(t);
         }
         continue;
      }
      if (g_pos[i].usdTrail) continue;              // LONG after the touch: trailed tick by tick
      if (side > 0 && !g_pos[i].ride && InpFixTpPips <= 0 && InpLongTouch == 0) {
         double tgt = Ema(g_pos[i].exitE, 1) - InpLongTpPips * Pip();
         if (!g_pos[i].noTp && InpLongExit == 1 && tgt > g_pos[i].entry && c1 >= tgt) {
            if (TpReached(i, tgt) || !PositionSelectByTicket(t)) continue;
            sl = PositionGetDouble(POSITION_SL);        // locked; the trail may tighten it on this same candle
         }
         if (g_pos[i].noTp && !TrailOn(1) && c1 < Ema(g_pos[i].exitE, 1)) { g_pos[i].why = StringFormat("closed below %d EMA", g_pos[i].exitE); trade.PositionClose(t); continue; }
      }
      bool afterEntryBar = g_pos[i].entryTime < t1;
      if (TrailOn(side) && afterEntryBar) {
         g_pos[i].best = side > 0 ? MathMax(g_pos[i].best, h1) : MathMin(g_pos[i].best, l1);
         bool started = InpRide ? g_pos[i].ride : (side > 0 ? g_pos[i].best - g_pos[i].entry : g_pos[i].entry - g_pos[i].best) >= InpTrailStart * Pip();
         if (started) {
            double lvl;
            if (InpTrailMode == 0) {
               lvl = side > 0 ? DBL_MAX : 0;
               for (int k = 1; k <= InpTrailN; k++)
                  lvl = side > 0 ? MathMin(lvl, BLow(k)) : MathMax(lvl, BHigh(k));
            } else if (InpTrailMode == 1) lvl = side > 0 ? g_pos[i].best - InpTrailPips * Pip() : g_pos[i].best + InpTrailPips * Pip();
            else lvl = side > 0 ? g_pos[i].best - InpTrailAtr * Atr(1) : g_pos[i].best + InpTrailAtr * Atr(1);
            bool better = side > 0 ? (lvl > sl + _Point && lvl < c1) : ((sl == 0 || lvl < sl - _Point) && lvl > c1);
            if (better && ModifySl(t, lvl)) { SlMoved(i, lvl, StringFormat("trail %.2f", lvl)); sl = lvl; }
         }
      }
      if (InpBeUsd > 0 && afterEntryBar) {
         double best = side > 0 ? h1 - g_pos[i].entry : g_pos[i].entry - l1;
         bool done = side > 0 ? sl >= g_pos[i].entry : (sl > 0 && sl <= g_pos[i].entry);
         if (!done && best > InpBeUsd && ModifySl(t, g_pos[i].entry)) SlMoved(i, g_pos[i].entry, "BE");
      }
   }
}

double DayPnl()
{
   MqlDateTime d; TimeToStruct(TimeCurrent(), d); d.hour = 0; d.min = 0; d.sec = 0;
   if (!HistorySelect(StructToTime(d), TimeCurrent() + 60)) return 0;
   double s = 0;
   for (int i = HistoryDealsTotal() - 1; i >= 0; i--) {
      ulong k = HistoryDealGetTicket(i);
      if (HistoryDealGetInteger(k, DEAL_MAGIC) != InpMagicNumber) continue;
      s += HistoryDealGetDouble(k, DEAL_PROFIT) + HistoryDealGetDouble(k, DEAL_COMMISSION) + HistoryDealGetDouble(k, DEAL_SWAP);
   }
   return s;
}

void TryEntry()
{
   if (g_pSide == 0 || ArraySize(g_pos) >= InpMaxPos || g_gSide != 0) return;
   if (InpNoNewMins > 0 && MinsToClose() <= InpNoNewMins) { g_skipClose++; DSkip(g_pSide, "too close to the day's close"); g_pSide = 0; return; }
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double pip = Pip();
   int side = g_pSide;
   if (InpEntryMode == 2) {
      // liquidity sweep: price first runs the stops beyond the setup candle, then comes back
      double far = side > 0 ? g_pLow - InpSweepPips * pip : g_pHigh + InpSweepPips * pip;
      if (!g_swept && (side > 0 ? bid < far : ask > far)) { g_swept = true; g_sweepExt = side > 0 ? bid : ask; Log(StringFormat("SWEEP of the setup candle's %s at %s", side > 0 ? "low" : "high", Px(g_sweepExt))); }
      if (g_swept) g_sweepExt = side > 0 ? MathMin(g_sweepExt, bid) : MathMax(g_sweepExt, ask);
      if (!g_swept) return;
      bool go = InpSweepEntry == 0 ? (side > 0 ? bid > g_pLow : ask < g_pHigh)
                                   : (side > 0 ? bid > g_pHigh + InpBreakPips * pip : bid < g_pLow - InpBreakPips * pip);
      if (!go) return;
      if (InpMaxSpreadPts > 0 && (ask - bid) / _Point > InpMaxSpreadPts) return;
      g_pSide = 0; g_swept = false;
      DoEntry(side, side > 0 ? g_sweepExt - InpSweepSlPips * pip : g_sweepExt + InpSweepSlPips * pip);
      return;
   }
   bool hit = g_late > 0 || (side > 0 ? (InpTrigBid ? bid : ask) > g_pHigh + InpBreakPips * pip : bid < g_pLow - InpBreakPips * pip);
   if (!hit) return;
   if (InpMaxSpreadPts > 0 && (ask - bid) / _Point > InpMaxSpreadPts) return;    // wait for a normal spread
   g_pSide = 0;
   g_brk = g_late > 0 ? 0 : (side > 0 ? g_pHigh + InpBreakPips * pip : g_pLow - InpBreakPips * pip);   // TEST tvbars
   if (InpEntryMode == 1) {
      // the break happened: now wait for the dip back into the setup candle
      g_aSide = side; g_aHigh = g_pHigh; g_aLow = g_pLow; g_aExit = g_pExit; g_aLeft = InpRetestBars;
      g_aLevel = side > 0 ? g_pHigh - InpRetestFrac * (g_pHigh - g_pLow) : g_pLow + InpRetestFrac * (g_pHigh - g_pLow);
      Log(StringFormat("BREAK %s -> waiting %d candle(s) for a dip to %s", side > 0 ? "up" : "down", InpRetestBars, Px(g_aLevel)));
      return;
   }
   // chart-test: the indicator's TOP / BOTTOM FILTER - where the entry sits in the last N CLOSED candles, judged at the break level
   string bands = side > 0 ? InpBandsB : InpBandsS;
   bool off = false;
   g_ck = -1;
   if (true) {
      int look = side > 0 ? InpRangeLook : InpRangeLookS;
      double hi = 0, lo = DBL_MAX;
      for (int k = 1; k <= look; k++) { hi = MathMax(hi, BHigh(k + g_late)); lo = MathMin(lo, BLow(k + g_late)); }
      double lvl = side > 0 ? g_pHigh + InpBreakPips * pip : g_pLow - InpBreakPips * pip, o0 = BOpen(g_late);
      double px = side > 0 ? MathMax(lvl + 0.01, o0) : MathMin(lvl - 0.01, o0);
      double chase = hi > lo ? (side > 0 ? (px - lo) / (hi - lo) : (hi - px) / (hi - lo)) * 100 : 50;
      int bk = chase > 100 ? 20 : chase <= 0 ? 0 : MathMin((int)MathFloor(chase / 5), 19);
      g_ck = bk + (side > 0 ? 0 : 21);
      off = StringLen(bands) > bk && StringGetCharacter(bands, bk) == '0';
      if (off && InpBandOff == 0) { g_bandSkips++; DSkip(side, StringFormat("entry at %.0f%% of the range: unticked box", chase)); return; }
   }
   // TEST tvbars: the chart's entry price (the level + 1 cent, or the open beyond it) for the chart's decisions: stop, risk, target EMA
   g_bidC = !g_useTv ? bid : g_late > 0 ? g_lateBid : side > 0 ? MathMax(g_brk + 0.01, BOpen(0)) : MathMin(g_brk - 0.01, BOpen(0));
   g_enC = !g_useTv ? (side > 0 ? ask : bid) : side > 0 ? g_bidC + ChartSpr() : g_bidC;
   DoEntry(side, StopFor(side, g_enC, g_pHigh, g_pLow), off);
}

// mode 1: the dip after the break
void TryDip()
{
   if (g_aSide == 0 || ArraySize(g_pos) >= InpMaxPos || g_gSide != 0) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   int side = g_aSide;
   if (side > 0 ? ask > g_aLevel : bid < g_aLevel) return;
   double sl = StopFor(side, side > 0 ? ask : bid, g_aHigh, g_aLow);
   g_aSide = 0;
   if (side > 0 ? bid <= sl : ask >= sl) { g_skipDip++; Log("dip went through the stop - skipped"); return; }
   g_pHigh = g_aHigh; g_pLow = g_aLow; g_pExit = g_aExit;
   DoEntry(side, sl);
}

// the stop for an entry at `en` from a setup candle [lo, hi]
double StopFor(int side, double en, double hi, double lo)
{
   double pip = Pip();
   if (InpSlMode == 1) { double a = Atr(1 + g_late) * InpSlAtrMult; return side > 0 ? en - a : en + a; }
   if (InpSlMode == 2) return side > 0 ? en - InpSlUsd : en + InpSlUsd;
   return side > 0 ? lo - InpSlPips * pip : hi + InpSlPips * pip;
}

// lots for this trade: fixed, or InpRiskPct of equity (0 = skip)
double LotsFor(int side, double en, double sl)
{
   if (InpRiskPct <= 0) return InpLots;
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE), ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if (tv <= 0 || ts <= 0 || step <= 0) return InpLots;
   double perLot = MathAbs(en - sl) / ts * tv;                  // $ lost per 1 lot at the stop
   if (perLot <= 0) return 0;
   double lots = MathFloor(eq * InpRiskPct / 100.0 / perLot / step) * step;
   if (lots < mn) {
      if (InpMinLotRiskPct > 0 && mn * perLot > eq * InpMinLotRiskPct / 100.0) { g_skipMinLot++; return 0; }
      lots = mn;
   }
   lots = MathMin(lots, InpMaxLots);
   // margin: keep 10% free
   double m = 0;
   while (lots >= mn && OrderCalcMargin(side > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, _Symbol, lots, en, m) && m > AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.9)
      lots = MathFloor((lots - step) / step) * step;
   if (lots < mn) { g_skipMinLot++; return 0; }
   return NormalizeDouble(lots, 2);
}

void DoEntry(int side, double sl, bool ghost = false)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double pip = Pip();
   double en = side > 0 ? ask : bid;
   double enD = g_enC > 0 ? g_enC : en, bidD = g_bidC > 0 ? g_bidC : bid;     // TEST tvbars: the chart's entry price for the decisions
   g_enC = 0; g_bidC = 0;
   if (InpMaxRiskUsd > 0 && MathAbs(enD - sl) > InpMaxRiskUsd) { g_skipRisk++; DSkip(side, StringFormat("stop too far ($%.2f > $%.2f)", MathAbs(enD - sl), InpMaxRiskUsd)); return; }
   // v1.24 gates: trend strength (ADX) and the volatility band (ATR of the last closed candle)
   if (InpAdxMin > 0 && Adx(1 + g_late) < InpAdxMin) { g_skipAdx++; DSkip(side, StringFormat("ADX %.1f below %.1f (ranging)", Adx(1 + g_late), InpAdxMin)); return; }
   if ((InpAtrMinUsd > 0 && Atr(1 + g_late) < InpAtrMinUsd) || (InpAtrMaxUsd > 0 && Atr(1 + g_late) > InpAtrMaxUsd)) { g_skipVol++; DSkip(side, StringFormat("ATR $%.2f outside the band", Atr(1 + g_late))); return; }
   double tp = 0;
   bool noTp = false, resTp1 = false;
   int nxE = 0;
   if (InpExitMode == 1) {                 // v1.25: the nearer EMA beyond the entry, from the LIVE EMAs (the forming candle)
      double l9 = EmaAt(9, bidD), l50 = EmaAt(50, bidD);
      bool b9 = side > 0 ? l9 > enD : l9 < enD, b50 = side > 0 ? l50 > enD : l50 < enD;
      nxE = b9 && b50 ? (MathAbs(l9 - enD) <= MathAbs(l50 - enD) ? 9 : 50) : b9 ? 9 : b50 ? 50 : -1;
   } else if (InpExitMode == 2) nxE = -2;
   else if (side < 0) {
      double sup = LastSupport(bid - InpMinTpPips * pip);
      if (sup <= 0) { g_skipSup++; DSkip(side, "no support below to target"); return; }
      tp = sup + InpShortTpPips * pip;
      if (InpMaxTpPips > 0 && bid - tp > InpMaxTpPips * pip) { g_skipSup++; DSkip(side, "support too far"); return; }
   } else {
      noTp = Ema(g_pExit, 0) - InpLongTpPips * pip < en + InpMinTpPips * pip;
      if (noTp && InpLongResTp1 && InpLongTouch == 1) {
         double res = LastResistance(en + InpMinTpPips * pip);
         if (res > 0) { tp = res; noTp = false; resTp1 = true; }
      }
   }
   bool rideShort = side < 0 && TrailOn(-1) && InpRide && InpFixTpPips <= 0;
   if (InpFixTpPips > 0) { tp = side > 0 ? en + InpFixTpPips * pip : en - InpFixTpPips * pip; noTp = false; }
   if (ghost) {      // chart-test: stand aside - the trade runs unseen (same stop and exit), no new trade until it ends
      g_gSide = side; g_gEntry = enD; g_gSl = sl; g_gNxE = nxE; g_gExitE = g_pExit; g_gTp = tp; g_gNoTp = noTp; g_gTime = TimeCurrent(); g_ghosts++; g_gBrk = g_brk; g_gBar = CurBar();
      return;
   }
   double lots = LotsFor(side, en, sl);
   if (lots <= 0) { DSkip(side, "even the minimum lot risks too much of this account"); return; }
   bool blind = BlindNow();      // TEST tvbars diagnostic: no broker stop inside the entry candle
   bool ok = side > 0 ? trade.Buy(lots, _Symbol, 0, blind ? 0 : NormalizeDouble(sl, _Digits), InpFixTpPips > 0 ? NormalizeDouble(tp, _Digits) : 0, EA_COMMENT + " BUY")
                      : trade.Sell(lots, _Symbol, 0, blind ? 0 : NormalizeDouble(sl, _Digits), rideShort ? 0 : NormalizeDouble(tp, _Digits), EA_COMMENT + " SELL");
   if (!ok) return;
   ulong t = trade.ResultOrder();
   ulong deal = trade.ResultDeal();
   if (deal > 0 && HistoryDealSelect(deal)) t = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
   PosState p;
   p.ticket = t; p.side = side; p.entry = trade.ResultPrice() > 0 ? trade.ResultPrice() : en; p.tp = tp;
   p.nxE = nxE; p.brk = g_brk; p.bar = CurBar(); p.enC = enD; p.pendSl = blind ? NormalizeDouble(sl, _Digits) : 0; p.pendClose = false;
   p.exitE = g_pExit; p.noTp = noTp; p.resTp1 = resTp1; p.ride = side > 0 && (noTp || (resTp1 && InpResTp1Ride)) && TrailOn(1) && InpFixTpPips <= 0;
   p.entryTime = TimeCurrent(); p.best = p.entry;
   p.num = ++g_num; p.slNow = NormalizeDouble(sl, _Digits); p.slFrom = p.entryTime; p.why = ""; p.usdTrail = false; p.tpNext = 0; p.tpStage = 1; p.setup = ""; p.sl0 = p.slNow; p.risk = 0; p.tp1 = ""; p.tp1At = 0; p.tps = ""; p.ctcAt = 0; p.moves = 0; p.mfe = 0;
   p.setup = g_pDesc; p.sl0 = p.slNow; p.mfe = p.entry;
   p.risk = MathAbs(p.entry - sl) * lots * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   p.tp1 = nxE > 0 ? StringFormat("touch of the %d EMA (now %.2f), all closed", nxE == 9 ? InpEmaFast : InpEmaSlow, Ema(nxE, 0))
         : nxE == -1 ? StringFormat("no EMA beyond the entry: out after a close back across the %d EMA", InpEmaFast)
         : nxE == -2 ? StringFormat("no target: out after a close back across the %d EMA", InpEmaSlow)
         : side > 0 ? (noTp ? "none (exit EMA below entry, no resistance above) - trailing from entry"
                            : resTp1 ? StringFormat("next resistance %.2f (the %d EMA is below the entry)", tp, g_pExit)
                            : StringFormat("touch of the %d EMA (now %.2f)", g_pExit, Ema(g_pExit, 0)))
                    : StringFormat("last support %.2f", tp);
   int n = ArraySize(g_pos); ArrayResize(g_pos, n + 1); g_pos[n] = p;
   g_entries++;
   Log(StringFormat("ENTRY #%d %s %.2f lots @ %s | SL %s (risk $%.2f) | TP1 %s | setup: %s",
                    p.num, side > 0 ? "BUY" : "SELL", lots, Px(p.entry), Px(p.sl0), p.risk, p.tp1, p.setup));
   if (Drawing()) {
      string tpTxt = side > 0 ? (noTp ? "none - trailing from entry" : resTp1 ? StringFormat("%.2f (next resistance)", tp)
                                                                               : StringFormat("touch of the %d EMA", g_pExit))
                              : StringFormat("%.2f (last support)", tp);
      double risk = p.risk;
      DArrow(p.entryTime, p.entry, side);
      Callout(p.entryTime, p.entry, side < 0, 3.0,
            StringFormat("%s #%d @ %.2f", side > 0 ? "BUY" : "SELL", p.num, p.entry), side > 0 ? InpLongColor : InpShortColor, 10,
            StringFormat("%s #%d  entry %.2f | SL %.2f (-$%.2f) | TP %s | %s", side > 0 ? "BUY" : "SELL", p.num, p.entry, sl, risk, tpTxt, g_pDesc));
      DText(p.entryTime, sl, StringFormat("SL %.2f", sl), InpSlTextColor, 7, side > 0 ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER);
      if (side < 0) {
         DLine(p.entryTime, tp, p.entryTime + 8 * PeriodSeconds(), tp, clrLime, STYLE_DASH, 1, "TP: last support");
         DText(p.entryTime, tp, StringFormat("TP %.2f (last support)", tp), InpTpTextColor, 7, ANCHOR_LEFT_UPPER);
      } else if (resTp1) {
         DLine(p.entryTime, tp, p.entryTime + 8 * PeriodSeconds(), tp, clrLime, STYLE_DASH, 1, "TP1: next resistance");
         DText(p.entryTime, tp, StringFormat("TP1 %.2f (next resistance)", tp), InpTpTextColor, 7, ANCHOR_LEFT_LOWER);
      } else if (!noTp)
         DText(p.entryTime + PeriodSeconds(), Ema(g_pExit, 0), StringFormat("TP1: touch of the %d EMA", g_pExit), InpTpTextColor, 7, ANCHOR_LEFT_LOWER);
   }
   if (InpVerbose) PrintFormat("[SAAD] %s at %.2f | SL %.2f | TP %s", side > 0 ? "BUY" : "SELL", p.entry, sl,
                               side > 0 ? (noTp ? "none (trail)" : StringFormat("EMA%d", g_pExit)) : DoubleToString(tp, 2));
}

void DayCloseCheck()
{
   if (InpCloseLossMins <= 0 || ArraySize(g_pos) == 0 || MinsToClose() > InpCloseLossMins) return;
   if (BlindNow()) return;      // TEST tvbars diagnostic: a candle seen only at its close never reaches the last minutes
   double bidN = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (!PositionSelectByTicket(g_pos[i].ticket) || g_pos[i].pendSl > 0) continue;
      double pl = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      if (g_useTv) pl = g_pos[i].side > 0 ? bidN - g_pos[i].enC : g_pos[i].enC - (bidN + ChartSpr());   // TEST tvbars: the chart's view of "in loss"
      if (pl < 0) {
         g_pos[i].why = "day close, in loss";
         Log(StringFormat("#%d day close in %d min and the trade is $%.2f down -> shutting it", g_pos[i].num, MinsToClose(), pl));
         if (trade.PositionClose(g_pos[i].ticket)) g_closeLoss++;
      }
   }
}

// TEST tvbars: when the two feeds disagree by cents, the CHART's candle that just closed decides (out at this open)
bool g_freed = false;   // the chart's trade / ghost ended INSIDE the candle that just closed: the chart was free at its close
void TvVerdict()
{
   datetime t1 = BTime(1);
   if (t1 <= 0) return;
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (!PositionSelectByTicket(g_pos[i].ticket) || g_pos[i].pendClose) continue;
      int sd = g_pos[i].side; double sl = PositionGetDouble(POSITION_SL);
      // entered in that candle on an MT5 break the chart's candle never made: the chart has no trade
      if (g_pos[i].brk != 0 && g_pos[i].bar == t1 && !(sd > 0 ? BHigh(1) > g_pos[i].brk : BLow(1) < g_pos[i].brk)) {
         g_pos[i].why = "the chart's candle never broke the level";
         g_freed = true;
         if (trade.PositionClose(g_pos[i].ticket)) g_vNoBrk++; else g_pos[i].pendClose = true;
         continue;
      }
      if (g_pos[i].bar >= t1) continue;              // the chart judges a trade from the candle after its entry candle
      if (sl > 0 && (sd > 0 ? BLow(1) <= sl : BHigh(1) + ChartSpr() >= sl)) {
         g_pos[i].why = StringFormat("stop %.2f hit on the chart's candle", sl);
         g_freed = true;
         if (trade.PositionClose(g_pos[i].ticket)) g_vStop++; else g_pos[i].pendClose = true;
         continue;
      }
      if (g_pos[i].nxE > 0 && ChartTouched(sd, g_pos[i].nxE, g_pos[i].enC)) {
         g_pos[i].why = StringFormat("%d EMA touched on the chart's candle", g_pos[i].nxE == 9 ? InpEmaFast : InpEmaSlow);
         g_freed = true;
         if (trade.PositionClose(g_pos[i].ticket)) g_vTp++; else g_pos[i].pendClose = true;
      }
   }
}

// chart-test: the ghost's exit, tick by tick (the indicator runs it through the same engine as a real trade)
void GhostTick()
{
   if (g_gSide == 0) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   int s = g_gSide;
   bool end = false;
   // TEST tvbars: after its entry candle the CHART's candles judge the ghost (GhostBar); inside it MT5's ticks do, where the chart has 1-minute data
   if (!(g_useTv && InpTvVerdict) || (CurBar() == g_gBar && g_gBar >= InpTvStepFrom)) {
      end = s > 0 ? bid <= g_gSl : ask >= g_gSl;
      if (!end && g_gNxE > 0) { double e = Ema(g_gNxE, 0); end = s > 0 ? bid >= e && (!InpLongEmaAbove || e > g_gEntry) : ask <= e; }
      if (!end && g_gNxE == 0) {                    // the v1.23 exits, simplified: TP1 reached ends it
         if (s > 0 && !g_gNoTp) { double tg = Ema(g_gExitE, 0) - InpLongTpPips * Pip(); end = tg > g_gEntry && bid >= tg; }
         if (s < 0 && g_gTp > 0) end = bid <= g_gTp;
      }
   }
   if (!end && InpCloseLossMins > 0 && MinsToClose() <= InpCloseLossMins) end = s > 0 ? bid < g_gEntry : ask > g_gEntry;
   if (end) g_gSide = 0;
}

void GhostBar()
{
   if (g_gSide == 0) return;
   datetime t1 = BTime(1);
   if (g_useTv && InpTvVerdict) {
      if (g_gBrk != 0 && g_gBar == t1 && !(g_gSide > 0 ? BHigh(1) > g_gBrk : BLow(1) < g_gBrk)) { g_gSide = 0; g_vNoBrk++; g_freed = true; return; }
      if (g_gBar < t1) {
         bool hit = g_gSide > 0 ? BLow(1) <= g_gSl : BHigh(1) + ChartSpr() >= g_gSl;
         if (!hit && g_gNxE > 0) hit = ChartTouched(g_gSide, g_gNxE, g_gEntry);
         if (hit) { g_gSide = 0; g_gChart++; g_freed = true; return; }
      }
   }
   if (g_gBar >= t1) return;     // like the indicator: not on the entry candle's own close
   int ce = g_gNxE == -1 ? 9 : g_gNxE == -2 ? 50 : 0;
   double c1 = BClose(1);
   if (ce > 0 && (g_gSide > 0 ? c1 < Ema(ce, 1) : c1 > Ema(ce, 1))) g_gSide = 0;
}

void OnTick()
{
   MqlDateTime dn; TimeToStruct(TimeCurrent(), dn);
   if (dn.day_of_year != g_dayKey) { g_dayKey = dn.day_of_year; g_dayStartEq = AccountInfoDouble(ACCOUNT_EQUITY); }
   SyncPos();
   DayCloseCheck();
   SyncPos();
   bool busyStart = ArraySize(g_pos) > 0 || g_gSide != 0;     // TEST tvbars: still open when the last candle closed (before this tick's exits)
   ManageTick();
   GhostTick();
   SyncPos();
   datetime bar = CurBar();
   if (bar != g_lastBar && TvReady(bar)) {
      g_lastBar = bar;
      g_open0 = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      g_freed = false;
      if (InpTvVerdict && g_useTv) { TvVerdict(); SyncPos(); }
      if (Bars(_Symbol, PERIOD_CURRENT) >= InpEmaSlow * 2 + 20 && !g_tvStale && (!g_useTv || g_tvEnd >= InpEmaSlow * 2 + 19)) {
         ManageBar();
         GhostBar();
         SyncPos();
         g_busyAtClose = busyStart && !(g_freed && ArraySize(g_pos) == 0 && g_gSide == 0);
         // the waiting setup: a gap in time cancels it, otherwise one fewer candle to break
         if (g_aSide != 0) {
            if (InpGapCancel && BTime(0) - BTime(1) > PeriodSeconds() * 3 / 2) { g_aSide = 0; g_skipDip++; }
            else if (--g_aLeft <= 0) { g_aSide = 0; g_skipDip++; Log("no dip within the window - skipped"); }
         }
         if (g_pSide != 0 && InpEntryMode == 2 && g_pLeft <= 1) { if (!g_swept) g_skipSweep++; }
         if (g_pSide != 0) {
            // TEST tvbars: the chart's candle broke the level and MT5's ticks did not -> the chart entered in that candle: enter at this open
            if (InpTvVerdict && g_useTv && InpEntryMode == 0 && ArraySize(g_pos) == 0 && g_gSide == 0 && BTime(1) > g_pTime &&
                (g_pSide > 0 ? BHigh(1) > g_pHigh + InpBreakPips * Pip() : BLow(1) < g_pLow - InpBreakPips * Pip())) {
               double lvl = g_pSide > 0 ? g_pHigh + InpBreakPips * Pip() : g_pLow - InpBreakPips * Pip();
               g_lateBid = g_pSide > 0 ? MathMax(lvl + 0.01, BOpen(1)) : MathMin(lvl - 0.01, BOpen(1));
               Log(StringFormat("the chart's candle broke the %s (MT5's ticks did not) - entering at this open", g_pSide > 0 ? "high" : "low"));
               g_vLate++; g_late = 1; TryEntry(); g_late = 0;
               if (g_pSide != 0 && --g_pLeft <= 0) g_pSide = 0;
            }
            else if (InpGapCancel && BTime(0) - BTime(1) > PeriodSeconds() * 3 / 2) { g_skipGap++; DSkip(g_pSide, "market closed in between"); g_pSide = 0; }
            else if (--g_pLeft <= 0) { g_skipBreak++; DSkip(g_pSide, StringFormat("%s not broken in %d candle%s", g_pSide > 0 ? "high" : "low", InpBreakBars, InpBreakBars > 1 ? "s" : "")); g_pSide = 0; }
         }
         DetectSetup();
      }
   }
   TryEntry();
   TryDip();
}

// a new setup on the candle that just closed
datetime g_coolUntil = 0;
void CheckCooldown()
{
   static int seen = 0;
   if (InpCoolBars <= 0) return;
   if (!HistorySelect(TimeCurrent() - 86400 * 3, TimeCurrent() + 60)) return;
   int n = HistoryDealsTotal();
   if (n == seen) return;
   seen = n;
   for (int i = n - 1; i >= 0; i--) {
      ulong k = HistoryDealGetTicket(i);
      if (HistoryDealGetInteger(k, DEAL_MAGIC) != InpMagicNumber || HistoryDealGetInteger(k, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      if (HistoryDealGetDouble(k, DEAL_PROFIT) < 0) g_coolUntil = MathMax(g_coolUntil, (datetime)HistoryDealGetInteger(k, DEAL_TIME) + InpCoolBars * PeriodSeconds());
      break;
   }
}

void DetectSetup()
{
   if (InpNoNewMins > 0 && MinsToClose() <= InpNoNewMins) return;   // too close to the day's close
   if (InpNoEntryExitBar && g_busyAtClose) { g_busy++; return; }     // TEST tvbars: the chart was still in a trade at this candle's close
   CheckCooldown();
   if (TimeCurrent() < g_coolUntil) return;
   int shape = Shape(1);
   if (shape == 0) return;
   MqlDateTime dt; TimeToStruct(BTime(1), dt);
   if (dt.hour < InpSessFrom || dt.hour >= InpSessTo) return;
   if (InpSkipDow >= 0 && dt.day_of_week == InpSkipDow) return;
   double e9 = Ema(9, 1), e50 = Ema(50, 1);
   if (e9 <= 0 || e50 <= 0) return;
   double h = BHigh(1), l = BLow(1);
   double o = BOpen(1), c = BClose(1);

   bool on9L = OnLine(1, e9, 1), on50L = OnLine(1, e50, 1);
   bool rulesOk = InpLongRule != 1 && on9L  && !(InpLongExitAbove && e50 <= h);
   bool invOk   = InpLongRule != 0 && on50L && !(InpLongExitAbove && e9 <= h);
   bool longLine = rulesOk || invOk;
   bool shortLine = InpShortLine == 0 ? OnLine(1, e50, -1) : InpShortLine == 1 ? OnLine(1, e9, -1) : (OnLine(1, e50, -1) || OnLine(1, e9, -1));
   bool longOk  = InpBuys && longLine && (shape == 1 || (shape == 2 && (!shortLine || c >= o)));
   bool shortOk = InpSells && shortLine && (shape == -1 || shape == 2) && !longOk;
   if (!longOk && !shortOk) return;
   if (Choppy()) {
      g_chop++;
      if (InpDrawSkips) Callout(BTime(1), longOk ? l : h, !longOk, 1.0, "skip: choppy", clrDimGray, 7);
      return;
   }
   int side = longOk ? 1 : -1;

   if (hHtf != INVALID_HANDLE) {
      // the last CLOSED higher-timeframe candle: price on the trade's side of its EMA, and the EMA moving that way
      double hc = iClose(_Symbol, g_htf, 1), he1 = Buf(hHtf, 1), he2 = Buf(hHtf, 2);
      bool ok = side > 0 ? (hc > he1 && he1 > he2) : (hc < he1 && he1 < he2);
      if (he1 <= 0 || he2 <= 0 || !ok) { g_filtered++; return; }
   }
   if ((InpTrendAlign && (side > 0 ? e9 <= e50 : e9 >= e50)) ||
       (InpPriceSide && (side > 0 ? c <= e50 : c >= e50)) ||
       (InpSlopePips > 0 && (Ema(50, 1) - Ema(50, 1 + InpSlopeLook)) * side < InpSlopePips * Pip()) ||
       (InpEmaGapPips > 0 && MathAbs(e9 - e50) < InpEmaGapPips * Pip())) { g_filtered++; return; }

   if (InpDayLossUsd > 0 || InpDayTargetUsd > 0) {
      double d = DayPnl();
      if ((InpDayLossUsd > 0 && d <= -InpDayLossUsd) || (InpDayTargetUsd > 0 && d >= InpDayTargetUsd)) { g_dayStop++; return; }
   }
   if (InpDayLossPct > 0 && AccountInfoDouble(ACCOUNT_EQUITY) <= g_dayStartEq * (1 - InpDayLossPct / 100.0)) { g_dayLossStop++; return; }
   if (ArraySize(g_pos) >= InpMaxPos || g_gSide != 0 || ((g_pSide != 0 || g_aSide != 0) && !InpReplace)) { g_busy++; return; }
   if (ArraySize(g_pos) > 0 && InpExtraDir != 0) {
      bool same = g_pos[0].side == side;
      if ((InpExtraDir == 1 && !same) || (InpExtraDir == 2 && same)) { g_busy++; return; }
   }

   g_pSide = side; g_pHigh = h; g_pLow = l; g_pLeft = InpEntryMode == 2 ? InpSweepBars : InpBreakBars; g_setups++; g_swept = false; g_aSide = 0;
   g_pExit = side > 0 ? (rulesOk ? 50 : 9) : 0;
   string kindTxt = g_kind == 1 ? "PIN BAR" : g_kind == 2 ? (side > 0 ? "HAMMER" : "SHOOTING STAR") : "MARUBOZU";
   string lineTxt = side > 0 ? (rulesOk ? "9 EMA" : "50 EMA") : (OnLine(1, e9, -1) ? "9 EMA" : "50 EMA");
   g_pTime = BTime(1);
   g_pDesc = StringFormat("%s %s on the %s%s", side > 0 ? "LONG" : "SHORT", kindTxt, lineTxt,
                          side > 0 ? (rulesOk ? " (exit at 50 EMA)" : " (exit at 9 EMA)") : " (TP last support)");
   Log(StringFormat("SETUP %s | candle %s H %s L %s | waiting 1 candle for a break %s %s", g_pDesc, Ts(g_pTime), Px(h), Px(l),
                    side > 0 ? "above" : "below", Px(side > 0 ? h + InpBreakPips * Pip() : l - InpBreakPips * Pip())));
   if (Drawing()) {
      double lvl = side > 0 ? h + InpBreakPips * Pip() : l - InpBreakPips * Pip();
      color sc = side > 0 ? InpLongColor : InpShortColor;
      DBox(g_pTime, h, g_pTime + PeriodSeconds(), l, sc);
      DLine(g_pTime, lvl, g_pTime + (InpBreakBars + 1) * PeriodSeconds(), lvl, sc, STYLE_DOT, 1, "break level");
      Callout(g_pTime + PeriodSeconds() / 2, side > 0 ? h : l, side > 0, 2.5,
              StringFormat("SETUP %s: %s on %s", side > 0 ? "LONG" : "SHORT", kindTxt, lineTxt), InpSetupTextColor, 9,
              StringFormat("%s | wait max %d candle(s) for a break %s %.2f", g_pDesc, InpBreakBars, side > 0 ? "above" : "below", lvl));
   }
   if (InpVerbose) PrintFormat("[SAAD] %s setup (%s) on %s | waiting for %s %.2f", side > 0 ? "LONG" : "SHORT",
                               g_kind == 1 ? "pin" : g_kind == 2 ? "hammer/star" : "marubozu",
                               side > 0 ? (rulesOk ? "9 EMA, exit 50" : "50 EMA, exit 9") : "EMA", side > 0 ? ">" : "<", side > 0 ? h : l);
}
