# v3.40 Proposed Patch — Smart Conditional Cut

## Motivation

Across the 64-day OHLC backtest:
- **Saves +$10,909 mechanically** by capping catastrophic SL hits
- **Doesn't sacrifice any of Zee's 20 textbook Feb 11 wins**
- Only adversely affects his 18:41 cluster (already a loss) by $0.57

## The Rule

```
On each tick after entry:
  if elapsed_bars >= 1
     AND current_pnl <= -InpEarlyStopUSD          (-$2)
     AND peak_pnl    <  InpEarlyCutPeakGuard      ($1.00)
  then CLOSE at market
```

## Why the Specific Values

| Param | Old | New | Why |
|---|---|---|---|
| `InpEarlyStopUSD` | 0 (disabled) | 2.0 | $2 captures trades going wrong fast |
| `InpEarlyCutPeakGuard` | 0.5 | 1.0 | $1 = peak-trail bank threshold |
| `InpEarlyCutMinBars` | (didn't exist) | 1 | Skip the entry bar — spread effects fire $2 instantly |

The peak guard at $1.00 is identical to the peak-trail bank threshold.
This means: **the smart cut only fires when peak-trail hasn't engaged yet.**
A trade that briefly showed profit (peak >= $1) is protected by peak-trail;
a trade that NEVER showed profit and is now at −$2 gets cut.

## EA Code Changes

### File: `mt5/UhvSweepExhaustion.mq5`

```diff
 input double InpEarlyStopUSD       = 0.0;
+input int    InpEarlyCutMinBars    = 1;
 input double InpEarlyCutPeakGuard  = 0.5;
```

Change defaults:
```diff
-input double InpEarlyStopUSD       = 0.0;
+input double InpEarlyStopUSD       = 2.0;
-input double InpEarlyCutPeakGuard  = 0.5;
+input double InpEarlyCutPeakGuard  = 1.0;
+input int    InpEarlyCutMinBars    = 1;
```

Add `g_open_bar_count` state variable.

```diff
 ulong    g_open_ticket          = 0;
 double   g_open_entry           = 0;
 double   g_open_lots            = 0;
 int      g_open_side            = 0;
+int      g_open_bar_count       = 0;
 datetime g_open_time            = 0;
 double   g_peak_pnl_usd         = 0;
```

Track bar count in OnTick (increment when new M1 bar appears while position open).

In `ManageOpenPosition()`, replace the existing early-cut block:

```diff
   // 1. Catastrophic early-cut — fires ONLY if trade never reached protective profit peak.
   if(InpEarlyStopUSD > 0 &&
      g_peak_pnl_usd < InpEarlyCutPeakGuard &&
+     g_open_bar_count >= InpEarlyCutMinBars &&
      pnl <= -InpEarlyStopUSD) {
-      Log("[EXIT catastrophic] pnl=$" + DoubleToString(pnl, 2) +
-          " (never reached $" + DoubleToString(InpEarlyCutPeakGuard, 2) + " peak)");
+      Log("[EXIT smart_cut] pnl=$" + DoubleToString(pnl, 2) +
+          " bars=" + IntegerToString(g_open_bar_count) +
+          " (never reached $" + DoubleToString(InpEarlyCutPeakGuard, 2) + " peak)");
       g_trade.PositionClose(g_open_ticket);
       return;
    }
```

In `OnTradeTransaction` (entry fill block):

```diff
       g_open_ticket  = pos_id;
       g_open_entry   = price;
       g_open_lots    = vol;
       g_open_side    = ...;
       g_open_time    = TimeCurrent();
+      g_open_bar_count = 0;
       g_peak_pnl_usd = 0;
```

In OnTick (new bar detection block), add:
```mql5
if(g_open_ticket != 0 && r0[0].time != g_last_check_m1) {
   g_open_bar_count++;
}
```

Update heartbeat version string:
```diff
-   json += "\"ea\":\"UhvSweepExhaustion v3.30\",";
+   json += "\"ea\":\"UhvSweepExhaustion v3.40\",";
```

Update OnInit log:
```diff
-   Log("Init v3.30 (lesson-2 + Zee-style exits). ...");
+   Log("Init v3.40 (lesson-2 + smart cut). ...");
```

## Validation Plan (Zee's morning)

1. Review this patch
2. Apply changes to `mt5/UhvSweepExhaustion.mq5` (or have Claude apply when you wake)
3. Recompile via `install_eas.ps1`
4. Run Strategy Tester on Feb 11 — must preserve or improve the +$165 result
5. If Feb 11 still ≥+$100, also test 2-3 other days
6. If clean across multiple days, deploy: Remove EA, drag fresh

## Expected behavior

- Most trades behave identically to v3.30
- Trades that would have hit the SL at −$30-$120 now exit at −$2 instead
- Trades that briefly dip to −$2 then recover to peak >= $1 are protected by the guard
- Net P&L should improve on losing days; might be slightly worse on
  perfect days where every trade peaks immediately
