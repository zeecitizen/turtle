//+------------------------------------------------------------------+
//| TapeProbe.mq5 — answer one question and trade nothing.            |
//|                                                                  |
//| DohaLevel placed ZERO orders on data where its own detector,      |
//| replayed in Python against the identical file, would have placed  |
//| 917. The file is fine — its first twelve bars read                |
//| 762 674 609 716 1062 856 1057 830 1030 1272 769 718.              |
//|                                                                  |
//| So either the EA sees different numbers, or it sees the same ones |
//| and something else is wrong. Guessing has cost us four wrong      |
//| calls in two days, so this measures instead.                      |
//|                                                                  |
//| THE SUSPICION: the tester reported "Bars 1764, Ticks 7056" —      |
//| exactly 4.000 ticks per bar. MT5 synthesises ticks for custom     |
//| symbols in 'OHLC M1' mode. If the bar volume it hands back is the |
//| count of GENERATED ticks rather than our imported volume, then    |
//| every volume rule we own — UHV, no-supply, breakout-volume — has  |
//| been reading a constant, and last night's S1Trader results were   |
//| measuring a strategy with its volume sense switched off.          |
//|                                                                  |
//| A separate filename because MT5 caches the compiled EA in memory  |
//| and served us a stale build twice in two days. A name it has      |
//| never seen cannot be stale.                                       |
//|                                                                  |
//| It places no orders. It cannot lose money. Run it and read the    |
//| Journal.                                                          |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.00"
#property strict

input int InpBars = 15;   // InpBars — how many bars to print

bool g_done = false;

int OnInit() {
   Print("=== TapeProbe: reporting what the EA actually sees. No orders. ===");
   return INIT_SUCCEEDED;
}

void OnTick() {
   if (g_done) return;
   int have = Bars(_Symbol, PERIOD_CURRENT);
   if (have < InpBars + 5) return;
   g_done = true;

   string vols = "", reals = "", rng = "";
   for (int k = 1; k <= InpBars; k++) {
      vols  += StringFormat("%d ", (int)iVolume(_Symbol, PERIOD_CURRENT, k));
      reals += StringFormat("%d ", (int)iRealVolume(_Symbol, PERIOD_CURRENT, k));
      rng   += StringFormat("%.2f ", iHigh(_Symbol, PERIOD_CURRENT, k) -
                                     iLow (_Symbol, PERIOD_CURRENT, k));
   }
   PrintFormat("=== SYMBOL %s · %d bars available", _Symbol, have);
   PrintFormat("=== iVolume     : %s", vols);
   PrintFormat("=== iRealVolume : %s", reals);
   PrintFormat("=== bar range   : %s", rng);

   // the verdict, stated so it cannot be misread
   long v1 = iVolume(_Symbol, PERIOD_CURRENT, 1);
   bool uniform = true;
   for (int k = 2; k <= InpBars; k++)
      if (iVolume(_Symbol, PERIOD_CURRENT, k) != v1) { uniform = false; break; }
   if (uniform)
      PrintFormat("=== VERDICT: iVolume is CONSTANT at %d — the tester is reporting "
                  "generated ticks, NOT our imported volume. Every volume rule we own "
                  "has been blind in the tester.", (int)v1);
   else
      PrintFormat("=== VERDICT: iVolume VARIES — the volume is reaching the EA. "
                  "The fault is elsewhere and the next suspect is the entry logic.");

   // and the same question asked of the file's own numbers, for a direct comparison
   PrintFormat("=== the CSV we imported begins: 762 674 609 716 1062 856 1057 830 ...");
}
//+------------------------------------------------------------------+
