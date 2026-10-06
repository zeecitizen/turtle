//+------------------------------------------------------------------+
//|  RiskGuardButtons.mq5                                            |
//|                                                                  |
//|  Built 2026-10-06, the day a 200 USD account was liquidated on    |
//|  PXBT gold. Zee's own account of it:                              |
//|                                                                   |
//|    "i increased lot size from 0.01 to 0.1.. and suddenly as i      |
//|     shorted.. the market reversed... i kept holding that maybe it  |
//|     will come back... i took a buy entry at this point this was    |
//|     the exact tip"                                                 |
//|                                                                    |
//|  THE ARITHMETIC OF THAT DAY, from his own logged gold ticks:        |
//|      0.01 lots = $1/point  -> 200 points of room before $200 gone  |
//|      0.10 lots = $10/point ->  20 points of room                   |
//|      gold's range over any 15 min: median 6.8 pts, p90 10.9        |
//|      a 20-point adverse move happens at 10.5% of entry moments      |
//|  He had 20 points of room on a market that routinely travels 7-11  |
//|  in a quarter hour. The direction was not the problem. The size     |
//|  left no room to be wrong once, and being wrong once is normal.     |
//|                                                                     |
//|  His own rule, written before that day:                             |
//|    "never trust a human to keep a self-imposed safety rule;          |
//|     mechanical enforcement is the job."                              |
//|                                                                      |
//|  So every limit here is enforced in code and none of them can be     |
//|  talked past at 3am. The EA does NOT decide direction - he does.     |
//|  It decides how much, and that there is always a stop.               |
//+------------------------------------------------------------------+
#property copyright "Zeeshan"
#property version   "1.14"
#define  VER        "1.14"
#property strict

#include <Trade/Trade.mqh>

//--- SIZE ------------------------------------------------------------
input double InpLots            = 0.01;   // the ONLY size this EA will trade
input double InpHardMaxLots     = 0.01;   // absolute ceiling. Nothing gets past this.
input double InpBiggerLotBalance= 2000.0; // balance required before InpLots may exceed 0.01
//--- RISK ------------------------------------------------------------
input double InpRiskPct         = 1.5;    // max % of balance a single trade may risk
input double InpMaxDailyLossPct = 5.0;    // after losing this much today, trading locks
//--- THE STOP --------------------------------------------------------
input int    InpSLBufferPips    = 5;      // beyond the candle's extreme
input int    InpSLBars          = 2;      // bars scanned for the stop, from the FORMING
                                          // candle back. 1 = forming only; 2 = forming +
                                          // last closed, so an early click still gets structure
//--- THE TARGET. Measured: tight stop + big target is the only viable shape on gold.
input double InpTargetR         = 6.0;    // take-profit = this many x the stop distance.
                                          // 6 x 5 pips = the 30-pip target.
input double InpMinR            = 4.0;    // refuse anything with a worse ratio than this
//--- SCALP MODE: fixed tiny stop and target, overriding the structural stop and the R rule.
//--- Measured at -0.57 pips a click on his own entry. Here so it can be TESTED, with a
//--- scoreboard, not because the arithmetic supports it.
input double InpFixedSLPips      = 5.0;   // >0 = use this stop instead of the candle's.
                                          // 5 with InpTargetR 6 = the 5/30 geometry:
                                          // random 17.9%, breakeven 19.1% on gold.
input double InpFixedTPPips      = 0.0;   // >0 = use this target instead of InpTargetR
input int    InpMinStopPips     = 2;      // absolute backstop only - the spread multiple
                                          // below is what actually sets the floor
input double InpMinStopVsSpread = 4.7;    // THE REAL FLOOR, in spreads - so it adapts to the
                                          // broker instead of being tuned for one. Derived
                                          // from PXBT's measured 8-pip floor / 1.70 spread.
                                          //   PXBT      4.7 x 1.70 = 8.0 pips
                                          //   Blueberry 4.7 x 0.70 = 3.3 pips
                                          //   Exness    4.7 x 0.80 = 3.8 pips
//--- DISCIPLINE ------------------------------------------------------
input int    InpCooldownSec     = 120;    // no new trade for this long after a LOSS
input bool   InpOnePositionOnly = false;  // stacking IS allowed - the caps below bound it
input int    InpMaxOpenPositions= 5;      // ...but not more than this many at once
input double InpMaxTotalRiskPct = 4.0;    // SUM of all open risk-to-stop. A per-trade cap does
                                          // not bind someone clicking ten times; this does.
