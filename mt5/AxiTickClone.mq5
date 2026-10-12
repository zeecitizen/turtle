//+------------------------------------------------------------------+
//| AxiTickClone.mq5 - script: copy a broker symbol's REAL ticks into |
//| a custom symbol, so the Strategy Tester replays 100% real ticks.   |
//|                                                                    |
//| Why (2026-10-12): since Axi revised its gold history (~Oct 10-11)  |
//| the tester discards real ticks for 135,070 of 271,894 Jan-Oct      |
//| minutes on XAUUSD.pro ("tick prices not matched") and replaces     |
//| them with generated ticks - in Zee's terminal and in the rig.      |
//| A custom symbol built only from the ticks has bars made from those |
//| same ticks, so nothing can be discarded.                           |
//|                                                                    |
//| Lessons kept from VsisaTickImport.mq5:                             |
//|  * select the custom symbol BEFORE writing ticks                   |
//|  * every tick carries BOTH the bid and the ask flag                |
//|  * CustomTicksReplace takes MILLISECONDS (VsisaTickImport passed   |
//|    seconds, which is why Replace "silently did nothing" there)     |
//| Sessions are copied from the broker symbol (not 24/7), so the EA's |
//| day-close rule and gap cancel still work.                          |
//+------------------------------------------------------------------+
#property script_show_inputs
#property version "1.00"

input string   InpSrc  = "XAUUSD.pro";            // broker symbol (real ticks)
input string   InpDst  = "XAUUSD_TK";             // custom symbol to build
input datetime InpFrom = D'2025.12.01 00:00';     // first day (includes indicator warm-up)
input datetime InpTo   = D'2026.10.10 00:00';     // last day (exclusive)

void OnStart()
{
   SymbolSelect(InpSrc, true);
   bool existed = SymbolInfoInteger(InpDst, SYMBOL_CUSTOM) > 0;
   if (!existed && !CustomSymbolCreate(InpDst, "Custom\\Clone", InpSrc)) {
      PrintFormat("[clone] CustomSymbolCreate failed: %d", GetLastError());
      Print("[clone] DONE (failed)");
      return;
   }
   PrintFormat("[clone] %s %s from %s", InpDst, existed ? "exists - replacing ticks" : "created", InpSrc);

   // money maths identical to the broker symbol
   CustomSymbolSetInteger(InpDst, SYMBOL_DIGITS, SymbolInfoInteger(InpSrc, SYMBOL_DIGITS));
   CustomSymbolSetDouble(InpDst, SYMBOL_POINT, SymbolInfoDouble(InpSrc, SYMBOL_POINT));
   CustomSymbolSetDouble(InpDst, SYMBOL_TRADE_TICK_SIZE, SymbolInfoDouble(InpSrc, SYMBOL_TRADE_TICK_SIZE));
   CustomSymbolSetDouble(InpDst, SYMBOL_TRADE_TICK_VALUE, SymbolInfoDouble(InpSrc, SYMBOL_TRADE_TICK_VALUE));
   CustomSymbolSetDouble(InpDst, SYMBOL_TRADE_CONTRACT_SIZE, SymbolInfoDouble(InpSrc, SYMBOL_TRADE_CONTRACT_SIZE));
   CustomSymbolSetDouble(InpDst, SYMBOL_VOLUME_MIN, SymbolInfoDouble(InpSrc, SYMBOL_VOLUME_MIN));
   CustomSymbolSetDouble(InpDst, SYMBOL_VOLUME_MAX, SymbolInfoDouble(InpSrc, SYMBOL_VOLUME_MAX));
   CustomSymbolSetDouble(InpDst, SYMBOL_VOLUME_STEP, SymbolInfoDouble(InpSrc, SYMBOL_VOLUME_STEP));
   CustomSymbolSetInteger(InpDst, SYMBOL_TRADE_STOPS_LEVEL, SymbolInfoInteger(InpSrc, SYMBOL_TRADE_STOPS_LEVEL));
   CustomSymbolSetInteger(InpDst, SYMBOL_TRADE_FREEZE_LEVEL, SymbolInfoInteger(InpSrc, SYMBOL_TRADE_FREEZE_LEVEL));
   CustomSymbolSetInteger(InpDst, SYMBOL_TRADE_MODE, SYMBOL_TRADE_MODE_FULL);
   CustomSymbolSetInteger(InpDst, SYMBOL_SPREAD_FLOAT, true);

   // the broker's own sessions
   for (int d = 0; d < 7; d++) {
      datetime f, t;
      for (uint k = 0; k < 10; k++) {
         if (!SymbolInfoSessionQuote(InpSrc, (ENUM_DAY_OF_WEEK)d, k, f, t)) break;
         CustomSymbolSetSessionQuote(InpDst, (ENUM_DAY_OF_WEEK)d, k, f, t);
      }
      for (uint k = 0; k < 10; k++) {
         if (!SymbolInfoSessionTrade(InpSrc, (ENUM_DAY_OF_WEEK)d, k, f, t)) break;
         CustomSymbolSetSessionTrade(InpDst, (ENUM_DAY_OF_WEEK)d, k, f, t);
      }
   }
   if (!SymbolSelect(InpDst, true)) PrintFormat("[clone] WARNING cannot select %s (err %d)", InpDst, GetLastError());

   long total = 0; int days = 0, empty = 0, fails = 0;
   for (datetime day = InpFrom; day < InpTo; day += 86400) {
      MqlTick tk[];
      ulong a = (ulong)day * 1000, b = (ulong)(day + 86400) * 1000;
      int n = -1;
      for (int tries = 0; tries < 30 && n < 0; tries++) { n = CopyTicksRange(InpSrc, tk, COPY_TICKS_ALL, a, b - 1); if (n < 0) Sleep(500); }
      if (n <= 0) { empty++; continue; }
      for (int i = 0; i < n; i++) tk[i].flags = TICK_FLAG_BID | TICK_FLAG_ASK;
      ResetLastError();
      int put = CustomTicksReplace(InpDst, (long)a, (long)(b - 1), tk);
      if (put <= 0) {
         ResetLastError();
         put = CustomTicksAdd(InpDst, tk);
      }
      if (put <= 0) { fails++; PrintFormat("[clone] FAILED %s: %d ticks, err %d", TimeToString(day, TIME_DATE), n, GetLastError()); continue; }
      total += put; days++;
      MqlDateTime dt; TimeToStruct(day, dt);
      if (dt.day == 1) PrintFormat("[clone] %s ... %I64d ticks so far", TimeToString(day, TIME_DATE), total);
   }
   PrintFormat("[clone] %s: %I64d ticks over %d days (%d empty days, %d failed)", InpDst, total, days, empty, fails);
   Print("[clone] DONE");
   TerminalClose(0);   // clean shutdown: the custom symbol's definition is saved on exit
}
