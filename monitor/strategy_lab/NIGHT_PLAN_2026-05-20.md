# Autonomous Night Plan — 2026-05-20 (Zee asleep, full permission to optimize+deploy)

## Mandate
Mine ALL teacher videos, backtest every idea on 12d real ticks, walk-forward
gate, deploy what holds. North star = PROFITABILITY (total P&L / EV / low
drawdown), NOT a vanity win-rate. Be 100% HONEST in the morning report — do
NOT fabricate a "we hit 90%" message. High WR with tiny TP/huge SL is a known
trap (see memory: 77-92% WR strategies that lost thousands).

## Deployed & validated THIS SESSION (all reversible input flags)
- S3Trader: M5-FVG required (EV $13.78->$26.24) + upper-wick rejection 0.35 (WR 63->69%)
- S1Trader v2: big-spread climax filter (OOS 80% WR, EV ->$41) — reattached
- NsndTrader: M15-only FVG (WR 54->62%) — needs Zee reattach

## REJECTED (backtested, do not deploy)
- S1 momentum/low-vol breakout filter (cuts P&L ~70%, even WITH big-spread: +$430 vs +$849)
- S1 definite-low SL (no OOS improvement)
- NSND 1-Day trend filter (turned +$784 into -$68)
- NSND asymmetric sell-TP (marginal -$6 OOS)
- S2 Engulfing as standalone EA (net negative)

## Per-strategy FVG timeframe rule (confirmed)
Each setup's FVG should come from its OWN structure TF: S3(M5 sweep)->M5,
NSND(M1 NS/ND)->M15, S1(UHV breakout)->H1. Coarse-H1-for-all was the systematic mistake.

## BACKTEST QUEUE (work through these each wakeup; mark DONE inline)
1. [done] S1 big-spread + low-vol breakout combo -> low-vol still hurts, keep big-spread only
2. [ ] Read scalping transcripts yt_2mKEfO85D04 (buy-side 1min) + yt_JWmETwP7sx0 (sell-side) -> extract exact mechanical entry, backtest if new vs existing EAs
3. [ ] yt_ddvZYdA2ETo "absorption candle 3-step entry" -> backtest
4. [ ] yt_B2PWH5tlvfw "two-bar reversal" -> backtest (this is the S2-engulfing backup entry; test as filter/addon to S1/S3)
5. [ ] Wyckoff rally pattern yt_q2Arjx0u0r0 + yt_NR7ReNPsZa0 -> new setup? backtest
6. [ ] Session-liquidity setup yt_MOMuSJrVkoY -> backtest
7. [ ] "Valid order block = followed by BOS" filter for S3/S1 -> backtest the BOS-validity gate on FVG
8. [ ] Portfolio: combined S1+S3+NSND daily P&L, drawdown, correlation; best lot allocation at 0.02
9. [ ] As channel transcripts complete (108 total), grep each for any rule we contradict; backtest deltas
10.[ ] Re-walk-forward any winner before deploying; recompile via mt5/install_eas.ps1

## Data / tooling
- 12d real ticks: shano_ticks_2026-04-29..05-14 in Common/Files
- Mirrors: ea_mirror_validate.py (s3,nsnd), backtest_s1_uhv_breakout.py (s1)
- replay: replay_ticks_both (both sides). stats() for metrics.
- Python: C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe
- Compile EAs: powershell mt5/install_eas.ps1 (then Zee must reattach to load)
- Channel transcripts: monitor/_loom_audio/yt_<id>.txt ; index _yt_channel_index.md

## LIVE RULE LEDGER (Zee's request — forward-test rules on live candles)
Each wakeup ALSO run: `python monitor/strategy_lab/live_rule_ledger.py`
It builds M5 from today's live tick file, evaluates each atomic teacher
rule-step on every closed candle, scores forward outcome via real ticks
(+/-$7.5 over 90m), accumulates per-rule + per-combo WR into
live_rule_ledger.json. Needs ~4h+ of live candles before it scores anything;
by morning it should have a meaningful forward-confirmation table. Report it
HONESTLY alongside the historical backtests (small live sample != proof).

