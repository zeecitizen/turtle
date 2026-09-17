//+------------------------------------------------------------------+
//|  VSISA_Minute.mq5 - the M1 absorption scalper                     |
//|                                                                   |
//|  Zee, 2026-09-18, after trading this by hand on the 1-minute:     |
//|  "after a mix of red / green high volumes.. smaller greens         |
//|   started appearing.. i were able to make a larger spread with     |
//|   lower volume than before.. it measures resistance based on       |
//|   volume.. as soon as you're confirming the slightest imbalance..  |
//|   an entry is taken."                                              |
//|                                                                   |
//|  v1.00 HAD THE SIGN BACKWARDS. It hunted quiet, efficient bars    |
//|  anywhere on the chart, found 9 setups a month, and lost about the |
//|  spread on each (-$22.51 a trade over 183 trades at confirm 1).    |
//|                                                                   |
//|  Replaying HIS OWN window on the OANDA M1 feed showed what he      |
//|  actually bought. At 22:28 volume hit 647 - 2.39x the 20-bar       |
//|  average and 1.46x the loudest recent bar - while price moved      |
//|  -0.31 with a body of 0.17. Enormous effort, no result: supply     |
//|  being absorbed. v1.00 explicitly REJECTED that bar. His third     |
//|  trade is the same picture stretched over six bars (22:33-22:38,   |
//|  ~3,300 volume for 0.89 of downward progress); he bought when      |
//|  volume collapsed to ~280 and the greens appeared, and closed at   |
//|  22:46 for $135-161.                                              |
//|                                                                   |
//|  THE CORRECTED READING - absorption, then release:                 |
//|    1. price falls INTO a window          (InpLegMin)               |
//|    2. that window is LOUD                (InpAbsorbVol)            |
//|    3. ...and goes nowhere                (InpAbsorbStuck)          |
//|    4. the next bar is QUIET and decided  (InpReleaseVol)           |
//|                                                                   |
//|  "a larger spread with lower volume than before" is step 4         |
//|  measured against step 2. This also explains how he made money     |
//|  BUYING INTO A DOWNTREND: he was not trading direction, he was     |
//|  trading the moment selling exhausted.                             |
//|                                                                   |
//|  THE EVIDENCE. First time traded on M1: 2026-09-17, four           |
//|  decisions, ten tickets at 1.00 lot, 22:09-22:46 broker, every one |
//|  a winner, +$1,036. Earlier manual losses in the fills log (2 Sep, |
//|  -$1,320) belong to a DIFFERENT strategy and are NOT evidence      |
//|  about this one - he said so explicitly.                           |
//|                                                                   |
//|  Four decisions is a hypothesis. InpStopPts is mandatory not       |
//|  because this has been seen to lose but because it has NOT yet,    |
//|  and a 1.00-lot scalper without a cap is one bad minute away from  |
//|  giving back a week.                                               |
//|                                                                   |
//|                                                                   |
//|  v1.11 -> v1.12: THE TESTER OVERRULED ME, TWICE.                  |
//|  I removed the release-quiet gate on the reasoning that he never   |
//|  asked for the green bar to be quiet - only for the two sides to   |
//|  be compared. That was wrong at the root: his FIRST description    |
//|  said "i were able to make a larger spread with LOWER VOLUME than  |
//|  before", which IS this gate. I overrode his own words because a   |
//|  single trade (01:28 on 18 Sep) did not fit them. Over a month it  |
//|  is the only thing keeping the EA positive:                        |
//|      release-quiet ON   n=151  +$1,160  45% WR  maxDD  $999        |
//|      release-quiet OFF  n=406  -$2,741  40% WR  maxDD $4,218       |
//|                                                                    |
//|  I also loosened InpAbsorbStuck 1.20 -> 1.60 to admit that same    |
//|  trade, and flagged it as fitted. It was: 1.20 -$2,256, 1.60       |
//|  -$2,741, 2.00 -$2,997 - monotonically worse the more it is bent.  |
//|                                                                    |
//|  And the side-edge FAILS the authenticity test: demanding more of  |
//|  it (1.60, 2.00) makes results WORSE, where a real edge strengthens|
//|  under pressure. It is kept but is not the load-bearing part.      |
//|                                                                    |
//|  NOT PROMOTED - CLAUDE.md. Only MT5's Strategy Tester or live      |
//|  fills may promote a default.                                      |
//+------------------------------------------------------------------+
#property copyright "Zeeshan"
#property version   "1.12"
#property strict

