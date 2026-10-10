//+------------------------------------------------------------------+
//| Saad_strategy.mq5  v2.00                                         |
//| Built from mt5/RULES_EMA_SAAD.md (2026-10-11). EMA 9 + EMA 50.   |
//|                                                                  |
//| LONG  - a bullish PIN BAR ("thumb pin") or bullish MARUBOZU      |
//|         made ON the 9 EMA; buy when the next or next-to-next     |
//|         candle breaks its HIGH (else skip). TP: a candle touches |
//|         the 50 EMA. SL: 20 pips below the pin/marubozu.          |
//| SHORT - a bearish pin bar or bearish marubozu made ON the 50 EMA;|
//|         sell when the next or next-to-next candle breaks its LOW |
//|         (else skip). TP: "till next liquidity (last support)" =  |
//|         the most recent swing low below entry. SL: 20 pips above.|
//| OPTION- "if our profit is above 3 USD, then we breakeven".       |
//|                                                                  |
//| READINGS I HAD TO MAKE (each is an input):                       |
//|  * "made on the EMA" = the candle's range contains the EMA       |
//|    (low <= EMA <= high).                                         |
//|  * A long's TP is the 50 EMA, so it is only a PROFIT target when |
//|    the 50 EMA sits above the entry. InpLong50Above (default on)  |
//|    takes longs only then; off = take every long and let the 50   |
//|    EMA touch close it wherever it is.                            |
//|  * 1 gold pip = 10 points ($0.10), the project's convention, so  |
//|    20 pips = $2.00 on gold. InpPipPts changes that per symbol.   |
//|  * "last support" = a swing low (InpSwingPivot bars lower on     |
//|    each side) within InpSwingLook bars, below the entry.         |
//+------------------------------------------------------------------+
#property copyright "turtle"
#property version   "3.20"
#property strict

#include <Trade/Trade.mqh>

//--- the two lines
input int    InpEmaFast     = 9;      // InpEmaFast — the LONG line
input int    InpEmaSlow     = 50;     // InpEmaSlow — the SHORT line, and the long's target

//--- candle shapes
input double InpWickMin     = 0.60;   // InpWickMin — pin: long wick >= this x range
input double InpBodyMax     = 0.30;   // InpBodyMax — pin: body <= this x range
input double InpNoseMax     = 0.25;   // InpNoseMax — pin: short wick <= this x range
input bool   InpMarubozu    = true;   // InpMarubozu — also accept a marubozu
input double InpMaruBody    = 0.80;   // InpMaruBody — marubozu: body >= this x range
input double InpMinRangeAtr = 0.50;   // InpMinRangeAtr — candle range >= this x ATR(14) (0 = off)

//--- entry
input int    InpBreakBars   = 2;      // InpBreakBars — the high/low must break within this many candles
input bool   InpLong50Above = true;   // InpLong50Above — longs only when the 50 EMA is above (TP is a profit)

//--- exits
input int    InpSlPips      = 25;     // InpSlPips — stop beyond the pin/marubozu (rules 20; v3.20 25: 15<20<25~30>35)
input int    InpPipPts      = 10;     // InpPipPts — points per pip (gold 10)
input int    InpSwingPivot  = 3;      // InpSwingPivot — bars each side that make a swing low
input int    InpSwingLook   = 100;    // InpSwingLook — bars back to search for "last support"
input double InpBeUsd       = 0.0;    // InpBeUsd — breakeven trigger in USD (0 = off; rules ask to test 3)
input int    InpBeMode      = 0;      // InpBeMode — 0 USD of PROFIT on the position · 1 USD of PRICE move

