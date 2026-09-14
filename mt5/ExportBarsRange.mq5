//+------------------------------------------------------------------+
//|  ExportBarsRange.mq5 — bars for a DATE RANGE, any timeframe.      |
//|                                                                   |
//|  ExportRecentBars is count-based and M1-only. Drawing every VSISA  |
//|  setup needs seven months of M5 with the tick_volume the EA        |
//|  actually judged, so this takes a symbol, a timeframe and a span.  |
//|                                                                   |
//|  CopyRates is called in CHUNKS. Asking for 40,000+ bars in one go  |
//|  silently returns fewer (or -1) depending on what the terminal has |
//|  paged in, and a short read here would quietly drop months of      |
//|  setups off the page with no error anywhere.                       |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs
#property version "1.00"

input string InpSymbol = "XAUUSD.pro";             // symbol (custom symbols allowed)
input int    InpTfMin  = 5;                    // timeframe in minutes
input string InpFrom   = "2026.03.01";         // inclusive
input string InpTo     = "2026.09.16";         // exclusive
input string InpFile   = "vsisa_bars_axi.csv";  // -> Common\Files

ENUM_TIMEFRAMES TF(int m) {
   switch (m) {
      case 1:  return PERIOD_M1;
      case 5:  return PERIOD_M5;
      case 15: return PERIOD_M15;
      case 30: return PERIOD_M30;
      case 60: return PERIOD_H1;
   }
   return PERIOD_M5;
}

void OnStart() {
   datetime from = StringToTime(InpFrom);
   datetime to   = StringToTime(InpTo);
   if (from <= 0 || to <= from) {
      PrintFormat("[bars] bad range %s -> %s", InpFrom, InpTo);
      return;
   }
   if (!SymbolSelect(InpSymbol, true))
      PrintFormat("[bars] warning: cannot select %s (err %d)", InpSymbol, GetLastError());

   int h = FileOpen(InpFile, FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if (h == INVALID_HANDLE) {
      PrintFormat("[bars] FileOpen %s failed err=%d", InpFile, GetLastError());
      return;
   }
   FileWrite(h, "time_iso", "open", "high", "low", "close", "tick_volume", "real_volume");

   ENUM_TIMEFRAMES tf = TF(InpTfMin);
   int digits = (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS);
   if (digits <= 0) digits = 2;

   long   step  = (long)InpTfMin * 60 * 5000;   // ~5000 bars per chunk
   long   total = 0;
   datetime cur = from;

   while (cur < to) {
      datetime end = (datetime)MathMin((long)to, (long)cur + step);
      MqlRates r[];
      ArraySetAsSeries(r, false);
      int got = CopyRates(InpSymbol, tf, cur, end, r);
      if (got > 0) {
         for (int i = 0; i < got; i++) {
            if (r[i].time < from || r[i].time >= to) continue;
            FileWrite(h,
                      TimeToString(r[i].time, TIME_DATE | TIME_SECONDS),
                      DoubleToString(r[i].open,  digits),
                      DoubleToString(r[i].high,  digits),
                      DoubleToString(r[i].low,   digits),
                      DoubleToString(r[i].close, digits),
                      IntegerToString((long)r[i].tick_volume),
                      IntegerToString((long)r[i].real_volume));
            total++;
         }
      } else {
         PrintFormat("[bars] chunk %s: got %d (err %d)",
                     TimeToString(cur, TIME_DATE), got, GetLastError());
      }
      cur = end;
   }
   FileClose(h);
   PrintFormat("[bars] %s %dm: wrote %I64d bars %s -> %s into %s",
               InpSymbol, InpTfMin, total, InpFrom, InpTo, InpFile);
}
//+------------------------------------------------------------------+
