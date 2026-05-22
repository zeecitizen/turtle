# EA System State & Results — for future Claude (and Zee)

**Last updated: 2026-05-22** — added "2R Free Roll" profit protection (breakeven /
partial scale-out) after a research doc (Protecting Peak Trading Profits.pdf) and a
live scare (two S3 buys floating +$168 with no trailing). Prior full update 2026-05-20.

This is the single source of truth for what's deployed, what was rejected, and the
real validated numbers. Read this first before changing any EA.

---

## S4Trader (magic 88007) — CANDIDATE, NOT DEPLOYED — Zee's Feb-11 entry mechanized

2026-05-21 overnight: full investigation of why Zee's Feb-11 day (~27 fills, manual,
~94% WR) couldn't be reproduced. Findings (all committed, see backtest_feb11_*.py):

- Zee's Feb-11 method = the simple **Lesson-2 "our strategy" UHV breakout** (he names
  it in lesson02.txt right after the Qatar/Doha-airport anecdote — "$70k in one day on
  a $200k account, just this strategy"). It is NOT S1/S3/NSND mechanics: classify_feb11.py
  showed only ~12/27 matched those.
- Trend = **same-TF HH/HL structure** ("camel humps"), NOT 1H+5min.
- His **exit (scalp/skim + scratch on first reversal) does NOT mechanize** — needs his
  94% discretionary hand. Mechanical proxies (peak-trail, intrabar, velocity-gated) all
  land 12-32% WR vs his 94%. The edge there is tape-reading, not a rule.
- BUT his **ENTRY does mechanize**, and over-filtering is why S1 is rare: the simple UHV
  breakout (NO sweep/big-spread/FVG) + HH/HL structure fires **~14/day** (vs S1 1.5/day).
- Paired with a mechanical **2:1 exit (TP12/SL6)** it is **walk-forward robust**:
  TRAIN +$1782 / TEST +$473 @0.10; the whole TP9-13 x SL5-7 grid is train+/test+ (broad
  plateau, not overfit); ~38% WR; 7/13 green days.

