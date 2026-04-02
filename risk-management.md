# Turtle Trader Desk — Risk Management Deep Dive

> **Who is this for?** A beginner trader who has heard words like "stop loss" and "trailing stop" but wants to understand *why* the system protects you the way it does, in plain language.

---

## The Big Picture: Why Risk Management Exists

Every trade you take has two possible outcomes: it works, or it doesn't. The job of risk management is not to prevent losses — losses are a normal part of trading. Its job is to make sure that when you're wrong, you lose a *small, controlled* amount, and when you're right, you keep as much of the profit as possible.

On a 1-minute Gold chart, things move fast. A bad trade can go 30–50 pips against you in under 10 seconds. Without automated protection layers, a single bad trade can wipe out the gains from your last 5 good trades.

This system has **twelve protection layers**, each designed to catch a different type of failure. They run in a strict priority order — the most urgent checks fire first.

---

## The Twelve Exit Layers (Priority Order)

### Layer 1 — MAE Emergency Stop (tick-based)
**What it protects against:** A trade immediately running hard against you before any other layer can react.

**How it works:** Every single price tick (not just on bar close), the system checks: "How far has this trade moved against me in pips?" and "How much unrealised dollar loss am I sitting on right now?" If either crosses the threshold — close the trade immediately.

- Default: 60 pips OR -$40 loss (whichever comes first)
- Fires on every realtime tick — fastest possible response
- Disabled once breakeven fires (at that point, the worst case is a tiny loss or small profit, so no emergency needed)

**Why 60 pips?** On XAUUSD 1-minute, a genuine UHV breakout should *never* go 60 pips against you. If it does, the breakout was fake and you need out — full stop. 60 pips is about $72 on 1 standard lot, which exceeds the 4% risk per trade target on a $900 account.

**Label:** `🚨 #N MAE Stop — -$X.XX`

---

### Layer 2 — Kill Timer (tick-based)
**What it protects against:** A trade that just... sits there. Not moving, not hitting stop loss, not hitting TP. Just drifting in limbo eating up your mental bandwidth and potentially drifting into the next news event.

**How it works:** Every tick, the system checks the wall-clock time since the trade fired. If the trade has been open for longer than 90 seconds and hasn't hit TP yet — close it.

