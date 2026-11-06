# GOLDEN GRAVITY: THE $1 HEIST — Game Design Document

**Version 2.2 — final, implementation-ready; pure sandbox; all decisions taken.** 2026-11-03. Owner: Zeeshan. Reviewed and proof-read for logical consistency by Claude Fable.
**Concept:** A 2.5D physics survival runner in which every object, slope, sound and injury is a true statement about one live XAU/USD trade of exactly one dollar at risk. **It is a sandbox, not a strategy:** the market gives the player gravity, momentum and consequences — never instructions. A beginner learns what a stop is by watching where the rope will tie; an advanced player hears the footsteps sprint and the sky darken and recognises a volume anomaly on his own. Both are free to fail.
**The Golden Rule:** *The game never lies.* Gravity is information, not fiction. The runner's position on the ground is always the exact floating result of the live trade; the ground's tilt is the last ten seconds of the market; every bite the rat takes is a real cent from the account.

A §14 at the end lists every logical fallacy found in the previous draft and how this version resolves it — read it first if you knew the old draft.

---

## 1. The story of one round (the trade lifecycle as the player lives it)

**Dawn on Ledger Street.** The Runner stands in the lobby with a $1 note. Behind him, the Bank: a brutalist iron facade with a cyborg vault-keeper in the doorway and a split-flap sign on the roof. Far to the right, past a crumbling marble path, the Buyer's gilded zeppelin hangs in the sky with a price tag swinging from its basket. Between them, a street that is the gold market made solid.

