//+------------------------------------------------------------------+
//| TradeLifecycle.mq5  v1.00  (2026-10-13)                           |
//| A trade ANALYZER, it never trades. Attach it to any chart.         |
//| It picks ONE trade - the open position, or else the last closed    |
//| one (or the ticket you type) - and draws its whole life on the     |
//| chart: entries and add-ons, the stop-loss and take-profit path,     |
//| every SL/TP change it knows of (breakeven, trail, widened), partial |
//| closes, the exit and why, the best/worst price reached, and a       |
//| summary panel with the full timeline.                               |
//|                                                                     |
//| Where the facts come from:                                          |
//|  * MT5 history: entry/exit deals, the opening order (first SL/TP),  |
//|    who opened/closed each part (EA / desktop / phone / web / SL /   |
//|    TP / stop-out). MT5 does NOT store SL/TP modifications, so:      |
//|  * this EA RECORDS every SL/TP change of every open position on the |
//|    account once a second, to Common\Files\TradeLifecycle\<login>.csv|
//|    - from the moment it is attached, any EA, terminal or phone.     |
//|  * the Saad EAs' own trade CSV (setup, TP1 rule/time, breakeven     |
//|    time) when the trade came from one of them.                      |
//|  * 1-minute candles for the best / worst price during the trade.    |
//+------------------------------------------------------------------+
#property copyright "turtle"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

input ulong  InpTicket        = 0;      // InpTicket — position ticket to show (0 = the open position, else the last closed one)
input long   InpMagic         = -1;     // InpMagic — only trades with this magic number (-1 = any)
input bool   InpChartSymbolOnly = false;// InpChartSymbolOnly — only trades on this chart's symbol (false = any; the chart switches to the trade's symbol)
input int    InpLookbackDays  = 60;     // InpLookbackDays — how far back to look for the last closed trade
input bool   InpRecord        = true;   // InpRecord — record every SL/TP change of every open position (Common\Files\TradeLifecycle)
input double InpLabelStepUsd  = 1.0;    // InpLabelStepUsd — label a stop move when it moved at least this $ since the last label (breakeven / widening always labelled)
input bool   InpShowPanel     = true;   // InpShowPanel — the summary panel with the timeline
input int    InpPanelFont     = 9;      // InpPanelFont — panel font size
input bool   InpSelfTest      = false;  // InpSelfTest — TESTER ONLY: open + manage a demo trade, then print its reconstructed lifecycle

#define PFX "TLA_"
//--- one event of the trade's life
enum EvKind { EV_ENTRY, EV_ADD, EV_PARTIAL, EV_EXIT, EV_SL, EV_TP, EV_INFO };
struct Ev { datetime t; int kind; double price; double vol; double sl; double tp; double pl; string txt; };
struct Rec { datetime t; double sl; double tp; double bid; double ask; };

ulong    g_pid = 0;            // the position being shown
string   g_sym = "";
int      g_side = 0;           // +1 buy, -1 sell
bool     g_open = false;
Ev       g_ev[];
string   g_lines[];
datetime g_lastDraw = 0;
// recorder: last known SL/TP per open position
ulong    g_rpid[]; double g_rsl[]; double g_rtp[];
string   g_recFile = "";
CTrade   trade;

