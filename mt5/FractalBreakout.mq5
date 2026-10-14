//+------------------------------------------------------------------+
//| FractalBreakout.mq5 — Williams Fractals (period 25) breakout, M5  |
//|                                                                  |
//| Zee, 2026-10-15: "there is william fractals indicator .. on       |
//| tradingview i've applied it with setting Periods 25... it draws   |
//| these arrows on the 5 min timeframe. i want to backtest a         |
//| strategy based on this"                                           |
//| Entry chosen: "Breakout of fractal level".                        |
//| Exit chosen:  "trailing stop loss.. and tp is when trailing sl is |
//|               hit"                                                |
//|                                                                  |
//| THE ARROW IS LATE. A period-25 fractal needs 25 CLOSED bars after |
//| the pivot before it exists — on M5 that is 2h05m. TradingView     |
//| paints it back on the pivot bar (offset -n), so the chart shows   |
//| it where nobody could have seen it. This EA only arms a level     |
//| once it is confirmed, exactly when TV would first draw it.        |
//|                                                                  |
//| ENTRY  BuyStop at the newest confirmed up-fractal high (+buffer),  |
//|        SellStop at the newest confirmed down-fractal low (-buffer).|
//|        One position at a time; a level is used once — filled, or   |
//|        traded through while we were busy — and never re-armed.     |
//| EXIT   Trailing stop only, no target.                              |
//|        InpTrailMode 0 = fixed $ distance behind price              |
//|        InpTrailMode 1 = newest confirmed opposite fractal          |
//| CONTROL InpEntryMode 1 = no rules: alternate buy/sell every        |
//|        InpCtrlEveryBars bars with the IDENTICAL trailing exit.     |
//|        If the control matches the fractals, the exit is the edge.  |
//|                                                                  |
//| magic 88410 — TEST, never on a live chart until MT5 says so.       |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input double InpLots          = 0.10;
input int    InpMagicNumber   = 88410;
input int    InpFractalN      = 25;     // bars each side, as Zee's TV setting "Periods 25"
input double InpBufferUsd     = 0.0;    // stop order this far beyond the fractal level ($)
input int    InpEntryMode     = 0;      // 0 = fractal breakout, 1 = no-rules control
input int    InpCtrlEveryBars = 24;     // control: one entry every N bars when flat (24 = 2h on M5)
input int    InpTrailMode     = 0;      // 0 = fixed $ trail, 1 = opposite-fractal trail
input double InpTrailUsd      = 5.0;    // mode 0: trail distance; also initial SL in mode 0
input double InpTrailStepUsd  = 0.50;   // only move the stop when it improves by this much
input double InpMaxInitSLUsd  = 30.0;   // mode 1: cap on the initial stop distance (0 = none)
input bool   InpLogFractals   = false;  // print each confirmed fractal (for checking against TV)

double   g_upLvl = 0, g_dnLvl = 0;       // newest confirmed fractal levels
bool     g_upUsed = true, g_dnUsed = true;
datetime g_lastBar = 0;
int      g_barsFlat = 0;
bool     g_ctrlBuy = true;

bool IsUpFractal(int n) {
   int p = n + 1;
   double h = iHigh(_Symbol, PERIOD_CURRENT, p);
   for (int i = 1; i <= n; i++)          if (iHigh(_Symbol, PERIOD_CURRENT, i) >= h) return false;
   for (int i = p + 1; i <= 2 * n + 1; i++) if (iHigh(_Symbol, PERIOD_CURRENT, i) >  h) return false;
   return true;
}

bool IsDnFractal(int n) {
   int p = n + 1;
   double l = iLow(_Symbol, PERIOD_CURRENT, p);
   for (int i = 1; i <= n; i++)          if (iLow(_Symbol, PERIOD_CURRENT, i) <= l) return false;
   for (int i = p + 1; i <= 2 * n + 1; i++) if (iLow(_Symbol, PERIOD_CURRENT, i) <  l) return false;
   return true;
}

bool MyPosition(long &type, double &sl, double &open, ulong &ticket) {
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      type = PositionGetInteger(POSITION_TYPE);
      sl = PositionGetDouble(POSITION_SL);
      open = PositionGetDouble(POSITION_PRICE_OPEN);
      ticket = t;
      return true;
   }
   return false;
}

ulong MyOrder(ENUM_ORDER_TYPE type, double &price) {
   for (int i = OrdersTotal() - 1; i >= 0; i--) {
      ulong t = OrderGetTicket(i);
      if (t == 0 || !OrderSelect(t)) continue;
      if (OrderGetInteger(ORDER_MAGIC) != InpMagicNumber || OrderGetString(ORDER_SYMBOL) != _Symbol) continue;
      if ((ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE) != type) continue;
      price = OrderGetDouble(ORDER_PRICE_OPEN);
      return t;
   }
   return 0;
}

void DeleteOrders() {
   double px;
   ulong t;
   while ((t = MyOrder(ORDER_TYPE_BUY_STOP, px)) != 0)  if (!trade.OrderDelete(t)) break;
   while ((t = MyOrder(ORDER_TYPE_SELL_STOP, px)) != 0) if (!trade.OrderDelete(t)) break;
}

double MinDist() {
   return (SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) + 1) * _Point;
}

//| Initial stop for an entry at `entry`.
double InitialSL(bool buy, double entry) {
   double dist = InpTrailUsd;
   if (InpTrailMode == 1) {
      double opp = buy ? g_dnLvl : g_upLvl;
      if (opp > 0 && (buy ? opp < entry : opp > entry)) dist = MathAbs(entry - opp);
      if (InpMaxInitSLUsd > 0) dist = MathMin(dist, InpMaxInitSLUsd);
   }
   dist = MathMax(dist, MinDist());
   return NormalizeDouble(buy ? entry - dist : entry + dist, _Digits);
}

