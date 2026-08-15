//+------------------------------------------------------------------+
//| SpikeProbe.mq5 — did the ASK really touch 4366.17?               |
//|                                                                  |
//| Zee, 2026-08-14: "on the chart the price was never 4366 around    |
//| that point so how did the log say BUY at 4366.17"                 |
//|                                                                  |
//| The live EA logged BUY @4366.17 and filled at 4360.7. Both OANDA  |
//| and TradingView show ~4360.8 at that minute. So either Blueberry  |
//| genuinely quoted 4366.17 for an instant — a spike only its own    |
//| feed would contain — or SymbolInfoDouble handed the EA a price    |
//| that never existed.                                               |
//|                                                                  |
//| This trades NOTHING. It walks the broker's own stored ticks and   |
//| reports, per minute, the highest ASK and the widest SPREAD it     |
//| can find. If 4366 appears here, it was a real quote. If the ask   |
//| never leaves the 4361 area, the price the EA acted on did not     |
//| come from the market.                                             |
//+------------------------------------------------------------------+
#property copyright "Zeeshan + Claude"
#property version   "1.00"
#property strict

input string InpFrom     = "2026.08.14 02:00";  // window start (broker time)
input string InpTo       = "2026.08.14 02:30";  // window end
input double InpLookFor  = 4366.17;             // the price in question

datetime g_from, g_to;
bool     g_done = false;

int OnInit() {
   g_from = StringToTime(InpFrom);
   g_to   = StringToTime(InpTo);
   PrintFormat("[SPIKE] scanning %s -> %s for an ask near %.2f",
               InpFrom, InpTo, InpLookFor);
   return INIT_SUCCEEDED;
}

void OnTick() {
   if (g_done) return;
   if (TimeCurrent() < g_to) return;      // wait until the window has passed
   g_done = true;

   MqlTick t[];
   int n = CopyTicksRange(_Symbol, t, COPY_TICKS_ALL,
                          (long)g_from * 1000, (long)g_to * 1000);
   if (n <= 0) {
      PrintFormat("[SPIKE] NO TICKS returned for that window (err %d) — "
                  "the broker's stored history does not cover it", GetLastError());
      return;
   }
   PrintFormat("[SPIKE] %d ticks in the window", n);

   double best_ask = 0, worst_spread = 0;
   datetime best_at = 0, worst_at = 0;
   int near = 0;
   // per-minute summary so the shape is visible, not just the extremes
   datetime cur = 0; double mn_hi = 0, mn_lo = 0, mn_sp = 0;
   for (int i = 0; i < n; i++) {
      double a = t[i].ask, b = t[i].bid;
      if (a <= 0 || b <= 0) continue;
      double sp = a - b;
      if (a > best_ask) { best_ask = a; best_at = t[i].time; }
      if (sp > worst_spread) { worst_spread = sp; worst_at = t[i].time; }
      if (MathAbs(a - InpLookFor) < 0.50) near++;

      datetime m = t[i].time - (t[i].time % 60);
      if (m != cur) {
         if (cur != 0)
            PrintFormat("[SPIKE] %s  ask %.2f-%.2f  widest spread %.2f",
                        TimeToString(cur, TIME_MINUTES), mn_lo, mn_hi, mn_sp);
         cur = m; mn_hi = a; mn_lo = a; mn_sp = sp;
      } else {
         if (a > mn_hi) mn_hi = a;
         if (a < mn_lo) mn_lo = a;
         if (sp > mn_sp) mn_sp = sp;
      }
   }
   if (cur != 0)
      PrintFormat("[SPIKE] %s  ask %.2f-%.2f  widest spread %.2f",
                  TimeToString(cur, TIME_MINUTES), mn_lo, mn_hi, mn_sp);

   PrintFormat("[SPIKE] ===== HIGHEST ASK IN WINDOW: %.2f at %s",
               best_ask, TimeToString(best_at, TIME_DATE | TIME_SECONDS));
   PrintFormat("[SPIKE] ===== WIDEST SPREAD: %.2f at %s",
               worst_spread, TimeToString(worst_at, TIME_DATE | TIME_SECONDS));
   PrintFormat("[SPIKE] ===== ticks within 0.50 of %.2f : %d", InpLookFor, near);
   PrintFormat("[SPIKE] ===== VERDICT: %s",
               near > 0 ? "that price DID exist in the broker's own feed"
                        : "that price NEVER appeared — it did not come from the market");
}

double OnTester() { return 0.0; }
