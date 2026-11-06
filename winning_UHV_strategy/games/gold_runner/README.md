# Golden Gravity: The $1 Heist

A small browser game in which every object on the street is a true statement about one real XAU/USD trade. You put a coin in the
Runner's pocket, shoot the Banker (that sends a market order with a stop and a target already attached), and from then on the Runner's
place on the street **is** the trade's floating result, to the cent. The ground tilts with the last ten seconds of price, the sky is the
session, the weather is volatility, and the rat bites only for real costs. There is no strategy inside the game and no advice: the market
gives gravity and consequences, the tallies in the lobby are the only teacher. The design is in `REQUIREMENTS.md` (v2.2); the code
contract is `CONTRACT.md`; the PrimeXBT wire protocol is `PROTOCOL.md`.

> **The numbers are real dollars, and small.** One coin is **0.01 oz** of gold with the anvil (stop) **$1.00 of gold price** away, so one
> coin risks **$0.01**. A $1 move in gold moves the result by $0.01. `$0.0067` on the roof sign means two-thirds of a cent.

---

## Starting it

| You want | Double-click | What happens |
|---|---|---|
| **Practice, no money** | `start_game_sim.bat` | starts `server.py --mode sim` (made-up market, made-up broker, a pretend $25 purse; the real note is labelled DEMO there) and opens http://127.0.0.1:8790/ |
| **The real street** | `start_game.bat` | if nothing answers on port 9222 it opens the PrimeXBT page in its own Chrome window (profile `chrome_profile/`); starts `server.py --mode live`; opens http://127.0.0.1:8790/ |

Both refuse to start if the other kind of server is already on port 8790 (so the practice street can never be mistaken for the real
one). Close the server window to stop the game.

**First time on the real street**
1. Run `start_game.bat`. A Chrome window opens on the PrimeXBT XAU/USD page. **Log in there once.** The game reads prices and sends
   orders through that page.
2. **Never close that Chrome window while you play.** If it closes or reloads, the street freezes (the record needle lifts) until the
   page is back; your stop and target stay with the broker meanwhile.
3. Play five wooden rounds in the Paper Trading Alley (see Safety), then sign the live switch with CONFIRM.

The game only ever touches the position **it** opened. Your own trades on the same account are never closed, moved or counted.

---

## Controls

Every action happens **on the click or key press** (Zee, 4 Nov: no holds). Only the kill switch still asks for a hold.

