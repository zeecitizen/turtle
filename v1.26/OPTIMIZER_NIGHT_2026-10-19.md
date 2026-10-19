# Why there is no v1.27 (yet): the overnight optimizer, 2026-10-19

Zee asked (06:40 PKT, before sleeping): *"run the optimizer that runs for next ~8 hours ... put every single setting into it that can be
tuned to make a better version of the v1.26 ... once u have sufficient data to improve upon 1.26 -> build and compile the 1.27"*.

**Result: nothing beat v1.26 on the months it was not tuned on, so v1.27 was not built. v1.26 stays the version to attach.**

## What ran

- **The search:** MT5's genetic optimizer on 26 settings around v1.26's values. It ran 06:45 – 12:46 PKT and was restarted once after an MT5 crash at 07:54.
  - Settings searched: EMAs, candle shape, touch, break, ATR stop, max risk (at or below $20), ADX, chop, ATR band, trading hours, the trend filter, range lookbacks, stand aside vs skip, and the breakeven / lock / partial options.
  - It learned on **Jan–Jun only** and scored each test by net ÷ max drawdown (at least 60 trades).
  - **About 4,980 tests.** Every one was decoded from the agents' logs and checked against the settings the EA printed: 5,045 of 5,045 matched.
- **Check 1:** the best 40 distinct settings plus v1.26 on **Jul 1 – Oct 16**, the months the search never saw. Random delay.
- **Check 2:** the 8 best of those plus v1.26 on the **full year, twice each**. Random delay.
- **Check 3:** every change the top 40 kept repeating, applied **alone** to v1.26 on the full year. A change only counts if it helps in **both** halves.

Pipeline: `monitor/strategy_lab/v127_night_run.py`, then `v127_single_changes.py`. Data: `v127_night.json`, `v127_single.json`, `v127_status.json`.

## The numbers (MT5, Blueberry real ticks, $100k, 2 lots)

**Jul–Oct (never seen by the search):**

| | Net | PF | Max DD |
|---|---|---|---|
| **v1.26** | **+$86,254** | **2.62** | $17,174 |
| best of the 40 | +$73,976 | 1.85 | $30,532 |
| the top Jan–Jun scorer | **−$12,017** | 0.91 | $39,576 |

**Full year (two random-delay runs each):**

| | Net | PF | Win rate | Max DD |
|---|---|---|---|---|
| **v1.26** | **+$213,085 / +$208,795** | 2.54 / 2.50 | 53% | $34–36k |
| c07 (EMA 12/36, break 6, ADX 20, max risk 15, ATR $3–25, skip, BE $8 + lock) | +$168,198 / +$202,258 | 1.72 / 1.85 | 46% | $23k |
| c13 (EMA 12/24, break 4, ADX 20, max risk 15, ATR $3–25, skip, BE $8, lock +$6 at +$8) | +$170,277 / +$177,249 | 2.01 / 2.07 | **38%** | **$17.5k** |

**Each repeated change alone on v1.26** (full year; the right-hand columns are the change against v1.26 in each half):

| Change | Year net | PF | Max DD | Jan–Jun | Jul–Oct |
|---|---|---|---|---|---|
| v1.26 | +$211,539 | 2.52 | $34,356 | | |
| ATR min $3 | +$212,769 | 2.55 | $35,304 | −$3.6k | +$4.8k |
| trade until midnight PKT | +$209,995 | 2.53 | $36,328 | −$4.4k | +$2.9k |
| body max 0.7 | +$209,965 | 2.50 | $36,934 | −$5.1k | +$3.5k |
| SELL on either EMA | +$209,871 | 2.51 | $33,230 | +$1.6k | −$3.2k |
| stand aside → skip | +$202,687 | 2.33 | $37,878 | −$6.5k | −$2.4k |
| LONG on the fast EMA only | +$183,041 | 2.66 | $23,204 | −$32.4k | +$3.9k |
| ADX 20 | +$179,899 | 1.38 | $44,051 | −$9.6k | −$22.1k |
| breakeven at +$8 | +$161,403 | 2.46 | $28,320 | −$34.3k | −$15.9k |
| max risk $15 | +$155,827 | **2.73** | **$19,914** | −$49.1k | −$6.6k |
| fast EMA 12 | +$152,383 | 1.74 | $50,757 | −$45.1k | −$14.1k |

Two runs of the same settings differ by about ±$4k, so the top four changes are noise.

## What it means

- **v1.26 is already at its peak.** No combination and no single change made more money in both halves of the year.
- **The genetic search fitted Jan–Jun.** Its favourite settings (ADX 20, EMA 12, breakeven at +$8, skip) each cost v1.26 money on their own, and its top scorers lost on Jul–Oct.
- **The one honest alternative, if a calmer ride is wanted:** **max risk $15**. It gives PF 2.73 and a drawdown of $19.9k instead of $34.4k, but about $56k less profit over the year.
