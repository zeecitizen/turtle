//+------------------------------------------------------------------+
//| ExportFeb11Ticks.mq5                                             |
//|                                                                  |
//| One-shot SCRIPT. Exports XAUUSD TICK history for 2026.02.10      |
//| through 2026.02.12 to Common\Files as CSV. Uses CopyTicksRange.  |
//|                                                                  |
//| Required because OANDA parquet has a ~$17 offset vs Zee's        |
//| Blueberry broker and different intra-minute shapes. We need the  |
//| actual broker ticks to reproduce his Feb 11 +$835/94% day.       |
//|                                                                  |
//| Usage: in MT5 Navigator > Scripts > drag onto XAUUSD chart.      |
//| Output: Common\Files\shano_ticks_2026-02-11.csv (plus 10, 12)    |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs
#property version "1.00"
#property description "Export Feb 11 2026 XAUUSD ticks for backtest reproduction"

input string   InpSymbol  = "XAUUSD";
input datetime InpFromUtc = D'2026.02.10 00:00';
input datetime InpToUtc   = D'2026.02.13 00:00';

void OnStart() {
   // Make sure ticks are loaded
   long sel = SymbolInfoInteger(InpSymbol, SYMBOL_SELECT);
   if(sel == 0) {
      if(!SymbolSelect(InpSymbol, true)) {
         Print("[FAIL] SymbolSelect ", InpSymbol, " err=", GetLastError());
         return;
      }
   }

   // Iterate day-by-day; one CSV per day matches shano_ticks_*.csv schema
   datetime cur = InpFromUtc;
   while(cur < InpToUtc) {
      datetime next = cur + 86400;
      ulong from_ms = (ulong)cur * 1000;
      ulong to_ms   = (ulong)next * 1000;

      MqlTick ticks[];
      int got = CopyTicksRange(InpSymbol, ticks, COPY_TICKS_ALL, from_ms, to_ms);
      if(got <= 0) {
         Print("[skip] ", TimeToString(cur, TIME_DATE), " — no ticks (err=", GetLastError(), ")");
         cur = next;
         continue;
      }

      // Build filename like shano_ticks_2026-02-11.csv
      MqlDateTime dt;
      TimeToStruct(cur, dt);
      string fname = StringFormat("shano_ticks_%04d-%02d-%02d.csv", dt.year, dt.mon, dt.day);

      int fh = FileOpen(fname, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
      if(fh == INVALID_HANDLE) {
         Print("[FAIL] FileOpen ", fname, " err=", GetLastError());
         cur = next; continue;
      }
      // Header: t,bid,ask  (matches existing shano_ticks_*.csv schema used by load_ticks)
      FileWriteString(fh, "t,bid,ask\r\n");

      for(int i = 0; i < got; i++) {
         // Format timestamp: YYYY.MM.DD HH:MM:SS.mmm
         datetime sec = (datetime)(ticks[i].time_msc / 1000);
         long ms = ticks[i].time_msc % 1000;
         MqlDateTime tt;
         TimeToStruct(sec, tt);
         string line = StringFormat("%04d.%02d.%02d %02d:%02d:%02d.%03d,%.2f,%.2f\r\n",
            tt.year, tt.mon, tt.day, tt.hour, tt.min, tt.sec, (int)ms,
            ticks[i].bid, ticks[i].ask);
         FileWriteString(fh, line);
      }
      FileClose(fh);

      Print("[ok] ", fname, " — ", got, " ticks written");
      cur = next;
   }

   Print("=== Done. CSVs land in Common\\Files\\shano_ticks_YYYY-MM-DD.csv ===");
}
//+------------------------------------------------------------------+
