"""Shano Scanner — Reads TradingView indicator state and fires trades via webhook.

Called every minute by Claude cron or standalone.

Usage:
    python shano_scanner.py                    # scan once, fire if needed
    python shano_scanner.py --status           # just show current state
    python shano_scanner.py --reset            # reset last_fired to 0
    python shano_scanner.py --set-fired 2082   # manually set last_fired

State file: monitor/.shano_state.json
Logs to: monitor/shano_scanner.log
"""

import json, sys, os, subprocess
from datetime import datetime
from pathlib import Path

# --- Config ---
SCRIPT_DIR = Path(__file__).parent
STATE_FILE = SCRIPT_DIR / ".shano_state.json"
LOG_FILE = SCRIPT_DIR / "shano_scanner.log"
WEBHOOK_SCRIPT = SCRIPT_DIR / "pc_webhook.py"
PYTHON = r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"

# --- Defaults (override via state file) ---
DEFAULTS = {
    "symbol": "BTCUSD",
    "lots": "0.10",
    "tp": "2000",
    "sl": "300",
    "last_fired": 0,
    "enabled": True,
    "mode": "fade",       # "fade" or "momentum"
    "direction": "both",  # "both", "buy_only", "sell_only"
    "total_fired": 0,
    "wins": 0,
    "losses": 0,
    "trades": []          # last 20 trades log
}

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            saved = json.load(f)
        # merge with defaults for any missing keys
        merged = {**DEFAULTS, **saved}
        return merged
    return DEFAULTS.copy()