//+------------------------------------------------------------------+
string Ts(datetime t) { return t == 0 ? "-" : TimeToString(t, TIME_DATE | TIME_SECONDS); }
string Px(double v)   { return v == 0 ? "-" : DoubleToString(v, (int)SymbolInfoInteger(g_sym, SYMBOL_DIGITS)); }
string Usd(double v)  { return (v < 0 ? "-$" : "+$") + DoubleToString(MathAbs(v), 2); }
string Dur(int s)     { return s >= 86400 ? StringFormat("%dd %02dh %02dm", s / 86400, (s % 86400) / 3600, (s % 3600) / 60) : StringFormat("%dh %02dm %02ds", s / 3600, (s % 3600) / 60, s % 60); }
string Who(long reason)
{
   switch ((int)reason) {
      case DEAL_REASON_CLIENT: return "manual (desktop)";
      case DEAL_REASON_MOBILE: return "manual (phone)";
      case DEAL_REASON_WEB:    return "manual (web)";
      case DEAL_REASON_EXPERT: return "EA";
      case DEAL_REASON_SL:     return "stop loss hit";
      case DEAL_REASON_TP:     return "take profit hit";
      case DEAL_REASON_SO:     return "stop out (margin)";
   }
   return "other";
}
string OrderWho(long reason)
{
   switch ((int)reason) {
      case ORDER_REASON_CLIENT: return "manual (desktop)";
      case ORDER_REASON_MOBILE: return "manual (phone)";
      case ORDER_REASON_WEB:    return "manual (web)";
      case ORDER_REASON_EXPERT: return "EA";
      case ORDER_REASON_SL:     return "stop loss";
      case ORDER_REASON_TP:     return "take profit";
      case ORDER_REASON_SO:     return "stop out";
   }
   return "other";
}
void AddEv(datetime t, int kind, double price, double vol, double sl, double tp, double pl, string txt)
{
   int n = ArraySize(g_ev); ArrayResize(g_ev, n + 1);
   g_ev[n].t = t; g_ev[n].kind = kind; g_ev[n].price = price; g_ev[n].vol = vol; g_ev[n].sl = sl; g_ev[n].tp = tp; g_ev[n].pl = pl; g_ev[n].txt = txt;
}
void SortEv()
{
   for (int i = 1; i < ArraySize(g_ev); i++) {
      Ev k = g_ev[i]; int j = i - 1;
      while (j >= 0 && g_ev[j].t > k.t) { g_ev[j + 1] = g_ev[j]; j--; }
      g_ev[j + 1] = k;
   }
}
void Line(string s) { int n = ArraySize(g_lines); ArrayResize(g_lines, n + 1); g_lines[n] = s; }

//--- recorder -------------------------------------------------------
string RecPath() { return StringFormat("TradeLifecycle\\%I64d.csv", AccountInfoInteger(ACCOUNT_LOGIN)); }
void RecWrite(ulong pid, string sym, double sl, double tp)
{
   int h = FileOpen(g_recFile, FILE_READ | FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_SHARE_READ | FILE_ANSI);
   if (h == INVALID_HANDLE) return;
   if (FileSize(h) == 0) FileWriteString(h, "time,position,symbol,sl,tp,bid,ask\r\n");
   FileSeek(h, 0, SEEK_END);
   FileWriteString(h, StringFormat("%s,%I64u,%s,%.5f,%.5f,%.5f,%.5f\r\n", TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS), pid, sym, sl, tp,
                                   SymbolInfoDouble(sym, SYMBOL_BID), SymbolInfoDouble(sym, SYMBOL_ASK)));
   FileClose(h);
}
void RecPoll()
{
   if (!InpRecord) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0) continue;
      ulong pid = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      double sl = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP);
      int k = -1;
      for (int j = 0; j < ArraySize(g_rpid); j++) if (g_rpid[j] == pid) { k = j; break; }
      if (k < 0) { k = ArraySize(g_rpid); ArrayResize(g_rpid, k + 1); ArrayResize(g_rsl, k + 1); ArrayResize(g_rtp, k + 1); g_rpid[k] = pid; g_rsl[k] = -1; g_rtp[k] = -1; }
      if (MathAbs(sl - g_rsl[k]) > _Point / 2 || MathAbs(tp - g_rtp[k]) > _Point / 2) {
         RecWrite(pid, PositionGetString(POSITION_SYMBOL), sl, tp);
         g_rsl[k] = sl; g_rtp[k] = tp;
      }
   }
}
// recorded SL/TP states of one position, oldest first
int RecLoad(ulong pid, Rec &out[])
{
   ArrayResize(out, 0);
   int h = FileOpen(g_recFile, FILE_READ | FILE_TXT | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_ANSI);
   if (h == INVALID_HANDLE) return 0;
   string want = StringFormat(",%I64u,", pid);
   while (!FileIsEnding(h)) {
      string ln = FileReadString(h);
      if (StringFind(ln, want) < 0) continue;
      string f[]; if (StringSplit(ln, ',', f) < 7) continue;
      int n = ArraySize(out); ArrayResize(out, n + 1);
      out[n].t = StringToTime(f[0]); out[n].sl = StringToDouble(f[3]); out[n].tp = StringToDouble(f[4]);
      out[n].bid = StringToDouble(f[5]); out[n].ask = StringToDouble(f[6]);
   }
   FileClose(h);
   return ArraySize(out);
}

