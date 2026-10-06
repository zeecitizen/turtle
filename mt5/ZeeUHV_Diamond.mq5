//+------------------------------------------------------------------+
//|  ZeeUHV_Diamond.mq5 — THE UNTOUCHED DIAMOND, resurrected         |
//|  Byte-identical to commit 718b68a (the streak-era machine,       |
//|  Aug 11-13 2026: 14 baskets, 100%, +$614) except this nameplate, |
//|  magic 88094->88154, [ZEE]->[DIA], zee_->zdia_ ticket tags.      |
//|  Zee, 2026-08-20: "i wanna see because that EA performed even    |
//|  better than what our ZeeUHV is doing now on 1 min."             |
//|  COURT RECEIPTS of this config (v1.47 RAW reconstruction):       |
//|  -1,640/six fortnights: POSITIVE in 4 of 6 (May +220, Jun +161,  |
//|  Jul +180, LIVE +38) — destroyed by Mar (-803) and Apr (-1,437). |
//|  At 0.10 lots a crash cluster can cost ~$1,700 in a day. It has  |
//|  NO pulse, NO laws 9+, NO clock discipline beyond hold-60.       |
//|  It is the wild ancestor, revived for live observation.          |
//+------------------------------------------------------------------+
#property copyright "Zee & his ghost"
#property version   "1.27"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

input double InpLots        = 0.02;   // InpLots — lot size
input int    InpMagicNumber = 88154;  // InpMagicNumber — 88094 = ZeeUHV, tester only

// ── HIS EYE, FOR THE ANCESTOR (2026-08-21). The Diamond judges UHVs on volume and
// owns no other guard, so the volume feed IS its strategy. Measured over four days
// at live size: broker +433.90 vs OANDA +1,358.10, better on 3 of 4 — and Aug 19,
// the day the broker feed cost it -522.30, came back +59.40 on his eye. That day is
// the Diamond's whole disease (one basket erases nine good days).
// Reads Common\Files\oanda_vol.csv, reloaded once per M1 bar, per-minute fallback
// to broker volume. Levels and fills stay Blueberry's, always. Default 0.
// ── HIS EYE OR NO TRADE (Zee 2026-09-06) ─────────────────────────────────────────
// "we donot wish to use broker volume, we want to completely transition to OANDA
//  volume taken from tradingview. any broker volume trades waste our time"
//
// Default flipped 0 -> 1. But the switch alone was never enough, and the 04:28 SELL
// of 04 Sep is the proof: BarVolume() falls back to the broker PER BAR, silently,
// whenever the table lacks a minute. That trade logged "UHV 02:23 (vol 87)" — broker
// to the decimal — while his own chart showed 150 that minute and made 02:22 the
// louder bar. A different candle, a different trigger, a trade that does not exist on
// his chart. It lost $123.10.
//
// So the fallback itself is the defect, not the default. InpOandaStrict makes a
// missing OANDA minute a minute we CANNOT READ: no fire, rather than a fire judged on
// a feed he does not use. InpVolFreshSec does the same for a stalled bridge.
// Levels, stops and fills stay Blueberry's — we trade his broker, we judge his chart.
input int    InpOandaVolume = 1;    // 1 = judge UHVs on OANDA (TradingView) volume
input bool   InpOandaStrict = true; // a missing OANDA minute = no trade, never broker
input int    InpVolFreshSec = 90;   // table older than this = stalled bridge, no trade

input group "── His rules (each one quoted from his labels in the code) ──"
input int    InpTrendLook   = 20;   // InpTrendLook — 20 validated
input int    InpPivot       = 3;      // InpPivot — swing pivot strength
input bool   InpRequireTrend = true;  // InpRequireTrend — false lets RANGING tape trade too (the 40% gate)
input int    InpRetraceBack = 20;   // InpRetraceBack — 20 validated
input double InpUhvBodyMin  = 0.5;   // InpUhvBodyMin — 0.5 validated. 0.3 finds more setups and loses money
input int    InpBreakWindow = 12;     // InpBreakWindow — bars after the UHV in which the break must come

input group "── Exit: SL 6 / TP 3 measured on his own setups ──"
input double InpStopPts     = 20.0;   // InpStopPts — 20 validated: 93.3% on 1,608 trades, 100% on both unseen sets
input double InpTargetPts   = 1.0;    // InpTargetPts — 1.0 is ZEE'S CALL: 25W/1L, 96%, his own Feb-11 shape
// 2026-08-30, Zee: "i want to check these minutes holding a trade for 0.3, 0.5,
// 1, 2, 3, 5, 10, 20, 30, 60". An int cannot express 18 or 30 seconds, so the
// hold cap is now a DOUBLE. 0.3 = 18s. Default unchanged at 60.
// SHIPPED 2026-09-01 as 20 (was 60). Court on his chart at random delay, 20-29 Aug,
// ten values from 18 seconds to an hour. A monotone ramp, not a spike:
//   0.3m -725 · 1m -787 · 3m +592 · 5m +1055 · 10m +1104 · 20m +3248 · 60m +2522
// Cutting fast destroys it — the ladder needs price to retrace to the FIRST fill, and
// that takes minutes. But an hour is pure exposure: 20m earns +725 more than 60m AND
// drops the worst ticket from -200.20 to -125.90.
input double InpMaxHoldMin  = 20;   // minutes to hold before closing at market

input group "── Housekeeping ──"
input int    InpMaxOpen     = 1;      // InpMaxOpen — concurrent SETUPS (a stack counts as one)
input int    InpCooldownBar = 3;      // InpCooldownBar — bars between entries
input int    InpMaxGapSec   = 300;    // InpMaxGapSec — never reason across a hole in the data
input bool   InpVerbose     = false;  // InpVerbose — OFF for optimisation (a sweep with logging is 100x slower)
input int    InpMinTrades   = 15;

input group "── Diamonds: conviction buys SIZE (Zee 2026-08-10) ──"
input bool   InpUseDiamonds = true;   // InpUseDiamonds — size by conviction instead of a flat lot
input double InpMaxRisk     = 0.0;    // InpMaxRisk — 0 = off. Cap TOTAL lots across the stack.
input bool   InpStackLots   = true;   // InpStackLots — each diamond opens ANOTHER position, each one bigger
input double InpStackStep   = 0.0;   // InpStackStep — 0.0 = every diamond ticket stays at InpLots (Zee's call)
input int    InpStackMult   = 2;      // InpStackMult — multiplies the whole stack. 2 => 8 tickets at 3 diamonds (Zee 2026-08-13)

// ── ONE ORDER, OR EIGHT? (2026-08-30) ────────────────────────────────────────────
// Zee saw the fills and said the right thing: "the diamond is oblivious of this — it
// just places an order and the fills are at the broker's responsibility". Exactly. The
// EA issues N market orders in a synchronous loop; the SPACING between them is round
// trip latency, not design. Nobody built a ladder — one fell out of the wiring.
//
// And because the stop and target are anchored to the FIRST fill, every later fill sits
// better against those fixed exits:
//     multiplier 1  sold 4560.21  risks 13.28 to make  7.72   1 : 0.58
//     multiplier 8  sold 4563.66  risks  9.83 to make 11.17   1 : 1.14
// So the accident may be HELPING. InpOneOrder places the whole size as a single market
// order instead — the implementation anyone would write on purpose — which hands the
// entire position multiplier 1's inferior geometry. Default false: live is unchanged.
input bool   InpOneOrder    = false;  // true = one order of the full size, no ladder

// ── DELIBERATE SPACING (2026-08-30) ──────────────────────────────────────────────
// The accident is worth double the clean design: at RANDOM delay the 8x0.10 ladder made
// +2,128.60 against one 0.80 order's +1,055.40, and at ZERO delay the two are identical
// to the cent — so the whole difference IS the spacing between fills.
//
// If unintended spacing is worth $1,073 over nine days, what is INTENDED spacing worth?
// InpSpaceSec spreads the basket over N seconds on purpose instead of placing it as fast
// as the broker allows. The stop and target stay anchored to the FIRST fill, because
// that anchoring is the mechanism: every later fill sits better against fixed exits.
//
// Not a blocking Sleep — that would freeze OnTick for half a minute live. The basket is
// remembered and one ticket is released per tick once its moment arrives.
input double InpSpaceSec    = 0.0;    // >0 = spread the basket over this many seconds

// ── THE LAWS OF CONVICTION, AS GATES (2026-08-31) ────────────────────────────────
// Zee: "there were some laws of conviction before the OANDA volume was used, can you
// test them all now on the OANDA volume?"
//
// Every one of these was built and tuned while the EA judged UHVs on BLUEBERRY volume —
// the feed we proved on 30 Aug inverts the sign of a day (broker -2,096 vs his chart
// +166 on the same two days). So their receipts are all suspect, and two of them read
// volume directly, which makes them suspect twice over.
//
// The Diamond carries only three of the eight, and only as SIZE — they add tickets and
// never refuse a setup. InpReqLaws makes any subset a GATE instead, so a law can be
// asked the harder question: does requiring you make the trades better?
//
//     1  UHV is LOUD      volume >= InpDiaLoudMult x the 20 bars before it   [volume]
//     2  SELLING CLIMAX   the UHV is the widest bar of the last 7
//     4  THE SWEEP        price poked beyond the prior extreme on the way in
//     8  EMA-5 CLOSE      the breakout closed decisively past the mean
//    16  WICK + QUIET     wick <= 0.25 of range AND breakout quieter than UHV [volume]
//    32  REF-8 BREAK      the 8-bar reference high/low was taken out
//    64  DEFENDED LEVEL   2+ prior bars tapped the trigger and closed back
//   128  LATE HUMP        4+ humps already in this staircase
//
// Sum the bits you want required. 0 = off, which is how it trades today.
// SHIPPED 2026-09-01 as 4 — THE SWEEP required. Court on his chart at random delay,
// three windows, the law demanded rather than merely counted:
//   20-29 Aug   none +2,184 PF 1.45  ->  sweep +4,333 PF 2.81   (in-sample)
//   17-19 Aug   none   +692 PF 1.74  ->  sweep +1,297 PF 5.22
//   05-07 Aug   none -1,223 PF 0.56  ->  sweep -1,261 PF 0.56   (inside noise)
// It raises PROFIT FACTOR rather than trade count — 488 trades against 511, so it
// refuses 23 setups and nearly doubles the money. Every other law tested WORSE as a
// gate, including law 1 (UHV is loud), whose threshold was tuned on Blueberry volume
// and collapses on his chart: +99 against +2,184.
// It does not rescue a bad window. 05-07 Aug loses under every law.
input int    InpReqLaws     = 0;      // bitmask of laws that must ALL hold to fire

// ── THE BREAKOUT HAS FAILED (2026-09-01) ─────────────────────────────────────────
// Zee, watching a basket 10 points underwater: "its a theory that if 1-X candles go
// against us after the breakout, the breakout has failed... on this open trade right now
// the down trend ended to give way to an uptrend (that's the only loss after so many
// wins, when the trend shifts)".
//
// A time cap cannot tell a slow winner from a dead trade — it only counts minutes. This
// counts EVIDENCE: consecutive closed candles running counter to the breakout. A sell
// that keeps printing greens is not slow, it is wrong.
//
// Consecutive, not cumulative: one green inside a fall is noise, three in a row is a
// change of hands. Reset whenever a candle closes our way. 0 = off.
input int    InpFailCandles = 0;      // >0: close the basket after N candles against us