def save_state(state):
    # keep only last 20 trades
    state["trades"] = state.get("trades", [])[-20:]
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def fire_trade(direction, state):
    """Fire a trade via pc_webhook.py"""
    cmd = [
        PYTHON, str(WEBHOOK_SCRIPT),
        direction, state["symbol"], state["lots"],
        f"--tp={state['tp']}", f"--sl={state['sl']}"
    ]
    log(f"FIRING: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    log(f"RESULT: {result.stdout.strip()}")
    if result.stderr:
        log(f"ERROR: {result.stderr.strip()}")
    return result.returncode == 0

def close_trade(direction, state):
    """Close a trade via pc_webhook.py"""
    close_dir = "closelong" if direction == "buy" else "closeshort"
    cmd = [PYTHON, str(WEBHOOK_SCRIPT), close_dir, state["symbol"]]
    log(f"CLOSING: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    log(f"RESULT: {result.stdout.strip()}")

def parse_status(rows):
    """Parse Shano indicator table rows into structured data."""
    info = {}
    for row in rows:
        if "Status |" in row:
            info["status_raw"] = row.split("| ")[1].strip()
            s = info["status_raw"]
            if "IDLE" in s:
                info["state"] = "IDLE"
            elif "PROBING" in s:
                info["state"] = "PROBING"
                # extract trade number and direction
                if "#" in s:
                    info["trade_num"] = int(s.split("#")[1].split(" ")[0])
                if "(LONG" in s:
                    info["direction"] = "buy"
                elif "(SHORT" in s:
                    info["direction"] = "sell"
            elif "TRADING" in s:
                info["state"] = "TRADING"
                if "#" in s:
                    info["trade_num"] = int(s.split("#")[1].split(" ")[0])
                if "(LONG" in s:
                    info["direction"] = "buy"
                elif "(SHORT" in s:
                    info["direction"] = "sell"
            elif "COOLDOWN" in s:
                info["state"] = "COOLDOWN"
            elif "SKIP" in s:
                info["state"] = "SKIP"
            else:
                info["state"] = "UNKNOWN"
        elif "Live Trade |" in row:
            lt = row.split("| ")[1].strip()
            if lt != "---":
                # parse "$5.28  |  1 lots  |  4 bars"
                parts = lt.split("|")
                try:
                    info["live_pnl"] = float(parts[0].strip().replace("$", ""))
                except:
                    info["live_pnl"] = 0.0
        elif "TODAY |" in row:
            info["today_raw"] = row.split("| ")[1].strip()
    return info

def scan(state):
    """Main scan logic — called each minute."""
    # This reads from stdin (piped from cron) or can be called with table data
    # For standalone use, we'd need TradingView MCP access
    # When called from cron, the cron passes the parsed state
    pass

def process(table_rows, state):
    """Process indicator table data and decide whether to fire."""
    info = parse_status(table_rows)

    if not info.get("state"):
        log("WARNING: Could not parse indicator state")
        return "ERROR"

    if not state["enabled"]:
        return f"DISABLED s={info['state']}"

    # TRADING detected — check if we should fire
    if info["state"] == "TRADING":
        trade_num = info.get("trade_num", 0)
        direction = info.get("direction", "buy")

        if trade_num > state["last_fired"]:
            # Direction filter
            if state["direction"] == "sell_only" and direction == "buy":
                log(f"SKIP: #{trade_num} {direction} blocked by sell_only filter")
                state["last_fired"] = trade_num
                save_state(state)
                return f"SKIP {direction} #{trade_num} (sell_only)"

            if state["direction"] == "buy_only" and direction == "sell":
                log(f"SKIP: #{trade_num} {direction} blocked by buy_only filter")
                state["last_fired"] = trade_num
                save_state(state)
                return f"SKIP {direction} #{trade_num} (buy_only)"

            # FIRE!
            log(f"=== TRADE CONFIRMED: {direction.upper()} #{trade_num} ===")
            success = fire_trade(direction, state)

            state["last_fired"] = trade_num
            state["total_fired"] += 1
            state["trades"].append({
                "num": trade_num,
                "dir": direction,
                "time": datetime.now().isoformat(),
                "fired": success
            })
            save_state(state)

            return f"FIRED! {direction} #{trade_num}"
        else:
            pnl = info.get("live_pnl", 0)
            return f"s=2 TRADE {direction.upper()} #{trade_num} ${pnl}"

    elif info["state"] == "PROBING":
        trade_num = info.get("trade_num", 0)
        direction = info.get("direction", "?")
        pnl = info.get("live_pnl", 0)
        return f"s=1 PROBE {direction.upper()} #{trade_num} ${pnl}"

    elif info["state"] == "COOLDOWN":
        return f"s=0 COOLDOWN"

    else:
        return f"s=0 {info['state']}"


if __name__ == "__main__":
    state = load_state()

    if "--status" in sys.argv:
        print(json.dumps(state, indent=2))
        sys.exit(0)

    if "--reset" in sys.argv:
        state["last_fired"] = 0
        save_state(state)
        print("Reset last_fired to 0")
        sys.exit(0)

    for arg in sys.argv:
        if arg.startswith("--set-fired="):
            state["last_fired"] = int(arg.split("=")[1])
            save_state(state)
            print(f"Set last_fired to {state['last_fired']}")
            sys.exit(0)

        if arg.startswith("--symbol="):
            state["symbol"] = arg.split("=")[1]
            save_state(state)

        if arg.startswith("--lots="):
            state["lots"] = arg.split("=")[1]
            save_state(state)

        if arg.startswith("--tp="):
            state["tp"] = arg.split("=")[1]
            save_state(state)

        if arg.startswith("--sl="):
            state["sl"] = arg.split("=")[1]
            save_state(state)

        if arg.startswith("--direction="):
            state["direction"] = arg.split("=")[1]
            save_state(state)

        if arg == "--enable":
            state["enabled"] = True
            save_state(state)
            print("Scanner ENABLED")
            sys.exit(0)

        if arg == "--disable":
            state["enabled"] = False
            save_state(state)
            print("Scanner DISABLED")
            sys.exit(0)

    # If called with table data on stdin, process it
    if not sys.stdin.isatty():
        rows = [line.strip() for line in sys.stdin.readlines()]
        result = process(rows, state)
        print(result)
    else:
        print("No table data on stdin. Use --status to check state.")
        print(f"Last fired: #{state['last_fired']}, Total: {state['total_fired']}")