//--- the Saad EAs' own trade CSV (setup, TP1, breakeven) ------------
bool SaadInfo(string sym, long magic, datetime entryT, double entryPx, string &setup, string &tp1rule, string &tp1at, string &ctcat, string &tps)
{
   string fn; long fh = FileFindFirst("*_trades_" + sym + "_" + IntegerToString(magic) + ".csv", fn, FILE_COMMON);
   if (fh == INVALID_HANDLE) return false;
   bool found = false;
   do {
      int h = FileOpen(fn, FILE_READ | FILE_TXT | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_ANSI);
      if (h == INVALID_HANDLE) continue;
      while (!FileIsEnding(h)) {
         string ln = FileReadString(h);
         string f[]; if (StringSplit(ln, ',', f) < 18 || f[0] == "num") continue;
         datetime et = StringToTime(f[4]);
         if (MathAbs((long)(et - entryT)) <= 5 && MathAbs(StringToDouble(f[5]) - entryPx) < 1.0) {
            setup = f[3]; tp1rule = f[8]; tp1at = f[9]; tps = f[10]; ctcat = f[11]; found = true;
         }
      }
      FileClose(h);
   } while (!found && FileFindNext(fh, fn));
   FileFindClose(fh);
   return found;
}

//--- which trade ----------------------------------------------------
bool PickTrade()
{
   g_pid = 0; g_open = false;
   if (InpTicket > 0) {
      for (int i = PositionsTotal() - 1; i >= 0; i--) {
         ulong t = PositionGetTicket(i);
         if (t == InpTicket || (ulong)PositionGetInteger(POSITION_IDENTIFIER) == InpTicket) { g_pid = (ulong)PositionGetInteger(POSITION_IDENTIFIER); g_open = true; return true; }
      }
      if (HistorySelectByPosition(InpTicket) && HistoryDealsTotal() > 0) { g_pid = InpTicket; return true; }
      return false;
   }
   datetime best = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0) continue;
      if (InpMagic >= 0 && PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if (InpChartSymbolOnly && PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      datetime pt = (datetime)PositionGetInteger(POSITION_TIME);
      if (pt > best) { best = pt; g_pid = (ulong)PositionGetInteger(POSITION_IDENTIFIER); g_open = true; }
   }
   if (g_open) return true;
   if (!HistorySelect(TimeCurrent() - InpLookbackDays * 86400, TimeCurrent() + 86400)) return false;
   for (int i = HistoryDealsTotal() - 1; i >= 0; i--) {
      ulong d = HistoryDealGetTicket(i);
      long e = HistoryDealGetInteger(d, DEAL_ENTRY);
      if (e != DEAL_ENTRY_OUT && e != DEAL_ENTRY_INOUT && e != DEAL_ENTRY_OUT_BY) continue;
      if (InpMagic >= 0 && HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic) continue;
      if (InpChartSymbolOnly && HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol) continue;
      g_pid = (ulong)HistoryDealGetInteger(d, DEAL_POSITION_ID);
      return true;
   }
   return false;
}

//--- rebuild the trade's life ----------------------------------------
double g_entry = 0, g_vol = 0, g_sl0 = 0, g_tp0 = 0, g_net = 0, g_mfe = 0, g_mae = 0, g_risk = 0;
datetime g_t0 = 0, g_t1 = 0, g_mfeT = 0, g_maeT = 0;
long g_magic = 0;
string g_openWho = "", g_comment = "";

