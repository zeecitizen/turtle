//+------------------------------------------------------------------+
//| ZeeUHV_B3_NoPreBreak.mq5 - B3 with the pre-break turned off      |
//| (a named copy of ZeeUHV_TurtleTV v1.08; only the defaults differ)   |
//| ZeeUHV_TurtleTV.mq5 - the UHV Diamond as Turtle TV UHV plays it    |
//| (monitor/TurtleTVUHV/uhv_engine.py + uhv_diamond.py), for Zee to    |
//| test in MT5's Strategy Tester on PrimeXBT's own EURUSD.             |
//|                                                                     |
//| Zee 2026-11-05: "write an EA that follows the Turtle TV UHV engine  |
//| and its settings -> I'll TEST IT MYSELF in the MT5 strategy tester" |
//| + "you can reuse the diamond EA we already have the code for".      |
//|                                                                     |
//| Detection = the Diamond engine (ZeeUHV_Diamond v1.27 /              |
//| DiamondEngineM1.mqh: retracement origin, UHV, breakout, camel_trend,|
//| laws) as Turtle TV runs it, plus Zee's Pine camel humps (Turtle     |
//| Trader Desk) for the side and LAWS.md's momentum + quieter breakout.|
//| Volume = the bar's tick volume (PrimeXBT ticks), as Turtle TV.      |
//|                                                                     |
//| Chart: EURUSD M1. Tester: "Every tick based on real ticks".         |
//| NOT in this EA: Saad's filters (InpUhvSaad) and the Turtle Trader   |
//| Desk indicator group (InpTtdOn) - Turtle TV only.                   |
//| v1.01: defaults = Zee's save 2026-11-05 05-45-38 (Turtle TV 97.7%) |
//| v1.02: defaults = Zee's save 2026-11-05 04-18-08 (Turtle TV 95.1%) |
//| v1.03 (2026-11-09): the Turtle TV loss filters the "TWICE AN HOUR"  |
//|   save uses (uhv_filters.skip / into_wall, uhv_engine gates):       |
//|   NoClose, MaxTrigSpread, MinTicks, SpikeAtr, MaxFlips60, MinSpanAtr,|
//|   WickFake, Wall + InpMaxPos (rounds open at once). Defaults = that  |
//|   save (Turtle TV: 11,656 trades, 98.46%, 2+ trades every hour).    |
//| v1.04 (2026-11-14): Zee: "create an EA of B3 and B4 = B3 + half     |
//|   rule 0.5 ... then i can run the strategy tester on this EA".      |
//|   New filters: InpUhvLateUtcFrom, InpUhvFriCutAllNY,                |
//|   InpUhvMaxFromSwing (B3), InpUhvMaxEntryPos (the half rule, B4).   |
//|   The stop is the order's own stop loss at the engine's stop price. |
//|   The 0.1-pip target cannot rest at the broker in the tester (stops |
//|   level), so it is closed at market at the touch AND every touch is |
//|   counted the way UhvEntryReplay v1.06 counts it (whole points,     |
//|   inside a trade session, ticks hidden by an executing order read   |
//|   back). The Journal ends with "TARGET HELD AT THE BROKER: ..." and |
//|   OnTester returns that win rate. Defaults = the B3 save.           |
//| v1.05 (2026-11-14): the breakout tick is compared with the level in |
//|   whole points (a bid exactly on the level is not beyond it), as    |
//|   uhv_engine now does - the last entries that differed. A setup    |
//|   that arrives while InpMaxPos rounds are open is skipped for good. |
//| v1.06 (2026-11-14): InpUhvCamExit - close at market when the camel  |
//|   hump line turns against the round (Zee: "once we buy and the next |
//|   candles start going down ... let's exit the trade"). Off.         |
//| v1.07 (2026-11-14): InpDetRetStart (uhv_diamond RET_START), for the |
//|   purified B3: candle-close entry on the UHV of the whole           |
//|   retracement.                                                      |
//| v1.08 (2026-11-14): InpDetDojiUhv - a doji inside the retracement   |
//|   can be the UHV (Zee, the 26 Oct 3:28 PM sell).                    |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.08"
#property strict

#include <Trade/Trade.mqh>

input group "=== UHV Diamond (Turtle TV UHV settings) ==="
input int    InpUhvMode      = 0;     // InpUhvMode: 0 every setup, 1 only the EA v1.27 would take, 2 royal (candle-close entry only)
input int    InpUhvMinLaws   = 0;     // InpUhvMinLaws: at least this many of the 3 laws (candle-close entry only)
input double InpUhvMinEr     = 0;     // InpUhvMinEr: 15-min efficiency ratio at least (0 = off; candle-close entry only)
input int    InpUhvEntry     = 1;     // InpUhvEntry: 1 = the tick price breaks the level, 0 = the breakout candle closes
input double InpUhvPreBreak  = 0;     // InpUhvPreBreak: instant entry this many pips BEFORE the level (0 = at the break)
input int    InpUhvStopMode  = 1;     // InpUhvStopMode: 1 LAWS (beyond the retracement), 2 beyond the breakout candle, 0 fixed pips
input double InpUhvSlBeyond  = 22.5;     // InpUhvSlBeyond: pips beyond the stop anchor (modes 1-2)
input double InpUhvRR        = 1;     // InpUhvRR: take profit = RR x the stop (modes 1-2, when InpUhvFixTp = 0)
input double InpUhvFixTp     = 0.1;     // InpUhvFixTp: fixed take profit in pips (modes 1-2; 0 = use InpUhvRR)
input double InpUhvBeR       = 0;     // InpUhvBeR: stop to entry once +BeR x R (0 = off; modes 1-2)
input double InpUhvTpPips    = 4;     // InpUhvTpPips: take profit pips (stop mode 0)
input double InpUhvSlPips    = 2;     // InpUhvSlPips: stop pips (stop mode 0)
input double InpUhvMaxSecs   = 0;     // InpUhvMaxSecs: close any round after this many seconds (0 = off)
input double InpUhvLossSecs  = 0;     // InpUhvLossSecs: close a round still IN LOSS after this many seconds (0 = off; when MaxSecs = 0)
input int    InpUhvCamExit   = 0;     // InpUhvCamExit: 1 = close at market when the camel hump line turns against the round, 2 = when it is no longer with it (0 = off)
input double InpUhvLots      = 1;     // InpUhvLots: lots per round

input group "=== Ride it: trailing stop (Turtle TV InpXTr) ==="
input int    InpXTr          = 0;     // InpXTr: 1 = trail InpXTrK pips behind the best price (0 = off)
input double InpXTrK         = 2;     // InpXTrK: trail distance, pips
input double InpXTrAct       = 0;     // InpXTrAct: the trail starts once +TrAct x R

input group "=== UHV detection (camel humps, UHV + breakout shape) ==="
input int    InpDetCamPiv     = 3;    // InpDetCamPiv: camel hump size (candles each side)
input int    InpDetCamConfirm = 1;    // InpDetCamConfirm: camel flips after this many humps in a row
input int    InpDetCamStrong  = 0;    // InpDetCamStrong: strong camel lets the breakout be louder (0 = never)
input int    InpDetMaxHumps   = 3;    // InpDetMaxHumps: hump budget (mode 1 'ea' tag)
input int    InpDetPivot      = 3;    // InpDetPivot: retracement swing size
input int    InpDetTrendLook  = 20;   // InpDetTrendLook: trend look-back, candles
input int    InpDetRetraceBack= 20;   // InpDetRetraceBack: retracement search back, candles
input double InpDetUhvBody    = 0.5;  // InpDetUhvBody: UHV min body share (mode 1 'ea' tag)
input double InpDetMomBody    = 0.7;  // InpDetMomBody: breakout min body share (momentum candle; 0 = any)
input int    InpDetDojiUhv    = 0;    // InpDetDojiUhv: 1 = a doji (close = open) inside the retracement can be the UHV; 0 = only counter-coloured candles
input int    InpDetRetStart   = 0;    // InpDetRetStart: 1 = the retracement starts at the first counter-coloured candle after the extreme (valid once a body breaks the last trend candle); 0 = at that breaking candle
input int    InpDetCooldown   = 3;    // InpDetCooldown: candles between setups (mode 1 'ea' tag)