// -- THE JURY: MT5's OWN INDICATORS AS A POST-ENTRY GUARD (Zee 2026-09-29) --------------
// "take the indicators MT5 provides -> momentum, stochastic, RSI, ADX.. now right after
//  entry notice the movements of these indicators. if they are moving in our favor. in the
//  direction of breakout, then OK let it go till TP. if they disagree, immediately come out
//  and exit and bam we're saved!"
//
// Four indicators are SNAPSHOTTED on the bar the basket opens, then read again InpJuryBars
// closed bars later. Each one votes: has it moved WITH the breakout, or against it?
//   RSI          rising favours a buy, falling favours a sell
//   Momentum     the same
//   Stochastic   main line, the same
//   ADX          the +DI/-DI SPREAD - widening in our direction is agreement
// InpJuryVotes of the four disagreeing closes the basket at market.
//
// Mode 1 asks ONCE, which is literally what he described ("right after entry"). Mode 2 keeps
// asking on every closed bar, so a basket that turns later is still caught. 0 = off, and off
// is the default until it has receipts - every new filter in this project starts off.
input int    InpJuryMode   = 0;    // 0=off - 1=one verdict at InpJuryBars - 2=re-vote every bar
input int    InpJuryBars   = 2;    // wait this many CLOSED bars after entry before voting
input int    InpJuryVotes  = 2;    // how many of the four must disagree to close the basket
input int    InpJuryRsiN   = 14;   // RSI period
input int    InpJuryMomN   = 14;   // Momentum period
input int    InpJuryAdxN   = 14;   // ADX period
input int    InpJuryStochK = 5;    // Stochastic %K
input int    InpJuryStochD = 3;    // Stochastic %D
input int    InpJuryStochS = 3;    // Stochastic slowing

// -- THE BAIL: "the breakout has to succeed IMMEDIATELY" (Zee 2026-09-29) --------------
// After InpBailSec seconds, a basket that is not at least InpBailAt (in PRICE, so 0.10 is
// one pip of gold) in front of its entry is a failed breakout and is closed at market. A
// basket that IS in front is left alone entirely.
//
// The difference from InpFailCandles, which is the whole reason this exists: FailCandles
// judges CANDLE COLOUR and so closes winners on their way up (97% -> 70% win rate, measured).
// This judges the trade's own P&L, so nothing that is working is ever touched.
//
// 0 = off. InpBailAt = 0.0 means "must simply be in front"; a negative value grants slack
// (-0.20 = allow two pips against before declaring failure).
input int    InpBailSec    = 0;      // >0: seconds after entry at which a basket must be working
input double InpBailAt     = 0.0;    // must be at least this far in FRONT (price) or it is closed

// -- THE DETECTION FIXES (2026-09-29). Each default FALSE so the baseline is unchanged. --
// InpRetraceFix: the UHV window was the TAIL of the pullback, not the pullback. Measured on
// the EA's own [LAWX] log, 155 fires: origin == UHV in 65% of them, so "the largest red
// volume" was a comparison of ONE candle. See LAWS.md, the UHV paragraph.
input bool   InpRetraceFix  = true;   // true = retracement starts at its FIRST breaking body
// InpOandaColour: "on OANDA volume, the colors are the correct ones we look for" (Zee). Colour
// came from Blueberry while volume came from his chart; 15% of bars have a body smaller than
// the documented 0.85 feed difference, so their colour depended on which feed was asked.
input bool   InpOandaColour = false;  // true = red/green decided by HIS candle, not the broker
// InpBreakBodyMin: LAWS.md's breakout clause (a) - "a momentum candle (no big wick) -> proven
// to be better than 'no wick test' via tests", and his own definition below it: "Body Size
// (>= 70% of Range) ... |Close - Open| / (High - Low) >= 0.70".
// BreakoutIsBar1() has NEVER tested this. It checks colour, the crossing and that volume is
// quieter than the UHV, and nothing about the candle's shape. Meanwhile InpUhvBodyMin applies
// a 0.5 body floor to the UHV candle, which his page does not ask for at all - so the
// momentum test existed in this EA but on the WRONG CANDLE at the WRONG THRESHOLD.
// The same clause in BasedOnLaws (v1.31-32) "deleted SEVEN losing trades and ZERO winners".
// 0.0 = off, 0.70 = his number.
input double InpBreakBodyMin = 0.0;   // breakout body / range floor. His law says 0.70
// InpOandaPrice: LAWS.md's opening rule applied to the TREND. CamelTrendD() draws its humps
// from iHigh()/iLow() - the broker's - so the pivots deciding "is this an uptrend", the high
// the impulse must break, and his line-45 defended low are all Blueberry's. A pivot is decided
// by the ORDERING of neighbouring extremes and the feeds differ by up to 0.85 in price, which
// is more than many M1 highs are apart - so a hump can move by whole bars, or vanish.
// M1 only (his table is one row per minute). Execution is always at broker prices.
input bool   InpOandaPrice  = false;  // true = camel humps drawn on HIS highs and lows

// ── HIS LINE 42, AT LAST (2026-09-01) ────────────────────────────────────────────
// Zee: "can you test setting the SL at the last low (retracement's low) 5-7 pips
// beneath it maybe".
//
// LAWS.md line 42: "The stop loss of this trade is placed at 5-7 pips below the lowest
// point of the retracement (the last low)". The Diamond has never done this. It puts the
// stop a flat $20 from wherever the first ticket happened to fill, which is why one bad
// basket costs 8 x 20 x 0.10 x 100 = $1,600 regardless of what the chart was doing.
//
// UNITS, and they matter: gold quotes 0.01 per point and 0.10 per pip, so 0.60 in PRICE
// is 6 pips — which is how BasedOnLaws has always done it. The D07 variant multiplied by
// 10 * _Point on top, giving 0.6 pips, and then went 0-for-4 in the eleven-law court.
// That result was measuring my arithmetic, not his law.
//
// 0 = off, the flat InpStopPts. >0 = this many PRICE units beyond the retracement's
// extreme, so 0.60 is his six pips.
// SHIPPED 2026-09-01 as 0.50 — FIVE PIPS under the retracement. His line 42, obeyed
// for the first time. Court on his chart at random delay, v1.13 as it traded:
//                      flat $20                 5 pips structural
//   20-29 Aug   +4,337 PF2.73 DD18.9%     +2,579 PF1.96 DD 9.1%   (in-sample)
//   17-19 Aug       +3 PF1.00 DD15.8%       +202 PF1.20 DD 7.7%
//   05-07 Aug   -1,243 PF0.59 DD37.8%       -342 PF0.84 DD22.2%
//
// IT MAKES LESS MONEY: -658 across the three windows. It is shipped anyway, because
// it HALVES THE DRAWDOWN in every window (37.8->22.2, 15.8->7.7, 18.9->9.1) and cuts
// the worst window by 73%. Nothing else tested has touched the bad days at all; every
// other candidate improved good tape and left the catastrophes exactly where they
// were. This account has been to $53.99 once.
//
// 5 pips beat his 6 — both inside noise of each other, and both inside his 5-7.
// UNITS: gold is 0.01/point, 0.10/pip, so 0.50 in PRICE is five pips. The D07
// variant multiplied by 10 * _Point on top, tested 0.6 pips, went 0-for-4, and I
// reported that as "his structural stop never helps". It was my arithmetic.
input double InpStructStop  = 0.50;   // stop this far (price) beyond the retracement extreme
input double InpDiaLoudMult = 1.30;   // law 1: how loud the UHV must be vs its neighbours
// ── THE TREND ENGINE (2026-09-08) ────────────────────────────────────────────────
// Zee: "our diamond EA is only lacking one thing. a proper trend checking system. we
// rely on camel humps. but the end of the trend is not reliably detected. this makes
// our EA lose hard when the trend is shifting."
//
// TrendNow() (mode 0) compares two STALE pivots to each other: highs[n-1] > highs[n-2]
// and lows[n-1] > lows[n-2]. A pivot is only confirmed InpPivot bars after it forms, so
// the test is structurally blind at the very moment a leg pushes into new ground — and
// BasedOnLaws measured the same test refusing 287 of 420 session minutes on a day Zee
// reads as an uptrend throughout. 80% of clean trends called a range across seven days.
// That is BOTH of tonight's failures at once: it misses setups inside strong moves, and
// it keeps saying "uptrend" through the confirmation lag at the top.
//
// Mode 1 is CamelTrend, ported MQL->MQL from BasedOnLaws v1.33-34 where it scored
// 61.1% / +1044.30 against the stale-pivot version's 31.6% / +298.10. It draws the humps
// from pivots and asks his question in the PRESENT TENSE — "are we breaking above
// previous highs" — instead of asking whether two old pivots were rising.
// ── READ THE TREND ON A SLOWER CHART, TRADE ON THIS ONE (2026-09-08) ─────────────
// Zee: "maybe i think the problem could be that the 1 minute timeframe shifts alot
// between trends ... it seems that shifting trend is the cause of the problem"
//
// He is describing the TREND, not the entry. Running the whole EA on M5 tests something
// else entirely — it moves the trend AND the entries AND the structural stop at once,
// and the court showed why that fails: setups collapse from ~1,000 to ~100 and the stop
// widens with the slower swings while the target stays a flat 1.00.
//
// This isolates his claim. The structure walk reads InpTrendTF; everything else — the
// retracement, the UHV, the breakout, the stop, the fills — stays on the trading chart.
// 0 = the chart the EA is attached to (unchanged behaviour).
// ── THE TEACHER'S ECONOMICS (Zee 2026-09-08) ─────────────────────────────────────
// "the idea is that if we maintain a low with us. we then have an SL for a trade at the
//  last low (the deeper low amongst the lows if there's more than one confirmed low).
//  then we target R:R ratio 1:2 as the TP. at R:R ratio 1:1 we breakeven and let it run
//  to R:R ratio 1:2 in TP. This is what the original author of the strategy said."
//
// The Diamond has never run this shape. Its target is a FLAT 1.00 against a structural
// stop of 2-4, i.e. ~0.2R, which needs ~83% just to break even; the live book delivers
// 67-81% and loses. Every loss costs three winners. This is the first configuration
// that changes the payoff instead of chasing the hit rate.
//
// InpSlMode 1 uses the level the trend engine DEFENDS — the deepest confirmed low —
// rather than the retracement's own extreme, which is his "deeper low amongst the lows".
input int    InpSlMode      = 0;      // 0 = retracement extreme (line 42) · 1 = defended structural low
input double InpTargetR     = 0.0;    // >0: TP = this many R. 0 = the flat InpTargetPts
input double InpBreakEvenR  = 0.0;    // >0: at this R move the stop to entry (his 1:1 rule)
input double InpBeBufferPts = 0.0;    // park breakeven this far the profitable side of entry