| What | Keyboard | Mouse |
|---|---|---|
| Pick the wooden token / the real note (lobby) | **O** / **N** | click it on the counter |
| Fund (coin into the pocket) | **Enter** | drag the token or the note onto the Runner's pocket |
| Take the coin back (at the door) | **Esc** | click the pocket |
| Choose the Buyer's price (the target, for the next round only; it goes back to $1.20 after each round) | **1 2 3 4 5** = skateboard / bicycle / car / jeep / helicopter ($1.00 / $1.20 / $1.50 / $2.00 / $3.00 of gold): the bigger the ride, the further the boss | click a vehicle on the counter |
| Mirror world (go short) | **F** | the page corner, top right |
| Invite the Twin (always in the Alley; on the real street after 50 real rounds) | **I** | the cabinet |
| **Rob the bank** = BUY (price rising: the Guard is shot, the Banker hands over the coin, carry it right to the mafia) | **Space** in the lobby | click the Guard or the little bank, straight from the lobby |
| **Rob the mafia** = SELL (price falling: the henchmen are shot, the boss hands over the coin, carry it left to the Gold Bank) | - | click the mafia on the right, straight from the lobby |
| Anvil to the next stake (trail the stop) | **A** | drag the anvil onto a lit stake |
| Build a wall right behind the Runner (a trailing stop: as many as you like, each one tighter, until the boss buys or you fall back onto your nearest wall) | **W** | click just behind the Runner |
| Machete (close half) | **M** (needs a 0.02 oz coin) | click the coin |
| Haggle (raise the target; only close to the Buyer, three at most) | **H** | click the Buyer's tag |
| Sell now to the passing cyclist: the **ice-cream girl** = you book a profit, the **thief** = you take a loss (no numbers: the rider tells you) | **T** | click the cyclist |
| Eject (close now at the market price, profit or loss) | **E** or **Space** | click the red balloon button |
| Another round | **Enter** or **Space** | "Another round" |
| Enough for today (a "gone home" sign; click to come back) | | "Enough for today" |
| Plain-words line on/off for this sitting (the ledger's switch sets the default; off on a fresh install) | **L** | click the roof sign or the receipt after a round |
| Sound on/off | **S** | the radio |
| Safety ledger | | the cog, top left |
| **Kill switch** | hold **K** 2 s, then hold **Space** 2 s on the red kill button | hold the kill button in the ledger 2 s |
| Close the ledger | **Esc** | "close the ledger" |

---

## The screens

* **Loading** - a spinning coin and "waiting for the first price..." until a real price arrives. Nothing is clickable before there is one.
* **Lobby** - the street at rest and the desk in front: the coin stack (your balance, to the cent), the mouse jar (every cent of cost
  so far), the day counter, the wooden token and the real note, the Buyer's four price tags, the radio (the news calendar), the cabinet
  (the Twin and every coin the Buyer has paid for), the tally slate, the trophy shelf and the big badge: WOODEN for the token, DEMO for
  the note on the practice street, LIVE on the real one.
* **At the door (aiming)** - the Runner holds the pistol in front of the Bank. Read the street; shoot when *you* decide.
* **The round** - the live street: Bank and Vault on one side, the Buyer's zeppelin on the other, the marble path between them.
* **Settlement** - the street folds like a map, the receipt prints a stamp (PAID, STOPPED, LIQUIDATED, SOLD, LET GO, CLOSING BELL,
  KILLED, CLOSED ELSEWHERE), the costs and one plain line about the trade. Then *Another round* or *Enough for today*.
* **Mirror world** - the same street printed backwards, for a short.
* **Jammed** - the Banker plays cards on the step; a 10-minute clock.
* **Locked** - the Debt Collector with his chain: see you tomorrow.
* **Shutters down** - no new round, with the reason: moon = dead hours, storm cloud = news, calendar = weekend, cut wire = no prices.
  An open round rides on; its stop and target are with the broker.
* **Time Freeze** - sepia, static and a lifted record needle when the game server has been silent for 2 s (or the market feed has been
  dead for 15 s). Nothing can be sent until it comes back; then the Runner slides to the true position. When only the prices pause,
  the roof sign shows an hourglass after 2 s and the controls still work.
* **Paper Trading Alley** - warm wooden tint, WOODEN everywhere, the Apprentice's token.
* **Safety ledger** - the cog: coin size, anvil distance, sound, plain line, the words on your balloon, the live switch, the kill switch,
  today's limits.

---

## Safety rules (these are the building, not settings)

* **Alley first.** The real note stays chained until you have finished **5 wooden rounds, one of them an eject** (and one machete if the
  coin is 0.02 oz). Wooden rounds use real prices but never send an order. Everything is counted per street: rounds, tallies, limits
  and the Alley on the practice street never count on the real one.
* **CONFIRM.** Even after the Alley, live orders need the live switch in the safety ledger, signed by typing **CONFIRM** in capitals.
  The signature is not saved: every time the server starts, the switch is off again. The live street has a red frame on every screen.
* **Coin size.** 0.01 oz (default) or 0.02 oz; anvil distance $1, $2 or $3 of gold. So one coin risks 1 to 6 cents. The game never
  makes the coin bigger after a win.
* **Daily limits** (counted from real rounds, per UTC day = from 5:00 AM PKT):
  * 30 rounds a day.
  * Loss limit: 10 coins, or 5% of the day's starting balance if that is smaller. Then the Debt Collector locks the street until 5:00 AM PKT.
  * 3 stops in a row: the bank door jams for 10 minutes.
* **Shutters** (no new round; an open one rides on): 15 minutes either side of high-impact US news; the dead hours 1:45 AM - 4:00 AM
  PKT (20:45-23:00 UTC); the daily break (3:00-4:00 AM PKT in winter, 2:00-3:00 AM PKT in summer) and the weekend (Saturday 3:00 AM to
  Monday 4:00 AM PKT in winter, an hour earlier in summer); no prices. The practice street ignores the clock (it trades at any hour)
  unless the server is started with `--real-hours`.
* **The closing bell.** 5 minutes before the daily break or the weekend (2:55 AM PKT in winter, 1:55 AM PKT in summer) the Merchant
  insists and closes an open round at market. That is the only forced close. A long trade only gets darker (night falls after 10 minutes); nothing is taken from you for it.
* **Kill switch.** Hold **K** for 2 s, then hold the red button in the ledger for 2 s: the game's own position is closed at market (it keeps
  retrying until the broker confirms), the live switch goes off and the street is locked until 5:00 AM PKT.
