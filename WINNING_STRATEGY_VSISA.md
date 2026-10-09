# WINNING STRATEGY — VSISA on Axi (XAUUSD M5)

*Started 2026-10-09. The one place to learn how to run VSISA, where it lives and what it has
proved. Update the "Results" table every time a new MT5 report comes in.*

---

## 1. What it is

**VSISA = Volume Spread Imbalance Shift Analysis**, Sajid Ahmed's volume method, built
into an EA on 2026-09-09 and refined to v1.24 by 2026-09-17. **Current: v1.28** (2026-10-10) — the looser fade, ~288 trades
over Jan–Oct instead of 163 (v1.25–v1.27 added optional sizing and other-market support).

In four lines:
1. A **cluster** of 2+ big-volume candles in one direction (effort).
2. A **reaction** candle closing the other way, on **low volume** (the resting orders are gone).
3. Enter on the reaction's close; stop just beyond the reaction candle.
4. Trade only with the M30 camel-hump trend; ratchet the stop up from 2R; target 10R.

It judges on the **broker's tick count**. That is why the broker matters: **it is tuned to
Axi's feed** (Zee, 2026-10-09: *"for VSISA we need AXI volume"*). It does **not** use OANDA.

## 2. Where everything is

| What | Where |
|---|---|
| EA source | `mt5/VSISA.mq5` (magic **88201**) |
| Compiled, ready to attach | Axi terminal: `%APPDATA%\MetaQuotes\Terminal\6FBEE76C719DC78AB2AE839B5A0C7442\MQL5\Experts\VSISA.ex5` |
| Also compiled | Blueberry terminal Experts folder (but see §5 — not the broker to run it on) |
| Zee's laws (his, never edit) | `LAWS_VSISA.md` |
| Each law with its MT5 verdict | `LAWS_VSISA_INFER.md` |
| Axi optimisation report (Sep) | `VSISA_AXI_OPTIMISATION.md` |
| Version-by-version history | `VERSION_HISTORY.md` → "VSISA" sections |
| The 2026-10-09 test reports | `testing/vsisa 9 october/` (zero latency) and `testing/vsisa 9 october/random delay/` |

## 3. How to run it