// ── NEW YORK ONLY (Zee 2026-09-08, his LAWS.md line 47) ──────────────────────────
// "ok YES let's make Diamond NY only.. to target a 91% winrate"
// Measured on 601 real Diamond tickets, 20 Aug - 8 Sep, split by broker hour:
//   NY (broker 15-23)  264 tk  91% WR  +494.60   +38.05/day   11 green days / 2 red
//   outside            337 tk  74% WR -1976.80  -141.20/day    7 green / 6 red
// Broker is UTC+3 and New York 08:00-17:00 ET is UTC-4 in September, so his session
// is broker 15:00-23:59. Hours are the BROKER's, which is what TimeCurrent() returns.
// ── THE HUMP BUDGET (Zee 2026-09-09, with his drawing) ──────────────────────────
// "When a trend starts on 1 minute scale it makes 2..3..X definite camel humps.. after
//  a certain number of humps the trend expires. price starts shifting to a new trend.
//  if we stop after the price has made a new trend and the X number of humps are done,
//  we might be able to avoid the ONE LAST TRADE that is taken at the end of the trend."
//
// A trend gets a BUDGET of humps rather than a verdict. Every other attempt on this
// problem asked "has the trend ended yet?" and answered too late by construction —
// TrendNow needs two fresh pivots, and line 45 needs the low already broken. Counting
// forward from the trend's birth needs no confirmation at all: the fourth hump is the
// fourth hump whether or not the top has printed.
//
// A hump = one confirmed swing in the trend's own direction — the orange arcs he drew.
// The count resets whenever the trend direction changes, so a new trend gets a new
// budget. 0 = off.
// SHIPPED AT 3 (Zee 2026-09-09): "let's set it at 3 and activate it on the diamond.
// this could result in us avoiding trades taken at the end of a trend where trend
// starts to shift."
//
// 3 is the MEASURED median. Instrumented over 113 trends on 31 Aug - 5 Sep: 1 hump 15
// trends, 2 humps 34, 3 humps 25, 4 humps 11 — median 3, mean 3.5, and 75% of trends
// are finished by hump 4. His model ("hump 3 trade, hump 4 hmm maybe it shifts") is
// what the tape actually does.
//
// SHIPPED AGAINST THE BACKTEST, ON HIS INSTRUCTION AND WITH THE NUMBER IN FRONT OF HIM.
// Three windows, real ticks: budget 3 = +768.10 (1/3 windows) against OFF = +2,287.40
// (2/3). Budget 8 scored better (+2,427.30, 3/3) but refuses ONE trade in 28 — a
// placebo, which is why it was withdrawn. 3 refuses 4-5 in 28 and is the only setting
// that actually implements the rule he is asking for.
input int    InpMaxHumps    = 3;      // >0: stop taking setups once the trend has made this many humps
// 2026-09-09, same day, his second call: "let's make it 2 instead of 3."
// 2 refuses 9 of 28 fires where 3 refuses 5, and cuts the three-window trade count to
// 324 against 462. It scores slightly BETTER than 3 (+830.30 vs +768.10, positive in
// 2 of 3 windows against 1 of 3) — but it is worse on aug31 specifically (-506.90 vs
// -215.10), which is the window holding the trend-shift losses this rule exists to
// stop. And it is one tier STRICTER than the model he described ("hump 1 trade, hump 2
// trade, hump 3 trade, hump 4 hmm"): budget 3 allows humps 0-1-2, budget 2 allows 0-1.
// Shipped on his instruction with both numbers in front of him.
input bool   InpNyOnly      = false;  // true = trade only the New York session
input int    InpNyFromHour  = 15;     // broker hour, inclusive
input int    InpNyToHour    = 24;     // broker hour, exclusive
input int    InpTrendTF     = 0;      // 0 = this chart · 5 = read trend on M5 · 15 = M15
// CAMELTREND ON — SHIPPED 2026-09-17 on Zee's instruction ("turn on mode 1 CAMEL on live
// EA on blueberry now"). He added the history: "that's coz we built Camel then left it
// replaced mid-testing other trend methods" — it was never rejected, it was mislaid.
//
// MEASURED IN THIS EA AT LAST. Every previous number for CamelTrend came from BasedOnLaws
// and was ported across. 8-17 Sep 2026, Blueberry real ticks, M1, every input pinned:
//
//     mode 0 TrendNow (shipped)   -$250   158 trades   72% WR   DD $778   streak 14
//     mode 1 CAMEL broke_top      +$404    74 trades   89% WR   DD $266   streak  8
//     mode 2 EMA slope            -$692   226 trades   79% WR   DD $1005  streak 16
//
// It turns a losing EA into a profitable one by REFUSING 84 of the 158 trades, and those
// 84 were collectively worse than worthless — which is exactly Zee's complaint, that the
// EA "fires when the breakout results in a failure". The slope reader is worse than either,
// the same ordering VSISA found independently on a different broker and a different volume
// feed: structure beats slope.
//
// THE EVIDENCE IS ONE WINDOW AND 74 TRADES, and that is worth saying plainly. Two earlier
// August windows were run to confirm it and returned NO TRADES at all, so there is no
// out-of-sample leg here — unlike everything shipped in VSISA this week, which had to hold
// in both walk-forward halves. Shipped on his call with that limitation in front of him.
input int    InpTrendMode   = 1;      // 0 = TrendNow (stale pivots) · 1 = CamelTrend · 2 = EMA slope
input int    InpHighTest    = 1;      // CamelTrend: 0 = rising pivots · 1 = broke_top (his words) · 2 = either
input int    InpEmaSlopeBars = 10;    // mode 2: slope of EMA-5 measured over N bars
input int    InpLastLowMode = 0;      // 0 = off · 1 = snapshot (BasedOnLaws) · 2 = latch
input bool   InpStopOnLastLow = false; // LAW 45: stop buying once the last low breaks

double   g_guard = 0;          // law 45: the level being defended, for the log
int      g_hump_dir = 0;      // the trend whose humps we are counting
int      g_hump_n = 0;        // humps completed since that trend began
datetime g_hump_last = 0;     // the newest swing already counted
int      c_humps = 0;         // setups the budget refused
bool     g_ll_dead_up = false; // law 45 LATCH: buying stopped, the last low broke
bool     g_ll_dead_dn = false; // the short mirror
int      c_law45 = 0;          // setups the latch refused
// THE FUNNEL (2026-09-29). One counter per gate, so "where did the setups go" is a fact
// rather than a guess. TryFire() runs once per bar; c_bars is the denominator.
int      c_bars     = 0;   // bars TryFire was asked to judge
int      c_session  = 0;   // refused: outside the New York window
int      c_maxopen  = 0;   // refused: a setup is already open (InpMaxOpen)
int      c_cooldown = 0;   // refused: still inside InpCooldownBar
int      c_gap      = 0;   // refused: a hole in the lookback
int      c_stale    = 0;   // refused: the OANDA bridge was stale
int      c_ranging  = 0;   // refused: no trend, and InpRequireTrend is on
int      c_noorigin = 0;   // no retracement found on the allowed side
int      c_nouhv    = 0;   // a retracement, but no UHV survived FindUhv
int      c_nobreak  = 0;   // a UHV, but bar 1 was not its breakout
int      c_laws     = 0;   // refused by the InpReqLaws gate (the SWEEP)
int      c_fired    = 0;   // setups that actually opened a basket
datetime g_last_bar = 0;
datetime g_last_fire = 0;

int      g_fail_side = 0;      // direction of the basket being watched
int      g_against   = 0;      // consecutive candles closed against it

// THE JURY's handles and its snapshot of the four indicators at the moment of entry
int      h_jrsi = INVALID_HANDLE, h_jmom = INVALID_HANDLE;
int      h_jstoch = INVALID_HANDLE, h_jadx = INVALID_HANDLE;
int      g_jury_side = 0;      // direction of the basket under observation
datetime g_jury_bar  = 0;      // the bar it opened on, so "bars since entry" is countable
bool     g_jury_done = false;  // mode 1 delivers ONE verdict per basket
double   g_j_rsi = 0, g_j_mom = 0, g_j_stoch = 0, g_j_di = 0;
int      c_jury = 0;           // baskets the jury closed
int      c_bail = 0;           // baskets the bail closed as failed breakouts

// HIS CANDLES - open/close per minute from oanda_bars.csv, so colour can come from the same
// chart the volume does. Parallel to g_ov_t/g_ov_v and loaded by the same call.
datetime g_oc_t[];
double   g_oc_o[], g_oc_c[], g_oc_h[], g_oc_l[];
int      g_oc_n = 0;
int      c_noprice = 0;        // structure reads his table could not answer
int      c_nocolour = 0;       // bars his table could not colour

// the basket still being released, when InpSpaceSec > 0
int      g_pend_left  = 0;      // tickets still to place
int      g_pend_side  = 0;
double   g_pend_lots  = 0, g_pend_sl = 0, g_pend_tp = 0;
int      g_pend_dia   = 0;
datetime g_pend_next  = 0;
int      g_pend_gap   = 0;      // seconds between releases

//+------------------------------------------------------------------+
//| The tester overwrites tick_volume with its synthesised tick count |
//| (4/bar) and preserves real_volume. Measured 2026-08-10 with       |
//| TapeProbe: iVolume returned 4 4 4 4 4 while iRealVolume returned  |
//| 572 454 270 174. Every volume rule we owned had been blind.       |
//+------------------------------------------------------------------+
// OANDA volume table, loaded once at init from Common\Files (works in the tester
// too — the tester reads FILE_COMMON, so this source is court-testable).
datetime g_ov_t[];
long     g_ov_v[];
int      g_ov_n = 0;
int      g_ov_miss = 0;          // lookups that fell back to broker volume
datetime g_ov_miss_bar = 0;      // last bar already reported, so one line per bar
datetime g_ov_newest = 0;        // newest minute in the table (freshness telemetry)

void LoadOandaVol() {
   g_ov_n = 0;
   // RETRY (2026-08-21): the writer swaps this file atomically every 60 s, and a
   // read landing inside that swap failed outright — one bar silently on broker
   // volume, logged at 21:46:02. Five quick attempts cover the swap window.
   int h = INVALID_HANDLE;
   for (int _try = 0; _try < 5 && h == INVALID_HANDLE; _try++) {
      h = FileOpen("oanda_vol.csv", FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON |
                                FILE_SHARE_READ | FILE_SHARE_WRITE);
      if (h == INVALID_HANDLE && !MQLInfoInteger(MQL_TESTER)) Sleep(40);
   }
   if (h == INVALID_HANDLE) {
      Print("[DIA] OANDA volume requested but oanda_vol.csv not found — using broker volume");
      return;
   }
   ArrayResize(g_ov_t, 8192); ArrayResize(g_ov_v, 8192);
   while (!FileIsEnding(h)) {
      string ln = FileReadString(h);
      int c = StringFind(ln, ",");
      if (c <= 0) continue;
      datetime t = StringToTime(StringSubstr(ln, 0, c));
      long v = (long)StringToInteger(StringSubstr(ln, c + 1));
      if (t <= 0) continue;
      if (g_ov_n >= ArraySize(g_ov_t)) {
         ArrayResize(g_ov_t, g_ov_n + 4096); ArrayResize(g_ov_v, g_ov_n + 4096);
      }
      g_ov_t[g_ov_n] = t; g_ov_v[g_ov_n] = v; g_ov_n++;
   }
   FileClose(h);
   g_ov_newest = (g_ov_n > 0) ? g_ov_t[g_ov_n - 1] : 0;
   PrintFormat("[DIA] OANDA volume table loaded: %d minutes (newest %s)",
               g_ov_n, TimeToString(g_ov_newest, TIME_DATE | TIME_MINUTES));
}