bool Build()
{
   ArrayResize(g_ev, 0); ArrayResize(g_lines, 0);
   g_entry = g_vol = g_sl0 = g_tp0 = g_net = g_mfe = g_mae = g_risk = 0; g_t0 = g_t1 = g_mfeT = g_maeT = 0; g_side = 0; g_magic = 0;
   if (g_pid == 0 || !HistorySelectByPosition(g_pid)) return false;
   double cost = 0;
   int nIn = 0;
   for (int i = 0; i < HistoryDealsTotal(); i++) {
      ulong d = HistoryDealGetTicket(i);
      long e = HistoryDealGetInteger(d, DEAL_ENTRY), type = HistoryDealGetInteger(d, DEAL_TYPE);
      if (type != DEAL_TYPE_BUY && type != DEAL_TYPE_SELL) continue;
      datetime t = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
      double px = HistoryDealGetDouble(d, DEAL_PRICE), v = HistoryDealGetDouble(d, DEAL_VOLUME);
      double pl = HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_COMMISSION) + HistoryDealGetDouble(d, DEAL_SWAP);
      string cm = HistoryDealGetString(d, DEAL_COMMENT);
      long rsn = HistoryDealGetInteger(d, DEAL_REASON);
      if (g_sym == "" || nIn == 0) g_sym = HistoryDealGetString(d, DEAL_SYMBOL);
      if (e == DEAL_ENTRY_IN) {
         if (nIn == 0) { g_side = type == DEAL_TYPE_BUY ? 1 : -1; g_t0 = t; g_magic = HistoryDealGetInteger(d, DEAL_MAGIC); g_comment = cm; g_openWho = Who(rsn); }
         cost += px * v; g_vol += v; nIn++;
         g_net += pl;
         AddEv(t, nIn == 1 ? EV_ENTRY : EV_ADD, px, v, 0, 0, pl, StringFormat("%s %.2f @ %s%s", type == DEAL_TYPE_BUY ? "BUY" : "SELL", v, Px(px), cm != "" ? " (" + cm + ")" : ""));
      } else {
         g_net += pl;
         double left = g_vol;
         for (int k = 0; k < ArraySize(g_ev); k++) if (g_ev[k].kind == EV_PARTIAL || g_ev[k].kind == EV_EXIT) left -= g_ev[k].vol;
         bool last = left - v < 1e-8;
         string why = Who(rsn);
         if (rsn == DEAL_REASON_SL && StringFind(cm, "sl") == 0) why = "stop hit (" + cm + ")";
         AddEv(t, last ? EV_EXIT : EV_PARTIAL, px, v, 0, 0, pl, StringFormat("%s %.2f @ %s - %s, %s", last ? "CLOSED" : "partial close", v, Px(px), why, Usd(pl)));
         g_t1 = t;
      }
   }
   if (nIn == 0) return false;
   g_entry = cost / g_vol;
   // the opening order: first SL / TP and who sent it
   for (int i = 0; i < HistoryOrdersTotal(); i++) {
      ulong o = HistoryOrderGetTicket(i);
      long ot = HistoryOrderGetInteger(o, ORDER_TYPE);
      if (ot != ORDER_TYPE_BUY && ot != ORDER_TYPE_SELL) continue;
      g_sl0 = HistoryOrderGetDouble(o, ORDER_SL); g_tp0 = HistoryOrderGetDouble(o, ORDER_TP);
      g_openWho = OrderWho(HistoryOrderGetInteger(o, ORDER_REASON));
      break;
   }
   g_open = PositionSelectByTicket(g_pid);
   if (!g_open) {   // hedging: ticket == identifier; netting: search
      for (int i = PositionsTotal() - 1; i >= 0; i--) if (PositionGetTicket(i) > 0 && (ulong)PositionGetInteger(POSITION_IDENTIFIER) == g_pid) { g_open = true; break; }
   }
   double tv = SymbolInfoDouble(g_sym, SYMBOL_TRADE_TICK_VALUE), ts = SymbolInfoDouble(g_sym, SYMBOL_TRADE_TICK_SIZE);
   double perLot = ts > 0 ? tv / ts : 100;   // $ per 1.0 price per lot
   if (g_sl0 > 0) g_risk = MathAbs(g_entry - g_sl0) * g_vol * perLot;
   // recorded SL / TP changes
   Rec r[]; int nr = RecLoad(g_pid, r);
   double curSl = g_sl0, curTp = g_tp0, lastLab = g_sl0;
   for (int i = 0; i < nr; i++) {
      if (r[i].t < g_t0) continue;
      if (MathAbs(r[i].sl - curSl) > _Point / 2) {
         string kind;
         bool better = g_side > 0 ? r[i].sl > curSl : (curSl == 0 || r[i].sl < curSl);
         bool be = r[i].sl > 0 && MathAbs(r[i].sl - g_entry) <= 2 * SymbolInfoDouble(g_sym, SYMBOL_POINT) * 10;
         bool inProfit = r[i].sl > 0 && (g_side > 0 ? r[i].sl > g_entry : r[i].sl < g_entry);
         kind = r[i].sl == 0 ? "stop REMOVED" : !better ? "stop WIDENED (more risk)" : be ? "stop to breakeven" : inProfit ? "trail (locked in profit)" : "stop tightened";
         bool label = !better || be || r[i].sl == 0 || MathAbs(r[i].sl - lastLab) >= InpLabelStepUsd || i == nr - 1 || curSl == g_sl0;
         AddEv(r[i].t, EV_SL, g_side > 0 ? r[i].bid : r[i].ask, 0, r[i].sl, r[i].tp, label ? 1 : 0, StringFormat("SL %s -> %s  %s", Px(curSl), Px(r[i].sl), kind));
         if (label) lastLab = r[i].sl;
         curSl = r[i].sl;
      }
      if (MathAbs(r[i].tp - curTp) > _Point / 2) {
         AddEv(r[i].t, EV_TP, g_side > 0 ? r[i].bid : r[i].ask, 0, r[i].sl, r[i].tp, 1, r[i].tp == 0 ? StringFormat("TP %s removed", Px(curTp)) : curTp == 0 ? StringFormat("TP set at %s", Px(r[i].tp)) : StringFormat("TP %s -> %s", Px(curTp), Px(r[i].tp)));
         curTp = r[i].tp;
      }
   }
   // for a closed trade without recordings: what the final stop must have been
   if (!g_open) for (int i = ArraySize(g_ev) - 1; i >= 0; i--) if (g_ev[i].kind == EV_EXIT && StringFind(g_ev[i].txt, "stop hit (sl ") >= 0 && nr == 0) {
      int a = StringFind(g_ev[i].txt, "(sl ") + 4, b = StringFind(g_ev[i].txt, ")", a);
      double fsl = StringToDouble(StringSubstr(g_ev[i].txt, a, b - a));
      if (g_sl0 > 0 && MathAbs(fsl - g_sl0) > _Point) AddEv(g_ev[i].t, EV_INFO, fsl, 0, fsl, 0, 0,
         StringFormat("the stop had been moved %s -> %s before the exit (no recording of when: TradeLifecycle was not running)", Px(g_sl0), Px(fsl)));
   }
   // Saad EA extras
   string setup = "", tp1rule = "", tp1at = "", ctcat = "", tps = "";
   if (SaadInfo(g_sym, g_magic, g_t0, g_ev[0].price, setup, tp1rule, tp1at, ctcat, tps)) {
      if (ctcat != "") AddEv(StringToTime(ctcat), EV_INFO, 0, 0, 0, 0, 0, "EA: 75% of the way to TP1 -> stop to breakeven");
      if (tp1at != "") AddEv(StringToTime(tp1at), EV_INFO, 0, 0, 0, 0, 0, "EA: TP1 reached (" + tp1rule + ")" + (tps != "" ? " then " + tps : ""));
   }
   // best / worst price from 1-minute candles
   datetime tEnd = g_open ? TimeCurrent() : g_t1;
   MqlRates m[]; int nb = CopyRates(g_sym, PERIOD_M1, g_t0, tEnd, m);
   for (int i = 0; i < nb; i++) {
      double fav = g_side > 0 ? m[i].high - g_entry : g_entry - m[i].low, adv = g_side > 0 ? g_entry - m[i].low : m[i].high - g_entry;
      if (fav > g_mfe) { g_mfe = fav; g_mfeT = m[i].time; }
      if (adv > g_mae) { g_mae = adv; g_maeT = m[i].time; }
   }
   SortEv();
   // the panel text
   Line(StringFormat("TRADE LIFECYCLE  #%I64u  %s  %s", g_pid, g_sym, g_open ? "OPEN" : "CLOSED"));
   Line(StringFormat("%s %.2f lots  avg entry %s  |  opened by %s%s", g_side > 0 ? "BUY" : "SELL", g_vol, Px(g_entry), g_openWho,
                     g_magic != 0 ? StringFormat(" (magic %I64d)", g_magic) : ""));
   if (setup != "") Line("setup: " + setup);
   Line(StringFormat("first stop %s   first TP %s   risk %s", Px(g_sl0), g_tp0 > 0 ? Px(g_tp0) : "none at the broker", g_risk > 0 ? "$" + DoubleToString(g_risk, 2) : "-"));
   Line("--- timeline ---");
   int shown = 0;
   for (int i = 0; i < ArraySize(g_ev); i++) {
      if (g_ev[i].kind == EV_SL && g_ev[i].pl == 0 && ArraySize(g_ev) > 26) continue;   // small trail steps: drawn, not listed
      Line(StringFormat("%s  %s", TimeToString(g_ev[i].t, TIME_DATE | TIME_SECONDS), g_ev[i].txt));
      if (++shown >= 22) { Line("... (more on the chart)"); break; }
   }
   Line("--- result ---");
   if (g_open) {
      double flt = 0; if (PositionSelectByTicket(g_pid)) flt = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      Line(StringFormat("still open %s  |  booked %s  floating %s  |  stop now %s", Dur((int)(TimeCurrent() - g_t0)), Usd(g_net), Usd(flt),
                        Px(PositionSelectByTicket(g_pid) ? PositionGetDouble(POSITION_SL) : 0)));
   } else
      Line(StringFormat("net %s  |  duration %s%s", Usd(g_net), Dur((int)(g_t1 - g_t0)), g_risk > 0 ? StringFormat("  |  %.2f R", g_net / g_risk) : ""));
   Line(StringFormat("best %s (%s)   worst %s (%s)  [1-min candles; the entry minute can include prices just before the fill]", "$" + DoubleToString(g_mfe, 2), Ts(g_mfeT), "$" + DoubleToString(g_mae, 2), Ts(g_maeT)));
   if (nr == 0) Line("SL/TP changes: none recorded (TradeLifecycle wasn't running) - first and final stop only");
   return true;
}

