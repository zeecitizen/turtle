//+------------------------------------------------------------------+
//| CaseSignalExecutor.mq5                                            |
//| Executes the pattern-matcher's TAKE signals on the DEMO account.  |
//|                                                                   |
//| Detection lives in Python (pattern_matcher.py live()) which       |
//| writes Common\Files\case_signal.json when a validated rule-stencil |
//| setup (Rule 1 / Rule 2) completes. This EA reads that file, opens  |
//| the trade, and manages the Feb-11 asymmetric exit:                 |
//|   - hard SL from the signal (cut losers small)                     |
//|   - let winners run; trailing-reversal: once +ArmPts, exit if it   |
//|     gives back GivePts from the peak; hard TP cap = runaway ceiling |
//|                                                                   |
//| Attach to XAUUSD, enable Algo Trading. DEMO only until proven.     |
//+------------------------------------------------------------------+
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>

input double InpDefaultLots = 0.10;   // fallback lots if signal omits it
input int    InpMagic       = 88020;  // CaseSignalExecutor magic
input double InpCatastPts   = 20.0;   // catastrophe backup stop (the real SL is the signal's UHV-low)
input double InpArmPts      = 8.0;    // trail arms LATE (+8pt) so winners RUN and capture the ~+24pt MFE
input double InpGivePts     = 4.0;    // give back this from the peak before exiting
input double InpTpCapPts    = 30.0;   // runaway take-profit ceiling (pts)
input string InpSignalFile  = "case_signal.json";

CTrade  trade;
long    g_last_id = -1;
double  g_peak_pts = 0.0;

int OnInit() { trade.SetExpertMagicNumber(InpMagic); EventSetTimer(1); return INIT_SUCCEEDED; }
void OnDeinit(const int r) { EventKillTimer(); }

// ── minimal JSON field readers (flat file we control) ─────────────────────
double JNum(string s, string key) {
   int p = StringFind(s, "\"" + key + "\":");
   if (p < 0) return EMPTY_VALUE;
   return StringToDouble(StringSubstr(s, p + StringLen(key) + 3));
}
string JStr(string s, string key) {
   int p = StringFind(s, "\"" + key + "\":\"");
   if (p < 0) return "";
   p += StringLen(key) + 4;
   int e = StringFind(s, "\"", p);
   return StringSubstr(s, p, e - p);
}

bool HasOurPos() {
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (PositionSelectByTicket(t)
          && PositionGetInteger(POSITION_MAGIC) == InpMagic
          && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
}

// Poll the signal file; open a trade on a NEW signal id.
void OnTimer() {
   if (!FileIsExist(InpSignalFile, FILE_COMMON)) return;
   int h = FileOpen(InpSignalFile, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if (h == INVALID_HANDLE) return;
   string txt = "";
   while (!FileIsEnding(h)) txt += FileReadString(h);
   FileClose(h);

   long id = (long)JNum(txt, "id");
   if (id <= g_last_id) return;      // already processed
   g_last_id = id;
   if (HasOurPos()) return;          // one position at a time

   string side = JStr(txt, "side");
   double lots = JNum(txt, "lots"); if (lots <= 0) lots = InpDefaultLots;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   // the SL is the signal's structural UHV-low (Zee's canonical, WR 73-77%);
   // if missing/invalid, fall back to a wide catastrophe parachute.
   double sl = JNum(txt, "sl");
   if (sl <= 0 || sl == EMPTY_VALUE)
      sl = (side == "BUY") ? (ask - InpCatastPts) : (bid + InpCatastPts);
   g_peak_pts = 0.0;
   if (side == "BUY")       trade.Buy(lots, _Symbol, 0, sl, 0, "case");
   else if (side == "SELL") trade.Sell(lots, _Symbol, 0, sl, 0, "case");
   PrintFormat("[CaseExec] signal #%d %s lots=%.2f sl(UHV)=%.2f", id, side, lots, sl);
}

// Manage the Feb-11 exit on every tick.
void OnTick() {
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (!PositionSelectByTicket(t)) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagic
          || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      bool isbuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double prof = isbuy ? (bid - entry) : (entry - ask);   // favourable move, price pts
      if (prof > g_peak_pts) g_peak_pts = prof;
      // catastrophe backup (broker SL from the signal's UHV-low is the primary stop)
      if (prof <= -InpCatastPts) { trade.PositionClose(t); g_peak_pts = 0; continue; }
      // runaway take-profit ceiling
      if (prof >= InpTpCapPts) { trade.PositionClose(t); g_peak_pts = 0; continue; }
      // trailing-reversal: let it run, exit on give-back after arming
      if (g_peak_pts >= InpArmPts && (g_peak_pts - prof) >= InpGivePts) {
         trade.PositionClose(t); g_peak_pts = 0; continue;
      }
   }
}
//+------------------------------------------------------------------+
