//+------------------------------------------------------------------+
//|                                              TickSpeedGauge.mq5  |
//|   Order-flow SPEED and DIRECTION for XAUUSD, on a rolling        |
//|   statistical baseline so "fast" means fast FOR RIGHT NOW.       |
//+------------------------------------------------------------------+
//  Zee, 2026-10-03: "i want you to help me take trades on XAUUSD chart on MT5.. by
//  developing an EA which is a meter with a needle to help me understand what is the
//  tick speed" ... then: "Tick speed alone cannot tell you direction ... you must combine
//  tick speed with price micro-structure."
//
//  He is right, and that is what v1.02 adds: the needle still measures INTENSITY, and a
//  separate delta bar measures VECTOR. The verdict line below them implements his own
//  summary table - ride, fade, or stand down.
//
//  HIS KEY INSIGHT, WHICH THIS FILE MUST NOT BREAK:
//      "A 'High' tick speed during the Asian session might only be 10 ticks per second,
//       whereas a 'High' tick speed during the New York open might exceed 80 ... a static
//       threshold will generate false signals."
//  So nothing here has a fixed threshold. Speed is scored in standard deviations from a
//  rolling baseline, and "stalling" is judged against a rolling baseline of price range -
//  because a 20-cent move is a stall at the New York open and a stampede at 3am.
//
//  THE ONE HONEST LIMITATION, stated where it cannot be missed:
//  True order flow needs the AGGRESSOR side - did the trade hit the bid or lift the ask.
//  MT5 exposes that in MqlTick.flags as TICK_FLAG_BUY / TICK_FLAG_SELL, but most retail
//  CFD feeds never set those bits; they send BID/ASK updates only. So this EA uses the
//  real flags WHEN THE BROKER SENDS THEM and otherwise infers side from the direction of
//  the price change, which is a proxy, not the truth. The readout says which mode is live
//  ("FLAGS" or "INFER") so the number is never trusted more than it deserves.
//
//  AND THE REASON FOR THE CSV: his three signals - delta continuation, velocity alignment,
//  absorption/exhaustion - are HYPOTHESES. This project has spent a week watching
//  plausible hypotheses die on measurement. Every second is logged with price beside it so
//  "does a +2 SD spike with 80% up-ticks actually precede an up-move?" can be answered
//  with a number before a single lot is risked on it.
//+------------------------------------------------------------------+
#property copyright "Zee + Claude"
#property link      ""
#property version   "1.53"
#define  VER         "1.53"
#property strict

#include <Canvas\Canvas.mqh>

//--- inputs ---------------------------------------------------------------------------
input group "── Measurement ──"
enum ESpeedSrc { SRC_AUTO = 0, SRC_TICKS = 1, SRC_BOOK = 2 };

input int    InpLiveWindowMs  = 2000;   // live window FLOOR (ms). Grows if the symbol is slow
input bool   InpAutoWindow    = true;   // widen the window until it holds InpMinWindowTicks
input int    InpMaxWindowMs   = 24000;  // ...but never wider than this
//--- WHICH EVENT STREAM IS "SPEED". On a throttled CFD feed the tape can be dead while the
//--- book is busy; measuring ticks there measures nothing. AUTO compares the two baselines.
input ESpeedSrc InpSpeedSource = SRC_AUTO;  // AUTO | TICKS | BOOK
input int    InpBaselineSec   = 300;    // rolling baseline window (seconds). 300 = his 5 min
input int    InpWarmupSec     = 30;     // show no verdict until this many samples exist

input group "── Direction thresholds ──"
input double InpHighSigma     = 2.0;    // his "+2 Standard Deviations" action zone
input double InpLowSigma      = 1.0;    // below baseline - this*SD = the dead zone
input double InpDeltaStrong   = 0.30;   // |up-down|/(up+down) above this = one-sided flow
input double InpStallFactor   = 0.60;   // range < this * its own baseline = price is STALLING

input group "── Minimums (a dead market must not produce a verdict) ──"
input double InpMinBaseTps    = 0.2;    // baseline tps below this = truly shut (sample size is the real guard)
input double InpMinBaseSd     = 0.15;   // sd below this makes the z-score meaningless
input int    InpMinWindowTicks= 10;     // fewer ticks than this in the live window = no verdict
input double InpMinRangeBase  = 2.0;    // range baseline (points) below this = no stall test

input group "── His three micro-structure setups ──"
input int    InpCoilMinRun    = 3;      // seconds delta must HOLD one side while price is pinned
input int    InpFlipWindow    = 6;      // a strong delta sign reversing within this many s = FLIP
input double InpWickSigma     = 3.0;    // "needle slams to maximum" - exhaustion needs this
input double InpVacuumDelta   = 0.75;   // ~90% one-sided, his momentum-ignition threshold
input double InpThinBookPct   = 0.60;   // book volume below this x its baseline = liquidity void
input int    InpEarlyWindowSec= 15;     // his "first 15 seconds after the minute rolls over"
input double InpObiTrigger    = 0.60;   // |OBI| above this = the opposing wall has collapsed
input double InpPredSigma     = 1.0;    // speed needed for a PREDICT (his "elevated", z >= 1)
//--- THE MASTER SIGNAL: his 3-filter checklist, one word, one colour.
//--- BOTH OF THESE MEASURED BADLY ON ETHUSDTp AND SHIP OFF. See TICK_SPEED.md section 37.
//--- THE SPRING. Best-evidenced signal here: 91% at 10s on the clean subset, p=0.0001,
//--- 36 independent episodes, and it PASSES the mirror test (backward 24% vs forward 82%).
input bool   InpShowSpring    = true;   // draw the coil and fire SPRING UP / SPRING DOWN
input double InpSpringLoad    = 0.25;   // bias beyond -/+ this is loading the spring
input double InpSpringFire    = 0.25;   // crossing back through -/+ this releases it
input bool   InpShowAbsorb    = false;  // absorption overlay. Measured 14% at 3s (base 52%)
input int    InpAbsorbLookSec = 60;     // "price refused to move" over this many seconds
//--- ICEBERG / RELOAD. Cumulative consumption at ONE price vs the biggest size ever shown
//--- there. Needs no aggressor flags, which is why it can work on this feed at all.
input bool   InpSweepDial     = true;   // a second, smaller dial for the sweep engine
input double InpSweepClamp    = 8.0;    // cons/peak ratio that pins the needle at full scale
input bool   InpTrapDial      = true;   // third dial: CVD vs price divergence over InpTrapSec
input int    InpTrapSec       = 60;     // the look-back the trapped score is built from
input int    InpProbeTicks   = 400;     // report what the tick feed carries after this many
input int    InpMinBookLevels = 4;      // fewer levels than this = an LP quote, not a book
input long   InpMinTouchVol   = 2;      // a touch volume that never exceeds this is a FLAG,
                                        // not a size - Blueberry serves 1 and 1 forever
input int    InpEdgeHoldSec   = 60;     // gold needs ~60s to clear its spread at all;
                                        // the old 10 was fitted to ETHUSDTp. See s.55/56.
//input int  InpEdgeHoldSec   = 10;     // the measured life of a sweep edge. Mean move peaks
                                        // at 10s (0.178), is 0.002 by 60s, negative by 120s
input bool   InpShowSweepUp   = true;   // ASK swept -> LONG. 88% at 3s, PASSES the mirror
                                        // test (fwd 87.6 vs bwd 64.9). TICK_SPEED.md s.42
input bool   InpShowSweepDn   = false;  // BID swept -> SHORT. 77% at 3s but it MIRRORS price
                                        // (fwd 76.6 vs bwd 78.0), so it ships off
input double InpIcebergRatio  = 3.0;    // consumed > peak x this, AND refilled, = ICEBERG
input int    InpIcebergMinVol = 15;     // ignore noise: the peak must be at least this
input int    InpIcebergWinSec = 20;     // the ratio must be reached WITHIN this many seconds,
                                        // else the counters reset - otherwise a level that
                                        // simply sits still eventually qualifies on time alone
input bool   InpIceNeedDelta  = false;  // also require a one-sided delta. OFF: delta measured
                                        // 25% at high speed - see TICK_SPEED.md section 29
input bool   InpShowThin      = false;  // thin-book alert. Measured +1 point of lift at 1s
input double InpThinAlertPct  = 0.90;   // book below this x its baseline = THIN
input double InpSigGoSigma    = 1.5;    // filter 1 VELOCITY: speed must exceed this many SD
input double InpSigDelta      = 0.50;   // filter 2 PRESSURE: |delta| must reach this
input double InpSigObi        = 0.50;   // filter 3 FRICTION: touch OBI must clear this
input double InpSigObiDeep    = 0.30;   // ...and the deep book must agree this far
input int    InpSignalHoldSec = 4;      // a fired PREDICT stays on the band this many seconds
input bool   InpSpreadGuard   = false;  // ON: refuse BUY/SELL when the spread eats the move
                                        // OFF (now): still shown, but muted and labelled
input double InpCommissionPx  = 0.0;    // ROUND-TURN commission in PRICE units. On a raw-
                                        // spread account this is the real cost, not the
                                        // spread. Gold at $X/lot/side: (2*X)/100.
input double InpMinEdgeRatio  = 2.0;    // a typical burst must be this many x the spread
input int    InpBurstSec      = 10;     // "a burst" = the move over this many seconds

input group "── Gauge position & size ──"
input int    InpX             = 20;     // X pixels from the corner
input int    InpY             = 20;     // Y pixels from the corner
input int    InpCorner        = 0;      // 0=top-left 1=top-right 2=bottom-left 3=bottom-right
input int    InpRadius        = 235;    // dial radius in pixels. Everything else scales from this
input double InpFontScale     = 1.15;   // text size multiplier on top of the dial scale

input group "── Logging (so the idea can be TESTED, not just watched) ──"
input bool   InpLogCsv        = true;   // one row per second to Common\Files
input string InpLogName       = "tickspeed4.csv";  // schema 4: speed column fixed

input group "── Alerts ──"
input bool   InpAlertOnSignal = false;  // popup when a RIDE or FADE verdict appears

//--- geometry -------------------------------------------------------------------------
#define SWEEP_FROM 215.0                 // degrees, left end of the dial
#define SWEEP_TO   -35.0                 // degrees, right end
#define TICKBUF    8192                  // circular buffer of tick samples
#define BASE_R     92.0                  // the radius every pixel constant was tuned at

//--- EVERY pixel dimension goes through this, so the dial stays proportioned at any size.
int SC(const double px)
{
   int v = (int)MathRound(px * (double)InpRadius / BASE_R);
   return (v < 1) ? 1 : v;
}

//--- TEXT ONLY. "The dial is too small" and "the text is too small" are not always the same
//--- complaint, so fonts get their own multiplier on top of the geometric scale. Above about
//--- 1.3 the two stats lines start to exceed the canvas width - they are ~78% of it at 1.0.
int FS(const double px)
{
   int v = (int)MathRound(px * (double)InpRadius / BASE_R * InpFontScale);
   return (v < 1) ? 1 : v;
}

//--- verdicts, straight from his summary table ----------------------------------------
#define V_WARMUP   0
#define V_NOTRADE  1
#define V_WATCH    2
#define V_RIDE_UP  3
#define V_RIDE_DN  4
#define V_FADE_UP  5                     // absorption at support -> expect up
#define V_FADE_DN  6                     // absorption at resistance -> expect down
#define V_MIXED    7
#define V_QUIET    8                     // too thin to say anything
#define V_COIL_UP  9                     // coiled spring, wall about to break upward
#define V_COIL_DN  10
#define V_WICK_UP  11                    // exhaustion: delta flipped, expect the wick
#define V_WICK_DN  12
#define V_VAC_UP   13                    // ignition into a thin book
#define V_VAC_DN   14
#define V_PRED_UP  15                    // engine pushing AND the ask wall is gone
#define V_PRED_DN  16
#define V_BRK_UP   17                    // peak speed, direction read from OBI - COINCIDENT
#define V_BRK_DN   18
#define V_SWP_UP   19                    // the ASK is being swept -> price rises. LEADS.
#define V_SWP_DN   20                    // the BID is being swept -> price falls. MIRROR.

//--- state ----------------------------------------------------------------------------
CCanvas  g_cv;
string   g_obj = "TickSpeedGauge";
int      g_w = 0, g_h = 0, g_cx = 0, g_cy = 0;

