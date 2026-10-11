//+------------------------------------------------------------------+
//| Saad_strategy_BTC.mq5  v1.00  (BTC M5 variant of Saad v4.03)     |
//| Built from mt5/RULES_EMA_SAAD.md. EMA 9 + EMA 50.                |
//| BTC VARIANT (2026-10-11) - NOT PROMOTED, LOSES (see report): every pip/$ input rescaled for BTCUSD  |
//| (Axi: contract 1 BTC, min lot 0.10, M5 candle ~$148, spread $12).|
//| Pips are $3.30 here (InpPipPts 330); $ caps are BTC price $.     |
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
//| v4.02 defaults = the MT5 court winner (2026-10-11/12, Axi real    |
//| ticks Jan 1-Oct 8, 3 random-delay runs each): break +2 pips, SL  |
//| 30, ATR x2.0 trail after the TP, lock exactly at the TP, no new  |
//| trades after +$150 in a day. The rest = Zee's chart settings.    |
//| 1 gold pip = 10 points ($0.10). Hours are broker server hours.   |
//+------------------------------------------------------------------+
#property copyright "turtle"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//--- the two lines
input int    InpEmaFast     = 9;      // InpEmaFast
input int    InpEmaSlow     = 50;     // InpEmaSlow

//--- ① setup candle
input double InpWickMin     = 0.35;   // InpWickMin — pin: long wick >= this x range
input double InpBodyMax     = 0.60;   // InpBodyMax — pin: body <= this x range
input double InpNoseMax     = 0.20;   // InpNoseMax — pin: short wick <= this x range
input bool   InpPinDir      = false;  // InpPinDir — pin must point the trade way (false = any pin, the EMA decides)
input bool   InpUsePin      = true;   // InpUsePin — accept pin bars
input bool   InpMarubozu    = true;   // InpMarubozu — accept a marubozu
input double InpMaruBody    = 0.70;   // InpMaruBody — marubozu: body >= this x range
input bool   InpHammer      = true;   // InpHammer — accept hammers (LONG)
input bool   InpStar        = true;   // InpStar — accept shooting stars (SHORT)
input double InpHamRatio    = 3.0;    // InpHamRatio — hammer: long wick >= this x body
input double InpHamNose     = 0.50;   // InpHamNose — hammer: opposite wick <= this x range
input double InpMinRangeAtr = 0.50;   // InpMinRangeAtr — candle range >= this x ATR(14) (0 = off)

//--- ① on the EMA
input int    InpLongRule    = 2;      // InpLongRule — 0 on 9 EMA exit 50 (rules) · 1 on 50 exit 9 (inverse) · 2 both
input int    InpShortLine   = 2;      // InpShortLine — 0 the 50 EMA (rules) · 1 the 9 EMA · 2 either
input int    InpTouchMode   = 0;      // InpTouchMode — 0 candle touches the EMA · 1 wick touches, body on the trade side
input double InpTouchPips   = 0;      // InpTouchPips — touch tolerance
input bool   InpLongExitAbove = false;// InpLongExitAbove — LONG only when its exit EMA is above the candle

//--- ② break · ③ entry
input int    InpBreakBars   = 2;      // InpBreakBars — the high/low must break within this many candles
input double InpBreakPips   = 2;      // InpBreakPips — break must clear the high/low by this many pips [v4.02: 0->2, MT5 court]
input bool   InpTrigBid     = true;   // InpTrigBid — LONG break judged on the BID like the chart (false = the ASK, a real buy stop)

