//+------------------------------------------------------------------+
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
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.02"
#property strict

#include <Trade/Trade.mqh>

input group "=== UHV Diamond (Turtle TV UHV settings) ==="
input int    InpUhvMode      = 0;     // InpUhvMode: 0 every setup, 1 only the EA v1.27 would take, 2 royal (candle-close entry only)
input int    InpUhvMinLaws   = 0;     // InpUhvMinLaws: at least this many of the 3 laws (candle-close entry only)
input double InpUhvMinEr     = 0;     // InpUhvMinEr: 15-min efficiency ratio at least (0 = off; candle-close entry only)
input int    InpUhvEntry     = 1;     // InpUhvEntry: 1 = the tick price breaks the level, 0 = the breakout candle closes
input double InpUhvPreBreak  = 0;     // InpUhvPreBreak: instant entry this many pips BEFORE the level (0 = at the break)
input int    InpUhvStopMode  = 2;     // InpUhvStopMode: 1 LAWS (beyond the retracement), 2 beyond the breakout candle, 0 fixed pips
input double InpUhvSlBeyond  = 20;     // InpUhvSlBeyond: pips beyond the stop anchor (modes 1-2)
input double InpUhvRR        = 2;     // InpUhvRR: take profit = RR x the stop (modes 1-2, when InpUhvFixTp = 0)
input double InpUhvFixTp     = 0.6;     // InpUhvFixTp: fixed take profit in pips (modes 1-2; 0 = use InpUhvRR)
input double InpUhvBeR       = 0;     // InpUhvBeR: stop to entry once +BeR x R (0 = off; modes 1-2)
input double InpUhvTpPips    = 2;     // InpUhvTpPips: take profit pips (stop mode 0)
input double InpUhvSlPips    = 2;     // InpUhvSlPips: stop pips (stop mode 0)
input double InpUhvMaxSecs   = 0;     // InpUhvMaxSecs: close any round after this many seconds (0 = off)
input double InpUhvLossSecs  = 0;     // InpUhvLossSecs: close a round still IN LOSS after this many seconds (0 = off; when MaxSecs = 0)
input double InpUhvLots      = 1;     // InpUhvLots: lots per round

input group "=== Ride it: trailing stop (Turtle TV InpXTr) ==="
input int    InpXTr          = 0;     // InpXTr: 1 = trail InpXTrK pips behind the best price (0 = off)
input double InpXTrK         = 2;     // InpXTrK: trail distance, pips
input double InpXTrAct       = 0;     // InpXTrAct: the trail starts once +TrAct x R

input group "=== UHV detection (camel humps, UHV + breakout shape) ==="
input int    InpDetCamPiv     = 1;    // InpDetCamPiv: camel hump size (candles each side)
input int    InpDetCamConfirm = 1;    // InpDetCamConfirm: camel flips after this many humps in a row
input int    InpDetCamStrong  = 0;    // InpDetCamStrong: strong camel lets the breakout be louder (0 = never)
input int    InpDetMaxHumps   = 3;    // InpDetMaxHumps: hump budget (mode 1 'ea' tag)
input int    InpDetPivot      = 3;    // InpDetPivot: retracement swing size
input int    InpDetTrendLook  = 20;   // InpDetTrendLook: trend look-back, candles
input int    InpDetRetraceBack= 20;   // InpDetRetraceBack: retracement search back, candles
input double InpDetUhvBody    = 0.5;  // InpDetUhvBody: UHV min body share (mode 1 'ea' tag)
input double InpDetMomBody    = 0.7;  // InpDetMomBody: breakout min body share (momentum candle; 0 = any)
input int    InpDetCooldown   = 3;    // InpDetCooldown: candles between setups (mode 1 'ea' tag)

input group "=== Range boxes (Saad v1.25-1.27) ==="
input string InpBandsB       = "111111111111111111111"; // InpBandsB: BUY boxes 0-5% .. >100% (0 = unticked)
input string InpBandsS       = "111111111111111111111"; // InpBandsS: SELL boxes
input int    InpRangeLook    = 7;     // InpRangeLook: BUY range = the last N closed candles
input int    InpRangeLookS   = 7;     // InpRangeLookS: SELL range
input int    InpBandOff      = 1;     // InpBandOff: unticked box 1 = stand aside (ghost round that blocks), 0 = skip

input group "=== Housekeeping ==="
input long   InpMagic        = 88420; // InpMagic
input bool   InpVerbose      = true;  // InpVerbose: print every setup / entry / exit

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

// ---------------------------------------------------------------- the round (a real position, or a stand-aside ghost)
bool     r_on = false, r_ghost = false; int r_side = 0; double r_fill = 0, r_sl = 0, r_tp = 0, r_stop = 0, r_best = -1e9; datetime r_t0 = 0;
ulong    r_ticket = 0; int r_box = 0;

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
         if(want_red ? body_lo(k) < lvl : body_hi(k) > lvl) return k;
   return -1;
}

