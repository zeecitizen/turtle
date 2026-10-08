# Win-rate loop — 2026-10-08 (night, PKT)

Goal set by Zee: 90%+ of BUY/SELL labels in profit X seconds after entry, entry at the
breakout candle's close, 1-minute XAUUSD (OANDA), judged on the indicator's own panel.

**Status: NOT reached. Best robust result: 71% on 51 labels.** Everything below is the
indicator's own measurement on candle data — a hypothesis under CLAUDE.md, not MT5 proof.

## The test (now on the stats panel, verified)

A label wins if `close[N candles later]` is beyond the entry (the signal candle's close) by
more than the spread ($0.13). N=1 → 60 s, the shortest the 1-minute data can measure (second
data needs a higher TradingView plan). Each label now prints its verdict (`✅ 60s +0.42`).
Verification: all 40 labels on the chart were recomputed from the raw candles — 40/40 agree
(entry price, next close, verdict).

History used: 2026-09-28 03:04 PKT → 2026-10-08, 11,161 one-minute candles.

## Results

| configuration | labels | win | older half | newer half |
|---|---|---|---|---|
| as it was (camel gates, strong-trend exception, …) | 316 | 42% | 44% | 41% |
| London+NY hours, breakout volume drop, no camel gate on retracement start | 69 | 67% | 74% | 60% |
| … + 15-minute candle aligned (uHTD=15) | 50 | 70% | 76% | 64% |
| **… + no cooldown (uCd=0) — now on the chart** | **51** | **71%** | **76%** | **65%** |
| … + sweep (rUS) + UHV body ≥50% | 17 | 76% | 88% | 67% |

Single-rule effects (round 1, from the 42% base): London+NY hours **+8** (50%), breakout
volume drop +6, 15-min alignment +5, judging after 2 candles +5. Everything else within ±3,
several negative (LAWS momentum body ≥70% −2, wide-spread UHV −14, volume spike UHV small n).
Raw logs: `results.jsonl` (rounds 1–2), `results_r3.jsonl`, `results_r4.jsonl`.

## Why 90% is not reachable honestly with this test

1. **The next minute of gold is close to a coin flip, and the spread tilts it below 50%.**
   Buying every candle wins 44% at 60 s. A search of 758 two- and three-condition filters
   (candle shape, volume, momentum, volatility, hour, 20-bar breakout) found nothing that holds
   above ~54% on both halves of the history.
2. **Every filter that adds win rate removes labels**, and the newer half always scores 10–20
   points below the older half — the signature of fitting noise. Pushing to 90% means a handful
   of labels, which would not repeat.
3. **A "touched profit within X" test reaches 90% with no signal at all**: buying every candle
   with a $0.05 take-profit and up to 5 minutes wins 91.6% — and loses $0.21 per trade, because
   the spread is paid every time. So that version of "90%" measures nothing and loses money
   (CLAUDE.md's SL-30 trap). It was deliberately NOT used.

## Tools built

- `pine/tv_lab.py` — push code (save that actually lands + fresh-copy swap with settings by
  name), set/get chart settings by name, read the scorecard.
- `pine/tv_sweep.py` — run a plan of configurations on the real indicator, log each result.
- `pine/tv_export.js` — export candles and BUY/SELL labels from the chart for verification.