//--- ④ stop · ⑤ target
input double InpSlPips      = 30;     // InpSlPips — stop beyond the candle [v4.02: 34->30]
input double InpMaxRiskUsd  = 300;    // InpMaxRiskUsd — skip if the stop is more than this $ of price away (0 = off) [BTC: gold cap x33, in BTC price $]
input int    InpLongExit    = 1;      // InpLongExit — 0 a candle touches the exit EMA · 1 a candle CLOSES at / beyond it
input double InpLongTpPips  = 0;      // InpLongTpPips — LONG: take profit this many pips before the EMA
input int    InpSwingPivot  = 3;      // InpSwingPivot — SHORT "last support" = swing low with this many candles each side
input int    InpSwingLook   = 300;    // InpSwingLook — candles back to search for the support
input double InpShortTpPips = 0;      // InpShortTpPips — SHORT: take profit this many pips before the support
input double InpMinTpPips   = 5;      // InpMinTpPips — TP at least this far from the entry
input double InpMaxTpPips   = 0;      // InpMaxTpPips — skip a SHORT whose support is further than this (0 = off)

//--- ⑥ breakeven
input double InpBeUsd       = 0.0;    // InpBeUsd — stop to entry once price moved this $ (0 = off)

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
input double InpChopEr      = 0.10;   // InpChopEr — skip if the efficiency ratio is below this (0 = off)
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
input double InpDayTargetUsd = 0;     // InpDayTargetUsd — no new trades today once the day made this $ (0 = off) [v4.02: 0->150 at 0.10 lots] [BTC: off]

//--- trading
input double InpLots        = 0.10;   // InpLots — lot size
input bool   InpBuys        = true;   // InpBuys — allow longs
input bool   InpSells       = true;   // InpSells — allow shorts
input int    InpPipPts      = 330;     // InpPipPts — points per pip (gold 10) [BTC: 10->330, BTC candles are 33x gold's, so one "pip" = $3.30]
input int    InpMagicNumber = 88303;  // InpMagicNumber — Saad_strategy [BTC variant: own magic]
input bool   InpVerbose     = false;  // InpVerbose — print every decision

CTrade   trade;
int      hFast = INVALID_HANDLE, hSlow = INVALID_HANDLE, hAtr = INVALID_HANDLE;
datetime g_lastBar = 0;

// the setup waiting for its break
int      g_pSide = 0;
double   g_pHigh = 0, g_pLow = 0;
int      g_pLeft = 0;
int      g_pExit = 50;           // long: which EMA is its exit

// per-position state
struct PosState { ulong ticket; int side; double entry; double tp; int exitE; bool noTp; bool ride; datetime entryTime; double best; };
PosState g_pos[];

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
   PrintFormat("[SAAD-BTC] v1.00 %s | stops level %d pts, freeze %d pts, spread now %d pts | SL %.0f pips, max risk $%.2f, ER %.2f/%d, hours %d-%d, trail %s N%d ride %s, maxPos %d",
               _Symbol, (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL),
               (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD), InpSlPips, InpMaxRiskUsd, InpChopEr, InpChopErLook, InpSessFrom, InpSessTo,
               InpTrail ? "on" : "off", InpTrailN, InpRide ? "on" : "off", InpMaxPos);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
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

bool Choppy()
{
   if (InpChopEr <= 0) return false;
   double net = MathAbs(iClose(_Symbol, PERIOD_CURRENT, 1) - iClose(_Symbol, PERIOD_CURRENT, InpChopErLook + 1));
   double path = 0;
   for (int i = 1; i <= InpChopErLook; i++)
      path += MathAbs(iClose(_Symbol, PERIOD_CURRENT, i) - iClose(_Symbol, PERIOD_CURRENT, i + 1));
   return path <= 0 || net / path < InpChopEr;
}

//--- positions
int FindPos(ulong t) { for (int i = 0; i < ArraySize(g_pos); i++) if (g_pos[i].ticket == t) return i; return -1; }

void SyncPos()
{
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--)
      if (!PositionSelectByTicket(g_pos[i].ticket)) {
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
   return trade.PositionModify(t, sl, PositionGetDouble(POSITION_TP));
}

