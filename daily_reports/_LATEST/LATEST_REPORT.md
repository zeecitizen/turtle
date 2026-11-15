# 9 November 2026 — "Twice an hour" study: the best configuration that trades 2+ times every weekday hour

Zee: *"i want you to study this strategy and find out the best possible configuration: 1. that has minimum losses -> has a high
winrate 2. it trades atleast twice every hour everyday ... in the end you'll say something like: ok, we can trade twice per hour
at a maximum winrate of X, and we'll have atleast Y losses per day which cannot be cut down further"*

**Every number here is a tester estimate** (Python UHV engine on PrimeXBT EUR/USD ticks, `sim.data("year1")`: 209 days with
data, 6 Mar – 4 Nov 2026 = 174 weekdays + 35 Sundays). Python generates the hypothesis; MT5 / live fills promote it. Nothing
here is promoted. Geometry frozen at the 12-09-37 family (SL beyond 22.5, RR 1, FixTp 0.1, instant entry, latency 0).

## Verdict
**ok, we can trade twice per hour at a maximum win rate of 98.46%, and we'll have at least 1 loss per weekday (179 losses on
174 weekdays) which cannot be cut down further** — with hour 21 UTC (the 5 pm New York rollover) as the one hour the market
itself cannot fill (even taking every setup it reaches 2 trades on only half the weekdays).

Saved as **`settings/saved/TWICE AN HOUR - 2+ trades every weekday hour, 98.46 pct (11656 trades).json`** (source
detector_lab over the ALL SETUPS base; result stored: 11,656 trades, net −$22,120, PF 0.44 at 1 lot).

| | trades | per weekday | per hour | losses | WR | net (tester, 1 lot) |
|---|---|---|---|---|---|---|
| ALL SETUPS (start) | 25,694 | 144.8 | 6.0 | 570 | 97.78% | −$88,388 |
| **TWICE AN HOUR (saved)** | **11,656** | **65.9** | **2.7** | **179** | **98.46%** | −$22,120 |
| if the rule is only a daily AVERAGE of 2/hour (48/day) | 8,579 | 49 | 2.0 avg | 107 | 98.75% | −$12,443 (hours 21–23 UTC nearly empty — breaks "every hour") |
| Zee's 100% save (976) for scale | 976 | 5.6 | 0.2 | 0 | 100% | +$1,534 (trades 07–20 UTC only) |

The changes from ALL SETUPS (10 inputs): `InpUhvNoClose 1` (no entries 16:45–17:45 NY), `InpUhvMaxTrigSpread 0.7`,
`InpUhvMinTicks 10`, `InpUhvSpikeAtr 4`, `InpUhvMaxFlips60 0.5` with `InpUhvFlipsBars 30`, `InpUhvMinSpanAtr 1`,
`InpUhvWickFake 1`, `InpUhvWall 2`, `InpMaxPos 2` (two positions at once instead of every setup).

## How "2 trades every hour" was measured
Weekdays only (Sunday has 3 hours of data). For every UTC hour-of-day the weekday total must be ≥ 2 × 174 = 348 trades, i.e.
an average of two per hour in EVERY hour, except hour 21 UTC which is excluded as unreachable (320 weekday trades even with
every setup taken). The saved setting's hours: 349–589 trades each (hour 22 UTC = 349, the binding one; hour 21 = 15).
"cov2" = share of weekday-hours that actually had ≥ 2 trades: 95% at ALL SETUPS, 67% at the saved setting (the average is
2.7/hour but the trades cluster).

## Where the losses live (ALL SETUPS, by UTC hour)
Hours 09–15 lose 1.0–1.7%; 19–20 lose 3–4%; **hour 21 loses 11%** and 22 loses 3.9%; Asia 03–07 loses 2.1–2.6%. Keeping
every hour alive means keeping the Asian and post-rollover losses — that is why the strict rule caps at ~98.5% while the
07–20 UTC settings reach 99.4–100%.

