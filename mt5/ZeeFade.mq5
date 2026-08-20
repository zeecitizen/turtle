//+------------------------------------------------------------------+
//|  ZeeFade.mq5 — THE CAPITULATION FADE (Zee's theory, 2026-08-20)  |
//|                                                                  |
//|  "when a very large candle forms.. like a largest red candle of  |
//|  the day, then price is bound to reverse a bit.. a large         |
//|  investor made a selling decision.. now someone's eyeing gold's  |
//|  price n says wow an opportunity to buy at such a low price,     |
//|  they start buying, fomo kicks in, more buyers buy.. the price   |
//|  goes up. test this theory thoroughly.. on feb 11 i remember     |
//|  taking such trades too."                                        |
//|                                                                  |
//|  ENTRY: bar 1 just closed as a GIANT candle — body >= GiantMult  |
//|  x the average body of the last AvgLook bars AND >= MinBodyPts   |
//|  absolute. Giant RED -> BUY the capitulation. Giant GREEN ->     |
//|  SELL the euphoria (each side toggleable).                       |
//|  EXIT: the house geometry (SL 5 / TP 1 / hold 3) so results are  |
//|  comparable with every other court verdict.                      |
//|  Lab EA: magic 88164, tag [FADE], tickets zfade_*.               |
//+------------------------------------------------------------------+
#property copyright "Zee + Claude"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input group "── Identity ──"
input double InpLots        = 0.02;
input long   InpMagic       = 88164;

input group "── The giant candle ──"
input double InpGiantMult   = 3.0;   // body >= this x avg body of the lookback
input int    InpAvgLook     = 60;    // bars of body-average context
input double InpMinBodyPts  = 1.5;   // absolute floor — a giant must be GIANT
input bool   InpFadeRed     = true;  // giant red -> BUY (his stated side)
input bool   InpFadeGreen   = true;  // giant green -> SELL (the mirror)

input group "── Exit: the house geometry ──"
input double InpStopPts     = 5.0;
input double InpTargetPts   = 1.0;
input int    InpMaxHoldMin  = 3;
input int    InpTickets     = 2;
input int    InpMaxOpen     = 1;
input int    InpCooldownBar = 5;     // giants cluster; one fade per cluster

input group "── Safety ──"
input double InpMaxSpread   = 0.50;
input bool   InpVerbose     = false;

datetime g_last_bar = 0;
datetime g_last_fire = 0;

double bOpen (int k) { return iOpen (_Symbol, PERIOD_CURRENT, k); }
double bClose(int k) { return iClose(_Symbol, PERIOD_CURRENT, k); }
double Body  (int k) { return MathAbs(bClose(k) - bOpen(k)); }

int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   PrintFormat("[FADE] ZeeFade v1.00 — the capitulation fade. giant = body >= %.1fx avg(%d) & >= %.2f pts"
               " · SL %.1f / TP %.1f / hold %d min · magic %d",
               InpGiantMult, InpAvgLook, InpMinBodyPts, InpStopPts, InpTargetPts,
               InpMaxHoldMin, (int)InpMagic);
   return INIT_SUCCEEDED;
}

int OpenCount()
{
   int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      n++;
   }
   return n;
}

void CloseOverdue()
{
   if (InpMaxHoldMin <= 0) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if (TimeCurrent() - (datetime)PositionGetInteger(POSITION_TIME) >= InpMaxHoldMin * 60)
         trade.PositionClose(t);
   }
}

void OnTick()
{
   CloseOverdue();
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bt == g_last_bar) return;
   g_last_bar = bt;

   if (OpenCount() >= InpMaxOpen) return;
   if (g_last_fire > 0 && TimeCurrent() - g_last_fire < InpCooldownBar * PeriodSeconds()) return;

   // the giant test on the just-closed bar
   double b1 = Body(1);
   if (b1 < InpMinBodyPts) return;
   double avg = 0; int got = 0;
   for (int k = 2; k < 2 + InpAvgLook; k++) { avg += Body(k); got++; }
   if (got < InpAvgLook / 2) return;
   avg /= got;
   if (avg <= 0 || b1 < avg * InpGiantMult) return;

   bool red = bClose(1) < bOpen(1);
   int side = 0;
   if (red && InpFadeRed)        side = +1;   // capitulation -> buy the panic
   else if (!red && InpFadeGreen) side = -1;  // euphoria -> sell the chase
   if (side == 0) return;

   MqlTick tk;
   if (!SymbolInfoTick(_Symbol, tk)) return;
   if (tk.ask - tk.bid > InpMaxSpread) return;
   double px = (side > 0) ? tk.ask : tk.bid;
   double sl = (side > 0) ? px - InpStopPts   : px + InpStopPts;
   double tp = (side > 0) ? px + InpTargetPts : px - InpTargetPts;
   string tag = (side > 0) ? "zfade_buy" : "zfade_sell";
   int placed = 0;
   for (int q = 0; q < InpTickets; q++) {
      bool ok = (side > 0) ? trade.Buy(InpLots, _Symbol, 0, sl, tp, tag)
                           : trade.Sell(InpLots, _Symbol, 0, sl, tp, tag);
      if (!ok) break;
      placed++;
   }
   if (placed > 0) {
      g_last_fire = TimeCurrent();
      PrintFormat("[FADE] %s @%.2f — giant %s body %.2f (avg %.2f, %.1fx) -> %d ticket(s)",
                  side > 0 ? "BUY" : "SELL", px, red ? "RED" : "GREEN",
                  b1, avg, b1 / avg, placed);
   }
}

double OnTester()
{
   double net = TesterStatistics(STAT_PROFIT);
   int    n   = (int)TesterStatistics(STAT_TRADES);
   int    w   = (int)TesterStatistics(STAT_PROFIT_TRADES);
   double days = MathMax(1.0, (TesterStatistics(STAT_TRADES) > 0 ? 1.0 : 1.0));
   PrintFormat("[FADE] ==== %d trades · %dW/%dL (%.1f%%) · net %.2f ====",
               n, w, n - w, n > 0 ? 100.0 * w / n : 0.0, net);
   return net;
}