input group "=== Range boxes (Saad v1.25-1.27) ==="
input string InpBandsB       = "111111111111111111111"; // InpBandsB: BUY boxes 0-5% .. >100% (0 = unticked)
input string InpBandsS       = "111111111111111111111"; // InpBandsS: SELL boxes
input int    InpRangeLook    = 7;     // InpRangeLook: BUY range = the last N closed candles
input int    InpRangeLookS   = 7;     // InpRangeLookS: SELL range
input int    InpBandOff      = 0;     // InpBandOff: unticked box 1 = stand aside (ghost round that blocks), 0 = skip

input group "=== Loss filters (Turtle TV UHV uhv_filters / engine gates) ==="
input int    InpUhvNoClose       = 1;     // InpUhvNoClose: 1 = no new entries 16:45-17:45 New York (the daily rollover)
input double InpUhvMaxTrigSpread = 0.15;   // InpUhvMaxTrigSpread: skip when the spread at the breakout tick is >= this many pips (0 = off)
input double InpUhvMinTicks      = 0;    // InpUhvMinTicks: dead tape - skip when the last 10 closed candles averaged fewer ticks (0 = off)
input double InpUhvSpikeAtr      = 0;     // InpUhvSpikeAtr: skip when one of the last InpUhvSpikeBars candles spanned more than this x ATR(14) (0 = off)
input int    InpUhvSpikeBars     = 15;    // InpUhvSpikeBars: candles back for the spike
input double InpUhvMaxFlips60    = 0;   // InpUhvMaxFlips60: choppy - skip when the closes changed direction more than this share of the time (0 = off)
input int    InpUhvFlipsBars     = 60;    // InpUhvFlipsBars: candles for the direction-change share
input double InpUhvMinSpanAtr    = 0;     // InpUhvMinSpanAtr: squeeze box - skip when the last InpUhvMinSpanBars candles span less than this x ATR (0 = off)
input int    InpUhvMinSpanBars   = 5;     // InpUhvMinSpanBars: candles for the span
input int    InpUhvWickFake      = 0;     // InpUhvWickFake: 1 = skip when one of the last InpUhvWickBars candles poked beyond the last swing and closed back
input int    InpUhvWickBars      = 3;     // InpUhvWickBars: candles back for the wick fake-break
input double InpUhvWall          = 0;     // InpUhvWall: skip when a tested round-figure wall lies 0..this many pips beyond the level (0 = off)
input int    InpUhvWallTouches   = 3;     // InpUhvWallTouches: touches (within 0.5 pip) that make a wall
input int    InpUhvWallBars      = 60;    // InpUhvWallBars: candles back for the wall
input double InpUhvWallFig       = 100;   // InpUhvWallFig: the figure grid in pips (100 = the 00 figures)
input int    InpUhvLateUtcFrom   = 21;    // InpUhvLateUtcFrom: no entries from this UTC hour to midnight UTC (0 = off)
input double InpUhvFriCutAllNY   = 16;    // InpUhvFriCutAllNY: no Friday entries from this New York hour on (0 = off)
input double InpUhvMaxFromSwing  = 3;     // InpUhvMaxFromSwing: B3 - skip a buy triggered more than this many pips above the last camel swing low (sell: below the last swing high; 0 = off)
input double InpUhvMaxEntryPos   = 0;       // InpUhvMaxEntryPos: B4 half rule - the trigger price must be within this share of the UHV candle from the level (0.5 = the nearer half; 0 = off)
input double InpUhvMaxUhvClosePos = 0;    // InpUhvMaxUhvClosePos: the UHV candle must have closed within this share of its range from the level (0.5 = the nearer half; 0 = off)
input int    InpMaxPos           = 0;     // InpMaxPos: rounds open at once (1 = one at a time, N = up to N, 0 = every setup)
input int    InpSrvUtcOff        = 0;     // InpSrvUtcOff: server clock minus UTC in hours (Turtle TV read PrimeXBT time as UTC: 0)

input group "=== Housekeeping ==="
input long   InpMagic        = 88423; // InpMagic
input bool   InpWriteCsv     = true;  // InpWriteCsv: write every position to Common\Files\<EA name>_trades.csv at the end
input bool   InpVerbose      = false;  // InpVerbose: print every setup / entry / exit

#define WIN      400
#define MAX_GAP  300
#define ER_N     16
#define ER_ROYAL 0.45
#define MAX_HOLD 86400

CTrade trade;
double PIP;

// ---------------------------------------------------------------- the bars (oldest first), E = the newest closed
datetime BT[]; double BO[], BH[], BL[], BC[]; long BV[];
int E = -1, NW = 0;                    // NW = bars in the window (<= WIN), as the Python's 400-bar window

double   o_(int k) { return BO[E - k + 1]; }
double   h_(int k) { return BH[E - k + 1]; }
double   l_(int k) { return BL[E - k + 1]; }
double   c_(int k) { return BC[E - k + 1]; }
long     v_(int k) { return BV[E - k + 1]; }
datetime t_(int k) { return BT[E - k + 1]; }
int      colour(int k) { double d = c_(k) - o_(k); return d > 0 ? 1 : (d < 0 ? -1 : 0); }
double   body_hi(int k) { return MathMax(o_(k), c_(k)); }
double   body_lo(int k) { return MathMin(o_(k), c_(k)); }

// ---------------------------------------------------------------- the Diamond's state
int      hump_dir = 0, hump_n = 0; datetime hump_last = 0, last_fire_t = 0;
// Zee's camel humps (Turtle Trader Desk pine CAMEL-HUMP TREND block)
int      czT = 0, czTr = 0, czStk = 0, czStk0 = 0, czEff = 0;
datetime czHB = 0, czL0B = 0, czLB = 0; double czHV = 0, czL0V = 0, czLV = 0;

// rough = a UHV level waiting during the forming minute; cut = the breakout candle just closed
bool     rough_ok = false; int rough_side = 0; double rough_level = 0, rough_ext = 0; datetime rough_uhv_t = 0, rough_min = 0; long rough_uhv_v = 0;
bool     cut_ok = false; int cut_side = 0; double cut_level = 0, cut_ext = 0; datetime cut_uhv_t = 0; int cut_laws = 0; bool cut_ea = false, cut_royal = false; double cut_er = -1;
datetime used_uhv[]; int n_used = 0;
double   rough_rng = 0, cut_rng = 0;      // v1.04: the UHV candle's high - low (the half rule)
double   rough_cpos = -1, cut_cpos = -1;  // v1.04: where the UHV candle closed, as a share of its range from the breakout level (whole points)
double   ClosePos(int u, int side) { long hp = (long)MathRound(h_(u) / _Point), lp = (long)MathRound(l_(u) / _Point), cp = (long)MathRound(c_(u) / _Point); return hp > lp ? (double)(side > 0 ? hp - cp : cp - lp) / (double)(hp - lp) : -1; }

// ---------------------------------------------------------------- the round (a real position, or a stand-aside ghost)
#define MAXR 512
struct Round { bool on; bool ghost; int side; double fill; double sl; double tp; double stop; double best; datetime t0; ulong ticket; int box; double slpx; long tpp; long opp; long om; bool got; bool touched; int h; };
Round    RR[MAXR]; int n_open = 0;
int      OpenRounds() { int n = 0; for(int i = 0; i < MAXR; i++) if(RR[i].on) n++; return n; }

// minute tick bookkeeping (instant entry: the ticks so far in the minute, its low / high up to the break)
datetime m_min = 0; long m_ticks = 0; double m_lo = 0, m_hi = 0;

