"""One-off patch: Saad_strategy_15min v1.12
- FIX: v1.11 reset p.resTp1 to false right after setting it (longs with the EMA below never got TP1)
- quiet trade logging in non-visual tester runs (the agent logs reached 381-866 MB and slowed / hung the rig)
- entry modes: 0 market on the break (unchanged) · 1 wait for a dip after the break (retest) · 2 liquidity sweep
- stop modes: 0 pips beyond the candle (unchanged) · 1 ATR x from entry · 2 fixed $ from entry
- partial close at TP1
- small-account sizing: risk % of equity per trade, skip when the minimum lot would risk too much, margin check
- daily loss limit in % of the day's starting equity
All defaults keep v1.11 behaviour (except the bug fix)."""
p = r'C:\Users\zeesh\turtle\mt5\Saad_strategy_15min.mq5'
s = open(p, encoding='utf-8').read()


def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (s.count(a), a[:90])
    s = s.replace(a, b)


# ---------- inputs ----------
rep("//--- trading\ninput double InpLots",
    '''//--- v1.12 variants (all off = v1.11 behaviour)
input int    InpEntryMode   = 0;      // InpEntryMode — 0 market on the break · 1 after the break wait for a dip (retest) · 2 liquidity sweep of the candle's low/high, then enter
input double InpRetestFrac  = 0.5;    // InpRetestFrac — mode 1: dip to this share back into the setup candle (0 = retest of the broken high/low, 0.5 = its middle, 1 = its far end)
input int    InpRetestBars  = 2;      // InpRetestBars — mode 1: candles to wait for the dip after the break
input double InpSweepPips   = 0;      // InpSweepPips — mode 2: price must trade this far beyond the setup candle's low (LONG) / high (SHORT)
input int    InpSweepBars   = 3;      // InpSweepBars — mode 2: candles allowed for the sweep and the entry
input int    InpSweepEntry  = 0;      // InpSweepEntry — mode 2: 0 enter when price reclaims the candle's low/high · 1 enter on the break of the candle's far end after the sweep
input double InpSweepSlPips = 10;     // InpSweepSlPips — mode 2: stop this many pips beyond the sweep's extreme
input int    InpSlMode      = 0;      // InpSlMode — 0 InpSlPips beyond the setup candle · 1 InpSlAtrMult x ATR from the entry · 2 InpSlUsd from the entry
input double InpSlAtrMult   = 1.0;    // InpSlAtrMult — stop mode 1
input double InpSlUsd       = 5.0;    // InpSlUsd — stop mode 2, $ of price
input double InpPartialPct  = 0;      // InpPartialPct — close this share of the position at TP1 (0 = off)
input double InpRiskPct     = 0;      // InpRiskPct — size each trade to risk this % of equity (0 = fixed InpLots)
input double InpMinLotRiskPct = 0;    // InpMinLotRiskPct — with InpRiskPct: skip a trade when even the minimum lot would risk more than this % of equity (0 = take it at the minimum lot)
input double InpMaxLots     = 50;     // InpMaxLots — upper limit for InpRiskPct sizing
input double InpDayLossPct  = 0;      // InpDayLossPct — no new trades today after losing this % of the day's starting equity (0 = off)

//--- trading
input double InpLots''')

# ---------- globals ----------
rep("int      g_pExit = 50;           // long: which EMA is its exit\n",
    '''int      g_pExit = 50;           // long: which EMA is its exit
// v1.12: entry armed after the break (mode 1) / sweep tracking (mode 2)
int      g_aSide = 0;            // mode 1: waiting for the dip
double   g_aLevel = 0, g_aHigh = 0, g_aLow = 0;
int      g_aLeft = 0, g_aExit = 50;
bool     g_swept = false;        // mode 2: the setup candle's low/high has been swept
double   g_sweepExt = 0;
double   g_dayStartEq = 0; int g_dayKey = -1;
int      g_skipDip = 0, g_skipSweep = 0, g_skipMinLot = 0, g_dayLossStop = 0, g_partials = 0;
''')