void LoadOandaBars() {
   g_oc_n = 0;
   if (!InpOandaColour && !InpOandaPrice) return;
   int h = INVALID_HANDLE;
   for (int _try = 0; _try < 5 && h == INVALID_HANDLE; _try++) {
      h = FileOpen("oanda_bars.csv", FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON |
                                     FILE_SHARE_READ | FILE_SHARE_WRITE);
      if (h == INVALID_HANDLE && !MQLInfoInteger(MQL_TESTER)) Sleep(40);
   }
   if (h == INVALID_HANDLE) {
      Print("[DIA] his chart was requested but oanda_bars.csv is missing - colour and structure stay on the broker");
      return;
   }
   ArrayResize(g_oc_t, 8192); ArrayResize(g_oc_o, 8192); ArrayResize(g_oc_c, 8192);
   ArrayResize(g_oc_h, 8192); ArrayResize(g_oc_l, 8192);
   while (!FileIsEnding(h)) {
      string ln = FileReadString(h);
      string p[];
      // time,open,high,low,close,volume
      if (StringSplit(ln, ',', p) < 5) continue;
      datetime t = StringToTime(p[0]);
      if (t <= 0) continue;
      if (g_oc_n >= ArraySize(g_oc_t)) {
         ArrayResize(g_oc_t, g_oc_n + 4096);
         ArrayResize(g_oc_o, g_oc_n + 4096);
         ArrayResize(g_oc_c, g_oc_n + 4096);
         ArrayResize(g_oc_h, g_oc_n + 4096);
         ArrayResize(g_oc_l, g_oc_n + 4096);
      }
      g_oc_t[g_oc_n] = t;
      g_oc_o[g_oc_n] = StringToDouble(p[1]);
      g_oc_h[g_oc_n] = StringToDouble(p[2]);
      g_oc_l[g_oc_n] = StringToDouble(p[3]);
      g_oc_c[g_oc_n] = StringToDouble(p[4]);
      g_oc_n++;
   }
   FileClose(h);
   PrintFormat("[DIA] HIS CANDLES loaded: %d minutes of OANDA open/close for colour", g_oc_n);
}

// His O/H/L/C for one minute, or false when his table does not hold it.
bool OandaOhlcAt(datetime t, double &o, double &h, double &l, double &c) {
   int lo = 0, hi = g_oc_n - 1;
   while (lo <= hi) {
      int mid = (lo + hi) / 2;
      if (g_oc_t[mid] == t) {
         o = g_oc_o[mid]; h = g_oc_h[mid]; l = g_oc_l[mid]; c = g_oc_c[mid];
         return true;
      }
      if (g_oc_t[mid] < t) lo = mid + 1; else hi = mid - 1;
   }
   return false;
}

// +1 green, -1 red, 0 = his table does not hold this minute
int OandaColourAt(datetime t) {
   int lo = 0, hi = g_oc_n - 1;
   while (lo <= hi) {
      int mid = (lo + hi) / 2;
      if (g_oc_t[mid] == t) {
         double d = g_oc_c[mid] - g_oc_o[mid];
         return (d > 0) ? +1 : ((d < 0) ? -1 : 0);
      }
      if (g_oc_t[mid] < t) lo = mid + 1; else hi = mid - 1;
   }
   return 0;
}

long OandaVolAt(datetime t) {          // binary search the sorted table
   int lo = 0, hi = g_ov_n - 1;
   while (lo <= hi) {
      int mid = (lo + hi) / 2;
      if (g_ov_t[mid] == t) return g_ov_v[mid];
      if (g_ov_t[mid] < t) lo = mid + 1; else hi = mid - 1;
   }
   return -1;
}

// ── THE TABLE IS PER-MINUTE; THE CHART NEED NOT BE (2026-09-08) ──────────────────
// Zee: "what if we test our EA on the OANDA, on the 5 minute timeframe instead of 1
// minute. maybe that one is much better due to having a stable trend."
//
// oanda_vol.csv holds ONE ROW PER MINUTE. OandaVolAt(iTime(...)) therefore returns the
// volume of the bar's FIRST MINUTE ONLY. On M1 that is the whole bar and correct; on M5
// it is about a fifth of it — and since every UHV test is a comparison BETWEEN bars,
// each reading a different fifth, the entire ranking would be wrong while every number
// still looked plausible. An M5 court run on that would have answered his question with
// noise.
//
// A bar's volume is the SUM of the minutes it spans. Under strict mode a single missing
// minute voids the whole bar: half a candle of his volume is not his candle.
long OandaVolSpan(datetime t, int mins) {
   if (mins <= 1) return OandaVolAt(t);
   long sum = 0;
   for (int m = 0; m < mins; m++) {
      long v = OandaVolAt(t + m * 60);
      if (v <= 0) {
         if (InpOandaStrict) return -1;   // an incomplete candle is not his candle
         continue;
      }
      sum += v;
   }
   return (sum > 0) ? sum : -1;
}

long BarVolume(int k) {
   if (InpOandaVolume == 1 && g_ov_n > 0) {
      long ov = OandaVolSpan(iTime(_Symbol, PERIOD_CURRENT, k),
                             (int)(PeriodSeconds() / 60));
      if (ov > 0) return ov;
   }
   // THE SILENT FALLBACK, NOW LOUD AND FATAL. Reaching here under strict mode means
   // the table lacks this minute; returning the broker's number would decide a UHV on
   // a feed Zee does not read. -1 propagates as "unreadable" and VolWindowWhole()
   // refuses the setup outright.
   if (InpOandaVolume == 1 && InpOandaStrict) return -1;
   long rv = iRealVolume(_Symbol, PERIOD_CURRENT, k);
   if (rv > 0) return rv;
   return iVolume(_Symbol, PERIOD_CURRENT, k);
}

// EVERY BAR THE DECISION TOUCHES MUST BE HIS. Checking only the UHV would still let
// the neighbour comparisons (loudness, "quieter than the UHV", the 20-bar average)
// read broker numbers, which is the same feed-mixing one level down.
bool VolWindowWhole(int need) {
   if (InpOandaVolume != 1 || !InpOandaStrict) return true;
   if (g_ov_n <= 0) return false;
   for (int q = 1; q <= need; q++)
      if (OandaVolSpan(iTime(_Symbol, PERIOD_CURRENT, q),
                       (int)(PeriodSeconds() / 60)) <= 0) return false;
   return true;
}

// A STALLED BRIDGE IS NOT A QUIET MARKET. It died for 61.8 hours over 5-6 Sep and
// nothing stopped trading; without this the EA would simply have run on broker volume
// the whole time and called the results his.
bool VolFeedFresh() {
   if (InpOandaVolume != 1 || InpVolFreshSec <= 0) return true;
   if (MQLInfoInteger(MQL_TESTER)) return true;      // the tester replays a frozen table
   return (g_ov_newest > 0 && (TimeCurrent() - g_ov_newest) <= InpVolFreshSec);
}

double bOpen(int k) { return iOpen (_Symbol, PERIOD_CURRENT, k); }
double bHigh(int k) { return iHigh (_Symbol, PERIOD_CURRENT, k); }
double bLow(int k) { return iLow  (_Symbol, PERIOD_CURRENT, k); }
double bClose(int k) { return iClose(_Symbol, PERIOD_CURRENT, k); }
// HIS COLOUR, NOT THE BROKER'S (Zee 2026-09-29). Every law that names a red or a green
// candle now reads the same chart the volume comes from. A minute his table does not hold
// falls back to the broker and is counted, so the fallback can never be silent.
int BarColour(int k) {
   if (InpOandaColour && g_oc_n > 0) {
      int c = OandaColourAt(iTime(_Symbol, PERIOD_CURRENT, k));
      if (c != 0) return c;
      c_nocolour++;
   }
   double d = bClose(k) - bOpen(k);
   return (d > 0) ? +1 : ((d < 0) ? -1 : 0);
}
bool IsGreen(int k) { return BarColour(k) > 0; }
bool IsRed(int k) { return BarColour(k) < 0; }
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
// ── LAW 45 — THE TREND IS OVER WHEN THE LAST LOW BREAKS (2026-09-07) ─────────────
//
// Zee: "the EA keeps performing until there occurs the end of a trend. at the end of
// the trend the EA expects the price to go upwards still whereas the price takes a
// turn downwards. that last trade is in much loss ... that last losing trade eats up
// all the profit"
//
// His LAWS.md line 45 already answers this, and the Diamond has never implemented it:
//   "Until when can we trade this strategy? we stop buying, when the last low is
//    broken .. we keep trading until the last low is safe (unbroken below). Whenever
//    a high is broken, the deepest point (the lowest point) is the confirmed higher
//    low."
//
// WHY TrendNow() CANNOT DO THIS JOB. It declares an uptrend dead only once TWO new
// pivot lows have printed and the newer sits under the older — and a pivot needs
// InpPivot bars on each side before it is confirmed at all. At a top the structure
// breaks first and TrendNow() keeps returning +1 through the confirmation lag. That
// lag is the window his losing trade is taken in. Line 45 needs no confirmation: one
// level is broken, buying stops, immediately.
//
// Ported MQL->MQL from BasedOnLaws' CamelTrend(), which has carried this law since
// 2026-08-23 — including the refinement that the guard only ever RISES (once the last
// hump top is taken out, the deepest point since it becomes the new defended low) and
// the exact mirror for shorts.
//
// DEFAULT OFF. A new gate ships dark and earns its way on with receipts.
bool LastLowSafe(int side) {
   if (InpLastLowMode != 2) return true;
   return (side > 0) ? !g_ll_dead_up : !g_ll_dead_dn;
}