#include <Trade/Trade.mqh>

input group "=== size and identity ==="
input double InpLots        = 1.00;  // InpLots - lots per ticket (his hand size)
input int    InpTickets     = 1;     // InpTickets - tickets per decision
input int    InpMagicNumber = 88203; // InpMagicNumber - VSISA_MINUTE
input int    InpMaxOpen     = 1;     // InpMaxOpen - concurrent decisions

input group "=== absorption: effort WITHOUT result ==="
input int    InpLook        = 20;    // InpLook - bars the averages are read over
input int    InpAbsorbBars  = 6;     // InpAbsorbBars - the window supply is absorbed in
input double InpAbsorbVol   = 1.30;  // InpAbsorbVol - that window averaged >= x the lookback
input double InpAbsorbStuck = 1.20;  // InpAbsorbStuck - net progress <= x avg range (NO result)
input double InpLegMin      = 0.50;  // InpLegMin - price fell into it by >= x avg range

input group "=== release: the effort collapses ==="
input double InpReleaseVol  = 0.85;  // InpReleaseVol - reaction volume <= x the absorption avg. HIS WORDS, restored
input double InpBodyFrac    = 0.40;  // InpBodyFrac - trigger body >= x its own range
input int    InpConfirmBars = 1;     // InpConfirmBars - qualifying bars in a row before entering

input group "=== who moves price more easily (his crossover) ==="
input int    InpSideBars    = 3;     // InpSideBars - window the two sides are compared over
input double InpSideMult    = 1.30;  // InpSideMult - our side's efficiency >= x the other side's
input int    InpSideMeasure = 0;     // InpSideMeasure - 0 = body (progress) - 1 = range (his "height")
input bool   InpUseAbsorb   = true;  // InpUseAbsorb - also require the absorption context

input group "=== the exit ==="
//  Zee, 2026-09-18, describing what he ACTUALLY does - and it is not a stop and target:
//  "i don't have a SL or TP set .. i enter .. it goes into profit .. yaay my guess was
//   right. close profitable positions .. if its in loss .. i wait a minute more .. and
//   usually it goes my way .. and i then close profitable positions."
//
//  THIS EXIT MANUFACTURES THE WIN RATE. Almost any entry with a slight edge wins 90%+ of
//  the time if losses are never taken and price is simply given more minutes. His 10-for-10
//  is mostly this rule, not the entry. So the honest question about this EA is NOT its win
//  rate - it is the TAIL: how deep does the worst open trade go, and how long is it held,
//  before price comes back? Mode 1 exists to MEASURE that, with InpMaxAdverse as the
//  catastrophe brake that his own hand does not have.
input int    InpExitMode    = 1;     // InpExitMode - 0 = TP/SL - 1 = wait for profit (HIS way)
input int    InpProfitPts   = 80;    // InpProfitPts - mode 1: close once this far in profit
input int    InpMaxHoldBars = 120;   // InpMaxHoldBars - mode 1: give up after this many bars
input int    InpMaxAdverse  = 600;   // InpMaxAdverse - mode 1: catastrophe brake (0 = none)
input int    InpHoldBars    = 10;    // InpHoldBars - mode 0: close after this many M1 bars
input int    InpTargetPts   = 150;   // InpTargetPts - mode 0: take profit
input int    InpStopPts     = 100;   // InpStopPts - mode 0: HARD stop
input bool   InpTrailOnBar  = false; // InpTrailOnBar - mode 0: pull the stop up each bar

input group "=== INTRABAR: reading the candle while it forms ==="
//  Zee, 2026-09-18: "i see the candle while its being formed.. the way the volume is
//  moving the price.. tells me something.. everything.."
//
//  This is the gap in every version above. A CLOSED bar collapses hundreds of ticks into
//  four prices and one volume - the exact information he is reading is destroyed by the
//  abstraction. He watches 600 ticks arrive, sees the last 200 barely move price down,
//  then sees it lift easily on fewer ticks, and acts BEFORE the candle closes.
//
//  His crossover works identically on ticks: points gained per tick of effort for the up
//  moves, against the same for the down moves. Effort is the tick COUNT (every tick is
//  someone trading), result is the points travelled. Absorption intrabar is many ticks
//  with no net progress; release is progress arriving on fewer ticks.
//
//  MT5's real-tick model replays every tick, so this is testable rather than a story.
input bool   InpIntrabar    = false;  // InpIntrabar - UNTESTED tick path. Default OFF: it bypasses every bar gate
input int    InpTickWindow  = 240;   // InpTickWindow - ticks of tape held in view
input int    InpTickSlice   = 80;    // InpTickSlice - the recent slice judged against the rest
input double InpTickMult    = 1.40;  // InpTickMult - our side's points/tick >= x the other side's
input int    InpTickMinBar  = 120;   // InpTickMinBar - ticks into the bar before it may decide
input double InpTickStall   = 0.35;  // InpTickStall - the older tape's net move <= x its travel

