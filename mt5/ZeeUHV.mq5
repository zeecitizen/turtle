//+------------------------------------------------------------------+
//| ZeeUHV.mq5 — HIS rules, not mine. Rebuilt from his own 146 labels. |
//|                                                                  |
//| Zee, 2026-08-10: "i labelled more than a 100 setups for you to    |
//| see which one is UHV which one is not."                          |
//|                                                                  |
//| He had, and I had forgotten. monitor/setup_labels/zee_labels.json |
//| holds 146 setups annotated in his own words, and only 27 of them  |
//| say the machine's drawing was right — about 18%. Every detector   |
//| we ever shipped encoded MY reading of "ultra high volume". This   |
//| one encodes his, rule by rule, with his sentence quoted above     |
//| each check so anyone reading the code can see whose authority it  |
//| carries.                                                          |
//|                                                                  |
//| On 3,159 bars of real archived gold his rules find 26 setups      |
//| where my detector found 193 — far stricter, and better:           |
//|     96% reach +$1.00 · 85% reach +$2.00 · 50% reach +$5.00        |
//| Walked forward bar by bar asking WHICH CAME FIRST (the mistake    |
//| that cost the DohaLevel call this morning):                       |
//|     SL 6 / TP 3 -> 83% (20W/4L), needs 67%, +1.50 pts per trade   |
//|     SL 6 / TP 2 -> 88% (22W/3L), needs 75%, +1.04                 |
//|     SL 4 / TP 3 -> 68% (17W/8L), needs 57%, +0.76                 |
//| The whole neighbourhood is positive, not one lucky cell — and it  |
//| says what he has been saying: WIDE STOP, MODEST TARGET. The       |
//| opposite of the ghost at 1.0, the ratchet at 0.3, the breakeven   |
//| lock at 0.3 and my own bound at 1.0.                              |
//|                                                                  |
//| ZEE'S CALL, twice (2026-08-10): "if 96% reach +$1, then let each   |
//| trade bring in the $1" and then, when I argued for a bigger        |
//| target, "nah i want a highest winrate even if we're earning        |
//| pennis". That is his decision and it stands.                       |
//|                                                                    |
//| What I could do FOR that decision rather than against it: the      |
//| break-even threshold is set by the STOP, not the target.           |
//|     SL 6 / TP 1 -> needs 86%, MT5 measured 83%  -> lost -$26.60    |
//|     SL 4 / TP 1 -> needs 80%, measured 88%      -> +8 of margin    |
//| So the $1 target stays and the stop comes in. Same high win rate,  |
//| a loss that costs $40 instead of $60, and eight points of room to  |
//| be wrong about the win rate — which matters, because 12 trades     |
//| cannot tell 83% from 96% and that gap is the whole result.         |
//|                                                                    |
//| each trade bring in the $1." Measured, and he is right — it is the |
//| safest cell on the board:                                          |
//|     SL 6 / TP 1 -> 96% (25W/1L)  +0.73 pt/trade                     |
//|     SL 6 / TP 2 -> 88% (22W/3L)  +1.04                              |
//|     SL 6 / TP 3 -> 83% (20W/4L)  +1.50                              |
//| A bigger target earns more on paper and loses four times as often. |
//| After six months of red days, an engine he can watch running at    |
//| 96% is worth more than a little extra theoretical expectancy — and |
//| 25W/1L is the shape he actually traded on Feb 11.                   |
//| Note the money: 1 point of gold = $1 of PRICE = $10 at 0.10 lots.  |
//| So 26 trades x $1 is $260/day at 0.10 lots, not $26.               |
//|                                                                    |
//| CAVEAT ON THE FACE OF IT: 26 setups, ~2 days, measured in Python. |
//| Direction only. Only MT5's tester or live fills promote anything. |
//| 25W/1L on one sample could be 22W/4L on the next week.            |
//|                                                                  |
//| magic 88094 = tester only.                                        |
//+------------------------------------------------------------------+
//| WATCHER REMOVED 2026-08-12. It defaulted to false and its guard returned
//| immediately, yet its mere presence changed the tester result: 1,608 trades at
//| 93.28% and +$2,599.10 became 1,665 at 69.43% and -$779.90 on identical data,
//| identical inputs and 97,564 identical bars. Removing it restores the number to
//| the cent. The mechanism is not yet understood, which is exactly why it is out:
//| dead code that moves live results is not dead.
#property copyright "Zee & his ghost"
#property version   "1.45"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input double InpLots        = 0.10;   // InpLots — lot size
input int    InpMagicNumber = 88094;  // InpMagicNumber — 88094 = ZeeUHV, tester only

input group "── His rules (each one quoted from his labels in the code) ──"
input int    InpTrendLook   = 20;   // InpTrendLook — 20 validated
input int    InpPivot       = 2;      // InpPivot — swing pivot strength
input bool   InpRequireTrend = true;  // InpRequireTrend — false lets RANGING tape trade too (the 40% gate)
input int    InpRetraceBack = 20;   // InpRetraceBack — 20 validated
input double InpUhvBodyMin  = 0.5;   // InpUhvBodyMin — 0.5 validated. 0.3 finds more setups and loses money
input int    InpBreakWindow = 12;     // InpBreakWindow — bars after the UHV in which the break must come

input group "── Exit: SL 6 / TP 3 measured on his own setups ──"
// ZEE'S CALL, 2026-08-15. The 20-point stop stopped doing anything the moment the hold
// came down to 5 minutes — it was an unused parameter carrying the whole tail risk.
//
// Measured on the live window (11-13 Aug), real ticks, at hold 5. Stops of 20, 12, 8 and 5
// are IDENTICAL TO THE CENT — no trade's adverse excursion reached even 5 points inside
// five minutes, so the stop never fired at any of them:
//     stop 20 / 12 / 8 / 5   67 trades  88.06%  +85.04     tightening is FREE
//     stop 3                 67 trades  83.58%  +63.94     starts binding, starts costing
//     stop 2                 67 trades  77.61%  +53.68
//
// And it is not only free here — at hold 5 it is BETTER in the two hostile months:
//     March   -443.66 -> -375.44        April   -296.24 -> -232.84
//     May     -154.02 -> -191.86        (the honest cost)
//
// What it actually buys is the tail. Eight tickets share one stop, so a failed setup at
// 0.10 lots costs 8 x 0.10 x stop x 100:
//     stop 20   $1,600   38.8% of the account    2.6 losing setups to ruin
//     stop  5     $400    9.7%                  10.3
// The 14 Aug stale-quote accident took $695 of a possible $1,600. Capped at $400 now.
input double InpStopPts     = 5.0;    // InpStopPts — 5, Zee 2026-08-15. Free at hold 5, and it caps the tail 4x.
input double InpTargetPts   = 1.0;    // InpTargetPts — 1.0 is ZEE'S CALL: 25W/1L, 96%, his own Feb-11 shape
// ZEE'S CALL, 2026-08-15: 5 minutes. He noticed his live trades nearly all finish inside
// three ("since all trades last nearly under 3 minutes .. would 90%+ trades still go into
// profit?") and asked for it to be measured on the LIVE window rather than on backtest
// periods — 11 Aug 01:51 to 14 Aug, the clean 14/14 run, excluding the two stale-quote
// trades of the 14th.
//
// Measured there, real ticks, 163 ms delay:
//     hold  win%     net    avgL    drawdown
//        3  68.66%  +67.60  -1.74     0.5%
//        4  82.09%  +93.44  -1.57     0.5%     best money
//        5  88.06%  +85.04  -4.86     1.0%     <- SHIPPED: keeps the win rate AND the money
//       60  89.06%  +29.84 -14.51     3.6%     the old setting
//
// Nearly 3x the money at a third of the drawdown, for one point of win rate. The mechanism
// is the average loss: -1.57 at four minutes against -14.51 at sixty. A short clock stops a
// failing trade bleeding for another 55 minutes.
//
// NOT a free lunch, recorded so it is not forgotten: across THREE periods the 60-minute
// hold wins overall, because March and May prefer it. What makes 5 more than a 3-day fit is
// that a SECOND, independent August window (10-13 Aug) also preferred short holds. It is a
// property of this regime, and this is the regime being traded. If the tape turns into
// March, revisit this line first.
input int    InpMaxHoldMin  = 3;    // 5 -> 3, Zee 2026-08-18 "ok ship 1.30". Six periods vs the
                                    // v1.29 baseline: +288.68, better in 5 of 6 incl. BOTH hostile
                                    // months, April flips positive (+47.78). Same sweep: h2 starves
                                    // winners (-115), SL2 whipsaws (-187), full ZeeSimple exit -309.
                                    // With last night's h8/12/20 sweep (all fail) the clock is now
                                    // bracketed from both sides: these entries pay by minute 3 or
                                    // not at all — the closest mechanical cousin of his Feb-11 cut.

input group "── Housekeeping ──"
input int    InpMaxOpen     = 1;      // InpMaxOpen — concurrent SETUPS (a stack counts as one)
input int    InpCooldownBar = 3;      // InpCooldownBar — bars between entries
input int    InpMaxGapSec   = 300;    // InpMaxGapSec — never reason across a hole in the data

input group "── STALE-QUOTE GUARD — the 2026-08-14 fault (v1.20) ──"
// WHAT HAPPENED, so nobody ever removes these thinking they are paranoia:
//
// 02:15 on 14 Aug the EA fired BUY on ask 4366.17 and filled at 4360.7. Blueberry's own
// stored ticks for that half hour top out at 4363.25, and the widest spread in 4,420 ticks
// was 0.56 — that price did not exist. It DID exist 18:52-20:30 the PREVIOUS EVENING.
// SymbolInfoDouble had handed back a quote roughly six hours old.
//
// The bars were fresh, so a real setup was found and the server filled correctly. But the
// stop and target were computed from 4366.17, which put the $1 target 6.4 points above the
// actual fill — unreachable inside the hold. Eight tickets aged out: -$695.
//
// A gap guard for BARS has existed since 08-10. Nothing checked the QUOTE.
input double InpMaxQuoteDrift  = 2.0;  // InpMaxQuoteDrift — refuse if the quote disagrees with bar 0 by more than this (0 = off). The fault measured 5.4; a normal fire is ~0.1.
input int    InpMaxQuoteAgeSec = 120;  // InpMaxQuoteAgeSec — refuse if the last quote is older than this (0 = off)

