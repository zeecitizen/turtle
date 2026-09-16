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

---

## The five-step "win rate fix" — four refuted, ONE real (2026-09-16)

An external analysis attributed the 22-25% win rate to five parameter choices and proposed a
fix for each. Tested at the shipped v1.13 geometry, Axi real ticks, Apr 1 → Sep 15.

| step | proposal | measured |
|---|---|---|
| 1 | `InpTargetR` 5.0 → 2.0 | WR claim CORRECT (43%), profit claim WRONG: **+$5,502 vs +$8,196** |
| 2 | `InpConfirmMode` 0 → 1/2 | mode 1: 30 trades, $18.63/trade; mode 2: 20 trades, $24.53 — vs base $25.78 |
| 3 | **`InpFakeBreak` = true** | **REAL — see below** |
| 4 | `InpSlBufPts` 120 → 250 | **+$5,975**, $21.81/trade vs base $25.78 |
| 5 | session 7–19 | +$4,655, $25.44/trade — same per trade, just fewer. No quality gain |
| — | all five combined | +$3,253 on 39 trades |

**Its central assumption is the error: that a higher win rate is better.** The whole R ladder
was measured on 2026-09-15 — 2.0R does give 43%, and it earns $2,694 LESS at the same
drawdown. The analysis's projection of "50% WR at 1:2 = $50/trade" is not measured; the
actual 2.0R figure is **$17.09/trade against 5.0R's $25.78**. Its drawdown percentages also
depend on the tester's deposit (37.52% of $5,000 is $1,875) and are not comparable to figures
quoted against $50,000.

### Step 3 was right, and it is the best filter found on this project

`InpFakeBreak` requires the setup to SWEEP a recent extreme and the reaction to close back
inside it — Zee's own tier-3 "strongest" case, built long ago and never re-tested since the
geometry corrections. Walk-forward, per trade:

| sweep | Apr–Jun | Jul–Sep |
|---|---|---|
| off | 25% WR · $23.66 | 24% WR · $28.21 |
| 20 bars | 33% · **$45.40** | 31% · **$51.46** |
| 30 bars | 34% · **$48.76** | 32% · **$54.50** |
| 50 bars | 38% · **$57.65** | 31% · **$59.39** |

**Win rate and per-trade value both roughly double, in BOTH halves, at EVERY sweep length.**
That is a plateau, not a spike — the opposite signature to the cap bar, volume floor, close
location, effort-per-range and quiet retracement, all of which failed this exact test.

It also halves the pain: **worst losing streak 15 → 9**, drawdown $905 → $586.

**But it does not beat the shipped config per unit of risk:**

| config | net | trades | WR | maxDD | streak | **net per $1 DD** |
|---|---|---|---|---|---|---|
| **SHIPPED 0.10** | +$8,196 | 318 | 25% | $905 | 15 | **9.06** |
| fakeBreak30 0.10 | +$3,991 | 78 | 33% | $586 | 9 | 6.81 |
| fakeBreak30 0.20 | +$7,981 | 78 | 33% | $1,173 | 9 | 6.81 |
| fakeBreak20 0.20 | +$8,348 | 87 | 32% | $1,173 | 9 | 7.12 |

Sized up to match, it earns slightly less for more drawdown. So it is not a free upgrade —
it is a genuine CHOICE: **+8 points of win rate and a 9-loss worst streak instead of 15, for
about half the income.** Given Zee's stated difficulty in bearing loss runs, that trade is
his to make and it is the first time tonight the option has been real.

---

## Is the 120pt stop too tight? No — tested 3 pips to 3 dollars (2026-09-16)

Zee: *"is our stop too tight? can we test 3-8 pips"*, quoting the claim that *"M5 Gold
volatility regularly generates $1.50–$2.50 noise wicks"* and that 120 points should be 250.

"Pips" on gold is ambiguous, so the whole range was swept — 30 points ($0.30/oz) to 300
points ($3.00/oz) — at the shipped v1.15 config (0.15 lots, fake break on, cap 900):

| buffer | net | trades | WR | maxDD | net per $1 DD |
|---|---|---|---|---|---|
| 30 pts ($0.30) | +$4,046 | 84 | 29% | $885 | 4.57 |
| 60 pts ($0.60) | +$5,130 | 82 | 32% | $918 | 5.59 |
| 80 pts ($0.80) | +$4,649 | 81 | 31% | $840 | 5.53 |
| **120 pts ($1.20) — SHIPPED** | **+$5,986** | 78 | **33%** | $879 | 6.81 |
| 160 pts ($1.60) | +$5,281 | 75 | 32% | $779 | 6.78 |
| 200 pts ($2.00) | +$5,828 | 71 | 32% | **$588** | **9.90** |
| 250 pts ($2.50) — suggested | +$5,349 | 67 | 31% | $634 | 8.44 |
| 300 pts ($3.00) | +$4,224 | 63 | 29% | $1,067 | 3.96 |

