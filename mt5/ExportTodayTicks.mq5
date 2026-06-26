//+------------------------------------------------------------------+
//| ExportTodayTicks.mq5                                             |
//|                                                                  |
//| One-shot SCRIPT. Exports XAUUSD TICK history for TODAY (UTC) to |
//| Common\Files\shano_ticks_YYYY-MM-DD.csv. Same schema as          |
//| ExportFeb11Ticks. Used to backtest auto-close-ms windows         |
//| against today's actual broker ticks.                             |
//|                                                                  |
//| Usage: drag from Scripts onto the XAUUSD M1 chart. Default       |
//| date range = today UTC midnight → tomorrow UTC midnight.         |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs
#property version "1.00"
#property description "Export today's XAUUSD ticks for auto-close-ms backtest"

input string InpSymbol  = "XAUUSD";
// Defaults set to today (2026-06-19) — override via dialog if needed.
input datetime InpFromUtc = D'2026.06.19 00:00';
input datetime InpToUtc   = D'2026.06.20 00:00';

void OnStart() {
   long sel = SymbolInfoInteger(InpSymbol, SYMBOL_SELECT);
   if (sel == 0) {
      if (!SymbolSelect(InpSymbol, true)) {
         Print("[FAIL] SymbolSelect ", InpSymbol, " err=", GetLastError());
         return;
      }
   }

   datetime cur = InpFromUtc;
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
      cur = next;
   }
   Print("=== Done. CSV → Common\\Files\\shano_ticks_2026-06-19.csv ===");
}
