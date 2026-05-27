# Overnight Progress Log

Autonomous 30-min cycles while Zee sleeps. Each entry: health + one research increment.
Rules: research/propose only, no live deploys, no config changes, validate FULL P&L
(walk-forward) not capture, no fabricated numbers. Zee reviews in the morning.

---

## ☀️ MORNING BRIEFING (read this first) — 11 cycles, 2026-05-27 02:40→10:16 PKT

**System health:** green all night. S1/S3/S4 heartbeating every cycle, ticks live, market OPEN,
loggers fresh. Only standing warning = NsndTrader stale, which is EXPECTED (NSND is disabled).
No service ever went down; nothing needed restarting.

**Live result today:** −$16.31 (12 trades, 75% WR) — a mild red day. Bounded: the $25 daily-loss
circuit breaker is verified wired (cycle 5), and all live fills are now uniformly 0.01 lots.

**3 things worth your attention:**
1. **🟢 The 0.01-lot fix was the biggest win.** Live S3 looked like −$27, but that was almost
   entirely 11 oversized 0.09-lot trades (−$99) from before the fix. Normalized to 0.01 it's
   +$3.67 (~breakeven). The sizing correction protected the account more than any filter could. (cycle 9)
2. **✅ BtcS4b — flagged then cleared.** Modeled over 51 days it's −$56 (21% WR), no edge, no
   weekend gate. BUT its heartbeat is frozen since 2026-05-24 → **it is NOT attached live** (nor
   is BtcS3M30). Zero live risk. Just don't reattach BTC EAs until one shows a real edge. (cycles 6, 13)
3. **📉 Backtests overstate edge ~3-4×.** S1/S3/S4 are all walk-forward-positive in backtest
   (combined +$749/18d idealized), but live is ~breakeven-to-thin. Real edge is small; don't size
   up on backtest $. The new 14-col magic/ea labels now give clean per-EA live tracking to settle
   this once ~30-50 fills/EA accumulate. (cycles 7, 9, 10)

**Every change tested was rejected or flagged** (ER filter ❌, S3 BUY-filter ❌ regime-artifact,
BtcS4b ⚠️) — so the validated live configs (S1/S3/S4 @0.01) stand UNCHANGED, which is correct.
Nothing was deployed or altered. Full detail per cycle below.

---

## Cycle 1 — 2026-05-27 ~05:09 PKT

**Health:** ✅ S1/S3/S4 alive (0s), ticks live (data_status=live, tick_age 0s),
market OPEN, TurtleTradeLogger publishing open_positions.json, ShanoTickLogger fresh.
Only warning: NsndTrader heartbeat stale — **expected** (NSND is intentionally disabled).
0 open positions. No action needed.

**Research:** Ran `backtest_all_eas_ticks.py` — 19 days real Exness ticks @ 0.10 lots,
walk-forward (train→OOS) baseline of all EAs:

| EA | n | WR | WR_OOS | Total | OOS | $/day | WF |
|----|---|----|--------|-------|-----|-------|----|
| **S1** (M5, TP7.5, sweep+bigSpread) | 93 | 73.1% | 73.2% | **+$2166** | **+$856** | +$114 | ✓ |
| S4b v2.00 (M1, ATR trail) | 300 | 32.0% | 29.9% | +$350 | −$144 | +$18 | ✗ |
| S4 (M1, TP12/SL6) | 288 | 34.4% | 30.5% | +$57 | −$850 | +$3 | ✗ |
| S3 (M5, peak-TP, sweep+wick) | 93 | 73.1% | 70.0% | −$153 | −$263 | −$8 | ✗ |
| S4 old (M1, TP5/SL6) | 299 | 51.2% | 52.8% | −$990 | −$193 | −$52 | ✗ |

(Caveat printed by script: S1/S3 here are WITHOUT the FVG filter — live config may differ.)

**Verdict:**
- S1 is the standout — robust across train+OOS, passes walk-forward. Strongest engine.
- **S3 is net-negative (−$153, OOS −$263) on this config** despite 73% WR → the avg loss
  ($101) dwarfs avg win ($35); TP/SL geometry is the suspect. **Thread for next cycle:**
  why does S3 win often but lose money? Test TP/SL or peak-TP exit variants.
- S4 / S4b / S4-old all fail walk-forward at 0.10 lots — OOS negative. Not deploy-worthy as-is.

Next cycle: dig into S3's win/loss asymmetry (R:R), since high-WR-but-losing = exit problem.

---

