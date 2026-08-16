# 💎 ALL DIAMONDS — what is live, why, and the proof

**Status: LIVE in `mt5/ZeeUHV.mq5` v1.25, magic 88094, attached 2026-08-16 19:21:31.**

A **diamond** is a mark of conviction. It does not decide *whether* to trade — it decides
*how much*. Every diamond a setup earns adds one more ticket to the stack.

> **THE GOVERNING RULE, learned the hard way on 2026-08-16:**
> **A thin or regime-dependent signal goes in as a DIAMOND, never as a GATE.**
> A gate acts on every trade it removes. A diamond acts only on the ones it marks. When the
> sample is small or the effect regime-bound, that difference is the entire risk.
>
> This rule exists because Zee argued for it. I had dismissed Law 6 as a "mirage" for having
> only 13 trades. He asked *"if its so good that it has a 100% winrate then why not?"* — and
> he was right: as a gate it discards 95% of trades on 13 observations, as a diamond it can
> barely hurt. It now improves all three test periods.

---

## The ticket arithmetic

```
tickets = (1 + diamonds_earned) × InpStackMult          capped at maxdia
maxdia  = 3 + (Law 6 active) + (Law 7 active) = 5       computed from ACTIVE laws
```

With `InpStackMult = 2` and `InpLots = 0.10`:

| diamonds | tickets | lots | risk at stop 5 |
|---|---|---|---|
| 0 | 2 | 0.20 | $100 |
| 3 | 8 | 0.80 | $400 |
| **5 (all)** | **12** | **1.20** | **$600** |

**The cap is computed from the active laws, never hardcoded.** A hardcoded `3` silently
discarded a 4th diamond once before and made a whole test return numbers identical to the
cent — the bug looked like "the change did nothing".

---

## The five live laws

### Law 1 — THE SWEEP
Price poked beyond the UHV's extreme in the 20 bars before it, then came back.

```cpp
for (int k = uhv + 1; k <= uhv + 20; k++) {
   if (side > 0 && bLow(k)  < lo) { d++; break; }
   if (side < 0 && bHigh(k) > hi) { d++; break; }
}
```
**Origin:** Zee's own labels, 2026-08-10. Wyckoff calls it a Shakeout/Spring — stops cleared
below a low so institutions can fill. His second PDF independently listed it as a law we
already had.

### Law 3 — THE EMA-5 CLOSE
The breakout candle closed decisively past the 5-period mean, by at least 0.10.

```cpp
double e5 = Ema5(1);
if (side > 0 && IsGreen(1) && bClose(1) > e5 + 0.10) d++;
if (side < 0 && IsRed(1)   && bClose(1) < e5 - 0.10) d++;
```
**Origin:** Zee's labels, 2026-08-10. Momentum confirmation, not a nervous poke.

### Law 5 — THE WICK AND THE VOLUME
The breakout has a small wick against it **and** is quieter than the UHV.

```cpp
double wick = (side > 0) ? (bHigh(1) - MathMax(bOpen(1), bClose(1))) / rng
                         : (MathMin(bOpen(1), bClose(1)) - bLow(1)) / rng;
if (wick <= 0.25 && BarVolume(1) < BarVolume(uhv)) d++;
```
**Origin:** Zee's labels, 2026-08-10. The VSA "No Supply" idea — supply exhausted, so the
break meets no resistance.

### Law 6 — THE UHV IS GENUINELY *ULTRA*  ⭐ NEW 2026-08-16
Volume at least **2×** the 20-bar average — high in *absolute* terms, not merely the loudest
of the last 20.

```cpp
if (InpUhvVolDia > 0) {                       // = 2.0
   double av = AvgVolBefore(uhv);
   if (av > 0 && (double)BarVolume(uhv) >= av * InpUhvVolDia) d++;
}
```
**Origin:** Zee's PDF *"The MT5 Laws of Conviction"*, `InpUHVVolumeMultiplier`. It exposed a
real gap — we had called it Ultra High Volume for six months while only ever requiring it be
the loudest of 20. In a quiet stretch that can be a perfectly ordinary candle.

**Proof — as a GATE it is dangerous, as a DIAMOND it is free:**

| | LIVE 11-13 | Mar 02-16 | Jun 01-15 |
|---|---|---|---|
| baseline | 67 · +1.27 | 228 · −1.65 | 368 · −0.23 |
| as a **gate** ×2.0 | **4** · +2.14 | **3** · +2.75 | **6** · +1.83 |
| as a **gate** ×1.5 | 12 · −1.03 | 17 · +1.82 | 33 · −0.75 |
| as a **DIAMOND** ×2.0 | 68 · **+1.28** | 229 · **−1.63** | 369 · **−0.22** |