// 2. the UHV (D_FindUhv)
int uhv(int org, int side, bool strict)
{
   bool want_red = side > 0; int best = -1; long bestv = -1;
   for(int k = org; k > 0; k--)
      if(want_red ? colour(k) < 0 : colour(k) > 0)
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
      rough_ext = retrace_extreme(o, side); rough_uhv_v = v_(u); rough_min = t_(1) + 60;
      return;
   }
   if(!fired) return;
   bool ea = trend == side && hump_n < InpDetMaxHumps && uhv(o, side, true) == u &&
             (last_fire_t == 0 || t_(1) - last_fire_t >= InpDetCooldown * 60);
   if(ea) last_fire_t = t_(1);
   cut_ok = true; cut_side = side; cut_level = side > 0 ? h_(u) : l_(u); cut_uhv_t = t_(u);
   cut_ext = retrace_extreme(o, side); cut_laws = laws(u, side); cut_er = efficiency_ratio();
   cut_ea = ea; cut_royal = ea && cut_er >= ER_ROYAL;
}

//+------------------------------------------------------------------+
bool LoadBars(int count)
{
   MqlRates r[];
   ArraySetAsSeries(r, false);
   int n = CopyRates(_Symbol, PERIOD_M1, 1, count, r);                // closed bars only, oldest first
   if(n <= 0) return false;
   ArrayResize(BT, n); ArrayResize(BO, n); ArrayResize(BH, n); ArrayResize(BL, n); ArrayResize(BC, n); ArrayResize(BV, n);
   for(int i = 0; i < n; i++) { BT[i] = r[i].time; BO[i] = r[i].open; BH[i] = r[i].high; BL[i] = r[i].low; BC[i] = r[i].close; BV[i] = r[i].tick_volume; }
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
   if(LoadBars(3000))
   {
      int n = ArraySize(BT);
      for(int e = WIN; e < n; e++) { E = e; NW = WIN; Step(); }
      E = n - 1;
   }
   rough_ok = false; cut_ok = false;
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

void Open(int side, double anchor_stop, double px_box, string why)
{
   MqlTick tk; if(!SymbolInfoTick(_Symbol, tk)) return;
   double fill = side > 0 ? tk.ask : tk.bid;
   double sl, tp;
   if(InpUhvStopMode == 1 || InpUhvStopMode == 2)
   {
      sl = MathMax((fill - anchor_stop) * side / PIP, 0.0) + InpUhvSlBeyond;
      tp = InpUhvFixTp > 0 ? InpUhvFixTp : InpUhvRR * sl;
   }
   else { sl = InpUhvSlPips; tp = InpUhvTpPips; }
   if(InpXTr == 1 && InpUhvFixTp <= 0 && InpUhvRR >= 50) tp = 0;      // "ride it": no target
   int box = Box(side, px_box);
   string bands = side > 0 ? InpBandsB : InpBandsS;
   bool aside = StringLen(bands) > box && StringGetCharacter(bands, box) == '0';
   if(aside && InpBandOff == 0) { if(InpVerbose) PrintFormat("SKIP %s box %d unticked", side > 0 ? "BUY" : "SELL", box); return; }
   r_on = true; r_ghost = aside; r_side = side; r_fill = fill; r_sl = sl; r_tp = tp; r_stop = -sl; r_best = -1e9; r_t0 = tk.time; r_box = box; r_ticket = 0;
   if(!aside)
   {
      double lots = NormalizeDouble(MathMax(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), MathRound(InpUhvLots / SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)) * SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)), 2);
      double slpx = NormalizeDouble(fill - side * (sl + 0.5) * PIP, _Digits);   // a broker-side safety stop just beyond the EA's own
      bool ok = side > 0 ? trade.Buy(lots, _Symbol, 0, slpx, 0, "UHV " + why) : trade.Sell(lots, _Symbol, 0, slpx, 0, "UHV " + why);
      if(!ok || (trade.ResultRetcode() != TRADE_RETCODE_DONE && trade.ResultRetcode() != TRADE_RETCODE_PLACED))
      {
         PrintFormat("[ORDER REJECTED] %s %.2f lots: retcode %d %s", side > 0 ? "BUY" : "SELL", lots, trade.ResultRetcode(), trade.ResultRetcodeDescription());
         r_on = false; return;
      }
      r_ticket = trade.ResultOrder();
      if(trade.ResultPrice() > 0) r_fill = trade.ResultPrice();
   }
   if(InpVerbose) PrintFormat("%s %s %s at %.5f  stop %.1f pips  target %.1f pips  box %d", aside ? "GHOST (stand aside)" : "OPEN", side > 0 ? "BUY" : "SELL", why, r_fill, sl, tp, box);
}

