//+------------------------------------------------------------------+
//| TradeReplay.mq5 - Zee 2026-10-22: "export a list of trades from the tester and feed to MT5 to see if MT5 holds"
//| Reads a trade list (Common\Files\<InpFile>: entry time, side, exit time - server time, one trade per line) and in the
//| Strategy Tester opens each trade at its entry second and closes it at its exit second, at MT5's real prices. No decisions
//| of its own: it prices the Turtle TV Tester's trades with real ticks. TEST - Strategy Tester only, never attach to an account.
//+------------------------------------------------------------------+
#property copyright "turtle"
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>

input string InpFile  = "replay_trades.csv";   // InpFile - in Common\Files: entry_epoch,side,exit_epoch,lots
input int    InpMagic = 88399;                 // InpMagic
input int    InpLateSec = 90;                  // InpLateSec - an entry more than this late (market closed) is skipped
input bool   InpAtPrice = true;                // InpAtPrice - close when the real price reaches the tester's exit price (deadline: its exit time + 60 s)

CTrade trade;
long g_in[], g_out[]; int g_side[]; double g_lots[], g_px[], g_en[];
int g_n = 0, g_next = 0, g_open = -1, g_skipped = 0, g_done = 0;
ulong g_ticket = 0;

int OnInit()
{
   int h = FileOpen(InpFile, FILE_READ | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if (h == INVALID_HANDLE) { Print("TradeReplay: cannot open ", InpFile); return INIT_FAILED; }
   while (!FileIsEnding(h)) {
      string a = FileReadString(h); if (a == "") break;
      long ti = StringToInteger(a); int sd = (int)StringToInteger(FileReadString(h)); long to = StringToInteger(FileReadString(h)); double lt = StringToDouble(FileReadString(h)); double en = StringToDouble(FileReadString(h)); double px = StringToDouble(FileReadString(h));
      ArrayResize(g_in, g_n + 1); ArrayResize(g_out, g_n + 1); ArrayResize(g_side, g_n + 1); ArrayResize(g_lots, g_n + 1); ArrayResize(g_px, g_n + 1); ArrayResize(g_en, g_n + 1); g_px[g_n] = px; g_en[g_n] = en;
      g_in[g_n] = ti; g_side[g_n] = sd; g_out[g_n] = to; g_lots[g_n] = lt; g_n++;
   }
   FileClose(h);
   trade.SetExpertMagicNumber(InpMagic);
   PrintFormat("TradeReplay: %d trades loaded", g_n);
   return INIT_SUCCEEDED;
}

void OnTick()
{
   long now = (long)TimeCurrent();
   bool hit = false;
   if (g_open >= 0 && InpAtPrice) {
      int i = g_open; double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      bool profit = (g_px[i] - g_en[i]) * g_side[i] > 0;              // the tester's exit was a gain: wait for the price to get there
      if (profit) hit = g_side[i] > 0 ? bid >= g_px[i] : ask <= g_px[i];
      else hit = g_side[i] > 0 ? bid <= g_px[i] : ask >= g_px[i];
   }
   if (g_open >= 0 && (hit || now >= g_out[g_open] + (InpAtPrice ? 60 : 0))) {                    // the tester's exit second: out at the real price
      if (PositionSelectByTicket(g_ticket)) trade.PositionClose(g_ticket);
      g_open = -1; g_done++;
   }
   while (g_open < 0 && g_next < g_n && now >= g_in[g_next]) {
      int i = g_next++;
      if (now - g_in[i] > InpLateSec || now >= g_out[i]) { g_skipped++; continue; }
      bool ok = g_side[i] > 0 ? trade.Buy(g_lots[i], _Symbol, 0, 0, 0, "replay") : trade.Sell(g_lots[i], _Symbol, 0, 0, 0, "replay");
      if (!ok) { g_skipped++; continue; }
      g_ticket = trade.ResultOrder(); ulong deal = trade.ResultDeal();
      if (deal > 0 && HistoryDealSelect(deal)) g_ticket = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
      g_open = i;
   }
}

void OnDeinit(const int reason) { PrintFormat("TradeReplay: %d of %d trades replayed, %d skipped (late / market closed)", g_done, g_n, g_skipped); }