* **The stop and the target always live with the broker.** If the game, the browser or the internet dies, they still work. If the game
  sees the broker's stop or target missing for 2 s it sets them again, and closes the position if it cannot. If the game server is
  restarted during a real round, it finds its position again and carries on (wooden and practice rounds are not resumed).

**What the numbers mean.** The roof sign shows the coin's value: what you risked plus the result. A $0.01 coin shows `$0.01` at the door
and drops by the spread the moment you shoot (about `$0.0067` on a normal 0.33 spread: that is the Spread Pit). The anvil is at about
`$0.00` (a little below if the fill slipped), and the Buyer's tag shows what he pays (`$0.022` with the $1.20 target). Crimson = below the
coin you put in, cyan = above it. The hourglass flap means the last price is older than 2 seconds. The receipt lists the costs: *the pit*
(spread) and *the rat* (slippage, fees). All settlement numbers come from the broker's own deal history, never from the game's arithmetic.

---

## What everything means (the honest mapping)

| On the street | In trading terms |
|---|---|
| The Runner's place on the path | the round's floating result (pinned to it every tick) |
| The tilt of the ground | the price slope of the last 10 seconds, for your side. Feel only: it never moves the Runner |
| The Bank door and the Spread Pit | the entry price; the pit's depth is the live spread |
| The Vault Anvil | the stop loss, with the broker (starts $1 of gold behind the entry) |
| The Buyer's basket and price tag | the take profit, with the broker |
| The fog beyond the Buyer | prices above the target (reachable only by haggling) |
| Hills and flat marble | where price traded in the last 20 one-minute candles (a price profile) |
| A Void Chasm | a gap: prices that never traded |
| Glowing stakes | confirmed swing lows (swing highs in the mirror world) |
| Shooting the Banker | a market order with the stop and target attached |
| Anvil to a stake (A) | trailing the stop to that swing low |
| A wall (W) | moving the stop up behind you (the first one never past break-even) |
| The machete (M) | closing half the position; the golden stake marks the worst you can still end at |
| Haggling (H) | target +$0.10 of gold, and the stop moves to the last stake at the same time |
| The Merchant (T) / the balloon (E) | closing at market now (the receipt later shows what the anvil would have done) |
| The Slippage Rat and the mouse jar | real costs: spread at entry, slippage, fees, financing; the jar is their running total |
| Dusty at the anvil (STOPPED) | the ordinary stop-loss fill |
| The pickle barrel (LIQUIDATED) | a stop filled through a gap, more than $0.30 worse than the stop (rare) |
| Clothes: tuxedo to boxers | how the round is going: in profit to deep in drawdown |
| The sky and the sun | the session: dawn = Asia, noon = London, afternoon = New York, night = dead hours |
| Weather: sepia fog, sunset, storm | volatility: dead, active, high |
| The season band at the top | the day's trend (leaves blow toward the Buyer when it favours you) |
| The Golden Bell | the London and New York opens, nothing else (1:00 PM and 7:30 PM PKT in winter; 12:00 PM and 6:30 PM PKT in summer) |
| Night falling on a round | the trade is older than 10 minutes (a picture, not a penalty) |
| Ghosts | your own earlier rounds at the same age |
| The Twin | a mechanical copy of your round that trails every stake and never haggles or ejects: discipline by contrast, never an entry signal |
| The Debt Collector | the daily loss limit |
| Cards on the step | 3 stops in a row: a 10-minute pause |
| The wooden token | paper trading on real prices (the Alley) |

