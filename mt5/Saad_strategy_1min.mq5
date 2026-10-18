//+------------------------------------------------------------------+
//| Saad_strategy_1min.mq5  v1.00 (2026-10-16)                       |
//| Zee: "take these settings from tradingview and saad_strategy_15  |
//| code and create a new EA from this called saad_strategy_1min.    |
//| then test these settings on 1 min timeframe in mt5"              |
//|                                                                  |
//| = Saad_strategy_15min v1.23 (same engine; it reads the chart's   |
//|   own candles, so attach it to an M1 chart) with Zee's           |
//|   TradingView settings of 16 Oct 2026 (VANTAGE:XAUUSD 1 min) as  |
//|   the defaults, plus three of the indicator's chart-only rules   |
//|   he had switched on:                                            |
//|   InpTrailGapUsd  the ATR trail stays $X under the candle close  |
//|   InpCutRunN      N candles in a row against a losing trade: out |
//|   InpRangeLook/Min/Max  enter only between Min% and Max% of the  |
//|                   last N closed candles' range (BUY from the     |
//|                   bottom, SELL mirrored)                         |
//| v1.01: a trail level already passed at the open closes at market |
//| v1.02: BUY and SELL entry bands are separate (InpRange*S)        |
//| v1.03: InpLockMode 1 - the lock per candle close, like the chart |
//|        InpBandAtLevel - entry band judged at the break level      |
//| v1.04: InpBarSource 1 - the TradingView chart's candles (bridge) |
//|        InpUsdTrailMode 1 - the $ trail after TP1 per candle        |
//|        InpNoEntryExitBar - no entry in the candle of an exit       |
//| v1.05: InpBandsB / InpBandsS - 21 range tick-boxes (5% each)     |
//| v1.06: InpHtfMin also 5 (the chart's "Require trend alignment")  |
//| v1.07: InpTpMode - TP1 method: normal / fixed $ / Fib / partial   |
//| v1.08: a TP1 share of 1 closes the whole trade at TP1            |
//| v1.09: InpTpNoFixSkip - skip a trade whose method target is near |
//| v1.10: InpBandPauseBars - pause N candles after a range skip       |
//| v1.11: InpWaitEntryBar - no management inside the entry minute    |
//| v1.12: InpSlNextBar - a stop moved mid-minute counts from the next |
//| v1.13: entry decisions judged at the chart's price (InpBandAtLevel)|
//| v1.14: InpTvVerdict - the chart's candle decides breaks / stop hits|
//| v1.15: no setup on a candle that closed with a trade open (busy)  |
//| v1.16: "market closed" at the daily open: retry the entry          |
//| v1.17: InpChartSpread - decisions use the chart's fixed spread     |
//| v1.18: a range-skip pause the chart's candle never broke is undone |
//| v1.19: the stop after TP1 is set from the chart's TP1 candle      |
//| v1.20: stop decisions use the chart's entry price (EnJ)          |
//| v1.21: TP1 reached on the chart's candle -> TP1 at the next open  |
//| v1.22: a chart-candle stop = closed during that candle (not busy) |
//| v1.23: no chart candles for a date -> MT5's own candles          |
//| v1.24: InpCsvName - per-trade CSV in fast tests (page's chart)   |
//|        + OnTester score for MT5's optimizer (net / max drawdown) |
//| v1.25: InpOptScore 2 = win rate of whole trades (TP1 + rest)     |
//| v1.26: chart candles on any timeframe (InpTvFile auto) + Zee's   |
//|        15-min settings of 17 Oct as defaults - attach to M15     |
//| v1.27: day-close cut judged at the chart candle's open (M5+)     |
//| v1.28: InpOptScore 3 = the worst month (robust optimizer score)  |
//| v1.29: defaults ATR stop 2.5x + TP1 10 pips early (all months +) |
//| v1.30: no chart-candle file -> MT5's own candles (no init fail)  |
//| v1.31: InpOptScore 4 = trade win rate, always (optimizer)        |
//| v1.32: InpAdaptWeeks - weekly self-tuning range boxes (off)      |
//| v1.33: InpAdaptToday - boxes re-judged after every trade (off)   |
//| v1.34: InpTpFixUsd - one fixed $ target for both sides (opt.)    |
//| v1.35: InpReEntry - re-enter the setup after a stop-out (off)    |
//|        trigger = the setup's break level again, as the indicator |
//| v1.36: InpCoolN/Dir/WinOnly - the chart's cool-down after exits  |
//| magic 88305. TEST - not promoted until MT5 says so.              |
//+------------------------------------------------------------------+
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
#property version   "1.36"
#property strict

#include <Trade/Trade.mqh>
#resource "\\Indicators\\SaadEMAs.ex5"   // v1.22: EMA 9 (blue) + EMA 50 (red) drawn thick, embedded: no separate install
// v1.23 (Zee): EMA touch tolerance 1 pip ($0.10) - a candle within 10 cents of the EMA counts as on it (MT5: +$8.8k full year, both halves, random delay +$7.5k)
// v1.22 (Zee): the two EMAs it trades on are drawn on the chart when attached - EMA 9 thick blue, EMA 50 thick red (InpShowEmas)
// v1.21 (Zee): EXIT label and SETUP label text in black; the TP1 labels in blue (InpExitTextColor / InpSetupTextColor / InpTpTextColor)
// v1.20 (Zee): stop-loss text in black (InpSlTextColor); the stop LINES stay red
// v1.19 (Zee): chart text colour by side - everything about a LONG in dark green, about a SHORT in red
// v1.18 (Zee): every trade's comment names the EA + version, so the account history shows where it came from
#define EA_COMMENT "Saad1m v1.36"

//--- the two lines
input int    InpEmaFast     = 14;      // InpEmaFast
input int    InpEmaSlow     = 70;     // InpEmaSlow
input bool   InpShowEmas    = true;   // InpShowEmas — draw the two EMAs on the chart: EMA 9 thick blue, EMA 50 thick red

//--- ① setup candle
input double InpWickMin     = 0.5;   // InpWickMin — pin: long wick >= this x range [v1.13: 0.35->0.45]
input double InpBodyMax     = 0.45;   // InpBodyMax — pin: body <= this x range
input double InpNoseMax     = 0.45;   // InpNoseMax — pin: short wick <= this x range
input bool   InpPinDir      = false;  // InpPinDir — pin must point the trade way (false = any pin, the EMA decides)
input bool   InpPinColor    = false;  // InpPinColor — pin body must close the trade way too: LONG green, SHORT red (with InpPinDir)
input bool   InpUsePin      = true;   // InpUsePin — accept pin bars
input bool   InpMarubozu    = true;   // InpMarubozu — accept a marubozu
input double InpMaruBody    = 0.53;   // InpMaruBody — marubozu: body >= this x range [v1.09: 0.70->0.50, Zee; 0.35-0.55 plateau] [v1.14: 0.50->0.53]
input bool   InpHammer      = true;   // InpHammer — accept hammers (LONG)
input bool   InpStar        = true;   // InpStar — accept shooting stars (SHORT)
input double InpHamRatio    = 2.0;    // InpHamRatio — hammer: long wick >= this x body [v1.13: 3->2.5]
input double InpHamNose     = 0.35;   // InpHamNose — hammer: opposite wick <= this x range
input double InpMinRangeAtr = 0.35;   // InpMinRangeAtr — candle range >= this x ATR(14) (0 = off) [v1.14: 0.50->0.55]

//--- ① on the EMA
input int    InpLongRule    = 2;      // InpLongRule — 0 on 9 EMA exit 50 (rules) · 1 on 50 exit 9 (inverse) · 2 both
input int    InpShortLine   = 2;      // InpShortLine — 0 the 50 EMA (rules) · 1 the 9 EMA · 2 either [M15: 2->1, SHORT setups on the 9 EMA]
input int    InpTouchMode   = 0;      // InpTouchMode — 0 candle touches the EMA · 1 wick touches, body on the trade side
input double InpTouchPips   = 1;      // InpTouchPips — touch tolerance [v1.23: 0->1; 1-3 pips plateau, 4+ worse]
input bool   InpLongExitAbove = false;// InpLongExitAbove — LONG only when its exit EMA is above the candle

//--- ② break · ③ entry
input int    InpBreakBars   = 1;      // InpBreakBars — the high/low must break within this many candles [M15: 2->1, one 15-min candle = three 5-min ones]
input double InpBreakPips   = 5;      // InpBreakPips — break must clear the high/low by this many pips [v4.02: 0->2, MT5 court]
input bool   InpTrigBid     = true;   // InpTrigBid — LONG break judged on the BID like the chart (false = the ASK, a real buy stop)

//--- ④ stop · ⑤ target
input double InpSlPips      = 36.0;     // InpSlPips — stop beyond the candle [v4.02: 34->30] [v1.13: 30->35, real-tick court + Jul-Oct holdout]
input double InpMaxRiskUsd  = 20.0;    // InpMaxRiskUsd — skip if the stop is more than this $ of price away (0 = off) [M15: 9->15; 14-18 plateau, 9 skips 2/3 of M15 setups]
input int    InpLongExit    = 1;      // InpLongExit — 0 a candle touches the exit EMA · 1 a candle CLOSES at / beyond it
input double InpLongTpPips  = 10;      // InpLongTpPips — LONG: take profit this many pips before the EMA
input int    InpSwingPivot  = 8;      // InpSwingPivot — SHORT "last support" = swing low with this many candles each side
input int    InpSwingLook   = 32;    // InpSwingLook — candles back to search for the support [M15: 300->100 candles = 25 hours]
input double InpShortTpPips = 10;      // InpShortTpPips — SHORT: take profit this many pips before the support
input double InpMinTpPips   = 10.0;      // InpMinTpPips — TP at least this far from the entry
input double InpMaxTpPips   = 0;      // InpMaxTpPips — skip a SHORT whose support is further than this (0 = off)

//--- ⑥ breakeven
input double InpBeUsd       = 0.0;    // InpBeUsd — stop to entry once price moved this $ (0 = off)
input int    InpNoNewMins   = 0;      // InpNoNewMins — no new setups / entries this many minutes before the day's close (0 = off) [v1.03 30; v1.05 OFF, Zee: costs ~$11k at 1 lot]
input int    InpCloseLossMins = 1;    // InpCloseLossMins — this many minutes before the close: shut trades in loss, keep winners (0 = off) [v1.03, Zee]
input int    InpLongTouch   = 1;      // InpLongTouch — LONG at the exit EMA: 1 on a TOUCH trail $X below the market + TP at the last resistance (Zee 2026-10-12) · 0 old exit
input double InpLongTrailUsd = 1.0;   // InpLongTrailUsd — ...the trailing stop's distance below the market, $ of price [v1.07: 3->2, Zee]
input bool   InpLongResTp   = true;   // InpLongResTp — ...and aim for the next liquidity: TP2 = last resistance, then TP3 = the one beyond (watched by the EA; the exit is the trail)
input bool   InpLongResTp1  = false;  // InpLongResTp1 — LONG whose exit EMA is below / too close to the entry: TP1 = the next resistance above the entry (false = no TP, trail from entry) [v1.11 Zee; v1.12 OFF: -$70k on real ticks (trailing from entry is better)]
input bool   InpResTp1Ride  = true;   // InpResTp1Ride — with InpLongResTp1: also trail from the entry (2xATR) until that resistance is reached
input int    InpShortTouch  = 1;      // InpShortTouch — SHORT at the support (TP1): 1 trail $X above the market + TP2/TP3 = the supports below (Zee 2026-10-12) · 0 old (lock + ATR trail)
input double InpTrailStepUsd = 0;     // InpTrailStepUsd — widen the $ trail by this much at each TP reached after TP1 (TP2 +1x, TP3 +2x ...; 0 = fixed)
input double InpShortTrailUsd = 2.0;  // InpShortTrailUsd — ...the trailing stop's distance above the market, $ of price [v1.07: 3->2, Zee]
input double InpBeTpPct     = 1.0;   // InpBeTpPct — CTC: stop to entry once price covered this share of the way to the TP (0 = off) [v1.02, Zee]

//--- ⑦ trailing
input bool   InpTrail       = true;   // InpTrail — use a trailing stop
input int    InpTrailSide   = 2;      // InpTrailSide — 0 LONG only · 1 SHORT only · 2 both
input bool   InpRide        = true;   // InpRide — let winners run: trail from the TP instead of exiting
input int    InpTrailMode   = 2;      // InpTrailMode — 0 low/high of last N candles · 1 X pips behind best · 2 ATR x behind best [v4.02: 0->2 ATR]
input int    InpTrailN      = 6;      // InpTrailN — N candles
input double InpTrailPips   = 30;     // InpTrailPips — X pips
input double InpTrailAtr    = 0.2;    // InpTrailAtr — ATR multiple [v4.02: 1.3->2.0; 1.75-2.5 plateau]
input double InpTrailStart  = 0;      // InpTrailStart — without ride: start trailing after this many pips of profit
input int    InpRideLock    = 0;      // InpRideLock — when the TP is reached lock the stop at: 0 the TP · 1 the entry · 2 don't lock
input double InpLockPips    = 0;      // InpLockPips — lock this many pips short of the TP [v4.02: 2->0]

