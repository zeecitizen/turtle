//+------------------------------------------------------------------+
//| UhvEntryReplay.mq5                                               |
//| MT5 execution of the Turtle TV UHV tester's own entries.         |
//|                                                                  |
//| Zee 2026-11-12: "test all settings with winrate above 99% ... on |
//| MT5". ZeeUHV_TurtleTV implements 52 inputs; the >99% saves use   |
//| up to 40 UHV filters it does not have, so running them through   |
//| it would test a looser strategy under their names. This EA takes |
//| the entries the tester chose (time, side, stop price, target     |
//| pips) from a CSV in Common\Files and executes each one on the    |
//| real ticks: a market order at the first tick at or after the     |
//| entry time, with the tester's stop and the fixed target (see     |
//| v1.01). The tester's filters decide WHICH trades; MT5 decides    |
//| what they make. Label results "MT5 execution of tester entries". |
//|                                                                  |
//| v1.01: EURUSDp's stops level rejects a 0.1-pip broker target, so  |
//| the target is a software close at the touch, measured from MT5's |
//| own fill (as ZeeUHV_TurtleTV v1.03 does); the stop stays on the  |
//| order. Live PXTrader accepts the 0.1-pip broker target.          |
//| v1.02: targets are registered from the position list on every tick |
//| (with random delay the position can appear after the order), and |
//| every position's result + whether its target was touched goes to |
//| Common\Files\<InpFile>.out.csv (broker-held-target equivalent).   |
//| v1.03: InpEjectPips (0 = off) closes a position at market once it is that many pips against  |
//| its own fill (bid for a buy, ask for a sell) - the live game player's eject (3 pips, harvest). |
//| v1.04 SPEED (Zee: "each run should take not more than 90 seconds"): every tick walked ALL     |
//| positions ever opened and Known() searched them again per open position (25k trades = 93 min). |
//| Now only the OPEN positions are walked, new ones are looked for only when PositionsTotal grows,  |
//| arrays grow in blocks, CTrade logs errors only, and the result file reads the history once.     |
//| v1.05: the result file also carries MT5's own fill (time_msc, price), the close (time_msc,     |
//| price) and each position's worst and best excursion in pips (bid for a buy, ask for a sell) -   |
//| diagnostics for the delay study. No change to trading.                                          |
//| v1.06 (review of the label chain, 2026-11-13) - the touch test is now what a broker-held take    |
//| profit does:                                                                                    |
//|  1. compared in whole points (the v1.05 double compare missed ~6% of exact 0.1-pip touches);     |
//|  2. counted only inside a trade session (a quote during the daily break cannot fill a target);   |
//|  3. not blind while another order executes: OrderSend returns only after the random delay, so    |
//|     the ticks in between never reached OnTick - they are now read back with CopyTicksRange and    |
//|     each open position is walked through them in order (target first = touched, stop first = not).|
//| The result file gains "ended by end of test" (col 11) and "touched in the catch-up" (col 12).    |
//| CSV (no header): entry_ms,side,stop_price,tp_pips,tester_fill    |
//|   entry_ms = server time in ms (PrimeXBT time, = tester time)    |
//+------------------------------------------------------------------+
#property copyright "turtle"
#property version   "1.06"
#include <Trade\Trade.mqh>

input string InpFile     = "uhv_replay.csv"; // InpFile: entries file in Common\Files
input double InpLots     = 1;                // InpLots: lots per trade
input double InpMaxLateS = 60;               // InpMaxLateS: skip an entry whose first tick comes this many seconds late
input double InpEjectPips = 0;              // InpEjectPips: close at market when this many pips against the fill (0 = off)
input long   InpMagic    = 88430;            // InpMagic

CTrade   trade;
long     E_ms[];
int      E_side[];
double   E_sl[], E_tp[];
int      n = 0, nxt = 0, sent = 0, late = 0, failed = 0, tpclose = 0, lateReg = 0, ejects = 0;
ulong    P_tk[]; double P_tp[]; int P_idx[]; bool P_touch[]; bool P_live[]; double P_ej[]; bool P_isej[]; double P_op[]; long P_om[]; double P_mae[]; double P_mfe[]; int P_sd[]; int np_ = 0;   // every position we ever saw (P_live = still open)
long     P_opp[]; long P_tpp[]; bool P_catch[];        // v1.06: open price and target in points; touched found in the catch-up scan
long     lastMsc = 0; bool didBlock = false; int scans = 0, scanErr = 0, catchTouch = 0, offSess = 0; long scanTicks = 0;
int      L[]; int nL = 0;                               // v1.04: indices (into P_*) of the positions still open
int      sentTick[];                                    // per entry: the tick counter at its send (-1 = not sent)
long     tickNo = 0;
double   pip = 0.0001;

