# Turtle Trader — Newsfeed & Bootstrap Architecture

## Read this first

You are building two pieces of infrastructure that the existing (and future) Turtle Trader crons depend on:

1. **Newsfeed** — a durable, append-only log where every cron records what it did, when, and what it found. Concurrent-write safe. Machine-parseable *and* human-readable. Designed so a future Claude session can open it, see "what happened today" at a glance, and eventually score crons by usefulness.
2. **Bootstrap** — a single-command (double-click) script that brings the entire Turtle Trader stack up from cold on any Windows machine or VPS. Idempotent. Re-run it after a crash and you're back to steady state in under 2 minutes. Models the Docker-deployment pattern in a pure Windows/PowerShell world.

These are the **substrate** for the existing `SIMPLIFY.md` work order (bulletproof CDP launch, named Pine inputs, headless EA install, etc.). Implement this architecture first; then the simplification tasks plug into it cleanly. Existing cron prompts (e.g. the 5-minute status job) get **ported** into the new structure, not re-invented.

Do not assume prior cron/monitoring code is correct. Verify by test. If you find existing code that already does something described here, prefer replacing it with the canonical version from this document rather than patching — the point is a single consistent architecture.

---

## Design principles

Five rules. Everything else flows from these.

1. **Append-only newsfeed.** No cron ever modifies or deletes a prior entry. Corrections happen by writing a new entry that references the old one.
2. **Per-writer unique files.** Every cron writes to its own unique filename in `newsfeed/inbox/`. No shared file handles, no locking, no write collisions possible — even with 10 crons firing simultaneously.
3. **Idempotent bootstrap.** Running `bootstrap.bat` when everything is already up must be safe and fast (<10s). Running it after a full crash must bring the stack back to the same state as a fresh boot. There is no "clean" vs "dirty" start path — there is one path.
4. **Declarative cron manifest.** Crons are defined in `crons/manifest.yaml`. Bootstrap reads the manifest and registers/updates crons to match. Adding cron #11 means editing one file.
5. **Fail loud, never silent.** A cron that errors writes a newsfeed entry marking its failure. A bootstrap step that fails halts the script with a clear reason and a suggested fix. No swallowing exceptions, no "warn and continue."

---

## Directory structure

