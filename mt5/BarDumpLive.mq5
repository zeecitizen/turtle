//+------------------------------------------------------------------+
//| BarDumpLive.mq5 - SCRIPT, research helper, never trades.           |
//| Asks the broker for every M1 and M15 candle of the symbol from     |
//| InpFrom to now (downloading what the terminal doesn't have) and    |
//| writes them with the values Saad reads (M15 EMA 9/50, ATR(14),     |
//| efficiency ratio 16) to Common\Files\barlive_<symbol>_M1/M15.csv.  |
//| Run at terminal start-up via [StartUp] Script=BarDumpLive.         |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.00"
#property script_show_inputs false

input datetime InpFrom = D'2026.10.12 00:00';

void Dump(ENUM_TIMEFRAMES tf, string name)
{
   MqlRates r[];
   ArraySetAsSeries(r, false);
   int n = 0;
   for (int a = 0; a < 30 && n <= 0; a++) { n = CopyRates(_Symbol, tf, InpFrom, TimeCurrent(), r); if (n <= 0) Sleep(1000); }
   int h = FileOpen(StringFormat("barlive_%s_%s.csv", _Symbol, name), FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if (h == INVALID_HANDLE) return;
   if (tf == PERIOD_M15) {
      int e9 = iMA(_Symbol, PERIOD_M15, 9, 0, MODE_EMA, PRICE_CLOSE), e50 = iMA(_Symbol, PERIOD_M15, 50, 0, MODE_EMA, PRICE_CLOSE), at = iATR(_Symbol, PERIOD_M15, 14);
      double b9[], b50[], ba[];
      for (int a = 0; a < 30; a++) {
         if (CopyBuffer(e9, 0, InpFrom, TimeCurrent(), b9) == n && CopyBuffer(e50, 0, InpFrom, TimeCurrent(), b50) == n && CopyBuffer(at, 0, InpFrom, TimeCurrent(), ba) == n) break;
         Sleep(1000);
      }
      FileWrite(h, "time,open,high,low,close,tickvol,spread,ema9,ema50,atr14,er16");
      for (int i = 0; i < n; i++) {
         double er = 0;
         if (i >= 16) { double path = 0; for (int k = i - 15; k <= i; k++) path += MathAbs(r[k].close - r[k - 1].close); er = path > 0 ? MathAbs(r[i].close - r[i - 16].close) / path : 0; }
         FileWrite(h, StringFormat("%s,%.2f,%.2f,%.2f,%.2f,%d,%d,%.3f,%.3f,%.3f,%.3f", TimeToString(r[i].time, TIME_DATE | TIME_MINUTES), r[i].open, r[i].high, r[i].low, r[i].close,
                   (int)r[i].tick_volume, r[i].spread, i < ArraySize(b9) ? b9[i] : 0, i < ArraySize(b50) ? b50[i] : 0, i < ArraySize(ba) ? ba[i] : 0, er));
      }
   } else {
      FileWrite(h, "time,open,high,low,close,tickvol,spread");
      for (int i = 0; i < n; i++)
         FileWrite(h, StringFormat("%s,%.2f,%.2f,%.2f,%.2f,%d,%d", TimeToString(r[i].time, TIME_DATE | TIME_MINUTES), r[i].open, r[i].high, r[i].low, r[i].close, (int)r[i].tick_volume, r[i].spread));
   }
   FileClose(h);
   PrintFormat("[BarDumpLive] %s %s: %d candles, last %s", _Symbol, name, n, n > 0 ? TimeToString(r[n - 1].time) : "-");
}

void OnStart()
{
   Dump(PERIOD_M1, "M1");
   Dump(PERIOD_M15, "M15");
}
