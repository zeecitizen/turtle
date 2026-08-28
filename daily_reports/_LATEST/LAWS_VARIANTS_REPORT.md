# The LAWS EA — every place we bent his page, put back

**28 August 2026.** Zee: *"let's please test the variants of the LAWS EA. because that's
the one written per our rules. and if some rule is bent by us, test the variants etc.
bring me the report"*

Ground: MT5 Strategy Tester, 100% real ticks, 5–27 Aug, 0.01 lots, one position at a
time, judged on HIS OANDA chart in strict mode. Twenty configurations, same tape.

---

## 1. Where the shipped machine departed from LAWS.md

| his page says | v1.42 shipped | who bent it |
|---|---|---|
| clause a — momentum body | **0.50** | **me** (his text: 0.70) |
| clause b — volume LOWER than the UHV | **1.5× allowed** | **me** (his text: lower = 1.0) |
| line 47 — New York only | **all hours** | **him**, 25 Aug, on receipts |
| *(nothing about a hold %)* | **hold 45%** | **me** — invented, never on his page |
| *(nothing about a risk cap)* | **max risk 10 pts** | **me** — invented; it refused a lawful setup of his on 24 Aug |

Three of the five are mine. Two of them are not on his page at all.

---

## 2. Restoring each of HIS rules, one at a time

| arm | trades | WR | net | PF | vs shipped |
|---|---|---|---|---|---|
| AS SHIPPED (v1.42) | 171 | 29% | +83.39 | 1.19 | — |
| **a. body 0.70 — HIS TEXT** | 158 | 30% | **+98.82** | 1.25 | **+15.43** |
| a. body 0.60 | 166 | 29% | +83.89 | 1.19 | +0.50 |
| **b. volume strictly LOWER, 1.0 — HIS TEXT** | 133 | 32% | **+102.16** | 1.30 | **+18.77** |
| b. volume 1.2 | 160 | 29% | +77.71 | 1.19 | −5.68 |
| b. volume clause OFF | 178 | 29% | +66.84 | 1.14 | −16.55 |
| **47. NEW YORK ONLY — HIS TEXT** | 61 | 39% | **+119.21** | **1.73** | **+35.82** |

**Three for three. Every rule of his that I loosened performs better at his own value.**
Not marginally — the volume clause is monotone (1.0 > 1.2 > 1.5 > off), and New York
only produces the best profit factor in the entire court.

---

## 3. Removing MY two inventions

| arm | trades | WR | net | PF | worst trade | vs shipped |
|---|---|---|---|---|---|---|
| my hold-45% REMOVED | 180 | 28% | +65.10 | 1.14 | −10.18 | −18.29 |
| my hold at 0.30 | 174 | 29% | +79.23 | 1.18 | −10.18 | −4.16 |
| my hold at 0.60 | 161 | 29% | +90.09 | 1.22 | −10.18 | +6.70 |
| **my risk-cap REMOVED** | 178 | 28% | **−40.70** | **0.93** | **−19.94** | **−124.09** |
| my risk-cap at 5.0 | 124 | 28% | +35.96 | 1.15 | −4.96 | −47.43 |

**Both of my additions earn their place**, and the risk cap is load-bearing: without it
the machine goes NEGATIVE and the worst trade nearly doubles. That cap was a number I
picked with no evidence, and it has been protecting the account ever since.

---

## 4. The combination

| arm | trades | WR | net | PF | per trade |
|---|---|---|---|---|---|
| AS SHIPPED | 171 | 29% | +83.39 | 1.19 | $0.49 |
| PURE PAGE (his text, my additions removed) | 49 | 39% | +84.16 | 1.44 | $1.72 |
| **HIS 3 + my 2 · ALL HOURS** | 119 | 34% | **+158.35** | 1.54 | $1.33 |
| **HIS 3 + my 2 · NY ONLY** | 39 | **46%** | +134.97 | **2.32** | **$3.46** |
| HIS 3 + my 2 · NY, hold 0.60 | 36 | 47% | +129.88 | 2.39 | $3.61 |

Two candidates, and they are a genuine trade-off:

* **ALL HOURS** — most money (+158.35), 119 trades, profit factor 1.54.
* **NEW YORK ONLY** — best quality: 46% win rate against 29% shipped, profit factor
  2.32, and **$3.46 a trade against $0.49**. Seven times the money per trade, on a third
  of the trades.

His standing goal is *fewer losing trades at fixed geometry*. By that measure NY-only
wins outright: 21 losing trades instead of 122.

---

## 5. What this changes

**Restore both of his clauses.** `InpMomBodyRatio 0.50 → 0.70` and
`InpBrkVolMax 1.5 → 1.0`. His text, measured better, three different ways.

**Keep both of my additions**, now with receipts rather than as silent defaults —
the hold test is worth +18.29 and the risk cap +124.09.

**The session law is his decision to make.** On 25 Aug he chose all-hours on the
evidence then available (v1.30, 7 days: +1,335 vs +1,044). On this evidence, with the
corrected clauses, the ranking has REVERSED — NY-only now wins on quality and nearly
matches on money. That reversal is worth him knowing; the choice stays his.

---

## 6. What I do not know

**Eight days.** His OANDA archive is the entire world this EA can be tested in. Every
number above rests on 5–27 August with the gaps that implies.

**Twenty configurations on one tape.** That is a lot of shots at one target, and this
week has already produced three findings that looked good on one window and died on the
next — the volume floor, the 2R target, the momentum spike. The DIRECTION here is
sturdy, because his values won on every clause independently AND in combination. The
MAGNITUDES are not.

**The live record is still four trades.** Nothing here has been proved with money.

The single thing that would most improve every number in this report is more of his
chart. The OANDA archive, not the strategy, is the binding constraint.
