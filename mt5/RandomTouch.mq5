//+------------------------------------------------------------------+
//|  RandomTouch.mq5 — the indicator's "random entry" baseline, on    |
//|  real ticks with the broker's real spread (2026-10-09).           |
//|                                                                  |
//|  The TradingView panel claims a random entry reaches "$1 profit  |
//|  on 0.1 lot within the candle + 1 minute" 84% of the time. Zee:  |
//|  "if u can make an EA score it randomly, that would literally    |
//|  break the internet." This EA settles it in MT5, not Python.     |
//|                                                                  |
//|  Rule, exactly as on the panel:                                  |
//|   * entry: at the first tick of a randomly chosen new M1 candle  |
//|     (its open), random direction, InpLots;                       |
//|   * WIN: the moment the position's profit after commission       |
//|     reaches InpTargetUSD, it is closed;                          |
//|   * otherwise closed at market when the NEXT candle ends.        |
//|  One position at a time. Fixed seed, so every run is repeatable. |
//+------------------------------------------------------------------+
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>
CTrade trade;

input double InpLots       = 0.10;   // lots
input double InpTargetUSD  = 1.00;   // win = profit after commission reaches this ($)
input int    InpEveryN     = 3;      // enter on ~1 of every N new candles (random)
input int    InpExtraBars  = 1;      // window = the entry candle + this many more candles
input int    InpSeed       = 42;     // random seed (repeatable)
input int    InpMagic      = 77101;
input double InpSLUSD      = 0;      // server stop-loss from the fill, $ on InpLots (0 = none)
input int    InpDir        = 0;      // 0 random, 1 always BUY, -1 always SELL, 2 follow last candle colour, -2 fade it
input bool   InpServerTP   = false;  // true = place a real take-profit with the order (fills on the server, no exit delay)

datetime g_lastBar = 0, g_deadline = 0;
ulong    g_pos = 0;
double   g_comm = 0;                 // round-trip commission estimate for the open position
int      g_n = 0, g_w = 0, g_nb = 0, g_wb = 0;
double   g_net = 0;
double   g_sprSum = 0, g_comSum = 0, g_bestSum = 0, g_best = 0;
int      g_hit0 = 0;      // reached ANY profit after costs (> $0) before the deadline
double   g_entryPx = 0;
int      g_rejected = 0, g_tpHits = 0;
bool     g_buy = true;

int OnInit() { MathSrand(InpSeed); trade.SetExpertMagicNumber(InpMagic); return INIT_SUCCEEDED; }

double EntryCommission(ulong ticket) {
   // the entry deal's commission; the exit is charged the same, so double it
   if (!HistorySelectByPosition(ticket)) return 0;
   double c = 0;
   for (int i = 0; i < HistoryDealsTotal(); i++) c += HistoryDealGetDouble(HistoryDealGetTicket(i), DEAL_COMMISSION);
   return 2.0 * c;   // commission is negative
}

void CloseAndCount(bool buy) {
   if (!PositionSelectByTicket(g_pos)) { g_pos = 0; return; }
   trade.PositionClose(g_pos);
   double net = 0;
   if (HistorySelectByPosition(g_pos))
      for (int i = 0; i < HistoryDealsTotal(); i++) {
         ulong d = HistoryDealGetTicket(i);
         net += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_COMMISSION) + HistoryDealGetDouble(d, DEAL_SWAP);
      }
   bool won = net >= InpTargetUSD - 1e-9;
   g_bestSum += g_best; g_hit0 += g_best > 0 ? 1 : 0;
   g_n++; g_w += won ? 1 : 0; g_net += net;
   if (buy) { g_nb++; g_wb += won ? 1 : 0; }
   g_pos = 0;
}

