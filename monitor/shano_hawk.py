"""Shano Hawk — Fully Autonomous Trading Daemon.

Reads TradingView signals, fires trades via PineConnector webhook,
monitors positions in real-time, implements Shano-style exits.
Survives crashes, resumes mid-trade, runs without Claude.

Usage:
    python shano_hawk.py                    # run forever
    python shano_hawk.py --once             # single scan
    python shano_hawk.py --dry-run          # no real trades
    python shano_hawk.py --status           # show state
    python shano_hawk.py --reset-session    # reset session counters

Config (edit .shano_state.json or use shano_scanner.py):
    python shano_scanner.py --symbol=XAUUSDm --lots=0.40 --direction=sell_only
"""

import json, subprocess, sys, time, os, signal
from datetime import datetime
from pathlib import Path
from threading import Thread, Event

if sys.platform == "win32":
    _CNW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    _orig_run = subprocess.run
    _orig_popen_init = subprocess.Popen.__init__

    def _run_silent(*a, **kw):
        kw["creationflags"] = kw.get("creationflags", 0) | _CNW
        return _orig_run(*a, **kw)

    def _popen_silent(self, *a, **kw):
        kw["creationflags"] = kw.get("creationflags", 0) | _CNW
        return _orig_popen_init(self, *a, **kw)

    subprocess.run = _run_silent
    subprocess.Popen.__init__ = _popen_silent

# ============================================================
#  PATHS
# ============================================================
SCRIPT_DIR = Path(__file__).parent
STATE_FILE = SCRIPT_DIR / ".shano_state.json"
PID_FILE = SCRIPT_DIR / ".shano_hawk.pid"
LOG_FILE = SCRIPT_DIR / "shano_hawk.log"
FILLS_CSV = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv")
PYTHON = r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"
NODE = r"C:\Program Files\nodejs\node.exe"
TV_CLI = r"C:\Users\zeesh\Documents\GitHub\tradingview-mcp\src\cli\index.js"
WEBHOOK_SCRIPT = SCRIPT_DIR / "pc_webhook.py"

# ============================================================
#  CONFIG DEFAULTS
# ============================================================
DEFAULTS = {
    # Trading config
    "symbol": "BTCUSD",
    "pc_symbol": "BTCUSD",       # PineConnector symbol (may differ)
    "lots": "0.10",
    "tp": "2000",                 # pips for PineConnector
    "sl": "300",                  # pips for PineConnector
    "direction": "both",          # both / buy_only / sell_only
    "enabled": True,

    # Signal tracking
    "last_fired": 0,
    "total_fired": 0,

    # Active position (crash recovery)
    "active_trade": None,         # {num, dir, entry_price, entry_time, peak_pnl}

    # Session stats
    "session_start": None,
    "session_pnl": 0.0,
    "session_trades": 0,
    "session_wins": 0,
    "session_losses": 0,

    # Position monitor config
    "monitor_interval": 5,        # seconds between tick checks when in trade
    "signal_interval": 5,         # seconds between signal scans (was 30, dropped for fast probe-fire — counter detection makes this safe)
    "last_buys_seen": 0,          # tracks Pine's buy counter to infer new signal direction
    "shano_exit": False,          # true = trailing exit (close when P&L drops)
    "trail_trigger": 10.0,        # start trailing after $10 profit
    "trail_drop": 3.0,            # close if profit drops $3 from peak

    # Fills tracking
    "last_fills_line": 0,
    "trades": []
}

# ============================================================
#  GLOBALS
# ============================================================
running = True
stop_event = Event()

def handle_signal(sig, frame):
    global running
    running = False
    stop_event.set()
    print("\n[HAWK] Shutdown signal received...")

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

# ============================================================
#  STATE MANAGEMENT
# ============================================================
def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            saved = json.load(f)
        return {**DEFAULTS, **saved}
    return DEFAULTS.copy()

def save_state(state):
    state["trades"] = state.get("trades", [])[-50:]
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ============================================================
#  PID FILE (prevent duplicate instances)
# ============================================================
def check_pid():
    if PID_FILE.exists():
        old_pid = PID_FILE.read_text().strip()
        # Check if process is still running
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {old_pid}"],
                capture_output=True, text=True
            )
            if f" {old_pid} " in result.stdout:
                print(f"[HAWK] Already running (PID {old_pid}). Kill it first or delete {PID_FILE}")
                sys.exit(1)
        except:
            pass
    PID_FILE.write_text(str(os.getpid()))

