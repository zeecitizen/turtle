//+------------------------------------------------------------------+
//| CaseSignalExecutorProbe.mq5                                       |
//| PROBE-SCALE-IN variant of CaseSignalExecutor (Zee 2026-07-29).    |
//|                                                                   |
//| On a signal it opens a tiny PROBE (0.01) in the breakout          |
//| direction. If the probe ACCELERATES positive it scales the        |
//| position up in tiers (0.10 -> 0.40 -> 0.80). If the probe fails   |
//| (goes adverse while still tiny) it cuts immediately for a ~$0.5   |
//| loss. Exit on the fast-harvest (arm/give) or the 3pt cap.         |
//|                                                                   |
//| Validated on OANDA (bar-level): higher net + worst trade ~ -$1    |
//| vs conviction's -$120, but lower WR (~38% — many tiny probe cuts).|
//|                                                                   |
//| SEPARATE magic 88021 so it never fights the original 88020 EA.    |
//| Attach ONE at a time. DEMO only until proven.                     |
//+------------------------------------------------------------------+
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>

input int    InpMagic      = 88021;   // probe-variant magic (distinct from 88020)
input double InpProbeLots  = 0.01;    // initial probe size
input double InpArmPts     = 0.3;     // harvest arms at +0.3pt
input double InpGivePts    = 0.2;     // exit on 0.2pt give-back from peak
input double InpCapPts     = 3.0;     // hard adverse cap
input double InpProbeCut   = 0.5;     // cut the probe if it goes -0.5pt while still tiny
// scale tiers: when peak favourable crosses Trig, grow TOTAL to Lot
input double InpT1Trig     = 0.5;   input double InpT1Lot = 0.10;
input double InpT2Trig     = 1.0;   input double InpT2Lot = 0.40;
input double InpT3Trig     = 1.5;   input double InpT3Lot = 0.80;
input string InpSignalFile = "case_signal.json";

CTrade  trade;
long    g_last_id = -1;
// live probe-trade state
bool    g_active = false;
bool    g_isbuy  = false;
double  g_entry  = 0.0;   // probe entry (reference for prof/peak)
double  g_peak   = 0.0;   // peak favourable pts
int     g_tier   = 0;     // 0 = probe only, 1/2/3 = scaled

int OnInit() { trade.SetExpertMagicNumber(InpMagic); EventSetTimer(1); return INIT_SUCCEEDED; }
void OnDeinit(const int r) { EventKillTimer(); }

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

// sum floating P&L + total volume across OUR positions
void OurBook(double &usd, double &lots) {
   usd = 0; lots = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (PositionSelectByTicket(t)
          && PositionGetInteger(POSITION_MAGIC) == InpMagic
          && PositionGetString(POSITION_SYMBOL) == _Symbol) {
         usd  += PositionGetDouble(POSITION_PROFIT);
         lots += PositionGetDouble(POSITION_VOLUME);
      }
   }
}

void LogClose(double usd, double lots, double prof_pts, string reason) {
   int h = FileOpen("caseexec_fills.csv", FILE_READ | FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if (h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS), (g_isbuy ? "BUY" : "SELL"),
             DoubleToString(g_entry, 2), "probe", DoubleToString(lots, 2),
             DoubleToString(prof_pts, 2), DoubleToString(usd, 2), reason);
   FileClose(h);
}

void CloseAll(string reason, double prof_pts) {
   double usd, lots; OurBook(usd, lots);
   LogClose(usd, lots, prof_pts, reason);
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (PositionSelectByTicket(t)
          && PositionGetInteger(POSITION_MAGIC) == InpMagic
          && PositionGetString(POSITION_SYMBOL) == _Symbol)
         trade.PositionClose(t);
   }
   g_active = false; g_tier = 0; g_peak = 0;
}

// grow the TOTAL position to targetLot by adding the delta at market
void ScaleTo(double targetLot) {
   double usd, cur; OurBook(usd, cur);
   double add = targetLot - cur;
   if (add < 0.005) return;
   if (g_isbuy) trade.Buy(add, _Symbol, 0, 0, 0, "probe-scale");
   else         trade.Sell(add, _Symbol, 0, 0, 0, "probe-scale");
}

// Open the probe on a NEW signal id.
void OnTimer() {
   if (g_active) return;                       // one probe-trade at a time
   if (!FileIsExist(InpSignalFile, FILE_COMMON)) return;
   int h = FileOpen(InpSignalFile, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if (h == INVALID_HANDLE) return;
   string txt = ""; while (!FileIsEnding(h)) txt += FileReadString(h);
   FileClose(h);

   long id = (long)JNum(txt, "id");
   if (id <= g_last_id) return;
   g_last_id = id;

   string side = JStr(txt, "side");
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   g_isbuy = (side == "BUY");
   double sl = g_isbuy ? (ask - InpCapPts) : (bid + InpCapPts);   // 3pt parachute
   bool ok = g_isbuy ? trade.Buy(InpProbeLots, _Symbol, 0, sl, 0, "probe")
                     : trade.Sell(InpProbeLots, _Symbol, 0, sl, 0, "probe");
   if (!ok) return;
   g_entry = g_isbuy ? ask : bid;
   g_peak = 0; g_tier = 0; g_active = true;
   PrintFormat("[Probe] #%d %s probe %.2f @ %.2f", id, side, InpProbeLots, g_entry);
}

// Manage the probe: scale on acceleration, cut on failure, harvest the winners.
void OnTick() {
   if (!g_active) return;
   // if somehow flat (manual close), reset
   double bookUsd, bookLots; OurBook(bookUsd, bookLots);
   if (bookLots < 0.005) { g_active = false; g_tier = 0; g_peak = 0; return; }

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double prof = g_isbuy ? (bid - g_entry) : (g_entry - ask);   // favourable pts from probe entry
   if (prof > g_peak) g_peak = prof;

   // 1) CUT the probe early if it fails while still tiny (tier 0)
   if (g_tier == 0 && prof <= -InpProbeCut) { CloseAll("probe-fail", prof); return; }
   // 2) hard adverse cap (safety for scaled positions)
   if (prof <= -InpCapPts) { CloseAll("cap", prof); return; }
   // 3) SCALE UP on acceleration (peak crossing tiers)
   if (g_tier < 1 && g_peak >= InpT1Trig) { ScaleTo(InpT1Lot); g_tier = 1; }
   if (g_tier < 2 && g_peak >= InpT2Trig) { ScaleTo(InpT2Lot); g_tier = 2; }
   if (g_tier < 3 && g_peak >= InpT3Trig) { ScaleTo(InpT3Lot); g_tier = 3; }
   // 4) HARVEST: once armed, exit the whole book on give-back from peak
   if (g_peak >= InpArmPts && (g_peak - prof) >= InpGivePts) { CloseAll("harvest", prof); return; }
}
//+------------------------------------------------------------------+