### Strategy Tester (Axi MT5)
| Setting | Value |
|---|---|
| Expert | **VSISA** (not "Moving Average" — check the report's Expert line) |
| Symbol | **XAUUSD.pro** |
| Timeframe | **M5** |
| Modelling | **Every tick based on real ticks** |
| Delays | **Random delay** |
| Deposit | **25000 USD** (0.28 lots needs the margin) |
| Leverage | 1:400 (Axi default) |
| Dates | 2026.01.01 → today |
| Inputs | defaults; `InpOandaVolume = 0` |

Check the Journal: it must start `[VSISA] v1.28 - setup AUTO 2-10 bars ...` and the
`VOLUME SOURCE` line must say broker tick count. The run should show **288 trades**
(~163 means old cached inputs: reset to defaults; `InpFadePct` 0.65, `InpFadeLook` 5).

### Live / demo
1. Open an **XAUUSD.pro M5** chart in the Axi terminal.
2. Drag **VSISA** on, tick *Allow Algo Trading*, keep the default inputs.
3. Size: **0.28 lots is for ~$25,000**. Scale down in proportion (≈0.05 lots on $5,000),
   or use the risk option below.
4. One chart only — two charts with magic 88201 would double every trade.

### Optional: risk-based sizing (v1.25, OFF by default)
- `InpRiskPct = 0` → fixed `InpLots` (the tested behaviour, all numbers below).
- `InpRiskPct = 0.5` → every trade sized so a full stop loses 0.5% of current equity; profits
  compound. For scale, the fixed 0.28 lots on $25k averaged a $134 loss ≈ **0.54%**.
- `InpRiskMaxLots` (default 5) caps the size; the EA also never uses more than 80% of free
  margin and rounds lots **down**.
- **Not yet tested in MT5** — see §6.

## 4. Results (MT5 Strategy Tester only — no Python numbers here)

**Axi demo, XAUUSD.pro, M5, 2026-01-01 → 10-08, 99% real ticks, $25,000, 0.28 lots, v1.24 defaults**

| | zero latency | **random delay** |
|---|---|---|
| Net profit | +$14,968.82 | **+$15,817.64** (+63%) |
| Profit factor | 2.39 | **2.41** |
| Trades / win rate | 163 / 51.5% | 163 / 49.7% |
| Max equity drawdown | $1,014 (2.7%) | $1,042 (3.3%) |
| Avg win / avg loss | +$306.59 / −$134.20 | +$333.84 / −$134.65 |
| Largest win / loss | +$1,676.64 / −$251.72 | +$1,676.64 / −$336.28 |
| Worst losing run | 5 trades, −$772.52 | 6 trades, −$840.84 |
| Recovery factor | 14.76 | 15.18 |

- **Every month made money**, January to October.
- **No single trade carries it:** the largest win is ~11% of the profit.
- **Delay does not hurt it:** it decides on closed M5 candles and its stops are $10–$25 wide,
  so milliseconds don't matter (the opposite of the 1-minute breakout work).
- **Days it never saw** (v1.24 shipped 17 Sep; 18 Sep → 7 Oct): ~19 trades,
  **+$2,010.62** with random delay, +$1,278.70 with zero latency.

**Earlier receipt (2026-09-09, v1.00):** Blueberry real ticks, Feb → Sep, 0.10 lots:
+$3,127.60, 120 trades, PF 1.94, 6 of 7 months green.

### Risk-sizing test (v1.25, 2026-10-09)
Axi, same window and settings (random delay, $25k), only `InpRiskPct` changed.
Reports: `testing/vsisa 9 october/with input risk/`.

| `InpRiskPct` | net | PF | max equity DD | worst losing run | lots used | recovery factor |
|---|---|---|---|---|---|---|
| 0 (fixed 0.28) | +$17,014 | **2.55** | $1,014 (3.8%) | 5, −$749 | 0.28 | **16.8** |
| 0.5 | +$16,470 | 2.27 | $1,615 (4.3%) | 6, −$1,226 | 0.14–0.90 | 10.2 |
| 1.0 | **+$46,897** | 2.37 | $4,965 (8.5%) | 6, −$3,794 | 0.28–2.96 | 9.5 |
| 1.0 (rerun, v1.26) | +$48,842 | 2.44 | $3,997 (6.9%) | 5, −$2,841 | 0.28–3.04 | 12.2 |

Monthly ($): fixed is green every month; 0.5% and 1.0% each lose a little in February
(−$9 / −$11).

**What it means:**
- **Equal risk per trade is *worse* than fixed lots** at the same scale: 0.5% ≈ the fixed
  size, yet it made less money with more drawdown. Fixed lots put more money on wide-stop
  setups, and those are evidently the better ones; equal-risk sizing shrinks them (down to
  0.14 lots) and inflates tight-stop ones (up to 0.90).
- **1.0% makes 2.8× the money but with 2.2× the drawdown %.** The extra comes from
  doubling the size and compounding, not from the sizing method. Return per unit of
  drawdown (recovery factor) falls from 16.8 to 9.5.
- An **8.5% drawdown is too close to a 10% funded-account floor.**
- Two fixed-lot runs of the same settings gave +$15,818 and +$17,014: random delay
  alone moves the result by about ±$1,200.

**Decision so far:** keep `InpRiskPct = 0`. Next candidate (built as v1.26, below):
compound while keeping the fixed-lot weighting, i.e. lots proportional to equity.

### Optional: equity-proportional compounding (v1.26, OFF by default)
- `InpCompoundBase = 25000` → lots = `InpLots` × equity / 25,000 (0.28 at $25k, 0.34 at $30k,
  0.20 at $18k). Every setup keeps the same weight relative to the others; only the
  overall size follows the account.
- `0` = off (fixed lots). Ignored if `InpRiskPct > 0`. Same safeguards: `InpRiskMaxLots`
  cap, ≤ 80% of free margin, lots rounded down.
- **Tested 2026-10-09** (Axi, same window, random delay, $25k, `InpRiskPct = 0`,
  `InpCompoundBase = 25000`; report `with input risk/ReportTester-InpCompoundBase-25000-riskpct-0.html`):

| | fixed 0.28 | **compounding** |
|---|---|---|
| Net | +$17,014 | **+$19,291** |
| PF | 2.55 | 2.34 |
| Max equity DD | $1,014 (3.8%) | $1,615 (3.85%) |
| Worst losing run | 5, −$749 | 6, −$1,286 |
| Lots used | 0.28 | 0.27 → 0.49 |
| Recovery factor | 16.8 | 11.9 |
| Unseen 18 Sep → 8 Oct | — | +$3,638 |

  Every month green. Drawdown **%** is unchanged, as designed; the dollar drawdown and
  recovery factor move only because later trades are bigger. The +$2.3k gain is barely
  above the ±$1.2k run-to-run noise over 9 months; the benefit grows the longer it runs.
  **Verdict: compounding keeps fixed-lot risk and adds growth. Safe to use; not yet the
  compiled default.**

### More trades per day (v1.27, 2026-10-09 night)
Zee: *"we can take as many setups as possible within a single day.. so we're not kept waiting
all day long"*. Court: Axi rig (`C:\mt5_rig_axi`, a portable copy, never the live terminal),
real ticks, random delay, $25k, 1 Jan → 8 Oct. Harness: `monitor/strategy_lab/axi_rig.py` +
`vsisa_more_trades.py`; raw rows in `vsisa_more_trades.jsonl`.

**Other markets and timeframes: the edge is gold M5 only.** Other markets were run at gold's
proportions (`InpPtsScale` = market's avg M5 range ÷ gold's 454 pts; lots sized so one
average candle ≈ $127, like gold at 0.28):

| run | trades | net | PF | max DD |
|---|---|---|---|---|
| gold M5 (shipped) | 163 | +$17,486 | 2.60 | 2.65% |
| gold M15 | 65 | +$2,505 | 1.21 | 13.7% |
| gold M1 | 894 | −$4,214 | 0.89 | 17.8% |
| US30 | 194 | −$712 | 0.96 | 16.8% |
| USTECH | 87 | +$1,207 | 1.13 | 10.2% |
| GER40 | 261 | +$95 | 1.00 | 13.0% |
| BTCUSD | 407 | −$3,146 | 0.89 | 17.1% |
| GBPUSD | 439 | −$10,952 | 0.74 | 48.4% |
| USDJPY | 251 | −$8,087 | 0.67 | 35.1% |

Not run: US500 (fourth index, after three failed), XAGUSD (spread 25% of a candle),
XPTUSD (spread larger than a candle). USOIL skipped (spread 15% of a candle; FX at 10% already lost badly). Spread as a share of the average candle predicts the result: gold 2.8% is the only market that works.

**The fade grid on gold M5 — this is where the extra trades are** (`InpFadePct` × `InpFadeLook`):

| fade ≤ | 4 bars | 5 bars | 6 bars |
|---|---|---|---|
| 0.60 | **shipped:** 163, +$17.5k | 195, +$15.5k | 229, +$15.4k |
| 0.65 | 230, +$17.2k | **288, +$19.4k** | 339, +$14.0k |
| 0.70 | 345, +$11.8k | 437, +$18.4k | 505, +$16.3k |
| 0.75 | 493, +$14.1k | 636, +$15.5k | 728, +$13.4k (DD 12%) |

Every cell makes money. With the fade at 0.65/5: fake break OFF → 1,192 trades, +$16.7k,
PF 1.15, DD 11.5% (rejected); sweep 50 → 220, +$16.3k; sweep 20 → 360, +$12.7k (both worse
than the shipped 30).

| gold M5 | trades | days with a trade | net | Jan–Apr | May–Oct | DD | net/$DD |
|---|---|---|---|---|---|---|---|
| shipped 0.60/4 | 163 | 104 | +$17,486 | +$2,343 | +$15,143 | 2.65% | 16.5 |
| **fade 0.65/5** | **288** | **141** | **+$19,417** | **+$3,416** | **+$16,001** | 4.1% | 11.2 |
| fade 0.70/5 | 437 | 162 | +$18,418 | +$4,316 | +$14,102 | 6.9% | 10.0 |

**SHIPPED as v1.28 (2026-10-10): `InpFadePct 0.65`, `InpFadeLook 5`.** Ship receipt, compiled
defaults, fixed 0.28 lots: **+$17,745 · 288 trades · PF 1.86 · DD $1,679 (4.08%) · a trade on
141 days instead of 104.**
Compounding was tested on top and **left off**: +$19,390 but DD 6.63% (lots reach 0.49 just as
the weaker late months arrive). Turn it on with `InpCompoundBase` only if a ~7% drawdown is
acceptable for the account.

## 5. What NOT to do
- **Don't run it on Blueberry.** On Blueberry's feed the same weeks lost: 17 Sep → 8 Oct
  −$801 (7 trades). The edge lives in Axi's tick volume.
- **Don't switch on OANDA volume** (`InpOandaVolume = 1`) — that feed is for the UHV EAs.
- **Don't trust short windows.** The September Axi report: a variant that made +$12,557
  in 9 days lost −$9,437 over 8 months. Judge on months.
- **Don't change defaults without an MT5 report** (CLAUDE.md: Python may suggest, only MT5
  or live fills may promote).

## 6. Open items
1. **Forward record.** Only three weeks are truly out-of-sample. Run it on the Axi demo and
   log every trade here.
2. ~~Risk sizing test (v1.25)~~ — done 2026-10-09, see §4: equal-risk sizing lost to fixed
   lots. v1.26 equity-proportional lots tested the same day: +$19,291 at the same 3.85% DD.
3. **Funded-account sizing.** On a 10%-floor account, keep risk per trade small enough that
   the worst run (6 losses) can't come near the floor.
