"""One-off patch: Saad_strategy_15min v1.04 - Zee's LONG exit (RULES_EMA_SAAD.md lines 11-16):
a candle touches the 50 EMA -> 1) trailing SL $3 below the market, 2) TP = next liquidity (last resistance)."""
p = r'C:\Users\zeesh\turtle\mt5\Saad_strategy_15min.mq5'
s = open(p, encoding='utf-8').read()


def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (s.count(a), a[:90])
    s = s.replace(a, b)


rep("input double InpBeTpPct     = 0.75;",
    "input int    InpLongTouch   = 1;      // InpLongTouch — LONG at the exit EMA: 1 on a TOUCH trail $X below the market + TP at the last resistance (Zee 2026-10-12) · 0 old exit\n"
    "input double InpLongTrailUsd = 3.0;   // InpLongTrailUsd — ...the trailing stop's distance below the market, $ of price\n"
    "input bool   InpLongResTp   = true;   // InpLongResTp — ...also set the TP at the next liquidity (last swing high above)\n"
    "input double InpBeTpPct     = 0.75;")

rep("struct PosState { ulong ticket; int side; double entry; double tp; int exitE; bool noTp; bool ride; datetime entryTime; double best;\n",
    "struct PosState { ulong ticket; int side; double entry; double tp; int exitE; bool noTp; bool ride; datetime entryTime; double best; bool usdTrail;\n")
# initialise the new field where positions are created
rep("p.num = ++g_num; p.slNow = PositionGetDouble(POSITION_SL); p.slFrom = p.entryTime; p.why = \"\";",
    "p.num = ++g_num; p.slNow = PositionGetDouble(POSITION_SL); p.slFrom = p.entryTime; p.why = \"\"; p.usdTrail = false;")
rep("p.num = ++g_num; p.slNow = NormalizeDouble(sl, _Digits); p.slFrom = p.entryTime; p.why = \"\";",
    "p.num = ++g_num; p.slNow = NormalizeDouble(sl, _Digits); p.slFrom = p.entryTime; p.why = \"\"; p.usdTrail = false;")

# last resistance helper, next to LastSupport
rep("bool Choppy()\n{",
    '''// the most recent confirmed swing high above `above` (the "next liquidity" for a LONG)
double LastResistance(double above)
{
   int p = InpSwingPivot;
   for (int i = 1 + p; i < 1 + p + InpSwingLook; i++) {
      double h = iHigh(_Symbol, PERIOD_CURRENT, i);
      if (h <= 0) break;
      if (h <= above) continue;
      bool piv = true;
      for (int k = 1; k <= p && piv; k++)
         if (iHigh(_Symbol, PERIOD_CURRENT, i - k) >= h || iHigh(_Symbol, PERIOD_CURRENT, i + k) > h) piv = false;
      if (piv) return h;
   }
   return 0.0;
}

bool Choppy()
{''')

# tick by tick: the touch, then the $ trail
rep("      if (InpFixTpPips > 0) continue;\n      if (g_pos[i].ride) continue;",
    '''      if (InpFixTpPips > 0) continue;
      if (g_pos[i].usdTrail && PositionSelectByTicket(g_pos[i].ticket)) {
         // LONG after the touch: the stop follows the market $X below, never back
         double want = NormalizeDouble(bid - InpLongTrailUsd, _Digits), cur = PositionGetDouble(POSITION_SL);
         if (want >= cur + 10 * _Point && ModifySl(g_pos[i].ticket, want)) {
            g_pos[i].slNow = want;      // drawn as one line at the exit, not a step per tick
         }
         continue;
      }
      if (InpLongTouch == 1 && g_pos[i].side > 0 && !g_pos[i].ride && !g_pos[i].noTp) {
         double tgt = Ema(g_pos[i].exitE, 0) - InpLongTpPips * Pip();
         if (tgt > g_pos[i].entry && bid >= tgt) { LongTouched(i, bid); continue; }
      }
      if (g_pos[i].ride) continue;''')

rep("// tick by tick: target touches\nvoid ManageTick()",
    '''// LONG: a candle touched the exit EMA -> trail $X below the market and aim for the last resistance
void LongTouched(int i, double bid)
{
   g_pos[i].ride = true; g_pos[i].usdTrail = true; g_rides++;
   if (!PositionSelectByTicket(g_pos[i].ticket)) return;
   double cur = PositionGetDouble(POSITION_SL);
   double sl = NormalizeDouble(MathMax(cur, bid - InpLongTrailUsd), _Digits);
   double res = InpLongResTp ? LastResistance(bid + InpMinTpPips * Pip()) : 0;
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
}

// tick by tick: target touches
void ManageTick()''')

# candle-close: the old close-mode TP and the ATR trail do not apply to these longs
rep("      if (side > 0 && !g_pos[i].ride && InpFixTpPips <= 0) {",
    "      if (g_pos[i].usdTrail) continue;              // LONG after the touch: trailed tick by tick\n"
    "      if (side > 0 && !g_pos[i].ride && InpFixTpPips <= 0 && InpLongTouch == 0) {")

# exit label: a broker TP on a long = last resistance
rep('   else if (reason == DEAL_REASON_TP) why = "TP (last support)";',
    '   else if (reason == DEAL_REASON_TP) why = p.side > 0 ? "TP (last resistance)" : "TP (last support)";')
rep('      why = MathAbs(p.slNow - p.entry) < _Point ? "breakeven (CTC)"',
    '      why = p.usdTrail ? StringFormat("trailing stop ($%.0f)", InpLongTrailUsd) : MathAbs(p.slNow - p.entry) < _Point ? "breakeven (CTC)"')

s = s.replace('#property version   "1.03"', '#property version   "1.04"').replace('"[SAAD-15min] v1.03 ', '"[SAAD-15min] v1.04 ')
open(p, 'w', encoding='utf-8').write(s)
print('patched')
