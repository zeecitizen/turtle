# Saad Strategy indicator — audit before PineConnector (2026-10-11)

*For Zee and Saad bhai. Chart: OANDA:XAUUSD 5-minute, Zee's saved settings
([optimal_settings_saad_strategy.md](optimal_settings_saad_strategy.md)). Every trade is listed in
[SAAD_SETUPS.md](SAAD_SETUPS.md), with the rule it followed, its SL, TP and how it ended.*

> These are the indicator's own figures, worked out on the chart. They are a hypothesis until MT5
> or live fills confirm them (CLAUDE.md). The EA port and its MT5 results are in
> [VERSION_HISTORY.md](VERSION_HISTORY.md).

## Bottom line

| | Before the audit (v3.20 engine) | After (v4 engine + guards) |
|---|---|---|
| Trades (13 Sep – 9 Oct) | 260 | 272 |
| Win rate | 42.3% | 54.0% |
| Net at 0.1 lots | +$4,754 (no spread, optimistic) | **+$2,495 after $0.20 spread** |
| Profit factor | 1.50 | 1.31 |

The old panel looked better because it was wrong in the trade's favour. Most of the gap comes from
the spread ($2 per trade × 272 = $544) and from deciding stop-vs-target inside the candle
minute by minute instead of guessing.

## What was wrong, and what was fixed

| # | Problem found by reading the journal | Example | Fix |
|---|---|---|---|
| 1 | A trade reached its TP, "rode" the trailing stop, then closed at a **loss** | #1, #6, #21… (old journal) | When the TP is reached the stop is locked 2 pips short of the TP, so a reached target can no longer become a loss. A modify alert goes to the broker. |
| 2 | Longs whose exit EMA was already **below the entry** fired a false "TP reached" on the first candle | old #14 | Shown as "TP none". The trade trails from the entry, or exits on a close below the EMA. |
| 3 | Trades taken while the 50 EMA was still warming up (e50 = NaN) | old #1–#3 | No setups in the first 100 candles. |
| 4 | No risk cap: one stop was $46 away | old #37 | Skip a setup whose stop is more than $9 from the entry (same as the EA). |
| 5 | The entry candle was never checked for SL/TP, and a candle touching both was guessed | — | Every candle is replayed minute by minute (1-minute data), starting with the minute after the break. |
| 6 | No spread or commission in the panel | — | $0.20 spread (PrimeXBT ≈ $0.19) taken off every trade; commission input. |
| 7 | No PineConnector messages | — | Added (see below). |
| 8 | A setup from before the **daily close** entered after the reopen (wide spread, jump) | #7, #253 — both lost | A waiting setup is cancelled across a gap in time (on by default). |
| 9 | SHORTs whose "last support" was only $0.09–0.30 below the entry could not beat the spread | #102, #227, #256 | The TP must be at least 5 pips away. SHORTs look further down for support; LONGs with the EMA too close trail instead. |

**Checked on all 272 trades with no problems:**
- the candle shape matches the thresholds (pin, marubozu, hammer, shooting star)
- the candle really touches its EMA
- the entry is at the high/low, or at the open if the market gapped past it
- the SL is exactly 34 pips beyond the candle
- the risk is ≤ $9
- the TP is on the right side of the entry
- the entry came within 2 candles of the setup
- every SL exit is at the SL price

The P&L matches the prices to within cent rounding.

## Missed setups

The panel now shows **"busy"**: setup candles that were ignored because a trade was already open
or another setup was waiting. On this chart that is **726**, against 272 trades taken. The
strategy takes one trade at a time, and a trade that is riding its trailing stop can stay open for
hours. Many of those 726 sit inside the same move, but this is the biggest source of "missing"
trades. The EA tests the two cures: a newer setup replaces the one waiting, and more than one
position at a time.

## What the numbers say (the indicator's figures, hypothesis only)

- **Hammers** did best (27 trades, 66.7% WR, +$1,086). **Shooting stars** were flat (+$33).
- **Setups on the 50 EMA** were flat (46 trades, −$6); **setups on the 9 EMA** made the money
  (+$2,501).
- **Every winner came from the trailing stop** (190 trades, 77% WR). Every loser is a full stop
  (82 trades, −$75 each). The strategy is: lose $75 sometimes, win $46 on average, more often.
- **SHORTs with far-away supports (TP > $8)** won only 33% of the time and lost $395.
- **Bad days:** 21 Sep −$585, 23 Sep −$435, 28 Sep −$349, 8 Oct −$287. It is not profitable
  every day: 12 of 22 trading days were green.

## PineConnector — how to connect it

1. Inputs → 🔌 PINECONNECTOR: switch **Send PineConnector alert messages** ON, enter the
   **license ID**, and set **Symbol name at the broker** to PrimeXBT's gold name. The PXBT
   terminal calls it `XAUUSDp` — check yours in Market Watch.
2. Create **one** alert: Condition = this indicator → **"Any alert() function call"**, trigger
   "Once per bar" is not needed (the script de-duplicates), expiry = open-ended, webhook = your
   PineConnector URL.
3. In the PineConnector EA on PrimeXBT: read **sl / tp as prices** and **risk as lots**. Lots
   come from "Lots for the $ figures" (0.1).
4. Messages sent:
   - `buy` / `sell` with sl= (and tp= for a SHORT that will not ride)
   - `newsltplong` / `newsltpshort` on every lock, trail or breakeven move
   - `closelong` / `closeshort` on every exit

   Because every exit also sends a close, the broker position closes when the chart's trade
   closes, even if a stop modify was refused.
5. **After any code update you must delete and re-create the alert.** An alert keeps running the
   code it was created with.

## What will still differ live (be ready for it)

1. **Different price feed.** The chart is OANDA; the trades are on PrimeXBT. The prices differ by
   a few cents, so a setup can appear on one and not the other, and SL prices are OANDA prices.
2. **Entry is a market order when the alert arrives**, typically 1–3 seconds after the break.
   The panel assumes a fill exactly at the high/low. Expect a few cents of slippage per trade.
3. **The TP lock sits 2 pips short of the TP.** If PrimeXBT's bid is already below that level,
   the broker refuses the modify (stop too close). The close message still closes the trade when
   the chart's trailing stop is hit. Raise "Lock this many pips short of the TP" to 5 if refusals
   show up in the PineConnector log.
4. **Around the clock.** Hours are OFF in these settings. The MT5 tests on Axi found 08–17 server
   time was the single biggest improvement.
