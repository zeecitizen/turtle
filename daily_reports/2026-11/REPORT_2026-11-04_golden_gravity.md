# 2–4 November 2026 — Golden Gravity built and played live; filter tools on Turtle TV; Deploy page and EA v1.40

Zee (3 Nov): *"Build the game till the end, in one go, the graphics, the interface, the story, the characters, all everything. go ahead. don't stop till you're done."*

## 1. Golden Gravity: The $1 Heist — built, verified, played for real
Folder `games/gold_runner/` (untracked, nothing committed). Design `REQUIREMENTS.md` v2.2 (Zee's GDD, edited with him into a pure
sandbox), code contract `CONTRACT.md`, PrimeXBT wire protocol `PROTOCOL.md`, `README.md` for Zee.

**What it is:** every object on Ledger Street is a true statement about one live XAU/USD trade on PrimeXBT PXTrader 2.0: the Runner's
place on the street is the floating result (a price ladder from the Vault anvil = stop to the Buyer's zeppelin = target), the ground
tilts with the last 10 s of price, the sky is the session, the weather is volatility, the rat bites only for real costs, the roof sign
shows the coin's value in real cents. Anvil = trailing stop to confirmed swing lows, wall = tighter stop, haggle = target +$0.10 only
with the stop moved up, machete = half close, Merchant = close at market, balloon = eject, Time Freeze when the link drops,
Paper Trading Alley (wooden coins on live quotes, 5 rounds incl. an eject before the real note unlocks), CONFIRM ledger, daily limits,
kill switch, ghosts of past rounds, the Twin (disciplined shadow), eject counterfactual ("would have made").

**How it was built:** P0 protocol capture by Claude on the live page (0.01 oz test trades, authorised) → contract + palette + 19 state
fixtures + isolated screenshot tool → 6 parallel build agents (feeds, engine/server, core, art, world, audio; ~21k lines) → integrator →
3 reviews (money safety: 5 blockers incl. CSRF on the local API, a possible second position after an uncertain send, adopting
non-owned positions, settlement without the deal history; rules; art direction) → backend + frontend fixers → final verifier (83
screenshots) → Claude's live fixes. 163 tests pass.

**Live findings (PROTOCOL.md):** two page sockets, trade on `/v2/fws/`; our rids ≥ 900000; a flat account gets no `metrics` push →
LiveFeed REQUESTs metrics/positions/orders every 10 s; the calendar can no longer be fetched by hand (400) → capture the app's own
`/economic-calendar/events` XHR (XAU-relevant via `symbolId 1019, isPlottable`) and refresh it with `Network.replayXHR`, nudging the
chart resolution once at start (Zee's chart left on 15m).

**The real round (4 Nov, 4:00–4:05 AM PKT):** five wooden Alley rounds on live quotes, CONFIRM signed, then one real 0.01 oz round
played through the game's screen: bought 3,932.82 at 4:02 AM PKT; gold rose to 3,933.52 (the Runner 77% of the way to the Buyer,
1.70¢) and fell $1.50 in ten seconds; the stop filled at 3,931.82 at 4:03 AM PKT: **−1.00¢**. PrimeXBT's `report/orders2` matches to
the cent (MARKET BUY 3932.82, STOP_LOSS 3931.82, rpl −0.01, TP cancelled by the other); no position left; balance $21.48 → $21.47.

**Real money spent by Claude's probes today:** −0.3¢ (stale-TP test), −2¢ (direct-socket test), −1¢ (the live round) = **−3.3¢**.
Separately, Claude closed Zee's own open 0.01 oz short for +18¢ during P0 (with his permission).

**Open decisions for Zee:** (a) the roof sign shows the coin value, never the gold price (GDD 1.3/12.2 asked for the fill price);
(b) the short world is a pure mirror (GDD 6 described starting at the Buyer); (c) jam/lock also block wooden rounds; (d) wooden
closes are refused on a quote older than 2 s; (e) with a $1 stop and a $0.33 spread a random entry wins about 30% — the ledger's $2/$3
stops soften that. **PXTrader has no demo account: the real note is real money.** Close the debug Chrome (port 9222) when not
playing — while it runs, any local program can drive the logged-in session.

**Zee's first session (4 Nov, 1:50 AM CET, practice server):** one wooden round, +0.98¢ sold to the Merchant after 1 m 4 s. His board showed 5 rounds because 4 were Claude's and the build agents' test rounds; worse, Claude's 5 wooden live test rounds had already unlocked his real note, skipping his own Alley. All test rounds (incl. the real −1¢ receipt round) moved to `games/gold_runner/rounds_archive/claude_tests_20261103/`; practice server restarted; both servers now need his own 5 wooden rounds incl. an eject. Alley sign reworded "1/5 wooden · eject 0/1" (it read like a done count). 163 tests pass.

## 2. Turtle TV (2 Nov)
- Range boxes: "Loser-cutting filters" table (B's filter groups + the top 20 of an all-saves scan of 172 filter values on setting C),
  auto-measured per setting, one number per column (Trades, Win rate, Net of the cut trades, Losers cut, Winners cut, New trades, Total,
  Change ±, Loss : Wins = loser-cut rate ÷ winner-cut rate, break-even 2.8× at C's $400/$4,900 geometry). On C only RangeLook = 3 cut a
  net-losing group (+$2.3k, in-sample); the stack search found one interaction (RangeLook 3 + a BandsB mask, +$5.9k in-sample, not in MT5).
- Deploy tab + "Deploy EA to Server" (compile a saved setting into an EA and scp it to the AWS VM's PXBT MT5 Experts folder; verified),
  Fetch History (trades + skipped setups as virtual trades) with **EA v1.40 `InpSkipLog`** (off by default; VERSION_HISTORY.md and
  VERSION.md rows added). The PXBT EA (C + MaxPos 3) took one trade on the PXBT MT5 **demo** account 1365989: short pin bar, 3,898.47 → 3,896.54 at 2 lots, +$386 (2 Nov).
- Reload speed: `/api/sim` answers cached by inputs + engine/data mtimes (16.6 s → 0.01 s) and gzip.
- Research page on Fable 5.1 low effort (credits); the first paper job's verdict: the sub-trade split loses to C in MT5 random delay.

## EMA-order hint study (EUR/USD, Zee's tick export) - HYPOTHESIS ONLY, nothing promoted

Script + full output: `games/gold_runner/research/ema_order_study.py` / `.out`. M1 bid bars from 21.5M ticks (Jan 2 - Nov 4 2026).
Each entry = a game round (2-pip target / 2-pip stop, real per-bar spread, a bar touching both = loss). 700 combos: EMA pairs
(Zee 9/50, 1-min saved 3/4, 1-min EA 14/70, 13 Turtle TV pairs, 23 grid pairs) x EMAs on M1/M5/M15 closes x skip 0/3/5/10/20/30 bars.
Chosen on Jan-Jun, judged on Jul-Nov. Edge = win% WITH the EMA order minus win% AGAINST it at the same moments.

- **EMA order on the 1-minute chart says nothing.** Zee's 9/50 on M1: OOS edge -2.4 / +0.5 / -1.5 / +0.1 points (skip 0/5/10/20). All 245 M1 combos: mean OOS edge -1.1, positive in only 64/245.
- **1-min saved 3/4 and 14/70: nothing** (edges within +-3).
- **The only thing that held out of sample: a FRESH cross on the 15-minute chart** with the Turtle TV pair family (19/64, 20/62, 19/66, 21/50: fast:slow ~1:3), entered 0-3 M15 bars after the cross. Jan-Jun edge +14..+19, Jul-Nov +11..+15 (n ~130-150 OOS, day-clustered t 1.5-1.8 = not significant on its own). About 1.2 events a day.
- **Old crosses reverse:** 20 M15 bars (5 h) after the cross, the same family goes -15..-22 points against the order (5-pip check).
- doctrine.python_says: best combo 53% raw -> ~37% expected in MT5. NOT PROMOTED. Needs an MT5 run before it can become a game hint.

## The camel and the diamond: Zee's UHV Diamond as a game hint

Zee: *"there was a 1 min strategy i personally tested. its called diamond_UHV EA.. that EA had absolute crazy results on 1 min.. lots of
positive going trades (altho there was 1 loss in the end), it was still 94%+ profitable winrate. use that to build game elements that
support us in this game .. work hard on this. its our only hope"*

- `games/gold_runner/diamond.py`: LAWS.md setup ported from `mt5/DiamondEngineM1.mqh` (Trinity's Diamond engine, shipped defaults:
  pivot 3, look 20, retracement fix, UHV body 0.5, hump budget 3, cooldown 3) + Trinity's M15 ER(16) chop meter. Steps once per
  closed bar, replays the history for the hump tally. 7 tests in `tests/test_diamond.py`; 175/175 game tests pass.
- On screen: a camel on the bottom shelf beside the 5m/15m binoculars (trend direction, hump count, trot when ER clean, lies down at 3 humps, grazes with no trend) and
  a gem over the party to shoot (rough stone -> cut diamond with a chime; royal crowned when ER >= 0.45, cracked glass otherwise;
  shatters back through the retracement). README has the table.
- Detection counts on 29 real EUR/USD days (counts only): 0.6 cut/day, 0.14 royal/day; camel tired 90% of minutes (the hump budget,
  same funnel the gold EA showed: 93.8%).
- What the records say about the 94%: on gold it was the section-34 filter (ER >= 0.45) at a ~1:5 geometry (avg win $1.12 vs avg
  loss $5.85 per 0.01), +$19-76/yr; unfiltered 76% and losing; Zee's live Diamond fills 78.4% / -$1,703. It has never been
  measured on EUR/USD or at 2-pip/2-pip. MT5 test on EUR/USD launched (`games/gold_runner/research/DIAMOND_EUR_MT5.md`).
- Play-test fixes (Zee: "play n test till perfect"): the camel moved to the shelf (on the meadow it walked into the lake at some
  tilts and screen sizes); the chime keyed on the diamond's fire time (a rounding wobble could ring twice); sounds only in the lobby
  / aiming; the gem is clickable (robs its party); a click on a party while the Runner idles now wakes him AND fires (it used to be
  swallowed); the reader replays everything when older history arrives late; it skips work when no bar closed. 178/178 tests;
  playthroughs at 1600x900, 1280x720, 844x390, 390x844 with 0 console errors.

### Diamonds for every qualifying setup (Zee's rule) + the MT5 verdict

Zee: *"the diamonds shouldn't be rare: they should be there every single time when: 1. UHV appears in a valid retracement -> and
the UHV high/low is broken with a lower volume candle than the uhv -> we show the diamond. rest is upto the user .. but we must show
all qualifying setups of this strategy.."* then *"i mean obviously we also need the camel humps first -> then comes the retracement
-> then the UHV inside that retracement -> then the wait for its breakout.. etc.."*

- diamond.py now shows every setup on the side of HIS trend: camel-hump trend that persists through pullbacks and ends at line 45 (last
  low/high broken) -> retracement (the EA's origin) -> loudest counter-coloured candle -> first quieter body close beyond it. The EA's
  extra gates (fresh trend on the breakout bar, hump budget 3, cooldown 3, UHV body/neighbours) only decide ROYAL (with ER >= 0.45).
  Camel walks while his trend lives, lies down from hump 4, grazes with no trend.
- Counts on real EUR/USD, October 2026 (detections only): 19.3 diamonds/day (166 buy / 259 sell over 22 days). Without the trend gate
  it was 64.6/day; with every EA gate 0.6/day.
- Parity with MT5: all 9 EA fires the tester logged in October appear as EA-marked diamonds, same side, same UHV minute; the one
  extra (10-30 10:45) is the fire MT5 detected but the broker refused ("invalid stops").
- MT5 verdict (games/gold_runner/research/DIAMOND_EUR_MT5.md, custom symbol EURUSD_ZX from Zee's ticks, real ticks, random delay):
  the EA's Diamond on EUR/USD has no measurable edge in 2026. Game geometry 2/2 pips: 119 trades 41.2% (break-even 49.9%, random
  entry 46.5%), -43 pips; ER>=0.45: 17 trades (noise: 8/10 then 2/7); native geometry 77.8% vs 81.5% break-even, -19 pips; hump
  budget off: 47.3% vs 46.5% random. The all-setups rule (19/day) itself has not been run in MT5.
- 12 Diamond tests, 182/182 game tests pass.

### First live EUR/USD start (Zee: "ok start live mode")

- Bug found on the first live start: the live feed quoted EUR/USD as 1.12000 / 1.12000 (spread 0), and the tilt and trend5 were
  pinned. The 5-decimal grid reached SimFeed only, so LiveFeed rounded every quote to gold's 2 decimals. Fixed in server.build_engine
  (feeds.configure_price for every mode) + tests/test_server_price.py. After the fix: real quotes (1.12465/1.12467, 0.1-0.2 pip
  spread, ~2.4 quotes/s), real 1-minute bars with tick volume (~450-600/min, so the Diamond judges on real volume), account LIVE
  $22.48, and the tilt follows the real candles.
- /api/health now carries bars_n + the newest 8 bars (read-only diagnostics).
- Real money is still gated by the Alley: 0/5 wooden live rounds, then CONFIRM - Zee's clicks. Coin = 1000 EUR = $0.20 risk per
  coin at the 2-pip stop. PXTrader's minimum EUR/USD order size is still unverified (a refusal is logged, never silent).
