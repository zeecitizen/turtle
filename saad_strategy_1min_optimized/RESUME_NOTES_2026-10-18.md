# RESUME NOTES - 2026-10-18 (read first after a context compaction)

## Zee's GOAL (his words): "work and keep working on the goal until you have a working EA on 1 min timeframe" - high win rate on BAD days too.
No more reports for their own sake. Test -> fix -> test in MT5 until a 1-min setup is profitable across the year (both halves, random delay).

## State of the code
- EA `mt5/Saad_strategy_1min.mq5` = **v1.39** (magic 88305). New since v1.36, all OFF by default:
  - v1.37 `InpHtfIdx` (0 off, 1=5m, 2=15m, 3=30m, 4=1h, 5=4h) + `InpOptScore` 5 = profit factor (0 if < InpOptMinTrades trades)
  - v1.38 `InpExitPreset` 0..8 (0 off, 1 normal, 2-5 fixed $1/2/3/5 close-all, 6/7 Fib 161.8/200 close-all, 8 partial half +$2 trail $2)
  - v1.39 `InpCostGateX` (skip if TP1 runway < X x live spread), `InpHardTp` (BUY sends TP1 to broker when share 1.0),
    `InpAdxPeriod`/`InpAdxMin`, `InpAtrMinUsd`/`InpAtrMaxUsd` (volatility band), `InpEntryMode` 3 = bar-open (candle CLOSE beyond break level).
  - **BUG to fix first**: InpEntryMode 3 gave 0 trades (setup probably expires after InpBreakBars=1 before the close-beyond check runs).
- Indicator `pine/saad_15min.pine`: Task 6 patch NOT yet applied: `monitor/strategy_lab/pending/pine_task6.py` (EXIT LAB panel bottom-left sorted
  + drawdown + vs-now, and `xPick` "EXIT · quick pick" input mapping = EA InpExitPreset). Apply ONLY after Task 3 finished; snapshot settings by
  POSITION first (server.tv_eval(server.JS_STUDY)), inject with `pine/inject_pine.py pine/saad_15min.pine --force` (open editor first:
  server.tv('pine','open','Saad Strategy v3.20')), restore settings by name, add `"xPick": ("InpExitPreset", {...})` to server.py CHOICES.
- Task 3 (`monitor/saad_compare/task3_chart_effects.py`) was running on the TV chart (do not touch chart while it runs); when done run
  `task3_report.py` -> optimizer_results/TASK3_setting_effects.md.
- Task 7 self-tuner built, not run: `monitor/strategy_lab/saad15_selftune.py` (beam search over setting tree, successive halving across 4 folds,
  ensemble vote, hold-out Sep-Oct; uses rigs axi2-7).
- Queue `saad_tasks_queue.py` (task1/task7/task5/task2) was STOPPED during Task 1 stage A (to prioritise the defended 1-min search).
- Task 4 DONE: optimizer_results/TASK4_why_october_works.md (Oct quietest month: 1-min candle $1.62 vs $4.09 Mar; fixed-$ settings fit only October;
  Feb/Mar 70% of losers stopped within 5 min).

## Results so far (MT5, XAUUSD_BB M1, Jan 1-Oct 16, random delay, $100k, 2 lots)
- Zee's current 1-min chart settings: PF 0.83-0.87, all months but Jan/Oct red.
- 40-setup menu (stop x target x EMA): best PF 0.95 (4-pip stop + Fib 300 + EMA 8/8). Pre-heat / daily selection / adaptive ranges / re-entry: no edge.
- Defenses smoke test: A = EMA 8/13, break 1, ATR stop 2.5, Fib 200 close-all + hard TP, cost gate 3x, ADX 20, session 10-20 server:
  PF 0.92, WR 67.5%, account blown by March. ADX 20 skipped 8,061 setups. C (Fib 300): PF 0.86.
- 15-min v1.30 (defaults) remains the only robust profitable setup: +$110k/yr, WR 82%, every half green.

## NEXT STEPS
1. DONE: InpEntryMode 3 fixed (commit). Smoke B Jan-Mar: PF 0.85, 2,222 trades.
2. RUNNING (relaunched after the PC restart 2026-10-18; the first run was killed by Windows updates): `py monitor/strategy_lab/saad_m1_defended_search.py` (read results with --read). ONE genetic optimizer (M1, learn Jan-Jun, forward Jul-Oct, InpOptScore 5, min 250 trades) over: EMAs, BreakPips 0-4, EntryMode 0-3,
   SlMode/SlAtrMult/SlPips, MaxRisk, TpMode 1-2 + InpTpFixUsd + Fib, PartialPct, HardTp, BeTpPct, CostGateX 0-6, AdxMin 0-35, AtrMin/Max,
   SessFrom/To, ChopEr, HtfIdx/HtfEma. Base = saad_tasks_base_m1.json with all range boxes ON, pause 0, cooldown 0, re-entry off.
3. Validate winners: full year + halves, random delay, per-month and per-day green ratio; iterate.
4. DONE: Task 6 Pine applied + injected (Exit Lab panel + xPick), Task 3 md written. LEFT: Task 5 sweeps on the winner, Task 7 self-tuner. Commit each EA version with VERSION.md + VERSION_HISTORY.md rows.
- One optimizer at a time (8 agents fill the 15.6 GB RAM). Compile tests on rig axi2.

## 2026-10-18 late evening (11 PM PKT) — M1 search verdict, then the shift to 5 min
- M1 defended search STOPPED for the forward check (`m1def_forward_check.py`): top 150 Jan-Jun passes run on Jul-Oct in MT5 ->
  5 of 150 profitable, PF 1.01-1.05, WR ~20%. Jan-Jun winners do not hold on Jul-Oct on 1 min.
