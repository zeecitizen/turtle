"""Build mt5/Saad_strategy_15min_tvbars.mq5 = v1.27 on the TradingView chart's own 15-min candles (Zee 2026-10-20:
"ok, make the EA read TradingView's own candles, and give me MT5 result for Aug,Sept, Oct"). The bridge code comes from
Saad_strategy_1min v1.39 (83 of 83 chart trades); everything else is v1.27 untouched."""
import re
from pathlib import Path

src = Path(r"C:\Users\zeesh\turtle\mt5\Saad_strategy_15min.mq5")
dst = Path(r"C:\Users\zeesh\turtle\mt5\Saad_strategy_15min_tvbars.mq5")
t = src.read_text(encoding="utf-8")


def rep(o, n, cnt=1):
    global t
    assert t.count(o) == cnt, (o[:90], t.count(o))
    t = t.replace(o, n)


# --- 1. every candle / indicator read goes through the bridge (done BEFORE the bridge code is inserted)
for f, g in (("iOpen", "BOpen"), ("iHigh", "BHigh"), ("iLow", "BLow"), ("iClose", "BClose"), ("iTime", "BTime")):
    t = t.replace(f"{f}(_Symbol, PERIOD_CURRENT, ", f"{g}(")
t = t.replace("Buf(hAtr, ", "Atr(")
rep("double e9 = Buf(hFast, 1), e50 = Buf(hSlow, 1);", "double e9 = Ema(9, 1), e50 = Ema(50, 1);")
rep("(Buf(hSlow, 1) - Buf(hSlow, 1 + InpSlopeLook))", "(Ema(50, 1) - Ema(50, 1 + InpSlopeLook))")
assert "Buf(hFast" not in t and "Buf(hSlow" not in t.replace("return Buf(which == 9 ? hFast : hSlow, s);", "")

# --- 2. name, magic, inputs
rep('#define EA_COMMENT "Saad15 v1.27"', '''// TEST tvbars (Zee 2026-10-20: "ok, make the EA read TradingView's own candles, and give me MT5 result for Aug,Sept, Oct"): v1.27 with
//       every decision on the CHART's 15-min candles (bridge file from monitor/saad_compare/tv_bars_bridge.py): the chart's candle clock
//       (Monday 01:01), EMAs, ATR, ADX (MT5's formula on the chart's candles) and range boxes; the chart's candle decides breaks / stops
//       the two feeds disagree on by cents; no setup on a candle that closed while a trade was open. TEST - never attach to an account.
#define EA_COMMENT "Saad15 tvbars"''')
rep("input int    InpMagicNumber = 88302;", "input int    InpMagicNumber = 88309;")
i = t.index("input int    InpExitMode    = 1;")
j = t.index("\n", i) + 1
t = t[:j] + '''// TEST tvbars (Zee 2026-10-20) - the TradingView chart's own candles
input int    InpBarSource   = 1;      // InpBarSource - 0 MT5's own candles (= v1.27) · 1 the TradingView chart's candles (Common\\Files\\InpTvFile, written by monitor/saad_compare/tv_bars_bridge.py)
input string InpTvFile      = "auto"; // InpTvFile - the chart's closed candles in broker server time "YYYY.MM.DD HH:MM,open,high,low,close" · auto = tv_bars_XAUUSD_M15.csv on M15
input int    InpTvWaitSec   = 20;     // InpTvWaitSec - live: wait up to N s after a candle closes for the chart's candle to arrive
input bool   InpTvVerdict   = true;   // InpTvVerdict - when the two feeds disagree by cents the CHART's candle decides, at the next open: it broke the level and MT5 did not -> enter; MT5 broke it and the chart did not -> out; it went through the stop / reached the target EMA and MT5's ticks did not -> out. A stand-aside ghost is judged on the chart's candles
input double InpChartSpread = 0.17;   // InpChartSpread - the chart's fixed spread ($ of price), for its SELL stop / target checks
input datetime InpTvStepFrom = D'2026.10.12 01:01'; // InpTvStepFrom - the chart's first candle WITH 1-minute data inside (server time; the indicator's event table shows it). Before it the chart judges a candle in one step, so a ghost is not ended inside its entry candle
input bool   InpNoEntryExitBar = true; // InpNoEntryExitBar - a setup candle that CLOSED while a trade (or a stand-aside ghost) was still open is ignored, like the chart (busy at that candle's close)
input bool   InpBlindEntryBar = false; // InpBlindEntryBar - DIAGNOSTIC ONLY (never live): before InpTvStepFrom act like the chart without 1-minute data - no stop at the broker and no exit until the entry candle has closed, and no day-close loss check at all (one step per candle never lands in the last minutes)
input bool   InpLongEmaAbove = true;  // InpLongEmaAbove - exit mode 1: a BUY banks the touch of its target EMA only while that EMA is still ABOVE the entry, like the chart (v1.27 also closed a BUY at the EMA after it had sunk below the entry, at a small loss)
''' + t[j:]

