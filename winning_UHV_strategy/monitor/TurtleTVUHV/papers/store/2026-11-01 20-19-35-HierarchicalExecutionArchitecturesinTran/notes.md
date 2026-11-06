# Working notes - paper -> EA setting (Claude Fable 5.1, headless, 2026-11-02)

Paper: **Hierarchical Execution Architectures in Transformer-Driven Algorithmic Trading: Bridging the
Signal-to-Profit Gap via Dynamic Sub-Trade Lot Allocation** - Abiodun Aremu (FxChartAI), dated
January 8, 2026. XAUUSD H1, July 22 - November 26, 2025, MT5 Strategy Tester, $100k.

## What the paper actually proposes

The signal (a transformer "sentiment" 0/1 with adaptive thresholding) is kept fixed. The claim is
that the *execution* decides profitability: the same signals traded as one position with a static
SL/TP ("Direct", Phase I) lost 99.99% (PF 0.71, 122 trades), while splitting every signal into five
sub-trades ("Dynamic Subtrade", Phase II) returned +$1.31M (PF 4.95, 80 trades, DD 33.9%).

The five sub-trades (lot share of the signal):

| sub-trade | share | category | stop logic |
|---|---|---|---|
| Matthew | 10% | fixed | fixed-pip trail, 5x slower than Matt; also the "state guard": no new signal cycle until it closes |
| Matt | 30% | fixed | fixed-pip trail, fast (locks the first impulse) |
| Mark | 30% | adaptive | low ATR-multiple trail |
| Luke | 20% | adaptive | 2.5x Mark's ATR |
| John | 10% | adaptive | 2x Luke's ATR (= 5x Mark) |

Evidence: two strategy-tester reports (direct vs subtrade) on 4 months of H1 gold, a 325-row
sentiment dataset. No out-of-sample test, no delay / slippage model mentioned, the fixed pip values
and ATR multipliers are not given. The author's own numbers ("PF 4.95 is exceptionally rare") are a
single in-sample backtest, i.e. exactly the kind of number this project calls a hypothesis.

## Mapping to Saad_strategy_15min v1.39 (existing inputs only - no new code needed)

