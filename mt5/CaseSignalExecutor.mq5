//+------------------------------------------------------------------+
//| CaseSignalExecutor.mq5                                            |
//| Executes the pattern-matcher's TAKE signals on the DEMO account.  |
//|                                                                   |
//| Detection lives in Python (pattern_matcher.py live()) which       |
//| writes Common\Files\case_signal.json when a validated rule-stencil |
//| setup (Rule 1 / Rule 2) completes. This EA reads that file, opens  |
//| the trade, and manages the Feb-11 asymmetric exit:                 |
//|   - hard SL from the signal (cut losers small)                     |
//|   - let winners run; trailing-reversal: once +ArmPts, exit if it   |
//|     gives back GivePts from the peak; hard TP cap = runaway ceiling |
//|                                                                   |
//| Attach to XAUUSD, enable Algo Trading. DEMO only until proven.     |
//+------------------------------------------------------------------+
#property version   "1.74"
// v1.74 PATIENCE + COLOUR-ABORT (Zee 2026-08-07, both trial-proven on 187 setups):
//  * GRACE PERIOD — "a VSA breakout takes several candles to actually go." The tape
//    agreed: median 15 bars to best price, only 21% peak within 3, and 57% of the
//    setups that eventually reached +2pt dipped -1pt FIRST (the floor was killing
//    more than half our winners). Suspending the basket floor for the first
//    InpGraceBars minutes: WR 50% -> 80%, net +$213 -> +$868, max DD -$72.
//    The 3pt parachute stays armed throughout, so the grace is bounded.
//  * COLOUR-ABORT — Zee's 19:02 catch: the door fired a SELL intrabar and that
//    candle CLOSED GREEN (+$-14.40). Across the tape, door fires whose candle
//    closed the WRONG colour ran 12% WR / -$153; right-colour ones 60% / +$1074.
//    So: when the ENTRY candle closes the wrong colour and we are not yet in
//    profit, the ghost leaves at once instead of grinding to the floor.
// v1.73 THE BASKET GAME (Zee 2026-08-06, his lifecycle verbatim): "multiple
// entries -> all in red -> IMP: wait until they turn blue -> some turn blue ->
// close all profitable (repeat) -> close the final lossy ones in loss -> done."
//  * NO per-click ghost — squad members tolerate individual red (Feb-11 receipts:
//    his real per-click losses were -0.09..-0.19pt, never 1pt stops).
//  * BASKET FLOOR: total adverse <= -(sum of per-click G) -> evaporate ALL.
//    G = max(1.0, 35% of avg last-5-candle range, cap 2.5) — volatility-aware,
//    so a 7pt-candle storm cannot rob the squad (the 16:05 SELL, -$11.10, then
//    a 16-point fall without us).
//  * GREEN SWEEP unchanged — the harvest loop, repeating.
//  * CAMPAIGN END: compass flips against the squad OR a click older than
//    InpCampaignMaxMin (25 = Feb-11 max patience) -> close remainder. Done.
//  * REMOVED: the 65s sibling time-exit (contradicted "wait until blue").
// v1.72 AUDIT FIXES (Zee: "find and fix any other bugs, wisdomfully"):
//  BUG1 RELOAD AMNESIA (receipts: the 08-04 #...032 double-fire, the 08-06 11:36
//    twins): every reattach wiped g_last_id/g_last_lamp/g_raids -> fresh (<180s)
//    signals refired and raid counters reset. Now persisted in terminal
//    GlobalVariables — they survive reattach, recompile, and terminal restart.
//  BUG2 STALE CROSS-PROOF: g_cross_t0 was not reset after firing, so a
//    harvest-and-return re-raid could fire instantly on proof accumulated BEFORE
//    the harvest. Reset on every fire; each raid earns its own 3 seconds.
// v1.71 SUSTAINED CROSS (the 15:10 doji wick-poke, -$10.80): a doji's wick kissed
// the lamp for ONE second, the door fired, price rejected instantly. Real breakouts
// HOLD beyond the lamp; pokes die in under a second. The door now requires the
// cross to persist InpCrossHoldS seconds before firing. (The momentum-body law
// only exists on the closed-candle path — the door cannot judge an unfinished
// candle, but it CAN demand the cross prove itself for three seconds.)
// v1.70 GREEN SWEEP — the true "Close All Profitable" semantics (Zee's example:
// +1 -5 +3 +4 -9 +8 -> sweep banks the greens (+16), reds -9 -5 stay and fight;
// later +1 -3 -> the green's own trail handles it; reds exit via ghost/BE).
// Trigger: 2+ PROFITABLE clicks whose combined profit >= InpGreenSumPts -> close
// ALL profitable positions same-second; reds untouched. A single green is never
// swept (that's the ratchet rider's seat — Feb-11's 37%-of-the-day money).
// v1.69: basket trigger becomes an OR (Zee's screenshots: +$15.70 and +$10.30
// baskets sat unharvested because avg/click was under $3). Now fires on EITHER
// avg >= InpBasketAvgPts ("$3 each") OR total >= InpBasketTotPts ($10 on the table).
// v1.68 THE FEB-11 EXIT TRINITY (Zee 2026-08-06):
//  1. BASKET HARVEST — his real exit: "wait for red then blue, then Close All
//     Profitable." 2+ clicks open averaging +InpBasketAvgPts each -> every
//     PROFITABLE position closes at once (23/24 Feb-11 bursts exited same-second).
//  2. TIME-HARVEST SIBLINGS — the overnight -$110.80 killed the distance bracket
//     in Asia chop; the time study (106 setups): edge develops over 45-65s
//     (65s = Feb-11 median hold, 95% on tape). Siblings hold InpSibHoldS seconds
//     (ghost bail -1.0), then close at market.
//  3. (matcher) Asia discipline: no click-bursts 01:00-07:00 broker.
// v1.67: sibling bracket 0.5 -> 1.0 — TWO independent days converge there: Aug-5
// tick curve rising through 1.0-1.2, and Feb-11's own median win = +1.01pt (94%%).
// v1.66 SPEED-HARVEST SIBLINGS (Zee 2026-08-06, tick-validated: 70% favorable-first
// at ±0.5pt within seconds of the breakout, EV +0.134pt/click at Raw costs):
// burst SIBLINGS exit on a software micro-bracket ±InpSibBracket — quick lamps in
// the breakout's living seconds. The LEAD click keeps ghost+ratchet (the riders).
// Max loss per sibling: $5.70 — tighter than the 1pt ghost. Edge requires
// Raw-account costs; on Standard spreads it computes ~breakeven.
// v1.65 CLICK-BURST (Zee 2026-08-06, his true Feb-11 mechanic): "buy buy buy
// multiple times 0.1 lots.. many ghosts into the room.. the multiplier should work
// not with larger lot size but with more trades of 0.1 each." A convicted lamp
// fires N separate 0.10 clicks a few seconds apart (armed file "clicks"); each
// click trails its OWN peak and dies its own cheap death. Burst siblings bypass
// the all-armed stacking rule (they ARE the burst); 1.20-lot ceiling still holds.
// v1.64 SEND-COOLDOWN (2026-08-05): the door path and the signal path were double-
// firing the same setup within 1 second — each checked "do we hold a position?"
// while the other's order was still IN FLIGHT at the broker (fill latency makes it
// invisible for ~hundreds of ms). One timestamp bridges the blindness: after any
// order is sent, no new entry for InpSendCooldownS seconds.
// v1.63 RATCHET TRAIL (2026-08-05): gold moved 109 points; the flat 0.2 give-back
// harvested $13.70 gross all morning (avg win $3.42 vs avg loss $11.76 = 77% WR
// needed to break even). Give now grows with the peak — max(InpGivePts,
// InpGiveFrac*peak) — so scalps harvest fast AND runners ride trends.
// v1.62 A LOSING RAID RETIRES THE LAMP (2026-08-05): the 23:13 -$32.40 was raid 2
// entering BIGGER after raid 1 lost. Feb-11 Zee added clicks to WINNING setups only.
// Now any ghost/backstop (losing) exit closes the lamp for good — next lamp, fresh start.
// v1.61 HARVEST-AND-RETURN (2026-08-05): a repeat apparition may only fire after
// price has RETURNED to the lamp since the previous raid. The 22:20 -$30 loss was
// raid 2 firing while price HOVERED above the lamp (never came back) — buying the
// crest of raid 1's own pop. Zee's model was always "harvest, price re-crosses the
// lamp, go again"; now the code matches the words.
// v1.60 STUCK-GHOST INSURANCE (Zee 2026-08-04):
//   * STRUCTURAL SL: broker stop a few points beyond the last swing before the
//     breakout ("in case the ghost is stuck"), sent per-lamp by the matcher ("sl").
//     Clamped: never wider than InpHardSLPts, never tighter than 0.4pt (broker).
//   * BREAKEVEN AT 1:1 R:R: once profit reaches one R (entry-to-SL distance), the
//     stop moves to entry — "breakeven ensures we're not losing money." The ghost
//     exit and trail still do the real exiting; these bound the stuck case.
// v1.51: the Laws of Conviction do NOT gate entry (Zee) — every armed lamp fires;
// diamonds only set the raid allowance, sent per-lamp by the matcher ("raids"):
// 0 diamonds -> 1 apparition, 1 -> 3, 2+ -> 6. InpMaxRaids stays the hard ceiling.
#property strict
#include <Trade/Trade.mqh>
// v1.50 REPEAT APPARITIONS (Zee 2026-08-04): "if the law of conviction holds on a
// trade, we go on to tell the ghost that it can keep apparating multiple times since
// we're dead sure this is a working setup. that's how i sometimes do a burst of 5-6
// trades to harvest as much profit as i can on a convicted law setup."
//   One convicted lamp = up to InpMaxRaids entries while it stays armed and fresh:
//   harvest a click, price re-crosses the lamp, go again. The matcher retires the
//   lamp when the setup dies (price runs away, candle-close break, slant flips) —
//   the raid counter is per-lamp and code-enforced (greed has no measurement).
// v1.40 STACKING + DYING LAMP (Zee 2026-08-04):
//   * "we allow and encourage multiple positions when sure to gather as much
//     profit as we can from a verified burst" — a new entry may JOIN open ones,
//     but only if every open click has already ARMED (its pop is proven), only
//     in the SAME direction, and only up to InpMaxStackLots total. The ceiling
//     is code, not judgement (greed has no measurement).
//   * "catching a lamp with dying light": the armed file now carries a per-lamp
//     chase allowance — 1pt normally, 3pt when the last bars are running hard in
//     the trade's direction (matcher decides; EA obeys).
//   * Each position now trails its OWN peak (per-ticket), so stacked clicks exit
//     independently: early clicks keep their trail, late clicks their ghost.
// v1.30 GHOST AT THE DOOR: matcher writes case_armed.json (lamp level, pattern
// complete except the break); OnTick fires the millisecond live price crosses.
// Armed data older than 180s is dead.

