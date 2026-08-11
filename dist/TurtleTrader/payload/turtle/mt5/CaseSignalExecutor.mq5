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
#property version   "1.82"
// v1.82 (2026-08-10) — THE TIGHT BOUND RESTORED, from Zee's own Feb-11 receipts
// replayed through MT5 on his real tick data. Same day, same tape:
//        avg WIN    avg LOSS   worst loss
//   ZEE  1.29 pt    0.13 pt    0.16 pt     69 trades, 94%, +EUR835
//   EA  10.20 pt    9.82 pt   21.93 pt      8 trades, 37%, -$213
// Our stop was 76x wider than his. He was not running a structural stop at all —
// he stepped off in a tenth of a point, 69 times in a day. That reflex IS the edge:
// at 10:1 win/loss you can be wrong half the time; at 1:1 you cannot.
// Tonight's five-trade test said "remove all interference"; his 69 REAL trades say
// the interference was the whole method. Five simulated trades do not outrank 69
// real ones, so the bound comes back: InpMaxRiskPts caps what any click may cost.
// The target still captures — only the downside is bounded.
// v1.81 (2026-08-10) — THE BREAKEVEN LOCK COMES OUT TOO. Zee swept its arming
// distance on the same 08-06 gold tape, five identical entries:
//     no lock at all   +$187.50      <-- best
//     lock at 4.0 pt   +$127.30
//     lock at 0.3 pt   +$116.90
//     lock at 1.0 pt   +$116.90
//     lock at 2.0 pt    +$57.80
// NO arming distance beat having no lock. My "synthesis" was wrong: the lock is
// the ratchet wearing a gentler name. At 2.0 it scratched at +$0.50 a trade that
// went on to make +$70.00; at 4.0 it did not arm in time to save the -$58.60 it
// exists for. It charges a premium every trade and pays out rarely.
// So v1.81 keeps ONLY what the market itself defines: the structural stop, the
// structural target, and the catastrophe parachute. The price of this is honest
// and must be said out loud — a full stop now costs what the structure says it
// costs (-$58.60 on that day at 0.10 lots) instead of being cut short.
// InpBEArmPts=0 turns the lock off; set it >0 to bring it back.
// v1.80 THE SYNTHESIS (2026-08-10) — decided by MT5's own Strategy Tester on
// XAUUSD_OANDA, 08-05..08-07, OUR real volume, real spread, real slippage.
// Three exits, IDENTICAL entries, five trades:
//     our live ratchet        +$12.90   (worst -$5.40)
//     Zee hold-to-flat + BE  +$116.00   (worst -$0.40)
//     pure structural target +$187.50   (worst -$58.60)
// Trade by trade the mechanism was visible: the ratchet took -$4.10 and -$5.40
// out of two trades that were worth +$70.00 and +$60.70 — it does not merely
// clip winners, it converts the biggest ones into losses. And the breakeven
// lock turned a -$58.60 disaster into +$0.50.
// So each exit owned one half. This version keeps both halves and drops the
// interference: BREAKEVEN LOCK protects, the STRUCTURAL TARGET captures, and
// nothing closes a live trade in between. On those same five trades the
// combination gives +$246.60 — better than any of the three.
// InpSynthesis=false restores the v1.79 machine in one input.
// v1.79 PROTECT WHAT YOU HAVE EARNED (CaseExec, 2026-08-08). Measured on the REAL
// losing fills, not a simulation: 63% of our losers were IN PROFIT before they
// became losses, and the 35 gold losses cost -$402.60. Moving the stop to breakeven
// once a trade is +0.3 in profit rescues 22 of those 35 and recovers +$219 —
// 54 cents of every dollar lost, from one rule. The old breakeven waited for "1R"
// (the structural stop distance, usually 2-6 points) and therefore almost never
// fired. A trade that has paid you must never be allowed to take it back.
// v1.78 ZEE'S OWN EXIT (2026-08-08). His Feb-11 broker report beside our ledger:
//   ZEE    69 trades  94% WR  avg win +$12.93  avg LOSS  -$1.32  worst  -$1.60
//   GHOST 287 trades  57% WR  avg win  +$5.43  avg LOSS -$12.73  worst -$39.00
// In 69 trades he NEVER took a $10 loss; his four losses that day totalled -$5.30.
// His losing buys at 18:41:50 were HELD 25 MINUTES and closed at -$1.43 — he is
// never stopped out, he waits for the trade to come back and steps off flat.
// Every stop I built manufactures the loss he never takes. So under InpZeeExit:
//   * a RED click is never cut by the ghost or the basket floor
//   * it is held until it returns to within InpFlatPts of breakeven, then closed
//   * winners keep the ratchet; the green sweep still banks the blue ones
//   * only the wide catastrophe parachute remains as a bound
// InpZeeExit=false restores the previous machine in one input.
// v1.77 THE COLOUR-ABORT WAS EATING GOOD TRADES (Zee 2026-08-08, three clicks of one
// setup cut together for -$70.40): the abort was built for the DOOR, where the entry
// candle IS the breakout candle — an intrabar entry whose candle then closes the
// wrong way really is a disproven breakout. With the door retired every entry is a
// CLOSED-CANDLE entry, so the position opens in the candle AFTER the breakout: the
// abort was demanding that the very NEXT candle also close our way, within seconds
// of entry, which flatly contradicts the 2-minute grace period shipped in the same
// version. Receipt: 23:59:24 SELL + 2 conviction clicks -> 00:00:00 all three cut at
// -2.23/-2.09/-2.10pt because the following candle closed green. The abort now
// applies ONLY to door entries (comment "ghost"); closed-candle entries have already
// proven their breakout at emit time and are left to the grace period.
// v1.76 THE TIP TRADES TO ITS TARGET (Zee 2026-08-07, "ok promote it"): the
// selling-climax pattern (no-supply candle WITH a heavy selling background) tested
// 83% then 75% WR at +$31.33 / +$21.76 per trade across two tape lengths, against a
// control of the SAME pattern without the background at 43% / 53%. It is now a full
// diamond: 3 conviction clicks, and uniquely it AIMS at the last structural swing
// instead of trailing. Those positions carry the comment "ghost-t" — the ratchet
// never clips them; they run to the broker TP, or die by the basket floor /
// campaign end / parachute like everyone else.
// v1.75 CONVICTION RECONNECTED (Zee 2026-08-07): with the door retired, the diamond
// multiplier had quietly gone inert — clicks forced to 1, raids lived in the door,
// lots capped: a 4-diamond lamp and a 0-diamond lamp got the identical trade.
// The matcher now counts the laws on the LAWFUL closed-candle setup and sends
// "clicks" in case_signal.json (0-1 diamond -> 1, 2 -> 2, 3+ -> 3). The EA fires
// the extra clicks InpClickSpaceS seconds apart, each one 0.10, each managed by the
// same basket floor and green sweep. Conviction pays again, with the law intact.
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
input bool   InpSynthesis    = true;   // v1.80: BE lock protects + target captures, no ratchet/scratch
input double InpMaxRiskPts   = 1.0;    // v1.82: a click may never cost more than this (Zee's Feb-11 reflex)
input double InpTgtRR        = 1.0;    // fallback target when the signal carries none: this x stop distance
input double InpBEArmPts     = 0.0;    // +profit that locks the stop at breakeven
input bool   InpZeeExit      = true;   // hold red clicks to flat instead of stopping out
input double InpFlatPts      = 0.05;   // "came back": within this of breakeven -> step off
input double InpHardSLPts    = 6.0;    // PARACHUTE broker stop (terminal-death insurance only)
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
int     g_sig_left = 0;                    // conviction clicks still to fire (signal path)
string  g_sig_side = "";
double  g_sig_lots = 0, g_sig_px = 0, g_sig_sl = 0;
long    g_sig_t0 = 0;
double  g_sig_tgt = 0;                     // structural target for tip trades

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
   double tgt = JNum(txt, "target");
   if (tgt == EMPTY_VALUE) tgt = 0;
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
   PrintFormat("[CaseExec] v1.81 loaded — structural stop + structural target only, breakeven lock at +%.2f (0=off) — breakeven lock at +%.2f, target captures, no ratchet, no scratch (tester: +$187 vs +$12.90 for the ratchet)", InpBEArmPts);
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
   double tgt = JNum(txt, "target");
   if (tgt == EMPTY_VALUE) tgt = 0;
   double ck = JNum(txt, "clicks");
   int nclicks = (ck == EMPTY_VALUE || ck < 1) ? 1 : (int)ck;
   g_sig_left = nclicks - 1;                       // the extra conviction clicks
   g_sig_side = side; g_sig_lots = lots; g_sig_sl = ssl; g_sig_tgt = tgt;
   g_sig_px = (side == "BUY") ? ask : bid;
   g_sig_t0 = (long)TimeGMT();
   string tag = (tgt > 0) ? "ghost-t" : "case";
   double tp0 = (tgt > 0) ? tgt : 0;
   if (side == "BUY")       trade.Buy(lots, _Symbol, 0, sl, tp0, tag);
   else if (side == "SELL") trade.Sell(lots, _Symbol, 0, sl, tp0, tag);
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
   // CONVICTION CLICKS (v1.75): the diamonds bought extra 0.10 entries on this
   // lawful setup — fire them a few seconds apart while price is still near the
   // signal price, under the same stack ceiling and send-cooldown.
   if (g_sig_left > 0 && g_sig_side != "") {
      long age = (long)TimeGMT() - g_sig_t0;
      if (age > 90) { g_sig_left = 0; }            // the moment has passed
      else if (age >= InpClickSpaceS
               && (long)TimeGMT() - g_last_send >= InpSendCooldownS) {
         double cbid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double cask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double now_px = (g_sig_side == "BUY") ? cask : cbid;
         bool near = MathAbs(now_px - g_sig_px) <= 0.60;      // not chasing
         if (near && OurLots() + g_sig_lots <= InpMaxStackLots + 1e-9) {
            g_last_send = (long)TimeGMT();
            g_sig_left--;
            double bsl = BrokerSL(g_sig_side == "BUY", now_px, g_sig_sl);
            string ctag = (g_sig_tgt > 0) ? "ghost-t" : "ghost-c";
            double ctp = (g_sig_tgt > 0) ? g_sig_tgt : 0;
            // v1.80: a trade with no target has nothing to run TO, so the ratchet
            // was the only thing that could end it. Give every click a target —
            // the structure's own if we have it, otherwise InpTgtRR x the stop
            // distance, which is what the market itself offered on this setup.
            if (InpSynthesis && ctp <= 0 && bsl > 0) {
               double sld = MathAbs(now_px - bsl);
               if (sld > 0) ctp = (g_sig_side == "BUY") ? now_px + InpTgtRR * sld
                                                       : now_px - InpTgtRR * sld;
            }
            if (g_sig_side == "BUY")  trade.Buy(g_sig_lots, _Symbol, 0, bsl, ctp, ctag);
            else                      trade.Sell(g_sig_lots, _Symbol, 0, bsl, ctp, ctag);
            PrintFormat("[CaseExec] CONVICTION CLICK (%d left) %s %.2f lots @ %.2f",
                        g_sig_left, g_sig_side, g_sig_lots, now_px);
         } else if (!near) {
            g_sig_left = 0;                        // price left the setup - stand down
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
               // v1.77: only DOOR entries ("ghost") can be disproven by their own
               // candle. A closed-candle entry proved its breakout before it was
               // emitted — judging the NEXT candle would just be impatience.
               if (PositionGetString(POSITION_COMMENT) != "ghost") continue;
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
      if (InpZeeExit) cn = 0;            // ZEE EXIT: no collective stop-out either
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
      // BREAKEVEN AT +InpBEArmPts (v1.79): the moment a trade has genuinely paid,
      // its stop moves to entry. Measured on real fills: 63% of our losers had been
      // in profit first. The old rule waited for one R (2-6 pts) and never fired.
      double cursl = PositionGetDouble(POSITION_SL);
      if (prof >= InpBEArmPts) {
         bool at_be = (cursl > 0) && (isbuy ? (cursl >= entry) : (cursl <= entry));
         if (!at_be) {
            double bepx = isbuy ? entry + 0.05 : entry - 0.05;
            if (trade.PositionModify(t, bepx, PositionGetDouble(POSITION_TP)))
               PrintFormat("[CaseExec] BREAKEVEN LOCK at +%.2f — this one can no longer lose", prof);
         }
      }
      // (v1.73: the per-click ghost is GONE — squad members tolerate individual
      // red; the BASKET FLOOR above judges danger collectively, as Zee's hands did.)
      // ── ZEE EXIT (v1.78): a red click is never stopped out. Hold it until it
      // comes back to flat, then step off — that is how his losses stay pennies.
      if (InpSynthesis) {
         // v1.82 THE BOUND: no click may cost more than InpMaxRiskPts. This is not
         // a structural stop — the structure on gold sits 5-20 points away, and Zee
         // never once let a trade travel that far. It is his step-off reflex, made
         // mechanical, because a human cannot be trusted to do it 69 times a day.
         if (InpMaxRiskPts > 0 && prof <= -InpMaxRiskPts) {
            PrintFormat("[CaseExec] BOUND: %.2fpt against — stepping off (Zee's reflex)", prof);
            trade.PositionClose(t); DropPeakOf(t);
            continue;
         }
         // v1.80: nothing closes a live trade between the breakeven lock and the
         // target. The scratch-at-flat rule closed a trade that went on to make
         // +$70.00 in the tester; the ratchet turned two winners into losses.
         // The stop (at entry once it has paid) and the target are the only exits.
         if (prof <= -InpHardSLPts) {
            PrintFormat("[CaseExec] catastrophe parachute at %.2fpt", prof);
            trade.PositionClose(t); DropPeakOf(t); g_raids = InpMaxRaids;
         }
         continue;
      }
      if (InpZeeExit && prof < 0 && pk < InpArmPts) {
         if (prof >= -InpFlatPts) {
            PrintFormat("[CaseExec] ZEE EXIT: came back to flat (%.2fpt) — stepping off", prof);
            trade.PositionClose(t); DropPeakOf(t);
         } else if (prof <= -InpHardSLPts) {
            PrintFormat("[CaseExec] catastrophe parachute at %.2fpt", prof);
            trade.PositionClose(t); DropPeakOf(t);
         }
         continue;                       // no ghost, no floor, no give-back on reds
      }
      // absolute software backstop at the parachute distance (belt and braces)
      if (prof <= -InpHardSLPts) {
         trade.PositionClose(t); DropPeakOf(t);
         g_raids = InpMaxRaids;              // losing raid -> lamp retired
         continue;
      }
      // runaway take-profit ceiling
      if (prof >= InpTpCapPts) { trade.PositionClose(t); DropPeakOf(t); continue; }
      // trailing-reversal: let it run, exit on give-back after arming
      // TARGET TRADES (v1.76): the tip aims at its structural swing — the ratchet
      // does not clip it; it exits on the broker TP, the floor, the campaign end
      // or the parachute.
      if (StringFind(PositionGetString(POSITION_COMMENT), "ghost-t") >= 0) continue;
      double give = MathMax(InpGivePts, InpGiveFrac * pk);   // ratchet trail
      if (pk >= InpArmPts && (pk - prof) >= give) {
         trade.PositionClose(t); DropPeakOf(t); continue;
      }
   }
   if (!HasOurPos()) for (int i = 0; i < 24; i++) { g_tk[i] = 0; g_pk[i] = 0; g_gv[i] = 0; }   // flat -> clean slate
}
//+------------------------------------------------------------------+
