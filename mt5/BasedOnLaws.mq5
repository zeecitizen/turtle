//+------------------------------------------------------------------+
//|  BasedOnLaws.mq5 — LAWS.md, and nothing but LAWS.md              |
//|                                                                  |
//|  Zee, 2026-08-23: "build a variant of the EA, call it            |
//|  based_on_laws EA and test it, it should break no law stated in  |
//|  the LAWS.md."                                                   |
//|                                                                  |
//|  Every provision of his page is a HARD GATE here, in his order   |
//|  and his words. Nothing from ZeeUHV's own history is imported —  |
//|  no rank-6 auditions, no diamonds, no pulse, no hour dimmer, no  |
//|  Law 9/10c/12. If it is not in LAWS.md it is not in this EA.     |
//|                                                                  |
//|  BUY SIDE ONLY — his page says "Buy side trade setup", and       |
//|  "gold is mostly bullish". The sell mirror is present but off.   |
//|                                                                  |
//|  Magic 88184 · log tag [LAW] · tickets zlaw_*                    |
//+------------------------------------------------------------------+
#property copyright "Zeeshan's LAWS.md, mechanized"
#property version   "1.35"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input group "── size & identity ──"
input double InpLots          = 0.01;
input long   InpMagic         = 88184;
input int    InpMaxOpen       = 1;

input group "── LAW: the trend (camel humps) ──"
input bool   InpRequireTrend  = true;   // "we don't trade in a ranging market"
input int    InpTrendLook     = 90;    // NOT LOAD-BEARING under camel humps: 60, 90
                                        // and 120 give byte-identical results (the
                                        // same humps are found either way).
                                        // 2 hours — his 7:02 PM trade was defending
                                        // the 5:40 PM low, 82 bars back. A 20-40 bar
                                        // window cannot see the leg it is trading.
                                        // 90 reproduces all three of his marked
                                        // setups to the minute; 120 loses the first.     // 2026-08-23: was 20 — MY number, inherited from
                                        // ZeeUHV, never his. He reads camel humps across an
                                        // hour+; 20 bars declared RANGE inside a clean climb
                                        // and cost Friday 4 of its 5 setups. 40 finds all
                                        // five (3W/2L, +259.20); 60 is byte-identical — a
                                        // plateau, not a spike.
input int    InpPivot         = 2;
input int    InpTrendMode     = 2;      // 0 = old inferred structure · 1 = EMA-5 SLOPE
                                        // 2026-08-24: HIS OWN LAW WINS. Camel humps
                                        // drawn from pivots beat the EMA substitute
                                        // 61.1%/+1044.30 vs 52.2%/+876.20 over seven
                                        // days, and the page and the code now agree.
                                        // 2 = CAMEL HUMPS drawn from pivots (his line 7)
                                        // 2026-08-24, HIS idea, and it beat my
                                        // structure code on every axis at once:
                                        // 30 trades vs 24 · 40.0% vs 33.3% · +624.00
                                        // vs +296.60 over the same seven days.
input int    InpEmaSlopeBars  = 10;     // how many candles the EMA-5 slope spans.
                                        // dial so far: 1=+403 · 3=+323 · 5=+597 ·
                                        // 10=+624. 15/20/30 still running — this
                                        // default may move when the crest is found.
input bool   InpTrendSticky   = true;   // LAWS.md line 33: a confirmed uptrend STAYS
                                        // in force until its last low is broken. Off =
                                        // re-derive HH+HL every minute (the old
                                        // behaviour, which called 80% of the week a
                                        // range).
input bool   InpGuardSwing    = true;   // the confirmed higher low may only move when
                                        // a genuine SWING high (hump top) is taken
                                        // out — not every candle that ticks higher
input bool   InpTrendBeforeRetrace = true;  // read the humps BEFORE the pullback,
                                            // not through it (his 7:02 PM setup)
input bool   InpBuyOnly       = true;   // "Buy side trade setup" · "gold is mostly bullish"

input group "── LAW: the retracement ──"
input int    InpRetraceMax    = 20;     // how far back the pullback may reach
input int    InpMinRetraceBars = 2;     // a pullback must be at least this many candles,
                                        // and must be broken BEFORE the breakout bar
// 2026-08-23, Zee on trade #1: "4:57 PM is a green candle with a green candle before
// it.. a retracement begins when a red candle breaks below the last green's low. is
// that valid here?" It was not. His page says a pullback is "a sequence of red
// candles AFTER A SEQUENCE OF GREEN CANDLES (price moving up)" — and before 4:57 the
// tape was RED RED RED RED, green, red, doji. One lone green is not an up-move. I had
// never implemented that clause, so any single green whose low later broke qualified.
input int    InpUpRunBars     = 2;      // the origin must sit at the end of this many
                                        // with-trend candles (his "sequence of greens")
input double InpUpRunPts      = 0.0;    // and/or the run must cover this many points

input group "── LAW: the breakout ──"
input double InpMomBodyMult   = 0.0;    // RETIRED 2026-08-23. This was my second
                                        // shape test — body vs the last 20 bodies —
                                        // and his ruling covers it: "a candle that
                                        // closes well above your level is a momentum
                                        // candle, whatever its shape." Removing it is
                                        // worth +186 on Friday and +90..+175 over the
                                        // seven days, and it RECOVERS a winner.
input double InpMomBodyRatio  = 0.70;   // 1. |C-O| / (H-L) — the body must dominate
input double InpMomAtrMult    = 0.0;    // 2. body > this x ATR(14) — REFUSED by the
                                        // court: with expansion on, 23 trades become
                                        // 17 and THREE WINNERS die (+756.80 vs
                                        // +876.20). Too strict for M1. Dead input.
input double InpMomSmaMult    = 0.0;    // ... OR body > this x SMA(body,20) — same verdict
input double InpMomClosePos   = 0.20;   // 3. close inside this share of the extreme —
                                        // byte-identical with and without it once the
                                        // body ratio is enforced (a 0.70 body already
                                        // closes near its extreme). Kept: his clause,
                                        // costs nothing.
input double InpBreakHold     = 0.45;   // "(no big wick)" measured against HIS LEVEL:
                                        // the close must still hold this share of what
                                        // the candle took above the UHV's high. His
                                        // ruling: a candle that closes well above the
                                        // level IS a momentum candle, whatever its
                                        // shape; a wick in the breakout's direction is
                                        // rejection and weakens the break.