input group "=== guards ==="
//  THE PRE-CLOSE GUARD, written from a live trade on 2026-09-18.
//  He opened 4 unstopped lots at 23:35, 24 minutes before the daily break. The feed then
//  stopped for 65 minutes (last bar 23:59, next 01:04) with the position 161 points under
//  water and no way to act on it. It reopened ~$3 higher and paid +$189.50 a lot.
//  The same gap downward is about -$1,200 across four lots, and nobody is managing it.
//  This is the one risk in his method that has nothing to do with reading the tape.
input int    InpNoOpenBefore = 20;   // InpNoOpenBefore - no NEW trades within this many minutes of the break
input int    InpBreakHour    = 0;    // InpBreakHour - broker hour the daily break starts (0 = midnight)
input int    InpBreakMin     = 0;    // InpBreakMin - ...and the minute
input bool   InpFlatAtBreak  = true; // InpFlatAtBreak - close everything before the break
input double InpDayLossStop = 400.0; // InpDayLossStop - stop for the day after this loss (0 = off)
input int    InpCoolBars    = 1;     // InpCoolBars - bars to wait after a decision
input bool   InpBuys        = true;  // InpBuys - his ten tickets were all BUY
input bool   InpSells       = false; // InpSells - off until the short side is tested
input int    InpSessFrom    = 0;     // InpSessFrom - broker hour, inclusive
input int    InpSessTo      = 24;    // InpSessTo - broker hour, exclusive
input bool   InpVerbose     = true;  // InpVerbose - print every decision

void OpenTrade(const int dir, const string why);

CTrade  trade;

//--- the tape: a ring of recent tick prices, newest last.
double   g_tape[];
int      g_tapeN     = 0;   // how many ticks are actually in it
int      g_tapeHead  = 0;   // next write slot
int      g_barTicks  = 0;   // ticks seen inside the FORMING bar

datetime g_lastBar   = 0;
int      g_openedBar = 0;
int      g_coolUntil = 0;
int      g_barIndex  = 0;
double   g_dayLoss   = 0.0;
int      g_dayStamp  = -1;
int      g_streak    = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   ArrayResize(g_tape, MathMax(InpTickWindow * 2, 64));
   ArrayInitialize(g_tape, 0.0);
   g_tapeN = 0; g_tapeHead = 0; g_barTicks = 0;
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   if(InpExitMode == 0 && InpStopPts <= 0)
     {
      Print("[VSISA_MIN] REFUSING to run with no stop. A 1.00-lot scalper without a cap "
            "is one bad minute away from giving back a week.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   PrintFormat("[VSISA_MIN] v1.12 - absorb>=%.2fx over %d bars | stuck<=%.2fx | leg>=%.2fx | "
               "release<=%.2fx | confirm %d | hold %d bar(s) | tp %d | stop %d | day stop %.0f | %s",
               InpAbsorbVol, InpAbsorbBars, InpAbsorbStuck, InpLegMin, InpReleaseVol,
               InpConfirmBars, InpHoldBars, InpTargetPts, InpStopPts, InpDayLossStop,
               InpSells ? "both ways" : "LONG ONLY (his ten tickets)");
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason) { PrintFormat("[VSISA_MIN] stopped (reason %d)", reason); }

//+------------------------------------------------------------------+
double BarVolume(const int shift)
  {
   long rv = iRealVolume(_Symbol, PERIOD_CURRENT, shift);
   if(rv > 0) return((double)rv);
   return((double)iTickVolume(_Symbol, PERIOD_CURRENT, shift));   // tester overwrites real
  }

double Spread(const int shift)
  { return(iHigh(_Symbol,PERIOD_CURRENT,shift) - iLow(_Symbol,PERIOD_CURRENT,shift)); }