---

### The camel and the diamond (Zee's UHV Diamond, 2026-11-04)

`diamond.py` reads Zee's LAWS.md setup on the game's own 1-minute bars, in his order (Zee: *"we also need the camel humps first ->
then comes the retracement -> then the UHV inside that retracement -> then the wait for its breakout"*), and shows **every**
qualifying setup (*"we must show all qualifying setups of this strategy"*):

1. **Camel humps:** a trend confirmed by higher highs that break the last top and higher lows (lower lows / lower highs for a sell).
   It lives through its own pullbacks and ends when his line 45 says so: the last low (high) breaks.
2. **Retracement** in that trend: the first body breaking the last impulse candle's low (high).
3. **UHV:** the loudest counter-coloured candle of the retracement.
4. **Breakout:** the first candle whose body closes beyond the UHV's high (low) on LOWER volume than the UHV: the diamond.

The rules are ported from `mt5/DiamondEngineM1.mqh` (the Diamond engine inside Trinity_1min). The EA's extra gates (a fresh trend
reading on the breakout bar, the 3-hump budget, a 3-bar cooldown, UHV body >= 0.5 and louder than its neighbours) no longer hide a
setup; with Trinity's 15-minute chop meter (efficiency ratio over 16 candles >= 0.45) they decide only whether it is ROYAL.
Parity: every EA fire MT5 logged on EUR/USD in October 2026 (9, plus one the broker refused) is a diamond here, same side, same UHV.
Volume = the bar's own tick volume, or our count of quotes in that minute when a bar carries none.

| on screen | what it means |
|---|---|
| camel on the shelf beside the binoculars, walking right / left | his trend is up (toward the mafia) / down (toward the bank) |
| 1, 2 or 3 humps on its back | the swings this trend has made |
| camel trotting, dust at its hooves | ...and the 15-minute market is moving cleanly (ER >= 0.45) |
| camel lying down, z's | hump 4+: "hump 4 hmm maybe it shifts" (diamonds still show; your call) |
| camel grazing | no trend, or line 45 just ended it: no diamonds |
| rough grey stone over the bank (buy) / the mafia (sell) | a retracement in the trend has its UHV; waiting for the breakout |
| a cut diamond there, with a chime | the breakout closed beyond the UHV on lower volume |
| big blue-white diamond with a crown (two chimes) | ...and the EA itself would take it, in a clean 15-minute market (report section 34) |
| small cloudy, cracked diamond | a qualifying setup the EA's extra gates would skip |
| 1-3 sparks circling it | the counted laws that held (sweep before the UHV, close beyond EMA-5, a clean quiet breakout) |
| the diamond shatters | price came back through the retracement's extreme |

Clicking the gem robs the party under it (a click on a party also wakes a dozing Runner and fires). A hint, never an order and
never a promise: on real EUR/USD (October 2026) it shows ~19 diamonds a day; MT5 found NO edge for the EA version on EUR/USD at the
game's 2-pip geometry (`research/DIAMOND_EUR_MT5.md`). `window.__ggDia = {...}` forces a reading for screenshots. `dia_unit`
(admin) = one gold dollar in the symbol's price.

## Known limitations

* **The real-money connection (`feeds.LiveFeed`) has not yet been seen working live end to end.** It is built from the protocol captured
  on 2026-11-03 and tested against simulated pages. These parts are assumptions until a live session proves them: the exact activity
  titles for a stop-loss fill, how an order without a reply is found again, the check that the broker still holds the stop and target,
  the calendar fetch, the account pin to L1869984, and settlement from the deal history. Watch the first live rounds closely, at 0.01 oz.
