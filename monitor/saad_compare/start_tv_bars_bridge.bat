@echo off
rem Saad_strategy_1min v1.04 (InpBarSource 1) trades on the TradingView chart's candles.
rem Keep this window open while the EA runs live: it copies each closed 1-min candle of the chart
rem (BLUEBERRY:XAUUSD, 1 minute, TradingView started with the CDP bridge) into MT5's Common\Files.
"C:\Users\zeesh\AppData\Local\Programs\Python\Python312-arm64\python.exe" "%~dp0tv_bars_bridge.py" --export --live