input group "-- Laws of Conviction from Zee's PDF, 2026-08-16 --"
// All default OFF, so the shipped behaviour is unchanged until one earns its place.
// UHV ANATOMY — is this candle actually what we claim it is?
input double InpUhvVolMult   = 0.0; // InpUhvVolMult — 0 = off. UHV volume >= SMA(vol,20) x this. THE "is it genuinely ULTRA" test — we have only ever required it be the loudest of 20, never high in absolute terms.
input double InpUhvRangeATR  = 0.0; // InpUhvRangeATR — 0 = off. UHV range >= ATR(14) x this. Effort vs result measured against VOLATILITY (the earlier test used volume).
input double InpUhvClosePos  = 0.0; // InpUhvClosePos — 0 = off. 0.4 = the UHV must close above the bottom 40% of its own range (absorption, not collapse).
// CONTEXT
input double InpPreCompress  = 0.0; // InpPreCompress — 0 = off. The 5 bars before the UHV must average LESS than ATR(14) x this. Breakouts out of compression.
input double InpMaxPullback  = 0.0; // InpMaxPullback — 0 = off. 0.618 = the retracement may not exceed this fraction of the impulse that preceded it.
// EXECUTION
input double InpMaxSpreadPts = 0.0;

input group "-- Wyckoff / VSA composite (Zee's 2nd PDF, 2026-08-16) --"
// L1 AS A DIAMOND, at Zee's insistence and he is right. As a GATE it discards 95% of trades
// (67 -> 4) on 13 observations, and 13 wins in a row is a 19.1% coincidence at our baseline
// 88.06% win rate. As a DIAMOND it blocks nothing and only sizes up when it fires, so a
// false signal costs almost nothing while a true one pays. Correct use of a small sample.
// ── LAW 9 CANDIDATE (2026-08-17, default OFF — shipped behaviour unchanged) ──────
// Zee, forensic on the 11:08 PKT loser (−$43.20/ticket): "the UHV marked is not a UHV
// because: 1. its not the highest red volume  2. none of the red candles breaks the
// last green's low (a valid retracement did not start)". Verified on broker bars:
// the origin code accepted 11:04 because its body broke the low of 11:03 — a ONE-BAR
// bounce INSIDE the pullback. Against the leg's real last green (11:01, the impulse)
// nothing broke. Label #e014 says that means no retracement ever started.
// With this ON the origin's reference green (BUY) / red (SELL) must be an IMPULSE bar
// — one that expanded in the leg's direction — never pullback chop. Traced by hand on
// the 11:08 window this widens the scope, promotes 11:02 (vol 237) to UHV candidate,
// and the local-peak law then rejects it (11:01 louder at 266): NO TRADE, exactly his
// reading, two laws deep.
input bool   InpImpulseOrigin = true;  // Law 9 LIVE 2026-08-17 (Zee: "make it LIVE: Law 9 that
                                       // passes the promotion rule"). Receipts, six periods, real
                                       // ticks: -1,615.18 -> -1,177.80 (+437.38), better in kind
                                       // (LIVE +14.54, Jun +308.52 -> POSITIVE, Jul +82.70) AND
                                       // hostile (Mar +202.42), at the cost of Apr -66.12 and
                                       // May -104.68. ~10% fewer tickets.
// ── RANK-N (2026-08-18, default 1 = shipped behaviour byte-identical) ────────────
// The pipeline census answered Zee's "why is our trade count so low": of 4,137 August
// bars, 1,439 retracements died because the SINGLE loudest candidate failed a law
// (887 body<min, 552 neighbour-louder) and no second candidate was ever examined.
// His own rank rule from the labels — "every UHV in the retracement, not only the
// loudest" — walks candidates by volume rank and takes the FIRST that passes every
// law AND is actually broken by bar 1 (the v13 FindUhvRanked semantics, +46%% Aug in
// the 08-13 receipts). Ships only with fresh six-period receipts, as always.
// ── THE PROBE (2026-08-18 night, default OFF — Zee: "ZeeSimple opens a 0.01 lot,
// then if its going successful, we mark the direction as a conviction (due to
// ZeeSimple having probed the region), then when we open our trade, it results in a
// burst of (pre-tested) environment.") Single-EA testable form: at every signal a
// lone 0.01 scout enters first, naked (no SL/TP — the deadline is its exit, and the
// 3-min hold sweep is the backstop). At the deadline: moved >= InpProbeMinPts our
// way -> close the scout, open the FULL basket into pre-tested ground; otherwise
// the scout retreats and the basket never risks itself.
// ── SHOP-B TRANSPLANT (2026-08-19, defaults OFF — Zee: "explore all possible paths
// of combining the two shops"). Night-2 isolated Shop B's stabilizer: a trade wants
// to be JUDGED EXACTLY WHEN A CANDLE ENDS, and ~3 minutes is the right life. These
// inputs transplant that discipline onto the M1 chart, keeping M1's entry frequency:
//   InpBoundaryExit 1 = close at the FIRST M3 boundary after entry (life 0-3 min)
//   InpBoundaryExit 2 = close at the first boundary giving >= 3 min of life (3-6 min)
//   InpEntryBoundary  = only fire when the just-closed M1 bar completes an M3 candle
input int    InpBoundaryExit  = 0;   // 0=off · 1=next M3 boundary · 2=first boundary past 3 min
input bool   InpEntryBoundary = false; // fire only on M3-boundary minutes
// HtfMode 1 turns the M3 consultation from a VETO into SIZING (the Law-10c pattern):
// a trade against the M3 drift is not refused — it opens at InpHtfSizeFrac of its
// tickets. Laws multiply, they don't gate. (Zee 2026-08-19: "mix n match the two")
input int    InpHtfMode      = 0;    // 0 = veto side against HTF · 1 = downsize instead
input double InpHtfSizeFrac  = 0.25; // ticket fraction when trading against the HTF drift
input bool   InpLaw11        = false; // LAW 11: origin integrity — the retracement may not contain new leg extremes
// ── LAW 12 (2026-08-18, Zee: "instead of 20 bars back it should be 'last highest
// peak' because otherwise that would be another retracement like 20 bars ago") ──
// 1 = the origin search may not walk past the leg's birth peak (SELL) / trough (BUY)
// 2 = additionally the origin candle must have LEFT the peak's range (its high below
//     the peak bar's low) — catches ghosts sitting AT the peak, like 14:37 today
input int    InpLaw12        = 0;    // 0=off · 1=peak-bounded search · 2=bound + below-the-peak
// ── THE SELF-AWARE SWITCH (2026-08-19, Zee: "ok test it" — the season calendar).
// The machine reads its OWN pulse: the net of its last InpRegimeLook closed tickets.
// Red pulse -> every basket opens at InpRegimeFrac of its tickets (scout size — it
// NEVER stops, because a stopped machine cannot feel the season change). Green
// pulse -> full stack. Harvest-and-return, mechanized. Default OFF.
input int    InpRegimeLook   = 20;   // LIVE 2026-08-20 (Zee: "make the 1.45 live go ahead").
                                     // The pulse: net of the last 20 closed tickets. Red ->
                                     // quarter-size scouts; green -> full stack. Receipts:
                                     // six-period total -228.88 -> +276.22 — the FIRST
                                     // net-positive M1 configuration in project history.
                                     // Better/tied in 5 of 6 periods; dial is a hill
                                     // (p10 +265). Mar -247->-87 · May -384->-91 · Apr green.
input double InpRegimeFrac   = 0.25; // basket fraction while the pulse is red

// Zee 2026-08-19: "feb11 exits (smallest losses) are possible, its just that we're
// not trying that hard.. look deeper. i have full confidence in you."
input group "── FEB-11 EXIT LAB (overnight 2026-08-19, all default OFF) ──"
// THE REVISIT INSIGHT: his 18:41 losing cluster was held 25 MINUTES and scratched at
// -€1.43 — the hand did not cut fast, it WAITED FOR THE RETOUCH of entry. Gold M1
// oscillates; adverse moves usually revisit the entry before becoming disasters.
input double InpScratchArm  = 0.0;  // adverse pts that ARM the scratch (0 = lab off)
input double InpScratchOfs  = 0.0;  // scratch level vs entry (0 = breakeven, -0.1 = pay a dime)
input int    InpScratchHold = 25;   // minutes an ARMED trade may wait for its retouch
input bool   InpRevExit     = false; // his other described exit: first opposing candle while red
// THE NIGHT'S SYNTHESIS: the lab proved the retouch shrinks losses to pennies but
// also scratches the dip-first winners. His hand scratched ONLY true deaths — and
// the pulse knows the season of deaths. Scratch ONLY while the pulse is red.
input bool   InpScratchRedOnly = false; // scratch mode active only when RollingNet(20) < 0
input int    InpProbeSec     = 0;    // probe duration seconds (0 = off; must be < hold*60)
input double InpProbeMinPts  = 0.10; // conviction threshold the probe must show
input double InpProbeLots    = 0.01; // scout size
input int    InpUhvRank      = 6;    // LIVE 2026-08-18 (Zee: "ship rank 6"). The dial swept
                                     // {2,3,6,10}: every position positive, 6 == 10 in five of
                                     // six periods — saturation, the plateau of a real law.
                                     // +121.86/six periods (reproduced to the cent), passes
                                     // promotion. Every retracement now auditions up to six
                                     // candidates; the quality laws stay exactly as strict.