// TP reached: ride (lock + trail) or close. Returns true when the position was closed.
bool TpReached(int i, double tpLv)
{
   if (TrailOn(g_pos[i].side) && InpRide) {
      g_pos[i].ride = true; g_rides++;
      if (InpRideLock != 2 && PositionSelectByTicket(g_pos[i].ticket)) {
         double cur = PositionGetDouble(POSITION_SL);
         double lock = InpRideLock == 0 ? (g_pos[i].side > 0 ? tpLv - InpLockPips * Pip() : tpLv + InpLockPips * Pip()) : g_pos[i].entry;
         bool better = g_pos[i].side > 0 ? lock > cur : (cur == 0 || lock < cur);
         if (better && !ModifySl(g_pos[i].ticket, lock)) g_lockFail++;
      }
      return false;
   }
   return trade.PositionClose(g_pos[i].ticket);
}

// tick by tick: target touches
void ManageTick()
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask0 = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (InpLockAtUsd > 0 && PositionSelectByTicket(g_pos[i].ticket)) {
         double moved = g_pos[i].side > 0 ? bid - g_pos[i].entry : g_pos[i].entry - ask0;
         double want = g_pos[i].entry + g_pos[i].side * InpLockUsd, cur = PositionGetDouble(POSITION_SL);
         if (moved >= InpLockAtUsd && (g_pos[i].side > 0 ? want > cur + _Point : (cur == 0 || want < cur - _Point))) ModifySl(g_pos[i].ticket, want);
      }
      if (InpMaxBars > 0 && TimeCurrent() - g_pos[i].entryTime >= InpMaxBars * PeriodSeconds()) { trade.PositionClose(g_pos[i].ticket); continue; }
      if (InpFixTpPips > 0) continue;
      if (g_pos[i].ride) continue;
      if (g_pos[i].side < 0) {
         // SHORT that will ride: no TP at the broker, so watch the support here (chart price = bid)
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
      if (side > 0 && !g_pos[i].ride && InpFixTpPips <= 0) {
         double tgt = Ema(g_pos[i].exitE, 1) - InpLongTpPips * Pip();
         if (!g_pos[i].noTp && InpLongExit == 1 && tgt > g_pos[i].entry && c1 >= tgt) {
            if (TpReached(i, tgt) || !PositionSelectByTicket(t)) continue;
            sl = PositionGetDouble(POSITION_SL);        // locked; the trail may tighten it on this same candle
         }
         if (g_pos[i].noTp && !TrailOn(1) && c1 < Ema(g_pos[i].exitE, 1)) { trade.PositionClose(t); continue; }
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
            if (better) { ModifySl(t, lvl); sl = lvl; }
         }
      }
      if (InpBeUsd > 0 && afterEntryBar) {
         double best = side > 0 ? h1 - g_pos[i].entry : g_pos[i].entry - l1;
         bool done = side > 0 ? sl >= g_pos[i].entry : (sl > 0 && sl <= g_pos[i].entry);
         if (!done && best > InpBeUsd) ModifySl(t, g_pos[i].entry);
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
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double pip = Pip();
   int side = g_pSide;
   bool hit = side > 0 ? (InpTrigBid ? bid : ask) > g_pHigh + InpBreakPips * pip : bid < g_pLow - InpBreakPips * pip;
   if (!hit) return;
   if (InpMaxSpreadPts > 0 && (ask - bid) / _Point > InpMaxSpreadPts) return;    // wait for a normal spread
   g_pSide = 0;
   double en = side > 0 ? ask : bid;
   double sl = side > 0 ? g_pLow - InpSlPips * pip : g_pHigh + InpSlPips * pip;
   if (InpMaxRiskUsd > 0 && MathAbs(en - sl) > InpMaxRiskUsd) { g_skipRisk++; return; }
   double tp = 0;
   bool noTp = false;
   if (side < 0) {
      double sup = LastSupport(bid - InpMinTpPips * pip);
      if (sup <= 0) { g_skipSup++; return; }
      tp = sup + InpShortTpPips * pip;
      if (InpMaxTpPips > 0 && bid - tp > InpMaxTpPips * pip) { g_skipSup++; return; }
   } else {
      noTp = Ema(g_pExit, 0) - InpLongTpPips * pip < en + InpMinTpPips * pip;
   }
   bool rideShort = side < 0 && TrailOn(-1) && InpRide && InpFixTpPips <= 0;
   if (InpFixTpPips > 0) { tp = side > 0 ? en + InpFixTpPips * pip : en - InpFixTpPips * pip; noTp = false; }
   bool ok = side > 0 ? trade.Buy(InpLots, _Symbol, 0, NormalizeDouble(sl, _Digits), InpFixTpPips > 0 ? NormalizeDouble(tp, _Digits) : 0, "saad_long")
                      : trade.Sell(InpLots, _Symbol, 0, NormalizeDouble(sl, _Digits), rideShort ? 0 : NormalizeDouble(tp, _Digits), "saad_short");
   if (!ok) return;
   ulong t = trade.ResultOrder();
   ulong deal = trade.ResultDeal();
   if (deal > 0 && HistoryDealSelect(deal)) t = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
   PosState p;
   p.ticket = t; p.side = side; p.entry = trade.ResultPrice() > 0 ? trade.ResultPrice() : en; p.tp = tp;
   p.exitE = g_pExit; p.noTp = noTp; p.ride = side > 0 && noTp && TrailOn(1) && InpFixTpPips <= 0;
   p.entryTime = TimeCurrent(); p.best = p.entry;
   int n = ArraySize(g_pos); ArrayResize(g_pos, n + 1); g_pos[n] = p;
   g_entries++;
   if (InpVerbose) PrintFormat("[SAAD] %s at %.2f | SL %.2f | TP %s", side > 0 ? "BUY" : "SELL", p.entry, sl,
                               side > 0 ? (noTp ? "none (trail)" : StringFormat("EMA%d", g_pExit)) : DoubleToString(tp, 2));
}