//--- v3.00 VARIANTS (2026-10-11) - every one OFF by default, so the plain rules reproduce
input bool   InpPinAnyDir   = false;  // InpPinAnyDir — a pin of EITHER wick direction counts (the line picks the side)
input int    InpLongTp      = 0;      // InpLongTp — 0 candle touches 50 EMA (rules) · 1 last resistance (swing high)
input int    InpSlMode      = 0;      // InpSlMode — 0 InpSlPips beyond the candle (rules) · 1 InpSlAtr x ATR beyond it · 2 prior swing + 5 pips
input double InpSlAtr       = 1.5;    // InpSlAtr — ATR multiple for InpSlMode 1
input double InpBeR         = 0.0;    // InpBeR — breakeven once price has moved this many R (0 = off)
input int    InpTrailBars   = 0;      // InpTrailBars — once in profit, trail the stop under/over the last N candles (0 = off)
input bool   InpTrendAlign  = false;  // InpTrendAlign — longs only if EMA9 > EMA50, shorts only if EMA9 < EMA50

//--- v3.10 CHOP FILTERS (Zee, 2026-10-11: "we want to avoid choppy markets") - each 0 = off
input int    InpChopCross    = 0;     // InpChopCross — skip if EMA9 crossed EMA50 MORE than this many times...
input int    InpChopCrossLook = 20;   // InpChopCrossLook — ...in this many candles
input double InpChopEr       = 0.20;  // InpChopEr — skip if Kaufman efficiency ratio is BELOW this (0 = off; v3.10 default 0.20)
input int    InpChopErLook   = 14;    // InpChopErLook — candles the efficiency ratio is measured over
input double InpChopSlope    = 0.0;   // InpChopSlope — skip if the 50 EMA moved fewer pips than this...
input int    InpChopSlopeLook = 5;    // InpChopSlopeLook — ...over this many candles
input double InpChopAdx      = 0.0;   // InpChopAdx — skip if ADX(14) is below this (e.g. 20)

//--- v3.20 (2026-10-11) - off by default; the v3.10 baseline is unchanged
input int    InpLongMode    = 0;      // InpLongMode — 0 rules (pin on 9 EMA, TP 50 EMA) · 1 MIRROR (pin on 50 EMA, EMA9>EMA50, TP last swing high)
input int    InpTpPips      = 0;      // InpTpPips — fixed take profit in pips for BOTH sides (0 = the rules' targets)

//--- trading
input double InpLots        = 0.10;   // InpLots — lot size
input bool   InpBuys        = true;   // InpBuys — allow longs
input bool   InpSells       = true;   // InpSells — allow shorts
input int    InpSessFrom    = 8;      // InpSessFrom — broker hour, inclusive (Axi UTC+3: 08 = 10 AM PKT)
input int    InpSessTo      = 17;     // InpSessTo — broker hour, exclusive (17 = 7 PM PKT)
input int    InpMagicNumber = 88301;  // InpMagicNumber — Saad_strategy
input bool   InpVerbose     = true;   // InpVerbose — print every decision

CTrade   trade;
int      hFast = INVALID_HANDLE, hSlow = INVALID_HANDLE, hAtr = INVALID_HANDLE, hAdx = INVALID_HANDLE;
int      g_chop = 0;
datetime g_lastBar = 0;

// the setup waiting for its break
int      g_pSide = 0;          // +1 long, -1 short, 0 none
double   g_pHigh = 0, g_pLow = 0;
int      g_pLeft = 0;          // candles still allowed to break it
double   g_pTp = 0;            // short only: the support target

int g_setups = 0, g_entries = 0, g_skips = 0, g_tpEma = 0, g_be = 0, g_noTarget = 0;

