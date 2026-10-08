//+------------------------------------------------------------------+
//|  SignalReplay.mq5 — trade the TradingView indicator's own        |
//|  BUY/SELL signals on the broker's real ticks (2026-10-09).       |
//|                                                                  |
//|  The signals are made on TradingView (OANDA price + OANDA volume, |
//|  as LAWS.md requires) and exported by test_tv_indicator_on_mt5.py |
//|  to Common\Files\tv_signals.csv. This EA never re-derives a      |
//|  signal, so it cannot quietly differ from what is on the chart.  |
//|                                                                  |
//|  Per signal: during the signal's minute (server time = UTC +     |
//|  InpOffsetSec), wait for THIS broker's price to cross the high   |
//|  (BUY) / low (SELL) of the same UHV candle on THIS broker's      |
//|  chart, enter at market, put the take-profit and stop on the     |
//|  server measured from the actual fill, close at market when the  |
//|  time window ends. A minute without a cross = "missed".          |
//|                                                                  |
//|  InpExportBars: instead write this broker's M1 candles to        |
//|  Common\Files\pxbt_m1.csv, so the script can find the time offset |
//|  by matching them against the OANDA candles.                     |
//+------------------------------------------------------------------+
#property version   "1.00"
#property strict
#property tester_file "tv_signals.csv"   // shipped to optimisation agents (they cannot see Common\Files)
#include <Trade/Trade.mqh>
CTrade trade;

input string InpFile       = "tv_signals.csv";
input int    InpOffsetSec  = 0;       // broker server time minus UTC, seconds
input double InpLots       = 0.10;
input double InpTargetUSD  = 1.00;    // server take-profit, $ profit on InpLots (0 = none)
input double InpSLUSD      = 0;       // server stop-loss, $ loss on InpLots (0 = none)
input int    InpExtraBars  = 1;       // time window: the signal candle + this many more
input bool   InpExportBars = false;   // calibration mode: export this broker's M1 candles
input int    InpEntryMode  = 0;       // 0 = on this broker's cross inside the signal minute (can enter BEFORE the indicator's cross)
                                      // 1 = at the first tick AFTER the signal minute: the indicator has certainly signalled (no look-ahead)
input int    InpMagic      = 77201;

long     s_t[];      // signal candle open, UTC seconds
int      s_d[];      // +1 BUY, -1 SELL
long     s_u[];      // UHV candle open, UTC seconds
double   s_x[];      // TradingView trigger price (for the report only)
int      s_n = 0, s_i = 0;
ulong    g_pos = 0;
datetime g_deadline = 0;
bool     g_buy = true;
int      g_taken = 0, g_missed = 0, g_w = 0, g_n = 0, g_nb = 0, g_wb = 0, g_rej = 0;
double   g_net = 0, g_slipSum = 0;
int      fh = INVALID_HANDLE;

int OnInit() {
   trade.SetExpertMagicNumber(InpMagic);
   if (InpExportBars) return INIT_SUCCEEDED;
   int h = FileOpen(InpFile, FILE_READ | FILE_SHARE_READ | FILE_CSV | FILE_ANSI, ',');                      // agent copy (tester_file)
   if (h == INVALID_HANDLE) h = FileOpen(InpFile, FILE_READ | FILE_SHARE_READ | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if (h == INVALID_HANDLE) { PrintFormat("[REPLAY] cannot open %s (error %d)", InpFile, GetLastError()); return INIT_FAILED; }
   while (!FileIsEnding(h)) {
      string a = FileReadString(h); if (a == "" || a == "t") { FileReadString(h); FileReadString(h); FileReadString(h); continue; }
      long t = StringToInteger(a); int d = (int)StringToInteger(FileReadString(h));
      long u = StringToInteger(FileReadString(h)); double x = StringToDouble(FileReadString(h));
      ArrayResize(s_t, s_n + 1); ArrayResize(s_d, s_n + 1); ArrayResize(s_u, s_n + 1); ArrayResize(s_x, s_n + 1);
      s_t[s_n] = t; s_d[s_n] = d; s_u[s_n] = u; s_x[s_n] = x; s_n++;
   }
   FileClose(h);
   PrintFormat("[REPLAY] %d signals loaded, offset %d s, TP $%.2f SL $%.2f window +%d", s_n, InpOffsetSec, InpTargetUSD, InpSLUSD, InpExtraBars);
   return INIT_SUCCEEDED;
}

void Count(ulong pos, bool buy) {
   double net = 0;
   if (HistorySelectByPosition(pos))
      for (int i = 0; i < HistoryDealsTotal(); i++) {
         ulong d = HistoryDealGetTicket(i);
         net += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_COMMISSION) + HistoryDealGetDouble(d, DEAL_SWAP);
      }
   bool won = InpTargetUSD > 0 ? net >= InpTargetUSD - 0.011 : net > 0;
   g_n++; g_w += won ? 1 : 0; g_net += net;
   if (buy) { g_nb++; g_wb += won ? 1 : 0; }
}

