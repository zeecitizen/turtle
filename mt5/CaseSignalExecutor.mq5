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
input int    InpMaxSignalAgeSec = 180;  // ignore signals older than this (stale-signal guard)
input string InpSignalFile   = "case_signal.json";
input string InpHeartbeatFile = "xau_live.json";   // live price/position feed for Turtle Desktop
input string InpHistoryFile   = "xau_history.csv";   // MT5 closed-trade history for Turtle Desktop
input string InpCloseFile     = "xau_close.json";   // Claude can order an exit here

//--- Claude can order an exit. The trail already handles the fast, mechanical part far
//--- better than any human or model could (0.2pt give-back in milliseconds). This is for the
//--- judgement part: "this is turning against us, get out now" - which is the piece Zee has
//--- always said belongs to the master, not the machine.
void CheckCloseCommand()
{
   if (!FileIsExist(InpCloseFile, FILE_COMMON)) return;
   int h = FileOpen(InpCloseFile, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if (h == INVALID_HANDLE) return;
   string txt = "";
   while (!FileIsEnding(h)) txt += FileReadString(h);
   FileClose(h);
   FileDelete(InpCloseFile, FILE_COMMON);          // one command, once
   if (StringLen(txt) < 2) return;

   long ts = (long)JNum(txt, "ts");
   if (ts > 0 && (long)TimeGMT() - ts > InpMaxSignalAgeSec)
   {
      PrintFormat("[close] IGNORING stale close command (%d s old)", (int)(TimeGMT() - ts));
      return;
   }

   int closed = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if (trade.PositionClose(tk)) closed++;
   }
   PrintFormat("[close] Claude ordered an exit -> %d position(s) closed", closed);
}

//--- Export the terminal's OWN closed-trade history for this symbol. The 2026-07-31 gold
//--- trades lived only in the History tab: no CSV had them, so Turtle Desktop could not
//--- show a single real trade. Written once at init and after every close.
void ExportHistory(int days = 30)
{
   datetime from = TimeCurrent() - (datetime)days * 86400;
   if (!HistorySelect(from, TimeCurrent())) return;

   int h = FileOpen(InpHistoryFile, FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if (h == INVALID_HANDLE) return;
   FileWrite(h, "close_time", "symbol", "side", "lots", "entry", "exit", "pts", "usd",
             "magic", "comment", "ticket");

   int total = HistoryDealsTotal();
   for (int i = 0; i < total; i++)
   {
      ulong d = HistoryDealGetTicket(i);
      if (d == 0) continue;
      if (HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;   // closes only
      string sym = HistoryDealGetString(d, DEAL_SYMBOL);
      if (StringFind(sym, _Symbol) < 0) continue;

      double vol   = HistoryDealGetDouble(d, DEAL_VOLUME);
      double price = HistoryDealGetDouble(d, DEAL_PRICE);
      double usd   = HistoryDealGetDouble(d, DEAL_PROFIT)
                   + HistoryDealGetDouble(d, DEAL_SWAP)
                   + HistoryDealGetDouble(d, DEAL_COMMISSION);
      long   type  = HistoryDealGetInteger(d, DEAL_TYPE);
      // a closing SELL deal closes a BUY position, and vice versa
      string side  = (type == DEAL_TYPE_SELL) ? "BUY" : "SELL";
      long   pid   = HistoryDealGetInteger(d, DEAL_POSITION_ID);

      double entry = 0.0;                      // find this position's opening deal
      for (int k = 0; k < total; k++)
      {
         ulong o = HistoryDealGetTicket(k);
         if (o == 0) continue;
         if (HistoryDealGetInteger(o, DEAL_POSITION_ID) != pid) continue;
         if (HistoryDealGetInteger(o, DEAL_ENTRY) != DEAL_ENTRY_IN) continue;
         entry = HistoryDealGetDouble(o, DEAL_PRICE); break;
      }
      double pts = (entry > 0) ? ((side == "BUY") ? price - entry : entry - price) : 0.0;

      FileWrite(h,
                TimeToString((datetime)HistoryDealGetInteger(d, DEAL_TIME), TIME_DATE | TIME_SECONDS),
                sym, side, DoubleToString(vol, 2), DoubleToString(entry, 2),
                DoubleToString(price, 2), DoubleToString(pts, 2), DoubleToString(usd, 2),
                (string)HistoryDealGetInteger(d, DEAL_MAGIC),
                HistoryDealGetString(d, DEAL_COMMENT), (string)d);
   }
   FileClose(h);
   PrintFormat("[history] exported %s history -> %s", _Symbol, InpHistoryFile);
}

//--- Live heartbeat: Turtle Desktop needs the BROKER's own truth (price, spread, and any
//--- running position with its live P&L). Python cannot query MT5 on this ARM64 machine,
//--- so the EA publishes it to a small JSON every timer tick.
void WriteHeartbeat()
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   string pos = "";
   int    n   = 0;
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   for (int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if (n > 0) pos += ",";
      pos += StringFormat("{\"ticket\":%I64u,\"side\":\"%s\",\"lots\":%.2f,\"entry\":%.2f,"
                          "\"sl\":%.2f,\"price\":%.2f,\"profit\":%.2f,\"opened\":%I64d}",
             tk,
             (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "BUY" : "SELL"),
             PositionGetDouble(POSITION_VOLUME), PositionGetDouble(POSITION_PRICE_OPEN),
             PositionGetDouble(POSITION_SL),     PositionGetDouble(POSITION_PRICE_CURRENT),
             PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP),
             (long)PositionGetInteger(POSITION_TIME));
      n++;
   }
   string js = StringFormat("{\"symbol\":\"%s\",\"bid\":%.2f,\"ask\":%.2f,\"spread\":%.2f,"
                            "\"balance\":%.2f,\"equity\":%.2f,\"ts\":%I64d,\"positions\":[%s]}",
                            _Symbol, bid, ask, ask - bid, bal, eq, (long)TimeGMT(), pos);
   int h = FileOpen(InpHeartbeatFile, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if (h != INVALID_HANDLE) { FileWriteString(h, js); FileClose(h); }
}

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
   CheckCloseCommand();

   WriteHeartbeat();

   if (!FileIsExist(InpSignalFile, FILE_COMMON)) return;
   int h = FileOpen(InpSignalFile, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if (h == INVALID_HANDLE) return;
   string txt = "";
   while (!FileIsEnding(h)) txt += FileReadString(h);
   FileClose(h);

   long id = (long)JNum(txt, "id");
   if (id <= g_last_id) return;      // already processed
   g_last_id = id;
   // STALENESS GUARD: don't fire an old signal (matcher stopped / EA re-attached).
   long ts = (long)JNum(txt, "ts");
   if (ts > 0) {
      long age = (long)TimeGMT() - ts;
      if (age > InpMaxSignalAgeSec) { PrintFormat("[CaseExec] IGNORING stale signal #%d (%d s old)", id, age); return; }
   }
   if (HasOurPos()) return;          // one position at a time

   string side = JStr(txt, "side");
   double lots = JNum(txt, "lots"); if (lots <= 0) lots = InpDefaultLots;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   // FAST-SCALP: broker SL at the 3pt hard stop-cap (NOT the wide UHV SL) — cut losers small.
   double sl = (side == "BUY") ? (ask - SafeStopPts(InpHardSLPts)) : (bid + SafeStopPts(InpHardSLPts));
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
