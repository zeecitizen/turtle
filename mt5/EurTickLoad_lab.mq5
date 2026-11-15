//+------------------------------------------------------------------+
//| EurTickLoad_lab.mq5 - LAB TOOL (2026-11-04), test rigs only.      |
//| Loads Zee's own MT5 EURUSD tick export (EURUSD_tick_data/         |
//| EURUSD.i_202601020000_202611040757.csv, blanks forward-filled)    |
//| into a custom symbol so the Strategy Tester replays REAL ticks    |
//| (not 4 synthetic ticks per bar). Pattern = BbTickLoad.mq5, but it |
//| reads the rig's OWN MQL5\Files (never Common\Files, which the     |
//| live terminal's EAs share). Specs + sessions copied from          |
//| EURUSD.pro (Axi). Run as a StartUp script; closes the terminal so |
//| the custom symbol definition is saved.                            |
//+------------------------------------------------------------------+
#property script_show_inputs
#property version   "1.00"

input string InpSymbol = "EURUSD_ZX";   // custom symbol to create / fill
input string InpOrigin = "EURUSD.pro";  // copy its specs and sessions
input int    InpChunk  = 1000000;       // ticks per write

void OnStart()
{
   if (!SymbolSelect(InpSymbol, false) || !SymbolInfoInteger(InpSymbol, SYMBOL_CUSTOM)) {
      if (!CustomSymbolCreate(InpSymbol, "", InpOrigin)) { PrintFormat("[eurload] create %s from %s failed: %d", InpSymbol, InpOrigin, GetLastError()); TerminalClose(1); return; }
   }
   int ht = FileOpen("eur_t.bin", FILE_READ | FILE_BIN | FILE_SHARE_READ);
   int hb = FileOpen("eur_bid.bin", FILE_READ | FILE_BIN | FILE_SHARE_READ);
   int ha = FileOpen("eur_ask.bin", FILE_READ | FILE_BIN | FILE_SHARE_READ);
   if (ht == INVALID_HANDLE || hb == INVALID_HANDLE || ha == INVALID_HANDLE) { Print("[eurload] cannot open the tick files"); TerminalClose(1); return; }
   long total = (long)(FileSize(ht) / 8);
   CustomRatesDelete(InpSymbol, 0, LONG_MAX);
   CustomTicksDelete(InpSymbol, 0, LONG_MAX);
   double t[], b[], a[]; MqlTick tk[];
   long done = 0; uint t0 = GetTickCount();
   while (done < total) {
      int n = (int)MathMin((long)InpChunk, total - done);
      if (FileReadArray(ht, t, 0, n) != n || FileReadArray(hb, b, 0, n) != n || FileReadArray(ha, a, 0, n) != n) { Print("[eurload] short read"); break; }
      ArrayResize(tk, n);
      for (int i = 0; i < n; i++) {
         long ms = (long)MathRound(t[i] * 1000.0);
         tk[i].time = (datetime)(ms / 1000); tk[i].time_msc = ms; tk[i].bid = b[i]; tk[i].ask = a[i];
         tk[i].last = 0; tk[i].volume = 0; tk[i].volume_real = 0; tk[i].flags = TICK_FLAG_BID | TICK_FLAG_ASK;
      }
      int w = CustomTicksReplace(InpSymbol, tk[0].time_msc, tk[n - 1].time_msc, tk);
      if (w < 0) { PrintFormat("[eurload] CustomTicksReplace failed at %s: %d", TimeToString(tk[0].time), GetLastError()); break; }
      done += n;
      PrintFormat("[eurload] %I64d / %I64d ticks (%s) %.0f s", done, total, TimeToString(tk[n - 1].time), (GetTickCount() - t0) / 1000.0);
   }
   FileClose(ht); FileClose(hb); FileClose(ha);
   MqlRates r[];
   int nb = CopyRates(InpSymbol, PERIOD_M1, D'2026.01.01', D'2026.11.05', r);
   PrintFormat("[eurload] DONE %s: %I64d ticks in %.0f s, M1 bars %d, digits %d, contract %.0f", InpSymbol, done, (GetTickCount() - t0) / 1000.0,
               nb, (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS), SymbolInfoDouble(InpSymbol, SYMBOL_TRADE_CONTRACT_SIZE));
   TerminalClose(0);
}
