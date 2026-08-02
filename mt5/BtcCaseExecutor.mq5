//+------------------------------------------------------------------+
//| BtcCaseExecutor.mq5 — BTC variant of the fast-scalp executor.     |
//|                                                                   |
//| SEPARATE from CaseSignalExecutor (XAUUSD) in every way so the two |
//| can never cross-fire:                                             |
//|   - own magic 88022                                               |
//|   - own signal file  btc_signal.json  (written by btc_live_matcher)|
//|   - SYMBOL GUARD: refuses to run unless the chart symbol has "BTC" |
//|                                                                   |
//| BTC moves ~4.5x more per M1 bar than XAUUSD, so the exit is scaled:|
//|   stop/tp 14 pts, arm 1.4, give-back 0.9  (gold: 3 / 0.3 / 0.2)   |
//|                                                                   |
//| LOTS ARE RISK-BASED: we size from InpRiskUsd and the symbol's real |
//| tick value, so a wrong contract-size assumption can't blow up the  |
//| account. Hard-capped by InpMaxLots.                                |
//|                                                                   |
//| Volume feed for detection is COINBASE:BTCUSD (OANDA BTC volume is  |
//| useless: spike ratio only 1.37x, i.e. no detectable UHV).          |
//|                                                                   |
//| Attach to the BTC chart, Algo Trading on. DEMO only.               |
//+------------------------------------------------------------------+
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>

input int    InpMagic     = 88022;   // BTC executor magic (distinct from 88020/88021)
input double InpRiskUsd   = 3.0;     // $ risked per 1x trade (lots derived from this)
input double InpMaxLots   = 0.10;    // hard cap — safety against contract-size surprises
input double InpStopPts   = 14.0;    // BTC-scaled hard stop (gold 3 x 4.5)
input double InpArmPts    = 1.4;     // trail arms here (gold 0.3 x 4.5)
input double InpGivePts   = 0.9;     // give-back from peak to exit (gold 0.2 x 4.5)
input double InpTpCapPts  = 14.0;    // take-profit ceiling
input int    InpMaxSignalAgeSec = 180;  // ignore signals older than this (stale-signal guard)
input string InpSignalFile = "btc_signal.json";

//--- Brokers enforce a minimum distance between price and the stop (SYMBOL_TRADE_STOPS_LEVEL,
//--- plus the spread for a market order). Our scalp stops are deliberately tight, so on
//--- 2026-08-02 EVERY BTC order came back [invalid stops] and nothing traded all session.
//--- Widen the stop to the broker's own minimum whenever ours is tighter.
double SafeStopPts(double wanted)
{
   long   lvl    = (long)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   long   frz    = (long)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * point;
   double minpts = (double)MathMax(lvl, frz) * point + spread;
   if (minpts <= 0) minpts = spread * 2.0;             // some brokers report 0
   double need = minpts * 1.15 + point;                // small buffer over the wire
   if (wanted < need)
   {
      PrintFormat("[stops] SL widened %.2f -> %.2f (broker min %.2f incl spread %.2f)",
                  wanted, need, minpts, spread);
      return need;
   }
   return wanted;
}

CTrade  trade;
long    g_last_id = -1;
double  g_peak_pts = 0.0;

int OnInit() {
   if (StringFind(_Symbol, "BTC") < 0 && StringFind(_Symbol, "btc") < 0) {
      Print("[BtcExec] REFUSING: chart symbol '", _Symbol, "' is not BTC. Attach to the BTC chart.");
      return INIT_FAILED;
   }
   trade.SetExpertMagicNumber(InpMagic);
   EventSetTimer(1);
   PrintFormat("[BtcExec] ready on %s — contract %.4f, tickval %.5f, ticksize %.5f",
               _Symbol, SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE),
               SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE),
               SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE));
   return INIT_SUCCEEDED;
}
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

// $ per 1.0 price point per 1.0 lot, from the broker's own spec (no assumptions).
double MoneyPerPointPerLot() {
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if (ts <= 0 || tv <= 0) return 0;
   return tv / ts;
}

