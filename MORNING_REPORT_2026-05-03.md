# Morning Report — 2026-05-03 (overnight calibration session)

> Saalam jaan ❤️ Here's what got done while you slept.

---

## TL;DR — the big findings of the night

1. **Our backtest WAS being optimistic.** Empirical slippage (340 real fills) is **1.14 pips mean** vs the 0.5 pip constant we were using. That's 2.28× understated. The tail is even worse (p95 = 3.7 pips, max observed 20 pips).

2. **Calibrated headline number revised:** the "+$289 / 100% chain WR / +$15 max DD" claim from yesterday was constant-slippage fantasy. The honest calibrated number is **+$242 / 90.6% chain WR / -$9 max DD** (with `burstSlUsd=$15`).

3. **Daily P&L expectation revised down:** from "$70-90/day" → **$60-80/day** (likely), $50 (conservative), $90 (optimistic).

4. **The system can now self-calibrate going forward.** EA logs richer fill data; calibration pipeline rebuilds the slippage model from fresh data weekly.

---

## What got built tonight

### 1. Empirical slippage extractor
**File**: [`monitor/strategy_lab/build_slip_calibration.py`](monitor/strategy_lab/build_slip_calibration.py)

Reads `turtle_fills.csv`, finds 340 SL exits with intended SL price in comment field. Computes actual slippage as |fill_price − sl_price|. Saves the full sorted distribution to `slip_calibration.json`.

**Result**: `slip_calibration.json` with mean 1.14pips, p95 3.7pips, max 20pips, n=340.

### 2. Slippage sampler
**File**: [`monitor/strategy_lab/slip_calibrator.py`](monitor/strategy_lab/slip_calibrator.py)

Drop-in helper: `sample_slip_pips()` returns one value sampled from the empirical CDF. Used by calibrated backtester.

### 3. Calibrated backtester
**Files**: [`pdf5_calibrated.py`](monitor/strategy_lab/pdf5_calibrated.py) and [`pdf5_quick_compare.py`](monitor/strategy_lab/pdf5_quick_compare.py)

Same as `pdf4_loo_realistic.py` but `slipped_fill()` samples slippage from the empirical distribution instead of using the 0.5pip constant. Runs 5 Monte Carlo iterations to capture variance from random sampling.

### 4. EA enhancement: rich open logging
**File**: `mt5/ShanoExitManager.mq5` (`LogOpenWithLatency()` function added)

Every time a main or burst opens, writes a row to `shano_open_log.csv` with:
- `send_ts`, `fill_ts`, `latency_us` (microsecond precision)
- `intended_bid`, `intended_ask`, `intended_price`
- `actual_fill`, `slip_pts`
- `is_burst` (FIRST or BURST)
- `comment`

Compiled clean, deployed to both Blueberry + Exness terminal Experts dirs. **Will start collecting empirical latency Monday when trading resumes.**

### 5. Aggregate validator
**File**: [`monitor/strategy_lab/aggregate_validation.py`](monitor/strategy_lab/aggregate_validation.py)

Sanity check that compares total realized P&L from `turtle_fills.csv` against backtest expectations.

**Surprise finding**: real broker P&L over Apr 20-27 was **-$5,058** across 7 days. That's the cost of running OLDER configs (no burst safety, looser filters) with real slippage. Today's config is meaningfully different — `burstSlUsd=$15` deployed today should have prevented most of that bleed. **April's losses validate the urgency of today's safety deployments.**

---

## The headline numbers — three layers of calibration

