# VSISA on Axi — the overnight optimisation, 2026-09-12

**Zee:** *"i want you to test and find the highest profit variant of the current VSISA EA
on AXI volume.. take your time. test as deeply as possible."*

**Answer: the highest-profit variant is the one we already had.** Roughly 1,900 tester
passes across nine grids found nothing that beats the ORIGINAL shipped configuration on
any honest out-of-sample test. The search is written up below in the order it happened,
including the two dead ends, because the dead ends are the useful part.

---

## The evidence, all of it

Three windows. The two long ones are the evidence; the 9-day one is the trap.

| configuration | **Axi · 8 months of bars** | **Blueberry · 7 months REAL TICKS** | Axi · Sep real ticks (9 d) |
|---|---|---|---|
| **ORIGINAL (shipped v1.00)** | **+$4,184.50** · 121 tr · **45% WR** | **+$3,127.60** · 120 tr · **34% WR** · **6/7 green** | −$202.00 · 8 tr |
| Axi-tuned "candidate A" | +$4,548.70 · 164 tr · 37% WR | +$1,810.90 · 191 tr · 21% WR · 4/7 green | +$91.10 · 23 tr |
| **CURRENT LIVE (loosened)** | +$572.38 · 889 tr | **+$356.00** · 960 tr · 22% WR · 4/7 green | +$155.80 · 69 tr |
| the September-tuned "winner" | **−$9,436.83** · 8,978 tr | — | +$12,557.41 · 528 tr |

**ORIGINAL** = `VolLookback 100 · StrictDir true · TrendTF 60 · MaxOpen 1 · CoolBars 3 ·
BigPct 0.80 · BigAvg 1.20 · TargetR 2.5 · BE 1 · SlBuf 30 · MaxSl 900`

**CURRENT LIVE** = the same with `VolLookback 10 · StrictDir false · TrendTF 0 ·
MaxOpen 10 · CoolBars 0`

---

## 1. The 9-day trap, in full

Tuning on Axi's September real ticks — the only real-tick data Axi holds — produced a
spectacular result: **+$12,557 over 528 trades, PF 1.51, and all nine days green.** Nine
green days out of nine felt like robustness. It was not.

The same configuration on eight months of Axi's own data: **−$9,436.83.**

Nine days will happily crown a variant that means nothing, and "every day was green"
is not protection when there are only nine of them.

## 2. The unconstrained search DEGENERATES — this is worth knowing permanently

Each time the geometry grid hit its ceiling I extended it, and each time the optimiser
asked for more:

| round | best TargetR | best MaxSlPts | net | drawdown |
|---|---|---|---|---|
| 1 | 4.0 *(ceiling)* | 1000 | +$2,533 | 1.1% |
| 2 | 4.0 | 1200 | +$1,909 | 2.7% |
| 3 (long window) | 8.0 *(ceiling)* | 2000 *(ceiling)* | +$22,268 | 15.0% |
| 4 (long window) | **14.0** *(ceiling)* | **3500** *(ceiling)* | +$62,536 | **23.9%** |

It never converges. The optimiser is not finding an edge — it is discovering that on a
trending instrument **"never take profit and use an enormous stop"** wins a backtest.