// ── ZEE'S FUNNEL (2026-08-18, default true = shipped behaviour) ──────────────────
// Zee, correcting the rank-6 reading: "i meant fire on a UHV in EVERY retracement,
// not just some retracements... out of 100 retracements all 100 should have a UHV."
// In his model the loudest counter-candle of a retracement simply IS its UHV — the
// body and local-peak rules (from the 146 labels) should not be able to VETO it.
// The census counted those vetoes at 1,439 per 4,137 August bars. With this false,
// the two vetoes are off and only the breakout decides. His theory, measurable.
input bool   InpLocalPeak    = true; // false = body & neighbour rules cannot veto the UHV
input double InpUhvVolDia   = 2.0;  // InpUhvVolDia — LAW 6, ACTIVE. +1 diamond when UHV volume >= SMA(vol,20) x this.
input int    InpClimaxDia   = 60;   // InpClimaxDia — LAW 7, ACTIVE. +1 diamond when the UHV is the WIDEST bar of the last N.
//
// THE SQUAT BAR — and note it CONTRADICTS the effort-vs-result law tested earlier. That one
// wanted a WIDE spread on high volume; Wyckoff's squat wants a NARROW spread on high volume,
// reading it as buyers and sellers matched order-for-order. Both cannot be right, so both
// get measured.
input double InpSquatMax    = 0.0;  // InpSquatMax — 0 = off. UHV range must be UNDER ATR(14) x this (narrow = squat).
//
// EFFORT-VS-RESULT FAILURE: the bar right after the UHV fails to extend past it. Heavy
// selling with no follow-through.
input bool   InpNextFails   = false; // InpNextFails — the bar after the UHV must NOT break the UHV's low (buy) / high (sell)
//
// SELLING CLIMAX: the UHV is not merely loud, it is the WIDEST bar in recent memory.
input int    InpClimaxLook  = 0;    // InpClimaxLook — 0 = off. UHV must have the widest range of the last N bars.
//
// PUSH THROUGH SUPPLY — this DIRECTLY CONTRADICTS Zee's own rule. His breakout must be
// QUIETER than the UHV; PTS says it should be a HIGH-volume green bar cutting through. His
// rule was measured today and tightening it only removed winners, so this tests the opposite
// direction of the same dial.
input double InpBrkVolMin   = 0.0;  // InpBrkVolMin — 0 = off. Breakout volume must be ABOVE this fraction of the UHV's. // InpMaxSpreadPts — 0 = off. Refuse entry above this spread. Measured mean 0.2014, peak 0.56 — and 0.56 is 56% of a 1-point target.
// ── LAW 10 CANDIDATES (2026-08-17, both default OFF — measurement first) ─────────
// Zee, forensic on the 12:21 basket: "the displacement was shallow — a 15-cent
// close-through on 90% effort. That's a testable law." The breakout closed 4397.04
// against a 4397.19 trigger (0.15 pts) carrying 215/240 = 90% of the UHV's volume:
// huge effort, no result — absorption at support, and the reversal that followed
// stopped all twelve tickets. Two independent reads of the same defect:
input double InpBrkMarginPts = 0.0; // Law 10a: breakout must CLOSE >= this many pts beyond the trigger (0 = off)
input double InpBrkVolMaxFrac = 0.0; // Law 10b: breakout vol <= this frac of UHV vol (0 = off; entry already requires < 1.0)
// ── LAW 10c — the NON-BLOCKING form (Zee 2026-08-17: "can we maybe find a
// non-blocking version of this LAW... i don't wanna cut down trades.. 6 per day is
// already so less"). House doctrine: laws never gate; they multiply. The gate form
// (volmax 0.85) earned +$786 over six periods but halved the trade count and blocked
// three of today's winners. This form fires EVERY trade the current EA fires — but a
// breakout in the loud band (vol > InpLoudVolFrac x UHV, the band where the $500
// baskets live) opens FEWER TICKETS instead of none. Tempo untouched, tail halved.
input double InpLoudVolFrac  = 0.85; // Law 10c: loud band starts at this fraction of UHV volume
input double InpLoudSizeFrac = 0.25; // Law 10c LIVE 2026-08-17 (Zee: "go"). Quarter tickets in the
                                     // loud band: recovers 68% of the gate's +786 with ZERO trades
                                     // cut (+538.38 over six periods, better in 5 of 6, passes
                                     // promotion). A 12:21-style basket: 6 tickets -> 2.

// Higher-timeframe alignment. Measured as a GATE across 8 periods: drawdown lower or
// equal in 8/8 and 18% better per trade. As a DIAMOND it was worse than shipped, so
// its value is removing bad trades rather than sizing good ones.
input int    InpHtfMinutes = 0;     // InpHtfMinutes — 0 = off · 15 = M15 · 60 = H1 (GATE)
input int    InpHtfLook    = 8;     // InpHtfLook — bars of that timeframe to measure over

input bool   InpVerbose     = false;  // InpVerbose — OFF for optimisation (a sweep with logging is 100x slower)
input int    InpMinTrades   = 15;

input group "── Diamonds: conviction buys SIZE (Zee 2026-08-10) ──"
input bool   InpUseDiamonds = true;   // InpUseDiamonds — size by conviction instead of a flat lot
input double InpMaxRisk     = 0.0;    // InpMaxRisk — 0 = off. Cap TOTAL lots across the stack.
input bool   InpStackLots   = true;   // InpStackLots — each diamond opens ANOTHER position, each one bigger
input double InpStackStep   = 0.0;   // InpStackStep — 0.0 = every diamond ticket stays at InpLots (Zee's call)
input int    InpStackMult   = 2;      // InpStackMult — multiplies the whole stack. 2 => 8 tickets at 3 diamonds (Zee 2026-08-13)

datetime g_last_bar = 0;
datetime g_last_fire = 0;

//+------------------------------------------------------------------+
//| The tester overwrites tick_volume with its synthesised tick count |
//| (4/bar) and preserves real_volume. Measured 2026-08-10 with       |
//| TapeProbe: iVolume returned 4 4 4 4 4 while iRealVolume returned  |
//| 572 454 270 174. Every volume rule we owned had been blind.       |
//+------------------------------------------------------------------+
//--- plain ATR(14): the mean true range of bars k..k+13
double AtrAt(int k) {
   double sum = 0;
   for (int i = k; i < k + 14; i++) {
      double h = bHigh(i), l = bLow(i), pc = bClose(i + 1);
      double tr = MathMax(h - l, MathMax(MathAbs(h - pc), MathAbs(l - pc)));
      sum += tr;
   }
   return sum / 14.0;
}

//--- mean volume of the 20 bars BEFORE k (k itself excluded, or it would dilute itself)
double AvgVolBefore(int k) {
   double sum = 0; int n = 0;
   for (int i = k + 1; i <= k + 20; i++) { sum += (double)BarVolume(i); n++; }
   return (n > 0) ? sum / n : 0.0;
}

long BarVolume(int k) {
   long rv = iRealVolume(_Symbol, PERIOD_CURRENT, k);
   if (rv > 0) return rv;
   return iVolume(_Symbol, PERIOD_CURRENT, k);
}

double bOpen(int k) { return iOpen (_Symbol, PERIOD_CURRENT, k); }
double bHigh(int k) { return iHigh (_Symbol, PERIOD_CURRENT, k); }
double bLow(int k) { return iLow  (_Symbol, PERIOD_CURRENT, k); }
double bClose(int k) { return iClose(_Symbol, PERIOD_CURRENT, k); }
bool IsGreen(int k) { return bClose(k) > bOpen(k); }
bool IsRed(int k) { return bClose(k) < bOpen(k); }
double BodyHi(int k) { return MathMax(bOpen(k), bClose(k)); }
double BodyLo(int k) { return MathMin(bOpen(k), bClose(k)); }

//+------------------------------------------------------------------+
//| 0. REGIME                                                         |
//|   "we cannot sell in an uptrend, we only buy in an uptrend" (e027)|
//|   "our setup only works if the market is not in a ranging         |
//|    condition" (e012)                                              |
//|   He judges trend by STRUCTURE — every complaint is phrased as    |
//|   'price made a lower low' or 'formed HH' — so this reads swing   |
//|   pivots, and returns 0 when they disagree.                       |
//+------------------------------------------------------------------+
int TrendNow() {
   double highs[]; double lows[];
   ArrayResize(highs, 0); ArrayResize(lows, 0);
   for (int k = InpTrendLook; k >= InpPivot + 1; k--) {
      bool ph = true, pl = true;
      for (int d = 1; d <= InpPivot; d++) {
         if (bHigh(k) < bHigh(k - d) || bHigh(k) < bHigh(k + d)) ph = false;
         if (bLow(k) > bLow(k - d) || bLow(k) > bLow(k + d)) pl = false;
      }
      if (ph) { int n = ArraySize(highs); ArrayResize(highs, n + 1); highs[n] = bHigh(k); }
      if (pl) { int n = ArraySize(lows);  ArrayResize(lows,  n + 1); lows[n]  = bLow(k); }
   }
   int nh = ArraySize(highs), nl = ArraySize(lows);
   if (nh < 2 || nl < 2) return 0;
   if (highs[nh-1] > highs[nh-2] && lows[nl-1] > lows[nl-2]) return +1;
   if (highs[nh-1] < highs[nh-2] && lows[nl-1] < lows[nl-2]) return -1;
   return 0;
}

//+------------------------------------------------------------------+
//| 1. THE RETRACEMENT AND WHERE IT STARTS                            |
//|   "In uptrend we take a buy -> in uptrend we find a retracement   |
//|    OF RED COLORED CANDLES" (#8)                                   |
//|   "the origin candle was a valid retracement itself as it broke   |
//|    the low of previous green" (#e025)                             |
//|   "its not a valid retracement as the last green's low wasn't     |
//|    broken by the origin, so no retracement started" (#e014)       |
//|   "the body of green candle doesnot break above the last red"(#c4)|
//|                                                                  |
//|   The BODY requirement is what every earlier detector missed: he  |
//|   rejects a retracement that only pokes past with a wick.         |
//+------------------------------------------------------------------+
int RetracementOrigin(int side) {
   bool wantRed = (side > 0);
   // LAW 12: the current swing begins at its extreme — origins beyond it are ghosts
   int kmax = InpRetraceBack, peakbar = -1;
   if (InpLaw12 > 0) {
      double ext = 0;
      for (int b = 1; b <= InpRetraceBack + 8; b++) {
         double e = wantRed ? -bLow(b) : bHigh(b);     // BUY: leg births at a trough
         if (peakbar < 0 || e > ext) { ext = e; peakbar = b; }
      }
      if (peakbar > 0 && peakbar - 1 < kmax) kmax = peakbar - 1;
   }
   for (int k = 1; k <= kmax; k++) {
      if (wantRed  && !IsRed(k))   continue;
      if (!wantRed && !IsGreen(k)) continue;
      int prev = -1;
      for (int j = k + 1; j <= k + 8; j++) {
         if (wantRed ? IsGreen(j) : IsRed(j)) {
            // Law 9 (see input): the reference bar must be an IMPULSE bar of the leg —
            // a green that made a new high (BUY) / a red that made a new low (SELL).
            // A bounce inside the pullback is not a reference; keep walking.
            if (InpImpulseOrigin) {
               if (wantRed  && bHigh(j) <= bHigh(j + 1)) continue;
               if (!wantRed && bLow(j)  >= bLow(j + 1))  continue;
            }
            prev = j; break;
         }
      }
      if (prev < 0) continue;
      bool broke = wantRed ? (BodyLo(k) < bLow(prev)) : (BodyHi(k) > bHigh(prev));
      if (!broke) continue;
      // ── LAW 11 — ORIGIN INTEGRITY (2026-08-18, Zee on the 14:46 loser: "a UHV
      // that's not in a valid retracement (the greens did not break the prior red)
      // has cost us money"). The pipeline had anchored that trade's origin at 14:37 —
      // a green from the PREVIOUS up-swing — and price then fell THROUGH it for six
      // minutes. The tell: a true retracement cannot contain NEW EXTREMES of the leg
      // it claims to retrace. So: between the origin and the breakout, no bar may
      // exceed the origin's own extreme (bar 1, the breakout itself, is exempt — its
      // job is to break). A violated origin is a GHOST from another swing: skip it
      // and keep scanning. Default OFF until the receipts speak.
      if (InpLaw11) {
         bool ghost = false;
         for (int g = 2; g < k; g++) {
            if (wantRed  && bHigh(g) > bHigh(k)) { ghost = true; break; }
            if (!wantRed && bLow(g)  < bLow(k))  { ghost = true; break; }
         }
         if (ghost) continue;
      }
      if (InpLaw12 == 2 && peakbar > 0) {
         // the origin must have LEFT the peak's range — a green at the peak's own
         // shoulder is the prior swing still speaking, not a retracement of this leg
         if (wantRed  && bLow(k)  <= bHigh(peakbar)) continue;
         if (!wantRed && bHigh(k) >= bLow(peakbar))  continue;
      }
      return k;
   }
   return -1;
}