ulong    g_t_ms[TICKBUF];                // tick arrival time
double   g_t_px[TICKBUF];                // mid price at that tick
char     g_t_side[TICKBUF];              // +1 up, -1 down, 0 flat
int      g_head = 0;
long     g_seen = 0;
double   g_prev_px = 0.0;
bool     g_have_flags = false;           // broker actually sets TICK_FLAG_BUY/SELL
//--- FEED PROBE: what does this broker actually send? Decides whether anything but raw speed
//--- is possible when there is no Level 2.
long     g_pr_n = 0, g_pr_flag = 0, g_pr_last = 0, g_pr_vol = 0;
bool     g_pr_said = false;
bool     g_dom_ok      = false;          // MarketBookAdd succeeded = Level 2 exists
long     g_dom_bidvol  = 0, g_dom_askvol = 0;
long     g_dom_delta   = 0;              // (bid side vol - ask side vol), TRUE order book
int      g_dom_events  = 0;
//--- ring of BOOK EVENT arrival times, so book rate can be measured exactly like tick rate
#define  BEVBUF 8192
ulong    g_e_ms[BEVBUF];
int      g_ehead = 0; long g_eseen = 0;
double   g_ebase[];                      // per-second book-event counts
double   g_vbase[];                      // per-second CONSUMED VOLUME - the book-mode speed
double   g_vmean = 0.0, g_vsd = 0.0;
double   g_emean = 0.0, g_esd = 0.0;     // book-stream baseline
double   g_tmean = 0.0, g_tsd = 0.0;     // tick-stream baseline
int      g_src   = SRC_TICKS;            // the stream actually driving the gauge
int      g_win_ev = 0;                   // events of the ACTIVE stream in the live window
//--- latch for the master band: a one-second flash cannot be acted on
//--- CAN THIS SYMBOL EVEN PAY THE SPREAD? A perfect signal on a move smaller than the
//--- spread is a guaranteed loss. Measured, not assumed, and it vetoes the band.
double   g_midr[300];                    // per-second mid, for the burst estimate
int      g_mh = 0, g_mn = 0;
double   g_burst = 0.0;                  // typical (p90-ish) move over InpBurstSec
int      g_minhold = 0;                  // shortest hold whose mean move beats the spread
double   g_edge  = 0.0;                  // g_burst / spread. Below 1 nothing can be traded.
double   g_accel = 0.0;                  // z[i] - z[i-1]. Shown, not acted on - see v1.22
double   g_prev_z = 0.0;
int      g_sig_latch = 0;                // V_PRED_UP / V_PRED_DN / 0
int      g_swp_latch = 0;                // V_SWP_UP / V_SWP_DN / 0
ulong    g_swp_ms    = 0;
int      g_swp_left  = 0;                // seconds left on the sweep latch
ulong    g_exit_ms   = 0;                // when the last sweep fired, for the exit clock
double   g_swp_bias = 0.0;               // -1 bid being swept .. +1 ask being swept
double   g_swp_hold = 0.0;               // peak-hold: order flow SNAPS, the eye needs a trace
//--- TRAPPED SCORE. Measured as a FILTER on sweep (80% -> 89% at 10s), NOT as a signal of its
//--- own (56% vs a 57% base) and NOT as a 60-second hold (it mirrors the minute just gone).
double   g_cvd = 0.0, g_pch = 0.0;       // consumed-volume delta and price change over InpTrapSec
double   g_trap = 0.0;                   // -1 trapped buyers .. +1 trapped sellers
double   g_trap_raw = 0.0;               // computed once a second; g_trap eases toward it
double   g_cvd_n = 1.0, g_pch_n = 1.0;   // rolling normalisers
ulong    g_sig_ms    = 0;                // when it fired

//--- previous book snapshot, for CONSUMPTION (what left the book, not what sits in it)
#define  BOOKMAX 64
double   g_pb_px[BOOKMAX], g_pa_px[BOOKMAX];
long     g_pb_vol[BOOKMAX], g_pa_vol[BOOKMAX];
int      g_pnb = 0, g_pna = 0;
//--- ring of consumption events so it can be summed over the live window
#define  CONSBUF 4096
ulong    g_c_ms[CONSBUF];
long     g_c_bid[CONSBUF], g_c_ask[CONSBUF];
int      g_chead = 0; long g_cseen = 0;
double   g_dom_dlt = 0.0;                // book-consumption delta, -1..+1
//--- TOUCH consumption: the best bid / best ask only. Deep levels churn with cancellations
//--- that are not aggression; the touch is where market orders actually land.
double   g_tb_px = 0.0, g_ta_px = 0.0;   // previous best bid / best ask price
long     g_tb_vol = 0,  g_ta_vol = 0;    // and their volumes
long     g_touch_b = 0, g_touch_a = 0;   // consumed at an UNCHANGED touch price (unambiguous)

//--- delta history, so a SUSTAINED attack can be told from a FLIP. This is the only thing
//--- separating his coiled spring from his early wick, and they predict opposite directions.
#define DHIST 120
double   g_dh[DHIST];                    // per-second delta
int      g_dh_head = 0, g_dh_n = 0;
int      g_run = 0;                      // consecutive seconds holding the same strong sign
int      g_run_sign = 0;
bool     g_flipped = false;              // strong sign reversed within InpFlipWindow
//--- book thickness, for the liquidity void
double   g_bookv = 0.0, g_book_base = 0.0;
double   g_bkb[];                        // rolling baseline of total resting book volume
int      g_bk_head = 0, g_bk_n = 0;
int      g_sec_into_bar = 0;
ulong    g_win_ms = 2000;                // the live window actually in use right now
//--- ORDER BOOK IMBALANCE. Touch = responsive but spoofable; deep = stable but slow. The
//--- trigger needs both, because one alone is a quote flicker.
double   g_obi = 0.0;                    // at the touch: (bestBid - bestAsk)/(sum)
double   g_obi_deep = 0.0;               // whole book
long     g_bbv = 0, g_bav = 0;           // resting volume at best bid / best ask
int      g_book_levels = 0;              // how many levels this broker actually serves
//--- ICEBERG STATE, per side, reset whenever the touch price moves. No *_px member: the
//--- level identity already lives in g_ta_px / g_tb_px, and a second copy would just rot.
long     g_ice_b_cons = 0, g_ice_a_cons = 0;   // cumulative consumed AT THIS PRICE
long     g_ice_b_repl = 0, g_ice_a_repl = 0;   // cumulative REFILLED at this price
long     g_ice_b_peak = 0, g_ice_a_peak = 0;   // biggest size ever shown here
ulong    g_ice_b_t0 = 0, g_ice_a_t0 = 0;      // when this level started being tracked
long     g_swept_b = 0, g_swept_a = 0;   // touch level disappeared as price moved through it
long     g_cons_b = 0, g_cons_a = 0;     // consumed in the live window

double   g_base[];                       // ring of per-second tps samples
double   g_rbase[];                      // ring of per-second price-range samples (points)
int      g_bhead = 0, g_bn = 0;

double   g_tps = 0.0, g_mean = 0.0, g_sd = 0.0, g_z = 0.0;
double   g_delta = 0.0;                  // -1 .. +1
int      g_up = 0, g_dn = 0;
double   g_net_pts = 0.0, g_range_pts = 0.0, g_range_base = 0.0;
int      g_verdict = V_WARMUP;
double   g_needle = 0.0;
double   g_bias = 0.0;                    // eased (touch+deep)/2 OBI: -1 SELL .. +1 BUY
double   g_coilL = 0.0;                  // LEFT  coil: loaded by a SELL-heavy book -> LONG
double   g_coilR = 0.0;                  // RIGHT coil: loaded by a BUY-heavy  book -> SHORT
double   g_prev_obi = 0.0;
int      g_spw = 0;                      // width of the coil strip
int      g_swr = 0;                      // radius of the sweep dial
int      g_spring = 0;                   // +1 fired up, -1 fired down, 0 idle
ulong    g_spring_ms = 0;
ulong    g_last_sec = 0;
int      g_log = INVALID_HANDLE;
int      g_prev_verdict = V_WARMUP;

//+------------------------------------------------------------------+
int OnInit()
{
   int pad = SC(14);
   g_spw = InpShowSpring ? SC(46) : 0;        // a strip on EACH side, one coil per side
   g_w = InpRadius * 2 + pad * 2 + g_spw * 2;
   g_swr = InpSweepDial ? (int)(InpRadius * 0.42) : 0;   // the sweep dial, scaled off the main one
   g_h = InpRadius + pad * 2 + SC(214) + (g_swr > 0 ? g_swr + SC(16) : 0);
   g_cx = g_spw + pad + InpRadius;            // dial centre, NOT panel centre
   g_cy = InpRadius + pad;

   if(!g_cv.CreateBitmapLabel(0, 0, g_obj, InpX, InpY, g_w, g_h, COLOR_FORMAT_ARGB_NORMALIZE))
   {
      Print("[TPS] could not create the canvas - is another copy already on this chart?");
      return(INIT_FAILED);
   }
   ObjectSetInteger(0, g_obj, OBJPROP_CORNER, InpCorner);
   ObjectSetInteger(0, g_obj, OBJPROP_BACK, false);

   int n = MathMax(10, InpBaselineSec);
   // a raw-spread account with no commission entered makes "edge" meaningless, and the
   // number would be flattering rather than merely wrong - so it is called out once.
   {
      double sp0 = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double mid0 = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) + SymbolInfoDouble(_Symbol, SYMBOL_BID)) / 2.0;
      if(mid0 > 0.0 && sp0 > 0.0 && InpCommissionPx <= 0.0)
      {
         double bp0 = 10000.0 * sp0 / mid0;
         if(bp0 < 1.0)
            PrintFormat("[TPS] spread is %.4f (%.2f bp) - that is a RAW-SPREAD account and the"
                        " real cost is COMMISSION. InpCommissionPx is 0, so the edge reading"
                        " will be far too flattering. Set it from your contract specs:"
                        " gold at $X per lot per side = (2*X)/100 in price.", sp0, bp0);
      }
   }
   if(MathMax(5, InpWarmupSec) > n)
      PrintFormat("[TPS] InpWarmupSec %d exceeds the %d-sample baseline ring and would never"
                  " complete - clamped to %d", InpWarmupSec, n, n);
   ArrayResize(g_base, n);   ArrayInitialize(g_base, 0.0);
   ArrayResize(g_rbase, n);  ArrayInitialize(g_rbase, 0.0);
   ArrayResize(g_bkb, n);    ArrayInitialize(g_bkb, 0.0);
   ArrayResize(g_ebase, n);  ArrayInitialize(g_ebase, 0.0);
   ArrayResize(g_vbase, n);  ArrayInitialize(g_vbase, 0.0);
   ArrayInitialize(g_dh, 0.0);
   ArrayInitialize(g_t_ms, 0);

   if(InpLogCsv)
   {
      // ONE FILE PER SYMBOL, and shared. A single hardcoded name meant the second chart
      // to load simply lost its logging - which is how SOLUSDTp and ETHUSDTp ended up
      // silently recording nothing.
      string lf = InpLogName;
      int dot = StringFind(lf, ".");
      string stem = (dot > 0) ? StringSubstr(lf, 0, dot) : lf;
      string ext  = (dot > 0) ? StringSubstr(lf, dot)    : ".csv";
      lf = stem + "_" + _Symbol + ext;
      g_log = FileOpen(lf, FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI
                           |FILE_SHARE_READ|FILE_SHARE_WRITE, ',');
      if(g_log != INVALID_HANDLE)
      {
         FileSeek(g_log, 0, SEEK_END);
         if(FileTell(g_log) == 0)
            FileWrite(g_log, "server_time", "local_ms", "symbol", "speed", "speed_base", "speed_sd", "z",
                      "up", "down", "delta", "net_pts", "range_pts", "range_base",
                      "verdict", "side_mode", "bid", "ask", "spread_pts",
                      "book_bid_vol", "book_ask_vol", "touch_consumed_bid",
                      "touch_consumed_ask", "swept_bid", "swept_ask",
                      "run", "flip", "book_total", "book_base", "sec_into_bar", "early",
                      "obi_touch", "obi_deep", "best_bid_vol", "best_ask_vol", "book_levels",
                      "bps", "bps_base", "tps_tick_base", "src", "ticks_1s",
                      "ice_b_cons", "ice_b_repl", "ice_b_peak",
                      "ice_a_cons", "ice_a_repl", "ice_a_peak");
      }
      else Print("[TPS] could not open ", lf, " - logging off this session");
   }

   MqlTick t;
   if(SymbolInfoTick(_Symbol, t)) g_prev_px = (t.bid + t.ask) / 2.0;

   // LEVEL 2. Measured on 164,760 of this broker's ticks: last=0 and volume=0 on 100% of
   // them, so TICK_FLAG_BUY/SELL will never arrive and any price-derived delta correlates
   // +0.49 with the move ALREADY PAST and only +0.03 with the next one. The order book is
   // the only genuinely independent source left - so ask for it, and report honestly
   // whether this broker actually serves it.
   g_dom_ok = MarketBookAdd(_Symbol);
   PrintFormat("[TPS] depth of market on %s: %s", _Symbol,
               g_dom_ok ? "AVAILABLE - true book delta in use"
                        : "NOT AVAILABLE - direction is INFERRED from price and lags it");

   EventSetMillisecondTimer(50);
   Draw();
   PrintFormat("[TPS] v%s on %s - live %dms, baseline %ds, high +%.1fSD, delta %.2f, stall %.2f",
               VER, _Symbol, InpLiveWindowMs, InpBaselineSec, InpHighSigma, InpDeltaStrong, InpStallFactor);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   if(g_dom_ok) MarketBookRelease(_Symbol);
   if(g_log != INVALID_HANDLE) FileClose(g_log);
   g_cv.Destroy();
   ObjectDelete(0, g_obj);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| One tick: store time, price, and which way it went. O(1).         |
