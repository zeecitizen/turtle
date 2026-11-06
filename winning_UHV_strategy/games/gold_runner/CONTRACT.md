# Golden Gravity — BUILD CONTRACT (v1, 2026-11-03)

The single source every build agent follows. The game design is `REQUIREMENTS.md` (v2.2, read it fully); the broker wire protocol is
`PROTOCOL.md`; this file fixes the code-level contract: files, ownership, interfaces, data shapes, coordinates, style, and safety.
Where this file and REQUIREMENTS.md disagree on a *number or a shape*, this file wins; on *what the game is*, REQUIREMENTS.md wins.

Working directory: `C:\Users\zeesh\turtle\games\gold_runner`. Python: `C:\Users\zeesh\AppData\Local\Programs\Python\Python312-arm64\python.exe`
(stdlib + `websocket-client`; no other pip installs). Browser code: plain ES modules, no build step, no CDN, no frameworks.

---------------------------------------------------------------------------------------------------------------------------------
## 0. SAFETY — READ FIRST (real money)

* Chrome on port **9222** (profile `chrome_profile/`) holds Zee's **live PrimeXBT session** (account L1869984, real money, ~$20).
  **Zee 2026-11-05: "i want you to have full access to that chrome for testing/debugging/building for now. the money in account 20 USD is
  not much to frown upon."** Claude may attach to it, open and screenshot tabs, navigate, click and debug there. Take care not to close or
  reload the PrimeXBT tab while the live game runs (its price feed freezes until the page is back).
* Engine and frontend tests still prefer `--mode sim` and the isolated headless Chrome via `tools/shoot.py` (port **9333**) when a fresh,
  throw-away browser is enough.
* Never print, log, record or store PrimeXBT WebSocket URLs (they carry the session JWT). Recordings strip them.
* The game may only send a trading frame as the direct consequence of a player action (shoot, anvil, wall, haggle, machete, merchant,
  eject, kill) or the documented automatic exits (session end / weekend). Nothing else trades. Wooden (Alley), sim and replay rounds never
  reach the broker.
* The game touches **only the position it opened** (by sub-position id). Zee trades this account by hand too: never close, modify or
  count a position the game did not open. The kill switch closes only the game's position.

---------------------------------------------------------------------------------------------------------------------------------
## 1. Files and ownership (each agent writes ONLY its files)

```
games/gold_runner/
  REQUIREMENTS.md PROTOCOL.md P0_FEASIBILITY.md CONTRACT.md      (read-only for agents)
  cdpcore.py              (exists; read-only)  CDP session + page sockets
  tools/shoot.py          (exists; read-only)  isolated headless screenshots + scripted input
  config.json             [B-ENGINE]  all tunables (section 5)
  feeds.py                [B-FEEDS]   Feed interface, LiveFeed, SimFeed, ReplayFeed, recorder
  engine.py               [B-ENGINE]  rules, round state machine, tallies, logs (authoritative game state)
  server.py               [B-ENGINE]  HTTP static + SSE + actions; CLI modes
  tests/test_engine.py    [B-ENGINE]  engine tests on SimFeed (python -m unittest)
  tests/test_feeds.py     [B-FEEDS]   SimFeed / ReplayFeed tests
  start_game.bat          [B-ENGINE]  one double-click start (see section 3)
  static/index.html       [F-CORE]
  static/css/style.css    [F-CORE]
  static/js/palette.js    (exists; read-only) colours, line weights, shared helpers
  static/js/net.js        [F-CORE]    SSE client, clock offset, link age, act()
  static/js/main.js       [F-CORE]    loop, camera/layout, input, screens, fixture mode, composition of every draw call
  static/js/screens.js    [F-CORE]    loading, lobby, settlement scene, locked/jam/shutters, safety screen (DOM), alley dressing
  static/js/art.js        [F-ART]     every character and prop (section 8.2)
  static/js/fx.js         [F-ART]     particle pools + screen shake (section 8.4)
  static/js/world.js      [F-WORLD]   sky, sun, weather, skyline, terrain, chasms, fog, season band, grading (section 8.3)
  static/js/audio.js      [F-AUDIO]   WebAudio synthesiser, the sound bible (section 8.5)
  static/gallery_art.html   [F-ART]   renders every art.js/fx.js function in every state (visual proof)
  static/gallery_world.html [F-WORLD] renders every world.js function in every env (visual proof)
  static/gallery_audio.html [F-AUDIO] one button per sound
  static/fixtures/*.json   (exists; read-only) snapshot fixtures, one per phase (section 7.4)
  rounds/                  runtime: one JSON per finished round (engine writes)
  state/                   runtime: settings.json, jar/tallies cache (engine writes; git-ignored)
  recordings/              runtime: recorded live feeds (git-ignored)
```

---------------------------------------------------------------------------------------------------------------------------------
## 2. Architecture