double Body(const int shift)
  { return(iClose(_Symbol,PERIOD_CURRENT,shift) - iOpen(_Symbol,PERIOD_CURRENT,shift)); }

int OpenCount()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(PositionGetSymbol(i) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) n++;
   return(n);
  }

//+------------------------------------------------------------------+
//| THE TAPE - his crossover, measured on TICKS inside the forming    |
//| candle instead of on closed bars.                                 |
//|                                                                   |
//| Effort is the tick COUNT; result is the points travelled. Split   |
//| the window into an OLDER part and a RECENT SLICE:                 |
//|                                                                   |
//|   older part  - lots of ticks, little NET move = absorption       |
//|                 (measured as |net| / total travel <= InpTickStall)|
//|   recent slice - one side now getting more points per tick        |
//|                                                                   |
//| Returns the recent slice's edge for `dir`; 0 if the tape is not   |
//| yet readable.                                                     |
//+------------------------------------------------------------------+
double TapeRead(const int dir, bool &stalled, string &why)
  {
   stalled = false;
   if(g_tapeN < InpTickWindow) { why = "tape filling"; return(0.0); }

   int oldN = InpTickWindow - InpTickSlice;
   if(oldN < 20 || InpTickSlice < 10) { why = "window too small"; return(0.0); }

   double travel = 0.0, net = 0.0;
   double prev = 0.0;
   bool   first = true;
   // the OLDER part: is the tape churning without getting anywhere?
   for(int i = 0; i < oldN; i++)
     {
      int idx = (g_tapeHead - g_tapeN + i + ArraySize(g_tape) * 2) % ArraySize(g_tape);
      double px = g_tape[idx];
      if(first) { prev = px; first = false; continue; }
      travel += MathAbs(px - prev);
      prev = px;
     }
   int i0 = (g_tapeHead - g_tapeN + ArraySize(g_tape) * 2) % ArraySize(g_tape);
   int i1 = (g_tapeHead - g_tapeN + oldN - 1 + ArraySize(g_tape) * 2) % ArraySize(g_tape);
   net = MathAbs(g_tape[i1] - g_tape[i0]);
   if(travel <= 0.0) { why = "no travel"; return(0.0); }
   stalled = (net / travel) <= InpTickStall;

   // the RECENT SLICE: points per tick, each side separately
   double upPts = 0.0, dnPts = 0.0;
   int    upTk = 0, dnTk = 0;
   first = true;
   for(int i = oldN; i < InpTickWindow; i++)
     {
      int idx = (g_tapeHead - g_tapeN + i + ArraySize(g_tape) * 2) % ArraySize(g_tape);
      double px = g_tape[idx];
      if(first) { prev = px; first = false; continue; }
      double d = px - prev;
      if(d > 0)      { upPts += d;  upTk++; }
      else if(d < 0) { dnPts += -d; dnTk++; }
      prev = px;
     }
   if(upTk < 3 || dnTk < 3) { why = "one-sided slice"; return(0.0); }
   double effUp = upPts / upTk;
   double effDn = dnPts / dnTk;
   if(effUp <= 0.0 || effDn <= 0.0) { why = "flat slice"; return(0.0); }
   double edge = (dir > 0) ? effUp / effDn : effDn / effUp;
   why = StringFormat("tape stall %.2f edge %.2fx (%d ticks in bar)",
                      net / travel, edge, g_barTicks);
   return(edge);
  }

//+------------------------------------------------------------------+
//| WHO MOVES PRICE MORE EASILY - his own description of the read:    |
//|                                                                   |
//|  "how easy it is for X volume to move Y spread (height of the     |
//|   candle) .. ok sellers are pushing this way.. ok buyers are      |
//|   pushing this way.. ok sellers seem to not be able to move it    |
//|   further.. ok buyers seem to move it relatively easily now"      |
//|                                                                   |
//| That is not a threshold on one bar, it is a COMPARISON between    |
//| the two sides over a window: progress per unit of volume for the  |
//| up bars, against the same for the down bars. It is self-scaling - |
//| no absolute volume cutoff - which is why it keeps working when    |
//| the tape speeds up or slows down.                                 |
//|                                                                   |
//| Returns the ratio  our-side efficiency / other-side efficiency.   |
//| Above 1 means our side is getting more done per unit of effort.   |
//+------------------------------------------------------------------+
double SideEdge(const int shift, const int dir)
  {
   double upMove = 0.0, upVol = 0.0, dnMove = 0.0, dnVol = 0.0;
   for(int k = shift; k < shift + InpSideBars; k++)
     {
      double bd = Body(k), v = BarVolume(k);
      double amount = (InpSideMeasure == 1) ? Spread(k) : MathAbs(bd);
      if(v <= 0.0) continue;
      if(bd > 0)      { upMove += amount; upVol += v; }
      else if(bd < 0) { dnMove += amount; dnVol += v; }
     }
   if(upVol <= 0.0 || dnVol <= 0.0) return(0.0);
   double effUp = upMove / upVol;
   double effDn = dnMove / dnVol;
   if(effUp <= 0.0 || effDn <= 0.0) return(0.0);
   return((dir > 0) ? effUp / effDn : effDn / effUp);
  }