//+------------------------------------------------------------------+
void OnTick()
{
   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t)) return;
   double mid = (t.bid + t.ask) / 2.0;

   char side = 0;
   // PREFER THE BROKER'S OWN AGGRESSOR FLAG. Most retail CFD feeds never set these, so
   // this branch simply never fires on such a feed - and the readout says INFER.
   if((t.flags & TICK_FLAG_BUY) != 0)       { side = 1;  g_have_flags = true; }
   else if((t.flags & TICK_FLAG_SELL) != 0) { side = -1; g_have_flags = true; }

   // --- what does this feed actually carry? Counted on real ticks, reported once.
   g_pr_n++;
   if((t.flags & (TICK_FLAG_BUY | TICK_FLAG_SELL)) != 0) g_pr_flag++;
   if(t.last   > 0.0) g_pr_last++;
   if(t.volume > 0)   g_pr_vol++;
   if(!g_pr_said && g_pr_n >= InpProbeTicks)
   {
      g_pr_said = true;
      PrintFormat("[TPS] FEED PROBE on %s after %d ticks: aggressor flags %.1f%%, last price"
                  " %.1f%%, volume %.1f%%.  DOM %s.",
                  _Symbol, (int)g_pr_n, 100.0 * g_pr_flag / g_pr_n,
                  100.0 * g_pr_last / g_pr_n, 100.0 * g_pr_vol / g_pr_n,
                  (g_dom_ok ? "available" : "NOT available"));
      if(g_pr_flag > 0)
         Print("[TPS] -> this feed TAGS THE AGGRESSOR. That is better than a book: the delta is"
               " real, not inferred. Set InpSideMode to FLAGS and re-run the calibration.");
      else if(!g_dom_ok)
         Print("[TPS] -> no flags and no book. DIRECTION CANNOT BE MEASURED on this symbol -"
               " only SPEED is real here. A price-derived delta is a mirror (TICK_SPEED.md s.3),"
               " and SPRING / SWEEP / PREDICT / BREAK all need the book, so none of them can"
               " fire. Use PXBT for book research, or find an Exness symbol that serves DOM.");
   }
   else if(g_prev_px > 0.0)
   {
      if(mid > g_prev_px)      side = 1;
      else if(mid < g_prev_px) side = -1;
   }

   g_t_ms[g_head]   = GetTickCount64();
   g_t_px[g_head]   = mid;
   g_t_side[g_head] = side;
   g_head = (g_head + 1) % TICKBUF;
   g_seen++;
   g_prev_px = mid;
}

//+------------------------------------------------------------------+
//| Everything measured over the last `ms` milliseconds, in one pass.  |
//+------------------------------------------------------------------+
void Window(const ulong now, const ulong ms,
            int &cnt, int &up, int &dn, double &first, double &last, double &hi, double &lo)
{
   cnt = up = dn = 0;
   first = last = hi = lo = 0.0;
   int have = (int)MathMin((long)TICKBUF, g_seen);
   bool init = false;
   for(int i = 1; i <= have; i++)
   {
      int idx = (g_head - i + TICKBUF) % TICKBUF;
      if(now - g_t_ms[idx] > ms) break;   // ring is time-ordered walking backwards
      double p = g_t_px[idx];
      if(!init) { last = p; hi = p; lo = p; init = true; }
      if(p > hi) hi = p;
      if(p < lo) lo = p;
      first = p;                          // keeps moving back, ends on the oldest
      cnt++;
      if(g_t_side[idx] > 0) up++;
      else if(g_t_side[idx] < 0) dn++;
   }
}

//+------------------------------------------------------------------+
//| Book events inside a window - the book-side twin of Window().
//+------------------------------------------------------------------+
int BookWithin(const ulong now, const ulong ms)
{
   int have = (int)MathMin((long)BEVBUF, g_eseen);
   int n = 0;
   for(int i = 1; i <= have; i++)
   {
      int idx = (g_ehead - i + BEVBUF) % BEVBUF;
      if(now - g_e_ms[idx] > ms) break;   // time-ordered walking backwards
      n++;
   }
   return n;
}

//+------------------------------------------------------------------+
//| Level 2, if this broker serves it. Volume resting on each side of the
//| book is independent of price - which is exactly what the inferred
//| delta is not.
//+------------------------------------------------------------------+
void OnBookEvent(const string &symbol)
{
   if(symbol != _Symbol) return;
   MqlBookInfo book[];
   if(!MarketBookGet(_Symbol, book)) return;

   double nb_px[BOOKMAX], na_px[BOOKMAX];
   long   nb_vol[BOOKMAX], na_vol[BOOKMAX];
   int    nnb = 0, nna = 0;
   long   b = 0, a = 0;

   for(int i = 0; i < ArraySize(book); i++)
   {
      bool isBid = (book[i].type == BOOK_TYPE_BUY  || book[i].type == BOOK_TYPE_BUY_MARKET);
      bool isAsk = (book[i].type == BOOK_TYPE_SELL || book[i].type == BOOK_TYPE_SELL_MARKET);
      if(isBid) { b += book[i].volume;
                  if(nnb < BOOKMAX) { nb_px[nnb] = book[i].price; nb_vol[nnb] = book[i].volume; nnb++; } }
      if(isAsk) { a += book[i].volume;
                  if(nna < BOOKMAX) { na_px[nna] = book[i].price; na_vol[nna] = book[i].volume; nna++; } }
   }
   g_dom_bidvol = b; g_dom_askvol = a; g_dom_delta = b - a; g_dom_events++;
   g_e_ms[g_ehead] = GetTickCount64();
   g_ehead = (g_ehead + 1) % BEVBUF;
   g_eseen++;

   // CONSUMPTION: for every level that existed last snapshot, how much size has gone?
   // A level that vanished entirely counts in full. This is the only quantity available
   // here that is NOT derived from price.
   // CAVEAT, and it is a real one: a cancelled order looks identical to a filled one.
   long gone_b = 0, gone_a = 0;
   for(int i = 0; i < g_pnb; i++)
   {
      long now_v = 0;
      for(int j = 0; j < nnb; j++)
         if(MathAbs(nb_px[j] - g_pb_px[i]) < _Point / 2.0) { now_v = nb_vol[j]; break; }
      if(g_pb_vol[i] > now_v) gone_b += (g_pb_vol[i] - now_v);
   }
   for(int i = 0; i < g_pna; i++)
   {
      long now_v = 0;
      for(int j = 0; j < nna; j++)
         if(MathAbs(na_px[j] - g_pa_px[i]) < _Point / 2.0) { now_v = na_vol[j]; break; }
      if(g_pa_vol[i] > now_v) gone_a += (g_pa_vol[i] - now_v);
   }

   // ---- THE TOUCH, measured separately -------------------------------------------------
   // best bid = highest BUY price, best ask = lowest SELL price. Found explicitly rather
   // than relying on MarketBookGet's ordering, which is not guaranteed by the docs.
   double bb = 0.0, ba = 0.0; long bbv = 0, bav = 0;
   for(int i = 0; i < nnb; i++) if(nb_px[i] > bb)              { bb = nb_px[i]; bbv = nb_vol[i]; }
   for(int i = 0; i < nna; i++) if(ba == 0.0 || na_px[i] < ba) { ba = na_px[i]; bav = na_vol[i]; }

   long t_b = 0, t_a = 0, sw_b = 0, sw_a = 0;
   ulong ice_now = GetTickCount64();
   // FIRST SIGHT: seed the peaks, or the opening size is never counted and the ratio is
   // inflated by an under-stated denominator for the whole of the first level after attach.
   if(g_ta_px <= 0.0 && ba > 0.0) { g_ice_a_peak = bav; g_ice_a_t0 = ice_now; }
   if(g_tb_px <= 0.0 && bb > 0.0) { g_ice_b_peak = bbv; g_ice_b_t0 = ice_now; }

   if(g_ta_px > 0.0 && ba > 0.0)
   {
      // UNAMBIGUOUS: same price, less size = someone took it.
      if(MathAbs(ba - g_ta_px) < _Point / 2.0)
      {
         // TIME BOUND. Without this the ratio is eventually met by any level that simply
         // persists - which is exactly what made this fire in 36% of seconds.
         if(g_ice_a_t0 > 0 && ice_now - g_ice_a_t0 > (ulong)InpIcebergWinSec * 1000)
            { g_ice_a_cons = 0; g_ice_a_repl = 0; g_ice_a_peak = bav; g_ice_a_t0 = ice_now; }
         if(bav < g_ta_vol) { t_a = g_ta_vol - bav; g_ice_a_cons += t_a; }
         else if(bav > g_ta_vol) g_ice_a_repl += (bav - g_ta_vol);   // it refilled
         if(bav > g_ice_a_peak) g_ice_a_peak = bav;
      }
      // AMBIGUOUS: the level is gone. Could be swept by a buyer, could be a cancel-and-
      // requote. Counted apart so the two can be told apart later from the log instead of
      // being blended into one number nobody can audit.
      else
      {
         if(ba > g_ta_px) sw_a = g_ta_vol;
         // the level is gone - this iceberg, if it was one, is finished
         g_ice_a_cons = 0; g_ice_a_repl = 0; g_ice_a_peak = bav; g_ice_a_t0 = ice_now;
      }
   }
   if(g_tb_px > 0.0 && bb > 0.0)
   {
      if(MathAbs(bb - g_tb_px) < _Point / 2.0)
      {
         if(g_ice_b_t0 > 0 && ice_now - g_ice_b_t0 > (ulong)InpIcebergWinSec * 1000)
            { g_ice_b_cons = 0; g_ice_b_repl = 0; g_ice_b_peak = bbv; g_ice_b_t0 = ice_now; }
         if(bbv < g_tb_vol) { t_b = g_tb_vol - bbv; g_ice_b_cons += t_b; }
         else if(bbv > g_tb_vol) g_ice_b_repl += (bbv - g_tb_vol);
         if(bbv > g_ice_b_peak) g_ice_b_peak = bbv;
      }
      else
      {
         if(bb < g_tb_px) sw_b = g_tb_vol;
         g_ice_b_cons = 0; g_ice_b_repl = 0; g_ice_b_peak = bbv; g_ice_b_t0 = ice_now;
      }
   }
   // OBI, from the volumes already in hand. Positive = thick floor, thin ceiling = bullish.
   g_bbv = bbv; g_bav = bav;
   g_obi      = (bbv + bav > 0) ? (double)(bbv - bav) / (double)(bbv + bav) : 0.0;
   g_obi_deep = (b + a > 0)     ? (double)(b - a)     / (double)(b + a)     : 0.0;
   g_book_levels = nnb + nna;
   // Reported from the FIRST REAL BOOK EVENT, not from OnInit: MarketBookAdd() is
   // asynchronous, so a probe there reads an empty book and would claim 0 levels on a
   // broker that serves plenty. This line decides whether OBI means anything at all.
   // A BOOK THAT CANNOT CARRY INFORMATION IS NOT A BOOK. Blueberry returns 2 levels with
   // volume 1 on each side forever, which makes OBI identically zero and silently pins every
   // book-derived verdict while the panel still says BOOK. Demote it to tick mode instead.
   if(g_dom_ok && g_pr_n > 200)
   {
      static long seen_max_vol = 0;
      if(bbv > seen_max_vol) seen_max_vol = bbv;
      if(bav > seen_max_vol) seen_max_vol = bav;
      static bool demoted = false;
      if(!demoted && (g_book_levels < InpMinBookLevels || seen_max_vol <= InpMinTouchVol))
      {
         demoted = true; g_dom_ok = false;
         PrintFormat("[TPS] DEMOTING %s to tick mode: %d levels, largest touch volume ever seen"
                     " %d. That is an LP quote, not an order book - OBI would be a constant and"
                     " SPRING / SWEEP / PREDICT / BREAK would be pinned without saying so.",
                     _Symbol, g_book_levels, (int)seen_max_vol);
      }
   }

   static bool said_depth = false;
   if(!said_depth)
   {
      said_depth = true;
      PrintFormat("[TPS] book depth on %s: %d levels (%d bid / %d ask). OBI needs several;"
                  " a 1-2 level book is an LP quote, not an order book.",
                  _Symbol, g_book_levels, nnb, nna);
   }

   // BOTH sides accumulate. An if/else here would let one side always win a tie and skew
   // the delta bar permanently toward that side.
   g_touch_a += t_a; g_touch_b += t_b;
   g_swept_a += sw_a; g_swept_b += sw_b;
   g_tb_px = bb; g_ta_px = ba; g_tb_vol = bbv; g_ta_vol = bav;

   if(t_a > 0 || t_b > 0)
   {
      g_c_ms[g_chead]  = GetTickCount64();
      g_c_bid[g_chead] = t_b;          // volume taken from the BID = aggressive selling
      g_c_ask[g_chead] = t_a;          // volume taken from the ASK = aggressive buying
      g_chead = (g_chead + 1) % CONSBUF;
      g_cseen++;
   }

   // The deep-book totals (gone_b / gone_a) are still computed above and logged, but they
   // no longer drive the delta: levels far from the touch churn with cancellations that are
   // not aggression, and blending them in buried the signal that actually matters.

   for(int i = 0; i < nnb; i++) { g_pb_px[i] = nb_px[i]; g_pb_vol[i] = nb_vol[i]; }
   for(int i = 0; i < nna; i++) { g_pa_px[i] = na_px[i]; g_pa_vol[i] = na_vol[i]; }
   g_pnb = nnb; g_pna = nna;
}