# --- 3. state
rep("int num; double slNow; datetime slFrom; string why; int nxE; };", "int num; double slNow; datetime slFrom; string why; int nxE; double brk; datetime bar; double enC; double pendSl; bool pendClose; };")
# InpBlindEntryBar (diagnostic): the stop goes to the broker only when the entry candle has closed
rep("""   bool ok = side > 0 ? trade.Buy(lots, _Symbol, 0, NormalizeDouble(sl, _Digits), InpFixTpPips > 0 ? NormalizeDouble(tp, _Digits) : 0, EA_COMMENT + " BUY")
                      : trade.Sell(lots, _Symbol, 0, NormalizeDouble(sl, _Digits), rideShort ? 0 : NormalizeDouble(tp, _Digits), EA_COMMENT + " SELL");""",
    """   bool blind = BlindNow();      // TEST tvbars diagnostic: no broker stop inside the entry candle
   bool ok = side > 0 ? trade.Buy(lots, _Symbol, 0, blind ? 0 : NormalizeDouble(sl, _Digits), InpFixTpPips > 0 ? NormalizeDouble(tp, _Digits) : 0, EA_COMMENT + " BUY")
                      : trade.Sell(lots, _Symbol, 0, blind ? 0 : NormalizeDouble(sl, _Digits), rideShort ? 0 : NormalizeDouble(tp, _Digits), EA_COMMENT + " SELL");""")
rep("""   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      g_pos[i].mfe = g_pos[i].side > 0 ? MathMax(g_pos[i].mfe, bid) : (g_pos[i].mfe == 0 ? ask0 : MathMin(g_pos[i].mfe, ask0));""",
    """   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (g_pos[i].pendClose) {            // TEST tvbars: the chart's verdict could not close it (market closed) - every 5 s until it can
         static datetime retryAt = 0;
         if (TimeCurrent() >= retryAt && !trade.PositionClose(g_pos[i].ticket)) retryAt = TimeCurrent() + 5;
         continue;
      }
      if (g_pos[i].pendSl > 0) {           // TEST tvbars diagnostic: blind inside the entry candle; its stop goes in at the next candle's open
         if (g_pos[i].bar >= CurBar()) continue;
         double ps = g_pos[i].pendSl;
         if (g_pos[i].side > 0 ? bid <= ps : ask0 >= ps) { g_pos[i].why = "stop (the candle opened beyond it)"; g_pos[i].pendSl = 0; trade.PositionClose(g_pos[i].ticket); continue; }
         if (!ModifySl(g_pos[i].ticket, ps)) continue;
         g_pos[i].pendSl = 0;
      }
      g_pos[i].mfe = g_pos[i].side > 0 ? MathMax(g_pos[i].mfe, bid) : (g_pos[i].mfe == 0 ? ask0 : MathMin(g_pos[i].mfe, ask0));""")
# the day-close "in loss" rule: judged against the CHART's entry price (the chart: the minute's bid vs its entry)
rep("""   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (!PositionSelectByTicket(g_pos[i].ticket)) continue;
      double pl = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      if (pl < 0) {""", """   if (BlindNow()) return;      // TEST tvbars diagnostic: a candle seen only at its close never reaches the last minutes
   double bidN = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (!PositionSelectByTicket(g_pos[i].ticket) || g_pos[i].pendSl > 0) continue;
      double pl = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      if (g_useTv) pl = g_pos[i].side > 0 ? bidN - g_pos[i].enC : g_pos[i].enC - (bidN + ChartSpr());   // TEST tvbars: the chart's view of "in loss"
      if (pl < 0) {""")
rep("""   if (!end && InpCloseLossMins > 0 && MinsToClose() <= InpCloseLossMins) end = s > 0 ? bid < g_gEntry : ask > g_gEntry;""",
    """   if (!end && !BlindNow() && InpCloseLossMins > 0 && MinsToClose() <= InpCloseLossMins) end = s > 0 ? bid < g_gEntry : (g_useTv ? bid + ChartSpr() : ask) > g_gEntry;""")
