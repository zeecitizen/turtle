//+------------------------------------------------------------------+
//| BarDump.mq5 - research helper, never trades.                       |
//| Writes every closed M1 and M15 candle of the test period, with the |
//| values Saad_strategy_15min reads (M15 EMA 9 / 50, ATR(14),         |
//| efficiency ratio over 16 candles), to Common\Files\bardump_<tag>_  |
//| M1.csv and _M15.csv. Used to rebuild trade lifecycles.             |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.00"
#property strict

input int InpTag = 0;   // InpTag — output file tag

int hE9, hE50, hAtr, f1 = INVALID_HANDLE, f15 = INVALID_HANDLE;
datetime last1 = 0, last15 = 0;

double B(int h, int k) { double b[1]; return CopyBuffer(h, 0, k, 1, b) == 1 ? b[0] : 0; }
double ER(int n)
{
   double path = 0;
   for (int k = 1; k <= n; k++) path += MathAbs(iClose(_Symbol, PERIOD_M15, k) - iClose(_Symbol, PERIOD_M15, k + 1));
   return path > 0 ? MathAbs(iClose(_Symbol, PERIOD_M15, 1) - iClose(_Symbol, PERIOD_M15, 1 + n)) / path : 0;
}
int OnInit()
{
   hE9 = iMA(_Symbol, PERIOD_M15, 9, 0, MODE_EMA, PRICE_CLOSE);
   hE50 = iMA(_Symbol, PERIOD_M15, 50, 0, MODE_EMA, PRICE_CLOSE);
   hAtr = iATR(_Symbol, PERIOD_M15, 14);
   f1 = FileOpen(StringFormat("bardump_%d_M1.csv", InpTag), FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   f15 = FileOpen(StringFormat("bardump_%d_M15.csv", InpTag), FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   FileWrite(f1, "time,open,high,low,close,tickvol,spread_pts");
   FileWrite(f15, "time,open,high,low,close,tickvol,ema9,ema50,atr14,er16");
   return INIT_SUCCEEDED;
}
void OnTick()
{
   datetime t1 = iTime(_Symbol, PERIOD_M1, 1);
   if (t1 != last1 && t1 > 0) {
      last1 = t1;
      FileWrite(f1, StringFormat("%s,%.2f,%.2f,%.2f,%.2f,%d,%d", TimeToString(t1, TIME_DATE | TIME_MINUTES),
                iOpen(_Symbol, PERIOD_M1, 1), iHigh(_Symbol, PERIOD_M1, 1), iLow(_Symbol, PERIOD_M1, 1), iClose(_Symbol, PERIOD_M1, 1),
                (int)iVolume(_Symbol, PERIOD_M1, 1), iSpread(_Symbol, PERIOD_M1, 1)));
   }
   datetime t15 = iTime(_Symbol, PERIOD_M15, 1);
   if (t15 != last15 && t15 > 0) {
      last15 = t15;
      FileWrite(f15, StringFormat("%s,%.2f,%.2f,%.2f,%.2f,%d,%.3f,%.3f,%.3f,%.3f", TimeToString(t15, TIME_DATE | TIME_MINUTES),
                iOpen(_Symbol, PERIOD_M15, 1), iHigh(_Symbol, PERIOD_M15, 1), iLow(_Symbol, PERIOD_M15, 1), iClose(_Symbol, PERIOD_M15, 1),
                (int)iVolume(_Symbol, PERIOD_M15, 1), B(hE9, 1), B(hE50, 1), B(hAtr, 1), ER(16)));
   }
}
void OnDeinit(const int reason) { if (f1 != INVALID_HANDLE) FileClose(f1); if (f15 != INVALID_HANDLE) FileClose(f15); }
