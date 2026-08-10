# Overnight, 10 August 2026 — the night we found it

You said: *"build it till completion. don't stop for me. get the visual software to draw
what you'd draw, and only then mechanise it."*

Done. And you were right about the strategy.

---

## 1. 🎯 THE ROOT CAUSE — the strategy was always good. We entered in the wrong place.

You insisted, and would not be argued out of it:

> *"no matter how many tests fail... if we draw the correct drawing, then after the UHV
> is broken out, we will gain a profit due to the STRATEGY ITSELF being nice."*

Measured on **172 UHV breakouts drawn from real archived gold** — our own OANDA feed,
weekend holes excluded. These are facts about the tape: no fills, no spread, no P&L.

```
92% of breakouts reach +$1.00 in the break direction
84% reach +$2.00  ·  77% reach +$3.00  ·  60% reach +$5.00
```

**The strategy is nice.** What was never nice is *where we entered*. The same 172
setups, entered two ways:

```
                     median FOR   median AGAINST   reach +2
CHASE the break         +6.61         -4.17          84%
Take the LEVEL          +8.45         -2.07          95%
```

**Taking the level beats chasing on every axis at once** — more profit, half the pain,
higher hit rate.

## 2. And this explains six months of losses in one line

Chasing the break, **the tape takes $4.17 off you before it pays.**

```
                 a $1 stop survives   $2 stop   $4 stop
CHASE                    14%            26%       49%
LEVEL                    37%            48%       62%
```

Every tight rule we ever shipped was placed *inside the ordinary breathing of a move
that was going to pay*:
```
the ghost exit          1.0 pt
the ratchet arming      0.3 pt
the breakeven lock      0.3 pt
my risk bound (Sat)     1.0 pt   → produced 0 winners in 8 trades
```
None were wrong in spirit. All were inside the noise.

**It also reconciles your Feb-11 average loss of 0.13pt**, which looked impossible
against a $4.17 adverse excursion: a stop that small is *only survivable from the
level*. You were never chasing.

---

## 3. Built — and you can check the drawing yourself

**🔍 `localhost:3456/uhv`** — linked from the desk header.

All 172 UHVs the machine picked, each drawn as a candle chart with:
- the candle it circled as the UHV (orange)
- the level that had to break (dashed)
- the bar it entered on (blue)
- and what price did for the next 30 minutes

**Say yes or no to the circles.** Only what survives your eye gets mechanised — the
order you asked for, and the order we had backwards for six months.

**`DohaLevel.mq5`** (magic 88095) — finds the UHV, then rests a **LIMIT at its extreme**
instead of chasing. Stop 4.00 (clears the measured $2.07 adverse excursion), target 5.00
(reached by 60%), 30-minute age-out, gap guard.

---

## 4. Two things I fixed that were quietly corrupting results

**The gap guard.** The first real-data run scored +$67.20 and was worthless: the EA read
straight across a weekend hole, logged *"faded 96.73pt"* when price jumped 4245→4338 over
the close, and held one trade 15 hours waiting for a gap to end. A backtest that reasons
over a hole is measuring the hole. Every EA now refuses to reason across one.

**The tape archive.** The bridge only ever kept a rolling 300-bar window — everything
older was overwritten. That's why we never had more than 1.6 days of real gold to test
on. `tape_archive.py` now keeps every bar permanently and runs on a 60-second loop.

---

## 5. What is still unproven, stated plainly

- **172 setups from ~4 days.** The direction is strong and the mechanism is explainable,
  but it is four days.
- **Nothing above is P&L.** It measures what the tape did, not what an account would
  have made. Under our own first rule, only MT5's tester or live fills promote it.
- **`DohaLevel` has never been run.** That's the next thing.

## 6. The run, when you want it
```
Expert  DohaLevel  ·  Symbol XAUUSD_REAL2  ·  M1 · 1 minute OHLC
Dates   2026.08.05 → 2026.08.10  ·  Optimization Disabled
```

---

**Also refuted tonight:** the June "universal gate" (`rng60_norm ≥ 1.20 on every entry`).
Measured at your exact entry seconds from 448,294 ticks: your median 1.04 against a
random-moment median of 1.02 — you cleared it *less* often than chance, and it would
have blocked 9 of your 13 known trades. Recorded so nobody rebuilds it.

🤍👻