int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(1000);
   trade.LogLevel(LOG_LEVEL_ERRORS);
   pip = (_Digits == 3 || _Digits == 5) ? 10 * _Point : _Point;
   int h = FileOpen(InpFile, FILE_READ | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if(h == INVALID_HANDLE) { Print("UhvEntryReplay: cannot open ", InpFile, " in Common\Files, error ", GetLastError()); return INIT_FAILED; }
   while(!FileIsEnding(h))
   {
      string s_ms = FileReadString(h);
      if(s_ms == "") { if(FileIsEnding(h)) break; continue; }
      int    sd = (int)StringToInteger(FileReadString(h));
      double sl = StringToDouble(FileReadString(h));
      double tp = StringToDouble(FileReadString(h));
      FileReadString(h);                       // tester fill (kept in the file for the comparison only)
      ArrayResize(E_ms, n + 1, 4096); ArrayResize(E_side, n + 1, 4096); ArrayResize(E_sl, n + 1, 4096); ArrayResize(E_tp, n + 1, 4096);
      E_ms[n] = StringToInteger(s_ms); E_side[n] = sd; E_sl[n] = sl; E_tp[n] = tp; n++;
   }
   FileClose(h);
   ArrayResize(sentTick, n); ArrayInitialize(sentTick, -1);
   PrintFormat("UhvEntryReplay v1.06: %d entries loaded from %s", n, InpFile);
   return n > 0 ? INIT_SUCCEEDED : INIT_FAILED;
}

int  SS_n[7]; datetime SS_a[7][8], SS_b[7][8]; bool SS_ok = false;
bool InSession(long msc)                                // is this tick time inside a trade session of the symbol?
{
   if(!SS_ok)
   {
      for(int d = 0; d < 7; d++) { SS_n[d] = 0; datetime a, b;
         for(int q = 0; q < 8 && SymbolInfoSessionTrade(_Symbol, (ENUM_DAY_OF_WEEK)d, q, a, b); q++) { SS_a[d][SS_n[d]] = a; SS_b[d][SS_n[d]] = b; SS_n[d]++; } }
      SS_ok = true;
   }
   datetime tm = (datetime)(msc / 1000); MqlDateTime z; TimeToStruct(tm, z); long sod = z.hour * 3600 + z.min * 60 + z.sec;
   if(SS_n[z.day_of_week] == 0) return false;
   for(int q = 0; q < SS_n[z.day_of_week]; q++) if(sod >= (long)SS_a[z.day_of_week][q] && sod < (long)SS_b[z.day_of_week][q]) return true;
   return false;
}
long Pts(double px) { return (long)MathRound(px / _Point); }
bool TouchAt(int j, double bid, double ask) { return P_sd[j] > 0 ? Pts(bid) - P_opp[j] >= P_tpp[j] : P_opp[j] - Pts(ask) >= P_tpp[j]; }
bool StopAt(int j, double bid, double ask)  { double sl = E_sl[P_idx[j]]; return P_sd[j] > 0 ? bid <= sl : ask >= sl; }

void CatchUp(long toMsc)                                // v1.06: the ticks that passed while an order was executing (lastMsc, toMsc)
{
   if(nL == 0 || toMsc - 1 < lastMsc + 1) return;
   MqlTick tk[]; int c = CopyTicksRange(_Symbol, tk, COPY_TICKS_ALL, (ulong)(lastMsc + 1), (ulong)(toMsc - 1));
   scans++; if(c < 0) { scanErr++; return; }
   scanTicks += c; if(c == 0) return;
   for(int k = nL - 1; k >= 0; k--)
   {
      int j = L[k]; if(P_touch[j]) continue;
      for(int q = 0; q < c; q++)
      {
         if(tk[q].time_msc < P_om[j]) continue;          // before this position's own fill
         double mv = (P_sd[j] > 0 ? tk[q].bid - P_op[j] : P_op[j] - tk[q].ask) / pip;
         if(mv > P_mfe[j]) P_mfe[j] = mv;
         if(-mv > P_mae[j]) P_mae[j] = -mv;
         if(StopAt(j, tk[q].bid, tk[q].ask)) break;      // the stop came first
         if(TouchAt(j, tk[q].bid, tk[q].ask)) { if(InSession(tk[q].time_msc)) { P_touch[j] = true; P_catch[j] = true; catchTouch++; break; } else offSess++; }
      }
   }
}

