"""bread_winner v1.03: the New York 8:00-8:45 AM momentum trigger (InpTrig 128), same code as the research copy
mt5/bread_nymom.mq5 (run_bread_ny.py). Used by build_bread_final.py: apply_ny(text) -> text."""
EDITS = []


def rep(a, b):
    EDITS.append((a, b))


rep('input int    InpShotMax     = 1;',
'''input int    InpShotMax     = 1;
input double InpNyFrom      = 8.0;    // InpNyFrom — RESEARCH NY-momentum trigger (InpTrig 128): window start, New York hours
input double InpNyTo        = 8.75;   // InpNyTo — window end, New York hours (8.75 covers the 8:00 and 8:30 candles)
input int    InpNyMode      = 1;      // InpNyMode — 1 PULSE (pullback minute, then a momentum minute the M15 trend's way) · 2 BURST (a big momentum minute, its own way) · 3 the M15 candle (body + size), its own way, at its close
input double InpNyBody      = 60;     // InpNyBody — momentum candle: body >= this % of its range
input double InpNyAtr       = 1.5;    // InpNyAtr — momentum candle range >= this x ATR(14) of its timeframe (modes 2, 3)
input bool   InpNyCtx       = false;  // InpNyCtx — the shot must also pass the context (trend side + ER)''')
rep('''   int side = BwTrendSide();
   if ((InpTrig & 16) != 0) {''',
'''   int side = BwTrendSide();
   if ((InpTrig & 128) != 0) {                       // NY momentum: 8:00-8:45 AM New York (Axi server = New York + 7 h)
      MqlDateTime n; TimeToStruct(TimeCurrent() - 7 * 3600, n);
      double nh = n.hour + n.min / 60.0;
      if (nh >= InpNyFrom && nh < InpNyTo && n.day_of_week >= 1 && n.day_of_week <= 5) {
         int s = 0;
         if (InpNyMode == 1 && side != 0) {
            double o1 = iOpen(_Symbol, PERIOD_M1, 1), c1 = iClose(_Symbol, PERIOD_M1, 1), h1 = iHigh(_Symbol, PERIOD_M1, 1), l1 = iLow(_Symbol, PERIOD_M1, 1);
            double o2 = iOpen(_Symbol, PERIOD_M1, 2), c2 = iClose(_Symbol, PERIOD_M1, 2), r = h1 - l1;
            bool mom = r > 0 && MathAbs(c1 - o1) >= InpNyBody / 100.0 * r && side * (c1 - o1) > 0 && (side > 0 ? c1 >= h1 - 0.25 * r : c1 <= l1 + 0.25 * r);
            if (mom && side * (c2 - o2) < 0) s = side;
         } else if (InpNyMode == 2 || InpNyMode == 3) {
            static datetime lastM15 = 0;
            ENUM_TIMEFRAMES tf = InpNyMode == 2 ? PERIOD_M1 : PERIOD_M15;
            bool fresh = true;
            if (InpNyMode == 3) { datetime b = iTime(_Symbol, PERIOD_M15, 1); fresh = b != lastM15 && TimeCurrent() - iTime(_Symbol, PERIOD_M15, 0) < 120; lastM15 = b; }
            if (g_hNyAtr1 == INVALID_HANDLE) { g_hNyAtr1 = iATR(_Symbol, PERIOD_M1, 14); g_hNyAtr15 = iATR(_Symbol, PERIOD_M15, 14); }
            double o1 = iOpen(_Symbol, tf, 1), c1 = iClose(_Symbol, tf, 1), h1 = iHigh(_Symbol, tf, 1), l1 = iLow(_Symbol, tf, 1), r = h1 - l1;
            double a = BwBuf(InpNyMode == 2 ? g_hNyAtr1 : g_hNyAtr15, 1);
            if (fresh && r > 0 && a > 0 && r >= InpNyAtr * a && MathAbs(c1 - o1) >= InpNyBody / 100.0 * r)
               s = c1 > o1 ? 1 : -1;
         }
         if (s != 0) { g_sig[4]++; if (!InpNyCtx || BwContextOk(s)) { BwHostShot(s, 4); return; } }
      }
   }
   if ((InpTrig & 16) != 0) {''')
rep('// ---- host triggers on each new M1 bar ----', 'int g_hNyAtr1 = INVALID_HANDLE, g_hNyAtr15 = INVALID_HANDLE;\n// ---- host triggers on each new M1 bar ----')


def apply_ny(s):
    for a, b in EDITS:
        assert s.count(a) == 1, (s.count(a), a[:70])
        s = s.replace(a, b)
    return s
