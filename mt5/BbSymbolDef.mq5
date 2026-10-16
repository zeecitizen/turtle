//+------------------------------------------------------------------+
//| BbSymbolDef.mq5 - script for an Axi test rig: define the custom   |
//| symbol XAUUSD_BB with Blueberry's specs and sessions, read from   |
//| Common\Files\bb_symbol_spec.csv (written by BbTickClone.mq5 in    |
//| Zee's Blueberry terminal). Its ticks / bars are copied in after.  |
//| Zee 2026-10-17: "maybe we can run these on blueberry instead?"    |
//+------------------------------------------------------------------+
#property version "1.02"
input string InpDst = "XAUUSD_BB";
input string InpOrigin = "XAUUSD_TK";     // a working custom gold symbol in this rig to copy the trading settings from

void OnStart()
{
   int fh = FileOpen("bb_symbol_spec.csv", FILE_READ | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if (fh == INVALID_HANDLE) { Print("[bbdef] no bb_symbol_spec.csv"); Print("[bbdef] DONE (failed)"); TerminalClose(0); return; }
   // v1.01: start from XAUUSD_TK (market execution, margin, profit maths already right for the tester), then Blueberry's specs + sessions
   if (SymbolInfoInteger(InpDst, SYMBOL_CUSTOM) != 0) { SymbolSelect(InpDst, false); if (!CustomSymbolDelete(InpDst)) PrintFormat("[bbdef] could not delete the old %s (err %d)", InpDst, GetLastError()); }
   if (SymbolInfoInteger(InpDst, SYMBOL_CUSTOM) == 0 && !CustomSymbolCreate(InpDst, "Custom\Clone", InpOrigin)) {
      PrintFormat("[bbdef] CustomSymbolCreate failed %d", GetLastError()); FileClose(fh); Print("[bbdef] DONE (failed)"); TerminalClose(0); return;
   }
   // currencies, margin mode (leverage) and execution come from InpOrigin - a plain CFD margin mode ignored the leverage (v1.00: "not enough money")
   for (int d = 0; d < 7; d++) { for (uint k = 0; k < 10; k++) { CustomSymbolSetSessionQuote(InpDst, (ENUM_DAY_OF_WEEK)d, k, 0, 0); CustomSymbolSetSessionTrade(InpDst, (ENUM_DAY_OF_WEEK)d, k, 0, 0); } }
   int nq[7], nt[7]; ArrayInitialize(nq, 0); ArrayInitialize(nt, 0);
   while (!FileIsEnding(fh)) {
      string key = FileReadString(fh);
      if (key == "quote" || key == "trade") {
         int d = (int)FileReadNumber(fh); datetime f = (datetime)(long)FileReadNumber(fh), t = (datetime)(long)FileReadNumber(fh);
         if (key == "quote") CustomSymbolSetSessionQuote(InpDst, (ENUM_DAY_OF_WEEK)d, nq[d]++, f, t);
         else                CustomSymbolSetSessionTrade(InpDst, (ENUM_DAY_OF_WEEK)d, nt[d]++, f, t);
         continue;
      }
      double v = FileReadNumber(fh);
      if (key == "digits")    CustomSymbolSetInteger(InpDst, SYMBOL_DIGITS, (long)v);
      if (key == "point")     CustomSymbolSetDouble(InpDst, SYMBOL_POINT, v);
      if (key == "ticksize")  CustomSymbolSetDouble(InpDst, SYMBOL_TRADE_TICK_SIZE, v);
      if (key == "tickvalue") CustomSymbolSetDouble(InpDst, SYMBOL_TRADE_TICK_VALUE, v);
      if (key == "contract")  CustomSymbolSetDouble(InpDst, SYMBOL_TRADE_CONTRACT_SIZE, v);
      if (key == "volmin")    CustomSymbolSetDouble(InpDst, SYMBOL_VOLUME_MIN, v);
      if (key == "volmax")    CustomSymbolSetDouble(InpDst, SYMBOL_VOLUME_MAX, v);
      if (key == "volstep")   CustomSymbolSetDouble(InpDst, SYMBOL_VOLUME_STEP, v);
      if (key == "stops")     CustomSymbolSetInteger(InpDst, SYMBOL_TRADE_STOPS_LEVEL, (long)v);
      if (key == "freeze")    CustomSymbolSetInteger(InpDst, SYMBOL_TRADE_FREEZE_LEVEL, (long)v);
   }
   FileClose(fh);
   // a CFD's tick value can read 0 in the source terminal: $ per tick per lot = tick size x contract
   if (SymbolInfoDouble(InpDst, SYMBOL_TRADE_TICK_VALUE) <= 0)
      CustomSymbolSetDouble(InpDst, SYMBOL_TRADE_TICK_VALUE, SymbolInfoDouble(InpDst, SYMBOL_TRADE_TICK_SIZE) * SymbolInfoDouble(InpDst, SYMBOL_TRADE_CONTRACT_SIZE));
   CustomSymbolSetInteger(InpDst, SYMBOL_TRADE_MODE, SYMBOL_TRADE_MODE_FULL);
   CustomSymbolSetInteger(InpDst, SYMBOL_SPREAD_FLOAT, true);
   SymbolSelect(InpDst, true);
   PrintFormat("[bbdef] %s defined: digits %d, contract %.0f, sessions Mon quote %d / trade %d", InpDst, (int)SymbolInfoInteger(InpDst, SYMBOL_DIGITS),
               SymbolInfoDouble(InpDst, SYMBOL_TRADE_CONTRACT_SIZE), nq[1], nt[1]);
   Print("[bbdef] DONE");
   TerminalClose(0);
}
