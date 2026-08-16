//+------------------------------------------------------------------+
//| SecondScaleProbe.mq5 — is Zee's setup FRACTAL?                    |
//|                                                                  |
//| Zee, 2026-08-16: "if we look at the 15 minute bars, one bar       |
//| breaks into 15 bars of 1 minute. so our retracement, our UHV, our |
//| breakout all happen inside one bar of higher time frame .. the    |
//| bars of 1 minute timeframe can be divided into 60 bars of 1       |
//| second. on that scale we can find out a trend, a retracement, a   |
//| uhv, a breakout on that micro scale. and if our law holds there,  |
//| we would be taking trades on every single 1 minute bar."          |
//|                                                                  |
//| THE THEORY IS TESTABLE AND THIS TESTS IT — no Python, real ticks. |
//| MT5 has no 1-second timeframe, so this BUILDS one from the        |
//| broker's own ticks and then runs THE SAME RULE CHAIN over it:     |
//| TrendNow -> RetracementOrigin -> FindUhv -> BreakoutIsBar1, with  |
//| the same inputs the live EA uses. It trades NOTHING; it counts.   |
//|                                                                  |
//| Three things must all be true for the theory to pay:              |
//|   1. the structure must FORM at that scale (enough resolution)    |
//|   2. VOLUME must still discriminate — a UHV needs to stand out,   |
//|      and a 1-second bar may hold only 2 or 3 ticks                |
//|   3. the move must clear the SPREAD, or the edge is eaten before  |
//|      it starts                                                    |
//| This reports all three plus the setup count, so the answer is a   |
//| measurement and not an argument.                                  |
//+------------------------------------------------------------------+
#property copyright "Zeeshan + Claude"
#property version   "1.00"
#property strict

input int    InpSecBars     = 400;   // rolling 1-second bars to keep
input int    InpTrendLook   = 20;    // identical to the live EA
input int    InpPivot       = 2;     // identical
input int    InpRetraceBack = 20;    // identical
input double InpUhvBodyMin  = 0.5;   // identical
input int    InpBreakWindow = 12;    // identical
input bool   InpRequireTrend = true; // identical

// ── the 1-second bars we build from ticks ────────────────────────────────────
double sO[], sH[], sL[], sC[];
long   sV[];
datetime sT[];
int    nS = 0;                 // how many are filled (index 0 = NEWEST)
datetime curSec = 0;
double cO, cH, cL, cC; long cV = 0;

// ── measurement ──────────────────────────────────────────────────────────────
long   totTicks = 0, totSecs = 0, emptyRuns = 0;
double sumSpread = 0; long nSpread = 0;
double sumSecRange = 0; long nSecRange = 0;
long   volHist[11];            // ticks-per-second histogram, 10+ in the last bucket
long   setups = 0, trendOK = 0, retraceOK = 0, uhvOK = 0;
double sumWin40 = 0; long nWin40 = 0;   // price travel over the rule's lookback

int OnInit() {
   ArrayResize(sO, InpSecBars); ArrayResize(sH, InpSecBars);
   ArrayResize(sL, InpSecBars); ArrayResize(sC, InpSecBars);
   ArrayResize(sV, InpSecBars); ArrayResize(sT, InpSecBars);
   ArrayInitialize(volHist, 0);
   Print("[SEC] building 1-second bars from real ticks; the rule chain is the live EA's");
   return INIT_SUCCEEDED;
}

bool GreenS(int i) { return sC[i] > sO[i]; }
bool RedS(int i)   { return sC[i] < sO[i]; }
double BodyHiS(int i) { return MathMax(sO[i], sC[i]); }
double BodyLoS(int i) { return MathMin(sO[i], sC[i]); }

