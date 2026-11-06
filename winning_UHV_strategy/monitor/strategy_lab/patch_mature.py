"""Build mt5/Saad_mature.mq5 = Saad_cut + "mature runner" HTF exit (Zee 2026-10-13).
A position becomes MATURE when it has been open InpMatureBars candles AND is in profit, or when its open
profit reaches InpMatureR x its initial risk. From then on the EA stops all M15 management of it ($ trail,
ATR trail, EMA exits, CTC) and only does this, once per new M15 candle:
   InpMatureMode 1: stop = the last H1 swing low (LONG) / swing high (SHORT) - InpMatureBufPips
                 2: the same on H4
                 3: stop = best price -/+ InpMatureAtr x ATR(14, M15)
 never worse than the entry (profit floor), and after the switch it only ever tightens.
 Swing = a candle whose low (high) is the lowest (highest) of InpMatureSwingK candles on each side."""
src = r'C:\Users\zeesh\turtle\mt5\Saad_cut.mq5'
dst = r'C:\Users\zeesh\turtle\mt5\Saad_mature.mq5'
s = open(src, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("input int    InpFlatMode    = 0;",
    """input int    InpMatureMode  = 0;      // InpMatureMode — mature-runner exit: 0 off · 1 H1 swing · 2 H4 swing · 3 ATR x InpMatureAtr trail
input int    InpMatureBars  = 20;     // InpMatureBars — mature after this many candles open AND in profit (0 = never by time)
input double InpMatureR     = 3.0;    // InpMatureR — ...or once open profit reaches this x the initial risk (0 = never by profit)
input double InpMatureAtr   = 3.0;    // InpMatureAtr — mode 3: ATR(14) multiple
input int    InpMatureSwingK = 2;     // InpMatureSwingK — swing = lowest/highest of this many HTF candles each side
input double InpMatureBufPips = 10;   // InpMatureBufPips — stop this many pips beyond the swing
input int    InpFlatMode    = 0;""")
rep("int num; double slNow;", "bool mature; int num; double slNow;")
rep("p.tpNext = 0; p.tpStage = 1; p.setHi = g_pHigh;", "p.tpNext = 0; p.tpStage = 1; p.mature = false; p.setHi = g_pHigh;")
s = s.replace("p.tpNext = 0; p.tpStage = 1; p.resTp1 = false; p.setHi = 0; p.setLo = 0;", "p.tpNext = 0; p.tpStage = 1; p.resTp1 = false; p.mature = false; p.setHi = 0; p.setLo = 0;")
rep("int g_ctc = 0,", "int g_matured = 0, g_matureMoves = 0;\nint g_ctc = 0,")

rep("void ManageTick()\n{", r'''//--- mature runners -----------------------------------------------------------
double HtfSwing(int side)
{
   ENUM_TIMEFRAMES tf = InpMatureMode == 2 ? PERIOD_H4 : PERIOD_H1;
   int k = MathMax(1, InpMatureSwingK);
   for (int b = k + 1; b < 200; b++) {
      double v = side > 0 ? iLow(_Symbol, tf, b) : iHigh(_Symbol, tf, b);
      if (v <= 0) return 0;
      bool piv = true;
      for (int j = 1; j <= k && piv; j++) {
         double a = side > 0 ? iLow(_Symbol, tf, b - j) : iHigh(_Symbol, tf, b - j), c = side > 0 ? iLow(_Symbol, tf, b + j) : iHigh(_Symbol, tf, b + j);
         if (side > 0 ? (a < v || c < v) : (a > v || c > v)) piv = false;
      }
      if (piv) return v;
   }
   return 0;
}
// once per new candle: does position i become mature, and where does its stop go
void MatureBar(int i)
{
   if (InpMatureMode <= 0 || !PositionSelectByTicket(g_pos[i].ticket)) return;
   int side = g_pos[i].side;
   double px = side > 0 ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double risk = MathAbs(g_pos[i].entry - g_pos[i].sl0); if (risk <= 0) risk = Buf(hAtr, 1);
   double prof = side * (px - g_pos[i].entry);
   if (!g_pos[i].mature) {
      int bars = (int)((TimeCurrent() - g_pos[i].entryTime) / PeriodSeconds());
      bool byTime = InpMatureBars > 0 && bars >= InpMatureBars && prof > 0;
      bool byProf = InpMatureR > 0 && prof >= InpMatureR * risk;
      if (!byTime && !byProf) return;
      g_pos[i].mature = true; g_matured++;
      Log(StringFormat("#%d MATURE (%s) -> H%s exit engine", g_pos[i].num, byProf ? "profit" : "time", InpMatureMode == 3 ? "ATR" : (InpMatureMode == 2 ? "4 swing" : "1 swing")));
   }
   double want = 0;
   if (InpMatureMode == 3) want = side > 0 ? g_pos[i].mfe - InpMatureAtr * Buf(hAtr, 1) : g_pos[i].mfe + InpMatureAtr * Buf(hAtr, 1);
   else { double sw = HtfSwing(side); if (sw > 0) want = side > 0 ? sw - InpMatureBufPips * Pip() : sw + InpMatureBufPips * Pip(); }
   if (want <= 0) return;
   want = side > 0 ? MathMax(want, g_pos[i].entry) : MathMin(want, g_pos[i].entry);       // profit floor
   want = NormalizeDouble(want, _Digits);
   double cur = PositionGetDouble(POSITION_SL);
   bool first = g_pos[i].slFrom < g_pos[i].entryTime + 1 || cur == 0;                    // (never moved yet)
   bool better = side > 0 ? want > cur + _Point : (cur == 0 || want < cur - _Point);
   static ulong switched[]; bool done = false;
   for (int k = 0; k < ArraySize(switched); k++) if (switched[k] == g_pos[i].ticket) { done = true; break; }
   if (!done) {                                                                            // the switch itself may LOOSEN the stop
      int n = ArraySize(switched); ArrayResize(switched, n + 1); switched[n] = g_pos[i].ticket;
      better = MathAbs(want - cur) > _Point;
   }
   if ((side > 0 ? px - want : want - px) < (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point) return;
   if (better && ModifySl(g_pos[i].ticket, want)) { g_matureMoves++; SlMoved(i, want, "mature"); }
}

void ManageTick()
{''')
# mature positions: skip all tick management (only the MFE is tracked)
rep("      g_pos[i].mfe = g_pos[i].side > 0 ? MathMax(g_pos[i].mfe, bid) : (g_pos[i].mfe == 0 ? ask0 : MathMin(g_pos[i].mfe, ask0));\n",
    "      g_pos[i].mfe = g_pos[i].side > 0 ? MathMax(g_pos[i].mfe, bid) : (g_pos[i].mfe == 0 ? ask0 : MathMin(g_pos[i].mfe, ask0));\n"
    "      if (g_pos[i].mature) continue;\n")
# per bar: maturity check + HTF stop first, then skip normal bar management for mature ones
rep("      ulong t = g_pos[i].ticket;\n      if (!PositionSelectByTicket(t)) continue;\n      int side = g_pos[i].side;\n      double sl = PositionGetDouble(POSITION_SL);\n",
    "      ulong t = g_pos[i].ticket;\n      if (!PositionSelectByTicket(t)) continue;\n      MatureBar(i);\n      if (g_pos[i].mature) continue;\n"
    "      int side = g_pos[i].side;\n      double sl = PositionGetDouble(POSITION_SL);\n")
rep('   PrintFormat("[SAAD] CTC breakevens %d',
    '   PrintFormat("[SAAD-MATURE] mode %d: %d positions matured, %d HTF stop moves", InpMatureMode, g_matured, g_matureMoves);\n   PrintFormat("[SAAD] CTC breakevens %d')
open(dst, 'w', encoding='utf-8').write(s)
print('wrote', dst)
