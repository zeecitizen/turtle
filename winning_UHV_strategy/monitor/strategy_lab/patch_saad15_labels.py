"""One-off patch: chart labels for mt5/Saad_strategy_15min.mq5 (v1.01). Run once."""
p = r'C:\Users\zeesh\turtle\mt5\Saad_strategy_15min.mq5'
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:90])
    s = s.replace(a, b)


rep("input bool   InpVerbose     = false;  // InpVerbose — print every decision\n",
    "input bool   InpVerbose     = false;  // InpVerbose — print every decision\n"
    "input bool   InpDraw        = true;   // InpDraw — labels on the chart (visual tester + live): setups, entries, stop moves, exits\n"
    "input bool   InpDrawSkips   = true;   // InpDrawSkips — also label setups that were skipped (no break, risk, no support, choppy)\n")

rep("struct PosState { ulong ticket; int side; double entry; double tp; int exitE; bool noTp; bool ride; datetime entryTime; double best; };",
    "struct PosState { ulong ticket; int side; double entry; double tp; int exitE; bool noTp; bool ride; datetime entryTime; double best;\n"
    "                  int num; double slNow; datetime slFrom; string why; };")

HELPERS = r'''
//--- chart labels (like the TradingView indicator). Plain text: MT5 shows no emoji.
int      g_obj = 0, g_num = 0;
string   g_pDesc = "";            // the waiting setup, for its labels
datetime g_pTime = 0;
bool Drawing() { return InpDraw && (!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_VISUAL_MODE)); }
string ObjName() { return StringFormat("SAAD_%d", g_obj++); }
void DText(datetime t, double price, string txt, color c, int size = 8, ENUM_ANCHOR_POINT anc = ANCHOR_LEFT_LOWER, string tip = "")
{
   if (!Drawing()) return;
   string n = ObjName();
   ObjectCreate(0, n, OBJ_TEXT, 0, t, price);
   ObjectSetString(0, n, OBJPROP_TEXT, txt);
   ObjectSetString(0, n, OBJPROP_FONT, "Arial");
   ObjectSetInteger(0, n, OBJPROP_FONTSIZE, size);
   ObjectSetInteger(0, n, OBJPROP_COLOR, c);
   ObjectSetInteger(0, n, OBJPROP_ANCHOR, anc);
   ObjectSetString(0, n, OBJPROP_TOOLTIP, tip == "" ? txt : tip);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
}
void DLine(datetime t1, double p1, datetime t2, double p2, color c, ENUM_LINE_STYLE st = STYLE_SOLID, int w = 1, string tip = "")
{
   if (!Drawing()) return;
   string n = ObjName();
   ObjectCreate(0, n, OBJ_TREND, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, n, OBJPROP_COLOR, c);
   ObjectSetInteger(0, n, OBJPROP_STYLE, st);
   ObjectSetInteger(0, n, OBJPROP_WIDTH, w);
   ObjectSetInteger(0, n, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
   if (tip != "") ObjectSetString(0, n, OBJPROP_TOOLTIP, tip);
}
void DBox(datetime t1, double p1, datetime t2, double p2, color c)
{
   if (!Drawing()) return;
   string n = ObjName();
   ObjectCreate(0, n, OBJ_RECTANGLE, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, n, OBJPROP_COLOR, c);
   ObjectSetInteger(0, n, OBJPROP_FILL, false);
   ObjectSetInteger(0, n, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, n, OBJPROP_BACK, true);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
}
void DArrow(datetime t, double price, int side)
{
   if (!Drawing()) return;
   string n = ObjName();
   ObjectCreate(0, n, side > 0 ? OBJ_ARROW_BUY : OBJ_ARROW_SELL, 0, t, price);
   ObjectSetInteger(0, n, OBJPROP_COLOR, side > 0 ? clrDodgerBlue : clrOrangeRed);
   ObjectSetInteger(0, n, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
}
// a skipped setup: grey note under (long) / over (short) its candle
void DSkip(int side, string why)
{
   if (!InpDrawSkips || g_pTime == 0) return;
   double off = 2 * Pip();
   DText(g_pTime, side > 0 ? g_pLow - off : g_pHigh + off, "x SKIP: " + why, clrGray, 7,
         side > 0 ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER, "skipped: " + why + " | " + g_pDesc);
}
// the stop moved: end the old segment, start a new one
void SlMoved(int i, double newSl, string note)
{
   if (!Drawing()) return;
   datetime now = TimeCurrent();
   DLine(g_pos[i].slFrom, g_pos[i].slNow, now, g_pos[i].slNow, g_pos[i].ride ? clrOrange : clrRed, STYLE_DASH, 2);
   g_pos[i].slNow = newSl; g_pos[i].slFrom = now;
   if (note != "") DText(now, newSl, note, clrOrange, 7, g_pos[i].side > 0 ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER);
}
// the position is gone: label its exit from the closing deal
void DrawExit(PosState &p)
{
   if (!Drawing() || !HistorySelectByPosition(p.ticket)) return;
   double px = 0, pnl = 0; datetime t = 0; long reason = -1;
   for (int k = HistoryDealsTotal() - 1; k >= 0; k--) {
      ulong d = HistoryDealGetTicket(k);
      if (HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      px = HistoryDealGetDouble(d, DEAL_PRICE); t = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
      pnl += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_COMMISSION) + HistoryDealGetDouble(d, DEAL_SWAP);
      reason = HistoryDealGetInteger(d, DEAL_REASON);
   }
   if (t == 0) return;
   string why = p.why;
   if (reason == DEAL_REASON_SL) why = (p.ride || (p.side > 0 ? p.slNow > p.entry : p.slNow < p.entry)) ? "trailing stop" : "stop loss";
   else if (reason == DEAL_REASON_TP) why = "TP (last support)";
   else if (why == "") why = "closed";
   DLine(p.slFrom, p.slNow, t, p.slNow, p.ride ? clrOrange : clrRed, STYLE_DASH, 2);
   DLine(p.entryTime, p.entry, t, px, pnl >= 0 ? clrLime : clrRed, STYLE_DOT, 1);
   color c = pnl > 0 ? clrLimeGreen : clrRed;
   string txt = StringFormat("EXIT #%d %s %s$%.2f", p.num, why, pnl >= 0 ? "+" : "-", MathAbs(pnl));
   DText(t, px, txt, c, 8, p.side > 0 ? ANCHOR_LEFT_LOWER : ANCHOR_LEFT_UPPER,
         StringFormat("#%d %s  entry %.2f -> exit %.2f  (%s)  %s$%.2f", p.num, p.side > 0 ? "BUY" : "SELL", p.entry, px, why,
                      pnl >= 0 ? "+" : "-", MathAbs(pnl)));
}
'''
rep("//--- positions\nint FindPos", HELPERS + "\n//--- positions\nint FindPos")

