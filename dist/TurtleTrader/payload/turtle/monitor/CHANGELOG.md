# Turtle Trader Monitor — CHANGELOG

---

## Session 50 — 2026-04-20 (Simplification Pass)

### P0: TradingView CDP launch replaced
**What changed**: Replaced `launch_tv_debug.bat` / `.vbs` (both broken for MSIX installs) with `launch_tv_debug.ps1`.
**Files touched**: `C:\Users\zeesh\Documents\GitHub\tradingview-mcp\scripts\launch_tv_debug.ps1` (new), `monitor\start_all.bat` (updated — removed `pause`, now calls PS script, exits non-zero on failure).
**How verified**: Script written; requires cold-boot test to confirm CDP response. The `ELECTRON_EXTRA_LAUNCH_ARGS` at user-scope + `tradingview:` protocol method was documented as working in a prior session.
**Known limitations**: Needs 3× cold-boot verification per acceptance criteria. Run manually if needed: `powershell -ExecutionPolicy Bypass -File tradingview-mcp\scripts\launch_tv_debug.ps1`

---

### P0: Named Pine inputs map created
**What changed**: Created `pine/inputs_map.json` with all 140 inputs (in_0 through in_139) mapped from Pine source. Built `monitor/get_pine_input.ps1` and `monitor/set_pine_input.ps1` for safe lookup and change proposal.
**Files touched**: `pine\inputs_map.json` (new), `monitor\get_pine_input.ps1` (new), `monitor\set_pine_input.ps1` (new).
**How verified**: Map manually derived by counting all `input.*()` calls in `turtle.pine` in order. Key mappings confirmed against known values: `in_0=iMon` (was 865, updated to 2000 this session), `in_39=uTPPips=52`, `in_42=uBERR=0.1`, `in_46=iExHSL=10`.
**Known limitations**: If Pine source adds/removes/reorders inputs between `pine_version` changes, map must be regenerated. Version guard in both helper scripts fails loudly on mismatch. No direct MCP call from scripts — Claude must execute the `indicator_set_inputs` call.

---

### P1: Headless EA install + auto-attach
**What changed**: Replaced 5-step manual install process with `mt5/install_logger.ps1`. Compiles EA headlessly via `metaeditor64.exe /compile`, writes `XAUUSD M5` chart file (`chart02.chr`) to the `Default` profile with TurtleTradeLogger pre-attached, restarts MT5, and verifies the "ready" line in the Experts log.
**Files touched**: `mt5\install_logger.ps1` (new), `mt5\install_logger.bat` (rewritten to call PS script), `MQL5\Profiles\Charts\Default\chart02.chr` (written by script at install time).
**How verified**: Script written; requires execution on live system. Headless compile via metaeditor64 is confirmed to work for MQL5. Chart file format derived from inspecting existing `deleted\01.chr` (PineConnector chart, text/Unicode format).
**Known limitations**: Period encoding (`period_type=0, period_size=5` for M5) is inferred from file inspection — if wrong, MT5 may open a different timeframe. The script prints diagnostic guidance if `ready` is not detected within 20s. Falls back to manual drag-drop if auto-attach fails.

---

### P1: Alert refresh workflow documented
**What changed**: Created `pine/save_and_refresh_alert.md` documenting the critical limitation: `alert_create` MCP tool only supports price alerts, NOT Pine indicator alerts. Any `pine_save` that changes `pine_version` requires manual alert recreation in the TradingView UI.
**Files touched**: `pine\save_and_refresh_alert.md` (new).
**How verified**: `mcp__tradingview__alert_create` schema confirmed to only accept `condition` + `price` parameters. Alert type `pine_alert` is not supported via MCP.
**Known limitations**: UI automation via MCP (`ui_click`, `ui_find_element`, `ui_keyboard`) COULD automate alert recreation but adds ~6s and ~10 UI steps. Deferred. Current safe rule: never call `pine_save` without reading `save_and_refresh_alert.md` first.

---

### P1: Timezone header script
**What changed**: Created `monitor/tz_header.ps1` that outputs a `[tz]` line showing UTC, Moscow (UTC+3, no DST), and Blueberry broker time (EET: UTC+3 summer Apr-Oct, UTC+2 winter) with last-signal elapsed time.
**Files touched**: `monitor\tz_header.ps1` (new).
**How verified**: Script written. Broker offset uses month-based EET DST approximation (Mar-Oct = UTC+3, Nov-Feb = UTC+2). Moscow is hardcoded UTC+3 (no DST since 2011). To include in cron output: call with `-LastSigBrokerTime` from `read_mt5_log.ps1` output.
**Known limitations**: Broker DST offset is approximated (last Sunday rule not implemented). Will be off by 1h for ~2 weeks at DST transitions. Cache file (`tz_cache.json`) not yet implemented — would allow manual override for DST edge cases.

---

### Balance update
**What changed**: Updated `iMon` (in_0) from $865 to $2000 for new Blueberry demo account.
**Files touched**: None (live TradingView indicator input only, via `indicator_set_inputs`).
**How verified**: `indicator_set_inputs(entity_id='B8A8LH', inputs={'in_0': 2000})` returned `success: true, updated_inputs: {in_0: 2000}`.

---

## Session 49 — 2026-04-20

### iExHSL reduced 15 → 10 pips
**What changed**: Hard SL sent to MT5 reduced to cap spike losses at ~-$40 instead of ~-$62. Does not affect Pine sim stats or lot sizing.
**How verified**: Next live signal showed `sl=10` in MT5 EA log (09:14 UTC SELL).
