"""VSISA v1.29 -> v1.30: a live status panel on the chart (Zee 2026-10-14: "when i attach it to the chart. it shows
what its doing in real time. is it waiting for setup? which stage of setup is it in. which candle is it monitoring..
we can't leave the user with a blank chart"). Display only: no trading decision changes.
Shows: state (waiting / outside hours / cooling down / max open / day-loss stop) + countdown to the next candle
check; the candle just checked (box on the chart) with the BUY and SELL verdict = how far the setup got and where it
failed (from VSISA's own rejection counters); trend, regime, last meta-label score; open trades with R reached and
the exhaustion reading; today's funnel and top rejection reasons."""
p = r'C:\Users\zeesh\turtle\mt5\VSISA.mq5'
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:70])
    s = s.replace(a, b)


rep('#property version   "1.29"', '#property version   "1.30"')
rep('PrintFormat("[VSISA] v1.29 (ML:', 'PrintFormat("[VSISA] v1.30 (ML:')
rep('input bool   InpVerbose     = false;', 'input bool   InpDashboard   = true;   // InpDashboard — live status panel + the candle being checked, on the chart\ninput bool   InpVerbose     = false;')

# capture the last meta score and exhaustion reading for the panel
rep('      mlscore = V_MetaModelScore(mlf);', '      mlscore = V_MetaModelScore(mlf); g_dMeta = mlscore; g_dMetaT = TimeCurrent();')
rep('      if (InpExhMode == 1 && flt > 0) { p = V_ExhModelProb(e);', '      if (InpExhMode == 1 && flt > 0) { p = V_ExhModelProb(e); g_dExh = p; g_dExhPos = (ulong)PositionGetInteger(POSITION_IDENTIFIER);')