input double InpEmergencyClosePct=10.0;   // floating loss past this %% of balance closes ALL
//--- STRUCTURE GUARDS ------------------------------------------------
input bool   InpBlockAtSR       = true;   // refuse a trade INTO a level that reversed before
input int    InpSRLookbackBars  = 300;    // M5 bars scanned for those levels
input int    InpSRMinTouches    = 2;      // "a reversal happened once or twice before"
input int    InpSRZonePips      = 12;     // how close counts as "at" the level
input bool   InpBlockRanging    = false;  // OFF: measured BACKWARDS at the 5/30 geometry.
                                          // ER<0.20 wins 27.0% (breakeven 19.1%); ER>0.50
                                          // wins 12.6%. Blocking chop blocked the only band
                                          // that pays. Efficiency is still shown, not acted on.
input int    InpRangeBars       = 15;     // M1 bars used to judge it
input double InpRangeMinEff     = 0.30;   // net move / total path below this = ranging
input int    InpRangeCooldownSec= 300;    // "take a coffee break"
input int    InpLossStreakLock  = 12;     // At a 22.7%% win rate, 8 losses in a row is the
                                          // DESIGN, not a warning. 5 would fire on 27.6%% of
                                          // runs. The daily cap in MONEY is the real guard.
input int    InpStreakCooldownSec=600;
input bool   InpNeedCandleAgrees= true;   // refuse a BUY while the forming candle is red,
                                          // and a SELL while it is green
input bool   InpPanelBox        = false;  // a backing box behind the text. OFF: the text
                                          // colours itself from the chart background instead.
input bool   InpHideOneClick    = true;   // hide MT5's own one-click panel on this chart
input double InpPipOverride     = 0.0;    // 0 = auto. Set the pip in PRICE if the auto
                                          // detection is ever wrong on a new symbol.
input int    InpMagic           = 77001;

CTrade   trade;
string   BTN_BUY = "rg_buy", BTN_SELL = "rg_sell", BTN_CLOSE = "rg_close", BG = "rg_bg";

//--- text legible on whatever the CHART is painted. Read live, not hardcoded, because a
//--- template change is exactly what made the panel vanish on a white chart.
color ChartText(const bool dim)
{
   long bg = ChartGetInteger(0, CHART_COLOR_BACKGROUND);
   int r = (int)(bg & 0xFF), g = (int)((bg >> 8) & 0xFF), b = (int)((bg >> 16) & 0xFF);
   double lum = 0.299 * r + 0.587 * g + 0.114 * b;
   if(lum > 140.0) return (dim ? C'90,90,98'   : C'10,10,14');    // light chart -> black text
   return                 (dim ? C'150,152,160' : C'232,234,238'); // dark chart  -> light text
}
#define  NLINES 6
string   LBL[NLINES];   // OBJ_LABEL is SINGLE-LINE: it ignores newline escapes entirely,
                        // so the panel needs one object per line, not one with breaks.
datetime g_day = 0;
double   g_day_start_balance = 0.0;
datetime g_cooldown_until = 0;
string   g_msg = "";
datetime g_msg_at = 0;

//+------------------------------------------------------------------+
double PipSize()
{
   if(InpPipOverride > 0.0) return InpPipOverride;
   int    d  = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   // 3- and 5-digit FX quotes carry a fractional pip, so a pip is ten points.
   if(d == 3 || d == 5) return pt * 10.0;
   // METALS. Gold quotes to 2 digits (point 0.01) and its pip is 0.10 by convention. Without
   // this branch PipSize returned 0.01 on XAUUSD and every pip input was 10x too small - the
   // 5-pip stop became 0.05 against a 0.17 spread, i.e. inside it. Caught 2026-10-06.
   if(d == 2 && pt <= 0.011 && SymbolInfoDouble(_Symbol, SYMBOL_BID) > 100.0) return pt * 10.0;
   return pt;
}

double Spread() { return SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID); }

//--- money at risk if this stop is hit, in account currency
double RiskMoney(const double lots, const double slDistance)
{
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0.0 || tv <= 0.0) return 0.0;
   return (slDistance / ts) * tv * lots;
}

//--- THE SCOREBOARD. Read from closed deals, so it survives a restart and cannot be
//--- remembered more kindly than it happened.
void Score(int &trades, int &wins, double &netPips)
{
   trades = 0; wins = 0; netPips = 0.0;
   if(!HistorySelect(TimeCurrent() - 7 * 86400, TimeCurrent() + 60)) return;
   double pip = PipSize();
   for(int i = 0; i < HistoryDealsTotal(); i++)
   {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0) continue;
      if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      double p = HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP)
               + HistoryDealGetDouble(d, DEAL_COMMISSION);
      trades++;
      if(p > 0.0) wins++;
      double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      double lot = HistoryDealGetDouble(d, DEAL_VOLUME);
      if(tv > 0.0 && ts > 0.0 && lot > 0.0) netPips += p / (tv * lot / ts * pip);
   }
}