//+------------------------------------------------------------------+
//| Book consumption summed over the live window.                     |
//+------------------------------------------------------------------+
void ConsumedWithin(const ulong now, const ulong ms, long &cb, long &ca)
{
   cb = 0; ca = 0;
   int have = (int)MathMin((long)CONSBUF, g_cseen);
   for(int i = 1; i <= have; i++)
   {
      int idx = (g_chead - i + CONSBUF) % CONSBUF;
      if(now - g_c_ms[idx] > ms) break;
      cb += g_c_bid[idx];
      ca += g_c_ask[idx];
   }
}

//+------------------------------------------------------------------+
void OnTimer()
{
   ulong now = GetTickCount64();
   int cnt, up, dn; double first, last, hi, lo;

   // ADAPTIVE WINDOW. A fixed 2 s window holds ~160 ticks on gold at the open and 0-2 on a
   // slow symbol, where one tick means delta = +/-100%. Widen until there is a sample worth
   // measuring; the market speeding up shrinks it straight back.
   // CLAMPED: a zero window would make the doubling loop below (0*2 = 0) spin forever and
   // the tps division a divide-by-zero. One bad input should not hang the terminal.
   int wfloor = (InpLiveWindowMs < 100) ? 100 : InpLiveWindowMs;
   g_win_ms = (ulong)wfloor;
   Window(now, g_win_ms, cnt, up, dn, first, last, hi, lo);
   // the window must hold enough events of whatever stream is DRIVING the gauge - counting
   // ticks to size a window that is then measured in book events would size it for nothing
   g_win_ev = (g_src == SRC_BOOK) ? BookWithin(now, g_win_ms) : cnt;
   if(InpAutoWindow)
   {
      ulong wmax = (ulong)((InpMaxWindowMs < wfloor) ? wfloor : InpMaxWindowMs);
      while(g_win_ev < InpMinWindowTicks && g_win_ms < wmax)
      {
         g_win_ms *= 2;
         if(g_win_ms > wmax) g_win_ms = wmax;
         Window(now, g_win_ms, cnt, up, dn, first, last, hi, lo);
         g_win_ev = (g_src == SRC_BOOK) ? BookWithin(now, g_win_ms) : cnt;
      }
   }
   // still per SECOND, so needle and baseline stay comparable at any window width
   // the needle shows whatever the z-score is measuring, or the two tell different stories
   if(g_src == SRC_BOOK)
   {
      long wb = 0, wa = 0;
      ConsumedWithin(now, g_win_ms, wb, wa);
      g_tps = (double)(wb + wa) * 1000.0 / (double)g_win_ms;
   }
   else g_tps = g_win_ev * 1000.0 / (double)g_win_ms;
   g_up    = up;
   g_dn    = dn;
   g_delta = (up + dn > 0) ? (double)(up - dn) / (double)(up + dn) : 0.0;

   // THE BOOK WINS WHEN IT EXISTS. ask_consumed means offers were lifted = buying.
   if(g_dom_ok)
   {
      ConsumedWithin(now, g_win_ms, g_cons_b, g_cons_a);
      long tot = g_cons_a + g_cons_b;
      if(tot > 0)
      {
         g_dom_dlt = (double)(g_cons_a - g_cons_b) / (double)tot;
         g_delta   = g_dom_dlt;        // independent of price - the whole point
      }
   }
   double pt = (_Point > 0.0) ? _Point : 0.01;
   g_net_pts   = (cnt > 0) ? (last - first) / pt : 0.0;
   // IN BOOK MODE THE TICK RING IS EMPTY, so the line above returns 0.0 almost always - which
   // made RIDE unreachable and both halves of BREAK trivially true. The mid ring is fed from
   // bid/ask once a second and needs no ticks, so use it when the book is driving the gauge.
   if(g_src == SRC_BOOK && g_mn > 2)
   {
      int back2 = (int)(g_win_ms / 1000);
      if(back2 < 1) back2 = 1;
      if(back2 > g_mn - 1) back2 = g_mn - 1;
      int m1 = (g_mh - 1 + 300) % 300, m2 = (g_mh - 1 - back2 + 300) % 300;
      if(g_midr[m1] > 0.0 && g_midr[m2] > 0.0)
         g_net_pts = (g_midr[m1] - g_midr[m2]) / pt;
   }
   g_range_pts = (cnt > 0) ? (hi - lo) / pt : 0.0;

   //--- once a second: feed both rolling baselines and decide the verdict
   if(now - g_last_sec >= 1000)
   {
      g_last_sec = now;
      int c1, u1, d1; double f1, l1, h1, lo1;
      Window(now, 1000, c1, u1, d1, f1, l1, h1, lo1);

      int e1 = BookWithin(now, 1000);        // clean non-overlapping book-event count
      // BOOK-MODE SPEED IS VOLUME, NOT EVENTS. The event rate is the broker's push cadence -
      // on ETHUSDTp it sits at 9.2/s with sd 1.1 whatever the market does, so a z-score built
      // on it can never reach the action zone. Consumed volume is what actually varies.
      long vb1 = 0, va1 = 0;
      ConsumedWithin(now, 1000, vb1, va1);
      double v1 = (double)(vb1 + va1);

      int n = ArraySize(g_base);
      g_base[g_bhead]  = (double)c1;
      g_ebase[g_bhead] = (double)e1;
      g_vbase[g_bhead] = v1;
      g_rbase[g_bhead] = (c1 > 0) ? (h1 - lo1) / pt : 0.0;
      g_bhead = (g_bhead + 1) % n;
      if(g_bn < n) g_bn++;

      double s = 0.0, es = 0.0, vs = 0.0, rs = 0.0;
      for(int i = 0; i < g_bn; i++)
         { s += g_base[i]; es += g_ebase[i]; vs += g_vbase[i]; rs += g_rbase[i]; }
      g_tmean = s  / g_bn;
      g_emean = es / g_bn;
      g_vmean = vs / g_bn;
      g_range_base = rs / g_bn;
      double v = 0.0, ev = 0.0, vv = 0.0;
      for(int i = 0; i < g_bn; i++)
      {
         double d = g_base[i]  - g_tmean; v  += d * d;
         double e = g_ebase[i] - g_emean; ev += e * e;
         double q = g_vbase[i] - g_vmean; vv += q * q;
      }
      g_tsd = MathSqrt(v  / g_bn);
      g_esd = MathSqrt(ev / g_bn);
      g_vsd = MathSqrt(vv / g_bn);

      // WHICH STREAM DRIVES THE GAUGE. Compared on 300-second BASELINES, not on this second,
      // so the choice cannot flap and corrupt the very baseline it is chosen from.
      int want = (int)InpSpeedSource;
      if(want == SRC_AUTO) want = (g_dom_ok && g_emean > g_tmean) ? SRC_BOOK : SRC_TICKS;
      g_src = want;

      if(g_src == SRC_BOOK) { g_mean = g_vmean; g_sd = g_vsd; }
      else                  { g_mean = g_tmean; g_sd = g_tsd; }
      double cur = (g_src == SRC_BOOK) ? v1 : (double)c1;
      g_z = (g_sd > 1e-9) ? (cur - g_mean) / g_sd : 0.0;
      g_accel  = g_z - g_prev_z;           // rate of change of speed
      g_prev_z = g_z;

      // --- THE SPRING. Loading while OBI sits on one side; FIRES on the cross back.
      // The control said the trigger is the TURN, not the price refusal, so only the turn
      // is tested here.
      // each side loads its OWN coil and bleeds the other - a book flipping between sides is
      // not one sustained compression, which is what the shared counter in v1.28 implied
      if(g_obi <= -InpSpringLoad)
         { g_coilL = MathMin(1.0, g_coilL + 0.12); g_coilR = MathMax(0.0, g_coilR - 0.06); }
      else if(g_obi >= InpSpringLoad)
         { g_coilR = MathMin(1.0, g_coilR + 0.12); g_coilL = MathMax(0.0, g_coilL - 0.06); }
      else
         { g_coilL = MathMax(0.0, g_coilL - 0.06); g_coilR = MathMax(0.0, g_coilR - 0.06); }

      // the LEFT coil was loaded by sellers, so its release throws price UP
      if(g_prev_obi <= -InpSpringFire && g_obi >= InpSpringFire && g_coilL > 0.3)
         { g_spring =  1; g_spring_ms = GetTickCount64(); g_coilL = 0.0; }
      else if(g_prev_obi >= InpSpringFire && g_obi <= -InpSpringFire && g_coilR > 0.3)
         { g_spring = -1; g_spring_ms = GetTickCount64(); g_coilR = 0.0; }
      g_prev_obi = g_obi;
      if(g_spring != 0 && GetTickCount64() - g_spring_ms > (ulong)(InpSignalHoldSec * 1000))
         g_spring = 0;

      // --- burst size vs spread -------------------------------------------------------
      MqlTick qt;
      double midnow = 0.0, spr = 0.0;
      if(SymbolInfoTick(_Symbol, qt) && qt.bid > 0.0 && qt.ask > 0.0)
         { midnow = (qt.bid + qt.ask) / 2.0; spr = qt.ask - qt.bid; }
      if(midnow > 0.0)
      {
         g_midr[g_mh] = midnow;
         g_mh = (g_mh + 1) % 300;
         if(g_mn < 300) g_mn++;
         int back = (InpBurstSec < 1) ? 1 : InpBurstSec;
         if(g_mn > back)
         {
            // mean + 1.28 sd of |move over back seconds| ~ the 90th percentile
            double sm = 0.0, ss = 0.0; int cnt = 0;
            for(int i = 0; i + back < g_mn; i++)
            {
               int a1 = (g_mh - 1 - i + 300) % 300;
               int a2 = (g_mh - 1 - i - back + 300) % 300;
               double dm = MathAbs(g_midr[a1] - g_midr[a2]);
               sm += dm; ss += dm * dm; cnt++;
            }
            if(cnt > 2)
            {
               double mu = sm / cnt;
               double sg = MathSqrt(MathMax(0.0, ss / cnt - mu * mu));
               g_burst = mu + 1.28 * sg;
               // THE COST IS SPREAD + COMMISSION. A raw-spread account shows a spread near
               // zero and charges a commission instead; dividing by spread alone would make
               // edge read in the hundreds and declare every wiggle tradeable.
               double cost = spr + ((InpCommissionPx > 0.0) ? InpCommissionPx : 0.0);
               g_edge = (cost > 1e-12) ? g_burst / cost : 0.0;

               // THE MINIMUM VIABLE HOLD: the shortest horizon whose MEAN move exceeds the
               // round-turn cost. Below it no win rate can pay - not 90%, not 100% - so it is
               // a hard floor on the trade, not a preference. Measured per instrument so none
               // of this is inherited from the feed the thresholds were fitted on.
               g_minhold = 0;
               for(int hh = 1; hh <= 300 && hh < g_mn - 1; hh *= 2)
               {
                  double sm2 = 0.0; int cn2 = 0;
                  for(int q = 0; q + hh < g_mn && q < 290; q++)
                  {
                     int q1 = (g_mh - 1 - q + 300) % 300, q2 = (g_mh - 1 - q - hh + 300) % 300;
                     if(g_midr[q1] > 0.0 && g_midr[q2] > 0.0)
                        { sm2 += MathAbs(g_midr[q1] - g_midr[q2]); cn2++; }
                  }
                  if(cn2 > 10 && sm2 / cn2 > cost) { g_minhold = hh; break; }
               }
            }
         }
      }

      // --- delta history -> run length and flip detection
      // A CLEAN ONE-SECOND DELTA, not the live one. The live delta spans InpLiveWindowMs
      // (2000 ms) but is sampled every 1000 ms, so consecutive samples share half their
      // data and "run" would count the same burst two or three times. Since run >= 3 flips
      // a FADE into a COIL - the opposite trade - that overlap must not reach this.
      double d1s = 0.0;
      if(g_dom_ok)
      {
         long cb1 = 0, ca1 = 0;
         ConsumedWithin(now, 1000, cb1, ca1);
         if(ca1 + cb1 > 0) d1s = (double)(ca1 - cb1) / (double)(ca1 + cb1);
      }
      else if(u1 + d1 > 0) d1s = (double)(u1 - d1) / (double)(u1 + d1);

      g_dh[g_dh_head] = d1s;
      g_dh_head = (g_dh_head + 1) % DHIST;
      if(g_dh_n < DHIST) g_dh_n++;

      int sgn = (d1s >= InpDeltaStrong) ? 1 : ((d1s <= -InpDeltaStrong) ? -1 : 0);
      if(sgn != 0 && sgn == g_run_sign) g_run++;
      else { g_run = (sgn != 0) ? 1 : 0; g_run_sign = sgn; }

      g_flipped = false;
      if(sgn != 0)
      {
         for(int k = 1; k <= MathMin(InpFlipWindow, g_dh_n - 1); k++)
         {
            int idx = (g_dh_head - 1 - k + DHIST) % DHIST;
            double old = g_dh[idx];
            int osg = (old >= InpDeltaStrong) ? 1 : ((old <= -InpDeltaStrong) ? -1 : 0);
            if(osg != 0 && osg != sgn) { g_flipped = true; break; }
         }
      }

      // --- book thickness baseline (the liquidity void is a BOOK fact, not a speed fact)
      g_bookv = (double)(g_dom_bidvol + g_dom_askvol);
      int bn = ArraySize(g_bkb);
      g_bkb[g_bk_head] = g_bookv;
      g_bk_head = (g_bk_head + 1) % bn;
      if(g_bk_n < bn) g_bk_n++;
      double bs = 0.0;
      for(int i = 0; i < g_bk_n; i++) bs += g_bkb[i];
      g_book_base = (g_bk_n > 0) ? bs / g_bk_n : 0.0;

      // --- his "first 15 seconds after the minute rolls over"
      // iTime() returns 0 when the M1 series is not ready, which would make this ~1.8
      // BILLION seconds and put that straight on the display and into the CSV.
      datetime bar0 = iTime(_Symbol, PERIOD_M1, 0);
      int si = (bar0 > 0) ? (int)(TimeCurrent() - bar0) : -1;
      g_sec_into_bar = (si >= 0 && si < 60) ? si : -1;

      g_verdict = Decide();

      if(g_log != INVALID_HANDLE)
      {
         MqlTick t;
         if(SymbolInfoTick(_Symbol, t))
            FileWrite(g_log, TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
                      (string)now, _Symbol,
                      // "speed" must be the quantity g_mean/g_sd/g_z describe. In BOOK mode
                      // that is consumed VOLUME, not ticks - logging c1 here made column 4
                      // disagree with columns 5-7 for every build since v1.19.
                      DoubleToString((g_src == SRC_BOOK) ? v1 : (double)c1, 2),
                      DoubleToString(g_mean, 2), DoubleToString(g_sd, 2),
                      DoubleToString(g_z, 2), (string)g_up, (string)g_dn,
                      DoubleToString(g_delta, 3), DoubleToString(g_net_pts, 0),
                      DoubleToString(g_range_pts, 0), DoubleToString(g_range_base, 1),
                      VerdictName(g_verdict),
                      (g_have_flags ? "FLAGS" : (g_dom_ok ? "BOOK" : "INFER")),
                      DoubleToString(t.bid, _Digits), DoubleToString(t.ask, _Digits),
                      DoubleToString((t.ask - t.bid) / pt, 0),
                      (string)g_dom_bidvol, (string)g_dom_askvol,
                      (string)g_cons_b, (string)g_cons_a,
                      (string)g_swept_b, (string)g_swept_a,
                      (string)g_run, (g_flipped ? "1" : "0"),
                      DoubleToString(g_bookv, 0), DoubleToString(g_book_base, 0),
                      (string)g_sec_into_bar,
                      ((g_sec_into_bar >= 0 && g_sec_into_bar <= InpEarlyWindowSec)
                         ? "1" : "0"),
                      DoubleToString(g_obi, 3), DoubleToString(g_obi_deep, 3),
                      (string)g_bbv, (string)g_bav, (string)g_book_levels,
                      DoubleToString(BookWithin(GetTickCount64(), 1000), 0),
                      DoubleToString(g_emean, 3), DoubleToString(g_tmean, 3),
                      (g_src == SRC_BOOK ? "BOOK" : "TICKS"), (string)c1,
                      (string)g_ice_b_cons, (string)g_ice_b_repl, (string)g_ice_b_peak,
                      (string)g_ice_a_cons, (string)g_ice_a_repl, (string)g_ice_a_peak);
         FileFlush(g_log);
      }

      // TRAPPED SCORE. Must stay INSIDE the per-second gate: the normaliser easings below
      // use a 0.02 coefficient picked for 1 Hz, and running them at the 20 Hz timer rate made
      // their time constant ~2.5s instead of ~50s, so they chased the value and squashed the
      // very score the +FUEL tag is thresholded on.
      {
         int back = (InpTrapSec < 5) ? 5 : InpTrapSec;
         // the consumption ring is finite: a fast book can hold fewer seconds than asked for,
         // and silently truncating would understate CVD with no warning
         if(g_eseen > 0)
         {
            double evps = (g_emean > 0.1) ? g_emean : 1.0;
            int maxSec = (int)(CONSBUF / evps);
            if(back > maxSec)
            {
               static bool said_trap = false;
               if(!said_trap)
               {
                  said_trap = true;
                  PrintFormat("[TPS] trapped look-back clipped %ds -> %ds: the consumption ring"
                              " holds %d events at %.1f/sec", back, maxSec, CONSBUF, evps);
               }
               back = (maxSec < 5) ? 5 : maxSec;
            }
         }
         long qb = 0, qa = 0;
         ConsumedWithin(now, (ulong)back * 1000, qb, qa);
         g_cvd = (double)(qa - qb);
         if(g_mn > back)
         {
            int i1 = (g_mh - 1 + 300) % 300, i2 = (g_mh - 1 - back + 300) % 300;
            if(g_midr[i1] > 0.0 && g_midr[i2] > 0.0)
               g_pch = (g_midr[i1] - g_midr[i2]) / pt;
         }
         g_cvd_n += (MathAbs(g_cvd) - g_cvd_n) * 0.02; if(g_cvd_n < 1.0) g_cvd_n = 1.0;
         g_pch_n += (MathAbs(g_pch) - g_pch_n) * 0.02; if(g_pch_n < 1.0) g_pch_n = 1.0;
         g_trap_raw = g_pch / g_pch_n - g_cvd / g_cvd_n;
         if(g_trap_raw >  2.0) g_trap_raw =  2.0;
         if(g_trap_raw < -2.0) g_trap_raw = -2.0;
      }

      // AN EXPLICIT LIST, NOT A RANGE. The old test was "V_RIDE_UP..V_FADE_DN", written when
      // those were the only four verdicts; every verdict added since fell outside it, so the
      // alert covered the untested ones and was silent on SWEEP, PREDICT and SPRING - the
      // only three with measured forward records. A range re-reads itself every time a
      // #define is added; a list does not.
      bool actionable = (g_verdict == V_SWP_UP  || g_verdict == V_SWP_DN  ||
                         g_verdict == V_PRED_UP || g_verdict == V_PRED_DN);
      if(InpAlertOnSignal && actionable && g_verdict != g_prev_verdict)
         Alert(StringFormat("%s  %s   %.0f %s (%+.1fSD)  OBI %+.2f",
                            _Symbol, VerdictName(g_verdict), g_tps,
                            (g_src == SRC_BOOK ? "vol/s" : "tps"), g_z, g_obi));
      // SPRING is not a verdict - it lives in its own state - so it would never have alerted
      // at all. It is the best-evidenced signal here, so it gets its own edge-triggered alert.
      static int prev_spring = 0;
      if(InpAlertOnSignal && InpShowSpring && g_spring != 0 && g_spring != prev_spring)
         Alert(StringFormat("%s  SPRING %s   OBI %+.2f  edge %.1fx",
                            _Symbol, (g_spring > 0 ? "UP" : "DOWN"), g_obi, g_edge));
      prev_spring = g_spring;
      g_prev_verdict = g_verdict;
   }

   g_needle += (g_tps - g_needle) * 0.35;
   // the bias needle is watched for long stretches, so it is eased harder than the speed was
   double btgt = (g_dom_ok && g_book_levels >= 2) ? (g_obi + g_obi_deep) / 2.0 : 0.0;
   g_bias += (btgt - g_bias) * 0.20;
   g_trap += (g_trap_raw - g_trap) * 0.25;   // visual ease only - the value is per-second

   // SWEEP BIAS. Strain = how far past its own visible size each level has been eaten.
   double clamp = (InpSweepClamp < 1.0) ? 1.0 : InpSweepClamp;
   double sA = (g_ice_a_peak > 0) ? (double)g_ice_a_cons / (double)g_ice_a_peak : 0.0;
   double sB = (g_ice_b_peak > 0) ? (double)g_ice_b_cons / (double)g_ice_b_peak : 0.0;
   if(sA > clamp) sA = clamp;
   if(sB > clamp) sB = clamp;
   double tgt = (sA + sB > 1e-9) ? (sA - sB) / (sA + sB) : 0.0;
   g_swp_bias += (tgt - g_swp_bias) * 0.30;
   // PEAK-HOLD. A 10-lot wall taking a 50-lot order moves the ratio 0 -> 5 in ONE event and the
   // level reset drops it back immediately; without a lingering trace the sweep is never seen.
   if(MathAbs(g_swp_bias) > MathAbs(g_swp_hold)) g_swp_hold = g_swp_bias;
   else g_swp_hold *= 0.97;

   Draw();
}

