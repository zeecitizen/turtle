//+------------------------------------------------------------------+
//|  VSISA.mq5 — Volume Spread Imbalance Shift Analysis               |
//|                                                                   |
//|  Sajid Ahmed's method, as inferred in LAWS_VSISA_INFER.md from     |
//|  Zee's LAWS_VSISA.md and the 22-part course transcripts.           |
//|                                                                   |
//|  THE WHOLE ENGINE IN FOUR LINES:                                   |
//|    1. a 2-BAR SETUP of 2-3 same-direction bars carrying big volume     |
//|       (effort) — somebody is transacting hard in one place;        |
//|    2. a REACTION bar closing the OTHER way — that names which side  |
//|       the big volume actually was (LAW 2);                         |
//|    3. that reaction arrives on LOW volume — the resting orders are  |
//|       GONE, which is the imbalance shift itself (LAW 3);           |
//|    4. enter on its close, stop a few points past its extreme,      |
//|       target a multiple of that risk (LAW 8).                      |
//|                                                                   |
//|  Everything else in the course ships as an input defaulting OFF so |
//|  it can be convicted on its own MT5 receipts rather than smuggled  |
//|  in. Per feedback_backtests_hallucinate_take_all_chances.          |
//|                                                                   |
//|  VOLUME — WHAT THIS EA ACTUALLY JUDGES. BarVolume() asks iRealVolume |
//|  first, but MEASURED over Feb-Aug 2026 on XAUUSD it got 0 reads from  |
//|  it and 8,006,496 tick-count fallbacks: the broker publishes no real  |
//|  volume for gold CFD, so EVERY judgement below is made on TICK COUNT. |
//|  That is defensible — it is the same number the teacher reads on his  |
//|  own retail terminal — but it is NOT exchange volume, and a later     |
//|  session must not assume it is. OnDeinit prints the split every run.  |
//|  (The old project_tester_volume_blind warning still stands for M1     |
//|  work: in NON-real-tick modes MT5 fakes tick_volume at ~4/bar. Under  |
//|  model 4 it is the true tick count, which is why this works at all.)  |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//--- money -----------------------------------------------------------------
input double InpLots        = 0.10;   // InpLots — lot size per ticket
input int    InpTickets     = 1;      // InpTickets — tickets per decision (basket)
input int    InpMagicNumber = 88201;  // InpMagicNumber — VSISA
// MAX OPEN / COOLDOWN LIFTED (2026-09-12). Zee: "remove the InpMaxOpen = 1 and
// cooldown for now." The funnel is why: over seven months 236 setups passed EVERY law
// and only 124 fired — 47% were thrown away while a trade was already running, refused
// by plumbing rather than by anything the strategy believes.
//
// NOT set to unlimited. Detection runs once per CLOSED M5 bar and fires at most one
// decision per bar, so the real rate limit is one entry per 5 minutes either way; the
// ceiling only bounds how much can be open at once. 10 x 0.10 lots at the ~$45 average
// risk is roughly $450 exposed if every one is open and wrong together. Lower it if
// that is more than the account should carry.
input int    InpMaxOpen     = 10;     // InpMaxOpen — max concurrent decisions

//--- LAW 4: the 2-bar setup ----------------------------------------------------
input int    InpSetupBars   = 2;      // InpSetupBars — his 2 bar setup (2) or 3 bar setup (3)
input bool   InpRisingVol   = false;  // InpRisingVol — require each 2-bar setup bar louder than the last
// STRICT DIRECTION LIFTED (2026-09-12, Zee: "remove this condition"). It was the
// widest gate in the whole EA — 46,266 of 81,061 candidates, 57%, died here because
// BOTH 2-bar setup bars had to close the same way. His own 2-bar setup describes the
// SHAPE ("red down bars on big volume"), and demanding two perfect closes turns a
// description into a straitjacket: one bar closing a tick the wrong way voided the
// whole setup no matter how the volume looked.
input bool   InpStrictDir   = false;  // InpStrictDir — every setup bar must close its own way

//--- THE FEED (2026-09-11) -------------------------------------------------
// Zee, 2026-09-06: "we donot wish to use broker volume, we want to completely
// transition to OANDA volume taken from tradingview. any broker volume trades waste
// our time." VSISA v1.00 shipped reading BROKER TICK COUNT because the bridge was
// never wired in — an omission, not a decision. This is the Diamond's proven reader,
// ported verbatim.
//
// DEFAULT 0 ON PURPOSE, FOR NOW. All seven months of VSISA's receipts were earned on
// broker tick volume; OANDA coverage only begins 2026-08-05 (23 trading days), so the
// two cannot yet be compared over the same evidence. Flip this once the court says so.
input int    InpOandaVolume = 0;      // InpOandaVolume — 1 = judge on OANDA (TradingView) volume
input bool   InpOandaStrict = true;   // InpOandaStrict — a missing OANDA minute = no trade, never broker