rep("bool     g_gNoTp = false;", """bool     g_gNoTp = false;
double   g_gBrk = 0; datetime g_gBar = 0;   // TEST tvbars: the ghost's break level (0 = a late entry) and its entry candle
double   g_brk = 0;                         // TEST tvbars: the break level of the entry being made
double   g_enC = 0, g_bidC = 0;             // TEST tvbars: the CHART's entry price (ask / bid) of the entry being made
bool     g_busyAtClose = false;             // TEST tvbars: a trade / ghost was still open when the last candle closed""")
rep("      p.nxE = InpExitMode == 2 ? -2 : 0;", "      p.nxE = InpExitMode == 2 ? -2 : 0; p.brk = 0; p.bar = 0; p.enC = p.entry; p.pendSl = 0; p.pendClose = false;")
rep("   p.nxE = nxE;\n", "   p.nxE = nxE; p.brk = g_brk; p.bar = CurBar(); p.enC = enD; p.pendSl = blind ? NormalizeDouble(sl, _Digits) : 0; p.pendClose = false;\n")
rep("g_gSide = side; g_gEntry = en;", "g_gSide = side; g_gEntry = enD;")
rep("g_gTime = TimeCurrent(); g_ghosts++;", "g_gTime = TimeCurrent(); g_ghosts++; g_gBrk = g_brk; g_gBar = CurBar();")
# the chart's entry price decides the stop, the risk check and the target EMA (MT5's fill is a few cents away)
rep("   DoEntry(side, StopFor(side, side > 0 ? ask : bid, g_pHigh, g_pLow), off);",
    """   // TEST tvbars: the chart's entry price (the level + 1 cent, or the open beyond it) for the chart's decisions: stop, risk, target EMA
   g_bidC = !g_useTv ? bid : g_late > 0 ? g_lateBid : side > 0 ? MathMax(g_brk + 0.01, BOpen(0)) : MathMin(g_brk - 0.01, BOpen(0));
   g_enC = !g_useTv ? (side > 0 ? ask : bid) : side > 0 ? g_bidC + ChartSpr() : g_bidC;
   DoEntry(side, StopFor(side, g_enC, g_pHigh, g_pLow), off);""")
rep("""   double en = side > 0 ? ask : bid;
   if (InpMaxRiskUsd > 0 && MathAbs(en - sl) > InpMaxRiskUsd) { g_skipRisk++; DSkip(side, StringFormat("stop too far ($%.2f > $%.2f)", MathAbs(en - sl), InpMaxRiskUsd)); return; }""",
    """   double en = side > 0 ? ask : bid;
   double enD = g_enC > 0 ? g_enC : en, bidD = g_bidC > 0 ? g_bidC : bid;     // TEST tvbars: the chart's entry price for the decisions
   g_enC = 0; g_bidC = 0;
   if (InpMaxRiskUsd > 0 && MathAbs(enD - sl) > InpMaxRiskUsd) { g_skipRisk++; DSkip(side, StringFormat("stop too far ($%.2f > $%.2f)", MathAbs(enD - sl), InpMaxRiskUsd)); return; }""")
rep("""      double l9 = Ema(9, 0), l50 = Ema(50, 0);
      bool b9 = side > 0 ? l9 > en : l9 < en, b50 = side > 0 ? l50 > en : l50 < en;
      nxE = b9 && b50 ? (MathAbs(l9 - en) <= MathAbs(l50 - en) ? 9 : 50) : b9 ? 9 : b50 ? 50 : -1;""",
    """      double l9 = EmaAt(9, bidD), l50 = EmaAt(50, bidD);
      bool b9 = side > 0 ? l9 > enD : l9 < enD, b50 = side > 0 ? l50 > enD : l50 < enD;
      nxE = b9 && b50 ? (MathAbs(l9 - enD) <= MathAbs(l50 - enD) ? 9 : 50) : b9 ? 9 : b50 ? 50 : -1;""")
# a BUY banks its EMA only while that EMA is above the entry (the indicator's threshold)
rep("""            if (g_pos[i].side > 0 ? bid >= e : ask0 <= e) {""",
    """            if (g_pos[i].side > 0 ? bid >= e && (!InpLongEmaAbove || e > g_pos[i].enC) : ask0 <= e) {""")