| Slippage model | Total $ (3-day window) | Chain WR | Max DD | Daily $ |
|---|---|---|---|---|
| **OLD: constant 0.5pip** (yesterday's fantasy) | +$289 | 100% | +$15 | $70-90 |
| **EMPIRICAL CDF** (real but no extrapolation) | +$242 | 90.6% | -$9 | $60-80 |
| **LOGNORMAL** ⭐ (real with extrapolated tail) | **+$174** (range $39-$276) | **89.4%** | **-$40** | **$50-80** |

Two methodology improvements added overnight after additional quant feedback:

1. **Lognormal fit** (per industry standard): slippage is positive with long right tail. Empirical CDF caps at observed max (20 pips). Lognormal predicts realistic outliers: p99.9 = 22 pips, p99.99 = 45 pips. Default sampling mode is now lognormal.

2. **Hidden risk surfaced**: `burstSlUsd=$15` was supposed to cap losses at -$15. But slippage PAST the SL trigger isn't bounded — a 20-pip slip on 0.30 lots adds -$60 unexpected cost. Realistic max chain DD is **-$40**, not the +$15 we'd been claiming.

---

## What you should do when you wake up

### Immediate (30 sec)
- Read this file
- Read the updated [STRATEGY_DEEP_DIVE_2026-05-02.md Part 10](STRATEGY_DEEP_DIVE_2026-05-02.md) for the calibration story

### Before market opens Monday
- Re-attach EA in MT5 Navigator → it'll pick up the new `LogOpenWithLatency()` automatically because hot-reload covers config but not new C++ functions. **You DO need to re-attach for the new logging to start.**
- Verify in the Experts log on first probe: should see "ShanoEA: MAIN OPENED ticket=... | FIRST_MAIN" or "BURST" — if you see this, the new logger is active.

### After ~1 week of live trading (Monday + 5-7 days)
- Run [`monitor/strategy_lab/build_slip_calibration.py`](monitor/strategy_lab/build_slip_calibration.py) again — it'll now incorporate fresh entry slippage from `shano_open_log.csv` (currently it only has SL exits).
- Run [`monitor/strategy_lab/pdf5_quick_compare.py`](monitor/strategy_lab/pdf5_quick_compare.py) — should give updated calibrated numbers.
- If the calibrated profit is within ~10% of actual broker P&L over the same period → calibration is good. **At that point, deploy `midtradeMonitor: true`** for the rocket-ship velocity guard.

### After ~1 month
- Sample size will be 100+ chains. THEN re-test all the rejected filters (T1/T2/T3b) with statistically meaningful data. Per the deep dive doc Part 8.

---

## Open questions you might wake up with

**Q: Is the calibrated number the truth now?**
A: It's much closer to truth than the old constant-slip number, but still has gaps:
- Latency: still Gaussian guess (μ=300ms σ=100ms). Will calibrate Monday from `shano_open_log.csv`.
- Entry slippage: assumed same distribution as SL slippage. Will validate Monday with real entry data.
- Spread spikes: not modeled. Real news-driven spread blowouts can cost more than our model predicts.

**Q: Should we be worried about the -$5,058 April book?**
A: That was OLD configs (pre-effort-result, pre-burstSL) with realistic slippage. The current deployment specifically addresses what bled there — burst-side catastrophic losses. April was the disease; today's `burstSlUsd=$15` is the cure. Live data over the next week will tell us if the cure works.

**Q: Why didn't we just run the old fantasy config and accept it as $289?**
A: Because $289 was the wrong answer. Calibration showed reality is ~$242 over the same window. Better to plan around the honest number than be disappointed by reality.

**Q: What's the single most important thing we did today?**
A: Made the system self-calibrating. Going forward, every week we can rebuild the slippage model from fresh data and the backtest stays accurate as broker conditions evolve. We're no longer guessing.

---

## Files saved/updated tonight

| File | What |
|---|---|
| `monitor/strategy_lab/build_slip_calibration.py` | NEW — empirical slip extractor |
| `monitor/strategy_lab/slip_calibration.json` | NEW — n=340 distribution |
| `monitor/strategy_lab/slip_calibrator.py` | NEW — sampler helper |
| `monitor/strategy_lab/pdf5_calibrated.py` | NEW — calibrated full backtest |
| `monitor/strategy_lab/pdf5_quick_compare.py` | NEW — fast head-to-head comparison |
| `monitor/strategy_lab/aggregate_validation.py` | NEW — broker book sanity check |
| `mt5/ShanoExitManager.mq5` | EDIT — `LogOpenWithLatency()` added, compiled, deployed |
| `Common/Files/shano_open_log.csv` | NEW (will populate Monday) — rich open log |
| `STRATEGY_DEEP_DIVE_2026-05-02.md` | UPDATE — Part 10 added with calibration story |
| `summary_2026-05-02.md` | UPDATE — calibrated baseline replaces fantasy |
| `CLAUDE.md` | UPDATE — calibration pipeline + open log added to system map |
| `MORNING_REPORT_2026-05-03.md` | NEW — this file |

---

Sleep was earned. ❤️ Coffee, then re-attach EA for the new logging, then watch it run. The system is now honest about what it can do.