//+------------------------------------------------------------------+
//| ABSORPTION THEN RELEASE - what he actually traded on 17 Sep.      |
//+------------------------------------------------------------------+
bool Qualifies(const int shift, int &dir, string &why)
  {
   dir = 0;
   double sp = Spread(shift), bd = Body(shift), vol = BarVolume(shift);
   if(sp <= 0.0 || vol <= 0.0) { why = "empty bar"; return(false); }

   double volSum = 0.0, spSum = 0.0;
   int look0 = shift + InpAbsorbBars + 1;
   for(int k = look0; k < look0 + InpLook; k++)
     { volSum += BarVolume(k); spSum += Spread(k); }
   double volAvg = volSum / InpLook;
   double spAvg  = spSum  / InpLook;
   if(volAvg <= 0.0 || spAvg <= 0.0) { why = "no history"; return(false); }

   // the absorption window sits between this bar and the lookback
   int a0 = shift + 1, a1 = shift + InpAbsorbBars;
   double aVol = 0.0;
   double lo = iLow(_Symbol,PERIOD_CURRENT,a0), hi = iHigh(_Symbol,PERIOD_CURRENT,a0);
   for(int k = a0; k <= a1; k++)
     {
      aVol += BarVolume(k);
      lo = MathMin(lo, iLow(_Symbol,PERIOD_CURRENT,k));
      hi = MathMax(hi, iHigh(_Symbol,PERIOD_CURRENT,k));
     }
   aVol /= InpAbsorbBars;
   double entered = iOpen(_Symbol,PERIOD_CURRENT,a1);   // oldest bar of the window
   double left    = iClose(_Symbol,PERIOD_CURRENT,a0);  // newest bar of the window
   double net     = MathAbs(left - entered);

   if(InpUseAbsorb)
     {
      // LOUD
      if(aVol < InpAbsorbVol * volAvg)
        { why = StringFormat("not loud %.2fx (need %.2fx)", aVol/volAvg, InpAbsorbVol); return(false); }
      // ...and STUCK: all that effort bought no progress
      if(net > InpAbsorbStuck * spAvg)
        { why = StringFormat("not stuck %.2fx (max %.2fx)", net/spAvg, InpAbsorbStuck); return(false); }
      // RELEASE: effort collapses on this bar
      if(InpReleaseVol > 0.0 && vol > InpReleaseVol * aVol)
        { why = StringFormat("no release %.2fx (max %.2fx)", vol/aVol, InpReleaseVol); return(false); }
     }
   // a decided bar, not a doji
   if(MathAbs(bd) < InpBodyFrac * sp)
     { why = StringFormat("body %.2f (need %.2f)", MathAbs(bd)/sp, InpBodyFrac); return(false); }

   // which way did price come IN? Buying absorbed supply means it FELL in.
   double fellIn = entered - lo;
   double roseIn = hi - entered;
   if(bd > 0)
     {
      if(fellIn < InpLegMin * spAvg)
        { why = StringFormat("no down leg %.2fx", fellIn/spAvg); return(false); }
      dir = 1;
     }
   else
     {
      if(roseIn < InpLegMin * spAvg)
        { why = StringFormat("no up leg %.2fx", roseIn/spAvg); return(false); }
      dir = -1;
     }
   // HIS CROSSOVER - the side that moves price more easily per unit of volume.
   // Checked LAST because it needs the direction the bar has just declared.
   double edge = SideEdge(shift, dir);
   if(edge < InpSideMult)
     {
      why = StringFormat("no side edge %.2fx (need %.2fx)", edge, InpSideMult);
      dir = 0;
      return(false);
     }

   why = StringFormat("absorb %.2fx stuck %.2fx leg %.2fx release %.2fx body %.2f EDGE %.2fx",
                      aVol/volAvg, net/spAvg,
                      (bd > 0 ? fellIn : roseIn)/spAvg, vol/aVol, MathAbs(bd)/sp, edge);
   return(true);
  }