Create this layout under `c:\Users\zeesh\Documents\GitHub\turtle\`:

```
turtle/
├── bootstrap/
│   ├── bootstrap.bat               # ENTRY POINT — double-click or cmd
│   ├── bootstrap.ps1               # actual logic
│   ├── teardown.ps1                # clean shutdown (dev/test only)
│   ├── health_check.ps1            # standalone verify-everything
│   └── lib/
│       ├── step_launch_mt5.ps1
│       ├── step_launch_tv.ps1
│       ├── step_verify_ea.ps1
│       ├── step_register_crons.ps1
│       └── step_smoke_test.ps1
│
├── newsfeed/
│   ├── inbox/                      # crons write *.json here (unique names)
│   ├── archive/
│   │   ├── 2026-04-20.jsonl        # consolidated day file (append-only)
│   │   └── 2026-04-21.jsonl
│   ├── LATEST.md                   # human-readable, regenerated on read
│   ├── INDEX.json                  # {cron_id: most_recent_entry} for fast lookup
│   └── SCHEMA.md                   # canonical entry schema (doc, not data)
│
├── crons/
│   ├── manifest.yaml               # declarative cron definitions
│   ├── lib/
│   │   ├── newsfeed_writer.ps1     # shared: WriteNewsfeedEntry
│   │   ├── newsfeed_reader.ps1     # shared: ReadNewsfeed with filters
│   │   ├── cron_runner.ps1         # wraps a job with start/end/error capture
│   │   └── tz_helper.ps1           # single source of truth for timezone math
│   └── jobs/
│       ├── status_5min.ps1         # the existing 5-min monitor, ported
│       ├── trading_analysis.md     # prompt for Claude-driven cron
│       ├── daily_scorecard.ps1
│       └── ...
│
└── monitor/                        # existing scripts — leave in place for now
```

Do not invent alternative layouts. Consistency here is the whole point.

---

## Newsfeed data model

### Entry schema (JSON)

Every newsfeed entry is a JSON object with these fields. Save this as `newsfeed/SCHEMA.md`.

```json
{
  "entry_id": "2026-04-20T07:30:00.123Z_status_5min_00847",
  "cron_id": "status_5min",
  "cron_name": "5 Minute Status",
  "cron_version": "1.2.0",
  "run_number": 847,
  "prev_entry_id": "2026-04-20T07:25:00.101Z_status_5min_00846",
  "started_at": "2026-04-20T07:30:00.123Z",
  "finished_at": "2026-04-20T07:30:04.442Z",
  "duration_ms": 4319,
  "status": "success",
  "summary": "10 signals today, 6 BE, last SL=10p OK, alert live",
  "flags": [],
  "actionable": false,
  "novel": false,
  "result": {
    "...arbitrary cron-specific structured payload..."
  },
  "error": null
}
```

**Field rules:**

- `entry_id` — `<iso8601_utc>_<cron_id>_<zero_padded_run_number>`. Lexicographically sortable, globally unique, also used as the inbox filename: `inbox/<entry_id>.json`.
- `cron_id` — stable slug (snake_case). Primary key across time. Never changes once assigned.
- `cron_name` — human-friendly display name. Can change; use `cron_id` for lookups.
- `cron_version` — semver. Bump when the cron's logic or output shape changes. Lets future analytics detect behavior shifts.
- `run_number` — monotonic per-cron counter. Persisted in `crons/state/<cron_id>.json` (create the dir). Survives restarts.
- `prev_entry_id` — link to the previous successful run of the same cron. Enables trend analysis without scanning the whole feed. Null for first run ever.
- `status` — one of `success`, `partial`, `error`, `aborted` (aborted = runner killed before cron could write finished_at; bootstrap marks these on startup).
- `summary` — **single line, <200 chars**. This is what shows up in `LATEST.md` and anywhere Claude is asked "what's the latest." Write it first-person-neutral: "10 signals today" not "We have 10 signals."
- `flags` — array of uppercase short codes (`ALERT_DOWN`, `SPIKE_DAY`, `SL_WRONG`, etc.). Document all flag codes in `newsfeed/SCHEMA.md`. Crons must not invent new flag codes without adding them there.
- `actionable` — boolean: did this run produce something that warrants human/Claude action? Default false.
- `novel` — boolean: is this result meaningfully different from the previous run? Default false. (Crude but useful for scorecard-time.)
- `result` — opaque JSON blob. Per-cron schema. Keep under 64 KB. If a cron needs to record a large artifact (screenshot, CSV), write the artifact to `newsfeed/artifacts/<entry_id>/<filename>` and reference its path inside `result`.
- `error` — null on success; on error, `{ "message": str, "stack": str|null, "retriable": bool }`.

### Storage layout (the key design choice)

Three tiers:

**Tier 1: `inbox/`** — the hot write location. Each cron run writes exactly one file: `inbox/<entry_id>.json`. Because `entry_id` is globally unique, there is **no possibility of two crons writing the same file**, so there is no lock, no mutex, no race. Crons write atomically: write to `inbox/<entry_id>.json.tmp`, then `Move-Item` to `inbox/<entry_id>.json`. Readers ignore `.tmp` files.

**Tier 2: `archive/YYYY-MM-DD.jsonl`** — the cold consolidated view. The reader (or a daily meta-cron) consolidates inbox entries into a day file and deletes the originals from inbox. Archive files are append-only JSONL. Sorted by `started_at`.

**Tier 3: `INDEX.json`** — a single JSON object mapping `cron_id → most_recent_entry`. Regenerated after every read or on a 1-minute tick. Lets any caller answer "what's the last thing status_5min said?" in one file read without scanning the archive.

Why this design:
- **No write contention**: unique filenames = no locking needed, works identically on Windows filesystems, local, or VPS
- **Crash-safe**: a killed cron leaves either a `.tmp` file (ignored) or a complete `.json` file (readable). No half-written state is visible to readers.
- **Scales to 10+ crons without redesign**: adding crons just adds more unique filenames
- **Easy to grep**: JSONL archives work with `Select-String`, `jq`, etc.

### LATEST.md (human-readable)

Auto-generated by the reader whenever it runs. Format:

```markdown
# Turtle Trader Newsfeed — Latest

