//+------------------------------------------------------------------+
//| Saad_raw.mq5 v1.00 (2026-10-14) - the RAW Saad strategy, no       |
//| filters (Zee: "remove all bells n whistles like filters etc. and   |
//| just keep the core raw strategy of SAAD with trailing SL / TP").   |
//| Attach on XAUUSD M15. 1 gold pip = $0.10.                          |
//|                                                                    |
//| SETUP  a pin bar or marubozu touching the 9 EMA (closed candle);   |
//|        green = LONG, red = SHORT                                   |
//| ENTRY  the next candle breaks its high (LONG) / low (SHORT) by     |
//|        2 pips -> market order                                      |
//| STOP   35 pips beyond the setup candle                             |
//| TP1    LONG: price touches the 50 EMA. SHORT: the last support     |
//|        (swing low, 3 candles each side, 100 back)                  |
//| TRAIL  at TP1 the stop follows the market $2 away (never back).    |
//|        A LONG whose 50 EMA is already below the entry has no TP1:  |
//|        it trails 2 x ATR(14) behind its best price from candle 2.  |
//| One trade at a time. NO chop filter, size minimum, risk cap,       |
//| breakeven, partial close, day-close rule or gap cancel.            |
//+------------------------------------------------------------------+
#property copyright "turtle"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#resource "\\Indicators\\SaadEMAs.ex5"   // EMA 9 (blue) + EMA 50 (red) drawn on the chart
#define EA_COMMENT "SaadRaw v1.00"

input double InpLots        = 1.00;   // InpLots — lot size
input int    InpMagicNumber = 88303;  // InpMagicNumber — own magic (Saad_strategy_15min is 88302)
input int    InpEmaFast     = 9;      // InpEmaFast — the setup EMA
input int    InpEmaSlow     = 50;     // InpEmaSlow — the LONG target EMA
input double InpWickMin     = 0.45;   // InpWickMin — pin: long wick >= this x range
input double InpBodyMax     = 0.60;   // InpBodyMax — pin: body <= this x range
input double InpNoseMax     = 0.20;   // InpNoseMax — pin: short wick <= this x range
input double InpMaruBody    = 0.53;   // InpMaruBody — marubozu: body >= this x range
input double InpBreakPips   = 2;      // InpBreakPips — the break must clear the high / low by this many pips
input double InpSlPips      = 35;     // InpSlPips — stop beyond the setup candle
input double InpTrailUsd    = 2.0;    // InpTrailUsd — after TP1 the stop trails this $ of price from the market
input double InpTrailAtr    = 2.0;    // InpTrailAtr — LONG with no TP1: trail this x ATR(14) behind the best price
input int    InpSwingPivot  = 3;      // InpSwingPivot — SHORT last support = swing low with this many candles each side
input int    InpSwingLook   = 100;    // InpSwingLook — candles back to search for it
input double InpMinTpPips   = 5;      // InpMinTpPips — the support must be at least this far below the price
input bool   InpShowEmas    = true;   // InpShowEmas — draw EMA 9 (blue) and EMA 50 (red)
input bool   InpDraw        = true;   // InpDraw — arrows and labels on the chart (live + visual tester)

CTrade   trade;
int      hFast = INVALID_HANDLE, hSlow = INVALID_HANDLE, hAtr = INVALID_HANDLE, g_hEmas = INVALID_HANDLE;
datetime g_lastBar = 0;
// the setup waiting for its break (one candle)
int      g_pSide = 0;
double   g_pHigh = 0, g_pLow = 0;
// the open trade
ulong    g_tk = 0;
int      g_side = 0;
double   g_entry = 0, g_tp1 = 0, g_best = 0;
bool     g_noTp1 = false, g_trail = false;
datetime g_entryBar = 0;
int      g_obj = 0;
datetime g_modBlock = 0;

