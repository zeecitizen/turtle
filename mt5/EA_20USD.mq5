//+------------------------------------------------------------------+
//| EA_20USD.mq5 - Saad_strategy_15min v1.14 for a $20 account      
//| XAUUSD M15, fixed 0.01 lot (the smallest trade Axi allows).        
//|                                                                    
//| VERDICT: NOT VIABLE - most months end near $0
//|                                                                    
//| MT5 Strategy Tester, Axi real ticks (XAUUSD_TK), 1:1000 leverage,  
//| one-month runs started at each month Jan-Sep 2026 (9 starts):      
//|   months ending in a loss      : 6 of 9
//|   months losing more than half : 6 of 9
//|   worst month-end balance      : -$2.41 (wiped)
//|   typical (median) month end   : $3.82
//| One loss at 0.01 lot costs $8-15 (stop = candle + 35 pips, cap $15).
//| Leverage only lowers the margin; it does NOT make a loss smaller.  
//| Use money you can afford to lose completely. Test on demo first.   
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
#property version   "1.14"
#property strict

#include <Trade/Trade.mqh>

//--- the two lines
input int    InpEmaFast     = 9;      // InpEmaFast
input int    InpEmaSlow     = 50;     // InpEmaSlow

//--- ① setup candle
input double InpWickMin     = 0.45;   // InpWickMin — pin: long wick >= this x range [v1.13: 0.35->0.45]
input double InpBodyMax     = 0.60;   // InpBodyMax — pin: body <= this x range
input double InpNoseMax     = 0.20;   // InpNoseMax — pin: short wick <= this x range
input bool   InpPinDir      = false;  // InpPinDir — pin must point the trade way (false = any pin, the EMA decides)
input bool   InpPinColor    = false;  // InpPinColor — pin body must close the trade way too: LONG green, SHORT red (with InpPinDir)
input bool   InpUsePin      = true;   // InpUsePin — accept pin bars
input bool   InpMarubozu    = true;   // InpMarubozu — accept a marubozu
input double InpMaruBody    = 0.53;   // InpMaruBody — marubozu: body >= this x range [v1.09: 0.70->0.50, Zee; 0.35-0.55 plateau] [v1.14: 0.50->0.53]
input bool   InpHammer      = true;   // InpHammer — accept hammers (LONG)
input bool   InpStar        = true;   // InpStar — accept shooting stars (SHORT)
input double InpHamRatio    = 2.5;    // InpHamRatio — hammer: long wick >= this x body [v1.13: 3->2.5]
input double InpHamNose     = 0.50;   // InpHamNose — hammer: opposite wick <= this x range
input double InpMinRangeAtr = 0.55;   // InpMinRangeAtr — candle range >= this x ATR(14) (0 = off) [v1.14: 0.50->0.55]

//--- ① on the EMA
input int    InpLongRule    = 2;      // InpLongRule — 0 on 9 EMA exit 50 (rules) · 1 on 50 exit 9 (inverse) · 2 both
input int    InpShortLine   = 1;      // InpShortLine — 0 the 50 EMA (rules) · 1 the 9 EMA · 2 either [M15: 2->1, SHORT setups on the 9 EMA]
input int    InpTouchMode   = 0;      // InpTouchMode — 0 candle touches the EMA · 1 wick touches, body on the trade side
input double InpTouchPips   = 0;      // InpTouchPips — touch tolerance
input bool   InpLongExitAbove = false;// InpLongExitAbove — LONG only when its exit EMA is above the candle

//--- ② break · ③ entry
input int    InpBreakBars   = 1;      // InpBreakBars — the high/low must break within this many candles [M15: 2->1, one 15-min candle = three 5-min ones]
input double InpBreakPips   = 2;      // InpBreakPips — break must clear the high/low by this many pips [v4.02: 0->2, MT5 court]
input bool   InpTrigBid     = true;   // InpTrigBid — LONG break judged on the BID like the chart (false = the ASK, a real buy stop)