_Generated 2026-04-20 07:32:14 UTC_

## Active crons (9 of 10)

| Cron | Last ran | Status | Summary |
|------|----------|--------|---------|
| 5 Minute Status | 07:30:04 UTC (2m ago) | ✓ | 10 signals today, 6 BE, last SL=10p OK |
| Trading Analysis | 07:00:12 UTC (32m ago) | ✓ | No structural drift detected |
| Alert Health | 07:30:00 UTC (2m ago) | ⚠ | alert_count=1 OK; last fired 16m ago |
| Daily Scorecard | 00:05:00 UTC (7h ago) | ✓ | Week EV: +$54.12/trade |
| EA Install Verify | Never | — | (awaiting first run) |
| ... | | | |

## Flags raised today

- 05:27 UTC `status_5min` → `SPIKE_DAY` (1 trade ≤ -$40)

## Recent entries (last 10)

### [07:30:04 UTC] 5 Minute Status ✓
10 signals today, 6 BE, last SL=10p OK, alert live

### [07:30:00 UTC] Alert Health ⚠
alert_count=1 OK; last fired 16m ago — above normal cadence

...
```

This is what Claude reads first when resuming a session. Design it to answer "what happened while I was away" in one scroll.

---

## Newsfeed library

Two PowerShell modules under `crons/lib/`. Both dot-sourced by every cron.

### `newsfeed_writer.ps1`

Exports one function. Contract:

```powershell
# Signature
Write-NewsfeedEntry `
    -CronId <string> `
    -CronName <string> `
    -CronVersion <string> `
    -StartedAt <datetime> `      # UTC
    -Status <string> `           # success|partial|error|aborted
    -Summary <string> `          # <200 chars, required
    -Result <hashtable> `        # serialized to JSON
    [-Flags <string[]>] `
    [-Actionable <bool>] `
    [-Novel <bool>] `
    [-ErrorInfo <hashtable>]     # required if Status=error

# Behavior
# 1. Loads/increments run_number from crons/state/<cron_id>.json (atomic via temp+rename)
# 2. Reads prev entry from INDEX.json for prev_entry_id
# 3. Constructs entry object per SCHEMA.md
# 4. Writes newsfeed/inbox/<entry_id>.json.tmp
# 5. Move-Item to newsfeed/inbox/<entry_id>.json
# 6. Updates INDEX.json (read-modify-write with retry; acceptable since rare contention)
# 7. Returns the entry object
```

Failure modes the writer must handle:
- Summary over 200 chars → truncate and append `…`, add flag `SUMMARY_TRUNCATED`
- Result object over 64KB serialized → refuse, return error, cron should have written to `artifacts/` instead
- Invalid Status value → hard fail (programmer error)
- INDEX.json write race (two crons finishing in same millisecond) → retry up to 5 times with 50ms backoff; if all fail, write anyway (inbox file is source of truth; INDEX is cache)

### `newsfeed_reader.ps1`

Exports:

```powershell
# Read one cron's latest entry (fast — INDEX lookup)
Get-LatestEntry -CronId <string>

# Read last N entries across all crons
Get-RecentEntries -Count <int> [-SinceUtc <datetime>]

# Filter
Get-Entries `
    [-CronId <string>] `
    [-Status <string>] `
    [-Flags <string[]>] `
    [-SinceUtc <datetime>] `
    [-UntilUtc <datetime>] `
    [-Limit <int>]

# Consolidation: move inbox/*.json into archive/YYYY-MM-DD.jsonl
# Idempotent. Safe to call any time.
Invoke-NewsfeedConsolidation

# Render LATEST.md from current state
Update-LatestMarkdown

# Structured summary for injection into Claude prompts
Get-ClaudeBriefing [-MaxTokensApprox <int>]
```