// The warmup cannot exceed the baseline ring: g_bn caps at its size, so a larger warmup
// would make this permanently false and strand the gauge on WARMING UP. See WarmupTarget().
int  WarmupTarget()
{
   int want = MathMax(5, InpWarmupSec);
   int cap  = MathMax(10, InpBaselineSec);
   return (want > cap) ? cap : want;
}
bool Ready() { return g_bn >= WarmupTarget(); }

//+------------------------------------------------------------------+
//| His summary table, in code.                                       |
//+------------------------------------------------------------------+
int Decide()
{
   if(!Ready())                 return V_WARMUP;

   // DEAD-MARKET GUARDS. See the header note - these exist because the gauge once read
   // "0 /s", "+2.7 SD" and "FADE DOWN" in the same frame on a shut market.
   if(g_mean < InpMinBaseTps)             return V_QUIET;   // nothing is trading
   if(g_sd   < InpMinBaseSd)              return V_QUIET;   // z would divide by ~nothing
   // count the stream that is driving the gauge, not always ticks: on a throttled feed the
   // tape can be dead while the book is busy, and the tick count would veto a live book
   int sample = (g_src == SRC_BOOK) ? g_win_ev : (g_up + g_dn);
   if(sample < InpMinWindowTicks)         return V_QUIET;   // sample too small to have a side

   if(g_z < 1.0)                return V_NOTRADE;   // "Low -> NO TRADE (fake move)"

   // ---- THE PATH OF LEAST RESISTANCE ------------------------------------------------------
   // Engine (delta: aggressive orders arriving) matched with friction (OBI: resting orders
   // in the way). Buyers pushing into an ask side that has been emptied has nowhere to go but
   // up. Checked before the stall family because this is what RESOLVES a stall - it is the
   // moment the wall breaks, not another description of the wall.
   // BOTH the touch and the deep book must agree: the touch alone flickers with every pulled
   // quote, and this broker's book is its own liquidity pool, not a central exchange.
   if(g_dom_ok && g_z >= InpPredSigma && g_book_levels >= 2)
   {
      bool wallGoneUp = (g_obi >  InpObiTrigger) && (g_obi_deep >  InpObiTrigger * 0.5);
      bool wallGoneDn = (g_obi < -InpObiTrigger) && (g_obi_deep < -InpObiTrigger * 0.5);
      if(g_delta >=  InpDeltaStrong && wallGoneUp) return V_PRED_UP;
      if(g_delta <= -InpDeltaStrong && wallGoneDn) return V_PRED_DN;
   }

   // ---- ICEBERG / RELOAD ------------------------------------------------------------------
   // If a price level has absorbed far more than it ever VISIBLY held, and has been refilled
   // while doing so, size is hidden there. Ranked below PREDICT on purpose: PREDICT is 10-for-10
   // and this has no forward evidence yet.
   if(g_dom_ok && g_book_levels >= 2)
   {
      // NO repl gate: refill never reaches even 0.75 of consumption on this feed, so the
      // "reloading buyer" it was meant to confirm does not exist here. What IS here is a
      // sweep - the level being eaten - and it continues in the direction of the eating.
      bool swpAsk = (g_ice_a_peak >= InpIcebergMinVol) &&
                    (g_ice_a_cons > (double)g_ice_a_peak * InpIcebergRatio);
      bool swpBid = (g_ice_b_peak >= InpIcebergMinVol) &&
                    (g_ice_b_cons > (double)g_ice_b_peak * InpIcebergRatio);
      // buyers eating the ask push price UP - and this half LEADS price
      if(InpShowSweepUp && swpAsk && (!InpIceNeedDelta || g_delta >=  InpDeltaStrong))
         return V_SWP_UP;
      // sellers eating the bid push price DOWN - but this half only MIRRORS it
      if(InpShowSweepDn && swpBid && (!InpIceNeedDelta || g_delta <= -InpDeltaStrong))
         return V_SWP_DN;
   }

   if(g_z < InpHighSigma)       return V_WATCH;     // moving, but not his action zone

   // ABSORPTION FAMILY: speed is extreme and price has STOPPED travelling. Judged against
   // the rolling range baseline, because a 20-point range is a stall at the NY open and a
   // stampede at 3am - the same reason the speed zones are not fixed either.
   bool stalling = (g_range_base >= InpMinRangeBase) &&
                   (g_range_pts < InpStallFactor * g_range_base);

   if(stalling)
   {
      // 2. EARLY WICK - the attack COLLAPSED. Delta flipped while price was pinned and the
      //    needle is at the extreme. The new delta direction is the way it goes.
      if(g_flipped && g_z >= InpWickSigma)
      {
         if(g_delta >=  InpDeltaStrong) return V_WICK_UP;
         if(g_delta <= -InpDeltaStrong) return V_WICK_DN;
      }
      // 1. COILED SPRING - the attack is STILL ON. Same side held for InpCoilMinRun seconds
      //    while price cannot advance: the wall is being eaten, break goes WITH the delta.
      //    NOTE this is the OPPOSITE call to the generic fade below, and the run length is
      //    the only thing separating them.
      if(g_run >= InpCoilMinRun)
      {
         if(g_delta >=  InpDeltaStrong) return V_COIL_UP;
         if(g_delta <= -InpDeltaStrong) return V_COIL_DN;
      }
      // generic absorption, when neither pattern is established
      if(g_delta >=  InpDeltaStrong) return V_FADE_DN;
      if(g_delta <= -InpDeltaStrong) return V_FADE_UP;
      return V_MIXED;
   }

   // 3. MOMENTUM IGNITION - one-sided flow into a THIN book. "no buy limit orders to stop
   //    them" is a statement about resting liquidity, so it is measured from the book, not
   //    inferred from a quiet tick rate.
   bool thin = (g_book_base > 0.0) && (g_bookv < InpThinBookPct * g_book_base);
   if(thin && MathAbs(g_delta) >= InpVacuumDelta)
      return (g_delta > 0) ? V_VAC_UP : V_VAC_DN;

   // RIDE: one-sided flow AND price actually travelling that way.
   if(g_delta >=  InpDeltaStrong && g_net_pts > 0.0) return V_RIDE_UP;
   if(g_delta <= -InpDeltaStrong && g_net_pts < 0.0) return V_RIDE_DN;

   // PEAK SPEED MUST NOT BE SILENT. Above InpHighSigma the delta goes two-sided (everyone is
   // trading) so RIDE can never fire and MIXED was returned 21 times out of 21 at z >= 3.
   // Direction here comes from the book and from where price has actually travelled in the
   // window - measured at 88% agreement with the next 3 s at z >= 2, against delta's 25%.
   // COINCIDENT, NOT PREDICTIVE: OBI matches the PAST move slightly better than the next one.
   if(g_z >= InpHighSigma && g_dom_ok && g_book_levels >= 2)
   {
      if(g_obi >  InpObiTrigger * 0.5 && g_net_pts >= 0.0) return V_BRK_UP;
      if(g_obi < -InpObiTrigger * 0.5 && g_net_pts <= 0.0) return V_BRK_DN;
   }
   return V_MIXED;
}