# ---------- quiet logs + counters ----------
rep("   trade.SetExpertMagicNumber(InpMagicNumber);\n",
    "   trade.SetExpertMagicNumber(InpMagicNumber);\n"
    "   if (MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)) trade.LogLevel(LOG_LEVEL_ERRORS);   // v1.12: agent logs were 381-866 MB\n")
rep('PrintFormat("[SAAD] CTC breakevens %d', 'PrintFormat("[SAAD] v1.12: no dip %d, no sweep %d, min-lot too risky %d, day loss stops %d, partial closes %d", g_skipDip, g_skipSweep, g_skipMinLot, g_dayLossStop, g_partials);\n   PrintFormat("[SAAD] CTC breakevens %d')

# ---------- FIX resTp1 ----------
rep("p.why = \"\"; p.usdTrail = false; p.tpNext = 0; p.tpStage = 1; p.resTp1 = false; p.setup = \"\"; p.sl0 = p.slNow; p.risk = 0; p.tp1 = \"\"; p.tp1At = 0; p.tps = \"\"; p.ctcAt = 0; p.moves = 0; p.mfe = 0;\n   p.setup = g_pDesc;",
    "p.why = \"\"; p.usdTrail = false; p.tpNext = 0; p.tpStage = 1; p.setup = \"\"; p.sl0 = p.slNow; p.risk = 0; p.tp1 = \"\"; p.tp1At = 0; p.tps = \"\"; p.ctcAt = 0; p.moves = 0; p.mfe = 0;\n   p.setup = g_pDesc;")