bool LiveKnown(ulong tk) { for(int k = 0; k < nL; k++) if(P_tk[L[k]] == tk) return true; return false; }

void Register()                                         // every position of ours gets its target from its OWN open price, whenever it appears
{
   if(PositionsTotal() <= nL) return;                   // nothing new (the open list is refreshed before every call)
   for(int p = PositionsTotal() - 1; p >= 0; p--)
   {
      ulong q = PositionGetTicket(p);
      if(q == 0 || PositionGetInteger(POSITION_MAGIC) != InpMagic || LiveKnown(q)) continue;
      string c = PositionGetString(POSITION_COMMENT);
      if(StringSubstr(c, 0, 2) != "rp") continue;
      int i = (int)StringToInteger(StringSubstr(c, 2));
      if(i < 0 || i >= n) continue;
      if(sentTick[i] >= 0 && tickNo > sentTick[i]) lateReg++;
      int sd = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
      ArrayResize(P_tk, np_ + 1, 4096); ArrayResize(P_tp, np_ + 1, 4096); ArrayResize(P_idx, np_ + 1, 4096); ArrayResize(P_touch, np_ + 1, 4096); ArrayResize(P_live, np_ + 1, 4096); ArrayResize(P_ej, np_ + 1, 4096); ArrayResize(P_isej, np_ + 1, 4096);
      ArrayResize(P_opp, np_ + 1, 4096); ArrayResize(P_tpp, np_ + 1, 4096); ArrayResize(P_catch, np_ + 1, 4096);
      ArrayResize(P_op, np_ + 1, 4096); ArrayResize(P_om, np_ + 1, 4096); ArrayResize(P_mae, np_ + 1, 4096); ArrayResize(P_mfe, np_ + 1, 4096); ArrayResize(P_sd, np_ + 1, 4096);
      P_op[np_] = PositionGetDouble(POSITION_PRICE_OPEN); P_om[np_] = PositionGetInteger(POSITION_TIME_MSC); P_mae[np_] = 0; P_mfe[np_] = -1e9; P_sd[np_] = sd;
      P_opp[np_] = Pts(PositionGetDouble(POSITION_PRICE_OPEN)); P_tpp[np_] = (long)MathMax(1, MathRound(E_tp[i] * pip / _Point)); P_catch[np_] = false;
      P_tk[np_] = q; P_tp[np_] = PositionGetDouble(POSITION_PRICE_OPEN) + sd * E_tp[i] * pip; P_idx[np_] = i; P_touch[np_] = false; P_live[np_] = true;
      P_ej[np_] = InpEjectPips > 0 ? PositionGetDouble(POSITION_PRICE_OPEN) - sd * InpEjectPips * pip : 0; P_isej[np_] = false;
      ArrayResize(L, nL + 1, 256); L[nL++] = np_; np_++;
   }
}

void Refresh()                                          // drop closed positions from the open list (stop hit, target closed)
{
   for(int k = nL - 1; k >= 0; k--)
      if(!PositionSelectByTicket(P_tk[L[k]])) { P_live[L[k]] = false; L[k] = L[--nL]; }
}

void OnTick()
{
   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t)) return;
   tickNo++;
   if(didBlock) CatchUp(t.time_msc);                    // before Refresh: a position stopped in the gap may have touched first
   didBlock = false;
   Refresh();
   Register();
   for(int k = nL - 1; k >= 0; k--)                     // the software target: close at the touch (bid for a buy, ask for a sell) - open positions only
   {
      int j = L[k];
      if(!PositionSelectByTicket(P_tk[j])) { P_live[j] = false; L[k] = L[--nL]; continue; }
      long ty = PositionGetInteger(POSITION_TYPE);
      double mv = (ty == POSITION_TYPE_BUY ? t.bid - P_op[j] : P_op[j] - t.ask) / pip;      // v1.05: excursion at the closing side of the book
      if(mv > P_mfe[j]) P_mfe[j] = mv;
      if(-mv > P_mae[j]) P_mae[j] = -mv;
      if(P_touch[j]) { didBlock = true; if(trade.PositionClose(P_tk[j])) tpclose++; }          // touched in the catch-up: close it now
      else if(TouchAt(j, t.bid, t.ask))
      {
         if(InSession(t.time_msc)) { P_touch[j] = true; didBlock = true; if(trade.PositionClose(P_tk[j])) tpclose++; }
         else offSess++;
      }
      else if(InpEjectPips > 0 && ((ty == POSITION_TYPE_BUY && t.bid <= P_ej[j]) || (ty == POSITION_TYPE_SELL && t.ask >= P_ej[j])))
      {
         didBlock = true; if(trade.PositionClose(P_tk[j])) { ejects++; P_isej[j] = true; }
      }
   }
   while(nxt < n && E_ms[nxt] <= t.time_msc)
   {
      int i = nxt++;
      if(t.time_msc - E_ms[i] > (long)(InpMaxLateS * 1000)) { late++; PrintFormat("UhvEntryReplay: entry %d skipped late", i); continue; }
      bool ok; didBlock = true;
      if(E_side[i] > 0)
         ok = trade.Buy(InpLots, _Symbol, 0.0, NormalizeDouble(E_sl[i], _Digits), 0.0, "rp" + IntegerToString(i));
      else
         ok = trade.Sell(InpLots, _Symbol, 0.0, NormalizeDouble(E_sl[i], _Digits), 0.0, "rp" + IntegerToString(i));
      if(ok && (trade.ResultRetcode() == TRADE_RETCODE_DONE || trade.ResultRetcode() == TRADE_RETCODE_PLACED)) { sent++; sentTick[i] = (int)tickNo; }
      else { failed++; PrintFormat("UhvEntryReplay: entry %d side %d failed, retcode %d", i, E_side[i], trade.ResultRetcode()); }
   }
   Refresh();
   Register();                                          // positions that exist right after their send
   lastMsc = t.time_msc;
}