string VerdictName(int v)
{
   switch(v)
   {
      case V_NOTRADE: return "NO TRADE";
      case V_WATCH:   return "WATCH";
      case V_RIDE_UP: return "RIDE UP";
      case V_RIDE_DN: return "RIDE DOWN";
      case V_FADE_UP: return "FADE UP (absorb)";
      case V_FADE_DN: return "FADE DOWN (absorb)";
      case V_MIXED:   return "MIXED";
      case V_QUIET:   return "TOO QUIET";
      case V_COIL_UP: return "COIL -> UP";
      case V_COIL_DN: return "COIL -> DOWN";
      case V_WICK_UP: return "WICK -> UP";
      case V_WICK_DN: return "WICK -> DOWN";
      case V_VAC_UP:  return "IGNITION UP";
      case V_VAC_DN:  return "IGNITION DOWN";
      case V_PRED_UP: return "PREDICT UP";
      case V_PRED_DN: return "PREDICT DOWN";
      case V_BRK_UP:  return "BREAK UP";
      case V_BRK_DN:  return "BREAK DOWN";
      case V_SWP_UP:  return "SWEEP UP";
      case V_SWP_DN:  return "SWEEP DOWN";
   }
   return "WARMING UP";
}

//+------------------------------------------------------------------+
//| PASSIVE ABSORPTION, as Zee described it: a heavy wall on one side that price refuses to
//| move toward. +1 = heavy SELL wall and price has not fallen (his bullish case), -1 = the
//| mirror, 0 = neither. Measured on ETHUSDTp it is INVERTED - see the header of this version
//| and TICK_SPEED.md section 37 - which is why it ships behind InpShowAbsorb = false.
//+------------------------------------------------------------------+
int AbsorbState()
{
   int back = (InpAbsorbLookSec < 1) ? 1 : InpAbsorbLookSec;
   if(g_mn <= back) return 0;
   int inow = (g_mh - 1 + 300) % 300;
   int ithen = (g_mh - 1 - back + 300) % 300;
   double now = g_midr[inow], then = g_midr[ithen];
   if(now <= 0.0 || then <= 0.0) return 0;
   if(g_obi <= -0.5 && g_obi_deep <= -0.3 && now >= then) return  1;  // sell wall, no drop
   if(g_obi >=  0.5 && g_obi_deep >=  0.3 && now <= then) return -1;  // buy wall, no rise
   return 0;
}

//+------------------------------------------------------------------+
double FullScale()
{
   double fs = g_mean + 3.0 * g_sd;
   if(fs < 1.0) fs = 1.0;
   if(g_tps > fs) fs = g_tps;
   return fs;
}

double AngleFor(double value, double fs)
{
   double f = (fs > 0.0) ? value / fs : 0.0;
   if(f < 0.0) f = 0.0;
   if(f > 1.0) f = 1.0;
   return (SWEEP_FROM + (SWEEP_TO - SWEEP_FROM) * f) * M_PI / 180.0;
}