//--- ④ stop · ⑤ target
input double InpSlPips      = 35;     // InpSlPips — stop beyond the candle [v4.02: 34->30] [v1.13: 30->35, real-tick court + Jul-Oct holdout]
input double InpMaxRiskUsd  = 15.0;    // InpMaxRiskUsd — skip if the stop is more than this $ of price away (0 = off) [M15: 9->15; 14-18 plateau, 9 skips 2/3 of M15 setups]
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
input double InpLongTrailUsd = 2.0;   // InpLongTrailUsd — ...the trailing stop's distance below the market, $ of price [v1.07: 3->2, Zee]
input bool   InpLongResTp   = true;   // InpLongResTp — ...and aim for the next liquidity: TP2 = last resistance, then TP3 = the one beyond (watched by the EA; the exit is the trail)
input bool   InpLongResTp1  = false;  // InpLongResTp1 — LONG whose exit EMA is below / too close to the entry: TP1 = the next resistance above the entry (false = no TP, trail from entry) [v1.11 Zee; v1.12 OFF: -$70k on real ticks (trailing from entry is better)]
input bool   InpResTp1Ride  = true;   // InpResTp1Ride — with InpLongResTp1: also trail from the entry (2xATR) until that resistance is reached
input int    InpShortTouch  = 1;      // InpShortTouch — SHORT at the support (TP1): 1 trail $X above the market + TP2/TP3 = the supports below (Zee 2026-10-12) · 0 old (lock + ATR trail)
input double InpTrailStepUsd = 0;     // InpTrailStepUsd — widen the $ trail by this much at each TP reached after TP1 (TP2 +1x, TP3 +2x ...; 0 = fixed)
input double InpShortTrailUsd = 2.0;  // InpShortTrailUsd — ...the trailing stop's distance above the market, $ of price [v1.07: 3->2, Zee]
input double InpBeTpPct     = 0.75;   // InpBeTpPct — CTC: stop to entry once price covered this share of the way to the TP (0 = off) [v1.02, Zee]

//--- ⑦ trailing
input bool   InpTrail       = true;   // InpTrail — use a trailing stop
input int    InpTrailSide   = 2;      // InpTrailSide — 0 LONG only · 1 SHORT only · 2 both
input bool   InpRide        = true;   // InpRide — let winners run: trail from the TP instead of exiting
input int    InpTrailMode   = 2;      // InpTrailMode — 0 low/high of last N candles · 1 X pips behind best · 2 ATR x behind best [v4.02: 0->2 ATR]
input int    InpTrailN      = 6;      // InpTrailN — N candles
input double InpTrailPips   = 30;     // InpTrailPips — X pips
input double InpTrailAtr    = 2.0;    // InpTrailAtr — ATR multiple [v4.02: 1.3->2.0; 1.75-2.5 plateau]
input double InpTrailStart  = 0;      // InpTrailStart — without ride: start trailing after this many pips of profit
input int    InpRideLock    = 0;      // InpRideLock — when the TP is reached lock the stop at: 0 the TP · 1 the entry · 2 don't lock
input double InpLockPips    = 0;      // InpLockPips — lock this many pips short of the TP [v4.02: 2->0]