```
 PXTrader page (Chrome :9222) ──CDP──> feeds.LiveFeed ─┐
 synthetic market + broker ──────────> feeds.SimFeed  ─┼─> engine.Engine (authoritative state, rules, logs) ──> server.py ──SSE──> browser
 recorded frames ─────────────────────> feeds.ReplayFeed┘          ^                                            <──POST /api/act──
```
* The **backend owns everything that is money**: orders, the floating result, settlement (read from the broker), limits, the round state.
* The **frontend owns picture and sound** and never computes a price or a result: it draws the snapshot, interpolates between
  snapshots for smoothness (runner x, tilt), and sends player intents.

---------------------------------------------------------------------------------------------------------------------------------
## 3. Run modes and commands

```
python server.py --mode sim     [--port 8790] [--seed 7] [--speed 1.0]   # synthetic market + simulated broker (default for all testing)
python server.py --mode replay --file recordings/X.jsonl [--speed 1]     # replays recorded frames; REPLAY across the sky; wooden rounds only
python server.py --mode live    [--record]                               # attaches to the PXTrader page on :9222 (Claude only)
open http://127.0.0.1:8790/                 the game
open http://127.0.0.1:8790/?fixture=NAME    the client renders static/fixtures/NAME.json with no server (frontend dev / screenshots)
```
`start_game.bat`: if nothing answers on 127.0.0.1:9222, starts Chrome with `--remote-debugging-port=9222 --user-data-dir=<repo>\games\gold_runner\chrome_profile https://primexbt.com/my/trade/futures/l1869984/market/XAU%2FUSD`
(Zee logs in there once); then `python server.py --mode live`; then opens `http://127.0.0.1:8790/` in the default browser.
A second `start_game_sim.bat` starts sim mode only.

---------------------------------------------------------------------------------------------------------------------------------
## 4. The Feed interface (feeds.py) — B-FEEDS implements, B-ENGINE consumes

```python
class Feed:
    mode: str                     # "live" | "sim" | "replay"
    can_trade: bool               # True for live and sim; False for replay (orders refused with error "REPLAY")
    def start(self) -> None       # begin streaming (threads); idempotent
    def stop(self) -> None
    def subscribe(self, fn)       # fn(event: dict) called from the feed thread for every event below
    def state(self) -> dict       # thread-safe snapshot, shape below
    # trading - all synchronous, all with timeout, all return {"ok": bool, "error": str|None, "rtt_ms": float, ...}
    def place(self, side: int, qty: float, sl: float, tp: float, timeout=5.0) -> dict   # side +1 BUY / -1 SELL; returns "order_id", "position_id" (resolved, may take <1 s), "fill_price"
    def set_protective(self, position_id: int, kind: str, price: float, timeout=5.0) -> dict   # kind "STOP_LOSS"|"TAKE_PROFIT"
    def check_protective(self, position_id: int, price: float, timeout=3.0) -> dict          # -> "resolution", "profitLoss"
    def close(self, position_id: int, qty: float, timeout=5.0) -> dict                       # qty < position qty = partial
    def orders_report(self, since_ts: float, timeout=5.0) -> list[dict]                      # report/orders2 rows (executedPrice, rpl, fee, positionId, type, closeReason, executedAt)
```
`state()` shape:
```python
{ "ok": bool, "reason": str|None,              # ok = quotes fresh (< feed_dead_s) and connection alive
  "quote": {"bid","ask","mid","spread","ts","st"} | None,     # ts = local unix s of receipt; st = PX status field
  "tick_count": int,                            # monotonic count of quote updates (client plays a footstep per increment)
  "ticks": [[ts, bid, ask], ...],               # last 120 s of quotes
  "bars": [[t, o, h, l, c, v], ...],            # 1-minute BID bars, oldest first, last >= 300 (history + live forming bar last)
  "h24", "l24", "ch24",                         # 24h high/low/change from fx/market (ch = change)
  "account": {"id","type","balance","equity","upl","available","currency"} | None,
  "positions": [ {"id","side":+1|-1,"qty","open_price","mark","upl","sl","tp","sl_order","tp_order","open_time"} ],   # sub-positions only
  "orders": [ {"id","type","status","side","qty","trigger","position_id"} ],
  "activity": [ {"t","title","body"} ],         # last 50 trading/activity messages
  "news": [ {"t","title","impact","country"} ], # economic calendar if captured (may be [])
  "market_open": bool }
```
Events passed to subscribers: `{"type":"quote",...}`, `{"type":"bar","bar":[...],"closed":bool}`, `{"type":"positions","positions":[...]}`,
`{"type":"account",...}`, `{"type":"activity","title","body","t"}`, `{"type":"orders",...}`, `{"type":"feed","ok":bool,"reason":...}`.