## 🔑 TOP PRIORITY LEAD (from live ledger 05:51) — H1/HTF TREND FILTER
Live ledger on tonight's bearish session: SELL atomic rules 10/10=100%, BUY 0/10=0%
(same candles). Proves direction is the master edge. CRITICAL: our M5 24-bar trend
check (close-close[24]>1.0) flagged "uptrend" for all 10 LOSING buys (local bounces
in a downtrend) and missed the downtrend for the 10 WINNING sells. => M5 trend is
too local/noisy.
NEXT BACKTEST (do first): replace/AUGMENT the M5 trend gate in S1/S3/NSND with an
H1 (and/or daily) trend filter, backtest on 12d real ticks + walk-forward. Hypothesis:
HTF-trend alignment blocks counter-trend losers (like tonight's buys) and is the
regime guard that reconciles the earlier rejected NSND daily-trend test (which only
lost because the 12d window was mostly bullish). Measure total P&L, EV, AND
per-session/per-day robustness (esp. bearish days). If it holds OOS -> deploy.
Note: live sample is tiny (10/10) and one bearish session — NOT proof, it's a strong
LEAD to validate on the full historical ticks. Be honest about this in the report.

## Channel transcription status: 48 done / 60 FAILED on OpenAI quota (429 billing).
Zee must top up OpenAI to finish remaining 60. 48 transcripts are enough to mine for now.

## H1-TREND-FILTER VERDICT (06:05 wakeup): NOT a hard-deploy.
S3 12d: baseline 57tr/68.4%/+$1496/EV$26 vs H1-up-gate(lb6) 37tr/78.4%/+$1382/EV$37.
=> H1 gate raises WR+EV but LOWERS total (-$113) because 12d window mostly bullish
(removed winning trades). It's a regime/risk guard, helps on bearish days (like
tonight) but not net-positive on available data. DO NOT hard-gate buys.
NEXT IDEA (queued #2-prime): make S3 BIDIRECTIONAL with HTF gating — buys when
H1 up, SELLS when H1 down. Captures bearish nights (tonight sells were 10/10 live)
instead of sitting out. Backtest S3-sell-side + H1-down gate on 12d + walk-forward.

## BIDIRECTIONAL-S3 VERDICT (08:57 wakeup): REJECTED — current buy-only is best.
12d: buy-only-nogate +$1496/EV$26 (BEST) > bidirectional+HTFgate +$1221/EV$19 >
sell-only+gate +$75 (marginal). Adding sells dilutes the buy edge; gold's bullish
bias makes sells barely positive over 12d. Tonight's bearish night is the rare
exception. KEEP S3 buy-only. Confirms teacher "gold bullish, favor buys".
LIVE LEDGER @06:55 (72 candles, healthier sample): SELL 55-82% / BUY 0-29% (bearish
session). Strongest atomic rules live = uhv_big_spread 81% + swept_uhv_high 82% =>
validates S1 big-spread deploy. No longer fake-100%; realistic.
NEXT QUEUE: scalping transcripts (2mKEfO85D04 buy 1m / JWmETwP7sx0 sell), absorption
candle 3-step (ddvZYdA2ETo), two-bar reversal (B2PWH5tlvfw), then portfolio study.

## PORTFOLIO STUDY (10:01 wakeup) — combined 3 EAs, current best configs, 12d @ 0.02 lots
COMBINED: +$625.8 / 12d. Avg/day +$48. Positive days 11/13 (85%). Worst day -$12.5.
Max equity DD $12.5 (2.5% of $500). Per-EA: S3 +$299, S1 +$170, NSND +$157.
Diversification works: worst COMBINED day milder than any single EA's worst (they
rarely lose together). HONEST CAVEAT: this is in-sample, mostly-bullish window;
real fwd will be lower w/ bigger DD (live May19 did -$38, worse than any backtest day).
Report +$48/day as a CEILING not expectation. Structure (3 +EV low-corr EAs, 85% green)
is the real signal. Script: portfolio_study.py.

