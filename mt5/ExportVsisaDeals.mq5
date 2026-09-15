//+------------------------------------------------------------------+
//|  ExportVsisaDeals.mq5 — the EA's REAL closed trades, to CSV.       |
//|                                                                   |
//|  Zee, 2026-09-16: "but for these LIVE we can atleast show the      |
//|  profit / loss that was gained".                                   |
//|                                                                   |
//|  The VSISA page marks a card LIVE when the trade came from the     |
//|  attached EA's own log rather than the tester — but that log only  |
//|  records the ENTRY, so a live card had no outcome on it. This      |
//|  dumps the account's own deal history for the VSISA magic, which   |
//|  is the broker's record, not a replay: real fill, real commission, |
//|  real swap, real profit.                                           |
//|                                                                   |
//|  WHY A SCRIPT AND NOT THE EA. The EA could log its own closes, but |
//|  that only helps from the moment it ships; the trades already      |
//|  taken would stay blank forever. A script reads the whole history  |
//|  including everything that happened before it existed.             |
//|                                                                   |
//|  Drag it onto any chart in the Axi terminal. It touches nothing —  |
//|  no orders, no positions, no chart objects. It only reads history  |
//|  and writes one file.                                              |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.00"
#property strict
#property script_show_inputs

input int    InpMagic = 88201;                  // InpMagic — 0 = every magic
input string InpFile  = "vsisa_live_deals.csv"; // -> Common\Files
input string InpFrom  = "2026.01.01";           // history from

void OnStart() {
   datetime from = StringToTime(InpFrom);
   if (from <= 0) from = 0;

   if (!HistorySelect(from, TimeCurrent() + 86400)) {
      PrintFormat("[deals] HistorySelect failed, err %d", GetLastError());
      return;
   }

   int h = FileOpen(InpFile, FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if (h == INVALID_HANDLE) {
      PrintFormat("[deals] FileOpen %s failed, err %d", InpFile, GetLastError());
      return;
   }
   FileWrite(h, "close_time", "position", "symbol", "type", "volume",
                "price", "profit", "commission", "swap", "net", "comment", "magic");

   int total = HistoryDealsTotal(), written = 0;
   double sum = 0.0;
   for (int i = 0; i < total; i++) {
      ulong tk = HistoryDealGetTicket(i);
      if (tk == 0) continue;
      // Only the CLOSING half of a round trip carries the profit.
      if (HistoryDealGetInteger(tk, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      long mg = HistoryDealGetInteger(tk, DEAL_MAGIC);
      if (InpMagic != 0 && mg != InpMagic) continue;

      double pr = HistoryDealGetDouble(tk, DEAL_PROFIT);
      double cm = HistoryDealGetDouble(tk, DEAL_COMMISSION);
      double sw = HistoryDealGetDouble(tk, DEAL_SWAP);
      double net = pr + cm + sw;
      sum += net;
      written++;

      FileWrite(h,
                TimeToString((datetime)HistoryDealGetInteger(tk, DEAL_TIME),
                             TIME_DATE | TIME_SECONDS),
                IntegerToString((long)HistoryDealGetInteger(tk, DEAL_POSITION_ID)),
                HistoryDealGetString(tk, DEAL_SYMBOL),
                (HistoryDealGetInteger(tk, DEAL_TYPE) == DEAL_TYPE_BUY) ? "buy" : "sell",
                DoubleToString(HistoryDealGetDouble(tk, DEAL_VOLUME), 2),
                DoubleToString(HistoryDealGetDouble(tk, DEAL_PRICE), 2),
                DoubleToString(pr, 2), DoubleToString(cm, 2), DoubleToString(sw, 2),
                DoubleToString(net, 2),
                HistoryDealGetString(tk, DEAL_COMMENT),
                IntegerToString(mg));
   }
   FileClose(h);
   PrintFormat("[deals] wrote %d closed VSISA trades (net %.2f) to Common\\Files\\%s",
               written, sum, InpFile);
}
//+------------------------------------------------------------------+