`Get-ClaudeBriefing` is critical — it's what the 9 a.m. "initialize monitoring" command effectively wraps. Returns a compact text block:

```
Turtle newsfeed as of 2026-04-20 07:32 UTC:

Last from each cron:
• status_5min (2m ago, ✓): 10 signals today, 6 BE, last SL=10p OK
• trading_analysis (32m ago, ✓): No structural drift detected
• alert_health (2m ago, ⚠): alert_count=1 OK; last fired 16m ago
...

Flags raised in last 24h:
• 05:27 status_5min SPIKE_DAY — 1 trade ≤ -$40

Crons with errors in last 24h: none
Crons that haven't run in 24h: ea_install_verify (new)
```

Size-capped so it can be dropped into any prompt.

---

## Cron manifest

File: `crons/manifest.yaml`. Single source of truth for which crons exist.

```yaml
version: 1

crons:
  - id: status_5min
    name: "5 Minute Status"
    version: "1.2.0"
    enabled: true
    type: script                  # script | claude_prompt
    schedule: "*/5 * * * *"
    script: crons/jobs/status_5min.ps1
    timeout_seconds: 120
    register_as: durable          # durable | session
    description: >
      Reads MT5 EA log and TradingView Pine tables, compares live
      vs sim, writes a one-line status summary.

  - id: trading_analysis
    name: "Trading Analysis"
    version: "1.0.0"
    enabled: true
    type: claude_prompt
    schedule: "*/30 * * * *"
    prompt_file: crons/jobs/trading_analysis.md
    timeout_seconds: 600
    register_as: durable
    description: >
      Claude reads recent newsfeed + charts, identifies structural
      drift between live and sim, writes findings.

  - id: alert_health
    name: "Alert Health"
    version: "1.0.0"
    enabled: true
    type: script
    schedule: "*/5 * * * *"
    script: crons/jobs/alert_health.ps1
    timeout_seconds: 60
    register_as: durable

  - id: daily_scorecard
    name: "Daily Scorecard"
    version: "1.0.0"
    enabled: true
    type: script
    schedule: "5 0 * * *"         # 00:05 UTC daily
    script: crons/jobs/daily_scorecard.ps1
    timeout_seconds: 300
    register_as: durable

  # ... 6 more slots reserved for future crons
```

**Two cron types:**

- `type: script` — runs a `.ps1` directly. The script itself calls `Write-NewsfeedEntry` at end. Use for mechanical data collection.
- `type: claude_prompt` — registered via `CronCreate` with the prompt body loaded from `prompt_file`. The prompt **must** end with an explicit instruction to call `Write-NewsfeedEntry` via a PowerShell step. Use for analysis requiring reasoning.

Bootstrap reads this manifest and does the right thing per type. Adding cron #11 is: append to `manifest.yaml`, run `bootstrap.bat` again.

---

## Cron job authoring

### Script crons

Template at `crons/jobs/_template.ps1` — every script cron starts from this:

```powershell
# crons/jobs/status_5min.ps1
param()

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\newsfeed_writer.ps1"
. "$PSScriptRoot\..\lib\tz_helper.ps1"

$cronId = 'status_5min'
$cronName = '5 Minute Status'
$cronVersion = '1.2.0'
$startedAt = [datetime]::UtcNow

try {
    # --- work happens here ---
    $mt5Summary  = & "$PSScriptRoot\..\..\monitor\read_mt5_log.ps1"
    $tvData      = Get-PineTableData   # from a helper
    $alertStatus = Get-AlertStatus

    $flags = @()
    if ($alertStatus.count -eq 0) { $flags += 'ALERT_DOWN' }
    if ($mt5Summary.last_sl -ne 10) { $flags += 'SL_WRONG' }

    $result = @{
        mt5     = $mt5Summary
        tv      = $tvData
        alert   = $alertStatus
        tz      = Get-TzHeader
    }

    $summary = "$($mt5Summary.signals) signals, $($mt5Summary.be_fired) BE, SL=$($mt5Summary.last_sl)p, alert $($alertStatus.health)"

    Write-NewsfeedEntry `
        -CronId $cronId -CronName $cronName -CronVersion $cronVersion `
        -StartedAt $startedAt `
        -Status 'success' `
        -Summary $summary `
        -Flags $flags `
        -Actionable ($flags.Count -gt 0) `
        -Result $result
}
catch {
    Write-NewsfeedEntry `
        -CronId $cronId -CronName $cronName -CronVersion $cronVersion `
        -StartedAt $startedAt `
        -Status 'error' `
        -Summary "Failed: $($_.Exception.Message.Substring(0, [Math]::Min(150, $_.Exception.Message.Length)))" `
        -Result @{} `
        -ErrorInfo @{
            message   = $_.Exception.Message
            stack     = $_.ScriptStackTrace
            retriable = $true
        }
    exit 1
}
```

Every script cron follows this shape. No exceptions.

### Claude-prompt crons

`crons/jobs/trading_analysis.md` is a prompt, not code. Structure:

```markdown
You are the Trading Analysis cron. Run number {{run_number}}.

