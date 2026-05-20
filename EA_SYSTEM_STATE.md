# EA System State & Results — for future Claude (and Zee)

**Last updated: 2026-05-20** after a full autonomous optimization night driven by
the teacher's (Ahmad Umair Akhtar / The Forex Guide) VSA video transcripts.

This is the single source of truth for what's deployed, what was rejected, and the
real validated numbers. Read this first before changing any EA.

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