# --- 4. the bridge (from Saad_strategy_1min v1.39) + the chart's ADX
BRIDGE = r'''// ---- TEST tvbars: the TradingView chart's own candles (bridge code from Saad_strategy_1min v1.39) ----
datetime tvT[]; double tvO[], tvH[], tvL[], tvC[], tvEF[], tvES[], tvA[], tvX[];
bool     g_useTv = false;          // this candle has chart candles behind it (else MT5's own candles)
bool     g_tvStale = false;        // no new chart candle: the chart takes no step either
int      g_tvN = 0, g_tvEnd = -1;  // g_tvEnd = index of the last CLOSED chart candle (shift 1)
uint     g_tvReadMs = 0;
double   g_open0 = 0;              // the bid at the chart candle's first tick = its open
int      g_late = 0;               // 1 while entering at this open on the chart's break of the PREVIOUS candle (InpTvVerdict)
double   g_lateBid = 0;            // ...the price the chart entered at (bid)
int      g_vLate = 0, g_vNoBrk = 0, g_vStop = 0, g_vTp = 0, g_gChart = 0;
string TvFile() { if (InpTvFile != "auto") return InpTvFile; int m = PeriodSeconds() / 60; return m == 1 ? "tv_bars_XAUUSD.csv" : StringFormat("tv_bars_XAUUSD_M%d.csv", m); }
bool TvLoad()
{
   g_tvReadMs = GetTickCount();
   int fh = FileOpen(TvFile(), FILE_READ | FILE_CSV | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE, ',');
   if (fh == INVALID_HANDLE) return false;
   int n = 0, cap = MathMax(ArraySize(tvT), 1024);
   ArrayResize(tvT, cap); ArrayResize(tvO, cap); ArrayResize(tvH, cap); ArrayResize(tvL, cap); ArrayResize(tvC, cap);
   while (!FileIsEnding(fh)) {
      string ts = FileReadString(fh);
      if (FileIsLineEnding(fh) || FileIsEnding(fh)) continue;
      double o = FileReadNumber(fh), h = FileReadNumber(fh), l = FileReadNumber(fh), c = FileReadNumber(fh);
      while (!FileIsLineEnding(fh) && !FileIsEnding(fh)) FileReadString(fh);
      datetime bt = StringToTime(ts);
      if (bt <= 0 || o <= 0 || h <= 0 || l <= 0 || c <= 0 || (n > 0 && bt <= tvT[n - 1])) continue;   // a half-written or repeated line
      if (n >= cap) { cap *= 2; ArrayResize(tvT, cap); ArrayResize(tvO, cap); ArrayResize(tvH, cap); ArrayResize(tvL, cap); ArrayResize(tvC, cap); }
      tvT[n] = bt; tvO[n] = o; tvH[n] = h; tvL[n] = l; tvC[n] = c; n++;
   }
   FileClose(fh);
   g_tvN = n;
   int m = MathMax(n, 1);
   ArrayResize(tvEF, m); ArrayResize(tvES, m); ArrayResize(tvA, m); ArrayResize(tvX, m);
   double af = 2.0 / (InpEmaFast + 1), as = 2.0 / (InpEmaSlow + 1), ak = 2.0 / (InpAdxPeriod + 1), trs = 0, pdi = 0, ndi = 0, adx = 0;
   double tr[]; ArrayResize(tr, m);
   for (int i = 0; i < n; i++) {
      tvEF[i] = i == 0 ? tvC[0] : tvEF[i - 1] + af * (tvC[i] - tvEF[i - 1]);              // ta.ema: seeded with the first close
      tvES[i] = i == 0 ? tvC[0] : tvES[i - 1] + as * (tvC[i] - tvES[i - 1]);
      tr[i] = i == 0 ? tvH[0] - tvL[0] : MathMax(tvH[i], tvC[i - 1]) - MathMin(tvL[i], tvC[i - 1]);   // ta.tr(true)
      trs += tr[i]; if (i >= 14) trs -= tr[i - 14];
      tvA[i] = trs / MathMin(i + 1, 14);                                                     // ta.sma(tr, 14) = MT5 iATR
      // the indicator's mtAdx() = MT5's iADX on the chart's candles: +DM / -DM as a share of the true range, EMA-smoothed, DX EMA-smoothed
      double pdm = 0, ndm = 0;
      if (i > 0) {
         pdm = MathMax(tvH[i] - tvH[i - 1], 0); ndm = MathMax(tvL[i - 1] - tvL[i], 0);
         if (pdm > ndm) ndm = 0; else if (ndm > pdm) pdm = 0; else { pdm = 0; ndm = 0; }
      }
      double pd = tr[i] != 0 ? 100 * pdm / tr[i] : 0, nd = tr[i] != 0 ? 100 * ndm / tr[i] : 0;
      pdi = i == 0 ? pd : pdi + ak * (pd - pdi);
      ndi = i == 0 ? nd : ndi + ak * (nd - ndi);
      double s = pdi + ndi, dx = s != 0 ? 100 * MathAbs(pdi - ndi) / s : 0;
      adx = i == 0 ? dx : adx + ak * (dx - adx);
      tvX[i] = adx;
   }
   return n > 0;
}
// TradingView starts a week's first 15-min candles at the session open (Monday 01:01, 01:16 ...) while MT5's run 01:00, 01:15 ...:
// the EA's "current candle" opens when the CHART's candle closes. No chart candle for too long (bridge stopped) -> MT5's clock.
datetime CurBar()
{
   datetime mt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (InpBarSource != 1 || g_tvN == 0 || PeriodSeconds() <= 60) return mt;
   int P = PeriodSeconds(), warm = MathMin(InpEmaSlow * 2 + 19, g_tvN - 1);
   datetime now = TimeCurrent();
   if (!MQLInfoInteger(MQL_TESTER) && now >= tvT[g_tvN - 1] + 2 * P && GetTickCount() - g_tvReadMs >= 1000) TvLoad();   // live: the next candle is due
   int lo = 0, hi = g_tvN - 1, r = -1;
   while (lo <= hi) { int k = (lo + hi) / 2; if (tvT[k] + P <= now) { r = k; lo = k + 1; } else hi = k - 1; }
   if (r < warm) return mt;
   datetime tb = tvT[r] + P;
   if (MQLInfoInteger(MQL_TESTER) ? now > tvT[g_tvN - 1] + 2 * P : now - tb > P + InpTvWaitSec && mt > tb) return mt;
   return tb;
}
// the last chart candle that closed before the candle opening at `bar`
void TvSync(datetime bar)
{
   int lo = 0, hi = g_tvN - 1, r = -1;
   while (lo <= hi) { int k = (lo + hi) / 2; if (tvT[k] <= bar - PeriodSeconds()) { r = k; lo = k + 1; } else hi = k - 1; }
   g_tvEnd = r;
}
// live: the chart's candle that just closed has arrived (or we waited long enough)
bool TvReady(datetime bar)
{
   if (InpBarSource != 1) { g_useTv = false; return true; }
   if (g_tvN == 0 || tvT[g_tvN - 1] < bar - PeriodSeconds()) {
      if (!MQLInfoInteger(MQL_TESTER) && GetTickCount() - g_tvReadMs >= 1000) TvLoad();
   }
   static int lastEnd = -2;
   TvSync(bar);
   // before the chart's first candles (+ warm-up), or after the file ends in the tester, the EA uses MT5's own candles
   int warm = MathMin(InpEmaSlow * 2 + 19, g_tvN - 1);
   g_useTv = g_tvN > 0 && warm >= 0 && bar - PeriodSeconds() >= tvT[warm] && (!MQLInfoInteger(MQL_TESTER) || bar - PeriodSeconds() <= tvT[g_tvN - 1]);
   if (!g_useTv) { g_tvStale = false; lastEnd = g_tvEnd; return true; }
   g_tvStale = g_tvEnd < 0 || g_tvEnd == lastEnd;
   if (g_tvEnd >= 0 && tvT[g_tvEnd] >= bar - PeriodSeconds()) { lastEnd = g_tvEnd; return true; }
   if (MQLInfoInteger(MQL_TESTER)) { lastEnd = g_tvEnd; return true; }   // the file is complete; a missing chart candle stays missing
   if (TimeCurrent() - bar < InpTvWaitSec) return false;
   lastEnd = g_tvEnd;
   if (!g_tvStale) return true;
   static datetime warned = 0;
   if (warned != bar) { warned = bar; PrintFormat("[SAAD-15min-tv] WARNING: no TradingView candle for %s after %d s - is tv_bars_bridge.py running? Setups paused until it is back (last %s)",
                                                  TimeToString(bar - PeriodSeconds()), InpTvWaitSec, g_tvEnd >= 0 ? TimeToString(tvT[g_tvEnd]) : "none"); }
   return true;
}
int    TvI(int s) { int i = g_tvEnd - s + 1; return i >= 0 && i <= g_tvEnd ? i : -1; }
double BOpen(int s)  { if (s <= 0) return g_useTv && g_open0 > 0 ? g_open0 : iOpen(_Symbol, PERIOD_CURRENT, 0); if (!g_useTv) return iOpen(_Symbol, PERIOD_CURRENT, s); int i = TvI(s); return i < 0 ? 0 : tvO[i]; }
double BHigh(int s)  { if (!g_useTv || s <= 0) return iHigh(_Symbol, PERIOD_CURRENT, s);  int i = TvI(s); return i < 0 ? 0 : tvH[i]; }
double BLow(int s)   { if (!g_useTv || s <= 0) return iLow(_Symbol, PERIOD_CURRENT, s);   int i = TvI(s); return i < 0 ? 0 : tvL[i]; }
double BClose(int s) { if (!g_useTv || s <= 0) return iClose(_Symbol, PERIOD_CURRENT, s); int i = TvI(s); return i < 0 ? 0 : tvC[i]; }
datetime BTime(int s){ if (s == 0) return CurBar(); if (!g_useTv || s < 0) return iTime(_Symbol, PERIOD_CURRENT, s);  int i = TvI(s); return i < 0 ? 0 : tvT[i]; }
double Atr(int s)    { if (!g_useTv) return Buf(hAtr, s); int i = TvI(MathMax(s, 1)); return i < 0 ? 0 : tvA[i]; }
double Adx(int s)    { if (!g_useTv) return hAdx == INVALID_HANDLE ? 0 : Buf(hAdx, s); int i = TvI(MathMax(s, 1)); return i < 0 ? 0 : tvX[i]; }
double EmaX(int fast, int s)
{
   if (!g_useTv) return Buf(fast ? hFast : hSlow, s);
   int i = TvI(s > 0 ? s : 1 + g_late); if (i < 0) return 0;
   double e = fast ? tvEF[i] : tvES[i];
   if (s > 0) return e;
   double a = 2.0 / ((fast ? InpEmaFast : InpEmaSlow) + 1);              // the forming candle: the chart's emaLive, at the bid
   return e + a * ((g_late > 0 ? g_lateBid : SymbolInfoDouble(_Symbol, SYMBOL_BID)) - e);
}
double Ema(int which, int s) { return EmaX(which == 9 ? 1 : 0, s); }
// the chart's live EMA of the forming candle at price px (its emaLive(n, bid))
double EmaAt(int which, double px)
{
   if (!g_useTv) return Ema(which, 0);
   int i = TvI(1 + g_late); if (i < 0) return 0;
   bool fast = which == 9;
   double e = fast ? tvEF[i] : tvES[i], a = 2.0 / ((fast ? InpEmaFast : InpEmaSlow) + 1);
   return e + a * (px - e);
}
bool BlindNow() { return InpBlindEntryBar && g_useTv && CurBar() < InpTvStepFrom; }   // diagnostic: the chart has no 1-minute data here
double ChartSpr() { return InpChartSpread > 0 ? InpChartSpread : SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID); }
// the chart's candle that just closed reached a "next EMA" target (the indicator's thresholds: LONG bid >= the live EMA, SELL ask <= it)
bool ChartTouched(int sd, int nxE, double en)
{
   double a = 2.0 / ((nxE == 9 ? InpEmaFast : InpEmaSlow) + 1), ep = Ema(nxE, 2);
   if (ep <= 0) return false;
   if (sd > 0) return BHigh(1) >= (InpLongEmaAbove ? MathMax(ep, ep + (en - ep) / a + 0.001) : ep);
   return BLow(1) <= ep - ChartSpr() / (1 - a);
}'''
rep("double Ema(int which, int s) { return Buf(which == 9 ? hFast : hSlow, s); }", BRIDGE)

