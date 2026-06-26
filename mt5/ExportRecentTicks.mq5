//+------------------------------------------------------------------+
//| ExportRecentTicks.mq5                                            |
//|                                                                  |
//| One-shot SCRIPT. Exports XAUUSD TICK history for the past 8 days |
//| (2026.06.13 → 2026.06.21 UTC) to Common\Files\.                  |
//| Writes one CSV per day: shano_ticks_YYYY-MM-DD.csv               |
//| Schema: t,bid,ask  (millisecond precision)                       |
//|                                                                  |
//| Used for multi-day auto-close-ms backtest. Existing CSVs are     |
//| OVERWRITTEN (FILE_WRITE).                                        |
//|                                                                  |
//| Usage: drag from Scripts onto XAUUSD M1 chart, click OK.         |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs
#property version "1.00"
#property description "Export 8 days of XAUUSD ticks (06-13 to 06-21) for multi-day backtest"

input string InpSymbol  = "XAUUSD";
input datetime InpFromUtc = D'2026.06.13 00:00';
input datetime InpToUtc   = D'2026.06.21 00:00';

void OnStart() {
   long sel = SymbolInfoInteger(InpSymbol, SYMBOL_SELECT);
   if (sel == 0) {
      if (!SymbolSelect(InpSymbol, true)) {
         Print("[FAIL] SymbolSelect ", InpSymbol, " err=", GetLastError());
         return;
      }
   }

   datetime cur = InpFromUtc;
   int total_ticks = 0;
   int days_done = 0;
   while (cur < InpToUtc) {
      datetime next = cur + 86400;
      ulong from_ms = (ulong)cur * 1000;
      ulong to_ms   = (ulong)next * 1000;

      MqlTick ticks[];
      int got = CopyTicksRange(InpSymbol, ticks, COPY_TICKS_ALL, from_ms, to_ms);
      if (got <= 0) {
         Print("[skip] ", TimeToString(cur, TIME_DATE), " — no ticks (err=", GetLastError(), ")");
         cur = next; continue;
      }

      MqlDateTime dt; TimeToStruct(cur, dt);
      string fname = StringFormat("shano_ticks_%04d-%02d-%02d.csv", dt.year, dt.mon, dt.day);
      int fh = FileOpen(fname, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
      if (fh == INVALID_HANDLE) {
         Print("[FAIL] FileOpen ", fname, " err=", GetLastError());
         cur = next; continue;
      }
      FileWriteString(fh, "t,bid,ask\r\n");
      for (int i = 0; i < got; i++) {
         datetime sec = (datetime)(ticks[i].time_msc / 1000);
         long ms = ticks[i].time_msc % 1000;
         MqlDateTime tt; TimeToStruct(sec, tt);
         string line = StringFormat("%04d.%02d.%02d %02d:%02d:%02d.%03d,%.2f,%.2f\r\n",
            tt.year, tt.mon, tt.day, tt.hour, tt.min, tt.sec, (int)ms,
            ticks[i].bid, ticks[i].ask);
         FileWriteString(fh, line);
      }
      FileClose(fh);
      Print("[ok] ", fname, " — ", got, " ticks written");
      total_ticks += got;
      days_done++;
      cur = next;
   }
   Print("=== Done. ", days_done, " days, ", total_ticks, " total ticks. CSVs in Common\\Files\\ ===");
}