// v1.20 GHOST EXIT (2026-08-04, Zee's own words): "we never let the trade roll
// into loss in the first place. as soon as we realize the burst is going against
// us, we exit the market like a ghost trying to evaporate."
//   * The burst either pops (arm at +0.3, then trail) or it evaporates: a trade
//     that never armed and moves GhostCap points against us is closed at once.
//     No waiting for a bounce, no fixed-distance bleeding to a far stop.
//   * GhostCap shrinks as the burst grows so the exit money stays ~$10-$30:
//       0.10 -> 1.0pt ($10)   0.30 -> 1.0pt ($30)   0.60 -> 0.5pt ($30)
//   * The BROKER stop now sits far away (3pt) as a pure parachute — it exists
//     only for the day the terminal/EA itself dies mid-trade. The tight cut is
//     software, because 0.5pt broker stops get rejected as [invalid stops].
//   * Bursts up to 0.60 (Zee's real 6-click size on Feb 11; today's -$61.20
//     showed why cap must scale: 0.20 lots on a FLAT 3pt cap = double damage).
// v1.10: TP cap lifted (winners run on the trail), staleness guard (no refires).
input double InpDefaultLots = 0.10;   // fallback lots if signal omits it
input int    InpMagic       = 88020;  // CaseSignalExecutor magic
input double InpHardSLPts    = 3.0;    // PARACHUTE broker stop (terminal-death insurance only)
input double InpGhostPts     = 1.0;    // ghost exit: un-armed trade this far against us -> evaporate
input double InpArmPts       = 0.3;    // arm at +0.3pt -> the pop Zee harvests per click
input double InpGivePts      = 0.2;    // minimum give-back from peak (small rides)
input double InpGiveFrac     = 0.30;   // ratchet: give = max(GivePts, Frac*peak) — runners ride
input double InpTpCapPts     = 999.0;  // no ceiling — the trail is the exit
input int    InpMaxAgeSec    = 180;    // ignore signals older than this (re-attach refire guard)
input string InpSignalFile   = "case_signal.json";
input string InpArmedFile    = "case_armed.json";   // pre-breakout lamp level (tick-fire)
input double InpMaxChasePts  = 1.0;    // fallback chase past the lamp (armed file may allow 3)
input double InpMaxStackLots = 1.20;   // hard ceiling on total stacked lots (code-enforced)
input int    InpMaxRaids     = 6;      // apparitions per convicted lamp (Zee's 5-6 burst)
input int    InpSendCooldownS = 4;     // seconds after any order send before another entry
input int    InpClickSpaceS   = 2;     // spacing between burst sibling clicks
input int    InpCrossHoldS    = 3;     // door fires only after the cross holds this long
input int    InpGraceBars     = 2;     // minutes of patience before the basket floor arms
input bool   InpColourAbort  = true;  // leave if the ENTRY candle closes the wrong colour
input int    InpCampaignMaxMin = 25;   // max patience per click (Feb-11 maximum), minutes
input int    InpGreenMin      = 2;     // sweep needs at least this many GREEN clicks
input double InpGreenSumPts   = 0.6;   // ...whose combined profit reaches this (0.6 = ~$6)