//--- how many of ours are open, and what they collectively stand to lose
int OurPositions(double &totalRisk, double &floatPL)
{
   int cnt = 0; totalRisk = 0.0; floatPL = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      cnt++;
      floatPL += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double lots = PositionGetDouble(POSITION_VOLUME);
      // a position with NO stop is unbounded - count it at the emergency cap so the
      // total-risk test cannot be fooled by one
      if(sl <= 0.0) totalRisk += AccountInfoDouble(ACCOUNT_BALANCE) * InpEmergencyClosePct / 100.0;
      else          totalRisk += RiskMoney(lots, MathAbs(open - sl));
   }
   return cnt;
}

bool HaveOurPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic) return true;
   }
   return false;
}

void Say(const string m) { g_msg = m; g_msg_at = TimeCurrent(); Print("[RG] ", m); }

//+------------------------------------------------------------------+
//| A level price has REVERSED at before. Buying into resistance and selling into      |
//| support are the two trades that emptied the account on 2026-10-06.                 |
//+------------------------------------------------------------------+
bool NearSR(const bool isBuy, double &level, int &touches)
{
   level = 0.0; touches = 0;
   int bars = MathMin(InpSRLookbackBars, Bars(_Symbol, PERIOD_M5) - 3);
   if(bars < 30) return false;
   // One copy instead of thousands of time-series calls. Each iHigh/iLow crosses the MQL5
   // sandbox boundary; at ~1,500 per call, twice a second, that is cost for nothing.
   double highs[], lows[];
   if(CopyHigh(_Symbol, PERIOD_M5, 0, bars, highs) <= 0) return false;
   if(CopyLow (_Symbol, PERIOD_M5, 0, bars, lows)  <= 0) return false;
   ArraySetAsSeries(highs, true);
   ArraySetAsSeries(lows,  true);

   double zone = InpSRZonePips * PipSize();
   double px = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // a swing point is a bar whose extreme beats its two neighbours on each side
   for(int i = 2; i < bars - 2; i++)
   {
      double piv;
      if(isBuy)   // danger ABOVE: swing highs price has turned down from
      {
         double h = highs[i];
         if(!(h > highs[i+1] && h > highs[i+2] && h > highs[i-1] && h > highs[i-2])) continue;
         piv = h;
         if(piv < px) continue;                       // only levels ahead of the trade
      }
      else        // danger BELOW: swing lows price has bounced from
      {
         double l = lows[i];
         if(!(l < lows[i+1] && l < lows[i+2] && l < lows[i-1] && l < lows[i-2])) continue;
         piv = l;
         if(piv > px) continue;
      }
      if(MathAbs(piv - px) > zone) continue;          // not close enough to matter

      // how many OTHER swings sit at this same price? that is the "touched before" count
      int n = 0;
      for(int j = 2; j < bars - 2; j++)
         if(MathAbs((isBuy ? highs[j] : lows[j]) - piv) <= zone) n++;
      if(n > touches) { touches = n; level = piv; }
   }
   return (touches >= InpSRMinTouches);
}

//+------------------------------------------------------------------+
//| "ranging markets are poison" - net progress against distance travelled.            |
//| 1.0 = a clean one-way move. Near 0 = the market is sawing in place.                |
//+------------------------------------------------------------------+
double RangeEfficiency()
{
   int n = InpRangeBars;
   if(Bars(_Symbol, PERIOD_M1) < n + 2) return 1.0;
   double cl[];
   if(CopyClose(_Symbol, PERIOD_M1, 0, n + 1, cl) <= 0) return 1.0;
   ArraySetAsSeries(cl, true);
   double path = 0.0;
   for(int i = 0; i < n; i++) path += MathAbs(cl[i] - cl[i + 1]);
   if(path <= 0.0) return 1.0;
   return MathAbs(cl[0] - cl[n]) / path;
}

//--- +1 up, -1 down, 0 flat, on one timeframe
int TrendOf(const ENUM_TIMEFRAMES tf, const int look)
{
   if(Bars(_Symbol, tf) < look + 2) return 0;
   double now = iClose(_Symbol, tf, 0), then = iClose(_Symbol, tf, look);
   double atr = 0.0;
   for(int i = 0; i < look; i++) atr += iHigh(_Symbol, tf, i) - iLow(_Symbol, tf, i);
   atr /= look;
   if(atr <= 0.0) return 0;
   if(now - then >  atr * 0.5) return  1;
   if(now - then < -atr * 0.5) return -1;
   return 0;
}

//--- consecutive losing deals, read from history so a restart cannot forget them
int LossStreak()
{
   if(!HistorySelect(TimeCurrent() - 86400, TimeCurrent() + 60)) return 0;
   int streak = 0;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0) continue;
      if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      // COMMISSION BELONGS HERE. On a raw-spread account a +0.50 gross trade can be a net
      // loss, and without this the streak guard resets on a trade that lost money.
      double p = HistoryDealGetDouble(d, DEAL_PROFIT)
               + HistoryDealGetDouble(d, DEAL_SWAP)
               + HistoryDealGetDouble(d, DEAL_COMMISSION);
      if(p < 0.0) streak++;
      else break;
   }
   return streak;
}