- Driver test V1 (session 16-18 server, sweep entry, chop 0.3, ATR >= $2, break 3, ADX 30, Fib 200, cost gate 3, HTF 1 h / EMA 70,
  ATR stop 2, EMA 10/20, BE 0.75, max risk 10, partial 0.75, hard TP) on M1: Jan-Jun +$30,096 PF 2.09 WR 33.6% | Jul-Oct -$4,956 PF 0.77.
- Zee: "ok let's shift our focus to 5 min time frame". Chart = BLUEBERRY:XAUUSD 5 min, indicator set to the V1 values it HAS
  (`monitor/strategy_lab/pending/pine_set_v1.py`; snapshot before = `monitor/strategy_lab/saad_snapshot_2026-10-18_m5_before_v1.json`).
  NOT in the indicator / not passed by the page: session hours, sweep entry, cost gate, ADX, ATR band, hard TP (EA-only).
- MT5 M5, full year, random delay, $100k (rig axi):
  - V1 full (`saad_v1_m5.py`): +$498, PF 1.04, WR 19.5%, 41 trades; Jan-Jun +$2,826, Jul-Oct -$2,328. Trade count is limited by chop 0.3
    (1,671 skips) + the 2-hour session, not the $10 risk cap (2 skips).
  - V1 without the six EA-only gates (= the page's 10-month view): -$18,517, 1,016 trades; Jan-Jun +$8,201, Jul-Oct -$26,718.
  - v1.30 defaults (Zee's 15-min setup, `saad_v130_m5.py`): -$57,902, PF 0.94, WR 75.4%, 3,220 trades, DD 85%; Jan-Jun +$13.5k, Jul-Oct -$71.4k.
- Compare page fix: `year_runner.py` ran the 10-month view on M1 ALWAYS; it now uses the chart's timeframe (`__period` in the batch,
  stripped before MT5; shown in the page's heading).
- RUNNING (started 11:11 PM PKT): `py monitor/strategy_lab/saad_m5_defended_search.py` (read with --read) = the M1 defended search on M5,
  base saad_opt_base_sets_m5def.json (= m1def base), min 120 trades Jan-Jun, wider $ ranges for M5. Forward results come from MT5 itself.
  NEXT: read top by FORWARD PF; validate the best on the full year + halves with random delay; if one holds, ship as EA defaults (new version).

## 2026-10-19 ~1:15 AM PKT — 15-min optimizer running, chart on its best-so-far pass
- Self-tuner (Task 7) DONE: v1.23 defaults beat every tuned set on the Sep 1-Oct 16 hold-out (+$8.8k vs -$18.6k / -$15.6k). Keep v1.23 settings.
- Saad_strategy_15min v1.24 shipped (ATR band, ADX, OnTester; off by default; identical trades to v1.23).
- RUNNING: `chain_after_selftune.py` -> `saad15_driver_search.py` (MT5 genetic, M15, Jan-Jun learn / Jul-Oct forward, PF score, min 80 trades,
  rig axi, started 00:33:53), THEN `saad_m5_defended_search.py`, then the page's auto re-run back on. Peek: `py monitor/strategy_lab/opt_peek.py`.
- Indicator: new EA FILTERS inputs fSessFrom/fSessTo (broker hours, NY+7), fAdxMin (MT5 ADX formula), fAtrMin/fAtrMax; server.py DIRECT maps them,
  but the RUNNING page server still has the old map -> restart it (`taskkill` server.py; ensure_up restarts) only AFTER the chain is done
  (a restart sets auto = True and starts 6 rigs).
- Chart (15 min) now = EA v1.24 defaults + best-so-far pass PF 2.11 (pending/pass_211.json), lots kept 2. Zee's settings before:
  monitor/strategy_lab/saad_snapshot_2026-10-19_0111_before_pass.json. Chart shows Aug* +$52.3k PF 2.82 / Sep -$17.3k PF 0.70 / Oct +$4.5k PF 1.19.

## 2026-10-19 ~3:45 AM PKT — 15-min optimizer verdict (after the PC restart killed it at 15%)
- `s15_forward_check.py`: top 30 Jan-Jun passes (from the agents' logs, opt_peek.py) run on Jul 1-Oct 16 in MT5, random delay, 1 lot.
  Plain v1.23: **+$35,059, PF 1.20, 425 trades** (Oct -1.2k). Optimizer passes: 12 of 30 profitable, **0 of 30 beat v1.23's net**.
  Best Jan-Jun PF 2.40 -> Jul-Oct PF 0.97; 2.33 -> 1.08; 2.21 -> 0.79 (the afternoon + sweep + 1 h trend recipe fails out of sample, as on 1 min).
  Best Jul-Oct PF: 1.40 (+$24.4k, 160 tr: EMA 5/40, ATR stop 1x, chop 0.28, ADX 35, ATR $1-12, server 2-18). All 4 months green: EMA 13/70,
  break 3, SL 25 pips, chop 0.08, server 0-18, ATR $1-8, no ADX: +$20.5-23.5k, PF 1.17-1.19, ~318 tr.
- => keep v1.23 settings in the EA. Next lever = the EXIT (indicator TP1 methods 'Next EMA beyond the entry' / 'close back across the slow EMA'
  are chart-only; port to the EA as v1.25 and MT5-test) - Zee has not answered that offer yet.
- Indicator since the last notes: weekday table (left of Last 30 days), range table + EXIT LAB = whole chart, Trading session dropdown,
  the two chart-only TP1 methods. Page server restarted with the PC -> has the new session/ADX/ATR mapping.