//+------------------------------------------------------------------+
//| 2. THE UHV                                                        |
//|   "a correct UHV should have been the largest volume at 5:30" (#1)|
//|   "Y has the lowest volume among its neighbors, its not a valid   |
//|    uhv because its not having highest volume" (#5)                |
//|   "for a buy setup the uhv should be a red candle" (#11)          |
//|   "uhv candle for sell case must be a green" (#24)                |
//|   "Y is not a UHV as its not in a valid retracement" (#6)         |
//|   "UHV should also be a strong candle, so that when we mitigate   |
//|    it we are mitigating strong sellers" (#loser_001)              |
//|                                                                  |
//|   Scope is his, not ours: the search runs INSIDE the retracement  |
//|   only, so a louder candle outside it can never be chosen. That   |
//|   single constraint answers most of his complaints.               |
//+------------------------------------------------------------------+
bool UhvLawful(int k, int side) {
   bool wantRed = (side > 0);
   long v = BarVolume(k);
   double rng = bHigh(k) - bLow(k);
   if (rng <= 0) { g_ureason = 2; return false; }
   if (InpLocalPeak && MathAbs(bClose(k) - bOpen(k)) / rng < InpUhvBodyMin) { g_ureason = 2; return false; }
   if (InpSquatMax > 0) {
      double atr = AtrAt(k);
      if (atr <= 0 || rng > atr * InpSquatMax) { g_ureason = 9; return false; }
   }
   if (InpClimaxLook > 0) {
      for (int i = k + 1; i <= k + InpClimaxLook; i++)
         if ((bHigh(i) - bLow(i)) > rng) { g_ureason = 9; return false; }
   }
   if (InpNextFails && k > 1) {
      if (wantRed) { if (bLow(k - 1) < bLow(k)) { g_ureason = 9; return false; } }
      else         { if (bHigh(k - 1) > bHigh(k)) { g_ureason = 9; return false; } }
   }
   if (InpUhvVolMult > 0) {
      double av = AvgVolBefore(k);
      if (av <= 0 || (double)v < av * InpUhvVolMult) { g_ureason = 9; return false; }
   }
   if (InpUhvRangeATR > 0) {
      double atr = AtrAt(k);
      if (atr <= 0 || rng < atr * InpUhvRangeATR) { g_ureason = 9; return false; }
   }
   if (InpUhvClosePos > 0) {
      double pos = (bClose(k) - bLow(k)) / MathMax(rng, 1e-9);
      double want = wantRed ? pos : (1.0 - pos);
      if (want < InpUhvClosePos) { g_ureason = 9; return false; }
   }
   if (InpPreCompress > 0) {
      double atr = AtrAt(k);
      double pre = 0;
      for (int i = k + 1; i <= k + 5; i++) pre += (bHigh(i) - bLow(i));
      pre /= 5.0;
      if (atr <= 0 || pre > atr * InpPreCompress) { g_ureason = 9; return false; }
   }
   if (InpLocalPeak && BarVolume(k + 1) > v) { g_ureason = 7; return false; }   // louder neighbours
   if (InpLocalPeak && k > 1 && BarVolume(k - 1) > v) { g_ureason = 7; return false; }
   g_ureason = 0;
   return true;
}

// Walk candidates by DESCENDING volume (oldest wins ties, matching the old argmax),
// up to InpUhvRank auditions: first candidate that is LAWFUL and BROKEN wins.
// g_hadlawful tells the census whether death was a UHV law or the breakout stage.
bool g_hadlawful = false;
int FindUhvBroken(int origin, int side) {
   bool wantRed = (side > 0);
   int   idx[64]; long vol[64]; bool used[64]; int n = 0;
   for (int k = origin; k >= 1 && n < 64; k--) {
      if (wantRed ? IsRed(k) : IsGreen(k)) { idx[n] = k; vol[n] = BarVolume(k); used[n] = false; n++; }
   }
   g_hadlawful = false;
   if (n == 0) { g_ureason = 1; return -1; }
   int auditions = MathMax(1, InpUhvRank);
   for (int r = 0; r < auditions; r++) {
      int pick = -1; long pv = -1;
      for (int j = 0; j < n; j++)
         if (!used[j] && vol[j] > pv) { pv = vol[j]; pick = j; }
      if (pick < 0) break;
      used[pick] = true;
      int c = idx[pick];
      if (!UhvLawful(c, side)) continue;
      g_hadlawful = true;
      if (BreakoutIsBar1(c, side)) { g_ureason = 0; return c; }
   }
   return -1;
}


//+------------------------------------------------------------------+
//| 3. THE BREAKOUT                                                   |
//|   "for a buy setup the breakout should be with a green colored    |
//|    candle" (#8) · "breakout candle in sell case must be red"(#24) |
//|   "the R cannot be considered as breakout candle since its body   |
//|    doesnot break/cross below the Y's lowest point (wick's end)"   |
//|                                                              (#33)|
//|   "14:50 would be a valid breakout candle if its volume were      |
//|    lower than the Y which it is not" (#15)                        |
//|   "we mark only 1 Breakout" (#13) · "B cannot be same candle as   |
//|    Y" (#17)                                                       |
//+------------------------------------------------------------------+
bool BreakoutIsBar1(int uhv, int side) {
   g_breason = 1;                                    // default: no crossing yet
   if (uhv <= 1) return false;                       // B cannot be Y
   bool wantGreen = (side > 0);
   // the FIRST true crossing must be bar 1 — if an earlier bar already crossed,
   // this one is late and he would not mark it
   for (int k = uhv - 1; k >= 1; k--) {
      if (wantGreen  && !IsGreen(k)) continue;
      if (!wantGreen && !IsRed(k))   continue;
      bool crossed = wantGreen ? (BodyHi(k) > bHigh(uhv)) : (BodyLo(k) < bLow(uhv));
      if (!crossed) continue;
      if (BarVolume(k) >= BarVolume(uhv)) { g_breason = 2; return false; }   // must be quieter
      // PUSH THROUGH SUPPLY tests the OTHER direction: a breakout that is too quiet may be
      // no demand rather than absorption cleared.
      if (InpBrkVolMin > 0 && (double)BarVolume(k) < (double)BarVolume(uhv) * InpBrkVolMin)
         { g_breason = 2; return false; }
      // Law 10a — the close must DISPLACE, not graze. 15 cents is a rounding error,
      // not a broken level (the 12:21 basket's whole story).
      if (InpBrkMarginPts > 0) {
         bool deep = wantGreen ? (bClose(k) > bHigh(uhv) + InpBrkMarginPts)
                               : (bClose(k) < bLow(uhv)  - InpBrkMarginPts);
         if (!deep) return false;
      }
      // Law 10b — near-UHV effort with no result is absorption, not a breakout.
      if (InpBrkVolMaxFrac > 0 &&
          (double)BarVolume(k) > (double)BarVolume(uhv) * InpBrkVolMaxFrac)
         return false;
      g_breason = (k == 1) ? 0 : 3;
      return (k == 1);
   }
   return false;
}

bool WindowContinuous(int bars) {
   if (InpMaxGapSec <= 0) return true;
   int step = PeriodSeconds();
   for (int k = 1; k < bars; k++) {
      datetime a = iTime(_Symbol, PERIOD_CURRENT, k);
      datetime b = iTime(_Symbol, PERIOD_CURRENT, k + 1);
      if (a <= 0 || b <= 0) return false;
      if ((int)(a - b) > step + InpMaxGapSec) return false;
   }
   return true;
}

int OpenCount() {
   // counts TICKETS. The stack is built in one pass inside TryFire, so InpMaxOpen only
   // gates NEW setups afterwards — which is what we want: one setup at a time, however
   // many tickets that setup happens to be worth.
   int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) n++;
   }
   return n;
}

//+------------------------------------------------------------------+
//| THE LAWS OF CONVICTION — diamonds buy CLICKS, they never gate.     |
//|                                                                    |
//| Zee 2026-08-10: "have you tested with diamonds? because multiple    |
//| trades can bring us multiple profits aggregating to nice profits."  |
//| He is right that it was never tested: every ZeeUHV run so far fired |
//| a flat 0.10 regardless of how good the setup was, which throws away |
//| the whole point of the conviction system — that the BEST setups     |
//| should carry the MOST size.                                        |
//|                                                                    |
//| Mirrors diamonds_for() in monitor/oanda_live_matcher.py, which is   |
//| what the live machine already uses:                                 |
//|   Law 1  the sweep — price took liquidity before the setup          |
//|   Law 3  the EMA-5 close — the breakout closed decisively past it   |
//|   Law 5  the wick and the volume — clean body, quieter than the UHV |
//| and clicks_for(): 0-1 diamond -> 1 click, 2 -> 2, 3+ -> 3.          |
//+------------------------------------------------------------------+
double Ema5(int shift) {
   double k = 2.0 / 6.0, e = bClose(shift + 30);
   for (int i = shift + 29; i >= shift; i--) e = bClose(i) * k + e * (1.0 - k);
   return e;
}

// WHICH laws fired, as a bitmask, so D3 can be decomposed. Zee, 2026-08-17: "look at why D3
// specifically underperforms — it's the biggest bucket by far and something in it is
// dragging?" With five laws, D3 is ANY THREE OF FIVE — ten different setups wearing one
// label. The count alone can never answer his question; the mask can.
//   bit 0 = Law 6 ultra   bit 1 = Law 7 climax   bit 2 = Law 1 sweep
//   bit 3 = Law 3 ema     bit 4 = Law 5 wick+vol
int g_lawmask = 0;
bool g_htf_against = false;