//+------------------------------------------------------------------+
//| The size this EA is allowed to use, whatever the inputs say.      |
//+------------------------------------------------------------------+
double AllowedLots()
{
   double bal  = AccountInfoDouble(ACCOUNT_BALANCE);
   double want = InpLots;

   // HARD CEILING. The input cannot raise it - this is the line that was crossed
   // on 2026-10-06 when 0.01 became 0.1.
   if(want > InpHardMaxLots) want = InpHardMaxLots;

   // anything above the broker minimum needs a balance that can survive it
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(want > vmin && bal < InpBiggerLotBalance) want = vmin;

   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step > 0.0) want = MathFloor(want / step) * step;
   if(want < vmin) want = vmin;
   return NormalizeDouble(want, 2);
}

//+------------------------------------------------------------------+
//| Where the stop goes: beyond the candle being traded into.         |
//+------------------------------------------------------------------+
bool StopFor(const bool isBuy, double &sl, string &why)
{
   // The extreme across InpSLBars bars starting at the FORMING candle (shift 0). Using the
   // forming bar alone makes the stop depend on how far into the minute the click lands.
   int nb = (InpSLBars < 1) ? 1 : InpSLBars;
   double hi = 0.0, lo = 0.0;
   for(int b = 0; b < nb; b++)
   {
      double h = iHigh(_Symbol, PERIOD_CURRENT, b);
      double l = iLow(_Symbol, PERIOD_CURRENT, b);
      if(h <= 0.0 || l <= 0.0) continue;
      if(hi == 0.0 || h > hi) hi = h;
      if(lo == 0.0 || l < lo) lo = l;
   }
   if(hi <= 0.0 || lo <= 0.0) { why = "candle data not ready"; return false; }

   double pip = PipSize();
   double buf = InpSLBufferPips * pip;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double entry = isBuy ? ask : bid;

   sl = isBuy ? (lo - buf) : (hi + buf);

   // SCALP MODE overrides the structure entirely - his number, his experiment
   if(InpFixedSLPips > 0.0)
      sl = isBuy ? (entry - InpFixedSLPips * pip) : (entry + InpFixedSLPips * pip);

   double dist = MathAbs(entry - sl);

   // --- the stop must survive ordinary noise, or it is a donation -----------
   double minByPips   = InpMinStopPips * pip;
   double minBySpread = Spread() * InpMinStopVsSpread;
   double need = MathMax(minByPips, minBySpread);

   // ...and the broker's own minimum distance
   long stopsLvl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minByBroker = stopsLvl * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(minByBroker > need) need = minByBroker;

   // in scalp mode the broker's own minimum still binds, but the noise floor does not -
   // that floor exists to protect a structural stop, and he is deliberately not using one
   if(InpFixedSLPips > 0.0) need = minByBroker;

   if(dist < need)
   {
      // push it out rather than refuse - a wider stop is safe, a tighter one is not
      sl = isBuy ? (entry - need) : (entry + need);
      dist = need;
      why = StringFormat("stop widened to %.1f pips (candle was inside the noise floor)", dist / pip);
   }
   sl = NormalizeDouble(sl, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS));
   return true;
}

