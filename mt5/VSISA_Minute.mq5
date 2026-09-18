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
#property version   "1.58"
#property strict

#include <Trade/Trade.mqh>
#include <Canvas/Canvas.mqh>

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
//  2026-09-18, the deal: "then perfect me the entry 100% and i'll exit myself. i'll start
//  the EA only when i'm sitting on the computer."
//  MODE 2 IS THAT DEAL. The EA opens and then NEVER touches the position - no stop, no
//  target, no time exit, no brake. It is his trade from the moment it fills. This is the
//  honest division: four months of testing showed the entry is mechanisable and every exit
//  I encoded lost money, while his exit has taken 17 of 17 live. Mode 2 must only ever run
//  while he is watching, which is the condition he set himself.
input bool   InpMeterOnly   = true;  // InpMeterOnly - DRAW ONLY, never place a trade (his call)
input int    InpExitMode    = 1;     // InpExitMode - 0 = TP/SL - 1 = wait for profit - 2 = ENTRY ONLY
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
input int    InpTickWindow  = 120;   // InpTickWindow - ticks of tape held in view
input double InpTickGain    = 3.0;   // InpTickGain - spreads the needle over the dial (see notes)
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

input group "=== the running commentary ==="
//  Zee, 2026-09-18: "the EA should verbally tell me at each minute what its THINKING..
//  so i'm never left waiting to see oh whats this EA doing its complete silence all day."
//
//  Every closed minute it says, in words, what the sellers did, what the buyers did, and
//  which condition is still missing. It paints on the chart (always visible) and writes to
//  the Experts log, so the reasoning can be read back afterwards against what price did.
input group "=== the imbalance meter (a real gauge, drawn live) ==="
//  Zee, 2026-09-18: "make an imbalance meter .. real-time .. are u allowed to draw on an
//  MT5 chart the realtime imbalance meter >> LIKE A speedometer."
//
//  Yes - CCanvas renders a bitmap on the chart, so this is a real gauge and not a text
//  readout. The needle is the one number he trades: who is getting more price per unit of
//  effort. It reads the TICK tape, so it moves continuously inside the forming candle
//  rather than once a minute - which is the thing he says he actually watches.
//
//      needle hard LEFT   sellers are moving price easily
//      needle CENTRE      neither side is getting anywhere (the absorption he waits for)
//      needle hard RIGHT  buyers are moving price easily
//  2026-09-18, on which feed the meter should read:
//  "the same volume numbers you see on TradingView .. because the colors of volumes on
//   MT5 follow a different convention than tradingview and my eyes are trained on
//   tradingview's volumes.. on MT5 a red volume doesnot mean its selling, it means its
//   smaller than previous candle, duh!"
//
//  He is right, and it is a real trap. MT5 colours a volume bar by comparing it with the
//  PREVIOUS bar - red means "smaller than the last one", nothing to do with direction.
//  TradingView colours by the candle: green when close > open. Same numbers, opposite
//  meaning. This meter uses the TradingView convention, and source 1 reads the OANDA
//  minute table - the same feed his chart draws - so the numbers on the gauge are the
//  numbers under his eye.
//
//  The trade-off, stated plainly: OANDA volume arrives once a MINUTE, so on source 1 the
//  needle steps each minute instead of flowing with every tick. Source 0 flows tick by
//  tick but counts TICKS as effort, because this broker publishes no real volume for gold.
input int    InpMeterSource = 1;     // InpMeterSource - 0 = live ticks (broker) · 1 = OANDA volume (TradingView)
//  2026-09-18: "it says buyers finding it easier on the tradingview dial... when infact
//  buyer volumes have stopped coming and now its red volumes coming with price moving
//  downwards"
//  He was right and it was a lag, not a miscalculation: a flat 6-minute average still
//  carried four big green bars from BEFORE the turn, so the dial described the stretch he
//  had already stopped trading. A meter for spotting turns cannot weight a six-minute-old
//  bar the same as the one forming now.
//  InpMeterDecay fixes it: each older minute counts less. At 0.55 the newest bar carries
//  about twice the weight of the one before it and eight times the one three back, so the
//  needle turns with the tape while still being an average rather than a single candle.
input int    InpMeterBars   = 5;     // InpMeterBars - minutes in view (newest weigh most)
input double InpMeterDecay  = 0.55;  // InpMeterDecay - weight of each older minute (1.0 = flat average)
input string InpOandaFile   = "oanda_bars.csv"; // InpOandaFile - in Common\Files
//  2026-09-18: "oh can u create a tick by tick dial too .. live tick responsiveness.. its
//  ok it can be based on broker volume.. as sometimes i trade based on very fast decisions
//  and a candle forming"
//  So both dials are drawn together. LEFT is the true-volume read his eye is trained on,
//  stepping once a minute. RIGHT is the broker tick tape, flowing continuously inside the
//  forming candle. When they agree, the read is solid on both clocks; when the fast dial
//  swings and the slow one has not yet, that is the move happening before the minute closes.
input bool   InpGaugeDual   = true;  // InpGaugeDual - draw BOTH dials: volume (slow) + ticks (fast)
input bool   InpGauge       = true;  // InpGauge - draw the live imbalance meter
input int    InpGaugeCorner = 0;     // InpGaugeCorner - 0 TL · 1 TR · 2 BL · 3 BR
input int    InpGaugeX      = 20;    // InpGaugeX - pixels from that corner
input int    InpGaugeY      = 110;   // InpGaugeY - pixels from that corner (clears the commentary)
input int    InpGaugeSize   = 460;   // InpGaugeSize - width of ONE dial, in pixels
input int    InpFontScale   = 150;   // InpFontScale - percent. 100 = normal, 150 = half again bigger