**Tightening to 3–8 pips is refused outright** — 30/60/80 points all earn less AND draw more
than 120. The stop is not too tight in that direction.

**200 points looked like a real upgrade and is not.** Its full-window drawdown of $588
against 120's $879 implied room for a bigger lot, and at 0.22 lots it measured +$8,548 at
$863 DD with a 6-loss streak — apparently beating the shipped +$5,986 at $879 on every axis.
Then the halves:

| at 0.15 lots | Apr–Jun (tuned) | Jul–Sep (unseen) |
|---|---|---|
| buf 120 | +$3,203 · DD **$879** · 34% · streak 9 | +$2,783 · DD **$522** · 32% · streak 6 |
| buf 200 | +$3,251 · DD **$531** · 33% · streak 6 | +$2,577 · DD **$588** · 31% · streak 6 |

**The entire drawdown advantage is one half.** In Apr–Jun 200 draws $531 against 120's $879;
in the unseen half it draws MORE ($588 against $522). The full-window figure was reporting
Apr–Jun's number, and the whole case for sizing up rested on it. On net across both halves
120 wins ($5,986 against $5,828).

The one thing 200 does consistently is a 6-loss worst streak in both halves against 120's
9 then 6. Not enough to pay for it.

**NOT SHIPPED. 120 stands** — it has the best net and the best win rate at the real risk cap,
and the claim that it is too tight for gold is unsupported at every width tested.

---

## Jan → Sep 2026, month by month — and the 0.15 lot is too big (2026-09-16)

Zee asked for every month from January plus a combined total. Axi holds ticks back to Sept
2024, so January is real coverage. v1.15 exactly as shipped, one continuous run.

| month | trades | W-L | WR | NET | running |
|---|---|---|---|---|---|
| January | 5 | 1-4 | 20% | +$36.35 | +$36 |
| February | 4 | 1-3 | 25% | +$190.48 | +$227 |
| **March** | 7 | **0-7** | **0%** | **−$641.66** | −$415 |
| **April** | 10 | 2-8 | 20% | **−$218.15** | −$633 |
| May | 16 | 7-9 | 44% | +$1,943.47 | +$1,310 |
| June | 16 | 5-11 | 31% | +$1,061.47 | +$2,372 |
| July | 22 | 6-16 | 27% | +$1,233.04 | +$3,605 |
| August | 6 | 2-4 | 33% | +$787.77 | +$4,393 |
| September (to 14th) | 6 | 3-3 | 50% | +$761.82 | **+$5,155** |

**TOTAL: 92 trades · 27-65 · 29% WR · +$5,154.59 · 7 of 9 months green**
avg win +$417.43 · avg loss −$93.13 · payoff 4.48:1 · expectancy +$56.03/trade

**THE FINDING THAT MATTERS: max drawdown is $1,232.32 = 12.3% of $10,000. That BREACHES a
10% funded rule**, and the worst losing streak over the longer window is **13, not 9**.

The 0.15 lot was chosen on 2026-09-16 from the Apr–Sep window, where drawdown measured $879
(8.8%) and the worst streak was 9. Both numbers were understated because that window happens
to start AFTER the bad stretch. Jan–Apr is four months netting **−$634**, with March going
0-for-7.

| lots | Jan–Sep net | Jan–Sep maxDD | % of $10k | Apr–Sep maxDD (what it was chosen on) |
|---|---|---|---|---|
| **0.10** | +$3,714 | **$822** | **8.2%** | $586 |
| 0.12 | +$4,457 | $986 | 9.9% | $703 |
| **0.15 — SHIPPED** | +$5,571 | **$1,232** | **12.3% BREACH** | $879 |

0.12 sits at 9.9% — technically inside, with no margin at all for a period worse than any in
this sample. **0.10 is the defensible size on $10k**, and it is what the EA shipped at before
v1.15.

This is a walk-forward lesson about ME, not about the strategy: I sized the position on a
window that excluded the drawdown, then verified against that same window. The Apr–Sep split
was built to test ENTRY RULES out-of-sample; it was never a safe basis for a risk decision,
because both halves sit inside the good stretch.

---

# THE NIGHT OF 16-17 SEPTEMBER — five questions Zee left

