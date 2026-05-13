//+------------------------------------------------------------------+
//| ExportRecentBars.mq5 — count-based bar export                    |
//| Dumps last N bars regardless of date range (works around the     |
//| date-range CopyRates issue that misses today's bars).            |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs
#property version "1.00"
#property description "Export last N M1 bars (newest first) to CSV"

input string InpSymbol   = "XAUUSD";
input int    InpBarCount = 10000;
input string InpFileName = "rev_eng_m1_recent.csv";

void OnStart() {
   Print("=== ExportRecentBars starting ===");
   Print("Symbol: ", InpSymbol, "  count: ", InpBarCount);

   MqlRates rates[];
   ArraySetAsSeries(rates, false);  // ascending time
   int got = CopyRates(InpSymbol, PERIOD_M1, 0, InpBarCount, rates);
   if(got <= 0) {
      Print("CopyRates failed — got=", got, " err=", GetLastError());
      return;
   }

   int h = FileOpen(InpFileName, FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(h == INVALID_HANDLE) {
      Print("FileOpen failed err=", GetLastError());
      return;
   }
   FileWrite(h, "time_iso", "open", "high", "low", "close", "tick_volume", "real_volume", "spread");
   for(int i = 0; i < got; i++) {
      FileWrite(h,
         TimeToString(rates[i].time, TIME_DATE | TIME_SECONDS),
         DoubleToString(rates[i].open,  _Digits),
         DoubleToString(rates[i].high,  _Digits),
         DoubleToString(rates[i].low,   _Digits),
         DoubleToString(rates[i].close, _Digits),
         IntegerToString((long)rates[i].tick_volume),
         IntegerToString((long)rates[i].real_volume),
         IntegerToString((long)rates[i].spread));
   }
   FileClose(h);
   Print("Exported ", got, " bars. First: ", rates[0].time, "  Last: ", rates[got-1].time);
   Print("CSV: %APPDATA%\\MetaQuotes\\Terminal\\Common\\Files\\", InpFileName);
}