input double InpMaxWickFrac   = 0.00;   // the old shape test (wick vs the candle's own
                                        // range). MY number, never his — retired to a
                                        // dead input on 2026-08-23, kept so the earlier
                                        // receipts stay reproducible.
input bool   InpBodySpans     = true;   // his clause c: the breakout body must SHARE
                                        // BODY WITH the UHV's high — straddle it, not
                                        // open already above it
input bool   InpNeedEma5      = false;  // "an EXTRA confirmation" — his word, so optional

input group "── LAW: closing the trade ──"
input double InpStopBufPips   = 0.60;   // "5-7 pips below the lowest point" (0.1/pip)
input double InpTargetR       = 2.0;    // "risk-reward ratio of 1:2"
input double InpBreakEvenR    = 1.0;    // "after reaching 1:1 we make a BreakEven"
input double InpMinRiskPts    = 0.50;
input double InpMaxRiskPts    = 10.0;

input group "── LAW: when to stop trading ──"
input bool   InpStopOnLastLow = true;   // "we stop buying when the last low is broken"

input group "── LAW: session & higher timeframes ──"
input bool   InpNyOnly        = false;  // "we only trade in the NewYork session"
                                        // 2026-08-24, HIS CALL: "let's go all hours,
                                        // since the goal is to make maximum money".
                                        // The court, camel humps, seven days:
                                        //   NY only   18 tr 61.1% +1044.30  ($58/trade)
                                        //   ALL HOURS 39 tr 43.6% +1335.90  ($34/trade)
                                        //   pre-NY    18 tr 33.3%  +388.20  ($22/trade)
                                        // Outside NY the edge is ~break-even, not a
                                        // bleed — his session law protected QUALITY,
                                        // not money. All hours earns +$292 more in
                                        // total by taking 21 more trades at 17 fewer
                                        // win-rate points. NOTE: this now DIVERGES from
                                        // LAWS.md line 47 by his decision, not by
                                        // oversight.
input int    InpNyFromHour    = 15;     // broker 15:00 = 17:00 PKT
input int    InpNyToHour      = 22;
input bool   InpNeedM5M15     = false;  // REMOVED from LAWS.md 2026-08-23 — it was a
                                        // preference, never a law, and as a hard gate it
                                        // cost Friday its ONLY trade (a winner) and cut
                                        // July from 27 setups to 5. Kept as a dead input.

input group "── LAW: the volume source ──"
input int    InpOandaVolume   = 1;      // "we read volume from tradingview's OANDA volume chart"
input int    InpOandaBars     = 1;      // and the CANDLES too — he reads OANDA, so the
                                        // structure must be judged there. Orders still
                                        // fill at Blueberry's price.
input int    InpFreshMaxSec   = 40;     // LIVE ONLY: how long to wait for the bridge
                                        // to publish the just-closed candle before
                                        // giving up on it. Judging a half-written
                                        // candle cost the first live trade -8.86.
input bool   InpOandaStrict   = true;   // a MISSING OANDA minute is a minute we cannot
                                        // read: refuse the bar instead of silently
                                        // falling back to the broker's candle and
                                        // judging half the setup on the wrong chart.
input bool   InpVerbose       = false;
// per-bar narration for a chosen window (server HHMM), so a missed setup can be
// interrogated minute by minute. Zee 2026-08-23 gave exact times: his breakouts at
// 7:02 / 7:56 / 9:10 PM PKT = server 1702 / 1756 / 1910.
input int    InpDbgFrom       = 0;
input int    InpDbgTo         = 0;

datetime g_last_bar = 0;
bool     g_oanda_loaded = false;   // tester: read his chart once, then freeze it
uint     g_last_reload  = 0;       // live: throttle the re-read while waiting for a bar
// CENSUS (tester only) — Zee hand-drew 4 setups on Friday and the EA took 1.
// Every gate counts its own refusals so the narrow one names itself.
int c_bars=0, c_session=0, c_notrend=0, c_notbuy=0, c_lastlow=0, c_noretr=0,
    c_nouhv=0, c_brk_colour=0, c_brk_close=0, c_brk_vol=0, c_brk_mom=0,
    c_brk_wick=0, c_brk_ema=0, c_risk=0, c_fired=0, c_nooanda=0, c_brk_span=0, c_stale=0;
double   g_last_low = 0;                // the confirmed higher low we are defending

//──────────────────── OANDA volume (his stated source) ────────────────────
datetime g_ov_t[]; long g_ov_v[]; int g_ov_n = 0;