double Pip() { return 10 * _Point; }
double Buf(int h, int s) { double v[1]; return CopyBuffer(h, 0, s, 1, v) == 1 ? v[0] : 0.0; }
bool   Drawing() { return InpDraw && (!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_VISUAL_MODE)); }
void   Text(datetime t, double p, string s, color c)
{
   if (!Drawing()) return;
   string n = StringFormat("SRAW_%d", g_obj++);
   ObjectCreate(0, n, OBJ_TEXT, 0, t, p);
   ObjectSetString(0, n, OBJPROP_TEXT, s);
   ObjectSetInteger(0, n, OBJPROP_COLOR, c);
   ObjectSetInteger(0, n, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
}

int OnInit()
{
   hFast = iMA(_Symbol, PERIOD_CURRENT, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
   hSlow = iMA(_Symbol, PERIOD_CURRENT, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   hAtr  = iATR(_Symbol, PERIOD_CURRENT, 14);
   if (hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE || hAtr == INVALID_HANDLE) return INIT_FAILED;
   trade.SetExpertMagicNumber(InpMagicNumber);
   if (MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)) trade.LogLevel(LOG_LEVEL_ERRORS);
   if (InpShowEmas && !(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)) && ChartIndicatorGet(0, 0, "SaadEMAs") == INVALID_HANDLE) {
      g_hEmas = iCustom(_Symbol, PERIOD_CURRENT, "::Indicators\\SaadEMAs.ex5", PERIOD_CURRENT, InpEmaFast, InpEmaSlow);
      if (g_hEmas != INVALID_HANDLE) ChartIndicatorAdd(0, 0, g_hEmas);
   }
   PrintFormat("[SAAD-RAW] v1.00 %s | pin/marubozu on the %d EMA, break %.0f pips, SL %.0f pips, trail $%.2f / %.1fxATR, no filters",
               _Symbol, InpEmaFast, InpBreakPips, InpSlPips, InpTrailUsd, InpTrailAtr);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason)
{
   if (reason != REASON_CHARTCHANGE && reason != REASON_PARAMETERS) ChartIndicatorDelete(0, 0, "SaadEMAs");
}

// pin bar or marubozu on closed candle 1: +1 long, -1 short, 0 none (the candle's colour decides a pin's side)
int Shape()
{
   double o = iOpen(_Symbol, PERIOD_CURRENT, 1), c = iClose(_Symbol, PERIOD_CURRENT, 1);
   double h = iHigh(_Symbol, PERIOD_CURRENT, 1), l = iLow(_Symbol, PERIOD_CURRENT, 1);
   double rng = h - l;
   if (rng <= 0) return 0;
   double body = MathAbs(c - o), up = h - MathMax(o, c), lo = MathMin(o, c) - l;
   bool pin  = body <= InpBodyMax * rng && ((lo >= InpWickMin * rng && up <= InpNoseMax * rng) || (up >= InpWickMin * rng && lo <= InpNoseMax * rng));
   bool maru = !pin && body >= InpMaruBody * rng;
   if (!pin && !maru) return 0;
   return c >= o ? 1 : -1;
}

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

bool Modify(double sl)
{
   if (!PositionSelectByTicket(g_tk)) return false;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double lvl = MathMax((double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL)) * _Point;
   sl = NormalizeDouble(sl, _Digits);
   if (g_side > 0 ? sl >= bid - lvl : sl <= ask + lvl) return false;
   if (TimeCurrent() < g_modBlock) return false;                       // the broker refused the last change: wait
   if (trade.PositionModify(g_tk, sl, 0)) return true;
   uint rc = trade.ResultRetcode();
   g_modBlock = TimeCurrent() + ((rc == TRADE_RETCODE_MARKET_CLOSED || rc == TRADE_RETCODE_TRADE_DISABLED) ? 60 : 3);
   return false;
}

void Enter(int side)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl = side > 0 ? g_pLow - InpSlPips * Pip() : g_pHigh + InpSlPips * Pip();
   double tp1 = 0;
   bool noTp1 = false;
   if (side < 0) {
      tp1 = LastSupport(bid - InpMinTpPips * Pip());
      if (tp1 <= 0) return;                                   // nothing below to aim for
   } else
      noTp1 = Buf(hSlow, 0) < ask + InpMinTpPips * Pip();       // the 50 EMA is already below / at the entry
   bool ok = side > 0 ? trade.Buy(InpLots, _Symbol, 0, NormalizeDouble(sl, _Digits), 0, EA_COMMENT + " BUY")
                      : trade.Sell(InpLots, _Symbol, 0, NormalizeDouble(sl, _Digits), 0, EA_COMMENT + " SELL");
   if (!ok) return;
   ulong deal = trade.ResultDeal();
   g_tk = (deal > 0 && HistoryDealSelect(deal)) ? (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID) : trade.ResultOrder();
   g_side = side; g_entry = trade.ResultPrice() > 0 ? trade.ResultPrice() : (side > 0 ? ask : bid);
   g_tp1 = tp1; g_noTp1 = noTp1; g_trail = false; g_best = g_entry; g_entryBar = iTime(_Symbol, PERIOD_CURRENT, 0);
   Text(TimeCurrent(), g_entry, StringFormat("%s @ %.2f  SL %.2f  TP1 %s", side > 0 ? "BUY" : "SELL", g_entry, sl,
        side < 0 ? DoubleToString(tp1, 2) + " (last support)" : noTp1 ? "none: 2xATR trail" : "50 EMA touch"), side > 0 ? clrGreen : clrRed);
}

