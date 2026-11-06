"""One-off patch: Saad_strategy_15min v1.06 - TP1 -> trail $3, TP2 = next liquidity, TP3 = the one beyond
(ladder, watched by the EA; the exit is the trailing stop), for LONGs and SHORTs (Zee, RULES_EMA_SAAD.md)."""
p = r'C:\Users\zeesh\turtle\mt5\Saad_strategy_15min.mq5'
s = open(p, encoding='utf-8').read()


def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (s.count(a), a[:90])
    s = s.replace(a, b)


rep("input bool   InpLongResTp   = true;   // InpLongResTp — ...also set the TP at the next liquidity (last swing high above)\n",
    "input bool   InpLongResTp   = true;   // InpLongResTp — ...and aim for the next liquidity: TP2 = last resistance, then TP3 = the one beyond (watched by the EA; the exit is the trail)\n"
    "input int    InpShortTouch  = 1;      // InpShortTouch — SHORT at the support (TP1): 1 trail $X above the market + TP2/TP3 = the supports below (Zee 2026-10-12) · 0 old (lock + ATR trail)\n"
    "input double InpShortTrailUsd = 3.0;  // InpShortTrailUsd — ...the trailing stop's distance above the market, $ of price\n")

rep("datetime entryTime; double best; bool usdTrail;\n",
    "datetime entryTime; double best; bool usdTrail; double tpNext; int tpStage;\n")
rep('p.why = ""; p.usdTrail = false;', 'p.why = ""; p.usdTrail = false; p.tpNext = 0; p.tpStage = 1;', 2)

# the $ trail for both sides + the TP2 -> TP3 ladder
rep('''      if (g_pos[i].usdTrail && PositionSelectByTicket(g_pos[i].ticket)) {
         // LONG after the touch: the stop follows the market $X below, never back
         double want = NormalizeDouble(bid - InpLongTrailUsd, _Digits), cur = PositionGetDouble(POSITION_SL);
         if (want >= cur + 10 * _Point && ModifySl(g_pos[i].ticket, want)) {
            g_pos[i].slNow = want;      // drawn as one line at the exit, not a step per tick
         }
         continue;
      }''', '''      if (g_pos[i].usdTrail && PositionSelectByTicket(g_pos[i].ticket)) {
         // after TP1: the stop follows the market $X away, never back
         int sd = g_pos[i].side;
         double want = NormalizeDouble(sd > 0 ? bid - InpLongTrailUsd : ask0 + InpShortTrailUsd, _Digits), cur = PositionGetDouble(POSITION_SL);
         if ((sd > 0 ? want >= cur + 10 * _Point : (cur == 0 || want <= cur - 10 * _Point)) && ModifySl(g_pos[i].ticket, want))
            g_pos[i].slNow = want;      // drawn as one line at the exit, not a step per tick
         // the next liquidity reached: aim for the one beyond (TP2 -> TP3 -> ...)
         if (g_pos[i].tpNext > 0 && (sd > 0 ? bid >= g_pos[i].tpNext : bid <= g_pos[i].tpNext)) {
            double was = g_pos[i].tpNext;
            g_pos[i].tpStage++;
            g_pos[i].tpNext = sd > 0 ? LastResistance(was + InpMinTpPips * Pip()) : LastSupport(was - InpMinTpPips * Pip());
            NextTpLabel(i, was);
         }
         continue;
      }''')

# shorts: TP1 (the support) -> trail $3 + TP2
rep("         if (g_pos[i].tp > 0 && TrailOn(-1) && InpRide && bid <= g_pos[i].tp) TpReached(i, g_pos[i].tp);",
    "         if (g_pos[i].tp > 0 && InpShortTouch == 1 && bid <= g_pos[i].tp) { ShortTouched(i, bid); continue; }\n"
    "         if (g_pos[i].tp > 0 && TrailOn(-1) && InpRide && bid <= g_pos[i].tp) TpReached(i, g_pos[i].tp);")

