# PXTrader 2.0 (PrimeXBT web) — the wire protocol Golden Gravity uses

Captured 2026-11-03 from the live page `https://primexbt.com/my/trade/futures/l1869984/market/XAU%2FUSD` over CDP (Chrome 156,
`--remote-debugging-port=9222`, dedicated profile `games/gold_runner/chrome_profile`). Every request below was sent and answered for real
(0.01 oz trades authorised by Zee). **Never log or store the socket URLs: they carry the session JWT.**

## Transport
- The page holds **two WebSockets** (find them with `Runtime.queryObjects(WebSocket.prototype)`, see `cdpcore.PageSockets`):
  - socket `pws` — `wss://api.primexbt.com/v2/pws/...` platform: `mt5/accounts2`, `rates`, wallet, rewards.
  - socket `fws` — `wss://api.primexbt.com/v2/fws/?accountId=l1869984...` **futures: quotes, bars, account, positions, orders. Everything below.**
  - Identify `fws` by `url` containing `/v2/fws/`. It is index 1 today; do not hard-code the index.
- Frames are JSON text. Client → server: `{"type":"REQUEST","rid":<int>,"action":"…","body":{…}}` (or `"type":"SUBSCRIPTION"`).
  Server → client: `{"type":"RESPONSE","rid":<same>,"action":"…","body":{…}}` or, on failure, `{"type":"RESPONSE","rid":…,"action":"…","error":{"code":"POSITION_NOT_FOUND","description":"120: Not found position #1 …"}}`;
  pushes are `{"type":"EVENT","action":"…","body":{…},"sid":<sub id>,"aid":<seq>}`.
- **Our rids start at 900000** (the page counts up from ~1). Sending our own frames on the page's socket works; the page ignores unknown rids.
- All responses arrive on the same socket; read them with CDP `Network.webSocketFrameReceived` (enable `Network` first).

## Market data (pushed by the page's own subscriptions; we may add our own)
| action | body | notes |
|---|---|---|
| `fx/market` (EVENT) | `{"symId":1019,"a":ask,"b":bid,"lp":last,"s":spread,"h24","l24","v24","ch","chPct","pr":0.01,"st"}` | the chart symbol's quote, ~2.5/s. `symId 1019` = XAU/USD. Spread was a constant 0.33. |
| `markets2` (EVENT) | `{"data":[{"symbol":"XAU/USD","ask","bid","lastTrade","change"},…]}` | all symbols, ~1/s |
| `bars` (REQUEST → RESPONSE) | req `{"symbol":"XAU/USD","bar_size":"1M","to":<unix s>,"limit":329,"askOhlc":false}` → `{"data":[[t,o,h,l,c,v],…]}` | 1-minute history, bid OHLC, oldest first; `t` = bar open, unix s |
| `bar` (SUBSCRIPTION → RESPONSE + EVENTs) | req `{"symbolId":1019,"barSize":"1M","askOhlc":false}` → RESPONSE `{"data":[t,o,h,l,c,v]}` with `sid`, then EVENTs with the same `sid` | the live forming bar, updated every tick. The page's own chart subscription uses its chart's bar size (it was 15M) — subscribe our own 1M |
| `orders/buySell/impact` (EVENT) | `{"buyImpact":{orderCost,marginImpact,fee,resolution:"OK"/"INSUFFICIENT_FUNDS",liqPrice,minOrderSize:0.01,…},"sellImpact":{…}}` | the cost of the order in the page's panel (not ours) |

## Account
| action | body |
|---|---|
| `metrics` (EVENT, ~1/s) | `{"accountId":"L1869984","balance","equity","upl","usedMargin","availableMargin","openPositions","openOrders","demo":false,"positionMode":"HEDGE",…}` |
| `pfx/accounts2` (EVENT) | `{"data":[{"accountId","type":"LIVE","balance","equity","upl","specName":"PXTrader 2.0",…}]}` |

## Positions and orders
- `positions` (EVENT, ~1/s): `{"data":[<aggregate per side>],"positionMode":"HEDGE"}`. In hedge mode each aggregate has `"id":0` and the real
  positions in **`subPositions`**: `{"id":15394511,"side":"BUY","qty":0.01,"openPrice":3926.59,"markPrice":<bid for a long>,"upl","stopLossOrderId","stopLossPrice","takeProfitOrderId","takeProfitPrice","openTime","closeable":true,…}`.
  Use `subPositions`; the aggregate's `openPrice` is not the fill. `"data":[]` = flat.
- `orders/active2` (EVENT): the working orders, e.g. `{"id":2188572786,"type":"STOP_LOSS","status":"AWAITING","side":"SELL","qty":0.01,"triggerPrice":3923.71,"positionId":15394511,"protective":true}`.
- `trading/activity` (EVENT): human-readable confirmations — the fastest settlement signal:
  `{"level":"SUCCESS","title":"Market order filled","body":"Buy 0.01 XAU/USD @ 3926.59"}`,
  `"Stop loss linked to position"` (`"15394511: Stop loss #2188572786 sell XAU/USD @ 3923.71"`), `"Take profit linked to position"`,
  `"Stop loss replaced"`, `"Stop loss cancelled"`, `"Take profit cancelled"`, `"Take profit triggered"`, `"Take profit filled"` (`"Sell 0.01 XAU/USD @ 3928.98"`),
  presumably `"Stop loss triggered"` / `"Stop loss filled"` likewise.
