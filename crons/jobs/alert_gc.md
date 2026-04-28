Alert GC — Delete all stale Claude_Trader alerts from TradingView.
Run this before creating a new TV alert, or any time alerts have accumulated.
Typical run: 3-7 MCP calls (one overlayButton click + one dialog confirm per alert).

─────────────────────────────────────────
1. Get the current alert list:
   mcp__tradingview__alert_list

   Build TWO sets:
   ACTIVE_IDS   = alert_ids where active=true  AND message.includes("Claude_Trader")
   INACTIVE_IDS = alert_ids where active=false AND message.includes("Claude_Trader")

   If both empty → DONE (no cleanup needed).

─────────────────────────────────────────
2. Open the Alerts panel (needed so overlayButtons are in DOM):
   mcp__tradingview__ui_open_panel panel=alerts action=open

─────────────────────────────────────────
3. For EACH alert to delete (active first, then inactive), repeat steps 3a–3b:

3a. Trigger delete confirmation for ONE alert:
    mcp__tradingview__ui_evaluate expression="""
    (function() {
      var panel = document.querySelector('[class*="widgetbar-widget-alerts"]');
      var items = Array.from(panel.querySelectorAll('[class*="itemBody"]'));
      for (var i = 0; i < items.length; i++) {
        var btns = Array.from(items[i].querySelectorAll('[class*="overlayButton"]'));
        if (btns.length > 0) { btns[btns.length - 1].click(); return 'clicked'; }
      }
      return 'none';
    })()
    """

3b. Confirm the dialog (wait ~500ms for it to appear, then click Delete):
    mcp__tradingview__ui_evaluate expression="""
    (function() {
      var btns = Array.from(document.querySelectorAll('button'));
      var del = btns.find(function(b) { return b.textContent.trim() === 'Delete' && b.closest('[class*="dialog"]'); });
      if (del) { del.click(); return 'confirmed'; }
      return 'no_dialog';
    })()
    """

    If result == 'no_dialog': wait 300ms and retry 3b once.
    If still no_dialog: STOP (no more alerts to delete).

─────────────────────────────────────────
4. Verify cleanup:
   mcp__tradingview__alert_list

   Log count of remaining Claude_Trader alerts.
   Acceptable result: 0 active Claude_Trader alerts.
   Inactive (triggered) ones are harmless — they expire in 30 days.

─────────────────────────────────────────
NOTES:
- overlayButton[last] = delete (3 buttons: pause/edit/delete for active; restart/edit/delete for inactive)
- The confirmation dialog must be explicitly confirmed — overlayButton only triggers it
- TV confirms one at a time — do not batch-click multiple overlayButtons before confirming
- This GC is called from claude_trader.md step 7 before creating a new TV alert
