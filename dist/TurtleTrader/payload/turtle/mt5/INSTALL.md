# TurtleTradeLogger — Installation Guide

## One-time setup (5 minutes)

### Step 1 — Copy the file into MT5

In MT5: **File → Open Data Folder** → navigate to `MQL5\Experts\`

Copy this file there:
```
c:\Users\zeesh\Documents\GitHub\turtle\mt5\TurtleTradeLogger.mq5
```

Or run this command:
```
copy "c:\Users\zeesh\Documents\GitHub\turtle\mt5\TurtleTradeLogger.mq5" "C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Experts\"
```

### Step 2 — Compile it

In MT5: **Tools → MetaEditor** (or press F4)  
In MetaEditor: find `TurtleTradeLogger.mq5` in the Experts folder, press **F7**  
Should compile with 0 errors, 0 warnings.

### Step 3 — Attach to a chart

**Important: NOT the same chart as PineConnector.**  
Open any other chart — e.g., XAUUSD M5 — and drag `TurtleTradeLogger` onto it.  
Leave all settings at defaults.  
Click OK.

The EA will appear in the top-right corner of that chart.  
Check the **Experts** tab at the bottom — you should see:
```
TurtleTradeLogger v1.01 ready → Common\Files\turtle_fills.csv
```

### Step 4 — Verify it works

On the next trade close, check the Experts tab for:
```
TurtleTradeLogger: logged deal=XXXXXXXX SELL_closed XAUUSD 0.40 lots net=$-7.20
```

And verify the CSV exists:
```
powershell -ExecutionPolicy Bypass -File "c:\Users\zeesh\Documents\GitHub\turtle\monitor\read_fills.ps1"
```

---

## Output file location

```
C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv
```

## CSV columns

| Column | Example | Notes |
|---|---|---|
| broker_time | 2026.04.20 09:14:01 | MT5 broker server time (UTC+2 for Blueberry) |
| deal_ticket | 49591861 | Unique deal ID |
| position_ticket | 49591861 | Position ID (matches entry deal) |
| symbol | XAUUSD | |
| direction | BUY_closed / SELL_closed | The position that was closed |
| volume | 0.40 | Lots |
| close_price | 4789.870 | Exit price |
| profit | -1.20 | MT5 raw profit |
| commission | 0.00 | Broker commission |
| swap | 0.00 | Overnight swap |
| net_pnl | -1.20 | profit + commission + swap |
| comment | 0.40 | PineConnector comment field |

## Survival on restart

MT5 automatically reloads EAs on chart templates. As long as the XAUUSD M5 chart  
(or whichever chart you attached it to) is part of your default profile, it will  
restart automatically when MT5 opens.

To ensure this: **File → Save Profile** after attaching the EA.
