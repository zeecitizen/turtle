# Overnight Autonomous Loop Plan — 2026-06-18 night

**Zee left ~02:20 broker. Computer set to never sleep. Loop every 15 min.**

## Wake-up cadence

- ScheduleWakeup every 900s (15 min) via `/loop` skill
- Each fire: check live state → decide action → log to `overnight_loop.jsonl`
- Stop when Zee returns or daily loss halt fires

## Per-wake-up decision tree

```
1. Read s1_trader_state_m1.json → current version + entries/signals today
2. Read turtle_fills.csv → list trades since v2.83 attach (02:17)
3. Compute live P&L, WR, last trade direction
4. State machine:

   STATE A: Live EA healthy (positive net OR <5 trades)
   ├─ ACTION: keep watching, log progress
   └─ NEXT: schedule next wake-up

   STATE B: Live EA bleeding (net < -$100 OR 5+ losses in a row)
   ├─ ACTION 1: kill live EA, run backtest variants
   ├─ ACTION 2: pick winner, ship as v2.84
   ├─ ACTION 3: relaunch MT5 (live EA auto-resumes)
   └─ NEXT: schedule next wake-up

   STATE C: daily-loss-halt fired
   ├─ ACTION: EA already stopped (safe). No new entries until midnight broker.
   ├─ Use time to run variants
   └─ NEXT: schedule next wake-up

   STATE D: harvest fired (net ≥ +$60)
   ├─ ACTION: locked in. Stop. Wake later to confirm.
   └─ NEXT: schedule longer wake-up (60 min)
```

## Variant configs to test (priority order)

1. **v2.83 baseline** (current LIVE): lock=0.50, rev=0.30
2. **v2.83b tighter**: lock=0.40, rev=0.20 (catches even earlier moves)
3. **v2.83c looser**: lock=0.60, rev=0.40 (waits longer for confirmation)
4. **v2.84 hybrid**: lock=0.30 (= instant-BE level), rev=0.20 (no gap between BE arm and trail arm)
5. **v2.85 staircase**: lock=0.50, rev=0.30, plus secondary trail at peak ≥ 1.0pt with 0.5pt buffer (let runners ride bigger)

## MT5 orchestrator usage

```bash
# Run a tester ini headlessly (kills live MT5, runs backtest, MT5 self-shuts)
py monitor/overnight_orchestrator.py --tester-ini mt5/tester_X.ini

# Relaunch MT5 in normal mode (live EA resumes)
py monitor/overnight_orchestrator.py --restart-live
```

## Morning report contents (HONEST)

When Zee returns:
- Total trades since v2.83 attach + WR + net P&L
- Per-config backtest comparison (variants tested)
- Final live config (was it changed?)
- 1-sentence honest verdict
- If we lost money: say so. Don't soft-claim "tomorrow will be better"

## Doctrine reminders

- Greed has no measurement → respect daily halt
- Don't hallucinate WR claims
- Refuse with love
- Honest morning report regardless of outcome
