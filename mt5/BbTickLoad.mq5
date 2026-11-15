//+------------------------------------------------------------------+
//| BbTickLoad.mq5 - load Blueberry's real XAUUSD ticks 2023-2025     |
//| into a custom symbol in an MT5 TEST RIG (never the live terminal) |
//|                                                                   |
//| Zee 2026-10-28: "yes please do the task till completion" - run    |
//| the v1.38 gates on more than one year. The rig's XAUUSD_BB holds  |
//| 2026 only; this makes XAUUSD_BB3 (same specs, copied from         |
//| XAUUSD_BB) with the 2023-2025 ticks of the Turtle TV tick files.  |
//|                                                                   |
//| Reads three float64 arrays from Common\Files (hard links to       |
//| monitor/saad_view/simdata/m15_tick_raw_{t,bid,ask}.bin): time in  |
//| server seconds, bid, ask. Run as a StartUp script; it closes the  |
//| terminal when done. Progress: [bbload] lines in the rig's log.    |
//+------------------------------------------------------------------+
#property script_show_inputs
#property version   "1.00"

input string InpSymbol = "XAUUSD_BB3";   // custom symbol to create / fill
input string InpOrigin = "XAUUSD_BB";    // copy its specs and sessions
input long   InpFrom   = 0;              // first tick index to load
input long   InpTo     = 0;              // one past the last tick index
input int    InpChunk  = 1000000;        // ticks per write

void OnStart()
{
   if (!SymbolSelect(InpSymbol, false) || !SymbolInfoInteger(InpSymbol, SYMBOL_CUSTOM)) {
      if (!CustomSymbolCreate(InpSymbol, "", InpOrigin)) { PrintFormat("[bbload] create %s from %s failed: %d", InpSymbol, InpOrigin, GetLastError()); TerminalClose(1); return; }
   }
   int ht = FileOpen("bb3_t.bin", FILE_READ | FILE_BIN | FILE_COMMON | FILE_SHARE_READ);
   int hb = FileOpen("bb3_bid.bin", FILE_READ | FILE_BIN | FILE_COMMON | FILE_SHARE_READ);
   int ha = FileOpen("bb3_ask.bin", FILE_READ | FILE_BIN | FILE_COMMON | FILE_SHARE_READ);
   if (ht == INVALID_HANDLE || hb == INVALID_HANDLE || ha == INVALID_HANDLE) { Print("[bbload] cannot open the tick files"); TerminalClose(1); return; }
   FileSeek(ht, InpFrom * 8, SEEK_SET); FileSeek(hb, InpFrom * 8, SEEK_SET); FileSeek(ha, InpFrom * 8, SEEK_SET);
   double t[], b[], a[]; MqlTick tk[];
   long done = 0, total = InpTo - InpFrom; uint t0 = GetTickCount();
   while (done < total) {
      int n = (int)MathMin((long)InpChunk, total - done);
      if (FileReadArray(ht, t, 0, n) != n || FileReadArray(hb, b, 0, n) != n || FileReadArray(ha, a, 0, n) != n) { Print("[bbload] short read"); break; }
      ArrayResize(tk, n);
      for (int i = 0; i < n; i++) {
         long ms = (long)MathRound(t[i] * 1000.0);
         tk[i].time = (datetime)(ms / 1000); tk[i].time_msc = ms; tk[i].bid = b[i]; tk[i].ask = a[i];
         tk[i].last = 0; tk[i].volume = 0; tk[i].volume_real = 0; tk[i].flags = TICK_FLAG_BID | TICK_FLAG_ASK;
      }
      int w = CustomTicksReplace(InpSymbol, tk[0].time_msc, tk[n - 1].time_msc, tk);
      if (w < 0) { PrintFormat("[bbload] CustomTicksReplace failed at %s: %d", TimeToString(tk[0].time), GetLastError()); break; }
      done += n;
      PrintFormat("[bbload] %I64d / %I64d ticks (%s) %.0f s", done, total, TimeToString(tk[n - 1].time), (GetTickCount() - t0) / 1000.0);
   }
   FileClose(ht); FileClose(hb); FileClose(ha);
   PrintFormat("[bbload] DONE %s: %I64d ticks in %.0f s", InpSymbol, done, (GetTickCount() - t0) / 1000.0);
   TerminalClose(0);
}
