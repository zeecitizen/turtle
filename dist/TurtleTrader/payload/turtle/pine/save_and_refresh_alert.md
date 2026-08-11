# save_and_refresh_alert — Pine Code Change Workflow

## Critical limitation (discovered Session 50)

`mcp__tradingview__alert_create` only supports **price alerts** (`condition` + `price`).
It does NOT support Pine indicator alerts (`type: pine_alert`, `condition.type: pine_alert`).

This means: after a `pine_save` that increments `pine_version`, the existing alert is
silently bound to the OLD version and runs stale code. There is no API path to recreate
the alert programmatically.

## Safe workflow for Pine code changes

### If ONLY settings change (no pine_save)
Use `indicator_set_inputs`. The alert syncs automatically. No alert recreation needed.
This is confirmed working — Session 49 changed iExHSL 15→10 and it appeared in live signals.

### If Pine SOURCE changes (pine_save required)
The alert MUST be manually recreated. Steps:

1. **Before editing**: capture current alert config from `alert_list`:
   - `alert_id`, `last_fired` timestamp, `inputs` snapshot

2. **Make Pine edits** via `pine_set_source` + `pine_save`

3. **Verify new pine_version**: call `alert_list` — it will still show OLD `pine_version`

4. **Delete old alert** via `alert_delete(alert_id=...)`

5. **In TradingView UI** (manual step — no API substitute):
   - Right-click chart → "Add Alert"
   - Condition: "Turtle Trader Desk" → "alert() function calls only"
   - Frequency: "Once Per Bar Close" (or as previously configured)
   - Notification: Webhook URL → `https://pineconnector.com/api/webhook/...`
   - Click "Create"

6. **Verify**: call `alert_list` — should show ONE alert with new `pine_version`

## Planned automation path (not yet implemented)

UI automation via TradingView MCP tools (`ui_click`, `ui_find_element`, `ui_keyboard`)
COULD automate step 5. This requires:
- `ui_open_panel("alert")` or equivalent
- Finding the alert creation dialog
- Filling in the webhook URL (stored in `monitor/.alert_config.json`)
- Confirming

Implementing this would add ~10 UI steps and ~6s latency. Deferred to a future session.
Document this in CHANGELOG when implemented.

## Reference: current alert config (Session 50 / April 2026)
```
alert_id: 4506913119
symbol: OANDA:XAUUSD
resolution: 1 (1-minute)
pine_version: 189.0
frequency: 60 (once per bar)
expiration: 2026-05-20
webhook: PineConnector (see PineConnector dashboard for URL)
```

## inputs_map.json version tracking
When pine_version changes, update `pine/inputs_map.json`:
1. Set `"pine_version"` to new version number
2. Verify all input indices by re-reading the Pine source
3. Rebuild map if any input was added/removed/reordered