rep("      if (!PositionSelectByTicket(g_pos[i].ticket)) {\n         for (int j = i;",
    "      if (!PositionSelectByTicket(g_pos[i].ticket)) {\n         DrawExit(g_pos[i]);\n         for (int j = i;")
rep("p.entryTime = (datetime)PositionGetInteger(POSITION_TIME); p.best = p.entry;\n      int n = ArraySize(g_pos);",
    "p.entryTime = (datetime)PositionGetInteger(POSITION_TIME); p.best = p.entry;\n"
    "      p.num = ++g_num; p.slNow = PositionGetDouble(POSITION_SL); p.slFrom = p.entryTime; p.why = \"\";\n"
    "      int n = ArraySize(g_pos);")

rep('''      g_pos[i].ride = true; g_rides++;
      if (InpRideLock != 2 && PositionSelectByTicket(g_pos[i].ticket)) {
         double cur = PositionGetDouble(POSITION_SL);
         double lock = InpRideLock == 0 ? (g_pos[i].side > 0 ? tpLv - InpLockPips * Pip() : tpLv + InpLockPips * Pip()) : g_pos[i].entry;
         bool better = g_pos[i].side > 0 ? lock > cur : (cur == 0 || lock < cur);
         if (better && !ModifySl(g_pos[i].ticket, lock)) g_lockFail++;
      }
      return false;
   }
   return trade.PositionClose(g_pos[i].ticket);''', '''      g_pos[i].ride = true; g_rides++;
      string note = "TP reached -> trailing";
      if (InpRideLock != 2 && PositionSelectByTicket(g_pos[i].ticket)) {
         double cur = PositionGetDouble(POSITION_SL);
         double lock = InpRideLock == 0 ? (g_pos[i].side > 0 ? tpLv - InpLockPips * Pip() : tpLv + InpLockPips * Pip()) : g_pos[i].entry;
         bool better = g_pos[i].side > 0 ? lock > cur : (cur == 0 || lock < cur);
         if (better) {
            if (ModifySl(g_pos[i].ticket, lock)) { SlMoved(i, lock, ""); note += StringFormat(", SL locked %.2f", lock); }
            else { g_lockFail++; note += " (lock refused: too close)"; }
         }
      }
      DText(TimeCurrent(), tpLv, note, clrTeal, 7, g_pos[i].side > 0 ? ANCHOR_LEFT_LOWER : ANCHOR_LEFT_UPPER);
      return false;
   }
   g_pos[i].why = g_pos[i].side > 0 ? StringFormat("%d EMA (TP)", g_pos[i].exitE) : "TP (last support)";
   return trade.PositionClose(g_pos[i].ticket);''')