//+------------------------------------------------------------------+
double efficiency_ratio()
{
   // closes of the COMPLETED 15-minute candles in the window (the forming one is not complete)
   double cl[]; int n = 0; long cur = -1; long fb = (long)(BT[E] + 60) / 900;
   ArrayResize(cl, 0);
   for(int i = E - NW + 1; i <= E; i++)
   {
      long g = (long)BT[i] / 900;
      if(g >= fb) break;
      if(g != cur) { n++; ArrayResize(cl, n); cl[n - 1] = BC[i]; cur = g; }
      else cl[n - 1] = BC[i];
   }
   if(n < ER_N + 1) return -1;
   double path = 0;
   for(int i = n - ER_N - 1; i < n - 1; i++) path += MathAbs(cl[i + 1] - cl[i]);
   return path > 0 ? MathAbs(cl[n - 1] - cl[n - ER_N - 1]) / path : 0.0;
}

// 0. the regime: the Diamond's camel humps (D_CamelTrendD) - only for the 'ea' tag
int camel_trend()
{
   int p = InpDetPivot; double hs[], ls[]; int hidx[], lidx[]; int nh = 0, nl = 0;
   for(int k = InpDetTrendLook; k > p; k--)
   {
      bool ph = true, pl = true;
      for(int q = 1; q <= p; q++)
      {
         if(h_(k) <= h_(k - q) || h_(k) <= h_(k + q)) ph = false;
         if(l_(k) >= l_(k - q) || l_(k) >= l_(k + q)) pl = false;
      }
      if(ph) { nh++; ArrayResize(hs, nh); ArrayResize(hidx, nh); hs[nh - 1] = h_(k); hidx[nh - 1] = k; }
      if(pl) { nl++; ArrayResize(ls, nl); ArrayResize(lidx, nl); ls[nl - 1] = l_(k); lidx[nl - 1] = k; }
   }
   if(nh < 2 || nl < 2) return 0;
   bool higher_low = ls[nl - 1] > ls[nl - 2], lower_high = hs[nh - 1] < hs[nh - 2];
   bool broke_top = false, broke_bottom = false;
   for(int q = hidx[nh - 1] - 1; q > 0; q--) if(body_hi(q) > hs[nh - 1]) { broke_top = true; break; }
   for(int q = lidx[nl - 1] - 1; q > 0; q--) if(body_lo(q) < ls[nl - 1]) { broke_bottom = true; break; }
   bool up = broke_top && higher_low, down = broke_bottom && lower_high;
   if(up == down) return 0;
   return up ? 1 : -1;
}

void hump_update(int trend)
{
   if(trend != 0 && trend != hump_dir) { hump_dir = trend; hump_n = 0; hump_last = 0; }
   if(hump_dir == 0) return;
   int p = InpDetPivot;
   for(int k = p + 1; k <= InpDetTrendLook; k++)
   {
      bool ok = true;
      for(int q = 1; q <= p; q++)
      {
         if(hump_dir > 0 && (h_(k) <= h_(k - q) || h_(k) <= h_(k + q))) ok = false;
         if(hump_dir < 0 && (l_(k) >= l_(k - q) || l_(k) >= l_(k + q))) ok = false;
      }
      if(!ok) continue;
      if(t_(k) != hump_last) { hump_last = t_(k); hump_n++; }
      break;
   }
}

// Zee's Pine camel humps: one closed bar
void camel_step()
{
   int p = InpDetCamPiv;
   if(NW < 2 * p + 1) return;
   int c = p + 1;
   bool ph = true, pl = true;
   for(int d = 1; d <= p; d++)
   {
      if(h_(c) < h_(c - d) || h_(c) < h_(c + d)) ph = false;
      if(l_(c) > l_(c - d) || l_(c) > l_(c + d)) pl = false;
   }
   datetime tb = t_(c);
   if(ph)
   {
      double v = h_(c);
      if(czT == 1) { if(v >= czHV) { czHB = tb; czHV = v; } }
      else { czStk0 = czStk; czL0B = czLB; czL0V = czLV; czHB = tb; czHV = v; czT = 1; }
   }
   if(pl)
   {
      double v = l_(c); bool redraw = false;
      if(czT == 1) { czLB = tb; czLV = v; czT = -1; redraw = true; }
      else if(czT == -1 && v <= czLV) { czLB = tb; czLV = v; redraw = true; }
      else if(czT == 0) { czLB = tb; czLV = v; czT = -1; }
      if(redraw && czHB != 0 && czL0B != 0)
      {
         czTr = czLV > czL0V ? 1 : (czLV < czL0V ? -1 : 0);
         czStk = czTr == 1 ? MathMax(czStk0, 0) + 1 : (czTr == -1 ? MathMin(czStk0, 0) - 1 : 0);
         if(MathAbs(czStk) >= InpDetCamConfirm) czEff = czStk > 0 ? 1 : -1;
         else if(czTr == 0 && InpDetCamConfirm <= 1) czEff = 0;
      }
   }
}

// 1. the retracement (D_RetracementOrigin)
int origin(int side)
{
   bool want_red = side > 0; int ext = -1; double best = 0;
   for(int k = 2; k <= InpDetRetraceBack; k++)
   {
      double x = want_red ? h_(k) : l_(k);
      if(ext < 0 || (want_red ? x > best : x < best)) { best = x; ext = k; }
   }
   if(ext < 2) return -1;
   int g = -1;
   for(int k = ext; k <= MathMin(ext + 8, InpDetRetraceBack + 8); k++)
   {
      if(k > NW) break;
      if(want_red ? colour(k) > 0 : colour(k) < 0) { g = k; break; }
   }
   if(g < 2) return -1;
   double lvl = want_red ? l_(g) : h_(g);
   for(int k = g - 1; k > 0; k--)
      if(want_red ? colour(k) < 0 : colour(k) > 0)
         if(want_red ? body_lo(k) < lvl : body_hi(k) > lvl)
         {
            if(InpDetRetStart > 0)                                  // v1.07: the valid retracement starts at the first counter-coloured candle after the extreme
               for(int j = g - 1; j > k; j--) if(want_red ? colour(j) < 0 : colour(j) > 0) return j;
            return k;
         }
   return -1;
}

// 2. the UHV (D_FindUhv)
int uhv(int org, int side, bool strict)
{
   bool want_red = side > 0; int best = -1; long bestv = -1;
   for(int k = org; k > 0; k--)
      if((want_red ? colour(k) < 0 : colour(k) > 0) || (InpDetDojiUhv > 0 && colour(k) == 0))   // v1.08: a doji inside the retracement can be the UHV
         if(v_(k) > bestv) { bestv = v_(k); best = k; }
   if(best < 1) return -1;
   if(!strict) return best;
   double rng = h_(best) - l_(best);
   if(rng <= 0 || MathAbs(c_(best) - o_(best)) / rng < InpDetUhvBody) return -1;
   if(best + 1 <= NW && v_(best + 1) > bestv) return -1;
   if(best > 1 && v_(best - 1) > bestv) return -1;
   return best;
}

// 3. the breakout (D_BreakoutIsBar1): fired = bar 1 is the breakout; crossed = some candle already crossed
void breakout(int u, int side, bool loud_ok, bool &fired, bool &crossed)
{
   fired = false; crossed = false;
   if(u <= 1) return;
   bool want_green = side > 0;
   for(int k = u - 1; k > 0; k--)
   {
      if(!(want_green ? colour(k) > 0 : colour(k) < 0)) continue;
      bool cr = want_green ? body_hi(k) > h_(u) : body_lo(k) < l_(u);
      if(!cr) continue;
      crossed = true;
      if(v_(k) >= v_(u) && !loud_ok) return;                       // LAWS.md (b): quieter than the UHV
      double rk = h_(k) - l_(k);
      if(InpDetMomBody > 0 && (rk <= 0 || MathAbs(c_(k) - o_(k)) / rk < InpDetMomBody)) return;   // LAWS.md (a): momentum candle
      fired = (k == 1);
      return;
   }
}