// lots so that a full InpStopPts stop loses ~ risk_usd
double LotsForRisk(double risk_usd) {
   double mpp = MoneyPerPointPerLot();
   if (mpp <= 0) return SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lots = risk_usd / (InpStopPts * mpp);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if (step > 0) lots = MathFloor(lots / step) * step;
   lots = MathMax(lots, vmin);
   lots = MathMin(lots, InpMaxLots);
   return NormalizeDouble(lots, 2);
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

void LogFill(bool isbuy, double entry, double exitpx, double lots, double pts, string reason) {
   int h = FileOpen("btc_fills.csv", FILE_READ | FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if (h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS), (isbuy ? "BUY" : "SELL"),
             DoubleToString(entry, 2), DoubleToString(exitpx, 2), DoubleToString(lots, 2),
             DoubleToString(pts, 2), DoubleToString(pts * lots * MoneyPerPointPerLot(), 2), reason);
   FileClose(h);
}

// Poll btc_signal.json; open on a NEW id.
void OnTimer() {
   if (!FileIsExist(InpSignalFile, FILE_COMMON)) return;
   int h = FileOpen(InpSignalFile, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if (h == INVALID_HANDLE) return;
   string txt = ""; while (!FileIsEnding(h)) txt += FileReadString(h);
   FileClose(h);

   long id = (long)JNum(txt, "id");
   if (id <= g_last_id) return;
   g_last_id = id;
   // STALENESS GUARD: never act on an old signal (e.g. matcher stopped, EA re-attached).
   // Firing a 3-hour-old setup at the current price is how you lose money for nothing.
   long ts = (long)JNum(txt, "ts");
   if (ts > 0) {
      long age = (long)TimeGMT() - ts;
      if (age > InpMaxSignalAgeSec) {
         PrintFormat("[BtcExec] IGNORING stale signal #%d (%d s old)", id, age);
         return;
      }
   }
   if (HasOurPos()) return;

   string side = JStr(txt, "side");
   if (side != "BUY" && side != "SELL") return;
   double mult = JNum(txt, "mult");            // conviction multiplier (0.25 / 1 / 2 / 3)
   if (mult <= 0 || mult == EMPTY_VALUE) mult = 1.0;
   double lots = LotsForRisk(InpRiskUsd * mult);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl  = (side == "BUY") ? (ask - SafeStopPts(InpStopPts)) : (bid + SafeStopPts(InpStopPts));
   g_peak_pts = 0.0;
   bool ok = (side == "BUY") ? trade.Buy(lots, _Symbol, 0, sl, 0, "btc")
                             : trade.Sell(lots, _Symbol, 0, sl, 0, "btc");
   PrintFormat("[BtcExec] signal #%d %s lots=%.2f (mult %.2f, risk $%.2f) sl=%.2f ok=%d",
               id, side, lots, mult, InpRiskUsd * mult, sl, ok);
}

// BTC-scaled fast-harvest exit.
void OnTick() {
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (!PositionSelectByTicket(t)) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagic
          || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      bool isbuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double lots  = PositionGetDouble(POSITION_VOLUME);
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double prof = isbuy ? (bid - entry) : (entry - ask);
      double expx = isbuy ? bid : ask;
      if (prof > g_peak_pts) g_peak_pts = prof;
      if (prof <= -InpStopPts)  { LogFill(isbuy, entry, expx, lots, prof, "stop");    trade.PositionClose(t); g_peak_pts = 0; continue; }
      if (prof >=  InpTpCapPts) { LogFill(isbuy, entry, expx, lots, prof, "tp");      trade.PositionClose(t); g_peak_pts = 0; continue; }
      if (g_peak_pts >= InpArmPts && (g_peak_pts - prof) >= InpGivePts) {
         LogFill(isbuy, entry, expx, lots, prof, "harvest"); trade.PositionClose(t); g_peak_pts = 0; continue;
      }
   }
}
//+------------------------------------------------------------------+