* **PrimeXBT's trading hours are guessed** (daily break 17:00-18:00 New York = 3:00-4:00 AM PKT in winter, 2:00-3:00 AM PKT in summer;
  weekend Friday 17:00 to Sunday 18:00 New York). If PrimeXBT closes gold at other times, the closing bell will ring at the wrong moment. The dead hours come from the project's own trade records.
* **The sounds were tuned without ears**: every sound is synthesised in code and was checked by numbers and waveforms only. Turn them down
  (or press S) if one is unpleasant.
* The news shutters only know the events PrimeXBT's own calendar lists as high importance for the US.
* When the prices stop but the game server is still talking (a quiet or stuck feed), the street does not freeze until 15 s have passed:
  the hourglass shows after 2 s and your actions are still sent. On the real street the broker fills at its own price; in the Alley a
  wooden round is filled at the last price the game saw.
* A wooden or practice round that is open when the game server stops is simply gone after the restart (no receipt). Real rounds are resumed.

---

## Files

| File | What it is |
|---|---|
| `start_game.bat` / `start_game_sim.bat` | the two launchers |
| `server.py` | the local web server (127.0.0.1 only): the page, the live stream to the browser, the player's actions |
| `engine.py` | the rules: the round, the ladder, orders, settlement, limits, tallies, the round logs |
| `feeds.py` | the market and the broker: `LiveFeed` (PrimeXBT page over CDP), `SimFeed` (practice), `ReplayFeed`, the recorder |
| `cdpcore.py`, `cdp.py` | the Chrome DevTools connection used by `LiveFeed` |
| `config.json` | every number the rules use |
| `static/index.html`, `static/css/style.css` | the page |
| `static/js/main.js` | the game loop, camera, input, and the composition of every frame |
| `static/js/net.js` | the connection to the server (stream, clock, Time Freeze, actions) |
| `static/js/screens.js` | loading, lobby desk, settlement receipt, locked / jammed / shutters, the safety ledger |
| `static/js/art.js`, `static/js/fx.js` | every character and prop; particles and screen shake |
| `static/js/world.js` | sky, sun, weather, skyline, terrain, chasms, fog, colour grading |
| `static/js/audio.js` | the synthesised sound |
| `static/js/palette.js` | colours and line weights |
| `static/gallery_*.html` | test pages that draw every character, world state and sound |
| `static/fixtures/` | frozen game states for those test pages (`?fixture=NAME`) |
| `tests/` | the automatic tests (`python -m unittest discover -s tests`) |
| `tools/shoot.py` | screenshots through a separate, invisible Chrome (never the trading one) |
| `rounds/` | one JSON log per finished round (the tallies are counted from these) |
| `state/` | saved settings and the day's discipline state |
| `recordings/` | recorded live feeds for replay (socket addresses removed) |
| `chrome_profile/` | the trading Chrome's own profile: it holds your PrimeXBT login. Never share it, never commit it |
| `REQUIREMENTS.md`, `CONTRACT.md`, `PROTOCOL.md`, `P0_FEASIBILITY.md` | the design, the code contract, the wire protocol, the first feasibility test |

## Admin page (symbol and settings)

Open **http://127.0.0.1:8790/admin**. Pick the symbol the game trades (EUR/USD or XAU/USD) and edit each symbol's settings: coin size, stop and target distances, wall gap, haggle step, tilt scales, weather thresholds, price decimals and the practice-market mapping. **Save** writes `state/admin.json`; **Save & Apply** rebuilds the game around it (only in the lobby or on a receipt). Since 4 Nov 2026 the game runs on **EUR/USD** (PXTrader id 1000, 5 decimals, one coin = 500 EUR = $0.10 at risk with a 2-pip stop); gold waits on the admin page. The smallest EUR/USD amount PXTrader accepts is unverified: if a live order is refused, raise the coin size there.