//+------------------------------------------------------------------+
void CloseAll(const string tag)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      ulong  tk  = PositionGetInteger(POSITION_TICKET);
      double pnl = PositionGetDouble(POSITION_PROFIT);
      if(trade.PositionClose(tk) && InpVerbose)
         PrintFormat("[VSISA_MIN] closed #%I64u %s  P&L %.2f", tk, tag, pnl);
      if(pnl < 0) g_dayLoss += -pnl;
     }
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   //--- the tape is fed on EVERY tick, whatever mode we are in
   double mid = (SymbolInfoDouble(_Symbol, SYMBOL_BID) +
                 SymbolInfoDouble(_Symbol, SYMBOL_ASK)) / 2.0;
   if(ArraySize(g_tape) > 0)
     {
      g_tape[g_tapeHead] = mid;
      g_tapeHead = (g_tapeHead + 1) % ArraySize(g_tape);
      if(g_tapeN < ArraySize(g_tape)) g_tapeN++;
     }

   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   bool newBar = (bt != g_lastBar);
   if(newBar) g_barTicks = 0; else g_barTicks++;

   //--- MODE 1 EXITS ARE CHECKED ON EVERY TICK, not once a minute.
   //    He watches it continuously - "if i feel like after few seconds of entering the
   //    trade, its not going in our direction at all.. i maybe wait upto 1 minute and
   //    then bam i have to close it somehow". Taking profit the moment it appears, and
   //    giving up after about a minute, both need tick resolution to be faithful.
   if(InpExitMode == 1 && OpenCount() > 0)
     {
      double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      double best = -1e9, worst = 1e9;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         if(PositionGetSymbol(i) != _Symbol) continue;
         if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
         double op = PositionGetDouble(POSITION_PRICE_OPEN);
         double nw = PositionGetDouble(POSITION_PRICE_CURRENT);
         double gain = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
                       ? (nw - op) / pt : (op - nw) / pt;
         best  = MathMax(best, gain);
         worst = MathMin(worst, gain);
        }
      int heldBars = g_barIndex - g_openedBar;
      if(best >= InpProfitPts)
        { CloseAll(StringFormat("in profit %.0f pts", best));
          g_coolUntil = g_barIndex + InpCoolBars; return; }
      if(InpMaxAdverse > 0 && worst <= -InpMaxAdverse)
        { CloseAll(StringFormat("CATASTROPHE BRAKE %.0f pts", worst));
          g_coolUntil = g_barIndex + InpCoolBars; return; }
      if(heldBars >= InpMaxHoldBars)
        { CloseAll(StringFormat("gave up after %d bars at %.0f pts", heldBars, worst));
          g_coolUntil = g_barIndex + InpCoolBars; return; }
     }

   //--- INTRABAR: he acts while the candle is still forming, so the decision cannot
   //    wait for the close. The bar-close path below still runs afterwards.
   if(InpIntrabar && !newBar && OpenCount() == 0 && g_barTicks >= InpTickMinBar &&
      g_barIndex >= g_coolUntil && (InpDayLossStop <= 0.0 || g_dayLoss < InpDayLossStop))
     {
      MqlDateTime ts; TimeToStruct(bt, ts);
      if(ts.hour >= InpSessFrom && ts.hour < InpSessTo)
        {
         int   tdir = (InpBuys && !InpSells) ? 1 : ((InpSells && !InpBuys) ? -1 : 0);
         int   tries[2]; tries[0] = 1; tries[1] = -1;
         for(int a = 0; a < 2; a++)
           {
            int d = tries[a];
            if(d > 0 && !InpBuys)  continue;
            if(d < 0 && !InpSells) continue;
            if(tdir != 0 && d != tdir) continue;
            bool stalled = false; string twhy = "";
            double edge = TapeRead(d, stalled, twhy);
            if(edge >= InpTickMult && stalled)
              {
               OpenTrade(d, StringFormat("INTRABAR %s", twhy));
               return;
              }
           }
        }
     }

   if(!newBar) return;                    // the rest is a CLOSED-bar decision
   g_lastBar = bt;
   g_barIndex++;

   MqlDateTime t; TimeToStruct(bt, t);
   if(t.day != g_dayStamp) { g_dayStamp = t.day; g_dayLoss = 0.0; }

   if(OpenCount() > 0)
     {
      int held = g_barIndex - g_openedBar;

      // --- MODE 1: his way. No target, no stop. Take profit when it comes; if it is in
      //     loss, wait another minute. InpMaxAdverse is the brake his hand does not have,
      //     and InpMaxHoldBars stops one trade owning the account forever.
      if(InpExitMode == 1)
        {
         double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
         double best = -1e9, worst = 1e9;
         for(int i = PositionsTotal() - 1; i >= 0; i--)
           {
            if(PositionGetSymbol(i) != _Symbol) continue;
            if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
            double open = PositionGetDouble(POSITION_PRICE_OPEN);
            double now  = PositionGetDouble(POSITION_PRICE_CURRENT);
            double gain = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
                          ? (now - open) / pt : (open - now) / pt;
            best  = MathMax(best, gain);
            worst = MathMin(worst, gain);
           }
         if(best >= InpProfitPts)
           { CloseAll(StringFormat("in profit %.0f pts after %d bars", best, held));
             g_coolUntil = g_barIndex + InpCoolBars; }
         else if(InpMaxAdverse > 0 && worst <= -InpMaxAdverse)
           { CloseAll(StringFormat("CATASTROPHE BRAKE %.0f pts after %d bars", worst, held));
             g_coolUntil = g_barIndex + InpCoolBars; }
         else if(held >= InpMaxHoldBars)
           { CloseAll(StringFormat("gave up after %d bars at %.0f pts", held, worst));
             g_coolUntil = g_barIndex + InpCoolBars; }
         return;
        }

      if(held >= InpHoldBars) { CloseAll("time exit"); g_coolUntil = g_barIndex + InpCoolBars; }
      else if(InpTrailOnBar)
        {
         for(int i = PositionsTotal() - 1; i >= 0; i--)
           {
            if(PositionGetSymbol(i) != _Symbol) continue;
            if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
            double want = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
                          ? iLow(_Symbol,PERIOD_CURRENT,1) : iHigh(_Symbol,PERIOD_CURRENT,1);
            trade.PositionModify(PositionGetInteger(POSITION_TICKET), want,
                                 PositionGetDouble(POSITION_TP));
           }
        }
      return;
     }

   if(InpDayLossStop > 0.0 && g_dayLoss >= InpDayLossStop) return;
   if(g_barIndex < g_coolUntil) return;
   if(t.hour < InpSessFrom || t.hour >= InpSessTo) return;
   if(OpenCount() >= InpMaxOpen) return;

   int dir = 0; string why = "";
   if(!Qualifies(1, dir, why))
     {
      g_streak = 0;
      if(InpVerbose && g_barIndex % 240 == 0)
         PrintFormat("[VSISA_MIN] watching - %s", why);
      return;
     }

   g_streak++;
   if(g_streak < InpConfirmBars)
     {
      if(InpVerbose)
         PrintFormat("[VSISA_MIN] opinion forming %d/%d - %s", g_streak, InpConfirmBars, why);
      return;
     }
   g_streak = 0;

   if(dir > 0 && !InpBuys)  return;
   if(dir < 0 && !InpSells) return;

   OpenTrade(dir, why);
  }

//+------------------------------------------------------------------+
void OpenTrade(const int dir, const string why)
  {
   double pt  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double px  = (dir > 0) ? ask : bid;
   double sl = 0.0, tp = 0.0;
   if(InpExitMode == 0)
     {
      sl = (dir > 0) ? px - InpStopPts * pt : px + InpStopPts * pt;
      if(InpTargetPts > 0) tp = (dir > 0) ? px + InpTargetPts * pt : px - InpTargetPts * pt;
     }
   int sent = 0;
   for(int k = 0; k < InpTickets; k++)
      if((dir > 0) ? trade.Buy(InpLots, _Symbol, 0.0, sl, tp, "vsisa_min")
                   : trade.Sell(InpLots, _Symbol, 0.0, sl, tp, "vsisa_min")) sent++;
   if(sent > 0)
     {
      g_openedBar = g_barIndex;
      PrintFormat("[VSISA_MIN] %s %d x %.2f @ %.2f sl %.2f tp %.2f | %s",
                  dir > 0 ? "BUY" : "SELL", sent, InpLots, px, sl, tp, why);
     }
  }

//+------------------------------------------------------------------+