**LiveFeed rules (verbatim, from PROTOCOL.md):** attach with `cdpcore.CDPSession.attach()`; `Network.enable`; find the futures socket by
URL containing `/v2/fws/` via `cdpcore.PageSockets` (re-acquire on socket close or page reload — watch `Network.webSocketClosed`,
`Page.frameNavigated`); our rids start at 900000; request our own `bars` history (`bar_size:"1M"`, `limit:329`) and our own `bar`
SUBSCRIPTION (`symbolId:1019,barSize:"1M",askOhlc:false`) — the page's chart subscription is whatever timeframe the chart shows;
parse `fx/market` (symId 1019) for the quote; use hedge-mode `subPositions[].id`; map our fill to its position id from the
"…linked to position" activity text (`"15394511: Stop loss #… "`) or by diffing subPositions before/after; settle from
`report/orders2` (`rpl`); capture the economic calendar passively (the page POSTs `/v2/economic-calendar/events`: read the response
with `Network.getResponseBody`, keep the request's postData, re-issue it from the page with `fetch` every 30 min); market closed = quotes
stale for > `feed_dead_s` or `st` reports a closed status. `--record` writes `recordings/YYYYMMDD_HHMMSS.jsonl` lines
`{"t":unix,"dir":"in"|"out","frame":{…}}` with every socket URL removed.

**SimFeed must copy PX behaviour:** quotes ~2.5/s, spread 0.33 (0.45–0.80 at night and in storms), regime-switching volatility
(calm / active / storm, occasional news spikes and true gaps of $0.40–$1.50 that skip prices); 1-minute bid bars built from its ticks plus
330 bars of generated history at start; account starts at $25.00; `place` fills at ask (BUY) / bid (SELL) plus random slippage 0–0.06
adverse; a long's SL and TP trigger on the **bid**, a short's on the **ask**; a stop that the price gaps through fills at the first price
after the gap (worse than the stop → the barrel); **an already-crossed TP or SL is accepted and fills at once** (PX does this);
`set_protective`, `close` (partial ok, step 0.01, min 0.01), `orders_report` with `rpl`; emits PX-style activity titles
("Market order filled", "Stop loss linked to position", "Take profit triggered", "Take profit filled", "Stop loss triggered",
"Stop loss filled", "Stop loss replaced", "… cancelled"). Deterministic with `--seed`. `--speed` multiplies market time.
**ReplayFeed** plays a recording at its original pace × speed, `can_trade=False`.

---------------------------------------------------------------------------------------------------------------------------------
## 5. Engine rules (engine.py) — numbers live in config.json

config.json defaults (B-ENGINE writes the file; engine reads it at start; `state/settings.json` overrides the player-changeable ones):
```json
{ "port": 8790, "symbol": "XAU/USD", "sym_id": 1019,
  "coin_oz": 0.01, "min_qty": 0.01, "qty_step": 0.01, "stop_dist": 1.0, "stop_choices": [1.0, 2.0, 3.0],
  "targets": [1.0, 1.2, 1.5, 2.0], "target_default": 1.2,
  "haggle_step": 0.10, "haggle_max": 3, "haggle_reach_x": 0.12, "walls_max": 2, "wall_buffer": 0.30, "min_sl_gap": 0.05,
  "tilt_window_s": 10, "tilt_long_window_s": 30, "tilt_full_scale": 0.6, "patience_s": 30,
  "merchant_period_s": 20, "night_after_s": 600, "golden_hour_s": 60, "auto_close_before_close_min": 5,
  "link_freeze_s": 2.0, "stale_instruction_s": 2.0, "feed_stale_s": 2.0, "feed_dead_s": 15,
  "rounds_max": 30, "loss_max_coins": 10, "jam_after_stops": 3, "jam_minutes": 10,
  "alley_needed": 5, "twin_unlock_rounds": 50, "ghosts": 3, "barrel_gap": 0.30,
  "stake_pivot": 2, "stake_merge": 0.25, "profile_bars": 20, "terrain_bins": 96, "gap_min": 0.25,
  "dead_hours_utc": [["20:45", "23:00"]], "news_window_min": 15, "news_impacts": ["high"],
  "london_open": "08:00 Europe/London", "newyork_open": "09:30 America/New_York",
  "live_enabled": false }
```
Key rules (full detail in REQUIREMENTS.md §5; these are the binding interpretations):
* **Coin = `coin_oz` ounces; risk = coin_oz × stop_dist USD** (0.01 oz × $1.00 = $0.01). Money is shown in **real units**: cents with two
  decimals when risk < $1 (`"0.67¢"`), dollars otherwise. Never rescaled into fake dollars. Limits are counted in coins (1 coin = risk).
* **Entry:** `shoot` → place at market with SL/TP computed **from the live quote at send time**: long SL = ask − stop_dist,
  TP = ask + target; short SL = bid + stop_dist, TP = bid − target. The ladder is then re-anchored on the **actual** fill price and the
  broker's actual SL/TP.
* **The ladder (one axis).** stop_dist0 = |fill − SL0|, target_dist0 = |TP0 − fill| (fixed at the fill). The round result per initial
  ounce, in price units: `R = banked_usd/qty0 + f · side · (mark − fill)`, f = qty_now/qty0, mark = bid (long) / ask (short).
  **x = (R + stop_dist0) / (stop_dist0 + target_dist0)**: 0 = the vault anvil (initial stop), x_entry = stop_dist0/(stop_dist0+target_dist0),
  1 = the buyer at the initial target. Every price-anchored object p maps through the same line: **x(p) = a + b·p** with
  `b = f·side/(stop_dist0+target_dist0)`, `a = (banked_usd/qty0 − f·side·fill + stop_dist0)/(stop_dist0+target_dist0)` — the engine sends
  a and b. Haggles move the buyer to x > 1 (the fog). After the machete f = 0.5: the street re-projects, the vault anvil maps exactly onto
  the golden stake (= the worst remaining outcome), which is the proof the stake rule is right.
* **Runner x = x(mark)** every tick (kinematic). **Tilt** = clamp(side·Δmid over tilt_window_s / tilt_full_scale, −1, 1), EMA-smoothed;
  tilt_long_window_s after patience_s at the door. Tilt never moves the runner.
* **Stakes** = confirmed swing lows (long) / highs (short) of 1-minute bars: bar i is a pivot if its low is below the lows of `stake_pivot`
  bars on each side, lit only once those right-hand bars have closed; merge within stake_merge; never inside a chasm.
* **Anvil to stake (A):** SL → the lowest lit stake that is above the current SL and below mark − min_sl_gap (long; mirror for short),
  price = stake − 0.01. Only toward the buyer. Refused (anvil bounces) if no such stake or the broker refuses.
* **Wall (W):** SL → mark − wall_buffer (long; mirror short), only if that tightens the SL; the first wall never beyond the fill price
  (break-even); max walls_max per round.
* **Haggle (H):** only if x ≥ x_target − haggle_reach_x and tilt > 0 and a lit stake exists behind the runner above the SL: TP += haggle_step
  AND SL → that stake, both sent; max haggle_max; refused otherwise (the buyer shakes his head).
* **Machete (M):** close floor(qty/2/step)·step if ≥ min_qty and qty − that ≥ min_qty (so needs qty ≥ 0.02); once per round; golden stake at
  x of the vault/current SL after re-projection. At coin_oz 0.01 the machete is chained (can_machete false) and NOT required in the Alley.
* **Merchant (T) / Eject (E):** close at market. Merchant rolls by every merchant_period_s (visual); T always works (whistle + tackle).
* **Ends:** TP fill → "buyer"; SL fill → "anvil" — but if the SL fill is worse than the SL price by > barrel_gap → "barrel" with the chasm
  [x(SL), x(fill)]; merchant / eject → those; auto close auto_close_before_close_min before the daily break or the weekend → "session";
  kill → "kill"; position vanished without our close → "outside". Settlement numbers come from `orders_report` (`rpl`, `fee`) and the fill
  activity; never computed by the client.
* **Costs (the rat / the jar):** spread at entry (spread × qty), adverse slippage (|fill − quote at send| × qty when adverse), fee, financing.
  Each is a rat bite event; the jar is the running sum (persisted).
* **Limits:** rounds_max per UTC day; loss_max_coins of net loss per UTC day → locked (the Collector) until the next UTC day;
  jam_after_stops stops in a row → jammed jam_minutes; dead hours, weekend/market closed, news window (high impact ± news_window_min),
  no feed → shutters down (no new round; an open round rides on).
* **Alley (wooden):** the same engine with a shadow broker on the live quotes (SimFeed's broker logic over the current Feed's quotes);
  WOODEN everywhere; counted separately. Live rounds need alley_done ≥ alley_needed (with ≥ 1 eject; ≥ 1 machete only if can_split) AND
  `live_enabled` (set via the safety screen with the typed word CONFIRM) AND feed.mode == "live" AND balance ≥ risk + margin AND shutters up.
  In sim mode the "live" kind trades the SimFeed broker (that is the point of sim).
* **Twin:** a shadow round with the same entry, stop and target that moves its anvil to every new stake and never haggles, splits or
  ejects. In the Alley always available; on the street after twin_unlock_rounds real rounds; runs only when invited.
* **Ghosts:** the last `ghosts` rounds' paths `[[age_s, x], …]` (sampled 1/s) replayed by round age.
* **Eject counterfactual:** after an eject or merchant close keep shadowing the closed position until its SL or TP would have hit (or 60
  min) and record `would_have_usd` in that round's log and the tallies.
* **Tallies** (from rounds/*.json): by session, by weather, by patience (shot < patience_s after reaching the door vs later), wooden, live,
  ejected (+ would-have), twin-invited, twin results. Each `{n, wins, net_usd}`.
* **Stale instruction rule:** an action whose `sent_at` (client clock + offset = server time) is older than stale_instruction_s on arrival
  is refused with `"stale"`. Duplicate nonces are refused with `"duplicate"`.

---------------------------------------------------------------------------------------------------------------------------------
## 6. HTTP API (server.py)

* `GET /` and `/static/*` → files from `static/`. `index.html` at `/`.
* `GET /api/stream` → **Server-Sent Events**: `event: snap` with the full snapshot (section 7) on connect and every 100 ms;
  `event: ev` with discrete events (section 7.3) as they happen; a comment line `: hb` every second. `Cache-Control: no-store`.
* `GET /api/state` → one snapshot (JSON).
* `POST /api/act` body `{"action": str, "nonce": str, "sent_at": float, "args": {}}` → `{"accepted": bool, "why": str|null}` (HTTP 200 either
  way). Actions:
  | action | args | when |
  |---|---|---|
  | `fund` | `{"kind":"wooden"\|"live","side":1\|-1,"target":1.2,"twin":bool}` | lobby → aiming (refusals: limits, shutters, live gating, no feed) |
  | `unfund` | `{}` | aiming → lobby (note back in the pocket) |
  | `flip` | `{"side":1\|-1}` | lobby/aiming: the mirror world (short) |
  | `set_target` | `{"target":1.2}` | lobby/aiming |
  | `invite_twin` | `{"on":bool}` | lobby/aiming |
  | `shoot` | `{}` | aiming → sending → open |
  | `anvil_next` `wall` `haggle` `machete` `merchant` `eject` | `{}` | open |
  | `ack` | `{}` | settled → lobby |
  | `kill` | `{}` | any: close the game's position, lock the day |
* `POST /api/settings` `{"coin_oz"?, "stop_dist"?, "sound"?, "plain_line"?, "eject_words"?, "live_enabled"?: bool, "confirm_word"?: "CONFIRM"}`
  → `{"ok", "why", "settings"}`; enabling live requires confirm_word == "CONFIRM".
* `GET /api/rounds?limit=50` → recent round logs (summaries). `GET /api/tallies`.

---------------------------------------------------------------------------------------------------------------------------------
## 7. The snapshot (server → client), exact shape

```js
snap = {
  v: 1, t: 1793677790.44,            // server unix seconds (float)
  mode: "sim" | "live" | "replay",
  feed: { ok: true, age_s: 0.4, reason: null, tick_count: 18231, ticks_per_s: 2.4, market_open: true },
  account: { id: "L1869984", type: "LIVE" | "SIM" | "REPLAY", balance: 0.61, equity: 0.61, currency: "USD" } | null,
  quote: { bid: 3926.38, ask: 3926.71, mid: 3926.545, spread: 0.33, ts: 1793677790.1 } | null,
  market: {
    session: "asia" | "london" | "newyork" | "dead" | "closed",
    day_frac: 0.0..1.0,              // UTC time of day / 24 (sun position)
    weather: "dead" | "calm" | "active" | "storm", vol: 0..1, lightning: false,   // lightning = a spike right now
    season: -1..1,                   // daily trend: + = favours the player's chosen side (autumn leaves blow toward the buyer)
    tilt_raw: -1..1,                 // market slope, + = up (the client uses round/preview tilt for the street)
    h24: 3970.2, l24: 3891.13,
    shutters: { down: false, reason: null | "dead_hours" | "weekend" | "news" | "jam" | "locked" | "no_feed" | "rounds_max" | "market_closed", until: null | ts },
    bell: { last_t: null | ts, session: null | "london" | "newyork", next_t: ts },
    news: [ { t: ts, title: "US CPI", impact: "high" } ]
  },
  settings: { coin_oz: 0.01, stop_dist: 1.0, stop_choices: [1,2,3], target: 1.2, targets: [1,1.2,1.5,2], side: 1, live_enabled: false,
              twin_invited: false, twin_unlocked: false, sound: true, plain_line: true, eject_words: "", risk_usd: 0.01,
              money_unit: "cents" | "dollars", can_split: false, min_qty: 0.01 },
  limits: { rounds_today: 3, rounds_max: 30, loss_today_coins: 2.0, loss_max_coins: 10, stops_in_row: 1,
            jam_until: null | ts, locked_until: null | ts, alley_done: 2, alley_needed: 5, alley_eject_done: false,
            alley_machete_needed: false, live_allowed: false, why_not_live: "alley" | "confirm" | "mode" | "balance" | "shutters" | null },
  lobby: { jar_usd: 0.0132, jar_bites: 14, cabinet: [ { t, usd, kind } ], trophies: [ { key, title, t } ],
           tallies: { by_session: {asia:{n,wins,net_usd}, ...}, by_weather: {...}, by_patience: {quick:{...}, patient:{...}},
                      wooden: {...}, live: {...}, ejected: {n, wins, net_usd, would_have_usd}, twin: {...} },
           rounds_total: 12, live_rounds_total: 0 },
  phase: "lobby" | "aiming" | "sending" | "open" | "closing" | "settled",
  preview: Preview | null,           // lobby + aiming: the street anchored at the current price
  round: Round | null,               // sending / open / closing (and settled, frozen at the end)
  settlement: Settlement | null,     // settled
  freeze: false                      // server-side: feed dead or page lost -> Time Freeze
}
Preview = { entry: 3926.71, stop: 3925.71, target_price: 3927.91, side: 1, a: -1234.5, b: 0.4545, x_entry: 0.4545,
            x_mark: 0.305, tilt: 0.2, patience_s: 12.0, at_door: true,
            stakes: [ {price, x, lit: true} ], terrain: Terrain, pit: { x0: 0.305, x1: 0.4545, depth: 0.55 } }
Round = {
  id: "20261103-045012-sim", kind: "live" | "wooden", side: 1 | -1, qty: 0.01, qty0: 0.01,
  opened_t: ts, age_s: 42.0, patience_s: 12.0,
  fill: 3926.59, sl: 3925.59, tp: 3927.79, stop_dist0: 1.0, target_dist0: 1.2, target_dist: 1.2,
  mark: 3926.10, spread: 0.33, a: -1234.5, b: 0.4545,
  x: 0.2318, x_entry: 0.4545, x_sl: 0.0, x_tp: 1.0,
  tilt: -0.35,                                   // signed for the player: + = downhill toward the buyer
  pnl_usd: -0.0049, banked_usd: 0.0, result_usd: -0.0049, value_usd: 0.0051, risk_usd: 0.01,   // value = risk + result (the roof sign)
  value_text: "0.51¢", tag_text: "2.20¢",         // pre-formatted real money for the roof sign and the buyer's tag
  anvil: { price: 3925.59, x: 0.0, kind: "vault" | "stake" | "wall" | "haggle", pending: false },
  stakes: [ { price, x, lit: true, passed: true, used: false } ],
  walls: [ { price, x } ], walls_left: 2,
  golden: null | { price, x, usd, text },
  haggles: 0, haggle_max: 3, can_haggle: false, can_wall: true, can_anvil: true, can_machete: false, machete_done: false,
  merchant: { x: 0.8, visible: true, dir: -1, insists: false },
  terrain: Terrain, pit: { x0, x1, depth },
  night: false, golden_hour: false, tarnish: 0.07,
  twin: null | { x, anvil_x, state: "running" | "done", result_usd },
  ghosts: [ { id, path: [[age_s, x], ...] } ],
  rat: [ { t, usd, why: "spread" | "slippage" | "fee" | "financing" } ],
  pending: null | { action, since },
  last_refusal: null | { action, why, t }
}
Terrain = { x0: -0.3, x1: 1.3, h: [96 floats 0..1], chasms: [[xa, xb], ...], scorch: [x, ...], weathered: [[xa, xb], ...] }
Settlement = { id, kind, side, outcome: "buyer" | "anvil" | "barrel" | "merchant" | "eject" | "session" | "kill" | "outside",
               result_usd: 0.0239, result_text: "+2.39¢", costs: { spread_usd, slippage_usd, fee_usd, financing_usd },
               fill, exit, qty0, age_s, chasm: null | [xa, xb], balance_after: 0.63, twin_result_usd: null | float,
               would_have_usd: null | float, plain: "Bought 0.01 oz of gold at 3,926.59 …", t }
```
### 7.3 Events (`event: ev`)
`{type:"accepted"|"refused", nonce, action, why}` · `{type:"fill", side, price, qty}` · `{type:"bell", session}` ·
`{type:"rat", usd, why}` · `{type:"stake", x}` (newly lit) · `{type:"anvil", ok, x}` · `{type:"wall", ok, x}` · `{type:"haggle", ok}` ·
`{type:"machete", ok, usd}` · `{type:"settled", outcome}` · `{type:"lightning"}` · `{type:"refused_broker", action, why}` · `{type:"freeze", on}`

### 7.4 Fixtures (exist in static/fixtures/, generated by tools/make_fixtures.py — do not edit by hand)
`lobby`, `aiming`, `open_profit`, `open_loss`, `open_wall`, `open_haggle`, `open_machete` (coin 0.02), `open_short`, `open_storm`,
`open_night`, `freeze`, `settled_buyer`, `settled_anvil`, `settled_barrel`, `jammed`, `locked`, `shutters_dead`, `alley_wooden`, `replay`.
Each file is `{ "snap": <snapshot>, "events": [<ev>, ...] }`. With `?fixture=NAME` the client renders that snapshot (no server), loops its
events every few seconds, animates time and tilt as if live, and accepts input locally (hold rings work, actions are echoed as accepted).

---------------------------------------------------------------------------------------------------------------------------------
## 8. Frontend

### 8.1 Coordinates, scale, layout (F-CORE owns the mapping; everyone draws in screen px)
* **1 unit = the Runner's standing height.** `s` = pixels per unit; at 1600×900 `s ≈ 95`. Every art function takes `s`.
* Draw anchor = the **feet / ground contact point** `(x, y)` in screen px; positive y down; `facing` +1 = right.
* Round x_norm → screen: the whole ladder must be on screen. Long: bank building over x_norm [−0.42, −0.02], the street [0, 1], the buyer's
  zeppelin at [1.0, 1.15], fog from 1.12 on. `screenX = left + (x_norm + 0.42) / 1.62 * width` (F-CORE may refine, but the full ladder stays
  visible; haggles past 1.1 pan the camera). **Short (side −1): mirror horizontally** (bank on the right).
* The ground is a strip at ~72% screen height, rotated by the tilt (max 25°, pivot at the runner), heights from `terrain.h`.
* Approximate sizes in units: bank facade 4.6 h × 3.4 w with the roof sign 0.9 h × 2.2 w; banker visible in an upper doorway ~1.4;
  buyer + zeppelin carriage 2.4 w floating 2.6 above ground; merchant on unicycle 1.25; rat 0.22; anvil 0.42; stake 0.62; wall 0.9 h × 0.32 w;
  bell 1.1 (hangs above the bank); held coin radius 0.17; pickle barrel 0.85; balloon 1.3; collector 1.6; jar 0.5.

### 8.2 art.js (F-ART) — exports, all `(ctx, x, y, s, st)` unless noted; `st.t` = seconds; pure drawing, no globals except an internal cache
```
drawRunner(ctx,x,y,s,{outfit:"suit"|"tux"|"undershirt"|"boxers"|"dusty"|"barrel"|"staked", pose:"idle"|"run"|"slide"|"lean"|"kneel"|"ride"|"aim"|"cheer"|"hold"|"tackle"|"fly",
           lean:-1..1, facing:±1, t, coin:{visible,glow:0..1,tarnish:0..1,half:bool,spin:0..1}, hat:bool, cane:bool, alpha:1, wooden:bool, tint:null|"#hex"})
drawTwin(ctx,x,y,s,{pose,lean,facing,t,alpha})                 // brass clockwork runner with the visor (ghostly)
drawGhost(ctx,x,y,s,{pose,facing,t,alpha})                     // translucent past self
drawBank(ctx,x,y,s,{t,facing,shutters:0..1,jammed:bool,night:bool,wooden:bool,banker:{mood:"smug"|"shot"|"eager"|"gloat"|"sulk"|"cards"|"crane",crane:0..1}})
drawRoofSign(ctx,cx,cy,w,h,{id:"roof",text:"0.67¢",color:"crimson"|"cyan"|"gold",hourglass:bool,t})   // split-flap; keeps flap animation per id internally
drawBell(ctx,x,y,s,{swing:0..1,shock:0..1,t})
drawBuyer(ctx,x,y,s,{mood:"wait"|"tap"|"inspect"|"pay"|"laugh"|"wave_off"|"shake_head",champagne:0..1,tag:"2.20¢",t,facing})   // tycoon in the steam zeppelin; (x,y)= the point under the basket at ground level
drawMerchant(ctx,x,y,s,{sign:"1.04¢",roll:angle,t,facing,tackled:0..1})
drawRat(ctx,x,y,s,{phase:"peek"|"bite"|"run",t,facing})
drawAnvil(ctx,x,y,s,{glow:0..1,t,bounce:0..1})
drawTether(ctx,x1,y1,x2,y2,s,{tension:0..1,t})                 // 0 sag, 1 taut red-hot vibrating
drawStake(ctx,x,y,s,{lit:bool,golden:bool,rusty:bool,initials:"ZZ",t,label:null|"text"})
drawWall(ctx,x,y,s,{build:0..1,t,rat:bool})
drawCoin(ctx,cx,cy,r,{glow,tarnish,half,spin,t,wooden})        // r in px
drawNote(ctx,cx,cy,s,{label:"1¢",t,angle})                     // the dollar/cent note in the lobby
drawPistol(ctx,x,y,s,{glow:0..1,recoil:0..1,t,facing})
drawMachete(ctx,x,y,s,{swing:0..1,t})
drawBalloon(ctx,x,y,s,{words:"",inflate:0..1,t})
drawBarrel(ctx,x,y,s,{t,blink:bool})
drawCollector(ctx,x,y,s,{t,chain:0..1})
drawJar(ctx,x,y,s,{fill:0..1,t})
drawRadio(ctx,x,y,s,{on:bool,crackle:0..1,t,text:null|"…"})
drawCabinet(ctx,x,y,s,{coins:int,t})
drawTrophyShelf(ctx,x,y,s,{trophies:[{key,title}],t})
drawCoinStack(ctx,x,y,s,{usd:0.61,t})                          // the balance as a stack
drawPageCorner(ctx,x,y,s,{t,hover:bool})                       // flip to the mirror world
drawHoldRing(ctx,cx,cy,r,frac,{color,label})                   // hold-to-confirm ring (UI)
```
### 8.3 world.js (F-WORLD)
```
makeWorld() -> world  (internal pools and caches)
world.drawSky(ctx,w,h,env,t)              // env below
world.drawSkyline(ctx,w,h,camX,env,t)     // parallax Clockwork-Deco skyline (2 layers)
world.drawTerrain(ctx,view,terrain,env,t) // view: {xToScreen(xn)->px, groundY, tiltRad, pivotX, w, h, s, mirror}
world.groundYAt(view,terrain,xn) -> px   // the ground height at x_norm (characters stand on it)
world.drawPit(ctx,view,pit,env,t)         // molasses at the door, depth = spread
world.drawChasms / scorch / weathered are part of drawTerrain
world.drawFog(ctx,view,fromXn,env,t)      // beyond the buyer
world.drawWeather(ctx,w,h,env,dt,t)       // ash (dead), ticker-tape rain + lightning (storm), dust; pooled particles
world.drawSeasonBand(ctx,w,env,t)         // thin strip at the very top: leaves toward the buyer / snow toward the bank
world.drawGrade(ctx,w,h,env,t)            // golden hour amber, night, freeze sepia + static, wooden warm tint, REPLAY banner across the sky
env = { session, day_frac, weather, vol, lightning, season, night, golden_hour, freeze, wooden, replay, mirror, tilt, t }
```
### 8.4 fx.js (F-ART)
```
FX.burst(kind, x, y, opts)   kinds: "dust","smoke","sparks","shavings"(opts.to=[x,y] flies to the jar),"cash","bubbles","ticker","confetti","chips"
FX.update(dt); FX.draw(ctx); FX.shake(amount, dur); FX.offset() -> [dx,dy]; FX.clear()
```
### 8.5 audio.js (F-AUDIO) — WebAudio only, synthesised (no files)
```
Audio.init()  (call on the first user gesture)   Audio.muted / Audio.setMuted(bool)
Audio.play(name, opts)  names: footstep, pistons, bell, anvil, refused, rat, ping, machete, chime, balloon, fold, thud, chain, needle,
      gunshot, cash, coin, cough, creak, whoosh, thunder, molasses, haggle, wall, stake, page, cards, collector, tick
Audio.setTether(tension 0..1)   Audio.setAmbience(env)   Audio.setVolume(0..1)
```
Sound bible: ticks = footsteps; tilt change = pistons; bell = shockwave with a sub-bass bloom; anvil = cathedral clang; refused = clang +
bounce; tether taut = rising bass hum; rat = razor snips; shavings = glass pings; machete = bullet-time whoosh + one chime; eject = balloon
hiss; fold-up = paper + a coin thud; the Collector = one chain link at a time; Time Freeze = a record needle lifting.

### 8.6 Input (F-CORE) — every money action is hold-to-confirm; a shake never fires one
| action | key (hold) | mouse / touch (hold on) |
|---|---|---|
| fund | drag the note to the pocket, or Enter | drag |
| shoot | Space 0.5 s | the Banker |
| anvil → next stake | A 0.5 s | drag the anvil onto a lit stake |
| wall | W 2.0 s (the build time) | behind the runner |
| machete | M 0.5 s | the coin |
| haggle | H 0.5 s | the Buyer's tag |
| merchant | T 0.5 s | the Merchant |
| eject | E 1.0 s | the red balloon button |
| flip (short world) | F | the page corner |
| plain-words line | L | the roof sign after settlement |
| ack settlement | Enter / Space | "Another round" |
| sound | S | the radio |
| kill switch | K 2.0 s, then confirm on the safety screen | — |
Hit boxes are computed in world space before the shake offset. Inputs are never disabled, only confirmed; during a freeze nothing is sent
(rings fill but the release says the needle is up).

### 8.7 Screens (F-CORE, screens.js) — REQUIREMENTS §1, §4, §9, §11
Loading (spinning coin until the first snapshot with a quote), Lobby (the street at rest + the lobby desk in the foreground: coin stack,
mouse jar, buyer's cabinet, trophy shelf, radio; the runner with the note; four buyer tags to choose the target; the brass Twin in the cabinet
to invite; the page corner; a cog to the safety screen), Aiming (at the door, the pistol, the patience glow after patience_s), Round,
Settlement (fold-up like a map, coin onto the stack, shavings into the jar, banker/buyer reaction, the plain line, *Another round* /
*Enough for today*), Jammed (banker plays cards, 10-minute clock on the sign), Locked (the Collector, the chain, *see you tomorrow*),
Shutters (closed + reason icon: moon for dead hours, storm cloud for news, calendar for weekend, cut wire for no feed), Safety screen
(DOM overlay styled as a ledger page: coin size, stop distance, sound, plain line, eject words, live switch with typed CONFIRM, kill switch,
the daily limits shown), Alley dressing (wooden: warm tint, wooden token, the Apprentice), REPLAY banner, Time Freeze (sepia + static +
needle; link silent > link_freeze_s or snap.freeze).

### 8.8 Visual proof (mandatory for F-ART, F-WORLD, F-CORE)
Render, screenshot with `tools/shoot.py` (port 9333 only), **open the PNG with the Read tool and look at it**, fix, repeat. A module is not
done until its gallery screenshots look like the Art Bible. Keep screenshots in `%TEMP%`, not in the repo.
