# ⚖️ THE LAWS — what makes a setup

**Status: as enforced by `mt5/ZeeUHV.mq5` v1.60, magic 88094, XAUUSD M1.**
*(Zainab wrote this page at v1.58; kept current as the EA moves.)*

These are the **basic laws**: the six steps that decide whether a setup *exists*.
They are gates — every one must pass, or there is no trade.

Conviction is a separate matter. The diamonds in [DIAMONDS.md](DIAMONDS.md) never
decide *whether* to trade, only *how much*. A setup with zero diamonds still fires.
**Nothing on this page is optional; nothing in DIAMONDS.md is required.**

> **THE RULE BENEATH ALL THE OTHERS — body, not wick.**
> Zee, lesson 06: *"sweep kehte hain jab candle apni WICK se toray. break kehte hain
> jab candle BODY se toray."* A wick through a line is a **sweep**. Only a body
> through it is a **break**. Every level test below uses the body — `BodyHi()` /
> `BodyLo()`, never `bHigh()` / `bLow()`. This one distinction is why a level that
> looks broken on the chart is often not broken to the machine.

**Timeframe is not a preference.** M1. Every rule below counts *bars*, so on H1
`InpTrendLook=20` silently means twenty hours, and the M3 boundary arithmetic
(`iTime % 180`) stops meaning anything. Every court result in `VERSION_HISTORY.md`
was measured at M1.

---

## Law 1 — THE TREND

A trend must exist, read from the camel humps: higher highs and higher lows for an
uptrend, the mirror for a downtrend.

| | |
|---|---|
| lookback | `InpTrendLook = 20` bars |
| swing strength | `InpPivot = 2` |
| enforced | `InpRequireTrend = true` |

No trend, no trade. In RANGE the ghost waits.

---

## Law 2 — THE RETRACEMENT, AND WHAT MAKES IT VALID

Price pulls back against the trend: **red candles in an uptrend**, green in a
downtrend.

But a pullback is not a retracement merely because the colour changed. The
condition:

> **The retracing candle's BODY must break below the LAST GREEN CANDLE's low**
> (uptrend). If it has not broken it, no retracement has started.

```cpp
broke = wantRed ? (BodyLo(k) < bLow(prev))      // BUY: red body below the green's low
                : (BodyHi(k) > bHigh(prev));    // SELL: green body above the red's high
```

Note the asymmetry, and that it is deliberate: the retracing candle is tested by its
**body**, the reference candle by its **full low**. A red that only wicks below the
green has swept it, not broken it.

The candle that first achieves this is the **origin** — where the retracement began.
Searched back `InpRetraceBack = 20` bars.

### Law 9 — the reference must be an IMPULSE bar `LIVE 2026-08-17`

The green candle being broken cannot be any green candle. It must be one that made a
**new high** for the leg (BUY; new low for SELL). A bounce inside an existing
pullback is not a reference — the search keeps walking.

```cpp
if (InpImpulseOrigin) {                              // = true, LIVE
   if (wantRed  && bHigh(j) <= bHigh(j + 1)) continue;
   if (!wantRed && bLow(j)  >= bLow(j + 1))  continue;
}
```

**Why it exists:** the origin code once accepted a bar because its body broke the low
of the bar before it — a one-bar wobble in the middle of a move, dressed up as a
retracement.

---

## Law 3 — THE UHV, AND ITS LINES

Inside the retracement, find the **loudest counter-trend candle** — the red one
carrying the most volume in an uptrend. That is the Ultra High Volume candle:
institutions absorbing the selling.

| | |
|---|---|
| body must be | ≥ `InpUhvBodyMin = 0.5` of range |
| must be a local volume peak | `InpLocalPeak = true` |
| candidates auditioned | `InpUhvRank = 6` |

**Draw its high and its low.** The high (BUY) is the **door** — the trigger. The low
is the sweep line, and the structural reference the stop is measured from.

Rank 6 matters: the retracement does not blindly crown the single loudest candle. It
auditions up to six, in volume order, and takes the first that yields a lawful
setup. The cockpit says so out loud — *"the 04:15 candle (vol 26) — runner-up 04:10
(vol 24) — rank-6 auditions both."*

**The volume that decides this is OANDA's, not the broker's** (`InpOandaVolume = 1`).
The two feeds crown a *different* loudest candle in **46.4%** of rolling windows, so
this law is only as true as its feed.

---

## Law 4 — THE BREAKOUT MUST CLOSE THROUGH

A candle must take its **body** past the UHV's high (BUY) — not touch it, not wick
through it and fall back.

```cpp
crossed = wantGreen ? (BodyHi(k) > bHigh(uhv))
                    : (BodyLo(k) < bLow(uhv));
```

For a green candle `BodyHi` **is** the close, so this is exactly *"closes above the
high."* A candle that pokes through and closes back below has swept the door, and
the door stays shut.

Two further conditions, both from Zee's own labels:

