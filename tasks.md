# tasks.md — Zee's assigned tasks, numbered & tracked

Per Rule #10 (startup.bat). Append-only. Numbers are global across sessions.
A task is OPEN until Zee explicitly says it's complete.

| # | Status |
|---|---|
| (the rest is event log) | |


## TASK-001  opened 2026-06-04 00:30 PKT — Get live EA on Atmos producing real-money positive day (Rule #3 north star)

## TASK-002  opened 2026-06-04 00:30 PKT — Verify chat.claudezeeshan.com subdomain serves /chat-app over HTTPS

## TASK-003  opened 2026-06-04 00:30 PKT — Always display times to Zee in Pakistan Time (PKT) per Rule #9
- 2026-06-04 00:31 PKT — DNS CNAME added via cloudflared route, tunnel ingress updated, cert provisioned, HTTPS 200 verified from machine. Awaiting Zee's phone test.
- 2026-06-04 00:33 PKT — Rule #9 implemented in memory_hawk.py — entry headers now show PKT primary, UTC secondary. Latest hourly entry confirms: '## 2026-06-04 00:32 PKT (2026-06-03 19:32 UTC)'. All new chat messages to Zee also use PKT. Old entries left untouched (append-only).
- 2026-06-04 00:33 PKT — Infrastructure round done. EA paused on Atmos at -224.82 day P&L. Validated Python predicts +253 at 0.05 lots on June 3 ticks. Next test = tomorrow's Session1 at 06:30 PKT. Daemons all alive: dd_watch will alert on any fill within seconds.

## TASK-004  opened 2026-06-04 00:34 PKT — Daily 06:25 PKT pre-Session1 brief — morning_brief_hawk daemon

## TASK-005  opened 2026-06-04 00:43 PKT — Dry-run live EA against 27-day tick history — port Feb11TickMedium.mq5 logic to Python EXACTLY, run on same ticks as canonical detector, compare BOTH against turtle_fills.csv. If MQL5-port == Python canonical, divergence is broker. If not, MQL5 has logic bugs.
- 2026-06-04 00:45 PKT — Built diagnose_live_vs_python.py — per-day breakdown comparing Python signals vs live broker fills (in-window vs out-window classification). Running now.
- 2026-06-04 01:03 PKT — DIAGNOSTIC OUTPUT — 27 days analysed.

FINDING #1: 2796 of 2994 live fills (93%) fired OUTSIDE the validated UTC session window 01:30-02:30 + 16:45-19:45. Cost: -$5,741 of the -$5,917 27-day live loss = 97% of the loss is purely the session-timezone bug (FTMO GMT+3 calibration deployed on Atmos GMT+0). v1.18 recompile fixes this for tomorrow.

FINDING #2: Even INSIDE the validated window, live fired only 35 of 2619 Python-detected opportunities (1.3% match rate). Possibilities:
 - EA wasn't attached most of those windows (Atmos NOVA started 2026-06-02, EA newly attached, heartbeat staleness observed)
 - MQL5 ComputeRanges / M5TrendDir produce different filter values than Python tick-built bars
 - Broker spreads differ from CSV mid-derived spreads
 - EA throttle (check_every) sees different tick stream

FINDING #3: On the Atmos-era 3 days only (Jun 1-3): 71 live fills, -$130. 65 of 71 out-of-window. 6 in-window netted +$1. Python expects 302 in-window fires over those 3 days = ~$2k at 0.05L expected vs -$130 actual.

NEXT: deepen FINDING #2 by porting MQL5 logic to Python (full mirror). Compare on Feb 11 (where Python = +$14,774 / 172 fires).
- 2026-06-04 01:06 PKT — TASK-005 ROOT-CAUSE FOUND.

Built dry_run_mql5_mirror.py — exact port of Feb11TickMedium.mq5 OnTick loop with one-position-at-a-time constraint.

DIFFERENCE FROM CANONICAL PYTHON: canonical zee_tick_detector_OOS.py / MEDIUM.py iterates k forward every CHECK_EVERY ticks INDEPENDENTLY of any open position. It allows OVERLAPPING parallel trades. Real EA can only hold one position. When this constraint is enforced:

  MQL5-mirror 27-day total: +$312.35 at 0.05L = ~$11.50/day
  Canonical Python claim:   +$83,846 at 0.05L (unrealistic — 268x inflated by parallel trades)