// ── THE LATCH (2026-09-07, after the snapshot version scored 0 skips in 2,763 bars) ──
//
// The first implementation asked "is the close under the last low RIGHT NOW" at the
// moment of the breakout — and a breakout is a candle thrusting UP through a level,
// while the guard is a pivot low confirmed at least InpPivot bars earlier. The test was
// evaluated at the one instant it cannot fail: 106 trades, 106 with the gate on, not a
// single refusal.
//
// His line 45 is not a sample, it is a STATE: "we stop buying, WHEN the last low is
// broken .. we KEEP trading UNTIL the last low is safe". Buying stops at the break and
// stays stopped; it resumes only when "a high is broken" and the deepest point since
// becomes the new confirmed higher low. At a trend's end the low breaks, price bounces,
// and the breakout fires on the bounce — which is precisely the trade Zee describes as
// eating the week, and precisely the one a snapshot waves through.
//
// Updated once per CLOSED BAR, before any setup is searched for.
void LastLowUpdate() {
   if (InpLastLowMode != 2) return;
   int p = MathMax(1, InpPivot);
   double hs[64], ls[64];
   int    hidx[64], lidx[64];
   int nh = 0, nl = 0;
   for (int k = InpTrendLook; k >= p + 1; k--) {
      bool ph = true, pl = true;
      for (int q = 1; q <= p; q++) {
         if (bHigh(k) <= bHigh(k - q) || bHigh(k) <= bHigh(k + q)) ph = false;
         if (bLow(k)  >= bLow(k - q)  || bLow(k)  >= bLow(k + q))  pl = false;
      }
      if (ph && nh < 64) { hs[nh] = bHigh(k); hidx[nh] = k; nh++; }
      if (pl && nl < 64) { ls[nl] = bLow(k);  lidx[nl] = k; nl++; }
   }
   if (nh < 2 || nl < 2) return;          // no structure drawn: leave the latch alone

   double defend = ls[nl - 1];
   int    peak_bar = hidx[nh - 1];
   double peak = hs[nh - 1];
   bool taken = false;
   for (int q = peak_bar - 1; q >= 1; q--)
      if (bHigh(q) > peak) { taken = true; break; }
   if (taken) {                            // "whenever a high is broken, the deepest
      double deep = bLow(1);               //  point since is the confirmed higher low"
      for (int q = 1; q <= peak_bar; q++) deep = MathMin(deep, bLow(q));
      if (deep > defend) defend = deep;    // the guard only ever rises
   }
   g_guard = defend;

   // LONG SIDE. Break the defended low by BODY (his line 13 measures breaks by body,
   // "the low must be broken by body not wick") and buying stops. It resumes only when
   // a body closes above the last hump top — a new high broken, a new leg, and by his
   // own sentence a new confirmed higher low underneath it.
   if (!g_ll_dead_up) {
      if (BodyLo(1) < defend) g_ll_dead_up = true;
   } else if (BodyHi(1) > hs[nh - 1]) {
      g_ll_dead_up = false;
   }

   // SHORT MIRROR: selling stops when the defended high is taken by body, and resumes
   // when a body closes below the last trough.
   double defendH = hs[nh - 1];
   if (!g_ll_dead_dn) {
      if (BodyHi(1) > defendH) g_ll_dead_dn = true;
   } else if (BodyLo(1) < ls[nl - 1]) {
      g_ll_dead_dn = false;
   }
}

ENUM_TIMEFRAMES TrendTF() {
   if (InpTrendTF == 5)  return PERIOD_M5;
   if (InpTrendTF == 15) return PERIOD_M15;
   if (InpTrendTF == 3)  return PERIOD_M3;
   if (InpTrendTF == 30) return PERIOD_M30;
   return PERIOD_CURRENT;
}
// structure accessors — identical to b*() when InpTrendTF is 0
// HIS CHART FOR THE STRUCTURE (InpOandaPrice, 2026-09-29). Restricted to M1 because his
// table is one row per minute: on M5 a single row is a fifth of the bar and every pivot would
// be drawn from the wrong extreme while still looking plausible - the same trap OandaVolSpan()
// was written to avoid. A minute his table lacks falls back to the broker and is counted.
bool HisBar(int k, double &o, double &h, double &l, double &c) {
   if (!InpOandaPrice || g_oc_n == 0) return false;
   // TrendTF() returns PERIOD_CURRENT (0), NOT PERIOD_M1 (1), when InpTrendTF is 0 - so the
   // first version of this guard refused every bar and InpOandaPrice was a silent no-op. It
   // returned a result identical to the control TO THE DOLLAR, which is what gave it away.
   // Resolve PERIOD_CURRENT to the chart's actual period before comparing.
   ENUM_TIMEFRAMES tf = TrendTF();
   if (tf == PERIOD_CURRENT) tf = (ENUM_TIMEFRAMES)Period();
   if (tf != PERIOD_M1) return false;
   if (OandaOhlcAt(iTime(_Symbol, PERIOD_M1, k), o, h, l, c)) return true;
   c_noprice++;
   return false;
}
double tHigh(int k)  { double o,h,l,c; if (HisBar(k,o,h,l,c)) return h;
                       return iHigh (_Symbol, TrendTF(), k); }
double tLow(int k)   { double o,h,l,c; if (HisBar(k,o,h,l,c)) return l;
                       return iLow  (_Symbol, TrendTF(), k); }
double tOpen(int k)  { double o,h,l,c; if (HisBar(k,o,h,l,c)) return o;
                       return iOpen (_Symbol, TrendTF(), k); }
double tClose(int k) { double o,h,l,c; if (HisBar(k,o,h,l,c)) return c;
                       return iClose(_Symbol, TrendTF(), k); }
double tBodyHi(int k) { return MathMax(tOpen(k), tClose(k)); }
double tBodyLo(int k) { return MathMin(tOpen(k), tClose(k)); }

// ── CAMEL HUMPS, DRAWN — his line 7 in the present tense ─────────────────────────
// Ported from BasedOnLaws CamelTrend(). Returns +1/-1/0 and hands back the level his
// line 45 defends. The guard only ever RISES for a long (falls for a short): once the
// newest hump top is taken out, the deepest point since it becomes the confirmed
// higher low.
int CamelTrendD(double &lastLow) {
   int p = MathMax(1, InpPivot);
   double hs[64], ls[64];
   int    hidx[64], lidx[64];
   int nh = 0, nl = 0;
   for (int k = InpTrendLook; k >= p + 1; k--) {          // oldest -> newest
      bool ph = true, pl = true;
      for (int q = 1; q <= p; q++) {
         if (tHigh(k) <= tHigh(k - q) || tHigh(k) <= tHigh(k + q)) ph = false;
         if (tLow(k)  >= tLow(k - q)  || tLow(k)  >= tLow(k + q))  pl = false;
      }
      if (ph && nh < 64) { hs[nh] = tHigh(k); hidx[nh] = k; nh++; }
      if (pl && nl < 64) { ls[nl] = tLow(k);  lidx[nl] = k; nl++; }
   }
   lastLow = 0;
   if (nh < 2 || nl < 2) return 0;

   bool higher_low   = ls[nl - 1] > ls[nl - 2];
   bool rising_tops  = hs[nh - 1] > hs[nh - 2];
   bool broke_top = false;                    // "we are BREAKING ABOVE previous highs"
   for (int q = hidx[nh - 1] - 1; q >= 1; q--)
      if (tBodyHi(q) > hs[nh - 1]) { broke_top = true; break; }
   bool higher_high = (InpHighTest == 0) ? rising_tops
                    : (InpHighTest == 1) ? broke_top
                                         : (broke_top || rising_tops);

   bool lower_high      = hs[nh - 1] < hs[nh - 2];
   bool falling_bottoms = ls[nl - 1] < ls[nl - 2];
   bool broke_bottom = false;
   for (int q = lidx[nl - 1] - 1; q >= 1; q--)
      if (tBodyLo(q) < ls[nl - 1]) { broke_bottom = true; break; }
   bool lower_low = (InpHighTest == 0) ? falling_bottoms
                  : (InpHighTest == 1) ? broke_bottom
                                       : (broke_bottom || falling_bottoms);

   bool up   = (higher_high && higher_low);
   bool down = (lower_low   && lower_high);
   if (up == down) return 0;

   if (up) {
      double defend = ls[nl - 1];
      int    peak_bar = hidx[nh - 1];
      double peak = hs[nh - 1];
      bool taken = false;
      for (int q = peak_bar - 1; q >= 1; q--)
         if (tHigh(q) > peak) { taken = true; break; }
      if (taken) {
         double deep = tLow(1);
         for (int q = 1; q <= peak_bar; q++) deep = MathMin(deep, tLow(q));
         if (deep > defend) defend = deep;
      }
      lastLow = defend;
      return +1;
   }
   double defendH = hs[nh - 1];
   int    trough_bar = lidx[nl - 1];
   double trough = ls[nl - 1];
   bool broken = false;
   for (int q = trough_bar - 1; q >= 1; q--)
      if (tLow(q) < trough) { broken = true; break; }
   if (broken) {
      double peakSince = tHigh(1);
      for (int q = 1; q <= trough_bar; q++) peakSince = MathMax(peakSince, tHigh(q));
      if (peakSince < defendH) defendH = peakSince;
   }
   lastLow = defendH;
   return -1;
}

// His "extra confirmation" as a trend in its own right: the slope of EMA-5 over N bars.
// Scored +624 on BasedOnLaws where the stale-pivot structure scored +296.
int TrendByEma(double &lastLow) {
   lastLow = 0;
   int n = MathMax(1, InpEmaSlopeBars);
   double e0 = 0, e1 = 0;
   int h = iMA(_Symbol, PERIOD_CURRENT, 5, 0, MODE_EMA, PRICE_CLOSE);
   if (h == INVALID_HANDLE) return 0;
   double buf[];
   if (CopyBuffer(h, 0, 1, n + 1, buf) < n + 1) return 0;
   e0 = buf[n];          // newest
   e1 = buf[0];          // n bars older
   int p = MathMax(1, InpPivot);
   for (int k = p + 1; k <= InpTrendLook; k++) {   // the level line 45 defends
      bool bot = true;
      for (int q = 1; q <= p && bot; q++)
         if (bLow(k) >= bLow(k - q) || bLow(k) >= bLow(k + q)) bot = false;
      if (bot) { lastLow = bLow(k); break; }
   }
   if (e0 > e1) return +1;
   if (e0 < e1) return -1;
   return 0;
}

// Counts the trend's completed swings. Runs once per CLOSED BAR, before any gate, so
// the tally is right even on bars where the EA would not have traded anyway.
void HumpUpdate() {
   if (InpMaxHumps <= 0) return;
   double ll = 0;
   int t = TrendEngineFwd(ll);
   // ZERO IS NOT A NEW TREND — it is the absence of a reading, and both engines return
   // it constantly DURING a retracement, which is exactly when a hump is forming. The
   // first version reset on any change including t==0, so every hump erased its own
   // count and the tally never passed 1: budgets 2..8 were byte-identical to "off".
   // Only a genuine direction FLIP starts a new budget; a flicker to 0 is ignored and
   // the count keeps running against the direction last confirmed, which is what his
   // drawing shows — the trend persists through its own pullbacks.
   if (t != 0 && t != g_hump_dir) {
      if (InpVerbose && g_hump_dir != 0)
         PrintFormat("[HUMP] flip %s -> %s after %d humps",
                     (g_hump_dir > 0 ? "UP" : "DN"), (t > 0 ? "UP" : "DN"), g_hump_n);
      g_hump_dir = t;
      g_hump_n = 0;
      g_hump_last = 0;
   }
   int dir = g_hump_dir;
   if (dir == 0) return;
   int p = MathMax(1, InpPivot);
   for (int k = p + 1; k <= InpTrendLook; k++) {
      bool ok = true;
      for (int q = 1; q <= p && ok; q++) {
         if (dir > 0) {
            if (tHigh(k) <= tHigh(k - q) || tHigh(k) <= tHigh(k + q)) ok = false;
         } else {
            if (tLow(k) >= tLow(k - q) || tLow(k) >= tLow(k + q)) ok = false;
         }
      }
      if (!ok) continue;
      // the NEWEST confirmed swing only; older ones were counted when they printed
      datetime pt = iTime(_Symbol, TrendTF(), k);
      if (pt != g_hump_last) {
         g_hump_last = pt;
         g_hump_n++;
         if (InpVerbose)
            PrintFormat("[HUMP] %s hump %d at %s", (dir > 0 ? "UP" : "DN"),
                        g_hump_n, TimeToString(pt, TIME_MINUTES));
      }
      break;
   }
}