void OnTick() {
   datetime now = TimeCurrent();
   if (InpExportBars) {
      datetime b = iTime(_Symbol, PERIOD_M1, 1);
      static datetime last = 0;
      if (b != last && b > 0) {
         last = b;
         if (fh == INVALID_HANDLE) fh = FileOpen("pxbt_m1.csv", FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
         FileWrite(fh, (long)b, iOpen(_Symbol, PERIOD_M1, 1), iHigh(_Symbol, PERIOD_M1, 1), iLow(_Symbol, PERIOD_M1, 1), iClose(_Symbol, PERIOD_M1, 1));
      }
      return;
   }
   // manage the open position
   if (g_pos != 0) {
      if (!PositionSelectByTicket(g_pos)) { Count(g_pos, g_buy); g_pos = 0; }            // closed on the server (TP/SL)
      else if (now >= g_deadline) { trade.PositionClose(g_pos); Count(g_pos, g_buy); g_pos = 0; }
   }
   // skip signals whose entry window has passed
   int late = InpEntryMode == 1 ? 120 : 60;
   while (s_i < s_n && now >= (datetime)(s_t[s_i] + InpOffsetSec + late)) { g_missed++; s_i++; }
   if (s_i >= s_n || g_pos != 0) return;
   datetime st = (datetime)(s_t[s_i] + InpOffsetSec);
   if (now < st) return;
   if (InpEntryMode == 1 && now < st + 60) return;              // wait until the signal minute is over
   // the same UHV candle on this broker's chart
   datetime ut = (datetime)(s_u[s_i] + InpOffsetSec);
   int sh = iBarShift(_Symbol, PERIOD_M1, ut, true);
   if (sh < 0) { g_missed++; s_i++; return; }
   bool buy = s_d[s_i] > 0;
   double lvl = buy ? iHigh(_Symbol, PERIOD_M1, sh) : iLow(_Symbol, PERIOD_M1, sh);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if (InpEntryMode == 0 && (buy ? bid <= lvl : bid >= lvl)) return;   // not crossed yet this minute
   bool ok = buy ? trade.Buy(InpLots, _Symbol) : trade.Sell(InpLots, _Symbol);
   s_i++;
   if (!ok) { g_missed++; return; }
   g_pos = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (PositionGetInteger(POSITION_MAGIC) == InpMagic) { g_pos = t; break; }
   }
   if (g_pos == 0) { g_missed++; return; }
   g_taken++; g_buy = buy;
   double fill = PositionGetDouble(POSITION_PRICE_OPEN);
   g_slipSum += buy ? fill - (lvl + (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - bid)) : lvl - fill;
   double cs = InpLots * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double tp = InpTargetUSD > 0 ? NormalizeDouble(buy ? fill + InpTargetUSD / cs : fill - InpTargetUSD / cs, _Digits) : 0;
   double sl = InpSLUSD > 0 ? NormalizeDouble(buy ? fill - InpSLUSD / cs : fill + InpSLUSD / cs, _Digits) : 0;
   if ((tp != 0 || sl != 0) && !trade.PositionModify(g_pos, sl, tp)) g_rej++;
   g_deadline = st + (InpExtraBars + 1 + InpEntryMode) * 60;
}

void OnDeinit(const int r) { if (fh != INVALID_HANDLE) FileClose(fh); }

double OnTester() {
   if (InpExportBars) { Print("[REPLAY] bars exported"); return 0; }
   PrintFormat("[REPLAY] signals %d | taken %d | missed %d (no cross on this broker in that minute) | won %d = %.1f%% | BUY %d/%d SELL %d/%d | net $%.2f = $%.3f/trade | TP/SL placement refused %d",
               s_n, g_taken, g_missed, g_w, g_n > 0 ? 100.0 * g_w / g_n : 0, g_wb, g_nb, g_w - g_wb, g_n - g_nb, g_net,
               g_n > 0 ? g_net / g_n : 0, g_rej);
   return g_n > 0 ? g_net / g_n : 0;
}