// Ghost cut, lot-scaled so the exit money stays roughly constant per burst.
double GhostCap(double lots) {
   double scaled = InpHardSLPts * InpDefaultLots / MathMax(lots, InpDefaultLots);
   return MathMin(InpGhostPts, scaled);
}

CTrade  trade;
long    g_last_id = -1;
// armed lamp (refreshed each second from case_armed.json; up to InpMaxRaids fires per id)
long    g_armed_id = -1, g_last_lamp = -1, g_armed_ts = 0;
int     g_raids = 0, g_armed_raids = 1;   // per-lamp allowance from the matcher (diamonds)
bool    g_lamp_ready = true;               // harvest-and-return: reset by a lamp re-touch
long    g_last_send = 0;                   // send-cooldown anchor (epoch, TimeGMT)
long    g_cross_t0 = 0;                    // sustained-cross: when the cross was first seen
datetime g_last_bar = 0;                   // colour-abort: last M1 bar we examined
double  g_armed_sl = 0;                    // structural SL from the matcher (0 = none)
int     g_armed_clicks = 1;                // burst size (matcher "clicks", 0.10 each)
int     g_burst_left = 0;                  // siblings still to fire for this burst

// Broker stop: prefer the structural level; clamp to [0.4pt .. InpHardSLPts] distance.
double BrokerSL(bool isbuy, double px, double structural) {
   double d = isbuy ? (px - structural) : (structural - px);
   if (structural > 0 && d >= 0.4 && d <= InpHardSLPts) return structural;
   return isbuy ? (px - InpHardSLPts) : (px + InpHardSLPts);
}
string  g_armed_side = "";
double  g_armed_level = 0, g_armed_lots = 0, g_armed_chase = 1.0;

