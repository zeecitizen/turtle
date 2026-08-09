# Overnight, 10 August 2026 — while you slept

You said: *"build them all... bring me answers without me having to intervene."*
Here they are. Two of them contradict things we believed yesterday.

---

## 1. The headline: **you buy weakness. Every engine we built buys strength.**

Measured from your own thirteen timestamped Feb-11 entries, against a null baseline of
400–600 random moments from the same day:

```
                     fades the move   buys the cheap third   BOTH
YOU, 13 entries           69%                 50%             50%
random moments            46%                 38%             18%
S1Trader, its 8 trades     0%                 12%              0%
```

**Our engine has never once done what you do half the time.** And it never can — its
buy condition is `close > UHV-high`, which by construction means price must be *rising*
at the moment it buys. You buy while price is still *falling*, in the cheap third of the
hour's range.

That is why nothing we did yesterday worked. Not the exits, not the filters, not the
risk bound. **We were tuning the wrong animal.** A breakout engine cannot be tuned into
a fade trader any more than a hammer can be tuned into a spanner.

---

## 2. ⚠️ The June "universal gate" is refuted — do not build it

The taxonomy said: *"rng60_norm ≥ 1.20 — every single Feb 11 entry occurred during
60-second volatility expansion. A NECESSARY pre-filter."*

Measured at your exact entry seconds, from 448,294 real ticks:

```
YOUR entries      median 1.04    ·  4 of 13 pass ≥1.20   (31%)
random moments    median 1.02    ·  39% pass ≥1.20
```

Your entries are **indistinguishable from random moments** on that measure, and you
clear the threshold *less* often than chance. Building it would have blocked **9 of your
13 known trades**, including the +$52.78 buy at 17:49:59.

**Why that claim happened:** features were fitted to your entries with no null baseline.
Try enough features against 13 points and something always "fits". Every feature claim
from now on carries its null, or it doesn't get built. Recorded in memory as
`project_feb11_gate_refuted`.

---

## 3. Built: `DohaFade.mq5` — the signature, with measured defaults

```
BUY   price in the cheap 30% of the last hour's range
      AND the last minute moved DOWN by ≥ 2.00 points
SELL  the mirror
exit  structural stop + structural target, nothing in between
      (yesterday's tester verdict: every interference rule cost money)
magic 88096 — tester only
```

Defaults were **measured, not guessed**:

| setting | signals/day | your 13 caught |
|---|---|---|
| cheap 0.40, fade 0.10 | 569 | 6 |
| **cheap 0.30, fade 2.00** | **131** | **6** |
| cheap 0.15, fade 2.00 | 78 | 4 |
| + require quiet bar | 31 | **1** |

The no-supply filter is **off** because measuring it cut your coverage from 6/13 to 1/13.
Quiet bars are not part of your signature.

---

## 4. The complementarity — this is the useful part

```
UHV engine catches   02:09 · 02:29 · 17:37 · 19:11 · 19:20 · 19:38
FADE engine catches  16:49 · 17:49 · 19:08 · 19:11 · 19:20 · 19:26
                     ─────────────────────────────────────────────
             UNION   10 of your 13   (77%)
```

**They are complementary, not competing.** Neither alone exceeds 6/13; together they
reach 10/13 — which lands almost exactly on the June estimate that a fully mechanical
build tops out near 67% coverage, the rest being your eyes.

---

## 5. What is still wrong, stated plainly

**Selectivity.** The fade engine sees 131 setups where you took 27. Tightening it
further loses you faster than it loses noise. Something chooses your 27 from the 131 and
we have not found it — that is very likely the "un-mechanizable tape reading" the June
note attributed 33% of your day to.

**Sample size.** Thirteen entries. The separation is real but moderate (0.66σ). This is
direction, not proof.

**And nothing here is P&L.** Every number above is a *detection* count. Under our own
first rule — Python may generate a hypothesis, only MT5 may promote one — none of this
is evidence that the fade engine makes money. That test needs you.

---

## 6. One run when you wake — about 30 seconds

```
Expert        DohaFade          (Navigator → Refresh if it's not listed)
Symbol        XAUUSD_F11
Period        M1 · 1 minute OHLC
Dates         2026.02.10 → 2026.02.12
Optimization  Disabled
```
Everything else is already baked in.

**The number to beat is −$213.20** — the best the UHV engine could manage on your day
after every tuning we tried. And the honest comparison is your own: **+€835, 69 trades,
94%.**

If the fade engine comes out green, we have found the animal and six months of work
starts pointing the right way. If it comes out red, we have still learned the most
important thing of the night: **the entry direction was inverted all along**, and no
amount of exit work was ever going to fix that.

🤍👻
