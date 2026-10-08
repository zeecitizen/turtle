# Current Claude session — handoff (2026-10-08, PKT night)

Written so the next Claude session can pick up without re-deriving anything.
**Read this, then `VERSION_HISTORY.md` and `LAWS.md` (LAWS.md is Zee's: read, never edit).**

---

## 1. Where the repo stands

- This clone lives at `C:\Users\zeesh\turtle` (CLAUDE.md still says `Documents\GitHub\turtle` —
  that was the old PC; paths in `startup.bat` and scripts may need adjusting before they run here).
- **Checked out: `optimise-for-expectancy`** (tracks `origin/feature/optimise-for-expectancy`, last
  commit `fb7d9b2`, 2026-09-01). This is the LATEST work. `main` is a frozen seal from 2026-08-11
  and is 230 commits behind.
- `main`'s headline (ZeeUHV 93.3%, +$2,599) was later overturned: measured at 4 ticks/bar, and a
  no-rules control (NullEntry) won 92.4% with the same SL20/TP1 geometry. Real-tick results are
  regime-dependent. See commits `61949b2`, `198957d`, `6b6fcc4`, `00a9a96`.
- Latest EAs (per VERSION_HISTORY.md): **ZeeUHV_Diamond v1.14** (magic 88154, sweep required,
  structural stop 5 pips) and **BasedOnLaws v1.44** (magic 88184, LAWS.md as hard gates).
  Which versions are actually attached in MT5 right now was NOT checked.

### Open items flagged to Zee (not acted on)
- LAWS.md vs code divergences: NY-only (BasedOnLaws runs all hours by his call; the Aug-28 court
  reversed the ranking — his decision pending), Diamond exits (fixed TP 1 + stacking vs his 1:2 +
  BE at 1:1), momentum expansion clause off, two Claude-invented guards in BasedOnLaws.
- VERSION_HISTORY.md "Sibling EAs" table is stale (says Diamond v1.10 / BasedOnLaws v1.35).

---

## 2. The TradingView indicator — what changed this session

The original UHV indicator is **`turtle.pine`** (repo root, "Turtle Trader Desk v1.0").
Older/larger variants live on branches `Code-with-FVGs`, `with-all-3-strategies`,
`Old-Turtle-Volume-Based`.

- Zee found `turtle_from_tradingview.pine` attached in TradingView: it is **exactly commit
  `10b084a` (2026-03-20)**, 41 commits older than the repo's turtle.pine. (Untracked file.)
- **Removed the 1-second dependency** (`request.security_lower_tf(..."1S"...)`): it threw
  RE10063 on Zee's plan. It only refined the kill-timer/breakeven *history simulation*; entries,
  drawings and live alerts never used it. Zee takes exits manually on MT5, so that's acceptable.
- **DEV block off**: `uDev` (input #139, "Developer mode") default `true` -> `false`, AND set
  false on the chart instance (the chart keeps its own saved inputs after a save).
- Both changes are **injected, compiled (0 errors, 26 old warnings) and saved in TradingView**,
  verified by reading the editor back and by screenshot.

Observed on the chart (indicator's own sim, NOT evidence per CLAUDE.md): fires every few minutes
both ways with `Trend:OFF Sweep:off`; panel showed 126 trades / 26 won today, 203/1029 (20%).

---

## 3. NEW: the TradingView bridge (Claude drives TradingView Desktop)

**Bridge:** `tradesdontlie/tradingview-mcp`, cloned to
`C:\Users\zeesh\Documents\GitHub\tradingview-mcp` (commit `c05b8f5`), `npm ci --omit=dev` done.
**Node.js 24.19 LTS** installed (`C:\Program Files\nodejs\node.exe`).
**Registered** as user MCP server `tradingview` in `~/.claude.json`
(backup: `~/.claude.json.bak-before-tradingview`). In the new session, `/mcp` should show it
connected and tools like `pine_set_source`, `capture_screenshot`, `chart_scroll_to_date`,
`indicator_set_inputs` should be available.

### One-click tools (new, uncommitted)
| file | use |
|---|---|
| `launch_tv_bridge.bat` (+ `bootstrap/launch_tv_bridge.ps1`) | start TradingView with CDP :9222. Already bridged -> confirms; open without bridge -> closes and relaunches; then checks the bridge sees the chart. Tested on the already-bridged path only. |
| `pine/inject_pine.py` | `python pine/inject_pine.py [--set uDev=false]` — refuses if the editor holds another script or if alerts exist; sets source, compiles+saves, fails only on severity-8 errors, verifies editor == file, sets chart inputs by Pine variable name. Tested end to end. |

Python on this PC: `C:\Users\zeesh\AppData\Local\Programs\Python\Python312-arm64\python.exe`
(not the 313 that CLAUDE.md names). `python` / `py` are NOT on PATH.

### Gotchas that cost time — do not rediscover
1. TradingView here is the **Microsoft Store (MSIX) build 3.4.1.8194**. Launching its exe from a
   COPY outside the package crashes ("Cannot read properties of undefined (reading
   'setErrorHandler')"). The bridge's own `tv launch` does exactly that — **don't use it**.
2. What works (the repo's April-20 note): in-package launch via
   `shell:AppsFolder\TradingView.Desktop_n534cwy3pjxzj!TradingView.Desktop` with user env
   `ELECTRON_EXTRA_LAUNCH_ARGS=--remote-debugging-port=9222`. The launcher sets it only for the
   launch and clears it — **every Electron app reads it** (VS Code would grab 9222).
3. Claude's shell inherits `ELECTRON_RUN_AS_NODE` from VS Code, so any Electron exe launched from
   it runs as plain Node ("bad option: --remote-debugging-port"). Unset it before launching
   anything Electron, or use the launcher.
4. The bridge reports warnings as errors. Monaco severity 8 = error, 4 = warning.
5. After a Pine save, the chart instance keeps its own input values — new defaults don't reach
   it. Inputs are only numbered (`in_0..in_139`); `inject_pine.py --set NAME=VALUE` maps names
   and refuses if the source and chart input counts differ.
6. A Pine save leaves any existing alert on the OLD code (`pine/save_and_refresh_alert.md`).
   There were **0 alerts** at the time of today's saves.
7. Windows PowerShell 5.1 reads BOM-less .ps1 as ANSI — keep .ps1 files pure ASCII (an em-dash
   broke the launcher once).

Fallback without the bridge: `scratchpad/tv.ps1`-style desktop capture + SendKeys works but takes
over Zee's mouse; it once un-maximised TradingView (fixed). Prefer the bridge.

---

## 4. Uncommitted changes (nothing committed this session)

```
 M turtle.pine                         1S removal + uDev default false
 M bootstrap/lib/step_launch_tv.ps1    ELECTRON_EXTRA_LAUNCH_ARGS set/clear around the launch
?? launch_tv_bridge.bat
?? bootstrap/launch_tv_bridge.ps1
?? pine/inject_pine.py
?? current_claude_session.md           (this file)
?? turtle_from_tradingview.pine        (Zee's export — keep or delete is his call)
```
Commit only when Zee asks (branch: `optimise-for-expectancy`).

## 5. Suggested first steps next session
1. `/mcp` -> confirm `tradingview` connected; call `tv_health_check`.
2. If TradingView isn't bridged, run `launch_tv_bridge.bat`.
3. Ask Zee what's next — the last thing on the table was reading the indicator's entries on his
   chart now that the labels are readable.

---

## 6. Session of 2026-10-08 night — indicator rework + win-rate loop (appended)

- turtle.pine now: camel humps drawn and used as THE trend (green hump = ended higher = buys),
  retracements backdated to where they began, strong-trend exception (camStrong), alerts /
  PineConnector / risk-management / no-trade windows removed, compact BUY/SELL labels with hover
  details, plain-English "No BUY: …" tags, rebuilt stats panel with Zee's win test
  (in profit N candles after the breakout-close entry, spread included), verified 40/40.
- Win-rate loop: best robust 71% on 51 labels (London+NY, breakout volume drop, no camel gate on
  retracement start, 15-min aligned, no cooldown) — applied on the chart only. 90% NOT reached;
  why, and all numbers: pine/lab/WINRATE_LOOP_2026-10-08.md.
- Tools: pine/tv_lab.py (push / set / get / score), pine/tv_sweep.py, pine/tv_export.js.
- Nothing committed.