int laws(int u, int side)
{
   int d = 0;
   for(int k = u + 1; k <= MathMin(u + 20, NW); k++)
      if((side > 0 && l_(k) < l_(u)) || (side < 0 && h_(k) > h_(u))) { d++; break; }
   if(NW >= 31)
   {
      double kk = 2.0 / 6.0, e = c_(31);
      for(int i = 30; i > 0; i--) e = c_(i) * kk + e * (1.0 - kk);
      double unit = 1.2 * PIP;
      if((side > 0 && colour(1) > 0 && c_(1) > e + 0.10 * unit) || (side < 0 && colour(1) < 0 && c_(1) < e - 0.10 * unit)) d++;
   }
   double rng = MathMax(h_(1) - l_(1), 1e-12);
   double wick = side > 0 ? (h_(1) - body_hi(1)) / rng : (body_lo(1) - l_(1)) / rng;
   if(wick <= 0.25 && v_(1) < v_(u)) d++;
   return d;
}

double retrace_extreme(int org, int side)
{
   double x = side > 0 ? l_(1) : h_(1);
   for(int k = 1; k <= org; k++) x = side > 0 ? MathMin(x, l_(k)) : MathMax(x, h_(k));
   return x;
}

bool continuous(int nbars)
{
   for(int k = 1; k < MathMin(nbars, NW - 1); k++) if(t_(k) - t_(k + 1) > 60 + MAX_GAP) return false;
   return true;
}

// one closed bar (uhv_diamond.Diamond._step)
void Step()
{
   int trend = camel_trend();
   hump_update(trend);
   camel_step();
   rough_ok = false; cut_ok = false;
   for(int k = 1; k <= MathMin(InpDetTrendLook + InpDetRetraceBack + 8, NW); k++) if(v_(k) <= 0) return;   // a minute with no volume: no judgement
   if(!continuous(InpDetTrendLook + 5)) return;
   int side = czEff;
   if(side == 0) return;
   bool strong = InpDetCamStrong > 0 && (side > 0 ? czStk >= InpDetCamStrong : czStk <= -InpDetCamStrong);
   int o = origin(side);
   int u = o >= 0 ? uhv(o, side, false) : -1;
   if(u < 0) return;
   bool fired, crossed;
   breakout(u, side, strong, fired, crossed);
   if(!crossed)
   {
      rough_ok = true; rough_side = side; rough_level = side > 0 ? h_(u) : l_(u); rough_uhv_t = t_(u);
      rough_ext = retrace_extreme(o, side); rough_uhv_v = v_(u); rough_min = t_(1) + 60; rough_rng = h_(u) - l_(u); rough_cpos = ClosePos(u, side);
      return;
   }
   if(!fired) return;
   bool ea = trend == side && hump_n < InpDetMaxHumps && uhv(o, side, true) == u &&
             (last_fire_t == 0 || t_(1) - last_fire_t >= InpDetCooldown * 60);
   if(ea) last_fire_t = t_(1);
   cut_ok = true; cut_side = side; cut_level = side > 0 ? h_(u) : l_(u); cut_uhv_t = t_(u); cut_rng = h_(u) - l_(u); cut_cpos = ClosePos(u, side);
   cut_ext = retrace_extreme(o, side); cut_laws = laws(u, side); cut_er = efficiency_ratio();
   cut_ea = ea; cut_royal = ea && cut_er >= ER_ROYAL;
}

//+------------------------------------------------------------------+
#define VN 8192
datetime VT[VN]; long VV[VN]; bool vol_live = false; int vol_own = 0, vol_brk = 0;
void SetVol(datetime t, long v) { int i = (int)(((long)t / 60) & (VN - 1)); VT[i] = t; VV[i] = v; }
long GetVol(datetime t) { int i = (int)(((long)t / 60) & (VN - 1)); return VT[i] == t ? VV[i] : -1; }
// count the ticks of [from, to) into their minutes (the warm-up: the minutes before the EA saw its first tick)
bool VolFromTicks(datetime from, datetime to)
{
   MqlTick q[]; int c = CopyTicksRange(_Symbol, q, COPY_TICKS_ALL, (ulong)from * 1000, (ulong)to * 1000 - 1);
   if(c <= 0) return false;
   datetime cur = 0; long n = 0;
   for(int k = 0; k < c; k++)
   {
      datetime m = (datetime)(q[k].time - q[k].time % 60);
      if(m != cur) { if(cur != 0) SetVol(cur, n); cur = m; n = 0; }
      n++;
   }
   if(cur != 0) SetVol(cur, n);
   return true;
}
bool LoadBars(int count)
{
   MqlRates r[];
   ArraySetAsSeries(r, false);
   int n = CopyRates(_Symbol, PERIOD_M1, 1, count, r);                // closed bars only, oldest first
   if(n <= 0) return false;
   ArrayResize(BT, n); ArrayResize(BO, n); ArrayResize(BH, n); ArrayResize(BL, n); ArrayResize(BC, n); ArrayResize(BV, n);
   for(int i = 0; i < n; i++) { BT[i] = r[i].time; BO[i] = r[i].open; BH[i] = r[i].high; BL[i] = r[i].low; BC[i] = r[i].close; long ov = GetVol(r[i].time); if(ov >= 0) { BV[i] = ov; vol_own++; } else { BV[i] = r[i].tick_volume; vol_brk++; } }
   return true;
}

int Need() { return InpDetTrendLook + InpDetPivot + 2; }

int OnInit()
{
   PIP = (_Digits == 3 || _Digits == 5) ? 10 * _Point : _Point;
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(50);
   if(_Period != PERIOD_M1) Print("ZeeUHV_TurtleTV: attach to an M1 chart (Turtle TV reads 1-minute candles)");
   // warm the camel state up on history, as the Python steps the whole dataset
   datetime now0 = iTime(_Symbol, PERIOD_M1, 0);
   bool vt = VolFromTicks(now0 - 3000 * 60 * 3, now0);            // the closed minutes behind us (weekends included in the reach)
   PrintFormat("%s v1.08: candle volume = every tick in the minute; warm-up ticks %s", MQLInfoString(MQL_PROGRAM_NAME), vt ? "read" : "NOT available (the broker's tick volume until 400 candles have been counted)");
   if(LoadBars(3000))
   {
      int n = ArraySize(BT);
      for(int e = WIN; e < n; e++) { E = e; NW = WIN; Step(); }
      E = n - 1;
   }
   rough_ok = false; cut_ok = false;
   for(int i = 0; i < MAXR; i++) RR[i].on = false;
   m_min = iTime(_Symbol, PERIOD_M1, 0);                            // the newest closed bar was stepped above
   return INIT_SUCCEEDED;
}

bool Used(datetime t) { for(int i = 0; i < n_used; i++) if(used_uhv[i] == t) return true; return false; }
void AddUsed(datetime t) { n_used++; ArrayResize(used_uhv, n_used); used_uhv[n_used - 1] = t; if(n_used > 500) { ArrayRemove(used_uhv, 0, 250); n_used = ArraySize(used_uhv); } }

// range boxes: where the entry sits in the last N closed candles' range; returns the box (0..20)
int Box(int side, double px)
{
   int nb = side > 0 ? InpRangeLook : InpRangeLookS;
   double hi = h_(1), lo = l_(1);
   for(int k = 1; k <= MathMin(nb, NW); k++) { hi = MathMax(hi, h_(k)); lo = MathMin(lo, l_(k)); }
   double pct = hi > lo ? (side > 0 ? (px - lo) : (hi - px)) / (hi - lo) : 0.5;
   return pct <= 1.0 ? (int)MathMin(20, MathMax(0, (int)(pct * 20))) : 20;
}