- `report/orders2` (REQUEST → RESPONSE): `{"limit":100,"offset":0,"fromExecutedAt":<unix s>,"toExecutedAt":2114467199.999,"symbol":"XAU/USD"}` →
  executed orders newest first: `{"id","type":"MARKET"|"STOP_LOSS"|"TAKE_PROFIT","status":"EXECUTED"|"CANCELLED","side","qty","executedPrice","executedQty","rpl":<realised P&L, USD>,"fee","positionId","closeReason":"EXECUTION"|"REPLACED"|…,"executedAt"}`. **The settlement source.**

## Trading requests (all verified live)
| what | request body (action) | reply | latency seen |
|---|---|---|---|
| open at market with SL/TP attached | `orders/market/place` `{"qty":0.01,"side":"BUY"\|"SELL","symbol":"XAU/USD","takeProfit":{"price":3929.71},"stopLoss":{"price":3923.71}}` | `{"id":<order id>,"error":null}`; then activity "Market order filled @ x", "Stop loss linked", "Take profit linked" | 71–183 ms reply, fill +30 ms |
| move SL or TP | `positions/id/protective-order/set` `{"positionId":15394511,"price":3924,"type":"STOP_LOSS"\|"TAKE_PROFIT"}` | `{}`; activity "Stop loss replaced" | 62 ms |
| check a SL/TP before setting | `positions/id/protective-order/impact` `{"price":3924,"positionId":15394511}` | `{"profitLoss":-0.03,"resolution":"OK","resolutionLevel":"INFO"}` | 35 ms |
| close all or part of a position | `positions/id/close` `{"positionId":15394511,"qty":0.01}` (qty < position qty = partial; min step 0.01) | `{}`; activity "Stop loss cancelled", "Take profit cancelled", "Market order filled — Sell 0.01 … @ 3924.98" | 75 ms |
| server time | `time` `{}` | `{"time":<unix ms>}` | — |

Errors come back as a top-level `error` object with `code` and `description` (e.g. `POSITION_NOT_FOUND`).

## Rules learned the hard way
1. Compute SL/TP **from the live quote at the moment the request is sent**. A TP typed off a stale quote filled instantly (−$0.003).
2. A long's SL must be below the bid, its TP above the ask (mirror for a short). The server accepted an already-crossed TP and filled it at once — it does not protect you.
3. `minOrderSize` 0.01 oz: a 0.01-oz position cannot be partially closed. Splitting the coin needs ≥ 0.02 oz.
4. Hedge mode: several positions per side can coexist; always address the sub-position `id`.

## Added 2026-11-03 ~07:57 (read-only probes by Claude after the first LiveFeed read-only run)
- **With no open position the server does NOT push `metrics`, `positions` or `orders/active2`** (the page subscribed at load; the
  server pushes on change only). A LiveFeed that starts flat therefore has no balance. **Seed and refresh them with REQUESTs**
  (read-only, verified): `{"type":"REQUEST","rid":…,"action":"metrics","body":{}}` → RESPONSE body = the same object as the
  `metrics` EVENT (balance, equity, availableMargin, …); `"positions"` → `{"accountId","data":[…],"positionMode":"HEDGE"}`;
  `"orders/active2"` → `{"data":[…]}`. Re-request every ~10 s and after every trade. A SUBSCRIPTION for these returns
  `DUPLICATE_SUBSCRIPTION` (the page owns it) — do not subscribe.
- `pfx/accounts2` is unknown on the futures socket (it lives on the platform socket); use `metrics` instead.
- **Economic calendar:** REST, not WebSocket. From the page context:
  `fetch('https://api.primexbt.com/v2/economic-calendar/upcoming', {method:'POST', credentials:'include',
   headers:{'content-type':'application/json', Authorization:'Bearer ' + localStorage.getItem('prm-token')},
   body: JSON.stringify({importance:['HIGH'], limit:20})})` → `{"data":[{"eventId","eventTime":<unix s>,"eventTitle","importance":"HIGH",
  "regionCode":"US"|"TR"|…,"currency","forecast","previous","actual",…}]}` (401 without the Bearer header). The token never leaves the
  page: do the fetch inside Runtime.evaluate and return only the parsed events. "HIGH" covers every country (e.g. Turkish CPI):
  filter by region for gold (default `["US"]`). `economic-calendar/events` takes a paged body; `upcoming` is enough for the game.
- fx/market `st` is the tick direction ("SAME"/"UP"/"DOWN"), not a market-status flag; market closed = quotes stop.
- Zee's account balance read $21.48 at 07:57 (a top-up since the P0 tests left $0.61).

## Added 2026-11-03 ~22:20 UTC — the calendar, take two
- Our own page-context `fetch` of `/economic-calendar/upcoming` or `/events` now returns **400 WRONG_ARGS** for every body, even with the
  Bearer token and the `X-Auth-Guard` / `X-Client-Version` / `X-Client-Time` headers copied from the app. The app's own requests still
  get 200. Do not hand-craft calendar requests.
- What works: the app's chart (a same-origin blob iframe, TradingView) POSTs
  `/v2/economic-calendar/events` `{"symbolId":1019,"from","to" (~40-day window),"importance":["HIGH"],"isPlottable":true,"limit":200,"offset":0}`
  whenever its resolution changes or it loads. `symbolId:1019 + isPlottable` = only events relevant to XAU/USD (all US today).
  LiveFeed (1) captures that XHR passively (Network.requestWillBeSent → loadingFinished → getResponseBody), (2) refreshes it every
  30 min with **`Network.replayXHR(requestId)`** (re-sent byte for byte with the app's headers → 200), and (3) if the app has not asked
  since we attached, **nudges the chart once**: clicks another resolution button inside the iframe and straight back to the active
  one (`button[aria-checked=true]`; class `isActive-…`, beware `isInteractive-…`). Verified: 56 events captured in 5 s, the chart back on
  15m. Config `calendar_nudge` (default true) turns the nudge off.