Steps (in order, no skipping):

1. Call `Get-ClaudeBriefing` to load recent newsfeed context.
2. Call `data_get_pine_tables`, `data_get_pine_labels`, and `read_mt5_log.ps1` for fresh data.
3. Identify any of: structural drift, slippage patterns, stale alerts, novel losing clusters.
4. Produce a finding. If nothing notable, that IS the finding — say so.

Then MANDATORY: call the shell to record your run.

Run:
```
powershell -File crons/lib/cron_runner.ps1 `
    -CronId trading_analysis `
    -CronName "Trading Analysis" `
    -CronVersion "1.0.0" `
    -Status success `
    -Summary "<your one-line summary, under 200 chars>" `
    -Flags "<comma-separated flag codes or empty>" `
    -Actionable <true|false> `
    -Novel <true|false> `
    -ResultJson '<compact JSON, under 64KB>'
```

Do not end your response until you have made that call. If your analysis errored partway through, call with `-Status partial` or `-Status error` and include what went wrong in the Summary.
```

`cron_runner.ps1` is the CLI façade over `Write-NewsfeedEntry` — Claude can call it from any cron prompt without needing to dot-source PowerShell modules.

---

## Bootstrap script

### `bootstrap.bat` — entry point

```bat
@echo off
REM Turtle Trader bootstrap — one command brings the stack up
REM Safe to re-run. Re-running after a crash restores steady state.

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1" %*
if %errorlevel% neq 0 (
    echo.
    echo BOOTSTRAP FAILED. See output above.
    echo Re-running should be safe after addressing the error.
    pause
    exit /b %errorlevel%
)
exit /b 0
```

No `pause` on success — unattended reruns must not block.

### `bootstrap.ps1` — the real logic

Executes these phases in order. Each phase is idempotent. Each phase writes a newsfeed entry for itself (cron_id `bootstrap`) at the end — success or failure.

**Phase 0 — Preflight**
- Verify working directory is the turtle repo root
- Create any missing directories: `newsfeed/inbox`, `newsfeed/archive`, `newsfeed/artifacts`, `crons/state`
- Load `crons/manifest.yaml`; fail if missing or malformed
- Write phase-0 newsfeed entry

**Phase 1 — Mark orphaned runs as aborted**
- Scan `newsfeed/inbox/*.json` for entries with `finished_at: null` (cron started but never finished — likely killed by previous crash)
- For each, write a sibling entry with `status: aborted`, `summary: "aborted on bootstrap sweep"`, referencing the original via `prev_entry_id`
- Leave the original inbox file intact for audit

**Phase 2 — Consolidate yesterday's inbox**
- Call `Invoke-NewsfeedConsolidation`
- Anything older than today moves to `archive/YYYY-MM-DD.jsonl` and is removed from inbox
- Keeps inbox small

**Phase 3 — MT5**
- Check if `terminal64.exe` is running; if yes, skip launch
- If no, launch `C:\Program Files\Blueberry Markets MetaTrader 5\terminal64.exe`
- Wait up to 30s for process to stabilize
- Fail phase if not running after 30s