//--- ✖ filters
input double InpChopEr      = 0.0;   // InpChopEr — skip if the efficiency ratio is below this (0 = off) [v1.14: 0.10->0.11]
input int    InpChopErLook  = 16;     // InpChopErLook — efficiency ratio length
input int    InpSessFrom    = 0;      // InpSessFrom — broker hour, inclusive (Axi UTC+3; 0/24 = all day)
input int    InpSessTo      = 24;     // InpSessTo — broker hour, exclusive
input bool   InpGapCancel   = false;   // InpGapCancel — cancel a waiting setup across the daily close / weekend
input int    InpHtfMin      = 0;      // InpHtfMin — higher-timeframe trend filter: 0 off · 5 / 15 / 30 / 60 / 240 minutes (trade only with that timeframe's trend)
input int    InpHtfEma      = 9;     // InpHtfEma — the HTF trend EMA (LONG: HTF close above it and it is rising; SHORT the opposite)
input bool   InpTrendAlign  = false;  // InpTrendAlign — LONG only if EMA9 > EMA50, SHORT only if EMA9 < EMA50
input bool   InpPriceSide   = false;  // InpPriceSide — LONG only if the close is above the 50 EMA, SHORT below
input double InpSlopePips   = 0;      // InpSlopePips — the 50 EMA must move this many pips the trade's way...
input int    InpSlopeLook   = 5;      // InpSlopeLook — ...over this many candles (0 pips = off)
input double InpEmaGapPips  = 0;      // InpEmaGapPips — skip if the 9 and 50 EMA are closer than this (0 = off)
input double InpMaxSpreadPts = 0;     // InpMaxSpreadPts — skip an entry while the spread is wider (0 = off)
input int    InpSkipDow     = -1;     // InpSkipDow — no new setups on this weekday (0 Sun .. 6 Sat; -1 none)

//--- v4.01 tuning: geometry
input double InpLockAtUsd   = 0.0;      // InpLockAtUsd — once price moved this $ the trade's way... (0 = off; VSISA's one-lock ratchet)
input double InpLockUsd     = 0.0;      // InpLockUsd — ...lock the stop this $ beyond the entry
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
input double InpSlAtrMult   = 2.5;    // InpSlAtrMult — stop mode 1
input double InpSlUsd       = 5.0;    // InpSlUsd — stop mode 2, $ of price
input double InpPartialPct  = 0.95;    // InpPartialPct — close this share of the position at TP1 (0 = off) [v1.16: 0 -> 0.5, Zee's rule]
input bool   InpTp1Be       = true;   // InpTp1Be — at TP1 the rest of the position's stop is never worse than the entry (breakeven) [v1.16, Zee's rule]
input double InpRiskPct     = 0;      // InpRiskPct — size each trade to risk this % of equity (0 = fixed InpLots)
input double InpMinLotRiskPct = 0;    // InpMinLotRiskPct — with InpRiskPct: skip a trade when even the minimum lot would risk more than this % of equity (0 = take it at the minimum lot)
input double InpMaxLots     = 50;     // InpMaxLots — upper limit for InpRiskPct sizing
input int    InpModBackoffSec = 3;   // InpModBackoffSec — after the broker refuses a stop change, wait this many seconds before trying again (60 s when the market is closed)
input double InpDayLossPct  = 0;      // InpDayLossPct — no new trades today after losing this % of the day's starting equity (0 = off)

//--- trading
input double InpLots        = 2.00;   // InpLots — lot size [v1.17: 0.10 -> 1, Zee]
input bool   InpBuys        = true;   // InpBuys — allow longs
input bool   InpSells       = true;   // InpSells — allow shorts
input int    InpPipPts      = 10;     // InpPipPts — points per pip (gold 10)
input int    InpMagicNumber = 88305;  // InpMagicNumber — Saad_strategy [M15 variant: own magic, can run beside the M5 EA]
input bool   InpVerbose     = false;  // InpVerbose — print every decision
input bool   InpDraw        = true;   // InpDraw — labels on the chart (visual tester + live): setups, entries, stop moves, exits
input bool   InpLog         = true;   // InpLog — print every trade event to the Experts tab (live + visual tester)
input bool   InpLogCsv      = true;   // InpLogCsv — one CSV row per closed trade in Common\Files (live + visual tester)
input int    InpOptScore    = 0;      // InpOptScore — v1.24 optimizer score: 0 = net / max drawdown, 1 = win rate of closes, 2 = win rate of whole trades (v1.25), 3 = the worst month's net (v1.28) - both only for a net profit; a loss scores below every winner
input int    InpOptMinTrades = 200;  // InpOptMinTrades — v1.24 optimizer score: fewer closed trades than this scores below every real result
input string InpCsvName     = "";     // InpCsvName — v1.24: write the per-trade CSV under this name, also in a fast (non-visual) test (the compare page's 10-month chart)
input color  InpLongColor   = clrGreen; // InpLongColor — chart text/marks for LONG setups and trades (Zee: dark green)
input color  InpShortColor  = clrRed;   // InpShortColor — chart text/marks for SHORT setups and trades
input color  InpSetupTextColor = clrBlack; // InpSetupTextColor — the "SETUP LONG/SHORT: ..." label text (Zee: black); its box and break line keep the side colour
input color  InpTpTextColor = clrBlue;   // InpTpTextColor — the TP1 labels ("TP1: touch of the 50 EMA", "TP ... (last support)", "TP1 ... (next resistance)"; Zee: blue)
input color  InpExitTextColor = clrBlack; // InpExitTextColor — the "EXIT #n ... $" label (Zee: black; was green/red by profit)
input color  InpSlTextColor = clrBlack; // InpSlTextColor — stop-loss TEXT (the "SL price" label and stop-move notes; Zee: black). Lines stay red
input bool   InpDrawSkips   = true;   // InpDrawSkips — also label setups that were skipped (no break, risk, no support, choppy)
input group "1-MIN ADDITIONS (from the TradingView indicator, 16 Oct 2026)"
input double InpTrailGapUsd = 0.1;    // InpTrailGapUsd - the ATR trail stops at least this $ under (BUY) / over (SELL) the candle close (0 = off)
input int    InpCutRunN     = 5;      // InpCutRunN - this many candles in a row against a trade that is in loss: close it (0 = off)
input int    InpRangeLook   = 16;      // InpRangeLook - BUY: range of the last N closed candles for the entry band
input double InpRangeMin    = 0.0;     // InpRangeMin - skip a BUY entering below this % of that range (SELL mirrored; 0 = off)
input double InpRangeMax    = 0.0;     // InpRangeMax - skip a BUY entering above this % of that range (0 = off; over 100 = a new high)
input int    InpRangeLookS  = 9;      // InpRangeLookS - SELL: range of the last N closed candles (v1.02: BUY and SELL have their own band)
input double InpRangeMinS   = 0.0;     // InpRangeMinS - SELL: skip entering higher than this % from the top of that range (0 = off)
input double InpRangeMaxS   = 0.0;     // InpRangeMaxS - SELL: skip entering lower than this % from the top (0 = off; over 100 = a new low)
input int    InpLockMode    = 1;      // InpLockMode - 0 the lock on every tick (v1.02) · 1 at each candle close like the TradingView chart: set only once a closed candle's low (BUY) / high + spread (SELL) is past the lock level
input bool   InpBandAtLevel = true;   // InpBandAtLevel - judge the entry band at the break level + 0.01 (or the candle open past it), as the TradingView chart does; false = at the live bid (v1.02)
input bool   InpDumpBars    = false;  // InpDumpBars - debug: write every closed candle with its EMAs to Common\Files\saad1m_bars.csv (chart vs MT5 feed check)
input int    InpBarSource   = 1;      // InpBarSource - 0 the MT5 candles · 1 the TradingView chart's candles (Common\Files\InpTvFile, written by monitor/saad_compare/tv_bars_bridge.py) - same setups as the chart
input string InpTvFile      = "auto"; // InpTvFile - the chart's closed candles in broker server time: "YYYY.MM.DD HH:MM,open,high,low,close" · auto = tv_bars_XAUUSD.csv on M1, tv_bars_XAUUSD_M15.csv on M15 ... (the bridge's names)
input int    InpTvWaitSec   = 20;     // InpTvWaitSec - live: wait up to N s after a new candle for the chart's closed candle to arrive
input int    InpUsdTrailMode = 1;     // InpUsdTrailMode - the $ trail after TP1: 0 every tick (v1.03) · 1 once per candle from its high (BUY) / low + spread (SELL), like the chart
input bool   InpNoEntryExitBar = true; // InpNoEntryExitBar - no new trade in the candle where the last one closed (the chart's minute-by-minute engine)
input string InpBandsB      = "111011110010000010110"; // InpBandsB - BUY ranges of the last InpRangeLook candles, one digit each: 0-5%, 5-10% ... 95-100%, over 100% (1 = trade, 0 = skip) - the chart's TOP / BOTTOM tick-boxes
input string InpBandsS      = "111111110100001011110"; // InpBandsS - SELL ranges, measured down from the high, same 21 digits
// v1.24 (Zee 2026-10-17: "the first thing i need you to optimize for is the settings for Entry position in the range"): MT5's
// optimizer cannot search a text input, so the same 42 boxes as on/off inputs. InpBoxInputs true = these decide, the strings are ignored.
input bool   InpBoxInputs   = false;  // InpBoxInputs - true: the 42 InpBxx / InpSxx inputs below replace InpBandsB / InpBandsS
input bool   InpB00 = true;     // InpB00 - BUY 0-5% (InpBoxInputs)
input bool   InpB01 = true;     // InpB01 - BUY 5-10% (InpBoxInputs)
input bool   InpB02 = true;     // InpB02 - BUY 10-15% (InpBoxInputs)
input bool   InpB03 = true;     // InpB03 - BUY 15-20% (InpBoxInputs)
input bool   InpB04 = true;     // InpB04 - BUY 20-25% (InpBoxInputs)
input bool   InpB05 = true;     // InpB05 - BUY 25-30% (InpBoxInputs)
input bool   InpB06 = true;     // InpB06 - BUY 30-35% (InpBoxInputs)
input bool   InpB07 = true;     // InpB07 - BUY 35-40% (InpBoxInputs)
input bool   InpB08 = true;     // InpB08 - BUY 40-45% (InpBoxInputs)
input bool   InpB09 = true;     // InpB09 - BUY 45-50% (InpBoxInputs)
input bool   InpB10 = true;     // InpB10 - BUY 50-55% (InpBoxInputs)
input bool   InpB11 = true;     // InpB11 - BUY 55-60% (InpBoxInputs)
input bool   InpB12 = true;     // InpB12 - BUY 60-65% (InpBoxInputs)
input bool   InpB13 = true;     // InpB13 - BUY 65-70% (InpBoxInputs)
input bool   InpB14 = true;     // InpB14 - BUY 70-75% (InpBoxInputs)
input bool   InpB15 = true;     // InpB15 - BUY 75-80% (InpBoxInputs)
input bool   InpB16 = true;     // InpB16 - BUY 80-85% (InpBoxInputs)
input bool   InpB17 = true;     // InpB17 - BUY 85-90% (InpBoxInputs)
input bool   InpB18 = true;     // InpB18 - BUY 90-95% (InpBoxInputs)
input bool   InpB19 = true;     // InpB19 - BUY 95-100% (InpBoxInputs)
input bool   InpB20 = true;     // InpB20 - BUY over 100% (InpBoxInputs)
input bool   InpS00 = true;     // InpS00 - SELL 0-5% (InpBoxInputs)
input bool   InpS01 = true;     // InpS01 - SELL 5-10% (InpBoxInputs)
input bool   InpS02 = true;     // InpS02 - SELL 10-15% (InpBoxInputs)
input bool   InpS03 = true;     // InpS03 - SELL 15-20% (InpBoxInputs)
input bool   InpS04 = true;     // InpS04 - SELL 20-25% (InpBoxInputs)
input bool   InpS05 = true;     // InpS05 - SELL 25-30% (InpBoxInputs)
input bool   InpS06 = true;     // InpS06 - SELL 30-35% (InpBoxInputs)
input bool   InpS07 = true;     // InpS07 - SELL 35-40% (InpBoxInputs)
input bool   InpS08 = true;     // InpS08 - SELL 40-45% (InpBoxInputs)
input bool   InpS09 = true;     // InpS09 - SELL 45-50% (InpBoxInputs)
input bool   InpS10 = true;     // InpS10 - SELL 50-55% (InpBoxInputs)
input bool   InpS11 = true;     // InpS11 - SELL 55-60% (InpBoxInputs)
input bool   InpS12 = true;     // InpS12 - SELL 60-65% (InpBoxInputs)
input bool   InpS13 = true;     // InpS13 - SELL 65-70% (InpBoxInputs)
input bool   InpS14 = true;     // InpS14 - SELL 70-75% (InpBoxInputs)
input bool   InpS15 = true;     // InpS15 - SELL 75-80% (InpBoxInputs)
input bool   InpS16 = true;     // InpS16 - SELL 80-85% (InpBoxInputs)
input bool   InpS17 = true;     // InpS17 - SELL 85-90% (InpBoxInputs)
input bool   InpS18 = true;     // InpS18 - SELL 90-95% (InpBoxInputs)
input bool   InpS19 = true;     // InpS19 - SELL 95-100% (InpBoxInputs)
input bool   InpS20 = true;     // InpS20 - SELL over 100% (InpBoxInputs)
input int    InpAdaptWeeks  = 0;      // InpAdaptWeeks - v1.32 weekly self-tuning range boxes: every Monday, look back this many weeks of closed trades and switch OFF each box (BUY / SELL apart) that lost money, the rest ON (0 = off: the fixed boxes)
input int    InpAdaptDays   = 0;      // InpAdaptDays - v1.32 the same, rebuilt EVERY DAY from the last N days (Zee: "finetune the range everyday, getting ready for the next day"); 0 = off; overrides InpAdaptWeeks
input bool   InpAdaptToday  = false;  // InpAdaptToday - v1.33 intraday: every day starts with all boxes ON; after EVERY closed trade the boxes are rebuilt from TODAY's trades only (a box losing today goes OFF, the rest stay ON); reset at midnight (Zee: "on each 1 minute candle we optimize the range based on TODAY's data")
input int    InpAdaptMinTrades = 3;   // InpAdaptMinTrades - v1.32: a box needs at least this many trades in the look-back to be judged; fewer = stays ON (a switched-off box gets a fresh chance once its old trades age out)
input int    InpBandPauseBars = 1;   // InpBandPauseBars - after a trade skipped in an unticked range, no new trade for N candles (0 = take the next setup; the chart's "Pause N candles")
input bool   InpWaitEntryBar = true;  // InpWaitEntryBar - no TP1 / trail / lock / CTC inside the entry minute: the chart steps once per minute and starts managing a trade at the NEXT one (the broker stop is live from the first tick)
input bool   InpSlNextBar   = true;   // InpSlNextBar - a stop moved during a minute (TP1, CTC) takes effect at the NEXT minute's open, as on the chart (an open already beyond it closes at market)
input bool   InpTvVerdict   = true;   // InpTvVerdict - with InpBarSource 1, when the two feeds disagree by cents the CHART's candle decides: it broke the level and MT5 did not -> enter at the next open; MT5 broke it and the chart did not -> out at the next open; the chart's candle went through the stop and MT5 did not -> out at the next open (the broker stop stays)
input int    InpClosedRetryMins = 0;  // InpClosedRetryMins - the broker said "market closed" (Blueberry quotes from 01:00 but trades a little later): keep the setup and retry for N minutes (0 = drop it)
input double InpChartSpread = 0.17;     // InpChartSpread - the chart's fixed spread ($ of price, e.g. 0.17): every DECISION that uses the spread uses this one, as the chart does (0 = the live spread). Fills always pay the real spread
input int    InpTpMode      = 2;      // InpTpMode - TP1 method: 0 normal (BUY other-EMA touch, SELL last swing low) · 1 fixed $ · 2 Fibonacci extension of the setup candle · 3 partial (a share at the fixed $, the rest trails)
input double InpTpFixUsdB   = 2.0;    // InpTpFixUsdB - modes 1 / 3: BUY TP1 = the entry + $X
input double InpTpFixUsdS   = 2.0;    // InpTpFixUsdS - modes 1 / 3: SELL TP1 = the entry - $X
input int    InpCoolN       = 0;      // InpCoolN - v1.36 the chart's cool-down: no new trade for N candles after a trade closes, counting the exit candle (0 = off)
input int    InpCoolDir     = 1;      // InpCoolDir - v1.36: 0 blocks both directions · 1 only the same direction as the trade that closed (the chart's default)
input bool   InpCoolWinOnly = false;  // InpCoolWinOnly - v1.36: only after a WINNING exit
input bool   InpReEntry     = false;  // InpReEntry - v1.35 (Zee): a trade closed by its ORIGINAL stop loss arms a re-entry: when price comes back through the original entry price X, take the same setup again (same side, stop rule and TP1 rule) - once per original trade
input int    InpReEntryBars = 60;     // InpReEntryBars - v1.35: the re-entry stays armed this many candles after the stop-out
input double InpTpFixUsd    = 0;      // InpTpFixUsd - v1.34: when > 0, the SAME fixed $ target for BUY and SELL (overrides InpTpFixUsdB / S) - one input the optimizer can sweep
input double InpTpFibPct    = 161.8;  // InpTpFibPct - mode 2: BUY TP1 = setup low + X% of its range, SELL = setup high - X%
input double InpTpPartPct   = 0.8;    // InpTpPartPct - mode 3: close this share at the target (instead of InpPartialPct)
input double InpTpPartTrailUsd = 2.0; // InpTpPartTrailUsd - mode 3: the rest trails $X (instead of InpLongTrailUsd / InpShortTrailUsd)
input bool   InpTpNoFixSkip = false;  // InpTpNoFixSkip - modes 1-3: a target not InpMinTpPips beyond the entry skips the trade (false = the normal TP1)

