# Newsfeed Entry Schema

Every entry written by `Write-NewsfeedEntry` (or `cron_runner.ps1`) conforms to this schema.

## JSON Structure

```json
{
  "entry_id":     "2026-04-20T073000.123Z_status_5min_00847",
  "cron_id":      "status_5min",
  "cron_name":    "5 Minute Status",
  "cron_version": "1.2.0",
  "run_number":   847,
  "prev_entry_id":"2026-04-20T072500.101Z_status_5min_00846",
  "started_at":   "2026-04-20T07:30:00.123Z",
  "finished_at":  "2026-04-20T07:30:04.442Z",
  "duration_ms":  4319,
  "status":       "success",
  "summary":      "23 signals, 14 BE, SL=10p OK, alert live",
  "flags":        [],
  "actionable":   false,
  "novel":        false,
  "result":       { "...cron-specific payload..." },
  "error":        null
}
```

## Field Reference

| Field | Type | Rules |
|-------|------|-------|
| `entry_id` | string | `<iso8601_utc_compact>_<cron_id>_<zero_padded_5d_run>`. Also the inbox filename. Lexicographically sortable. |
| `cron_id` | string | Stable snake_case slug. Primary key. Never changes. |
| `cron_name` | string | Human display name. Can change; use cron_id for lookups. |
| `cron_version` | string | Semver. Bump when output shape changes. Enables analytics to detect shifts. |
| `run_number` | int | Monotonic per-cron counter. Persisted in `crons/state/<cron_id>.json`. |
| `prev_entry_id` | string\|null | Links to prior successful run. Enables trend analysis. Null on first run. |
| `started_at` | ISO8601 UTC | When cron began. Set by caller before work starts. |
| `finished_at` | ISO8601 UTC | When Write-NewsfeedEntry was called. |
| `duration_ms` | int | finished_at - started_at in milliseconds. |
| `status` | enum | `success` / `partial` / `error` / `aborted` |
| `summary` | string | **Single line, ≤200 chars.** What shows in LATEST.md. Required. |
| `flags` | string[] | Uppercase codes. See flag registry below. |
| `actionable` | bool | True if human/Claude action is warranted. Default false. |
| `novel` | bool | True if meaningfully different from previous run. Used by daily_scorecard. Default false. |
| `result` | object | Per-cron payload. ≤64KB serialized. Large artifacts go in `newsfeed/artifacts/<entry_id>/`. |
| `error` | object\|null | `{ message, stack, retriable }` on error; null on success. |

## Status Values

| Status | Meaning |
|--------|---------|
| `success` | Cron ran to completion, result is reliable. |
| `partial` | Cron completed but some data was unavailable (e.g. TV offline). |
| `error` | Cron failed. `error` field populated. |
| `aborted` | Cron process was killed before it could write finished_at. Written by bootstrap sweep. |

## Flag Registry

All flag codes used by any cron must be registered here.

| Flag | Raised by | Meaning |
|------|-----------|---------|
| `ALERT_DOWN` | status_5min, alert_health | Pine alert count is 0 — no active alerts |
| `SL_WRONG` | status_5min | MT5 EA SL does not match expected 10 pips |
| `SPIKE_DAY` | status_5min | At least one fill today with loss ≤ -$40 (intrabar spike SL) |
| `TV_DOWN` | status_5min, health_check | TradingView CDP not reachable |
| `MT5_DOWN` | health_check | terminal64.exe not running |
| `MT5_LOG_STALE` | status_5min | MT5 Expert log not updated in >30 min during market hours |
| `NO_LOG` | status_5min | No MT5 Expert log file for today |
| `EA_NOT_INSTALLED` | bootstrap, health_check | turtle_fills.csv absent — TurtleTradeLogger EA not running |
| `FILLS_STALE` | health_check | turtle_fills.csv not updated in >60 min during market hours |
| `SUMMARY_TRUNCATED` | newsfeed_writer | Summary exceeded 200 chars and was truncated |
| `INBOX_OVERFLOW` | health_check | >1000 files in newsfeed/inbox/ — consolidation broken |
| `CRON_OVERDUE` | health_check | A cron has not run within 3× its scheduled interval |
| `SIM_DIVERGE` | status_5min | Live P&L diverges from sim by >$100 today |

To add a new flag: add a row here, then use the code in your cron.

## Storage Tiers

| Tier | Path | Purpose |
|------|------|---------|
| Inbox | `newsfeed/inbox/<entry_id>.json` | Hot write location. Unique per entry. No locks needed. |
| Archive | `newsfeed/archive/YYYY-MM-DD.jsonl` | Daily consolidated JSONL. Append-only. Sortable by started_at. |
| Index | `newsfeed/INDEX.json` | `{cron_id: last_entry_summary}` cache. Rebuilt from archive if corrupted. |

Readers ignore `*.tmp` files in inbox (in-flight writes).