- Default: 90 seconds
- Fires on every realtime tick
- Disabled once breakeven fires (once you're protected, let the runner run)

**Why 90 seconds?** A UHV breakout on Gold resolves in 5–20 seconds under normal conditions. 90 seconds is the outer boundary for "still valid." Anything beyond that and you're no longer in a breakout — you're in a dead zone where the next data release or broker spike can hit you.

**Label:** `⏱ #N Kill Timer 93s — +$X.XX / -$X.XX`

---

### Layer 3 — Daily Loss Limit Hard Shutdown (tick-based)
**What it protects against:** A bad day turning into a wipe-out. Chasing losses is the #1 cause of blown accounts.

**How it works:** Two thresholds:
- **Soft limit** (default 2% of capital): blocks new entries, but lets existing trades play out normally
- **Hard limit** (default 5% of capital): closes ALL open trades immediately, regardless of breakeven status, AND blocks new entries for the rest of the day

**Why two levels?** The soft limit is a yellow flag — "slow down, something is off today." The hard limit is a red flag — "stop completely, this is a bad day." Forcing a pause after 5% daily drawdown is what separates funded traders from blown accounts.

**Label:** `💀 #N DLL Hard — -$X.XX`

---

### Layer 4 — Partial Take-Profit + Runner (tick-based)
**What it protects against:** Giving back a large winning trade because you were greedy.

**How it works:** When the trade reaches `ptpPips` profit (default: off), close `ptpPct`% of the position. Move the stop loss to breakeven for the remaining portion. Let the rest run.

- Closes partial lots: e.g. close 50% at +40 pips, run the rest to the R:R target
- After partial close, the remaining position is locked at breakeven — the worst case is now $0 (just the spread cost)
- Invalidation exit is naturally disabled for the runner (breakeven flag stops it)

**Label:** `💰 #N Partial TP +40p — +$X.XX (50%) → Runner at BE`

---

### Layer 5 — Invalidation Exit (bar-close)
**What it protects against:** A trade that *looked* valid at entry but the underlying reason for the trade is now gone.

**How it works:** Three modes (choose one):
- **UHV Range:** Close if price re-enters the entire high-volume candle range. The candle that triggered your entry is no longer holding as support/resistance.
- **UHV Midpoint:** Close if price crosses the midpoint of the UHV candle (open + close) / 2. VSA principle: if price can't hold above the halfway point of the absorption candle, institutions weren't actually buying — they were distributing.
- **Breakout Body:** Close if price crosses the midpoint of the breakout candle. The candle that "broke out" has lost more than 50% of its body — the breakout is failing.

- Only fires on bar close (prevents fake-outs from wicks that immediately recover)
- Disabled once breakeven fires

**Default mode:** UHV Midpoint (Session 33 change, based on VSA theory)

**Label:** `❌ #N Invalidation [UHV Midpoint] — -$X.XX`

---

### Layer 6 — Structural SL (bar-close)
**What it protects against:** The trade crossing the technical level that defined the trade in the first place.

**How it works:** When you enter a UHV breakout, the stop loss is placed below the breakout wick (for a buy) or above it (for a sell). This level is the *structural* reason the trade exists — price should NOT go back there. If it does on a bar close, the setup has definitively failed.

**Why this is separate from Layer 8 (Hard SL):** The hard SL sent to MT5 is 120 pips away — a risk-management backstop. The structural SL is usually only 20–40 pips away — a logic-based exit. Layer 6 sends a `closelong` command to MT5 at the logical level, well before the hard SL.

- Bar-close only (prevents false exits from wicks)
- Disabled once breakeven fires

**Label:** `🔻 #N Structure SL — -$X.XX`

---

### Layer 7 — Opposite UHV Candle Exit (bar-close)
**What it protects against:** Smart money flipping against your position.

**How it works:** After entry, if a high-volume candle (volume >= 2× the 20-bar average) closes in the *opposite* direction to your trade, this is a high-conviction reversal signal. The same institutional signature that created your entry signal now says the opposite.

- Volume threshold: 2× average volume (configurable via `ouK`)
- Only fires on a confirmed bar close with proper direction
- Disabled once breakeven fires

**The logic:** UHV candles mark institutional activity. A sell-side UHV candle appearing during your buy trade means large sellers have entered above your position. They know something you don't.

**Label:** `🔄 #N Opposite UHV — -$X.XX`

---

### Layer 8 — Breakout Failure Pattern Exit (bar-close)
**What it protects against:** The classic "bull trap" / "bear trap" — where price breaks a level, sucks in retail traders, then reverses.

**How it works:** After entry, the system watches for `bfBars` bars (default: 3) to see if price extends at least `bfPips` pips (default: 5) beyond the breakout level. If the window expires without extension AND price closes back inside the level — the breakout was fake.

- One-shot: once extension is confirmed, this exit never fires
- Bar-close only
- Disabled once breakeven fires

**Example:** You buy at the breakout of a UHV high at 2680.00. If after 3 bars the price has never been above 2680.50, and the current close is 2679.80 (back below 2680.00) — the breakout failed. Exit now before it dumps further.

**Label:** `💥 #N BF Pattern — -$X.XX`

---

### Layer 9 — Volatility Collapse Exit (bar-close)
**What it protects against:** Being trapped in a dead trade where momentum has evaporated.

**How it works:** ATR(14) is recorded at the moment of entry. If at any subsequent bar close the current ATR(14) drops below `vcFact`% (default: 60%) of that entry ATR, volatility has collapsed — the market has gone into "wait and see" mode.

- ATR stored in `_tATE` array per trade
- Bar-close only
- Disabled once breakeven fires

**Why ATR?** ATR (Average True Range) measures how much the market has been moving on average. A high-ATR breakout that drops back to low-ATR conditions means the breakout energy is gone. Either an exit happens now or you wait for the next news event, which could go either way.

**Label:** `📉 #N Vol Collapse — -$X.XX`

---

### Layer 10 — Volume Drop Exit (bar-close)
**What it protects against:** Entering on a high-volume candle but the follow-through has no institutional participation.

**How it works:** On the second bar after entry (entry bar itself is excluded — it may legitimately have low volume depending on when the signal fires), if volume drops below `vdFact`% (default: 50%) of the 20-bar volume average, institutions aren't participating in the follow-through.

- Fires from bar_index > entryBar + 1 (skips entry bar)
- Bar-close only
- Disabled once breakeven fires

**The logic:** A real breakout on Gold requires continuous institutional buying. If the bar after your entry shows lower-than-average volume, you bought into a retail fake-out. Exit before the lack of follow-through becomes a full reversal.

**Label:** `📊 #N Volume Drop — -$X.XX`

---

### Layer 11 — Micro-Structure Break Exit (bar-close)
**What it protects against:** The short-term price structure breaking down after entry.

**How it works:** After entry, the system finds the lowest low (bull trade) or highest high (bear trade) of the last `msLb` bars (default: 3). If price closes `msBuf` pips (default: 3) beyond that level — the micro-structure has cracked.

**Why this matters:** A healthy breakout prints higher lows (on a buy). Each bar should close above the previous bar's low. The moment this stops happening — you're in a reversal, not a breakout. Exit while the loss is still small.

- Bar-close only
- Only active after `msLb` bars have passed (needs enough history to form a swing)
- Disabled once breakeven fires

**Label:** `🏗️ #N Micro-Structure — -$X.XX`

---

### Layer 12 — Hard SL Simulation (tick-based)
**What it protects against:** The MT5 hard stop loss triggering without Pine knowing about it — causing Pine to show a "win" on a trade MT5 already closed as a loss.

**How it works:** When invalidation mode is on, MT5 uses a 120-pip hard stop loss instead of the structural SL. Pine simulates this: if price reaches the 120-pip level, mark the trade as closed in Pine with the correct P&L.

**This is Pine-side bookkeeping, not a new close command.** MT5 has already closed the trade via its own internal hard SL. Pine just needs to record it correctly in the stats.

**Label:** `🔴 #N Hard SL — -$X.XX`

---

### Layer 13 — Trail Stop (tick-based, MT5-managed)
**What it protects against:** Giving back a large winner because you stayed in too long.

**How it works:** Once the trade is `pcTTrig` pips in profit (default: 60 pips), MT5 activates a trailing stop that maintains the stop loss `pcTDist` pips (default: 20 pips) behind the highest price reached. It adjusts every `pcTStep` pips (default: 3 pips) of additional gain.

**Example:**
- Enter buy at 2680.00
- Price rises to 2686.00 (+60 pips) → trail activates, SL moves to 2684.00 (-20 pips from peak)
- Price rises to 2689.00 → SL moves to 2687.00
- Price falls to 2687.00 → trade closes at +70 pips

Pine simulates this for statistics. MT5 handles it in real execution.

**Label:** `🏃 #N Trail Stop — +$X.XX / -$X.XX`

---

### Layer 14 — Wick SL (bar-close fallback)
**What it protects against:** Everything the above layers missed.

**How it works:** The traditional stop loss check. If the bar low (bull) or bar high (bear) touches the structural stop loss level — mark the trade closed.

- When invalidation mode is on, this becomes the `effectiveSL` (120-pip hard level), not the structural wick level. This prevents double-counting with Layer 6.
- Only fires after ALL other exit checks have been exhausted.

---

### Layer 15 — Breakeven (tick-based)
**Not an exit layer, but a protection upgrade.** When the trade reaches `uBEPct`% of the TP distance (default: 10%), the stop loss is moved to entry + spread. From this point on, the worst case is $0 (a tiny spread cost). Layers 5, 6, 7, 8, 9, 10, 11 are all disabled after breakeven fires — they become irrelevant.

---

### Layer 16 — Take Profit
**The happy path.** When price reaches the calculated TP level, the trade closes as a win. The R:R ratio default is 7:1 — you risk 1 unit to make 7 units.

---

## Entry Filters (Pre-Trade Risk Management)

Beyond exit layers, the system also blocks entries before they happen:

### Spread Spike Filter
Blocks entries when the current 1-minute candle range exceeds `ssPips` pips. A 50-pip 1m candle is a news spike or liquidity event — breakouts during these are traps because the spread has already exploded and the reversal is instant.

### Volatility Blocker
Blocks entries when the current bar's true range is more than 4× the 14-bar ATR baseline. Prevents entering during chaotic market conditions.

### Max Trades Per Hour
No more than 3 entries in any rolling 60-minute window. Also enforces 5-minute minimum gap between entries. Prevents overtrading during choppy conditions.

### No-Trade Windows
Specific UTC time windows when trading is blocked:
- **19:00–21:00 UTC** (default ON): Volume fade / Friday close — institutional desks are shutting down
- **21:00–23:00 UTC** (off by default): NY Rollover — spreads spike 5–10×
- **23:00–03:00 UTC** (off by default): Late Asia lull — slow drift, high fakeout
- **04:00–07:00 UTC** (off by default): Pre-London trap — thin liquidity

### Time-of-Day Kill Switch
**Force-closes** open trades when a no-trade window begins (rather than just blocking new entries). Prevents being caught in a rollover spike with an open position.

---

## The Full Layer Priority Stack

```
1.  MAE Emergency Stop       — tick    — 60 pips OR -$40
2.  Kill Timer               — tick    — 90 seconds
3.  Daily Loss Hard Shutdown — tick    — 5% of capital
4.  Partial Take-Profit      — tick    — (off by default)
5.  Invalidation Exit        — bar-close — UHV Midpoint mode
6.  Structural SL            — bar-close — breakout wick level
7.  Opposite UHV Exit        — bar-close — (off by default)
8.  Breakout Failure Exit     — bar-close — (off by default)
9.  Volatility Collapse Exit — bar-close — (off by default)
10. Volume Drop Exit         — bar-close — (off by default)
11. Micro-Structure Break    — bar-close — (off by default)
12. Time-of-Day Kill         — tick    — (off by default)
13. Hard SL Simulation       — tick    — Pine bookkeeping
14. Trail Stop               — tick    — MT5-managed
15. Wick SL                  — bar-close — structural fallback
16. Breakeven                — tick    — SL upgrade, not exit
17. Take Profit              — tick    — the happy ending
```

---

## Why Bar-Close vs Tick-Based Matters

**Tick-based checks** (MAE, Kill Timer, DLL, Trail, TP, BE): These check on every single price update. They're fast and aggressive. Used when the threat is real-time: "price is at a dangerous level *right now*."

**Bar-close checks** (Invalidation, Structural SL, Opposite UHV, Breakout Failure, Volatility Collapse, Volume Drop, Micro-Structure): These only fire when a 1-minute bar fully closes. They require *confirmation*. A wick might touch a level during the bar, but price recovers before close — bar-close filters prevent you from getting stopped out on a fake spike.

The golden rule: **logic-based exits wait for bar close. Emergency exits fire immediately.**

---

## The Architecture Truth

Every exit layer follows the same pattern:
1. Check all higher-priority exits didn't already fire (`not _maeExited`, `not _killExited`, etc.)
2. Check the trade isn't already closed (`not array.get(_tSH, _ti)`)
3. Check the trade is past the entry bar (`bar_index > _entryBar`)
4. If condition met: set `_tSH[i] = true`, update P&L stats, draw label, send `closelong/closeshort` alert

Once `_tSH[i]` is set to `true`, ALL downstream monitoring blocks for that trade are skipped. This ensures exactly one exit per trade.

---

*Last updated: 2026-04-02 (Session 35)*
*Strategy: UHV Breakout, XAUUSD 1m, PineConnector → MT5*
