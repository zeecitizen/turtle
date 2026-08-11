# Shano's Strategy -- Complete Rules (From Her Own Words)

## Date Documented: 2026-04-24
## Source: WhatsApp interview + MT5 trade history analysis
## Status: 100% COMPLETE

---

## ENTRY RULES

1. **Wait for direction** -- don't trade in choppy/sideways markets ("I wait")
2. **Signal**: ONE single candle that is visibly BIG ("Bar not bars")
3. **Candle must be 25% LARGER than the PREVIOUS 2 candles** ("It's usually third one. Two before it" / "When it's one quarter bigger than last one take a trade")
4. **She reads candle SHAPE, not price numbers** ("Candle shape" / "I don't see values of selling dropping. Just candle coming down")
5. **SELL**: Big RED candle actively growing downward ("Price just dropped fast" / "Big red body coming downwards")
6. **BUY**: Big GREEN candle actively going upward ("Big green going up instead" / "Visible bar going high")
7. **Strategy is symmetrical** -- works same for buy and sell, she just focuses on sells ("Exactly works same way for buying green bars. But I can't focus more on buying candles so I take sell trades")
8. **She enters WHILE candle is still growing** -- not waiting for close ("While" / "No on way of it" = on the way, not after close)

## POSITION SIZING

9. **Scout trade**: 0.08 lots (her standard entry size)
10. **Scale up after 7 seconds** if scout is in profit ("Almost seven seconds")
11. **The scout turning positive IS the real confirmation signal** -- not candle patterns
12. **Open NEW separate trade** when scaling, don't modify existing ("New separate trade")
13. **Scaling progression**: 0.08 -> 0.10 -> 0.20 -> 0.40
14. **Can have 3-4 trades open simultaneously** in same direction

## EXIT RULES

15. **No stop loss set** ("No stoploss. Manually modify")
16. **Target: $10 profit per cluster** ("It's enough making ten I stop quickly")
17. **Close manually when she feels it's enough**
18. **On losing trades: HOLD and wait for reversal** ("I wait for loss to turn into profit again. Red values turning blues again")
19. **Only emergency close: when she's lost mid-way of account capital** ("No mid way of account capital I close" = 50% drawdown max)
20. **Close positions one at a time** with small lots first if multiple open

## SESSION & TIMING

21. **Timeframe**: 1 min (confirmed from her trade frequency -- trades every 1-2 minutes)
22. **Session**: London/NY overlap (14:00-17:00 Moscow based on her trade times)
23. **Can trade for 2 hours nonstop or just 5 minutes** ("It varies")

## RISK PROFILE

- **No SL**: She relies on the trade coming back
- **$10 TP target per cluster**: Quick in, quick out when profitable
- **50% account max drawdown**: Emergency exit only
- **69% win rate** from today's 32 visible trades
- **Average win: $5.30 | Average loss: -$8.97** (but she holds losers expecting reversal)
- **Sell bias**: 71% of her trades were sells (she rides the trend, doesn't fight it)

---

## AUTOMATABLE RULES (What we can code)

### Detection (via CDP tick stream):
- Monitor current candle body size in real-time
- Compare current candle body to the PREVIOUS 2 candle bodies
- If current candle body > 1.25x BOTH of the previous 2 candle bodies AND growing -> SIGNAL
- "One quarter bigger" = 25% larger than previous candle = 1.25x multiplier
- ONE big candle is the trigger, NOT a streak of candles
- Enter WHILE candle is still forming (don't wait for close)

### Entry:
- Fire 0.08 lot SELL when big red candle detected (body > both previous 2 candles)
- Fire 0.08 lot BUY when big green candle detected (body > both previous 2 candles)
- Enter while candle is still forming -- don't wait for close

### Scale-up (the REAL confirmation):
- After 7 seconds, check if scout trade P&L is positive
- If yes, fire NEW 0.10 lot trade in same direction
- After another 7 seconds, if in profit, fire 0.20 lot trade
- Scout P&L turning positive = strongest signal (not candle patterns)

### Exit:
- Close all when total cluster P&L reaches +$10
- If any single trade reaches -$7, switch direction (don't hold like Shano -- she has human judgment we don't)
- Emergency: close all if total loss exceeds -$30

### NOT automatable (requires human-like workaround):
- "It's clear on screen everytym" -- her visual intuition for direction
- Holding losers expecting reversal -- too risky without human judgment
- "I wait" for direction -- we use candle size ratio as mechanical filter

---

## CRITICAL INSIGHT: WHY OUR FIRST BACKTEST FAILED

Our exhaustion detection looked for 3-5 consecutive same-color candles with high volume.
Result: 1/32 trades detected (3%).

**Why?** Shano said "Bar not bars" -- she looks at ONE single big candle, not a streak.
Her strategy is momentum-based, not pattern-based:
1. See one big candle -> that IS the signal
2. Enter scout trade in same direction as the big candle
3. If scout turns positive in 7 seconds -> scale up
4. Take $10 and leave

The scout trade P&L is her REAL confirmation, not candle patterns.

---

## ALL ANSWERS CONFIRMED
- [x] Buy-side strategy: Same as sell, just reversed ("Big green going up instead")
- [x] Symmetrical: "Exactly works same way for buying green bars"
- [x] Why sell-only focus: "Can't focus more on buying candles so I take sell trades"
- [x] "Bar not bars" -- one candle is the trigger
- [x] Scale-up timing: 7 seconds ("Almost seven seconds")
- [x] Scout is the confirmation: "value of small lot turning positive is the major signal"
- [x] TP: $10 per cluster
- [x] No SL, holds losers
- [x] Emergency close at 50% account drawdown