//+------------------------------------------------------------------+
bool DailyLocked(string &reason)
{
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   if(g_day_start_balance <= 0.0) return false;
   double lost = g_day_start_balance - MathMin(bal, eq);
   double cap  = g_day_start_balance * InpMaxDailyLossPct / 100.0;
   if(lost >= cap)
   {
      reason = StringFormat("DAILY LOSS CAP HIT: -%.2f of %.2f allowed. Trading is locked until tomorrow.",
                            lost, cap);
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
void Open(const bool isBuy)
{
   string reason;
   if(DailyLocked(reason)) { Say(reason); return; }

   if(TimeCurrent() < g_cooldown_until)
   {
      Say(StringFormat("COOLDOWN: %d sec left after the last loss. This is the window revenge trades live in.",
                       (int)(g_cooldown_until - TimeCurrent())));
      return;
   }

   double openRisk, openPL;
   int openN = OurPositions(openRisk, openPL);

   if(InpOnePositionOnly && openN > 0)
   {
      Say("A position is already open. No stacking - close it first.");
      return;
   }
   if(openN >= InpMaxOpenPositions)
   {
      Say(StringFormat("REFUSED: %d positions already open, the ceiling is %d.",
                       openN, InpMaxOpenPositions));
      return;
   }

   // --- GUARD 0: the forming candle must already be going his way ----------------------
   // "if i click buy on a currently forming red candle where price is moving downwards.. it
   // should not buy." His own thesis, enforced rather than remembered.
   if(InpNeedCandleAgrees)
   {
      double o0 = iOpen(_Symbol, PERIOD_CURRENT, 0);
      double c0 = iClose(_Symbol, PERIOD_CURRENT, 0);
      if(o0 > 0.0 && c0 > 0.0)
      {
         bool green = (c0 > o0), red = (c0 < o0);
         if(isBuy && red)
         {
            Say("BLOCKED: the forming candle is RED and you clicked BUY. Your own rule - the "
                "candle has to already be going your way.");
            return;
         }
         if(!isBuy && green)
         {
            Say("BLOCKED: the forming candle is GREEN and you clicked SELL. Your own rule.");
            return;
         }
      }
   }

   // --- GUARD 1: do not trade INTO a level that has reversed price before -------------
   double lvl; int touch;
   if(InpBlockAtSR && NearSR(isBuy, lvl, touch))
   {
      Say(StringFormat("BLOCKED: %s straight into a level at %.*f that price has turned at %d "
                       "times. This is the trade that emptied the account.",
                       (isBuy ? "buying" : "selling"),
                       (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS), lvl, touch));
      return;
   }

   // --- GUARD 2: ranging M1 ------------------------------------------------------------
   double eff = RangeEfficiency();
   if(InpBlockRanging && eff < InpRangeMinEff)
   {
      g_cooldown_until = TimeCurrent() + InpRangeCooldownSec;
      Say(StringFormat("BLOCKED: M1 is RANGING (efficiency %.2f, needs %.2f). Ranging markets "
                       "are poison. Cooldown %d min - take a coffee break.",
                       eff, InpRangeMinEff, InpRangeCooldownSec / 60));
      return;
   }

   // --- GUARD 4: a losing streak is a state of mind, not a market ----------------------
   int streak = LossStreak();
   if(streak >= InpLossStreakLock)
   {
      g_cooldown_until = TimeCurrent() + InpStreakCooldownSec;
      Say(StringFormat("BLOCKED: %d losses in a row. Cooldown %d min. Nothing about the market "
                       "changed; something about the clicking did.",
                       streak, InpStreakCooldownSec / 60));
      return;
   }

   double sl; string why = "";
   if(!StopFor(isBuy, sl, why)) { Say(why); return; }

   double lots = AllowedLots();
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double entry = isBuy ? ask : bid;
   double dist = MathAbs(entry - sl);

   double risk = RiskMoney(lots, dist);
   double bal  = AccountInfoDouble(ACCOUNT_BALANCE);
   double cap  = bal * InpRiskPct / 100.0;

   if(bal <= 0.0)
   {
      Say("REFUSED: account balance is 0.00 - there is nothing to risk. Fund it or switch "
          "to a demo account before this EA will let anything through.");
      return;
   }
   if(risk > cap)
   {
      Say(StringFormat("REFUSED: that stop risks %.2f, the cap is %.2f (%.1f%% of %.2f). "
                       "Move the entry closer to your stop, or wait for a tighter candle.",
                       risk, cap, InpRiskPct, bal));
      return;
   }

   // THE CAP THAT ACTUALLY BINDS TEN CLICKS. Per-trade risk is small by design; it is the
   // SUM that reaches the account.
   double totalCap = bal * InpMaxTotalRiskPct / 100.0;
   if(openRisk + risk > totalCap)
   {
      Say(StringFormat("REFUSED: %d open already risking %.2f; this would make %.2f and the "
                       "total cap is %.2f (%.1f%% of balance). That is the whole point of the cap.",
                       openN, openRisk, openRisk + risk, totalCap, InpMaxTotalRiskPct));
      return;
   }

   int t1 = TrendOf(PERIOD_M1, 15), t5 = TrendOf(PERIOD_M5, 12), t15 = TrendOf(PERIOD_M15, 8);
   int want = isBuy ? 1 : -1;
   string against = "";
   if(t1  != 0 && t1  != want) against += "M1 ";
   if(t5  != 0 && t5  != want) against += "M5 ";
   if(t15 != 0 && t15 != want) against += "M15 ";

   // THE TARGET, as a multiple of the stop that is ACTUALLY being used - so the ratio
   // survives the noise-floor widening above instead of being quietly degraded by it.
   double tp = (InpFixedTPPips > 0.0)
               ? (isBuy ? entry + InpFixedTPPips * PipSize() : entry - InpFixedTPPips * PipSize())
               : (isBuy ? (entry + dist * InpTargetR) : (entry - dist * InpTargetR));
   tp = NormalizeDouble(tp, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS));
   double rr = (dist > 0.0) ? MathAbs(tp - entry) / dist : 0.0;
   if(rr < InpMinR && InpFixedTPPips <= 0.0)
   {
      Say(StringFormat("REFUSED: reward:risk is only %.1f, the floor is %.1f. At a tight stop "
                       "the ratio IS the edge - a small target needs a win rate no judgement "
                       "delivers.", rr, InpMinR));
      return;
   }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(20);
   bool ok = isBuy ? trade.Buy(lots, _Symbol, 0.0, sl, tp, "RiskGuard")
                   : trade.Sell(lots, _Symbol, 0.0, sl, tp, "RiskGuard");
   if(ok)
      Say(StringFormat("%s %.2f lots  SL %.*f (%.1f pips, %.2f = %.2f%%)  TP %.*f  R 1:%.1f %s",
                       (isBuy ? "BUY" : "SELL"), lots,
                       (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS), sl,
                       dist / PipSize(), risk, 100.0 * risk / bal,
                       (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS), tp, rr,
                       (against == "" ? why
                        : StringFormat("CAUTION: against the %strend. %s", against, why))));
   else
      Say(StringFormat("order rejected: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription()));
}

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| THE NET UNDER "i kept holding that maybe it will come back".
//| Checked every tick AND every second. No confirmation and no off switch - the
//| moment it is needed is the moment it would be argued with.
//+------------------------------------------------------------------+
void EmergencyCheck()
{
   double risk, pl;
   int n = OurPositions(risk, pl);
   if(n <= 0 || pl >= 0.0) return;
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   if(bal <= 0.0) return;
   double cap = bal * InpEmergencyClosePct / 100.0;
   if(-pl < cap) return;
   Say(StringFormat("EMERGENCY CLOSE: floating loss %.2f passed %.1f%% of balance (%.2f). "
                    "Closing all %d positions now.", pl, InpEmergencyClosePct, cap, n));
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      trade.PositionClose(t);
   }
   g_cooldown_until = TimeCurrent() + InpCooldownSec;
}

void OnTick() { EmergencyCheck(); }

void CloseAll()
{
   bool any = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      double p = PositionGetDouble(POSITION_PROFIT);
      if(trade.PositionClose(t))
      {
         any = true;
         Say(StringFormat("closed, P/L %.2f", p));
         if(p < 0.0) g_cooldown_until = TimeCurrent() + InpCooldownSec;
      }
   }
   if(!any) Say("nothing of ours to close");
}

//+------------------------------------------------------------------+
void Btn(const string name, const int x, const int y, const int w, const int h,
         const string text, const color bg)
{
   if(ObjectFind(0, name) < 0) ObjectCreate(0, name, OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, h);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, bg);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrWhite);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 11);
   ObjectSetInteger(0, name, OBJPROP_STATE, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
}

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   g_day = 0;
   Btn(BTN_BUY,   20,  30, 150, 34, "BUY 0.01",   C'0,130,70');
   Btn(BTN_SELL, 180,  30, 150, 34, "SELL 0.01",  C'170,45,45');
   Btn(BTN_CLOSE, 20,  70, 310, 28, "CLOSE ALL",  C'70,70,80');
   // the backing panel, only if asked for
   if(InpPanelBox)
   {
   if(ObjectFind(0, BG) < 0) ObjectCreate(0, BG, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, BG, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, BG, OBJPROP_XDISTANCE, 10);
   ObjectSetInteger(0, BG, OBJPROP_YDISTANCE, 20);
   ObjectSetInteger(0, BG, OBJPROP_XSIZE, 340);
   ObjectSetInteger(0, BG, OBJPROP_YSIZE, 190);
   ObjectSetInteger(0, BG, OBJPROP_XSIZE, 430);
   ObjectSetInteger(0, BG, OBJPROP_BGCOLOR, C'22,24,30');
   ObjectSetInteger(0, BG, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, BG, OBJPROP_COLOR, C'70,74,84');
   ObjectSetInteger(0, BG, OBJPROP_BACK, false);
   ObjectSetInteger(0, BG, OBJPROP_SELECTABLE, false);
   }
   else ObjectDelete(0, BG);

   for(int i = 0; i < NLINES; i++)
   {
      LBL[i] = StringFormat("rg_l%d", i);
      if(ObjectFind(0, LBL[i]) < 0) ObjectCreate(0, LBL[i], OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, LBL[i], OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, LBL[i], OBJPROP_XDISTANCE, 20);
      ObjectSetInteger(0, LBL[i], OBJPROP_YDISTANCE, 112 + i * 15);
      ObjectSetInteger(0, LBL[i], OBJPROP_FONTSIZE, 9);
      ObjectSetInteger(0, LBL[i], OBJPROP_SELECTABLE, false);
      ObjectSetString(0, LBL[i], OBJPROP_FONT, "Consolas");
   }
   {
      double pip = PipSize();
      double sp0 = Spread() / pip;
      int    dg  = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
      double stopPx = (InpFixedSLPips > 0.0) ? InpFixedSLPips * pip
                                             : sp0 * InpMinStopVsSpread * pip;
      PrintFormat("[RG] %s: 1 pip = %.5f in price (%d digits, point %.5f). Spread %.2f = %.1f pips.",
                  _Symbol, pip, dg, SymbolInfoDouble(_Symbol, SYMBOL_POINT), Spread(), sp0);
      PrintFormat("[RG] stop %.1f pips = %.*f in PRICE   target %.1f pips = %.*f   breakeven %.1f%%",
                  stopPx / pip, dg, stopPx, stopPx * InpTargetR / pip, dg, stopPx * InpTargetR,
                  100.0 * (stopPx + Spread()) / (stopPx * (1.0 + InpTargetR)));
      if(InpFixedSLPips > 0.0 && stopPx <= Spread() * 1.5)
         PrintFormat("[RG] *** WARNING: the %.1f-pip stop is %.*f in price and the spread is %.*f."
                     " The stop is inside or barely outside the spread - it will be hit at once."
                     " Raise InpFixedSLPips.", InpFixedSLPips, dg, stopPx, dg, Spread());
   }
   if(InpHideOneClick) ChartSetInteger(0, CHART_SHOW_ONE_CLICK, false);
   EventSetTimer(1);
   PrintFormat("[RG] RiskGuardButtons v%s on %s - max %.2f lots, risk cap %.1f%%, daily cap %.1f%%,"
               " SL %d pips beyond the low/high of %d bars incl. the forming one, cooldown %ds after a loss",
               VER, _Symbol, InpHardMaxLots, InpRiskPct, InpMaxDailyLossPct,
               InpSLBufferPips, InpSLBars, InpCooldownSec);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   ObjectDelete(0, BTN_BUY); ObjectDelete(0, BTN_SELL);
   ObjectDelete(0, BTN_CLOSE); ObjectDelete(0, BG);
   for(int i = 0; i < NLINES; i++) ObjectDelete(0, LBL[i]);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