- **Only the first crossing counts.** *"we mark only 1 Breakout"* (#13). If an
  earlier bar already crossed, this one is late and is not marked.
- **The breakout cannot be the UHV itself.** *"B cannot be same candle as Y"* (#17).

The break must arrive within `InpBreakWindow = 12` bars — though testing found this
inert: a real break always comes within 5. *Never sweep this parameter again.*

---

## Law 5 — WHAT THE BREAKOUT CANDLE MUST BE

Two hard conditions:

**1. Opposite colour to the UHV.** Green breaks a red UHV for a BUY.
*"for a buy setup the breakout should be with a green colored candle"* (#8) ·
*"breakout candle in sell case must be red"* (#24).

```cpp
if (wantGreen && !IsGreen(k)) continue;
```

**2. Quieter than the UHV.** Strictly lower volume — supply is exhausted, so the
break meets no resistance. If the break is *louder*, the sellers are still there and
it is absorption, not a breakout.

```cpp
if (BarVolume(k) >= BarVolume(uhv)) return false;   // g_breason = 2
```

*"14:50 would be a valid breakout candle if its volume were lower than the Y which it
is not"* (#15).

> **A correction worth recording.** "Momentum candle" is commonly listed as a third
> condition here. In v1.58 it is **not a gate** — there is no body-ratio test on the
> breakout. Momentum lives as **Law 3 of conviction**, a *diamond*: the breakout
> closing ≥ 0.10 beyond the EMA-5 earns an extra ticket, it does not grant or refuse
> the trade. This follows the governing rule in DIAMONDS.md — *a thin or
> regime-dependent signal goes in as a DIAMOND, never as a GATE.* If it should gate,
> that needs a court result first.

Two optional displacement laws sit here, both **off** by default:

| | input | live |
|---|---|---|
| Law 10a — close must clear the trigger by N pts, not graze it | `InpBrkMarginPts` | `0.0` (off) |
| Law 10b — reject near-UHV effort with no result | `InpBrkVolMaxFrac` | `0.0` (off) |

---

## Law 6 — ENTRY, STOP, TARGET

Entry at the breakout candle's close.

| | live value |
|---|---|
| lot size | `InpLots = 0.10` per ticket |
| stop | `InpStopPts = 5.0` |
| target | `InpTargetPts = 1.0` |
| max hold | `InpMaxHoldMin = 3` minutes |
| concurrent setups | `InpMaxOpen = 1` (a stack counts as one) |
| cooldown | `InpCooldownBar = 3` bars |

The 1-point target against a 5-point stop is the Feb-11 harvest shape: take the small
guaranteed pop and leave. The edge is not distance — it is frequency multiplied by a
high hit rate, with losses cut small.

> **That asymmetry is the whole risk.** A 5:1 stop-to-target needs roughly **83%**
> wins to break even before costs. The Friday 2026-08-21 tester run made **65%** and
> still lost **−$267.90**: average win +11.39, average loss −59.43. Judge this system
> by **expectancy per trade, never by win rate** — `NullBurst` scored 91.36% at random
> over 22,000 trades and lost $19,132.

---

## The order in one line

```
trend  →  retracement breaks the last impulse candle  →  crown the UHV, draw its high
       →  a quieter, opposite-coloured candle CLOSES its body through that high
       →  enter at its close
```

Or as the cockpit states it live:

> *A setup exists only when a green M1 candle CLOSES its body above 4531.93 on volume
> quieter than 26.*

---

## Where these live in code

| law | function |
|---|---|
| 2, 9, 12 | `RetracementOrigin()` |
| 3 | `FindUhvBroken()` |
| 4, 5, 10a, 10b | `BreakoutIsBar1()` |
| volume source | `BarVolume()` → `OandaVolAt()` |

Conviction and sizing: [DIAMONDS.md](DIAMONDS.md) — accurate but frozen at v1.25.
Version ledger: [VERSION_HISTORY.md](VERSION_HISTORY.md) — current.

**Before believing any change to a law here, re-run the baseline first.** Dead code
has moved results in this repo before. No Python result has ever promoted anything,
and none should — MT5's Strategy Tester with real ticks, or live fills, only.


---

## Candidates that are NOT laws (tried and refused, so nobody re-litigates)

A page of gates is only trustworthy if the rejected ones are listed too. Each of
these was built, courted, and turned away — receipts in `VERSION_HISTORY.md`.

| candidate | what it demanded | verdict |
|---|---|---|
| **Law 11 — origin integrity** | the retracement may contain no new leg extreme | −303.86 court, and it killed 8 of the golden streak's winners |
| **Law 12 — peak-bounded origin** | the origin search may not cross the last peak | +171 alone, but −276 on top of the pulse; WR 69-81% bought with net |
| **Law 13 — the momentum breakout** | breakout body ≥ 1.0-1.5× the last 20 bodies, and/or a close near its extreme | court −409..−633 vs virgin +324..+549 in all four shapes. It does not select better breaks, it simply trades LESS: June 366→236 tickets with win rate FALLING 77.3%→66.1%. Its sign is just the sign of the period. Deeper reason: it fights Law 6 — a quiet breakout (no supply) is rarely a big-bodied one |
| **The Bull** (buys only, no trend gate) | "gold tends up", so every red pullback is a retracement | lost all six court periods; the gate's silence is worth ~$1,600/12wk |
| **Taking the pruned setups** | fire on everything the vetoes discard | −6,506 vs +576. The prune pile is the laws' salary |
| **OANDA *prices* for levels** | judge the break on TradingView's candles | −144 vs broker candles: OANDA sits +0.120 median above Blueberry (max +0.845). SELECTION may cross feeds; PRICE LEVELS may not |

**The pattern in every refusal:** a filter that removes trades reduces exposure, and
reducing exposure looks brilliant in a losing period and ruinous in a winning one.
Only a filter that raises the win rate *while keeping the winners* is a law.