input bool   InpNarrate     = true;  // InpNarrate - say what it is thinking every minute
input bool   InpNarrateChart = true; // InpNarrateChart - also paint it on the chart
//  Alerts were firing on every near-miss and MT5 opens a modal window for each one -
//  four pop-ups in fifteen minutes, stealing focus while he is trying to trade.
//  0 = silent (the chart still shows everything)
//  1 = only when ALL conditions are met - a real signal
//  2 = also when one condition is short - the heads-up
input int    InpAlertMode   = 0;     // InpAlertMode - 0 silent (the panel says it all) · 1 signals · 2 near-misses
input bool   InpAlertSound  = true;  // InpAlertSound - a sound instead of a pop-up window

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
   GaugeCreate();
   ArrayResize(g_tape, MathMax(InpTickWindow * 2, 64));
   ArrayInitialize(g_tape, 0.0);
   g_tapeN = 0; g_tapeHead = 0; g_barTicks = 0;

   // the tick dial was blank for the first minute after every reattach - prefill it from
   // the terminal's own tick history so it is useful the moment it is dragged on.
   MqlTick pre[];
   int got = CopyTicks(_Symbol, pre, COPY_TICKS_ALL, 0, InpTickWindow * 2);
   if(got > 0)
     {
      int cap = ArraySize(g_tape);
      int take = MathMin(got, cap);
      for(int i = got - take; i < got; i++)
        {
         double mid = (pre[i].bid + pre[i].ask) / 2.0;
         if(mid <= 0.0) mid = pre[i].last;
         if(mid <= 0.0) continue;
         g_tape[g_tapeHead] = mid;
         g_tapeHead = (g_tapeHead + 1) % cap;
         if(g_tapeN < cap) g_tapeN++;
        }
      PrintFormat("[VSISA_MIN] tick dial primed with %d ticks from history", g_tapeN);
     }
   else
      PrintFormat("[VSISA_MIN] no tick history available (error %d) - the fast dial will "
                  "fill as ticks arrive", GetLastError());
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   if(InpMeterOnly)
      Print("[VSISA_MIN] METER ONLY. This EA will NOT trade. It draws the imbalance gauge and tells you what it sees; every entry and exit is yours.");
   if(InpExitMode == 2)
      Print("[VSISA_MIN] ENTRY-ONLY MODE. This EA will OPEN trades and NEVER close them. No stop, no target. Run it ONLY while you are at the screen.");
   if(InpExitMode == 0 && InpStopPts <= 0)
     {
      Print("[VSISA_MIN] REFUSING to run with no stop. A 1.00-lot scalper without a cap "
            "is one bad minute away from giving back a week.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   PrintFormat("[VSISA_MIN] v1.58 - absorb>=%.2fx over %d bars | stuck<=%.2fx | leg>=%.2fx | "
               "release<=%.2fx | confirm %d | hold %d bar(s) | tp %d | stop %d | day stop %.0f | %s",
               InpAbsorbVol, InpAbsorbBars, InpAbsorbStuck, InpLegMin, InpReleaseVol,
               InpConfirmBars, InpHoldBars, InpTargetPts, InpStopPts, InpDayLossStop,
               InpSells ? "both ways" : "LONG ONLY (his ten tickets)");
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   GaugeDestroy();
   Comment("");
   PrintFormat("[VSISA_MIN] stopped (reason %d)", reason);
  }

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
//| THE IMBALANCE METER - a real gauge, drawn on the chart.           |
//|                                                                   |
//| The needle is the imbalance he reads by eye:                      |
//|                                                                   |
//|     imbalance = (buyers' points-per-tick - sellers' points-per-tick)
//|                 -------------------------------------------------- |
//|                 (buyers' points-per-tick + sellers' points-per-tick)
//|                                                                   |
//| bounded -1 .. +1, so the needle cannot run off the dial however    |
//| violent the tape gets. It is computed from the TICK ring, so it    |
//| moves inside the forming candle instead of once a minute.         |
//+------------------------------------------------------------------+
CCanvas g_gauge;
bool    g_gaugeOK = false;

//--- what the last closed minute decided, in words, for the panel under the dials
string g_stVerdict = "starting up";
double g_stEffUp   = 0.0;      // ground per 100 volume, buyers - NOW
double g_stEffDn   = 0.0;      // ground per 100 volume, sellers - NOW
string g_stUpWord  = "";       // are the buyers getting stronger or weaker than they were?
string g_stDnWord  = "";
uint   g_stUpCol   = 0xFF6ED7AF;
uint   g_stDnCol   = 0xFFE27873;
string g_stNeed    = "";
string g_stNote    = "";
uint   g_stColour  = 0xFFB0B4BE;

//--- the OANDA minute table: the same feed his TradingView chart draws.
#define OV_KEEP 400
datetime g_ovTime[OV_KEEP];
double   g_ovOpen[OV_KEEP], g_ovClose[OV_KEEP], g_ovHigh[OV_KEEP], g_ovLow[OV_KEEP];
double   g_ovVol[OV_KEEP];
int      g_ovN = 0;

//--- the strength needs a memory: 95%% on the way UP is a setup, 60%% on the way DOWN is a
//--- move that already happened. Zee: "after imbalance it switches to forming.. instead it
//--- could measure and say let's say: imbalance fading out".
double   g_stPeak     = 0.0;      // highest strength lately
double   g_stPrev     = 0.0;      // what it was on the previous minute
datetime g_stPeakTime = 0;
datetime g_stLastBar  = 0;
double   g_stCurr     = 0.0;
datetime g_ovLastRead = 0;

//+------------------------------------------------------------------+
//| Pull the OANDA minute rows. Cheap: re-reads only every 5 seconds, |
//| and keeps just the newest OV_KEEP minutes.                        |
//+------------------------------------------------------------------+
void OandaRefresh()
  {
   if(TimeLocal() - g_ovLastRead < 5) return;
   g_ovLastRead = TimeLocal();

   int h = FileOpen(InpOandaFile, FILE_READ | FILE_CSV | FILE_COMMON | FILE_ANSI |
                 FILE_SHARE_READ | FILE_SHARE_WRITE, ',');
   if(h == INVALID_HANDLE)
     {
      static datetime lastMoan = 0;
      if(TimeLocal() - lastMoan > 60)
        {
         lastMoan = TimeLocal();
         PrintFormat("[VSISA_MIN] cannot open %s in the shared Files folder (error %d) - "
                     "the VOLUME dial will stay blank", InpOandaFile, GetLastError());
        }
      return;
     }

   // seek to near the end: we want the newest OV_KEEP minutes, nothing older. A row is
   // about 45 bytes, so this reads a small tail instead of the whole 2 MB table.
   ulong size = FileSize(h);
   ulong want = (ulong)OV_KEEP * 80;
   if(size > want)
     {
      FileSeek(h, (long)(size - want), SEEK_SET);
      FileReadString(h);          // discard the partial line we landed in the middle of
      while(!FileIsLineEnding(h) && !FileIsEnding(h)) FileReadString(h);
     }
   int n = 0;
   datetime tt[OV_KEEP]; double oo[OV_KEEP], hh[OV_KEEP], ll[OV_KEEP], cc[OV_KEEP], vv[OV_KEEP];
   while(!FileIsEnding(h))
     {
      string ts = FileReadString(h);
      if(ts == "") break;
      double o = StringToDouble(FileReadString(h));
      double hi = StringToDouble(FileReadString(h));
      double lo = StringToDouble(FileReadString(h));
      double c  = StringToDouble(FileReadString(h));
      double v  = StringToDouble(FileReadString(h));
      datetime t = StringToTime(ts);
      if(t <= 0) continue;
      int slot = n % OV_KEEP;
      tt[slot] = t; oo[slot] = o; hh[slot] = hi; ll[slot] = lo; cc[slot] = c; vv[slot] = v;
      n++;
     }
   FileClose(h);
   if(n <= 0) return;

   int keep = MathMin(n, OV_KEEP);
   static bool announced = false;
   if(!announced && keep > 0)
     {
      announced = true;
      PrintFormat("[VSISA_MIN] OANDA volume table read: %d rows, keeping newest %d", n, keep);
     }
   g_ovN = keep;
   for(int i = 0; i < keep; i++)
     {
      int slot = (n - keep + i) % OV_KEEP;
      g_ovTime[i] = tt[slot]; g_ovOpen[i] = oo[slot]; g_ovHigh[i] = hh[slot];
      g_ovLow[i] = ll[slot]; g_ovClose[i] = cc[slot]; g_ovVol[i] = vv[slot];
     }
  }

