# Claude EA — desktop app and Windows installer

Turns the vision-driven trading system into something you can install on any Windows PC.
Zee's reason: *"what if ye laptop koi chura kr le jaey? do we loose everything?"* — the
answer is no, and this makes recovery a two-minute job on a new machine.

---

## What the app does

`gui/claude_ea_gui.py` is a control panel:

| Button / panel | What it does |
|---|---|
| **▶ START EVERYTHING** | launches TradingView+CDP, the data bridge, the dashboards |
| **🧠 BEGIN AI EA TRADING** | opens a Claude Code session on this repo, pre-prompted to read `CLAUDE_REALTIME_EA.md` and resume live judging — **this is the piece that makes the GUI complete: it does not replace Claude, it starts her** |
| **📸 Snap now** | captures the live chart to `monitor/setup_labels/live.png` |
| **SYSTEM STATUS** | CDP, data symbol + freshness, bridge, both dashboards, pending setup |
| **ARMED** | a retracement+UHV exists, breakout not fired yet, distance to the level |
| **VERDICTS** | Claude's recent TAKE/SKIP calls with reasons |
| **REAL BROKER FILLS** | actual P&L from the EA, plus a running total |
| **MANUAL OVERRIDE** | TAKE 1x / 2x / SKIP for when no Claude session is running |

Run it directly with no build step:
```
pythonw gui\claude_ea_gui.py
```

---

## Build a standalone .exe

```bat
cd gui
build_exe.bat
```
Produces `gui\dist\ClaudeEA.exe` — a single file, no Python needed on the target PC.
(Requires `pip install pyinstaller` once.)

## Build the installer (setup.exe)

1. Install **Inno Setup** (free): https://jrsoftware.org/isdl.php
2. Build the exe first (above).
3. Open `gui\installer.iss` in Inno Setup and press **Compile**.

Produces `gui\Output\ClaudeEA-Setup.exe` — a normal Windows installer with a Start-menu
entry and a desktop shortcut.

---

## Setting up a NEW machine (e.g. after the laptop is lost)

1. `git clone https://github.com/zeecitizen/turtle.git`
2. Install Python 3.13, then `pip install websockets matplotlib mplfinance pandas anthropic`
3. Install **MetaTrader 5**, log into **BlueberryMarkets-Demo**, attach the EA from
   `mt5\` (F7 to compile), Algo Trading ON.
4. Install **TradingView Desktop**, log in, chart on `COINBASE:BTCUSD` or `OANDA:XAUUSD`.
5. Run `ClaudeEA-Setup.exe` (or `pythonw gui\claude_ea_gui.py`).
6. Press **START EVERYTHING**, then **BEGIN AI EA TRADING**.
7. Claude reads `CLAUDE_REALTIME_EA.md` and resumes exactly where things left off.

**What is NOT in the repo and must be restored by hand** (keep these in a password manager):
- `monitor\.claude_api_key`, `monitor\.whatsapp_config.json`, `monitor\.dashboard_password`
- the cloudflared tunnel credentials in `~\.cloudflared\` (these control the
  `claudezeeshan.com` subdomains — **revoke them from the Cloudflare dashboard if a machine
  is ever lost**)
- MT5 account logins

**Security, while we are here:** remove the saved password for the **real** `Live02`
account from MT5 — the demo is harmless, a live account on a stolen laptop is not — and
turn on BitLocker.