//--- LAW 5: what "big" means, relative to recent bars -----------------------
// LOOKBACK IS A PLATEAU, NOT A PEAK. Over seven months: 30->$3284, 45->$3385,
// 60->$3377, 75->$3050, 90->$3196, 105->$2948. Adjacent settings swing ~$300, so the
// $249 by which 60 beats 100 is noise, not signal. With net indistinguishable the
// choice falls to the standing goal (project_goal_winrate: fewer losing trades at
// FIXED geometry) — and 100 delivers 34% WR / PF 1.94 / 120 trades against 60's
// 31% / 1.83 / 153, on identical geometry. Change this line to 60 for ~7% more net
// and three points less win rate; both are validated.
// TEN BARS, NOT A HUNDRED (2026-09-12). Zee: "the 100-bar maximum.. that's alot of
// bars to check from.. we can just check the last 10 bars." It also matches what he
// actually does by eye — he compares a candle to the handful around it, not to eight
// hours of history. Smaller window = smaller maximum = the loudness test is far easier
// to satisfy, so this loosens the EA considerably on its own.
input int    InpVolLookback = 10;     // InpVolLookback — bars defining "recent"
input int    InpBigMode     = 1;      // InpBigMode — 0 EVERY 2-bar setup bar loud · 1 only the loudest
input double InpBigPct      = 0.80;   // InpBigPct — 2-bar setup volume >= this x lookback max
input double InpBigAvg      = 1.20;   // InpBigAvg — ...and >= this x lookback average

//--- LAW 3: the low-volume reaction. THE TRIGGER. --------------------------
input int    InpQuietRef    = 0;      // InpQuietRef — 0 quiet vs the SETUP · 1 quiet vs lookback AVERAGE
input double InpLowVolPct   = 1.00;   // InpLowVolPct — reaction volume <= this x the reference
input double InpBodyFrac    = 0.35;   // InpBodyFrac — reaction body >= this x its own range
input int    InpConfirmMode = 0;      // InpConfirmMode — 0 enter on reaction · 1 wait for no-supply TEST + confirm
input double InpTestVolPct  = 0.90;   // InpTestVolPct — the test bar's volume <= this x the LAW 3 reference
input bool   InpEngulf      = false;  // InpEngulf — reaction must engulf the last 2-bar setup bar

//--- LAW 8: geometry -------------------------------------------------------
// WHICH CANDLE THE STOP HANGS FROM (2026-09-12). His LAWS_VSISA.md is explicit:
// "Stop loss 2-3 pips below the bullish blue candle" — the REACTION candle, the blue
// one we enter on. The EA had been measuring from the lowest low of ALL THREE bars, and
// since the setup bars ARE the down-move their lows sit far below, every stop came out
// systematically too wide: the two live trades risked 526 and 876 points. That single
// reference error changed the R multiple of every trade in every test.
// Mode 0 is his specification. Mode 1 is the old behaviour, kept only so the two can be
// compared honestly rather than swapped on faith.
input int    InpStopRef     = 0;      // InpStopRef — 0 = below the REACTION candle (his spec) · 1 = whole setup
input int    InpSlBufPts    = 30;     // InpSlBufPts — points beyond it (30 pts = 3 gold pips)
input int    InpMinSlPts    = 60;     // InpMinSlPts — floor, so spread cannot eat the stop
input int    InpMaxSlPts    = 900;    // InpMaxSlPts — refuse setups whose risk is absurd
input double InpTargetR     = 2.5;    // InpTargetR — TP as a multiple of risk
input double InpBreakEvenR  = 1.0;    // InpBreakEvenR — >0: move stop to entry at this R

//--- LAW 6: the wick override (default OFF) --------------------------------
input int    InpWickMode    = 0;      // InpWickMode — 0 off · 1 require · 2 override big volume
input double InpWickFrac    = 0.35;   // InpWickFrac — wick >= this x the bar's range

//--- LAW 7: anomaly, tiny spread on huge volume (default OFF) --------------
input bool   InpAnomaly     = false;  // InpAnomaly — 2-bar setup's last bar must be a spread anomaly
input double InpAnomalyMax  = 0.70;   // InpAnomalyMax — its range <= this x recent average range

//--- LAW 13: fake break of a recent extreme (default OFF) ------------------
input bool   InpFakeBreak   = false;  // InpFakeBreak — 2-bar setup must sweep a recent extreme
input int    InpSweepLook   = 30;     // InpSweepLook — bars defining that extreme

//--- LAW 9: higher-timeframe trend (default OFF) ---------------------------
// H1 TREND FILTER OFF (2026-09-12, Zee: "remove"). Worth recording what this costs,
// because the seven-month court liked it: with it ON the EA made the SAME money on
// HALF the trades and seven more points of win rate (34% vs 27%). Off, it trades far
// more and wins less often for about the same net. His call; the receipt stands.
input int    InpTrendTF     = 0;      // InpTrendTF — 0 off · 15 = M15 · 60 = H1
input int    InpTrendBars   = 20;     // InpTrendBars — bars of slope on that timeframe

//--- LAW 11: session (default open) ----------------------------------------
input int    InpSessFrom    = 0;      // InpSessFrom — broker hour, inclusive
input int    InpSessTo      = 24;     // InpSessTo — broker hour, exclusive