# ---------- TryEntry -> trigger logic + DoEntry(side, sl) ----------
rep('''   int side = g_pSide;
   bool hit = side > 0 ? (InpTrigBid ? bid : ask) > g_pHigh + InpBreakPips * pip : bid < g_pLow - InpBreakPips * pip;
   if (!hit) return;
   if (InpMaxSpreadPts > 0 && (ask - bid) / _Point > InpMaxSpreadPts) return;    // wait for a normal spread
   g_pSide = 0;
   double en = side > 0 ? ask : bid;
   double sl = side > 0 ? g_pLow - InpSlPips * pip : g_pHigh + InpSlPips * pip;
   if (InpMaxRiskUsd > 0''', '''   int side = g_pSide;
   if (InpEntryMode == 2) {
      // liquidity sweep: price first runs the stops beyond the setup candle, then comes back
      double far = side > 0 ? g_pLow - InpSweepPips * pip : g_pHigh + InpSweepPips * pip;
      if (!g_swept && (side > 0 ? bid < far : ask > far)) { g_swept = true; g_sweepExt = side > 0 ? bid : ask; Log(StringFormat("SWEEP of the setup candle's %s at %s", side > 0 ? "low" : "high", Px(g_sweepExt))); }
      if (g_swept) g_sweepExt = side > 0 ? MathMin(g_sweepExt, bid) : MathMax(g_sweepExt, ask);
      if (!g_swept) return;
      bool go = InpSweepEntry == 0 ? (side > 0 ? bid > g_pLow : ask < g_pHigh)
                                   : (side > 0 ? bid > g_pHigh + InpBreakPips * pip : bid < g_pLow - InpBreakPips * pip);
      if (!go) return;
      if (InpMaxSpreadPts > 0 && (ask - bid) / _Point > InpMaxSpreadPts) return;
      g_pSide = 0; g_swept = false;
      DoEntry(side, side > 0 ? g_sweepExt - InpSweepSlPips * pip : g_sweepExt + InpSweepSlPips * pip);
      return;
   }
   bool hit = side > 0 ? (InpTrigBid ? bid : ask) > g_pHigh + InpBreakPips * pip : bid < g_pLow - InpBreakPips * pip;
   if (!hit) return;
   if (InpMaxSpreadPts > 0 && (ask - bid) / _Point > InpMaxSpreadPts) return;    // wait for a normal spread
   g_pSide = 0;
   if (InpEntryMode == 1) {
      // the break happened: now wait for the dip back into the setup candle
      g_aSide = side; g_aHigh = g_pHigh; g_aLow = g_pLow; g_aExit = g_pExit; g_aLeft = InpRetestBars;
      g_aLevel = side > 0 ? g_pHigh - InpRetestFrac * (g_pHigh - g_pLow) : g_pLow + InpRetestFrac * (g_pHigh - g_pLow);
      Log(StringFormat("BREAK %s -> waiting %d candle(s) for a dip to %s", side > 0 ? "up" : "down", InpRetestBars, Px(g_aLevel)));
      return;
   }
   DoEntry(side, StopFor(side, side > 0 ? ask : bid, g_pHigh, g_pLow));
}

// mode 1: the dip after the break
void TryDip()
{
   if (g_aSide == 0 || ArraySize(g_pos) >= InpMaxPos) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   int side = g_aSide;
   if (side > 0 ? ask > g_aLevel : bid < g_aLevel) return;
   double sl = StopFor(side, side > 0 ? ask : bid, g_aHigh, g_aLow);
   g_aSide = 0;
   if (side > 0 ? bid <= sl : ask >= sl) { g_skipDip++; Log("dip went through the stop - skipped"); return; }
   g_pHigh = g_aHigh; g_pLow = g_aLow; g_pExit = g_aExit;
   DoEntry(side, sl);
}

// the stop for an entry at `en` from a setup candle [lo, hi]
double StopFor(int side, double en, double hi, double lo)
{
   double pip = Pip();
   if (InpSlMode == 1) { double a = Buf(hAtr, 1) * InpSlAtrMult; return side > 0 ? en - a : en + a; }
   if (InpSlMode == 2) return side > 0 ? en - InpSlUsd : en + InpSlUsd;
   return side > 0 ? lo - InpSlPips * pip : hi + InpSlPips * pip;
}

// lots for this trade: fixed, or InpRiskPct of equity (0 = skip)
double LotsFor(int side, double en, double sl)
{
   if (InpRiskPct <= 0) return InpLots;
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE), ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if (tv <= 0 || ts <= 0 || step <= 0) return InpLots;
   double perLot = MathAbs(en - sl) / ts * tv;                  // $ lost per 1 lot at the stop
   if (perLot <= 0) return 0;
   double lots = MathFloor(eq * InpRiskPct / 100.0 / perLot / step) * step;
   if (lots < mn) {
      if (InpMinLotRiskPct > 0 && mn * perLot > eq * InpMinLotRiskPct / 100.0) { g_skipMinLot++; return 0; }
      lots = mn;
   }
   lots = MathMin(lots, InpMaxLots);
   // margin: keep 10% free
   double m = 0;
   while (lots >= mn && OrderCalcMargin(side > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, _Symbol, lots, en, m) && m > AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.9)
      lots = MathFloor((lots - step) / step) * step;
   if (lots < mn) { g_skipMinLot++; return 0; }
   return NormalizeDouble(lots, 2);
}

void DoEntry(int side, double sl)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double pip = Pip();
   double en = side > 0 ? ask : bid;
   if (InpMaxRiskUsd > 0''')

# lots in the order + risk
rep('''   bool ok = side > 0 ? trade.Buy(InpLots, _Symbol, 0, NormalizeDouble(sl, _Digits), InpFixTpPips > 0 ? NormalizeDouble(tp, _Digits) : 0, "saad_long")
                      : trade.Sell(InpLots, _Symbol, 0, NormalizeDouble(sl, _Digits), rideShort ? 0 : NormalizeDouble(tp, _Digits), "saad_short");''',
    '''   double lots = LotsFor(side, en, sl);
   if (lots <= 0) { DSkip(side, "even the minimum lot risks too much of this account"); return; }
   bool ok = side > 0 ? trade.Buy(lots, _Symbol, 0, NormalizeDouble(sl, _Digits), InpFixTpPips > 0 ? NormalizeDouble(tp, _Digits) : 0, "saad_long")
                      : trade.Sell(lots, _Symbol, 0, NormalizeDouble(sl, _Digits), rideShort ? 0 : NormalizeDouble(tp, _Digits), "saad_short");''')
rep('''   p.risk = MathAbs(p.entry - sl) * InpLots * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);''',
    '''   p.risk = MathAbs(p.entry - sl) * lots * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);''')