CTrade   trade;
int      hFast = INVALID_HANDLE, hSlow = INVALID_HANDLE, hAtr = INVALID_HANDLE, hHtf = INVALID_HANDLE;
ENUM_TIMEFRAMES g_htf = PERIOD_CURRENT;
datetime g_lastBar = 0;

// the setup waiting for its break
int      g_pSide = 0;
double   g_pHigh = 0, g_pLow = 0;
// v1.35 re-entry after a stop-out (Zee 2026-10-18: "When the market again crosses our entry price reverting from the stop loss point to our
// original point -> we initiate our original setup at X again")
int      g_reSide = 0, g_reExit = 50;
double   g_reX = 0, g_reHi = 0, g_reLo = 0;
string   g_reDesc = "";
datetime g_reUntil = 0;
bool     g_reTaking = false;
int      g_reArmed = 0, g_reTaken = 0;
// v1.36 the chart's cool-down (Zee 2026-10-18: "can you add the cool down rule to the EA?"): the last exit's candle, side and result
datetime g_lxBar = 0;
int      g_lxSide = 0;
bool     g_lxWin = false;
int      g_coolSkips = 0;
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
                  int num; double slNow; datetime slFrom; string why; int adRun; double lbest; double pendSl; string pendWhy; datetime pendBar; double brk; bool tp1Pend; double tp1Lvl; datetime tp1Bar; double enJ; double chase; double sHi; double sLo; int sExit; bool isRe; };
PosState g_pos[];
double g_chase = -1;   // v1.24: where the last entry sat in the range (%), -1 = not measured - logged per trade for the box optimizer
// v1.32 (Zee 2026-10-18: "calculate a new range every week and from that range execute the next week ... for each week we remove the
// failing ranges and keep the winning ranges"): every closed trade -> (close time, box 0-41, net); every Monday the boxes are rebuilt
datetime g_adT[]; int g_adK[]; double g_adP[];
datetime g_adWeek = 0;
int AdBucket(int side, double chase) { int b = chase > 100 ? 20 : chase <= 0 ? 0 : MathMin((int)MathFloor(chase / 5), 19); return b + (side > 0 ? 0 : 21); }
void AdRecord(int side, double chase, datetime t, double pnl)
{
   if ((InpAdaptWeeks <= 0 && InpAdaptDays <= 0 && !InpAdaptToday) || chase < 0) return;
   int n = ArraySize(g_adT); ArrayResize(g_adT, n + 1); ArrayResize(g_adK, n + 1); ArrayResize(g_adP, n + 1);
   g_adT[n] = t; g_adK[n] = AdBucket(side, chase); g_adP[n] = pnl;
   if (InpAdaptToday) { g_adWeek = 0; AdRebuild(t); }      // v1.33: re-judge at once after each trade
}
void AdRebuild(datetime now)
{
   if (InpAdaptWeeks <= 0 && InpAdaptDays <= 0 && !InpAdaptToday) return;
   MqlDateTime d; TimeToStruct(now, d);
   datetime day0 = now - (now % 86400);
   if (InpAdaptToday) {                                        // v1.33: today's trades only, from midnight (server)
      static datetime lastDay = 0; static int lastN = -1;
      if (day0 == lastDay && ArraySize(g_adT) == lastN) return;
      lastDay = day0; lastN = ArraySize(g_adT);
      double nt[42]; int ct[42]; ArrayInitialize(nt, 0); ArrayInitialize(ct, 0);
      for (int i = ArraySize(g_adT) - 1; i >= 0 && g_adT[i] >= day0; i--) { nt[g_adK[i]] += g_adP[i]; ct[g_adK[i]]++; }
      string bt = "", st = "";
      for (int k = 0; k < 21; k++) { bt += (ct[k] < InpAdaptMinTrades || nt[k] >= 0) ? "1" : "0"; st += (ct[k + 21] < InpAdaptMinTrades || nt[k + 21] >= 0) ? "1" : "0"; }
      g_bandsB = bt; g_bandsS = st;
      return;
   }
   datetime monday = InpAdaptDays > 0 ? day0 : day0 - (datetime)(((d.day_of_week + 6) % 7) * 86400);   // daily: "monday" = today
   if (monday == g_adWeek) return;
   g_adWeek = monday;
   double net[42]; int cnt[42]; ArrayInitialize(net, 0); ArrayInitialize(cnt, 0);
   datetime from = monday - (InpAdaptDays > 0 ? InpAdaptDays : InpAdaptWeeks * 7) * 86400;
   for (int i = 0; i < ArraySize(g_adT); i++) if (g_adT[i] >= from && g_adT[i] < monday) { net[g_adK[i]] += g_adP[i]; cnt[g_adK[i]]++; }
   string b = "", s = ""; int offB = 0, offS = 0;
   for (int k = 0; k < 21; k++) {
      bool onB = cnt[k] < InpAdaptMinTrades || net[k] >= 0, onS = cnt[k + 21] < InpAdaptMinTrades || net[k + 21] >= 0;
      b += onB ? "1" : "0"; s += onS ? "1" : "0"; offB += !onB; offS += !onS;
   }
   g_bandsB = b; g_bandsS = s;
   PrintFormat("[SAAD-1min] week of %s: range boxes from the last %d week(s) - BUY %s (%d off) | SELL %s (%d off)", TimeToString(monday, TIME_DATE), InpAdaptWeeks, b, offB, s, offS);
}
double EnJ(int i) { return InpTvVerdict && g_pos[i].enJ > 0 ? g_pos[i].enJ : g_pos[i].entry; }
datetime g_exitBar = 0;
bool g_late = false;
datetime g_pauseUntil = 0, g_pauseBar = 0; double g_pauseBrk = 0; int g_pauseSide = 0;   // v1.18: the range-skip pause and the break that started it
int g_closedSide = 0;     // v1.16: the last entry was refused with "market closed"
datetime g_retryUntil = 0;
datetime g_cancelBar = 0; // v1.15: the candle in which a trade the chart never had (MT5 broke, the chart's candle did not) was closed      // v1.14: entering at the next open because the chart's candle broke the level (MT5's ticks did not)   // the candle in which the last position closed

int g_ctc = 0, g_skipClose = 0, g_closeLoss = 0;
int g_setups = 0, g_entries = 0, g_skipBreak = 0, g_skipGap = 0, g_skipRisk = 0, g_skipSup = 0, g_chop = 0,
    g_busy = 0, g_rides = 0, g_lockFail = 0, g_dayStop = 0, g_filtered = 0;