# --- 5. OnInit / OnDeinit
rep("   if (hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE || hAtr == INVALID_HANDLE) return INIT_FAILED;",
    """   if (hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE || hAtr == INVALID_HANDLE) return INIT_FAILED;
   if (InpBarSource == 1) {
      if (!TvLoad()) PrintFormat("[SAAD-15min-tv] WARNING: no chart candles in Common\\\\Files\\\\%s - trading on MT5's own candles until they appear", TvFile());
      else PrintFormat("[SAAD-15min-tv] chart candles: %d, %s -> %s (server time)", g_tvN, TimeToString(tvT[0]), TimeToString(tvT[g_tvN - 1]));
   }""")
rep('PrintFormat("[SAAD-15min] v1.27 %s |', 'PrintFormat("[SAAD-15min] tvbars (v1.27 on the chart\'s candles) %s |')
rep('   PrintFormat("[SAAD] chart-test: stand-aside ghosts %d, unticked-box skips %d", g_ghosts, g_bandSkips);',
    '''   PrintFormat("[SAAD] chart-test: stand-aside ghosts %d, unticked-box skips %d", g_ghosts, g_bandSkips);
   PrintFormat("[SAAD] tvbars: the chart's candle decided - late entries %d, no break on the chart %d, stops %d, targets %d, ghosts ended %d", g_vLate, g_vNoBrk, g_vStop, g_vTp, g_gChart);''')