// ---------------------------------------------------------------- v1.04: what a take profit held at the broker does (UhvEntryReplay v1.06)
long   pend_n = 0; double pend_lo = 0, pend_hi = 0;                // hidden ticks of the minute now forming (counted in CatchUp, added in Work)
long   lastMsc = 0; bool didBlock = false; int scans = 0, scanErr = 0, catchTouch = 0, offSess = 0;
ulong  H_pid[]; bool H_touch[]; long H_ms[]; int H_side[]; double H_tpusd[]; int nH = 0;   // every real position: id, target touched, decision time, side, the target in $
int    r_hi = 0;                                                    // round slots in use: RR[0 .. r_hi-1]
bool   finished = false; int rejN = 0;

int  SS_n[7]; datetime SS_a[7][8], SS_b[7][8]; bool SS_ok = false;
bool InSession(long msc)                                           // is this tick time inside a trade session of the symbol? (a quote in the daily break cannot fill a target)
{
   if(!SS_ok)
   {
      for(int d = 0; d < 7; d++) { SS_n[d] = 0; datetime a, b;
         for(int q = 0; q < 8 && SymbolInfoSessionTrade(_Symbol, (ENUM_DAY_OF_WEEK)d, q, a, b); q++) { SS_a[d][SS_n[d]] = a; SS_b[d][SS_n[d]] = b; SS_n[d]++; } }
      SS_ok = true;
   }
   datetime tm = (datetime)(msc / 1000); MqlDateTime z; TimeToStruct(tm, z); long sod = z.hour * 3600 + z.min * 60 + z.sec;
   if(SS_n[z.day_of_week] == 0) return false;
   for(int q = 0; q < SS_n[z.day_of_week]; q++) if(sod >= (long)SS_a[z.day_of_week][q] && sod < (long)SS_b[z.day_of_week][q]) return true;
   return false;
}
long Pts(double px) { return (long)MathRound(px / _Point); }
bool TouchAt(int ri, double bid, double ask) { return RR[ri].tpp > 0 && (RR[ri].side > 0 ? Pts(bid) - RR[ri].opp >= RR[ri].tpp : RR[ri].opp - Pts(ask) >= RR[ri].tpp); }
bool StopAt(int ri, double bid, double ask)  { return RR[ri].side > 0 ? bid <= RR[ri].slpx : ask >= RR[ri].slpx; }

// the ticks that passed while an order was executing (the tester's random delay): OrderSend returns only after it, so they never reached OnTick
void CatchUp(long toMsc)
{
   if(lastMsc == 0 || toMsc - 1 < lastMsc + 1) return;
   MqlTick q[]; int c = CopyTicksRange(_Symbol, q, COPY_TICKS_ALL, (ulong)(lastMsc + 1), (ulong)(toMsc - 1));
   scans++; if(c < 0) { scanErr++; return; }
   if(c == 0) return;
   long new_ms = (long)iTime(_Symbol, PERIOD_M1, 0) * 1000;     // the minute now forming; hidden ticks before it belong to the minute Work() is about to close
   for(int k = 0; k < c; k++)
   {
      if(q[k].time_msc < new_ms && new_ms != (long)m_min * 1000) { m_ticks++; continue; }
      pend_n++; pend_lo = pend_n == 1 ? q[k].bid : MathMin(pend_lo, q[k].bid); pend_hi = pend_n == 1 ? q[k].bid : MathMax(pend_hi, q[k].bid);
   }
   for(int ri = 0; ri < r_hi; ri++)
   {
      if(!RR[ri].on || RR[ri].ghost || !RR[ri].got || RR[ri].touched) continue;
      for(int k = 0; k < c; k++)
      {
         if(q[k].time_msc < RR[ri].om) continue;                   // before this position's own fill
         if(StopAt(ri, q[k].bid, q[k].ask)) break;                 // the stop came first
         if(TouchAt(ri, q[k].bid, q[k].ask)) { if(InSession(q[k].time_msc)) { RR[ri].touched = true; H_touch[RR[ri].h] = true; catchTouch++; break; } else offSess++; }
      }
   }
}

void Open(int side, double anchor_stop, double px_box, string why, const MqlTick &tk)
{
   double fill = side > 0 ? tk.ask : tk.bid;
   double sl, tp;
   if(InpUhvStopMode == 1 || InpUhvStopMode == 2)
   {
      sl = MathMax((fill - anchor_stop) * side / PIP, 0.0) + InpUhvSlBeyond;
      tp = InpUhvFixTp > 0 ? InpUhvFixTp : InpUhvRR * sl;
   }
   else { sl = InpUhvSlPips; tp = InpUhvTpPips; }
   sl = MathMax(sl, 0.1);
   if(InpXTr == 1 && InpUhvFixTp <= 0 && InpUhvRR >= 50) tp = 0;      // "ride it": no target
   int box = Box(side, px_box);
   string bands = side > 0 ? InpBandsB : InpBandsS;
   bool aside = StringLen(bands) > box && StringGetCharacter(bands, box) == '0';
   if(aside && InpBandOff == 0) { if(InpVerbose) PrintFormat("SKIP %s box %d unticked", side > 0 ? "BUY" : "SELL", box); return; }
   int ri = -1; for(int i = 0; i < MAXR; i++) if(!RR[i].on) { ri = i; break; }
   if(ri < 0) { Print("SKIP: every round slot is busy"); return; }
   if(ri + 1 > r_hi) r_hi = ri + 1;
   RR[ri].on = true; RR[ri].ghost = aside; RR[ri].side = side; RR[ri].fill = fill; RR[ri].sl = sl; RR[ri].tp = tp; RR[ri].stop = -sl; RR[ri].best = -1e9; RR[ri].t0 = tk.time; RR[ri].box = box; RR[ri].ticket = 0;
   RR[ri].slpx = NormalizeDouble(fill - side * sl * PIP, _Digits);      // the tester's stop price: measured from the price at the decision tick, as uhv_engine
   RR[ri].tpp = tp > 0 ? (long)MathMax(1, MathRound(tp * PIP / _Point)) : 0; RR[ri].opp = Pts(fill); RR[ri].om = tk.time_msc; RR[ri].got = aside; RR[ri].touched = false; RR[ri].h = -1;
   if(!aside)
   {
      double lots = NormalizeDouble(MathMax(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), MathRound(InpUhvLots / SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)) * SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)), 2);
      didBlock = true;
      bool ok = side > 0 ? trade.Buy(lots, _Symbol, 0, RR[ri].slpx, 0, "UHV " + why) : trade.Sell(lots, _Symbol, 0, RR[ri].slpx, 0, "UHV " + why);
      if(!ok || (trade.ResultRetcode() != TRADE_RETCODE_DONE && trade.ResultRetcode() != TRADE_RETCODE_PLACED))
      {
         PrintFormat("[ORDER REJECTED] %s %.2f lots: retcode %d %s", side > 0 ? "BUY" : "SELL", lots, trade.ResultRetcode(), trade.ResultRetcodeDescription());
         RR[ri].on = false; return;
      }
      RR[ri].ticket = trade.ResultOrder();
      if(RR[ri].ticket == 0 && trade.ResultDeal() != 0 && HistoryDealSelect(trade.ResultDeal())) RR[ri].ticket = (ulong)HistoryDealGetInteger(trade.ResultDeal(), DEAL_POSITION_ID);
      if(trade.ResultPrice() > 0) RR[ri].fill = trade.ResultPrice();
      ArrayResize(H_pid, nH + 1, 4096); ArrayResize(H_touch, nH + 1, 4096); ArrayResize(H_ms, nH + 1, 4096); ArrayResize(H_side, nH + 1, 4096); ArrayResize(H_tpusd, nH + 1, 4096);
      double tsz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE), tvl = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      H_pid[nH] = RR[ri].ticket; H_touch[nH] = false; H_ms[nH] = tk.time_msc; H_side[nH] = side; H_tpusd[nH] = tsz > 0 ? RR[ri].tpp * _Point / tsz * tvl * lots : 0;
      RR[ri].h = nH; nH++;
   }
   if(InpVerbose) PrintFormat("%s %s %s at %.5f  stop %.1f pips  target %.1f pips  box %d  (open rounds %d)", aside ? "GHOST (stand aside)" : "OPEN", side > 0 ? "BUY" : "SELL", why, RR[ri].fill, sl, tp, box, OpenRounds());
}