//--- drawing -----------------------------------------------------------
void Del() { ObjectsDeleteAll(0, PFX); }
string N(string s) { static int k = 0; return PFX + s + IntegerToString(k++); }
void Txt(datetime t, double p, string s, color c, int sz, ENUM_ANCHOR_POINT a)
{
   string n = N("t"); ObjectCreate(0, n, OBJ_TEXT, 0, t, p);
   ObjectSetString(0, n, OBJPROP_TEXT, s); ObjectSetInteger(0, n, OBJPROP_COLOR, c); ObjectSetInteger(0, n, OBJPROP_FONTSIZE, sz);
   ObjectSetString(0, n, OBJPROP_FONT, "Consolas"); ObjectSetInteger(0, n, OBJPROP_ANCHOR, a); ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
}
void Seg(datetime t1, double p1, datetime t2, double p2, color c, ENUM_LINE_STYLE st, int w)
{
   string n = N("l"); ObjectCreate(0, n, OBJ_TREND, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, n, OBJPROP_COLOR, c); ObjectSetInteger(0, n, OBJPROP_STYLE, st); ObjectSetInteger(0, n, OBJPROP_WIDTH, w);
   ObjectSetInteger(0, n, OBJPROP_RAY_RIGHT, false); ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false); ObjectSetInteger(0, n, OBJPROP_BACK, true);
}
void Arrow(datetime t, double p, int code, color c, int w)
{
   string n = N("a"); ObjectCreate(0, n, OBJ_ARROW, 0, t, p);
   ObjectSetInteger(0, n, OBJPROP_ARROWCODE, code); ObjectSetInteger(0, n, OBJPROP_COLOR, c); ObjectSetInteger(0, n, OBJPROP_WIDTH, w);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
}
void Draw()
{
   Del();
   if (g_pid == 0) {
      Txt(TimeCurrent(), SymbolInfoDouble(_Symbol, SYMBOL_BID), "TradeLifecycle: no trade found (check InpMagic / InpLookbackDays)", clrOrange, 10, ANCHOR_RIGHT);
      ChartRedraw(); return;
   }
   if (g_sym != _Symbol) return;   // the chart is switching to the trade's symbol
   datetime tEnd = g_open ? TimeCurrent() : g_t1;
   int ps = PeriodSeconds();
   bool up = g_side > 0;
   // average entry line, first TP
   Seg(g_t0, g_entry, tEnd, g_entry, clrDodgerBlue, STYLE_DOT, 1);
   Txt(g_t0, g_entry, StringFormat("  entry %s", Px(g_entry)), clrDodgerBlue, 8, ANCHOR_LEFT_LOWER);
   // stop-loss path (and TP path) as steps
   double sl = g_sl0, tp = g_tp0; datetime from = g_t0;
   for (int i = 0; i < ArraySize(g_ev); i++) {
      if (g_ev[i].kind != EV_SL && g_ev[i].kind != EV_TP) continue;
      if (sl > 0) Seg(from, sl, g_ev[i].t, sl, clrRed, STYLE_DASH, 2);
      if (tp > 0) Seg(from, tp, g_ev[i].t, tp, clrLimeGreen, STYLE_DASH, 2);
      sl = g_ev[i].sl; tp = g_ev[i].tp; from = g_ev[i].t;
   }
   if (sl > 0) Seg(from, sl, tEnd, sl, clrRed, STYLE_DASH, 2);
   if (tp > 0) Seg(from, tp, tEnd, tp, clrLimeGreen, STYLE_DASH, 2);
   if (g_sl0 > 0) Txt(g_t0, g_sl0, StringFormat("  first stop %s (risk $%.2f)", Px(g_sl0), g_risk), clrRed, 8, up ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER);
   if (g_tp0 > 0) Txt(g_t0, g_tp0, StringFormat("  first TP %s", Px(g_tp0)), clrLimeGreen, 8, up ? ANCHOR_LEFT_LOWER : ANCHOR_LEFT_UPPER);
   // events
   int nInfo = 0;
   for (int i = 0; i < ArraySize(g_ev); i++) {
      Ev e = g_ev[i];
      switch (e.kind) {
         case EV_ENTRY:
         case EV_ADD:
            Arrow(e.t, e.price, up ? 233 : 234, up ? clrDodgerBlue : clrOrangeRed, e.kind == EV_ENTRY ? 3 : 2);
            Txt(e.t, e.price, (e.kind == EV_ENTRY ? "ENTRY " : "ADD ") + e.txt, up ? clrDodgerBlue : clrOrangeRed, 9, up ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER);
            break;
         case EV_PARTIAL:
         case EV_EXIT:
            Arrow(e.t, e.price, e.kind == EV_EXIT ? 251 : 159, e.pl >= 0 ? clrLimeGreen : clrRed, 3);
            Txt(e.t, e.price, "  " + e.txt, e.pl >= 0 ? clrLimeGreen : clrRed, 9, up ? ANCHOR_LEFT_LOWER : ANCHOR_LEFT_UPPER);
            break;
         case EV_SL:
            if (e.pl > 0) {   // labelled stop move
               Arrow(e.t, e.sl, 4, StringFind(e.txt, "WIDENED") >= 0 ? clrMagenta : clrOrange, 1);
               Txt(e.t, e.sl, "  " + e.txt, StringFind(e.txt, "WIDENED") >= 0 ? clrMagenta : clrOrange, 8, up ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER);
            }
            break;
         case EV_TP:
            Arrow(e.t, e.tp, 4, clrLimeGreen, 1);
            Txt(e.t, e.tp, "  " + e.txt, clrLimeGreen, 8, ANCHOR_LEFT_LOWER);
            break;
         case EV_INFO: {
            double y = e.price > 0 ? e.price : g_entry + (up ? -1 : 1) * (2 + nInfo++) * MathMax(_Point * 50, (g_mfe + g_mae) * 0.08);
            Seg(e.t, y, e.t, g_entry, clrGold, STYLE_DOT, 1);
            Txt(e.t, y, "  " + e.txt, clrGold, 8, ANCHOR_LEFT);
            break;
         }
      }
   }
   // best / worst
   if (g_mfeT > 0) { double p = up ? g_entry + g_mfe : g_entry - g_mfe; Arrow(g_mfeT, p, 159, clrAqua, 2); Txt(g_mfeT, p, StringFormat("  best +$%.2f", g_mfe), clrAqua, 8, up ? ANCHOR_LEFT_LOWER : ANCHOR_LEFT_UPPER); }
   if (g_maeT > 0) { double p = up ? g_entry - g_mae : g_entry + g_mae; Arrow(g_maeT, p, 159, clrSalmon, 2); Txt(g_maeT, p, StringFormat("  worst -$%.2f", g_mae), clrSalmon, 8, up ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER); }
   // panel
   if (InpShowPanel) {
      int lh = InpPanelFont + 6, w = 0;
      for (int i = 0; i < ArraySize(g_lines); i++) w = MathMax(w, StringLen(g_lines[i]));
      string bg = PFX + "panel";
      ObjectCreate(0, bg, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, bg, OBJPROP_XDISTANCE, 8); ObjectSetInteger(0, bg, OBJPROP_YDISTANCE, 22);
      ObjectSetInteger(0, bg, OBJPROP_XSIZE, (int)(w * InpPanelFont * 0.78) + 20); ObjectSetInteger(0, bg, OBJPROP_YSIZE, ArraySize(g_lines) * lh + 12);
      ObjectSetInteger(0, bg, OBJPROP_BGCOLOR, C'16,22,36'); ObjectSetInteger(0, bg, OBJPROP_BORDER_COLOR, clrGoldenrod); ObjectSetInteger(0, bg, OBJPROP_SELECTABLE, false);
      for (int i = 0; i < ArraySize(g_lines); i++) {
         string n = N("p"); ObjectCreate(0, n, OBJ_LABEL, 0, 0, 0);
         ObjectSetInteger(0, n, OBJPROP_XDISTANCE, 16); ObjectSetInteger(0, n, OBJPROP_YDISTANCE, 28 + i * lh);
         ObjectSetString(0, n, OBJPROP_TEXT, g_lines[i]); ObjectSetString(0, n, OBJPROP_FONT, "Consolas"); ObjectSetInteger(0, n, OBJPROP_FONTSIZE, InpPanelFont);
         ObjectSetInteger(0, n, OBJPROP_COLOR, i == 0 ? clrGold : StringFind(g_lines[i], "---") == 0 ? clrGoldenrod : clrWhiteSmoke); ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
      }
   }
   // show the trade: from a little before the entry
   ChartSetInteger(0, CHART_AUTOSCROLL, false);
   int sh = iBarShift(_Symbol, PERIOD_CURRENT, g_t0);
   int vis = (int)ChartGetInteger(0, CHART_VISIBLE_BARS);
   if (sh >= 0) ChartNavigate(0, CHART_END, -MathMax(0, sh - vis / 4));
   ChartRedraw();
}