void LoadOandaVol() {
   g_ov_n = 0;
   int h = INVALID_HANDLE;
   for (int t = 0; t < 5 && h == INVALID_HANDLE; t++) {
      h = FileOpen("oanda_vol.csv", FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
      if (h == INVALID_HANDLE && !MQLInfoInteger(MQL_TESTER)) Sleep(40);
   }
   if (h == INVALID_HANDLE) { Print("[LAW] oanda_vol.csv missing — broker volume used"); return; }
   ArrayResize(g_ov_t, 8192); ArrayResize(g_ov_v, 8192);
   while (!FileIsEnding(h)) {
      string ln = FileReadString(h);
      int c = StringFind(ln, ",");
      if (c <= 0) continue;
      datetime t = StringToTime(StringSubstr(ln, 0, c));
      if (t <= 0) continue;
      if (g_ov_n >= ArraySize(g_ov_t)) {
         ArrayResize(g_ov_t, g_ov_n + 4096); ArrayResize(g_ov_v, g_ov_n + 4096);
      }
      g_ov_t[g_ov_n] = t;
      g_ov_v[g_ov_n] = (long)StringToInteger(StringSubstr(ln, c + 1));
      g_ov_n++;
   }
   FileClose(h);
}

long OandaVolAt(datetime t) {
   int lo = 0, hi = g_ov_n - 1;
   while (lo <= hi) {
      int m = (lo + hi) / 2;
      if (g_ov_t[m] == t) return g_ov_v[m];
      if (g_ov_t[m] < t) lo = m + 1; else hi = m - 1;
   }
   return -1;
}

// ── HIS CHART, NOT THE BROKER'S (2026-08-23) ───────────────────────────────
// Zee questioned trade #1: "can you check if a retracement begun here?" In OANDA
// data the 4:59 green's low was NOT broken before the breakout — in Blueberry's it
// was, by 3 cents. Every structural comparison in this EA was being made on the
// broker's candles while he reads OANDA, and the feeds differ by up to 0.85. His
// page says the volume comes from TradingView; the CANDLES must come from there too,
// or the machine is judging a different chart. Fills and orders stay with Blueberry.
datetime g_ob_t[];
double   g_ob_o[], g_ob_h[], g_ob_l[], g_ob_c[];
long     g_ob_v[];        // the volume that came in the SAME row as the candle
int      g_ob_n = 0;

void LoadOandaBars() {
   g_ob_n = 0;
   int h = INVALID_HANDLE;
   for (int t = 0; t < 5 && h == INVALID_HANDLE; t++) {
      h = FileOpen("oanda_bars.csv", FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
      if (h == INVALID_HANDLE && !MQLInfoInteger(MQL_TESTER)) Sleep(40);
   }
   if (h == INVALID_HANDLE) { Print("[LAW] oanda_bars.csv missing — broker candles used"); return; }
   ArrayResize(g_ob_t, 8192); ArrayResize(g_ob_o, 8192);
   ArrayResize(g_ob_h, 8192); ArrayResize(g_ob_l, 8192); ArrayResize(g_ob_c, 8192);
   ArrayResize(g_ob_v, 8192);
   while (!FileIsEnding(h)) {
      string ln = FileReadString(h);
      string f[];
      if (StringSplit(ln, ',', f) < 6) continue;
      datetime t = StringToTime(f[0]);
      if (t <= 0) continue;
      if (g_ob_n >= ArraySize(g_ob_t)) {
         ArrayResize(g_ob_v, g_ob_n + 4096);
         int nn = g_ob_n + 4096;
         ArrayResize(g_ob_t, nn); ArrayResize(g_ob_o, nn);
         ArrayResize(g_ob_h, nn); ArrayResize(g_ob_l, nn); ArrayResize(g_ob_c, nn);
      }
      g_ob_t[g_ob_n] = t;
      g_ob_o[g_ob_n] = StringToDouble(f[1]);
      g_ob_h[g_ob_n] = StringToDouble(f[2]);
      g_ob_l[g_ob_n] = StringToDouble(f[3]);
      g_ob_c[g_ob_n] = StringToDouble(f[4]);
      g_ob_v[g_ob_n] = (long)StringToInteger(f[5]);
      g_ob_n++;
   }
   FileClose(h);
}

int ObIdx(int k) {
   if (InpOandaBars != 1 || g_ob_n == 0) return -1;
   datetime t = iTime(_Symbol, PERIOD_CURRENT, k);
   int lo = 0, hi = g_ob_n - 1;
   while (lo <= hi) {
      int m = (lo + hi) / 2;
      if (g_ob_t[m] == t) return m;
      if (g_ob_t[m] < t) lo = m + 1; else hi = m - 1;
   }
   return -1;
}

double bOpen (int k) { int i = ObIdx(k); return (i >= 0) ? g_ob_o[i] : iOpen (_Symbol, PERIOD_CURRENT, k); }
double bHigh (int k) { int i = ObIdx(k); return (i >= 0) ? g_ob_h[i] : iHigh (_Symbol, PERIOD_CURRENT, k); }
double bLow  (int k) { int i = ObIdx(k); return (i >= 0) ? g_ob_l[i] : iLow  (_Symbol, PERIOD_CURRENT, k); }
double bClose(int k) { int i = ObIdx(k); return (i >= 0) ? g_ob_c[i] : iClose(_Symbol, PERIOD_CURRENT, k); }
double BodyHi(int k) { return MathMax(bOpen(k), bClose(k)); }
double BodyLo(int k) { return MathMin(bOpen(k), bClose(k)); }
bool   IsGreen(int k) { return bClose(k) > bOpen(k); }
bool   IsRed  (int k) { return bClose(k) < bOpen(k); }

long BarVolume(int k) {
   // ONE PULL, ONE TRUTH (2026-08-24). oanda_vol.csv and oanda_bars.csv are written by
   // TWO SEPARATE pulls at different instants, so the same minute can carry different
   // volumes in each — tonight's 18:03 breakout was 1396 in the volume table and 1505
   // in the candle table, and the immutability rule then froze each at its own first
   // sight. Zee reads ONE chart; the EA was reading one and a bit. When the candles
   // come from the OANDA table, the volume must come from the SAME ROW.
   if (InpOandaBars == 1) {
      int ib = ObIdx(k);
      if (ib >= 0 && g_ob_v[ib] > 0) return g_ob_v[ib];
   }
   if (InpOandaVolume == 1 && g_ov_n > 0) {
      long ov = OandaVolAt(iTime(_Symbol, PERIOD_CURRENT, k));
      if (ov > 0) return ov;
   }
   long rv = iRealVolume(_Symbol, PERIOD_CURRENT, k);
   if (rv > 0) return rv;
   return iVolume(_Symbol, PERIOD_CURRENT, k);
}

double Ema(int len, int shift) {
   double k = 2.0 / (len + 1.0), e = bClose(shift + 5 * len);
   for (int i = shift + 5 * len - 1; i >= shift; i--) e = bClose(i) * k + e * (1.0 - k);
   return e;
}

//──── LAW: "we call it an uptrend if we're breaking above previous highs
//──── and forming new higher lows" — and the last low we must defend.
// 2026-08-23 — Zee's setup 1 exposed the flaw: this test re-measured structure on
// the MOST RECENT bars, which during a pullback are the pullback's own. A healthy
// retracement therefore printed lower highs and lower lows, the gate flipped to
// DOWNTREND, and it refused the very setup the pullback had created — at 7:02 PM it
// read trend=-1 while he was buying. He reads the humps BEFORE the pullback and then
// trades it. So the scan may start AFTER the retracement, at bar `from`.
// ── THE STRUCTURE, BUILT FROM RETRACEMENTS — NOT PIVOTS (2026-08-23) ──────────
// Zee, and this is the law that unlocks everything:
//   "we consider a red candle a NOISE candle if its not breaking the previous
//    green's low. a sequence of red candles which don't break the last green's low
//    are still noise. we consider them part of an impulse wave. at 6:35 PM there's a
//    low. that low is not updated. the two intermediary lows at 6:39 and 6:45 are
//    NOISE because they dont break the previous green's low. therefore when the red
//    candle starts at 6:51 its the FIRST time a red has broken below the last
//    green's low, thus starting a retracement there. thus the new low forms at 6:54
//    which is HIGHER than the last confirmed low at 6:35."
// Every pivot-based version I wrote counted 6:39 and 6:45 as lows and 6:56 as a peak,
// and so kept reading a downtrend inside his uptrend. Confirmed lows exist ONLY where
// a real retracement begins; the peak between two retracements is the confirmed high.
int TrendNow(double &lastLow, int from = 1) {
   double lows[8], highs[8];
   int nl = 0, nh = 0;
   double lastGreenLow = 0, curMin = 0, curMax = 0;
   bool inRetr = false;
   // walk OLDEST -> NEWEST across the window
   for (int i = InpTrendLook; i >= 1 && nl < 8; i--) {
      double o = bOpen(i), c = bClose(i), h = bHigh(i), l = bLow(i);
      if (curMax == 0 || h > curMax) curMax = h;
      if (!inRetr) {
         // BODY, NOT WICK — the rule beneath all the others. Zee: "6:39 is RED, low
         // 4584.70 — this did NOT break the previous green's low with its body, it
         // only broke with a wick." Verified: body low 4587.39 vs 4587.35, four
         // cents short. A wick through a level is a SWEEP; only a body is a BREAK.
         if (c < o && lastGreenLow > 0 && MathMin(o, c) < lastGreenLow) {
            inRetr = true;                       // a REAL retracement starts here
            curMin = l;
            if (nh < 8) highs[nh++] = curMax;    // the peak before it is confirmed
         }
      } else {
         if (l < curMin) curMin = l;
         if (c > lastGreenLow) {                 // price recovered -> the low is set
            inRetr = false;
            if (nl < 8) lows[nl++] = curMin;
            curMax = h;
         }
      }
      if (c > o) lastGreenLow = l;               // remember the last GREEN's low
   }
   lastLow = 0;
   if (nl < 2 || nh < 2) return 0;               // not enough structure yet
   // his test: higher lows AND breaking above previous highs
   bool hl = lows[nl - 1] > lows[nl - 2];
   bool hh = highs[nh - 1] > highs[nh - 2];
   if (!(hl && hh)) return 0;
   double defend = lows[nl - 1];                 // the last confirmed low
   if (inRetr && curMin < defend) defend = curMin;
   if (bClose(1) < defend) return 0;             // "stop buying when the last low breaks"
   lastLow = defend;
   return +1;
}

//──── LAW: higher timeframes — "1 minute bullish, 5 minute also, 15 minute also"
bool HtfAgrees(int side) {
   if (!InpNeedM5M15) return true;
   ENUM_TIMEFRAMES tfs[2]; tfs[0] = PERIOD_M5; tfs[1] = PERIOD_M15;
   for (int t = 0; t < 2; t++) {
      double c1 = iClose(_Symbol, tfs[t], 1), c3 = iClose(_Symbol, tfs[t], 3);
      if (c1 <= 0 || c3 <= 0) return false;
      if (side > 0 && !(c1 > c3)) return false;
      if (side < 0 && !(c1 < c3)) return false;
   }
   return true;
}

//──── LAW: "a valid retracement starts when the last green candle's LOW is
//──── broken by the next or next few red candles downwards"
// 2026-08-23, his words: "the green at 6:50 when broken by a red below it forms a
// first retracement origin. the green at 6:55 when broken by reds below its low
// forms the SECOND retracement origin -> this is a VALID setup too... so BOTH are
// valid retracements." Nested pullbacks each own a retracement, each owns a UHV.
// So we collect every origin and audition them newest-first.
int RetraceOrigins(int side, int &out[]) {
   int n = 0;
   ArrayResize(out, 16);
   for (int k = 2; k <= InpRetraceMax && n < 16; k++) {
      bool withTrend = (side > 0) ? IsGreen(k) : IsRed(k);
      if (!withTrend) continue;
      // his precondition: the origin must END A RUN of with-trend candles
      if (InpUpRunBars > 1) {
         int run = 0;
         for (int u = k; u <= k + 6; u++) {
            bool w = (side > 0) ? IsGreen(u) : IsRed(u);
            if (w) run++; else if (u > k) break;
         }
         if (run < InpUpRunBars) continue;
      }
      // and, if asked, the run must actually have MOVED price
      if (InpUpRunPts > 0) {
         double from = (side > 0) ? bLow(k + InpUpRunBars - 1) : bHigh(k + InpUpRunBars - 1);
         double to   = (side > 0) ? bHigh(k) : bLow(k);
         if (MathAbs(to - from) < InpUpRunPts) continue;
      }
      // 2026-08-23, Zee caught trade #1: the EA called 4:59 PM a retracement whose
      // low was broken by the 5:01 candle — the SAME candle it then traded as the
      // breakout. A pullback must EXIST BEFORE the break, so the breaking bar may
      // not be bar 1, and the pullback needs at least InpMinRetraceBars candles.
      for (int j = k - 1; j >= 2; j--) {
         bool broke = (side > 0) ? (BodyLo(j) < bLow(k)) : (BodyHi(j) > bHigh(k));
         if (broke && (k - 1) >= InpMinRetraceBars) { out[n++] = k; break; }
      }
   }
   ArrayResize(out, n);
   return n;
}

//──── LAW: "we compare all red colored candle's volumes; the largest is the UHV"
int UhvIn(int from, int side) {
   int best = -1; long bv = -1;
   for (int k = from; k >= 1; k--) {
      bool counter = (side > 0) ? IsRed(k) : IsGreen(k);
      if (!counter) continue;
      long v = BarVolume(k);
      if (v > bv) { bv = v; best = k; }
   }
   return best;
}

//──── LAW: the breakout candle — closes past the UHV's high, quieter than it,
//──── a momentum candle with no big wick, (optionally) closing past EMA-5.
bool BreakoutOK(int uhv, int side) {
   if (uhv < 2) return false;
   bool up = (side > 0);
   if (up && !IsGreen(1)) { c_brk_colour++; return false; }
   if (!up && !IsRed(1))  { c_brk_colour++; return false; }
   double lvl = up ? bHigh(uhv) : bLow(uhv);
   if (up  && !(bClose(1) > lvl)) { c_brk_close++; return false; }
   if (!up && !(bClose(1) < lvl)) { c_brk_close++; return false; }
   // FIRST CROSSING ONLY (2026-08-23). Zee on trade #1: "the 6:15 PM candle does not
   // break out the 6:09 UHV." He was right — the 6:11 candle had ALREADY closed above
   // 4583.38, so by 6:15 the level was four minutes broken and the EA bought $4 above
   // it. A breakout is an EVENT, not a state: only the first body-close through the
   // level counts, everything after is a chase.
   for (int e = uhv - 1; e >= 2; e--) {
      bool earlier = up ? (BodyHi(e) > lvl) : (BodyLo(e) < lvl);
      if (earlier) { c_brk_close++; return false; }
   }
   // "the breakout candle must cross — SHARE BODY WITH — the UHV candle's high"
   // (his clause c, 2026-08-23). First-crossing makes this true in almost every case,
   // but only almost: a candle that OPENS already above the level has not crossed it,
   // it started on the far side. His words say the body must straddle the level, so
   // that is now checked literally rather than inferred.
   if (InpBodySpans) {
      bool spans = up ? (BodyLo(1) <= lvl && BodyHi(1) > lvl)
                      : (BodyHi(1) >= lvl && BodyLo(1) < lvl);
      if (!spans) { c_brk_span++; return false; }
   }
   if (BarVolume(1) >= BarVolume(uhv)) { c_brk_vol++; return false; }
   // momentum: a real body against the recent tape
   if (InpMomBodyMult > 0) {
      double avg = 0; int n = 0;
      for (int q = 2; q <= 21; q++) { avg += MathAbs(bClose(q) - bOpen(q)); n++; }
      if (n > 0) avg /= n;
      if (avg > 0 && MathAbs(bClose(1) - bOpen(1)) < avg * InpMomBodyMult)
         { c_brk_mom++; return false; }
   }
   // ── "A MOMENTUM CANDLE", QUANTIFIED (2026-08-24) ──────────────────────────
   // He supplied the VSA definition and ruled out its fourth clause himself: "we
   // dont require Above-Average Volume, on the contrary our method uses the three
   // only" — because his own page says the breakout must be QUIETER than the UHV.
   //   1. dominant body   |C-O| / (H-L) >= 0.70      (small wicks, minimal rejection)
   //   2. expansion       body > 1.2*ATR(14)  OR  body > 1.5*SMA(body,20)
   //   3. close at the extreme   buy: C > O AND C >= H - 0.20*(H-L)
   //
   // Measured against every breakout on record before shipping — the body ratio
   // alone splits them perfectly:
   //   winners 0.81 · 0.89 · 0.85   |   losers 0.62 · 0.65 · 0.47 · 0.19
   // and it refuses BOTH of the EA's first two live trades, which lost -8.86 and
   // -10.13 on candles that were never momentum candles at all.
   if (InpMomBodyRatio > 0 || InpMomAtrMult > 0 || InpMomSmaMult > 0 || InpMomClosePos > 0) {
      double mrng = bHigh(1) - bLow(1);
      double mbody = MathAbs(bClose(1) - bOpen(1));
      if (mrng <= 0) { c_brk_mom++; return false; }
      if (InpMomBodyRatio > 0 && mbody / mrng < InpMomBodyRatio) { c_brk_mom++; return false; }
      if (InpMomAtrMult > 0 || InpMomSmaMult > 0) {
         double atr = 0; int na = 0;
         for (int q = 2; q <= 15; q++) {
            double pc = bClose(q + 1), hh = bHigh(q), ll = bLow(q);
            atr += MathMax(hh - ll, MathMax(MathAbs(hh - pc), MathAbs(ll - pc))); na++;
         }
         if (na > 0) atr /= na;
         double sb = 0; int nb = 0;
         for (int q = 2; q <= 21; q++) { sb += MathAbs(bClose(q) - bOpen(q)); nb++; }
         if (nb > 0) sb /= nb;
         bool expand = (InpMomAtrMult > 0 && atr > 0 && mbody > InpMomAtrMult * atr)
                    || (InpMomSmaMult > 0 && sb  > 0 && mbody > InpMomSmaMult * sb);
         if (!expand) { c_brk_mom++; return false; }
      }
      if (InpMomClosePos > 0) {
         bool at_extreme = up
            ? (bClose(1) > bOpen(1) && bClose(1) >= bHigh(1) - InpMomClosePos * mrng)
            : (bClose(1) < bOpen(1) && bClose(1) <= bLow(1)  + InpMomClosePos * mrng);
         if (!at_extreme) { c_brk_mom++; return false; }
      }
   }

   // "a momentum candle (no big wick)" — MEASURED AGAINST HIS LEVEL (2026-08-23).
   // Zee on trade #5: "the 10:02 breakout candle has a wick on top making it not a
   // momentum candle.. its body does break the UHV high but with a very very small
   // margin." Then the ruling that settles what the clause means: "a candle that
   // closes well above your level is a momentum candle, whatever its shape.. the wick
   // represents price rejection. a wick in the direction of the breakout weakens the
   // strength of the breakout."
   //
   // So the wick is not judged against the candle's own height — that is a shape test
   // blind to what was broken, and it was MY invention (0.35), not his page. It is
   // judged against THE BREAK: of everything the candle took above his level, how much
   // was still held at the close. Friday, his five setups:
   //     7:02 held 100%  ·  9:10 held 82%  ·  8:10 held 68%   → the winners
   //     8:51 held  31%  ·  10:02 held 9.6%                   → the two losers
   if (InpBreakHold > 0) {
      double took = up ? (bHigh(1) - lvl) : (lvl - bLow(1));   // reach past his level
      double kept = up ? (bClose(1) - lvl) : (lvl - bClose(1));// what the close held
      if (took > 0 && kept / took < InpBreakHold) { c_brk_wick++; return false; }
   }
   // the old shape test, kept as a dead input so its receipts stay reproducible
   if (InpMaxWickFrac > 0) {
      double rng = bHigh(1) - bLow(1);
      if (rng > 0) {
         double wick = up ? (bHigh(1) - BodyHi(1)) : (BodyLo(1) - bLow(1));
         if (wick / rng > InpMaxWickFrac) { c_brk_wick++; return false; }
      }
   }
   if (InpNeedEma5) {
      double e = Ema(5, 1);
      if (up  && !(bClose(1) > e)) { c_brk_ema++; return false; }
      if (!up && !(bClose(1) < e)) { c_brk_ema++; return false; }
   }
   return true;
}

//──── LAW 33 — THE TREND PERSISTS UNTIL THE LAST LOW BREAKS (2026-08-23).
// His page: "we stop buying, when the last low is broken .. we keep trading until the
// last low is safe (unbroken below). Whenever a high is broken, the deepest point
// (the lowest point) is the confirmed higher low."
//
// TrendNow() re-derives the whole structure every minute and demands the LAST TWO
// lows and the LAST TWO highs both be rising. One shallow pullback therefore ENDS the
// uptrend and it must be re-earned from scratch. Measured on Friday 21 Aug — a day
// Zee calls an uptrend nearly throughout — that test refused 287 of 420 session
// minutes, flickering in and out while price climbed 4613 -> 4627. 68% of a trending
// day declared a range, and across seven days it was 80%.
//
// His law is a LATCH, not a re-examination: once the humps confirm an uptrend, it
// stands until its defended low is broken BY BODY. Every time a new high is taken,
// the deepest point since the previous high becomes the new confirmed higher low.
// the most recent CONFIRMED hump top: a high with InpPivot lower highs on each side.
// Same pivot logic that draws the camel humps, so "a high" means what he draws.
int SwingHighIdx() {
   int p = MathMax(1, InpPivot);
   for (int k = p + 1; k <= InpTrendLook; k++) {
      bool top = true;
      for (int q = 1; q <= p && top; q++)
         if (bHigh(k) <= bHigh(k - q) || bHigh(k) <= bHigh(k + q)) top = false;
      if (top) return k;
   }
   return -1;
}

// the mirror of SwingHighIdx — the last confirmed hump TROUGH. In EMA mode this is
// what "the last low" means for the stop-buying law, since no structure walk runs.
int SwingLowIdx() {
   int p = MathMax(1, InpPivot);
   for (int k = p + 1; k <= InpTrendLook; k++) {
      bool bot = true;
      for (int q = 1; q <= p && bot; q++)
         if (bLow(k) >= bLow(k - q) || bLow(k) >= bLow(k + q)) bot = false;
      if (bot) return k;
   }
   return -1;
}

// ── THE CAMEL HUMPS, DRAWN (2026-08-24, his line 7, rebuilt on his own words) ──
//
//   "we identify trend by drawing camel humps.. price goes upwards in a lightning
//    shape fashion. first there is price going up in a straight slant trend line (the
//    impulse wave), then there's a retracement. so we call it an uptrend if we're
//    breaking above previous highs. and forming new higher lows."
//
// The first attempt (TrendNow) inferred the humps from a retracement state machine and
// re-proved the whole trend every minute, demanding the last TWO lows and the last TWO
// highs both be rising. It called 80% of a clean uptrend a range, and the control arm
// showed it was worse than having no gate at all. This one DRAWS the humps instead:
// pivot highs and pivot lows (InpPivot bars lower on each side — the same rule that
// draws them on a chart), then his two tests on the drawn swings.
//
// And his line 45 lives here, where it belongs: "whenever a high is broken, the
// deepest point (the lowest point) is the confirmed higher low."
int CamelTrend(double &lastLow) {
   int p = MathMax(1, InpPivot);
   double hs[24], ls[24];
   int    hidx[24], lidx[24];
   int nh = 0, nl = 0;
   for (int k = InpTrendLook; k >= p + 1; k--) {          // oldest -> newest
      bool ph = true, pl = true;
      for (int q = 1; q <= p; q++) {
         if (bHigh(k) <= bHigh(k - q) || bHigh(k) <= bHigh(k + q)) ph = false;
         if (bLow(k)  >= bLow(k - q)  || bLow(k)  >= bLow(k + q))  pl = false;
      }
      if (ph && nh < 24) { hs[nh] = bHigh(k); hidx[nh] = k; nh++; }
      if (pl && nl < 24) { ls[nl] = bLow(k);  lidx[nl] = k; nl++; }
   }
   if (nh < 2 || nl < 2) return 0;                        // not enough humps drawn yet
   bool higher_high = hs[nh - 1] > hs[nh - 2];            // "breaking above previous highs"
   bool higher_low  = ls[nl - 1] > ls[nl - 2];            // "forming new higher lows"
   if (!(higher_high && higher_low)) return 0;

   double defend = ls[nl - 1];
   // his line 45: once the newest hump top is taken out, the deepest point since it
   // becomes the confirmed higher low — the level we defend from then on.
   int peak_bar = hidx[nh - 1];
   double peak = hs[nh - 1];
   bool taken = false;
   for (int q = peak_bar - 1; q >= 1; q--)
      if (bHigh(q) > peak) { taken = true; break; }
   if (taken) {
      double deep = bLow(1);
      for (int q = 1; q <= peak_bar; q++) deep = MathMin(deep, bLow(q));
      if (deep > defend) defend = deep;                   // the guard only ever rises
   }
   lastLow = defend;
   return +1;
}

// TREND BY EMA-5 SLOPE (2026-08-24, Zee: "what if you remove this gate, see how it
// goes then? use the slope of EMA 5 instead as your trend line"). No structure walk,
// no camel-hump inference, no two-point test — the trend is simply which way his
// EMA-5 is pointing over the last InpEmaSlopeBars candles.
int TrendByEma(double &lastLow) {
   double now = Ema(5, 1), then = Ema(5, 1 + MathMax(1, InpEmaSlopeBars));
   int sl = SwingLowIdx();
   lastLow = (sl > 0) ? bLow(sl) : 0;
   if (now > then) return +1;
   if (now < then) return -1;
   return 0;
}

int    g_tr_state = 0;        // 0 = none, +1 = uptrend latched
double g_tr_defend = 0;       // the low we are defending
double g_tr_high = 0;         // the last high that was broken
double g_tr_deep = 0;         // deepest point since that high — the low-in-waiting

int StickyTrend(int fresh, double &lastLow) {
   // a fresh confirmation always (re)arms the latch
   if (fresh == +1) {
      if (g_tr_state != +1) {
         g_tr_state = +1;
         g_tr_defend = lastLow;
         g_tr_high = bHigh(1);
         g_tr_deep = bLow(1);
      }
   }
   if (g_tr_state != +1) return fresh;

   // "whenever a high is broken, the deepest point is the confirmed higher low"
   //
   // WHICH high? (2026-08-23, Zee: test the swing-high version.) Treating ANY new
   // high as "a high broken" ratchets the guard to within a few candles of price —
   // an ordinary pullback then kills the trend, it re-arms, and each re-arm admits a
   // fresh batch of marginal setups. Measured: 22 trades, 7W/15L, +281.10, where the
   // six trades it added over the strict version were 1W/5L. His camel humps are
   // SWING highs, so only a genuine hump top being taken out may move the guard.
   if (InpGuardSwing) {
      int sk = SwingHighIdx();
      if (sk > 0 && bHigh(1) > bHigh(sk)) {
         double deep = bLow(1);
         for (int q = 1; q <= sk; q++) deep = MathMin(deep, bLow(q));
         if (deep > g_tr_defend) g_tr_defend = deep;          // never lower the guard
      }
   } else {
      if (bLow(1) < g_tr_deep) g_tr_deep = bLow(1);
      if (bHigh(1) > g_tr_high) {
         if (g_tr_deep > g_tr_defend) g_tr_defend = g_tr_deep;
         g_tr_high = bHigh(1);
         g_tr_deep = bLow(1);
      }
   }
   // "we stop buying when the last low is broken" — by BODY, his oldest rule
   if (BodyLo(1) < g_tr_defend) {
      g_tr_state = 0; g_tr_defend = 0; g_tr_high = 0; g_tr_deep = 0;
      return fresh;                       // the latch is dead; only a fresh read counts
   }
   lastLow = g_tr_defend;
   return +1;
}

//──── LAW: "after reaching 1:1 we make a BreakEven"
void BreakEvenSweep() {
   if (InpBreakEvenR <= 0) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP);
      double cur = PositionGetDouble(POSITION_PRICE_CURRENT);
      bool isBuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      double risk = isBuy ? (entry - sl) : (sl - entry);
      if (risk <= 0 || MathAbs(sl - entry) < 0.02) continue;
      double got = isBuy ? (cur - entry) : (entry - cur);
      if (got >= risk * InpBreakEvenR)
         trade.PositionModify(t, NormalizeDouble(entry, _Digits), tp);
   }
}