void OnDeinit(const int reason)
{
   PrintFormat("UhvEntryReplay: loaded %d, sent %d, skipped late %d, failed %d, not reached %d, target closes %d, registered late %d, positions %d, ejects %d",
               n, sent, late, failed, n - nxt, tpclose, lateReg, np_, ejects);
   PrintFormat("UhvEntryReplay v1.06: catch-up scans %d (errors %d), ticks read back %I64d, touches found in the catch-up %d, touches outside a trade session ignored %d",
               scans, scanErr, scanTicks, catchTouch, offSess);
   int h = FileOpen(InpFile + ".out.csv", FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if(h == INVALID_HANDLE) return;
   HistorySelect(0, TimeCurrent() + 86400);             // v1.04: one pass over the history (was one HistorySelectByPosition per position)
   double PL[]; ArrayResize(PL, np_); ArrayInitialize(PL, 0);
   double CP[]; ArrayResize(CP, np_); ArrayInitialize(CP, 0); long CM[]; ArrayResize(CM, np_); ArrayInitialize(CM, 0); int EN[]; ArrayResize(EN, np_); ArrayInitialize(EN, 0);
   double K[][2]; ArrayResize(K, np_);                  // [position ticket, P index], sorted by ticket for a binary search
   for(int j = 0; j < np_; j++) { K[j][0] = (double)P_tk[j]; K[j][1] = j; }
   ArraySort(K);
   int nd = HistoryDealsTotal();
   for(int d = 0; d < nd; d++)
   {
      ulong dl = HistoryDealGetTicket(d);
      if(HistoryDealGetInteger(dl, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      double pid = (double)HistoryDealGetInteger(dl, DEAL_POSITION_ID);
      int lo = 0, hi = np_ - 1;
      while(lo <= hi) { int mid = (lo + hi) / 2; if(K[mid][0] < pid) lo = mid + 1; else if(K[mid][0] > pid) hi = mid - 1; else { int j = (int)K[mid][1];
         PL[j] += HistoryDealGetDouble(dl, DEAL_PROFIT) + HistoryDealGetDouble(dl, DEAL_SWAP) + HistoryDealGetDouble(dl, DEAL_COMMISSION);
         CP[j] = HistoryDealGetDouble(dl, DEAL_PRICE); CM[j] = HistoryDealGetInteger(dl, DEAL_TIME_MSC);
         if(StringFind(HistoryDealGetString(dl, DEAL_COMMENT), "end of test") >= 0) EN[j] = 1; break; } }
   }
   for(int j = 0; j < np_; j++)   // entry index, touched (0/1), closed P/L, ejected (0/1), fill ms, fill price, close ms, close price, worst pips, best pips, ended by end of test (or still open), touched in the catch-up
      FileWrite(h, P_idx[j], P_touch[j] ? 1 : 0, DoubleToString(PL[j], 2), P_isej[j] ? 1 : 0, IntegerToString(P_om[j]), DoubleToString(P_op[j], _Digits),
                IntegerToString(CM[j]), DoubleToString(CP[j], _Digits), DoubleToString(P_mae[j], 2), DoubleToString(P_mfe[j] < -1e8 ? 0 : P_mfe[j], 2),
                (EN[j] == 1 || CM[j] == 0) ? 1 : 0, P_catch[j] ? 1 : 0);
   FileClose(h);
}
