# Trade lifecycle — Saad_strategy_15min (no pyramiding)

How the EA opens, protects and closes a SELL and a BUY: `mt5/Saad_strategy_15min.mq5` **v1.18**, magic
88302, XAUUSD M15, default settings. Read from the code (`DoEntry`, `ManageTick`, `ManageBar`,
`LongTouched`, `ShortTouched`, `DayCloseCheck`, `DetectSetup`, `Shape`).
Re-verified against the code on 13 Oct 2026. At 1 lot, **$1 of gold price = $100**.

---

## SELL trade

1. **Setup:** a 15-minute candle closes touching the **9 EMA** (its high-low range includes the EMA) as
   one of:
   - a **red (bearish) marubozu**
   - a **shooting star**
   - a **pin bar that closes red**. A pin bar on the 9 EMA that closes green or flat is taken as a BUY
     instead (see below).
2. **Filters**, all must pass:
   - the candle is at least **0.55 × ATR(14)** tall
   - the market isn't choppy: the efficiency ratio over the last **16 candles** is at least **0.11**
   - no trade is open and no other setup is waiting
3. **Entry:** the **next candle** must break the setup candle's **low by 2 pips**. The EA sells the
   moment that happens. If it doesn't happen within one candle, or the market closes in between, the
   setup is dropped.
   **At that moment** the EA looks for the **last support**: the most recent swing low (the lowest of 3
   candles on each side, within the last 100 candles) at least 5 pips below the price.
   **No support → no trade.**
4. **Stop loss:** **35 pips ($3.50) above the setup candle's high**, sent to the broker with the
   order. If the stop would be more than **$15** from the entry, the trade is skipped.
5. **Target:** **TP1 = that support level.** The EA watches it; **no take-profit is sent to the
   broker.**
6. **Breakeven:** once price has fallen **75% of the way to TP1**, the stop moves to the **entry
   price** (logged as "CTC").
7. **TP1 touched:**
   - **half the trade is closed** and that profit is banked
   - the stop on the other half jumps to **price + $2**, never worse than the entry
   - **TP2** becomes the next support below
8. **Trailing:** the stop follows price down, **$2 above it, tick by tick**, and never moves back up.
   TP2, TP3… are **labels only**: the EA logs each one as price passes it, and nothing closes there.
9. **Exit**, whichever comes first:
   - **original stop** hit → full loss
   - **breakeven stop** hit → about $0
   - **$2 trail** hit after TP1 → small or big win
   - **3 minutes before the daily close while in loss** → closed

---

## BUY trade

1. **Setup:** a 15-minute candle closes touching the **9 EMA or the 50 EMA** as one of:
   - a **green (bullish) marubozu**
   - a **hammer**
   - a **pin bar**: on the 9 EMA only if it closes green or flat (a red one is a SELL); touching only
     the 50 EMA, any colour
   Its **exit EMA** is the other one: the 50 EMA for a setup on the 9 (also when the candle touches both),
   the 9 EMA for a setup on the 50.
2. **Filters:** the same as for a SELL (≥ 0.55 × ATR, not choppy, nothing open or waiting). If a candle
   qualifies as both a BUY and a SELL, the BUY wins.
3. **Entry:** the **next candle** must break the setup candle's **high by 2 pips** (judged on the bid,
   like the chart). The EA buys the moment that happens; otherwise the setup is dropped after one
   candle.
4. **Stop loss:** **35 pips below the setup candle's low**, sent to the broker. More than **$15**
   away → skipped.
5. **Which path the trade takes:**

   **Path A: the exit EMA is above the entry (the normal case)**
   1. **TP1 = the price touching the exit EMA.** The EMA moves, so TP1 moves with it. The EA watches
      it; nothing goes to the broker.
   2. At **75% of the way** to the EMA, the stop moves to the **entry**.
   3. **EMA touched:** **half the trade closes**, the stop jumps to **price − $2** (never below the
      entry), and **TP2** becomes the next swing high above.
   4. The stop follows price up, **$2 below it, tick by tick**. TP2, TP3… are labels only.

   **Path B: the exit EMA is already below the entry (or less than 5 pips above it)**
   1. There's no TP1, so there is **no half-close and no 75% breakeven step.**
   2. From the second candle on, at each candle close, the stop rises to
      **the highest high since entry − 2 × ATR(14)**. It never moves down.
6. **Exit:** the original stop, the breakeven stop, the trail, or "3 minutes before the daily close
   while in loss". Same as a SELL.

---

## The candle shapes (default settings)

| Shape | Rule (range = high − low) | Counts for |
|---|---|---|
| Pin bar | body ≤ 60% of the range, long wick ≥ 45%, other wick ≤ 20% | BUY or SELL, decided by the EMA and the close (above) |
| Hammer | lower wick ≥ 2.5 × body, upper wick ≤ 50% of the range | BUY |
| Shooting star | upper wick ≥ 2.5 × body, lower wick ≤ 50% of the range | SELL |
| Marubozu | body ≥ 53% of the range | green → BUY, red → SELL |

A candle is checked as a pin bar first, then as a hammer or shooting star, then as a marubozu.

## The same for both

- **One trade at a time** (`InpMaxPos = 1`). Setups that appear while a trade is open are skipped,
  not queued.
- **Winning trades stay open overnight and over weekends.** Only losing trades are closed 3 minutes
  before the daily close. A weekend gap can jump past the stop: 24 Jul, −$2,612 (report.md §12).
- **Only the stop loss lives at the broker.**

| Item | Held by the broker (works if the PC is off) | Done by the EA (needs the PC + MT5 running) |
|---|---|---|
| Original stop loss | ✅ | |
| Stop to entry at 75% | ✅ once moved | the move itself |
| TP1 half-close | | ✅ |
| $2 trail / 2× ATR trail | ✅ each level, once moved | the moving |
| TP2 / TP3 | | ✅ (labels only) |
| Closing losers before the daily close | | ✅ |

  If the PC or MT5 goes offline, an open trade keeps its **last stop** at the broker, so it stays
  protected, but it won't bank TP1, move to breakeven or trail until the EA is running again.

---

## Worked SELL example (illustrative numbers)

1. A red marubozu on the 9 EMA: high 4210.00, low 4205.00 ($5, more than 0.55 × ATR). Last support 4198.00.
2. The next candle breaks **4204.80** → **SELL 1 lot at 4204.80**.
3. **Stop** 4213.50 (4210.00 + $3.50) = **$870 risk**. **TP1** 4198.00 ($6.80 away).
4. Price reaches **4199.70** (75% of $6.80) → **stop to 4204.80**. The trade is now risk-free.
5. Price touches **4198.00** → **0.50 lot closed, +$340**. The stop on the other 0.50 moves to
   **4200.00**.
6. Price falls to 4190.00 → the stop follows to **4192.00** (TP2 is passed and only logged).
7. Price bounces to 4192.00 → **the second half closes, +$640**. Total about **+$980**, minus $4
   commission.

---

*Not covered here:* `Saad_strategy_15min_pyramiding_max_3`, which adds positions as a trade moves its
way (report.md §21–23). Full background and backtest numbers: report.md §24.