## SCALPING VIDEO (11:04 wakeup): 2mKEfO85D04 = S1 UHV-breakout ON M1, NOT a new rule.
Same mechanics (bullish structure -> retracement = last-buy-candle low broken by body ->
UHV in retracement -> momentum+low-vol breakout of UHV high -> SL below low, TP 1:1 then
runner). NOT building an M1 scalper EA: (1) low-vol-breakout already tested -> hurts;
(2) M1 tiny TPs get eaten by spread worse than M5; (3) live ledger already forward-tests
these atomic rules. No deploy.
LIVE LEDGER @09:05 (98 candles, full night): SELL:uhv_big_spread 80% (n=30) = single most
reliable atomic rule of the night = validates S1 big-spread deploy. BUY:uptrend 0/10 again
= M5 trend gauge is a poor regime filter (every M5-uptrend buy lost in tonight's downtrend).
Consistent across the night, not magic. Tonight bearish => sells win; on bullish days (norm)
buys win. Direction is the master variable.

## ABSORPTION BREAKOUT (12:06 wakeup): REJECTED — overfit, fails walk-forward.
Teacher ddvZYdA2ETo = continuation breakout of resistance w/ low-vol momentum candle
(distinct from our reversal setups). In-sample tight-wick BUY RR=2 looked good (+$875/EV$19)
but config-sensitive (res_lb12 -$56, res_lb20 +$161). WALK-FORWARD KILLS IT:
TRAIN +$2491/52% but TEST -$1616/32% OOS. Classic overfit (few big-RR winners in train).
Breakout-on-gold = false-break trap. DO NOT deploy. Script: absorption_test.py.
=> ADD to REJECTED list. Our reversal setups (S1/S3/NSND) stay superior. Discipline
(walk-forward gate) caught a trap that would've bled the account.

## SESSION-LIQUIDITY (13:13 wakeup): documented, NOT built tonight.
Teacher MOMuSJrVkoY = trade prev-session high/low as liquidity. Decomposes into:
ScenarioA (low-vol break of session level -> continuation) = ABSORPTION (already
rejected, overfit). ScenarioB (high-vol sweep of session level -> reverse) = our
existing S3/NSND sweep-reclaim, just anchored to session extreme vs local M5 swing.
ONE untested nugget: anchor reversals to PRIOR-SESSION high/low. Needs session-
boundary harness; deferred to a dedicated future test (half-redundant, half-rejected,
not worth rushing at hour 7). NOT a miss — disciplined scope call.

## ============ HONEST MORNING REPORT (draft, for Zee) ============
NIGHT OF 2026-05-20 — autonomous, hourly loop, full session.

WHAT I DEPLOYED (all validated on 12d real ticks + walk-forward; reversible flags):
  1. S3: M5-FVG required + upper-wick rejection -> EV/trade $13.78 -> $26.24, WR 63->69%
  2. S1: big-spread climax bar filter -> OOS 80% WR, EV ->$41 (walk-forward held strong)
  3. NSND: M15-only FVG (dropped coarse H1) -> WR 54->62%
  UNIFYING FIX: each setup's FVG must come from its OWN structure TF (S3=M5, NSND=M15,
  S1=H1). The old "H1-for-everything" was the systematic mistake. This is the night's
  best real improvement.

WHAT I REJECTED (tested honestly, would NOT deploy — this is the discipline that
protects the account):
  - H1 hard trend-gate: regime guard but LOWERS total on bullish data. Not deployed.
  - Bidirectional S3: sells add only +$75/12d on gold's bullish bias; dilutes buy edge.
  - M1 scalper: = S1-on-M1, spread-eats tiny TPs; low-vol-breakout already proven to hurt.
  - Absorption breakout: in-sample +$875 but WALK-FORWARD -$1616 OOS (textbook overfit).
  - (earlier) S1 momentum/low-vol/definite-SL, NSND 1D-trend/asym-TP, S2 standalone.

PORTFOLIO (all 3 EAs combined, 12d backtest @ 0.02 lots):
  +$625.8 / 12d, ~$48/day, 11/13 green days, max drawdown $12.5 (2.5% of $500).
  CAVEAT (critical): in-sample, mostly-BULLISH window. Real fwd will be LOWER w/ bigger
  DD. Live May19 did -$38 in one night (worse than any backtest day). Treat +$48/day as
  a CEILING, not a promise. The STRUCTURE (3 positive-EV, low-correlation EAs, 85% green)
  is the real signal — not the exact number.