double Pip() { return InpPipPts * _Point; }
// v1.20 (13 Oct #82): the chart's entry price (break level + 0.01 + its spread) for every STOP decision - CTC, lock, TP1 floor,
// cut-losers, day close. The real fill can be a few cents worse and flipped "stop never worse than the entry". P&L stays real.
// v1.17: the spread the chart decides with (its fixed setting), else the live one
double ChartSpr() { return InpChartSpread > 0 ? InpChartSpread : SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID); }
// v1.07 TP1 METHOD 3 (partial) brings its own share and trail
double PartPct() { return InpTpMode == 3 ? InpTpPartPct : InpPartialPct; }
double TrailL()  { return InpTpMode == 3 ? InpTpPartTrailUsd : InpLongTrailUsd; }
double TrailS()  { return InpTpMode == 3 ? InpTpPartTrailUsd : InpShortTrailUsd; }
double Buf(int h, int s) { double v[1]; return CopyBuffer(h, 0, s, 1, v) == 1 ? v[0] : 0.0; }
//--- v1.04 (Zee 2026-10-16: "the only way we can succeed is to sync both mt5 with tradingview"): every candle, EMA and ATR
// the strategy judges comes from ONE place. InpBarSource 1 = the TradingView chart's own candles, so the EA sees the
// setups the chart sees; orders, stops and fills stay on the MT5 price. Shift 0 (the forming candle) is always MT5's.
datetime tvT[]; double tvO[], tvH[], tvL[], tvC[], tvEF[], tvES[], tvA[];
bool g_useTv = false;                // v1.23: this candle has chart candles behind it (else MT5's own candles - Zee's 10-month run traded only Oct 12-16)
bool g_tvStale = false;              // live: the chart's candle never came - no setups / candle stops on an old candle
int g_tvN = 0, g_tvEnd = -1;          // g_tvEnd = index of the last CLOSED chart candle (shift 1)
uint g_tvReadMs = 0;
// v1.26 (Zee 2026-10-17: "Run the live EA on the chart's own 15-min candles"): the bridge writes one file per timeframe
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
   ArrayResize(tvEF, MathMax(n, 1)); ArrayResize(tvES, MathMax(n, 1)); ArrayResize(tvA, MathMax(n, 1));
   double af = 2.0 / (InpEmaFast + 1), as = 2.0 / (InpEmaSlow + 1), trs = 0;
   double tr[]; ArrayResize(tr, MathMax(n, 1));
   for (int i = 0; i < n; i++) {
      tvEF[i] = i == 0 ? tvC[0] : tvEF[i - 1] + af * (tvC[i] - tvEF[i - 1]);
      tvES[i] = i == 0 ? tvC[0] : tvES[i - 1] + as * (tvC[i] - tvES[i - 1]);
      tr[i] = i == 0 ? tvH[0] - tvL[0] : MathMax(tvH[i], tvC[i - 1]) - MathMin(tvL[i], tvC[i - 1]);   // ta.tr(true)
      trs += tr[i]; if (i >= 14) trs -= tr[i - 14];
      tvA[i] = trs / MathMin(i + 1, 14);                                                                  // ta.sma(tr, 14) = MT5 iATR
   }
   return n > 0;
}
// v1.26 (Zee 2026-10-17, 15-min mirror): TradingView starts a week's first 15-min candles at the session open (Monday 01:01,
// 01:16, 01:31 ...) while MT5's run 01:00, 01:15 ... - the EA saw each Monday chart candle ~14 minutes late (26 of 192 trades
// differed, nearly all on Mondays). On M5+ with chart candles the EA's "current candle" now opens when the CHART's candle closes.
// M1 keeps MT5's clock (its candles already line up: 333 of 333). No chart candle for too long (bridge stopped) -> MT5's clock.
datetime CurBar()
{
   datetime mt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (InpBarSource != 1 || g_tvN == 0 || PeriodSeconds() <= 60) return mt;
   int P = PeriodSeconds(), warm = MathMin(InpEmaSlow * 2 + 19, g_tvN - 1);
   datetime now = TimeCurrent();
   if (!MQLInfoInteger(MQL_TESTER) && now >= tvT[g_tvN - 1] + 2 * P && GetTickCount() - g_tvReadMs >= 1000) TvLoad();   // live: the next candle is due
   int lo = 0, hi = g_tvN - 1, r = -1;
   while (lo <= hi) { int m = (lo + hi) / 2; if (tvT[m] + P <= now) { r = m; lo = m + 1; } else hi = m - 1; }
   if (r < warm) return mt;
   datetime tb = tvT[r] + P;
   if (MQLInfoInteger(MQL_TESTER) ? now > tvT[g_tvN - 1] + 2 * P : now - tb > P + InpTvWaitSec && mt > tb) return mt;
   return tb;
}
// the last chart candle that closed before the MT5 candle opening at `bar`
void TvSync(datetime bar)
{
   int lo = 0, hi = g_tvN - 1, r = -1;
   while (lo <= hi) { int m = (lo + hi) / 2; if (tvT[m] <= bar - PeriodSeconds()) { r = m; lo = m + 1; } else hi = m - 1; }
   g_tvEnd = r;
}
// live: the chart's candle for the minute that just closed has arrived (or we waited long enough)
bool TvReady(datetime bar)
{
   if (InpBarSource != 1) { g_useTv = false; return true; }
   if (g_tvN == 0 || tvT[g_tvN - 1] < bar - PeriodSeconds()) {
      if (!MQLInfoInteger(MQL_TESTER) && GetTickCount() - g_tvReadMs >= 1000) TvLoad();
   }
   static int lastEnd = -2;
   TvSync(bar);
   // v1.23 (Zee 2026-10-17: "the graph for 10 months keeps going upwards"): before the chart's first candles (+ warm-up), or after the
   // file ends in the tester, the EA uses MT5's own candles instead of standing still - a long test trades every month
   int warm = MathMin(InpEmaSlow * 2 + 19, g_tvN - 1);
   g_useTv = g_tvN > 0 && warm >= 0 && bar - PeriodSeconds() >= tvT[warm] && (!MQLInfoInteger(MQL_TESTER) || bar - PeriodSeconds() <= tvT[g_tvN - 1]);
   if (!g_useTv) { g_tvStale = false; lastEnd = g_tvEnd; return true; }
   g_tvStale = g_tvEnd < 0 || g_tvEnd == lastEnd;          // no new chart candle: the chart takes no step either
   if (g_tvEnd >= 0 && tvT[g_tvEnd] >= bar - PeriodSeconds()) { lastEnd = g_tvEnd; return true; }
   if (MQLInfoInteger(MQL_TESTER)) { lastEnd = g_tvEnd; return true; }   // the file is complete; a missing chart minute stays missing
   if (TimeCurrent() - bar < InpTvWaitSec) return false;
   lastEnd = g_tvEnd;
   if (!g_tvStale) return true;
   static datetime warned = 0;
   if (warned != bar) { warned = bar; PrintFormat("[SAAD-1min] WARNING: no TradingView candle for %s after %d s - is tv_bars_bridge.py running? Setups paused until it is back (last %s)",
                                                  TimeToString(bar - PeriodSeconds()), InpTvWaitSec, g_tvEnd >= 0 ? TimeToString(tvT[g_tvEnd]) : "none"); }
   return true;
}
int    TvI(int s) { int i = g_tvEnd - s + 1; return i >= 0 && i <= g_tvEnd ? i : -1; }
double BOpen(int s)  { if (!g_useTv || s <= 0) return iOpen(_Symbol, PERIOD_CURRENT, s);  int i = TvI(s); return i < 0 ? 0 : tvO[i]; }
double BHigh(int s)  { if (!g_useTv || s <= 0) return iHigh(_Symbol, PERIOD_CURRENT, s);  int i = TvI(s); return i < 0 ? 0 : tvH[i]; }
double BLow(int s)   { if (!g_useTv || s <= 0) return iLow(_Symbol, PERIOD_CURRENT, s);   int i = TvI(s); return i < 0 ? 0 : tvL[i]; }
double BClose(int s) { if (!g_useTv || s <= 0) return iClose(_Symbol, PERIOD_CURRENT, s); int i = TvI(s); return i < 0 ? 0 : tvC[i]; }
datetime BTime(int s){ if (s == 0) return CurBar(); if (!g_useTv || s < 0) return iTime(_Symbol, PERIOD_CURRENT, s);  int i = TvI(s); return i < 0 ? 0 : tvT[i]; }
double Atr(int s)    { if (!g_useTv) return Buf(hAtr, s); int i = TvI(MathMax(s, 1)); return i < 0 ? 0 : tvA[i]; }
double EmaX(int fast, int s)
{
   if (!g_useTv) return Buf(fast ? hFast : hSlow, s);
   int i = TvI(MathMax(s, 1)); if (i < 0) return 0;
   double e = fast ? tvEF[i] : tvES[i];
   if (s > 0) return e;
   double a = 2.0 / ((fast ? InpEmaFast : InpEmaSlow) + 1);              // the forming candle: the chart's emaLive, at the bid
   return e + a * (SymbolInfoDouble(_Symbol, SYMBOL_BID) - e);
}
double Ema(int which, int s) { return EmaX(which == 9 ? 1 : 0, s); }
bool   TrailOn(int side) { return InpTrail && (InpTrailSide == 2 || (side > 0 && InpTrailSide == 0) || (side < 0 && InpTrailSide == 1)); }

int g_hEmas = INVALID_HANDLE;
void EmasShow()   // v1.22: same candles and periods the EA trades on, so the lines are exactly its lines
{
   if (!InpShowEmas || (MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE))) return;
   if (ChartIndicatorGet(0, 0, "SaadEMAs") != INVALID_HANDLE) return;   // already on the chart
   g_hEmas = iCustom(_Symbol, PERIOD_CURRENT, "::Indicators\\SaadEMAs.ex5", PERIOD_CURRENT, InpEmaFast, InpEmaSlow);
   if (g_hEmas == INVALID_HANDLE || !ChartIndicatorAdd(0, 0, g_hEmas)) PrintFormat("[SAAD] could not draw the EMAs (error %d)", GetLastError());
}

string g_bandsB = "", g_bandsS = "";   // v1.24: the 21 BUY / SELL boxes in force (InpBandsB/S, or the 42 InpBxx/InpSxx inputs)
string Boxes(bool a0, bool a1, bool a2, bool a3, bool a4, bool a5, bool a6, bool a7, bool a8, bool a9, bool a10, bool a11, bool a12, bool a13,
             bool a14, bool a15, bool a16, bool a17, bool a18, bool a19, bool a20)
{
   bool b[21] = {a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14, a15, a16, a17, a18, a19, a20};
   string s = "";
   for (int i = 0; i < 21; i++) s += b[i] ? "1" : "0";
   return s;
}