rep('''   Log(StringFormat("ENTRY #%d %s %.2f lots @ %s | SL %s (risk $%.2f) | TP1 %s | setup: %s",
                    p.num, side > 0 ? "BUY" : "SELL", InpLots,''',
    '''   Log(StringFormat("ENTRY #%d %s %.2f lots @ %s | SL %s (risk $%.2f) | TP1 %s | setup: %s",
                    p.num, side > 0 ? "BUY" : "SELL", lots,''')
rep('''      double risk = MathAbs(p.entry - sl) * InpLots * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);''',
    '''      double risk = p.risk;''')

# ---------- partial close at TP1 ----------
rep("// LONG: a candle touched the exit EMA -> trail $X below the market and aim for the last resistance\nvoid LongTouched(int i, double bid)\n{",
    '''// v1.12: bank part of the position at TP1
void PartialAtTp1(int i)
{
   if (InpPartialPct <= 0 || !PositionSelectByTicket(g_pos[i].ticket)) return;
   double vol = PositionGetDouble(POSITION_VOLUME), step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double part = MathFloor(vol * InpPartialPct / step) * step;
   if (part >= mn && vol - part >= mn - 1e-9 && trade.PositionClosePartial(g_pos[i].ticket, NormalizeDouble(part, 2))) {
      g_partials++;
      Log(StringFormat("#%d TP1: closed %.2f of %.2f lots", g_pos[i].num, part, vol));
   }
}

// LONG: a candle touched the exit EMA -> trail $X below the market and aim for the last resistance
void LongTouched(int i, double bid)
{
   PartialAtTp1(i);''')
rep("void ShortTouched(int i, double bid)\n{",
    "void ShortTouched(int i, double bid)\n{\n   PartialAtTp1(i);")

# ---------- OnTick: armed dip expiry + TryDip + day start equity ----------
rep('''         if (g_pSide != 0) {''', '''         if (g_aSide != 0) {
            if (InpGapCancel && iTime(_Symbol, PERIOD_CURRENT, 0) - iTime(_Symbol, PERIOD_CURRENT, 1) > PeriodSeconds() * 3 / 2) { g_aSide = 0; g_skipDip++; }
            else if (--g_aLeft <= 0) { g_aSide = 0; g_skipDip++; Log("no dip within the window - skipped"); }
         }
         if (g_pSide != 0 && InpEntryMode == 2 && g_pLeft <= 1) { if (!g_swept) g_skipSweep++; }
         if (g_pSide != 0) {''')
rep("   TryEntry();\n}", "   TryEntry();\n   TryDip();\n}")
rep("void OnTick()\n{\n   SyncPos();",
    '''void OnTick()
{
   MqlDateTime dn; TimeToStruct(TimeCurrent(), dn);
   if (dn.day_of_year != g_dayKey) { g_dayKey = dn.day_of_year; g_dayStartEq = AccountInfoDouble(ACCOUNT_EQUITY); }
   SyncPos();''')

# ---------- DetectSetup: busy with an armed dip; day loss %; sweep window ----------
rep("   if (ArraySize(g_pos) >= InpMaxPos || (g_pSide != 0 && !InpReplace)) { g_busy++; return; }",
    "   if (InpDayLossPct > 0 && AccountInfoDouble(ACCOUNT_EQUITY) <= g_dayStartEq * (1 - InpDayLossPct / 100.0)) { g_dayLossStop++; return; }\n"
    "   if (ArraySize(g_pos) >= InpMaxPos || ((g_pSide != 0 || g_aSide != 0) && !InpReplace)) { g_busy++; return; }")
rep("   g_pSide = side; g_pHigh = h; g_pLow = l; g_pLeft = InpBreakBars; g_setups++;",
    "   g_pSide = side; g_pHigh = h; g_pLow = l; g_pLeft = InpEntryMode == 2 ? InpSweepBars : InpBreakBars; g_setups++; g_swept = false; g_aSide = 0;")

s = s.replace('#property version   "1.11"', '#property version   "1.12"').replace('"[SAAD-15min] v1.11 ', '"[SAAD-15min] v1.12 ')
open(p, 'w', encoding='utf-8').write(s)
print('patched')