# LongTouched: no broker TP any more; TP2 is watched
rep('''   double res = InpLongResTp ? LastResistance(bid + InpMinTpPips * Pip()) : 0;
   double tp = res > 0 ? NormalizeDouble(res, _Digits) : 0;
   double lvl = MathMax((double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL)) * _Point;
   if (sl >= bid - lvl) sl = cur;
   if (tp > 0 && tp <= SymbolInfoDouble(_Symbol, SYMBOL_ASK) + lvl) tp = 0;
   bool ok = trade.PositionModify(g_pos[i].ticket, sl, tp);
   if (ok && sl != cur) SlMoved(i, sl, "");
   g_pos[i].tp = tp;
   string note = StringFormat("%d EMA touched -> trail $%.2f below%s", g_pos[i].exitE, InpLongTrailUsd,
                              tp > 0 ? StringFormat(", TP %.2f (last resistance)", tp) : ", no resistance above: no TP");
   Callout(TimeCurrent(), bid, true, 1.5, note, clrAqua, 8);
   if (tp > 0) DLine(TimeCurrent(), tp, TimeCurrent() + 8 * PeriodSeconds(), tp, clrLime, STYLE_DASH, 1, "TP: last resistance");
}''', '''   double res = InpLongResTp ? LastResistance(bid + InpMinTpPips * Pip()) : 0;
   double lvl = MathMax((double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL)) * _Point;
   if (sl >= bid - lvl) sl = cur;
   if (sl != cur && ModifySl(g_pos[i].ticket, sl)) SlMoved(i, sl, "");
   g_pos[i].tpNext = res; g_pos[i].tpStage = 2;
   string note = StringFormat("TP1: %d EMA touched -> trail $%.2f below%s", g_pos[i].exitE, InpLongTrailUsd,
                              res > 0 ? StringFormat(", TP2 %.2f (last resistance)", res) : ", no resistance above");
   Callout(TimeCurrent(), bid, true, 1.5, note, clrAqua, 8);
   if (res > 0) DLine(TimeCurrent(), res, TimeCurrent() + 8 * PeriodSeconds(), res, clrLime, STYLE_DASH, 1, "TP2: last resistance");
}

// SHORT: the support (TP1) reached -> trail $X above the market, aim for the next support (TP2)
void ShortTouched(int i, double bid)
{
   g_pos[i].ride = true; g_pos[i].usdTrail = true; g_rides++;
   if (!PositionSelectByTicket(g_pos[i].ticket)) return;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double cur = PositionGetDouble(POSITION_SL);
   double sl = NormalizeDouble(cur > 0 ? MathMin(cur, ask + InpShortTrailUsd) : ask + InpShortTrailUsd, _Digits);
   double lvl = MathMax((double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL)) * _Point;
   if (sl <= ask + lvl) sl = cur;
   if (sl != cur && ModifySl(g_pos[i].ticket, sl)) SlMoved(i, sl, "");
   double sup = LastSupport(bid - InpMinTpPips * Pip());
   g_pos[i].tpNext = sup; g_pos[i].tpStage = 2;
   string note = StringFormat("TP1: support reached -> trail $%.2f above%s", InpShortTrailUsd,
                              sup > 0 ? StringFormat(", TP2 %.2f (next support)", sup) : ", no support below");
   Callout(TimeCurrent(), bid, false, 1.5, note, clrAqua, 8);
   if (sup > 0) DLine(TimeCurrent(), sup, TimeCurrent() + 8 * PeriodSeconds(), sup, clrLime, STYLE_DASH, 1, "TP2: next support");
}

// TPn reached: label it and draw the next target
void NextTpLabel(int i, double was)
{
   int sd = g_pos[i].side;
   double nx = g_pos[i].tpNext;
   string note = StringFormat("TP%d %.2f reached -> %s", g_pos[i].tpStage - 1, was,
                              nx > 0 ? StringFormat("TP%d %.2f (%s)", g_pos[i].tpStage, nx, sd > 0 ? "next resistance" : "next support")
                                     : "no further level: riding the trailing stop");
   Callout(TimeCurrent(), was, sd > 0, 1.5, note, clrAqua, 8);
   if (nx > 0) DLine(TimeCurrent(), nx, TimeCurrent() + 8 * PeriodSeconds(), nx, clrLime, STYLE_DASH, 1, StringFormat("TP%d", g_pos[i].tpStage));
}''')

# exit label for shorts on the $ trail
rep('why = p.usdTrail ? StringFormat("trailing stop ($%.0f)", InpLongTrailUsd)',
    'why = p.usdTrail ? StringFormat("trailing stop ($%.0f) after TP%d", p.side > 0 ? InpLongTrailUsd : InpShortTrailUsd, p.tpStage - 1)')

s = s.replace('#property version   "1.05"', '#property version   "1.06"').replace('"[SAAD-15min] v1.05 ', '"[SAAD-15min] v1.06 ')
open(p, 'w', encoding='utf-8').write(s)
print('patched')
