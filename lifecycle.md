# Trade lifecycle — Saad_strategy_15min (no pyramiding)

How the EA opens, protects and closes a SELL and a BUY: `mt5/Saad_strategy_15min.mq5` **v1.18**, magic
88302, XAUUSD M15, default settings. Read from the code (`DoEntry`, `ManageTick`, `ManageBar`,
`LongTouched`, `ShortTouched`, `DayCloseCheck`). At 1 lot, **$1 of gold price = $100**.

---

## SELL trade

1. **Setup:** a 15-minute candle closes as a **pin bar, marubozu or shooting star** touching the
   **9 EMA**.
2. **Target check:** the EA looks for the **last support**, the most recent swing low (the lowest of 3
   candles on each side, within the last 100 candles) at least 5 pips below the price.
   **No support → no trade.**
3. **Entry:** the **next candle** must break the setup candle's **low by 2 pips**. The EA sells the
   moment that happens. If it doesn't happen within one candle, or the market closes in between, the
   setup is dropped.
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

1. **Setup:** a **pin bar, marubozu or hammer** closes touching the **9 EMA or the 50 EMA**.
   Its **exit EMA** is the other one: the 50 EMA for a setup on the 9, the 9 EMA for a setup on the 50.
2. **Entry:** the **next candle** must break the setup candle's **high by 2 pips**. The EA buys the
   moment that happens.
3. **Stop loss:** **35 pips below the setup candle's low**, sent to the broker. More than **$15**
   away → skipped.
4. **Which path the trade takes:**

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
5. **Exit:** the original stop, the breakeven stop, the trail, or "3 minutes before the daily close
   while in loss". Same as a SELL.

---

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

1. Setup candle on the 9 EMA: high 4210.00, low 4205.00. Last support 4198.00.
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