int TrendEngine(double &lastLow) {
   if (InpTrendMode == 1) return CamelTrendD(lastLow);
   if (InpTrendMode == 2) return TrendByEma(lastLow);
   lastLow = 0;
   return TrendNow();
}

int TrendEngineFwd(double &lastLow) { return TrendEngine(lastLow); }

int TrendNow() {
   double highs[]; double lows[];
   ArrayResize(highs, 0); ArrayResize(lows, 0);
   for (int k = InpTrendLook; k >= InpPivot + 1; k--) {
      bool ph = true, pl = true;
      for (int d = 1; d <= InpPivot; d++) {
         if (tHigh(k) < tHigh(k - d) || tHigh(k) < tHigh(k + d)) ph = false;
         if (tLow(k) > tLow(k - d) || tLow(k) > tLow(k + d)) pl = false;
      }
      if (ph) { int n = ArraySize(highs); ArrayResize(highs, n + 1); highs[n] = tHigh(k); }
      if (pl) { int n = ArraySize(lows);  ArrayResize(lows,  n + 1); lows[n]  = tLow(k); }
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
   // ---- HIS TEXT, FOLLOWED IN ORDER (InpRetraceFix, 2026-09-29) --------------------------
   // "a valid retracement starts when the last green candle in an uptrend, that candle's low
   //  is broken by the next or next few red candles downwards ... the low must be broken by
   //  body not wick."
   // The old branch below returned the MOST RECENT breaking body, which made the UHV window
   // the tail of the pullback: origin == UHV in 65% of 155 logged fires.
   if (InpRetraceFix) {
      // 1. where the impulse ended - the extreme the pullback is pulling back from
      int ext = -1; double best = 0;
      for (int k = 2; k <= InpRetraceBack; k++) {
         double v = wantRed ? bHigh(k) : bLow(k);
         if (ext < 0 || (wantRed ? (v > best) : (v < best))) { best = v; ext = k; }
      }
      if (ext < 2) return -1;
      // 2. "the last green candle in an uptrend" - at or just before that extreme
      int g = -1;
      for (int k = ext; k <= ext + 8 && k <= InpRetraceBack + 8; k++) {
         if (wantRed ? IsGreen(k) : IsRed(k)) { g = k; break; }
      }
      if (g < 2) return -1;
      double lvl = wantRed ? bLow(g) : bHigh(g);
      // 3. the FIRST body to break it. Walking from the oldest bar after g toward the
      //    present, so the match is where the retracement BEGAN, not where it ended.
      for (int k = g - 1; k >= 1; k--) {
         if (wantRed ? !IsRed(k) : !IsGreen(k)) continue;
         bool broke = wantRed ? (BodyLo(k) < lvl) : (BodyHi(k) > lvl);
         if (broke) return k;
      }
      return -1;
   }
   for (int k = 1; k <= InpRetraceBack; k++) {
      if (wantRed  && !IsRed(k))   continue;
      if (!wantRed && !IsGreen(k)) continue;
      int prev = -1;
      for (int j = k + 1; j <= k + 8; j++) {
         if (wantRed ? IsGreen(j) : IsRed(j)) { prev = j; break; }
      }
      if (prev < 0) continue;
      if (wantRed) { if (BodyLo(k) < bLow(prev)) return k; }
      else         { if (BodyHi(k) > bHigh(prev)) return k; }
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
int FindUhv(int origin, int side) {
   bool wantRed = (side > 0);
   int best = -1; long bestv = -1;
   for (int k = origin; k >= 1; k--) {
      if (wantRed  && !IsRed(k))   continue;
      if (!wantRed && !IsGreen(k)) continue;
      long v = BarVolume(k);
      if (v > bestv) { bestv = v; best = k; }
   }
   if (best < 1) return -1;
   double rng = bHigh(best) - bLow(best);
   if (rng <= 0 || MathAbs(bClose(best) - bOpen(best)) / rng < InpUhvBodyMin) return -1;
   if (BarVolume(best + 1) > bestv) return -1;      // louder than its neighbours
   if (best > 1 && BarVolume(best - 1) > bestv) return -1;
   return best;
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
   if (uhv <= 1) return false;                       // B cannot be Y
   bool wantGreen = (side > 0);
   // the FIRST true crossing must be bar 1 — if an earlier bar already crossed,
   // this one is late and he would not mark it
   for (int k = uhv - 1; k >= 1; k--) {
      if (wantGreen  && !IsGreen(k)) continue;
      if (!wantGreen && !IsRed(k))   continue;
      bool crossed = wantGreen ? (BodyHi(k) > bHigh(uhv)) : (BodyLo(k) < bLow(uhv));
      if (!crossed) continue;
      if (BarVolume(k) >= BarVolume(uhv)) return false;   // must be quieter
      // HIS CLAUSE (a): the breakout is a MOMENTUM candle. Checked on the crossing bar, which
      // is the candle his page is describing - not on the UHV, where InpUhvBodyMin sits.
      if (InpBreakBodyMin > 0) {
         double rngK = bHigh(k) - bLow(k);
         if (rngK <= 0) return false;
         if (MathAbs(bClose(k) - bOpen(k)) / rngK < InpBreakBodyMin) return false;
      }
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

double AvgVolBefore(int k) {
   double sum = 0; int n = 0;
   for (int i = k + 1; i <= k + 20; i++) { sum += (double)BarVolume(i); n++; }
   return (n > 0) ? sum / n : 0.0;
}

int g_dia_mask = 0;      // which laws held on the setup just judged

int DiamondsFor(int origin, int uhv, int side) {
   g_dia_mask = 0;
   int d = 0;
   // Law 1 — the sweep: did price poke beyond the prior extreme on the way in?
   double hi = bHigh(uhv), lo = bLow(uhv);
   for (int k = uhv + 1; k <= uhv + 20; k++) {
      if (side > 0 && bLow(k) < lo) { d++; g_dia_mask |= 4; break; }
      if (side < 0 && bHigh(k) > hi) { d++; g_dia_mask |= 4; break; }
   }
   // Law 3 — the EMA-5 close: the breakout candle closed decisively past the mean
   double e5 = Ema5(1);
   if (side > 0 && IsGreen(1) && bClose(1) > e5 + 0.10) { d++; g_dia_mask |= 8; }
   if (side < 0 && IsRed(1)   && bClose(1) < e5 - 0.10) { d++; g_dia_mask |= 8; }
   // Law 5 — the wick and the volume
   double rng = MathMax(bHigh(1) - bLow(1), 1e-9);
   double wick = (side > 0) ? (bHigh(1) - MathMax(bOpen(1), bClose(1))) / rng
                            : (MathMin(bOpen(1), bClose(1)) - bLow(1)) / rng;
   if (wick <= 0.25 && BarVolume(1) < BarVolume(uhv)) { d++; g_dia_mask |= 16; }
   // ── LAW 1 — the UHV is LOUD against its own neighbourhood (volume-dependent)
   {
      double av = AvgVolBefore(uhv);
      if (av > 0 && (double)BarVolume(uhv) >= av * InpDiaLoudMult) g_dia_mask |= 1;
   }
   // ── LAW 7 — SELLING CLIMAX: the UHV is the widest bar of the last 7
   {
      double r7 = bHigh(uhv) - bLow(uhv);
      bool widest = true;
      for (int i = uhv + 1; i <= uhv + 7; i++)
         if ((bHigh(i) - bLow(i)) > r7) { widest = false; break; }
      if (widest) g_dia_mask |= 2;
   }
   // ── REF-8 BREAK: the 8-bar reference extreme was taken out
   {
      int a8 = -1; double ext8 = 0;
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
         if (ref8 > 0)
            for (int k = 1; k < a8; k++) {
               if (side < 0 && bHigh(k) > bHigh(ref8)) { g_dia_mask |= 32; break; }
               if (side > 0 && bLow(k)  < bLow(ref8))  { g_dia_mask |= 32; break; }
            }
      }
   }
   // ── DEFENDED LEVEL: 2+ prior bars tapped the trigger and closed back
   {
      double trig = (side > 0) ? bHigh(uhv) : bLow(uhv);
      int defenses = 0;
      for (int k = uhv + 1; k <= uhv + 60; k++) {
         if (side < 0 && bLow(k)  <= trig + 0.30 && bClose(k) > trig) defenses++;
         if (side > 0 && bHigh(k) >= trig - 0.30 && bClose(k) < trig) defenses++;
      }
      if (defenses >= 2) g_dia_mask |= 64;
   }
   // ── LATE HUMP: 4+ humps already in this staircase
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
         else break;
      }
      if (humps >= 4) g_dia_mask |= 128;
   }
   return d;
}

int ClicksFor(int d) { return (d <= 1) ? 1 : ((d == 2) ? 2 : 3); }

//+------------------------------------------------------------------+
int OnInit() {
   if (InpOandaVolume == 1) LoadOandaVol();
   LoadOandaBars();               // his open/close, for InpOandaColour
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   // The jury's handles. Created once - creating an indicator per tick is the classic way
   // to make a tester crawl, and handles are cheap to hold.
   if (InpJuryMode > 0) {
      h_jrsi   = iRSI(_Symbol, PERIOD_CURRENT, InpJuryRsiN, PRICE_CLOSE);
      h_jmom   = iMomentum(_Symbol, PERIOD_CURRENT, InpJuryMomN, PRICE_CLOSE);
      h_jstoch = iStochastic(_Symbol, PERIOD_CURRENT, InpJuryStochK, InpJuryStochD,
                             InpJuryStochS, MODE_SMA, STO_LOWHIGH);
      h_jadx   = iADX(_Symbol, PERIOD_CURRENT, InpJuryAdxN);
      PrintFormat("[DIA] JURY mode %d: vote %d bars after entry, %d of 4 against closes "
                  "the basket (rsi %s mom %s stoch %s adx %s)",
                  InpJuryMode, InpJuryBars, InpJuryVotes,
                  h_jrsi   != INVALID_HANDLE ? "ok" : "FAILED",
                  h_jmom   != INVALID_HANDLE ? "ok" : "FAILED",
                  h_jstoch != INVALID_HANDLE ? "ok" : "FAILED",
                  h_jadx   != INVALID_HANDLE ? "ok" : "FAILED");
   }
   // The load fingerprint. Hot-reload of an attached chart is UNRELIABLE, so this line is
   // how a deploy is verified — if the Experts tab does not say v1.10 with stack x2, the
   // chart is still running the old binary and the change did NOT take.
   // KEEP THIS STRING IN STEP WITH #property version. It said v1.14 for the whole of
   // the v1.15 ship (2026-09-06) and the live log therefore misreported which machine
   // was trading — the one thing the load fingerprint exists to settle.
   // Every value below is READ BACK FROM THE INPUTS, never hardcoded, so the line cannot
   // claim a configuration the binary is not actually running - which is the one job a load
   // fingerprint has.
   PrintFormat("[DIA] ZeeUHV v1.27 - pivot %d - retraceFix %s - humpBudget %d - sweep %s"
               " - OANDA volume %s - stop %.2f beyond retracement - TP %.1f - hold %.0fm"
               " - %.2f/ticket, stack x%d (max %d tickets = %.2f lots) - magic %d",
               InpPivot, (InpRetraceFix ? "ON" : "off"), InpMaxHumps,
               (InpReqLaws == 0 ? "off" : "REQUIRED"),
               (InpOandaStrict ? "STRICT" : "loose"),
               InpStructStop, InpTargetPts, InpMaxHoldMin,
               InpLots, MathMax(1, InpStackMult),
               4 * MathMax(1, InpStackMult), 4 * MathMax(1, InpStackMult) * InpLots,
               InpMagicNumber);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int r) {
   if (h_jrsi   != INVALID_HANDLE) IndicatorRelease(h_jrsi);
   if (h_jmom   != INVALID_HANDLE) IndicatorRelease(h_jmom);
   if (h_jstoch != INVALID_HANDLE) IndicatorRelease(h_jstoch);
   if (h_jadx   != INVALID_HANDLE) IndicatorRelease(h_jadx);
   PrintFormat("[DIA] deinit reason=%d - jury closed %d, bail closed %d, "
               "his table missed %d colours and %d structure reads",
               r, c_jury, c_bail, c_nocolour, c_noprice);
   // THE FUNNEL, in the order the gates are actually asked. Every bar TryFire judged is
   // accounted for exactly once, so these must sum to c_bars (minus the per-side retries
   // in the last three, which can fire twice when InpRequireTrend is off).
   PrintFormat("[FUNNEL] bars=%d | session=%d maxopen=%d cooldown=%d gap=%d stale=%d "
               "volhole=%d humps=%d law45=%d ranging=%d | noorigin=%d nouhv=%d nobreak=%d "
               "laws=%d | FIRED=%d",
               c_bars, c_session, c_maxopen, c_cooldown, c_gap, c_stale, g_ov_miss,
               c_humps, c_law45, c_ranging, c_noorigin, c_nouhv, c_nobreak, c_laws, c_fired);
}

//+------------------------------------------------------------------+
void TryFire() {
   c_bars++;
   LastLowUpdate();            // his line 45 is a STATE — updated every closed bar,
                               // not sampled at the moment of a breakout
   HumpUpdate();               // and so is the hump tally
   // THE BUDGET IS SPENT. Checked before the session and before every law, because a
   // refusal here is about the trend's AGE, not about the setup in front of us.
   if (InpMaxHumps > 0 && g_hump_n >= InpMaxHumps) {
      c_humps++;
      if (InpVerbose)
         PrintFormat("[DIA] [SKIP] hump budget spent — %d humps on this %s trend",
                     g_hump_n, (g_hump_dir > 0 ? "up" : "down"));
      return;
   }
   // HIS LINE 47. Checked first: a session refusal is not a law refusal, and mixing
   // the two would make the skip counters lie about why the EA stood down.
   if (InpNyOnly) {
      MqlDateTime _t; TimeToStruct(TimeCurrent(), _t);
      if (_t.hour < InpNyFromHour || _t.hour >= InpNyToHour) { c_session++; return; }
   }
   if (OpenCount() >= InpMaxOpen) { c_maxopen++; return; }
   if (g_last_fire > 0 &&
       (TimeCurrent() - g_last_fire) < InpCooldownBar * PeriodSeconds()) { c_cooldown++; return; }
   if (!WindowContinuous(InpTrendLook + 5)) {
      c_gap++;
      if (InpVerbose) Print("[DIA] [SKIP] gap in lookback");
      return;
   }
   // HIS EYE OR NO TRADE — checked BEFORE any law is consulted, so a feed problem can
   // never be mistaken for the laws refusing a setup.
   if (!VolFeedFresh()) {
      c_stale++;
      static datetime _stale_said = 0;
      datetime _b = iTime(_Symbol, PERIOD_CURRENT, 0);
      if (_b != _stale_said) {                       // one line per bar, not per tick
         _stale_said = _b;
         PrintFormat("[DIA] [SKIP] OANDA volume %d s stale (bridge stalled?) — "
                     "standing down rather than judging on broker volume",
                     (int)(TimeCurrent() - g_ov_newest));
      }
      return;
   }
   if (!VolWindowWhole(InpTrendLook + InpRetraceBack + 8)) {
      g_ov_miss++;
      if (InpVerbose) Print("[DIA] [SKIP] OANDA table has a hole in the window");
      return;
   }
//  THE 40% GATE, under test (Zee 2026-08-10: "can u check what's stopping us from
//  taking every single opportunity we get?"). Measured on real gold, the structural
//  trend reads FLAT 40.3% of the time, and update_gate()'s "flat -> the ghost waits"
//  forbids BOTH sides for those four hours in ten — before any setup rule is even
//  consulted. It is the single largest brake on trade count, and it was assumed, never
//  tested. With InpRequireTrend=false a ranging tape may still trade: we simply try
//  both sides and take whichever completes a lawful setup.
   double lastLow = 0;
   int t = TrendEngine(lastLow);
   g_guard = lastLow;
   // HIS LINE 45, mode 1: the snapshot BasedOnLaws ships — refuse while price sits the
   // wrong side of the defended level. Mode 2 is the latch (LastLowUpdate). Mode 0 off.
   if (InpLastLowMode == 1 && lastLow > 0 && t != 0) {
      if ((t > 0 && bClose(1) < lastLow) || (t < 0 && bClose(1) > lastLow)) {
         c_law45++;
         if (InpVerbose)
            PrintFormat("[DIA] [SKIP] law 45 snapshot — guard %.2f, close %.2f",
                        lastLow, bClose(1));
         return;
      }
   }
   int sides[2]; int nsides = 0;
   if (t != 0) { sides[0] = t; nsides = 1; }
   else if (!InpRequireTrend) { sides[0] = +1; sides[1] = -1; nsides = 2; }
   else { c_ranging++; if (InpVerbose) Print("[DIA] [SKIP] ranging — his setup needs a trend"); return; }

   int origin = -1, uhv = -1, side = 0;
   for (int si = 0; si < nsides; si++) {
      int try_side = sides[si];
      int o = RetracementOrigin(try_side);
      if (o < 0) { c_noorigin++; continue; }
      int u = FindUhv(o, try_side);
      if (u < 0) { c_nouhv++; continue; }
      if (!BreakoutIsBar1(u, try_side)) { c_nobreak++; continue; }
      // HIS LINE 45, checked last: a lawful setup on a side whose defended level has
      // already broken is exactly the trade that ends the run. Inside the loop, so
      // blocking one side still lets the other be tried.
      if (!LastLowSafe(try_side)) {
         c_law45++;
         if (InpVerbose)
            PrintFormat("[DIA] [SKIP] law 45 — %s guard %.2f broken by close %.2f",
                        (try_side > 0 ? "last low" : "last high"), g_guard, bClose(1));
         continue;
      }
      origin = o; uhv = u; side = try_side; break;
   }
   if (side == 0) {
      if (InpVerbose && t != 0) Print("[DIA] [SKIP] no lawful setup on the allowed side");
      return;
   }
   t = side;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double px = (t > 0) ? ask : bid;
   double sl = (t > 0) ? px - InpStopPts   : px + InpStopPts;
   // HIS LINE 42 — the stop belongs under the retracement, not at a fixed distance the
   // market has never heard of. Still one price shared by the whole basket, because the
   // target is too, and splitting only one of them would change two things at once.
   if (InpStructStop > 0) {
      // InpSlMode 1: "the deeper low amongst the lows if there's more than one
      // confirmed low" — the level the trend engine is defending, which by his line 45
      // only ever rises. Falls back to the retracement extreme when the structure has
      // not drawn one, so the stop is never left undefined.
      double ext = RetraceExtreme(origin, t);
      if (InpSlMode == 1 && g_guard > 0) {
         ext = (t > 0) ? MathMin(ext, g_guard) : MathMax(ext, g_guard);
      }
      sl = (t > 0) ? ext - InpStructStop : ext + InpStructStop;
   }
   double tp = (t > 0) ? px + InpTargetPts : px - InpTargetPts;
   // HIS 1:2. Measured from the SAME entry the stop is, so "1:2" is the real distance
   // to the real stop rather than a nominal figure.
   if (InpTargetR > 0) {
      double risk = MathAbs(px - sl);
      if (risk > 0) tp = (t > 0) ? px + InpTargetR * risk : px - InpTargetR * risk;
   }

   // DiamondsFor also fills g_dia_mask, so it must run even when diamonds are off —
   // otherwise a law gate would be judging a stale mask from the previous setup.
   int dia = DiamondsFor(origin, uhv, t);
   if (!InpUseDiamonds) dia = 0;
   // THE LAWS AS A GATE (2026-08-31). Every required bit must hold or the setup is
   // refused outright — which is the opposite of how these laws have ever been used.
   if (InpReqLaws != 0 && (g_dia_mask & InpReqLaws) != InpReqLaws) {
      c_laws++;
      if (InpVerbose)
         PrintFormat("[DIA] [SKIP] laws %d required, setup had %d", InpReqLaws, g_dia_mask);
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
   int tickets = InpStackLots ? (1 + MathMax(0, MathMin(dia, 3))) * MathMax(1, InpStackMult) : 1;
   // ONE ORDER: same total size, placed in a single round trip, so there is no spacing
   // and every lot carries the first fill's risk-reward.
   double oneLots = 0;
   if (InpOneOrder) {
      oneLots = NormalizeDouble(InpLots * tickets, 2);
      if (InpMaxRisk > 0 && oneLots > InpMaxRisk + 1e-9)
         oneLots = NormalizeDouble(InpMaxRisk, 2);
      tickets = 1;
   }
   double placed = 0, total = 0;
   for (int q = 0; q < tickets; q++) {
      double lots = NormalizeDouble(InpLots + InpStackStep * q, 2);
      if (!InpStackLots) lots = NormalizeDouble(InpLots * (InpUseDiamonds ? ClicksFor(dia) : 1), 2);
      if (InpOneOrder) lots = oneLots;
      // 1e-9 slack: 0.20 + 0.10 evaluates to 0.30000000000000004 in doubles, so a cap
      // of 0.30 silently behaved like 0.20 and the sweep returned identical numbers for
      // both. Floating point must never quietly move a risk limit.
      if (InpMaxRisk > 0 && total + lots > InpMaxRisk + 1e-9) break;
      // Zee, 2026-08-12: "measure the diamond's earnings and decide which diamond is
      // the most earner". The count must survive into the deal record to be grouped
      // later, and the comment is the only field that travels with it.
      string tag = StringFormat("zdia_%s_D%d", (t > 0 ? "buy" : "sell"), dia);
      bool ok = (t > 0) ? trade.Buy (lots, _Symbol, 0, sl, tp, tag)
                        : trade.Sell(lots, _Symbol, 0, sl, tp, tag);
      if (!ok) break;
      total += lots; placed += 1;
      if (!InpStackLots) break;
      if (InpSpaceSec > 0 && tickets > 1) {
         // hand the remainder to ReleasePending, evenly spread over InpSpaceSec
         g_pend_left = tickets - 1;
         g_pend_side = t;
         g_pend_lots = lots;
         g_pend_sl   = sl;
         g_pend_tp   = tp;
         g_pend_dia  = dia;
         g_pend_gap  = (int)MathMax(1, MathRound(InpSpaceSec / (double)(tickets - 1)));
         g_pend_next = TimeCurrent() + g_pend_gap;
         break;
      }
   }
   if (placed > 0) {
      c_fired++;
      g_last_fire = TimeCurrent();
      g_fail_side = t; g_against = 0;   // a fresh basket to watch
      JurySnapshot(t);                  // and a fresh reading for the jury
      // 2026-08-26: it used to print UHV as a BAR SHIFT ("UHV 7"), which is
      // meaningless once the trade is over — the cockpit's forensic button could not
      // resolve a single Diamond fire. With eleven variants running, inspecting a fire
      // IS the experiment, so it now stamps the three anchors as TIMES in the same
      // [LAWX] grammar the laws EA uses, which law_trade_diagram.py already parses.
      PrintFormat("[LAWX] %s | origin %s %s (retracement began the bar after) | "
                  "UHV %s (vol %d, %s %.2f) | breakout %s (close %.2f, vol %d) | "
                  "entry %.2f stop %.2f target %.2f | hump %d | %d diamond(s) m%d -> %d ticket(s), %.2f lots",
                  t > 0 ? "BUY " : "SELL",
                  t > 0 ? "green" : "red",
                  TimeToString(iTime(_Symbol, PERIOD_CURRENT, origin), TIME_MINUTES),
                  TimeToString(iTime(_Symbol, PERIOD_CURRENT, uhv), TIME_MINUTES),
                  (int)BarVolume(uhv),
                  (t > 0 ? "high" : "low "),
                  (t > 0 ? bHigh(uhv) : bLow(uhv)),
                  TimeToString(iTime(_Symbol, PERIOD_CURRENT, 1), TIME_MINUTES),
                  bClose(1), (int)BarVolume(1),
                  px, sl, tp, g_hump_n, dia, g_dia_mask, (int)placed, total);
   }
}

// Close the whole basket once the tape has argued against it N candles running.
// The deepest point of the retracement we are trading — his "last low" for a buy,
// the mirror high for a sell. Walks from the origin down to the breakout bar.
double RetraceExtreme(int origin, int side) {
   double v = (side > 0) ? bLow(1) : bHigh(1);
   for (int k = 1; k <= origin; k++)
      v = (side > 0) ? MathMin(v, bLow(k)) : MathMax(v, bHigh(k));
   return v;
}

void BailCheck() {
   if (InpBailSec <= 0) return;
   int closed = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if ((double)(TimeCurrent() - opened) < InpBailSec) continue;   // not yet due
      long   ty  = PositionGetInteger(POSITION_TYPE);
      double ent = PositionGetDouble(POSITION_PRICE_OPEN);
      double now = PositionGetDouble(POSITION_PRICE_CURRENT);
      // AHEAD IN PRICE, measured the way the trade is facing. Deliberately price and not
      // POSITION_PROFIT: profit carries the spread and the ticket size, and this must mean
      // the same thing for every ticket in a stacked basket.
      double ahead = (ty == POSITION_TYPE_BUY) ? (now - ent) : (ent - now);
      if (ahead >= InpBailAt) continue;                              // it IS working
      if (trade.PositionClose(tk)) closed++;
   }
   if (closed > 0) {
      c_bail++;
      if (InpVerbose)
         PrintFormat("[DIA] BAIL - breakout not working after %ds, closed %d ticket(s)",
                     InpBailSec, closed);
   }
}

// ONE BUFFER VALUE, or false. A handle can be INVALID (jury off, or a failed create) and
// CopyBuffer legitimately fails while an indicator is still warming up at the start of a
// test - in both cases that indicator simply does not vote, rather than voting zero.
bool JuryVal(int h, int buf, int shift, double &out) {
   if (h == INVALID_HANDLE) return false;
   double a[];
   if (CopyBuffer(h, buf, shift, 1, a) != 1) return false;
   out = a[0];
   return true;
}

// Take the reading the verdict will be compared against. Called the moment a basket opens.
void JurySnapshot(int t) {
   g_jury_side = t;
   g_jury_bar  = iTime(_Symbol, PERIOD_CURRENT, 0);
   g_jury_done = false;
   g_j_rsi = 0; g_j_mom = 0; g_j_stoch = 0; g_j_di = 0;
   if (InpJuryMode <= 0) return;
   double d1 = 0, d2 = 0;
   JuryVal(h_jrsi,   0, 1, g_j_rsi);
   JuryVal(h_jmom,   0, 1, g_j_mom);
   JuryVal(h_jstoch, 0, 1, g_j_stoch);
   if (JuryVal(h_jadx, 1, 1, d1) && JuryVal(h_jadx, 2, 1, d2)) g_j_di = d1 - d2;
}

void JuryCheck() {
   if (InpJuryMode <= 0 || g_jury_side == 0 || g_jury_done) return;
   if (OpenCount() == 0) { g_jury_side = 0; return; }
   datetime b = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (b <= g_jury_bar) return;
   int since = (int)((b - g_jury_bar) / PeriodSeconds());
   if (since < InpJuryBars) return;

   int t = g_jury_side, against = 0, voted = 0;
   double v = 0, d1 = 0, d2 = 0;
   // A vote is the DIRECTION OF TRAVEL since entry, not a level. "Moving in our favor" is
   // his phrase and it is a derivative, so an overbought RSI that is still rising is
   // agreement - which is the whole point on a breakout.
   if (JuryVal(h_jrsi, 0, 1, v))
      { voted++; if ((t > 0 && v < g_j_rsi) || (t < 0 && v > g_j_rsi)) against++; }
   if (JuryVal(h_jmom, 0, 1, v))
      { voted++; if ((t > 0 && v < g_j_mom) || (t < 0 && v > g_j_mom)) against++; }
   if (JuryVal(h_jstoch, 0, 1, v))
      { voted++; if ((t > 0 && v < g_j_stoch) || (t < 0 && v > g_j_stoch)) against++; }
   if (JuryVal(h_jadx, 1, 1, d1) && JuryVal(h_jadx, 2, 1, d2)) {
      voted++; double di = d1 - d2;
      if ((t > 0 && di < g_j_di) || (t < 0 && di > g_j_di)) against++;
   }
   if (InpJuryMode == 1) g_jury_done = true;   // asked once, whichever way it went
   if (voted == 0 || against < InpJuryVotes) return;

   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      trade.PositionClose(tk);
   }
   c_jury++;
   if (InpVerbose)
      PrintFormat("[DIA] JURY closed the basket - %d of %d indicators against after %d bars",
                  against, voted, since);
   g_jury_side = 0;
}

void FailCandleCheck() {
   if (InpFailCandles <= 0 || g_fail_side == 0) return;
   if (OpenCount() == 0) { g_against = 0; return; }
   static datetime _fcbar = 0;
   datetime b = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (b == _fcbar) return;                 // judge once per closed candle
   _fcbar = b;
   bool against = (g_fail_side > 0) ? IsRed(1) : IsGreen(1);
   g_against = against ? g_against + 1 : 0;
   if (g_against < InpFailCandles) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong tk = PositionGetTicket(i);
      if (tk == 0 || !PositionSelectByTicket(tk)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      trade.PositionClose(tk);
   }
   if (InpVerbose)
      PrintFormat("[DIA] breakout failed — %d candles against, basket closed", g_against);
   g_against = 0;
}

// ── HIS 1:1 BREAKEVEN ────────────────────────────────────────────────────────────
// "at R:R ratio 1:1 we breakeven and let it run to R:R ratio 1:2 in TP."
// The basket shares one stop and one target anchored to the FIRST fill, so R is
// measured per ticket against that ticket's own entry — the later fills of a ladder sit
// better against the shared exits and would otherwise arm late.
void BreakEvenCheck() {
   if (InpBreakEvenR <= 0) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl    = PositionGetDouble(POSITION_SL);
      double tp    = PositionGetDouble(POSITION_TP);
      if (sl <= 0) continue;
      bool isBuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      double risk = MathAbs(entry - sl);
      if (risk <= 0) continue;
      double be = isBuy ? entry + InpBeBufferPts : entry - InpBeBufferPts;
      // already at or past breakeven: nothing to do
      if (isBuy ? (sl >= be - _Point) : (sl <= be + _Point)) continue;
      double gain = isBuy ? (bid - entry) : (entry - ask);
      if (gain < InpBreakEvenR * risk) continue;
      if (trade.PositionModify(t, be, tp) && InpVerbose)
         PrintFormat("[DIA] breakeven armed at %.1fR — stop %.2f -> %.2f",
                     InpBreakEvenR, sl, be);
   }
}

