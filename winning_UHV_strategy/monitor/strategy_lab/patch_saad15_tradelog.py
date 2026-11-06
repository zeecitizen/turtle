"""One-off patch: Saad_strategy_15min v1.10 - trade log: every event to the Experts tab + one CSV row per trade."""
p = r'C:\Users\zeesh\turtle\mt5\Saad_strategy_15min.mq5'
s = open(p, encoding='utf-8').read()


def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (s.count(a), a[:90])
    s = s.replace(a, b)


# ---------- inputs ----------
rep("input bool   InpDrawSkips   = false;",
    "input bool   InpLog         = true;   // InpLog — print every trade event to the Experts tab (live + visual tester)\n"
    "input bool   InpLogCsv      = true;   // InpLogCsv — one CSV row per closed trade in Common\\Files (live + visual tester)\n"
    "input bool   InpDrawSkips   = false;")

# ---------- per-trade record ----------
rep("datetime entryTime; double best; bool usdTrail; double tpNext; int tpStage;\n",
    "datetime entryTime; double best; bool usdTrail; double tpNext; int tpStage;\n"
    "                  string setup; double sl0; double risk; string tp1; datetime tp1At; string tps; datetime ctcAt; int moves; double mfe;\n")
rep('p.tpNext = 0; p.tpStage = 1;',
    'p.tpNext = 0; p.tpStage = 1; p.setup = ""; p.sl0 = p.slNow; p.risk = 0; p.tp1 = ""; p.tp1At = 0; p.tps = ""; p.ctcAt = 0; p.moves = 0; p.mfe = 0;', 2)

# ---------- helpers (after Drawing()) ----------
rep('string ObjName() { return StringFormat("SAAD_%d", g_obj++); }',
    r'''string ObjName() { return StringFormat("SAAD_%d", g_obj++); }
bool LogOn() { return InpLog && (!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_VISUAL_MODE) || InpVerbose); }
void Log(string msg) { if (LogOn()) Print("[SAAD-15min] ", msg); }
string Ts(datetime t) { return t == 0 ? "" : TimeToString(t, TIME_DATE | TIME_SECONDS); }
string Px(double v) { return v == 0 ? "" : DoubleToString(v, _Digits); }
// one row per closed trade: Common\Files\Saad15_trades_<symbol>_<magic>[_tester].csv
void CsvRow(string row)
{
   if (!InpLogCsv || (MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE))) return;
   string fn = StringFormat("Saad15_trades_%s_%d%s.csv", _Symbol, InpMagicNumber, MQLInfoInteger(MQL_TESTER) ? "_tester" : "");
   int h = FileOpen(fn, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ);
   if (h == INVALID_HANDLE) { Print("[SAAD-15min] cannot write ", fn, " error ", GetLastError()); return; }
   if (FileSize(h) == 0)
      FileWriteString(h, "num,symbol,side,setup,entry_time,entry,sl_initial,risk_usd,tp1_rule,tp1_time,tp_levels,ctc_time,"
                         "sl_moves,best_price,sl_final,exit_time,exit,exit_reason,profit,commission,swap,net\r\n");
   FileSeek(h, 0, SEEK_END);
   FileWriteString(h, row + "\r\n");
   FileClose(h);
}''')

# ---------- exit: always read the deals (not only when drawing), log + CSV ----------
rep('''   if (!Drawing() || !HistorySelectByPosition(p.ticket)) return;
   double px = 0, pnl = 0; datetime t = 0; long reason = -1;
   for (int k = HistoryDealsTotal() - 1; k >= 0; k--) {
      ulong d = HistoryDealGetTicket(k);
      if (HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      px = HistoryDealGetDouble(d, DEAL_PRICE); t = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
      pnl += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_COMMISSION) + HistoryDealGetDouble(d, DEAL_SWAP);
      reason = HistoryDealGetInteger(d, DEAL_REASON);
   }
   if (t == 0) return;''', '''   if (!(Drawing() || LogOn() || InpLogCsv) || !HistorySelectByPosition(p.ticket)) return;
   double px = 0, pnl = 0, prof = 0, comm = 0, swp = 0; datetime t = 0; long reason = -1;
   for (int k = HistoryDealsTotal() - 1; k >= 0; k--) {
      ulong d = HistoryDealGetTicket(k);
      comm += HistoryDealGetDouble(d, DEAL_COMMISSION);          // entry + exit commission
      if (HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      px = HistoryDealGetDouble(d, DEAL_PRICE); t = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
      prof += HistoryDealGetDouble(d, DEAL_PROFIT); swp += HistoryDealGetDouble(d, DEAL_SWAP);
      reason = HistoryDealGetInteger(d, DEAL_REASON);
   }
   if (t == 0) return;
   pnl = prof + comm + swp;''')