//+------------------------------------------------------------------+
//| The imbalance on the OANDA table, TradingView's convention:       |
//| a bar is BUYING when close > open, SELLING when close < open -    |
//| never "smaller than the previous bar", which is MT5's colouring   |
//| and means nothing about direction.                                |
//+------------------------------------------------------------------+
double OandaImbalance(double &effUpOut, double &effDnOut, int &barsOut, double &ageOut)
  {
   effUpOut = 0.0; effDnOut = 0.0; barsOut = 0; ageOut = -1;
   if(g_ovN < InpMeterBars + 1) return(0.0);
   int from = g_ovN - InpMeterBars;
   double upP = 0.0, dnP = 0.0, upV = 0.0, dnV = 0.0;
   double decay = (InpMeterDecay <= 0.0 || InpMeterDecay > 1.0) ? 1.0 : InpMeterDecay;
   for(int i = from; i < g_ovN; i++)
     {
      double body = g_ovClose[i] - g_ovOpen[i];
      double v = g_ovVol[i];
      if(v <= 0.0) continue;
      int age = (g_ovN - 1) - i;                  // 0 = the newest closed minute
      double wgt = MathPow(decay, age);
      if(body > 0)      { upP += body * wgt;  upV += v * wgt; }
      else if(body < 0) { dnP += -body * wgt; dnV += v * wgt; }
     }
   barsOut = InpMeterBars;
   ageOut = (double)(TimeCurrent() - g_ovTime[g_ovN - 1]) / 60.0;

   // the BARS keep the efficiency comparison - ground per unit of volume, each side
   if(upV > 0.0) effUpOut = upP / upV;
   if(dnV > 0.0) effDnOut = dnP / dnV;

//  THE NEEDLE IS DIRECTION, NOT EFFICIENCY.
//  v1.46 put efficiency on the dial and Zee caught it twice: "the tradingview dial says
//  buyers finding it easier.. when the price is moving downwards for past 3 red candles".
//  Both readings were arithmetically right - one big efficient green outscores three heavy
//  inefficient reds on ground-per-volume - but a NEEDLE that points BUY while the candles
//  fall is a meter that contradicts the chart, and he would be right to stop trusting it.
//  So the dial now answers "which way is price actually getting somewhere", and the bars
//  underneath answer "who is finding it easier". Two different questions, two places, and
//  the dial can never disagree with the candles again.
   double net = upP - dnP;          // both are already recency-weighted
   double tot = upP + dnP;
   if(tot <= 0.0) return(0.0);
   double imb = net / tot;
   if(imb > 1.0)  imb = 1.0;
   if(imb < -1.0) imb = -1.0;
   return(imb);
  }

double TapeImbalance(double &effUpOut, double &effDnOut, int &ticksOut)
  {
//  WHY THIS IS NOT THE SAME FORMULA AS THE VOLUME DIAL.
//  v1.42 compared average points per UPTICK against average points per DOWNTICK, which is
//  the volume dial's formula with ticks standing in for volume. Zee caught it immediately:
//  "ticks dial say both sides stuck but its a very large down candle". He was right, and
//  the fault is structural - a tick is roughly a fixed size, so points-per-tick is about
//  equal for both sides ALWAYS. A collapse is made of MANY downticks, not bigger ones, and
//  that formula cannot see a count asymmetry at all. It would read "balanced" through a
//  crash.
//
//  On the tape the honest measure of the same idea is net displacement against total
//  travel: of all the ground covered, how much became actual progress?
//
//      imbalance = (last - first) / sum(|tick moves|)
//
//  A hard down candle: travelled 5.0, ended 4.0 lower -> -0.80, pinned left.
//  Churn that goes nowhere: travelled 5.0, ended 0.1 lower -> -0.02, centre. THAT is
//  absorption - lots of effort, no ground - and it is exactly what he waits for.
   effUpOut = 0.0; effDnOut = 0.0; ticksOut = g_tapeN;
   int cap = ArraySize(g_tape);
   if(cap <= 0 || g_tapeN < 20) return(0.0);
   int n = MathMin(g_tapeN, InpTickWindow);

   double travel = 0.0, upP = 0.0, dnP = 0.0;
   double first = 0.0, last = 0.0, prev = 0.0;
   bool started = false;
   for(int i = g_tapeN - n; i < g_tapeN; i++)
     {
      int idx = (g_tapeHead - g_tapeN + i + cap * 2) % cap;
      double px = g_tape[idx];
      if(!started) { first = px; prev = px; started = true; continue; }
      double d = px - prev;
      travel += MathAbs(d);
      if(d > 0) upP += d; else dnP += -d;
      prev = px;
      last = px;
     }
   if(travel <= 0.0 || !started) return(0.0);

   // the bars under the panel still want "ground per unit of effort" for each side
   effUpOut = upP / n;
   effDnOut = dnP / n;

//  GAIN. net/travel is correct but COMPRESSED: over a long tick window `travel` collects
//  every micro-oscillation, so even a hard candle scores ~0.17 and lands inside the
//  "going nowhere" band. Zee: "the right dial direction keeps saying going nowhere.. even
//  at fast forming large candles." The ratio was right, the scale was not - so it is
//  stretched to use the whole dial, and the window shortened to track the forming candle.
   double imb = (last - first) / travel * InpTickGain;
   if(imb > 1.0)  imb = 1.0;
   if(imb < -1.0) imb = -1.0;
   return(imb);
  }