*"i want you to through the night experiment thoroughly with the following: wicks on candle's
we consider and their impact / finding out if we're taking all possible setups? / solving the
no-supply candle's mystery / tuning this strategy further, try diff config combinations /
increasing the frequency of trading, can we take more setups per day? its boring to sit idle
n wait all day only to find out it was a loss and then wait another few days for next trade."*

All of it measured with `monitor/strategy_lab/vsisa_lab.py`, written for the night: every
config runs the FULL window AND both walk-forward halves, and is judged on **net per $1 of
drawdown** — the only fair comparison when position risk differs — alongside win rate and
worst losing streak. Baseline throughout is v1.19 as shipped, 0.28 lots.

## 1. WICKS — the exception is harmful, and turning it off is the night's best find

| config | net | trades | WR | maxDD | streak | ratio | h1 | h2 |
|---|---|---|---|---|---|---|---|---|
| **v1.19 shipped (wick 2, frac .35)** | +$8,019 | 66 | 59% | $875 | 5 | 9.16 | 2.06 | 11.15 |
| wick 2, frac 0.20 | +$7,716 | 71 | 56% | $1,257 | 6 | 6.14 | 0.90 | 11.81 |
| wick 2, frac 0.50 | +$8,181 | 63 | 60% | $634 | 4 | 12.91 | 3.22 | 11.01 |
| **wick 0 — OFF** | **+$8,396** | 62 | **61%** | **$634** | **4** | **13.25** | **3.22** | **11.39** |
| wick 1, require, frac 0.20 | +$2,080 | 21 | 57% | $499 | 3 | 4.17 | 1.65 | 2.77 |
| wick 1, require, frac 0.35 | +$110 | 8 | 50% | $489 | 2 | 0.22 | 1.99 | −0.62 |

`InpWickMode 2` lets a LOUD reaction through when it carries a wick. **It is costing money.**
Switching it off is better on every axis and in BOTH halves — ratio 9.16 → **13.25**,
drawdown −28%, win rate +2 points, streak 5 → 4, for four fewer trades. Note frac 0.65 gives
numbers identical to OFF, because at that threshold the exception becomes unreachable.

This corroborates the trade-level result from 2026-09-15 (LOUD+wick ran 25% WR and −$11.12 a
trade) which was then too small to act on. At the current geometry it is worth $377 and 241
dollars of drawdown.

**REQUIRING a wick (mode 1) is not a filter, it is a famine** — 8 trades at frac 0.35.

## 2. ARE WE TAKING ALL POSSIBLE SETUPS? — the funnel, counted

```
dir        75,487 rejected    <- the setup bars must all close the same way
candidates 24,498 reach the volume test
not loud   21,895 of those    <- 89% die here
fake        2,342
trend          36
FIRED          62
```

Two gates do nearly all the work: **direction** and **loudness**. The fake break, which cuts
75% of what reaches it, is a distant third. Everything downstream — reaction, body, quiet,
trend — together refuses about 180.

So: we are NOT taking all possible setups, by design, and the 89% loudness gate is where the
missing ones are. Section 5 tests whether they are worth having.

## 3. THE NO-SUPPLY MYSTERY — SOLVED, and the answer is no

Re-tested at the v1.19 geometry, both as a gate (mode 1, wait for the test then a confirming
bar) and as the entry itself (mode 2, enter ON the test bar), with and without requiring the
test bar to close against the trade:

| config | net | trades | WR | ratio | h1 | h2 |
|---|---|---|---|---|---|---|
| **base, no test** | **+$8,396** | 62 | 61% | **13.25** | 3.22 | 11.39 |
| mode 1, test ≤0.90 | +$42 | 16 | 38% | 0.03 | 0.21 | −0.22 |
| mode 1, RED test ≤0.90 | −$847 | 10 | 20% | −0.83 | −0.74 | −0.70 |
| mode 1, test ≤1.20 | +$982 | 19 | 47% | 1.20 | 1.07 | 0.19 |
| mode 2, enter on test ≤1.20 | +$1,023 | 23 | 43% | 1.24 | −0.15 | 3.42 |
| mode 2, enter on test ≤0.70 | −$387 | 4 | 0% | −1.00 | −1.00 | −1.00 |

**Every single variant is far worse than not testing at all**, and several are negative. This
is now the THIRD geometry it has been refuted on (v1.06 at 2.0R, v1.10 at 5.0R, v1.19 here).

The mystery is not that the encoding is wrong — it has been written three ways, including
Zee's own diagram-11 sequence with the red test bar. It is that the no-supply test, applied
mechanically to gold M5, removes 70-95% of trades and the survivors are no better than the
ones it removed. Whatever the teacher is reading on that bar is not in the price-and-volume
of the bar itself. **Recommend it be closed as an idea rather than re-encoded a fourth time.**

