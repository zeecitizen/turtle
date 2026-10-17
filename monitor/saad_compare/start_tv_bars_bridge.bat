@echo off
rem Saad_strategy_1min (InpBarSource 1) trades on the TradingView chart's candles.
rem Keep this window open while the EA runs live: it copies each closed candle of the chart
rem (BLUEBERRY:XAUUSD, TradingView started with the CDP bridge) into MT5's Common\Files.
rem v1.26 (17 Oct): the chart's timeframe picks the file - 1 min tv_bars_XAUUSD.csv, 15 min tv_bars_XAUUSD_M15.csv.
rem Keep the chart on the SAME timeframe as the EA's MT5 chart.
"C:\Users\zeesh\AppData\Local\Programs\Python\Python312-arm64\python.exe" "%~dp0tv_bars_bridge.py" --export --live