The EA already has the building blocks: two partial closes (`InpXP1R/Frac/Be`, `InpXP2R/Frac`),
one trail on the remainder (`InpXTr` 2 = ATR from the best, `InpXTrK`, `InpXTrAct`), lab targets
(`InpXTgt`), an ATR stop mode (`InpSlMode` 1), a loss cap (`InpXLossCap`), position gating
(`InpMaxPos` 1 - already the base's), the broker TP (`InpFixTpPips`).

**Key fact found on the way:** the base `2026-11-01 08-38-10` wins $2 per trade (20-pip broker TP,
`InpFixTpPips` 20) against a $26 stop (`InpSlMode` 2 / `InpSlUsd` 26). Its `InpXTgt` 4 / 26 lab
target never fires (the TP closes first), and any "partial at 1R" ($26) never fires either. My first
tranche variants (V1-V4, V9, V12, V13, V16 in tester_variants.json) were therefore identical to the
base to the cent or just an "ATR trail from the entry" - not the paper. The real mapping is in units
of the $2 win: 0.077R.

## Tester runs (Turtle TV m15, 2022-2026) - ALL HYPOTHESIS

| variant | n | WR % | net $ | PF | worst | DD |
|---|---|---|---|---|---|---|
| base | 1615 | 97.2 | 402,831 | 2.79 | -5,574 | 14,841 |
| ATR trail 2x from entry, no target (V2) | 1760 | 78.1 | 177,533 | 1.45 | -5,272 | 16,712 |
| ATR stop + ATR target k=4 (V6) | 1620 | 91.6 | 264,066 | 1.79 | -9,054 | 13,000 |
| ATR stop min(6 ATR, $26), $2 TP kept (V15) | 1607 | 94.8 | 327,245 | 2.15 | -5,572 | 14,485 |
| TP off; 60% at $2 + BE; 40% trails 2 ATR from entry (W1) | 1633 | 77.1 | 98,357 | 1.25 | -5,272 | 14,204 |
| TP off; 60% at $2 + BE; 40% trails 2 ATR after the partial (W2) | 1509 | 95.9 | 339,581 | 2.37 | -5,868 | 14,068 |
| TP off; 60% at $2 + BE; 40% trails 5 ATR after the partial (W3) | 1399 | 96.0 | 331,615 | 2.43 | -5,868 | 13,684 |
| TP off; 60% at $2 + BE, 25% at $4, 15% trails 2.5 ATR (W4) | 1518 | 96.4 | 354,746 | 2.48 | -5,868 | 14,599 |
| **TP off; 60% at $2 + BE; 40% to the $26 1R target (W5 = candidate B)** | 1391 | 96.3 | 373,738 | 2.83 | -5,868 | 12,639 |
| **TP off; paper split 40% at $2 + BE, 30% at $5, 30% trails 2.5 ATR (W6 = candidate)** | 1503 | 96.1 | 356,496 | 2.51 | -5,868 | 14,073 |
| TP off; 60% at $2 + BE; 40% trails 1 ATR (W7) | 1539 | 95.5 | 311,093 | 2.27 | -5,868 | 15,611 |
| TP off; 80% at $2 + BE; 20% trails 2.5 ATR (W8) | 1516 | 96.3 | 350,448 | 2.46 | -5,868 | 14,715 |
| TP off; 60% at $2 no BE; 40% trails 2.5 ATR, stop stays $26 (W9) | 1307 | 71.3 | 297,554 | 1.77 | -5,578 | 19,260 |

Reading: no sub-trade variant beats the base's net in the tester. The fixed-anchor variants with
breakeven after the first partial stay within ~1 WR point of the base and cost $30-50k of net over
four years; the breakeven exits of the runner are the "losses" (small). Pure ATR trailing from the
entry (the paper's adaptive sub-trades on their own) destroys the 97% win rate - gold's M15 noise
takes a 2-ATR trail out long before the $2 fixed win is safe. The paper's own observation that the
anchor sub-trade gates new signals shows up here too: n falls 1615 -> 1391-1503 because the runner
holds the one allowed position longer.

The ATR-adaptive stop (the paper's "Adaptive" category applied to the stop itself) lowers the win
rate in every form tried - the base's $26 stop is already wider than 6 ATR in 2023-2024, and the
capped version min(6 ATR, $26) only tightens stops (doctrine-safe) yet still loses 2.4 WR points.

## Candidates sent to MT5 (axi6; base on axi5)

* `... candidate`  = W6, the paper's own 40/30/30 split (fixed anchor at $2 + BE, second anchor at
  $5, 30% on a 2.5 x ATR trail that starts after the first partial).
* `... candidate B` = W5, the fixed-anchor half only (60% at $2 + BE, 40% to the base's $26 1R target).

Both keep the entry, the filters and the $26 stop. Both change the exit geometry (the paper is about
exits): the 20-pip broker TP is replaced by lab partials. MT5 M15, Blueberry real ticks, $100k,
2 lots, 2023-2026, delay none and random - the random column is the verdict (see result.json).

## MT5 verdict (M15, Blueberry real ticks, $100k, 2 lots) - the judge

| setting | delay | 2023 | 2024 | 2025 | 2026 | total |
|---|---|---|---|---|---|---|
| base 2026-11-01 08-38-10 | none | 58,126 | 101,749 | 95,664 | 132,477 | **388,016** |
| base | random | 58,048 | 89,859 | 77,528 | 129,333 | **354,768** |
| candidate (paper 40/30/30, ATR runner) | none | 53,991 | 114,065 | 75,813 | 126,099 | 369,968 |
| candidate | random | 64,137 | 100,238 | 31,780 | 115,342 | **311,497** |
| candidate B (60% at $2 + BE, 40% to 1R) | none | 47,845 | 108,327 | 94,693 | 116,653 | 367,518 |
| candidate B | random | 54,045 | 98,050 | 76,661 | 89,011 | **317,767** |

Base MT5 random WR 96.1% (per position). The candidates' MT5 win rates (77% / 69%) count partial
closes and breakeven exits as separate trades and are not comparable; their tester per-position
hypothesis was 96.1% / 96.3%.

Verdict: the paper's sub-trade architecture does NOT improve the base under random delay
(-$43k; candidate B -$37k). It wins 2023-2024 and loses 2025-2026; the 2025 random pass collapses
($75.8k -> $31.8k, PF 1.21, DD 17.6%) because the delay lands on the partial fills and the
breakeven stop moves the architecture depends on. Nothing promoted; the base stays. Rows are in
research/mt5_years.json under the gates `save:<id> candidate`, `save:<id> candidate B`,
`save:2026-11-01 08-38-10`.
