"""
Shano Strategy v3 -- Single-Candle Momentum Scalper.

Reverse-engineered from Shano's $100->$700 session on 2026-04-24.
100% confirmed via WhatsApp interview.

CONFIRMED RULES (from her own words):

1. ENTRY SIGNAL: ONE big candle that is larger than the previous 2 candles
   - "It's usually third one. Two before it"
   - "Bar not bars" -- single candle trigger, NOT a streak
   - She reads candle SHAPE, not price numbers

2. ENTRY TIMING: While the candle is still growing
   - "While" / "No on way of it" -- enters on the way, not after close
   - She enters in the direction of the big candle (NOT reversal)

3. DIRECTION:
   - Big RED candle growing down -> SELL
   - Big GREEN candle growing up -> BUY
   - Strategy is symmetrical but she focuses on sells (71% of trades)
   - "Exactly works same way for buying green bars"

4. SCOUT TRADE: 0.08 lots
   - Scout P&L turning positive after 7 seconds = REAL confirmation
   - "value of small lot turning positive is the major signal"

5. SCALING: 0.08 -> 0.10 -> 0.20 -> 0.40
   - Only scale when scout is in profit after 7 seconds
   - Open NEW separate trade, don't modify existing

6. EXIT: $10 per cluster, no SL, hold losers expecting reversal
   - Emergency close at 50% account drawdown
"""

import json
import time
from pathlib import Path
from datetime import datetime, timezone

SCRIPT_DIR = Path(__file__).parent
STATE_FILE = SCRIPT_DIR / "shano_state.json"
CONFIG_FILE = SCRIPT_DIR / "shano_config.json"

DEFAULT_CONFIG = {
    "enabled": False,
    # Detection -- single candle vs previous 2
    "lookback_candles": 2,              # Compare to last N candles ("Two before it")
    "body_multiplier": 1.25,            # "When it's one quarter bigger than last one"
                                        # 1.25 = 25% bigger than previous candle
    "min_body_points": 0.5,             # Minimum absolute body size to avoid doji noise
    # Position sizing (from her actual lot distribution)
    "scout_lots": 0.08,                 # Her standard entry (14 trades at 0.08)
    "confirmed_lots": 0.10,             # Scale up after scout profits (86% WR at this size)
    "aggressive_lots": 0.20,            # After 2+ wins in same direction (57% WR)
    "max_lots": 0.40,                   # Only when extremely confident (1 trade, 100% WR)
    # Timing
    "scout_confirm_seconds": 7,         # "Almost seven seconds"
    "entry_while_growing": True,        # Enter while candle is still forming
    # Risk management
    "max_loss_scout": 7.0,              # Cut 0.08 trade at -$7
    "max_loss_confirmed": 10.0,         # Cut 0.10 trade at -$10
    "max_loss_aggressive": 15.0,        # Cut 0.20 trade at -$15
    "max_loss_max": 25.0,               # Cut 0.40 trade at -$25
    "switch_direction_on_big_loss": True,
    "big_loss_threshold": 15.0,
    # Cluster management
    "cluster_tp": 10.0,                 # $10 TP per cluster ("It's enough making ten")
    "rest_after_trades": 8,
    "rest_duration_minutes": 20,
    "max_cluster_loss": 30.0,
    # Session
    "session_start_utc": "11:00",       # 14:00 Moscow
    "session_end_utc": "14:00",         # 17:00 Moscow
    "late_session_end_utc": "18:00",
    # Execution
    "pineconnector_id": "8778286989525",
    "symbol": "XAUUSD",
    "sl_pips": 15,
    "tp_pips": 52,
    "spread_max": 30,
}


def load_config():
    """Load or create config."""
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text("utf-8"))
    CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
    return DEFAULT_CONFIG.copy()


