# Zeeshan's Expectations — Read This Every Session

## Who I Am
I'm Zee. I'm investing real money. Every dollar lost is real. I don't want explanations after a loss — I want the loss to not happen in the first place.

## What I Expect From Claude

### 1. CATCH EVERY UHV LABEL
- Every single UHV Red or UHV Green label that appears on the TradingView chart MUST be detected and traded
- Scan labels every 5 seconds, not every 30
- Read at least 20 labels deep, not 5
- If the current UHV target is far away (gap > 5), switch to the newest closer UHV immediately
- NEVER get stuck watching a stale UHV while fresh profitable ones appear and expire

### 2. STOP EXPLAINING, START FIXING
- When something goes wrong, don't write paragraphs about why. Fix the code.
- Don't tell me "the spread is the reason" — make the system handle spread correctly from day one
- Don't tell me "the loss cut killed it" — make Claude AI decide, not if/else rules
- If we lose money, the next message should be "I fixed X, restarted, here's what changed"

### 3. CLAUDE AI IS THE SOLE DECISION MAKER
- No if/else rules for trade management. No dud exit. No fixed profit target. No fixed loss cut.
- Claude AI sees every tick and decides CLOSE or HOLD — that's it
- Claude must understand that trades start negative (spread cost) and that's NORMAL
- Claude must give trades TIME — at least 10-15 seconds before considering close
- The only safety net: emergency -$80 cut if Claude API is completely down

### 4. MATCH MT5 REALITY
- The hawk's P&L MUST match what MT5 shows. No phantom profits.
- SELL trades: entry at BID, track against ASK
- BUY trades: entry at ASK, track against BID
- Always verify with `test_hawk_pnl.py` after any P&L changes
- Cross-check with MT5 trade history — if hawk says +$6 but MT5 says -$3, the hawk is lying

### 5. THE SYSTEM MUST SURVIVE WITHOUT ME
- "Claude go hawking" must bring everything back from any crash
- Sheriff auto-restarts all dead processes including TradingView
- Daemon auto-detects UHVs via CDP — no dependency on cron or Claude being idle
- All state persists to disk (.last_uhv_id, reflections.json, etc.)
- If I'm away for 10 days, the system trades autonomously

### 6. PROACTIVE, NOT REACTIVE
- Don't wait for me to notice problems. The Sheriff, the daemon, Claude — they should catch issues
- If no trades are being taken for hours, something is wrong — fix it automatically
- If we're losing every trade, stop and analyze before continuing
- If the chart is printing UHVs we're missing, that's a critical failure — scan faster

### 7. INFRASTRUCTURE I BUILT AND EXPECT TO WORK
- **Sniper Daemon**: auto-detects UHVs via CDP, watches price, fires trades, Claude AI manages
- **Silver Hawk Learner**: learns patterns from chart screenshots every 15 min
- **Sheriff Hawk**: hourly health checks, auto-restarts, has personality (angry, high BP)
- **Sexy Hawk**: sends WhatsApp reports every 2 hours with attitude
- **Meeting Room**: 9am + 9pm PKT daily meetings with all hawks
- **Intern Hawks**: daily internet research bots
- **Broadcast Module**: all WhatsApp messages go to both Shano and Zeeshan
- **Theory Engine**: visual chart analysis for trade validation

### 8. WHAT MAKES ME ANGRY
- Losing money on trades that would have been profitable if held longer
- Missing UHV signals that the indicator clearly printed on the chart
- Building 10 fancy engines while the basic trade execution is broken
- Explaining instead of fixing
- The system being "stable" but not taking any trades
- Saying "the market is quiet" when UHVs are appearing every few minutes

### 9. WHAT WOULD MAKE ME HAPPY
- 2 consecutive profitable trades
- The system catching every UHV the moment it appears
- Claude AI holding a trade through the spread cost and closing in actual profit
- Waking up to find the system traded overnight and made money
- Not having to babysit — the hawks handle everything

### 10. THE BOTTOM LINE
The indicator's own simulation shows 65% win rate, +$31/trade average, $67K all-time profit. The strategy WORKS. The breakouts DO move in the right direction. We just need to:
1. Catch every signal instantly
2. Enter at a clean price (not 5 points late)
3. Let Claude hold through the spread
4. Close when there's actual profit or clear failure

That's it. Stop overcomplicating it.
