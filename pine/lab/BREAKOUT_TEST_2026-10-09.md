# Breakout test — Instant at Breakout (2026-10-09)

Zee's definition: a BUY/SELL label **wins if, after entry, price moved our way by at least the
spread + a minimum profit** within the rest of the breakout candle + N minutes (he exits by hand
the moment he is in profit). Settings: `scMin` (profit in $ on 0.1 lot), `scN` (extra minutes),
`uSpread`. Entry: Instant = at the trigger (or the candle open if it opened beyond it).

## The system (verified)

- **Instant mode on history no longer peeks at the close.** It fires when the candle's high
  (BUY) / low (SELL) passes the trigger. Close, colour and breakout-volume rules are unknown at
  the moment of entry, so they are skipped on historical candles (live they see the candle so far).
  Camel trend, strong-trend and higher-timeframe checks use the previous, finished candle.
- **Exact window.** For a BUY that crossed up through the trigger, every price at or above it in
  that candle comes after the cross, so the candle's high really is after the entry.
- **Random baseline on the panel.** Every candle is also a pretend BUY and SELL at its open,
  judged by the same rule; the panel prints the edge (our % minus random %).
- **Independent checker:** `python pine/verify_panel.py` loads the full history, reads every
  recorded entry from the indicator's data series, recomputes every result from raw candles and
  compares all test rows. PASS on 500/500 and 162/162 signals; PASS under three different
  settings; FAILS (7 mismatches) when fed a deliberately wrong spread — so it can catch errors.

## Results ($1 profit on 0.1 lot, rest of candle + 1 min; random scores 84%)

| setup | labels | win | halves | edge | at $5 profit (random 64%) |
|---|---|---|---|---|---|
| base (pre-loop settings, Instant) | 500 | 91.2% | 92/91 | +6.8 | 68.8% |
| **UHV body ≥50% + 1-hour candle aligned — on the chart** | **162** | **94.4%** | **94/95** | **+10.0** | **75.3%** |
| structural trend + 1-hour aligned | 124 | 96.0% | 95/97 | +11.5 | 72.6% |
| structural trend + 15-min aligned + cooldown 10 | 127 | 95.3% | 95/95 | +10.8 | 72.4% |
| structural trend + UHV body ≥50% | 110 | 96.4% | 93/100 | +11.9 | 76.4% |

Logs: `results_A.jsonl` (single rules), `results_B.jsonl` (combinations), `results_C.jsonl`.

## Not modelled — what still separates this from MT5

Spread fixed at $0.13 (the panel setting); no latency or slippage at the trigger (a market order
fills after the cross, usually a little worse); volume rules skipped on history in Instant mode;
OANDA chart prices, not the broker's. "Fire before the UHV high" (uPBD) makes almost every candle
a signal in Instant mode — keep it 0. Candle data simulation: a hypothesis until live fills.

## MT5 check of the random baseline (2026-10-09, Prime XBT XAUUSDp, real ticks)

`mt5/RandomTouch.mq5`, run with `mt5/run_rig.ps1` on a separate portable copy of the Prime XBT
terminal (`C:\mt5_rig_pxbt`; the live terminal was not touched). Random entries at a candle's
open, 0.1 lot, closed the moment profit reaches $1, else at the end of the next candle.
28 Sep – 8 Oct, ~3,470 trades per run. Spread measured: $0.17 average; commission: none.

| exit delay | banked $1 | touched $1+ at some tick | $/trade |
|---|---|---|---|
| 0 ms | 80.6% | 86.2% | −2.20 |
| 50 ms | 77.0% | 85.7% | −2.10 |
| 200 ms | 72.8% | 86.1% | −1.73 |
| 500 ms | 63.4% | 86.0% | −1.57 |
| 1 s | 58.8% | 86.5% | −1.28 |
| 2 s | 50.6% | 85.5% | −1.93 |
| random delay | 52.3% | 84.7% | −1.76 |

Reading: the panel's price-path math is right (zero-delay MT5 80.6% vs panel 84%, the gap is
the wider real spread, 0.17 vs 0.13). What the panel cannot model is EXIT SPEED: the $1 touches
are brief, and every 100 ms of delay loses wins. The panel's breakout test is a zero-delay upper
bound — fine for comparing settings against each other and against random, not an executable
win rate. The executable number needs the signals themselves in MT5 at a realistic delay.