void Refresh()
{
   if (!PickTrade()) { g_pid = 0; Draw(); return; }
   if (!Build()) { g_pid = 0; Draw(); return; }
   if (g_sym != _Symbol && !MQLInfoInteger(MQL_TESTER)) { ChartSetSymbolPeriod(0, g_sym, PERIOD_CURRENT); return; }
   Draw();
   g_lastDraw = TimeCurrent();
}

//--- self-test (Strategy Tester only): a scripted trade to check the reconstruction ---
int g_stStep = 0; ulong g_stPos = 0; double g_stEn = 0; datetime g_stT = 0;
void SelfTest()
{
   if (!MQLInfoInteger(MQL_TESTER)) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if (g_stStep == 0 && TimeCurrent() > g_stT) {
      if (trade.Buy(1.0, _Symbol, 0, NormalizeDouble(ask - 5, _Digits), NormalizeDouble(ask + 20, _Digits), "selftest")) {
         g_stEn = trade.ResultPrice(); g_stPos = trade.ResultOrder();
         if (HistoryDealSelect(trade.ResultDeal())) g_stPos = (ulong)HistoryDealGetInteger(trade.ResultDeal(), DEAL_POSITION_ID);
         g_stStep = 1;
      }
      return;
   }
   if (g_stStep == 0 || !PositionSelectByTicket(g_stPos)) { if (g_stStep > 0 && g_stStep < 99) { g_stStep = 99; Refresh(); for (int i = 0; i < ArraySize(g_lines); i++) Print("[TLA] ", g_lines[i]); } return; }
   double sl = PositionGetDouble(POSITION_SL);
   if (g_stStep == 1 && bid - g_stEn >= 2.0) { trade.PositionModify(g_stPos, NormalizeDouble(g_stEn, _Digits), PositionGetDouble(POSITION_TP)); g_stStep = 2; }
   else if (g_stStep == 2 && bid - g_stEn >= 3.0) { trade.PositionClosePartial(g_stPos, 0.5); g_stStep = 3; }
   else if (g_stStep == 3) { double w = NormalizeDouble(bid - 1.5, _Digits); if (w > sl + 0.3) trade.PositionModify(g_stPos, w, 0); }
}