void GaugeCreate()
  {
   if(!InpGauge) return;
   int w = InpGaugeDual ? (int)(InpGaugeSize * 1.92) : InpGaugeSize;
   int h = (int)(InpGaugeSize * 1.46) + (MathMax(80, InpFontScale) - 100) * InpGaugeSize / 260;
   if(!g_gauge.CreateBitmapLabel("vsisa_gauge", InpGaugeX, InpGaugeY, w, h,
                                 COLOR_FORMAT_ARGB_NORMALIZE))
     { Print("[VSISA_MIN] gauge could not be created"); return; }
   ObjectSetInteger(0, "vsisa_gauge", OBJPROP_CORNER, InpGaugeCorner);
   ObjectSetInteger(0, "vsisa_gauge", OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
   // with a right/bottom corner the offset is measured to the object's own edge, so a wide
   // canvas anchored 20px from the right runs off the chart - push it in by its own size.
   int px = InpGaugeX, py = InpGaugeY;
   if(InpGaugeCorner == 1 || InpGaugeCorner == 3) px = InpGaugeX + w;
   if(InpGaugeCorner == 2 || InpGaugeCorner == 3) py = InpGaugeY + h;
   ObjectSetInteger(0, "vsisa_gauge", OBJPROP_XDISTANCE, px);
   ObjectSetInteger(0, "vsisa_gauge", OBJPROP_YDISTANCE, py);
   ObjectSetInteger(0, "vsisa_gauge", OBJPROP_BACK, false);
   ObjectSetInteger(0, "vsisa_gauge", OBJPROP_SELECTABLE, true);
   ObjectSetInteger(0, "vsisa_gauge", OBJPROP_HIDDEN, false);
   PrintFormat("[VSISA_MIN] gauge %dx%d at corner %d (%d,%d) - drag it if it sits badly",
               w, h, InpGaugeCorner, px, py);
   g_gaugeOK = true;
  }

void GaugeDestroy()
  {
   if(g_gaugeOK) { g_gauge.Destroy(); g_gaugeOK = false; }
   ObjectDelete(0, "vsisa_gauge");
  }

//+------------------------------------------------------------------+
//| The needle in his own language. He reads this as RESISTANCE -     |
//| "it measures resistance based on volume" - so the dial says which |
//| side is meeting less of it, rather than making him read a decimal.|
//| The middle band is the one that matters most: neither side is     |
//| getting anywhere, which is the absorption he waits for.           |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Is this side getting MORE or LESS for its effort than it was?     |
//| "ok sellers seem to not be able to move it further.. ok buyers    |
//|  seem to move it relatively easily now" - that is a change over   |
//| time, so each side is compared with ITSELF over the previous      |
//| stretch, not with the other side (the bar lengths already show    |
//| the contest).                                                     |
//|                                                                   |
//| NOT a probability. Nothing here is calibrated against outcomes,   |
//| and calling it one would invite trusting it further than it has   |
//| earned. It says what the tape just did, not what happens next.    |
//+------------------------------------------------------------------+
string SideWord(const double now, const double before, uint &col, const bool isSeller)
  {
//  Every label must say a STATE or a CHANGE. v1.45 printed the bare noun "selling" when
//  there was no earlier selling to compare against, which reads as neither - Zee: "the word
//  selling is neutral.. it doesnot say if its a verb / comparison etc". These all answer
//  "what are they doing, compared with a moment ago".
   if(now <= 0.0)
     {
      col = isSeller ? 0xFF8A6A68 : 0xFF6A8A7C;
      return(isSeller ? "sellers gone" : "buyers gone");
     }
   if(before <= 0.0)
     {
      col = isSeller ? 0xFFFF6B66 : 0xFF3FE39B;
      return(isSeller ? "SELLERS JUST ARRIVED" : "BUYERS JUST ARRIVED");
     }
   double r = now / before;
   if(r >= 1.35) { col = isSeller ? 0xFFFF6B66 : 0xFF3FE39B;
                   return(isSeller ? "SELLERS STRONGER" : "BUYERS STRONGER"); }
   if(r <= 0.65) { col = 0xFFE1C85A;
                   return(isSeller ? "SELLERS WEAKENING" : "BUYERS WEAKENING"); }
   col = isSeller ? 0xFFE27873 : 0xFF6ED7AF;
   return(isSeller ? "sellers holding steady" : "buyers holding steady");
  }

//+------------------------------------------------------------------+
//| IMBALANCE STRENGTH - 0 to 1. Not a direction.                     |
//|                                                                   |
//| Zee, 2026-09-18: "the first dial.. it should be the imbalance      |
//| strength, low to high.. when it touches highest -> we look at the  |
//| tick dial and see if its making a move in which direction and take |
//| a trade in that direction". And on why direction was the wrong     |
//| thing to put there: "the current price movement we can also read   |
//| from chart's candles" - a needle that repeats the chart is wasted  |
//| space, and it was contradicting the candles besides.               |
//|                                                                   |
//| Strength is how RIPE the setup is, from the three things his       |
//| method actually requires:                                          |
//|   LOUD    the fight is heavier than normal      (effort)           |
//|   STUCK   all that effort is going nowhere      (no result)        |
//|   GAP     one side is getting far more per unit (someone winning)  |
//+------------------------------------------------------------------+
double ImbalanceStrength(double &loudOut, double &stuckOut, double &gapOut)
  {
   loudOut = 0.0; stuckOut = 0.0; gapOut = 0.0;
   if(g_ovN < InpMeterBars + 2) return(0.0);

   double decay = (InpMeterDecay <= 0.0 || InpMeterDecay > 1.0) ? 1.0 : InpMeterDecay;
   int from = g_ovN - InpMeterBars;

   double volNow = 0.0, wsum = 0.0;
   double upP = 0.0, dnP = 0.0, upV = 0.0, dnV = 0.0;
   for(int i = from; i < g_ovN; i++)
     {
      int age = (g_ovN - 1) - i;
      double wgt = MathPow(decay, age);
      double body = g_ovClose[i] - g_ovOpen[i];
      double v = g_ovVol[i];
      volNow += v * wgt; wsum += wgt;
      if(v <= 0.0) continue;
      if(body > 0)      { upP += body * wgt;  upV += v * wgt; }
      else if(body < 0) { dnP += -body * wgt; dnV += v * wgt; }
     }
   if(wsum <= 0.0) return(0.0);
   volNow /= wsum;

   // the normal to judge against: the stretch before this one, unweighted
   double volBase = 0.0, rngBase = 0.0; int nb = 0;
   for(int i = MathMax(0, from - 20); i < from; i++)
     { volBase += g_ovVol[i]; rngBase += (g_ovHigh[i] - g_ovLow[i]); nb++; }
   if(nb <= 0 || volBase <= 0.0 || rngBase <= 0.0) return(0.0);
   volBase /= nb; rngBase /= nb;

   double net = MathAbs(g_ovClose[g_ovN - 1] - g_ovOpen[from]);

//  RECALIBRATED 2026-09-18. The first formula scored a total imbalance at 26%:
//  "the left dial for imbalance strength said nothing here yet even when the right one
//  kept saying buyers meet no resistance" - with sellers GONE and buyers taking 770 volume
//  for 7.38 of ground, it read loud 0%, stuck 4%, gap 100%.
//  Two errors. It demanded a LOUD fight, when one side simply vanishing is every bit as
//  strong a signal. And STUCK punished price for moving - so the score collapsed at the
//  very moment the imbalance resolved, which is backwards for an instrument meant to say
//  "now". The three parts are now the three ways an imbalance is actually strong:
//
//    GAP    one side gets far more ground per unit of volume   (who is winning)
//    SHARE  ...and the other side has largely stopped trading  (how one-sided)
//    PUSH   ...with real volume behind it, not a dead tape     (conviction)
   double effUp = (upV > 0.0) ? upP / upV : 0.0;
   double effDn = (dnV > 0.0) ? dnP / dnV : 0.0;
   double gap   = (effUp + effDn > 0.0)
                  ? MathAbs(effUp - effDn) / (effUp + effDn) : 0.0;

   double winV  = (effUp >= effDn) ? upV : dnV;
   double loseV = (effUp >= effDn) ? dnV : upV;
   double share = (winV + loseV > 0.0) ? winV / (winV + loseV) : 0.5;
   double push  = volNow / volBase;

   gapOut   = MathMin(1.0, gap / 0.60);                              // 0.60+ = total
   stuckOut = MathMin(1.0, MathMax(0.0, (share - 0.50) * 2.0));      // one-sidedness
   loudOut  = MathMin(1.0, MathMax(0.0, (push - 0.70) / 0.60));      // 1.30x = full

   return(MathMin(1.0, gapOut * 0.45 + stuckOut * 0.30 + loudOut * 0.25));
  }

//+------------------------------------------------------------------+
//| WHICH STAGE OF THE SETUP ARE WE IN?                               |
//|                                                                   |
//| Zee, 2026-09-18: "we classify our strategy into two things:       |
//|   Selling campaign (high volume red candles)                      |
//|   Low volume reaction Candle                                      |
//|   Price moving up on low volume candles                           |
//|  beneath the dials maybe we can show which stage of the setup     |
//|  we're in right now."                                             |
//|                                                                   |
//| The dials say how strong and which way; this says HOW FAR ALONG,  |
//| which is the part that tells him whether to get ready or to act.  |
//| Mirrored for the short side: a BUYING campaign, a low-volume       |
//| reaction, then price sliding on low volume.                       |
//|                                                                   |
//| Returns 0 nothing · 1 campaign · 2 reaction · 3 moving away.      |
//| `dir` is the direction the SETUP points (campaign down -> buy).   |
//+------------------------------------------------------------------+
int SetupStage(int &dir, double &campVol, int &campLen)
  {
   dir = 0; campVol = 0.0; campLen = 0;
   if(g_ovN < 26) return(0);

   int last = g_ovN - 1;

   // the normal to judge "heavy" against
   double base = 0.0; int nb = 0;
   for(int i = g_ovN - 26; i < g_ovN - 6; i++) { base += g_ovVol[i]; nb++; }
   if(nb <= 0 || base <= 0.0) return(0);
   base /= nb;

   // 1. THE CAMPAIGN - a run of same-direction bars on heavy volume, somewhere in the
   //    last dozen minutes. Walk back from the newest bar looking for where it ended.
   int campEnd = -1, campDir = 0;
   for(int e = last; e >= last - 9 && e >= 3; e--)
     {
      int d = (g_ovClose[e] > g_ovOpen[e]) ? 1 : ((g_ovClose[e] < g_ovOpen[e]) ? -1 : 0);
      if(d == 0) continue;
      int len = 0; double vsum = 0.0;
      for(int k = e; k >= 0 && len < 8; k--)
        {
         int dk = (g_ovClose[k] > g_ovOpen[k]) ? 1 : ((g_ovClose[k] < g_ovOpen[k]) ? -1 : 0);
         if(dk != d) break;
         vsum += g_ovVol[k]; len++;
        }
      if(len >= 2 && (vsum / len) >= base * 1.15)
        { campEnd = e; campDir = d; campVol = vsum / len; campLen = len; break; }
     }
   if(campEnd < 0) return(0);

   dir = -campDir;                       // a SELLING campaign sets up a BUY

   // 2. THE REACTION - after the campaign, a quiet bar that stops going its way
   int react = -1;
   for(int i = campEnd + 1; i <= last; i++)
     {
      if(g_ovVol[i] <= campVol * InpReleaseVol)
        {
         int di = (g_ovClose[i] > g_ovOpen[i]) ? 1 : ((g_ovClose[i] < g_ovOpen[i]) ? -1 : 0);
         if(di != campDir) { react = i; break; }
        }
     }
   if(react < 0) return(1);
   if(react == last) return(2);

   // 3. MOVING AWAY - price continuing against the campaign, still on light volume
   int moved = 0;
   for(int i = react + 1; i <= last; i++)
     {
      int di = (g_ovClose[i] > g_ovOpen[i]) ? 1 : ((g_ovClose[i] < g_ovOpen[i]) ? -1 : 0);
      if(di == dir && g_ovVol[i] <= campVol) moved++;
     }
   return(moved > 0 ? 3 : 2);
  }

string StrengthWords(const double st, uint &col)
  {
   bool falling = (st < g_stPrev - 0.03);
   bool spent   = (g_stPeak >= 0.65 && st < g_stPeak - 0.12);

   if(st >= 0.80) { col = ARGB(255,  80, 235, 160); return("IMBALANCE READY - check direction"); }
   if(spent)
     {
      col = ARGB(255, 150, 140, 200);
      return(StringFormat("IMBALANCE FADING - peaked at %.0f%%", g_stPeak * 100));
     }
   if(st >= 0.60)
     {
      col = ARGB(255, 225, 200, 90);
      return(falling ? "easing off" : "BUILDING - nearly there");
     }
   if(st >= 0.35)
     {
      col = ARGB(255, 190, 170, 110);
      return(falling ? "fading" : "forming");
     }
   col = ARGB(255, 130, 136, 148);
   return("nothing here yet");
  }

string ResistanceWords(const double imb, uint &col)
  {
   if(imb >= 0.40) { col = ARGB(255,  70, 230, 155); return("BUY - buyers meet no resistance"); }
   if(imb >= 0.15) { col = ARGB(255,  60, 185, 135); return("leaning BUY"); }
   if(imb <= -0.40){ col = ARGB(255, 255,  95,  90); return("SELL - sellers meet no resistance"); }
   if(imb <= -0.15){ col = ARGB(255, 215,  90,  85); return("leaning SELL"); }
   col = ARGB(255, 225, 200, 90);
   return("no side favoured yet");
  }

//+------------------------------------------------------------------+
//| One dial. `imb` is -1..+1; the needle sweeps 180 degrees.         |
//+------------------------------------------------------------------+
void DrawDial(const int cx, const int cy, const int R, const double imb,
              const string title, const string footer, const uint footCol,
              const bool strengthMode = false, const double strength = 0.0)
  {
   for(int deg = 0; deg <= 180; deg += 2)
     {
      double a = (180 - deg) * M_PI / 180.0;
      double f = deg / 180.0;
      uint col;
      if(strengthMode)
        {
         if(f < 0.35)      col = ARGB(255,  90,  96, 110);
         else if(f < 0.60) col = ARGB(255, 170, 155,  90);
         else if(f < 0.80) col = ARGB(255, 225, 200,  90);
         else              col = ARGB(255,  70, 230, 155);
        }
      else if(f < 0.38) col = ARGB(255, 214, 69, 65);
      else if(f > 0.62) col = ARGB(255, 46, 170, 122);
      else              col = ARGB(255, 150, 150, 60);
      int inner = R - MathMax(16, R / 5);
      int x1 = cx + (int)(MathCos(a) * inner), y1 = cy - (int)(MathSin(a) * inner);
      int x2 = cx + (int)(MathCos(a) * R),        y2 = cy - (int)(MathSin(a) * R);
      g_gauge.LineAA(x1, y1, x2, y2, col);
     }
   double ang = (1.0 - (imb + 1.0) / 2.0) * M_PI;
   int nx = cx + (int)(MathCos(ang) * (R - MathMax(20, R / 4)));
   int ny = cy - (int)(MathSin(ang) * (R - MathMax(20, R / 4)));
   for(int t = -2; t <= 2; t++)
      g_gauge.LineAA(cx + t, cy, nx, ny, ARGB(255, 245, 245, 250));
   for(int t = -2; t <= 2; t++)
      g_gauge.LineAA(cx, cy + t, nx, ny, ARGB(255, 245, 245, 250));
   g_gauge.FillCircle(cx, cy, MathMax(7, R / 14), ARGB(255, 235, 235, 240));

   g_gauge.FontSet("Arial Bold", MathMax(20, R / 5) * MathMax(80, InpFontScale) / 100);
   g_gauge.TextOut(cx, cy - R / 2 - R / 8,
                   strengthMode ? StringFormat("%.0f%%", strength * 100)
                                : StringFormat("%+.2f", imb),
                   ARGB(255, 240, 240, 245), TA_CENTER | TA_TOP);
   g_gauge.FontSet("Arial", MathMax(12, R / 14) * MathMax(80, InpFontScale) / 100);
   g_gauge.TextOut(cx, cy - R - R / 6, title, ARGB(255, 150, 155, 165), TA_CENTER | TA_TOP);
   g_gauge.TextOut(cx - R + 2, cy + 8, strengthMode ? "LOW" : "SELL",
                   strengthMode ? ARGB(255, 130, 136, 148) : ARGB(255, 214, 69, 65),
                   TA_LEFT | TA_TOP);
   g_gauge.TextOut(cx + R - 2, cy + 8, strengthMode ? "HIGH" : "BUY",
                   strengthMode ? ARGB(255, 70, 230, 155) : ARGB(255, 46, 170, 122),
                   TA_RIGHT | TA_TOP);
   uint vcol;
   string verdict = strengthMode ? StrengthWords(strength, vcol)
                                 : ResistanceWords(imb, vcol);
   g_gauge.FontSet("Arial Bold", MathMax(13, R / 11) * MathMax(80, InpFontScale) / 100);
   g_gauge.TextOut(cx, cy + MathMax(24, R / 6), verdict, vcol, TA_CENTER | TA_TOP);
   g_gauge.FontSet("Arial", MathMax(11, R / 16) * MathMax(80, InpFontScale) / 100);
   g_gauge.TextOut(cx, cy + MathMax(46, R / 6 + R / 8), footer, footCol, TA_CENTER | TA_TOP);
  }

void GaugeDraw()
  {
   if(!g_gaugeOK) return;

   double vUp, vDn, age = -1; int vBars = 0;
   OandaRefresh();
   double imbVol = OandaImbalance(vUp, vDn, vBars, age);
   bool stale = (age < 0 || age > 3.0);

   double tUp, tDn; int ticks = 0;
   double imbTick = TapeImbalance(tUp, tDn, ticks);

   int w = g_gauge.Width(), h = g_gauge.Height();
   g_gauge.Erase(ARGB(220, 18, 20, 26));
   g_gauge.Rectangle(0, 0, w - 1, h - 1, ARGB(255, 60, 64, 76));

   int cy = (int)(h * 0.52);
   if(InpGaugeDual)
     {
      int R = (int)MathMin(w * 0.225, h * 0.30);
      double lo, stk, gp;
      double strength = ImbalanceStrength(lo, stk, gp);

      if(g_ovN > 0 && g_ovTime[g_ovN - 1] != g_stLastBar)
        {
         g_stLastBar = g_ovTime[g_ovN - 1];
         g_stPrev = g_stCurr;
         if(strength >= g_stPeak) { g_stPeak = strength; g_stPeakTime = g_stLastBar; }
         // a peak older than ten minutes stops counting as "recent"
         if(g_stLastBar - g_stPeakTime > 600) { g_stPeak = strength; g_stPeakTime = g_stLastBar; }
        }
      g_stCurr = strength;
      DrawDial((int)(w * 0.26), cy, R, strength * 2.0 - 1.0,
               "IMBALANCE STRENGTH (volume)",
               (age < 0) ? "NO DATA" : (stale ? StringFormat("STALE %.0f min", age)
                                      : StringFormat("gap %.0f%%   one-sided %.0f%%   push %.0f%%",
                                                     gp * 100, stk * 100, lo * 100)),
               stale ? ARGB(255, 230, 120, 60) : ARGB(255, 150, 155, 165), true, strength);
//  THE RIGHT DIAL IS THE IMBALANCE'S OWN DIRECTION, not the tape.
//  Zee, 2026-09-18: "instead of the dial on left saying direction now (live ticks), lets
//  replace it with Imbalance supports direction: and the dial goes from red SELL on the
//  left to right BUY.. so the first needle on left tells us ok imbalance ready.. the
//  second needle on the dial on the right tells us whether to buy or sell."
//  Both dials now read from the same measurement - one says HOW RIPE, the other says
//  WHICH WAY - so they can never tell contradictory stories. The live tape stays on the
//  panel as a note, where it says whether price has turned yet.
      double dirImb = 0.0;
      if(g_stEffUp + g_stEffDn > 0.0)
         dirImb = (g_stEffUp - g_stEffDn) / (g_stEffUp + g_stEffDn);
      DrawDial((int)(w * 0.74), cy, R, dirImb, "IMBALANCE SUPPORTS",
               StringFormat("live tape %+.2f  ·  %d ticks", imbTick, ticks),
               ARGB(255, 150, 155, 165), false, 0.0);
      g_gauge.LineAA(w / 2, (int)(h * 0.22), w / 2, (int)(h * 0.66), ARGB(120, 70, 74, 86));
     }
   else
     {
      int R = (int)MathMin(w * 0.42, h * 0.60);
      bool useVol = (InpMeterSource == 1);
      DrawDial(w / 2, cy, R, useVol ? imbVol : imbTick,
               useVol ? "VOLUME (TradingView)" : "TICKS (live)",
               useVol ? (stale ? StringFormat("STALE %.0f min", age)
                               : StringFormat("%d min", vBars))
                      : StringFormat("%d ticks", ticks),
               (useVol && stale) ? ARGB(255, 230, 120, 60) : ARGB(255, 150, 155, 165));
     }

   int sc  = MathMax(80, InpFontScale);
   int fB  = 18 * sc / 100;          // the verdict
   int fR  = 15 * sc / 100;          // the two effort lines
   int fN  = 13 * sc / 100;          // what is still needed
   int lh  = (int)(fR * 1.85);       // line height

//  THE CALL. Zee: "instead of the constant text called WAITING.. can we say BUY NOW,
//  SELL NOW.. based on the imbalance strength when its READY.. so we calculate direction
//  buy/sell somehow from our calculations".
//  DIRECTION COMES FROM THE IMBALANCE ITSELF. v1.53 let the live tape veto the call;
//  he corrected it: "no i think the direction comes from imbalance.. if small volumes are
//  making large spreads of red, it means SELL.. if small green volumes are causing large
//  spreads of green it means buy". That is precisely ground-per-unit-of-volume, one side
//  against the other - the same number the bars draw. The tape no longer overrules it; if
//  it happens to be pointing the other way that is shown as a note, not a block, because
//  price moving against the side that is meeting no resistance is what the setup looks
//  like just before it turns.
   string callTxt = g_stVerdict;
   uint   callCol = (uint)(0xFF000000 | (g_stColour & 0x00FFFFFF));
   if(InpGaugeDual)
     {
      double lo2, stk2, gp2;
      double st2 = ImbalanceStrength(lo2, stk2, gp2);
      if(st2 >= 0.80)
        {
         int d = 0;
         if(g_stEffUp > g_stEffDn * 1.15)      d =  1;   // greens buy more ground per volume
         else if(g_stEffDn > g_stEffUp * 1.15) d = -1;   // reds do

         double tUp2, tDn2; int tk2;
         double tImb = TapeImbalance(tUp2, tDn2, tk2);
         int tickDir = (tImb >= 0.15) ? 1 : ((tImb <= -0.15) ? -1 : 0);

         if(d > 0)      { callTxt = "BUY NOW";  callCol = ARGB(255,  70, 235, 155); }
         else if(d < 0) { callTxt = "SELL NOW"; callCol = ARGB(255, 255,  95,  90); }
         else           { callTxt = "READY - neither side is cheaper yet";
                          callCol = ARGB(255, 225, 200, 90); }

         if(d != 0 && tickDir != 0 && tickDir != d)
            g_stNote = (d > 0) ? "note: price still falling - the turn has not shown yet"
                               : "note: price still rising - the turn has not shown yet";
         else
            g_stNote = "";
        }
     }

   int py = (int)(h * 0.70);
   g_gauge.LineAA(16, py - 10, w - 16, py - 10, ARGB(120, 70, 74, 86));
   g_gauge.FontSet("Arial Bold", fB);
   g_gauge.FontSet("Arial Bold", (callTxt == "BUY NOW" || callTxt == "SELL NOW")
                                 ? (int)(fB * 1.6) : fB);
   g_gauge.TextOut(w / 2, py, callTxt, callCol, TA_CENTER | TA_TOP);
   // TWO BARS. Longer bar = that side is moving price more easily for its volume.
   // No sentence to parse: the eye compares two lengths in a fraction of a second.
   int by   = py + (int)(fB * 1.7);
   int barH = (int)(fR * 1.15);
   int x0   = (int)(w * 0.26);                 // bars start after the labels
   int maxW = (int)(w * 0.40);
   double top = MathMax(g_stEffUp, g_stEffDn);
   if(top <= 0.0) top = 1.0;

   g_gauge.FontSet("Arial Bold", fR);
   g_gauge.TextOut(x0 - 12, by, "SELLERS", ARGB(255, 226, 120, 115), TA_RIGHT | TA_TOP);
   g_gauge.TextOut(x0 - 12, by + lh, "BUYERS", ARGB(255, 120, 215, 175), TA_RIGHT | TA_TOP);

   int wDn = (int)(maxW * g_stEffDn / top);
   int wUp = (int)(maxW * g_stEffUp / top);
   g_gauge.FillRectangle(x0, by + 2, x0 + MathMax(wDn, 2), by + barH,
                         ARGB(255, 214, 69, 65));
   g_gauge.FillRectangle(x0, by + lh + 2, x0 + MathMax(wUp, 2), by + lh + barH,
                         ARGB(255, 46, 170, 122));

   g_gauge.FontSet("Arial Bold", fR);
   g_gauge.TextOut(x0 + maxW + 14, by, g_stDnWord,
                   (uint)(0xFF000000 | (g_stDnCol & 0x00FFFFFF)), TA_LEFT | TA_TOP);
   g_gauge.TextOut(x0 + maxW + 14, by + lh, g_stUpWord,
                   (uint)(0xFF000000 | (g_stUpCol & 0x00FFFFFF)), TA_LEFT | TA_TOP);
   g_gauge.FontSet("Arial", fN);
   g_gauge.TextOut(w / 2, by - (int)(fN * 1.5),
                   "how much ground each side is getting for its volume  (longer = easier)",
                   ARGB(255, 150, 156, 166), TA_CENTER | TA_TOP);
   g_gauge.FontSet("Arial", fN);
   g_gauge.TextOut(w / 2, py + (int)(fB * 1.7) + lh * 2,
                   (g_stNote != "") ? g_stNote : g_stNeed,
                   (g_stNote != "") ? ARGB(255, 225, 200, 90) : ARGB(255, 180, 186, 196),
                   TA_CENTER | TA_TOP);

   // --- the three stages of the setup, left to right
   int sdir = 0, sclen = 0; double scvol = 0.0;
   int stage = SetupStage(sdir, scvol, sclen);
   string s1 = (sdir > 0) ? "1. SELLING CAMPAIGN" : ((sdir < 0) ? "1. BUYING CAMPAIGN"
                                                                : "1. CAMPAIGN");
   string s2 = "2. QUIET REACTION";
   string s3 = (sdir > 0) ? "3. RISING ON LOW VOLUME" : ((sdir < 0) ? "3. FALLING ON LOW VOLUME"
                                                                   : "3. MOVING AWAY");
   int sy = (int)(fN * 2.6);            // just under the title, above the dials
   int col1 = (int)(w * 0.19), col2 = (int)(w * 0.50), col3 = (int)(w * 0.81);
   g_gauge.FontSet("Arial Bold", (int)(fN * 1.15));
   uint dim = ARGB(255, 110, 116, 128), donec = ARGB(255, 120, 190, 150),
        nowc = ARGB(255, 255, 220, 110);
   g_gauge.TextOut(col1, sy, s1, (stage >= 2) ? donec : ((stage == 1) ? nowc : dim),
                   TA_CENTER | TA_TOP);
   g_gauge.TextOut(col2, sy, s2, (stage >= 3) ? donec : ((stage == 2) ? nowc : dim),
                   TA_CENTER | TA_TOP);
   g_gauge.TextOut(col3, sy, s3, (stage == 3) ? nowc : dim, TA_CENTER | TA_TOP);
   g_gauge.FontSet("Arial", (int)(fN * 0.92));
   string stageNote;
   if(stage == 0)      stageNote = "no campaign yet - nothing to set up from";
   else if(stage == 1) stageNote = StringFormat("campaign running: %d bars at %.0f volume - waiting for it to stall",
                                                sclen, scvol);
   else if(stage == 2) stageNote = "the quiet reaction has appeared - this is the moment";
   else                stageNote = (sdir > 0) ? "moving up on light volume - the setup is playing out"
                                              : "moving down on light volume - the setup is playing out";
   g_gauge.TextOut(w / 2, sy + (int)(fN * 1.8), stageNote,
                   ARGB(255, 160, 166, 176), TA_CENTER | TA_TOP);
   g_gauge.LineAA(16, sy + (int)(fN * 3.3), w - 16, sy + (int)(fN * 3.3),
                  ARGB(120, 70, 74, 86));

   g_gauge.FontSet("Arial Bold", 14 * MathMax(80, InpFontScale) / 100);
   g_gauge.TextOut(w / 2, 8, "IMBALANCE - price gained per unit of effort",
                   ARGB(255, 175, 180, 190), TA_CENTER | TA_TOP);
   g_gauge.Update();
  }

//+------------------------------------------------------------------+
//| THE RUNNING COMMENTARY.                                           |
//|                                                                   |
//| Says what the tape just did in the same terms he reads it in -    |
//| how much ground each side bought for its volume - then names the  |
//| condition that is still missing. Silence is the thing he asked me |
//| to remove, so this speaks every minute whether or not it acts.    |
//+------------------------------------------------------------------+
void Narrate(const int shift)
  {
   if(!InpNarrate) return;

   double volSum = 0.0, spSum = 0.0;
   int look0 = shift + InpAbsorbBars + 1;
   for(int k = look0; k < look0 + InpLook; k++)
     { volSum += BarVolume(k); spSum += Spread(k); }
   double volAvg = volSum / InpLook, spAvg = spSum / InpLook;
   if(volAvg <= 0.0 || spAvg <= 0.0) return;

   int a0 = shift + 1, a1 = shift + InpAbsorbBars;
   double aVol = 0.0;
   for(int k = a0; k <= a1; k++) aVol += BarVolume(k);
   aVol /= InpAbsorbBars;
   double entered = iOpen(_Symbol, PERIOD_CURRENT, a1);
   double left    = iClose(_Symbol, PERIOD_CURRENT, a0);
   double net     = MathAbs(left - entered);

   // what each side bought for its effort, over the comparison window
   double upP = 0.0, dnP = 0.0, upV = 0.0, dnV = 0.0;
   for(int k = shift; k < shift + InpSideBars; k++)
     {
      double bd = Body(k), v = BarVolume(k);
      if(v <= 0.0) continue;
      double amt = (InpSideMeasure == 1) ? Spread(k) : MathAbs(bd);
      if(bd > 0)      { upP += amt; upV += v; }
      else if(bd < 0) { dnP += amt; dnV += v; }
     }
   double effUp = (upV > 0.0) ? upP / upV : 0.0;
   double effDn = (dnV > 0.0) ? dnP / dnV : 0.0;

   double sp = Spread(shift), bd0 = Body(shift), vol = BarVolume(shift);
   int    dir = (bd0 > 0) ? 1 : -1;
   double edge = 0.0;
   if(effUp > 0.0 && effDn > 0.0) edge = (dir > 0) ? effUp / effDn : effDn / effUp;

   // score the conditions
   bool cLoud    = (aVol >= InpAbsorbVol * volAvg);
   bool cStuck   = (net <= InpAbsorbStuck * spAvg);
   bool cRelease = (InpReleaseVol <= 0.0 || vol <= InpReleaseVol * aVol);
   bool cBody    = (sp > 0.0 && MathAbs(bd0) >= InpBodyFrac * sp);
   bool cEdge    = (edge >= InpSideMult);
   int missing = (!cLoud) + (!cStuck) + (!cRelease) + (!cBody) + (!cEdge);

   string verdict;
   if(missing == 0)      verdict = "*** ALL CONDITIONS MET - taking the " + (dir > 0 ? "BUY" : "SELL") + " ***";
   else if(missing == 1) verdict = "CLOSE - one condition short";
   else                  verdict = "watching";

   string why = "";
   if(!cLoud)    why += StringFormat("needs heavier selling/buying first (%.2fx, want %.2fx) · ", aVol/volAvg, InpAbsorbVol);
   if(!cStuck)   why += StringFormat("that effort IS moving price (%.2fx, want <=%.2fx) · ", net/spAvg, InpAbsorbStuck);
   if(!cRelease) why += StringFormat("this bar is not quieter than the fight (%.2fx, want <=%.2fx) · ", (aVol>0?vol/aVol:0), InpReleaseVol);
   if(!cBody)    why += StringFormat("indecisive bar (body %.2f, want %.2f) · ", (sp>0?MathAbs(bd0)/sp:0), InpBodyFrac);
   if(!cEdge)    why += StringFormat("neither side is winning (%.2fx, want %.2fx) · ", edge, InpSideMult);
   if(why == "") why = "-";

   string line = StringFormat(
      "[VSISA_MIN] %s  %s\n"
      "  sellers: %.0f volume bought %.2f of ground   (%.3f per 100)\n"
      "  buyers : %.0f volume bought %.2f of ground   (%.3f per 100)\n"
      "  who is winning: %.2fx   |  fight was %.2fx as loud as normal, moved %.2fx a bar\n"
      "  %s",
      TimeToString(iTime(_Symbol, PERIOD_CURRENT, shift), TIME_MINUTES), verdict,
      dnV, dnP, effDn * 100.0,
      upV, upP, effUp * 100.0,
      edge, aVol / volAvg, net / spAvg,
      missing == 0 ? "GO" : why);

   g_stEffDn = effDn * 100.0;
   g_stEffUp = effUp * 100.0;

   // the same two numbers, measured over the PREVIOUS stretch of the same length
   double pUpP = 0.0, pDnP = 0.0, pUpV = 0.0, pDnV = 0.0;
   for(int k = shift + InpSideBars; k < shift + InpSideBars * 2; k++)
     {
      double b2 = Body(k), v2 = BarVolume(k);
      if(v2 <= 0.0) continue;
      double a2 = (InpSideMeasure == 1) ? Spread(k) : MathAbs(b2);
      if(b2 > 0)      { pUpP += a2; pUpV += v2; }
      else if(b2 < 0) { pDnP += a2; pDnV += v2; }
     }
   double pEffUp = (pUpV > 0.0) ? pUpP / pUpV * 100.0 : 0.0;
   double pEffDn = (pDnV > 0.0) ? pDnP / pDnV * 100.0 : 0.0;

   g_stDnWord = SideWord(g_stEffDn, pEffDn, g_stDnCol, true);
   g_stUpWord = SideWord(g_stEffUp, pEffUp, g_stUpCol, false);
   if(missing == 0)
     {
      g_stVerdict = StringFormat("READY - every condition met for a %s", dir > 0 ? "BUY" : "SELL");
      g_stColour  = (dir > 0) ? 0xFF46AA7A : 0xFFD64541;
      g_stNeed    = "this is the moment the method describes";
     }
   else
     {
      g_stVerdict = (missing == 1) ? "ALMOST - one condition short" : "WAITING";
      g_stColour  = (missing == 1) ? 0xFFE1C85A : 0xFF9AA0AC;
      string n = why;
      StringReplace(n, " · ", "; ");
      g_stNeed = "still needed: " + n;
     }

   Print(line);
   if(InpNarrateChart) Comment(line);
   if(missing == 0 && InpAlertMode >= 1)
     {
      string msg = StringFormat("VSISA: ALL CONDITIONS MET - %s", dir > 0 ? "BUY" : "SELL");
      if(InpAlertSound) { PlaySound("alert2.wav"); Print(msg); } else Alert(msg);
     }
   else if(missing == 1 && InpAlertMode >= 2)
     {
      string msg = StringFormat("VSISA: one condition short - %s", why);
      if(InpAlertSound) { PlaySound("tick.wav"); Print(msg); } else Alert(msg);
     }
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

   GaugeDraw();                    // the meter moves with the tape, not with the bar

   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   bool newBar = (bt != g_lastBar);
   if(newBar) g_barTicks = 0; else g_barTicks++;

   //--- MODE 1 EXITS ARE CHECKED ON EVERY TICK, not once a minute.
   //    He watches it continuously - "if i feel like after few seconds of entering the
   //    trade, its not going in our direction at all.. i maybe wait upto 1 minute and
   //    then bam i have to close it somehow". Taking profit the moment it appears, and
   //    giving up after about a minute, both need tick resolution to be faithful.
   if(InpExitMode == 2) { /* ENTRY ONLY - the position is HIS */ }
   else if(InpExitMode == 1 && OpenCount() > 0)
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
   if(!InpMeterOnly && InpIntrabar && !newBar && OpenCount() == 0 && g_barTicks >= InpTickMinBar &&
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

   if(InpExitMode != 2 && OpenCount() > 0)
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

   Narrate(1);                     // he asked never to be left in silence

   int dir = 0; string why = "";
   if(!Qualifies(1, dir, why))
     {
      g_streak = 0;
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

   if(InpMeterOnly)
     {
      PrintFormat("[VSISA_MIN] SIGNAL (meter-only, not trading): %s %s",
                  dir > 0 ? "BUY" : "SELL", why);
      if(InpAlertMode >= 1)
        {
         string m = StringFormat("VSISA imbalance: %s  %s", dir > 0 ? "BUY" : "SELL", why);
         if(InpAlertSound) { PlaySound("alert2.wav"); Print(m); } else Alert(m);
        }
      return;
     }
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
