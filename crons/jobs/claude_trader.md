Claude Trader v2 — UHV Alert Setter.
Sets a TradingView price alert for each new UHV. TV fires the PineConnector webhook natively when price crosses.
Normal run: 1 MCP call. New UHV run: 2 MCP calls + 1 node command.

─────────────────────────────────────────
1. data_get_pine_labels verbose=false
   Find the most recent "⚡ UHV Red" or "⚡ UHV Green" label.
   Set: UHV_LEVEL = label.price, UHV_COLOUR = Red|Green
   Set: UHV_KEY = "Red_<level>" or "Green_<level>"  (e.g. "Red_4777.5")

   If no UHV label found → run step 2 then STOP.

2. (No UHV) Write watch_state s=0:
   powershell -Command "$s=[ordered]@{s=0;t=(Get-Date).ToUniversalTime().ToString('o')};$s|ConvertTo-Json -Compress|Out-File 'c:\Users\zeesh\Documents\GitHub\turtle\monitor\watch_state.json' -Encoding UTF8 -Force"

─────────────────────────────────────────
3. Dedup — read cached key:
   powershell -Command "if(Test-Path 'c:\Users\zeesh\Documents\GitHub\turtle\monitor\.last_uhv_id'){Get-Content 'c:\Users\zeesh\Documents\GitHub\turtle\monitor\.last_uhv_id' -Encoding UTF8}else{'NONE'}"

   If output == UHV_KEY → STOP. (Alert already live, TV is watching.)

─────────────────────────────────────────
4. New UHV detected. data_get_ohlcv count=2 summary=false
   D = last completed bar (higher volume of the two).
   Set: DIRECTION = "buy" if UHV Red, "sell" if UHV Green
   Set: CROSS_DIR = "up" if buy, "down" if sell
   Set: MSG = "8778286989525,<DIRECTION>,XAUUSD,vol_lots=0.40,sl_pips=15,tp_pips=52,spread=30,betrigger=8,comment=Claude_Trader_v1"

─────────────────────────────────────────
5. Check if already broke:
   UHV Red:   broke = (D.high > UHV_LEVEL)
   UHV Green: broke = (D.low  < UHV_LEVEL)

   If BROKE → go to step 6 (direct fire).
   If NOT broke → go to step 7 (create TV alert).

─────────────────────────────────────────
STEP 6 — ALREADY BROKE: fire directly then save state.

6a. Fire exec.ps1 (pass D.high and D.low for WhatsApp candle info):
    powershell -ExecutionPolicy Bypass -File "c:\Users\zeesh\Documents\GitHub\turtle\monitor\claude_uhv_exec.ps1" -Direction <DIRECTION> -Lots 0.40 -Comment "Claude_Trader_v1" -UhvBarTime "<UHV_KEY>" -Reason "BRK <above|below> <UHV_LEVEL>" -CandleHigh <D.high> -CandleLow <D.low>

6b. Write watch_state s=6:
    powershell -Command "$s=[ordered]@{s=6;d='<DIRECTION>';l=<UHV_LEVEL>;t=(Get-Date).ToUniversalTime().ToString('o')};$s|ConvertTo-Json -Compress|Out-File 'c:\Users\zeesh\Documents\GitHub\turtle\monitor\watch_state.json' -Encoding UTF8 -Force"

6c. Save UHV key:
    powershell -Command "'<UHV_KEY>'|Out-File 'c:\Users\zeesh\Documents\GitHub\turtle\monitor\.last_uhv_id' -Encoding UTF8 -NoNewline -Force"

6d. Launch kill timer (1000ms, non-blocking):
    powershell -Command "Start-Process -FilePath 'C:\Users\zeesh\Documents\GitHub\turtle\monitor\start_close_monitor.bat' -ArgumentList '1000' -WindowStyle Hidden"

6e. Write newsfeed:
    powershell -ExecutionPolicy Bypass -File "c:\Users\zeesh\Documents\GitHub\turtle\crons\lib\cron_runner.ps1" -CronId "claude_trader" -CronName "Claude Trader v2" -CronVersion "2.0.0" -StartedAtUtc "<now_utc>" -Status "success" -Summary "DIRECT FIRE <DIRECTION> | UHV@<UHV_LEVEL> already broke | kill timer 1000ms launched" -Flags "" -Actionable "false" -Novel "true" -ResultJson "{\"signal\":\"<DIRECTION>\",\"uhv\":<UHV_LEVEL>}"

    Wait for NEWSFEED_WRITTEN. STOP.

─────────────────────────────────────────
STEP 7 — NOT BROKE: write target for persistent sniper daemon.
The daemon (claude_sniper_daemon.py) is already running — it reads this file
and starts watching the UHV level immediately. No process launch needed.

7. Write sniper target file (include UHV candle OHLCV for theory engine):
   powershell -Command "[System.IO.File]::WriteAllText('c:\Users\zeesh\Documents\GitHub\turtle\monitor\sniper_target.json','{\"uhv_key\":\"<UHV_KEY>\",\"level\":<UHV_LEVEL>,\"direction\":\"<DIRECTION>\",\"candle\":{\"open\":<D.open>,\"high\":<D.high>,\"low\":<D.low>,\"close\":<D.close>,\"volume\":<D.volume>},\"t\":\"'+((Get-Date).ToUniversalTime().ToString('o'))+'\"}',[System.Text.Encoding]::UTF8)"

7b. Send WhatsApp heads-up (non-blocking):
    powershell -Command "Start-Process -FilePath 'C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe' -ArgumentList 'C:\Users\zeesh\Documents\GitHub\turtle\monitor\whatsapp_alert.py --direction <DIRECTION> --price <UHV_LEVEL> --uhv-key <UHV_KEY> --mode headsup' -WindowStyle Hidden"

─────────────────────────────────────────
8. Save UHV key:
   powershell -Command "'<UHV_KEY>'|Out-File 'c:\Users\zeesh\Documents\GitHub\turtle\monitor\.last_uhv_id' -Encoding UTF8 -NoNewline -Force"

9. Write newsfeed:
   powershell -ExecutionPolicy Bypass -File "c:\Users\zeesh\Documents\GitHub\turtle\crons\lib\cron_runner.ps1" -CronId "claude_trader" -CronName "Claude Trader v2" -CronVersion "2.0.0" -StartedAtUtc "<now_utc>" -Status "success" -Summary "TARGET SET <DIRECTION> @ <UHV_LEVEL> | daemon watching" -Flags "" -Actionable "false" -Novel "true" -ResultJson "{\"target\":\"<DIRECTION>\",\"uhv\":<UHV_LEVEL>}"

   Wait for NEWSFEED_WRITTEN. STOP.