//--- push the completed second onto the rolling array (0 = newest)
void PushSecond() {
   for (int i = InpSecBars - 1; i > 0; i--) {
      sO[i] = sO[i-1]; sH[i] = sH[i-1]; sL[i] = sL[i-1];
      sC[i] = sC[i-1]; sV[i] = sV[i-1]; sT[i] = sT[i-1];
   }
   sO[0] = cO; sH[0] = cH; sL[0] = cL; sC[0] = cC; sV[0] = cV; sT[0] = curSec;
   if (nS < InpSecBars) nS++;
   totSecs++;
   volHist[(int)MathMin(cV, 10)]++;
   sumSecRange += (cH - cL); nSecRange++;
}

//--- THE SAME RULES, on second bars ------------------------------------------
int TrendNowS() {
   double highs[]; double lows[];
   ArrayResize(highs, 0); ArrayResize(lows, 0);
   for (int k = InpTrendLook; k >= InpPivot + 1; k--) {
      if (k + InpPivot >= nS) continue;
      bool ph = true, pl = true;
      for (int d = 1; d <= InpPivot; d++) {
         if (sH[k] < sH[k-d] || sH[k] < sH[k+d]) ph = false;
         if (sL[k] > sL[k-d] || sL[k] > sL[k+d]) pl = false;
      }
      if (ph) { int n = ArraySize(highs); ArrayResize(highs, n+1); highs[n] = sH[k]; }
      if (pl) { int n = ArraySize(lows);  ArrayResize(lows,  n+1); lows[n]  = sL[k]; }
   }
   int nh = ArraySize(highs), nl = ArraySize(lows);
   if (nh < 2 || nl < 2) return 0;
   if (highs[nh-1] > highs[nh-2] && lows[nl-1] > lows[nl-2]) return +1;
   if (highs[nh-1] < highs[nh-2] && lows[nl-1] < lows[nl-2]) return -1;
   return 0;
}

// FAITHFUL to ZeeUHV.mq5. The first draft of this compared bar k against bar k+1
// WHATEVER ITS COLOUR — which is the precise bug the Pine changelog recorded fixing in
// April ("_bRet used close < low[1], any colour, and falsely triggered"). The real rule
// walks forward to the first OPPOSITE-coloured bar within 8 and measures against that.
int RetracementOriginS(int side) {
   bool wantRed = (side > 0);
   for (int k = 1; k <= InpRetraceBack; k++) {
      if (k + 9 >= nS) break;
      if (wantRed  && !RedS(k))   continue;
      if (!wantRed && !GreenS(k)) continue;
      int prev = -1;
      for (int j = k + 1; j <= k + 8; j++) {
         if (wantRed ? GreenS(j) : RedS(j)) { prev = j; break; }
      }
      if (prev < 0) continue;
      if (wantRed) { if (BodyLoS(k) < sL[prev]) return k; }
      else         { if (BodyHiS(k) > sH[prev]) return k; }
   }
   return -1;
}

int FindUhvS(int origin, int side) {
   bool wantRed = (side > 0);
   int best = -1; long bestv = -1;
   for (int k = origin; k >= 1; k--) {
      if (wantRed && !RedS(k)) continue;
      if (!wantRed && !GreenS(k)) continue;
      if (sV[k] > bestv) { bestv = sV[k]; best = k; }
   }
   if (best < 1) return -1;
   double rng = sH[best] - sL[best];
   if (rng <= 0 || MathAbs(sC[best] - sO[best]) / rng < InpUhvBodyMin) return -1;
   // THE LOCAL-PEAK TEST, which the first draft of this probe omitted entirely. It is
   // hardcoded in the live EA, not optional, and the ablation showed it is the gate that
   // protects the edge — dropping it turned +1.60/trade into -0.52.
   if (best + 1 < nS && sV[best + 1] > sV[best]) return -1;
   if (best > 1 && sV[best - 1] > sV[best]) return -1;
   return best;
}