void OnTimer()
{
   EmergencyCheck();

   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   datetime today = StringToTime(StringFormat("%04d.%02d.%02d", t.year, t.mon, t.day));
   if(today != g_day)
   {
      g_day = today;
      g_day_start_balance = AccountInfoDouble(ACCOUNT_BALANCE);
      Say(StringFormat("new day. Starting balance %.2f, daily loss cap %.2f",
                       g_day_start_balance, g_day_start_balance * InpMaxDailyLossPct / 100.0));
   }

   double bal  = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq   = AccountInfoDouble(ACCOUNT_EQUITY);
   double lots = AllowedLots();

   double sl; string why = "";
   double riskBuy = 0.0, pipsBuy = 0.0;
   if(StopFor(true, sl, why))
   {
      double d = MathAbs(SymbolInfoDouble(_Symbol, SYMBOL_ASK) - sl);
      riskBuy = RiskMoney(lots, d); pipsBuy = d / PipSize();
   }

   double oRisk, oPL; int oN = OurPositions(oRisk, oPL);
   double eff2 = RangeEfficiency();
   int st1 = TrendOf(PERIOD_M1, 15), st5 = TrendOf(PERIOD_M5, 12), st15 = TrendOf(PERIOD_M15, 8);
   string arrow = "";
   StringConcatenate(arrow, (st1 > 0 ? "M1 up" : (st1 < 0 ? "M1 dn" : "M1 --")), "  ",
                            (st5 > 0 ? "M5 up" : (st5 < 0 ? "M5 dn" : "M5 --")), "  ",
                            (st15 > 0 ? "M15 up" : (st15 < 0 ? "M15 dn" : "M15 --")));

   double lvlB = 0.0, lvlS = 0.0; int tB = 0, tS = 0;
   bool srBuy  = InpBlockAtSR && NearSR(true,  lvlB, tB);
   bool srSell = InpBlockAtSR && NearSR(false, lvlS, tS);
   int ls = LossStreak();

   double po = iOpen(_Symbol, PERIOD_CURRENT, 0), pc = iClose(_Symbol, PERIOD_CURRENT, 0);
   bool candleGreen = (po > 0.0 && pc > po), candleRed = (po > 0.0 && pc < po);
   bool candleNoBuy  = InpNeedCandleAgrees && candleRed;
   bool candleNoSell = InpNeedCandleAgrees && candleGreen;

   string warn = "";
   if(candleNoBuy)  warn += "forming candle RED - no BUY   ";
   if(candleNoSell) warn += "forming candle GREEN - no SELL   ";
   if(srBuy)  warn += StringFormat("BUY BLOCKED: resistance touched %dx   ", tB);
   if(srSell) warn += StringFormat("SELL BLOCKED: support touched %dx   ", tS);
   if(InpBlockRanging && eff2 < InpRangeMinEff)
      warn += StringFormat("RANGING %.2f - coffee break   ", eff2);
   if(ls >= InpLossStreakLock) warn += StringFormat("%d LOSSES IN A ROW   ", ls);

   string lockReason = ""; bool locked = DailyLocked(lockReason);
   int cd = (int)MathMax(0, (long)g_cooldown_until - (long)TimeCurrent());
   string state = locked ? "LOCKED (daily cap)"
                : (cd > 0 ? StringFormat("COOLDOWN %ds", cd)
                : (oN > 0 ? "IN A TRADE" : "ready"));
   string recent = ((TimeCurrent() - g_msg_at < 25) ? g_msg : "");

   string L[NLINES];
   L[0] = StringFormat("RiskGuard %s   %s", VER, state);
   L[1] = StringFormat("balance %.2f  equity %.2f  today %+.2f of -%.2f  losing streak %d",
                       bal, eq, eq - g_day_start_balance,
                       g_day_start_balance * InpMaxDailyLossPct / 100.0, ls);
   L[2] = StringFormat("open %d/%d  risking %.2f of %.2f  floating %+.2f (auto-close -%.2f)",
                       oN, InpMaxOpenPositions, oRisk, bal * InpMaxTotalRiskPct / 100.0,
                       oPL, bal * InpEmergencyClosePct / 100.0);
   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double tpBuy = SymbolInfoDouble(_Symbol, SYMBOL_ASK) + (pipsBuy * PipSize()) * InpTargetR;
   L[3] = (bal <= 0.0)
          ? "ACCOUNT BALANCE IS 0.00 - nothing can be risked, every click will be refused"
          : StringFormat("BUY now: %.2f lots  SL %.*f (%.1f pips, %.2f%%)  TP %.*f  R 1:%.1f",
                         lots, dg, sl, pipsBuy, 100.0 * riskBuy / bal, dg, tpBuy, InpTargetR);
   int sct, scw; double scp; Score(sct, scw, scp);
   L[4] = (sct > 0)
          ? StringFormat("SCORE %d clicks  %.0f%% won  %+.1f pips  %+.3f/click   eff %.2f",
                         sct, 100.0 * scw / sct, scp, scp / sct, eff2)
          : StringFormat("trend %s    M1 efficiency %.2f %s",
                         arrow, eff2,
                         (InpBlockRanging ? StringFormat("(blocks under %.2f)", InpRangeMinEff)
                                          : "(shown, not blocked)"));
   L[5] = (warn != "") ? warn : recent;

   for(int li = 0; li < NLINES; li++)
   {
      ObjectSetString(0, LBL[li], OBJPROP_TEXT, L[li]);
      color c = ChartText((li == 1 || li == 2 || li == 4));
      if(li == 5 && warn != "")            c = clrOrangeRed;
      else if(li == 3 && bal <= 0.0)       c = clrOrangeRed;
      else if(li == 0 && locked)           c = clrOrangeRed;
      else if(li == 0 && cd > 0)           c = clrGoldenrod;
      ObjectSetInteger(0, LBL[li], OBJPROP_COLOR, c);
   }


   // the buttons themselves go dark when the guards say no - a disabled button is clearer
   // than a message under one that still looks clickable
   bool rangeStop = InpBlockRanging && eff2 < InpRangeMinEff;
   bool noBuy  = locked || cd > 0 || srBuy  || candleNoBuy  || rangeStop || ls >= InpLossStreakLock;
   bool noSell = locked || cd > 0 || srSell || candleNoSell || rangeStop || ls >= InpLossStreakLock;
   ObjectSetInteger(0, BTN_BUY,  OBJPROP_BGCOLOR, noBuy  ? C'45,45,50' : C'0,130,70');
   ObjectSetInteger(0, BTN_SELL, OBJPROP_BGCOLOR, noSell ? C'45,45,50' : C'170,45,45');
   ObjectSetString(0, BTN_BUY,  OBJPROP_TEXT,
                   noBuy  ? "BUY  X" : StringFormat("BUY %.2f", lots));
   ObjectSetString(0, BTN_SELL, OBJPROP_TEXT,
                   noSell ? "SELL X" : StringFormat("SELL %.2f", lots));

   ChartRedraw(0);
}

//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id != CHARTEVENT_OBJECT_CLICK) return;
   ObjectSetInteger(0, sparam, OBJPROP_STATE, false);   // MQL5 buttons latch; release it
   if(sparam == BTN_BUY)        Open(true);
   else if(sparam == BTN_SELL)  Open(false);
   else if(sparam == BTN_CLOSE) CloseAll();
   ChartRedraw(0);
}
//+------------------------------------------------------------------+
