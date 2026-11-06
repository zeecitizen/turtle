# Install and run: the UHV game + Turtle TV UHV on any Windows computer

This folder is a **one-stop copy** of everything needed:

| Folder | What it is | Address |
|---|---|---|
| `monitor/TurtleTVUHV/` | **Turtle TV UHV**: the tick tester, Exit Lab scanner, list of trades, saved settings | http://127.0.0.1:8774/ |
| `games/gold_runner/` | **Golden Gravity**: the game, its server, the live PrimeXBT bridge, the angel | http://127.0.0.1:8790/ |
| `monitor/strategy_lab/`, `monitor/saad_compare/`, `monitor/doctrine.py` | helper modules the Turtle TV server imports | — |
| `mt5/` | MT5 EAs: `ZeeUHV_TurtleTV.mq5` (the UHV EA) and the Saad EAs the server reads | — |
| `bot/u97_bot.py` | the bot that plays the angel's blessed signals live | — |
| `START_ALL.bat` | starts everything in one double-click | — |

Documents: `HOW_WE_REACHED_100_PERCENT.md` (the strategy story), `RISK_MANAGER.md` (the angel).

The folder layout mirrors the main repo (`monitor/…`, `games/…`, `mt5/…`) on purpose: the code finds its helpers by
relative paths.

---

## 1. Get the files

**Option A, from GitHub** (branch `UHV_Winning_Game`):
```
git lfs install
git clone --branch UHV_Winning_Game --single-branch https://github.com/zeecitizen/turtle.git
cd turtle\winning_UHV_strategy
git lfs pull
```
Git LFS is required. The tick database `monitor/TurtleTVUHV/simdata/uhv_ticks_all.npz` (435 MB) is stored with LFS.
Without it Turtle TV UHV cannot run. Install Git LFS from https://git-lfs.com (it comes with Git for Windows).

**Option B:** copy this whole `winning_UHV_strategy` folder on a USB stick.

## 2. Install Python and packages

1. Install **Python 3.12** (the tested version is 3.12.10) from python.org. Tick "Add python.exe to PATH".
2. Open a terminal in `winning_UHV_strategy` and run:
   ```
   py -m pip install -r requirements.txt
   ```
   Packages: numpy, numba, pandas, websocket-client. Tested versions: numpy 2.5.3, numba 0.68, pandas 3.0.6.
3. On ARM laptops (Snapdragon), set `NUMBA_CPU_NAME=generic` before starting Turtle TV. `START_ALL.bat` does this
   for you.

## 3. Google Chrome (only for LIVE play)

The game trades through **your logged-in PrimeXBT page in Chrome**, controlled over the DevTools port 9222.

- `START_ALL.bat` starts a separate Chrome with `--remote-debugging-port=9222` and its own profile folder
  `games/gold_runner/chrome_profile`, opening the PrimeXBT EUR/USD page.
- **Log in to PrimeXBT once in that window, and keep it open.** That window holds the session.
- **Keep the PrimeXBT tab VISIBLE**, in its own window, not minimized. Chrome freezes hidden tabs and the quotes stop:
  the game then shows "no_feed" and refuses to trade. Also add primexbt.com under Chrome Settings → Performance →
  "Always keep these sites active".
- The Chrome profile is **never** in Git: it holds your login.

> If your PrimeXBT account number differs from `l1869984`, edit `PXURL` in `START_ALL.bat` and the account in
> `games/gold_runner/state/admin.json`.

## 4. Start everything

Double-click **`START_ALL.bat`**. It:
1. starts **Turtle TV UHV** (`py monitor\TurtleTVUHV\server.py`) on port 8774;
2. starts the debug Chrome on 9222 with PrimeXBT, unless something already answers on 9222;
3. starts the **game server in LIVE mode** (`py games\gold_runner\server.py --mode live`) on port 8790;
4. opens http://127.0.0.1:8774/ and http://127.0.0.1:8790/.

**Practice without money:** `games\gold_runner\start_game_sim.bat` (synthetic market, no Chrome).

### Manual start, one by one
```
cd monitor\TurtleTVUHV
set NUMBA_CPU_NAME=generic
py server.py                          → http://127.0.0.1:8774/

cd games\gold_runner
py server.py --mode live              → http://127.0.0.1:8790/   (or --mode sim)
```

### The bot (optional, plays live for you)
```
cd bot
py u97_bot.py
```
- **Budget:** edit `BUDGET_USD` / `FLOOR_FIXED` at the top. It stops when the balance reaches the floor.
- **Stop it:** create a file named `STOP_BOT` in the bot folder, or press Ctrl+C.
- **What it does:** shoots only on the angel's blessed signals, and only after 2 minutes of fresh quotes. It ejects
  at −2 pips, and stops if the win rate falls under 94% after 20 rounds.

## 5. Using it

**Turtle TV UHV (8774):**
- Load the saved setting **`2026-11-06 16-00-00`**: the angel zone + Friday cut + 1-touch wall, 610 trades / 0 losses
  in Python.
- **List of trades:** every loss carries your comment box and Claude's chart reading.
- **Exit Lab → Scan:** tunes every setting; STOP SCAN kills a running scan.
- **The first run after a fresh install** builds `simdata/det_cache` and `sim_cache`, so it is slow for a few minutes.
  Later runs are fast.

**Golden Gravity (8790):**
- **Live consent:** the game asks you to type CONFIRM once per day. It is saved in `state/live_signed.json`.
- **Safety:** K = kill switch, space = eject.
- **What you'll see:** the yogi appears when a setup forms; the angel blesses (bubble) or blocks (light shields); the
  sky shows the risk level (sun = zero risk, rain, storm with thunder).
- **Real-money limits** are in `state/admin.json` (EURUSD profile): `coin_oz` 5000, `coins_max` 10, `live_max_qty`
  50000, `loss_max_balance_pct` 0.50.

## 6. Rebuilding the tick data (only if you have new ticks)

`monitor/TurtleTVUHV/uhv_ticks.py` rebuilds `simdata/uhv_ticks_all.npz` from a PrimeXBT MT5 tick export, e.g.
`EURUSDp_202603060000_202611042359.csv`. Edit the `TICKS = Path(...)` line at the top to point to your CSV, then run
`py uhv_ticks.py`. Delete `simdata/det_cache` and `simdata/sim_cache` afterwards.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| Game shows `no_feed` / "quotes stale" | the PrimeXBT tab is hidden or frozen: bring it to the front, in its own window |
| "Network.enable failed" | same cause; or Chrome was started without `--remote-debugging-port=9222` |
| Port 8790 / 8774 taken | an old server is still running: close its window, or end the python process |
| Turtle TV: `ModuleNotFoundError` | run `py -m pip install -r requirements.txt` |
| Turtle TV very slow on first run | normal: the caches are being built |
| `uhv_ticks_all.npz` is a tiny text file | Git LFS was not pulled: run `git lfs pull` |
| Turtle TV "research paper" page fails | it needs `monitor/.claude_api_key` (not included, it's secret) |

## 8. What is deliberately NOT included
- `games/gold_runner/chrome_profile/`: your PrimeXBT login.
- `games/gold_runner/recordings/`: raw websocket recordings, which can carry session tokens.
- `state/live_signed.json` (daily consent) and `feeds_live_owned.json` (a local lock).
- `simdata/det_cache`, `simdata/sim_cache`: rebuilt automatically.
- `monitor/.claude_api_key`.