rep('''   DLine(p.slFrom, p.slNow, t, p.slNow, p.ride ? clrOrange : clrRed, STYLE_DASH, 2);
   DLine(p.entryTime, p.entry, t, px, pnl >= 0 ? clrLime : clrRed, STYLE_DOT, 1);''',
    '''   Log(StringFormat("EXIT #%d %s %s @ %s | entry %s | %s | best %s | SL moves %d | net %s%.2f (profit %.2f, commission %.2f, swap %.2f)",
                    p.num, p.side > 0 ? "BUY" : "SELL", Ts(t), Px(px), Px(p.entry), why, Px(p.mfe), p.moves,
                    pnl >= 0 ? "+" : "-", MathAbs(pnl), prof, comm, swp));
   string setupCsv = p.setup; StringReplace(setupCsv, ",", ";");
   string tp1Csv = p.tp1; StringReplace(tp1Csv, ",", ";");
   CsvRow(StringFormat("%d,%s,%s,%s,%s,%s,%s,%.2f,%s,%s,%s,%s,%d,%s,%s,%s,%s,%s,%.2f,%.2f,%.2f,%.2f",
                       p.num, _Symbol, p.side > 0 ? "BUY" : "SELL", setupCsv, Ts(p.entryTime), Px(p.entry), Px(p.sl0), p.risk,
                       tp1Csv, Ts(p.tp1At), p.tps, Ts(p.ctcAt), p.moves, Px(p.mfe), Px(p.slNow), Ts(t), Px(px), why,
                       prof, comm, swp, pnl));
   DLine(p.slFrom, p.slNow, t, p.slNow, p.ride ? clrOrange : clrRed, STYLE_DASH, 2);
   DLine(p.entryTime, p.entry, t, px, pnl >= 0 ? clrLime : clrRed, STYLE_DOT, 1);''')

# SlMoved counts every move; drawing only when drawing
rep('''void SlMoved(int i, double newSl, string note)
{
   if (!Drawing()) return;''', '''void SlMoved(int i, double newSl, string note)
{
   g_pos[i].moves++;
   if (note != "" && StringFind(note, "trail") != 0) Log(StringFormat("#%d SL %s -> %s (%s)", g_pos[i].num, Px(g_pos[i].slNow), Px(newSl), note));
   if (!Drawing()) { g_pos[i].slNow = newSl; return; }''')

# ---------- entry ----------
rep('''   int n = ArraySize(g_pos); ArrayResize(g_pos, n + 1); g_pos[n] = p;
   g_entries++;
   if (Drawing()) {''', '''   p.setup = g_pDesc; p.sl0 = p.slNow; p.mfe = p.entry;
   p.risk = MathAbs(p.entry - sl) * InpLots * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   p.tp1 = side > 0 ? (noTp ? "none (exit EMA below entry) - trailing from entry" : StringFormat("touch of the %d EMA (now %.2f)", g_pExit, Ema(g_pExit, 0)))
                    : StringFormat("last support %.2f", tp);
   int n = ArraySize(g_pos); ArrayResize(g_pos, n + 1); g_pos[n] = p;
   g_entries++;
   Log(StringFormat("ENTRY #%d %s %.2f lots @ %s | SL %s (risk $%.2f) | TP1 %s | setup: %s",
                    p.num, side > 0 ? "BUY" : "SELL", InpLots, Px(p.entry), Px(p.sl0), p.risk, p.tp1, p.setup));
   if (Drawing()) {''')

# ---------- setup + skips ----------
rep('''   g_pDesc = StringFormat("%s %s on the %s%s", side > 0 ? "LONG" : "SHORT", kindTxt, lineTxt,
                          side > 0 ? (rulesOk ? " (exit at 50 EMA)" : " (exit at 9 EMA)") : " (TP last support)");''',
    '''   g_pDesc = StringFormat("%s %s on the %s%s", side > 0 ? "LONG" : "SHORT", kindTxt, lineTxt,
                          side > 0 ? (rulesOk ? " (exit at 50 EMA)" : " (exit at 9 EMA)") : " (TP last support)");
   Log(StringFormat("SETUP %s | candle %s H %s L %s | waiting 1 candle for a break %s %s", g_pDesc, Ts(g_pTime), Px(h), Px(l),
                    side > 0 ? "above" : "below", Px(side > 0 ? h + InpBreakPips * Pip() : l - InpBreakPips * Pip())));''')
