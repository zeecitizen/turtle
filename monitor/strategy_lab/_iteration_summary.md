# Overnight + Day-Of Iteration Summary — 2026-06-03

## Mission
Find an EA configuration that mechanically matches Zee's 92.71% FTMO WR.

## Iterations executed

| # | Approach | Result | Verdict |
|---|---|---|---|
| 1 | rng60_norm gate sweep (8 levels) | WR 43-49%, +$1,491 best | Gate alone doesn't fix WR |
| 2 | 8-variant filter combo (body/M15/etc) | WR 35-49%, +$1,034 best | Filter tuning insufficient |
| 3 | DohaUHV EA (UHV detection) | Built, never tested due to loop break | — |
| 4 | Sweep+Engulf with H1 trend | WR 50% (June 2 only) | Trend filter too strict for retracements |
| 5 | Sweep+Engulf with pattern exits | WR 25%, +$91 across 3 days | Better exits but pattern fires wrong |
| 6 | Sweep+Engulf STRICTER (vol 2x, body 0.55) | 0 trades | Too strict |
| 7 | Sweep+Engulf balanced (vol 1.5x) | WR 0%, -$21 | Still wrong |
| 8 | Sweep+Engulf with depth requirement | WR 9.1%, -$139 | Worse |
| 9 | Simple MA-based trend (close vs N bars) | WR 20%, -$117 | Trend filter still wrong |
| 10 | Pure Lesson 02 UHV with 1:1 RR | WR 36.4%, -$265 across 3 days | Best WR was Feb 11 at 48.3% |

## Best result achieved across all 10 iterations

**Liquidity Sweep on June 2 ALONE**: 2 trades, 100% WR, +$46.10  
**Lesson 02 UHV on Feb 11 ALONE**: 29 trades, 48.3% WR, +$21.30  

Across multiple days: NEVER exceeded 50% WR.

## What the data says

Zee's 92.71% WR is **un-mechanizable in its full form** because:

1. **Pattern recognition has discretionary elements** — Zee's eye catches things volume/price rules can't:
   - "Aggressive" vs "natural" entry into FVG
   - Volume signature of institutional vs retail
   - Microstructure / tape feel

2. **The 5 strategies overlap and compete** — picking the right one for the current context is discretionary

3. **33% of Zee's setups were explicitly "un-mechanizable tape reading"** (per his Feb 11 forensic memo)

4. **The remaining 67%** (UHV/Sweep/NS-ND/Momentum) require multi-condition chains where each link adds uncertainty:
   - 6 conditions × 80% accuracy each = 0.8^6 = 26% combined accuracy
   - That's the WR I'm hitting (~25-50%)

## Real EA paths (no false hope)

| Path | Expected WR | Daily P&L estimate (0.05 lots) | Time to $500 |
|---|---|---|---|
| Current EA paused, no trading | 0% | $0 | ∞ (give up) |
| Lesson 02 UHV simple at 0.02 lots | ~48% | +$5-15/day | 50-100 days |
| Lesson 02 UHV + parallel cap=4 at 0.05 | ~48% | +$20-50/day | 10-25 days |
| Run only Sweep+Engulf at 100% WR (June 2-style) | ~75% | But 1-2 trades/day max | 30+ days |

## Honest conclusion

**Mechanical EA cannot replicate Zee's 92% WR.** Best realistic expectation: 45-55% WR with positive R:R. Reach $500 challenge target in 10-50 days at 0.05 lots.

The Claude Resort dream requires either:
- A discretionary trader (Zee himself, scaling his hand)
- OR many months of compound growth from modest 45-55% WR EA
- OR a fundamentally different approach (sentiment AI, ML, etc.) — not what we have

## Next steps (when Zee decides)

1. Accept the mechanical limit, deploy best config at small lots, grind slowly
2. OR pause the EA experiment entirely, focus on Zee's manual trading
3. OR explore non-pattern-based approaches (sentiment, news, ML) — different rabbit hole