//+------------------------------------------------------------------+
int OnInit()
{
   g_recFile = RecPath();
   g_sym = "";
   if (InpSelfTest && MQLInfoInteger(MQL_TESTER)) g_stT = TimeCurrent() + 3600;
   RecPoll();
   EventSetTimer(1);
   Refresh();
   PrintFormat("[TradeLifecycle] v1.00 | showing position %I64u %s | recording SL/TP changes to Common\\Files\\%s", g_pid, g_sym, g_recFile);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason) { EventKillTimer(); if (reason != REASON_CHARTCHANGE) Del(); }
void OnTimer()
{
   RecPoll();
   // an open trade is redrawn every 2 s; in auto mode a newer trade takes over
   static ulong shown = 0;
   if (g_open || InpTicket == 0) {
      ulong was = g_pid;
      if (TimeCurrent() - g_lastDraw >= 2 || was != shown) { Refresh(); shown = g_pid; }
   }
}
void OnTick()
{
   if (InpSelfTest) SelfTest();
   if (MQLInfoInteger(MQL_TESTER)) RecPoll();   // the tester has no timer between ticks
}
void OnTradeTransaction(const MqlTradeTransaction &tr, const MqlTradeRequest &rq, const MqlTradeResult &rs)
{
   if (tr.type == TRADE_TRANSACTION_POSITION || tr.type == TRADE_TRANSACTION_DEAL_ADD) { RecPoll(); if (!MQLInfoInteger(MQL_TESTER)) Refresh(); }
}