bool BreakoutIsBar1S(int uhv, int side) {
   if (uhv <= 1) return false;
   bool wantGreen = (side > 0);
   for (int k = uhv - 1; k >= 1; k--) {
      if (wantGreen && !GreenS(k)) continue;
      if (!wantGreen && !RedS(k)) continue;
      bool crossed = wantGreen ? (BodyHiS(k) > sH[uhv]) : (BodyLoS(k) < sL[uhv]);
      if (!crossed) continue;
      if (sV[k] >= sV[uhv]) return false;
      return (k == 1);
   }
   return false;
}

void CheckRules() {
   if (nS < InpTrendLook + InpPivot + 2) return;
   int t = TrendNowS();
   if (t == 0) { if (!InpRequireTrend) return; else return; }
   trendOK++;
   int o = RetracementOriginS(t);
   if (o < 0) return;
   retraceOK++;
   int u = FindUhvS(o, t);
   if (u < 0) return;
   uhvOK++;
   if (!BreakoutIsBar1S(u, t)) return;
   setups++;
   // how far did price travel across the window the rules just read?
   double hi = sH[0], lo = sL[0];
   for (int k = 1; k <= MathMin(InpTrendLook, nS-1); k++) {
      if (sH[k] > hi) hi = sH[k];
      if (sL[k] < lo) lo = sL[k];
   }
   sumWin40 += (hi - lo); nWin40++;
}

void OnTick() {
   MqlTick tk;
   if (!SymbolInfoTick(_Symbol, tk)) return;
   totTicks++;
   if (tk.ask > 0 && tk.bid > 0) { sumSpread += (tk.ask - tk.bid); nSpread++; }
   double px = tk.bid;
   datetime sec = tk.time;                       // MqlTick.time is second resolution

   if (curSec == 0) { curSec = sec; cO = cH = cL = cC = px; cV = 1; return; }
   if (sec != curSec) {
      PushSecond();
      if (sec - curSec > 1) emptyRuns += (long)(sec - curSec - 1);   // seconds with NO tick
      CheckRules();
      curSec = sec; cO = cH = cL = cC = px; cV = 1;
      return;
   }
   if (px > cH) cH = px;
   if (px < cL) cL = px;
   cC = px; cV++;
}

void OnDeinit(const int reason) {
   Print("[SEC] ===================== RESULT =====================");
   PrintFormat("[SEC] ticks %d · seconds WITH a tick %d · seconds with NONE %d",
               (int)totTicks, (int)totSecs, (int)emptyRuns);
   if (totSecs > 0)
      PrintFormat("[SEC] ticks per ticked-second: mean %.2f", (double)totTicks / totSecs);
   string h = "";
   for (int i = 0; i <= 10; i++)
      h += StringFormat("%d:%d ", i, (int)volHist[i]);
   PrintFormat("[SEC] ticks-per-second histogram (10 = 10+): %s", h);
   if (nSpread > 0) PrintFormat("[SEC] mean spread %.4f pts", sumSpread / nSpread);
   if (nSecRange > 0) PrintFormat("[SEC] mean 1-SECOND range %.4f pts", sumSecRange / nSecRange);
   if (nWin40 > 0)
      PrintFormat("[SEC] mean price travel across the %d-bar lookback at a setup: %.4f pts",
                  InpTrendLook, sumWin40 / nWin40);
   Print("[SEC] --- the rule chain, on 1-second bars ---");
   PrintFormat("[SEC] trend not flat  : %d", (int)trendOK);
   PrintFormat("[SEC] + retracement   : %d", (int)retraceOK);
   PrintFormat("[SEC] + lawful UHV    : %d", (int)uhvOK);
   PrintFormat("[SEC] + BREAKOUT      : %d   <-- COMPLETE SETUPS", (int)setups);
   if (totSecs > 0)
      PrintFormat("[SEC] that is one setup every %.1f seconds (%.2f per MINUTE)",
                  setups > 0 ? (double)totSecs / setups : 0.0,
                  setups > 0 ? 60.0 * setups / totSecs : 0.0);
   Print("[SEC] ==================================================");
}

double OnTester() { return 0.0; }
