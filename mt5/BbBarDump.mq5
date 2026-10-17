//+------------------------------------------------------------------+
//| BbBarDump.mq5 - Strategy Tester helper: writes every closed M1    |
//| candle the tester builds from the symbol's real ticks to          |
//| Common\Files\<InpOut> (server time, open, high, low, close).      |
//| The compare page's chart draws the SAME candles the Saad EA saw.  |
//| Zee 2026-10-17: "use the real ticks downloaded by blueberry to    |
//| create a chart.. and then apply all settings to that chart"       |
//+------------------------------------------------------------------+
#property version "1.00"
input string InpOut = "bb_bars.csv";

int      g_fh = INVALID_HANDLE;
datetime g_last = 0;

int OnInit()
{
   g_fh = FileOpen(InpOut, FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   return g_fh == INVALID_HANDLE ? INIT_FAILED : INIT_SUCCEEDED;
}

void OnTick()
{
   datetime t0 = iTime(_Symbol, PERIOD_M1, 0);
   if (t0 == g_last) return;
   g_last = t0;
   MqlRates r[];
   if (CopyRates(_Symbol, PERIOD_M1, 1, 1, r) != 1) return;
   FileWrite(g_fh, TimeToString(r[0].time, TIME_DATE | TIME_MINUTES), DoubleToString(r[0].open, _Digits), DoubleToString(r[0].high, _Digits),
             DoubleToString(r[0].low, _Digits), DoubleToString(r[0].close, _Digits));
}

void OnDeinit(const int reason)
{
   if (g_fh == INVALID_HANDLE) return;
   MqlRates r[];                                  // the last candle of the test is closed by the end of the test
   if (CopyRates(_Symbol, PERIOD_M1, 0, 1, r) == 1)
      FileWrite(g_fh, TimeToString(r[0].time, TIME_DATE | TIME_MINUTES), DoubleToString(r[0].open, _Digits), DoubleToString(r[0].high, _Digits),
                DoubleToString(r[0].low, _Digits), DoubleToString(r[0].close, _Digits));
   FileClose(g_fh);
}