ulong PosTicketOf(ulong order)
{
   // the position opened by this order (netting: one position per symbol; hedging: POSITION_IDENTIFIER == the order ticket)
   if(order != 0 && PositionSelectByTicket(order) && PositionGetInteger(POSITION_MAGIC) == InpMagic) return order;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(!PositionSelectByTicket(t) || PositionGetInteger(POSITION_MAGIC) != InpMagic || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(order != 0 && ((ulong)PositionGetInteger(POSITION_IDENTIFIER) == order || t == order)) return t;
   }
   return 0;
}

void CloseRound(int ri, string why, double m)
{
   if(!RR[ri].ghost)
   {
      ulong t = PosTicketOf(RR[ri].ticket);
      didBlock = true;
      if(t != 0 && !trade.PositionClose(t))
      {
         // v1.03: a rejected close (Friday "market closed", 65 of them in the first MT5 run) must NOT drop the round - the position is still
         // ours, so the round stays on and the close is retried on the next tick (the engine's round runs on until its exit fills)
         if(rejN++ < 5) PrintFormat("[CLOSE REJECTED] retcode %d %s - the round stays on, retrying (only the first 5 are printed)", trade.ResultRetcode(), trade.ResultRetcodeDescription());
         if(trade.ResultRetcode() != TRADE_RETCODE_POSITION_CLOSED) return;
      }
   }
   if(InpVerbose) PrintFormat("%s %s %s %+.1f pips", RR[ri].ghost ? "GHOST END" : "CLOSE", RR[ri].side > 0 ? "BUY" : "SELL", why, m);
   RR[ri].on = false;
}

// the round on this tick (uhv_engine._play: stop and target first, then breakeven, trail, time)
void Manage(int ri, const MqlTick &tk)
{
   if(!RR[ri].ghost)
   {
      ulong pt = PosTicketOf(RR[ri].ticket);
      if(pt == 0)
      {
         // v1.03: with the tester's random delay the position appears a moment after the order is placed - wait for it (up to 10 s)
         if(tk.time - RR[ri].t0 <= 10 && OrderSelect(RR[ri].ticket)) return;
         if(tk.time - RR[ri].t0 <= 10 && PositionsTotal() == 0 && !RR[ri].got) return;
         if(InpVerbose) Print("CLOSE by the stop at the broker");
         RR[ri].on = false; return;
      }
      if(!RR[ri].got)                                              // v1.04: the target is measured from MT5's own fill, in whole points
      {
         RR[ri].fill = PositionGetDouble(POSITION_PRICE_OPEN); RR[ri].opp = Pts(RR[ri].fill); RR[ri].om = PositionGetInteger(POSITION_TIME_MSC); RR[ri].got = true;
      }
   }
   double px = RR[ri].side > 0 ? tk.bid : tk.ask;
   double m = (px - RR[ri].fill) * RR[ri].side / PIP;
   double el = (double)(tk.time - RR[ri].t0);
   double R = RR[ri].sl;
   if(m > RR[ri].best) RR[ri].best = m;
   bool moved = RR[ri].stop > -RR[ri].sl + 1e-9;                   // the unmoved stop is the broker's (the order's own stop loss)
   if(RR[ri].ghost ? m <= RR[ri].stop : (moved && m <= RR[ri].stop)) { CloseRound(ri, moved ? "stop (moved)" : "stop", m); return; }
   if(RR[ri].touched) { CloseRound(ri, "target", m); return; }     // touched while an order was executing, or a close that was rejected: close now
   if(TouchAt(ri, tk.bid, tk.ask))
   {
      if(RR[ri].ghost || InSession(tk.time_msc)) { RR[ri].touched = true; if(RR[ri].h >= 0) H_touch[RR[ri].h] = true; CloseRound(ri, "target", m); return; }
      offSess++;
   }
   if((InpUhvStopMode == 1 || InpUhvStopMode == 2) && InpUhvBeR > 0 && RR[ri].best >= InpUhvBeR * R && RR[ri].stop < 0) RR[ri].stop = 0;
   if(InpXTr == 1 && RR[ri].best >= InpXTrAct * R) { double ts = RR[ri].best - InpXTrK; if(ts > RR[ri].stop) RR[ri].stop = ts; }
   if(InpUhvMaxSecs > 0 && el >= InpUhvMaxSecs) { CloseRound(ri, "time", m); return; }
   if(InpUhvMaxSecs <= 0 && InpUhvLossSecs > 0 && el >= InpUhvLossSecs && m < 0) { CloseRound(ri, "time (in loss)", m); return; }
   if(el >= MAX_HOLD) { CloseRound(ri, "24 h", m); return; }
}

// ---------------------------------------------------------------- the loss filters (monitor/TurtleTVUHV/uhv_filters.py), on the closed bars:
// k = 1 is the last closed candle (Python's k), k = 2 the one before ... exactly as skip() reads h[k-n+1..k]
double atr14()
{
   // sim._atr_adx: the 14-candle simple mean of the true range (MT5 iATR), at the last closed candle
   double s = 0; int n = 0;
   for(int k = 1; k <= 14 && k + 1 <= NW; k++) { s += MathMax(h_(k), c_(k + 1)) - MathMin(l_(k), c_(k + 1)); n++; }
   return n > 0 ? s / n : 0;
}

// the last 1-candle pivot high / low (>=, as uhv_filters._prep: a pivot at j is known once j+1 closed) at or before closed candle q
int LastPivot(int q, bool high)
{
   for(int j = q; j + 1 <= NW; j++)                                // j = q is Python's lastH[q-1] candidate (its pivot test reads q's neighbour)
   {
      if(j + 1 > NW || j - 1 < 1) continue;
      bool p = high ? (h_(j) >= h_(j + 1) && h_(j) >= h_(j - 1)) : (l_(j) <= l_(j + 1) && l_(j) <= l_(j - 1));
      if(p) return j;
      if(j - q > 400) break;
   }
   return -1;
}