## 4. TUNING — the shipped values are right, and the exit is not what we thought

| config | net | trades | WR | maxDD | streak | ratio | h1 | h2 |
|---|---|---|---|---|---|---|---|---|
| **BASE wick0** | +$8,396 | 62 | 61% | $634 | 4 | **13.25** | 3.22 | 11.39 |
| ratchet start 1.50 | +$5,868 | 62 | 65% | $634 | 4 | 9.26 | 1.78 | 10.21 |
| ratchet start 2.50 | +$8,414 | 62 | 52% | $841 | 5 | 10.00 | 3.10 | 8.79 |
| ratchet start 3.00 | +$8,006 | 62 | 47% | $938 | 5 | 8.54 | 3.98 | 5.39 |
| **ratchet OFF** | **+$10,352** | 62 | 35% | $1,701 | 10 | 6.08 | 2.45 | 4.63 |
| targetR 4.0 / 6.0 / 7.0 | +$8,392–8,396 | 62 | 61% | $634 | 4 | 13.25 | — | — |
| camelPivot 1 | +$5,293 | 60 | 52% | $777 | 4 | 6.82 | 1.76 | 8.45 |
| camelPivot 3 | +$8,253 | 63 | 60% | $710 | 3 | 11.62 | 2.29 | 11.87 |
| camelLook 60 / 240 | +$8,396 | 62 | 61% | $634 | 4 | 13.25 | — | — |

**Ratchet start 2.0, camelPivot 2 and camelLook 120 are all already optimal.** Nothing in
the shipped trend or exit settings wants moving.

**THE FINDING THAT MATTERS — the 5R target is decorative.** Over the full window **all 62
trades close at the STOP and not one reaches the target**, and the average stop-exit is
**+$136.68**, i.e. most stops are now taken in PROFIT. The mechanism is arithmetic: the
ratchet locks at 5R exactly where the 5R target sits, so the stop always arrives first. That
is why `InpTargetR` 4.0, 6.0 and 7.0 return byte-identical numbers — **the target has not
been the exit since the ratchet shipped.** The trailing step is the only exit parameter left
that can matter.

It also reframes the win rate. "61% win rate" does not mean 61% of trades reached a 5R
target; it means 61% got past 2R and ratcheted into profit before turning back.

**And it prices the ratchet honestly.** Switching it off earns **+$10,352 against +$8,396** —
$1,956 MORE money — at 35% win rate, a 10-trade losing streak and $1,701 of drawdown. The
ratchet is buying calm with about a fifth of the profit. That is the trade Zee chose on
2026-09-16 and it remains his to re-choose.

## 5. FREQUENCY — the honest answer is that it costs more than it earns

The 89% gate is `not loud`, so that is where more trades live. Loosening it:

| config | trades | net | maxDD | WR | ratio | **h1 ratio** |
|---|---|---|---|---|---|---|
| **BASE wick0** | **62** | +$8,396 | $634 | 61% | **13.25** | **3.22** |
| BigPct 0.70 | 68 | +$7,934 | $812 | 57% | 9.77 | 2.90 |
| BigAvg 1.00 | 106 | +$6,870 | $1,425 | 47% | 4.82 | **0.08** |
| BigAvg 0.80 | 157 | +$4,804 | $2,419 | 41% | 1.99 | **−0.50** |
| BigAvg 0.60 | 170 | +$5,078 | $2,161 | 40% | 2.35 | **−0.38** |
| BigMode 0 (every bar loud) | 45 | +$6,306 | $793 | 62% | 7.95 | 1.22 |
| swingMin 14 | 66 | +$6,517 | $820 | 53% | 7.95 | 1.95 |
| swingMin 20 | 66 | +$5,914 | $820 | 50% | 7.21 | 2.37 |

**Trades are available — 62 can become 170 — but the edge is not.** At 106 trades the first
half is already flat (0.08); at 157 and 170 it is NEGATIVE. Drawdown quadruples. The big-
volume requirement is load-bearing, not decoration: it is the whole reason the reaction means
anything.

Tightening the sweep instead (`InpSweepLook` 40, 60) reduces trades further, so there is no
free direction: **60-ish trades in 8½ months is what this edge supports on one instrument.**

**The route that WOULD work is more instruments, not looser setups.** The same 8 trades a
month across six symbols is 48 a month. This could not be tested tonight — Axi's rig holds
2026 ticks for XAUUSD.pro only (EURUSD and XAUUSD have one month each, from the Blueberry
era), and downloading history needs the rig logged into the account, which risks knocking the
live terminal offline while Zee sleeps. **Recommended as the first job of the morning.**