// Per-position peaks: with stacking, every click trails its OWN best point.
ulong  g_tk[24];
double g_pk[24];
double g_gv[24];                          // per-click volatility ghost G (basket floor)
double PeakOf(ulong t)            { for (int i = 0; i < 24; i++) if (g_tk[i] == t) return g_pk[i]; return 0.0; }
void   SetPeakOf(ulong t, double v) {
   for (int i = 0; i < 24; i++) if (g_tk[i] == t) { g_pk[i] = v; return; }
   for (int i = 0; i < 24; i++) if (g_tk[i] == 0) { g_tk[i] = t; g_pk[i] = v; return; }
}
void   DropPeakOf(ulong t)        { for (int i = 0; i < 24; i++) if (g_tk[i] == t) { g_tk[i] = 0; g_pk[i] = 0; g_gv[i] = 0; return; } }
double GOf(ulong t)               { for (int i = 0; i < 24; i++) if (g_tk[i] == t) return g_gv[i]; return 0.0; }
void   SetGOf(ulong t, double v)  { for (int i = 0; i < 24; i++) if (g_tk[i] == t) { g_gv[i] = v; return; } }
bool   HasSlot(ulong t)           { for (int i = 0; i < 24; i++) if (g_tk[i] == t) return true; return false; }
// volatility-aware per-click ghost: 35% of the recent candle weather, 1.0..2.5
double CalcG() {
   double s = 0; int n = 0;
   for (int k = 1; k <= 5; k++) {
      double hh = iHigh(_Symbol, PERIOD_M1, k), ll = iLow(_Symbol, PERIOD_M1, k);
      if (hh > 0 && ll > 0) { s += hh - ll; n++; }
   }
   double avg = (n > 0) ? s / n : 1.0;
   return MathMin(2.5, MathMax(1.0, 0.35 * avg));
}

double OurLots() {
   double tot = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (!PositionSelectByTicket(t)) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagic
          || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      tot += PositionGetDouble(POSITION_VOLUME);
   }
   return tot;
}

// Zee: stack onto a VERIFIED burst only — same direction, every open click already
// armed (pop proven), total lots under the code-enforced ceiling. Never averaging
// into a loser, never hedging our own raid.
bool StackAllowed(string side, double addlots) {
   double tot = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (!PositionSelectByTicket(t)) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagic
          || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      bool isbuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      if ((side == "BUY") != isbuy) return false;
      if (PeakOf(t) < InpArmPts) return false;
      tot += PositionGetDouble(POSITION_VOLUME);
   }
   return (tot + addlots <= InpMaxStackLots + 0.001);
}

