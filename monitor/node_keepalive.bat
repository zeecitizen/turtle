@echo off
REM Node.js dashboard server keepalive — runs every minute via Windows Task Scheduler
REM Restarts the server if it dies. Silent on healthy state.
"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe" "C:\Users\zeesh\Documents\GitHub\turtle\monitor\node_keepalive.py" >> "C:\Users\zeesh\Documents\GitHub\turtle\monitor\.keepalive_stdout.log" 2>&1
