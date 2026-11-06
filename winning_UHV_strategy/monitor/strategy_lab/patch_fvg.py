"""Build mt5/Saad_fvg.mq5 = Saad_guard + FVG-tap "safe zone" filter (Zee 2026-10-12).
A bullish FVG: low[c3] > high[c1] (3 candles, c1 oldest). Price later trades back into the gap = a TAP
(liquidity collected). If it taps without closing through the gap's far edge, the FVG HELD.
Modes (InpFvgMode): 0 off · 1 LONG only within InpFvgWin candles after a bullish FVG was tapped and held
(SHORT mirror) · 2 the setup candle itself taps a same-direction FVG.
InpFvgSl: 0 normal stop · 1 stop InpFvgSlPips beyond the tapped FVG's far edge · 2 the tighter of the two."""
src = r'C:\Users\zeesh\turtle\mt5\Saad_guard.mq5'
dst = r'C:\Users\zeesh\turtle\mt5\Saad_fvg.mq5'
s = open(src, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("input int    InpHtfMin      = 0;",
    """input int    InpFvgMode     = 0;      // InpFvgMode — FVG safe zone: 0 off · 1 trade only within InpFvgWin candles after a same-side FVG was tapped and held · 2 the setup candle taps it
input double InpFvgMinAtr   = 0.5;    // InpFvgMinAtr — only FVGs at least this x ATR(14) tall ("larger" FVGs)
input int    InpFvgTf       = 0;      // InpFvgTf — FVG timeframe in minutes (0 = the chart's)
input int    InpFvgLook     = 96;     // InpFvgLook — FVGs older than this many chart candles are forgotten
input int    InpFvgWin      = 8;      // InpFvgWin — mode 1: the safe zone lasts this many candles after the tap
input int    InpFvgSl       = 0;      // InpFvgSl — 0 normal stop · 1 beyond the tapped FVG's far edge · 2 the tighter of the two
input double InpFvgSlPips   = 10;     // InpFvgSlPips — stop distance beyond the FVG's far edge
input int    InpHtfMin      = 0;""")

rep("int g_ctc = 0, g_skipClose = 0, g_closeLoss = 0;", """// ---- FVGs ----
struct Fvg { int side; double top; double bot; datetime born; datetime tap; bool dead; };
Fvg g_fvg[];
datetime g_fvgLastBar = 0;
double g_fvgEdge = 0;        // far edge of the FVG that made the current setup safe (for InpFvgSl)
int g_ctc = 0, g_skipClose = 0, g_closeLoss = 0;""")

# scanning + tap tracking, called on each new chart candle
rep("// a new setup on the candle that just closed\ndatetime g_coolUntil = 0;", """// FVG scan on the FVG timeframe + tap / hold / break tracking on the chart's last closed candle
void FvgUpdate()
{
   if (InpFvgMode <= 0) return;
   ENUM_TIMEFRAMES tf = InpFvgTf == 0 ? PERIOD_CURRENT : InpFvgTf == 15 ? PERIOD_M15 : InpFvgTf == 30 ? PERIOD_M30 : InpFvgTf == 60 ? PERIOD_H1 : InpFvgTf == 240 ? PERIOD_H4 : PERIOD_CURRENT;
   datetime b1 = iTime(_Symbol, tf, 1);
   if (b1 != g_fvgLastBar) {                      // a new FVG-timeframe candle closed: is [3,2,1] a gap?
      g_fvgLastBar = b1;
      double a = Buf(hAtr, 1); if (tf != PERIOD_CURRENT) a *= MathSqrt((double)PeriodSeconds(tf) / PeriodSeconds());
      double h3 = iHigh(_Symbol, tf, 3), l3 = iLow(_Symbol, tf, 3), h1 = iHigh(_Symbol, tf, 1), l1 = iLow(_Symbol, tf, 1);
      Fvg f; f.tap = 0; f.dead = false; f.born = b1;
      bool add = false;
      if (l1 > h3 && l1 - h3 >= InpFvgMinAtr * a) { f.side = 1; f.bot = h3; f.top = l1; add = true; }
      else if (h1 < l3 && l3 - h1 >= InpFvgMinAtr * a) { f.side = -1; f.top = l3; f.bot = h1; add = true; }
      if (add) { int n = ArraySize(g_fvg); ArrayResize(g_fvg, n + 1); g_fvg[n] = f; }
   }
   double h = iHigh(_Symbol, PERIOD_CURRENT, 1), l = iLow(_Symbol, PERIOD_CURRENT, 1), c = iClose(_Symbol, PERIOD_CURRENT, 1);
   datetime t1 = iTime(_Symbol, PERIOD_CURRENT, 1);
   for (int i = ArraySize(g_fvg) - 1; i >= 0; i--) {
      bool old = t1 - g_fvg[i].born > InpFvgLook * PeriodSeconds();
      if (old || g_fvg[i].dead) { for (int j = i; j < ArraySize(g_fvg) - 1; j++) g_fvg[j] = g_fvg[j + 1]; ArrayResize(g_fvg, ArraySize(g_fvg) - 1); continue; }
      if (t1 <= g_fvg[i].born) continue;          // not on the candles that made it
      if (g_fvg[i].side > 0) {
         if (c < g_fvg[i].bot) { g_fvg[i].dead = true; continue; }            // closed through: broken
         if (l <= g_fvg[i].top) g_fvg[i].tap = t1;                             // traded into the gap: tapped and held
      } else {
         if (c > g_fvg[i].top) { g_fvg[i].dead = true; continue; }
         if (h >= g_fvg[i].bot) g_fvg[i].tap = t1;
      }
   }
}
// is the setup on the candle that just closed inside an FVG safe zone for this side?
bool FvgSafe(int side)
{
   if (InpFvgMode <= 0) return true;
   datetime t1 = iTime(_Symbol, PERIOD_CURRENT, 1);
   for (int i = 0; i < ArraySize(g_fvg); i++) {
      if (g_fvg[i].side != side || g_fvg[i].dead || g_fvg[i].tap == 0) continue;
      bool ok = InpFvgMode == 2 ? g_fvg[i].tap == t1 : (t1 - g_fvg[i].tap) <= InpFvgWin * PeriodSeconds();
      if (ok) { g_fvgEdge = side > 0 ? g_fvg[i].bot : g_fvg[i].top; return true; }
   }
   return false;
}

// a new setup on the candle that just closed
datetime g_coolUntil = 0;""")

rep("void DetectSetup()\n{", "void DetectSetup()\n{\n   FvgUpdate();")
rep("   int side = longOk ? 1 : -1;\n", "   int side = longOk ? 1 : -1;\n   if (!FvgSafe(side)) { g_filtered++; return; }\n")

# stop beyond the FVG edge
rep("   DoEntry(side, StopFor(side, side > 0 ? ask : bid, g_pHigh, g_pLow));\n}",
    """   double slN = StopFor(side, side > 0 ? ask : bid, g_pHigh, g_pLow);
   if (InpFvgMode > 0 && InpFvgSl > 0 && g_fvgEdge > 0) {
      double slF = side > 0 ? g_fvgEdge - InpFvgSlPips * Pip() : g_fvgEdge + InpFvgSlPips * Pip();
      bool valid = side > 0 ? slF < (side > 0 ? ask : bid) : slF > bid;
      if (valid) slN = InpFvgSl == 1 ? slF : (side > 0 ? MathMax(slN, slF) : MathMin(slN, slF));
   }
   DoEntry(side, slN);
}""")
s = s.replace('#property version   "1.16"', '#property version   "1.17"').replace('"[SAAD-15min] v1.16 ', '"[SAAD-15min] v1.17 ')
open(dst, 'w', encoding='utf-8').write(s)
print('wrote', dst)