//--- housekeeping ----------------------------------------------------------
input int    InpCoolBars    = 0;      // InpCoolBars — bars to wait after a decision (0 = none)
input bool   InpBuys        = true;   // InpBuys — allow long setups
input bool   InpSells       = true;   // InpSells — allow short setups
input bool   InpVerbose     = true;   // InpVerbose — print every fire line

//--- state -----------------------------------------------------------------
datetime g_last_bar = 0;
datetime g_last_fire = 0;
int      g_cool     = 0;
int      g_fires    = 0;

// THE FUNNEL. v1.00 fired zero trades over five days of real M5 ticks and the report
// could not say why — "no trades" looks identical whether the 2-bar setup never formed or
// the reaction was never quiet enough. These count the bar at which each candidate
// died, and OnDeinit prints them, so a tightening can be aimed instead of guessed.
int g_seen = 0, g_rej_dir = 0, g_rej_loud = 0, g_rej_rise = 0, g_rej_anom = 0;
int g_rej_fake = 0, g_rej_react = 0, g_rej_body = 0, g_rej_quiet = 0, g_rej_trend = 0;
int g_rej_test = 0;
long g_rv_hit = 0, g_rv_miss = 0, g_ov_hit = 0;

// HOW CLOSE DID WE GET. A funnel says which gate rejected; these say by how much, which
// is the difference between "loosen this threshold a little" and "this law never
// happens on M5 gold at all". Also proves the volume feed is populated — a max of 0
// would mean iRealVolume is empty and every ratio in this file is meaningless.
long   g_vmax_seen = 0;
double g_best_loud = 0;    // best (weakest 2-bar setup bar / lookback max) reached
double g_best_quiet = 999; // lowest (reaction vol / 2-bar setup vol) reached

//+------------------------------------------------------------------+
//| Bar accessors                                                     |
//+------------------------------------------------------------------+
double bHigh(int k)  { return iHigh (_Symbol, PERIOD_CURRENT, k); }
double bLow(int k)   { return iLow  (_Symbol, PERIOD_CURRENT, k); }
double bOpen(int k)  { return iOpen (_Symbol, PERIOD_CURRENT, k); }
double bClose(int k) { return iClose(_Symbol, PERIOD_CURRENT, k); }
double bRange(int k) { return bHigh(k) - bLow(k); }
double bBody(int k)  { return MathAbs(bClose(k) - bOpen(k)); }
bool   bUp(int k)    { return bClose(k) > bOpen(k); }
bool   bDown(int k)  { return bClose(k) < bOpen(k); }

datetime g_ov_t[];
long     g_ov_v[];
int      g_ov_n = 0;
int      g_ov_miss = 0;          // lookups that fell back to broker volume
datetime g_ov_miss_bar = 0;      // last bar already reported, so one line per bar
datetime g_ov_newest = 0;        // newest minute in the table (freshness telemetry)

void LoadOandaVol() {
   g_ov_n = 0;
   // RETRY (2026-08-21): the writer swaps this file atomically every 60 s, and a
   // read landing inside that swap failed outright — one bar silently on broker
   // volume, logged at 21:46:02. Five quick attempts cover the swap window.
   int h = INVALID_HANDLE;
   for (int _try = 0; _try < 5 && h == INVALID_HANDLE; _try++) {
      h = FileOpen("oanda_vol.csv", FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON |
                                FILE_SHARE_READ | FILE_SHARE_WRITE);
      if (h == INVALID_HANDLE && !MQLInfoInteger(MQL_TESTER)) Sleep(40);
   }
   if (h == INVALID_HANDLE) {
      Print("[VSISA] OANDA volume requested but oanda_vol.csv not found — using broker volume");
      return;
   }
   ArrayResize(g_ov_t, 8192); ArrayResize(g_ov_v, 8192);
   while (!FileIsEnding(h)) {
      string ln = FileReadString(h);
      int c = StringFind(ln, ",");
      if (c <= 0) continue;
      datetime t = StringToTime(StringSubstr(ln, 0, c));
      long v = (long)StringToInteger(StringSubstr(ln, c + 1));
      if (t <= 0) continue;
      if (g_ov_n >= ArraySize(g_ov_t)) {
         ArrayResize(g_ov_t, g_ov_n + 4096); ArrayResize(g_ov_v, g_ov_n + 4096);
      }
      g_ov_t[g_ov_n] = t; g_ov_v[g_ov_n] = v; g_ov_n++;
   }
   FileClose(h);
   g_ov_newest = (g_ov_n > 0) ? g_ov_t[g_ov_n - 1] : 0;
   PrintFormat("[VSISA] OANDA volume table loaded: %d minutes (newest %s)",
               g_ov_n, TimeToString(g_ov_newest, TIME_DATE | TIME_MINUTES));
}

long OandaVolAt(datetime t) {          // binary search the sorted table
   int lo = 0, hi = g_ov_n - 1;
   while (lo <= hi) {
      int mid = (lo + hi) / 2;
      if (g_ov_t[mid] == t) return g_ov_v[mid];
      if (g_ov_t[mid] < t) lo = mid + 1; else hi = mid - 1;
   }
   return -1;
}

