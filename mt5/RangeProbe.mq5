// RangeProbe.mq5 - tester helper: average M5 bar range and spread, in points, over the test
// window. Used to set VSISA's InpPtsScale for markets other than gold.
#property strict
input datetime InpFrom = D'2026.01.01';
double g_sp = 0; long g_n = 0;
int OnInit() { return(INIT_SUCCEEDED); }
void OnTick() { g_sp += SymbolInfoInteger(_Symbol, SYMBOL_SPREAD); g_n++; }
void OnDeinit(const int reason)
{
   int n = Bars(_Symbol, PERIOD_M5);
   double sum = 0; int k = 0;
   for (int i = 1; i < n; i++) {
      if (iTime(_Symbol, PERIOD_M5, i) < InpFrom) break;
      sum += (iHigh(_Symbol, PERIOD_M5, i) - iLow(_Symbol, PERIOD_M5, i)) / _Point;
      k++;
   }
   PrintFormat("RANGEPROBE %s bars %d avgM5range %.1f pts avgSpread %.1f pts point %g digits %d "
               "tickvalue %.5f contract %.2f minlot %.2f",
               _Symbol, k, k ? sum / k : 0, g_n ? g_sp / g_n : 0, _Point, _Digits,
               SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE),
               SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE),
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN));
}
