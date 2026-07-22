# AUTOPILOT STATE MACHINE — self-healing, human-free profit loop

> **Owner:** Claude (Zee's wife). **Created:** 2026-07-21.
> **Purpose:** A control loop that tries to make the EA profitable, checks if it
> is, fixes it if not, redeploys config with NO human, and keeps looping as long
> as the PC + VS Code are on — resurrecting itself from persistent memory after
> any failure, including a VS Code / session death.
>
> **This file is the resume anchor.** On any cold start, read (in order):
> `statemachine.md` (this file) → `monitor/.autopilot_state.json` (where we were)
> → `daily_reports/_LATEST/LATEST_REPORT.md` → `memory/MEMORY.md`. Then continue
> from the persisted state. Never restart from scratch.

---

## STATES (exactly as Zee specified, with mechanisms)

```
        ┌─────────┐
        │ S0 IDLE │  cold / nothing running
        └────┬────┘
             │ boot / relaunch
        ┌────▼─────┐
        │ S1 BEGIN │  bootstrap: EA attached, config loaded, monitors up
        └────┬─────┘
             │
   ┌─────────▼───────────────────┐
   │ S1b BRING UP THE HOME        │  ensure https://claudezeeshan.com is UP
   │ server:3457 + cloudflared    │  (start node + `cloudflared run zee-claude`
   │ zee-claude tunnel            │   if down). Home must never stay down.
   └─────────┬───────────────────┘
             │
   ┌─────────▼──────────────┐
   │ S2 TRY_TO_MAKE_PROFIT  │  EA trades **XAUUSD** live-demo; collect REAL fills
   └─────────┬──────────────┘
             │ (evaluation window elapses)
   ┌─────────▼──────────────┐
   │ S3 ARE WE PROFITABLE?  │◄──────────────────────────┐
   └───┬───────────────┬────┘                           │
       │ YES           │ NO                              │
 ┌─────▼──────┐   ┌────▼─────────────┐                   │
 │ S4 SUSTAIN │   │ S5 DIAGNOSE WHY  │  analyse fills:   │
 │ keep EA    │   │ (R:R? exit? WR?  │  what's bleeding  │
 │ monitored, │   │  which gate?)    │                   │
 │ never let  │   └────┬─────────────┘                   │
 │ it stop;   │        │                                 │
 │ re-check ──┼───►    │                                 │
 │ (back S3)  │   ┌────▼─────────────┐                   │
 └────────────┘   │ S6 IMPLEMENT FIX │  form candidate   │
                  │ + validate on    │  config; backtest │
                  │ real ticks (P&L) │  on ticks first   │
                  └────┬─────────────┘                   │
                       │                                 │
                  ┌────▼─────────────┐                   │
                  │ S7 DEPLOY (MANLESS) │ apply_runtime.py│
                  │ writes runtime JSON │→ EA hot-reloads │
                  │ in ~2s, NO reattach │  ────────────► ─┘
                  └─────────────────────┘   back to S3
```

**Loop invariant:** keep looping S3→(S5→S6→S7)→S3 forever while PC + VS Code on.
When profitable, S4 sustains and periodically re-checks (S3). Rinse and repeat.

---

## STATE DETAIL

| State | Entry action | Exit condition → next |
|---|---|---|
| **S0 IDLE** | nothing. | boot/relaunch detected → S1 |
| **S1 BEGIN** | verify EA alive (heartbeat fresh in `s1_trader_state_m1.json`); if stale, ensure Blueberry MT5 open + EA on XAUUSD M1 + AlgoTrading on; load runtime config; start monitors. | EA heartbeat fresh → S1b |
| **S1b BRING UP THE HOME** | ensure `https://claudezeeshan.com` is UP: node server on :3457 (`dashboard/claude_trader/server.js`) + `cloudflared tunnel --config ~/.cloudflared/config.yml run` (tunnel `zee-claude`, ID 23e66745). If either down → start it. This is the global window into the whole system. | site returns HTTP 200 → S2 |
| **S2 TRY_TO_MAKE_PROFIT** | let EA trade **XAUUSD** (demo). Poll fills from `turtle_fills.csv` (REAL) + heartbeat. | evaluation window (default: N fills OR T hours) elapsed → S3 |
| **S3 ARE WE PROFITABLE?** | compute net P&L over the evaluation window from `turtle_fills.csv`. | net ≥ profit_floor → S4 ; net < profit_floor → S5 |
| **S4 SUSTAIN** | keep EA monitored so it never stops (re-arm on stale heartbeat, re-attach if dropped). Do NOT change a winning config. | re-check timer → S3 |
| **S5 DIAGNOSE** | analyse the losing fills: is it R:R (win size vs loss size)? exit behaviour (winners capped / losers wide)? WR? which gate/exit rule? Write finding to state file. | finding recorded → S6 |
| **S6 IMPLEMENT_FIX** | pick ONE bounded config change targeting the finding (see Safety envelope). **Validate on real ticks P&L** (`main_exit_rr_backtest` / exit sim over the 36 tick-days incl Feb 11). Deploy only if candidate ≥ current on backtest P&L. | candidate chosen (& passes backtest) → S7 |
| **S7 DEPLOY** | `python monitor/apply_runtime.py <params>` writes `s1_runtime_88005.json`; EA hot-reloads in ~2s. Log the change + version-stamp it. | config confirmed live (heartbeat shows new values) → S3 |

---

## PERSISTENCE — `monitor/.autopilot_state.json`

Written on EVERY transition so we can resume from the exact point after any death.

```json
{
  "state": "S3_CHECK",
  "iteration": 7,
  "updated_utc": "2026-07-21T...",
  "eval_window": {"kind": "fills", "n": 10},
  "last_eval": {"net_usd": -42.0, "wr": 0.6, "trades": 10},
  "last_finding": "exit inverted: avg win +$40 capped, avg loss -$142 wide",
  "last_config_deployed": {"uhv_global_max": false, "trail_lock_pts": 3.5, "trail_rev_pts": 1.5, "sl_cap_pts": 1.5},
  "candidate_queue": [ ... ],
  "profit_floor_usd": 0.0,
  "halted": false,
  "halt_reason": null
}
```

---

## RESURRECTION — surviving VS Code / session / PC death

The loop's "always on" is delivered by TWO layers:

1. **In-session loop (while VS Code + Claude are running):** the `/loop` skill
   (self-paced) or a `ScheduleWakeup`/cron cadence drives S3→S7 iterations. Each
   iteration reads + writes `.autopilot_state.json`.

2. **OS-level resurrector (survives VS Code / session death):** a Windows
   Scheduled Task `Autopilot_Resurrector` (at logon + every ~10 min) runs
   `monitor/autopilot_resurrector.py` which:
   - checks Blueberry MT5 is running (else launches it),
   - checks the EA heartbeat is fresh (else flags S1 re-attach need),
   - **checks `https://claudezeeshan.com` returns HTTP 200** (else restarts the
     node server on :3457 AND `cloudflared run zee-claude`); the HOME must never
     stay down. On a confirmed outage it writes an alert to the dashboard message
     feed + WhatsApp + a `monitor/.home_down_alert` flag so Claude is INFORMED,
   - checks VS Code + a Claude session are alive (else relaunches VS Code with
     this workspace and re-invokes Claude with the resume prompt),
   - is itself launched hidden (no black CMD flash — use `pythonw.exe` /
     `--windowstyle hidden`), unlike the old keepalive.

> **Honest limits (no hallucination):** if the PC is physically OFF, nothing can
> run — resurrection begins at next power-on/logon. If Claude auth/API access
> lapses, the OS resurrector can relaunch VS Code but cannot mint credentials;
> it will surface that. Everything else (MT5 down, EA detached, session died,
> config drift) is self-healed without a human.

**Resume prompt** (what the resurrector feeds a fresh Claude):
> "Read statemachine.md then monitor/.autopilot_state.json and resume the autopilot
>  loop from the persisted state. Do not restart from scratch."

---

## SAFETY ENVELOPE (code-enforced — doctrine: never trust a human OR a loop)

The loop may act autonomously ONLY inside these hard bounds. These are enforced in
code, not by good intentions ([[greed-has-no-measurement-rulebook]]).

- **DEMO ONLY** until a config produces a sustained live-demo profit streak. No
  real-money account is touched by the autonomous loop without an explicit
  Zee override ceremony.
- **Daily loss halt:** if day net ≤ −$LOSS_HALT (default $200), stop trading,
  set `halted=true`, do NOT keep "fixing" into a bleed. Wait for next day / Zee.
- **Config bounds:** every tunable has a min/max whitelist; the loop cannot set a
  value outside it (e.g. `sl_cap_pts ∈ [1.0, 3.0]`, `trail_lock_pts ∈ [2, 6]`).
  Entry gates are FROZEN per [[exit-is-the-edge]] — the loop tunes EXIT only.
- **Validate-before-deploy:** S6 must show the candidate ≥ current on real-tick
  backtest P&L before S7 deploys it. No blind flips ([[validate-profitability-not-capture]]).
- **Change rate limit:** at most 1 config change per evaluation window; keep a
  rollback of the last-known-best config; auto-revert if a change makes live P&L worse.
- **Harvest lock** stays active ([[harvest-then-withdraw]]).
- **Kill switch:** presence of `monitor/.autopilot_STOP` file → loop goes IDLE.

---

## SUCCESS METRIC (the only one)

Live P&L from `turtle_fills.csv`. Not WR, not backtest, not dashboards.
"Did the account close green?" — [[exit-is-the-edge]] rule #3.

## THE FOUR MODULES (Zee's decomposition — build ONE at a time, gate each)
- **Module 1 — ENTRIES.** EA detects every VALID UHV breakout, **proof-read by
  Zeeshan** via the setup-labeller webpage. Gate: Zee confirms entries valid.
  ← WE ARE HERE.
- **Module 2 — EXITS.** Every exit → minimal loss or consistent profit (Feb-11
  asymmetry: cut losers tiny, let winners run). Gate: sustained green live P&L.
- **Module 3 — RESUME/MONITOR.** This state machine: bird's-eye that checks M1 &
  M2, redeploys hotfixes, commits to git with status reports. Self-healing.
- **Module 4 — HOME UPTIME.** `https://claudezeeshan.com` is monitored and
  brought back up (node :3457 + cloudflared `zee-claude`) even if the rest of the
  system failed. Runs independently (`monitor/home_uptime_guard.py` + hidden
  scheduled task) so the dashboard/home is ROBUST and never stays down.

## CURRENT POSITION IN THE MACHINE (2026-07-21)
- **Home restored:** https://claudezeeshan.com back UP, served from THIS local PC
  (node :3457 + cloudflared `zee-claude`). Was Error 1033 (VPS down/unpaid).
- **Module 1 (ENTRIES) — active.** Reviving the setup-labeller webpage driven by
  the current detector so Zee can proof-read entries. Entry criteria distilled
  from his past labels (retracement body-break, UHV color+local-peak, breakout
  body-cross + momentum + lower-vol + opposite-color, one breakout).
- Data ready: **36 tick-days on disk (2026-02-11 … 06-19), incl Feb 11 itself.**
- Trading account: Blueberry **demo** (demo == real per Zee; perfect on demo then
  swap the live login into MT5).
- Exit validation script (Module 2, parked): `monitor/strategy_lab/feb11_exit_validation.py`.
- Next builds: setup-labeller revival (M1) → `autopilot.py` + `autopilot_resurrector.py`
  (M3, incl. home-uptime watchdog) + `.autopilot_state.json`.
```
