//+------------------------------------------------------------------+
//| BarProbe.mq5 — what colour and volume did the EA ACTUALLY see?   |
//|                                                                  |
//| Zee, 2026-08-16: "ye dono candles green marked hain? issko thora |
//| check kr saktay hain? kyunk normally uhv ka color opposite hota  |
//| hai" — he spotted a SELL whose marked candles looked green, and  |
//| his rule says a SELL's UHV must be GREEN and its breakout RED.   |
//|                                                                  |
//| The forensic chart draws OANDA bars. The EA reads BLUEBERRY. We  |
//| already know those two disagree: on the 21:18 SELL the EA logged |
//| the UHV's volume as 206 while OANDA's bar for the same minute    |
//| holds 378. So an OANDA candle cannot settle what the EA saw.     |
//|                                                                  |
//| This trades NOTHING. It prints the broker's own O/H/L/C, colour  |
//| and REAL volume for a window of M1 bars, so the EA's rule can be |
//| checked against the data the EA was actually looking at.         |
//+------------------------------------------------------------------+
#property copyright "Zeeshan + Claude"
#property version   "1.00"
#property strict

input string InpFrom = "2026.08.14 20:10";   // window start (broker time)
input string InpTo   = "2026.08.14 20:20";   // window end

datetime g_from, g_to;
bool     g_done = false;

int OnInit() {
   g_from = StringToTime(InpFrom);
   g_to   = StringToTime(InpTo);
   PrintFormat("[BARS] %s -> %s (broker time)", InpFrom, InpTo);
   return INIT_SUCCEEDED;
}

// The tester overwrites tick_volume with a synthesised count and preserves real_volume,
// so every volume rule in this project reads iRealVolume first. Same here or the numbers
// would not be comparable with the EA's own log lines.
long BarVol(int i) {
   long rv = iRealVolume(_Symbol, PERIOD_M1, i);
   if (rv > 0) return rv;
   return iVolume(_Symbol, PERIOD_M1, i);
}

void OnTick() {
   if (g_done) return;
   if (TimeCurrent() < g_to) return;          // wait until the window has passed
   g_done = true;

   int total = Bars(_Symbol, PERIOD_M1);
   int shown = 0;
   for (int i = total - 1; i >= 0; i--) {
      datetime bt = iTime(_Symbol, PERIOD_M1, i);
      if (bt < g_from || bt > g_to) continue;
      double o = iOpen (_Symbol, PERIOD_M1, i);
      double c = iClose(_Symbol, PERIOD_M1, i);
      string col = (c > o) ? "GREEN" : ((c < o) ? "RED  " : "flat ");
      PrintFormat("[BARS] %s  shift %3d  O %.2f  C %.2f  %s  vol %d",
                  TimeToString(bt, TIME_MINUTES), i, o, c, col, (int)BarVol(i));
      shown++;
   }
   PrintFormat("[BARS] %d bars printed", shown);
}

double OnTester() { return 0.0; }