def remove_pid():
    if PID_FILE.exists():
        PID_FILE.unlink()

# ============================================================
#  LOGGING
# ============================================================
def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] [{level}] {msg}\n")

def log_quiet(msg):
    """Overwrite current line (for idle/tick updates)."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\r[{ts}] {msg}          ", end="", flush=True)

# ============================================================
#  TRADINGVIEW DATA (via Node.js CLI)
# ============================================================
def tv_call(cmd_args):
    """Call TradingView CLI and return parsed JSON."""
    try:
        full_cmd = [NODE, TV_CLI] + cmd_args
        result = subprocess.run(
            full_cmd, capture_output=True, text=True, timeout=15,
            cwd=str(Path(TV_CLI).parent.parent)
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except:
        return None

def read_indicator_state():
    """Read Shano indicator table from TradingView."""
    data = tv_call(["data", "tables", "--study-filter=Shano"])
    if not data or not data.get("success") or data.get("study_count", 0) == 0:
        return None

    rows = data["studies"][0]["tables"][0]["rows"]
    info = {}

    for row in rows:
        if "Status |" in row:
            s = row.split("| ", 1)[1].strip()
            info["status_raw"] = s
            if "IDLE" in s:
                info["state"] = "IDLE"
            elif "PROBING" in s:
                info["state"] = "PROBING"
                if "#" in s: info["trade_num"] = int(s.split("#")[1].split(" ")[0])
                info["dir"] = "buy" if "(LONG" in s else "sell" if "(SHORT" in s else "?"
            elif "TRADING" in s:
                info["state"] = "TRADING"
                if "#" in s: info["trade_num"] = int(s.split("#")[1].split(" ")[0])
                info["dir"] = "buy" if "(LONG" in s else "sell" if "(SHORT" in s else "?"
            elif "COOLDOWN" in s:
                info["state"] = "COOLDOWN"
            else:
                info["state"] = s.split(" ")[0] if s else "UNKNOWN"

        elif "Live Trade |" in row:
            lt = row.split("| ", 1)[1].strip()
            if lt != "---":
                parts = lt.split("|")
                try:
                    info["live_pnl"] = float(parts[0].strip().replace("$", ""))
                except:
                    info["live_pnl"] = 0.0

        elif "TODAY |" in row:
            info["today_raw"] = row

        elif "Signals |" in row:
            # "Signals | 297  (B:0 S:297)" — total monotonically-increasing counter,
            # robust against state machine resolving faster than poll interval.
            v = row.split("| ", 1)[1].strip()
            try:
                info["signal_count"] = int(v.split()[0])
            except (ValueError, IndexError):
                info["signal_count"] = 0
            # Direction split — used to skip buy-only signals when sell-only mode is on
            try:
                inside = v[v.index("(") + 1: v.rindex(")")]
                for part in inside.split():
                    if part.startswith("B:"): info["buys"] = int(part[2:])
                    elif part.startswith("S:"): info["sells"] = int(part[2:])
            except (ValueError, IndexError):
                pass

    return info

_LAST_PRICE_FILE = SCRIPT_DIR / ".shano_last_price.json"

def get_current_price():
    """Get current XAUUSD price from TradingView CLI and persist for dashboard.

    TV CLI 'quote' returns { success, last, close, open, high, low, volume, ... }
    at top level — no nested 'quote' key. (Was incorrectly parsing as nested before.)
    """
    data = tv_call(["quote"])
    if data and data.get("success"):
        last = data.get("last") or data.get("close")
        if last is None:
            return None
        out = {
            "last": last,
            "bid": data.get("bid", last),
            "ask": data.get("ask", last),
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            _LAST_PRICE_FILE.write_text(json.dumps(out, separators=(",", ":")))
        except Exception:
            pass
        return out
    return None

# ============================================================
#  TRADE EXECUTION (via PineConnector webhook)
# ============================================================
def fire_trade(direction, state, dry_run=False):
    """Open a trade on MT5 via PineConnector webhook. NO TP/SL — Shano style."""
    args = [direction, state["pc_symbol"], state["lots"]]
    # NO TP/SL — hawk closes trade when sim exits (Shano style)

    cmd = [PYTHON, str(WEBHOOK_SCRIPT)] + args
    log(f"{'[DRY] ' if dry_run else ''}FIRE {direction.upper()} {state['pc_symbol']} {state['lots']} lots (NO TP/SL — hawk manages exit)")

    if dry_run:
        return True

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        log(f"  -> {result.stdout.strip()}")
        return result.returncode == 0
    except Exception as e:
        log(f"  -> FAILED: {e}", "ERROR")
        return False

def close_trade(direction, state, dry_run=False):
    """Close a trade on MT5."""
    close_dir = "closelong" if direction == "buy" else "closeshort"
    cmd = [PYTHON, str(WEBHOOK_SCRIPT), close_dir, state["pc_symbol"]]
    log(f"{'[DRY] ' if dry_run else ''}CLOSE {close_dir} {state['pc_symbol']}")

    if dry_run:
        return True

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        log(f"  -> {result.stdout.strip()}")
        return True
    except Exception as e:
        log(f"  -> CLOSE FAILED: {e}", "ERROR")
        return False

# ============================================================
#  MT5 FILLS MONITOR
# ============================================================
def check_new_fills(state):
    """Check turtle_fills.csv for newly CLOSED trades.

    Filters:
    - Only "_closed" actions (skip "_open" lines, those have profit=0).
    - Only deal_id != "0" — TurtleTradeLogger writes TWO lines per close:
        one EA-snapshot (deal_id=0) and one MT5-confirmed (deal_id>0).
        Counting both inflates session_pnl. We trust the deal_id>0 record.
    """
    if not FILLS_CSV.exists():
        return []

    try:
        with open(FILLS_CSV, "r") as f:
            lines = f.readlines()

        last_pos = state.get("last_fills_line", 0)
        new_lines = lines[last_pos:]
        state["last_fills_line"] = len(lines)

        fills = []
        sym = state["symbol"]
        for line in new_lines:
            if sym not in line:
                continue
            parts = line.strip().split(",")
            if len(parts) < 11:
                continue
            deal_id = parts[1]
            action  = parts[4]
            # Skip opens (no realized P&L) and EA-snapshot dupes
            if not action.endswith("_closed"):
                continue
            if not deal_id or deal_id == "0":
                continue
            try:
                fills.append({
                    "time":   parts[0],
                    "dir":    action,
                    "lots":   parts[5],
                    "price":  parts[6],
                    "pnl":    float(parts[10]) if parts[10] else 0,
                    "ticket": parts[2],
                })
            except (ValueError, IndexError):
                pass
        return fills
    except Exception:
        return []

# ============================================================
#  CRASH RECOVERY
# ============================================================
def recover_state(state):
    """On startup, check if we have an active trade to resume."""
    active = state.get("active_trade")
    if active:
        log(f"RECOVERING: Active {active['dir'].upper()} #{active['num']} from {active['entry_time']}")
        log(f"  Entry: {active['entry_price']}, Peak P&L: ${active.get('peak_pnl', 0):.2f}")
        return True

    # Also check TV indicator state — maybe we crashed mid-trade
    info = read_indicator_state()
    if info and info.get("state") == "TRADING":
        num = info.get("trade_num", 0)
        if num == state["last_fired"]:
            log(f"RECOVERING from TV: TRADING #{num} still active")
            price = get_current_price()
            state["active_trade"] = {
                "num": num,
                "dir": info.get("dir", "?"),
                "entry_price": price.get("last", 0) if price else 0,
                "entry_time": datetime.now().isoformat(),
                "peak_pnl": 0,
                "recovered": True
            }
            save_state(state)
            return True

    return False

# ============================================================
#  POSITION MONITOR (tick-by-tick when in trade)
# ============================================================
def monitor_position(state, dry_run=False):
    """Monitor active position tick-by-tick. Returns when trade closes."""
    active = state.get("active_trade")
    if not active:
        return

    direction = active["dir"]
    entry = active.get("entry_price", 0)
    peak_pnl = active.get("peak_pnl", 0)
    interval = state.get("monitor_interval", 5)
    shano_exit = state.get("shano_exit", False)
    trail_trigger = state.get("trail_trigger", 10.0)
    trail_drop = state.get("trail_drop", 3.0)
    tick_count = 0

    log(f"MONITORING {direction.upper()} | Entry ~{entry} | Interval {interval}s")

    while running and state.get("active_trade"):
        tick_count += 1

        # Check indicator state EVERY tick — catch sim exit immediately
        info = read_indicator_state()
        if info:
            sim_state = info.get("state", "")
            sim_pnl = info.get("live_pnl", 0)

            if sim_state in ("IDLE", "COOLDOWN"):
                # Pine sim resolved its simulation cycle. Real MT5 exits are owned by
                # ShanoExitManager EA (tick-level OnTick), not by this hawk. Just clear
                # local state and stop monitoring — don't fire close webhooks.
                state["active_trade"] = None
                save_state(state)
                return

            if sim_state == "TRADING":
                log_quiet(f"TRADE {direction.upper()} #{active['num']} | sim ${sim_pnl:.2f} | peak ${peak_pnl:.2f} | tick {tick_count}")

                # Update peak (informational only — EA does the real trail)
                if sim_pnl > peak_pnl:
                    peak_pnl = sim_pnl
                    active["peak_pnl"] = peak_pnl
                    save_state(state)
            else:
                log_quiet(f"TRADE {direction.upper()} #{active['num']} | TV read failed | tick {tick_count}")
        else:
            log_quiet(f"TRADE {direction.upper()} #{active['num']} | peak ${peak_pnl:.2f} | tick {tick_count}")

        # Check MT5 fills — did the trade close on MT5?
        fills = check_new_fills(state)
        for fill in fills:
            pnl = fill["pnl"]
            log(f"\nMT5 FILL: {fill['dir']} {fill['lots']} @ {fill['price']} = ${pnl:.2f}")
            if pnl > 0:
                state["session_wins"] += 1
            elif pnl < 0:
                state["session_losses"] += 1
            state["session_pnl"] += pnl
            save_state(state)

        # Sleep
        try:
            stop_event.wait(timeout=interval)
        except:
            break

        if stop_event.is_set():
            break

    print()  # newline after \r

# ============================================================
#  MAIN SIGNAL LOOP
# ============================================================
def signal_loop(state, dry_run=False):
    """Main loop: scan for signals, fire trades, monitor positions."""
    interval = state.get("signal_interval", 30)
    cycle = 0

    while running:
        cycle += 1

        # --- Read TradingView ---
        info = read_indicator_state()
        if info is None:
            log_quiet(f"TV read failed | cycle {cycle}")
            stop_event.wait(timeout=interval)
            continue

        # Refresh live price for dashboard (writes .shano_last_price.json)
        # Cheap because tv_call is already used per cycle for tables.
        if cycle % 2 == 0:  # every other cycle = every 10s, balance freshness vs load
            try:
                get_current_price()
            except Exception:
                pass

        st = info.get("state", "UNKNOWN")

        # --- COUNTER-BASED SIGNAL DETECTION (catches signals even when state already returned to IDLE) ---
        # Pine resolves PROBE→CONFIRMED→TP within seconds, so polling state misses signals.
        # The Signals counter only goes UP — robust race-free detector.
        sigcount = info.get("signal_count")
        if sigcount is not None and sigcount > state.get("last_fired", 0):
            sells = info.get("sells", 0)
            buys = info.get("buys", 0)
            # Sell-only mode: skip if Pine reports the new signal was a buy
            #   (sells increment vs buys increment tells us direction of LATEST signal)
            new_signals = sigcount - state.get("last_fired", 0)
            # Best-effort direction inference: if Pine indicator is sell-only on its side,
            # buys should be 0 — any new count is a sell.
            inferred_dir = "sell" if buys == 0 else (
                "buy" if buys > state.get("last_buys_seen", 0) else "sell"
            )

            if state["direction"] == "sell_only" and inferred_dir == "buy":
                log(f"BLOCKED counter: signal #{sigcount} BUY (sell_only)")
                state["last_fired"] = sigcount
                state["last_buys_seen"] = buys
                save_state(state)
            else:
                print()
                log(f"{'='*50}")
                log(f"COUNTER SIGNAL: #{sigcount} {inferred_dir.upper()} (+{new_signals} since last)")
                log(f"{'='*50}")
                # Fire the 0.01 PROBE — ShanoExitManager EA on MT5 will scale to 0.40 if it confirms.
                # Override lots temporarily to probe size (don't mutate state long-term).
                probe_state = dict(state)
                probe_state["lots"] = "0.01"
                success = fire_trade(inferred_dir, probe_state, dry_run)

                state["last_fired"] = sigcount
                state["last_buys_seen"] = buys
                state["total_fired"] = state.get("total_fired", 0) + 1
                state["session_trades"] = state.get("session_trades", 0) + 1
                state["trades"].append({
                    "num": sigcount,
                    "dir": inferred_dir,
                    "time": datetime.now().isoformat(),
                    "fired": success,
                    "via": "counter",
                })
                save_state(state)
                # Don't enter monitor_position here — EA owns the lifecycle now.
                stop_event.wait(timeout=interval)
                continue

        # --- TRADING: check if new trade to fire (legacy state-based path) ---
        if st == "TRADING":
            trade_num = info.get("trade_num", 0)
            direction = info.get("dir", "buy")

            if trade_num > state["last_fired"]:
                # Direction filter
                if state["direction"] == "sell_only" and direction == "buy":
                    log(f"BLOCKED: #{trade_num} BUY (sell_only)")
                    state["last_fired"] = trade_num
                    save_state(state)
                elif state["direction"] == "buy_only" and direction == "sell":
                    log(f"BLOCKED: #{trade_num} SELL (buy_only)")
                    state["last_fired"] = trade_num
                    save_state(state)
                else:
                    # FIRE!
                    print()
                    log(f"{'='*50}")
                    log(f"SIGNAL: {direction.upper()} #{trade_num}")
                    log(f"{'='*50}")

                    success = fire_trade(direction, state, dry_run)

                    state["last_fired"] = trade_num
                    state["total_fired"] += 1
                    state["session_trades"] += 1

                    # Set active trade for monitoring
                    price = get_current_price()
                    state["active_trade"] = {
                        "num": trade_num,
                        "dir": direction,
                        "entry_price": price.get("last", 0) if price else 0,
                        "entry_time": datetime.now().isoformat(),
                        "peak_pnl": 0
                    }

                    state["trades"].append({
                        "num": trade_num,
                        "dir": direction,
                        "time": datetime.now().isoformat(),
                        "fired": success
                    })
                    save_state(state)

                    # Enter position monitoring mode
                    if success:
                        monitor_position(state, dry_run)

            else:
                # Already fired this trade, monitor it
                pnl = info.get("live_pnl", 0)
                if state.get("active_trade"):
                    if pnl and pnl > state["active_trade"].get("peak_pnl", 0):
                        state["active_trade"]["peak_pnl"] = pnl
                        save_state(state)
                    log_quiet(f"TRADE {direction.upper()} #{trade_num} ${pnl} | cycle {cycle}")
                else:
                    log_quiet(f"TRADE {direction.upper()} #{trade_num} ${pnl} (not ours) | cycle {cycle}")

        elif st == "PROBING":
            num = info.get("trade_num", 0)
            pnl = info.get("live_pnl", 0)
            log_quiet(f"PROBE {info.get('dir','?').upper()} #{num} ${pnl} | cycle {cycle}")

        elif st == "COOLDOWN":
            # Pine sim ended — but ShanoExitManager EA handles real MT5 exits, NOT us.
            # The hawk only fires the initial probe; EA scales to 0.40 and trails out.
            if state.get("active_trade"):
                state["active_trade"] = None
                save_state(state)
            log_quiet(f"COOLDOWN | cycle {cycle}")

        else:
            # IDLE — same as above, EA owns the exit lifecycle, hawk just clears local state.
            if state.get("active_trade"):
                state["active_trade"] = None
                save_state(state)
            log_quiet(f"IDLE | fired:{state['total_fired']} W:{state['session_wins']} L:{state['session_losses']} P&L:${state['session_pnl']:.2f} | cycle {cycle}")

        # Check MT5 fills
        fills = check_new_fills(state)
        for fill in fills:
            pnl = fill["pnl"]
            print()
            log(f"MT5: {fill['dir']} {fill['lots']} @ {fill['price']} = ${pnl:.2f}")
            if pnl > 0:
                state["session_wins"] += 1
            elif pnl < 0:
                state["session_losses"] += 1
            state["session_pnl"] += pnl
            save_state(state)

        # Wait
        if not running:
            break
        stop_event.wait(timeout=interval)
        if stop_event.is_set():
            break

# ============================================================
#  BANNER
# ============================================================
def print_banner(state, dry_run=False):
    b = "=" * 60
    print(b)
    print("  SHANO HAWK  -  Autonomous Trading Daemon")
    if dry_run:
        print("  *** DRY RUN MODE ***")
    print(b)
    print(f"  Symbol:      {state['symbol']} (PC: {state['pc_symbol']})")
    print(f"  Lots:        {state['lots']}")
    print(f"  TP / SL:     {state['tp']} / {state['sl']} pips")
    print(f"  Direction:   {state['direction']}")
    print(f"  Last fired:  #{state['last_fired']}")
    print(f"  Total fired: {state['total_fired']}")
    if state.get("active_trade"):
        at = state["active_trade"]
        print(f"  ACTIVE:      {at['dir'].upper()} #{at['num']} (recovering)")
    print(f"  Signal scan: every {state.get('signal_interval', 30)}s")
    print(f"  Tick monitor: every {state.get('monitor_interval', 5)}s")
    if state.get("shano_exit"):
        print(f"  Shano exit:  trail after ${state['trail_trigger']}, drop ${state['trail_drop']}")
    print(b)
    print("  Ctrl+C to stop | Logs: monitor/shano_hawk.log")
    print(b)

# ============================================================
#  MAIN
# ============================================================
def main():
    dry_run = "--dry-run" in sys.argv
    once = "--once" in sys.argv

    state = load_state()

    # --- CLI commands ---
    if "--status" in sys.argv:
        print(json.dumps(state, indent=2))
        return

    if "--reset-session" in sys.argv:
        state["session_pnl"] = 0.0
        state["session_trades"] = 0
        state["session_wins"] = 0
        state["session_losses"] = 0
        state["session_start"] = datetime.now().isoformat()
        save_state(state)
        print("Session counters reset")
        return

    if not state["enabled"]:
        print("[HAWK] DISABLED. Run: python shano_scanner.py --enable")
        return

    # Prevent duplicate instances
    if not once:
        check_pid()

    # Set session start
    if not state.get("session_start"):
        state["session_start"] = datetime.now().isoformat()
        save_state(state)

    print_banner(state, dry_run)

    # Crash recovery
    had_active = recover_state(state)

    # Test TV connection
    log("Testing TradingView connection...")
    info = read_indicator_state()
    if info:
        log(f"TV connected: {info.get('state', '?')} | {info.get('today_raw', '')}")
    else:
        log("WARNING: TV not responding — will retry", "WARN")

    # Main loop
    try:
        if once:
            # Single scan
            info = read_indicator_state()
            if info:
                log(f"State: {info.get('state')} | {info.get('status_raw', '')}")
            fills = check_new_fills(state)
            for f in fills:
                log(f"MT5: {f['dir']} @ {f['price']} = ${f['pnl']:.2f}")
        else:
            log("Starting signal loop...")
            signal_loop(state, dry_run)
    finally:
        # Shutdown
        print()
        log("=" * 50)
        log("SHANO HAWK SHUTDOWN")
        log(f"  Session: {state.get('session_start', '?')}")
        log(f"  Trades:  {state['session_trades']}")
        log(f"  W/L:     {state['session_wins']}W / {state['session_losses']}L")
        log(f"  P&L:     ${state['session_pnl']:.2f}")
        if state.get("active_trade"):
            at = state["active_trade"]
            log(f"  WARNING: Trade #{at['num']} still active on MT5!")
            log(f"  Will resume on next startup.")
        log("=" * 50)
        save_state(state)
        remove_pid()


if __name__ == "__main__":
    main()