rep('''void DSkip(int side, string why)
{''', '''void DSkip(int side, string why)
{
   Log("SKIP: " + why + " | " + g_pDesc);''')

# ---------- CTC ----------
rep('''               g_ctc++;
               SlMoved(''', '''               g_ctc++; g_pos[i].ctcAt = TimeCurrent();
               SlMoved(''')

# ---------- $ trail: count moves, track best price ----------
rep('''         if ((sd > 0 ? want >= cur + 10 * _Point : (cur == 0 || want <= cur - 10 * _Point)) && ModifySl(g_pos[i].ticket, want))
            g_pos[i].slNow = want;      // drawn as one line at the exit, not a step per tick''',
    '''         if ((sd > 0 ? want >= cur + 10 * _Point : (cur == 0 || want <= cur - 10 * _Point)) && ModifySl(g_pos[i].ticket, want)) {
            g_pos[i].slNow = want;      // drawn as one line at the exit, not a step per tick
            g_pos[i].moves++;
         }''')
rep("   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {\n      if (InpLockAtUsd > 0",
    "   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {\n"
    "      g_pos[i].mfe = g_pos[i].side > 0 ? MathMax(g_pos[i].mfe, bid) : (g_pos[i].mfe == 0 ? ask0 : MathMin(g_pos[i].mfe, ask0));\n"
    "      if (InpLockAtUsd > 0")

# ---------- TP1 / TP2 / TP3 ----------
rep('''   g_pos[i].tpNext = res; g_pos[i].tpStage = 2;''',
    '''   g_pos[i].tpNext = res; g_pos[i].tpStage = 2; g_pos[i].tp1At = TimeCurrent();
   g_pos[i].tps = res > 0 ? "TP2 " + Px(res) : "TP2 none";
   Log(StringFormat("#%d TP1: %d EMA touched @ %s (entry %s, +$%.2f) | SL -> %s ($%.2f trail) | TP2 %s",
                    g_pos[i].num, g_pos[i].exitE, Px(bid), Px(g_pos[i].entry), bid - g_pos[i].entry, Px(sl), InpLongTrailUsd,
                    res > 0 ? Px(res) + " (last resistance)" : "none above"));''')
rep('''   g_pos[i].tpNext = sup; g_pos[i].tpStage = 2;''',
    '''   g_pos[i].tpNext = sup; g_pos[i].tpStage = 2; g_pos[i].tp1At = TimeCurrent();
   g_pos[i].tps = sup > 0 ? "TP2 " + Px(sup) : "TP2 none";
   Log(StringFormat("#%d TP1: support reached @ %s (entry %s, +$%.2f) | SL -> %s ($%.2f trail) | TP2 %s",
                    g_pos[i].num, Px(bid), Px(g_pos[i].entry), g_pos[i].entry - bid, Px(sl), InpShortTrailUsd,
                    sup > 0 ? Px(sup) + " (next support)" : "none below"));''')
rep('''   int sd = g_pos[i].side;
   double nx = g_pos[i].tpNext;''', '''   int sd = g_pos[i].side;
   double nx = g_pos[i].tpNext;
   g_pos[i].tps += StringFormat(" > TP%d %s", g_pos[i].tpStage, nx > 0 ? Px(nx) : "none");
   Log(StringFormat("#%d TP%d %s reached -> TP%d %s", g_pos[i].num, g_pos[i].tpStage - 1, Px(was), g_pos[i].tpStage,
                    nx > 0 ? Px(nx) : "none (riding the trailing stop)"));''')

# ---------- day close ----------
rep('''      if (pl < 0) { g_pos[i].why = "day close, in loss"; if (trade.PositionClose(g_pos[i].ticket)) g_closeLoss++; }''',
    '''      if (pl < 0) {
         g_pos[i].why = "day close, in loss";
         Log(StringFormat("#%d day close in %d min and the trade is $%.2f down -> shutting it", g_pos[i].num, MinsToClose(), pl));
         if (trade.PositionClose(g_pos[i].ticket)) g_closeLoss++;
      }''')

s = s.replace('#property version   "1.09"', '#property version   "1.10"').replace('"[SAAD-15min] v1.09 ', '"[SAAD-15min] v1.10 ')
open(p, 'w', encoding='utf-8').write(s)
print('patched')