void AgeOut() {
   if (InpMaxHoldMin <= 0) return;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || !PositionSelectByTicket(t)) continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if ((double)(TimeCurrent() - opened) >= InpMaxHoldMin * 60.0)
         if (trade.PositionClose(t) && InpVerbose)
            PrintFormat("[DIA] aged out after %dm", InpMaxHoldMin);
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
double OnTester() {
   double trades = TesterStatistics(STAT_TRADES);
   if (trades < InpMinTrades) return 0.0;
   if (TesterStatistics(STAT_PROFIT) <= 0) return 0.0;
   double wins = TesterStatistics(STAT_PROFIT_TRADES);
   return (wins / trades) * 100.0;
}

//+------------------------------------------------------------------+
// Release one ticket of a spaced basket when its moment arrives. Runs on every tick,
// never blocks, and inherits the FIRST fill's stop and target exactly as the accidental
// ladder does.
void ReleasePending() {
   if (g_pend_left <= 0) return;
   if (TimeCurrent() < g_pend_next) return;
   string tag = StringFormat("zdia_%s_D%d", (g_pend_side > 0 ? "buy" : "sell"), g_pend_dia);
   bool ok = (g_pend_side > 0)
             ? trade.Buy (g_pend_lots, _Symbol, 0, g_pend_sl, g_pend_tp, tag)
             : trade.Sell(g_pend_lots, _Symbol, 0, g_pend_sl, g_pend_tp, tag);
   if (!ok) { g_pend_left = 0; return; }       // broker refused — abandon the rest
   g_pend_left--;
   g_pend_next = TimeCurrent() + g_pend_gap;
}

void OnTick() {
   static datetime _ovbar = 0;
   // SPEED, and nothing else (2026-09-29). During a backtest oanda_vol.csv is a FROZEN
   // FILE: OnInit already read it, and re-reading all 43,434 rows once per simulated bar
   // spent ~13 minutes a run recomputing a value that cannot have changed. VolFeedFresh()
   // above already states the same premise - "the tester replays a frozen table" - so this
   // is that decision applied consistently. LIVE STILL RELOADS EVERY BAR: there the bridge
   // appends a minute every 60 s and a stale table would blind the EA to the newest candle.
   if (InpOandaVolume == 1 && !MQLInfoInteger(MQL_TESTER)) {
      datetime _b = iTime(_Symbol, PERIOD_CURRENT, 0);
      if (_b != _ovbar) { _ovbar = _b; LoadOandaVol(); }
   }
   BailCheck();          // first: "is it working?" outranks every other exit
   AgeOut();
   BreakEvenCheck();
   FailCandleCheck();
   JuryCheck();
   ReleasePending();
   datetime bt = iTime(_Symbol, PERIOD_CURRENT, 0);
   if (bt == g_last_bar) return;
   g_last_bar = bt;
   TryFire();
}
//+------------------------------------------------------------------+