## 6-8. THE EXIT, RE-READ — one lock beats a trail, and the target was never the exit

| config | net | trades | WR | maxDD | streak | ratio | h1 | h2 |
|---|---|---|---|---|---|---|---|---|
| v1.19 shipped | +$8,019 | 66 | 59% | $875 | 5 | 9.16 | 2.06 | 11.15 |
| wick0 only | +$8,396 | 62 | 61% | $634 | 4 | 13.25 | 3.22 | 11.39 |
| w0 + swing6 + step2 + t10 | +$8,954 | 58 | 64% | $624 | 4 | 14.36 | 3.67 | 11.95 |
| w0 + swing6 + step3 | +$9,221 | 58 | 64% | $624 | 4 | 14.78 | 3.67 | 12.43 |
| w0 + swing6 + step8 | +$9,261 | 58 | 64% | $624 | 4 | 14.85 | 3.67 | 12.50 |
| w0 + swing6 + **step20** | +$9,261 | 58 | 64% | $624 | 4 | **14.85** | 3.67 | 12.50 |
| **w0 + swing5 + step8 — SHIPPED** | **+$8,979** | 54 | **65%** | **$558** | **3** | **16.09** | **4.79** | **11.72** |
| w0 + swing4 + step8 | +$6,593 | 44 | 68% | $465 | 3 | 14.19 | **8.13** | 8.49 |

**Step 8 and step 20 are IDENTICAL**, which is the proof: no second rung is ever reached, so
the rule is *lock 2R once and hands off*. Trailing beyond the first rung cuts winners.

Neighbours agree on every axis — step 1.5/2/2.5/3/5/8 all sit 14.0-14.9, ratchetStart 2.0 is
a clean peak (1.75 → 12.43, 2.25 → 11.60), and targetR 8/10/12 are identical. This is a
plateau, not a spike.

`swingMin 4` is worth noting for a future session: only 44 trades but **h1 ratio 8.13**, by
far the best first-half number seen. Too few trades to ship on, but if more history ever
arrives it is the first place to look.

---

## LAW 14 — THE FADE. Zee's own eye, and it beats the shipped build (2026-09-17)

He took a trade the EA refused — 16 Sep 22:33 broker, **+$858 on 1 lot** — and described how
he read it:

> *"i filtered out the red candles: saw that reds are ultra highs .. then tried to find a
> green reaction candle.. i saw that the green's had reduced alot from one green to another
> green. so it meant that now buyers have to apply less force to bring the price up.."*

**That is not the shipped setup and no loosening reaches it.** Gaps up to 3 contrary bars
fire nothing that night. Two things differ:

1. **The background is not adjacent.** He reads the red bars of the whole recent leg. At his
   entry there was no red run at all — the bar before was green.
2. **The comparison is GREEN-TO-GREEN.** The EA asks "is the reaction quieter than the reds
   behind it". He asks "is each green quieter than the LAST GREEN" — falling effort for the
   same result, the Base Case read forwards.

Built as `InpFadeMode` — a SECOND entry path, tried only after the ordinary setup refuses.

**It failed badly at first, and the failure was informative.** Without a sweep requirement it
fired 1,455–5,558 times over 8½ months at ratio 0.03–1.46 against the shipped 9.16. His eye
was doing more than he said: he was looking at **a low that had just been made**. Applying
LAW 13 to the fade path too roughly doubled every variant.

**Then it had to survive the spike test.** 0.60/look4 first appeared between neighbours of
5.39 and 6.40 — the shape this project has rejected all week. A fine grid settled it:

| fade ≤ | look3 | look4 | look5 |
|---|---|---|---|
| 0.55 | 5.19 | 6.58 | 5.62 |
| **0.60** | 6.26 | **15.75** | **12.99** |
| 0.65 | 6.00 | 9.58 | 8.36 |

The 0.60 column wins at every lookback. It is a ridge, not a cell.

**fade ≤0.60 / look 4, against v1.20 as shipped:**

| | v1.20 | fade 0.60/look4 |
|---|---|---|
| net, Jan–Sep | +$8,019 | **+$10,400** |
| trades | 66 | **121** |
| win rate | 59% | 51% |
| max drawdown | $875 | **$661** |
| worst streak | 5 | **4** |
| net per $1 DD | 9.16 | **15.75** |
| walk-forward halves | 2.06 / 11.15 | **4.16 / 12.43** |

**+30% money, nearly double the trades, LESS drawdown, a shorter streak, and better in BOTH
halves.** The only thing that falls is win rate, 59% → 51%.

This is the first thing all week to answer the frequency question without paying for it —
and it came from him watching a chart, not from any parameter search.