That is not VSISA (the teacher's targets are 1:2 to 1:4), and it is not survivable: at
`MaxSlPts 3500` a single 0.10 ticket risks **$350**, and with `MaxOpen 10` that is
**$3,500 exposed against a $500 real account**. The search was therefore bounded to
targets ≤ 4R and stops ≤ 1200 points for everything that followed.

**Rule for next time: if extending a bound moves the optimum to the new bound, the
parameter has no optimum and the search is telling you the model is wrong.**

## 3. What the long window actually wants: TIGHTER, not looser

Searching within sane bounds on eight months, the direction reversed completely. Every
loosening that the 9-day fit loved, the 8-month sample punished:

| `InpBigAvg` | trades | PF | drawdown |
|---|---|---|---|
| 1.2 | 1,269 | 1.10 | 5.87% |
| 1.4 | 542 | 1.21 | 2.53% |
| 1.6 | 240 | 1.77 | 1.81% |
| **1.8** | **190** | **1.94** | **1.53%** |
| 2.2 | 64 | **3.36** | 0.75% |

Fewer, better trades — monotonically. `VolLookback` climbed the same way, 16 → 36 → 42,
walking back toward the **100** that was shipped originally and that Zee shortened to 10
by eye. That is not a coincidence; it is the long sample rediscovering the original
design.

## 4. Why the current LIVE settings are the weakest of the three

On Blueberry's seven months of real ticks, the loosening costs **89% of the profit**:

| | ORIGINAL | CURRENT LIVE |
|---|---|---|
| net | **+$3,127.60** | +$356.00 |
| trades | 120 | **960** |
| win rate | **34%** | 22% |
| green months | **6/7** | 4/7 |
| worst month | −$49.20 | **−$2,627.90** (May) |

Eight times the trades for a ninth of the money, and a single month that loses more than
the whole period makes. Each change was individually reasonable; together they removed
the selectivity the strategy runs on.

---

## The recommendation

**Revert to the ORIGINAL configuration.** It is the best variant on both long windows,
it carries the best win rate on both (45% on Axi bars, 34% on Blueberry ticks), and it
is the only one green in 6 of 7 months.

It is worth being clear about one thing: the only window where the original looks bad is
Axi's 9 days of September real ticks (−$202 on **8 trades**). Eight trades decide
nothing, and that same window is the one that manufactured the +$12,557 mirage.

Three caveats I am not going to bury:

1. **The Axi long window is BAR data, not real ticks.** Axi holds only `202609.tkc`.
   Model 1 rebuilds M5 from M1 OHLC, which is weaker evidence than real ticks — it is
   used here because eight months of weaker evidence beats nine days of strong evidence
   for a question about robustness.
2. **Axi publishes no real volume either.** The feed probe measured it: `iRealVolume`
   returned 0 on XAUUSD.pro, so VSISA judges Axi's TICK COUNT. The move gave us a
   different broker's tick count, not exchange volume.
3. **Nothing here beats the original.** After ~1,900 passes the honest finding is a
   negative one, and a negative finding reported straight is worth more than a curve fit
   reported confidently.

## How to reproduce

```
py monitor/strategy_lab/axi_sweep.py --grid sane  --frm 2026.01.05 --to 2026.09.01 --model 1
py monitor/strategy_lab/axi_sweep.py --grid tight --frm 2026.01.05 --to 2026.09.01 --model 1
py monitor/strategy_lab/axi_sweep.py --backtest --inputs "<config>"        # Sep real ticks
py monitor/strategy_lab/vsisa_validate.py --label X --inputs "<config>"   # Blueberry 7 months
```

The Axi rig is `C:/axi_rig`, a portable clone of the Axi install plus a copy of its
history. Nothing in that harness can reach the terminal the EA is attached to.

---

## Widening the stop — asked 2026-09-15, answered NO

Zee, on the 14 Sep 04:10 trade (−$85.20): *"this trade was narrowly stopped, so can you
check if increasing the SL would've rescued it into a profit?"*

**That trade, exactly.** Reaction candle 04:05 low 4329.80, stop 4328.60 (the 120pt
buffer). Price ran to 4326.19 — it needed a **361pt buffer** to survive, three times what
it has. But the target is 2R, so it travels outward with the stop:

| buffer | stop | risk | 2R target | outcome |
|---|---|---|---|---|
| 120 (shipped) | 4328.60 | 846 | 4353.98 | stopped 04:15 |
| 300 | 4326.80 | 1026 | 4357.58 | stopped 04:20 |
| 361 | 4326.19 | 1087 | 4358.80 | stopped 04:20 |
| 400 | 4325.80 | 1126 | 4359.58 | stopped 07:35 |

The highest price in the 24h after entry was **4355.51**. Every target from 200pts of
buffer upward sits above it. Widening the stop converts this loss into a **bigger** loss —
it never rescues it, because at a fixed R multiple the target retreats exactly as fast as
the stop widens. Only holding the target STILL rescues it (400pt buffer, original target
4352.51, hit 04:55 at 1.37R) — and that is a change to the TP rule, not the SL.

**In aggregate it is an overfit.** Buffer 120→400 × cap 900/1500, both halves, Axi real
ticks M5:

| config | Apr–Jun (tuned) | Jul–Sep (unseen) | max DD |
|---|---|---|---|
| **120 / 900 — shipped** | +$3,545 | **+$1,672** | 0.89% / 1.75% |
| 240 / 1500 — Apr–Jun winner | **+$5,529** | **−$14** | 1.80% / 3.56% |
| 120 / 1500 | +$4,798 | +$279 | 1.32% / 3.33% |

Raising the 900pt cap looks like +56% on the tuning half and inverts to a loss on the
unseen one, with drawdown roughly doubled. Against $500 of real capital that is
disqualifying twice over. **Shipped 120 / 900 is the best out-of-sample config in the
grid and stays.**

Receipts: grid `wide` in `monitor/strategy_lab/axi_sweep.py`, 16 passes per half.

---

## The stop is structural, the target runs — Zee's call, 2026-09-15

*"SL should not be tied to TP. SL can be below the first reaction candle's low (low volume
bullish candle after bearish background big volumes).. and TP can be very high up until
1:7 .. can you test this?"*

**He was right, and my earlier reading was wrong.** I had tested the R ladder only as far as
2.5R, found it worse than 2.0R, and concluded 2.0R was the peak. It is not — it is a LOCAL
peak. The curve dips at 2.5R and then climbs to a second, higher one:

| InpTargetR | trades | WR | net | maxDD | % of $10k |
|---|---|---|---|---|---|
| **2.0 — shipped** | 322 | **43%** | +$5,502 | $946 | 9.5% |
| 2.5 | 322 | 36% | +$4,503 | — | — |
| 3.0 | 322 | 32% | +$4,624 | — | — |
| 3.5 | 322 | 29% | +$5,016 | — | — |
| 4.0 | 322 | 27% | +$6,374 | $1,014 | 10.1% ⚠ |
| **5.0** | 322 | **25%** | **+$8,153** | **$950** | **9.5%** |
| 6.0 | 322 | 22% | +$8,744 | $1,322 | 13.2% ⚠ |
| 7.0 | 322 | 19% | +$8,112 | — | — |

