# PDF Paper Evaluation — "Comprehensive Analysis of Ultra-High WR Strategies"

**Date**: 2026-05-02
**Source**: User-provided PDF (Layered Testing, Burst Safety, Forensic Dissection)
**Test script**: `monitor/strategy_lab/pdf_paper_layered_test.py`

## Status: REJECTED — none of the testable claims improve our LIVE stack

## Mapping: PDF claims → our infrastructure

| PDF concept | Status |
|---|---|
| Wilson 95% CI | Already implemented in `wilson_ci()` |
| Forensic dissection | Already used (`losing_chain_forensic.py`) |
| Layered testing methodology | Already standard practice |
| CVD divergence (absorption/exhaustion) | Already deployed (`cddDivExit`) |
| Velocity kill switch | Built (`midtradeMonitor`), deployed-OFF |
| Multi-timeframe trend alignment | 2-min + M15 deployed |
| Streak/clustering detection | `chainStopAfterLoss=2` |
| Burst safety on volatility | `burstSlUsd=$15` deployed |
| Dark pool routing | N/A for retail PineConnector/MT5 |
| Uncorrelated alpha (ILS, CTAs, IP) | Out of scope for XAU scalper |
| Regime classification (Quiet vs Volatile) | Tested → ATR ratio threshold rarely triggered |

## Tested claims (4 layered on LIVE + burstSL=$15)

Baseline: 9 chains / 73.3% mainWR / 100% chainWR / +$289.22 / 0 losing / +$15.88 max DD

| Test | Best variant | Δ profit | Verdict |
|---|---|---|---|
| T1: Skip "strong UHV trap" (top X% body) | top 5%: -$16 | NEGATIVE | Skips winners proportionally; trap intuition doesn't survive layered test |
| T2: Skip Dragonfly/Gravestone UHV shape | -$100 | NEGATIVE | Removes 2 winners that happened to be doji-shaped |
| T3: Skip Volatile regime (ATR-20/ATR-100 > X) | 0 blocks at >1.5; -$87 at >1.2 | NEUTRAL/NEGATIVE | Threshold too high to fire; lower threshold cuts winners |
| T3b: Realized-vol regime (rv-short/rv-long > X) | -$26 at rv(3m)/rv(30m)>1.5; 0 blocks at >2.0 | NEUTRAL/NEGATIVE | Same problem as T3 — blocks a winner, doesn't catch loser. Loser was structural-trap, not regime issue. |
| T4: INVERT direction on top X% UHV | top 5%: +$44 | CURVE-FIT | n=1 inversion, hindsight on the known loser; collapses at top 10%+ |

## Why claims don't translate

1. **Sample size**: 9 chains too small. Wilson 95% CI on most filters reverses across the noise floor.
2. **Correlation with existing filters**: PDF concepts already implicitly captured by trend/UHV/effort/setup1 gates.
3. **Scope mismatch**: PDF describes hedge fund portfolio diversification; we're a single-instrument retail scalper.

## What IS valuable from the PDF

1. **More data is the bottleneck**. Every test failed for sample-size reasons, not concept reasons. Run live for 1 month, collect 200+ chains, then re-test.
2. **`midtradeMonitor` direction reinforced**. PDF's "velocity kill switch" aligns with our rocket-ship probe-velocity guard. Validate `burstSlUsd=$15` first, then flip `midtradeMonitor: true`.
3. **Regime classification needs finer metric**. ATR-20/ATR-100 doesn't have enough range in M1 XAU. Try realized-volatility / session-baseline-vol or a Hurst-exponent-style measure.

## Future-Claude reminder

**DO NOT re-test T1/T2/T3/T3b/T4 in their current forms at this sample size.** Filed as REJECTED. If revisiting:
- Wait until live data has 100+ chains (statistical floor)
- T3b (realized-vol) is now coded — rerun with bigger n to see if rv-regime emerges as predictive
- Layered testing on LIVE — never standalone

## Action plan (data-driven, not filter-driven)

1. **Run live ~1 month** with `burstSlUsd=$15` to gather 100-200 chains
2. **Apply Wilson 95% CI** when re-evaluating any filter (already in code)
3. **Activate `midtradeMonitor: true`** after `burstSlUsd=$15` validates over a few days
4. **Rerun T3b** with bigger n — realized-vol regime might emerge as predictive once sample isn't a bottleneck

The principle: **stop adding technical filters; fix the data problem.**