int DiamondsFor(int origin, int uhv, int side) {
   int d = 0;
   g_lawmask = 0;
   // ── LAW 6 — the UHV is genuinely ULTRA in ABSOLUTE terms, not merely loudest of 20.
   // Zee, 2026-08-16, arguing against my dismissal of it: "if its so good that it has a
   // 100% winrate then why not?" He was right. As a GATE it discards 95% of trades on 13
   // observations — and 13 wins in a row is a 19.1% coincidence at our 88% baseline. As a
   // DIAMOND it blocks nothing and only sizes up when it fires. Measured: better in all
   // three periods (+1.27->+1.28, -1.65->-1.63, -0.23->-0.22).
   if (InpUhvVolDia > 0) {
      double av = AvgVolBefore(uhv);
      if (av > 0 && (double)BarVolume(uhv) >= av * InpUhvVolDia) { d++; g_lawmask |= 1; }
   }
   // ── LAW 7 — SELLING CLIMAX: the UHV is not merely loud, it is the WIDEST bar in recent
   // memory. Better in all three periods, but on only 15 trades — which is exactly why it
   // is a diamond and not a gate.
   if (InpClimaxDia > 0) {
      double r7 = bHigh(uhv) - bLow(uhv);
      bool widest = true;
      for (int i = uhv + 1; i <= uhv + InpClimaxDia; i++)
         if ((bHigh(i) - bLow(i)) > r7) { widest = false; break; }
      if (widest) { d++; g_lawmask |= 2; }
   }
   // Law 1 — the sweep: did price poke beyond the prior extreme on the way in?
   double hi = bHigh(uhv), lo = bLow(uhv);
   for (int k = uhv + 1; k <= uhv + 20; k++) {
      if (side > 0 && bLow(k) < lo) { d++; g_lawmask |= 4; break; }
      if (side < 0 && bHigh(k) > hi) { d++; g_lawmask |= 4; break; }
   }
   // Law 3 — the EMA-5 close: the breakout candle closed decisively past the mean
   double e5 = Ema5(1);
   if (side > 0 && IsGreen(1) && bClose(1) > e5 + 0.10) { d++; g_lawmask |= 8; }
   if (side < 0 && IsRed(1)   && bClose(1) < e5 - 0.10) { d++; g_lawmask |= 8; }
   // Law 5 — the wick and the volume
   double rng = MathMax(bHigh(1) - bLow(1), 1e-9);
   double wick = (side > 0) ? (bHigh(1) - MathMax(bOpen(1), bClose(1))) / rng
                            : (MathMin(bOpen(1), bClose(1)) - bLow(1)) / rng;
   if (wick <= 0.25 && BarVolume(1) < BarVolume(uhv)) { d++; g_lawmask |= 16; }
   // ── LAW 8 CANDIDATE — TAG ONLY, bit 32, NOT a diamond (2026-08-17) ─────────────
   // Zee, reading the forensic of the 12:21 PKT loser: "all the green candle's
   // highs/lows inside this retracement do not break the last independent bar's
   // high.. meaning this is an invalid retracement." Structural reading, confirmed
   // by him: a RETRACEMENT is only real if it displaced past the last bar of the
   // leg that expanded in the retracement's direction. On that loser the down-leg's
   // last upward-independent bar (12:11) had high 4401.40 and the whole retracement
   // topped at 4399.26 — three green candles of effort, zero displacement: chop.
   //
   // Mechanics (SELL; BUY mirrored):
   //   anchor  = the leg extreme — lowest low among bars [origin .. origin+RetraceBack]
   //   ref     = walking back from the anchor, the first bar whose high exceeded the
   //             bar before it (the leg's last upward-independent bar)
   //   valid   = some retracement bar [1 .. anchor-1] broke above ref's high
   // No ref found in 20 bars, or nothing broke it -> the tag stays OFF.
   //
   // It only writes the comment (zee_sell_D2_m52 style) so six periods of tester
   // receipts can judge whether it predicts BEFORE it is allowed to size anything.
   {
      int a8 = -1;
      double ext8 = 0;
      for (int k = origin; k <= origin + InpRetraceBack && k < iBars(_Symbol, PERIOD_CURRENT) - 25; k++) {
         double e = (side < 0) ? bLow(k) : bHigh(k);
         if (a8 < 0 || (side < 0 && e < ext8) || (side > 0 && e > ext8)) { a8 = k; ext8 = e; }
      }
      if (a8 > 0) {
         int ref8 = -1;
         for (int k = a8 + 1; k <= a8 + 20; k++) {
            if (side < 0 && bHigh(k) > bHigh(k + 1)) { ref8 = k; break; }
            if (side > 0 && bLow(k)  < bLow(k + 1))  { ref8 = k; break; }
         }
         if (ref8 > 0) {
            for (int k = 1; k < a8; k++) {
               if (side < 0 && bHigh(k) > bHigh(ref8)) { g_lawmask |= 32; break; }
               if (side > 0 && bLow(k)  < bLow(ref8))  { g_lawmask |= 32; break; }
            }
         }
      }
   }

   // ── TAG bit 64 — DEFENDED LEVEL (Zee 2026-08-18, on the 14:46 loser: "price
   // tapped this point twice before... maybe if we check for such strong support
   // zones that we're trying to break, it could improve our winrate?"). Counts how
   // many bars in the last 60 TAPPED the trigger zone (within 0.30) yet closed back
   // on the defended side. 2+ prior defenses = a proven floor/ceiling under attack.
   {
      double trig = (side > 0) ? bHigh(uhv) : bLow(uhv);
      int defenses = 0;
      for (int k = uhv + 1; k <= uhv + 60; k++) {
         if (side < 0 && bLow(k)  <= trig + 0.30 && bClose(k) > trig) defenses++;
         if (side > 0 && bHigh(k) >= trig - 0.30 && bClose(k) < trig) defenses++;
      }
      if (defenses >= 2) g_lawmask |= 64;
   }
   // ── TAG bit 128 — LATE HUMP (Zee: "after a few humps the probability of making
   // another hump decreases with the number of humps taken" — the camel-humps decay
   // theory, measured before it may ever gate). Counts the current staircase of
   // consecutive lower pivot-lows (SELL) / higher pivot-highs (BUY), d=2 pivots,
   // 90-bar memory. 4+ humps = a mature leg being asked for one more.
   {
      int humps = 0; double last = 0; bool first = true;
      for (int k = 3; k <= 90; k++) {
         bool piv = true;
         for (int dd = 1; dd <= 2; dd++) {
            if (side < 0 && (bLow(k) > bLow(k - dd) || bLow(k) > bLow(k + dd))) piv = false;
            if (side > 0 && (bHigh(k) < bHigh(k - dd) || bHigh(k) < bHigh(k + dd))) piv = false;
         }
         if (!piv) continue;
         double e = (side < 0) ? bLow(k) : bHigh(k);
         if (first) { last = e; first = false; humps = 1; continue; }
         if ((side < 0 && e > last) || (side > 0 && e < last)) { humps++; last = e; }
         else break;                        // the staircase ends where order breaks
      }
      if (humps >= 4) g_lawmask |= 128;
   }
   return d;
}

int ClicksFor(int d) { return (d <= 1) ? 1 : ((d == 2) ? 2 : 3); }

//+------------------------------------------------------------------+
int OnInit() {
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   // The load fingerprint. Hot-reload of an attached chart is UNRELIABLE, so this line is
   // how a deploy is verified — if the Experts tab does not say v1.20 AND name both
   // guards, the chart is still running the old binary and the change did NOT take.
   PrintFormat("[ZEE] ZeeUHV v1.45 — HIS rules from 146 labels. SL %.1f / TP %.1f · magic %d"
               " · hold %d min · stack x%d (max %d tickets = %.2f lots, risk %.0f per failed setup)",
               InpStopPts, InpTargetPts, InpMagicNumber, InpMaxHoldMin, MathMax(1, InpStackMult),
               (1 + 3 + ((InpUhvVolDia > 0) ? 1 : 0) + ((InpClimaxDia > 0) ? 1 : 0))
                  * MathMax(1, InpStackMult),
               (1 + 3 + ((InpUhvVolDia > 0) ? 1 : 0) + ((InpClimaxDia > 0) ? 1 : 0))
                  * MathMax(1, InpStackMult) * InpLots,
               (1 + 3 + ((InpUhvVolDia > 0) ? 1 : 0) + ((InpClimaxDia > 0) ? 1 : 0))
                  * MathMax(1, InpStackMult) * InpLots * InpStopPts * 100.0);
   PrintFormat("[ZEE] PRICE via SymbolInfoTick + tick-history cross-check %s — refuse if "
               "the two disagree >%.2f pts or the tick is >%d s old · levels re-anchored "
               "on each fill (the 2026-08-14 -$695 fault)",
               (InpMaxQuoteDrift > 0 || InpMaxQuoteAgeSec > 0) ? "ARMED" : "*** OFF ***",
               InpMaxQuoteDrift, InpMaxQuoteAgeSec);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r) { PrintFormat("[ZEE] deinit reason=%d", r); }

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| CurrentTick — the ONLY way this EA is allowed to learn a price.  |
//|                                                                  |
//| Zee, 2026-08-15: "can u ensure that we're using a method to pull  |
//| the latest price only while trading.. so we're using the current  |
//| price always"                                                     |
//|                                                                  |
//| The old code called SymbolInfoDouble(SYMBOL_ASK). That returns a  |
//| number and NOTHING ELSE — no timestamp, no way to know whether it |
//| is from this second or from last night. On 2026-08-14 it returned |
//| a price six hours old, twice, and the stop and target were built  |
//| on it. -$695 on one trade and a 4.43-point stop on the other.     |
//|                                                                  |
//| SymbolInfoTick returns the same price WITH tick.time, so age      |
//| becomes a fact instead of an assumption. Four checks, and the     |
//| function refuses rather than guessing:                            |
//|                                                                  |
//|   1. the call itself must succeed                                 |
//|   2. the symbol must be SYNCHRONIZED with the server              |
//|   3. the tick must be younger than InpMaxQuoteAgeSec              |
//|   4. the tick DATABASE (a different code path) must agree with it |
//|                                                                  |
//| Every refusal prints. A guard that blocks silently is             |
//| indistinguishable from a quiet market.                            |
//+------------------------------------------------------------------+
bool CurrentTick(MqlTick &out) {
   if (!SymbolInfoTick(_Symbol, out)) {
      PrintFormat("[ZEE] [BLOCKED] SymbolInfoTick failed (%d) — no price, no trade",
                  GetLastError());
      return false;
   }
   if (out.ask <= 0 || out.bid <= 0) {
      PrintFormat("[ZEE] [BLOCKED] nonsense quote bid=%.2f ask=%.2f", out.bid, out.ask);
      return false;
   }
   if (!SymbolIsSynchronized(_Symbol)) {
      Print("[ZEE] [BLOCKED] symbol is NOT synchronized with the server — refusing to trade");
      return false;
   }
   if (InpMaxQuoteAgeSec > 0) {
      long age = (long)(TimeCurrent() - out.time);
      if (age > InpMaxQuoteAgeSec) {
         PrintFormat("[ZEE] [BLOCKED] the tick is %d s old (limit %d) — this is the "
                     "2026-08-14 fault", (int)age, InpMaxQuoteAgeSec);
         return false;
      }
   }
   // The tick DATABASE is filled by a different mechanism than the symbol cache, so it
   // is an independent witness. If the cache had gone stale on 08-14, this is what would
   // have disagreed with it.
   if (InpMaxQuoteDrift > 0) {
      MqlTick h[];
      if (CopyTicks(_Symbol, h, COPY_TICKS_INFO, 0, 1) == 1 && h[0].ask > 0) {
         if (MathAbs(h[0].ask - out.ask) > InpMaxQuoteDrift) {
            PrintFormat("[ZEE] [BLOCKED] cache says %.2f, tick history says %.2f — %.2f "
                        "pts apart (limit %.2f). One of them is lying.",
                        out.ask, h[0].ask, MathAbs(h[0].ask - out.ask), InpMaxQuoteDrift);
            return false;
         }
         if (h[0].time_msc > out.time_msc) out = h[0];   // always prefer the NEWER tick
      }
   }
   return true;
}