## The searches (all full-engine, 4-worker pool, scratchpad `hourly/greedy.py`, `swap.py`)
Greedy from ALL SETUPS: every round tries every tightening of every engine input (190–225 candidates: every Detector Lab
grid value, every loss filter, sessions that don't delete hours, risk manager, zones, Saad switches, positions) and accepts
only rows that keep every hour ≥ 348.
- precision-first pick (most losses removed per trade removed): 29 cuts → 15,050 / 239 / 98.41%, stopped at the floor.
- most-losses-first pick: 6 cuts → 10,149 / 226 / 97.77% (worse — big blunt cuts spend the frequency budget).
- max-win-rate pick: 10 cuts → 11,399 / 177 / 98.45%; a continuation found nothing feasible.
- swap search from that point (loosen one applied filter back, tighten any other: 2,018 runs): best 11,656 / 179 / 98.46%
  (MaxAtrPips back off, MinTicks 10) = the saved setting. Gains of 0.01–0.02 points are noise: **the frontier is flat at
  ~98.45% between 11,000 and 15,000 trades under the every-hour rule.**
- daily-average floor (48/weekday, hours free): 42 cuts → 8,579 / 107 / 98.75%, hours 21–23 UTC at 36–70 trades total.

## Caveats
In-sample on the same 209 days. Net is negative at every setting above ~2,000 trades (loss:win geometry ≈ 11:1, see
`project_frequency_frontier`): win rate alone hides it, so the saved setting is a frequency/WR answer, not a P&L answer.
MT5 Strategy Tester (random delay) is the promotion step before anything touches money.

## MT5 Strategy Tester on the saved winner (evening, Zee: "can you run mt5 tester on it")
EA `ZeeUHV_TurtleTV` **v1.03** (the save's 8 loss filters + `InpMaxPos` ported from the engine; defaults = the save), rig `C:\mt5_rig_pxbt`,
PrimeXBT EURUSDp **100% real ticks**, 6 Mar-5 Nov 2026, random delay, $100k, 1 lot. Two EA bugs fixed on the way (a rejected Friday close
dropped the round and orphaned the position; a position appearing after the delayed order read as closed).

| | trades | full stops | WR | net |
|---|---|---|---|---|
| Turtle TV tester | 11,656 | 179 (1.54%) | 98.46% | -$22,120 |
| **MT5 run 3 (clean)** | **11,244** | **179 (1.6%)** | **81.5%** ($0 exits as wins) / **68.5%** strict | **-$21,556**, PF 0.56, DD $22k |

Exits in MT5: 179 full stops (-$42.6k), 26 mid losses, 1,875 small losses (16.7%, -$5.2k), 1,458 at $0 (13.0%), 4,238 wins of $0-2,
3,467 wins over $2 (+$27.3k). **The entries, filters and structural loss rate match the tester; the 0.1-pip target does not survive execution**
(the same finding as v1.01 on 5 Nov). The saved setting's row shows the MT5 result; report file `monitor/TurtleTVUHV/runs/ZeeUHV_TurtleTV_TWICE_AN_HOUR_mt5.htm`.

### MT5 target sweep (Zee: "sweep it") - same EA, rig, period, delay; only the fixed target and the position limit move
| target (pips) | positions | trades | per hour | full stops | $0 + small-loss exits | WR (>0) | net | PF |
|---|---|---|---|---|---|---|---|---|
| 0.2 | 2 | 10,043 | 2.4 | 224 (2.2%) | 1495 | 82.58% | $-22,055 | 0.62 |
| 0.3 | 2 | 9,388 | 2.2 | 242 (2.6%) | 875 | 87.86% | $-16,687 | 0.72 |
| 0.5 | 2 | 8,408 | 2.0 | 274 (3.3%) | 437 | 91.26% | $-15,752 | 0.77 |
| 0.6 | 2 | 7,863 | 1.9 | 288 (3.7%) | 269 | 92.64% | $-11,357 | 0.84 |
| 0.8 | 2 | 7,306 | 1.7 | 308 (4.2%) | 155 | 93.38% | $-8,584 | 0.88 |
| 1 | 2 | 6,472 | 1.5 | 327 (5.1%) | 94 | 93.17% | $-6,709 | 0.92 |
| 1.5 | 2 | 5,442 | 1.3 | 374 (6.9%) | 31 | 92.12% | $-7,099 | 0.92 |
| 2 | 2 | 4,605 | 1.1 | 403 (8.8%) | 17 | 90.42% | $-5,683 | 0.94 |
| 3 | 2 | 3,632 | 0.9 | 431 (11.9%) | 8 | 87.14% | $-4,900 | 0.95 |
| 0.8 | 4 | 10,861 | 2.6 | 484 (4.5%) | 214 | 93.21% | $-20,592 | 0.82 |
| 1 | 4 | 9,963 | 2.4 | 527 (5.3%) | 107 | 93.23% | $-15,065 | 0.88 |
| 0.8 | unlimited | 14,336 | 3.4 | 673 (4.7%) | 250 | 93.25% | $-33,713 | 0.79 |
| 1 | unlimited | 14,334 | 3.4 | 827 (5.8%) | 130 | 92.96% | $-36,734 | 0.82 |
| 1.5 | unlimited | 14,335 | 3.4 | 1057 (7.4%) | 68 | 91.7% | $-34,194 | 0.87 |

The win rate peaks at 0.8-1.0 pip (93%); wider targets lose more full stops than they save $0 exits. Longer rounds block new setups under the
2-position limit, so 4 positions restore the frequency: **target 1.0 pip + 4 positions = 9,963 trades (2.4/hour), 527 full stops (5.3%), WR 93.2%
strictly positive, net -$15,065, PF 0.88, DD 17%** - saved as `TWICE AN HOUR - MT5 tuned, target 1.0 pip, 4 positions (MT5 93.2 pct, 2.4 per hour)`
with its MT5 receipt in the row. Unlimited positions trade 3.4/hour at the same WR but double the drawdown. Net is negative at every target: a
22.5-pip stop against a 1-pip target needs > 95.7% to break even, and MT5 gives 93%.

## Also today
- **11 Nov night: Claude played Golden Gravity LIVE on the applied setting (2026-11-07 12-09-37 + extender)** while Zee slept, through the game's own
  /api/act (fund live -> shoot -> ack), coin cut to 1,000 EUR for the night (the setting's 22.5-pip stop = $2.26 risk per round vs a $0.01 target; at
  5,000 EUR it would have been ~$11 of a $20 account) and restored to 5,000 at exit. **25 rounds, 25 wins (all 0.1-pip target hits), +$0.32, balance
  $20.32 -> $20.64**, 23:12-06:15 UTC (4:12-11:15 AM PKT); 13 sells / 12 buys; 15 rounds settled in under 2 min, the slowest took 2 h 9 min. Two signals
  skipped in the 20:45-23:00 UTC dead hours. Receipts: scratchpad play/play.log + play/rounds.jsonl. Live, not Python - but 25 rounds is 1/7 of a loss
  at the tester's 1.5% stop rate, so it proves the plumbing (signal -> fill -> broker-held stop/target), not the win rate.
- **10 Nov: data extended to today.** Zee exported PrimeXBT ticks 1-10 Nov (EURUSD_tick_data/PrimeXBTMT5Downloads/EURUSDp_202611012206_202611101458.csv); the same recipe as year1 (bid OHLC, tick count, mean spread: zero diff on 4,413 overlap minutes) appended 5,197 bars + 1.32 M ticks: year1 now 254,431 bars, 6 Mar - 10 Nov 14:57 UTC. Setups rebuilt (3,691; 91 on 5-10 Nov); TWICE AN HOUR save 11,656 -> 11,930 trades, WR 98.5% unchanged. Repeatable: py monitor/TurtleTVUHV/append_ticks.py <tick csv> (stop the server first; backups in simdata/backup).
- Turtle TV UHV: Detector Lab save handler stored no `result` (it read the cache's JSON bytes as a dict) — fixed in
  `server.py`, server restarted, Zee's tab reloaded; the TWICE AN HOUR save back-filled through `/api/sim`.
- 🔭 scan results table sortable (click a column: desc → asc → scan rank); Saved settings table sortable + one-line rows;
  Overview "Trades per day" card; STARTER (10,761) and ALL SETUPS (25,694, `InpMaxPos 0`) saves; `InpMaxPos` added to the
  engine (1 = one at a time, N = up to N open, 0 = every setup).
