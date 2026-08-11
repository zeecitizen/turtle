# Save MT5 Setup As Default (One-Time)

After you have:
- 3 XAUUSD charts open
- PineConnector on chart 1
- TurtleTradeLogger on chart 2
- ShanoExitManager on chart 3
- AutoTrading green
- Smiley faces on all EA charts

**Lock it in as the default startup state:**

1. **File menu → Profiles → Save As...**
2. Name it: `Shano-Live`
3. Click OK

That's it — MT5 doesn't have an explicit "default" option. **Whichever profile is active when you close MT5 is the one that auto-loads on next start.** As long as `Shano-Live` has the ✓ checkmark in File → Profiles, it's active.

To verify: close MT5 completely, reopen — your 3 charts with all EAs should be there.

**Bonus — auto-launch MT5 on startup:**

The `install_eas.ps1` script can be extended to also launch MT5. Add this to startup.bat AFTER the EA install:

```bat
REM Launch MT5 with default profile
start "" "C:\Program Files\Blueberry Markets MetaTrader 5\terminal64.exe"
```

MT5 opens, loads the default profile (Shano-Live), and all 3 EAs are active automatically.
