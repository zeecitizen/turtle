# Sir Sajid Ahmad's "Volume Spread Imbalance Shift Analysis" (VSISA) — Rule Spec

Synthesized from 19 of 22 transcripts (Hindi/Urdu, ~225KB) of the YouTube course "Volume Spread Imbalance Shift Analysis" by Trade with Forex Master, plus the Waqas Ahmed CSM tutorial.

**TARGET: XAUUSD (gold)** — per Zee's confirmation 2026-05-07.
**CSM filter is NOT applied** for XAUUSD because gold is not a currency pair and CSM tools don't expose XAU strength. The CSM section below is preserved for reference / future currency-pair extensions.

---

## 1. Core Thesis

The market alternates between **buy-side imbalance** and **sell-side imbalance**. A "shift" in that imbalance is the trade signal. The shift is detected by reading the **interaction of price spread and volume on consecutive candles**.

Key idea: **big volume by itself is ambiguous** (50% buy / 50% sell). The volume of the *next candle* (the reaction) reveals which side really won.

---

## 2. Setup Detection — the Imbalance Shift pattern

There are **two mirrored setups**: BUY (after sell-side imbalance shifts to buy-side) and SELL (after buy-side imbalance shifts to sell-side).

### SELL setup (buy→sell shift)
1. Market is in an uptrend / ranging-up move.
2. **Effort bar**: a candle (any direction, often bullish) appears with **big volume relative to the recent session** (compare to the last 2-3 days' big volumes — *not* the VSA indicator's coloured bands, which the speaker says are misleading).
3. **Reaction bar (the trigger)**: the very next candle is bearish AND
   - **Engulfs** the body of the prior candle (full-range engulf preferred), AND
   - Has **low volume** (smaller than the effort bar's volume — typically <50%).
4. Optional confirm: **3-bar variant** — three consecutive up-bars with big volume, then a bearish reaction.
5. Optional strongest variant — "fake break of prior support/resistance + reversal" or "small candle with disproportionately large volume" (anomaly).

### BUY setup (sell→buy shift)
Mirror image:
1. Market in downtrend / ranging-down.
2. **Effort bar**: down-bar with big volume (could be aggressive selling OR absorption — ambiguous on its own).
3. **Reaction bar**: bullish candle that engulfs the prior body with **low volume**.
4. Same 3-bar/anomaly variants.

---

## 3. Hard Filter — Currency Strength Meter (CSM)

The speaker repeats this **on every example**: VSA alone produces too many losing trades. The CSM filter is the highest-impact gate.

For each currency pair, both currencies are scored 0-10 on instantaneous strength (the speaker uses what looks like a CSM tool — likely an external indicator).

**Rule:**
- Compute `strength_diff = |strength(base) - strength(quote)|`
- If `strength_diff ≥ 3` → **SKIP the trade** (one currency too dominant; reversal will fail)
- If `strength_diff ≤ 2` → **TRADE OK** (currencies "comparatively close" — reversal likely to play out)
- Optimal: difference around 1, with the *intended-direction* currency gaining strength while the other loses

**Direction sanity check:**
- For SELL on EUR/USD: USD must be (or be becoming) STRONGER than EUR
- For SELL on GBP/JPY: JPY must be (or be becoming) STRONGER than GBP
- If the "weak" currency is actually strengthening, skip even if VSA aligns

**ATS / AR break wait rule:**
- After VSA setup forms, draw the **Automatic Support (AS)** for sells / **Automatic Rally (AR)** for buys (the small reaction the effort bar made before the engulf)
- **Wait for AS/AR to break** before entry — this is the confirmation
- During the AS/AR break, re-check CSM: if the strength differential has *narrowed* to ≤2, take the trade. If still ≥3, skip.

---

## 4. Multi-Timeframe Workflow

| Step | Timeframe | Purpose |
|---|---|---|
| Trend context | H1 | "Trend direction" — only take setups WITH the H1 trend (don't catch tops/bottoms) |
| Setup detection | M15 (or H1 zoomed) | Identify the effort+reaction pattern in a confluence zone |
| Confluence zone | H1 with Fibonacci | Setup must form in **Fib 50%–61.8% retracement** of the prior swing |
| Entry execution | M5 | Refine entry on the AS/AR break with low volume |

**Session timing:**
- **London open** (~12:00–13:00 PKT, summer/winter shifts) is the highest-volume session — best for setups.
- Asian session: smaller volumes, but aggressive AUD/JPY/NZD pairs work well there.
- Avoid trading when current session's volume is unusually low (no liquidity → fakeouts).

---

## 5. Entry Rules

### Aggressive entry (speaker's preference)
- Enter at the **close of the reaction (engulf) bar** on M5 — same bar as the signal
- Stop loss: above (sell) / below (buy) the engulfing bar's high/low + small buffer

### Conservative entry (recommended for beginners)
- Wait for AR/AS to break with low volume (M5)
- Enter at the close of the AR/AS break bar
- Stop loss: above the recent up-thrust (sell) / below recent down-thrust (buy)

---

## 6. Exit Rules / Risk Management

- **Stop loss:** beyond the engulfing bar (aggressive) or beyond the AR/AS line (conservative)
- **Profit booking:** scale out — book ~30-50% at **1R**, more at **2R**, let runner go to **4R typical**
- "Don't be greedy — once 1R hit, book partial. Don't watch a winner round-trip."
- The speaker emphasizes 1:4 R:R as achievable **on filtered, in-trend setups only**

---

## 7. Disqualifiers (skip the trade)

| Condition | Reason |
|---|---|
| Reaction bar has **high** volume (not low) | Imbalance hasn't shifted — both sides still active |
| Strength differential ≥ 3 | Dominant currency will overpower the reversal |
| Effort-bar volume not "big enough" relative to recent session | Not significant enough to mark institutional activity |
| Engulf bar doesn't fully engulf the prior body | Weak signal |
| H1 trend opposite to setup direction | Counter-trend trades have low WR ("don't catch tops/bottoms") |
| Asian session in slow-volume environment | No conviction; high fakeout risk |
| Setup outside Fib 50-61.8% zone of prior swing | Not at the institutional decision point |

---

## 8. Key Concept Translations

| Speaker's term | Standard term |
|---|---|
| "Big volume on up bar = sign of weakness" | Climax volume / distribution |
| "Imbalance shift" | Order flow flip |
| "End of rising market" | Buying climax / churn bar |
| "Bag holding" | Stop hunt / liquidity grab |
| "AR / AS" (Automatic Rally / Auto Support) | Wyckoff AR/AS (first reaction high/low after climax) |
| "No supply / No demand test" | Wyckoff secondary test |
| "Sustain buying" (سستین بائنگ) | Continuation volume |
| "Aggressive selling/buying" | Market-order absorption |
| "VSA bands are misleading" | Don't use indicator's coloured bands; use raw volume comparison vs last 2-3 days |
| "CSM" | Currency Strength Meter (external tool/indicator) |

---

## 9. XAUUSD adaptation (final, per Zee 2026-05-07)

**No CSM filter** — Sir Sajid himself does not use CSM for gold setups because CSM tools don't expose a XAU strength reading (gold is not a currency).

**On XAUUSD we test the pure VSISA pattern stack:**
1. Effort bar with big volume (vs last 2-3 days' big volumes)
2. Reaction bar = low-volume engulf in opposite direction
3. H1 trend alignment (don't catch tops/bottoms)
4. Fib 50-61.8% retracement zone of prior H1 swing (confluence)
5. London or NY session preferred (highest volumes)

Filter variants to backtest:
- **V1 — Pure VSISA**: just the effort+reaction pattern, no other filter (baseline)
- **V2 — VSISA + H1 trend**: only trade with prevailing H1 direction
- **V3 — VSISA + Fib zone**: only trade when setup is in 50-61.8% Fib zone of last H1 swing
- **V4 — VSISA + H1 trend + Fib zone**: most selective

---

## 10. Backtest design proposal

### Inputs needed
- M5 + H1 OHLCV history (2-3 months minimum) for chosen pair
- Per-currency strength time series (computed from a basket: e.g., EUR strength = avg of EUR pairs, USD strength from DXY, etc.)

### Pseudocode
```python
for each M5 bar (in trading sessions):
    if not in_London_or_NewYork_session(): continue
    if not h1_trend_aligned_with_intended_direction(): continue
    if not in_fib_50_618_of_h1_swing(): continue
    
    # Detect VSA pattern
    effort_bar = previous_bar
    reaction_bar = current_bar
    if not (
        effort_bar.volume >= big_volume_threshold(last_3_days) and
        reaction_bar.engulfs(effort_bar.body) and
        reaction_bar.direction != effort_bar.direction and
        reaction_bar.volume < 0.6 * effort_bar.volume
    ):
        continue
    
    # CSM filter
    base_str = currency_strength(base, t)
    quote_str = currency_strength(quote, t)
    diff = abs(base_str - quote_str)
    if diff >= 3: continue  # too dominant
    
    # Direction sanity
    if (sell_signal and base_str > quote_str) or (buy_signal and base_str < quote_str):
        continue
    
    # Entry
    enter at reaction_bar.close
    sl = reaction_bar.high (sell) or .low (buy) + buffer
    
    # Exit: scale out at 1R / 2R / 4R or trail
```

### Comparison metrics
- Win rate
- Avg R per trade
- Net P&L
- Max drawdown
- Trades per week (frequency check)
- Performance with vs without CSM filter (proves whether the filter is the magic)

---

## 11. Open questions / decisions

1. ~~CSM source~~ — N/A for XAUUSD (Zee confirmed Sajid doesn't use CSM on gold)
2. **"Big volume" threshold** — defaulting to **top quartile of last 3 sessions** (matches "compare to last 2-3 days' big volumes" guidance)
3. **Engulfing** — defaulting to **full-body engulf** (stricter, matches the speaker's emphasis)
4. ~~AR/AS wait~~ — **optional** per Zee (aggressive entry at engulf-bar close is the default; AR/AS break is the conservative refinement)
5. **Instrument** — **XAUUSD** confirmed
6. **Period** — start with whatever tick CSVs we have (~5 days of 1Hz ticks aggregable to M5/M15/H1), then extend with MT5 historical M1 bars if signal looks promising
