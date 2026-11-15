// ExportRates.mq5 - research helper (2026-10-28): writes M15 bars of other symbols to Common\Files\rates_<symbol>_M15.csv
// so the Python research can test a correlated hedge. Run once in the Strategy Tester; it trades nothing.
#property strict
input string InpSymbols = "USDJPY.pro,XAGUSD.pro,EURUSD.pro";
input string InpFrom    = "2023.01.01";

int OnInit()
{
   string s[]; int n = StringSplit(InpSymbols, ',', s);
   for(int k = 0; k < n; k++)
   {
      MqlRates r[]; SymbolSelect(s[k], true);
      int got = CopyRates(s[k], PERIOD_M15, StringToTime(InpFrom), TimeCurrent(), r);
      int h = FileOpen("rates_" + s[k] + "_M15.csv", FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
      if(h == INVALID_HANDLE) continue;
      for(int i = 0; i < got; i++) FileWrite(h, (long)r[i].time, r[i].open, r[i].high, r[i].low, r[i].close);
      FileClose(h);
      PrintFormat("ExportRates %s: %d bars", s[k], got);
   }
   return INIT_SUCCEEDED;
}
void OnTick() {}