2026-05-22: added a **regime filter** (Kaufman efficiency ratio over the trend window,
InpERMin=0.15) — skips ranging/choppy markets where S4 bleeds (Zee's own observation).
Backtest: ER>=0.15 keeps ~all profit while lifting OOS +$473->+$629, WR 37->38%+,
8/13 green, ~1/3 fewer (choppy) trades. ER 0.15-0.20 is a robust plateau; >=0.30
over-filters (OOS turns negative). Validated lever, baked in as default.

S4Trader.mq5 implements exactly this (M1, BUY+SELL, TP12/SL6, ER>=0.15 regime filter,
0.02 lots FTMO-safe, circuit breaker + grab + heartbeat). Compiled into all terminals,
**NOT attached.**
CAVEATS before live: 13 days only; 38% WR = many losers (psychologically harder);
worst day -$536@0.10 (>FTMO -$300, hence 0.02 lots); forward-test first. It is a
DIFFERENT profile from the selective EAs (high-freq / low-WR / 2:1) — could complement
or replace S1. Awaiting Zee's review + a forward-test before deployment.

---

## 2R FREE ROLL — profit protection (added 2026-05-22)

Tested per-EA on 13 real-tick days, same deployed signals, only the exit varies.
Harnesses: `monitor/strategy_lab/backtest_exit_protocols.py` (S3),
`backtest_exit_protocols_multi.py` (S1 + NSND). Side-aware tick-level manager
`ManageOpenPositions()` added to all three EAs (magic-scoped, manages already-open
trades on reattach by capturing each position's ORIGINAL SL on first sight).

| EA | Deployed | baseline → chosen | Why |
|----|----------|-------------------|-----|
| **S3** (88003) | **BE@+1R + partial 50%@+1.5R, keep TP** (both ON) | +$115 → **+$250**, worst −$87.8→−$62.9, WR .60→.80 | catches the give-back-to-zero. **n=5 — PROVISIONAL.** |
| **NSND** (88006) | **breakeven ON, partial OFF** | +$475 → **+$518**, WR 31%→53%, PF 3.13→4.13, OOS +$311→+$330, **n=93** | partial DILUTES (+$488, caps big runners); BE-only is best & robust |
| **S1** (88004) | **both OFF (inert)** | +$431.8 → +$431.8 (identical) | SL at UHV-red low ⇒ 1R usually wider than the $7.5 TP, so BE/partial can't arm before TP. n=34. Toggle left in code. |

**REJECTED for all three:** the doc's headline move — drop the static TP and trail the
runner on 3×H1-ATR (Chandelier). It scored *worse* than keeping our TP every time
(S3 +$187<+$250; NSND +$443<+$475 = below baseline). Our small-TP scalps beat a
trend-runner trail on XAU. Do not add it.

Inputs (all EAs): `InpEnableBreakeven`, `InpBreakevenR`, `InpEnablePartial`,
`InpPartialR`, `InpPartialFrac`, `InpBEBufferPts` ($0.30 above/below entry).

---

## TL;DR — the honest numbers

- **3 live EAs on XAUUSD** (Blueberry demo), all at 0.02 lots, all on validated configs.
- **Combined backtest (12 days real ticks, @0.02): +$625.8, avg +$48/day, 11/13 positive days, max drawdown $12.5 (2.5% of the $500 live capital).**
- **Realistic win rate ≈ 65%** with strong positive expectancy. NOT 90%+. Anyone
  claiming a near-100% WR on this system is looking at a small/one-directional sample
  (e.g. a single trending session). High-WR/tiny-TP traps blew up earlier strategies —
  see memory `feedback_validate_profitability_not_capture`.
- **Live confirmation:** 2026-05-20 ran 6/6 wins +$72.42 (favorable trending day, small
  sample). 2026-05-19 did −$38 on the day (worse than any backtest day). Both are normal.

---

## DEPLOYED CONFIGS (validated on 12d real ticks + walk-forward; all reversible input flags)

### S3Trader.mq5 (magic 88003) — Liquidity-sweep entry = teacher Lesson 10
- Buy-only. Green candle sweeps a retracement red's low, closes back inside, higher volume.
- **`InpRequireM5Fvg=true`** — same-TF (M5) FVG tap. Walk-forward: EV/trade $13.78→$26.24,
  WR 63→69%, holds OOS (~2× EV both halves). H1 FVG was too coarse (only 7 trades/12d).
- **`InpMaxUpperWickFrac=0.35`** — reject if the green's upper wick > 35% of range (teacher
  "no rejection" rule). WR 63→69%, EV +19%.
- SL = wicking-green.low − $2.00; TP = peak of last 10 M5 bars.

### S1Trader.mq5 (magic 88004) — UHV/Climactic-Action-Bar breakout = Lesson 2 / VSA Scenario 3
- BUY+SELL. Highest-volume bar in retracement, sweep of its extreme, break of its other side.
- **`InpRequireBigSpread=true`, `InpBigSpreadMult=1.3`** — the climax bar must be a BIG-SPREAD
  candle (range ≥ 1.3× avg of prior 10), not just highest-volume. Walk-forward: OOS test
  +$413 vs +$168 baseline, **80% WR, EV $41.30** (3.4× baseline). Strongest single win of the night.
- SL = UHV extreme ± $2.00; TP = $7.5 pts.

### NsndTrader.mq5 (magic 88006) — No Supply/No Demand = Lessons 6-7
- M1 NS/ND candle (small spread, vol < prev2), prior UHV, sweep+break entry.
- **`InpUseH1Fvg=false`** → M15-only FVG. Walk-forward: WR 54→62%, train +$489→+$598,
  identical on test (every H1-FVG signal also had M15 FVG). Strictly ≥ old M15+H1.
- SL tiny (past the NS/ND candle); TP $12.

### THE UNIFYING INSIGHT (most important takeaway)
**Each setup's FVG must come from its OWN structure timeframe**, not a one-size H1:
- S3 (M5 liquidity sweep) → **M5** FVG
- NSND (M1 NS/ND) → **M15** FVG
- S1 (UHV breakout, a higher-TF structural event) → **H1** FVG
The old "H1 FVG for everything" was the systematic mistake. Matching each fixed all three.

---

## REJECTED (tested honestly, would NOT deploy — discipline that protects the account)

| Idea | Why rejected |
|---|---|
| Absorption-candle breakout (Lesson: ddvZYdA2ETo) | In-sample +$875 but **walk-forward train +$2491 → test −$1616**. Textbook overfit. |
| S3 add sell-side / bidirectional | Sells lose on gold's bullish bias (−$46); bidirectional +$1450 < buy-only +$1496. Keep buy-only. |
| H1 hard trend-gate on S3 | Raises WR to 78% but LOWERS total (+$1382 vs +$1496) on bullish data. Regime guard, not net-positive. |
| M1 scalper EA (2mKEfO85D04) | = S1-on-M1; spread eats tiny TPs; low-vol-breakout already proven to hurt. |
| S1 momentum/low-vol breakout filter | Cuts P&L ~70% even combined with big-spread (+$430 vs +$849). |
| S1 definite-low SL | No OOS improvement (−$27 vs baseline). |
| NSND 1-Day trend filter | Turned +$784 into −$68. |
| NSND asymmetric sell-TP | Marginal −$6 OOS. |
| S2 Engulfing as standalone EA | Net negative on 12d. |

---

## PORTFOLIO ANALYSIS (deep study — portfolio_deep.py)

### Per-EA risk (daily, @0.02 lots)
| EA | total | mean/d | std/d | Sharpe | worst | maxDD |
|---|---:|---:|---:|---:|---:|---:|
| S3 | +$299 | +$23.0 | 34.7 | 0.66 | −$21.1 | $21.1 |
| S1 | +$170 | +$13.1 | 12.7 | **1.03** | $0.0 | $0.0 |
| NSND | +$157 | +$12.1 | 28.3 | 0.43 | −$16.6 | $16.6 |

### Daily P&L correlation
```
        S3     S1   NSND
S3    1.00  -0.13   0.66
S1   -0.13   1.00  -0.26
NSND  0.66  -0.26   1.00
```
- **S1 is the diversifier** — negatively correlated with both S3 and NSND, highest Sharpe,
  never had a losing day in the backtest. It smooths the whole portfolio.
- **S3 & NSND are +0.66 correlated** (both buy reversals) — they tend to win/lose together.

### Lot allocation @ fixed 0.06-lot total budget
| scheme | S3 | S1 | NSND | total$ | Sharpe | maxDD$ |
|---|---:|---:|---:|---:|---:|---:|
| equal (current live) | 0.020 | 0.020 | 0.020 | +625.8 | 0.86 | 12.5 |
| **EV-weighted** | 0.029 | 0.016 | 0.015 | **+685.1** | 0.82 | **8.0** |
| Sharpe-weighted | 0.019 | 0.029 | 0.012 | +623.3 | **1.04** | 6.1 |
| inverse-vol | 0.012 | 0.033 | 0.015 | +578.3 | 1.13 | 9.8 |

- **EV-weighted (tilt to S3 ~0.03) gives +9% more return AND lower drawdown** ($8 vs $12.5).
- **Sharpe/inverse-vol (tilt to S1) give the smoothest equity** (Sharpe ~1.1) at slightly less total.

### DEPLOYED 2026-05-20 (Zee approved): EV-weighted lots, total budget UNCHANGED at 0.06
- **S3 = 0.03** (highest EV), **S1 = 0.02** (diversifier, kept), **NSND = 0.01** (most volatile, underweighted).
- Total exposure identical to old equal-0.02 (0.06), just redistributed → same worst-case day,
  ~+9% expected return. Reattach S3 + NSND in MT5 to load (S1 unchanged).
- Honest caveat: this is in-sample weighting; the robust facts (S1 diversifies, S3 highest EV,
  NSND most volatile) justify the tilt, but don't over-trust the exact +9%.

---

## HONEST CAVEATS (read these before trusting the numbers)
1. All backtests are **in-sample on a 12-day, mostly-bullish window** (Apr 29–May 14).
   Real forward will be lower with bigger drawdowns. Treat +$48/day as a CEILING.
2. The lot-allocation optimum is mild curve-fitting; the **robust** facts are: S1
   diversifies, S3 has the highest EV, equal weighting already works.
3. ShanoTickLogger must stay attached or we lose the data that powers all of this.
4. Win rate is ~65%, not magic. The edge is **positive expectancy + low drawdown +
   3 low-correlation EAs**, which is what compounds an account safely.

## Teacher lesson → EA mapping
L2 UHV breakout → S1 · L6-7 No Supply/Demand → NSND · L8 engulfing → (S2, not deployed) ·
L9 liquidity-grab (theory) · L10 liquidity-sweep entry → S3. 48/108 channel videos
transcribed (monitor/_loom_audio/yt_*.txt); rest blocked on OpenAI credits.

## Key scripts (all local, free to re-run)
- `monitor/strategy_lab/portfolio_study.py` / `portfolio_deep.py` — combined P&L, correlation, allocation
- `monitor/strategy_lab/s1_video2_backtest.py` / `s1_video2_walk_forward.py` — S1 big-spread
- `monitor/strategy_lab/s3_fvg_timeframe_sweep.py` / `s3_m5fvg_walk_forward.py` — S3 M5-FVG
- `monitor/strategy_lab/nsnd_walk_forward.py` — NSND M15-only
- `monitor/strategy_lab/backtest_teacher_faithful.py` — the 3 teacher-fix tests
- `monitor/strategy_lab/live_rule_ledger.py` — forward-tests atomic rules on live candles
- `monitor/strategy_lab/NIGHT_PLAN_2026-05-20.md` — full overnight work log
- recompile EAs: `powershell mt5/install_eas.ps1` (then detach+reattach in MT5 to load)

---

## SHANO-PROBE OVERLAY — tested 2026-05-20, SHELVED (not deployed, revisit w/ more data)
Hypothesis: add Shano's probe (enter only if price moves +confirm in our favor before
−fail, within a short window) as a momentum-confirmation gate on our EA entries.