def load_state():
    """Load strategy state."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text("utf-8"))
    return {
        "phase": "idle",        # idle, scouting, confirmed, aggressive, resting
        "direction": None,      # buy or sell
        "current_lots": 0,
        "scout_entry_time": None,
        "scout_entry_price": None,
        "trades_in_cluster": 0,
        "cluster_start_time": None,
        "cluster_pnl": 0.0,
        "consecutive_wins": 0,
        "rest_until": None,
        "session_pnl": 0.0,
        "session_trades": 0,
        "last_big_loss_direction": None,
    }


def save_state(state):
    """Save strategy state."""
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def detect_big_candle(candles: list[dict], config: dict) -> dict | None:
    """
    Detect Shano's single big candle signal:
    - Current candle body must be LARGER than each of the previous 2 candle bodies
    - Direction: red candle = sell, green candle = buy

    candles: list of {open, high, low, close, volume} dicts, newest LAST.
    Returns: {direction, body, prev_bodies, ...} or None
    """
    lookback = config.get("lookback_candles", 2)
    multiplier = config.get("body_multiplier", 1.0)
    min_body = config.get("min_body_points", 1.0)

    # Need at least lookback+1 candles (current + N previous)
    if len(candles) < lookback + 1:
        return None

    current = candles[-1]
    current_body = abs(current["close"] - current["open"])

    # Skip tiny candles (dojis, noise)
    if current_body < min_body:
        return None

    # Compare to each of the previous N candles
    prev_candles = candles[-(lookback + 1):-1]
    prev_bodies = [abs(c["close"] - c["open"]) for c in prev_candles]

    # Current body must be bigger than ALL previous candle bodies
    for prev_body in prev_bodies:
        if current_body <= prev_body * multiplier:
            return None

    # Determine direction based on candle color
    if current["close"] < current["open"]:
        direction = "sell"
        color = "red"
    elif current["close"] > current["open"]:
        direction = "buy"
        color = "green"
    else:
        return None  # Doji, no direction

    return {
        "direction": direction,
        "color": color,
        "body": round(current_body, 2),
        "prev_bodies": [round(b, 2) for b in prev_bodies],
        "ratio_to_max_prev": round(current_body / max(prev_bodies), 2) if max(prev_bodies) > 0 else 999,
        "volume": current.get("volume", 0),
    }


# Keep old function name as alias for backtest compatibility
def detect_exhaustion(candles: list[dict], config: dict) -> dict | None:
    """Legacy alias -- redirects to detect_big_candle."""
    result = detect_big_candle(candles, config)
    if result:
        # Map to old format for backtest compatibility
        result["strength"] = result["ratio_to_max_prev"]
        result["pattern"] = f"{result['color']}_momentum"
        result["candle_count"] = 1
    return result


def get_lots_for_phase(phase: str, config: dict) -> float:
    """Get lot size based on current trading phase."""
    if phase == "scouting":
        return config.get("scout_lots", 0.08)
    elif phase == "confirmed":
        return config.get("confirmed_lots", 0.10)
    elif phase == "aggressive":
        return config.get("aggressive_lots", 0.20)
    elif phase == "max":
        return config.get("max_lots", 0.40)
    return config.get("scout_lots", 0.08)


def get_max_loss_for_phase(phase: str, config: dict) -> float:
    """Get max loss threshold based on current trading phase."""
    if phase == "scouting":
        return config.get("max_loss_scout", 7.0)
    elif phase == "confirmed":
        return config.get("max_loss_confirmed", 10.0)
    elif phase == "aggressive":
        return config.get("max_loss_aggressive", 15.0)
    elif phase == "max":
        return config.get("max_loss_max", 25.0)
    return config.get("max_loss_scout", 7.0)


def should_scale_up(state: dict, config: dict, scout_pnl: float) -> str | None:
    """
    Determine if we should scale up based on Shano's pattern:
    - Scout profits after 7 seconds -> scale to confirmed (0.10)
    - 2+ consecutive wins -> scale to aggressive (0.20)
    - 3+ consecutive wins -> scale to max (0.40)
    """
    phase = state.get("phase", "idle")
    wins = state.get("consecutive_wins", 0)

    if scout_pnl <= 0:
        return None

    if phase == "scouting" and wins >= 1:
        return "confirmed"
    elif phase == "confirmed" and wins >= 2:
        return "aggressive"
    elif phase == "aggressive" and wins >= 3:
        return "max"
    return None


if __name__ == "__main__":
    config = load_config()
    print("Shano Strategy v3 -- Single-Candle Momentum Scalper")
    print(f"Strategy enabled: {config.get('enabled', False)}")
    print(f"Lookback candles: {config.get('lookback_candles', 2)}")
    print(f"Body multiplier: {config.get('body_multiplier', 1.0)}x")
    print(f"Min body points: {config.get('min_body_points', 1.0)}")
    print(f"Scout lots: {config.get('scout_lots', 0.08)}")
    print(f"Scout confirm: {config.get('scout_confirm_seconds', 7)}s")
    print(f"Cluster TP: ${config.get('cluster_tp', 10.0)}")
    print()

    # Test with Shano's actual first trade setup
    # She saw 5 reds, but her trigger was the BIG one (body 2.5), not the streak
    test_candles = [
        {"open": 4734.0, "high": 4734.1, "low": 4733.9, "close": 4733.9, "volume": 709},  # Doji
        {"open": 4733.9, "high": 4734.0, "low": 4731.4, "close": 4731.4, "volume": 839},  # R body=2.5
        {"open": 4731.4, "high": 4731.5, "low": 4729.2, "close": 4729.2, "volume": 852},  # R body=2.2
        {"open": 4729.2, "high": 4729.6, "low": 4728.8, "close": 4728.8, "volume": 904},  # R body=0.4
        {"open": 4728.8, "high": 4729.2, "low": 4728.4, "close": 4728.4, "volume": 786},  # R body=0.4
        {"open": 4728.4, "high": 4728.5, "low": 4728.3, "close": 4728.3, "volume": 947},  # R body=0.1
    ]

    print("Testing at each bar (simulating real-time scan):")
    for i in range(3, len(test_candles) + 1):
        subset = test_candles[:i]
        result = detect_big_candle(subset, config)
        last = subset[-1]
        body = abs(last["close"] - last["open"])
        color = "R" if last["close"] < last["open"] else "G" if last["close"] > last["open"] else "D"
        if result:
            print(f"  Bar {i}: {color} body={body:.1f} -> SIGNAL: {result['direction'].upper()} "
                  f"(body={result['body']}, ratio={result['ratio_to_max_prev']}x)")
        else:
            print(f"  Bar {i}: {color} body={body:.1f} -> no signal")
