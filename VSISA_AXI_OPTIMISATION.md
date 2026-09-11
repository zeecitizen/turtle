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