//| Keep exactly one stop order per armed, unused level while flat.
void ManageOrder(bool buy) {
   ENUM_ORDER_TYPE type = buy ? ORDER_TYPE_BUY_STOP : ORDER_TYPE_SELL_STOP;
   double lvl = buy ? g_upLvl : g_dnLvl;
   bool used = buy ? g_upUsed : g_dnUsed;
   double want = NormalizeDouble(buy ? lvl + InpBufferUsd : lvl - InpBufferUsd, _Digits);
   double have = 0;
   ulong t = MyOrder(type, have);
   if (t != 0 && (used || MathAbs(have - want) > _Point / 2)) {
      trade.OrderDelete(t);
      t = 0;
   }
   if (t != 0 || used || lvl <= 0) return;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if (buy ? ask >= want - MinDist() : bid <= want + MinDist()) {  // already through: spent
      if (buy) g_upUsed = true; else g_dnUsed = true;
      return;
   }
   double sl = InitialSL(buy, want);
   bool ok = buy ? trade.BuyStop (InpLots, want, _Symbol, sl, 0, ORDER_TIME_GTC, 0, "frac_buy")
                 : trade.SellStop(InpLots, want, _Symbol, sl, 0, ORDER_TIME_GTC, 0, "frac_sell");
   if (!ok && InpLogFractals) PrintFormat("[FRAC] stop order failed %d", trade.ResultRetcode());
}

void Trail(long type, double sl, double open, ulong ticket) {
   bool buy = (type == POSITION_TYPE_BUY);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double px = buy ? bid : ask;
   double nsl;
   if (InpTrailMode == 1) {
      nsl = buy ? g_dnLvl - InpBufferUsd : g_upLvl + InpBufferUsd;
      if (nsl <= 0) return;
   } else {
      nsl = buy ? px - InpTrailUsd : px + InpTrailUsd;
   }
   nsl = NormalizeDouble(nsl, _Digits);
   if (buy ? nsl > px - MinDist() : nsl < px + MinDist()) return;
   bool better = (sl == 0) || (buy ? nsl >= sl + InpTrailStepUsd : nsl <= sl - InpTrailStepUsd);
   if (better) trade.PositionModify(ticket, nsl, 0);
}

void OnNewBar() {
   int n = InpFractalN;
   if (Bars(_Symbol, PERIOD_CURRENT) < 2 * n + 3) return;
   if (IsUpFractal(n)) {
      g_upLvl = iHigh(_Symbol, PERIOD_CURRENT, n + 1);
      g_upUsed = false;
      if (InpLogFractals)
         PrintFormat("[FRAC] UP   pivot %s  level %.2f  confirmed %s", TimeToString(iTime(_Symbol, PERIOD_CURRENT, n + 1)),
                     g_upLvl, TimeToString(iTime(_Symbol, PERIOD_CURRENT, 0)));
   }
   if (IsDnFractal(n)) {
      g_dnLvl = iLow(_Symbol, PERIOD_CURRENT, n + 1);
      g_dnUsed = false;
      if (InpLogFractals)
         PrintFormat("[FRAC] DOWN pivot %s  level %.2f  confirmed %s", TimeToString(iTime(_Symbol, PERIOD_CURRENT, n + 1)),
                     g_dnLvl, TimeToString(iTime(_Symbol, PERIOD_CURRENT, 0)));
   }
}

int OnInit() {
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(50);
   PrintFormat("[FRAC] FractalBreakout v1.00  N=%d  entry=%s  trail=%s %.2f",
               InpFractalN, InpEntryMode == 0 ? "fractal" : "CONTROL", InpTrailMode == 0 ? "fixed$" : "fractal", InpTrailUsd);
   return INIT_SUCCEEDED;
}

void OnTick() {
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   bool newBar = (bt != g_lastBar);
   if (newBar) {
      g_lastBar = bt;
      OnNewBar();
   }

   long type; double sl, open; ulong ticket;
   if (MyPosition(type, sl, open, ticket)) {
      g_barsFlat = 0;
      DeleteOrders();
      // a level price walks through while we are in a trade is spent, not saved for later
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if (!g_upUsed && ask >= g_upLvl + InpBufferUsd) g_upUsed = true;
      if (!g_dnUsed && bid <= g_dnLvl - InpBufferUsd) g_dnUsed = true;
      Trail(type, sl, open, ticket);
      return;
   }

   if (InpEntryMode == 1) {
      if (!newBar) return;
      if (++g_barsFlat < InpCtrlEveryBars) return;
      g_barsFlat = 0;
      bool buy = g_ctrlBuy;
      g_ctrlBuy = !g_ctrlBuy;
      double entry = buy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double isl = InitialSL(buy, entry);
      if (buy) trade.Buy(InpLots, _Symbol, 0, isl, 0, "ctrl_buy");
      else     trade.Sell(InpLots, _Symbol, 0, isl, 0, "ctrl_sell");
      return;
   }

   ManageOrder(true);
   ManageOrder(false);
}

void OnTradeTransaction(const MqlTradeTransaction &tx, const MqlTradeRequest &req, const MqlTradeResult &res) {
   if (tx.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if (!HistoryDealSelect(tx.deal)) return;
   if (HistoryDealGetInteger(tx.deal, DEAL_MAGIC) != InpMagicNumber) return;
   if (HistoryDealGetInteger(tx.deal, DEAL_ENTRY) != DEAL_ENTRY_IN) return;
   if (HistoryDealGetInteger(tx.deal, DEAL_TYPE) == DEAL_TYPE_BUY) g_upUsed = true;
   else g_dnUsed = true;
}

double OnTester() {
   return TesterStatistics(STAT_PROFIT);
}