1. **Fund.** The player drags the note into the Runner's pocket. One dollar is now at risk and nothing else will ever be.
2. **Read the street.** No one tells the player when to shoot. He stands at the bank door and reads what the world is doing: the footsteps (ticks) sluggish or sprinting, the fog thinning, the pistons rumbling, the sky's colour, the sun's height, the depth of the molasses. High above the bank hangs the Golden Bell — it rings at the London and New York opens (a real injection of liquidity) and for nothing else. Shooting into a dead sepia session is allowed; the rat and the pit will teach why it was a bad idea.
3. **Execute.** He shoots the Banker. The Banker spits his cigar and hurls the coin — the market order fills — and the Runner lands in the Spread Pit outside the door: knee-deep molasses whose depth is the live spread. The roof sign clacks to the fill price. From this instant a broker-side stop (the **Vault Anvil**, one dollar of gold price behind the entry) and a broker-side target (the Buyer's tag) exist. There is never a moment of the round without both.
4. **The ground wakes.** Iron pistons groan under the marble and the street tilts with the last ten seconds of price. If gold climbs, the path slopes down toward the Buyer and the Runner's heels throw dust as he slides right; if gold falls, the pistons crank the other way and he slides back toward the Bank. His *position* is the floating result; the *tilt* is what the market is doing right now. A flat market is level ground, wherever he stands.
5. **Survive.** The sky tells the session; the weather tells the volatility; footsteps are the ticks. Stakes glow in the marble where the market has made confirmed swing lows. He may drag the anvil forward to a stake (a trailing stop), hammer a wall behind himself (a protective stop), machete the coin in half and bank a piece (a partial close), haggle with the Buyer for a higher tag once he is nearly there (a trailing target), tackle the Merchant to sell at today's sign (a manual close), or pull the eject balloon (a panic close). Each of these is a real order and each one can be refused by the broker, visibly.
6. **Settle.** The round ends only when the Buyer pays, the anvil catches him, the Merchant buys, or the balloon lifts him — or, on the rarest day, when the ground tears open under a gap and the Banker's crane takes everything (an unfilled stop). The canvas folds like a map; the coin (or its remains) thuds onto the lobby stack; the rat's shavings ping into the jar; the roof sign prints one plain line about what the trade was, for those who want to read it.
7. **The street keeps the discipline.** Three shirts lost in a row jam the bank door for ten minutes; the daily loss limit brings the Debt Collector and his chain until the next server day; storms close the shutters around news; the dead hours put the street to sleep. None of these are settings. They are the building.

---

## 2. The world is a price ladder (the core mapping, made consistent)

The previous draft put two different x-axes on one ground (the runner at a *P&L* coordinate, the bumps at *time* coordinates). This version has one axis: **the ground from the Vault to the Buyer is the price ladder of this trade.**

| World coordinate | Trade meaning |
|---|---|
| The Vault (back wall of the Bank) | Entry − $1.00 of gold price: the initial stop; the Vault Anvil sits here |
| The Bank door / Spread Pit | The entry price (the fill) |
| The marble path | Every price between entry and target, left to right |
| The Buyer's basket | Entry + target (default +$1.20) |
| Beyond the Buyer | Prices above target: fog — reachable only by haggling |

* **Runner x = floating result.** Pinned every tick: `x = lerp(vaultX, buyerX, (pnl + 1) / (1 + target))`. After a partial close, `pnl` is the *round's* result (banked + floating) — see §5.3.
* **Tilt = the price slope** of the last 10 seconds, signed for the player's side, clamped to ±25°. It is rendered (lean, dust, sagging or taut tether, camera roll, piston sounds) and fed to the physics engine's gravity vector for *feel* only. The engine's body for the Runner is kinematic: its position is set from `pnl`, never integrated from gravity.
* **The bumps = where price has lived.** Each stretch of path is raised by how many of the last 20 one-minute candles touched that price level (a price profile): hills where the market dwelt (support, resistance), flat marble where it passed quickly, and **a Void Chasm where it never printed at all** — a liquidity gap. A stake can only stand on marble; an anvil dragged toward a chasm stops at its edge. Old ground does not crumble behind the Runner (it is price, not time); it *weathers*: levels the market has left behind for more than 20 minutes fade to grey.
* **Stakes = confirmed swing lows** (for a long; swing highs in the mirror world). A stake lights only after the candles that confirm the swing have closed — the game never plants a stake the market hasn't finished making. Stakes closer than $0.25 merge.
* **Time lives in the sky, not on the ground.** The sun is the session clock; the season band is the daily trend; the weather is volatility; the hourglass on the roof sign is the age of the trade.

---

## 3. Characters

**The Runner** — the player. A real-time health bar made of clothes.
- *Drop-in* (around break-even): dusty suspender suit, sleeves rolled, hugging the glowing coin, leaning into the wind.
- *Runaway profit*: the suit snaps into a Gatsby tuxedo, a silk top hat lands, the coin goes white-hot and he rides it like a snowboard with a diamond cane.
- *Drawdown*: the wind tears the tuxedo to a torn undershirt, then polka-dot boxers.
- *Dusty* (stopped at the anvil — the ordinary loss): on his knees at the anvil, suit torn but on; the Banker's crane takes the coin politely and the sign stamps STOPPED.
- *Barrelled* (an unfilled stop — the rare catastrophe): dragged across a Void Chasm into the Vault; a pickle barrel slams over him; the sign stamps LIQUIDATED. Reserved for a gap through the stop; must stay rare or it stops meaning anything.
- *Staked* (after a partial): half a coin on his back and a golden stake behind him with his initials.

**The Banker** — cyborg vault-keeper in a green visor with a cigar, built into the facade. Smug before the shot; coughs black smoke and hurls the coin when shot; repaints nothing — the roof sign does that; crane-arm politely retrieves the coin at the anvil; stamps LIQUIDATED only when the ground itself failed. Plays cards on the step during a door jam.

**The Buyer** — an obscenely rich tycoon in a steam zeppelin, champagne flute in hand, price tag swinging from the basket. Inspects the coin with a loupe, laughs, fires a golden blunderbuss of cash. When haggled he raises the tag by ten cents, the zeppelin drifts a step right and the champagne drops; at the third haggle the flute is empty and he waves the player off.

**The Merchant** — a trench-coated clockwork automaton on a unicycle, neon sign showing the coin's current value. Rolls by every ~20 s; can always be whistled (long press / hotkey). Tackle him to sell: a dust cloud, then settlement.

**The Slippage Rat** — razor blades and brass, lives in walls and under anvils. Bites the coin only for real cents: the spread at entry, commission, and slippage on fills. Never bites for drama.

**The Twin** (optional, unlockable training wheels) — a brass clockwork runner, not a strategy: he enters when *you* enter and then plays the round with perfect discipline — drags the anvil to every next stake, never haggles, never ejects, never walls twice. In the Paper Trading Alley he is available from the first wooden round — the silent tutorial of what mechanical discipline looks like. On the demo/live street he must be earned: he unlocks after 50 real rounds, lives in the lobby cabinet, and runs one lane behind you only when invited. A player should feel the chaos of his own emotional exits before he can appreciate the Twin's cold ones. He teaches discipline by contrast, never entries.

**The Ghosts** — translucent replays of the player's own earlier rounds at the same clock time on the same street. You watch yourself drop the anvil too early again.

**The Debt Collector** — tall, grey, a kind face, a chain and a padlock. Appears when the daily loss limit is hit, locks the street, hangs *see you tomorrow*. The only character who cannot be argued with.

**The Apprentice** (onboarding only, §9) — a wooden-token Runner who plays the same street on live data without ever placing an order.

---

## 4. The street: environment, sky, sound

**Terrain:** crushed marble, old ledger pages, gears; iron pistons beneath crank the tilt with groans and sparks. Scorch craters where wicks blew (drawn only at wicks that have already printed). Rusty stakes where past rounds' anvils stood. Golden stakes where profit was banked. Void Chasms where price never printed.

**Sky and weather:**
- *Dead market*: flat sepia fog, falling ash, silence.
- *Active market*: an aggressive sunset.
- *Storm (high volatility)*: pitch-black sky, neon-purple lightning on the path, rain of ticker tape sticking to the screen; the Spread Pit deepens.
- *Session*: dawn = Asia, high noon = London, long afternoon = New York; night = the dead hours, when the Bank's shutters are down and the street sleeps.
- *Night falls on a long trade* (replaces the old forced 5-minute exit — see §14): after ten minutes the sun sets on the round, the coin tarnishes visibly, the Merchant rolls by more often and the Buyer's lamp is the only light. Nothing is taken from the player that the market doesn't take: tarnish is a picture of time, not a tax — the game cannot invent a margin call the broker hasn't issued. Let the player sweat in the dark under the Buyer's lamp; the discomfort is the teacher. The only forced close is the real one — the session's end or the weekend, when the Merchant insists.
- *Season band*: a quiet strip at the top of the sky; autumn leaves blow toward the Buyer when the daily trend favours him, snow drifts toward the Bank when it doesn't.
- *Golden hour*: the last minute before the Merchant insists — amber light, long shadows, the hourglass turning.

**The roof sign:** a mechanical split-flap board that clacks in time with the ticks: the coin's live value (crimson below $1.00, searing cyan above). A small hourglass flap appears whenever the latest quote is older than two seconds — the sign never shows a price it doesn't have.

**Sound bible** (nothing is informative by sound alone; everything sounds like what it is): ticks = footsteps; tilt change = pistons; bell = shockwave with a sub-bass bloom; anvil = cathedral clang; refused anvil = clang and bounce; tether taut = rising bass hum; rat = razor snips; shavings = glass pings; machete = bullet-time whoosh and one chime; eject = balloon hiss; fold-up = paper and a coin thud; the Collector = one chain link at a time; connection lost = a record needle lifting.

---

## 5. Mechanics (every action is an order; every rule is exact)

### 5.1 Funding and sizing
- One coin per round, one round at a time, **1 oz of gold** per coin so that a $1.00 move = $1.00 of result. On PXBT MT5 that is **0.01 lot** (1 lot = 100 oz). On the PrimeXBT web platform the same trade is *amount 1.00*, not 0.01: the screenshot's "0.01 XAU/USD, position value $39.44" was 0.01 oz, on which a $1 move is one cent. Risk, not margin, is the fixed thing; margin at 1000× is about $4 and is never shown.
- The lobby refuses to fund if: balance < $1, daily round limit reached (30), daily loss limit reached (the Collector), shutters down (news window, dead hours, weekend), or a connection is not live.

### 5.2 Entry
- **Shoot** = market order with broker-side SL at entry − $1.00 (long) and TP at entry + target. Default target $1.20; the lobby offers $1.00 / $1.20 / $1.50 / $2.00 (risk-to-reward 1:1, 1:1.2, 1:1.5, 1:2) for the next round only — fixed steps, so the player consciously chooses the round's volatility threshold instead of letting a target float — each with the player's own historical hit rate beside it once he has 50 rounds.
- A refused order (requote, off quotes, margin): the Banker ducks; retry after 3 s; three refusals return the note to the pocket.
- The Golden Bell rings only at the London and New York opens; the pistol never glows. The bell's rope hangs to the street; pulling it yourself gives a dull clunk — the bell marks time, it does not advise.

### 5.3 Managing the trade
- **Drag the anvil to a stake** (trailing stop): modifies the broker SL to the stake's price minus one tick. Only toward the Buyer, never back; only to a lit stake the Runner has passed; refused by the broker → the anvil bounces back with a clang.
- **Build a wall** (protective stop): two seconds to build, at most two per round, only behind the Runner; the first wall never beyond break-even minus costs. The anvil locks to the wall. The rat lives in walls: real slippage on a stop fill is drawn as the rat eating at the wall.
- **Machete** (partial close): closes half the position at market; the banked amount is pocketed. The **golden stake** rises at the round's worst remaining outcome — `x(banked − 0.5 × stopDistance)` — so the Runner can be dragged back to it but never past it. (Not at the spot where he stood: a stake there would promise money the trade could still lose.) The remaining half-coin is lighter: he accelerates visibly, the physics of a smaller position.
- **Haggle** (trailing target): available only within one stake-length of the Buyer with the tilt in the player's favour; raises the TP by $0.10 and *simultaneously* moves the SL to the last stake. Max three. Greed only with a rope on.
- **Tackle the Merchant** (manual close at market). **Eject** (panic close at market): the balloon is painted with the words the player wrote on setup day; the tally later shows what ejected rounds would have done at the anvil — the only way to learn whether the panic was wisdom or fear.

### 5.4 Ending the round
- **Buyer pays** (TP fill) · **Dusty** (SL fill) · **Merchant / Eject** (market close) · **Barrelled** (a gap through the stop: the fill is worse than the stop; the Void Chasm is drawn where the price jumped so the player sees exactly why the anvil never caught) · **Session end / weekend**: the Merchant insists and buys at market before the market closes.
- Settlement numbers are read from the deal history, never computed by the game.

### 5.5 Discipline (the building, not the settings)
- Three stops in a row → bank door jams 10 minutes. Daily loss limit $10 (ten full coins; on a live account the smaller of $10 and 5 % of balance) → the Collector, until the next server day. Daily round limit 30: thirty one-minute trades is an exhausting sprint, and the cap stops a tilt spiral. News: shutters down 15 minutes before and after high-impact events (an open coin rides it out — its anvil is with the broker). Dead hours (the session with 0 % historical win rate in the project's own records): street asleep.
- Live mode: typed CONFIRM on the safety screen, red frame on every screen. Kill switch: closes any open position and locks the street.
- Discipline quests only ("walk away when the Collector comes", "wait out one storm", "tie before you haggle", "let the Twin play a round"). Never "win five in a row". Rejected forever: jackpot lights, streak bonuses, a bigger coin after a win (size is how the project's own $200 account died), hiding the rat.

---

## 6. The mirror world (going short)

When the bell rings for a short, the whole street turns like a page and is printed on its back, read right-to-left. The Runner now starts at the Buyer's basket: the Buyer **lends** him a coin (he is short gold), and the run is toward the Banker, who will **buy the coin back** cheaper if gold falls. Price falling for a short is the ground sloping toward the Banker. Stakes are confirmed swing highs. The Vault Anvil sits one dollar *above* the entry, behind the Buyer's basket. Everything else — pit, rat, jar, haggle, machete, chasms — is identical, mirrored. A short is the same story told backwards, and the page turn says so.

---

## 7. States of the world and of the connection

| State | Trigger | What the player sees | What the backend does |
|---|---|---|---|
| **Lobby** | no round | the street at rest, tallies, jar, cabinet, radio, Demo/Live badge | polls account, calendar, bell |
| **Round** | order filled | the live street | streams ticks, floating result, deal events (the backend never decides an entry) |
| **Time Freeze** | no WebSocket message for 2 s | the picture goes sepia and static, the record needle lifts, the roof sign shows the hourglass flap, every control greys except nothing can be *sent* | nothing changes: SL and TP are with the broker; the backend keeps its own copy of the position and keeps managing nothing (it never trades for the player); on reconnect the client resyncs from the account |
| **Reconnect** | messages resume | the needle drops, colour returns, the Runner snaps to the true position (with a visible slide, never a teleport without a sound) | sends a full state snapshot first |
| **Storm** | volatility above threshold / news window | lightning, ticker-tape rain, deep pit, shutters down for new rounds | marks the round as storm-affected in the log |
| **Night** | round older than 10 min | sunset on the round, tarnish, more Merchants | unchanged |
| **Jam** | 3 stops in a row | cards on the step, door shut, 10-minute clock on the sign | refuses `open` |
| **Locked** | daily limit | the Collector, the chain | refuses `open` until next server day |
| **Replay** | recorded data | REPLAY in huge letters across the sky; wooden coins only | no orders possible |

---

## 8. Inputs (deliberate by design; nothing precise is required during a storm)

Desktop first (mouse + keyboard), touch second. Every money-moving action is **hold-to-confirm** (a ring fills over 0.5 s) so a shake can never fire it; a release before the ring completes cancels with a soft click. Inputs are never disabled, only confirmed.

| Action | Keyboard | Mouse | Touch |
|---|---|---|---|
| Fund | drag the note | drag | drag |
| Shoot | **Space** (hold 0.5 s) | hold on the Banker | hold |
| Anvil → next stake | **A** (hold) | drag the anvil onto a lit stake | drag |
| Build wall | **W** (hold 2 s, the build time) | hold behind the Runner | hold |
| Machete (half) | **M** (hold) | hold on the coin | swipe across the coin, then hold |
| Haggle | **H** (hold) | hold on the Buyer's tag | hold |
| Whistle / tackle the Merchant | **T** (hold) | hold on the Merchant | hold |
| Eject | **E** (hold 1 s) | hold the red button | hold |
| Toggle the plain-words line | **L** | click the roof sign after settlement | tap |

Screen-shake moves the camera, never the hit targets: hit boxes are computed in world space before the shake offset is applied.

---

## 9. Paper Trading Alley (onboarding)

A side street behind the Bank where the **Apprentice** plays with a **wooden token** instead of a note. Same live data, same tilt, same stakes, rat, chasms and bell — and no order is ever sent: the token's round is a shadow trade priced from the same quote stream, settled as if filled at the quote with the live spread and the account's commission schedule. The lobby shows the Alley tally separately and labels it WOODEN everywhere. A player must finish five wooden rounds (including one eject and one machete) before the real note appears in the lobby; after that the Alley stays open forever for practice. The Alley is not the demo account: the demo account is a real broker account with pretend money; the Alley is pretend orders with real prices.

---

## 10. Engineering contract (what must be true of the build)

**Ownership.** The backend (Python, next to the PXBT MT5 terminal) owns everything that is money: it places and modifies orders, it computes the floating result from the account, it reads settlements from the deal history, it enforces the limits, and it keeps the authoritative round state. The frontend owns everything that is picture and sound. The frontend never computes a price or a result; it only draws what it is told.

**Stream.** Ticks and state at up to 50 ms, but the client *batches* everything that arrived since the last frame and applies it once per render tick (60 fps target). Terrain blocks, anvils, stakes, shavings, footstep sounds and ticker-tape rain are all **object-pooled**; nothing is allocated per tick. A volatility spike that delivers 200 ticks in a second must cost the client one frame of work, not 200.

**Messages** (client ← server): `snapshot` (full state, on connect and after any reconnect), `tick` {bid, ask, ts}, `pnl` {floating, banked, position x, tilt}, `terrain` (price profile, stakes, chasms; sent on change), `bell` {session, ts}, `fill` / `refused` / `modified` / `closed` {deal details, costs}, `shutters` {reason, until}, `weather` {session, volatility, news_in}, `lock` {reason, until}.
**Messages** (client → server): `fund`, `shoot`, `anvil_to` {stake}, `wall`, `machete`, `haggle`, `merchant`, `eject`, `alley` {on|off}. Each carries a client nonce; the server answers every one with `accepted` / `refused` {why}, so the picture can show the clang.

**Freeze rule.** If the client has not heard from the server for 2 s it enters Time Freeze and sends nothing; the server never acts on a stale client instruction (every instruction older than 2 s on arrival is refused with `stale`).

**Logs.** Every round writes a JSON record (quotes used, every instruction with its nonce and answer, fills, costs, settlement) and the lobby's tallies are computed only from those records and the deal history. Replay mode plays these records back with REPLAY across the sky.

---

## 11. Lobby and tallies (the honest scoreboard)

The stack of coins (balance), the mouse jar (every cent of cost, counted aloud by the Merchant once a week — the only dollar figure spoken in the game), the Buyer's cabinet (every coin ever delivered, dated), the trophy shelf (discipline trophies only), the radio (the calendar's storms), the Demo/Live badge (huge), and tallies that never merge: **by session** (dawn / noon / afternoon / night), **by weather** (calm / storm), **by patience** (shot within 30 s of arriving at the door, or after), **wooden rounds**, **ejected rounds — and what they would have done at the anvil**, and, once unlocked, **rounds with the Twin invited**. The sandbox gives no advice; the tallies let the player find his own.

---

## 12. Acceptance criteria (demo account, before any live switch)

1. Cold start to a funded round in under 15 s, with a live quote shown before anything is clickable.
2. Shooting places a real market order with broker-side SL (entry − $1.00 on 1 oz) and TP; the fill price is on the roof sign within one second of the fill event.
3. The Runner's position equals the account's floating result on every tick; the tilt follows the last ten seconds of price and never moves him by itself; a flat market is level ground.
4. Anvil, wall, haggle and machete each produce the matching broker-side change, or a visible refusal; the golden stake stands at the round's worst remaining outcome.
5. Time Freeze engages within 2 s of silence and resyncs on reconnect without a teleport; no instruction is sent during a freeze.
6. A gap through the stop produces the Void Chasm and the barrel exactly once per such fill, with the deal history's real loss.
7. Settlement, costs and every tally match the deal history to the cent.
8. Limits lock the street; Live needs the typed word; the kill switch closes and locks.
9. Zee plays ten demo rounds in one sitting without seeing a trading term on screen except the two signs — and five wooden rounds before that.

---

## 13. Decisions taken (2026-11-03) — nothing open

1. **The Twin:** in the Alley from the first wooden round; on the demo/live street only after 50 real rounds.
2. **Targets:** default $1.20; fixed choices $1.00 / $1.20 / $1.50 / $2.00 (1:1 … 1:2), chosen per round.
3. **Demo limits:** 30 rounds and $10 of loss per day.
4. **The ten-minute night:** a picture only; the Merchant never forces a close before the real session end or weekend.
5. **The golden stake** stands at `x(banked − 0.5 × stopDistance)`. Worked example: bank half at +$0.50 → $0.25 realised; if the remaining half later hits the $1.00 stop it loses $0.50; worst case −$0.25, and that is exactly where the stake stands — the runner can never be dragged past his true locked-in worst case.

---

## 14. Proof-reading record: the fallacies found in v1.1 and how v2.0 resolves them

1. **Two x-axes on one ground.** The Runner stood at a P&L coordinate while the bumps were time-ordered candles, so a candle "under his feet" meant nothing. → The ground is now a **price ladder**; bumps are a price profile of the last 20 minutes; time moved to the sky.
2. **Position mapped to gravity.** A flat market would have frozen the Runner on a slope. → Position is pinned to the floating result; tilt is the 10-second slope and drives feel only.
3. **"$1 margin, 0.01 lots."** The screenshot's 0.01 was 0.01 oz (position value $39): a $1 move on it is one cent. → One coin = **1 oz** (MT5 0.01 lot; web amount 1.00); $1 at risk by the stop distance; margin ≈ $4, never shown.
4. **The golden stake "where he stood."** It promised money the remaining half could still lose. → The stake stands at the worst remaining outcome (banked − half the stop).
5. **The 5-minute forced exit** truncated the very moves the setup is built to catch (the project's own data: winners resolve in minutes, but the target is often further than five). → Removed. Night falls as a picture; only the real session end or weekend forces a close.
6. **The barrel for every loss.** It made the ordinary stop and the catastrophic gap look the same. → Dusty at the anvil (STOPPED) for the normal loss; barrel (LIQUIDATED) only for a fill through the stop, drawn with the Void Chasm that caused it.
7. **"Statistically viable ML setup" / a wired-in entry strategy.** The ML filters tested on 1–2 Nov 2026 have no out-of-sample skill, and the project's research says the edge is in the exit, not the entry — so a mandated entry would dictate the part that matters least. → **No strategy in the game.** The bell is the session's opening bell; entries are the player's own; the tallies (by session, weather, patience) are the only teacher; the Twin is optional training wheels for discipline, never a signal.
8. **Crumbling ground behind the Runner.** Ground was price, not time, so nothing should crumble as he moves. → Ground weathers with age instead.
9. **No connection-loss state.** → Time Freeze, the stale-instruction rule, and the snapshot resync.
10. **No representation of gaps.** → Void Chasms on the ladder; anvils cannot stand in one; a fill through a chasm is the only road to the barrel.
11. **Mobile swipes on a desktop build and precise clicks during shakes.** → Hold-to-confirm on every money action, hotkeys, hit boxes in world space.
12. **No onboarding in a game with no text.** → The Paper Trading Alley with wooden tokens: same street, same live data, no orders.
13. **A 50 ms stream into a browser physics engine.** → Backend owns money; client batches per frame and pools every object.
14. **The short story.** "Shoot the Buyer to borrow the coin" left the profit mechanism unclear. → The Buyer lends the coin, the Banker buys it back cheaper; stakes become swing highs; the Vault Anvil sits above the entry.