**1:5 is the answer.** +48% profit over the shipped config for IDENTICAL drawdown ($950 vs
$946). 6.0 makes $591 more but draws $1,322 — a 13.2% breach of a standard funded limit —
and 4.0 breaches marginally at 10.1%. Only 5.0 sits under the line.

**It walks forward better than anything else tested.** Apr–Jun +$4,022 · Jul–Sep +$3,988 —
the two halves within 1% of each other, on a split it was never fitted to. The shipped 2.0R
manages +$3,621 / +$1,741, so 5.0R beats it on BOTH halves, doubling the unseen one.

The trade count never changes (322) — same setups, same stops, same losses (avg −$57.35
throughout). Only the winners run: avg win +$279.62 against 2.0R's +$114.99, payoff 4.9:1.

**The cost is win rate: 43% → 25%, and the worst losing streak goes 11 → 15.**

**Context filters do NOT help at high R.** H1 trend at 5.0R halves the profit ($4,231 vs
$8,010) and leaves win rate at 24%. Its win-rate benefit was specific to 2.0R.

Receipts: `AXI_bt_2231*`–`2235*`, Axi XAUUSD.pro M5 model 4, stop 120 structural throughout.

---

## Timeframes re-tested at 1:5 — M5 is not a preference, it is the whole edge (2026-09-16)

Zee: *"i want you to check how our EA would perform on the 1 min, 2 min, 3min, 10 min, 15
min scales.. maybe we can take more trades there? or a better winrate?"*

**The first pass was rigged and I re-ran it.** `InpSlBufPts=120` is an ABSOLUTE distance
tuned on M5 — on M1 that is enormous next to the candle, on M15 it is tiny. So the stop
floor and cap were scaled by sqrt(timeframe) for a fair comparison (M1 40/25/400 …
M15 200/105/1560). Axi real ticks, Apr 1 → Sep 15, 0.10 lots, everything else shipped.

| timeframe | net | trades | WR | maxDD | net per $1 DD |
|---|---|---|---|---|---|
| M1 buf 40 | −$2,047 | 1,192 | 16% | $2,890 | −0.71 |
| M1 buf 60 | −$1,520 | 1,161 | 16% | $2,580 | −0.59 |
| M2 buf 60 | −$705 | 641 | 17% | $1,845 | −0.38 |
| M2 buf 120 (unscaled) | +$3,482 | 738 | 18% | $2,030 | 1.72 |
| M3 buf 90 | −$2,364 | 476 | 15% | $3,117 | −0.76 |
| **M5 buf 120 — SHIPPED** | **+$8,008** | **322** | **25%** | **$950** | **8.43** |
| M10 buf 170 | +$3,559 | 200 | 20% | $1,833 | 1.94 |
| M10 buf 240 | +$1,672 | 188 | 18% | $3,203 | 0.52 |
| M15 buf 200 | −$2,460 | 172 | 15% | $3,986 | −0.62 |
| M15 buf 300 | −$4,777 | 160 | 12% | $5,545 | −0.86 |

**Both of his hopes are answered, and one of them backwards.** More trades: yes, abundantly —
M1 takes 1,192 against M5's 322. Better win rate: **no, the opposite.** M5 is 25% and every
other timeframe lands between 12% and 20%. Scaling the stop did not move that; the win rate
is a property of the timeframe, not of the geometry.

M5's nearest rival is M10 at ratio 1.94, against M5's 8.43 — a **4.3x** gap, not a margin.
Both immediate neighbours, M3 and M10, are far worse, so this is not a plateau M5 happens to
sit on top of.

**Is it overfitting?** The parameters were tuned on M5, which is the obvious worry — but the
stop was RE-tuned per timeframe here and the gap survived. And M5's two walk-forward halves
are +$4,004 and +$4,004, as stable as anything measured on this project. The most likely
reading is that 5-minute bars match the rhythm of the absorption-then-test pattern on gold:
faster and the reaction candle is noise, slower and the imbalance has already resolved inside
the bar.

**Treat M5 as part of the strategy, not a setting.** Nothing changed; the EA stays on M5.

### maxOpen=2, walk-forwarded on the same day

| | Apr–Jun | Jul–Sep |
|---|---|---|
| maxOpen=10 | +$4,004 · DD $898 | +$4,004 · DD $950 |
| maxOpen=2 | +$4,004 · DD $898 (**never binds**) | +$4,192 · DD $905 |

It is identical in the first half — the cap never engages — and +$188 with $45 less drawdown
in the second, from removing 4 trades. The PROFIT evidence is thin and one-sided. The RISK
case is not: it bounds concurrent exposure at roughly $90 instead of a possible $450, at no
measured cost in either half. Worth shipping on safety grounds, not on the $188.
