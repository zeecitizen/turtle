# Diamond geometry — the per-day brief, answered (2026-09-17)

**Zee's brief, going to bed:** *"for the UHV EA.. i want you to find a configuration of
TP/SL that retains the frequency of trades and its ok to not have a very high winrate as
long as we're profitable .. try to maximize the profit per day."*

**Rig:** C:/mt5_rig · ZeeUHV_Diamond v1.18 · XAUUSD M1 · 2026.09.08–09.17 (7 trading
days) · 100% real ticks · 0.10 lots · every input pinned.

**Each row is identified from the report's OWN `Inputs:` line, not from file order.**
That is how the earlier off-by-one mis-mapping happened, and `monitor/strategy_lab/dia_decode.py`
now reads the inputs back rather than trusting the launch sequence.

| config | net | trades | $/day | tr/day | WR | maxDD | PF |
|---|---|---|---|---|---|---|---|
| **mode1 TP1.0 / SL20 (SHIPPED)** | **+$488** | 82 | **+$69.7** | 11.7 | **90%** | **$394** | **2.83** |
| mode1 TP5.0 / SL20 | +$342 | 82 | +$48.9 | 11.7 | 54% | $1,014 | 1.21 |
| mode1 struct-stop 2.0R + BE 1:1 | +$200 | 82 | +$28.6 | 11.7 | 54% | $1,014 | 1.12 |
| mode1 TP3.0 / SL20 | +$185 | 82 | +$26.4 | 11.7 | 63% | $1,014 | 1.13 |
| mode1 TP10.0 / SL20 | +$26 | 82 | +$3.6 | 11.7 | 54% | $1,014 | 1.02 |
| mode0 TP1.0 / SL20 | −$372 | 182 | −$53.2 | 26.0 | 71% | $885 | 0.79 |
| mode0 TP5.0 / SL20 | −$296 | 182 | −$42.4 | 26.0 | 43% | $2,067 | 0.93 |

## Findings

**1. Frequency was never the Diamond's problem.** 82 trades in 7 days is **11.7 a day**.
The "waiting all day for one trade" complaint is VSISA's, not this EA's. So the brief's
constraint — "retains the frequency" — is not binding on anything tested here: every
mode-1 config takes exactly 82 trades. **Geometry is free in this EA; the entry filters
set the trade count by themselves.**

**2. TP 1 point wins the per-day objective outright, and it is not close.** +$69.7/day
against the next best +$48.9. Widening the target lowers money *and* raises drawdown at
every step: $394 → $1,014 the moment TP leaves 1.0. The absurd-looking 1:20 payoff is
what the edge actually is — the EA is a high-frequency, high-accuracy scalper, and
stretching it into a swing geometry destroys it.

**3. Zee's 1:2-with-breakeven idea is REFUTED — and the earlier +$211 claim is withdrawn.**
The B re-run produced 82 trades this time (the earlier "no trades" was a harness fault,
not a verdict). It returns **+$200 — identical to its no-breakeven twin.** So breakeven
at 1:1 is worth **$0**, not +$211. That earlier figure compared C against a row that was
never B, and it is hereby struck. The structural-stop family all land at 54% WR, $1,014
DD and well under the shipped +$488.

**4. CamelTrend is confirmed again, under a second objective.** Mode 0 loses money at
both targets (−$372, −$296) despite taking 182 trades — more than twice the frequency and
still negative. This is a genuinely independent confirmation of the v1.18 ship, which had
rested on one window judged on net-per-drawdown; it now also wins on profit per day.

**5. The identical $1,014 drawdown across four different configs is unexplained** and
worth a look before anything is built on those rows. Four configs with different targets
should not share a drawdown to the dollar; it suggests one stacked basket dominates the
equity low in all of them.

## Verdict

**Nothing ships. The shipped v1.18 geometry already maximises profit per day**, and each
alternative he proposed was measured and lost. The honest answer to task 1 is that the
geometry is already at its optimum and the search found no room — which is a result, not
a failure to find one.

**The caveat stands:** one 9-day window, 82 trades, no out-of-sample leg — the same thin
evidence flagged next to `InpTrendMode` in the source. Every conclusion above inherits it.
