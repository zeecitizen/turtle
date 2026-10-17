# Saad 1-min EA - one setting at a time (MT5 optimizer, Blueberry XAUUSD_BB, Jan 1 - Oct 17 2026)

Zee 2026-10-17: *"run one by one on all settings in tradingview -> the MT5 optimizer -> pick a setting -> ... set it in tradingview indicator -> and keep going till all are optimized"*

Score = net / max drawdown (OnTester). Execution delay 0 while searching. A value wins only if it beats the chart's value with its neighbours averaged in, and on profit.

| # | Setting | Was | Now | Profit was → now | Why |
|---|---|---|---|---|---|
| 1 | iMaxRisk (InpMaxRiskUsd) | 0 | **20.0** | +47,287 → +88,903 (WR 83.2% → 83.3%) | higher win rate: 83.1% vs -499999958.4% (with neighbours), profit +88,903 vs +47,287 |
| 2 | iMaxRisk (InpMaxRiskUsd) | 20 | **20.0** | +88,903 → +88,903 (WR 83.3% → 83.3%) | no clear win-rate gain (best 21: 83.3% vs 83.2%) - kept |