rep("if (InpMaxBars > 0 && TimeCurrent() - g_pos[i].entryTime >= InpMaxBars * PeriodSeconds()) { trade.PositionClose(g_pos[i].ticket); continue; }",
    "if (InpMaxBars > 0 && TimeCurrent() - g_pos[i].entryTime >= InpMaxBars * PeriodSeconds()) { g_pos[i].why = \"time exit\"; trade.PositionClose(g_pos[i].ticket); continue; }")
rep("if (g_pos[i].noTp && !TrailOn(1) && c1 < Ema(g_pos[i].exitE, 1)) { trade.PositionClose(t); continue; }",
    "if (g_pos[i].noTp && !TrailOn(1) && c1 < Ema(g_pos[i].exitE, 1)) { g_pos[i].why = StringFormat(\"closed below %d EMA\", g_pos[i].exitE); trade.PositionClose(t); continue; }")
rep("if (better) { ModifySl(t, lvl); sl = lvl; }",
    "if (better && ModifySl(t, lvl)) { SlMoved(i, lvl, StringFormat(\"trail %.2f\", lvl)); sl = lvl; }")
rep("if (!done && best > InpBeUsd) ModifySl(t, g_pos[i].entry);",
    "if (!done && best > InpBeUsd && ModifySl(t, g_pos[i].entry)) SlMoved(i, g_pos[i].entry, \"BE\");")
rep("(cur == 0 || want < cur - _Point))) ModifySl(g_pos[i].ticket, want);",
    "(cur == 0 || want < cur - _Point)) && ModifySl(g_pos[i].ticket, want)) SlMoved(i, want, \"lock\");")

rep("if (InpMaxRiskUsd > 0 && MathAbs(en - sl) > InpMaxRiskUsd) { g_skipRisk++; return; }",
    "if (InpMaxRiskUsd > 0 && MathAbs(en - sl) > InpMaxRiskUsd) { g_skipRisk++; DSkip(side, StringFormat(\"stop too far ($%.2f > $%.2f)\", MathAbs(en - sl), InpMaxRiskUsd)); return; }")
rep("if (sup <= 0) { g_skipSup++; return; }",
    "if (sup <= 0) { g_skipSup++; DSkip(side, \"no support below to target\"); return; }")
rep("if (InpMaxTpPips > 0 && bid - tp > InpMaxTpPips * pip) { g_skipSup++; return; }",
    "if (InpMaxTpPips > 0 && bid - tp > InpMaxTpPips * pip) { g_skipSup++; DSkip(side, \"support too far\"); return; }")