int OpenCount() {
   int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) == _Symbol &&
          PositionGetInteger(POSITION_MAGIC) == InpMagic) n++;
   }
   return n;
}

int OnInit() {
   trade.SetExpertMagicNumber(InpMagic);
   if (InpOandaVolume == 1) LoadOandaVol();
   if (InpOandaBars == 1) LoadOandaBars();
   g_oanda_loaded = true;
   if (MQLInfoInteger(MQL_TESTER))
      PrintFormat("[LAW] chart FROZEN for this run — %d OANDA volume rows, %d OANDA bars",
                  g_ov_n, g_ob_n);
   PrintFormat("[LAW] BasedOnLaws v1.35 — LAWS.md only. buy%s · NY %s · M5+M15 %s · "
               "stop %.1f pips under the last low · %.1fR target · BE at %.1fR · "
               "momentum body %.1fx · break must HOLD %.0f%% of what it took · EMA5 %s · %s volume · magic %d",
               InpBuyOnly ? " only" : "+sell", InpNyOnly ? "only" : "off",
               InpNeedM5M15 ? "required" : "off", InpStopBufPips * 10.0,
               InpTargetR, InpBreakEvenR, InpMomBodyMult, InpBreakHold * 100.0,
               InpNeedEma5 ? "required" : "extra/off",
               (InpOandaVolume == 1 && g_ov_n > 0) ? "OANDA" : "broker", (int)InpMagic);
   return INIT_SUCCEEDED;
}