void ReadArmed() {
   if (!FileIsExist(InpArmedFile, FILE_COMMON)) { g_armed_id = -1; return; }
   int h = FileOpen(InpArmedFile, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if (h == INVALID_HANDLE) return;
   string txt = "";
   while (!FileIsEnding(h)) txt += FileReadString(h);
   FileClose(h);
   g_armed_id = (long)JNum(txt, "id");
   g_armed_side = JStr(txt, "side");
   g_armed_level = JNum(txt, "level");
   g_armed_lots = JNum(txt, "lots");
   g_armed_ts = (long)JNum(txt, "ts");
   double c = JNum(txt, "chase");
   g_armed_chase = (c == EMPTY_VALUE || c <= 0) ? InpMaxChasePts : c;
   double r = JNum(txt, "raids");
   g_armed_raids = (r == EMPTY_VALUE || r < 1) ? 1 : (int)r;
   double s = JNum(txt, "sl");
   g_armed_sl = (s == EMPTY_VALUE) ? 0 : s;
   double ck = JNum(txt, "clicks");
   g_armed_clicks = (ck == EMPTY_VALUE || ck < 1) ? 1 : (int)ck;
}

int OnInit() {
   trade.SetExpertMagicNumber(InpMagic);
   EventSetTimer(1);
   // BUG1 fix: restore persistent counters (survive reattach/recompile)
   if (GlobalVariableCheck("CaseExec_last_id"))   g_last_id   = (long)GlobalVariableGet("CaseExec_last_id");
   if (GlobalVariableCheck("CaseExec_last_lamp")) g_last_lamp = (long)GlobalVariableGet("CaseExec_last_lamp");
   if (GlobalVariableCheck("CaseExec_raids"))     g_raids     = (int)GlobalVariableGet("CaseExec_raids");
   Print("[CaseExec] v1.74 loaded — grace period + colour-abort");
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r) { EventKillTimer(); }

// ── minimal JSON field readers (flat file we control) ─────────────────────
double JNum(string s, string key) {
   int p = StringFind(s, "\"" + key + "\":");
   if (p < 0) return EMPTY_VALUE;
   return StringToDouble(StringSubstr(s, p + StringLen(key) + 3));
}
string JStr(string s, string key) {
   int p = StringFind(s, "\"" + key + "\":\"");
   if (p < 0) return "";
   p += StringLen(key) + 4;
   int e = StringFind(s, "\"", p);
   return StringSubstr(s, p, e - p);
}

bool HasOurPos() {
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (PositionSelectByTicket(t)
          && PositionGetInteger(POSITION_MAGIC) == InpMagic
          && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
}

// Poll the signal file; open a trade on a NEW signal id.
void OnTimer() {
   ReadArmed();
   if (!FileIsExist(InpSignalFile, FILE_COMMON)) return;
   int h = FileOpen(InpSignalFile, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if (h == INVALID_HANDLE) return;
   string txt = "";
   while (!FileIsEnding(h)) txt += FileReadString(h);
   FileClose(h);

   long id = (long)JNum(txt, "id");
   if (id <= g_last_id) return;      // already processed
   g_last_id = id;
   GlobalVariableSet("CaseExec_last_id", (double)g_last_id);
   // STALENESS GUARD: reattach resets g_last_id and re-reads the file — never
   // execute an old signal at today's price (bitten twice on 2026-08-04).
   long ts = (long)JNum(txt, "ts");
   if (ts > 0 && (long)TimeGMT() - ts > InpMaxAgeSec) {
      PrintFormat("[CaseExec] IGNORING stale signal #%d (%d s old)", id, (long)TimeGMT() - ts);
      return;
   }
   string side = JStr(txt, "side");
   double lots = JNum(txt, "lots"); if (lots <= 0) lots = InpDefaultLots;
   if (!StackAllowed(side, lots)) return;   // join a verified burst, or wait
   if ((long)TimeGMT() - g_last_send < InpSendCooldownS) return;   // in-flight guard
   g_last_send = (long)TimeGMT();

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   // Broker SL: structural level from the signal if sane, else the 3pt parachute.
   double ssl = JNum(txt, "sl"); if (ssl == EMPTY_VALUE) ssl = 0;
   double sl = BrokerSL(side == "BUY", (side == "BUY") ? ask : bid, ssl);
   if (side == "BUY")       trade.Buy(lots, _Symbol, 0, sl, 0, "case");
   else if (side == "SELL") trade.Sell(lots, _Symbol, 0, sl, 0, "case");
   PrintFormat("[CaseExec] signal #%d %s lots=%.2f ghost=%.2fpt stackable parachute=%.2f",
               id, side, lots, GhostCap(lots), sl);
}

// Manage the Feb-11 exit on every tick — and grab armed lamps at tick speed.
void OnTick() {
   // BURST SIBLINGS (v1.65): after the lead click, fire the remaining 0.10 clicks
   // a few seconds apart while price is still in the lamp's zone. Siblings bypass
   // the all-armed stack rule; the 1.20-lot ceiling and direction rule still hold.
   if (g_burst_left > 0 && g_armed_id == g_last_lamp
       && (long)TimeGMT() - g_last_send >= InpClickSpaceS
       && (long)TimeGMT() - g_armed_ts <= InpMaxAgeSec) {
      double sb = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sa = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      bool inzone = (g_armed_side == "BUY")
                    ? (sa > g_armed_level - 0.3 && sa <= g_armed_level + g_armed_chase)
                    : (sb < g_armed_level + 0.3 && sb >= g_armed_level - g_armed_chase);
      if (inzone && OurLots() + g_armed_lots <= InpMaxStackLots + 1e-9) {
         g_last_send = (long)TimeGMT();
         g_burst_left--;
         double bsl = BrokerSL(g_armed_side == "BUY",
                               (g_armed_side == "BUY") ? sa : sb, g_armed_sl);
         if (g_armed_side == "BUY")  trade.Buy(g_armed_lots, _Symbol, 0, bsl, 0, "ghost-s");
         else                        trade.Sell(g_armed_lots, _Symbol, 0, bsl, 0, "ghost-s");
         PrintFormat("[CaseExec] BURST sibling %d remaining (basket game), lamp %.2f",
                     g_burst_left, g_armed_level);
      } else if (!inzone) {
         g_burst_left = 0;            // zone left the station — no chasing siblings
      }
   }

   // GHOST AT THE DOOR: fire the instant live price crosses the armed level.
   // REPEAT APPARITIONS: while the convicted lamp stays armed, harvest-and-return —
   // up to InpMaxRaids entries per lamp (Zee's 5-6 burst on a Law-of-Conviction
   // setup). Chase allowance comes per-lamp; stacking allowed onto a verified burst.
   if (g_armed_id > 0 && (long)TimeGMT() - g_armed_ts <= InpMaxAgeSec) {
      if (g_armed_id != g_last_lamp) {
         g_last_lamp = g_armed_id; g_raids = 0; g_lamp_ready = true; g_cross_t0 = 0;
         GlobalVariableSet("CaseExec_last_lamp", (double)g_last_lamp);
         GlobalVariableSet("CaseExec_raids", 0);
      }
      int raid_cap = (int)MathMin(InpMaxRaids, g_armed_raids);   // diamonds decide
      if (g_raids < raid_cap && StackAllowed(g_armed_side, g_armed_lots)) {
         double abid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double aask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         // HARVEST-AND-RETURN: after a raid, price must come BACK to the lamp before
         // the ghost may cross again — no re-firing mid-hover above it.
         if (!g_lamp_ready) {
            if (g_armed_side == "BUY" && aask <= g_armed_level) g_lamp_ready = true;
            else if (g_armed_side == "SELL" && abid >= g_armed_level) g_lamp_ready = true;
         }
         bool cross = false;
         if (g_lamp_ready && g_armed_side == "BUY")
            cross = (aask > g_armed_level && aask <= g_armed_level + g_armed_chase);
         else if (g_lamp_ready && g_armed_side == "SELL")
            cross = (abid < g_armed_level && abid >= g_armed_level - g_armed_chase);
         // SUSTAINED CROSS (v1.71): the cross must prove itself for InpCrossHoldS
         // seconds — wick-pokes reject in under one and never earn the fire.
         if (cross && g_cross_t0 == 0) g_cross_t0 = (long)TimeGMT();
         if (!cross) g_cross_t0 = 0;
         bool proven = cross && g_cross_t0 > 0
                       && (long)TimeGMT() - g_cross_t0 >= InpCrossHoldS;
         if (proven && (long)TimeGMT() - g_last_send >= InpSendCooldownS) {
            g_last_send = (long)TimeGMT();
            g_raids++;
            g_lamp_ready = false;
            g_cross_t0 = 0;                                   // BUG2: fresh proof per raid
            GlobalVariableSet("CaseExec_raids", g_raids);     // BUG1: survive reloads
            g_burst_left = g_armed_clicks - 1;   // siblings follow (Zee's buy-buy-buy)
            double asl = BrokerSL(g_armed_side == "BUY",
                                  (g_armed_side == "BUY") ? aask : abid, g_armed_sl);
            if (g_armed_side == "BUY")  trade.Buy(g_armed_lots, _Symbol, 0, asl, 0, "ghost");
            else                        trade.Sell(g_armed_lots, _Symbol, 0, asl, 0, "ghost");
            PrintFormat("[CaseExec] GHOST-DOOR #%d %s raid %d/%d lamp %.2f lots=%.2f chase=%.1f ghost=%.2fpt",
                        g_armed_id, g_armed_side, g_raids, raid_cap, g_armed_level,
                        g_armed_lots, g_armed_chase, GhostCap(g_armed_lots));
         }
      }
   }
   // COLOUR-ABORT (v1.74): when a new M1 bar forms, look at the candle that just
   // closed; any position opened INSIDE it that finished the wrong colour and is
   // not in profit leaves immediately (Zee's 19:02 green-candle SELL).
   if (InpColourAbort) {
      datetime bt0 = iTime(_Symbol, PERIOD_M1, 0);
      if (bt0 != g_last_bar) {
         if (g_last_bar != 0) {
            datetime bt1 = iTime(_Symbol, PERIOD_M1, 1);
            double o1 = iOpen(_Symbol, PERIOD_M1, 1), c1 = iClose(_Symbol, PERIOD_M1, 1);
            bool bar_green = (c1 > o1), bar_red = (c1 < o1);
            double abid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double aask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            for (int ai = PositionsTotal() - 1; ai >= 0; ai--) {
               ulong at = PositionGetTicket(ai);
               if (!PositionSelectByTicket(at)) continue;
               if (PositionGetInteger(POSITION_MAGIC) != InpMagic
                   || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
               datetime pt = (datetime)PositionGetInteger(POSITION_TIME);
               if (pt < bt1 || pt >= bt0) continue;          // not the entry candle
               bool isbuy2 = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
               double e2 = PositionGetDouble(POSITION_PRICE_OPEN);
               double pf = isbuy2 ? (abid - e2) : (e2 - aask);
               bool wrong = (isbuy2 && bar_red) || (!isbuy2 && bar_green);
               if (wrong && pf <= 0) {
                  PrintFormat("[CaseExec] COLOUR-ABORT: entry candle closed %s on a %s — leaving (%.2fpt)",
                              bar_green ? "GREEN" : "RED", isbuy2 ? "BUY" : "SELL", pf);
                  trade.PositionClose(at); DropPeakOf(at);
               }
            }
         }
         g_last_bar = bt0;
      }
   }

   // THE BASKET GAME (v1.73): register every click with its weather-ghost G, and
   // enforce the SQUAD FLOOR — total adverse beyond -(sum G) means the burst was
   // simply wrong: evaporate ALL, campaign over, lamp retired.
   {
      int cn = 0; double csum = 0, gsum2 = 0;
      double cbid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double cask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      for (int ci = PositionsTotal() - 1; ci >= 0; ci--) {
         ulong ct = PositionGetTicket(ci);
         if (!PositionSelectByTicket(ct)) continue;
         if (PositionGetInteger(POSITION_MAGIC) != InpMagic
             || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
         bool cb = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
         double ce = PositionGetDouble(POSITION_PRICE_OPEN);
         double cp = cb ? (cbid - ce) : (ce - cask);
         if (!HasSlot(ct)) { SetPeakOf(ct, 0.0); SetGOf(ct, CalcG()); }
         cn++; csum += cp; gsum2 += GOf(ct);
      }
      // GRACE PERIOD (v1.74): the floor stays disarmed while the campaign is young —
      // breakouts need several candles to go. The 3pt parachute still guards below.
      long youngest = 0;
      for (int ci = PositionsTotal() - 1; ci >= 0; ci--) {
         ulong ct = PositionGetTicket(ci);
         if (!PositionSelectByTicket(ct)) continue;
         if (PositionGetInteger(POSITION_MAGIC) != InpMagic
             || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
         long agec = (long)TimeCurrent() - (long)PositionGetInteger(POSITION_TIME);
         if (youngest == 0 || agec < youngest) youngest = agec;
      }
      bool in_grace = (youngest > 0 && youngest < (long)InpGraceBars * 60);
      if (cn > 0 && csum <= -gsum2 && !in_grace) {
         PrintFormat("[CaseExec] BASKET FLOOR: %d clicks %+.2fpt breached -%.2f -> evaporate ALL",
                     cn, csum, gsum2);
         for (int ci = PositionsTotal() - 1; ci >= 0; ci--) {
            ulong ct = PositionGetTicket(ci);
            if (!PositionSelectByTicket(ct)) continue;
            if (PositionGetInteger(POSITION_MAGIC) != InpMagic
                || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
            trade.PositionClose(ct); DropPeakOf(ct);
         }
         g_raids = InpMaxRaids;
         GlobalVariableSet("CaseExec_raids", g_raids);
      }
   }

   // GREEN SWEEP (v1.70, Zee's true Close-All-Profitable): count the GREENS only;
   // 2+ greens totalling +InpGreenSumPts -> bank every green same-second. Reds stay
   // and fight under ghost/BE; a lone green rides its ratchet (the Feb-11 riders).
   {
      int gn = 0; double gsum = 0;
      double bbid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double bask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      for (int bi = PositionsTotal() - 1; bi >= 0; bi--) {
         ulong bt = PositionGetTicket(bi);
         if (!PositionSelectByTicket(bt)) continue;
         if (PositionGetInteger(POSITION_MAGIC) != InpMagic
             || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
         bool bb = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
         double be = PositionGetDouble(POSITION_PRICE_OPEN);
         double pp = bb ? (bbid - be) : (be - bask);
         if (pp > 0) { gn++; gsum += pp; }
      }
      if (gn >= InpGreenMin && gsum >= InpGreenSumPts) {
         PrintFormat("[CaseExec] CLOSE ALL PROFITABLE: %d greens %+.2fpt banked (reds fight on)",
                     gn, gsum);
         for (int bi = PositionsTotal() - 1; bi >= 0; bi--) {
            ulong bt = PositionGetTicket(bi);
            if (!PositionSelectByTicket(bt)) continue;
            if (PositionGetInteger(POSITION_MAGIC) != InpMagic
                || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
            bool bb = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
            double be = PositionGetDouble(POSITION_PRICE_OPEN);
            double pp = bb ? (bbid - be) : (be - bask);
            if (pp > 0) { trade.PositionClose(bt); DropPeakOf(bt); }
         }
      }
   }
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (!PositionSelectByTicket(t)) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagic
          || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      bool isbuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double prof = isbuy ? (bid - entry) : (entry - ask);   // favourable move, price pts
      // CAMPAIGN END (v1.73): the compass flipped against the squad, or this
      // click has outlived the Feb-11 maximum patience -> close it, done.
      long cage = (long)TimeCurrent() - (long)PositionGetInteger(POSITION_TIME);
      bool flipped = (g_armed_id > 0 && (long)TimeGMT() - g_armed_ts <= InpMaxAgeSec
                      && g_armed_side != "" && ((g_armed_side == "BUY") != isbuy));
      if (flipped || cage >= (long)InpCampaignMaxMin * 60) {
         trade.PositionClose(t); DropPeakOf(t);
         continue;
      }
      double pk = PeakOf(t);
      if (prof > pk) { pk = prof; SetPeakOf(t, pk); }
      // BREAKEVEN AT 1:1 (Zee): profit reached one R -> stop to entry. Not losing.
      double cursl = PositionGetDouble(POSITION_SL);
      double R = isbuy ? (entry - cursl) : (cursl - entry);
      if (cursl > 0 && R > 0.05 && prof >= R) {
         bool at_be = isbuy ? (cursl >= entry) : (cursl <= entry);
         if (!at_be) trade.PositionModify(t, isbuy ? entry + 0.05 : entry - 0.05,
                                          PositionGetDouble(POSITION_TP));
      }
      // (v1.73: the per-click ghost is GONE — squad members tolerate individual
      // red; the BASKET FLOOR above judges danger collectively, as Zee's hands did.)
      // absolute software backstop at the parachute distance (belt and braces)
      if (prof <= -InpHardSLPts) {
         trade.PositionClose(t); DropPeakOf(t);
         g_raids = InpMaxRaids;              // losing raid -> lamp retired
         continue;
      }
      // runaway take-profit ceiling
      if (prof >= InpTpCapPts) { trade.PositionClose(t); DropPeakOf(t); continue; }
      // trailing-reversal: let it run, exit on give-back after arming
      double give = MathMax(InpGivePts, InpGiveFrac * pk);   // ratchet trail
      if (pk >= InpArmPts && (pk - prof) >= give) {
         trade.PositionClose(t); DropPeakOf(t); continue;
      }
   }
   if (!HasOurPos()) for (int i = 0; i < 24; i++) { g_tk[i] = 0; g_pk[i] = 0; g_gv[i] = 0; }   // flat -> clean slate
}
//+------------------------------------------------------------------+