// ── THE TABLE IS PER-MINUTE; THE CHART NEED NOT BE (2026-09-08) ──────────────────
// Zee: "what if we test our EA on the OANDA, on the 5 minute timeframe instead of 1
// minute. maybe that one is much better due to having a stable trend."
//
// oanda_vol.csv holds ONE ROW PER MINUTE. OandaVolAt(iTime(...)) therefore returns the
// volume of the bar's FIRST MINUTE ONLY. On M1 that is the whole bar and correct; on M5
// it is about a fifth of it — and since every UHV test is a comparison BETWEEN bars,
// each reading a different fifth, the entire ranking would be wrong while every number
// still looked plausible. An M5 court run on that would have answered his question with
// noise.
//
// A bar's volume is the SUM of the minutes it spans. Under strict mode a single missing
// minute voids the whole bar: half a candle of his volume is not his candle.
long OandaVolSpan(datetime t, int mins) {
   if (mins <= 1) return OandaVolAt(t);
   long sum = 0;
   for (int m = 0; m < mins; m++) {
      long v = OandaVolAt(t + m * 60);
      if (v <= 0) {
         if (InpOandaStrict) return -1;   // an incomplete candle is not his candle
         continue;
      }
      sum += v;
   }
   return (sum > 0) ? sum : -1;
}


// iRealVolume, NOT iVolume. See the header — in the tester iVolume is a constant and
// every ratio in this file would silently become 1.0.
long BarVolume(int k) {
   if (InpOandaVolume == 1 && g_ov_n > 0) {
      long ov = OandaVolSpan(iTime(_Symbol, PERIOD_CURRENT, k),
                             (int)(PeriodSeconds() / 60));
      if (ov > 0) { g_ov_hit++; return ov; }
   }
   // NO SILENT FALLBACK UNDER STRICT MODE. Reaching here with OANDA requested means the
   // table lacks this bar; handing back the broker's number would decide a setup on a
   // feed Zee does not read. -1 propagates and VolWhole() refuses the setup outright.
   if (InpOandaVolume == 1 && InpOandaStrict) return -1;

   long rv = iRealVolume(_Symbol, PERIOD_CURRENT, k);
   if (rv > 0) { g_rv_hit++; return rv; }
   // WHICH NUMBER IS ACTUALLY BEING JUDGED. On an exchange-traded symbol iRealVolume is
   // contracts; on a CFD the broker often publishes none and this line quietly hands
   // back the TICK COUNT instead. Both are defensible proxies — the teacher reads his
   // own terminal's tick volume — but they are not the same number, and a strategy
   // built on "volume" must be able to say which one it saw. OnDeinit prints the split.
   g_rv_miss++;
   return iVolume(_Symbol, PERIOD_CURRENT, k);
}

//+------------------------------------------------------------------+
//| LAW 5 — "big" is relative to the recent past, never a band        |
//|                                                                   |
//| Part 1: "these bands are misleading... compare with the big volumes|
//| of the previous two or three days". So the yardstick is a rolling  |
//| window, and a bar is loud when it stands up against BOTH the peak  |
//| and the average of that window — peak alone lets a merely-average  |
//| bar through on a quiet stretch, average alone lets a mid-sized bar |
//| through next to a genuine climax.                                  |
//+------------------------------------------------------------------+
bool VolStats(int from, long &vmax, double &vavg, double &ravg) {
   vmax = 0; vavg = 0; ravg = 0;
   int n = 0;
   for (int k = from; k < from + InpVolLookback; k++) {
      long v = BarVolume(k);
      double r = bRange(k);
      if (v <= 0) continue;
      if (v > vmax) vmax = v;
      vavg += (double)v;
      ravg += r;
      n++;
   }
   // Half the window is enough to judge by; less than that and we are at the very
   // start of the data with no "recent past" to compare against, so stand down.
   // UNDER STRICT OANDA THE WINDOW MUST BE WHOLE. Skipping absent minutes would quietly
   // shrink the yardstick every setup is measured against — the same feed-mixing one
   // level down that InpOandaStrict exists to prevent.
   if (InpOandaVolume == 1 && InpOandaStrict && n < InpVolLookback) return false;
   if (n < InpVolLookback / 2 || vmax <= 0) return false;
   vavg /= n;
   ravg /= n;
   return true;
}

//+------------------------------------------------------------------+
//| LAW 9 — higher-timeframe trend, OFF by default                    |
//| Returns +1 up, -1 down, 0 flat/unknown.                           |
//+------------------------------------------------------------------+
int TrendDir() {
   if (InpTrendTF <= 0) return 0;
   ENUM_TIMEFRAMES tf = (InpTrendTF == 15) ? PERIOD_M15
                      : (InpTrendTF == 30) ? PERIOD_M30
                      : (InpTrendTF == 60) ? PERIOD_H1 : PERIOD_H4;
   int n = MathMax(3, InpTrendBars);
   double now  = iClose(_Symbol, tf, 1);
   double then = iClose(_Symbol, tf, n);
   if (now == 0 || then == 0) return 0;
   if (now > then) return 1;
   if (now < then) return -1;
   return 0;
}