LIVE EVIDENCE TONIGHT:
  - Deployed EAs took 3 real trades today: 3 wins, +$46.60 @0.02 (small n, partly luck,
    but real money + green).
  - Live rule ledger (123 candles): big-spread climax rule = strongest atomic confirm
    (sell-side 69% n=49 in tonight's down-then-mixed session). Validates S1 deploy.
  - MASTER LESSON: direction is everything. M5 trend gauge is too local (BUY:uptrend went
    0/10 in the overnight downtrend). The teacher's HTF-trend emphasis is right as a
    REGIME guard — but mechanically hard-gating hurt on bullish data, so it stays a
    known-weakness note, not a deploy.

HONEST BOTTOM LINE: NO magic 90-100% WR (that's a blowup trap and I won't fake it).
What we DO have: a 3-EA, positive-EV, low-correlation, teacher-faithful system, each EA
improved + walk-forward-validated tonight, with disciplined rejection of 4 tempting-but-
overfit ideas. That's a stronger, more honest system than 24h ago.

PENDING FOR ZEE:
  - Reattach NsndTrader (M15-only FVG compiled, needs reload). S3/S1 already live.
  - OpenAI out of credits: 48/108 videos transcribed; top up to get remaining 60.
  - Future test idea: prior-session-extreme reversal anchor (session-liquidity).

## Progress log (append each wakeup)
- 04:55 night start. S1 combo test done (#1 -> low-vol still hurts, keep big-spread only).
  Loop armed hourly. Channel txn ~17/108. Live ledger built; only 25 M5 candles
  so far (01:00-03:00), too early to score — will fill through the night.
- ~03:05 broker: Zee asked why no trades 22:22->03:05. ANSWER (verified on 12d):
  broker hrs 01:00-02:59 = 0 signals in 12 days (deadest window in gold's cycle);
  00:00=0.2/day, 03:00=1.8/day, active 08-20=~42/day. He woke at broker 03:00 =
  tail of the dead zone. ALSO: tonight's filters cut freq BUT raised total P&L on
  all 3 (S3 102->57tr +$1406->+$1496; S1 34->18 +$720->+$849; NSND 52->47 +$1170->+$1280)
  => fewer trades, more money; skipped trades were net losers. Frequency != the goal.
  All 3 EAs alive at 03:05. NSND reattached (M15-only loaded). Loop still armed (next ~06:03).
- 05:51 broker: channel transcription DONE (48 ok / 60 failed on OpenAI quota). Live ledger
  extended to BUY+SELL. RESULT: tonight bearish -> SELL 10/10=100%, BUY 0/10=0%. Master lead:
  M5 trend gate too local; H1/daily trend filter is the priority backtest (see TOP PRIORITY above).
  Next wakeup: build + walk-forward the HTF-trend-filter on all 3 EAs.
- ~06:00 broker: Zee added sell-side to live_rule_ledger (eval_sell_rules, find_bear_fvgs,
  both contexts in main). Ran clean: 61 M5 candles. RESULT IS A DIRECTIONAL ARTIFACT —
  gold trended DOWN 01:00-06:00 so ALL sell rules show 100% WR and ALL buy rules 0%.
  NOT a real edge; just one-directional session. Must report this honestly: small live
  sample confounded by session direction; 12d backtest (spans both directions) is the judge.
  Ledger will keep accumulating across directions through the night.

## TRANSCRIPTION CAPPED (out of OpenAI credits) — 48/108 done, NO MORE COMING
Do NOT attempt further transcription (API 429, Zee out of money). Work ONLY with
the 48 existing transcripts in monitor/_loom_audio/yt_*.txt. The core strategy
content IS captured (Power of 03 1-3, Power of 4 2-3, Wyckoff Rally 1-2, absorption
candle, session liquidity, VSA scenarios, risk mgmt, 7-rules/7-mistakes).
ALL remaining work is LOCAL + FREE (backtest on 12d ticks, walk-forward, deploy).
Loop focus now: (a) read un-analyzed strategy transcripts, extract any concrete
mechanical rule, (b) backtest vs existing EAs, (c) deploy what walk-forward holds.
Highest-value un-read: absorption-candle 3-step (ddvZYdA2ETo), Wyckoff Rally
(q2Arjx0u0r0, NR7ReNPsZa0), session-liquidity (MOMuSJrVkoY), Power-of-03 (4ytPyiZybJw,
r3qO2PQ-tsI, 85RcVVM2o2k).