void CloseRound(string why, double m)
{
   if(!r_ghost)
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong t = PositionGetTicket(i);
         if(PositionSelectByTicket(t) && PositionGetInteger(POSITION_MAGIC) == InpMagic && PositionGetString(POSITION_SYMBOL) == _Symbol)
            if(!trade.PositionClose(t)) PrintFormat("[CLOSE REJECTED] retcode %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
      }
   }
   if(InpVerbose) PrintFormat("%s %s %s %+.1f pips", r_ghost ? "GHOST END" : "CLOSE", r_side > 0 ? "BUY" : "SELL", why, m);
   r_on = false;
}

bool HavePosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(PositionSelectByTicket(t) && PositionGetInteger(POSITION_MAGIC) == InpMagic && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
}

// the round on this tick (uhv_engine._play: stop and target first, then breakeven, trail, time)
void Manage(const MqlTick &tk)
{
   if(!r_ghost && !HavePosition()) { if(InpVerbose) Print("CLOSE by the broker's safety stop"); r_on = false; return; }
   double px = r_side > 0 ? tk.bid : tk.ask;
   double m = (px - r_fill) * r_side / PIP;
   double el = (double)(tk.time - r_t0);
   double R = r_sl;
   if(m > r_best) r_best = m;
   if(m <= r_stop) { CloseRound(r_stop >= 0 ? "stop (moved)" : "stop", m); return; }
   if(r_tp > 0 && m >= r_tp) { CloseRound("target", m); return; }
   if((InpUhvStopMode == 1 || InpUhvStopMode == 2) && InpUhvBeR > 0 && r_best >= InpUhvBeR * R && r_stop < 0) r_stop = 0;
   if(InpXTr == 1 && r_best >= InpXTrAct * R) { double ts = r_best - InpXTrK; if(ts > r_stop) r_stop = ts; }
   if(InpUhvMaxSecs > 0 && el >= InpUhvMaxSecs) { CloseRound("time", m); return; }
   if(InpUhvMaxSecs <= 0 && InpUhvLossSecs > 0 && el >= InpUhvLossSecs && m < 0) { CloseRound("time (in loss)", m); return; }
   if(el >= MAX_HOLD) { CloseRound("24 h", m); return; }
}

void OnTick()
{
   MqlTick tk; if(!SymbolInfoTick(_Symbol, tk)) return;
   datetime bar0 = iTime(_Symbol, PERIOD_M1, 0);
   bool newbar = false;
   if(bar0 != m_min)                                               // a new minute: step the bar that just closed
   {
      m_min = bar0; m_ticks = 0; m_lo = tk.bid; m_hi = tk.bid;
      if(LoadBars(WIN))
      {
         E = ArraySize(BT) - 1; NW = ArraySize(BT);
         if(NW >= Need() + 2) { Step(); newbar = true; }
      }
   }
   m_ticks++; m_lo = MathMin(m_lo, tk.bid); m_hi = MathMax(m_hi, tk.bid);

   if(r_on) Manage(tk);
   if(r_on) return;                                                // one round at a time (a ghost blocks too)

   if(InpUhvEntry == 0)
   {
      if(!newbar || !cut_ok) return;
      if((InpUhvMode == 1 && !cut_ea) || (InpUhvMode == 2 && !cut_royal) || cut_laws < InpUhvMinLaws || (InpUhvMinEr > 0 && (cut_er < 0 || cut_er < InpUhvMinEr))) return;
      double anchor = InpUhvStopMode == 1 ? cut_ext : (cut_side > 0 ? l_(1) : h_(1));
      Open(cut_side, anchor, c_(1), "breakout candle closed");
      return;
   }
   // instant: the first tick whose bid crosses the waiting UHV level, if the minute so far is quieter than the UHV
   if(!rough_ok || rough_min != bar0 || Used(rough_uhv_t)) return;
   if(InpUhvMode != 0 || InpUhvMinLaws > 0 || InpUhvMinEr > 0) return;  // as Turtle TV: instant setups carry no laws / ea / ER
   double lv = rough_level - rough_side * InpUhvPreBreak * PIP;
   if(!(rough_side > 0 ? tk.bid > lv : tk.bid < lv)) return;
   AddUsed(rough_uhv_t);
   if(m_ticks >= rough_uhv_v) { if(InpVerbose) PrintFormat("SKIP break of %s: %d ticks so far, not quieter than the UHV's %d", TimeToString(rough_uhv_t), m_ticks, rough_uhv_v); return; }
   double anchor = InpUhvStopMode == 1 ? rough_ext : (rough_side > 0 ? m_lo : m_hi);
   Open(rough_side, anchor, rough_level, "break of UHV " + TimeToString(rough_uhv_t, TIME_MINUTES));
}
//+------------------------------------------------------------------+