# --- 6. entry: late entries, break level, the gates on the chart's candles
rep("   bool hit = side > 0 ? (InpTrigBid ? bid : ask) > g_pHigh + InpBreakPips * pip : bid < g_pLow - InpBreakPips * pip;",
    "   bool hit = g_late > 0 || (side > 0 ? (InpTrigBid ? bid : ask) > g_pHigh + InpBreakPips * pip : bid < g_pLow - InpBreakPips * pip);")
rep("""   if (InpMaxSpreadPts > 0 && (ask - bid) / _Point > InpMaxSpreadPts) return;    // wait for a normal spread
   g_pSide = 0;""", """   if (InpMaxSpreadPts > 0 && (ask - bid) / _Point > InpMaxSpreadPts) return;    // wait for a normal spread
   g_pSide = 0;
   g_brk = g_late > 0 ? 0 : (side > 0 ? g_pHigh + InpBreakPips * pip : g_pLow - InpBreakPips * pip);   // TEST tvbars""")
rep("for (int k = 1; k <= look; k++) { hi = MathMax(hi, BHigh(k)); lo = MathMin(lo, BLow(k)); }",
    "for (int k = 1; k <= look; k++) { hi = MathMax(hi, BHigh(k + g_late)); lo = MathMin(lo, BLow(k + g_late)); }")
