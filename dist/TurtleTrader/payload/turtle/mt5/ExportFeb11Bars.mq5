//+------------------------------------------------------------------+
//| ExportFeb11Bars.mq5                                              |
//|                                                                  |
//| One-shot SCRIPT (not EA). Exports XAUUSD M1 + H1 OHLCV for       |
//| 2026.02.10 through 2026.02.12 to Common\Files for the Python     |
//| reverse-engineering analyzer.                                    |
//|                                                                  |
//| Usage: drag onto any chart. Runs once, writes CSVs, exits.       |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs
#property version "1.00"
#property description "Export XAUUSD M1+H1 bars for Feb 11 reverse engineering"

input string   InpSymbol     = "XAUUSD";
input datetime InpFromUtc    = D'2026.02.01 00:00';   // wide default — covers Feb 11 + adjacent weeks
input datetime InpToUtc      = D'2026.05.14 00:00';   // extends through today (was 05.13)
input string   InpM1FileName = "rev_eng_m1.csv";
input string   InpH1FileName = "rev_eng_h1.csv";

int ExportTimeframe(ENUM_TIMEFRAMES tf, string fname) {
   MqlRates rates[];
   ArraySetAsSeries(rates, false);   // ascending time order for CSV
   int got = CopyRates(InpSymbol, tf, InpFromUtc, InpToUtc, rates);
   if(got <= 0) {
      Print("CopyRates failed for ", EnumToString(tf), " — got=", got, " err=", GetLastError());
      return 0;
   }

   // FILE_COMMON so the file lands in Common\Files (shared across terminals)
   int h = FileOpen(fname, FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(h == INVALID_HANDLE) {
      Print("FileOpen failed for ", fname, " err=", GetLastError());
      return 0;
   }

   // Header
   FileWrite(h, "time_iso", "open", "high", "low", "close", "tick_volume", "real_volume", "spread");

   for(int i = 0; i < got; i++) {
      string ts = TimeToString(rates[i].time, TIME_DATE | TIME_SECONDS);
      FileWrite(h,
         ts,
         DoubleToString(rates[i].open,  _Digits),
         DoubleToString(rates[i].high,  _Digits),
         DoubleToString(rates[i].low,   _Digits),
         DoubleToString(rates[i].close, _Digits),
         IntegerToString((long)rates[i].tick_volume),
         IntegerToString((long)rates[i].real_volume),
         IntegerToString((long)rates[i].spread)
      );
   }
   FileClose(h);
   Print("Exported ", got, " bars of ", EnumToString(tf), " to Common\\Files\\", fname);
   return got;
}

void OnStart() {
   Print("=== ExportFeb11Bars starting ===");
   Print("Symbol: ", InpSymbol, "  From: ", InpFromUtc, "  To: ", InpToUtc);

   int n_m1 = ExportTimeframe(PERIOD_M1, InpM1FileName);
   int n_h1 = ExportTimeframe(PERIOD_H1, InpH1FileName);

   Print("=== Done. M1 bars=", n_m1, "  H1 bars=", n_h1, " ===");
   Print("CSVs at: %APPDATA%\\MetaQuotes\\Terminal\\Common\\Files\\", InpM1FileName,
         " and ", InpH1FileName);
}