ADDITIONAL FINDING: At 0.05 lots, broker SL/TP parachute ($25/$50 USD) becomes TIGHTER than EA's internal SKIM/MAX_LOSS ($50 each). EVERY exit fires as BROKER_SL or BROKER_TP. EA's internal exit logic never runs. Effective trade R:R = 1:2 (capped $25 loss vs $50 win).

TRUE expected: live EA should produce ~$11/day at 0.05 lots, not the $3k/day Python claimed. Wall of shame retraction needed.

Realistic path to Rule #3 north star: scale lots (0.05 -> 0.10 doubles to ~$22/day; 0.20 = $44/day) PROVIDED tomorrow's Session1 confirms live matches mirror.

## TASK-006  opened 2026-06-04 01:19 PKT — Parallel-trade EA per Zee's hedging insight: rewrite Feb11TickMedium.mq5 to allow stacking positions (Path B from Zee 2026-06-04). Backtest Python with realistic max-concurrent cap (5/10/20 simultaneous) before committing EA changes — per validate-profitability-not-capture rule.

## TASK-007  opened 2026-06-04 01:19 PKT — Gemini Deep Research connector: install gemini-research-mcp OR build CLI skill so Claude can autonomously dispatch deep research jobs + collect results overnight. Per Zee 2026-06-04 — currently he submits manually, automate it.
- 2026-06-04 01:19 PKT — Zee diagnosed the Python parallel-trade issue independently and identified Path B (rewrite EA to support stacking in Hedging mode). Spinning that out as TASK-006 since it's a separate decision/implementation. TASK-005 specifically about the mirror diagnostic is now near-done — opened TASK-006 + 007 for the next moves.

## TASK-008  opened 2026-06-04 01:29 PKT — Status dashboard at claudezeeshan.com root — task list + 'Ask Claude for status' button
- 2026-06-04 01:29 PKT — PARALLEL-CAP RESULTS:
  max_par=1 (current): -64 USD / 27d (-2.37/day)
  max_par=2:           +34 USD / 27d (+1.27/day)
  max_par=3-20:        all NEGATIVE (-213 to -1867)
  max_par=infinite:    +15,886 USD / 27d (peak concurrent = 233)

Even 2-trade stacking is marginally break-even, not the magic-bullet the canonical's infinite parallel suggested. The 248 difference between AGGR config and MEDIUM config canonical may come from DD circuit + loss-streak interactions.

Best broker SL/TP grid: SL=25 USD, TP=75 USD = +378 USD / 27d = +14 USD/day at 0.05L (with current MEDIUM EA).

NEXT lever to test: lot sizing (0.05 -> 0.10 doubles to ~28/day at SL=25 TP=75).
- 2026-06-04 01:36 PKT — Status dashboard SHIPPED at claudezeeshan.com root + /status. Lists all open/closed tasks with expand-on-click for event history. EA snapshot card (broker truth: day P&L, W/L, WR, heartbeat). Gold 'Ask Claude for status' button → chat.claudezeeshan.com/chat-app. Auto-refresh 30s + on visibility change.

## TASK-009  opened 2026-06-04 01:36 PKT — Visualizer: highlight MQL5-mirror trade candles on feb11-lab (Zee 2026-06-04). Gold ★ entry + green/red circle exit markers. Toggle in Layers panel. Live now.
- 2026-06-04 01:36 PKT — Generated feb11_mirror_signals.json (16 trades, +$46.80 at 0.05L Feb 11). build_feb11_lab.py extended with new MIRROR layer + toggle + fetch. Page hard-refresh on phone to see new gold stars on the right candles.
- 2026-06-04 01:44 PKT — TIME-TO-TARGET PROJECTION (Atmos NOVA = +$500 target):
At MQL5-mirror baseline ~$11.50/day at 0.05 lots:
  Lots 0.05 → 43 days to +$500 (way past Atmos challenge cutoff)
  Lots 0.10 → 22 days
  Lots 0.20 → 11 days
  Lots 0.30 → 7 days ← clears 8-day phase
  Lots 0.50 → 4 days

Implication: to clear Atmos NOVA target on realistic backtest expectations, lot size needs to be ~0.20-0.30. Zee currently at 0.05 (his explicit cap). Need his OK to scale.