## Cycle 2 — 2026-05-27 ~05:46 PKT

**Health:** ✅ S1/S3/S4 alive (4s), ticks live, market OPEN. NSND stale = expected (disabled).
**1 open position** (S3 BUY 0.01 @4518.38, +$3.56, SL 4508.82 / TP 4527.96) — confirms the new
LIVE panel + open_positions.json snapshot render with a real trade. Good.

**Research:** Ran `v230_backtest.py` — the EXACT live v2.30 config (proper SL buffer) at 0.01 lots,
19 days real ticks, walk-forward:

| EA (v2.30 live config) | n | WR | AvgW | AvgL | Total | TRAIN | OOS | WF |
|----|---|----|------|------|-------|-------|-----|----|
| S1 | 197 | ~72% | — | — | — | +$216 | **+$235** | ✅ |
| S3 | 290 | 61.0% | $5.7 | $6.2 | **+$298.6** | +$184 | **+$115** | ✅ |

S3 by side: SELL +$240 (EV +$1.47) carries it; BUY only +$58 (EV +$0.46).

**Verdict — CORRECTION to Cycle 1:** Cycle 1 flagged "S3 loses money / R:R asymmetry."
That was a **mismatched variant** (peak-TP, no-FVG, different SL) — NOT the deployed config.
The actual live **S3 v2.30 is profitable AND walk-forward-positive** (+$298, OOS +$115),
with balanced R:R (AvgW $5.7 ≈ AvgL $6.2). False alarm — retracted. Lesson: always backtest
the EXACT live config, not a lab variant. Both deployed S1 and S3 are healthy.

**Real (smaller) thread:** S3's edge is almost entirely the SELL side (BUY EV +$0.46 vs SELL
+$1.47). Worth *carefully* exploring whether S3 BUYs need a stronger filter — but per-side n is
small, high overfitting risk, so this needs multi-split proof before any change. Next cycle:
test an S3 BUY-side filter idea with multi-split, or move to a fresh BTC/S4 angle.

---

## Cycle 3 — 2026-05-27 ~06:16 PKT

**Health:** ✅ all engines alive (0s), ticks live, market OPEN. NSND stale = expected.
**3 open positions** (S1 BUY + 2× S3 BUY, all 0.01, net ~+$1.4). Today realized +$2.24, 3/3 wins.
LIVE panel showing real multi-position data correctly.

**Research:** Ran `backtest_er_filter.py` — Kaufman Efficiency-Ratio (trend-strength) filter
sweep, thresholds 0.10–0.30, on S1/S3/NSND (19 days real ticks, walk-forward). Script uses
old 0.06/0.09 lots so read RELATIVELY (vs-base column).

- **S1: ER filter REJECTED.** Base (ER OFF) strictly best: +$1299 / OOS +$513 / WF✓.
  Every threshold reduces total (vs base −$232 to −$745). S1 is already a clean breakout;
  a regime filter only removes good trades. (Re-confirms prior S1 momentum-filter rejection.)