**Phase 4 — TradingView with CDP**
- Check `http://localhost:9222/json/version` — if 200 OK, skip (already up)
- Otherwise run the P0-fixed launcher from `SIMPLIFY.md`:
  1. `Stop-Process -Name TradingView -Force`
  2. `[Environment]::SetEnvironmentVariable('ELECTRON_EXTRA_LAUNCH_ARGS', '--remote-debugging-port=9222', 'User')`
  3. `Start-Process 'tradingview:'`
  4. Poll `localhost:9222/json/version` for up to 45s
  5. Once up, clear the env var with `[Environment]::SetEnvironmentVariable('ELECTRON_EXTRA_LAUNCH_ARGS', $null, 'User')`
- Fail phase if CDP not reachable after 45s

**Phase 5 — EA verification**
- Check for `turtle_fills.csv` at the MT5 Common\Files path
- If absent: call `mt5\install_logger.bat` (which should be the P1-fixed headless version from SIMPLIFY.md)
- If still absent after 60s: write newsfeed entry with `flag: EA_NOT_INSTALLED`, `actionable: true`, continue (do NOT fail bootstrap — monitoring can run in degraded mode)

**Phase 6 — Register crons**
- For each enabled cron in `manifest.yaml`:
  - Compute a deterministic hash of `(id, schedule, type, script/prompt content, version)`. Store in `crons/state/<cron_id>.registration_hash`.
  - If a registered cron with matching hash already exists (check via whatever mechanism the cron system exposes — `cron_list` or equivalent), skip re-registration
  - Otherwise: `CronDelete` the old one (if present) and `CronCreate` the new one
- Disabled crons: if registered, `CronDelete` them
- Fail phase if any required cron fails to register