rep('''   p.entryTime = TimeCurrent(); p.best = p.entry;
   int n = ArraySize(g_pos); ArrayResize(g_pos, n + 1); g_pos[n] = p;
   g_entries++;''', '''   p.entryTime = TimeCurrent(); p.best = p.entry;
   p.num = ++g_num; p.slNow = NormalizeDouble(sl, _Digits); p.slFrom = p.entryTime; p.why = "";
   int n = ArraySize(g_pos); ArrayResize(g_pos, n + 1); g_pos[n] = p;
   g_entries++;
   if (Drawing()) {
      string tpTxt = side > 0 ? (noTp ? "none - trailing from entry" : StringFormat("candle closes at the %d EMA", g_pExit))
                              : StringFormat("%.2f (last support)", tp);
      double risk = MathAbs(p.entry - sl) * InpLots * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
      DArrow(p.entryTime, p.entry, side);
      DText(p.entryTime, side > 0 ? p.entry - 3 * pip : p.entry + 3 * pip,
            StringFormat("%s #%d @ %.2f", side > 0 ? "BUY" : "SELL", p.num, p.entry), side > 0 ? clrDodgerBlue : clrOrangeRed, 9,
            side > 0 ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER,
            StringFormat("%s #%d  entry %.2f | SL %.2f (-$%.2f) | TP %s | %s", side > 0 ? "BUY" : "SELL", p.num, p.entry, sl, risk, tpTxt, g_pDesc));
      DText(p.entryTime, sl, StringFormat("SL %.2f", sl), clrRed, 7, side > 0 ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER);
      if (side < 0) {
         DLine(p.entryTime, tp, p.entryTime + 8 * PeriodSeconds(), tp, clrLime, STYLE_DASH, 1, "TP: last support");
         DText(p.entryTime, tp, StringFormat("TP %.2f (last support)", tp), clrLime, 7, ANCHOR_LEFT_UPPER);
      } else if (!noTp)
         DText(p.entryTime + PeriodSeconds(), Ema(g_pExit, 0), StringFormat("TP: close at %d EMA", g_pExit), clrLime, 7, ANCHOR_LEFT_LOWER);
   }''')

rep("{ g_skipGap++; g_pSide = 0; }", "{ g_skipGap++; DSkip(g_pSide, \"market closed in between\"); g_pSide = 0; }")
rep("else if (--g_pLeft <= 0) { g_skipBreak++; g_pSide = 0; }",
    "else if (--g_pLeft <= 0) { g_skipBreak++; DSkip(g_pSide, StringFormat(\"%s not broken in %d candle%s\", g_pSide > 0 ? \"high\" : \"low\", InpBreakBars, InpBreakBars > 1 ? \"s\" : \"\")); g_pSide = 0; }")

rep("   if (Choppy()) { g_chop++; return; }", '''   if (Choppy()) {
      g_chop++;
      if (InpDrawSkips) DText(iTime(_Symbol, PERIOD_CURRENT, 1), longOk ? l - 2 * Pip() : h + 2 * Pip(), "x choppy", clrDarkGray, 7,
                              longOk ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER);
      return;
   }''')

rep('''   g_pSide = side; g_pHigh = h; g_pLow = l; g_pLeft = InpBreakBars; g_setups++;
   g_pExit = side > 0 ? (rulesOk ? 50 : 9) : 0;''', '''   g_pSide = side; g_pHigh = h; g_pLow = l; g_pLeft = InpBreakBars; g_setups++;
   g_pExit = side > 0 ? (rulesOk ? 50 : 9) : 0;
   string kindTxt = g_kind == 1 ? "PIN BAR" : g_kind == 2 ? (side > 0 ? "HAMMER" : "SHOOTING STAR") : "MARUBOZU";
   string lineTxt = side > 0 ? (rulesOk ? "9 EMA" : "50 EMA") : (OnLine(1, e9, -1) ? "9 EMA" : "50 EMA");
   g_pTime = iTime(_Symbol, PERIOD_CURRENT, 1);
   g_pDesc = StringFormat("%s %s on the %s%s", side > 0 ? "LONG" : "SHORT", kindTxt, lineTxt,
                          side > 0 ? (rulesOk ? " (exit at 50 EMA)" : " (exit at 9 EMA)") : " (TP last support)");
   if (Drawing()) {
      double lvl = side > 0 ? h + InpBreakPips * Pip() : l - InpBreakPips * Pip();
      DBox(g_pTime, h, g_pTime + PeriodSeconds(), l, clrGold);
      DLine(g_pTime, lvl, g_pTime + (InpBreakBars + 1) * PeriodSeconds(), lvl, clrGold, STYLE_DOT, 1, "break level");
      DText(g_pTime, side > 0 ? h + 4 * Pip() : l - 4 * Pip(),
            StringFormat("SETUP %s: %s on %s", side > 0 ? "LONG" : "SHORT", kindTxt, lineTxt), clrGold, 8,
            side > 0 ? ANCHOR_LEFT_LOWER : ANCHOR_LEFT_UPPER,
            StringFormat("%s | wait max %d candle(s) for a break %s %.2f", g_pDesc, InpBreakBars, side > 0 ? "above" : "below", lvl));
   }''')

s = s.replace('#property version   "1.00"', '#property version   "1.01"').replace('"[SAAD-15min] v1.00 ', '"[SAAD-15min] v1.01 ')
open(p, 'w', encoding='utf-8').write(s)
print('patched')