Alternative: find a filter combo that produces >$14/day at 0.05L.
- 2026-06-04 01:47 PKT — Setup recipe written to monitor/gemini_dr_setup.md. uv (Astral pkg mgr) installed. google-generativeai SDK available. AWAITING: Zee to generate GEMINI_API_KEY at https://aistudio.google.com/app/apikey and drop to monitor/.gemini_api_key. Then either uvx gemini-research-mcp (community pkg) OR custom FastMCP wrapper using Interactions API. Stays OPEN per Rule 10 until first deep research round-trip completes.
- 2026-06-04 01:50 PKT — PEAK PARALLEL COUNT: canonical Python with no parallel cap hit peak_concurrent = 233 simultaneous trades across the 27-day backtest. At 0.05 lots each = 11.65 total XAUUSD lots exposure = $11.6k to $58k margin required on a $10k account. UNATTAINABLE on any broker (margin reject + position cap of 100-200 typical). The +$15,886/27d at max_par=∞ is a mirage. Even capped at 20 (broker-feasible), the backtest produces NEGATIVE results due to clustered-reversal floating-DD (your Path A floating-DD insight). One-position-at-a-time is the only realistically deployable mode.
- 2026-06-04 02:00 PKT — GEMINI'S 5-METRIC VERDICT (realistic state-machine AGGRESSIVE, no broker parachute):
  Trade count:    196 / 27d = 7.3/day  ⚠ (Gemini expected 10-40)
  Win Rate:       48.5%                 ✗ (Gemini: 62%+ profitable)
  Profit Factor:  0.99                  ✗ (Gemini: ≤1.0 = edge was fake)
  Avg hold:       1340s = 22 min        ✓ realistic
  Max DD:         $665.65              ✓ within Atmos $800 limit
  TOTAL:          -$45.66/27d = -$1.69/day at 0.05L

PROFIT FACTOR 0.99 = NO REAL EDGE. The +$477k AGGRESSIVE claim was entirely chronological-leak. The MQL5-mirror's +$312/27d came from the BROKER SL=$25 cap doing the work of cutting losses tighter than EA's internal CB=$50. Without that parachute, AGGRESSIVE is break-even at best.

IMPLICATIONS for Atmos NOVA goal:
  - The +500 USD target on a 10k account is harder than we thought
  - Current EA needs FILTER refinement (not just lot scaling) to get PF > 1.25
  - Lot scaling on PF 0.99 strategy just amplifies losses
  - REAL next step: search for filter combinations with PF >= 1.25 in state-machine backtest

Saved zee_tick_detector_realistic.py — the canonical 'no future-peek' version for future verification.
- 2026-06-04 02:03 PKT — MEDIUM under state-machine: PF=0.93 (WORSE than AGGRESSIVE 0.99). -$295/27d (-$10.96/day).

SUMMARY of all variants:
                            Trades  WR     PF    $/day(0.05L)
  AGGRESSIVE state-machine    196   48.5%  0.99   -$1.69    (no edge)
  MEDIUM     state-machine    197   45.7%  0.93   -$10.96   (worse)
  AGGRESSIVE mirror (w/ SL=25) 254  39.0%  1.20   +$11.50   (broker SL = strategy)
  MEDIUM     mirror (w/ SL=25) 254  39.0%  1.20   +$14.02   (best, but broker-dependent)
  Canonical Python (parallel)  N/A  94%    inflated +$3,100/day (mirage)

FINAL INSIGHT: The broker-side SL=$25 is the ACTUAL strategy. The EA's rng60+M5 filter picks entry timing but the broker's 1:2 R:R parachute (loss $25 / win $50) is what creates positive expectancy. Without the broker tightening losses, the EA filter is break-even.

WHAT THIS MEANS FOR TOMORROW'S SESSION1:
  - Live EA with v1.18 GMT+0 sessions + broker SL=$25 SHOULD produce ~$0-$15/day
  - At 0.05 lots this is a SLOW path to $500 (33-43 days)
  - Filter changes won't help (state-machine shows no real edge)
  - Broker SL tightening (e.g. $20 or $15) might INCREASE expectancy IF win rate stays
  - Need to find a NEW strategy, not tune existing filters, for >$30/day at 0.05L

This is the final TASK-005 verdict. Waiting on Zee close 005.