// every tick: TP1 and the $ trail
void Manage()
{
   if (g_tk == 0) return;
   if (!PositionSelectByTicket(g_tk)) { g_tk = 0; g_side = 0; return; }
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double cur = PositionGetDouble(POSITION_SL);
   if (!g_trail) {
      bool hit = g_side > 0 ? (!g_noTp1 && Buf(hSlow, 0) > g_entry && bid >= Buf(hSlow, 0)) : (bid <= g_tp1);
      if (hit) { g_trail = true; Text(TimeCurrent(), bid, "TP1 -> trail $" + DoubleToString(InpTrailUsd, 2), clrBlue); }
   }
   if (g_trail) {
      double want = NormalizeDouble(g_side > 0 ? bid - InpTrailUsd : ask + InpTrailUsd, _Digits);
      if (g_side > 0 ? want >= cur + 10 * _Point : (cur == 0 || want <= cur - 10 * _Point)) Modify(want);
   }
}

// each new candle: the no-TP1 LONG's ATR trail
void ManageBar()
{
   if (g_tk == 0 || g_trail || !g_noTp1 || !PositionSelectByTicket(g_tk)) return;
   if (iTime(_Symbol, PERIOD_CURRENT, 1) < g_entryBar) return;              // from the candle after the entry
   g_best = MathMax(g_best, iHigh(_Symbol, PERIOD_CURRENT, 1));
   double lvl = g_best - InpTrailAtr * Buf(hAtr, 1), cur = PositionGetDouble(POSITION_SL);
   if (lvl > cur + _Point && lvl < iClose(_Symbol, PERIOD_CURRENT, 1)) Modify(lvl);
}

void OnTick()
{
   Manage();
   datetime bar = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bar != g_lastBar) {
      g_lastBar = bar;
      if (Bars(_Symbol, PERIOD_CURRENT) < InpEmaSlow * 2 + 20) return;
      ManageBar();
      g_pSide = 0;                                            // a setup gets exactly one candle to break
      if (g_tk == 0) {
         int side = Shape();
         double e9 = Buf(hFast, 1), h = iHigh(_Symbol, PERIOD_CURRENT, 1), l = iLow(_Symbol, PERIOD_CURRENT, 1);
         if (side != 0 && e9 > 0 && l <= e9 && h >= e9) {
            g_pSide = side; g_pHigh = h; g_pLow = l;
            Text(iTime(_Symbol, PERIOD_CURRENT, 1), side > 0 ? h : l, side > 0 ? "SETUP LONG" : "SETUP SHORT", clrBlack);
         }
      }
   }
   if (g_pSide != 0 && g_tk == 0) {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if (g_pSide > 0 ? bid > g_pHigh + InpBreakPips * Pip() : bid < g_pLow - InpBreakPips * Pip()) {
         int s = g_pSide; g_pSide = 0;
         Enter(s);
      }
   }
}