void OnTick() {
   BreakEvenSweep();
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bt == g_last_bar) return;
   // THE GROUND MUST NOT MOVE UNDER A TEST (2026-08-23). These tables are rewritten
   // every cycle by the live OANDA bridge, and re-reading them on every bar let the
   // file change MID-RUN: Aug 18 returned 1 trade (-34.70) and then 0 trades from the
   // same binary and the same .set, purely because two bytes landed in oanda_bars.csv
   // between the runs. The tester reads once and judges a frozen chart.
   if (MQLInfoInteger(MQL_TESTER)) {
      if (!g_oanda_loaded) {
         if (InpOandaVolume == 1) LoadOandaVol();
         if (InpOandaBars == 1) LoadOandaBars();
         g_oanda_loaded = true;
      }
   } else {
      // ── NEVER JUDGE A CANDLE THE BRIDGE HAS NOT FINISHED WRITING (2026-08-24) ──
      // The first live trade proved this the expensive way. At 18:31:00.386 the EA
      // read the 18:30 candle as "close 4676.37, vol 788" and fired. The finished
      // candle was "close 4675.84, vol 2109" — it had simply caught the bridge's
      // export mid-minute. His law says the breakout must be QUIETER than the UHV
      // (997): 788 passes, 2109 REFUSES. The trade was forbidden by its own law and
      // was taken only because the volume was still accumulating. It lost -8.86.
      //
      // A candle is safe to judge only once the table already contains a row for a
      // LATER minute — that is the bridge's own proof it has moved past it.
      uint nowms = GetTickCount();
      if (nowms - g_last_reload >= 900 || g_ob_n == 0) {
         if (InpOandaVolume == 1) LoadOandaVol();
         if (InpOandaBars == 1) LoadOandaBars();
         g_last_reload = nowms;
      }
      if (InpOandaBars == 1 && InpFreshMaxSec > 0) {
         datetime newest = (g_ob_n > 0) ? g_ob_t[g_ob_n - 1] : 0;
         if (newest < bt) {                       // the closed bar is not published yet
            if (TimeCurrent() - bt < InpFreshMaxSec)
               return;                            // wait — and RETRY on the next tick
            c_stale++;                            // waited too long: refuse the bar
            g_last_bar = bt;
            PrintFormat("[LAW] bar %s skipped — OANDA still %d s behind (bridge stalled?)",
                        TimeToString(bt, TIME_MINUTES), (int)(TimeCurrent() - bt));
            return;
         }
      }
   }
   g_last_bar = bt;
   if (OpenCount() >= InpMaxOpen) return;

   // LAW: New York session only
   c_bars++;
   if (InpNyOnly) {
      int hh = (int)((TimeCurrent() / 3600) % 24);
      if (hh < InpNyFromHour || hh >= InpNyToHour) { c_session++; return; }
   }

   // HIS CHART OR NO TRADE (2026-08-23). bOpen/bHigh/... fall back to the BROKER's
   // candle, silently, one bar at a time, whenever the OANDA table lacks that minute.
   // A day with partial coverage therefore judges half the setup on his chart and
   // half on Blueberry's — the same feed-mixing that voided the Aug-21 volume test,
   // and undetectable in the result. If he reads OANDA, a missing OANDA minute is a
   // minute we cannot read: the window must be whole or we do not fire.
   if (InpOandaBars == 1 && InpOandaStrict) {
      int need = InpTrendLook + InpRetraceMax + 8;
      for (int q = 1; q <= need; q++)
         if (ObIdx(q) < 0) { c_nooanda++; return; }
   }

   MqlDateTime _dt; TimeToStruct(TimeCurrent(), _dt);
   int _hm = _dt.hour * 100 + _dt.min;
   bool _dbg = (InpDbgFrom > 0 && _hm >= InpDbgFrom && _hm <= InpDbgTo);

   // the trend is STATE now: established by HH+HL, alive while its last low holds
   double lastLow = 0;
   int t;
   if (InpTrendMode == 1) {
      t = TrendByEma(lastLow);            // his EMA-5 slope, no structure at all
   } else if (InpTrendMode == 2) {
      t = CamelTrend(lastLow);            // his camel humps, drawn from pivots
      if (InpTrendSticky) t = StickyTrend(t, lastLow);
   } else {
      t = TrendNow(lastLow, 1);
      if (InpTrendSticky) t = StickyTrend(t, lastLow);
   }
   if (_dbg) {
      int _og[]; int _n = RetraceOrigins(+1, _og);
      int _rs = (_n > 0) ? _og[0] : -1;
      int _u  = (_rs > 0) ? UhvIn(_rs, +1) : -1;
      PrintFormat("[DBG] %02d:%02d trend=%d lastLow=%.2f close1=%.2f | retrStart=%d "
                  "uhv=%d uhvHi=%.2f uhvVol=%d | bar1 %s c=%.2f v=%d body=%.2f",
                  _dt.hour, _dt.min, t, lastLow, bClose(1), _rs, _u,
                  _u > 0 ? bHigh(_u) : 0.0, _u > 0 ? (int)BarVolume(_u) : 0,
                  IsGreen(1) ? "GREEN" : (IsRed(1) ? "RED" : "doji"),
                  bClose(1), (int)BarVolume(1), MathAbs(bClose(1) - bOpen(1)));
   }
   if (InpRequireTrend && t == 0) { c_notrend++; return; }
   if (InpBuyOnly && t != +1) { c_notbuy++; return; }
   if (!HtfAgrees(t)) return;

   // LAW: "we stop buying when the last low is broken .. we keep trading until the
   // last low is safe (unbroken below)"
   if (InpStopOnLastLow && lastLow > 0) {
      if (t > 0 && bClose(1) < lastLow) { c_lastlow++; return; }
      if (t < 0 && bClose(1) > lastLow) { c_lastlow++; return; }
      g_last_low = lastLow;
   }

   int origins[];
   int no = RetraceOrigins(t, origins);
   if (no == 0) { c_noretr++; return; }
   int rs = -1, uhv = -1;
   for (int oi = 0; oi < no; oi++) {          // newest origin first, as he reads them
      int cand = UhvIn(origins[oi], t);
      if (cand < 2) continue;
      if (BreakoutOK(cand, t)) { rs = origins[oi]; uhv = cand; break; }
   }
   if (uhv < 2) { c_nouhv++; return; }

   // LAW: stop 5-7 pips below the LOWEST POINT of the retracement (the last low)
   double deep = (t > 0) ? bLow(1) : bHigh(1);
   for (int q = 1; q <= rs; q++) {
      if (t > 0) deep = MathMin(deep, bLow(q));
      else       deep = MathMax(deep, bHigh(q));
   }
   MqlTick tk;
   if (!SymbolInfoTick(_Symbol, tk)) return;
   double px = (t > 0) ? tk.ask : tk.bid;
   double sl = (t > 0) ? deep - InpStopBufPips : deep + InpStopBufPips;
   double risk = MathAbs(px - sl);
   if (risk < InpMinRiskPts || risk > InpMaxRiskPts) {
      c_risk++;
      if (InpVerbose) PrintFormat("[LAW] risk %.2f pts outside band — skipped", risk);
      return;
   }
   double tp = (t > 0) ? px + risk * InpTargetR : px - risk * InpTargetR;
   bool ok = (t > 0) ? trade.Buy(InpLots, _Symbol, 0, sl, tp, "zlaw_buy")
                     : trade.Sell(InpLots, _Symbol, 0, sl, tp, "zlaw_sell");
   if (ok) c_fired++;
   if (ok) {
      // Zee 2026-08-23: "tell me which time is the retracement begin, which time is
      // the UHV, which time is the breakout candle so i can check and verify."
      // Every fire now stamps its three anchors as CLOCK TIMES, not bar offsets.
      // and how much of the break the body was still holding at the close — the
      // number his wick clause is judged on, stamped so any fire can be re-argued.
      double _lvl  = (t > 0) ? bHigh(uhv) : bLow(uhv);
      double _took = (t > 0) ? (bHigh(1) - _lvl) : (_lvl - bLow(1));
      double _kept = (t > 0) ? (bClose(1) - _lvl) : (_lvl - bClose(1));
      PrintFormat("[LAWX] %s | origin green %s (retracement began the bar after) | UHV %s (vol %d, high %.2f) | breakout %s "
                  "(close %.2f, vol %d, HELD %.0f%% of its break) | entry %.2f stop %.2f target %.2f (%.1fR)",
                  t > 0 ? "BUY " : "SELL",
                  TimeToString(iTime(_Symbol, PERIOD_CURRENT, rs), TIME_MINUTES),
                  TimeToString(iTime(_Symbol, PERIOD_CURRENT, uhv), TIME_MINUTES),
                  (int)BarVolume(uhv), bHigh(uhv),
                  TimeToString(iTime(_Symbol, PERIOD_CURRENT, 1), TIME_MINUTES),
                  bClose(1), (int)BarVolume(1),
                  _took > 0 ? 100.0 * _kept / _took : 100.0, px, sl, tp, InpTargetR);
   }
}

double OnTester() {
   PrintFormat("[LAWCEN] bars %d | out-of-session %d | NO OANDA WINDOW %d | no trend %d | "
               "not buy-side %d | last low broken %d | no retracement %d | no UHV %d || "
               "breakout: colour %d, no close past %d, too loud %d, no momentum %d, "
               "big wick %d, body did not span %d, ema %d || risk out of band %d || FIRED %d",
               c_bars, c_session, c_nooanda, c_notrend, c_notbuy, c_lastlow, c_noretr,
               c_nouhv, c_brk_colour, c_brk_close, c_brk_vol, c_brk_mom, c_brk_wick,
               c_brk_span, c_brk_ema, c_risk, c_fired);
   double net = TesterStatistics(STAT_PROFIT);
   int n = (int)TesterStatistics(STAT_TRADES), w = (int)TesterStatistics(STAT_PROFIT_TRADES);
   PrintFormat("[LAW] ==== %d trades · %dW/%dL (%.1f%%) · net %.2f ====",
               n, w, n - w, n > 0 ? 100.0 * w / n : 0.0, net);
   return net;
}