rep('//--- machine-learning hooks -----------------------------------------------------', r'''//--- v1.30 live dashboard ------------------------------------------------------------
double   g_dMeta = -1; datetime g_dMetaT = 0; double g_dExh = -1; ulong g_dExhPos = 0;
string   g_dState = "starting - waiting for the first candle to close";
string   g_dBuy = "-", g_dSell = "-", g_dFade = "";
datetime g_dCandle = 0;
int      g_dDay = -1, g_dChecked = 0, g_dSetups = 0, g_dVeto = 0, g_dTrades = 0;
int      g_dRej[14];
string   g_dRejName[14] = {"setup bars not all closing one way", "no loud (high-volume) setup bar", "volume not rising into the turn",
                           "setup bar not a spread anomaly", "no fake break (no sweep of a recent extreme)", "no reaction candle",
                           "reaction body too small", "reaction not quiet enough", "against the higher-timeframe trend",
                           "test / confirmation failed", "target too near", "last setup bar not the capped loud one",
                           "reaction did not close at its extreme", "no setup run before the turn"};
void DashSnap(int &v[])
{
   ArrayResize(v, 13);
   v[0] = g_rej_dir; v[1] = g_rej_loud; v[2] = g_rej_rise; v[3] = g_rej_anom; v[4] = g_rej_fake; v[5] = g_rej_react; v[6] = g_rej_body;
   v[7] = g_rej_quiet; v[8] = g_rej_trend; v[9] = g_rej_test; v[10] = g_rej_tgt; v[11] = g_rej_cap; v[12] = g_rej_loc;
}
// what one Detect() call concluded, from which rejection counter moved
string DashWhy(const int &a[], const int &b[], bool found)
{
   if (found) return "SETUP FOUND";
   for (int i = 0; i < 13; i++) if (b[i] > a[i]) { g_dRej[i]++; return "rejected: " + g_dRejName[i]; }
   g_dRej[13]++;
   return "no setup: " + g_dRejName[13];
}
void DashNewDay() { MqlDateTime d; TimeToStruct(TimeCurrent(), d); if (d.day_of_year != g_dDay) { g_dDay = d.day_of_year; g_dChecked = g_dSetups = g_dVeto = g_dTrades = 0; ArrayInitialize(g_dRej, 0); } }
void DashLabel(string name, int x, int y, string text, color c, int size)
{
   if (ObjectFind(0, name) < 0) { ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0); ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER); ObjectSetString(0, name, OBJPROP_FONT, "Consolas"); ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false); }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x); ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text); ObjectSetInteger(0, name, OBJPROP_COLOR, c); ObjectSetInteger(0, name, OBJPROP_FONTSIZE, size);
}
void DashDraw()
{
   if (!InpDashboard || (MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE))) return;
   string L[]; color C[]; int n = 0;
   #define DL(txt, col) { ArrayResize(L, n + 1); ArrayResize(C, n + 1); L[n] = txt; C[n] = col; n++; }
   int left = (int)(iTime(_Symbol, PERIOD_CURRENT, 0) + PeriodSeconds() - TimeCurrent());
   DL(StringFormat("VSISA v1.30  %s M%d  magic %d  lots %.2f", _Symbol, PeriodSeconds() / 60, InpMagicNumber, InpLots), clrGold);
   DL(StringFormat("ML: meta %s  regime %s  exhaustion %s", InpMetaMode > 0 ? StringFormat("ON (skip < %.2f)", InpMetaThr) : "off",
                   InpRegimeMode > 0 ? "ON" : "off", InpExhMode > 0 ? StringFormat("ON (close at P >= %.2f)", InpExhThr) : "off"), clrSilver);
   DL("STATE: " + g_dState, clrWhite);
   DL(StringFormat("next candle check in %d:%02d", MathMax(0, left) / 60, MathMax(0, left) % 60), clrSilver);
   int td = TrendDir();
   string rg = g_mlRegime < 0 ? "-" : StringFormat("cluster %d%s", g_mlRegime, ((InpRegSkipMask >> g_mlRegime) & 1) == 1 && InpRegimeMode > 0 ? " (HIGH VOL: entries paused)" : "");
   DL(StringFormat("trend (M%d): %s   regime: %s", InpTrendTF, td > 0 ? "UP" : td < 0 ? "DOWN" : "flat/none", rg), clrSilver);
   DL("--- last candle checked: " + (g_dCandle > 0 ? TimeToString(g_dCandle, TIME_DATE | TIME_MINUTES) : "-") + " ---", clrGoldenrod);
   DL("BUY : " + g_dBuy, StringFind(g_dBuy, "FOUND") >= 0 ? clrLime : clrWhiteSmoke);
   DL("SELL: " + g_dSell, StringFind(g_dSell, "FOUND") >= 0 ? clrLime : clrWhiteSmoke);
   if (g_dFade != "") DL("FADE: " + g_dFade, clrWhiteSmoke);
   if (g_dMetaT > 0) DL(StringFormat("last meta-label score %.2f at %s", g_dMeta, TimeToString(g_dMetaT, TIME_MINUTES)), clrSilver);
   DL("--- open trades ---", clrGoldenrod);
   int open = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || PositionGetInteger(POSITION_MAGIC) != InpMagicNumber || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      open++;
      int sd = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
      double en = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP);
      double px = sd > 0 ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double r = sl > 0 && MathAbs(en - sl) > 0 ? sd * (px - en) / MathAbs(en - sl) : 0;
      double flt = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      ulong pid = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      DL(StringFormat("%s %.2f @ %.2f  SL %.2f  TP %.2f  |  %s$%.2f  (%.2f R)%s", sd > 0 ? "BUY" : "SELL", PositionGetDouble(POSITION_VOLUME), en, sl, tp,
                      flt >= 0 ? "+" : "-", MathAbs(flt), r, (g_dExhPos == pid && g_dExh >= 0) ? StringFormat("  exhaustion %.2f", g_dExh) : ""), flt >= 0 ? clrLime : clrSalmon);
   }
   if (open == 0) DL("none", clrSilver);
   DL(StringFormat("--- today: %d candles checked, %d setups, %d vetoed by ML, %d trades ---", g_dChecked, g_dSetups, g_dVeto, g_dTrades), clrGoldenrod);
   int idx[3] = {-1, -1, -1};
   for (int k = 0; k < 3; k++) { int best = -1; for (int i = 0; i < 14; i++) { bool used = false; for (int j = 0; j < k; j++) if (idx[j] == i) used = true; if (!used && g_dRej[i] > 0 && (best < 0 || g_dRej[i] > g_dRej[best])) best = i; } idx[k] = best; }
   for (int k = 0; k < 3; k++) if (idx[k] >= 0) DL(StringFormat("  %3d x %s", g_dRej[idx[k]], g_dRejName[idx[k]]), clrSilver);
   // panel
   TextSetFont("Consolas", -90); uint mw = 0, lh = 0;
   for (int i = 0; i < n; i++) { uint w, h; TextGetSize(L[i], w, h); mw = MathMax(mw, w); lh = MathMax(lh, h); }
   lh += 3;
   if (ObjectFind(0, "VSD_bg") < 0) { ObjectCreate(0, "VSD_bg", OBJ_RECTANGLE_LABEL, 0, 0, 0); ObjectSetInteger(0, "VSD_bg", OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, "VSD_bg", OBJPROP_BGCOLOR, C'16,22,36'); ObjectSetInteger(0, "VSD_bg", OBJPROP_BORDER_COLOR, clrGoldenrod); }
   ObjectSetInteger(0, "VSD_bg", OBJPROP_XDISTANCE, 8); ObjectSetInteger(0, "VSD_bg", OBJPROP_YDISTANCE, 22);
   ObjectSetInteger(0, "VSD_bg", OBJPROP_XSIZE, (int)mw + 24); ObjectSetInteger(0, "VSD_bg", OBJPROP_YSIZE, n * (int)lh + 14);
   for (int i = 0; i < n; i++) DashLabel("VSD_l" + IntegerToString(i), 18, 29 + i * (int)lh, L[i], C[i], 9);
   for (int i = n; i < 40; i++) ObjectDelete(0, "VSD_l" + IntegerToString(i));
   // the candle being checked: a box + its verdict above it
   if (g_dCandle > 0) {
      int sh = iBarShift(_Symbol, PERIOD_CURRENT, g_dCandle);
      double hi = iHigh(_Symbol, PERIOD_CURRENT, sh), lo = iLow(_Symbol, PERIOD_CURRENT, sh);
      if (ObjectFind(0, "VSD_box") < 0) { ObjectCreate(0, "VSD_box", OBJ_RECTANGLE, 0, 0, 0, 0, 0); ObjectSetInteger(0, "VSD_box", OBJPROP_SELECTABLE, false); ObjectSetInteger(0, "VSD_box", OBJPROP_FILL, false); ObjectSetInteger(0, "VSD_box", OBJPROP_WIDTH, 2); }
      ObjectSetInteger(0, "VSD_box", OBJPROP_TIME, 0, g_dCandle); ObjectSetDouble(0, "VSD_box", OBJPROP_PRICE, 0, hi);
      ObjectSetInteger(0, "VSD_box", OBJPROP_TIME, 1, g_dCandle + PeriodSeconds()); ObjectSetDouble(0, "VSD_box", OBJPROP_PRICE, 1, lo);
      bool any = StringFind(g_dBuy + g_dSell, "FOUND") >= 0;
      ObjectSetInteger(0, "VSD_box", OBJPROP_COLOR, any ? clrLime : clrGold);
      if (ObjectFind(0, "VSD_tag") < 0) { ObjectCreate(0, "VSD_tag", OBJ_TEXT, 0, 0, 0); ObjectSetInteger(0, "VSD_tag", OBJPROP_SELECTABLE, false); ObjectSetString(0, "VSD_tag", OBJPROP_FONT, "Consolas"); ObjectSetInteger(0, "VSD_tag", OBJPROP_FONTSIZE, 8); ObjectSetInteger(0, "VSD_tag", OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER); }
      double pad = (iHigh(_Symbol, PERIOD_CURRENT, iHighest(_Symbol, PERIOD_CURRENT, MODE_HIGH, 20, 0)) - iLow(_Symbol, PERIOD_CURRENT, iLowest(_Symbol, PERIOD_CURRENT, MODE_LOW, 20, 0))) * 0.06;
      double top = iHigh(_Symbol, PERIOD_CURRENT, iHighest(_Symbol, PERIOD_CURRENT, MODE_HIGH, MathMax(1, sh + 1), 0));
      ObjectSetInteger(0, "VSD_tag", OBJPROP_TIME, 0, g_dCandle); ObjectSetDouble(0, "VSD_tag", OBJPROP_PRICE, 0, top + pad);
      ObjectSetString(0, "VSD_tag", OBJPROP_TEXT, any ? "VSISA: SETUP on this candle" : "VSISA checked: " + (StringFind(g_dBuy, "no setup") == 0 && StringFind(g_dSell, "no setup") == 0 ? "no setup" : "rejected"));
      ObjectSetInteger(0, "VSD_tag", OBJPROP_COLOR, any ? clrLime : clrGold);
   }
   ChartRedraw();
}

//--- machine-learning hooks -----------------------------------------------------''')