void OnTick() {
   if (g_pos != 0 && !PositionSelectByTicket(g_pos)) {
      double net = 0; bool b = g_buy;
      if (HistorySelectByPosition(g_pos))
         for (int i = 0; i < HistoryDealsTotal(); i++) {
            ulong d = HistoryDealGetTicket(i);
            net += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_COMMISSION) + HistoryDealGetDouble(d, DEAL_SWAP);
         }
      bool won = net >= InpTargetUSD - 0.011;   // TP from the fill: $1.00 within a cent of rounding
      g_n++; g_w += won ? 1 : 0; g_net += net; g_tpHits++;
      if (b) { g_nb++; g_wb += won ? 1 : 0; }
      g_bestSum += net; g_hit0 += net > 0 ? 1 : 0;
      g_pos = 0;
   }
   if (g_pos != 0 && PositionSelectByTicket(g_pos)) {
      bool buy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      double pnl = PositionGetDouble(POSITION_PROFIT) + g_comm;     // profit if closed at this tick
      g_best = MathMax(g_best, pnl);
      if ((!InpServerTP && pnl >= InpTargetUSD) || TimeCurrent() >= g_deadline) CloseAndCount(buy);
   }
   datetime bar = iTime(_Symbol, PERIOD_M1, 0);
   if (bar == g_lastBar) return;
   g_lastBar = bar;
   if (g_pos != 0) return;
   if (MathRand() % MathMax(InpEveryN, 1) != 0) return;
   bool lastGreen = iClose(_Symbol, PERIOD_M1, 1) >= iOpen(_Symbol, PERIOD_M1, 1);
   bool buy = InpDir == 2 ? lastGreen : InpDir == -2 ? !lastGreen : InpDir > 0 ? true : InpDir < 0 ? false : (MathRand() % 2) == 0;
   if (InpDir != 0) MathRand();   // keep the entry-candle choices identical across directions
   g_buy = buy;
   double spr = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double tp = 0;
   if (InpServerTP) {
      // $InpTargetUSD on InpLots: price distance = target / (lots * contract size), measured from the fill side
      double dist = InpTargetUSD / (InpLots * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE));
      tp = buy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) + dist : SymbolInfoDouble(_Symbol, SYMBOL_BID) - dist;
      tp = NormalizeDouble(tp, _Digits);
   }
   bool ok = buy ? trade.Buy(InpLots, _Symbol) : trade.Sell(InpLots, _Symbol);
   if (!ok) g_rejected++;
   if (!ok) return;
   g_pos = trade.ResultOrder();
   if (!PositionSelectByTicket(g_pos)) {
      // ResultOrder is the order ticket; find the position it opened
      g_pos = 0;
      for (int i = PositionsTotal() - 1; i >= 0; i--) {
         ulong t = PositionGetTicket(i);
         if (PositionGetInteger(POSITION_MAGIC) == InpMagic) { g_pos = t; break; }
      }
   }
   g_comm = EntryCommission(g_pos);
   if (InpServerTP && g_pos != 0 && PositionSelectByTicket(g_pos)) {
      double dist = InpTargetUSD / (InpLots * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE));
      double fill = PositionGetDouble(POSITION_PRICE_OPEN);
      double tpx = NormalizeDouble(buy ? fill + dist : fill - dist, _Digits);
      double sld = InpSLUSD / (InpLots * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE));
      double slx = InpSLUSD > 0 ? NormalizeDouble(buy ? fill - sld : fill + sld, _Digits) : 0;
      if (!trade.PositionModify(g_pos, slx, tpx)) g_rejected++;
   }
   g_sprSum += spr; g_comSum += g_comm; g_best = -1e9;
   g_deadline = bar + (InpExtraBars + 1) * 60;   // end of the next candle
}

double OnTester() {
   PrintFormat("[RANDOMTOUCH] trades %d  won %d  = %.1f%%  | BUY %d/%d  SELL %d/%d | net $%.2f ($%.3f/trade) | target $%.2f lots %.2f window +%d",
               g_n, g_w, g_n > 0 ? 100.0 * g_w / g_n : 0, g_wb, g_nb, g_w - g_wb, g_n - g_nb, g_net,
               g_n > 0 ? g_net / g_n : 0, InpTargetUSD, InpLots, InpExtraBars);
   if (g_n > 0)
      PrintFormat("[RANDOMTOUCH] avg spread at entry %.3f | avg round-trip commission $%.2f | avg best profit reached $%.2f | reached ANY profit after costs: %.1f%%",
                  g_sprSum / g_n, g_comSum / g_n, g_bestSum / g_n, 100.0 * g_hit0 / g_n);
   PrintFormat("[RANDOMTOUCH] server TP %s | closed by TP %d | orders rejected %d | broker stop level %d points, freeze level %d points, point %.3f",
               InpServerTP ? "ON" : "off", g_tpHits, g_rejected, (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL),
               (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL), _Point);
   return g_n > 0 ? g_net / g_n : -1e9;   // optimizer criterion: net $ per trade
}
