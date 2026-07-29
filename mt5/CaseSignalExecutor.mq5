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
input double InpHardSLPts    = 3.0;    // FAST-SCALP hard stop-cap: cut losers at 3pt (Zee Feb-11 losers were tiny)
input double InpArmPts       = 0.3;    // arm at +0.3pt -> catch the guaranteed initial pop
input double InpGivePts      = 0.2;    // exit on 0.2pt reversal from peak (seconds-scalp)
input double InpTpCapPts     = 3.0;    // take-profit ceiling 3pt. dom=0 fast-scalp: ~115/day, ~79% WR
input string InpSignalFile   = "case_signal.json";

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

// Log the REAL fill (entry, exit, actual points P&L) so the dashboard shows the true
// result, not a bar-level simulation.
void LogFill(bool isbuy, double entry, double exitpx, double lots, double prof_pts, string reason) {
   int h = FileOpen("caseexec_fills.csv", FILE_READ | FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if (h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   double usd = prof_pts * lots * 100.0;
   FileWrite(h, TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS), (isbuy ? "BUY" : "SELL"),
             DoubleToString(entry, 2), DoubleToString(exitpx, 2), DoubleToString(lots, 2),
             DoubleToString(prof_pts, 2), DoubleToString(usd, 2), reason);
   FileClose(h);
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
   // FAST-SCALP: broker SL at the 3pt hard stop-cap (NOT the wide UHV SL) — cut losers small.
   double sl = (side == "BUY") ? (ask - InpHardSLPts) : (bid + InpHardSLPts);
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
      double lots = PositionGetDouble(POSITION_VOLUME);
      double expx = isbuy ? bid : ask;
      // fast-scalp hard stop-cap (backup to the broker SL) — cut losers at 3pt
      if (prof <= -InpHardSLPts) { LogFill(isbuy, entry, expx, lots, prof, "stop"); trade.PositionClose(t); g_peak_pts = 0; continue; }
      // runaway take-profit ceiling
      if (prof >= InpTpCapPts) { LogFill(isbuy, entry, expx, lots, prof, "tp"); trade.PositionClose(t); g_peak_pts = 0; continue; }
      // trailing-reversal: let it run, exit on give-back after arming
      if (g_peak_pts >= InpArmPts && (g_peak_pts - prof) >= InpGivePts) {
         LogFill(isbuy, entry, expx, lots, prof, "harvest"); trade.PositionClose(t); g_peak_pts = 0; continue;
      }
   }
}
//+------------------------------------------------------------------+
