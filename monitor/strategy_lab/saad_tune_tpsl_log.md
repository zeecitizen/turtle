# Saad 1-min EA - one setting at a time (MT5 optimizer, Blueberry XAUUSD_BB, Jan 1 - Oct 17 2026)

Zee 2026-10-17: *"run one by one on all settings in tradingview -> the MT5 optimizer -> pick a setting -> ... set it in tradingview indicator -> and keep going till all are optimized"*

Score = net / max drawdown (OnTester). Execution delay 0 while searching. A value wins only if it beats the chart's value with its neighbours averaged in, and on profit.

| # | Setting | Was | Now | Profit was → now | Why |
|---|---|---|---|---|---|
| 1 | iSlPips (InpSlPips) | 36 | **36.0** | +178,684 → +178,684 (WR 70.2% → 70.2%) | kept: no value with a higher win rate and at least the same profit/drawdown (70.1%, 1.57) |
| 2 | tpMode (InpTpMode) | Fibonacci extension of the setup candle | **Fibonacci extension of the setup candle** | +178,684 → +178,684 (WR 70.2% → 70.2%) | kept: no value with a higher win rate and at least the same profit/drawdown (70.2%, 1.71) |
| 3 | tpFib (InpTpFibPct) | 161.8 | **161.8** | +178,684 → +178,684 (WR 70.2% → 70.2%) | kept: no value with a higher win rate and at least the same profit/drawdown (70.2%, 2.05) |