// px = the price that triggered (the bid at the breakout tick; the breakout candle's close for the candle-close entry), uhv_rng = the UHV candle's high - low
string LossFilter(int side, double level, double spread, double px, double uhv_rng, double uhv_cpos, datetime srv)
{
   if(NW < 131) return "";                                        // skip(): k < 130 -> no filter
   if(InpUhvMaxTrigSpread > 0 && spread >= InpUhvMaxTrigSpread * PIP - 1e-12) return "spread at the breakout tick";
   double atr = atr14();
   if(InpUhvWall > 0)
   {
      int T = MathMax(1, InpUhvWallTouches), N = MathMax(10, InpUhvWallBars); double g = MathMax(1.0, InpUhvWallFig) * PIP;
      for(int a = 1; a <= N; a++)
      {
         double cc = MathRound((side > 0 ? h_(a) : l_(a)) / 0.00001) * 0.00001;
         double d = (side > 0 ? cc - level : level - cc) / PIP;
         if(d < 0 || d > InpUhvWall) continue;
         if(MathAbs(cc - MathRound(cc / g) * g) > PIP) continue;
         int touches = 0;
         for(int b = 1; b <= N; b++) if(MathAbs((side > 0 ? h_(b) : l_(b)) - cc) <= 0.5 * PIP) touches++;
         if(touches >= T) return "into a tested round-figure wall";
      }
   }
   if(InpUhvMinTicks > 0) { double s = 0; for(int a = 1; a <= 10; a++) s += (double)v_(a); if(s / 10.0 < InpUhvMinTicks) return "dead tape"; }
   if(InpUhvSpikeAtr > 0 && atr > 0)
   {
      int n = MathMax(1, InpUhvSpikeBars); double mx = 0;
      for(int a = 1; a <= n; a++) mx = MathMax(mx, h_(a) - l_(a));
      if(mx > InpUhvSpikeAtr * atr) return "spike";
   }
   if(InpUhvMaxFlips60 > 0)
   {
      int nf = MathMax(5, InpUhvFlipsBars);
      if(NW >= nf + 2)
      {
         int flips = 0, pairs = 0, prev = 0;
         for(int a = nf; a >= 1; a--)                             // closes c[k-nf..k] oldest first: a = nf+1 .. 1; diffs between neighbours
         {
            double d = c_(a) - c_(a + 1); int sg = d > 0 ? 1 : (d < 0 ? -1 : 0);
            if(a < nf) { pairs++; if(sg * prev < 0) flips++; }
            prev = sg;
         }
         if(pairs > 0 && (double)flips / pairs > InpUhvMaxFlips60) return "choppy hour";
      }
   }
   if(InpUhvLateUtcFrom > 0)                                      // v1.04: no entries from this UTC hour to midnight UTC
   {
      MqlDateTime u; TimeToStruct(srv - InpSrvUtcOff * 3600, u);
      if(u.hour >= InpUhvLateUtcFrom) return "late session";
   }
   if(InpUhvMinSpanAtr > 0 && atr > 0)
   {
      int N = MathMax(2, InpUhvMinSpanBars); double hi = h_(1), lo = l_(1);
      for(int a = 1; a <= N; a++) { hi = MathMax(hi, h_(a)); lo = MathMin(lo, l_(a)); }
      if(hi - lo < InpUhvMinSpanAtr * atr) return "short squeeze box";
   }
   if(InpUhvWickFake > 0)
   {
      for(int q = MathMax(1, InpUhvWickBars); q >= 1; q--)
      {
         int j = LastPivot(q + 1, side > 0);                      // the last pivot known at q-1 (Python lastx[q-1])
         if(j < 0) continue;
         if(side > 0 && h_(q) > h_(j) && c_(q) < h_(j)) return "wick fake-break";
         if(side < 0 && l_(q) < l_(j) && c_(q) > l_(j)) return "wick fake-break";
      }
   }
   // v1.04 (B3): chasing - the trigger price is more than this many pips past the last confirmed camel swing low (buy) / high (sell).
   // czLV / czHV after this bar's camel_step = uhv_filters._camel_levels at the forming candle
   if(InpUhvMaxFromSwing > 0)
   {
      bool have = side > 0 ? czLB != 0 : czHB != 0; double ref = side > 0 ? czLV : czHV;
      if(have && (px - ref) * side > InpUhvMaxFromSwing * PIP + 1e-12) return "far from the last swing";
   }
   // v1.04 (B4): the half rule - the trigger price must be within this share of the UHV candle's range from the breakout level
   if(InpUhvMaxEntryPos > 0 && uhv_rng > 0 && (level - px) * side / uhv_rng > InpUhvMaxEntryPos + 1e-9) return "entry not deep enough into the UHV candle";
   // v1.04: the UHV candle itself closed within this share of its range from the breakout level (uhv_filters InpUhvMaxUhvClosePos)
   if(InpUhvMaxUhvClosePos > 0 && uhv_cpos >= 0 && uhv_cpos > InpUhvMaxUhvClosePos + 1e-9) return "UHV candle closed away from the level";
   return "";
}

// New York minute of the day and day of the week for a server time (uhv_engine: zoneinfo America/New_York on the tick time)
void NyClock(datetime srv, int &minute, int &dow)
{
   datetime utc = srv - InpSrvUtcOff * 3600;
   MqlDateTime d; TimeToStruct(utc, d);
   // US DST: from the second Sunday of March 07:00 UTC to the first Sunday of November 06:00 UTC
   int y = d.year;
   datetime mar1 = StringToTime(StringFormat("%04d.03.01 00:00", y)); MqlDateTime m1; TimeToStruct(mar1, m1);
   int secondSun = 1 + ((7 - m1.day_of_week) % 7) + 7;
   datetime nov1 = StringToTime(StringFormat("%04d.11.01 00:00", y)); MqlDateTime n1; TimeToStruct(nov1, n1);
   int firstSun = 1 + ((7 - n1.day_of_week) % 7);
   datetime dstStart = StringToTime(StringFormat("%04d.03.%02d 07:00", y, secondSun));
   datetime dstEnd = StringToTime(StringFormat("%04d.11.%02d 06:00", y, firstSun));
   int off = (utc >= dstStart && utc < dstEnd) ? -4 : -5;
   datetime ny = utc + off * 3600;
   MqlDateTime z; TimeToStruct(ny, z);
   minute = z.hour * 60 + z.min; dow = z.day_of_week;
}

// the session rules decided on the tick time: "" or why not
string Clock(datetime srv)
{
   if(InpUhvNoClose <= 0 && InpUhvFriCutAllNY <= 0) return "";
   int nm, dw; NyClock(srv, nm, dw);
   if(InpUhvNoClose > 0 && nm >= 16 * 60 + 45 && nm < 17 * 60 + 45) return "the New York rollover 16:45-17:45";
   if(InpUhvFriCutAllNY > 0 && dw == 5 && nm >= InpUhvFriCutAllNY * 60) return "Friday after the cut-off";
   return "";
}