bool InSession() {
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   if (InpSessFrom <= InpSessTo) return (t.hour >= InpSessFrom && t.hour < InpSessTo);
   return (t.hour >= InpSessFrom || t.hour < InpSessTo);   // window wrapping midnight
}

int OpenDecisions() {
   int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) n++;
   }
   return n;
}

//+------------------------------------------------------------------+
//| The setup.  side = +1 buy, -1 sell.                               |
//|                                                                   |
//| Bar indices are set by InpConfirmMode (see below); the 2-bar setup sits |
//| behind the reaction, oldest last. The whole judgement is made on    |
//| CLOSED bars only — a forming bar's volume is a fraction of what it |
//| will end as, and comparing it to a finished bar is the classic way |
//| to invent a signal that evaporates on the next tick.               |
//+------------------------------------------------------------------+
bool Detect(int side, double &sl_level, string &why) {
   int nb = MathMax(2, MathMin(3, InpSetupBars));

   // WHERE THE REACTION BAR SITS.
   // Mode 0 is his aggressive entry — Part 9: "I take an aggressive entry, my entry is
   // right here" — the reaction bar IS the entry bar, so it is bar 1.
   // Mode 1 is his confirmed entry — Part 9: "after this they did a testing, we call it
   // a NO SUPPLY TEST... if the test has small volume you should wait for the next bar
   // to be bullish, then the setup is confirmed." That costs two bars, so the reaction
   // sits at bar 3 with the test at bar 2 and the confirming bar at bar 1.
   int r = (InpConfirmMode == 1) ? 3 : 1;      // index of the REACTION bar
   int c0 = r + 1;                              // index of the newest 2-BAR SETUP bar
   int need = c0 + nb + InpVolLookback + 2;
   if (Bars(_Symbol, PERIOD_CURRENT) < need) return false;

   long vmax; double vavg, ravg;
   if (!VolStats(c0 + nb, vmax, vavg, ravg)) return false;
   g_seen++;
   if (vmax > g_vmax_seen) g_vmax_seen = vmax;

   //--- LAW 4: the 2-bar setup runs AGAINST the trade we are about to take.
   // Buying needs the effort to have been on the way DOWN (bars closing down);
   // that is where the absorbed selling sits.
   long vsum = 0, vmin_setup = 0;
   double worst_loud = 1.0, best_loud_bar = 0.0;
   double ext = (side > 0) ? bLow(c0) : bHigh(c0);
   for (int q = 0; q < nb; q++) {
      int k = c0 + q;
      if (InpStrictDir) {
         if (side > 0 && !bDown(k)) { g_rej_dir++; return false; }
         if (side < 0 && !bUp(k))   { g_rej_dir++; return false; }
      }
      long v = BarVolume(k);
      if (v <= 0) return false;

      // LAW 5, two readings of the same sentence. Zee wrote "these volumes will be
      // that SESSION'S HIGHEST VOLUMES" (plural — mode 0, every bar stands up against
      // the rolling peak). Part 8 says "the BIGGEST volume is here", singular — mode 1,
      // one standout bar carries the 2-bar setup while the rest need only beat the average.
      // Mode 0 is the literal reading and is tested first; mode 1 exists because three
      // consecutive bars each at 70% of a rolling maximum may simply never happen.
      double loud = (double)v / (double)vmax;
      if (q == 0 || loud < worst_loud) worst_loud = loud;
      if (loud > best_loud_bar) best_loud_bar = loud;
      if (InpBigMode == 0 && (double)v < InpBigPct * (double)vmax) {
         if (worst_loud > g_best_loud) g_best_loud = worst_loud;
         g_rej_loud++; return false;
      }
      if ((double)v < InpBigAvg * vavg) { g_rej_loud++; return false; }

      // LAW 4 — optional: the effort must ESCALATE. Part 4: the second bar's volume
      // higher than the first, the third "even higher than the previous two".
      if (InpRisingVol && q > 0) {
         long prev = BarVolume(k - 1);      // k-1 is the NEWER bar
         if (prev <= v) { g_rej_rise++; return false; }
      }
      vsum += v;
      if (vmin_setup == 0 || v < vmin_setup) vmin_setup = v;
      if (side > 0) ext = MathMin(ext, bLow(k));
      else          ext = MathMax(ext, bHigh(k));
   }
   double vsetup = (double)vsum / nb;
   if (InpBigMode == 1 && best_loud_bar < InpBigPct) {
      if (best_loud_bar > g_best_loud) g_best_loud = best_loud_bar;
      g_rej_loud++; return false;
   }
   double reach = (InpBigMode == 1) ? best_loud_bar : worst_loud;
   if (reach > g_best_loud) g_best_loud = reach;

   //--- LAW 7: anomaly — the last 2-bar setup bar spends huge volume for tiny spread.
   if (InpAnomaly) {
      if (ravg <= 0) return false;
      if (bRange(c0) > InpAnomalyMax * ravg) { g_rej_anom++; return false; }
   }

   //--- LAW 13: the fake break. The 2-bar setup must take out a recent extreme, and the
   // reaction must close back INSIDE it — Zee's tier-3 "strongest" case.
   if (InpFakeBreak) {
      double lvl = (side > 0) ? bLow(c0 + nb) : bHigh(c0 + nb);
      for (int k = c0 + nb; k < c0 + nb + InpSweepLook; k++) {
         if (side > 0) lvl = MathMin(lvl, bLow(k));
         else          lvl = MathMax(lvl, bHigh(k));
      }
      if (side > 0) {
         if (ext >= lvl)       { g_rej_fake++; return false; }  // never swept the low
         if (bClose(r) <= lvl) { g_rej_fake++; return false; }  // no close back inside
      } else {
         if (ext <= lvl)       { g_rej_fake++; return false; }
         if (bClose(r) >= lvl) { g_rej_fake++; return false; }
      }
   }

   //--- LAW 2: the reaction names the side.
   if (side > 0 && !bUp(r))   { g_rej_react++; return false; }
   if (side < 0 && !bDown(r)) { g_rej_react++; return false; }

   // Part 15: "its closing is strongly bullish". A doji that happens to close a tick
   // up is not a reaction, so the body has to carry the bar.
   double rng1 = bRange(r);
   if (rng1 <= 0) return false;
   if (bBody(r) < InpBodyFrac * rng1) { g_rej_body++; return false; }

   if (InpEngulf) {
      if (side > 0 && bClose(r) <= bHigh(c0)) return false;
      if (side < 0 && bClose(r) >= bLow(c0))  return false;
   }

   //--- LAW 3: THE TRIGGER. The reaction must arrive on LOW volume.
   // Part 15: "the lower the volume on it, the stronger the signal. If a big volume
   // comes, SKIP it, wait more." So this is a veto, not a score.
   long v1 = BarVolume(r);
   if (v1 <= 0) return false;
   // WHICH "LOW" DOES HE MEAN? Mode 0 reads it as low RELATIVE TO THE CLIMAX just
   // seen — the collapse he draws on the chart. Mode 1 reads it as low for this market
   // generally, i.e. below the recent average. Volume is strongly autocorrelated, so
   // the bar right after three loud bars is itself usually loud: the two-day probe
   // never got below 0.83x 2-bar setup. Mode 1 exists because if that holds over a month,
   // mode 0 is not a strict rule — it is an impossible one, and the distinction is
   // worth a receipt rather than a guess.
   double vref = (InpQuietRef == 1) ? vavg : vsetup;
   double qr = (double)v1 / MathMax(1.0, vref);
   if (qr < g_best_quiet) g_best_quiet = qr;
   bool quiet = ((double)v1 <= InpLowVolPct * vref);

   //--- LAW 6: the wick. On a big-volume bar a wick against the move says the volume
   // was aggression that WON, not absorption that is still sitting there — which is
   // the one case the teacher says not to wait on.
   double upper = bHigh(r) - MathMax(bOpen(r), bClose(r));
   double lower = MathMin(bOpen(r), bClose(r)) - bLow(r);
   bool wick = (side > 0) ? (lower >= InpWickFrac * rng1)
                          : (upper >= InpWickFrac * rng1);

   if (InpWickMode == 1 && !wick) { g_rej_quiet++; return false; }  // require outright
   if (!quiet) {
      // Part 6: "in the case of aggressive selling, even if a big volume comes, you
      // don't wait — you enter here." Mode 2 is that exception, and ONLY that.
      if (!(InpWickMode == 2 && wick)) { g_rej_quiet++; return false; }
   }

   //--- THE NO-SUPPLY TEST (InpConfirmMode = 1).
   // Part 9: "after this they did a testing — we call it a NO SUPPLY TEST. If the test
   // has a small volume you should wait for the next bar to be bullish, then the setup
   // is confirmed. A big volume on the test would have meant sustained buying."
   //
   // So the test bar must (a) probe BACK toward the 2-bar setup, (b) do it on volume lower
   // than the reaction's, and (c) FAIL to take out the setup extreme — a test that
   // breaks the low is not a test, it is the setup being wrong. Then the bar after it
   // has to close our way, which is the actual entry bar.
   if (InpConfirmMode == 1) {
      long vt = BarVolume(2);
      if (vt <= 0) { g_rej_test++; return false; }
      // MEASURED AGAINST THE CLIMAX, NOT AGAINST THE REACTION. The first cut of this
      // compared the test bar to the reaction bar — but LAW 3 has already forced the
      // reaction to be quiet, so that asked the test to be quieter than something
      // already quiet. It rejected 100% of setups: 48 sweep passes over seven months
      // fired ZERO trades. Every "small volume" the teacher names is small next to the
      // effort that came before it, so the test uses the same reference as LAW 3.
      if ((double)vt > InpTestVolPct * vref) { g_rej_test++; return false; }
      if (side > 0) {
         if (bLow(2) <= ext)  { g_rej_test++; return false; }   // broke the low: not a test
         if (!bUp(1))         { g_rej_test++; return false; }   // no confirming bar
         if (bClose(1) <= bClose(2)) { g_rej_test++; return false; }
      } else {
         if (bHigh(2) >= ext) { g_rej_test++; return false; }
         if (!bDown(1))       { g_rej_test++; return false; }
         if (bClose(1) >= bClose(2)) { g_rej_test++; return false; }
      }
   }

   //--- LAW 9 (off by default)
   int td = TrendDir();
   if (td != 0 && td != side) { g_rej_trend++; return false; }

   //--- LAW 8: the stop. `ext` above is the SETUP's extreme and is still what the
   // fake-break and no-supply tests need, so the stop gets its own reference.
   double sref;
   if (InpStopRef == 0)
      sref = (side > 0) ? bLow(r) : bHigh(r);          // his spec: the reaction candle
   else
      sref = (side > 0) ? MathMin(ext, bLow(r))        // the old, wider behaviour
                        : MathMax(ext, bHigh(r));
   if (InpConfirmMode == 1) {
      // the test and the confirming bar happened after the reaction; the stop has to
      // sit outside everything the setup has already defended, not just the reaction
      for (int k = 1; k <= 2; k++) {
         if (side > 0) sref = MathMin(sref, bLow(k));
         else          sref = MathMax(sref, bHigh(k));
      }
   }
   double buf = InpSlBufPts * _Point;
   sl_level = (side > 0) ? sref - buf : sref + buf;

   why = StringFormat("2-bar setup %d bars vol %.0f (max %d avg %.0f) | reaction vol %d = %.2fx%s%s",
                      nb, vsetup, (int)vmax, vavg, (int)v1,
                      (double)v1 / MathMax(1.0, vsetup),
                      quiet ? " QUIET" : " LOUD",
                      wick ? " +wick" : "");
   return true;
}

