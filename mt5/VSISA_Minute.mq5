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
//|  NOT PROMOTED - CLAUDE.md. Only MT5's Strategy Tester or live      |
//|  fills may promote a default.                                      |
//+------------------------------------------------------------------+
#property copyright "Zeeshan"
#property version   "1.03"
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
input double InpReleaseVol  = 0.85;  // InpReleaseVol - trigger volume <= x the absorption avg
input double InpBodyFrac    = 0.40;  // InpBodyFrac - trigger body >= x its own range
input int    InpConfirmBars = 1;     // InpConfirmBars - qualifying bars in a row before entering

input group "=== who moves price more easily (his crossover) ==="
input int    InpSideBars    = 6;     // InpSideBars - window the two sides are compared over
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

input group "=== guards ==="
input double InpDayLossStop = 400.0; // InpDayLossStop - stop for the day after this loss (0 = off)
input int    InpCoolBars    = 1;     // InpCoolBars - bars to wait after a decision
input bool   InpBuys        = true;  // InpBuys - his ten tickets were all BUY
input bool   InpSells       = false; // InpSells - off until the short side is tested
input int    InpSessFrom    = 0;     // InpSessFrom - broker hour, inclusive
input int    InpSessTo      = 24;    // InpSessTo - broker hour, exclusive
input bool   InpVerbose     = true;  // InpVerbose - print every decision

CTrade  trade;
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
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   if(InpExitMode == 0 && InpStopPts <= 0)
     {
      Print("[VSISA_MIN] REFUSING to run with no stop. A 1.00-lot scalper without a cap "
            "is one bad minute away from giving back a week.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   PrintFormat("[VSISA_MIN] v1.03 - absorb>=%.2fx over %d bars | stuck<=%.2fx | leg>=%.2fx | "
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
      if(vol > InpReleaseVol * aVol)
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
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(bt == g_lastBar) return;            // one decision per CLOSED bar
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