int OnInit()
{
   hFast = iMA(_Symbol, PERIOD_CURRENT, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
   hSlow = iMA(_Symbol, PERIOD_CURRENT, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   hAtr  = iATR(_Symbol, PERIOD_CURRENT, 14);
   if (InpChopAdx > 0) {
      hAdx = iADX(_Symbol, PERIOD_CURRENT, 14);
      if (hAdx == INVALID_HANDLE) return INIT_FAILED;
   }
   if (hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE || hAtr == INVALID_HANDLE) return INIT_FAILED;
   trade.SetExpertMagicNumber(InpMagicNumber);
   PrintFormat("[SAAD] v3.20 - EMA %d (long) / %d (short + long TP) | pin %.2f/%.2f/%.2f marubozu %s>=%.2f "
               "| break within %d | SL %d pips (%d pts/pip) | long needs 50 above: %s | BE %s",
               InpEmaFast, InpEmaSlow, InpWickMin, InpBodyMax, InpNoseMax, InpMarubozu ? "on " : "off ",
               InpMaruBody, InpBreakBars, InpSlPips, InpPipPts, InpLong50Above ? "yes" : "no",
               InpBeUsd > 0 ? StringFormat("%.2f USD %s", InpBeUsd, InpBeMode == 0 ? "profit" : "price") : "off");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   PrintFormat("[SAAD] stopped: %d setups, %d entries, %d skipped (no break), %d long TPs at 50 EMA, "
               "%d breakevens, %d shorts skipped (no support below)",
               g_setups, g_entries, g_skips, g_tpEma, g_be, g_noTarget);
   PrintFormat("[SAAD] chop filter refused %d setups", g_chop);
}

double Buf(int h, int s) { double v[1]; return CopyBuffer(h, 0, s, 1, v) == 1 ? v[0] : 0.0; }

// +1 bullish pin/marubozu, -1 bearish, 0 none — on closed bar s
int Shape(int s)
{
   double o = iOpen(_Symbol, PERIOD_CURRENT, s), c = iClose(_Symbol, PERIOD_CURRENT, s);
   double h = iHigh(_Symbol, PERIOD_CURRENT, s), l = iLow(_Symbol, PERIOD_CURRENT, s);
   double rng = h - l;
   if (rng <= 0) return 0;
   if (InpMinRangeAtr > 0 && rng < InpMinRangeAtr * Buf(hAtr, s)) return 0;
   double body = MathAbs(c - o), up = h - MathMax(o, c), lo = MathMin(o, c) - l;
   if (InpPinAnyDir && body <= InpBodyMax * rng &&
       ((lo >= InpWickMin * rng && up <= InpNoseMax * rng) || (up >= InpWickMin * rng && lo <= InpNoseMax * rng)))
      return 2;                                                    // a pin, direction left to the line
   if (body <= InpBodyMax * rng) {                                 // pin bars
      if (lo >= InpWickMin * rng && up <= InpNoseMax * rng) return +1;   // thumb pin
      if (up >= InpWickMin * rng && lo <= InpNoseMax * rng) return -1;
   }
   if (InpMarubozu && body >= InpMaruBody * rng) return c > o ? +1 : -1;
   return 0;
}

// the most recent swing low below `below`, searched from bar `from` back
double LastSupport(double below, int from)
{
   int p = InpSwingPivot;
   for (int i = from + p; i < from + InpSwingLook; i++) {
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

double LastResistance(double above, int from)
{
   int p = InpSwingPivot;
   for (int i = from + p; i < from + InpSwingLook; i++) {
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

// the stop for a setup candle [l,h] on side `side`
double StopFor(int side, double h, double l)
{
   double pip = InpPipPts * _Point;
   if (InpSlMode == 1) {
      double a = Buf(hAtr, 1) * InpSlAtr;
      return side > 0 ? l - a : h + a;
   }
   if (InpSlMode == 2) {
      double sw = side > 0 ? LastSupport(l, 1) : LastResistance(h, 1);
      if (sw > 0) return side > 0 ? sw - 5 * pip : sw + 5 * pip;
   }
   return side > 0 ? l - InpSlPips * pip : h + InpSlPips * pip;
}

double g_risk0 = 0;            // the entry's initial risk, for InpBeR

// true = the market is choppy by any filter that is switched on (judged on closed candles)
bool Choppy()
{
   if (InpChopCross > 0) {
      int n = 0;
      for (int i = 1; i <= InpChopCrossLook; i++) {
         bool a = Buf(hFast, i) > Buf(hSlow, i), b = Buf(hFast, i + 1) > Buf(hSlow, i + 1);
         if (a != b) n++;
      }
      if (n > InpChopCross) return true;
   }
   if (InpChopEr > 0) {
      double net = MathAbs(iClose(_Symbol, PERIOD_CURRENT, 1) - iClose(_Symbol, PERIOD_CURRENT, InpChopErLook + 1));
      double path = 0;
      for (int i = 1; i <= InpChopErLook; i++)
         path += MathAbs(iClose(_Symbol, PERIOD_CURRENT, i) - iClose(_Symbol, PERIOD_CURRENT, i + 1));
      if (path <= 0 || net / path < InpChopEr) return true;
   }
   if (InpChopSlope > 0) {
      double pips = MathAbs(Buf(hSlow, 1) - Buf(hSlow, 1 + InpChopSlopeLook)) / (InpPipPts * _Point);
      if (pips < InpChopSlope) return true;
   }
   if (InpChopAdx > 0 && Buf(hAdx, 1) < InpChopAdx) return true;
   return false;
}

bool HavePosition(ulong &ticket)
{
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol &&
          PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) { ticket = t; return true; }
   }
   return false;
}

void Manage(ulong t)
{
   if (!PositionSelectByTicket(t)) return;
   bool buy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double open = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL);
   double tp = PositionGetDouble(POSITION_TP);

   // LONG TP: any candle touching the 50 EMA — checked on the live candle, tick by tick
   if (buy && InpLongTp == 0 && InpLongMode == 0 && InpTpPips == 0) {
      double e50 = Buf(hSlow, 0);
      double hi = iHigh(_Symbol, PERIOD_CURRENT, 0), lo = iLow(_Symbol, PERIOD_CURRENT, 0);
      if (e50 > 0 && lo <= e50 && hi >= e50) {
         if (trade.PositionClose(t)) {
            g_tpEma++;
            if (InpVerbose) PrintFormat("[SAAD] LONG closed at %.2f — candle touched 50 EMA %.2f (entry %.2f)",
                                        bid, e50, open);
         }
         return;
      }
   }

   // breakeven once profit passes InpBeUsd
   if (InpBeUsd > 0) {
      bool done = buy ? (sl >= open) : (sl > 0 && sl <= open);
      if (!done) {
         double gain = InpBeMode == 0 ? PositionGetDouble(POSITION_PROFIT)
                                      : (buy ? bid - open : open - ask);
         if (gain > InpBeUsd && trade.PositionModify(t, open, tp)) {
            g_be++;
            if (InpVerbose) PrintFormat("[SAAD] breakeven: stop -> entry %.2f", open);
         }
      }
   }
   if (InpBeR > 0 && g_risk0 > 0) {
      bool done = buy ? (sl >= open) : (sl > 0 && sl <= open);
      double moved = buy ? bid - open : open - ask;
      if (!done && moved >= InpBeR * g_risk0 && trade.PositionModify(t, open, tp)) { g_be++; sl = open; }
   }
   if (InpTrailBars > 0) {
      bool inProfit = buy ? bid > open : ask < open;
      if (inProfit) {
         double lvl = buy ? DBL_MAX : 0;
         for (int k = 1; k <= InpTrailBars; k++)
            lvl = buy ? MathMin(lvl, iLow(_Symbol, PERIOD_CURRENT, k)) : MathMax(lvl, iHigh(_Symbol, PERIOD_CURRENT, k));
         double stopLvl = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
         bool better = buy ? (lvl > sl + _Point && lvl < bid - stopLvl) : ((sl == 0 || lvl < sl - _Point) && lvl > ask + stopLvl);
         if (better) trade.PositionModify(t, NormalizeDouble(lvl, _Digits), tp);
      }
   }
}

void OnTick()
{
   ulong t = 0;
   bool inTrade = HavePosition(t);
   if (inTrade) Manage(t);

   // a waiting setup fires the moment price breaks its extreme
   if (!inTrade && g_pSide != 0) {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double pip = InpPipPts * _Point;
      if (g_pSide > 0 && ask > g_pHigh) {
         double sl = StopFor(+1, g_pHigh, g_pLow);
         double ltp = 0;
         bool swingTp = (InpLongTp == 1 || InpLongMode == 1);
         if (InpTpPips > 0) ltp = ask + InpTpPips * pip;
         else if (swingTp) ltp = LastResistance(ask, 1);
         if (InpTpPips <= 0 && swingTp && ltp <= 0) {
            g_noTarget++;
            g_pSide = 0;
            return;
         }
         g_risk0 = ask - sl;
         if (trade.Buy(InpLots, _Symbol, 0, sl, ltp, "saad_long")) {
            g_entries++;
            if (InpVerbose) PrintFormat("[SAAD] LONG at %.2f broke %.2f | SL %.2f | TP = 50 EMA touch", ask, g_pHigh, sl);
         }
         g_pSide = 0;
      } else if (g_pSide < 0 && bid < g_pLow) {
         double sl = StopFor(-1, g_pHigh, g_pLow);
         double tp = InpTpPips > 0 ? bid - InpTpPips * pip : LastSupport(bid, 1);
         g_risk0 = sl - bid;
         if (tp <= 0) {
            g_noTarget++;
            if (InpVerbose) PrintFormat("[SAAD] short skipped: no support below %.2f", bid);
         } else if (trade.Sell(InpLots, _Symbol, 0, sl, tp, "saad_short")) {
            g_entries++;
            if (InpVerbose) PrintFormat("[SAAD] SHORT at %.2f broke %.2f | SL %.2f | TP last support %.2f",
                                        bid, g_pLow, sl, tp);
         }
         g_pSide = 0;
      }
   }

   datetime bar = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bar == g_lastBar) return;
   g_lastBar = bar;

   // a new candle opened: the waiting setup has one fewer candle to break
   if (g_pSide != 0 && --g_pLeft <= 0) {
      g_skips++;
      if (InpVerbose) PrintFormat("[SAAD] skipped: %s not broken within %d candles",
                                  g_pSide > 0 ? "high" : "low", InpBreakBars);
      g_pSide = 0;
   }

   MqlDateTime dt; TimeToStruct(bar, dt);
   if (dt.hour < InpSessFrom || dt.hour >= InpSessTo) return;
   if (HavePosition(t)) return;

   // the candle that just closed: a pin/marubozu on its line?
   int side = Shape(1);
   if (side == 0) return;
   double h = iHigh(_Symbol, PERIOD_CURRENT, 1), l = iLow(_Symbol, PERIOD_CURRENT, 1);
   double e9 = Buf(hFast, 1), e50 = Buf(hSlow, 1);
   if (e9 == 0 || e50 == 0) return;

   bool on9 = (l <= e9 && h >= e9), on50 = (l <= e50 && h >= e50);
   if (side == 2) side = on9 ? +1 : (on50 ? -1 : 0);       // any-direction pin: the line decides
   if (side == 0) return;
   if (Choppy()) { g_chop++; return; }
   if (InpTrendAlign && ((side > 0 && e9 <= e50) || (side < 0 && e9 >= e50))) return;
   bool longOk = false;
   if (side > 0 && InpBuys) {
      if (InpLongMode == 1) longOk = on50 && e9 > e50;           // mirror: buy the 50 EMA pullback in an uptrend
      else                  longOk = on9 && !(InpLong50Above && e50 <= h);   // rules: TP must sit above
   }
   if (longOk) {
      g_pSide = +1; g_pHigh = h; g_pLow = l; g_pLeft = InpBreakBars; g_setups++;
      if (InpVerbose) PrintFormat("[SAAD] long setup on %s EMA %.2f | waiting for > %.2f",
                                  InpLongMode == 1 ? "50" : "9", InpLongMode == 1 ? e50 : e9, h);
   } else if (side < 0 && InpSells && on50) {
      g_pSide = -1; g_pHigh = h; g_pLow = l; g_pLeft = InpBreakBars; g_setups++;
      if (InpVerbose) PrintFormat("[SAAD] short setup on 50 EMA %.2f | waiting for < %.2f", e50, l);
   }
}