//+------------------------------------------------------------------+
//| Fire                                                              |
//+------------------------------------------------------------------+
void Fire(int side, double sl_level, string why) {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double entry = (side > 0) ? ask : bid;
   double risk  = MathAbs(entry - sl_level);

   // The floor exists because his 2-3 pips are FX pips on a pair whose spread is a
   // fraction of gold's. A stop narrower than the spread is not a tight stop, it is a
   // guaranteed loss on entry.
   double minr = InpMinSlPts * _Point;
   double maxr = InpMaxSlPts * _Point;
   if (risk < minr) {
      risk = minr;
      sl_level = (side > 0) ? entry - risk : entry + risk;
   }
   if (risk > maxr) {
      if (InpVerbose)
         PrintFormat("[VSISA] refused: risk %.0f pts > cap %d", risk / _Point, InpMaxSlPts);
      return;
   }

   double tp = (InpTargetR > 0)
             ? ((side > 0) ? entry + InpTargetR * risk : entry - InpTargetR * risk)
             : 0.0;

   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   sl_level = NormalizeDouble(sl_level, dg);
   if (tp > 0) tp = NormalizeDouble(tp, dg);

   int n = MathMax(1, InpTickets);
   int placed = 0;
   for (int i = 0; i < n; i++) {
      string tag = StringFormat("vsisa_%d_%d", g_fires, i);
      bool ok = (side > 0) ? trade.Buy (InpLots, _Symbol, 0, sl_level, tp, tag)
                           : trade.Sell(InpLots, _Symbol, 0, sl_level, tp, tag);
      if (ok) placed++;
   }
   if (placed == 0) {
      if (InpVerbose) PrintFormat("[VSISA] send failed: %d %s", trade.ResultRetcode(),
                                  trade.ResultRetcodeDescription());
      return;
   }
   g_fires++;
   g_cool = InpCoolBars;
   g_last_fire = iTime(_Symbol, PERIOD_CURRENT, 0);

   if (InpVerbose)
      PrintFormat("[VSISA] #%d %s @ %.2f SL %.2f (%.0f pts) TP %.2f (%.1fR) | %s",
                  g_fires, (side > 0) ? "BUY" : "SELL", entry, sl_level,
                  risk / _Point, tp, InpTargetR, why);
}