rep("o0 = BOpen(0);", "o0 = BOpen(g_late);")
rep("if (InpSlMode == 1) { double a = Atr(1) * InpSlAtrMult;", "if (InpSlMode == 1) { double a = Atr(1 + g_late) * InpSlAtrMult;")
rep('''   if (hAdx != INVALID_HANDLE && Buf(hAdx, 1) < InpAdxMin) { g_skipAdx++; DSkip(side, StringFormat("ADX %.1f below %.1f (ranging)", Buf(hAdx, 1), InpAdxMin)); return; }
   if ((InpAtrMinUsd > 0 && Atr(1) < InpAtrMinUsd) || (InpAtrMaxUsd > 0 && Atr(1) > InpAtrMaxUsd)) { g_skipVol++; DSkip(side, StringFormat("ATR $%.2f outside the band", Atr(1))); return; }''',
    '''   if (InpAdxMin > 0 && Adx(1 + g_late) < InpAdxMin) { g_skipAdx++; DSkip(side, StringFormat("ADX %.1f below %.1f (ranging)", Adx(1 + g_late), InpAdxMin)); return; }
   if ((InpAtrMinUsd > 0 && Atr(1 + g_late) < InpAtrMinUsd) || (InpAtrMaxUsd > 0 && Atr(1 + g_late) > InpAtrMaxUsd)) { g_skipVol++; DSkip(side, StringFormat("ATR $%.2f outside the band", Atr(1 + g_late))); return; }''')

# --- 7. the chart's verdict + the ghost on the chart's candles
i0 = t.index("// chart-test: the ghost's exit, tick by tick")
i1 = t.index("void OnTick()")
t = t[:i0] + r'''// TEST tvbars: when the two feeds disagree by cents, the CHART's candle that just closed decides (out at this open)
bool g_freed = false;   // the chart's trade / ghost ended INSIDE the candle that just closed: the chart was free at its close
void TvVerdict()
{
   datetime t1 = BTime(1);
   if (t1 <= 0) return;
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (!PositionSelectByTicket(g_pos[i].ticket) || g_pos[i].pendClose) continue;
      int sd = g_pos[i].side; double sl = PositionGetDouble(POSITION_SL);
      // entered in that candle on an MT5 break the chart's candle never made: the chart has no trade
      if (g_pos[i].brk != 0 && g_pos[i].bar == t1 && !(sd > 0 ? BHigh(1) > g_pos[i].brk : BLow(1) < g_pos[i].brk)) {
         g_pos[i].why = "the chart's candle never broke the level";
         g_freed = true;
         if (trade.PositionClose(g_pos[i].ticket)) g_vNoBrk++; else g_pos[i].pendClose = true;
         continue;
      }
      if (g_pos[i].bar >= t1) continue;              // the chart judges a trade from the candle after its entry candle
      if (sl > 0 && (sd > 0 ? BLow(1) <= sl : BHigh(1) + ChartSpr() >= sl)) {
         g_pos[i].why = StringFormat("stop %.2f hit on the chart's candle", sl);
         g_freed = true;
         if (trade.PositionClose(g_pos[i].ticket)) g_vStop++; else g_pos[i].pendClose = true;
         continue;
      }
      if (g_pos[i].nxE > 0 && ChartTouched(sd, g_pos[i].nxE, g_pos[i].enC)) {
         g_pos[i].why = StringFormat("%d EMA touched on the chart's candle", g_pos[i].nxE == 9 ? InpEmaFast : InpEmaSlow);
         g_freed = true;
         if (trade.PositionClose(g_pos[i].ticket)) g_vTp++; else g_pos[i].pendClose = true;
      }
   }
}

// chart-test: the ghost's exit, tick by tick (the indicator runs it through the same engine as a real trade)
void GhostTick()
{
   if (g_gSide == 0) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   int s = g_gSide;
   bool end = false;
   // TEST tvbars: after its entry candle the CHART's candles judge the ghost (GhostBar); inside it MT5's ticks do, where the chart has 1-minute data
   if (!(g_useTv && InpTvVerdict) || (CurBar() == g_gBar && g_gBar >= InpTvStepFrom)) {
      end = s > 0 ? bid <= g_gSl : ask >= g_gSl;
      if (!end && g_gNxE > 0) { double e = Ema(g_gNxE, 0); end = s > 0 ? bid >= e && (!InpLongEmaAbove || e > g_gEntry) : ask <= e; }
      if (!end && g_gNxE == 0) {                    // the v1.23 exits, simplified: TP1 reached ends it
         if (s > 0 && !g_gNoTp) { double tg = Ema(g_gExitE, 0) - InpLongTpPips * Pip(); end = tg > g_gEntry && bid >= tg; }
         if (s < 0 && g_gTp > 0) end = bid <= g_gTp;
      }
   }
   if (!end && InpCloseLossMins > 0 && MinsToClose() <= InpCloseLossMins) end = s > 0 ? bid < g_gEntry : ask > g_gEntry;
   if (end) g_gSide = 0;
}

void GhostBar()
{
   if (g_gSide == 0) return;
   datetime t1 = BTime(1);
   if (g_useTv && InpTvVerdict) {
      if (g_gBrk != 0 && g_gBar == t1 && !(g_gSide > 0 ? BHigh(1) > g_gBrk : BLow(1) < g_gBrk)) { g_gSide = 0; g_vNoBrk++; g_freed = true; return; }
      if (g_gBar < t1) {
         bool hit = g_gSide > 0 ? BLow(1) <= g_gSl : BHigh(1) + ChartSpr() >= g_gSl;
         if (!hit && g_gNxE > 0) hit = ChartTouched(g_gSide, g_gNxE, g_gEntry);
         if (hit) { g_gSide = 0; g_gChart++; g_freed = true; return; }
      }
   }
   if (g_gBar >= t1) return;     // like the indicator: not on the entry candle's own close
   int ce = g_gNxE == -1 ? 9 : g_gNxE == -2 ? 50 : 0;
   double c1 = BClose(1);
   if (ce > 0 && (g_gSide > 0 ? c1 < Ema(ce, 1) : c1 > Ema(ce, 1))) g_gSide = 0;
}

''' + t[i1:]

