"""One-off patch: Saad_strategy_15min v1.03 - day-close rules + clearer callout labels."""
p = r'C:\Users\zeesh\turtle\mt5\Saad_strategy_15min.mq5'
s = open(p, encoding='utf-8').read()


def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (s.count(a), a[:90])
    s = s.replace(a, b)


# ---------- inputs ----------
rep("input bool   InpDrawSkips   = true;",
    "input bool   InpDrawSkips   = false;")
rep("input double InpBeTpPct     = 0.75;",
    "input int    InpNoNewMins   = 30;     // InpNoNewMins — no new setups / entries this many minutes before the day's close (0 = off) [v1.03, Zee]\n"
    "input int    InpCloseLossMins = 3;    // InpCloseLossMins — this many minutes before the close: shut trades in loss, keep winners (0 = off) [v1.03, Zee]\n"
    "input double InpBeTpPct     = 0.75;")

# ---------- day close helpers (after TrailOn) ----------
rep("//--- chart labels (like the TradingView indicator).",
    r'''//--- the day's close, from the broker's trading sessions for this symbol (covers the Friday close too)
datetime SessionEnd(datetime now)
{
   MqlDateTime d; TimeToStruct(now, d);
   long sec = d.hour * 3600 + d.min * 60 + d.sec;
   datetime day0 = now - (datetime)sec;
   datetime from, to;
   for (uint k = 0; k < 10; k++) {
      if (!SymbolInfoSessionTrade(_Symbol, (ENUM_DAY_OF_WEEK)d.day_of_week, k, from, to)) break;
      long f = (long)from % 86400, t = (long)to; if (t > 86400) t = t % 86400; if (t == 0) t = 86400;
      if (sec >= f && sec < t) {
         // a session running to 24:00 that the next day continues at 00:00 is not a close
         if (t == 86400) {
            datetime f2, t2; MqlDateTime n; TimeToStruct(day0 + 86400, n);
            if (SymbolInfoSessionTrade(_Symbol, (ENUM_DAY_OF_WEEK)n.day_of_week, 0, f2, t2) && (long)f2 % 86400 == 0) return 0;
         }
         return day0 + (datetime)t;
      }
   }
   return 0;
}
int MinsToClose() { datetime e = SessionEnd(TimeCurrent()); return e == 0 ? 100000 : (int)((e - TimeCurrent()) / 60); }

//--- chart labels (like the TradingView indicator).''')

# ---------- callout labels: text away from the candle, arrow back to it ----------
rep("// a skipped setup: grey note under (long) / over (short) its candle",
    r'''// a label placed `lvl` x ATR away from the candle (above when up=true) with an arrow pointing back to (t, price)
void Callout(datetime t, double price, bool up, double lvl, string txt, color c, int size = 9, string tip = "")
{
   if (!Drawing()) return;
   double a = Buf(hAtr, 1); if (a <= 0) a = 10 * Pip();
   double ty = up ? price + lvl * a : price - lvl * a;
   string n = ObjName();
   ObjectCreate(0, n, OBJ_ARROWED_LINE, 0, t, ty, t, price);
   ObjectSetInteger(0, n, OBJPROP_COLOR, c);
   ObjectSetInteger(0, n, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, n, OBJPROP_BACK, true);
   DText(t, ty, txt, c, size, up ? ANCHOR_LOWER : ANCHOR_UPPER, tip);
}
// a skipped setup: grey note under (long) / over (short) its candle''')
rep('''   DText(g_pTime, side > 0 ? g_pLow - off : g_pHigh + off, "x SKIP: " + why, clrGray, 7,
         side > 0 ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER, "skipped: " + why + " | " + g_pDesc);''',
    '''   Callout(g_pTime, side > 0 ? g_pLow - off : g_pHigh + off, side < 0, 1.0, "skip: " + why, clrGray, 7, "skipped: " + why + " | " + g_pDesc);''')

# setup label -> callout above (long) / below (short), 2.5 ATR away
rep('''      DText(g_pTime, side > 0 ? h + 4 * Pip() : l - 4 * Pip(),
            StringFormat("SETUP %s: %s on %s", side > 0 ? "LONG" : "SHORT", kindTxt, lineTxt), clrGold, 8,
            side > 0 ? ANCHOR_LEFT_LOWER : ANCHOR_LEFT_UPPER,
            StringFormat("%s | wait max %d candle(s) for a break %s %.2f", g_pDesc, InpBreakBars, side > 0 ? "above" : "below", lvl));''',
    '''      Callout(g_pTime + PeriodSeconds() / 2, side > 0 ? h : l, side > 0, 2.5,
              StringFormat("SETUP %s: %s on %s", side > 0 ? "LONG" : "SHORT", kindTxt, lineTxt), clrGold, 9,
              StringFormat("%s | wait max %d candle(s) for a break %s %.2f", g_pDesc, InpBreakBars, side > 0 ? "above" : "below", lvl));''')

