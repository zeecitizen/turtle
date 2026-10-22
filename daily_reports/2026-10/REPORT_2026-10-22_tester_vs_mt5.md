# 2026-10-22: why the Python tester disagrees with MT5 (Saad 15-min, settings 02-38-09, 2026 M1)

Status: CALIBRATED, NOT PERFECT. The matched tester is now within about $7k of MT5 on the full year for settings 02-38-09 (zero daily limits). Unmatched trades: 224 (baseline 495 under the old count; 198 before the entry offset). Turtle TV uses the new default. Other saved settings are NOT yet checked against MT5.

## Committed today
- `bdf1d53d` Saad_strategy_15min v1.35: a refused order is logged (`[ORDER REJECTED]`), never silent. Trading unchanged. VERSION.md and VERSION_HISTORY.md updated.
- `205f5c17` sim_full: long dip fills were taken at the minute's low (the `aSide`/`side` test). Fixed. Also commits the `hf` tick-order parameter that HEAD was missing.

## Found (receipts)
- **Margin wipe-out in MT5 run r20261022_091133** (100k deposit, 2 lots): no free margin from 19 Mar 09:04; every order "not enough money"; the EA dropped them silently. Fixed by v1.35 logging. The $1M run r20261022_dep1M has zero margin rejections.
- **Clock**: candle labels = MT5 server-time strings; the raw label clock matches best (95%). A DST-aware offset matched worse (83%). Not adopted.
- **Dip fills**: the tester's fill rule is right in principle (`TryDip`: first tick with ask at or below aLevel after the break). 13/13 sample entries checked against raw ticks.
- **Exit attribution**: one position at a time (InpMaxPos=1). Exits pair by ticket; no FIFO/LIFO issue.
- **Cooldown**: EA cooldown = exit + InpCoolBars x bar, set on losing out-deals. Simulator equivalent on losing full closes. Losing partials: MT5 sets it, simulator does not. Adding it made the count worse (554), so reverted.
- **9-Jan case**: MT5 short stopped at 09:03:00 (ask 4475.34, stop 4475.32). The simulator at 15-second time points exited at 09:03:12, which blocked the 09:04 decision. Per-second points fix the exit second (now 09:03:00).

## Numbers (zero daily limits, 02-38-09 inputs, 2026 M1, MT5 $1M run)
| version | unmatched trades (baseline 495) | tester net | gap to MT5 (-231,728) |
|---|---|---|---|
| committed 205f5c17 (15-s points) | 495 | -262,439 | -30.7k |
| per-second points (uncommitted) | 198 | -339,962 | -108.2k |

Gap decomposition (per-second, matched 5,802 trades): entry price -110k, exit price +38k, lots/partials -25k.
Stop overshoot calibration (MT5 stop-outs +$0.12 median, trailing +$0.05, sd 0.5-0.95): applying it makes the gap WORSE. Rejected.
Exact-tick fill at the second's extreme: makes it worse (-265k). Rejected.

## Open
1. Entry fill price (the largest piece, -110k). Measurement in progress: MT5 entry vs the tester's aLevel and its second's range.
2. Trailing stops: tester -63k against MT5 (on the 15-s version).
3. Unmatched: 198 remaining.
4. Turtle TV: to be replaced with the matched tester once the gap closes. Old results stay, marked superseded.

## Not committed
The per-second time base (sim_full.py, sim.py) and the year1_sec / year1_tHL datasets. Keep uncommitted until the entry fills match.

## Update (later the same session)
- Entry-price calibration: MT5 fills dip entries a median $0.054/oz (mean $0.118) better than the simulator's level fill (5,802 matched entries). Added `slip_entry = -0.10` as the default in `sim.py` (XDEFAULT). The TradingView chart keeps 0.
- Full year, 02-38-09, zero daily limits: tester total -224,287 vs MT5 -231,728 (gap +7.4k). Matched gap +15.2k.
- Out of sample: Jan-Jun gap +5.4k (calibrated on the full year, so this half is not clean), Jul-Oct gap +9.8k. Without the offset: -74k and -22k.
- Trade set: unmatched rises from 198 to 224 with the offset (the offset trades some trade-set agreement for P&L agreement).
- Stop overshoot and exact-tick fills were tested and rejected (see above).
- Per-second points: `simdata/year1_sec.npz` (built from the 2026 tick file). Not in git.
