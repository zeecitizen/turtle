@echo off
rem Turtle TV - the year of Blueberry 15-min candles with the MT5 Strategy Tester's own trades: http://127.0.0.1:8773
cd /d C:\Users\zeesh\turtle
start "" "C:\Users\zeesh\AppData\Local\Programs\Python\Python312-arm64\pythonw.exe" monitor\saad_view\server.py
timeout /t 3 >nul
start "" http://127.0.0.1:8773
