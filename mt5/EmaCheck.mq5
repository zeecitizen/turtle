//+------------------------------------------------------------------+
//| EmaCheck.mq5 - test helper: SaadEMAs (embedded copy) must equal     |
//| iMA on M15 for the M15 candle each chart bar belongs to.            |
//+------------------------------------------------------------------+
#property version "1.00"
#resource "\\Indicators\\SaadEMAs.ex5"
int hC, h9, h50; int checks = 0, bad = 0; datetime last = 0;
int OnInit()
{
   hC = iCustom(_Symbol, PERIOD_CURRENT, "::Indicators\\SaadEMAs.ex5", PERIOD_M15, 9, 50);
   h9 = iMA(_Symbol, PERIOD_M15, 9, 0, MODE_EMA, PRICE_CLOSE); h50 = iMA(_Symbol, PERIOD_M15, 50, 0, MODE_EMA, PRICE_CLOSE);
   return hC == INVALID_HANDLE ? INIT_FAILED : INIT_SUCCEEDED;
}
void OnTick()
{
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 1);
   if (t == last) return; last = t;
   double c9[1], c50[1], m9[1], m50[1];
   if (CopyBuffer(hC, 0, 1, 1, c9) != 1 || CopyBuffer(hC, 1, 1, 1, c50) != 1) return;
   int sh = iBarShift(_Symbol, PERIOD_M15, t, false);
   if (CopyBuffer(h9, 0, sh, 1, m9) != 1 || CopyBuffer(h50, 0, sh, 1, m50) != 1) return;
   checks++;
   if (MathAbs(c9[0] - m9[0]) > 0.001 || MathAbs(c50[0] - m50[0]) > 0.001) bad++;
}
void OnDeinit(const int r) { PrintFormat("[EmaCheck] bars checked %d, mismatches %d", checks, bad); }