//--- ✖ filters
input double InpChopEr      = 0.11;   // InpChopEr — skip if the efficiency ratio is below this (0 = off) [v1.14: 0.10->0.11]
input int    InpChopErLook  = 16;     // InpChopErLook — efficiency ratio length
input int    InpSessFrom    = 0;      // InpSessFrom — broker hour, inclusive (Axi UTC+3; 0/24 = all day)
input int    InpSessTo      = 24;     // InpSessTo — broker hour, exclusive
input bool   InpGapCancel   = true;   // InpGapCancel — cancel a waiting setup across the daily close / weekend
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
input int    InpSlMode      = 0;      // InpSlMode — 0 InpSlPips beyond the setup candle · 1 InpSlAtrMult x ATR from the entry · 2 InpSlUsd from the entry
input double InpSlAtrMult   = 1.0;    // InpSlAtrMult — stop mode 1
input double InpSlUsd       = 5.0;    // InpSlUsd — stop mode 2, $ of price
input double InpPartialPct  = 0;      // InpPartialPct — close this share of the position at TP1 (0 = off)
input double InpRiskPct     = 0;      // InpRiskPct — size each trade to risk this % of equity (0 = fixed InpLots)
input double InpMinLotRiskPct = 0;    // InpMinLotRiskPct — with InpRiskPct: skip a trade when even the minimum lot would risk more than this % of equity (0 = take it at the minimum lot)
input double InpMaxLots     = 50;     // InpMaxLots — upper limit for InpRiskPct sizing
input int    InpModBackoffSec = 3;   // InpModBackoffSec — after the broker refuses a stop change, wait this many seconds before trying again (60 s when the market is closed)
input double InpDayLossPct  = 0;      // InpDayLossPct — no new trades today after losing this % of the day's starting equity (0 = off)

//--- trading
input double InpLots        = 0.01;   // InpLots — lot size [EA_20USD: minimum lot]
input bool   InpBuys        = true;   // InpBuys — allow longs
input bool   InpSells       = true;   // InpSells — allow shorts
input int    InpPipPts      = 10;     // InpPipPts — points per pip (gold 10)
input int    InpMagicNumber = 88310;  // InpMagicNumber — Saad_strategy [M15 variant: own magic, can run beside the M5 EA] [EA_20USD]
input bool   InpVerbose     = false;  // InpVerbose — print every decision
input bool   InpDraw        = true;   // InpDraw — labels on the chart (visual tester + live): setups, entries, stop moves, exits
input bool   InpLog         = true;   // InpLog — print every trade event to the Experts tab (live + visual tester)
input bool   InpLogCsv      = true;   // InpLogCsv — one CSV row per closed trade in Common\Files (live + visual tester)
input bool   InpDrawSkips   = false;   // InpDrawSkips — also label setups that were skipped (no break, risk, no support, choppy)

CTrade   trade;
int      hFast = INVALID_HANDLE, hSlow = INVALID_HANDLE, hAtr = INVALID_HANDLE;
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
                  int num; double slNow; datetime slFrom; string why; };
PosState g_pos[];

int g_ctc = 0, g_skipClose = 0, g_closeLoss = 0;
int g_setups = 0, g_entries = 0, g_skipBreak = 0, g_skipGap = 0, g_skipRisk = 0, g_skipSup = 0, g_chop = 0,
    g_busy = 0, g_rides = 0, g_lockFail = 0, g_dayStop = 0, g_filtered = 0;

double Pip() { return InpPipPts * _Point; }
double Buf(int h, int s) { double v[1]; return CopyBuffer(h, 0, s, 1, v) == 1 ? v[0] : 0.0; }
double Ema(int which, int s) { return Buf(which == 9 ? hFast : hSlow, s); }
bool   TrailOn(int side) { return InpTrail && (InpTrailSide == 2 || (side > 0 && InpTrailSide == 0) || (side < 0 && InpTrailSide == 1)); }