# OnTick: states + verdicts
rep('''   if (t == g_last_bar) return;
   g_last_bar = t;
   MlBar();
''', '''   if (t == g_last_bar) { static uint lastDraw = 0; if (GetTickCount() - lastDraw > 1000) { DashDraw(); lastDraw = GetTickCount(); } return; }
   g_last_bar = t;
   MlBar();
   DashNewDay();
''')
rep('''   if (DayLossHit()) return;
   if (g_cool > 0) { g_cool--; return; }
   if (!InSession()) return;
   if (OpenDecisions() >= InpMaxOpen) return;

   double sl = 0;
   string why = "";
   if (InpBuys  && Detect(+1, sl, why)) { Fire(+1, sl, why); return; }
   if (InpSells && Detect(-1, sl, why)) { Fire(-1, sl, why); return; }
   // LAW 14 only gets a look once the ordinary setup has said no.
   if (InpBuys  && DetectFade(+1, sl, why)) { Fire(+1, sl, why); return; }
   if (InpSells && DetectFade(-1, sl, why)) { Fire(-1, sl, why); return; }
}''', '''   g_dCandle = iTime(_Symbol, PERIOD_CURRENT, 1); g_dFade = "";
   if (DayLossHit()) { g_dState = "daily loss limit hit - no new trades today"; g_dBuy = g_dSell = "not checked"; DashDraw(); return; }
   if (g_cool > 0) { g_cool--; g_dState = StringFormat("cooling down after a trade: %d more candle(s)", g_cool); g_dBuy = g_dSell = "not checked"; DashDraw(); return; }
   if (!InSession()) { g_dState = StringFormat("outside trading hours (%02d:00-%02d:00 broker time)", InpSessFrom, InpSessTo); g_dBuy = g_dSell = "not checked"; DashDraw(); return; }
   if (OpenDecisions() >= InpMaxOpen) { g_dState = StringFormat("managing %d open trade(s) - limit reached, no new setups", OpenDecisions()); g_dBuy = g_dSell = "not checked"; DashDraw(); return; }

   double sl = 0;
   string why = "";
   g_dChecked++;
   g_dState = OpenDecisions() > 0 ? "managing open trade(s) + watching each candle for a new setup" : "waiting for a setup - checking every closed candle";
   int a[], b[]; bool got;
   int fires0 = g_fires, veto0 = g_mlMetaVeto + g_mlRegVeto;
   DashSnap(a); got = InpBuys && Detect(+1, sl, why); DashSnap(b); g_dBuy = InpBuys ? DashWhy(a, b, got) : "buys disabled";
   if (got) { g_dSetups++; Fire(+1, sl, why); DashAfterFire(fires0, veto0, +1); return; }
   DashSnap(a); got = InpSells && Detect(-1, sl, why); DashSnap(b); g_dSell = InpSells ? DashWhy(a, b, got) : "sells disabled";
   if (got) { g_dSetups++; Fire(-1, sl, why); DashAfterFire(fires0, veto0, -1); return; }
   // LAW 14 only gets a look once the ordinary setup has said no.
   if (InpBuys  && DetectFade(+1, sl, why)) { g_dFade = "BUY fade setup FOUND"; g_dSetups++; Fire(+1, sl, why); DashAfterFire(fires0, veto0, +1); return; }
   if (InpSells && DetectFade(-1, sl, why)) { g_dFade = "SELL fade setup FOUND"; g_dSetups++; Fire(-1, sl, why); DashAfterFire(fires0, veto0, -1); return; }
   DashDraw();
}
void DashAfterFire(int fires0, int veto0, int side)
{
   string sd = side > 0 ? "BUY" : "SELL";
   if (g_fires > fires0) { g_dTrades++; g_dState = sd + " trade OPENED on this candle"; }
   else if (g_mlMetaVeto + g_mlRegVeto > veto0) { g_dVeto++; g_dState = sd + StringFormat(" setup VETOED by the ML filter (%s)", g_mlRegVeto > 0 && g_mlMetaVeto == 0 ? "regime" : StringFormat("meta score %.2f < %.2f", g_dMeta, InpMetaThr)); }
   else g_dState = sd + " setup found but refused (risk too big / target too near / order failed)";
   DashDraw();
}''')
rep('void OnDeinit(const int reason) {\n', 'void OnDeinit(const int reason) {\n   EventKillTimer(); ObjectsDeleteAll(0, "VSD_");\n')
rep('int OnInit() {\n', 'int OnInit() {\n   EventSetTimer(1);\n')
s = s.rstrip() + '\nvoid OnTimer() { DashDraw(); }   // v1.30: keep the panel and the countdown live between ticks\n'
s = s.replace('//| VSISA v1.29 (2026-10-14) = v1.28 + three machine-learning layers, |',
              '//| VSISA v1.30 (2026-10-14): live status panel on the chart (state,   |\n//| candle checked + why, trend/regime, open trades, today\'s funnel).  |\n//| v1.29 = v1.28 + three machine-learning layers,                     |')
open(p, 'w', encoding='utf-8').write(s)
print('v1.30 written')