int OnInit()
{
   g_bandsB = InpBoxInputs ? Boxes(InpB00, InpB01, InpB02, InpB03, InpB04, InpB05, InpB06, InpB07, InpB08, InpB09, InpB10, InpB11, InpB12, InpB13, InpB14, InpB15, InpB16, InpB17, InpB18, InpB19, InpB20) : InpBandsB;
   g_bandsS = InpBoxInputs ? Boxes(InpS00, InpS01, InpS02, InpS03, InpS04, InpS05, InpS06, InpS07, InpS08, InpS09, InpS10, InpS11, InpS12, InpS13, InpS14, InpS15, InpS16, InpS17, InpS18, InpS19, InpS20) : InpBandsS;
   EmasShow();
   hFast = iMA(_Symbol, PERIOD_CURRENT, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
   hSlow = iMA(_Symbol, PERIOD_CURRENT, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   hAtr  = iATR(_Symbol, PERIOD_CURRENT, 14);
   if (InpHtfMin > 0) {
      g_htf = InpHtfMin == 5 ? PERIOD_M5 : InpHtfMin == 15 ? PERIOD_M15 : InpHtfMin == 30 ? PERIOD_M30 : InpHtfMin == 60 ? PERIOD_H1 : InpHtfMin == 240 ? PERIOD_H4 : PERIOD_M15;
      hHtf = iMA(_Symbol, g_htf, InpHtfEma, 0, MODE_EMA, PRICE_CLOSE);
      if (hHtf == INVALID_HANDLE) return INIT_FAILED;
   }
   if (hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE || hAtr == INVALID_HANDLE) return INIT_FAILED;
   if (InpBarSource == 1) {
      // v1.30 (Zee 2026-10-18: his Blueberry test stopped at once - the 15-min candle file was missing): no chart candles = MT5's own
      // candles with a warning, instead of refusing to start (live: the bridge's file is read again once it appears)
      if (!TvLoad() || g_tvN == 0)
         PrintFormat("[SAAD-1min] WARNING: no TradingView candles in Common\\Files\\%s - trading on MT5's own candles (start monitor/saad_compare/start_tv_bars_bridge.bat for the chart's)", TvFile());
      else
         PrintFormat("[SAAD-1min] TradingView candles: %d from %s to %s (%s)", g_tvN, TimeToString(tvT[0]), TimeToString(tvT[g_tvN - 1]), TvFile());
   }
   trade.SetExpertMagicNumber(InpMagicNumber);
   if (MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)) trade.LogLevel(LOG_LEVEL_ERRORS);   // v1.12: agent logs were 381-866 MB
   PrintFormat("[SAAD-1min] v1.36 %s | stops level %d pts, freeze %d pts, spread now %d pts | SL %.0f pips, max risk $%.2f, ER %.2f/%d, hours %d-%d, trail %s N%d ride %s, maxPos %d",
               _Symbol, (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL),
               (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD), InpSlPips, InpMaxRiskUsd, InpChopEr, InpChopErLook, InpSessFrom, InpSessTo,
               InpTrail ? "on" : "off", InpTrailN, InpRide ? "on" : "off", InpMaxPos);
   datetime e = SessionEnd(TimeCurrent());
   PrintFormat("[SAAD] day close for %s: %s (no new trades %d min before; losers shut %d min before)", _Symbol,
               e == 0 ? "none found (no daily break)" : TimeToString(e), InpNoNewMins, InpCloseLossMins);
   return INIT_SUCCEEDED;
}

// v1.24 (Zee 2026-10-17: "we can use the MT5's own strategy optimizer to find the best settings"): the optimizer's score
// (OptimizationCriterion 6 = "Custom max"). Profit over the worst equity drawdown, so a setting that makes money by risking the
// account does not win; a losing setting scores its loss (negative, below every winner); too few trades scores lowest of all.
// v1.25 (Zee 2026-10-17: "what we're trying to get is winrate ... as long as each setup results in profit"): score 2 = the win
// rate of whole TRADES (a position's TP1 partial + its rest = one trade; MT5's own STAT_PROFIT_TRADES counts each close)
int g_posN = 0, g_posW = 0;
void PositionStats()
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

// v1.28 (Zee 2026-10-18: "what we want is a set of rules ... robust enough to survive bad months and good months" - June made +$0.6k
// while May made +$27k): score 3 = the WORST month's net (every month from the first to the last of the test, a month without trades
// = 0) + 5% of the total as a tie-break. The optimizer lifts the weakest month instead of the best year.
double WorstMonth()
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
   // v1.31: score 4 = the win rate of whole trades, ALWAYS (also for a losing setting) - the report's Profit column carries the money
   if (InpOptScore == 4) { PositionStats(); return g_posN > 0 ? 100.0 * g_posW / g_posN : 0; }
   if (InpOptScore == 3) {
      if (n < InpOptMinTrades) return -1e9 + n;
      return WorstMonth() + 0.05 * net;
   }
   if (InpOptScore == 2) {
      PositionStats();
      if (g_posN < InpOptMinTrades) return -1e9 + g_posN;
      if (net <= 0) return net / 1000.0 - 100.0;                       // a losing year ranks below every profitable one
      return 100.0 * g_posW / g_posN;
   }
   if (n < InpOptMinTrades) return -1e9 + n;
   if (net <= 0) return net / 1000.0;
   if (InpOptScore == 1) return 100.0 * TesterStatistics(STAT_PROFIT_TRADES) / n;   // Zee: "optimize specifically for the highest win rate"
   return net / MathMax(dd, 1.0);
}

void OnDeinit(const int reason)
{
   if (InpReEntry) PrintFormat("[SAAD] v1.35 re-entries: armed %d, taken %d", g_reArmed, g_reTaken);
   if (InpCoolN > 0) PrintFormat("[SAAD] v1.36 cool-down skips: %d", g_coolSkips);
   if (reason != REASON_CHARTCHANGE && reason != REASON_PARAMETERS) ChartIndicatorDelete(0, 0, "SaadEMAs");
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
void Log(string msg) { if (LogOn()) Print("[SAAD-1min] ", msg); }
string Ts(datetime t) { return t == 0 ? "" : TimeToString(t, TIME_DATE | TIME_SECONDS); }
string Px(double v) { return v == 0 ? "" : DoubleToString(v, _Digits); }
// one row per closed trade: Common\Files\Saad15_trades_<symbol>_<magic>[_tester].csv
void CsvRow(string row)
{
   // v1.24: InpCsvName set -> always write, under that name (6 parallel test copies each need their own file)
   if (InpCsvName == "" && (!InpLogCsv || (MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)))) return;
   string fn = InpCsvName != "" ? InpCsvName : StringFormat("Saad1m_trades_%s_%d%s.csv", _Symbol, InpMagicNumber, MQLInfoInteger(MQL_TESTER) ? "_tester" : "");
   int h = FileOpen(fn, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ);
   if (h == INVALID_HANDLE) { Print("[SAAD-1min] cannot write ", fn, " error ", GetLastError()); return; }
   if (FileSize(h) == 0)
      FileWriteString(h, "num,symbol,side,setup,entry_time,entry,sl_initial,risk_usd,tp1_rule,tp1_time,tp_levels,ctc_time,"
                         "sl_moves,best_price,sl_final,exit_time,exit,exit_reason,profit,commission,swap,net,range_pct\r\n");
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
   if (!(Drawing() || LogOn() || InpLogCsv || InpCsvName != "" || InpAdaptWeeks > 0 || InpAdaptDays > 0 || InpAdaptToday || InpReEntry || InpCoolN > 0) || !HistorySelectByPosition(p.ticket)) return;   // v1.24: InpCsvName writes even with InpLogCsv off; v1.32 the weekly boxes need every result
   double px = 0, pnl = 0, prof = 0, comm = 0, swp = 0; datetime t = 0; long reason = -1;
   for (int k = HistoryDealsTotal() - 1; k >= 0; k--) {
      ulong d = HistoryDealGetTicket(k);
      comm += HistoryDealGetDouble(d, DEAL_COMMISSION);          // entry + exit commission
      if (HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      if (t == 0) {   // v1.04: the LAST closing deal (newest first) - a TP1 partial used to be reported as the exit
         px = HistoryDealGetDouble(d, DEAL_PRICE); t = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
         reason = HistoryDealGetInteger(d, DEAL_REASON);
      }
      prof += HistoryDealGetDouble(d, DEAL_PROFIT); swp += HistoryDealGetDouble(d, DEAL_SWAP);
   }
   if (t == 0) return;
   pnl = prof + comm + swp;
   AdRecord(p.side, p.chase, t, pnl);                      // v1.32
   g_lxBar = CurBar(); g_lxSide = p.side; g_lxWin = pnl > 0;   // v1.36 cool-down: the exit candle (the chart: lxBar := bar_index)
   string why = p.why;
   if (reason == DEAL_REASON_SL)
      why = p.usdTrail ? StringFormat("trailing stop ($%.0f) after TP%d", p.side > 0 ? TrailL() : TrailS(), p.tpStage - 1) : MathAbs(p.slNow - p.entry) < _Point ? "breakeven (CTC)"
          : (p.ride || (p.side > 0 ? p.slNow > p.entry : p.slNow < p.entry)) ? "trailing stop" : "stop loss";
   else if (reason == DEAL_REASON_TP) why = p.side > 0 ? "TP (last resistance)" : "TP (last support)";
   else if (why == "") why = "closed";
   // v1.35: the ORIGINAL stop took it (not breakeven, not a trail) and it was not itself a re-entry -> arm the re-entry at its entry price
   if (InpReEntry && why == "stop loss" && !p.isRe) {
      g_reSide = p.side; g_reX = p.entry; g_reHi = p.sHi; g_reLo = p.sLo; g_reExit = p.sExit; g_reDesc = p.setup;
      g_reUntil = t + InpReEntryBars * PeriodSeconds(); g_reArmed++;
      Log(StringFormat("#%d stopped out - re-entry armed: %s again if price comes back through %s within %d candles", p.num, p.side > 0 ? "BUY" : "SELL", Px(g_reX), InpReEntryBars));
   }
   Log(StringFormat("EXIT #%d %s %s @ %s | entry %s | %s | best %s | SL moves %d | net %s%.2f (profit %.2f, commission %.2f, swap %.2f)",
                    p.num, p.side > 0 ? "BUY" : "SELL", Ts(t), Px(px), Px(p.entry), why, Px(p.mfe), p.moves,
                    pnl >= 0 ? "+" : "-", MathAbs(pnl), prof, comm, swp));
   string setupCsv = p.setup; StringReplace(setupCsv, ",", ";");
   string tp1Csv = p.tp1; StringReplace(tp1Csv, ",", ";");
   CsvRow(StringFormat("%d,%s,%s,%s,%s,%s,%s,%.2f,%s,%s,%s,%s,%d,%s,%s,%s,%s,%s,%.2f,%.2f,%.2f,%.2f,%.1f",
                       p.num, _Symbol, p.side > 0 ? "BUY" : "SELL", setupCsv, Ts(p.entryTime), Px(p.entry), Px(p.sl0), p.risk,
                       tp1Csv, Ts(p.tp1At), p.tps, Ts(p.ctcAt), p.moves, Px(p.mfe), Px(p.slNow), Ts(t), Px(px), why,
                       prof, comm, swp, pnl, p.chase));
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
         g_exitBar = CurBar();
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
      p.num = ++g_num; p.slNow = PositionGetDouble(POSITION_SL); p.slFrom = p.entryTime; p.why = ""; p.usdTrail = false; p.tpNext = 0; p.tpStage = 1; p.resTp1 = false; p.setup = ""; p.sl0 = p.slNow; p.risk = 0; p.tp1 = ""; p.tp1At = 0; p.tps = ""; p.ctcAt = 0; p.moves = 0; p.mfe = 0; p.adRun = 0; p.lbest = p.entry; p.pendSl = 0; p.pendWhy = ""; p.pendBar = 0; p.brk = 0; p.tp1Pend = false; p.tp1Lvl = 0; p.tp1Bar = 0; p.enJ = 0;
      int n = ArraySize(g_pos); ArrayResize(g_pos, n + 1); g_pos[n] = p;
   }
}

// v1.12 (Zee 2026-10-17 "we want all trades to match"): the chart moves a stop inside a minute but it only counts from the NEXT
// minute (11 Oct #3: TP1 moved the stop to the entry at 02:39, MT5's broker stop was hit 7 s later, the chart's at 02:40 open).
bool QueueSl(int i, double lvl, string why)
{
   if (!InpSlNextBar) { if (!ModifySl(g_pos[i].ticket, lvl)) return false; SlMoved(i, lvl, why); return true; }
   int sd = g_pos[i].side;
   if (g_pos[i].pendSl != 0 && (sd > 0 ? lvl <= g_pos[i].pendSl + _Point : lvl >= g_pos[i].pendSl - _Point)) return false;   // already queued
   g_pos[i].pendSl = NormalizeDouble(lvl, _Digits); g_pos[i].pendWhy = why; g_pos[i].pendBar = CurBar();
   return true;
}
// v1.14 (Zee 2026-10-17 "we want all trades to match, no questions"): the chart's candle that just closed decides when the two
// feeds disagree by cents (chart #63 12 Oct: its 20:57 candle touched the trail, MT5's ticks stayed above - MT5 held overnight)
void TvVerdict()
{
   datetime t1 = BTime(1);
   if (t1 <= 0) return;
   // v1.18 (13 Oct 14:28 UTC: the chart's high was exactly the level, MT5 went a cent above): a range skip -> pause that came from an
   // MT5 break the chart's candle never made did not happen on the chart - cancel the pause
   if (g_pauseUntil > 0 && g_pauseBar == t1 && !(g_pauseSide > 0 ? BHigh(1) > g_pauseBrk : BLow(1) < g_pauseBrk)) { g_pauseUntil = 0; Log("pause cancelled: the chart's candle never broke"); }
   double spr = ChartSpr();
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (!PositionSelectByTicket(g_pos[i].ticket)) continue;
      int sd = g_pos[i].side; double sl = PositionGetDouble(POSITION_SL);
      // entered in that candle on an MT5 break the chart's candle never made: the chart has no trade
      if (g_pos[i].brk != 0 && g_pos[i].entryTime >= t1 && g_pos[i].entryTime < t1 + PeriodSeconds() &&
          !(sd > 0 ? BHigh(1) > g_pos[i].brk : BLow(1) < g_pos[i].brk)) {
         g_pos[i].why = "the chart's candle never broke the level"; trade.PositionClose(g_pos[i].ticket); g_cancelBar = CurBar(); continue;
      }
      // the chart's candle went through the stop that was in force during it (the chart checks from the minute after the entry)
      if (g_pos[i].entryTime < t1 && sl > 0 && (sd > 0 ? BLow(1) <= sl : BHigh(1) + spr >= sl)) {
         // v1.22 (16 Oct 20:21): the chart closed DURING that candle, so it was free at its close - not "busy", and it may enter now
         g_pos[i].why = StringFormat("stop %.2f hit on the chart's candle", sl); trade.PositionClose(g_pos[i].ticket); g_cancelBar = CurBar(); continue;
      }
      // v1.21 (16 Oct #265 / #305): the chart's candle reached a fixed TP1 that MT5's bid missed by cents - the chart banked TP1 and
      // trailed (+$456 / +$56), MT5 waited and was stopped (-$1,088 / -$1,138). TP1 now, the stop from that candle (ApplyPendingSl)
      if (!g_pos[i].ride && g_pos[i].entryTime < t1 && g_pos[i].tp > 0 && (sd < 0 || g_pos[i].resTp1) && (sd > 0 ? BHigh(1) >= g_pos[i].tp : BLow(1) <= g_pos[i].tp)) {
         Log(StringFormat("#%d TP1 %.2f reached on the chart's candle (MT5's ticks did not) - TP1 at this open", g_pos[i].num, g_pos[i].tp));
         double bNow = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         if (sd > 0) LongTouched(i, bNow); else ShortTouched(i, bNow);
         g_pos[i].tp1Bar = t1;   // its stop is judged on that candle, at this same open
      }
   }
}