int OnInit()
{
   hFast = iMA(_Symbol, PERIOD_CURRENT, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
   hSlow = iMA(_Symbol, PERIOD_CURRENT, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   hAtr  = iATR(_Symbol, PERIOD_CURRENT, 14);
   if (hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE || hAtr == INVALID_HANDLE) return INIT_FAILED;
   trade.SetExpertMagicNumber(InpMagicNumber);
   if (MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)) trade.LogLevel(LOG_LEVEL_ERRORS);   // v1.12: agent logs were 381-866 MB
   PrintFormat("[EA_20USD] v1.14 %s | stops level %d pts, freeze %d pts, spread now %d pts | SL %.0f pips, max risk $%.2f, ER %.2f/%d, hours %d-%d, trail %s N%d ride %s, maxPos %d",
               _Symbol, (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL),
               (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD), InpSlPips, InpMaxRiskUsd, InpChopEr, InpChopErLook, InpSessFrom, InpSessTo,
               InpTrail ? "on" : "off", InpTrailN, InpRide ? "on" : "off", InpMaxPos);
   datetime e = SessionEnd(TimeCurrent());
   PrintFormat("[SAAD] day close for %s: %s (no new trades %d min before; losers shut %d min before)", _Symbol,
               e == 0 ? "none found (no daily break)" : TimeToString(e), InpNoNewMins, InpCloseLossMins);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
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
   double o = iOpen(_Symbol, PERIOD_CURRENT, s), c = iClose(_Symbol, PERIOD_CURRENT, s);
   double h = iHigh(_Symbol, PERIOD_CURRENT, s), l = iLow(_Symbol, PERIOD_CURRENT, s);
   double rng = h - l;
   if (rng <= 0) return 0;
   if (InpMinRangeAtr > 0 && rng < InpMinRangeAtr * Buf(hAtr, s)) return 0;
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
   double o = iOpen(_Symbol, PERIOD_CURRENT, s), c = iClose(_Symbol, PERIOD_CURRENT, s);
   double h = iHigh(_Symbol, PERIOD_CURRENT, s), l = iLow(_Symbol, PERIOD_CURRENT, s);
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
      double l = iLow(_Symbol, PERIOD_CURRENT, i);
      if (l <= 0) break;
      if (l >= below) continue;
      bool piv = true;
      for (int k = 1; k <= p && piv; k++)
         if (iLow(_Symbol, PERIOD_CURRENT, i - k) <= l || iLow(_Symbol, PERIOD_CURRENT, i + k) < l) piv = false;
      if (piv) return l;
   }
   return 0.0;
}

// the most recent confirmed swing high above `above` (the "next liquidity" for a LONG)
double LastResistance(double above)
{
   int p = InpSwingPivot;
   for (int i = 1 + p; i < 1 + p + InpSwingLook; i++) {
      double h = iHigh(_Symbol, PERIOD_CURRENT, i);
      if (h <= 0) break;
      if (h <= above) continue;
      bool piv = true;
      for (int k = 1; k <= p && piv; k++)
         if (iHigh(_Symbol, PERIOD_CURRENT, i - k) >= h || iHigh(_Symbol, PERIOD_CURRENT, i + k) > h) piv = false;
      if (piv) return h;
   }
   return 0.0;
}