The gate at ×2.0 wins 13 of 13 — but **13 straight wins is a 19.1% coincidence** at our
88.06% baseline, and loosening to ×1.5 (62 trades) fails in two of three. As a diamond it
improves all three periods for **+$7.36** total. Small, safe, positive.

### Law 7 — THE SELLING CLIMAX  ⭐ NEW 2026-08-16
The UHV is not merely loud — it is the **widest bar of the last 60**.

```cpp
if (InpClimaxDia > 0) {                       // = 60
   double r7 = bHigh(uhv) - bLow(uhv);
   bool widest = true;
   for (int i = uhv + 1; i <= uhv + InpClimaxDia; i++)
      if ((bHigh(i) - bLow(i)) > r7) { widest = false; break; }
   if (widest) d++;
}
```
**Origin:** Zee's second PDF, *"Selling Climax & Automatic Rally"*. Capitulation absorbed by
smart money; the break of that bar's extreme is the Automatic Rally.

**Proof:** better in all three periods (LIVE +2.14, Mar −1.21, Jun +2.08 against baselines
+1.27 / −1.65 / −0.23) — but on **15 trades total**. Diamond only, for exactly the Law 6
reason.

---

## Measured effect of adding Laws 6 and 7

Real ticks, 163 ms delay, at the **actual live configuration** (0.10 lots, StackMult 2),
11–13 Aug:

```
v1.23   3 diamonds   134 tickets   88.06%   +838.80   DD 8.42%
v1.25   5 diamonds   138 tickets   88.41%   +881.50   DD 8.35%
                     +4 tickets   +0.35pp   +$42.70   −0.07pp
```

More money, higher win rate, slightly lower drawdown, four extra tickets.

---

## Rejected — and why (do not re-add without new evidence)

| candidate | tried as | result |
|---|---|---|
| **H1 alignment** | diamond | **WORSE** than shipped (−586.72 vs −559.10 over 5 periods). Its value is *removing* bad trades, not sizing good ones — it belongs as a gate. Expectancy barely moved as a diamond (+1.27→+1.31), proving the aligned trades aren't better; the misaligned ones are worse. |
| Squat bar (narrow UHV) | gate | +2.36/trade in the live window, **−3.37 in March**. Also directly contradicts effort-vs-result, which wants a *wide* spread. Each wins in a different regime. |
| Effort vs result (range/vol) | gate | Helps March (−1.65→−0.83), wrecks the live window (+85→+28). |
| UHV range ≥ ATR ×1.2/1.5 | gate | Fails in two of three. |
| UHV close position ≥ 0.4 | gate | No trades in the live window; negative elsewhere. |
| Pre-breakout compression | gate | 1 of 3. |
| Pullback ≤ 0.618 | gate | 2 of 3 — March much worse. |
| Next-bar fails to extend | gate | 1 of 3. |
| Breakout close position | gate | Inconsistent in both directions. |
| Break window 5 vs 12 | gate | **Completely inert** — the break, when it comes, always arrives within 5 bars. Never sweep this again. |
| Diamonds vs flat sizing | — | At *equal exposure* they are identical (avgW ratio 4.02, avgL 3.98). The diamonds multiply; they do not select. Keeping them is a sizing choice, not an edge. |

---

## Sitting outside as its own EA

**`mt5/ZeeUHV_Loud_Breakout.mq5`, magic 88104, tag `[LOUD]`** — Wyckoff's *Push Through
Supply* directly contradicts Zee's rule that the breakout must be quieter than the UHV. This
EA keeps **both**: quieter than the UHV **and** ≥ 0.8× its volume — the loud end of the quiet
breakouts.

```
ZeeUHV_Loud_Breakout    94 tickets  100.00%  +$1,000.60  DD 2.28%
live ZeeUHV            138 tickets   88.41%    +$881.50  DD 8.35%
```

**45 straight wins at an 88.06% baseline is a 0.33% coincidence** — a hundred times less
likely than Law 6's thirteen. So the effect is real. But March (−2.31 vs −1.65) and June
(−0.35 vs −0.23) say it is **regime-dependent**, and only the live market can say whether the
current regime is its regime. It needs its **own chart** — MT5 runs one EA per chart.

---

## For the next session

- Everything above is measured on **MT5's Strategy Tester with real ticks**. No Python result
  has ever promoted anything here, and none should.
- **Rank by expectancy per trade, never by win rate.** `NullBurst` scored 91.36% at random on
  22,000 trades and lost $19,132.
- **The average loss decides everything.** Across 13 windows avgW spans a factor of 1.3 while
  avgL spans a factor of **83**.
- Candidates and full results: [testing/LAWS_OF_CONVICTION_CANDIDATES.md](testing/LAWS_OF_CONVICTION_CANDIDATES.md)
- Before believing any new law, re-run the baseline first. Dead code has moved results in
  this repo before — see the Watcher.