//+------------------------------------------------------------------+
void Draw()
{
   g_cv.Erase(ColorToARGB(clrBlack, 200));
   double fs = FullScale();

   uint cDead = ColorToARGB(clrDimGray,     255);
   uint cNorm = ColorToARGB(C'60,140,200',  255);
   uint cElev = ColorToARGB(clrGoldenrod,   255);
   uint cHigh = ColorToARGB(clrOrangeRed,   255);
   uint cUp   = ColorToARGB(C'0,200,110',   255);
   uint cDn   = ColorToARGB(C'225,60,60',   255);
   uint cText = ColorToARGB(clrWhite,       255);
   uint cDim  = ColorToARGB(clrSilver,      255);

   //--- THE BIAS BAND. Left half = SELL side, right half = BUY side, neutral in the middle.
   //--- f runs 0..1 left to right, so bias = 2f - 1.
   int steps = (int)MathMax(120, InpRadius * 3);
   for(int d = 0; d <= steps; d++)
   {
      double f   = (double)d / (double)steps;
      double bv  = 2.0 * f - 1.0;              // -1 at the left end, +1 at the right
      double a   = (SWEEP_FROM + (SWEEP_TO - SWEEP_FROM) * f) * M_PI / 180.0;
      uint c = ColorToARGB(C'55,55,62', 255);  // the neutral middle
      if(!Ready())                 c = cDead;
      else if(bv <= -0.60)         c = ColorToARGB(C'200,45,45', 255);
      else if(bv <= -0.25)         c = ColorToARGB(C'130,55,55', 255);
      else if(bv >=  0.60)         c = ColorToARGB(C'0,175,95',  255);
      else if(bv >=  0.25)         c = ColorToARGB(C'35,110,75', 255);
      g_cv.LineThick(g_cx + (int)((InpRadius - SC(2))  * cos(a)),
                     g_cy - (int)((InpRadius - SC(2))  * sin(a)),
                     g_cx + (int)((InpRadius - SC(13)) * cos(a)),
                     g_cy - (int)((InpRadius - SC(13)) * sin(a)),
                     c, SC(3), STYLE_SOLID, LINE_END_BUTT);
   }

   //--- centre (balanced book) and the two OBI trigger levels PREDICT actually uses
   for(int m = 0; m < 3; m++)
   {
      double bv = (m == 0) ? 0.0 : ((m == 1) ? InpObiTrigger : -InpObiTrigger);
      double f  = (bv + 1.0) / 2.0;
      double a  = (SWEEP_FROM + (SWEEP_TO - SWEEP_FROM) * f) * M_PI / 180.0;
      uint   c  = (m == 0) ? cDim : ((m == 1) ? cUp : cDn);
      int    ln = (m == 0) ? SC(34) : SC(28);
      g_cv.LineThick(g_cx + (int)((InpRadius - SC(15)) * cos(a)), g_cy - (int)((InpRadius - SC(15)) * sin(a)),
                     g_cx + (int)((InpRadius - ln)     * cos(a)), g_cy - (int)((InpRadius - ln)     * sin(a)),
                     c, SC(2), STYLE_SOLID, LINE_END_BUTT);
   }

   //--- needle = the BIAS. Left is sell pressure, right is buy pressure.
   double bf = (g_bias + 1.0) / 2.0;
   if(bf < 0.0) bf = 0.0; if(bf > 1.0) bf = 1.0;
   double an = (SWEEP_FROM + (SWEEP_TO - SWEEP_FROM) * bf) * M_PI / 180.0;
   uint cn = cDead;
   if(Ready())
   {
      cn = cText;
      if(g_bias >=  0.25) cn = cUp;
      if(g_bias <= -0.25) cn = cDn;
   }
   g_cv.LineThick(g_cx, g_cy,
                  g_cx + (int)((InpRadius - SC(22)) * cos(an)),
                  g_cy - (int)((InpRadius - SC(22)) * sin(an)),
                  cn, SC(4), STYLE_SOLID, LINE_END_ROUND);
   g_cv.FillCircle(g_cx, g_cy, SC(7), cn);

   //--- THE TWO COILS. Each sits on the side that COMPRESSES it and throws price the other
   //--- way, which is what a spring does. LEFT loaded by sellers -> fires LONG. RIGHT loaded
   //--- by buyers -> fires SHORT. The load % is per side, so it is never ambiguous which one
   //--- is winding up - the single shared coil of v1.28 could not say.
   if(InpShowSpring && g_spw > 0)
   {
      for(int sideIdx = 0; sideIdx < 2; sideIdx++)
      {
         bool   isLeft = (sideIdx == 0);
         int    sx     = isLeft ? (g_spw / 2) : (g_w - g_spw / 2);
         double load   = isLeft ? g_coilL : g_coilR;
         bool   fired  = isLeft ? (g_spring > 0) : (g_spring < 0);
         uint   fireC  = isLeft ? cUp : cDn;

         int bot = g_cy + SC(30), top = SC(34);
         int span = bot - top;
         if(fired) load = 0.0;                       // snaps open when it goes
         int hh = (int)(span * (1.0 - 0.55 * load));
         int y0 = bot - hh;

         // HUE = the trade it will fire. BRIGHTNESS = how loaded it is. The old scheme spent
         // the hue on load (which the % already states) and only revealed direction in the
         // instant of firing - too late to be ready for it.
         uint cc;
         if(fired)
            cc = isLeft ? ColorToARGB(C'140,255,195', 255) : ColorToARGB(C'255,150,150', 255);
         else if(load > 0.60)
            cc = isLeft ? ColorToARGB(C'0,205,115', 255)   : ColorToARGB(C'230,65,65', 255);
         else if(load > 0.25)
            cc = isLeft ? ColorToARGB(C'0,140,80', 255)    : ColorToARGB(C'160,45,45', 255);
         else if(load > 0.05)
            cc = isLeft ? ColorToARGB(C'22,80,55', 255)    : ColorToARGB(C'95,38,38', 255);
         else
            cc = ColorToARGB(C'48,48,55', 255);

         int coils = 9, amp = g_spw / 2 - SC(5);
         for(int k = 0; k < coils; k++)
         {
            int ya = y0 + (int)(hh * (double)k / coils);
            int yb = y0 + (int)(hh * (double)(k + 1) / coils);
            int xa = sx + ((k % 2 == 0) ? -amp : amp);
            int xb = sx + ((k % 2 == 0) ?  amp : -amp);
            g_cv.LineThick(xa, ya, xb, yb, cc, SC(2), STYLE_SOLID, LINE_END_ROUND);
         }
         g_cv.LineThick(sx - amp, bot, sx + amp, bot, cDim, SC(3), STYLE_SOLID, LINE_END_BUTT);
         g_cv.LineThick(sx - amp, y0,  sx + amp, y0,  cc,   SC(3), STYLE_SOLID, LINE_END_BUTT);

         // LABELLED BY THE TRADE, NOT BY THE WALL. The cause (a sell wall compresses the
         // left spring) is true but it is a noun the reader has to translate mid-trade, and
         // it made "SELL WALL" sit beside "FAVOURS BUY" looking like a contradiction when the
         // two gauges agreed. The cause lives in TICK_SPEED.md; the dial carries the action.
         uint lblC = (load > 0.05 || fired) ? cc : cDead;
         g_cv.FontSet("Consolas", FS(10), FW_BOLD);
         g_cv.TextOut(sx, top - SC(14), isLeft ? "BUY" : "SELL", lblC, TA_CENTER | TA_TOP);

         g_cv.FontSet("Consolas", FS(8), FW_BOLD);
         g_cv.TextOut(sx, bot + SC(5),
                      fired ? (isLeft ? "BUY NOW!" : "SELL NOW!")
                            : StringFormat("%.0f%%", load * 100.0),
                      cc, TA_CENTER | TA_TOP);
      }
   }

   //--- speed readout
   g_cv.FontSet("Consolas", FS(19), FW_BOLD);
   uint bc = (g_bias >= 0.25) ? cUp : ((g_bias <= -0.25) ? cDn : cDim);
   g_cv.TextOut(g_cx, g_cy + SC(12), StringFormat("%+.2f", g_bias), bc, TA_CENTER | TA_TOP);

   g_cv.FontSet("Consolas", FS(11), FW_NORMAL);
   string zone = "WARMING UP";
   uint   zc   = cDead;
   if(Ready())
   {
      if(!g_dom_ok || g_book_levels < 2) { zone = "NO BOOK - NO BIAS"; zc = cDead; }
      else if(g_bias <= -0.60) { zone = "SELL SIDE - HEAVY"; zc = cDn; }
      else if(g_bias <= -0.25) { zone = "SELL SIDE";         zc = cDn; }
      else if(g_bias >=  0.60) { zone = "BUY SIDE - HEAVY";  zc = cUp; }
      else if(g_bias >=  0.25) { zone = "BUY SIDE";          zc = cUp; }
      else                     { zone = "BALANCED";          zc = cDim; }
   }
   g_cv.TextOut(g_cx, g_cy + SC(40), zone, zc, TA_CENTER | TA_TOP);

   //--- THE SPEED BAR, 0-100. The dial carries OBI now, so showing OBI here too would be the
   //--- same number twice. Speed is a TRIGGER, not a direction - a bar is the honest shape for
   //--- it: it fills, and above the +2 SD mark it is worth looking at the dial.
   int barW = InpRadius * 2 - SC(28);
   int barH = SC(16);
   int barX = g_cx - barW / 2;
   int barY = g_cy + SC(58);
   g_cv.FillRectangle(barX, barY, barX + barW, barY + barH, ColorToARGB(C'35,35,40', 255));
   // THE BAR AND ITS LABELS MUST DESCRIBE THE SAME MEASUREMENT. g_delta comes from the
   // BOOK when DOM is live, so gating and labelling it with TICK counts put +80%% on the bar
   // and "12 dn / up 14" (=+7.7%%) underneath it - two numbers for one thing, and no way to
   // tell which one the verdict used.
   double pct = (fs > 0.0) ? 100.0 * g_needle / fs : 0.0;
   if(pct < 0.0) pct = 0.0; if(pct > 100.0) pct = 100.0;
   uint pcol = cNorm;
   if(!Ready())                    pcol = cDead;
   else if(g_z >= InpHighSigma)    pcol = cHigh;
   else if(g_z >= 1.0)             pcol = cElev;
   else if(g_z <= -InpLowSigma)    pcol = cDead;
   g_cv.FillRectangle(barX, barY, barX + (int)(barW * pct / 100.0), barY + barH, pcol);
   // where +2 SD sits on this bar - above it, the dial is worth reading
   if(Ready() && fs > 0.0)
   {
      double hf = (g_mean + InpHighSigma * g_sd) / fs;
      if(hf > 0.0 && hf < 1.0)
      {
         int hx = barX + (int)(barW * hf);
         g_cv.Line(hx, barY - SC(3), hx, barY + barH + SC(3), cHigh);
      }
   }
   g_cv.FontSet("Consolas", FS(10), FW_NORMAL);
   // label with whatever actually drove the bar
   // "hit"/"lift" not "bid"/"ask": these are volumes CONSUMED, while the OBI field two lines
   // below is volume RESTING. Labelling both by side invites reading one as the other.
   // ends = the RESTING walls the bar is made of; centre = OBI, and the delta that was the
   // bar until v1.20, kept visible because it is still filter 2 of the checklist
   // ONE line, not three. Three labels on a 271px strip collided at both ends on his screen
   // ("0 v/SPEED 0/100  -0.2 SID+14%"); shrinking the font cannot fix a width overrun, it only
   // delays it. 22 chars at FS(9) is 218px of 271 at R=160 and 315px of 398 at R=235.
   g_cv.TextOut(g_cx, barY + barH + SC(3),
                StringFormat("%.0f%s %.0f/100 %+.1fSD %+.0f%%",
                             g_tps, (g_src == SRC_BOOK ? "v/s" : "/s"), pct, g_z, g_delta * 100.0),
                cText, TA_CENTER | TA_TOP);

   //--- THE VERDICT - his summary table, one line
   uint vc = cDim;
   if(g_verdict == V_RIDE_UP || g_verdict == V_FADE_UP ||
      g_verdict == V_COIL_UP || g_verdict == V_WICK_UP || g_verdict == V_VAC_UP ||
      g_verdict == V_PRED_UP || g_verdict == V_BRK_UP ||
      g_verdict == V_SWP_UP) vc = cUp;
   if(g_verdict == V_RIDE_DN || g_verdict == V_FADE_DN ||
      g_verdict == V_COIL_DN || g_verdict == V_WICK_DN || g_verdict == V_VAC_DN ||
      g_verdict == V_PRED_DN || g_verdict == V_BRK_DN ||
      g_verdict == V_SWP_DN) vc = cDn;
   if(g_verdict == V_NOTRADE || g_verdict == V_WARMUP)  vc = cDead;
   g_cv.FontSet("Consolas", FS(15), FW_BOLD);
   g_cv.TextOut(g_cx, barY + barH + SC(86) + (g_swr > 0 ? g_swr + SC(16) : 0), VerdictName(g_verdict), vc, TA_CENTER | TA_TOP);

   //--- THE PATH LINE: the ENGINE and the FRICTION combined into an actual conclusion.
   //--- Without this the gauge shows "+87%" next to "OBI -0.57" and leaves the reader to work
   //--- out that those two disagree. OBI > 0 = thick bid / thin ask = the way UP is clear.
   //--- THE MASTER SIGNAL BAND: his 3-filter checklist as ONE word and ONE colour, so the
   //--- five numbers above it never have to be read together in a hurry.
   //---   1 VELOCITY  z >= InpSigGoSigma
   //---   2 PRESSURE  |delta| >= InpSigDelta
   //---   3 FRICTION  OBI (touch AND deep) clear in the SAME direction as the pressure
   string sig = "WAIT";
   uint   sbg = ColorToARGB(C'45,45,52',   255);
   uint   stx = cDim;

   if(!Ready())
   {
      sig = "WARMING UP";
   }
   else if(g_verdict == V_QUIET)
   {
      // the dead-market floors outrank everything: with sd ~ 0 the z-score is meaningless,
      // so no signal built on it may be shown. This is the v1.06 lesson, kept.
      sig = "TOO QUIET";
      sbg = ColorToARGB(C'35,35,40', 255);
   }
   else
   {
      // LATCH: PREDICT is the only thing in this build with a track record (10 firings across
      // two logs, wrong zero times at 1 s, 3 s and 10 s) and it was flashing for a single
      // second on the small verdict line while this band said WAIT. It owns the band now, and
      // it stays up long enough to be acted on.
      ulong nowms = GetTickCount64();
      if(g_verdict == V_PRED_UP || g_verdict == V_PRED_DN)
         { g_sig_latch = g_verdict; g_sig_ms = nowms; }
      if(g_verdict == V_SWP_UP || g_verdict == V_SWP_DN)
      {
         if(g_swp_latch == 0) g_exit_ms = nowms;   // a NEW sweep starts the exit clock
         g_swp_latch = g_verdict; g_swp_ms = nowms;
      }
      g_swp_left = 0;
      if(g_swp_latch != 0)
      {
         g_swp_left = InpSignalHoldSec - (int)((nowms - g_swp_ms) / 1000);
         if(g_swp_left <= 0) { g_swp_latch = 0; g_swp_left = 0; }
      }
      int holdLeft = 0;
      if(g_sig_latch != 0)
      {
         int age = (int)((nowms - g_sig_ms) / 1000);
         holdLeft = InpSignalHoldSec - age;
         if(holdLeft <= 0) { g_sig_latch = 0; holdLeft = 0; }
      }

      // A PERFECT SIGNAL ON A MOVE SMALLER THAN THE SPREAD IS A GUARANTEED LOSS. Measured on
      // ETHUSDTp: PREDICT UP was right 11 times out of 11 (p=0.001) and buying the ask then
      // selling the bid 10 s later lost on ALL ELEVEN - spread 1.310, median move 0.090.
      bool canPay = (g_edge >= InpMinEdgeRatio);

      bool haveBook = (g_dom_ok && g_book_levels >= 2);
      bool fastOk   = (g_z >= InpSigGoSigma);
      bool pushUp   = (g_delta >=  InpSigDelta);
      bool pushDn   = (g_delta <= -InpSigDelta);
      bool clearUp  = haveBook && (g_obi >=  InpSigObi) && (g_obi_deep >=  InpSigObiDeep);
      bool clearDn  = haveBook && (g_obi <= -InpSigObi) && (g_obi_deep <= -InpSigObiDeep);
      bool wallUp   = haveBook && (g_obi <= -InpSigObiDeep);   // pushing up into a thick ask
      bool wallDn   = haveBook && (g_obi >=  InpSigObiDeep);   // pushing down into a thick bid

      // with the guard OFF the signal still shows - but never cleanly. thin() mutes the
      // colour and the label carries the ratio, so an un-payable edge cannot look confident.
      bool thin = (g_edge > 0.0 && !canPay);
      string tag = thin ? StringFormat("  %.1fx", g_edge) : "";

      // SPRING FIRST: 91% at 10 s on the clean subset, p=0.0001, 36 independent episodes, and
      // the only signal in this build that passes the mirror test. TICK_SPEED.md section 38.
      if(InpShowSpring && g_spring != 0)
      {
         sig = (g_spring > 0) ? "SPRING UP" : "SPRING DOWN";
         if(thin) sig += tag;
         if(g_spring > 0) sbg = thin ? ColorToARGB(C'0,85,45',255)  : ColorToARGB(C'0,165,85',255);
         else             sbg = thin ? ColorToARGB(C'110,30,30',255): ColorToARGB(C'205,45,45',255);
         stx = ColorToARGB(clrWhite, 255);
      }
      else if(InpSpreadGuard && thin)
      {
         sig = StringFormat("SPREAD TOO WIDE %.1fx", g_edge);
         sbg = ColorToARGB(C'70,35,35', 255); stx = ColorToARGB(clrWhite, 255);
      }
      else if(g_sig_latch == V_PRED_UP)
      {
         sig = StringFormat("BUY NOW  %d%s", holdLeft, tag);
         sbg = thin ? ColorToARGB(C'0,80,45', 255) : ColorToARGB(C'0,150,75', 255);
         stx = thin ? ColorToARGB(C'170,200,180', 255) : ColorToARGB(clrWhite, 255);
      }
      else if(g_sig_latch == V_PRED_DN)
      {
         sig = StringFormat("SELL NOW  %d%s", holdLeft, tag);
         sbg = thin ? ColorToARGB(C'105,30,30', 255) : ColorToARGB(C'190,40,40', 255);
         stx = thin ? ColorToARGB(C'215,180,180', 255) : ColorToARGB(clrWhite, 255);
      }
      // a reloading hidden order. NOT "BUY NOW" - it has no forward record yet.
      // peak-speed direction. Deliberately NOT "BUY NOW": this says the burst is going up
      // right now, not that it will continue. Coincident, and labelled so.
      else if(g_verdict == V_BRK_UP)
      {
         sig = "BREAK UP";   sbg = ColorToARGB(C'0,120,180', 255); stx = ColorToARGB(clrWhite, 255);
      }
      else if(g_verdict == V_BRK_DN)
      {
         sig = "BREAK DOWN"; sbg = ColorToARGB(C'170,70,20', 255); stx = ColorToARGB(clrWhite, 255);
      }
      // the 3-filter checklist is demoted: it has NO track record, PREDICT has one
      else if(fastOk && pushUp && clearUp)
      {
         sig = "LEAN BUY";  sbg = ColorToARGB(C'0,95,50',  255); stx = ColorToARGB(clrWhite, 255);
      }
      else if(fastOk && pushDn && clearDn)
      {
         sig = "LEAN SELL"; sbg = ColorToARGB(C'120,30,30', 255); stx = ColorToARGB(clrWhite, 255);
      }
      else if((pushUp && wallUp) || (pushDn && wallDn))
      {
         // NOT the catch-all: this means the push and the book actively FIGHT each other
         sig = "BLOCKED";  sbg = ColorToARGB(C'150,115,15', 255); stx = ColorToARGB(clrWhite, 255);
      }
      else if(!haveBook) sig = "WAIT - NO BOOK";
      // ABSORPTION - OFF by default. The hit rate is in the label on purpose: this measured
      // 14% at 3 s against a 52% base rate, i.e. it is inverted, and it must not be possible
      // to look at this overlay without seeing that.
      else if(InpShowAbsorb && haveBook && g_mn > InpAbsorbLookSec && AbsorbState() != 0)
      {
         int ab = AbsorbState();
         sig = (ab > 0) ? "ABSORB BUY? 14%" : "ABSORB SELL? 9%";
         sbg = ColorToARGB(C'60,60,95', 255); stx = ColorToARGB(C'190,190,215', 255);
      }
      // THIN BOOK - OFF by default. +1 point of lift at 1 s, negative beyond it.
      else if(InpShowThin && haveBook && g_book_base > 0.0 &&
              g_bookv < InpThinAlertPct * g_book_base)
      {
         sig = StringFormat("THIN BOOK %.2fx", g_bookv / g_book_base);
         sbg = ColorToARGB(C'95,75,30', 255); stx = ColorToARGB(C'225,210,180', 255);
      }
      else if(!fastOk)   sig = "WAIT - SLOW";
      else               sig = "WAIT";
   }

   int sigY = barY + barH + SC(20);
   int sigH = SC(30);
   g_cv.FillRectangle(barX, sigY, barX + barW, sigY + sigH, sbg);
   g_cv.FontSet("Consolas", FS(18), FW_BOLD);
   g_cv.TextOut(g_cx, sigY + sigH / 2, sig, stx, TA_CENTER | TA_VCENTER);

   //--- THE SWEEP DIAL. Left = the BID being eaten (sell pressure), right = the ASK being
   //--- eaten (buy pressure). The RIGHT half is drawn in full colour because section 42
   //--- measured it LEADING price (fwd 87.6 vs bwd 64.9); the LEFT half is MUTED because it
   //--- mirrors (fwd 76.6 vs bwd 78.0). The needle swings both ways - the dial just refuses to
   //--- give a lagging half the same visual weight as a leading one.
   int swDialBot = sigY + sigH + SC(6);
   if(g_swr > 0)
   {
      int gap2 = InpTrapDial ? (g_swr + SC(8)) : 0;
      int cx2 = g_cx - gap2, cy2 = swDialBot + g_swr;
      int st2 = (int)MathMax(90, g_swr * 3);
      for(int d2 = 0; d2 <= st2; d2++)
      {
         double f2 = (double)d2 / (double)st2;
         double bv2 = 2.0 * f2 - 1.0;
         double a2 = (SWEEP_FROM + (SWEEP_TO - SWEEP_FROM) * f2) * M_PI / 180.0;
         uint c2 = ColorToARGB(C'45,45,52', 255);
         if(bv2 >=  0.55)      c2 = ColorToARGB(C'0,185,100', 255);   // validated half
         else if(bv2 >=  0.20) c2 = ColorToARGB(C'25,105,70',  255);
         else if(bv2 <= -0.55) c2 = ColorToARGB(C'105,55,55',  255);  // mirror half, muted
         else if(bv2 <= -0.20) c2 = ColorToARGB(C'70,45,48',   255);
         g_cv.LineThick(cx2 + (int)((g_swr - SC(1)) * cos(a2)), cy2 - (int)((g_swr - SC(1)) * sin(a2)),
                        cx2 + (int)((g_swr - SC(7)) * cos(a2)), cy2 - (int)((g_swr - SC(7)) * sin(a2)),
                        c2, SC(2), STYLE_SOLID, LINE_END_BUTT);
      }
      // peak-hold trace, so a snap that has already passed is still visible
      double hf = (g_swp_hold + 1.0) / 2.0;
      if(hf < 0.0) hf = 0.0; if(hf > 1.0) hf = 1.0;
      double ah = (SWEEP_FROM + (SWEEP_TO - SWEEP_FROM) * hf) * M_PI / 180.0;
      g_cv.LineThick(cx2 + (int)((g_swr - SC(8))  * cos(ah)), cy2 - (int)((g_swr - SC(8))  * sin(ah)),
                     cx2 + (int)((g_swr - SC(16)) * cos(ah)), cy2 - (int)((g_swr - SC(16)) * sin(ah)),
                     ColorToARGB(clrGoldenrod, 255), SC(2), STYLE_SOLID, LINE_END_BUTT);
      double nf = (g_swp_bias + 1.0) / 2.0;
      if(nf < 0.0) nf = 0.0; if(nf > 1.0) nf = 1.0;
      double an2 = (SWEEP_FROM + (SWEEP_TO - SWEEP_FROM) * nf) * M_PI / 180.0;
      uint cn2 = (g_swp_bias >= 0.20) ? cUp : ((g_swp_bias <= -0.20) ? ColorToARGB(C'150,70,70',255) : cDim);
      g_cv.LineThick(cx2, cy2, cx2 + (int)((g_swr - SC(12)) * cos(an2)),
                     cy2 - (int)((g_swr - SC(12)) * sin(an2)), cn2, SC(3), STYLE_SOLID, LINE_END_ROUND);
      g_cv.FillCircle(cx2, cy2, SC(5), cn2);
      g_cv.FontSet("Consolas", FS(8), FW_BOLD);
      g_cv.TextOut(cx2 - g_swr + SC(4), cy2 - SC(10), "SELL",  ColorToARGB(C'150,70,70',255), TA_LEFT | TA_TOP);
      g_cv.TextOut(cx2 - g_swr + SC(4), cy2 - SC(1),  "mirror", cDead,                        TA_LEFT | TA_TOP);
      g_cv.TextOut(cx2 + g_swr - SC(4), cy2 - SC(10), "BUY",   cUp,                           TA_RIGHT | TA_TOP);
      g_cv.TextOut(cx2 + g_swr - SC(4), cy2 - SC(1),  "87%",   cDim,                          TA_RIGHT | TA_TOP);
      g_cv.FontSet("Consolas", FS(9), FW_BOLD);
      g_cv.TextOut(cx2, cy2 - SC(26), StringFormat("SWEEP %+.2f", g_swp_bias), cText, TA_CENTER | TA_TOP);

      //--- THIRD DIAL: TRAPPED. Left = trapped BUYERS (bearish), right = trapped SELLERS
      //--- (bullish). It is a CONFLUENCE FILTER, measured to lift sweep from 80% to 89% at
      //--- 10 seconds - NOT a signal of its own (56% against a 57% base) and NOT the
      //--- 60-second hold the idea promises: at 60s it scores 62% forward against 92%
      //--- BACKWARD, because the score contains a 60-second price term by construction.
      if(InpTrapDial)
      {
         int cx3 = g_cx + gap2;
         for(int d3 = 0; d3 <= st2; d3++)
         {
            double f3 = (double)d3 / (double)st2;
            double bv3 = 2.0 * f3 - 1.0;
            double a3 = (SWEEP_FROM + (SWEEP_TO - SWEEP_FROM) * f3) * M_PI / 180.0;
            uint c3 = ColorToARGB(C'45,45,52', 255);
            if(bv3 >=  0.45)      c3 = ColorToARGB(C'0,160,90',  255);
            else if(bv3 >=  0.15) c3 = ColorToARGB(C'25,95,65',  255);
            else if(bv3 <= -0.45) c3 = ColorToARGB(C'190,55,55', 255);
            else if(bv3 <= -0.15) c3 = ColorToARGB(C'110,50,50', 255);
            g_cv.LineThick(cx3 + (int)((g_swr - SC(1)) * cos(a3)), cy2 - (int)((g_swr - SC(1)) * sin(a3)),
                           cx3 + (int)((g_swr - SC(7)) * cos(a3)), cy2 - (int)((g_swr - SC(7)) * sin(a3)),
                           c3, SC(2), STYLE_SOLID, LINE_END_BUTT);
         }
         double tf = (g_trap / 2.0 + 1.0) / 2.0;      // score runs -2..+2
         if(tf < 0.0) tf = 0.0; if(tf > 1.0) tf = 1.0;
         double at = (SWEEP_FROM + (SWEEP_TO - SWEEP_FROM) * tf) * M_PI / 180.0;
         uint ct = (g_trap >= 0.3) ? cUp : ((g_trap <= -0.3) ? cDn : cDim);
         g_cv.LineThick(cx3, cy2, cx3 + (int)((g_swr - SC(12)) * cos(at)),
                        cy2 - (int)((g_swr - SC(12)) * sin(at)), ct, SC(3), STYLE_SOLID, LINE_END_ROUND);
         g_cv.FillCircle(cx3, cy2, SC(5), ct);
         g_cv.FontSet("Consolas", FS(8), FW_BOLD);
         // the ends say the TRADE the side favours, not the market-microstructure noun.
         // "SELLERS trapped" is true and licenses nothing; "SELL" / "BUY" is what to do with
         // a signal that arrives while the needle sits there.
         g_cv.TextOut(cx3 - g_swr + SC(4), cy2 - SC(10), "SELL", cDn, TA_LEFT  | TA_TOP);
         g_cv.TextOut(cx3 + g_swr - SC(4), cy2 - SC(10), "BUY",  cUp, TA_RIGHT | TA_TOP);
         // the right side is the measured one: sweep scores 89% with it and 70% against it.
         g_cv.TextOut(cx3 + g_swr - SC(4), cy2 - SC(1), "89%", cDim, TA_RIGHT | TA_TOP);
         g_cv.FontSet("Consolas", FS(9), FW_BOLD);
         // FAVOURS, not BUY NOW. Standalone this gauge is 56% against a 57% base - it GRADES
         // a signal that arrives, it never generates one.
         string tlab = "NO BIAS";
         uint   tlc  = cDim;
         if(g_trap >=  0.30) { tlab = "FAVOURS BUY";  tlc = cUp; }
         if(g_trap <= -0.30) { tlab = "FAVOURS SELL"; tlc = cDn; }
         g_cv.TextOut(cx3, cy2 - SC(26), tlab, tlc, TA_CENTER | TA_TOP);
         g_cv.FontSet("Consolas", FS(7), FW_NORMAL);
         g_cv.TextOut(cx3, cy2 - SC(17), StringFormat("%+.2f", g_trap), cDim, TA_CENTER | TA_TOP);
      }
   }

   //--- THE SWEEP STRIP. Its own row, so the best-evidenced signal here is never hidden by
   //--- whatever the single-slot band happens to be showing. Two rows also make agreement and
   //--- disagreement between the two strongest signals visible instead of silently resolved.
   int swY = swDialBot + (g_swr > 0 ? g_swr + SC(10) : SC(0));
   int swH = SC(22);
   string swTxt = "SWEEP  --";
   uint swBg = ColorToARGB(C'30,30,36', 255), swTx = cDead;
   // THE EXIT CLOCK. The edge has a measured half-life: mean move peaks at 10s, is ~0 by 60s
   // and negative by 120s. Holding past it gives the move back.
   int edgeLeft = 0;
   if(g_exit_ms > 0)
   {
      edgeLeft = InpEdgeHoldSec - (int)((GetTickCount64() - g_exit_ms) / 1000);
      if(edgeLeft < 0) { edgeLeft = 0; g_exit_ms = 0; }
   }
   if(g_swp_latch == 0 && edgeLeft > 0)
   {
      swTxt = StringFormat("IN TRADE - EDGE ENDS IN %ds", edgeLeft);
      swBg  = ColorToARGB(C'70,60,20', 255); swTx = ColorToARGB(C'235,215,150', 255);
   }
   if(g_swp_latch == V_SWP_UP)
   {
      // "+FUEL" is the measured confluence: sweep alone 80% at 10s, sweep with trap>0 89%,
      // sweep against it 70%. The tag marks the 89% case and nothing more is claimed.
      swTxt = StringFormat("ASK SWEPT - BUY NOW!  %d%s", g_swp_left, (g_trap > 0.0 ? "  +FUEL" : ""));
      swBg  = ColorToARGB(C'0,140,75', 255); swTx = ColorToARGB(clrWhite, 255);
   }
   else if(g_swp_latch == V_SWP_DN)
   {
      swTxt = StringFormat("BID SWEPT - SELL NOW!  %d", g_swp_left);
      swBg  = ColorToARGB(C'165,40,40', 255); swTx = ColorToARGB(clrWhite, 255);
   }
   g_cv.FillRectangle(barX, swY, barX + barW, swY + swH, swBg);
   g_cv.FontSet("Consolas", FS(10), FW_BOLD);   // 23 chars x ~16px = 368 of 398 - fits
   g_cv.TextOut(g_cx, swY + swH / 2, swTxt, swTx, TA_CENTER | TA_VCENTER);

   //--- the numbers behind it, so nothing is a black box
   g_cv.FontSet("Consolas", FS(10), FW_NORMAL);
   // TWO LINES. One 88-character line needed 871 px inside a 392 px canvas, so everything
   // from OBI onward was clipped off-screen - the diagnostics were invisible exactly when
   // they mattered. ~39 characters fit per line at this font.
   string s1, s2;
   if(Ready())
   {
      s1 = StringFormat("%s base %.1f sd %.1f win %.0fs run %d%s",
                        (g_src == SRC_BOOK ? "BK" : "TK"),
                        g_mean, g_sd, g_win_ms / 1000.0, g_run, (g_flipped ? "F" : ""));
      s2 = StringFormat("edge %.1fx min %ds L%d %s",
                        g_edge, g_minhold, g_book_levels,
                        (g_have_flags ? "FLAGS" : (g_dom_ok ? "BOOK" : "INFER")));
   }
   else
   {
      s1 = StringFormat("warming up  %d / %d s", g_bn, WarmupTarget());
      s2 = "";
   }
   g_cv.TextOut(g_cx, barY + barH + SC(108) + (g_swr > 0 ? g_swr + SC(16) : 0), s1, cDim, TA_CENTER | TA_TOP);
   g_cv.TextOut(g_cx, barY + barH + SC(122) + (g_swr > 0 ? g_swr + SC(16) : 0), s2, cDim, TA_CENTER | TA_TOP);

   g_cv.Update();
}
//+------------------------------------------------------------------+