- Optimistic first cut (probe as pure filter, entry at signal price): S3 WR 68→83%,
  NSND 55→79%. Looked great.
- HONEST re-test (realistic: enter at the confirmed price paying the move+spread, same
  engine for baseline & probe, + walk-forward train6d/test6d):
  - S3 probe 0.30/0.30/30s: in-sample WR 68→78% BUT OOS test EV $4.64 ≈ baseline $5.38,
    total LOWER ($42 vs $97). In-sample mirage, no real OOS edge.
  - NSND probe 0.45/0.45/60s: OOS WR 75% / EV $8.11 looks great BUT test sample = only
    n=4 trades (probe cut frequency ~half). Statistically meaningless.
  - Both reduce TOTAL $ at fixed lots. S1 (already a breakout) is HURT by the probe.
- VERDICT: do NOT deploy. Classic in-sample-WR trap that walk-forward + realistic entry
  strip away. Script: shano_probe_realistic.py (honest), shano_probe_overlay.py (optimistic).
- REVISIT WHEN: ShanoTickLogger has accumulated ~30+ tick-days (collecting daily now).
  Then the OOS sample is big enough to truly judge. The probe DOES raise in-sample WR on
  reversal EAs (S3/NSND) — promising, just unproven on current 12d.

---

## ICHIMOKU CONFLUENCE SCALP — tested 2026-05-20, REJECTED (loses on XAUUSD)
Source: "Systematizing Alpha" Ichimoku scalping PDF (Strategy II: Kumo + EMA21 + RSI9
confluence, M5). Genuine backtest: real Ichimoku math (Tenkan/Kijun/Kumo/SpanA-B + 26
shift), EMA21, RSI9, real tick fills (buy/sell-stop trigger + bracket), both param sets
(std 9/26/52 and accelerated 5/13/26), TP sweep, walk-forward. Script: ichimoku_backtest.py.

RESULT — does NOT work on gold:
- High-WR fixed-TP configs (up to 78% WR) all have Profit Factor 0.47-0.96 -> net LOSS
  (tiny $2-5 wins vs $17-20 losses = the high-WR/tiny-TP trap the PDF itself warns about).
- Only R:R 2.0 showed a small positive on full 12d (PF ~1.08) BUT walk-forward destroyed it:
  std R:R2.0 TRAIN +$404 (PF 2.23) -> TEST -$321 (PF 0.58); acc R:R2.0 TRAIN +$485 -> TEST -$373.
  Regime-dependent (worked only on trending train half), not a real edge.
WHY: Ichimoku lags on M5 gold (buys top of impulse); small TPs eaten by spread/noise;
R:R 2.0 needs sustained trends gold's chop rarely gives. The PDF's 80%/6.0-PF/2944% claims
are forex majors / crypto / cherry-picked trend conditions, NOT validated OOS on gold.
VERDICT: do not deploy. Confirms VSA reversal EAs (S1/S3/NSND) are the right tool for gold;
trend-following Ichimoku is not. Do not re-test unless on a different (trending FX) instrument.