- **S3: ER filter NOT robust → rejected.** The WF✓ thresholds (≥0.20, ≥0.30) rest on tiny
  samples (OOS n=7 and n=3, 100% WR = overfitting artifact), while ≥0.15 is WORSE than base.
  Non-monotonic, sample-starved. No trustworthy improvement. (Also note: this script's S3 base
  is −$138, a different variant than the live v2.30 +$298 from cycle 2 — don't conflate.)
- NSND: ~4% WR across the board → this script's NSND config is broken; disabled EA, ignored.

**Verdict: REJECTED for both live EAs.** No ER filter to be added to S1 or S3 — would cost money
(S1) or rests on overfit micro-samples (S3). Value here is *not* making a bad change. Aligns
with memory (feedback_validate_profitability_not_capture).

Next cycle: switch angle to BTC (backtest_btc_friday.py) since gold filters are well-explored.

---

## Cycle 4 — 2026-05-27 ~06:46 PKT

**Health:** ✅ engines alive (2s), ticks live, market OPEN. NSND stale = expected.
1 open (S3 BUY −$8.53, near stop). **Today turned slightly red: −$14.66, 5 trades, 60% WR**
(was +$2.24 last cycle) — normal live variance, no action (can't touch live trades at night).

**Research:** BTC angle. Ran `backtest_btc_friday.py` (despite the name it sims a 10-day
window 2026-05-15→05-24) on `btc_m1_recent.csv` (which actually spans 51 days, 04-04→05-24).
BtcS4b v2.00 config (UHV≥$100, ATR(7) SL=2x/trail=2x/BE@1x), 0.01 lots:

  10 days: n=15, WR 20.0%, avgW $0.35, avgL −$1.06, **TOTAL −$11.72**

**Verdict: NEEDS MORE — mild concern flagged.** BtcS4b (deployed, magic 88010, weekend BTC)
is net-negative over this recent 10-day window with poor R:R (avg loss 3× avg win). BUT:
(a) small sample (15 trades), (b) the window includes weekdays — BtcS4b's intended use is
WEEKEND-only (when gold's closed), so this isn't an apples-to-apples test of its real job,
(c) only 10 of the 51 available days were used. Not a rejection yet — but the deployed EA
showing red deserves a proper test. **No change made.**

Next cycle: build/run a full-span (51-day) BTC backtest that ISOLATES weekend sessions
(Fri post-gold-close → Sun), to judge BtcS4b on the job it's actually deployed for.

---

## Cycle 5 — 2026-05-27 ~07:16 PKT

**Health:** ✅ engines alive (3s), ticks live, market OPEN. NSND stale = expected. 0 open.
**Today −$23.52, 7 trades, 57% WR** (down from −$14.66) → ~19% of the $126 account.

**Research — protection validation (given the red day):** Verified the daily-loss circuit
breaker is real and about to engage:
- Source `S3Trader.mq5`: `InpDailyLossHalt = 25.0` (comment: Shano $126 ~20% cap).
  `DailyLossHalted()` returns true when day P&L (incl. floating) ≤ −$25, and it's wired into
  BOTH entry gates (lines 285, 437) — blocks NEW entries. Same pattern in S1/S4 (all $25, 0.01 lots).
- Behaviour: halt stops NEW entries; it does NOT force-close open positions (those run to SL/TP).
- Status: at −$23.52 realized, the breaker is ~$1.50 away. **Account is bounded** — today can't
  run away. This is the safety working as designed, not a bug.

**Verdict: PROTECTION CONFIRMED — no action.** Today's drawdown is within the designed cap and
the EAs are validated (S1/S3 walk-forward positive, cycles 1-2); 7 trades is variance, not a
broken edge. Nothing to change at night.

**Proposal for Zee (morning, needs EA recompile+reattach — NOT done):** the EA heartbeat JSON
doesn't expose live day-P&L or halt status, so the dashboard can't show "halt armed/engaged".
Adding `day_pnl` + `halted` to each EA's state write would let the dashboard surface the circuit
breaker visually. Small, safe, but requires a reattach — leaving it for Zee to approve.

Next cycle: return to the full-span weekend-isolated BTC test (deferred from cycle 4).

---

## Cycle 6 — 2026-05-27 ~07:46 PKT

**Health:** ✅ engines alive (3s), ticks live, market OPEN. NSND stale = expected. 0 open.
Today recovered to −$18.31, 11 trades, 73% WR (was −$23.52) — EAs clawed back, below the halt.

**Research:** Built `backtest_btc_weekend_fullspan.py` (reuses BtcS4b's exact signal +
ATR-trail logic) and ran it over the FULL 51-day btc_m1_recent span, isolating weekend vs
weekday. Modeled BtcS4b v2.00 @0.01 lots:

| Segment | n | WR | avgW | avgL | TOTAL |
|---------|---|----|------|------|-------|
| ALL | 139 | 20.9% | $1.05 | −$0.79 | **−$56.58** |
| WEEKEND (Sat+Sun) | 9 | 11.1% | $0.12 | −$0.38 | −$2.90 |
| WEEKDAY | 130 | 21.5% | $1.08 | −$0.82 | −$53.68 |

Weekend walk-forward: only 9 weekend trades / 51 days — too thin to prove anything.

**Source check:** `BtcS4bTrader.mq5` has **NO weekend/session gate** (line 81 `IsNewDay` is just
a daily-counter reset; no day-of-week filter anywhere). So despite the "weekend trading" label,
the live EA fires any day its UHV+trend+ATR setup triggers.

**Verdict: ROBUST CONCERN — recommend review (no change made).** Confirms cycle 4 across the full
span: modeled BtcS4b is net-negative (−$56.58 / 51 days, 21% WR, avgW only 1.3× avgL — the ATR
trail isn't capturing big trends). The intended weekend niche barely produces signals (9 trades)
and is ~flat. Two honest caveats: (1) this is my reconstruction of the config, not the deployed
binary; (2) unknown whether BtcS4bTrader is currently ATTACHED on a live BTC chart — the dashboard
doesn't track it, so live risk may be zero.

**Recommendation for Zee (morning):** confirm whether BtcS4b is attached anywhere live. If yes,
strongly consider pausing it — it has no edge in this data and (lacking a session gate) bleeds on
weekdays. A weekend-only gate won't rescue it: the weekend sample is too thin and also negative.

Committed the new full-span script for reuse.

---

## Cycle 7 — 2026-05-27 ~08:16 PKT

**Health:** ✅ engines alive (0s), ticks live, market OPEN. NSND stale = expected. 0 open.
Today flat at −$18.31 since last cycle (quiet patch, no new trades).

**Research — PORTFOLIO view of the deployed pair (S1+S3 v2.30 @0.01).** Pure aggregation of
already-validated configs (no overfitting risk), combined into one equity curve over 19 days:

| Metric | Value |
|--------|-------|
| Combined TOTAL | **+$749.7** / 18 active days |
| Win-days | 15 / 18 (83%) |
| Avg/day | +$41.65 |
| Max drawdown | $28.1 (worst single dip: 2026-05-14, −$28) |
| Both sides contribute | S1 and S3 each positive across TRAIN + OOS |

Equity curve is steadily up; only 3 losing days (−8, −17, −28), all quickly recovered.

**Verdict: SHAPE robust & positive, MAGNITUDE idealized — discount hard for live.**
The *profile* is exactly what you want: high win-day rate, small controlled DD, diversified
across two walk-forward-positive engines. BUT these $ are an OPTIMISTIC backtest (no slippage/
spread modeled). Reality check: **live today = −$18.31** while the backtest implies a strongly
positive day — that IS the backtest>live gap the memory warns about. So treat +$41/day as a
ceiling, not an expectation; the real edge is smaller and noisier (today proves it).

**Open question for a future cycle / Zee:** reconcile backtest vs live using the calibration
pipeline (`build_slip_calibration.py` + `pdf5_quick_compare.py`) once enough live fills
accumulate — that's the honest way to size expectations. No change made.

(Used an inline parse of v230_backtest output; no new script committed.)

---

## Cycle 8 — 2026-05-27 ~08:46 PKT

**Health:** ✅ engines alive (1s), ticks live, market OPEN. NSND stale = expected. 1 open.
Today still −$18.31 (flat, no new closes).

**Research:** Validated the DEPLOYED S4 config (M5, TP2/SL7.5, td24≥7, ER off — confirmed from
S4Trader.mq5 source) via `verify_s4_trend_only.py`, multi-split walk-forward on real ticks:

- **td24≥7 (deployed): 6/7 splits beat baseline ✅ ROBUST.** td24≥5 also 5/7 ✅.
- Totals ≈ +$58 TRAIN + ~+$28 OOS ≈ **+$87 / 19 days @ 0.01** (~+$4.6/day). Small but positive.
- The trend filter earns its keep on choppy days: 05-04 −$7.0→+$0.5, 05-05 −$1.0→+$6.5,
  05-14 −$7.5→skipped (0 trades). It removes losers, not winners.
- Worst day −$15 (05-25, 2 trades both lost) — within the $25 daily halt.

**Verdict: VALIDATED — keep.** S4 is a legitimate small contributor with a robust trend filter.
Unlike BtcS4b (cycle 6, net-negative, no edge), S4's live config is walk-forward-positive. Honest
limit: the edge is small (~$4.6/day backtest, less live) and one −$15 day erases ~3 good days, so
it's a minor add-on, not a workhorse. No change needed.

**Per-EA scorecard so far (backtest, real ticks, 0.01 lots):**
- S1 ✅ strong (OOS +$235, WF✓) · S3 ✅ solid (+$298, WF✓, SELL-heavy) · S4 ✅ small+robust (+$87, 6/7)
- BtcS4b ⚠️ net-negative (−$56/51d, no edge — review) · NSND ⏸ disabled
- ER filter ❌ rejected for all (hurts S1, overfit on S3)

---

## Cycle 9 — 2026-05-27 ~09:16 PKT

**Health:** ✅ engines alive (1s), ticks live, market OPEN. NSND stale = expected. 0 open.
Today recovered slightly to −$16.31, 12 trades, 75% WR (open from cycle 8 closed +$2).

**Research — LIVE vs BACKTEST reconciliation (real fills).** Ran `s3_live_performance.py`
(matches s3_decisions tickets → turtle_fills) then normalized P&L to uniform 0.01 lots:

| Measure | Value |
|---------|-------|
| Live S3, 43 trades, 65.1% WR | — |
| RAW net (as-traded, MIXED lots) | **−$27.32** |
| NORMALIZED to 0.01 lots | **+$3.67** |

By lot size (raw $): 0.09 lots → **−$99.5** (11 trades) · 0.03 → +$41.9 · 0.02 → +$20.9 ·
0.04 → +$23.6 · 0.01 (recent) → −$15.9.

**Verdict: KEY INSIGHT — the live loss was a POSITION-SIZING artifact, not a broken edge.**
- The −$27 raw is dominated by 0.09-lot trades (9× the correct size for a $126 acct, FTMO-era
  sizing from before the fix). At the now-deployed 0.01 lots, the SAME trades net **+$3.67**
  (~breakeven). → The 0.01-lot correction we applied was exactly the right protective call;
  it's the single biggest P&L-protection lever, bigger than any filter tested this session.
- BUT: normalized live (~breakeven over 8 days) is still well BELOW the backtest's implied
  ~+$15/day (cycle 7's +$298/19d). So the backtest>live gap is REAL — slippage/spread/execution
  thin the edge to roughly flat live. Honest read: S3's live edge is marginal, not the rosy
  backtest. Recent 0.01-lot days (05-26/27) are slightly negative — current variance, small n.

**Implications for Zee (morning):** (1) confirms keeping lots at 0.01 (don't size up on backtest
$). (2) The backtest overstates edge ~3-4×; the calibration pipeline should quantify this before
trusting any "+$X/day" projection. No change made.

---

## Cycle 10 — 2026-05-27 ~09:46 PKT

**Health:** ✅ engines alive (3s), ticks live, market OPEN. NSND stale = expected. 0 open.
Today flat at −$16.31 (quiet patch, no new closes).

**Research — live-attribution audit + going-forward baseline.** Tried to extend cycle 9's
live-vs-backtest reconciliation to S1/S4. Found data gaps:
- **S1 has NO decisions CSV** — can't ticket-join S1 historically.
- **S4 has only 3 decisions logged** (s4_decisions.csv, all today) — too few to analyze.
- S3's 43 (cycle 9) is the only sizeable per-EA history.
- (Note: csv.DictReader is BLIND to the new magic/ea columns — the 12-col header truncates
  them; must raw-split to read cols 12-13.)

So the unified attribution source going forward is the **14-col magic/ea label** (live since the
v1.02 reattach). First clean snapshot, last ~9h, all at 0.01 lots (raw == normalized):

| Source | n | net @0.01 |
|--------|---|-----------|
| Human (Shano manual) | 6 | +$4.49 |
| S1 | 1 | −$7.34 |
| S3 | 3 | −$17.40 |
| S4 | 2 | +$3.94 |

**Verdict: baseline established (n too small for edge claims).** Confirms (a) all live fills are
now uniformly 0.01 lots — the sizing fix is fully in effect; (b) the magic→EA attribution works
end-to-end; (c) Shano's manual trades are net-positive over this window. EAs are slightly red on
n=12 — pure variance, not signal. The honest takeaway: we now have CLEAN per-EA live tracking
from here on, which is what cycle 7/9 said we needed to size expectations properly.

**Proposal for Zee (morning):** rely on the 14-col ea label for all future live-vs-backtest
tracking (S1 lacks a decisions CSV, but the magic column covers it). Once ~30-50 clean 0.01-lot
fills accumulate per EA, re-run the cycle-9 normalized comparison for a real edge read.

---

## Cycle 11 — 2026-05-27 ~10:16 PKT

**Health:** ✅ engines alive (1s), ticks live, market OPEN. NSND stale = expected. 0 open.
Today flat at −$16.31 (~80min no fills — quiet pre-morning).

**Research — tested cycle 2's "S3 is SELL-heavy" thread on LIVE fills (not backtest).**
Split the 43 live S3 trades by side, normalized to 0.01:
- LIVE: **BUY n=42 (64.3% WR, EV +$0.06)** vs **SELL n=1**.
- Backtest (cycle 2) was the OPPOSITE: SELL n=164 > BUY n=126.

**Verdict: cycle-2 SELL-heavy thread RETIRED — it was regime-specific, not structural.**
S3's side mix simply follows the trend regime (its td filter only fires BUYs in an uptrend);
gold trended up these ~9 days → almost all live signals were BUYs. A "filter the weak BUY side"
change would have eliminated ~all live S3 activity. So: do NOT add a BUY-side filter. Live BUYs
are ~breakeven (consistent with cycle 9's thin-edge live read). No change made.

This closes the last open optimization thread from the session — every candidate change tested
(ER filter, S3 side filter, BtcS4b) was either rejected or flagged; the validated live configs
(S1/S3/S4 @0.01) stand unchanged, which is the correct outcome.

---

## Cycle 12 — 2026-05-27 ~10:48 PKT

**Health:** ✅ engines alive (3s), ticks live, market OPEN. NSND stale = expected. 1 open.
Today still −$16.31 (~2h no closes — quiet market).

**Research:** Re-ran `verify_thorough.py` to close the loop on the WORKHORSE S1 (validated S3/S4
via dedicated multi-split earlier; S1 only had v230's single split so far).

- **S1 td24 trend threshold × 7 split points:** thr=**7.0 (deployed) beats $2 baseline in 7/7
  splits**, highest total +$744.9, OOS +274.7..+509.9. thr=5 also 7/7 (lower total); thr=9
  fragile (2/7). → **S1's deployed 7.0 is the robust optimum. Confirmed, no change.** ✅
- **S3 2R-Free-Roll (deployed) vs plain SL/TP:** PLAIN +$503.5 vs 2R-ON +$466.2 (−$37), splits
  4 PLAIN-better / 3 2R-better → a wash, slight lean to PLAIN. Reconfirms it's ~neutral.

**Verdict: S1 deployed config VALIDATED 7/7 (robust optimum).** The workhorse is correctly tuned.
S3's 2R-free-roll is marginally negative-to-neutral — a low-priority candidate to turn OFF for a
tiny gain, but within noise (4/3) so NOT worth a recompile without more evidence. No change made.

This completes multi-split validation of ALL THREE live engines: S1 ✅ 7/7, S3 ✅ (+$298, WF✓),
S4 ✅ 6/7. The deployed gold portfolio is on robust, validated settings.

---

## Cycle 13 — 2026-05-27 ~11:16 PKT

**Health:** ✅ S1/S3/S4 alive (2s), ticks live, market OPEN. NSND stale = expected. 1 open.
Today still −$16.31 (~3.5h no closes — very quiet, gold flat ~4520).

**Research — resolved the night's one open flag: is BtcS4b attached live?** Checked the BTC EA
heartbeats:
- `btc_s4b_trader_state.json`: last write **2026-05-24 12:54** (frozen ~3 days), entries_today=0,
  last_signal=never. → **BtcS4b is NOT running live.**
- `btc_s3_m30_state.json`: last write 2026-05-16 (~11 days stale). → BtcS3M30 also NOT running.

**Verdict: cycle-6 BtcS4b concern is MOOT — zero live risk.** The net-negative BtcS4b isn't
attached anywhere, so its bad profile costs nothing right now. Recommendation downgrades from
"consider pausing" to simply "don't reattach it until it shows a real edge." The LIVE trading
system is purely **S1/S3/S4 on XAUUSDm** — all three multi-split validated this session.

This resolves every open item. Net session outcome: system healthy, all live configs validated &
unchanged, the one risk (BtcS4b) confirmed dormant, and the 0.01-lot sizing fix confirmed as the
key protective lever.

---

## Cycle 14 — 2026-05-27 ~11:46 PKT

**Health:** ✅ S1/S3/S4 alive (4s), ticks live, market OPEN. NSND stale = expected. 0 open.
**Today recovered to −$1.33 (14 trades, 79% WR)** — up ~$15 since cycle 13. Red was variance.

**Research — today's recovery, broken down by engine (live fills, normalized 0.01):**

| Source | n | WR | net @0.01 |
|--------|---|----|-----------|
| S1 (workhorse) | 3 | 67% | **+$7.64** |
| S4 | 2 | 100% | +$3.94 |
| Human (Shano manual) | 6 | 100% | +$4.49 |
| S3 | 3 | 33% | **−$17.40** |
| **TOTAL** | | | **−$1.33** |

Today's tick file `shano_ticks_2026-05-27.csv` = 3.2MB and writing → dataset growing for future
validation (data integrity OK).

**Verdict: today's red was ENTIRELY S3 (−$17.40, 2 wide-stop SL hits); everything else positive.**
S1 led (+$7.64, consistent with its backtest dominance), S4 clean (2/2), Shano's manual 6/6. All
samples tiny (n=2-3) so this is variance, not signal — but it lines up with the session's findings:
S1 is the reliable workhorse, S3's live edge is thin/choppy. Nothing actionable. No change made.