void OnTick()
{
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
         if (g_pSide != 0) {
            if (InpGapCancel && iTime(_Symbol, PERIOD_CURRENT, 0) - iTime(_Symbol, PERIOD_CURRENT, 1) > PeriodSeconds() * 3 / 2) { g_skipGap++; g_pSide = 0; }
            else if (--g_pLeft <= 0) { g_skipBreak++; g_pSide = 0; }
         }
         DetectSetup();
      }
   }
   TryEntry();
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
   if (Choppy()) { g_chop++; return; }
   int side = longOk ? 1 : -1;

   if ((InpTrendAlign && (side > 0 ? e9 <= e50 : e9 >= e50)) ||
       (InpPriceSide && (side > 0 ? c <= e50 : c >= e50)) ||
       (InpSlopePips > 0 && (Buf(hSlow, 1) - Buf(hSlow, 1 + InpSlopeLook)) * side < InpSlopePips * Pip()) ||
       (InpEmaGapPips > 0 && MathAbs(e9 - e50) < InpEmaGapPips * Pip())) { g_filtered++; return; }

   if (InpDayLossUsd > 0 || InpDayTargetUsd > 0) {
      double d = DayPnl();
      if ((InpDayLossUsd > 0 && d <= -InpDayLossUsd) || (InpDayTargetUsd > 0 && d >= InpDayTargetUsd)) { g_dayStop++; return; }
   }
   if (ArraySize(g_pos) >= InpMaxPos || (g_pSide != 0 && !InpReplace)) { g_busy++; return; }
   if (ArraySize(g_pos) > 0 && InpExtraDir != 0) {
      bool same = g_pos[0].side == side;
      if ((InpExtraDir == 1 && !same) || (InpExtraDir == 2 && same)) { g_busy++; return; }
   }

   g_pSide = side; g_pHigh = h; g_pLow = l; g_pLeft = InpBreakBars; g_setups++;
   g_pExit = side > 0 ? (rulesOk ? 50 : 9) : 0;
   if (InpVerbose) PrintFormat("[SAAD] %s setup (%s) on %s | waiting for %s %.2f", side > 0 ? "LONG" : "SHORT",
                               g_kind == 1 ? "pin" : g_kind == 2 ? "hammer/star" : "marubozu",
                               side > 0 ? (rulesOk ? "9 EMA, exit 50" : "50 EMA, exit 9") : "EMA", side > 0 ? ">" : "<", side > 0 ? h : l);
}