bool Choppy()
{
   if (InpChopEr <= 0) return false;
   double net = MathAbs(iClose(_Symbol, PERIOD_CURRENT, 1) - iClose(_Symbol, PERIOD_CURRENT, InpChopErLook + 1));
   double path = 0;
   for (int i = 1; i <= InpChopErLook; i++)
      path += MathAbs(iClose(_Symbol, PERIOD_CURRENT, i) - iClose(_Symbol, PERIOD_CURRENT, i + 1));
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
   ObjectSetInteger(0, n, OBJPROP_COLOR, side > 0 ? clrDodgerBlue : clrOrangeRed);
   ObjectSetInteger(0, n, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
}
// a label placed `lvl` x ATR away from the candle (above when up=true) with an arrow pointing back to (t, price)
void Callout(datetime t, double price, bool up, double lvl, string txt, color c, int size = 9, string tip = "")
{
   if (!Drawing()) return;
   double a = Buf(hAtr, 1); if (a <= 0) a = 10 * Pip();
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
   if (note != "") DText(now, newSl, note, clrOrange, 7, g_pos[i].side > 0 ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER);
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
   color c = pnl > 0 ? clrLimeGreen : clrRed;
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
      Callout(TimeCurrent(), tpLv, g_pos[i].side > 0, 1.5, note, clrAqua, 8);
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
   Callout(TimeCurrent(), bid, true, 1.5, note, clrAqua, 8);
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
   Callout(TimeCurrent(), bid, false, 1.5, note, clrAqua, 8);
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
   Callout(TimeCurrent(), was, sd > 0, 1.5, note, clrAqua, 8);
   if (nx > 0) DLine(TimeCurrent(), nx, TimeCurrent() + 8 * PeriodSeconds(), nx, clrLime, STYLE_DASH, 1, StringFormat("TP%d", g_pos[i].tpStage));
}

// tick by tick: target touches
void ManageTick()
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask0 = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      g_pos[i].mfe = g_pos[i].side > 0 ? MathMax(g_pos[i].mfe, bid) : (g_pos[i].mfe == 0 ? ask0 : MathMin(g_pos[i].mfe, ask0));
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
   double c1 = iClose(_Symbol, PERIOD_CURRENT, 1), h1 = iHigh(_Symbol, PERIOD_CURRENT, 1), l1 = iLow(_Symbol, PERIOD_CURRENT, 1);
   datetime t1 = iTime(_Symbol, PERIOD_CURRENT, 1);
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      ulong t = g_pos[i].ticket;
      if (!PositionSelectByTicket(t)) continue;
      int side = g_pos[i].side;
      double sl = PositionGetDouble(POSITION_SL);
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
                  lvl = side > 0 ? MathMin(lvl, iLow(_Symbol, PERIOD_CURRENT, k)) : MathMax(lvl, iHigh(_Symbol, PERIOD_CURRENT, k));
            } else if (InpTrailMode == 1) lvl = side > 0 ? g_pos[i].best - InpTrailPips * Pip() : g_pos[i].best + InpTrailPips * Pip();
            else lvl = side > 0 ? g_pos[i].best - InpTrailAtr * Buf(hAtr, 1) : g_pos[i].best + InpTrailAtr * Buf(hAtr, 1);
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
   if (g_pSide == 0 || ArraySize(g_pos) >= InpMaxPos) return;
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
   bool hit = side > 0 ? (InpTrigBid ? bid : ask) > g_pHigh + InpBreakPips * pip : bid < g_pLow - InpBreakPips * pip;
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
   DoEntry(side, StopFor(side, side > 0 ? ask : bid, g_pHigh, g_pLow));
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
   if (InpSlMode == 1) { double a = Buf(hAtr, 1) * InpSlAtrMult; return side > 0 ? en - a : en + a; }
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
   if (InpMaxRiskUsd > 0 && MathAbs(en - sl) > InpMaxRiskUsd) { g_skipRisk++; DSkip(side, StringFormat("stop too far ($%.2f > $%.2f)", MathAbs(en - sl), InpMaxRiskUsd)); return; }
   double tp = 0;
   bool noTp = false, resTp1 = false;
   if (side < 0) {
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
   double lots = LotsFor(side, en, sl);
   if (lots <= 0) { DSkip(side, "even the minimum lot risks too much of this account"); return; }
   bool ok = side > 0 ? trade.Buy(lots, _Symbol, 0, NormalizeDouble(sl, _Digits), InpFixTpPips > 0 ? NormalizeDouble(tp, _Digits) : 0, "saad_long")
                      : trade.Sell(lots, _Symbol, 0, NormalizeDouble(sl, _Digits), rideShort ? 0 : NormalizeDouble(tp, _Digits), "saad_short");
   if (!ok) return;
   ulong t = trade.ResultOrder();
   ulong deal = trade.ResultDeal();
   if (deal > 0 && HistoryDealSelect(deal)) t = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
   PosState p;
   p.ticket = t; p.side = side; p.entry = trade.ResultPrice() > 0 ? trade.ResultPrice() : en; p.tp = tp;
   p.exitE = g_pExit; p.noTp = noTp; p.resTp1 = resTp1; p.ride = side > 0 && (noTp || (resTp1 && InpResTp1Ride)) && TrailOn(1) && InpFixTpPips <= 0;
   p.entryTime = TimeCurrent(); p.best = p.entry;
   p.num = ++g_num; p.slNow = NormalizeDouble(sl, _Digits); p.slFrom = p.entryTime; p.why = ""; p.usdTrail = false; p.tpNext = 0; p.tpStage = 1; p.setup = ""; p.sl0 = p.slNow; p.risk = 0; p.tp1 = ""; p.tp1At = 0; p.tps = ""; p.ctcAt = 0; p.moves = 0; p.mfe = 0;
   p.setup = g_pDesc; p.sl0 = p.slNow; p.mfe = p.entry;
   p.risk = MathAbs(p.entry - sl) * lots * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   p.tp1 = side > 0 ? (noTp ? "none (exit EMA below entry, no resistance above) - trailing from entry"
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
            StringFormat("%s #%d @ %.2f", side > 0 ? "BUY" : "SELL", p.num, p.entry), side > 0 ? clrDodgerBlue : clrOrangeRed, 10,
            StringFormat("%s #%d  entry %.2f | SL %.2f (-$%.2f) | TP %s | %s", side > 0 ? "BUY" : "SELL", p.num, p.entry, sl, risk, tpTxt, g_pDesc));
      DText(p.entryTime, sl, StringFormat("SL %.2f", sl), clrRed, 7, side > 0 ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER);
      if (side < 0) {
         DLine(p.entryTime, tp, p.entryTime + 8 * PeriodSeconds(), tp, clrLime, STYLE_DASH, 1, "TP: last support");
         DText(p.entryTime, tp, StringFormat("TP %.2f (last support)", tp), clrLime, 7, ANCHOR_LEFT_UPPER);
      } else if (resTp1) {
         DLine(p.entryTime, tp, p.entryTime + 8 * PeriodSeconds(), tp, clrLime, STYLE_DASH, 1, "TP1: next resistance");
         DText(p.entryTime, tp, StringFormat("TP1 %.2f (next resistance)", tp), clrLime, 7, ANCHOR_LEFT_LOWER);
      } else if (!noTp)
         DText(p.entryTime + PeriodSeconds(), Ema(g_pExit, 0), StringFormat("TP1: touch of the %d EMA", g_pExit), clrLime, 7, ANCHOR_LEFT_LOWER);
   }
   if (InpVerbose) PrintFormat("[SAAD] %s at %.2f | SL %.2f | TP %s", side > 0 ? "BUY" : "SELL", p.entry, sl,
                               side > 0 ? (noTp ? "none (trail)" : StringFormat("EMA%d", g_pExit)) : DoubleToString(tp, 2));
}