void Work(const MqlTick &tk)
{
   datetime bar0 = iTime(_Symbol, PERIOD_M1, 0);
   bool newbar = false;
   pend_n = 0;
   if(didBlock) CatchUp(tk.time_msc);                              // v1.04: the ticks an executing order hid from OnTick
   didBlock = false;
   if(bar0 != m_min)                                               // a new minute: step the bar that just closed
   {
      if(m_min != 0 && vol_live) SetVol(m_min, m_ticks);           // v1.04: the closed minute's volume = every tick in it, as Turtle TV counts
      vol_live = true;
      m_min = bar0; m_ticks = 0; m_lo = tk.bid; m_hi = tk.bid;
      if(LoadBars(WIN))
      {
         E = ArraySize(BT) - 1; NW = ArraySize(BT);
         if(NW >= Need() + 2) { Step(); newbar = true; }
      }
   }
   if(pend_n > 0) { m_ticks += pend_n; m_lo = MathMin(m_lo, pend_lo); m_hi = MathMax(m_hi, pend_hi); }
   m_ticks++; m_lo = MathMin(m_lo, tk.bid); m_hi = MathMax(m_hi, tk.bid);

   while(r_hi > 0 && !RR[r_hi - 1].on) r_hi--;
   for(int i = 0; i < r_hi; i++) if(RR[i].on) Manage(i, tk);
   // v1.06: the hump-line exit (uhv_engine InpUhvCamExit) - when a candle opens and the camel hump line is against the round (1) / no longer with it (2),
   // from the second candle after the entry (the round was opened in an earlier minute)
   if(newbar && InpUhvCamExit > 0)
      for(int i = 0; i < r_hi; i++)
      {
         if(!RR[i].on || RR[i].t0 >= bar0 - 60) continue;         // opened in the candle that just closed: not yet
         if(InpUhvCamExit == 1 ? czEff != -RR[i].side : czEff == RR[i].side) continue;
         double pxc = RR[i].side > 0 ? tk.bid : tk.ask;
         CloseRound(i, "hump line against the trade", (pxc - RR[i].fill) * RR[i].side / PIP);
      }
   // v1.03 sweeper: a position of ours that no round tracks for 10 s (the first run left 6 open to the end of the test) is closed at market
   for(int p = PositionsTotal() - 1; p >= 0; p--)
   {
      ulong t = PositionGetTicket(p);
      if(!PositionSelectByTicket(t) || PositionGetInteger(POSITION_MAGIC) != InpMagic || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(tk.time - (datetime)PositionGetInteger(POSITION_TIME) < 10) continue;
      ulong pid = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      bool tracked = false;
      for(int i = 0; i < r_hi; i++) if(RR[i].on && !RR[i].ghost && (RR[i].ticket == t || RR[i].ticket == pid)) { tracked = true; break; }
      if(!tracked) { PrintFormat("ORPHAN position #%I64u closed", t); didBlock = true; trade.PositionClose(t); }
   }
   bool full = InpMaxPos > 0 && OpenRounds() >= InpMaxPos;         // uhv_engine InpMaxPos: rounds open at once (a ghost counts too)

   if(InpUhvEntry == 0)
   {
      if(!newbar || !cut_ok || full) return;
      if((InpUhvMode == 1 && !cut_ea) || (InpUhvMode == 2 && !cut_royal) || cut_laws < InpUhvMinLaws || (InpUhvMinEr > 0 && (cut_er < 0 || cut_er < InpUhvMinEr))) return;
      if(Clock(tk.time) != "") return;
      string lf0 = LossFilter(cut_side, cut_level, tk.ask - tk.bid, c_(1), cut_rng, cut_cpos, tk.time);   // the spread at the entry tick (the first tick after the close)
      if(lf0 != "") { if(InpVerbose) PrintFormat("SKIP %s: %s", cut_side > 0 ? "BUY" : "SELL", lf0); return; }
      double anchor0 = InpUhvStopMode == 1 ? cut_ext : (cut_side > 0 ? l_(1) : h_(1));
      Open(cut_side, anchor0, c_(1), "breakout candle closed", tk);
      return;
   }
   // instant: the first tick whose bid crosses the waiting UHV level, if the minute so far is quieter than the UHV
   if(!rough_ok || rough_min != bar0 || Used(rough_uhv_t)) return;
   if(InpUhvMode != 0 || InpUhvMinLaws > 0 || InpUhvMinEr > 0) return;  // as Turtle TV: instant setups carry no laws / ea / ER
   double lv = rough_level - rough_side * InpUhvPreBreak * PIP;
   double bp = (double)Pts(tk.bid), lvp = lv / _Point;             // v1.05: in whole points - a bid exactly on the level is not beyond it (as uhv_engine)
   if(!(rough_side > 0 ? bp > lvp + 1e-6 : bp < lvp - 1e-6)) return;
   AddUsed(rough_uhv_t);
   if(full) { if(InpVerbose) Print("SKIP: every allowed round is open"); return; }   // v1.05: a setup that arrives while full is skipped for good, as uhv_engine (it used to wait for a later tick)
   if(m_ticks >= rough_uhv_v) { if(InpVerbose) PrintFormat("SKIP break of %s: %d ticks so far, not quieter than the UHV's %d", TimeToString(rough_uhv_t), m_ticks, rough_uhv_v); return; }
   string ck = Clock(tk.time);
   if(ck != "") { if(InpVerbose) Print("SKIP: ", ck); return; }
   string lf = LossFilter(rough_side, rough_level, tk.ask - tk.bid, tk.bid, rough_rng, rough_cpos, tk.time);
   if(lf != "") { if(InpVerbose) PrintFormat("SKIP %s: %s", rough_side > 0 ? "BUY" : "SELL", lf); return; }
   double anchor = InpUhvStopMode == 1 ? rough_ext : (rough_side > 0 ? m_lo : m_hi);
   Open(rough_side, anchor, rough_level, "break of UHV " + TimeToString(rough_uhv_t, TIME_MINUTES), tk);
}

void OnTick()
{
   MqlTick tk; if(!SymbolInfoTick(_Symbol, tk)) return;
   Work(tk);
   lastMsc = tk.time_msc;
}

// ---------------------------------------------------------------- v1.04: the result with the target held at the broker
// The tester refuses a take profit 0.1 pip from the price (EURUSDp's stops level), so the EA closes at market when the target is touched and the
// fill comes a tick later - the tester's own report shows that. A target resting at the broker fills AT the touch: every position whose target
// was touched counts as a win of exactly the target; every other position keeps what MT5 paid. That figure is printed here and is OnTester's result.
double OnTester()
{
   int w = 0; for(int j = 0; j < nH; j++) if(H_touch[j]) w++;
   int open_now = 0; for(int i = 0; i < r_hi; i++) if(RR[i].on && !RR[i].ghost) open_now++;
   return nH - open_now > 0 ? 100.0 * w / (nH - open_now) : 0;
}

void Finish()
{
   if(finished || nH == 0) return;
   finished = true;
   HistorySelect(0, TimeCurrent() + 86400);
   double PL[]; ArrayResize(PL, nH); ArrayInitialize(PL, 0);
   int EN[]; ArrayResize(EN, nH); ArrayInitialize(EN, 0);
   int CL[]; ArrayResize(CL, nH); ArrayInitialize(CL, 0);
   double K[][2]; ArrayResize(K, nH);                              // [position id, H index], sorted by id for a binary search
   for(int j = 0; j < nH; j++) { K[j][0] = (double)H_pid[j]; K[j][1] = j; }
   ArraySort(K);
   int nd = HistoryDealsTotal();
   for(int d = 0; d < nd; d++)
   {
      ulong dl = HistoryDealGetTicket(d);
      if(HistoryDealGetInteger(dl, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      double pid = (double)HistoryDealGetInteger(dl, DEAL_POSITION_ID);
      int lo = 0, hi = nH - 1;
      while(lo <= hi)
      {
         int mid = (lo + hi) / 2;
         if(K[mid][0] < pid) lo = mid + 1;
         else if(K[mid][0] > pid) hi = mid - 1;
         else
         {
            int j = (int)K[mid][1];
            PL[j] += HistoryDealGetDouble(dl, DEAL_PROFIT) + HistoryDealGetDouble(dl, DEAL_SWAP) + HistoryDealGetDouble(dl, DEAL_COMMISSION); CL[j] = 1;
            if(StringFind(HistoryDealGetString(dl, DEAL_COMMENT), "end of test") >= 0) EN[j] = 1;
            break;
         }
      }
   }
   int n = 0, w = 0, ended = 0, pos = 0; double net_b = 0, net_s = 0, lost = 0;
   for(int j = 0; j < nH; j++)
   {
      net_s += PL[j]; if(PL[j] > 0) pos++;
      if(EN[j] == 1 || CL[j] == 0) { ended++; net_b += PL[j]; continue; }
      n++;
      if(H_touch[j]) { w++; net_b += H_tpusd[j]; } else { net_b += PL[j]; lost += PL[j]; }
   }
   string nm = MQLInfoString(MQL_PROGRAM_NAME);
   PrintFormat("%s: %d positions, %d still open at the end of the test (left out of the win rate)", nm, nH, ended);
   PrintFormat("%s TARGET HELD AT THE BROKER: %d trades, %d wins, %d not at target, win rate %.2f%%, net %+.2f (the losses %+.2f)", nm, n, w, n - w, n > 0 ? 100.0 * w / n : 0, net_b, lost);
   PrintFormat("%s as the tester report shows it (target closed at market, a tick late): %d of %d strictly positive = %.2f%%, net %+.2f", nm, pos, nH, 100.0 * pos / nH, net_s);
   PrintFormat("%s: catch-up scans %d (errors %d), touches found in them %d, touches outside a trade session ignored %d", nm, scans, scanErr, catchTouch, offSess);
   if(rejN > 0) PrintFormat("%s: %d close attempts were rejected and retried (market closed)", nm, rejN);
   if(!InpWriteCsv) return;
   int h = FileOpen(nm + "_trades.csv", FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if(h == INVALID_HANDLE) return;
   for(int j = 0; j < nH; j++)   // decision time ms, side, position id, target touched, MT5 P/L, still open at the end of the test
      FileWrite(h, IntegerToString(H_ms[j]), H_side[j], IntegerToString((long)H_pid[j]), H_touch[j] ? 1 : 0, DoubleToString(PL[j], 2), (EN[j] == 1 || CL[j] == 0) ? 1 : 0);
   FileClose(h);
}

void OnDeinit(const int reason) { Finish(); }
//+------------------------------------------------------------------+
