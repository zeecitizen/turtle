# claude_read_me — bringing the Saad compare page up (http://127.0.0.1:8772)

For: a future Claude session (or anyone) on Zee's laptop who needs the **Saad compare page** running.
That page puts Zee's TradingView Saad indicator next to the real EA `Saad_strategy_1min` in MT5, trade by trade.

Written 16 Oct 2026. Repo: `C:\Users\zeesh\turtle`, branch `feature/optimise-for-expectancy`.
The page's own bottom section, **"How MT5 is synced with TradingView"**, has the full technical background.

---

## 0. TL;DR — after a computer restart

The page should **already be up**: a watcher starts at every Windows logon (section 3). Check it:

```
py C:\Users\zeesh\turtle\monitor\saad_compare\ensure_up.py --status
```

If it says `DOWN`, or to bring it up and open it in one go:

```
py C:\Users\zeesh\turtle\monitor\saad_compare\ensure_up.py --open
```

or double-click `C:\Users\zeesh\turtle\monitor\saad_compare\start_compare_page.bat`.

`py` = `C:\Users\zeesh\AppData\Local\Programs\Python\Python312-arm64\python.exe`. This laptop uses Python 3.12 arm64. CLAUDE.md mentions Python313 and `Documents\GitHub\turtle` — both are from the old laptop.

Why a page link alone can't do this: `127.0.0.1:8772` is served by a Python process on this laptop. While that process is down, the browser has nothing to talk to, so the page cannot show a "start me" button. Something outside the browser has to start it — the watcher, the .bat file, or `ensure_up.py`.

---

## 1. What has to be running

| Piece | What it is | Needed for | How it starts |
|---|---|---|---|
| **Page server** | `monitor\saad_compare\server.py`, plain Python `http.server` on 127.0.0.1:8772. Serves `index.html` (re-read on every request, so HTML edits show on refresh) and the `/api/*` endpoints | the page itself | `ensure_up.py` (watcher at logon) |
| **Watcher** | `ensure_up.py --watch`, runs under `pythonw` (no window). Checks every 20 s and restarts the server if it died. Log: `monitor\saad_compare\server.log` | page survives crashes and restarts | Startup-folder entry `saad_compare_page.vbs` |
| **TradingView Desktop + CDP** | the chart **BLUEBERRY:XAUUSD, 1 minute**, with the indicator "Saad 15min v1.23 — mirror of the EA" on it | buttons 1, 2 and 3 (they read the chart) | Zee opens it. If the CDP bridge is down, see memory `tradingview-bridge-setup.md` (TV must be launched with CDP; MSIX build) |
| **tradingview-mcp CLI** | `node C:\Users\zeesh\Documents\GitHub\tradingview-mcp\src\cli\index.js` (Node at `C:\Program Files\nodejs\node.exe`). `server.tv()` / `tv_eval()` call it | reading the chart | nothing to start; it runs per call |
| **Blueberry MT5 terminal** | `C:\Program Files\Blueberry Markets MetaTrader 5 Terminal\terminal64.exe`, Zee's demo 12665564, data folder `%APPDATA%\MetaQuotes\Terminal\27280402C90F04230EE7E17540AE21E1` | button 2 with "Blueberry demo XAUUSD – your open terminal" | already installed. The page **closes it gracefully, runs the Strategy Tester, and reopens it**. Zee authorised this on 16 Oct 2026 |
| **Live candle bridge** (optional) | `tv_bars_bridge.py --live`: appends each closed chart candle to `%APPDATA%\MetaQuotes\Terminal\Common\Files\tv_bars_XAUUSD.csv` | **only** while `Saad_strategy_1min` trades live on a chart. The page's tests do NOT need it (they export the candles first) | `monitor\saad_compare\start_tv_bars_bridge.bat`, keep the window open. Deliberately not auto-started: it needs TradingView open |

---

## 2. `ensure_up.py` commands

```
py monitor\saad_compare\ensure_up.py              # start server.py if port 8772 is down (no console window)
py monitor\saad_compare\ensure_up.py --open       # same, then open the page in the browser
py monitor\saad_compare\ensure_up.py --status     # page UP/DOWN, logon entry installed?, live bridge running?
py monitor\saad_compare\ensure_up.py --watch      # stay running, restart the server within 20 s if it dies
py monitor\saad_compare\ensure_up.py --install    # add the logon entry AND start a watcher now
py monitor\saad_compare\ensure_up.py --uninstall  # remove the logon entry
```

Every command is safe to run any number of times. If the server is already up, nothing happens.
"Up" means `GET /api/state` answers, or at least port 8772 accepts connections: a long MT5 run holds the server's lock, but it still answers.

---

## 3. The auto-start at logon (installed 16 Oct 2026)

- **File:** `C:\Users\zeesh\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\saad_compare_page.vbs`
- **Content:** one line, `WScript.Shell.Run "pythonw.exe ensure_up.py --watch", 0` — the `0` means no window flashes at logon.
- **Remove:** `py ensure_up.py --uninstall` (a watcher already running keeps going until logoff).
- **Restore after a laptop reset:** `py ensure_up.py --install`.

To check it works after a restart: run `ensure_up.py --status`, or look at `server.log`, which gets a `--- <time> starting server.py` line each time the server starts. Tested on 16 Oct: the server was killed, and the watcher restarted it 25 s later.

---

## 4. Using the page

1. **1 · Read TradingView** reads the indicator's 91 settings by position (named from `pine/saad_15min.pine`) and every chart trade, with its exit reason, from the indicator's export table.
2. **2 · Run MT5 with these settings:**
   - Exports the chart's candles to `tv_bars_XAUUSD.csv`. This merges with the existing file and never shrinks it.
   - Runs `mt5/Saad_strategy_1min.mq5` (magic 88305) in the chosen terminal's Strategy Tester (model 4, real ticks) with the chart's settings, then lists both sides.
   - For **sync**, use "Blueberry demo XAUUSD – your open terminal" with execution delay **none**. To judge money, use **random** delay.
   - Server time is UTC+3 until the first Sunday of November, then UTC+2.
