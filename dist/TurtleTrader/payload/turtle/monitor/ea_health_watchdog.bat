@echo off
REM Hourly EA health watchdog — runs via Windows Task Scheduler
REM Sends WhatsApp alert to Zee if anything's wrong with v3.x EA.
"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe" "C:\Users\zeesh\Documents\GitHub\turtle\monitor\ea_health_watchdog.py" >> "C:\Users\zeesh\Documents\GitHub\turtle\monitor\.watchdog_stdout.log" 2>&1