//+------------------------------------------------------------------+
//| Breakeven — LAW 8's optional half                                 |
//+------------------------------------------------------------------+
void BreakEvenCheck() {
   if (InpBreakEvenR <= 0) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;

      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      if (sl == 0) continue;
      long   type = PositionGetInteger(POSITION_TYPE);
      double risk = MathAbs(open - sl);
      if (risk <= 0) continue;

      double px = (type == POSITION_TYPE_BUY)
                ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double gained = (type == POSITION_TYPE_BUY) ? (px - open) : (open - px);
      if (gained < InpBreakEvenR * risk) continue;

      // already at or past breakeven — nothing to do
      if (type == POSITION_TYPE_BUY  && sl >= open) continue;
      if (type == POSITION_TYPE_SELL && sl <= open) continue;
      trade.PositionModify(tk, NormalizeDouble(open, _Digits), tp);
   }
}

//+------------------------------------------------------------------+
int OnInit() {
   if (InpOandaVolume == 1) LoadOandaVol();
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(30);
   // KEEP THIS STRING IN STEP WITH #property version — the Diamond's banner said
   // v1.14 for nine versions and nobody could tell from a log which build was live.
   PrintFormat("[VSISA] v1.00 — 2-bar setup %d bars (bigmode %d, big>=%.2fxmax/%.2fxavg) | "
               "reaction<=%.2fx%s | TP %.1fR, BE %.1fR, SL buf %d pts (floor %d) | "
               "trendTF %d, confirm %d, wick %d, anomaly %d, fake %d | feed %s | %.2f lots x%d | "
               "magic %d",
               InpSetupBars, InpBigMode, InpBigPct, InpBigAvg,
               InpLowVolPct, (InpQuietRef == 1) ? " avg" : " 2-bar setup",
               InpTargetR, InpBreakEvenR, InpSlBufPts, InpMinSlPts,
               InpTrendTF, InpConfirmMode, InpWickMode, (int)InpAnomaly,
               (int)InpFakeBreak,
               (InpOandaVolume == 1) ? (InpOandaStrict ? "OANDA-STRICT" : "OANDA")
                                     : "BROKER-TICKS",
               InpLots, InpTickets, InpMagicNumber);

   // WHICH NUMBER IS THIS BROKER ACTUALLY GIVING US (2026-09-12).
   // Zee moved VSISA to Axi because "AXI volume happens to be more accurate on the
   // VSISA strategy". Whether that is true is a FACT ABOUT THE FEED, and it is knowable
   // in one line at startup instead of guessed: on Blueberry iRealVolume returned 0 for
   // gold CFD on every one of 8,006,496 reads, so the strategy silently ran on tick
   // count. This says out loud which one Axi hands back, on the symbol actually attached.
   {
      long rv = 0, tv = 0; int probed = 0;
      for (int k = 1; k <= 20; k++) {
         long r = iRealVolume(_Symbol, PERIOD_CURRENT, k);
         long t = iVolume(_Symbol, PERIOD_CURRENT, k);
         if (t > 0) { rv += r; tv += t; probed++; }
      }
      if (probed == 0)
         Print("[VSISA] FEED PROBE: no bars yet — check again once history loads");
      else if (rv > 0)
         PrintFormat("[VSISA] FEED PROBE on %s: REAL VOLUME available (%d bars: real %I64d "
                     "vs tick %I64d). BarVolume() will judge on REAL volume.",
                     _Symbol, probed, rv, tv);
      else
         PrintFormat("[VSISA] FEED PROBE on %s: no real volume (%d bars, tick total "
                     "%I64d). BarVolume() falls back to TICK COUNT, same as Blueberry.",
                     _Symbol, probed, tv);
   }

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   PrintFormat("[VSISA] stopped, %d decisions taken", g_fires);
   // The funnel, widest gate first. Whichever line eats the candidates is the law to
   // aim a variant at — guessing which one is what cost the first five-day run.
   PrintFormat("[VSISA] FUNNEL candidates %d | dir %d | not loud %d | not rising %d | "
               "anomaly %d | fake %d | reaction %d | body %d | not quiet %d | test %d "
               "| trend %d | FIRED %d",
               g_seen, g_rej_dir, g_rej_loud, g_rej_rise, g_rej_anom, g_rej_fake,
               g_rej_react, g_rej_body, g_rej_quiet, g_rej_test, g_rej_trend, g_fires);
   PrintFormat("[VSISA] VOLUME SOURCE OANDA %I64d | iRealVolume %I64d | broker tick "
               "count %I64d — %s", g_ov_hit, g_rv_hit, g_rv_miss,
               (g_ov_hit > 0 && g_rv_miss == 0 && g_rv_hit == 0)
                   ? "ALL OANDA (his feed)"
                   : ((g_ov_hit == 0 && g_rv_hit == 0)
                      ? "EVERY judgement used BROKER TICK COUNT" : "MIXED"));
   PrintFormat("[VSISA] REACH loudest lookback max %d | best 2-bar setup/max %.2f "
               "(need %.2f) | best reaction/2-bar setup %.2f (need %.2f)",
               (int)g_vmax_seen, g_best_loud, InpBigPct,
               (g_best_quiet > 900 ? -1.0 : g_best_quiet), InpLowVolPct);
}

void OnTick() {
   BreakEvenCheck();

   // One decision per closed bar. Everything this EA judges is a finished bar, so
   // running the detector on every tick would only re-answer the same question.
   datetime t = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (t == g_last_bar) return;
   g_last_bar = t;

   if (g_cool > 0) { g_cool--; return; }
   if (!InSession()) return;
   if (OpenDecisions() >= InpMaxOpen) return;

   double sl = 0;
   string why = "";
   if (InpBuys  && Detect(+1, sl, why)) { Fire(+1, sl, why); return; }
   if (InpSells && Detect(-1, sl, why)) { Fire(-1, sl, why); return; }
}
//+------------------------------------------------------------------+