void DayCloseCheck()
{
   if (InpCloseLossMins <= 0 || ArraySize(g_pos) == 0 || MinsToClose() > InpCloseLossMins) return;
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (!PositionSelectByTicket(g_pos[i].ticket)) continue;
      double pl = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      if (pl < 0) {
         g_pos[i].why = "day close, in loss";
         Log(StringFormat("#%d day close in %d min and the trade is $%.2f down -> shutting it", g_pos[i].num, MinsToClose(), pl));
         if (trade.PositionClose(g_pos[i].ticket)) g_closeLoss++;
      }
   }
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
   datetime bar = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bar != g_lastBar) {
      g_lastBar = bar;
      if (Bars(_Symbol, PERIOD_CURRENT) >= InpEmaSlow * 2 + 20) {
         ManageBar();
         SyncPos();
         // the waiting setup: a gap in time cancels it, otherwise one fewer candle to break
         if (g_aSide != 0) {
            if (InpGapCancel && iTime(_Symbol, PERIOD_CURRENT, 0) - iTime(_Symbol, PERIOD_CURRENT, 1) > PeriodSeconds() * 3 / 2) { g_aSide = 0; g_skipDip++; }
            else if (--g_aLeft <= 0) { g_aSide = 0; g_skipDip++; Log("no dip within the window - skipped"); }
         }
         if (g_pSide != 0 && InpEntryMode == 2 && g_pLeft <= 1) { if (!g_swept) g_skipSweep++; }
         if (g_pSide != 0) {
            if (InpGapCancel && iTime(_Symbol, PERIOD_CURRENT, 0) - iTime(_Symbol, PERIOD_CURRENT, 1) > PeriodSeconds() * 3 / 2) { g_skipGap++; DSkip(g_pSide, "market closed in between"); g_pSide = 0; }
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
   CheckCooldown();
   if (TimeCurrent() < g_coolUntil) return;
   int shape = Shape(1);
   if (shape == 0) return;
   MqlDateTime dt; TimeToStruct(iTime(_Symbol, PERIOD_CURRENT, 1), dt);
   if (dt.hour < InpSessFrom || dt.hour >= InpSessTo) return;
   if (InpSkipDow >= 0 && dt.day_of_week == InpSkipDow) return;
   double e9 = Buf(hFast, 1), e50 = Buf(hSlow, 1);
   if (e9 <= 0 || e50 <= 0) return;
   double h = iHigh(_Symbol, PERIOD_CURRENT, 1), l = iLow(_Symbol, PERIOD_CURRENT, 1);
   double o = iOpen(_Symbol, PERIOD_CURRENT, 1), c = iClose(_Symbol, PERIOD_CURRENT, 1);

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
      if (InpDrawSkips) Callout(iTime(_Symbol, PERIOD_CURRENT, 1), longOk ? l : h, !longOk, 1.0, "skip: choppy", clrDimGray, 7);
      return;
   }
   int side = longOk ? 1 : -1;

   if ((InpTrendAlign && (side > 0 ? e9 <= e50 : e9 >= e50)) ||
       (InpPriceSide && (side > 0 ? c <= e50 : c >= e50)) ||
       (InpSlopePips > 0 && (Buf(hSlow, 1) - Buf(hSlow, 1 + InpSlopeLook)) * side < InpSlopePips * Pip()) ||
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
   g_pTime = iTime(_Symbol, PERIOD_CURRENT, 1);
   g_pDesc = StringFormat("%s %s on the %s%s", side > 0 ? "LONG" : "SHORT", kindTxt, lineTxt,
                          side > 0 ? (rulesOk ? " (exit at 50 EMA)" : " (exit at 9 EMA)") : " (TP last support)");
   Log(StringFormat("SETUP %s | candle %s H %s L %s | waiting 1 candle for a break %s %s", g_pDesc, Ts(g_pTime), Px(h), Px(l),
                    side > 0 ? "above" : "below", Px(side > 0 ? h + InpBreakPips * Pip() : l - InpBreakPips * Pip())));
   if (Drawing()) {
      double lvl = side > 0 ? h + InpBreakPips * Pip() : l - InpBreakPips * Pip();
      DBox(g_pTime, h, g_pTime + PeriodSeconds(), l, clrGold);
      DLine(g_pTime, lvl, g_pTime + (InpBreakBars + 1) * PeriodSeconds(), lvl, clrGold, STYLE_DOT, 1, "break level");
      Callout(g_pTime + PeriodSeconds() / 2, side > 0 ? h : l, side > 0, 2.5,
              StringFormat("SETUP %s: %s on %s", side > 0 ? "LONG" : "SHORT", kindTxt, lineTxt), clrGold, 9,
              StringFormat("%s | wait max %d candle(s) for a break %s %.2f", g_pDesc, InpBreakBars, side > 0 ? "above" : "below", lvl));
   }
   if (InpVerbose) PrintFormat("[SAAD] %s setup (%s) on %s | waiting for %s %.2f", side > 0 ? "LONG" : "SHORT",
                               g_kind == 1 ? "pin" : g_kind == 2 ? "hammer/star" : "marubozu",
                               side > 0 ? (rulesOk ? "9 EMA, exit 50" : "50 EMA, exit 9") : "EMA", side > 0 ? ">" : "<", side > 0 ? h : l);
}
