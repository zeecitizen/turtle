# P0 feasibility — PXTrader 2.0 (PrimeXBT web) as the Golden Gravity transport

2026-11-03, Chrome 156 with `--remote-debugging-port=9222` on a dedicated profile (`games/gold_runner/chrome_profile`; Chrome 136+ refuses remote debugging on the default profile), driven by `games/gold_runner/cdp.py`. No order was placed.

## The data path works without any API
The page keeps one WebSocket open and the game can read every frame of it through CDP (`Network.webSocketFrameReceived`). Frames are JSON `{"type":"EVENT","action":…,"body":…}`. In 20 s on the XAU/USD page:

| action | frames / 20 s | what it carries |
|---|---|---|
| `fx/market` | 49 (≈2.5 per second) | the chart symbol's quote: `a` ask, `b` bid, `lp` last, `s` spread, `h24` `l24` `v24`, `ch` `chPct`; `symId` 1019 = XAU/USD |
| `markets2` | 19 (≈1 per second) | bid / ask / lastTrade for every symbol |
| `bar` | 20 | the live 1-minute candle `[t, o, h, l, c, v]` of the chart symbol |
| `metrics` | 20 | account: balance, equity, `upl` (floating P&L), margin use |
| `positions` | 19 | open positions: symbol, side, qty (oz), openPrice, upl, sl, tp |
| `orders/buySell/impact` | 19 | the cost of the order currently in the panel: orderCost, marginImpact, fee, `resolution` (e.g. INSUFFICIENT_FUNDS) |
| `pfx/accounts2`, `mt5/accounts2` | 19 / 10 | the account list |

Spread on XAU/USD during the test: a constant **$0.33** (`s: 0.33`). Fee 0, financing 0 (as the panel shows). Quote cadence ≈ 2–3 updates per second: enough for the tilt (10-second slope) and the roof sign; the 50 ms stream in the GDD is faster than what the platform itself gets.

## Accounts seen
- **L1869984 — PXTrader (pfx) futures account, `type: LIVE`**, balance $0.45, equity $0.62, one open XAU/USD short of 0.01 oz at 3,945.35 (+$0.16). This is real money.
- MT5 accounts: 1351481 LIVE $0, 1362934 LIVE $0, **1365989 DEMO $10,386** — the only demo account is an MT5 one.

→ The web platform's futures account has no demo twin in this list; the demo money lives in MT5. Decision needed (see below).

## The order panel (mapped, not pressed)
- Amount input `#mat-input-0` (text, "0.01") with a unit menu button **"ounces"** beside it.
- Tabs Market / Limit / Stop (`XBT-TAB-BUTTON`, Market active). Margin type **Cross**, leverage **1000x** buttons. One-click toggle (`mat-mdc-slide-toggle-0`).
- **Take profit / Stop loss checkbox** `#mat-mdc-checkbox-1-input` — opens the TP/SL fields for the order.
- **Sell** / **Buy** buttons showing live bid / ask (3,929.03 Sell · 3,929.36 Buy).
- Positions table with per-row **Close** and **Close all**; TP/SL pencil per position; Hedge mode toggle.
- Before any click the `orders/buySell/impact` frame already tells the game the order's cost and whether it would be refused.

## Sizing (the number that matters)
`0.01` in the panel is **0.01 oz** (order value ≈ $39): a $1.00 move in gold = $0.01. The GDD's $1 coin needs **1 oz** (order value ≈ $3,930, margin ≈ $3.93 at 1000×). On a $0.45 balance the largest possible position is ≈ 0.1 oz. A "cent street" (0.1 oz, 10-cent coin, $1.00 stop distance) is the only round this account can play today.

## What is still unmeasured
A real open → modify SL → close round trip (fill latency, slippage, whether TP/SL set at order time land server-side). Not done: the only account reachable on this platform is live. Options: (a) fund the pfx account for a 0.1-oz cent-street test (≈ 10 cents at risk); (b) run the round-trip on the MT5 demo (1365989) through the PXBT MT5 terminal — the game's *orders* would then go to MT5 while its *picture* can still come from the web socket, but that mixes two accounts and is not the single-account design; (c) ask PrimeXBT whether the pfx platform has a demo mode.

## Live round trip — done (2026-11-03 ~04:47 server, authorised by Zee: live account L1869984, 0.01 oz)

1. **Close of Zee's open short** (0.01 oz from 3,945.23, +$0.18): Positions row → *Close* → confirmation dialog "Close position … at the first available market price" → *Close position*. Balance $0.45 → **$0.63**, position gone in the next `positions` frame.
2. **Buy 0.01 oz with TP/SL attached.** The panel's Buy button opens a confirmation popup (*Place market order*, with TP/SL, margin impact, costs) unless One-click is on; *Buy Market at …* sends one WebSocket frame:
   `{"type":"REQUEST","action":"orders/market/place","body":{"qty":0.01,"side":"BUY","symbol":"XAU/USD","takeProfit":{"price":3927.9},"stopLoss":{"price":3925.7}}}`

| t after the frame was sent | server event |
|---|---|
| **71 ms** | `orders/market/place` reply `{id: 2188562137, error: null}` |
| **104 ms** | `trading/activity` "Market order filled — Buy 0.01 XAU/USD @ 3929.28" |
| **120 ms** | "Stop loss linked to position" @ 3925.70 and "Take profit linked" @ 3927.90 (server-side, attached to the position) |
| 505 ms | "Take profit triggered / filled — Sell 0.01 @ 3928.98"; SL cancelled; position closed |

   The TP fired at once because it was typed while the ask was 3,926.7 and the order filled at 3,929.28 (the popup even warned "Take profit will trigger immediately. Set TP above 3,929.30"). Result −$0.003. Lesson for the game: **TP/SL must be computed from the live ask at the moment the order is sent**, not at the moment the coin is picked up — the backend builds the frame, the picture never does.

## Verdict
- **PXTrader 2.0 is a workable transport without any API**: quotes, candles, account and positions stream on the page's WebSocket; an order is one JSON frame; fills, linked SL/TP, triggers and cancels come back as `trading/activity` events within ~100 ms. That is faster than anything the game's picture needs.
- Next build step (P1 bridge): send `orders/market/place` (and the modify/close requests — still to capture: SL move, partial close, close) **directly through the page's own socket** from the backend via CDP, instead of clicking buttons; keep the page open and logged in as the session holder. Capture the frames for *modify SL*, *close position*, *close partial* the same way before writing the bridge.
- Coin size for now (Zee): **0.01 oz**, i.e. a $1.00 move in gold = $0.01; the $1.00 stop distance risks one cent; spread $0.33 = 0.33 cents per round.