// The machine's own pulse: net of its last n closed tickets (works identically in
// the tester and live — both read the same trade history by magic).
double RollingNet(int n) {
   if (!HistorySelect(0, TimeCurrent())) return 0;
   double sum = 0; int got = 0;
   for (int i = HistoryDealsTotal() - 1; i >= 0 && got < n; i--) {
      ulong tk = HistoryDealGetTicket(i);
      if (tk == 0) continue;
      if (HistoryDealGetInteger(tk, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      if (HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagicNumber) continue;
      sum += HistoryDealGetDouble(tk, DEAL_PROFIT)
           + HistoryDealGetDouble(tk, DEAL_SWAP)
           + HistoryDealGetDouble(tk, DEAL_COMMISSION);
      got++;
   }
   return sum;
}

// ── PIPELINE CENSUS (Zee 2026-08-18: "i dont know why our trade count is so low..
// i wanna check if some original law is hindering trades"). Counts every bar's fate
// through the funnel; printed by OnTester as [CEN]. Zero effect on behaviour.
// hourly funnel (Zee 2026-08-18: "we skip the entire session mostly until 22:32...
// is our EA so selective its skipping major hours, or did the market not give a
// chance?") — same counters, bucketed by broker hour, printed as [HCEN].
long h_bars[24], h_rang[24], h_noorig[24], h_nouhv[24], h_wait[24], h_fired[24];
long z_bars=0, z_maxopen=0, z_cooldown=0, z_gap=0, z_ranging=0,
     z_no_origin=0, z_no_uhv=0, z_no_break=0, z_fired=0,
     z_u_nocand=0, z_u_body=0, z_u_neigh=0, z_u_other=0,
     z_b_nocross=0, z_b_loud=0, z_b_late=0;
int g_ureason=0, g_breason=0;

void TryFire() {
   z_bars++;
   int z_hr = (int)((TimeCurrent() / 3600) % 24);
   // Shop-B entry discipline: act only when the just-closed M1 bar COMPLETED an M3
   // candle (bar-1 open time is the last minute of an M3 triplet).
   if (InpEntryBoundary && (iTime(_Symbol, PERIOD_CURRENT, 0) % 180) != 0) return;
   h_bars[z_hr]++;
   if (OpenCount() >= InpMaxOpen) { z_maxopen++; return; }
   if (g_last_fire > 0 &&
       (TimeCurrent() - g_last_fire) < InpCooldownBar * PeriodSeconds()) { z_cooldown++; return; }
   if (!WindowContinuous(InpTrendLook + 5)) {
      z_gap++;
      if (InpVerbose) Print("[ZEE] [SKIP] gap in lookback");
      return;
   }
//  THE 40% GATE, under test (Zee 2026-08-10: "can u check what's stopping us from
//  taking every single opportunity we get?"). Measured on real gold, the structural
//  trend reads FLAT 40.3% of the time, and update_gate()'s "flat -> the ghost waits"
//  forbids BOTH sides for those four hours in ten — before any setup rule is even
//  consulted. It is the single largest brake on trade count, and it was assumed, never
//  tested. With InpRequireTrend=false a ranging tape may still trade: we simply try
//  both sides and take whichever completes a lawful setup.
   int t = TrendNow();
   int sides[2]; int nsides = 0;
   if (t != 0) { sides[0] = t; nsides = 1; }
   else if (!InpRequireTrend) { sides[0] = +1; sides[1] = -1; nsides = 2; }
   else { z_ranging++; h_rang[z_hr]++; if (InpVerbose) Print("[ZEE] [SKIP] ranging — his setup needs a trend"); return; }

   int htf = 0;
   if (InpHtfMinutes > 0) {
      // 2026-08-19, Zee: "we can use the 3 minute chart to add strength to the trend
      // filter... at 1 min scale we are consulting the 3 min. this way it can help us
      // cut loss." The night-2 matrix showed M3 is where hostile months flatten — this
      // asks M3 for a second opinion on direction before an M1 side may fire.
      ENUM_TIMEFRAMES htf_tf = (InpHtfMinutes >= 60) ? PERIOD_H1 :
                               (InpHtfMinutes >= 15) ? PERIOD_M15 :
                               (InpHtfMinutes >= 5)  ? PERIOD_M5  :
                               (InpHtfMinutes >= 3)  ? PERIOD_M3  : PERIOD_M2;
      double hnow = iClose(_Symbol, htf_tf, 1), hthen = iClose(_Symbol, htf_tf, 1 + InpHtfLook);
      if (hnow > 0 && hthen > 0) htf = (hnow > hthen) ? +1 : ((hnow < hthen) ? -1 : 0);
   }

   int origin = -1, uhv = -1, side = 0;
   for (int si = 0; si < nsides; si++) {
      int try_side = sides[si];
      if (InpHtfMinutes > 0 && htf != 0 && try_side != htf) {
         if (InpHtfMode == 0) continue;               // classic veto
         g_htf_against = true;                         // mode 1: trade, but smaller
      } else g_htf_against = false;
      int o = RetracementOrigin(try_side);
      if (o < 0) { z_no_origin++; h_noorig[z_hr]++; continue; }
      int u = FindUhvBroken(o, try_side);
      if (u < 0) {
         if (!g_hadlawful) {
            z_no_uhv++; h_nouhv[z_hr]++;
            if (g_ureason == 1) z_u_nocand++;
            else if (g_ureason == 2) z_u_body++;
            else if (g_ureason == 7) z_u_neigh++;
            else z_u_other++;
         } else {
            z_no_break++; h_wait[z_hr]++;
            if (g_breason == 2) z_b_loud++;
            else if (g_breason == 3) z_b_late++;
            else z_b_nocross++;
         }
         continue;
      }
      z_fired++; h_fired[z_hr]++;
      origin = o; uhv = u; side = try_side; break;
   }
   if (side == 0) {
      if (InpVerbose && t != 0) Print("[ZEE] [SKIP] no lawful setup on the allowed side");
      return;
   }
   t = side;

   MqlTick tk;
   if (!CurrentTick(tk)) return;          // no trustworthy price -> no trade, ever
   double ask = tk.ask;
   double bid = tk.bid;
   double px = (t > 0) ? ask : bid;

   // ── THE QUOTE MUST BE FRESH, AND IT MUST AGREE WITH THE TAPE ─────────────
   // Both refusals PRINT UNCONDITIONALLY. A guard that blocks silently is
   // indistinguishable from a quiet market, and that confusion has cost this
   // project a full day before.
   if (InpMaxQuoteAgeSec > 0) {
      datetime qt = (datetime)SymbolInfoInteger(_Symbol, SYMBOL_TIME);
      long age = (long)(TimeCurrent() - qt);
      if (qt > 0 && age > InpMaxQuoteAgeSec) {
         PrintFormat("[ZEE] [BLOCKED] quote is %d s old (limit %d) — refusing to trade on it",
                     (int)age, InpMaxQuoteAgeSec);
         return;
      }
   }
   if (InpMaxQuoteDrift > 0) {
      // bar 0's close arrives through the HISTORY path, so it is an INDEPENDENT
      // witness to the quote cache. When the two disagree, one of them is lying,
      // and on 2026-08-14 it was the quote — by 5.4 points.
      double c0 = iClose(_Symbol, PERIOD_CURRENT, 0);
      if (c0 > 0 && MathAbs(px - c0) > InpMaxQuoteDrift) {
         PrintFormat("[ZEE] [BLOCKED] quote %.2f vs tape %.2f — %.2f pts apart (limit %.2f). "
                     "This is the 2026-08-14 fault. Trade refused.",
                     px, c0, MathAbs(px - c0), InpMaxQuoteDrift);
         return;
      }
   }
   double sl = (t > 0) ? px - InpStopPts   : px + InpStopPts;
   double tp = (t > 0) ? px + InpTargetPts : px - InpTargetPts;

   if (InpMaxSpreadPts > 0 && (ask - bid) > InpMaxSpreadPts) {
      PrintFormat("[ZEE] [BLOCKED] spread %.2f over limit %.2f", ask - bid, InpMaxSpreadPts);
      return;
   }
   if (InpMaxPullback > 0) {
      // the impulse is the leg into the retracement; the pullback is origin..1
      double swing = 0, pull = 0;
      if (t > 0) {
         double lo = bLow(origin), hi = bHigh(origin);
         for (int k = origin; k <= origin + 20; k++) if (bLow(k) < lo) lo = bLow(k);
         for (int k = 1; k <= origin; k++) if (bHigh(k) > hi) hi = bHigh(k);
         swing = hi - lo;
         double pl = bLow(1);
         for (int k = 1; k <= origin; k++) if (bLow(k) < pl) pl = bLow(k);
         pull = hi - pl;
      } else {
         double hi2 = bHigh(origin), lo2 = bLow(origin);
         for (int k = origin; k <= origin + 20; k++) if (bHigh(k) > hi2) hi2 = bHigh(k);
         for (int k = 1; k <= origin; k++) if (bLow(k) < lo2) lo2 = bLow(k);
         swing = hi2 - lo2;
         double ph = bHigh(1);
         for (int k = 1; k <= origin; k++) if (bHigh(k) > ph) ph = bHigh(k);
         pull = ph - lo2;
      }
      if (swing > 0 && (pull / swing) > InpMaxPullback) return;
   }

   int dia = InpUseDiamonds ? DiamondsFor(origin, uhv, t) : 0;

   // ── THE PROBE GATE — scout first, basket only on conviction ──────────────────
   if (InpProbeSec > 0) {
      bool loudp = false;
      if (InpLoudSizeFrac > 0 && InpLoudSizeFrac < 1.0 && uhv > 1) {
         double lrp = (double)BarVolume(1) / MathMax(1.0, (double)BarVolume(uhv));
         loudp = (lrp > InpLoudVolFrac);
      }
      MqlTick ptk;
      if (!CurrentTick(ptk)) return;
      double ppx = (t > 0) ? ptk.ask : ptk.bid;
      bool pok = (t > 0) ? trade.Buy (InpProbeLots, _Symbol, 0, 0.0, 0.0, "zee_probe")
                         : trade.Sell(InpProbeLots, _Symbol, 0, 0.0, 0.0, "zee_probe");
      if (pok) {
         g_probe_ticket   = trade.ResultOrder();
         g_probe_open     = ppx;
         g_probe_side     = t;
         g_probe_dia      = dia;
         g_probe_mask     = g_lawmask;
         g_probe_loud     = loudp;
         g_probe_deadline = TimeCurrent() + InpProbeSec;
         g_last_fire      = TimeCurrent();
         PrintFormat("[ZEE] [PROBE] scout %s @%.2f — %ds to prove %.2f pts",
                     t > 0 ? "BUY" : "SELL", ppx, InpProbeSec, InpProbeMinPts);
      }
      return;
   }

   // THE STACK — Zee 2026-08-10: "the diamonds should each not only add 1 trade, but
   // add the trade in twice the lots that we already have... 0.1, then 0.2, then 0.3,
   // then 0.4 — it stacks while increasing the lot size as our conviction increases."
   //
   // So a diamond is not a multiplier on one ticket; it is ANOTHER ticket, larger than
   // the one before it. A setup with no diamonds is a single 0.10. A three-diamond
   // setup opens 0.10 + 0.20 + 0.30 + 0.40 = 1.00 across four positions, all sharing
   // the same stop and target.
   //
   // Note what this does to risk: at SL 7 a full four-deep stack risks 7 x 100 x 1.00
   // = $700 on ONE setup. The live receipts from 2026-08-06 already warn about
   // conviction sizing multiplying losses, so InpMaxRisk exists to cap the total and
   // this must be proven in the tester before it goes anywhere near live.
   // Zee, 2026-08-13: "since our winrate since past two days is 100%, let's increase the
   // multiplier of each diamond. so that instead of opening 4 trades, it opens 8 trades."
   //
   // HIS CALL, MADE WITH THE NUMBERS IN FRONT OF HIM. Measured on real ticks first, and
   // recorded here so nobody later mistakes it for an untested change:
   //
   //   * It is a PURE MULTIPLIER. Four periods at 0.02 lots gave -2451.16 against the
   //     4-ticket -1225.58 — exactly 2.000x. Per-ticket expectancy did not move
   //     ($1.40 -> $1.40) and neither did the average loss. It does not make the system
   //     better, it makes it bigger, in both directions.
   //   * AT 0.10 LOTS IT CHANGES WHAT MARCH DOES TO THE ACCOUNT. The 4-ticket stack
   //     survives March at 73.5% equity drawdown; at 8 tickets it BLEW THE ACCOUNT
   //     (93.0%). April blew up either way, but faster.
   //   * All tickets share one stop and fail together, so one lost setup costs
   //     8 x 0.10 x 20pt x $100 = $1,600, which is 38.8% of the $4,123 demo.
   //     Roughly 2.6 losing setups in a row would end it.
   //
   // The concern was put to him in those terms and he chose to ship it. Demo account.
   // the cap must follow the number of ACTIVE laws or the extra diamond is silently lost
   int maxdia = 3 + ((InpUhvVolDia > 0) ? 1 : 0) + ((InpClimaxDia > 0) ? 1 : 0);
   int tickets = InpStackLots ? (1 + MathMax(0, MathMin(dia, maxdia))) * MathMax(1, InpStackMult) : 1;
   // Law 10c — size down the loud band instead of refusing it (see inputs above).
   // Every ticket is equal-sized (StackStep 0), so scaling the COUNT scales the
   // exposure exactly; MathMax(1, ...) guarantees no setup is ever reduced to zero —
   // the law can shrink a trade, never delete one.
   if (InpLoudSizeFrac > 0 && InpLoudSizeFrac < 1.0 && uhv > 1) {
      double lr10 = (double)BarVolume(1) / MathMax(1.0, (double)BarVolume(uhv));
      if (lr10 > InpLoudVolFrac)
         tickets = (int)MathMax(1, MathRound(tickets * InpLoudSizeFrac));
   }
   // HTF-disagree sizing (InpHtfMode 1): the M3 second opinion shrinks, never blocks
   if (InpHtfMode == 1 && g_htf_against && InpHtfSizeFrac > 0 && InpHtfSizeFrac < 1.0)
      tickets = (int)MathMax(1, MathRound(tickets * InpHtfSizeFrac));
   // the self-aware switch: red pulse -> scout size, green pulse -> full stack
   if (InpRegimeLook > 0 && InpRegimeFrac > 0 && InpRegimeFrac < 1.0) {
      if (RollingNet(InpRegimeLook) < 0)
         tickets = (int)MathMax(1, MathRound(tickets * InpRegimeFrac));
   }
   double placed = 0, total = 0;
   for (int q = 0; q < tickets; q++) {
      double lots = NormalizeDouble(InpLots + InpStackStep * q, 2);
      if (!InpStackLots) lots = NormalizeDouble(InpLots * (InpUseDiamonds ? ClicksFor(dia) : 1), 2);
      // 1e-9 slack: 0.20 + 0.10 evaluates to 0.30000000000000004 in doubles, so a cap
      // of 0.30 silently behaved like 0.20 and the sweep returned identical numbers for
      // both. Floating point must never quietly move a risk limit.
      if (InpMaxRisk > 0 && total + lots > InpMaxRisk + 1e-9) break;
      // Zee, 2026-08-12: "measure the diamond's earnings and decide which diamond is
      // the most earner". The count must survive into the deal record to be grouped
      // later, and the comment is the only field that travels with it.
      string tag = StringFormat("zee_%s_D%d_m%d", (t > 0 ? "buy" : "sell"), dia, g_lawmask);
      bool ok = (t > 0) ? trade.Buy (lots, _Symbol, 0, sl, tp, tag)
                        : trade.Sell(lots, _Symbol, 0, sl, tp, tag);
      if (!ok) break;
      total += lots; placed += 1;

      // SECOND LINE OF DEFENCE. The order goes out with quote-based levels so a
      // position is NEVER naked, then this resets the stop and target from the price
      // the ticket ACTUALLY filled at. Even if a bad quote gets past the guard above,
      // the target lands 1 point from the real entry instead of 6.4.
      ulong pt = trade.ResultOrder();
      if (pt > 0 && PositionSelectByTicket(pt)) {
         double fill = PositionGetDouble(POSITION_PRICE_OPEN);
         if (MathAbs(fill - px) > _Point) {
            double nsl = (t > 0) ? fill - InpStopPts   : fill + InpStopPts;
            double ntp = (t > 0) ? fill + InpTargetPts : fill - InpTargetPts;
            if (!trade.PositionModify(pt, nsl, ntp))
               PrintFormat("[ZEE] !! could not re-anchor #%I64u (%d) — still on QUOTE levels",
                           pt, trade.ResultRetcode());
            else if (MathAbs(fill - px) >= 1.0)
               PrintFormat("[ZEE] !! fill %.2f vs quote %.2f (%.2f pts) — levels re-anchored "
                           "on the fill", fill, px, MathAbs(fill - px));
         }
      }
      if (!InpStackLots) break;
   }
   if (placed > 0) {
      g_last_fire = TimeCurrent();
      PrintFormat("[ZEE] %s @%.2f — %d diamond(s) -> %d ticket(s), %.2f lots total · "
                  "UHV %d (vol %d) · brk vol %d",
                  t > 0 ? "BUY " : "SELL", px, dia, (int)placed, total,
                  uhv, (int)BarVolume(uhv), (int)BarVolume(1));
   }
}

void AgeOut() {
   if (InpMaxHoldMin <= 0 && InpBoundaryExit == 0) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if (InpScratchArm > 0 && (!InpScratchRedOnly || RollingNet(20) < 0)) {
         // FEB-11 SCRATCH MODE: once adverse by InpScratchArm, the target moves to
         // the entry (+ofs) and the trade WAITS for its retouch — the hard SL stays
         // as disaster insurance, InpScratchHold as the patience limit.
         int    pside = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
         double entry = PositionGetDouble(POSITION_PRICE_OPEN);
         double cur   = PositionGetDouble(POSITION_PRICE_CURRENT);
         double tpnow = PositionGetDouble(POSITION_TP);
         double scr   = NormalizeDouble(entry + pside * InpScratchOfs, _Digits);
         bool armed = (tpnow > 0 && MathAbs(tpnow - scr) < 0.02);
         if (!armed && pside * (entry - cur) >= InpScratchArm) {
            trade.PositionModify(t, PositionGetDouble(POSITION_SL), scr);
            armed = true;
         }
         int lim = armed ? InpScratchHold : InpMaxHoldMin;
         if (lim > 0 && TimeCurrent() - opened >= lim * 60)
            trade.PositionClose(t);
         continue;                       // scratch mode owns this position's lifecycle
      }
      if (InpBoundaryExit > 0) {
         // Shop B's judgment: the exit is an M3 candle's END, not a stopwatch
         datetime first = ((opened / 180) + 1) * 180;                  // next boundary
         if (InpBoundaryExit == 2 && first - opened < 180) first += 180; // guarantee >=3 min
         if (TimeCurrent() >= first)
            trade.PositionClose(t);
         continue;
      }
      if (TimeCurrent() - opened >= InpMaxHoldMin * 60)
         if (trade.PositionClose(t) && InpVerbose)
            PrintFormat("[ZEE] aged out after %dm", InpMaxHoldMin);
   }
}

//+------------------------------------------------------------------+
//| OnTester — let MT5 rank the passes by WIN RATE, in MT5's own       |
//| numbers.                                                           |
//|                                                                    |
//| Zee, 2026-08-10: "i want you to find something that has a 90%+     |
//| winrate on MT5 tester not Python. Find it using your tests."        |
//|                                                                    |
//| So the search moves inside the tester. The optimiser maximises     |
//| whatever this returns, and this returns the win rate measured by   |
//| MT5 with real spread and real execution — no Python anywhere in    |
//| the loop.                                                           |
//|                                                                    |
//| TWO GUARDS, because an unguarded win rate is trivially gamed:      |
//|   * fewer than InpMinTrades closed trades scores ZERO. Otherwise   |
//|     one lucky trade returns 100% and wins the whole optimisation.  |
//|   * a pass that LOST money scores zero however pretty its win      |
//|     rate. A 95% win rate that nets negative is the SL-30 trap he   |
//|     found this afternoon, where one loss wipes thirty wins.        |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| DO THE DIAMONDS ACTUALLY PREDICT? — per-diamond breakdown.        |
//|                                                                  |
//| Zee, 2026-08-17, reading the fills: "i notice that the lossy      |
//| trades are having comment_D2 while the ones that won have         |
//| comment_D3, is that so?"                                          |
//|                                                                  |
//| Live it looked true — D2 -468.90, D3 +571.80 — but the entire D2  |
//| loss was ONE stop-out, and without it D2 was +35.50 on five       |
//| baskets. Six baskets cannot answer this. The tester can, with     |
//| thousands.                                                        |
//|                                                                  |
//| The report HTML carries no per-trade comment, so the grouping is  |
//| done here. The closing deal's comment is overwritten by MT5 with  |
//| "[tp ...]" or "[sl ...]", so the D count must be read from the    |
//| OPENING deal of the same position — which is why this walks       |
//| position IDs instead of just reading the OUT deal.                |
//| OnTester runs in the TESTER ONLY. It can never affect live.       |
//+------------------------------------------------------------------+
double OnTester() {
   double pnl[8]; int cnt[8], won[8];
   for (int i = 0; i < 8; i++) { pnl[i] = 0; cnt[i] = 0; won[i] = 0; }
   double mpnl[256]; int mcnt[256], mwon[256];
   for (int i = 0; i < 256; i++) { mpnl[i] = 0; mcnt[i] = 0; mwon[i] = 0; }

   if (HistorySelect(0, TimeCurrent())) {
      int total = HistoryDealsTotal();
      for (int i = 0; i < total; i++) {
         ulong tk = HistoryDealGetTicket(i);
         if (tk == 0) continue;
         if (HistoryDealGetInteger(tk, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
         if (HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagicNumber) continue;
         long pos = HistoryDealGetInteger(tk, DEAL_POSITION_ID);
         double p = HistoryDealGetDouble(tk, DEAL_PROFIT)
                  + HistoryDealGetDouble(tk, DEAL_SWAP)
                  + HistoryDealGetDouble(tk, DEAL_COMMISSION);
         // find this position's OPENING deal and read the D count from its comment
         int dia = -1, msk = -1;
         for (int j = 0; j < total; j++) {
            ulong t2 = HistoryDealGetTicket(j);
            if (t2 == 0) continue;
            if (HistoryDealGetInteger(t2, DEAL_POSITION_ID) != pos) continue;
            if (HistoryDealGetInteger(t2, DEAL_ENTRY) != DEAL_ENTRY_IN) continue;
            string c = HistoryDealGetString(t2, DEAL_COMMENT);
            int at = StringFind(c, "_D");
            if (at >= 0) dia = (int)StringToInteger(StringSubstr(c, at + 2));
            int am = StringFind(c, "_m");
            if (am >= 0) msk = (int)StringToInteger(StringSubstr(c, am + 2));
            break;
         }
         if (dia < 0 || dia > 7) continue;
         cnt[dia]++; pnl[dia] += p; if (p > 0) won[dia]++;
         if (msk >= 0 && msk < 256) { mcnt[msk]++; mpnl[msk] += p; if (p > 0) mwon[msk]++; }
      }
   }
   Print("[HCEN] hour(broker) bars ranging no-origin uhv-veto waiting FIRED");
   for (int h = 0; h < 24; h++)
      if (h_bars[h] > 0)
         PrintFormat("[HCEN] %02d:00  %4d %6d %8d %8d %7d %5d",
                     h, h_bars[h], h_rang[h], h_noorig[h], h_nouhv[h], h_wait[h], h_fired[h]);
   Print("[CEN] ======== PIPELINE CENSUS — where the bars die ========");
   PrintFormat("[CEN] bars evaluated %d", z_bars);
   PrintFormat("[CEN]   blocked: maxopen %d · cooldown %d · gap %d", z_maxopen, z_cooldown, z_gap);
   PrintFormat("[CEN]   RANGING (trend gate) %d  (%.1f%%)", z_ranging, z_bars>0 ? 100.0*z_ranging/z_bars : 0);
   PrintFormat("[CEN]   no valid retracement origin %d", z_no_origin);
   PrintFormat("[CEN]   no lawful UHV %d  = no counter candle %d · body<min %d · NEIGHBOUR LOUDER %d · other %d",
               z_no_uhv, z_u_nocand, z_u_body, z_u_neigh, z_u_other);
   PrintFormat("[CEN]   UHV found, no entry %d  = not crossed yet %d · crossing too LOUD %d · crossed LATE %d",
               z_no_break, z_b_nocross, z_b_loud, z_b_late);
   PrintFormat("[CEN]   FIRED %d", z_fired);
   Print("[DIA] ===== per-diamond breakdown (tickets, not baskets) =====");
   for (int i = 0; i < 8; i++) {
      if (cnt[i] == 0) continue;
      PrintFormat("[DIA] D%d  tickets %5d  won %5d  win %6.2f%%  net %10.2f  per ticket %7.3f",
                  i, cnt[i], won[i], 100.0 * won[i] / cnt[i], pnl[i], pnl[i] / cnt[i]);
   }
   Print("[DIA] --- WHICH laws fired (1=ultra 2=climax 4=sweep 8=ema 16=wick 32=L8 64=DEFENDED 128=LATEHUMP) ---");
   for (int i = 0; i < 256; i++) {
      if (mcnt[i] < 1) continue;                  // print everything: the harness aggregates
      int bits = 0;
      for (int b = 0; b < 5; b++) if ((i & (1 << b)) != 0) bits++;   // bit 32 is a TAG, not a diamond
      PrintFormat("[DIA] mask %2d  D%d  tickets %5d  win %6.2f%%  net %9.2f  per ticket %7.3f",
                  i, bits, mcnt[i], 100.0 * mwon[i] / mcnt[i], mpnl[i], mpnl[i] / mcnt[i]);
   }
   Print("[DIA] ==========================================================");

   double trades = TesterStatistics(STAT_TRADES);
   if (trades < InpMinTrades) return 0.0;
   if (TesterStatistics(STAT_PROFIT) <= 0) return 0.0;
   double wins = TesterStatistics(STAT_PROFIT_TRADES);
   return (wins / trades) * 100.0;
}

//+------------------------------------------------------------------+
// probe state: one scout at a time; the pending setup rides with it
ulong    g_probe_ticket = 0;
datetime g_probe_deadline = 0;
int      g_probe_side = 0, g_probe_dia = 0, g_probe_mask = 0;
bool     g_probe_loud = false;
double   g_probe_open = 0;

// The burst: the full stack, sized from the SIGNAL-time diamonds and loud-band flag
// (bar indices shift while the scout works, so the decision travels as data, not as
// indices). Deliberately lean vs the main path: the per-ticket fill-price SL/TP
// re-reset is skipped — acceptable for a default-OFF test arm; noted for any ship.
void FireBasket(int side, int dia, int mask, bool loud) {
   int maxdia = 3 + ((InpUhvVolDia > 0) ? 1 : 0) + ((InpClimaxDia > 0) ? 1 : 0);
   int tickets = InpStackLots ? (1 + MathMax(0, MathMin(dia, maxdia))) * MathMax(1, InpStackMult) : 1;
   if (InpLoudSizeFrac > 0 && InpLoudSizeFrac < 1.0 && loud)
      tickets = (int)MathMax(1, MathRound(tickets * InpLoudSizeFrac));
   MqlTick tk;
   if (!CurrentTick(tk)) return;
   double px = (side > 0) ? tk.ask : tk.bid;
   double sl = (InpStopPts   > 0) ? (side > 0 ? px - InpStopPts   : px + InpStopPts)   : 0.0;
   double tp = (InpTargetPts > 0) ? (side > 0 ? px + InpTargetPts : px - InpTargetPts) : 0.0;
   string tag = StringFormat("zee_%s_D%d_m%d", (side > 0 ? "buy" : "sell"), dia, mask);
   int placed = 0; double total = 0;
   for (int q = 0; q < tickets; q++) {
      double lots = NormalizeDouble(InpLots + InpStackStep * q, 2);
      if (InpMaxRisk > 0 && total + lots > InpMaxRisk + 1e-9) break;
      bool ok = (side > 0) ? trade.Buy (lots, _Symbol, 0, sl, tp, tag)
                           : trade.Sell(lots, _Symbol, 0, sl, tp, tag);
      if (!ok) break;
      total += lots; placed++;
   }
   if (placed > 0) {
      g_last_fire = TimeCurrent();
      PrintFormat("[ZEE] BURST %s @%.2f — %d diamond(s) -> %d ticket(s), pre-tested ground",
                  side > 0 ? "BUY" : "SELL", px, dia, placed);
   }
}

void ProbeManage() {
   if (g_probe_ticket == 0) return;
   if (!PositionSelectByTicket(g_probe_ticket)) {            // swept by hold or closed
      g_probe_ticket = 0; return;
   }
   if (TimeCurrent() < g_probe_deadline) return;
   double cur = PositionGetDouble(POSITION_PRICE_CURRENT);
   double moved = (cur - g_probe_open) * g_probe_side;
   trade.PositionClose(g_probe_ticket);                       // scout's job is done either way
   g_probe_ticket = 0;
   if (moved >= InpProbeMinPts) {
      PrintFormat("[ZEE] [PROBE] conviction %.2f pts -> BURST", moved);
      FireBasket(g_probe_side, g_probe_dia, g_probe_mask, g_probe_loud);  // pre-tested environment
   } else if (InpVerbose)
      PrintFormat("[ZEE] [PROBE] only %.2f pts -> retreat, no basket", moved);
}

void RevExitSweep() {
   // his other exit: while a position is RED, the first opposing-color closed candle
   // says the thesis is disproven — leave. Positions in profit are left for the TP.
   if (!InpRevExit) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if (PositionGetDouble(POSITION_PROFIT) >= 0) continue;
      int pside = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      if ((pside > 0 && IsRed(1)) || (pside < 0 && IsGreen(1)))
         trade.PositionClose(t);
   }
}

void OnTick() {
   ProbeManage();
   AgeOut();
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bt == g_last_bar) return;
   g_last_bar = bt;
   RevExitSweep();
   TryFire();
}
//+------------------------------------------------------------------+