# entry label -> callout below (long) / above (short), 3 ATR away
rep('''      DText(p.entryTime, side > 0 ? p.entry - 3 * pip : p.entry + 3 * pip,
            StringFormat("%s #%d @ %.2f", side > 0 ? "BUY" : "SELL", p.num, p.entry), side > 0 ? clrDodgerBlue : clrOrangeRed, 9,
            side > 0 ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER,''',
    '''      Callout(p.entryTime, p.entry, side < 0, 3.0,
            StringFormat("%s #%d @ %.2f", side > 0 ? "BUY" : "SELL", p.num, p.entry), side > 0 ? clrDodgerBlue : clrOrangeRed, 10,''')

# exit label -> callout, 4 ATR away on the far side of the move
rep('''   DText(t, px, txt, c, 8, p.side > 0 ? ANCHOR_LEFT_LOWER : ANCHOR_LEFT_UPPER,''',
    '''   Callout(t, px, p.side > 0, 4.0, txt, c, 10,''')

# TP reached note -> callout
rep('''      DText(TimeCurrent(), tpLv, note, clrTeal, 7, g_pos[i].side > 0 ? ANCHOR_LEFT_LOWER : ANCHOR_LEFT_UPPER);''',
    '''      Callout(TimeCurrent(), tpLv, g_pos[i].side > 0, 1.5, note, clrAqua, 8);''')

# choppy note -> callout (only with skips on)
rep('''      if (InpDrawSkips) DText(iTime(_Symbol, PERIOD_CURRENT, 1), longOk ? l - 2 * Pip() : h + 2 * Pip(), "x choppy", clrDarkGray, 7,
                              longOk ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER);''',
    '''      if (InpDrawSkips) Callout(iTime(_Symbol, PERIOD_CURRENT, 1), longOk ? l : h, !longOk, 1.0, "skip: choppy", clrDimGray, 7);''')

# ---------- day-close rules ----------
# 1) no new setups near the close
rep("void DetectSetup()\n{\n   CheckCooldown();",
    "void DetectSetup()\n{\n   if (InpNoNewMins > 0 && MinsToClose() <= InpNoNewMins) return;   // too close to the day's close\n   CheckCooldown();")
# 2) a waiting setup is not entered near the close
rep("   if (g_pSide == 0 || ArraySize(g_pos) >= InpMaxPos) return;\n",
    "   if (g_pSide == 0 || ArraySize(g_pos) >= InpMaxPos) return;\n"
    "   if (InpNoNewMins > 0 && MinsToClose() <= InpNoNewMins) { g_skipClose++; DSkip(g_pSide, \"too close to the day's close\"); g_pSide = 0; return; }\n")
# 3) at the close: shut losers, keep winners
rep("void OnTick()\n{\n   SyncPos();\n   ManageTick();",
    '''void DayCloseCheck()
{
   if (InpCloseLossMins <= 0 || ArraySize(g_pos) == 0 || MinsToClose() > InpCloseLossMins) return;
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (!PositionSelectByTicket(g_pos[i].ticket)) continue;
      double pl = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      if (pl < 0) { g_pos[i].why = "day close, in loss"; if (trade.PositionClose(g_pos[i].ticket)) g_closeLoss++; }
   }
}

void OnTick()
{
   SyncPos();
   DayCloseCheck();
   SyncPos();
   ManageTick();''')
rep("int g_ctc = 0;", "int g_ctc = 0, g_skipClose = 0, g_closeLoss = 0;")
rep('PrintFormat("[SAAD] CTC breakevens %d", g_ctc);',
    'PrintFormat("[SAAD] CTC breakevens %d | day close: setups dropped %d, losing trades shut %d", g_ctc, g_skipClose, g_closeLoss);')
# print today's sessions at start, so the close time can be checked in the journal
rep("   return INIT_SUCCEEDED;\n}\n\nvoid OnDeinit",
    '''   datetime e = SessionEnd(TimeCurrent());
   PrintFormat("[SAAD] day close for %s: %s (no new trades %d min before; losers shut %d min before)", _Symbol,
               e == 0 ? "none found (no daily break)" : TimeToString(e), InpNoNewMins, InpCloseLossMins);
   return INIT_SUCCEEDED;
}

void OnDeinit''')

s = s.replace('#property version   "1.02"', '#property version   "1.03"').replace('"[SAAD-15min] v1.02 ', '"[SAAD-15min] v1.03 ')
open(p, 'w', encoding='utf-8').write(s)
print('patched')