**Phase 7 — Smoke test**
- For each enabled cron of `type: script`, run it **once, synchronously**, with a short timeout
- Verify each produced a newsfeed entry
- Claude-prompt crons skip this phase (can't synchronously invoke a Claude session; first real tick will validate)
- Fail phase if any script cron errored — the stack is not actually ready

**Phase 8 — Regenerate LATEST.md and report**
- Call `Update-LatestMarkdown`
- Print the top section of `LATEST.md` to console
- Write final bootstrap newsfeed entry: `status: success`, summary includes phase durations

**Total target time:** under 2 minutes end-to-end on a warm system, under 4 on cold boot.

### Resumption of Claude session (optional Phase 9)

If `monitor\.last_session` exists:
```powershell
Start-Process claude -ArgumentList "--resume", (Get-Content .last_session), "--prompt", "initialize monitoring"
```
Otherwise skip — user resumes manually first time, and we capture the session id on that first run for future boots.

This is the P2 "True single-click start" from `SIMPLIFY.md`, implemented as the last bootstrap phase.

---

## Health check and teardown

### `health_check.ps1`

Standalone, runs at any time, no side effects. Checks:

1. `localhost:9222/json/version` responds
2. `terminal64.exe` is running
3. `turtle_fills.csv` is being updated (mtime within last hour during market hours)
4. Each enabled cron has a newsfeed entry within `3 × schedule_interval`
5. No cron has a `status: error` in its latest entry
6. `newsfeed/inbox/` has fewer than 1000 pending files (a sign consolidation is broken)

Output is a single structured report printed to console **and** written as a newsfeed entry under `cron_id: health_check`.

Run on demand. Also wire it to a 15-minute cron so degradation is caught fast.

### `teardown.ps1`

For dev/test only. Stops everything cleanly:
- `CronDelete` all registered turtle crons
- Stop MT5 and TradingView gracefully
- Do NOT delete newsfeed data
- Write a teardown newsfeed entry

Never run this on production.

---

## Claude consumption pattern

Two canonical ways Claude sessions consume the newsfeed:

**On session start** (the `initialize monitoring` command):
1. Read `newsfeed/LATEST.md` directly
2. Call `Get-ClaudeBriefing` for structured summary
3. Respond with a one-paragraph "here's where we stand" + any flags that need user attention

**During normal operation:**
- Before making any recommendation, check `Get-LatestEntry -CronId trading_analysis` for recent analysis
- When user asks "what happened at 3pm?", call `Get-Entries -SinceUtc ... -UntilUtc ...`
- When user asks "which cron is most useful?", that's the scorecard (see next section)

Document both patterns in `crons/README.md` so future Claude sessions know the conventions.

---

## Scorecard (future, design now)

One of the user's goals: eventually let Claude read the feed and say "this cron is the most useful." Implement a minimal version now so data accretes correctly from day one.

Add cron `daily_scorecard` to the manifest (already listed above). Runs 00:05 UTC daily. Reads the last 7 days of archive. Emits:

```json
{
  "scorecard_date": "2026-04-20",
  "period_days": 7,
  "per_cron": {
    "status_5min": {
      "runs": 2016,
      "error_rate": 0.001,
      "actionable_rate": 0.04,
      "novel_rate": 0.02,
      "avg_duration_ms": 4200,
      "usefulness_score": 0.52
    },
    "trading_analysis": {
      "runs": 336,
      "error_rate": 0.0,
      "actionable_rate": 0.18,
      "novel_rate": 0.12,
      "avg_duration_ms": 180000,
      "usefulness_score": 0.74
    }
  },
  "ranking": ["trading_analysis", "status_5min", "alert_health", ...]
}
```

`usefulness_score` formula: `0.4 * actionable_rate + 0.4 * novel_rate + 0.2 * (1 - error_rate)`. Tune later. The point now is that the fields `actionable` and `novel` get recorded on every entry, so when this cron ships, it has real data to work with.

Scorecard writes a normal newsfeed entry with the ranking in `result`. `LATEST.md` renders the ranking as a small table.

---

## Failure modes (and what happens)

Walk through each before shipping. The architecture must degrade gracefully on each.

| Failure | Expected behavior |
|---------|-------------------|
| Cron process killed mid-run | Leaves no `.json` in inbox (only `.tmp`). Next bootstrap sweep writes an `aborted` entry. |
| Concurrent INDEX.json writes | Writer retries up to 5x. If all fail, inbox is source of truth; INDEX rebuilds on next read. |
| Cron writes malformed result (>64KB) | Writer refuses, returns error, cron logs `status: error` with reason. |
| Disk full | Writer fails loudly. Cron retries on next schedule. Nothing corrupts. |
| TV crashes mid-session | Next 5-min status cron writes entry with `flag: TV_DOWN`. `alert_health` cron flags it too. User-visible in LATEST.md within 5 min. |
| MT5 crashes | Same pattern, `flag: MT5_DOWN`. |
| Two crons schedule same minute | Safe — unique `entry_id` per write. Order in INDEX is whichever finished last; archive preserves both by `started_at`. |
| Bootstrap runs during active session | Phase checks ("is TV up?") mean most phases are no-ops. Cron re-registration hash means no duplicate registration. Full run <10s on warm system. |
| VPS reboots | On login, user double-clicks `bootstrap.bat`. Within 2–4 minutes, stack is back to steady state. Newsfeed history survives (it's on disk). |
| Corrupted INDEX.json | Reader rebuilds from archive + inbox scan. Cost: one slow read. Write it back. |
| Corrupted archive file | Loud error in health check. Manual intervention needed — but inbox entries of that day, if still present, can be re-consolidated. |

If you find a failure mode not in this table, add it to `FAILURE_MODES.md` before shipping.

---

## Implementation phases

Ship in this order. Each phase has acceptance criteria. Do not start phase N+1 before phase N passes.

### Phase A — Newsfeed core (no crons yet)
- `newsfeed/SCHEMA.md`, directory layout
- `newsfeed_writer.ps1`, `newsfeed_reader.ps1`
- Unit tests: 10 concurrent writes from 10 PowerShell processes produce 10 distinct inbox files, all readable, INDEX.json has the right last-write

**Acceptance:** in a test script, fork 10 background jobs that each write 100 entries as fast as possible (1000 total). After completion: exactly 1000 files in inbox OR archive, INDEX has the expected top-of-feed per cron_id, zero corrupt files, zero `.tmp` leftovers.

### Phase B — Port `status_5min` cron to new framework
- Rewrite the existing 5-min status as `crons/jobs/status_5min.ps1` using the template
- Run it manually 20 times, verify newsfeed entries make sense
- Regenerate LATEST.md, eyeball it

**Acceptance:** LATEST.md shows `status_5min` at top with sensible summary, status ✓, flags correct when known-bad state is induced.

### Phase C — Manifest + cron registration
- `crons/manifest.yaml` with the 4 crons listed above
- `step_register_crons.ps1` that reads manifest, computes hashes, registers/updates
- Re-running must be a no-op when nothing changed

**Acceptance:** run phase C twice in a row; second run reports "0 crons changed, 4 unchanged."

### Phase D — Bootstrap phases 0–7 (excluding Claude resume)
- All eight phases wired, each idempotent
- Smoke test actually runs each script cron synchronously once

**Acceptance:** `bootstrap.bat` from cold boot (reboot the machine first) produces a successful stack in <4 minutes with no human input. Running `bootstrap.bat` again immediately completes in <10s with zero changes.

### Phase E — LATEST.md + `Get-ClaudeBriefing`
- Auto-regenerate on writer activity (or on every read — simpler)
- Briefing format matches spec, stays under 2KB text

**Acceptance:** a new Claude session reading `LATEST.md` or calling `Get-ClaudeBriefing` can describe the last 24h in one paragraph without needing any other tool.

### Phase F — Remaining crons
- Port `alert_health`, `daily_scorecard`, `trading_analysis` (Claude-prompt type)
- Add `health_check` cron on 15-min schedule

**Acceptance:** all 5 crons appear in LATEST.md with real data, none in persistent error state.

### Phase G — Claude session resume (bootstrap phase 9)
- Capture session id on first `initialize monitoring`
- Subsequent bootstraps auto-resume

**Acceptance:** reboot machine, double-click `bootstrap.bat`, wait 4 minutes, Claude Code is open in the resumed session with monitoring active.

### Phase H — Scorecard
- Implement `daily_scorecard` cron logic
- Render ranking in LATEST.md

**Acceptance:** after 2 days of data, scorecard produces sensible rankings.

---

## Deliberately NOT in scope this session

- Changing any Pine strategy logic or parameter values
- Building a web UI for the newsfeed (it's a file; `cat LATEST.md` is the UI)
- Replacing the existing durable-cron mechanism with a custom scheduler
- Adding crons beyond the 4 listed in the manifest above (reserve 6 slots; fill later)
- Porting the tradingview-mcp repo patches from `SIMPLIFY.md` (separate work)

If any of these become tempting during implementation, stop and ask.

---

## Reporting back

For each phase completed, append to `crons/CHANGELOG.md`:
- **Phase letter + name**
- **Files created/changed** (paths)
- **How verified** (the exact command or test run)
- **Known limitations / deviations from this doc** (there will be some — note them honestly)

If you deviate from this architecture at any point — e.g. you discover the unique-filename scheme doesn't actually work on some filesystem, or `CronCreate` can't take the prompts this design implies — **stop and explain** rather than silently adapting. Architecture changes are the user's call, not yours.

---

## Sanity-check questions to ask the user before starting

Before writing any code, confirm with the user:

1. Is the durable cron mechanism (`CronCreate`) the correct scheduler, or should this target a Windows-native scheduler (Task Scheduler, cron-on-WSL)? Durable cron dies with the Claude session — that may or may not be acceptable.
2. Should `type: claude_prompt` crons share a single persistent Claude session, or spawn fresh sessions per run? Shared is cheaper and keeps context; fresh is cleaner.
3. Is there ever a case where two crons need to write entries that are conceptually a single transaction? (Expected: no. Confirming.)
4. Should `health_check` escalate to email/SMS/push on critical flags, or is newsfeed visibility sufficient for now? (Design as newsfeed-only; add notifier later.)

Get answers before phase A.