# --- 8. OnTick on the chart's clock
rep('''   ManageTick();
   GhostTick();
   SyncPos();
   datetime bar = BTime(0);
   if (bar != g_lastBar) {
      g_lastBar = bar;
      if (Bars(_Symbol, PERIOD_CURRENT) >= InpEmaSlow * 2 + 20) {
         ManageBar();
         GhostBar();
         SyncPos();''', '''   bool busyStart = ArraySize(g_pos) > 0 || g_gSide != 0;     // TEST tvbars: still open when the last candle closed (before this tick's exits)
   ManageTick();
   GhostTick();
   SyncPos();
   datetime bar = CurBar();
   if (bar != g_lastBar && TvReady(bar)) {
      g_lastBar = bar;
      g_open0 = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      g_freed = false;
      if (InpTvVerdict && g_useTv) { TvVerdict(); SyncPos(); }
      if (Bars(_Symbol, PERIOD_CURRENT) >= InpEmaSlow * 2 + 20 && !g_tvStale && (!g_useTv || g_tvEnd >= InpEmaSlow * 2 + 19)) {
         ManageBar();
         GhostBar();
         SyncPos();
         g_busyAtClose = busyStart && !(g_freed && ArraySize(g_pos) == 0 && g_gSide == 0);''')
rep('''         if (g_pSide != 0) {
            if (InpGapCancel && BTime(0) - BTime(1) > PeriodSeconds() * 3 / 2) { g_skipGap++; DSkip(g_pSide, "market closed in between"); g_pSide = 0; }
            else if (--g_pLeft <= 0)''', '''         if (g_pSide != 0) {
            // TEST tvbars: the chart's candle broke the level and MT5's ticks did not -> the chart entered in that candle: enter at this open
            if (InpTvVerdict && g_useTv && InpEntryMode == 0 && ArraySize(g_pos) == 0 && g_gSide == 0 && BTime(1) > g_pTime &&
                (g_pSide > 0 ? BHigh(1) > g_pHigh + InpBreakPips * Pip() : BLow(1) < g_pLow - InpBreakPips * Pip())) {
               double lvl = g_pSide > 0 ? g_pHigh + InpBreakPips * Pip() : g_pLow - InpBreakPips * Pip();
               g_lateBid = g_pSide > 0 ? MathMax(lvl + 0.01, BOpen(1)) : MathMin(lvl - 0.01, BOpen(1));
               Log(StringFormat("the chart's candle broke the %s (MT5's ticks did not) - entering at this open", g_pSide > 0 ? "high" : "low"));
               g_vLate++; g_late = 1; TryEntry(); g_late = 0;
               if (g_pSide != 0 && --g_pLeft <= 0) g_pSide = 0;
            }
            else if (InpGapCancel && BTime(0) - BTime(1) > PeriodSeconds() * 3 / 2) { g_skipGap++; DSkip(g_pSide, "market closed in between"); g_pSide = 0; }
            else if (--g_pLeft <= 0)''')
rep('''   CheckCooldown();
   if (TimeCurrent() < g_coolUntil) return;''', '''   if (InpNoEntryExitBar && g_busyAtClose) { g_busy++; return; }     // TEST tvbars: the chart was still in a trade at this candle's close
   CheckCooldown();
   if (TimeCurrent() < g_coolUntil) return;''')

dst.write_text(t, encoding="utf-8")
print("written", dst, len(t.splitlines()), "lines")