3. **3 · Check sync** (`sync_check.py`) produces a bulleted list of `ISSUE` / `FIXED` / `NOTE` / `OK`:

   | Area | What it checks | Fixes automatically? |
   |---|---|---|
   | Chart | symbol and timeframe; chart-only settings the EA does not have | no |
   | EA | every mapped setting exists as an EA input; the chart-alignment inputs (`InpBarSource`, `InpLockMode`, `InpBandAtLevel`, `InpUsdTrailMode`, `InpNoEntryExitBar`) are on | no |
   | EA build | Blueberry's compiled EA is not older than the code | yes: recompiles |
   | Candle file | equals the chart: no restated or missing candles, and it covers the first chart trade | yes: re-exports |
   | Server time | page's server-time setting matches the broker | yes: corrects the page |
   | Live bridge | running or not | no |
   | Last MT5 run | settings changed since the run; unmatched trades, each with a reason; exits in a different minute; chart vs MT5 money | no |

4. **10 months in MT5 with the chart's settings** (`year_runner.py`) is the panel after the trade table. It needs no button.
   - **How it reacts:** change a setting on the chart, and within ~4 s Jan–Oct 2026 starts running in MT5 (Axi XAUUSD_TK real ticks). Each month fills in as it finishes: trades, win rate, net, "vs before" (the effect of the change), PF and green days.
   - **Speed:** about 1.5 min for new settings. Settings run before show instantly from the cache.
   - **Controls:** the checkbox turns auto-run off. The delay selector switches between random (realistic) and none (same numbers on every run, best for comparing two settings). "Run now" re-reads the chart.
   - **Needs** the 6 rigs `C:\mt5_rig_axi2` … `C:\mt5_rig_axi7`. To rebuild one: `robocopy C:\mt5_rig_axi4 C:\mt5_rig_axiN /E /XD Tester logs reports`. Add new rigs to `RIGS` in `monitor\strategy_labxi_rig.py` and `year_runner.py`.
   - **Cache:** `monitor\saad_compare\why_out\year_cache.json`; delete it to force fresh runs.

Last result for 12–15 Oct 2026: **83 of 83** chart trades identical in MT5 (EA v1.04).

---

## 5. Files

```
monitor\saad_compare\
  server.py                  page server + /api/tv, /api/mt5, /api/sync, /api/state
  index.html                 the page (incl. "How MT5 is synced with TradingView" at the bottom)
  sync_check.py              the "3 · Check sync" checks
  tv_bars_bridge.py          chart candles -> Common\Files\tv_bars_XAUUSD.csv (--export / --live)
  ensure_up.py               start / watch / install the page server
  year_runner.py             "10 months in MT5": watches the chart's settings, runs Jan-Oct on 6 rigs, caches by settings
  why_compare.py             trade-by-trade with exit reasons from the EA log (py why_compare.py 2026.10.11 2026.10.17)
  start_compare_page.bat     ensure_up.py --open
  start_tv_bars_bridge.bat   tv_bars_bridge.py --export --live (live trading only)
  server.log                 server output (git-ignored)
monitor\strategy_lab\axi_rig.py   tester INI writer (ini_input: string inputs must be plain k=v) + report parser
mt5\Saad_strategy_1min.mq5        the EA (v1.04)
pine\saad_15min.pine              the indicator
saad_strategy_1min_optimized\     Zee's frozen optimized settings (README.md, .set, indicator code, screenshots) + this file
```

---

## 6. When something fails

| Symptom | Cause / fix |
|---|---|
| Browser: "can't reach 127.0.0.1" | Server down. `py ensure_up.py --open`. If it doesn't come up, read `monitor\saad_compare\server.log` (usually a Python error after an edit; run `py monitor\saad_compare\server.py` in a terminal to see it). |
| Port 8772 taken by an old server running old code | `server.py` imports `sync_check` once, so restart after editing it. Kill it with `Get-CimInstance Win32_Process -Filter "Name like 'python%'" \| ? { $_.CommandLine -like '*saad_compare*server.py*' } \| % { Stop-Process -Id $_.ProcessId -Force }`; the watcher restarts it within 20 s. |
| "TradingView bridge: …" / "no Saad indicator on the chart" | TradingView not running with CDP, or the indicator is not on the chart. |
| "the chart has N settings but pine/saad_15min.pine declares M" | The chart's copy of the indicator is older or newer than the file. Inject with `pine/inject_pine.py --force` and click "Update on chart" (memory `pine-save-and-chart-update.md`). |
| "the Blueberry terminal did not close (a dialog open?)" | Close the dialog in MT5, press 2 again. |
| "the Blueberry tester wrote no report" | See the terminal's Journal. `BB_DATA\reports\` must exist (the server creates it). |
| MT5 runs but takes 0 trades | Tester log `…\Tester\27280402…\Agent-*\logs\*.log`. "cannot read Common\Files\tv_bars_XAUUSD.csv" = run `py tv_bars_bridge.py --export`. A string input written in the `||` range form gives the same symptom (`axi_rig.ini_input` handles it). |
| No MT5 trades on today's date | The Blueberry tester usually has no ticks for the current day yet. |

**Never** copy or read the Blueberry terminal's `accounts.dat` / `servers.dat`; that was refused as credential access. Use the open terminal as described.
**Remember:** matching the chart does not mean profitable. The same settings lost −$53,632 on Axi XAUUSD_TK, 15 Sep – 15 Oct. See `VERSION_HISTORY.md`.