// at the new minute's open: the queued stop, or out at market if the open is already beyond it (the chart exits at the open)
void ApplyPendingSl()
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   // v1.19 (14 Oct #129): the stop after TP1 is set from the chart's WHOLE TP1 candle, in the chart's order - CTC (if that candle went
   // far enough), then the TP1 stop from the touch price ($ trail), then never worse than the entry. Tick by tick the EA had missed the
   // CTC (the bid touched TP1 before the ask went far enough) and trailed $2 from the ask instead of sitting at the entry.
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (!g_pos[i].tp1Pend || CurBar() <= g_pos[i].tp1Bar || !PositionSelectByTicket(g_pos[i].ticket)) continue;
      g_pos[i].tp1Pend = false;
      int sd = g_pos[i].side; double en = EnJ(i), lv = g_pos[i].tp1Lvl, cur = PositionGetDouble(POSITION_SL), spr = ChartSpr();
      double base = cur, nsl;
      double dist = sd > 0 ? lv - en : en - lv;
      bool atEntry = sd > 0 ? cur >= en : (cur > 0 && cur <= en);
      if (InpBeTpPct > 0 && g_pos[i].ctcAt == 0 && dist > 0 && !atEntry && (sd > 0 ? BHigh(1) - en : en - (BLow(1) + spr)) >= InpBeTpPct * dist) { base = en; g_ctc++; g_pos[i].ctcAt = TimeCurrent(); }
      if (sd > 0) {
         double px = MathMax(lv, BOpen(1));
         nsl = MathMax(base, px - TrailL());
         if (InpTp1Be && en < px) nsl = MathMax(nsl, en);
      } else {
         double ak = MathMin(lv, BOpen(1)) + spr;
         nsl = cur > 0 ? MathMin(base, ak + TrailS()) : ak + TrailS();
         if (InpTp1Be && en > ak) nsl = MathMin(nsl, en);
      }
      nsl = NormalizeDouble(nsl, _Digits);
      if (MathAbs(nsl - cur) < _Point) continue;
      if (sd > 0 ? nsl >= bid : nsl <= ask) { g_pos[i].why = StringFormat("stop %.2f already passed at the open", nsl); trade.PositionClose(g_pos[i].ticket); continue; }
      if (ModifySl(g_pos[i].ticket, nsl)) SlMoved(i, nsl, "TP1 (chart's candle)");
   }
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (g_pos[i].pendSl == 0 || CurBar() <= g_pos[i].pendBar || !PositionSelectByTicket(g_pos[i].ticket)) continue;   // not in the minute it was queued
      double lvl = g_pos[i].pendSl, cur = PositionGetDouble(POSITION_SL); int sd = g_pos[i].side;
      string why = g_pos[i].pendWhy;
      g_pos[i].pendSl = 0; g_pos[i].pendWhy = "";
      if (!(sd > 0 ? lvl > cur + _Point : (cur == 0 || lvl < cur - _Point))) continue;
      if (sd > 0 ? lvl >= bid : lvl <= ask) { g_pos[i].why = StringFormat("stop %.2f already passed at the open", lvl); trade.PositionClose(g_pos[i].ticket); continue; }
      if (ModifySl(g_pos[i].ticket, lvl)) SlMoved(i, lvl, why);
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
   if (PartPct() <= 0 || !PositionSelectByTicket(g_pos[i].ticket)) return;
   // v1.08 (Zee 2026-10-16): share 1 = close EVERYTHING at TP1 (before, the remainder check refused it and nothing closed)
   if (PartPct() >= 1.0 - 1e-9) { g_pos[i].why = "TP1 - all closed"; trade.PositionClose(g_pos[i].ticket); return; }
   double vol = PositionGetDouble(POSITION_VOLUME), step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double part = MathFloor(vol * PartPct() / step) * step;
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
   double sl = NormalizeDouble(MathMax(cur, bid - TrailL()), _Digits);
   if (InpTp1Be && g_pos[i].entry < bid) sl = NormalizeDouble(MathMax(sl, g_pos[i].entry), _Digits);
   if (InpTvVerdict && g_useTv && InpSlNextBar) { g_pos[i].tp1Pend = true; g_pos[i].tp1Lvl = g_pos[i].resTp1 ? g_pos[i].tp : bid; g_pos[i].tp1Bar = CurBar(); sl = cur; }   // v1.19: decided on the chart's TP1 candle
   double res = InpLongResTp ? LastResistance(bid + InpMinTpPips * Pip()) : 0;
   double lvl = MathMax((double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL)) * _Point;
   if (sl >= bid - lvl) sl = cur;
   if (sl != cur) QueueSl(i, sl, "");
   g_pos[i].tpNext = res; g_pos[i].tpStage = 2; g_pos[i].tp1At = TimeCurrent();
   g_pos[i].tps = res > 0 ? "TP2 " + Px(res) : "TP2 none";
   Log(StringFormat("#%d TP1: %s @ %s (entry %s, +$%.2f) | SL -> %s ($%.2f trail) | TP2 %s",
                    g_pos[i].num, g_pos[i].resTp1 ? "resistance " + Px(g_pos[i].tp) + " reached" : StringFormat("%d EMA touched", g_pos[i].exitE), Px(bid), Px(g_pos[i].entry), bid - g_pos[i].entry, Px(sl), TrailL(),
                    res > 0 ? Px(res) + " (last resistance)" : "none above"));
   string note = StringFormat("TP1: %s -> trail $%.2f below%s", g_pos[i].resTp1 ? "resistance reached" : StringFormat("%d EMA touched", g_pos[i].exitE), TrailL(),
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
   double sl = NormalizeDouble(cur > 0 ? MathMin(cur, ask + TrailS()) : ask + TrailS(), _Digits);
   if (InpTp1Be && g_pos[i].entry > ask) sl = NormalizeDouble(MathMin(sl, g_pos[i].entry), _Digits);
   if (InpTvVerdict && g_useTv && InpSlNextBar) { g_pos[i].tp1Pend = true; g_pos[i].tp1Lvl = g_pos[i].tp; g_pos[i].tp1Bar = CurBar(); sl = cur; }   // v1.19: decided on the chart's TP1 candle
   double lvl = MathMax((double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL)) * _Point;
   if (sl <= ask + lvl) sl = cur;
   if (sl != cur) QueueSl(i, sl, "");
   double sup = LastSupport(bid - InpMinTpPips * Pip());
   g_pos[i].tpNext = sup; g_pos[i].tpStage = 2; g_pos[i].tp1At = TimeCurrent();
   g_pos[i].tps = sup > 0 ? "TP2 " + Px(sup) : "TP2 none";
   Log(StringFormat("#%d TP1: support reached @ %s (entry %s, +$%.2f) | SL -> %s ($%.2f trail) | TP2 %s",
                    g_pos[i].num, Px(bid), Px(g_pos[i].entry), g_pos[i].entry - bid, Px(sl), TrailS(),
                    sup > 0 ? Px(sup) + " (next support)" : "none below"));
   string note = StringFormat("TP1: support reached -> trail $%.2f above%s", TrailS(),
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
      g_pos[i].mfe = g_pos[i].side > 0 ? MathMax(g_pos[i].mfe, bid) : (g_pos[i].mfe == 0 ? ask0 : MathMin(g_pos[i].mfe, ask0));
      // v1.11 (Zee 2026-10-17 "we want all trades to match"): chart #3 SELL 11 Oct 23:38 UTC - the EA took TP1 9 s after the entry and was
      // out a minute before the chart, which then saw a different setup; every later trade shifted. The chart never acts in the entry minute.
      if (InpWaitEntryBar && g_pos[i].entryTime >= CurBar()) continue;
      if (InpLockAtUsd > 0 && InpLockMode == 0 && PositionSelectByTicket(g_pos[i].ticket)) {
         double moved = g_pos[i].side > 0 ? bid - g_pos[i].entry : g_pos[i].entry - ask0;
         double want = g_pos[i].entry + g_pos[i].side * InpLockUsd, cur = PositionGetDouble(POSITION_SL);
         if (moved >= InpLockAtUsd && (g_pos[i].side > 0 ? want > cur + _Point : (cur == 0 || want < cur - _Point)) && ModifySl(g_pos[i].ticket, want)) SlMoved(i, want, "lock");
      }
      if (InpMaxBars > 0 && TimeCurrent() - g_pos[i].entryTime >= InpMaxBars * PeriodSeconds()) { g_pos[i].why = "time exit"; trade.PositionClose(g_pos[i].ticket); continue; }
      if (InpBeTpPct > 0 && !g_pos[i].ride && PositionSelectByTicket(g_pos[i].ticket)) {
         // the TP this trade is heading for: the support (SHORT), the exit EMA now (LONG), or a fixed TP
         double tpRef = g_pos[i].side < 0 || InpFixTpPips > 0 ? g_pos[i].tp
                      : (g_pos[i].noTp ? 0 : g_pos[i].resTp1 ? g_pos[i].tp : Ema(g_pos[i].exitE, 0) - InpLongTpPips * Pip());
         double dist = g_pos[i].side > 0 ? tpRef - EnJ(i) : EnJ(i) - tpRef;
         double cur = PositionGetDouble(POSITION_SL);
         bool atEntry = g_pos[i].side > 0 ? cur >= EnJ(i) : (cur > 0 && cur <= EnJ(i));
         if (tpRef > 0 && dist > 0 && !atEntry) {
            double moved = g_pos[i].side > 0 ? bid - EnJ(i) : EnJ(i) - (InpTvVerdict ? bid + ChartSpr() : ask0);
            if (moved >= InpBeTpPct * dist && QueueSl(i, EnJ(i), StringFormat("CTC: %d%% of TP -> SL to entry", (int)MathRound(InpBeTpPct * 100)))) {
               g_ctc++; g_pos[i].ctcAt = TimeCurrent();
            }
         }
      }
      if (InpFixTpPips > 0) continue;
      if (g_pos[i].usdTrail && PositionSelectByTicket(g_pos[i].ticket)) {
         // after TP1: the stop follows the market $X away, never back
         int sd = g_pos[i].side;
         double dist = (sd > 0 ? TrailL() : TrailS()) + InpTrailStepUsd * MathMax(0, g_pos[i].tpStage - 2);
         double want = NormalizeDouble(sd > 0 ? bid - dist : ask0 + dist, _Digits), cur = PositionGetDouble(POSITION_SL);
         if (InpUsdTrailMode == 0 && (sd > 0 ? want >= cur + 10 * _Point : (cur == 0 || want <= cur - 10 * _Point)) && ModifySl(g_pos[i].ticket, want)) {
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
         // v1.17: a fixed-price TP1 (resistance / TP1 method) fires at its price even when the real fill was a cent above it
         // (13 Oct #83: TP1 4186.41, fill 4186.42 - it never fired and the trade rode 6 h to its stop, -$1,146; the chart took TP1)
         if ((g_pos[i].resTp1 || tgt > EnJ(i)) && bid >= tgt) { LongTouched(i, bid); continue; }
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
      // InpCutRunN: N candles in a row closing against a trade that is in loss at the close -> out now (the next open)
      if (InpCutRunN > 0 && g_pos[i].entryTime < t1) {
         double o1 = BOpen(1), spr = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
         bool against = side > 0 ? c1 < o1 : c1 > o1;
         g_pos[i].adRun = against ? g_pos[i].adRun + 1 : 0;
         bool loss = side > 0 ? c1 < EnJ(i) : c1 + (InpTvVerdict ? ChartSpr() : spr) > EnJ(i);
         if (loss && g_pos[i].adRun >= InpCutRunN) { g_pos[i].why = StringFormat("%d candles against the trade", g_pos[i].adRun); trade.PositionClose(t); continue; }
      }
      // v1.03 InpLockMode 1 (Zee 2026-10-16, chart vs MT5 #76/#37/#33): the chart sets the lock once per candle and only
      // when the whole candle stayed past it; the tick-by-tick lock was hit by the next small dip. Same rule here.
      if (InpLockAtUsd > 0 && InpLockMode == 1 && g_pos[i].entryTime < t1) {
         double spr2 = ChartSpr();
         g_pos[i].lbest = side > 0 ? MathMax(g_pos[i].lbest, h1) : MathMin(g_pos[i].lbest, l1 + spr2);
         double pr = side > 0 ? g_pos[i].lbest - EnJ(i) : EnJ(i) - g_pos[i].lbest;
         double want = NormalizeDouble(EnJ(i) + side * InpLockUsd, _Digits);
         bool ok = side > 0 ? (want > sl + 0.01 && want < l1) : ((sl == 0 || want < sl - 0.01) && want > h1 + spr2);
         if (pr >= InpLockAtUsd && ok) {
            double bNow = SymbolInfoDouble(_Symbol, SYMBOL_BID), aNow = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            if (side > 0 ? want >= bNow : want <= aNow) { g_pos[i].why = StringFormat("lock %.2f already passed at the open", want); trade.PositionClose(t); continue; }
            if (ModifySl(t, want)) { SlMoved(i, want, "lock"); sl = want; }
         }
      }
      // v1.04 (chart vs MT5 #37 -> #38): the chart moves the $ trail after TP1 once per candle, from that candle's extreme;
      // tick by tick the EA was taken out 2 minutes earlier and the next trade started at another candle.
      if (g_pos[i].usdTrail && InpUsdTrailMode == 1 && g_pos[i].entryTime < t1 && g_pos[i].tp1At < t1) {   // not from the TP1 candle itself (chart)
         double dist = (side > 0 ? TrailL() : TrailS()) + InpTrailStepUsd * MathMax(0, g_pos[i].tpStage - 2);
         double spr3 = ChartSpr();
         double want = NormalizeDouble(side > 0 ? h1 - dist : l1 + spr3 + dist, _Digits);
         if (side > 0 ? want >= sl + 0.10 - 1e-9 : (sl == 0 || want <= sl - 0.10 + 1e-9)) {
            double bNow = SymbolInfoDouble(_Symbol, SYMBOL_BID), aNow = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            if (side > 0 ? want >= bNow : want <= aNow) { g_pos[i].why = StringFormat("trailing stop %.2f already passed at the open", want); trade.PositionClose(t); continue; }
            if (ModifySl(t, want)) { g_pos[i].slNow = want; g_pos[i].moves++; sl = want; }
         }
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
            // InpTrailGapUsd: an accepted ATR level is pulled back to at least $X from the close (a 0.1 x ATR stop sat ON the close)
            if (better && InpTrailMode == 2 && InpTrailGapUsd > 0) {
               lvl = side > 0 ? MathMin(lvl, c1 - InpTrailGapUsd) : MathMax(lvl, c1 + InpTrailGapUsd);
               better = side > 0 ? lvl > sl + _Point : (sl == 0 || lvl < sl - _Point);
            }
            // v1.01 (Zee 2026-10-16, TV #22 vs MT5): the new trail level is already beyond the price at this open, so the
            // broker refuses the stop and the trade used to ride on to the old stop. The trail says "out": close at market.
            if (better) {
               double bNow = SymbolInfoDouble(_Symbol, SYMBOL_BID), aNow = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
               if (side > 0 ? lvl >= bNow : lvl <= aNow) { g_pos[i].why = StringFormat("trailing stop %.2f already passed at the open", lvl); trade.PositionClose(t); continue; }
               if (ModifySl(t, lvl)) { SlMoved(i, lvl, StringFormat("trail %.2f", lvl)); sl = lvl; }
            }
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
   if (g_pSide == 0 || ArraySize(g_pos) >= InpMaxPos) return;
   // v1.04 (chart vs MT5 #38): the chart steps minute by minute and never opens a trade in the minute it closed one
   if (InpNoEntryExitBar && g_exitBar == CurBar() && g_cancelBar != g_exitBar) return;
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
   bool hit = g_late || (side > 0 ? (InpTrigBid ? bid : ask) > g_pHigh + InpBreakPips * pip : bid < g_pLow - InpBreakPips * pip);
   if (!hit) return;
   if (InpMaxSpreadPts > 0 && (ask - bid) / _Point > InpMaxSpreadPts) return;    // wait for a normal spread
   g_pSide = 0;
   if (InpEntryMode == 1) {
      // the break happened: now wait for the dip back into the setup candle
      g_aSide = side; g_aHigh = g_pHigh; g_aLow = g_pLow; g_aExit = g_pExit; g_aLeft = InpRetestBars;
      g_aLevel = side > 0 ? g_pHigh - InpRetestFrac * (g_pHigh - g_pLow) : g_pLow + InpRetestFrac * (g_pHigh - g_pLow);
      Log(StringFormat("BREAK %s -> waiting %d candle(s) for a dip to %s", side > 0 ? "up" : "down", InpRetestBars, Px(g_aLevel)));
      return;
   }
   // InpRangeMin/Max: where this entry sits in the last InpRangeLook closed candles (BUY 0 = bottom .. 100 = top; SELL mirrored)
   int    bLook = side > 0 ? InpRangeLook : InpRangeLookS;
   double bMin = side > 0 ? InpRangeMin : InpRangeMinS, bMax = side > 0 ? InpRangeMax : InpRangeMaxS;
   string bands = side > 0 ? g_bandsB : g_bandsS;
   // v1.10 (Zee 2026-10-17, "the stand aside is just a form of a cooldown"): pausing after a trade skipped in an unticked range
   // v1.36: the chart's cool-down - it checks this before the range pause (the indicator's order)
   if (InpCoolN > 0 && g_lxBar > 0 && (BTime(0) - g_lxBar) / PeriodSeconds() <= InpCoolN && (InpCoolDir == 0 || side == g_lxSide) && (!InpCoolWinOnly || g_lxWin)) {
      g_coolSkips++;
      DSkip(side, StringFormat("cool-down: %d candle(s) after the last %s closed%s", (int)((BTime(0) - g_lxBar) / PeriodSeconds()), g_lxSide > 0 ? "BUY" : "SELL", g_lxWin ? " in profit" : ""));
      return;
   }
   if (InpBandPauseBars > 0 && BTime(0) <= g_pauseUntil) { DSkip(side, StringFormat("pausing %d candles after a trade skipped in an unticked range", InpBandPauseBars)); return; }
   g_chase = -1;
   if (bMin > 0 || bMax > 0 || StringFind(bands, "0") >= 0 || InpAdaptWeeks > 0 || InpAdaptDays > 0 || InpAdaptToday) {
      double hi = 0, lo = DBL_MAX;
      int sh = g_late ? 1 : 0;
      for (int k = 1; k <= bLook; k++) { hi = MathMax(hi, BHigh(k + sh)); lo = MathMin(lo, BLow(k + sh)); }
      // v1.03 (chart vs MT5 #16 #22 #32 #40 #56 #61 #62 #73 #75 #78): the chart judges the band at the break level, the EA judged
      // it at the tick that fired, a few cents further - 50% became 51-52% and the trade was skipped.
      double lvl = side > 0 ? g_pHigh + InpBreakPips * pip : g_pLow - InpBreakPips * pip, o0 = g_late ? BOpen(1) : BOpen(0);
      double px = !InpBandAtLevel ? bid : side > 0 ? MathMax(lvl + 0.01, o0) : MathMin(lvl - 0.01, o0);
      double chase = hi > lo ? (side > 0 ? (px - lo) / (hi - lo) : (hi - px) / (hi - lo)) * 100 : 50;
      g_chase = chase;
      if ((bMin > 0 && chase < bMin - 1e-6) || (bMax > 0 && chase > bMax + 1e-6)) {     // v1.04 #32: 50.000000000008% is 50%
         DSkip(side, StringFormat("entry at %.0f%% of the last %d candles' range (band %.0f-%.0f%%)", chase, bLook, bMin, bMax));
         return;
      }
      // v1.05 (Zee 2026-10-16): 21 tick-boxes on the chart, 5% each - the same buckets as the indicator's rpBucket()
      int bk = chase > 100 ? 20 : chase <= 0 ? 0 : MathMin((int)MathFloor(chase / 5), 19);
      if (StringLen(bands) > bk && StringGetCharacter(bands, bk) == '0') {
         DSkip(side, StringFormat("entry at %.0f%% of the last %d candles' range: the %s range is unticked", chase, bLook,
                                  bk == 20 ? "over 100%" : StringFormat("%d-%d%%", bk * 5, bk * 5 + 5)));
         if (InpBandPauseBars > 0) {
            g_pauseBar = g_late ? BTime(1) : BTime(0);                 // the chart counts from its break candle
            g_pauseUntil = g_pauseBar + InpBandPauseBars * PeriodSeconds();
            g_pauseBrk = side > 0 ? g_pHigh + InpBreakPips * pip : g_pLow - InpBreakPips * pip; g_pauseSide = side;
         }
         return;
      }
   }
   DoEntry(side, StopFor(side, side > 0 ? ask : bid, g_pHigh, g_pLow));
   // v1.16 (chart #64 / #126, 22:00 UTC = the daily open): the chart bought at the first minute, the broker refused ("market closed")
   // - keep the setup and try again on the next ticks until the market opens
   if (g_closedSide != 0 && InpClosedRetryMins > 0) {
      g_pSide = g_closedSide; g_closedSide = 0;
      if (g_retryUntil == 0) { g_retryUntil = TimeCurrent() + InpClosedRetryMins * 60; Log("market closed - retrying the entry until the broker opens"); }
      if (TimeCurrent() > g_retryUntil) { g_pSide = 0; g_retryUntil = 0; }
   }
   g_closedSide = 0;
}

// mode 1: the dip after the break
void TryDip()
{
   if (g_aSide == 0 || ArraySize(g_pos) >= InpMaxPos) return;
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
   if (InpSlMode == 1) { double a = Atr(1) * InpSlAtrMult; return side > 0 ? en - a : en + a; }
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

void DoEntry(int side, double sl)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double pip = Pip();
   double en = side > 0 ? ask : bid;
   // v1.13 (Zee 2026-10-17, chart #16 11 Oct 02:38): every entry DECISION is judged at the chart's price - the break level + 0.01
   // (or the candle open past it), + the spread for a BUY - not at the fill a few cents further. The chart took a Fibonacci TP1
   // $0.15 away from 4208.02; MT5 filled at 4208.15, found it $0.02 away and fell back to "no TP1". The fill itself stays real.
   double bidJ = bid, enJ = en;
   if (InpBandAtLevel && InpEntryMode == 0) {
      double lvl = side > 0 ? g_pHigh + InpBreakPips * pip : g_pLow - InpBreakPips * pip, o0 = g_late ? BOpen(1) : BOpen(0);
      bidJ = side > 0 ? MathMax(lvl + 0.01, o0) : MathMin(lvl - 0.01, o0);
      enJ = side > 0 ? bidJ + ChartSpr() : bidJ;
   }
   if (InpMaxRiskUsd > 0 && MathAbs(enJ - sl) > InpMaxRiskUsd) { g_skipRisk++; DSkip(side, StringFormat("stop too far ($%.2f > $%.2f)", MathAbs(enJ - sl), InpMaxRiskUsd)); return; }
   double tp = 0;
   bool noTp = false, resTp1 = false;
   // v1.07 TP1 METHOD (Zee 2026-10-16, the chart's EXIT LAB): a fixed $ or Fibonacci TP1 replaces the normal one
   double fix = 0;
   if (InpTpMode == 1 || InpTpMode == 3) fix = enJ + side * (InpTpFixUsd > 0 ? InpTpFixUsd : side > 0 ? InpTpFixUsdB : InpTpFixUsdS);
   else if (InpTpMode == 2) fix = side > 0 ? g_pLow + InpTpFibPct / 100.0 * (g_pHigh - g_pLow) : g_pHigh - InpTpFibPct / 100.0 * (g_pHigh - g_pLow);
   if (fix != 0 && (fix - enJ) * side < InpMinTpPips * pip) {          // not far enough beyond the entry: the normal TP1, or skip (v1.09)
      if (InpTpNoFixSkip) { DSkip(side, "the TP1-method target is not far enough beyond the entry"); return; }
      fix = 0;
   }
   if (side < 0 && fix != 0) tp = fix;
   else if (side > 0 && fix != 0) { tp = fix; resTp1 = true; }        // a fixed-price LONG TP1: the resistance-TP1 path
   else if (side < 0) {
      double sup = LastSupport(bidJ - InpMinTpPips * pip);
      if (sup <= 0) { g_skipSup++; DSkip(side, "no support below to target"); return; }
      tp = sup + InpShortTpPips * pip;
      if (InpMaxTpPips > 0 && bidJ - tp > InpMaxTpPips * pip) { g_skipSup++; DSkip(side, "support too far"); return; }
   } else {
      double eJ = Ema(g_pExit, g_late ? 2 : 1); eJ = eJ + 2.0 / ((g_pExit == 9 ? InpEmaFast : InpEmaSlow) + 1) * (bidJ - eJ);   // the chart's emaLive at its bid
      noTp = (InpBandAtLevel ? eJ : Ema(g_pExit, 0)) - InpLongTpPips * pip < enJ + InpMinTpPips * pip;
      if (noTp && InpLongResTp1 && InpLongTouch == 1) {
         double res = LastResistance(en + InpMinTpPips * pip);
         if (res > 0) { tp = res; noTp = false; resTp1 = true; }
      }
   }
   bool rideShort = side < 0 && TrailOn(-1) && InpRide && InpFixTpPips <= 0;
   if (InpFixTpPips > 0) { tp = side > 0 ? en + InpFixTpPips * pip : en - InpFixTpPips * pip; noTp = false; }
   double lots = LotsFor(side, en, sl);
   if (lots <= 0) { DSkip(side, "even the minimum lot risks too much of this account"); return; }
   bool ok = side > 0 ? trade.Buy(lots, _Symbol, 0, NormalizeDouble(sl, _Digits), InpFixTpPips > 0 ? NormalizeDouble(tp, _Digits) : 0, EA_COMMENT + " BUY")
                      : trade.Sell(lots, _Symbol, 0, NormalizeDouble(sl, _Digits), rideShort ? 0 : NormalizeDouble(tp, _Digits), EA_COMMENT + " SELL");
   if (!ok) { if (trade.ResultRetcode() == TRADE_RETCODE_MARKET_CLOSED) g_closedSide = side; return; }
   g_retryUntil = 0;
   ulong t = trade.ResultOrder();
   ulong deal = trade.ResultDeal();
   if (deal > 0 && HistoryDealSelect(deal)) t = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
   PosState p;
   p.enJ = enJ;
   // a late entry was already confirmed by the chart's break candle: no "never broke" check on the candle it entered in
   p.brk = InpEntryMode == 0 && !g_late ? (side > 0 ? g_pHigh + InpBreakPips * pip : g_pLow - InpBreakPips * pip) : 0;
   p.ticket = t; p.side = side; p.entry = trade.ResultPrice() > 0 ? trade.ResultPrice() : en; p.tp = tp;
   p.exitE = g_pExit; p.noTp = noTp; p.resTp1 = resTp1; p.ride = side > 0 && (noTp || (resTp1 && InpResTp1Ride && fix == 0)) && TrailOn(1) && InpFixTpPips <= 0;
   p.entryTime = TimeCurrent(); p.best = p.entry;
   p.num = ++g_num; p.slNow = NormalizeDouble(sl, _Digits); p.slFrom = p.entryTime; p.why = ""; p.usdTrail = false; p.tpNext = 0; p.tpStage = 1; p.setup = ""; p.sl0 = p.slNow; p.risk = 0; p.tp1 = ""; p.tp1At = 0; p.tps = ""; p.ctcAt = 0; p.moves = 0; p.mfe = 0; p.adRun = 0; p.lbest = p.entry; p.pendSl = 0; p.pendWhy = ""; p.pendBar = 0; p.tp1Pend = false; p.tp1Lvl = 0; p.tp1Bar = 0;   // brk / enJ were set above (v1.20 fix: this line used to wipe them)
   p.setup = g_pDesc; p.sl0 = p.slNow; p.mfe = p.entry; p.chase = g_chase;
   p.sHi = g_pHigh; p.sLo = g_pLow; p.sExit = g_pExit; p.isRe = g_reTaking;   // v1.35: the setup, for a re-entry
   p.risk = MathAbs(p.entry - sl) * lots * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   p.tp1 = side > 0 ? (noTp ? "none (exit EMA below entry, no resistance above) - trailing from entry"
                            : fix != 0 ? StringFormat("%.2f (TP1 method %d)", tp, InpTpMode)
                            : resTp1 ? StringFormat("next resistance %.2f (the %d EMA is below the entry)", tp, g_pExit)
                            : StringFormat("touch of the %d EMA (now %.2f)", g_pExit, Ema(g_pExit, 0)))
                    : fix != 0 ? StringFormat("%.2f (TP1 method %d)", tp, InpTpMode) : StringFormat("last support %.2f", tp);
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
   if (InpCloseLossMins <= 0 || ArraySize(g_pos) == 0) return;
   // v1.27 (Zee 2026-10-17, "some settings might be amiss"): the chart judges the window at each CANDLE's open time
   // (inCloseWin: close - InpCloseLossMins - 1 .. close). On 15-min candles the last one opens at 4:45 PM New York, never inside a
   // 1-3 minute window, so the chart never shuts a trade; the EA shut Oct 5 / Oct 7 at 4:57 PM (-$810, -$596 vs chart +$326, +$516).
   // In chart-candle mode on M5+ the EA now judges it at the chart candle's open the same way. M1 unchanged.
   if (InpTvVerdict && InpBarSource == 1 && PeriodSeconds() > 60) {
      datetime b = CurBar(), e = SessionEnd(b);
      if (e == 0 || e < b || (e - b) / 60 > InpCloseLossMins + 1) return;
   }
   else if (MinsToClose() > InpCloseLossMins) return;
   // v1.20: the chart judges "in loss" once, at each minute's open, against its own entry price
   static datetime lastBar = 0;
   if (InpTvVerdict) { if (CurBar() == lastBar) return; lastBar = CurBar(); }
   double bidNow = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (!PositionSelectByTicket(g_pos[i].ticket)) continue;
      double pl = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      if (InpTvVerdict) pl = g_pos[i].side > 0 ? bidNow - EnJ(i) : EnJ(i) - (bidNow + ChartSpr());
      if (pl < 0) {
         g_pos[i].why = "day close, in loss";
         Log(StringFormat("#%d day close in %d min and the trade is $%.2f down -> shutting it", g_pos[i].num, MinsToClose(), pl));
         if (trade.PositionClose(g_pos[i].ticket)) g_closeLoss++;
      }
   }
}

// v1.35: an armed re-entry fires when price is back through the original entry (BUY: bid at or above X; SELL: ask at or below X)
void ReEntryCheck()
{
   if (g_reSide == 0) return;
   if (TimeCurrent() > g_reUntil) { g_reSide = 0; return; }
   if (ArraySize(g_pos) >= InpMaxPos || g_pSide != 0) return;       // the chart re-arms only when no other setup waits
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), pip = Pip();
   // the chart's rule: the setup candle's break level again (BUY high + InpBreakPips, SELL low - InpBreakPips), judged on the bid
   if (g_reSide > 0 ? bid <= g_reHi + InpBreakPips * pip : bid >= g_reLo - InpBreakPips * pip) return;
   int side = g_reSide; g_reSide = 0;
   double sh = g_pHigh, sl0 = g_pLow; int se = g_pExit; string sd = g_pDesc; bool sLate = g_late;
   g_pHigh = g_reHi; g_pLow = g_reLo; g_pExit = g_reExit; g_pDesc = "RE-ENTRY after stop: " + g_reDesc; g_late = false;
   int n0 = ArraySize(g_pos);
   g_reTaking = true;
   DoEntry(side, StopFor(side, side > 0 ? ask : bid, g_reHi, g_reLo));
   g_reTaking = false;
   if (ArraySize(g_pos) > n0) g_reTaken++;
   g_pHigh = sh; g_pLow = sl0; g_pExit = se; g_pDesc = sd; g_late = sLate;
}

void OnTick()
{
   MqlDateTime dn; TimeToStruct(TimeCurrent(), dn);
   if (dn.day_of_year != g_dayKey) { g_dayKey = dn.day_of_year; g_dayStartEq = AccountInfoDouble(ACCOUNT_EQUITY); }
   SyncPos();
   DayCloseCheck();
   SyncPos();
   ManageTick();
   SyncPos();
   ReEntryCheck();                                          // v1.35
   datetime bar = CurBar();
   if (bar != g_lastBar && TvReady(bar)) {
      g_lastBar = bar;
      AdRebuild(bar);                                       // v1.32 weekly range boxes
      if (InpDumpBars) {
         static int fh = INVALID_HANDLE;
         if (fh == INVALID_HANDLE) fh = FileOpen("saad1m_bars.csv", FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
         if (fh != INVALID_HANDLE) { FileWrite(fh, TimeToString(iTime(_Symbol, PERIOD_CURRENT, 1), TIME_DATE | TIME_MINUTES), Px(iOpen(_Symbol, PERIOD_CURRENT, 1)), Px(iHigh(_Symbol, PERIOD_CURRENT, 1)),
                                               Px(iLow(_Symbol, PERIOD_CURRENT, 1)), Px(iClose(_Symbol, PERIOD_CURRENT, 1)), DoubleToString(Buf(hFast, 1), 3), DoubleToString(Buf(hSlow, 1), 3)); FileFlush(fh); }
      }
      if (InpTvVerdict && g_useTv) { TvVerdict(); SyncPos(); }
      ApplyPendingSl();
      SyncPos();
      if (Bars(_Symbol, PERIOD_CURRENT) >= InpEmaSlow * 2 + 20 && !g_tvStale && (!g_useTv || g_tvEnd >= InpEmaSlow * 2 + 19)) {
         ManageBar();
         SyncPos();
         // the waiting setup: a gap in time cancels it, otherwise one fewer candle to break
         if (g_aSide != 0) {
            if (InpGapCancel && CurBar() - BTime(1) > PeriodSeconds() * 3 / 2) { g_aSide = 0; g_skipDip++; }
            else if (--g_aLeft <= 0) { g_aSide = 0; g_skipDip++; Log("no dip within the window - skipped"); }
         }
         if (g_pSide != 0 && InpEntryMode == 2 && g_pLeft <= 1) { if (!g_swept) g_skipSweep++; }
         if (g_pSide != 0) {
            if (InpGapCancel && CurBar() - BTime(1) > PeriodSeconds() * 3 / 2) { g_skipGap++; DSkip(g_pSide, "market closed in between"); g_pSide = 0; }
            else if (g_retryUntil > TimeCurrent()) { /* waiting for the broker to open: keep the setup */ }
            else if (InpTvVerdict && g_useTv && InpEntryMode == 0 && ArraySize(g_pos) == 0 && BTime(1) > g_pTime &&
                     (g_pSide > 0 ? BHigh(1) > g_pHigh + InpBreakPips * Pip() : BLow(1) < g_pLow - InpBreakPips * Pip())) {
               Log(StringFormat("the chart's candle broke the %s (MT5's ticks did not) - entering at this open", g_pSide > 0 ? "high" : "low"));
               g_late = true; TryEntry(); g_late = false;
               if (g_pSide != 0 && --g_pLeft <= 0) g_pSide = 0;
            }
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
   // v1.15 (chart vs MT5 11 Oct 23:39): the chart ignores a setup candle while a trade is open at its close ("busy") - also a trade
   // that only closes at this open. A trade the chart never had (cancelled by its candle) does not count.
   if (InpTvVerdict && (ArraySize(g_pos) > 0 || g_retryUntil > TimeCurrent() || (g_exitBar == CurBar() && g_cancelBar != g_exitBar))) { g_busy++; return; }
   if (InpNoNewMins > 0 && MinsToClose() <= InpNoNewMins) return;   // too close to the day's close
   CheckCooldown();
   if (TimeCurrent() < g_coolUntil) return;
   int shape = Shape(1);
   if (shape == 0) return;
   MqlDateTime dt; TimeToStruct(BTime(1), dt);
   if (dt.hour < InpSessFrom || dt.hour >= InpSessTo) return;
   if (InpSkipDow >= 0 && dt.day_of_week == InpSkipDow) return;
   double e9 = EmaX(1, 1), e50 = EmaX(0, 1);
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
       (InpSlopePips > 0 && (EmaX(0, 1) - EmaX(0, 1 + InpSlopeLook)) * side < InpSlopePips * Pip()) ||
       (InpEmaGapPips > 0 && MathAbs(e9 - e50) < InpEmaGapPips * Pip())) { g_filtered++; return; }

   if (InpDayLossUsd > 0 || InpDayTargetUsd > 0) {
      double d = DayPnl();
      if ((InpDayLossUsd > 0 && d <= -InpDayLossUsd) || (InpDayTargetUsd > 0 && d >= InpDayTargetUsd)) { g_dayStop++; return; }
   }
   if (InpDayLossPct > 0 && AccountInfoDouble(ACCOUNT_EQUITY) <= g_dayStartEq * (1 - InpDayLossPct / 100.0)) { g_dayLossStop++; return; }
   if (ArraySize(g_pos) >= InpMaxPos || ((g_pSide != 0 || g_aSide != 0) && !InpReplace)) { g_busy++; return; }
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
