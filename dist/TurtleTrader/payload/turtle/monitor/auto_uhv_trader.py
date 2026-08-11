"""auto_uhv_trader.py — Self-contained UHV detector + sniper-target writer.

Replaces the Claude-driven `crons/jobs/claude_trader.md` cron. Runs as a daemon
that reads the live tick CSV (written by ShanoTickLogger.mq5), builds M1 bars,
detects new UHV bars, and writes sniper_target.json for the sniper daemon to
act on. No Claude / TV MCP required.

UHV detection (matches Pine indicator):
  Red UHV   = highest tick-count bar in last UHV_LOOKBACK that is RED  (close < open)
  Green UHV = highest tick-count bar in last UHV_LOOKBACK that is GREEN (close > open)

Direction mapping (matches claude_trader.md cron, REVERSAL strategy):
  Red UHV   → BUY  (sellers exhausted, expect bounce)
  Green UHV → SELL (buyers exhausted, expect drop)

Outputs:
  monitor/sniper_target.json — read by sniper daemon
  monitor/.last_uhv_id       — dedup cache
  monitor/auto_uhv_trader.log

Run:
  python monitor/auto_uhv_trader.py
"""
from __future__ import annotations
import csv, json, time, sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT       = Path(r"C:\Users\zeesh\Documents\GitHub\turtle")
COMMON_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
HERE       = ROOT / "monitor"
SNIPER_TARGET = HERE / "sniper_target.json"
LAST_UHV_ID   = HERE / ".last_uhv_id"
HEARTBEAT     = HERE / "auto_uhv_trader_heartbeat.json"
LOG           = HERE / "auto_uhv_trader.log"
EXEC_PS1      = HERE / "claude_uhv_exec.ps1"

UHV_LOOKBACK   = 20    # Match Pine + EA setup1 lookback
POLL_SEC       = 60    # Cron-equivalent tick rate
LOTS_DIRECT    = 0.40  # Direct-fire lot size when UHV already broken


# ─── data layer (matches forward_tester.py) ───
def parse_ticks_for_today():
    today = datetime.now().strftime("%Y-%m-%d")
    path = COMMON_DIR / f"shano_ticks_{today}.csv"
    if not path.exists():
        return []
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        next(f, None)
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 4: continue
            try:
                dt = datetime.strptime(parts[0], "%Y.%m.%d %H:%M:%S")
                bid = float(parts[2]); ask = float(parts[3])
                out.append((dt, bid, ask))
            except (ValueError, IndexError):
                continue
    return out


def build_m1_bars(ticks):
    """Returns list of dicts {time, open, high, low, close, n_ticks}."""
    bars = {}
    for dt, bid, ask in ticks:
        bm = dt.replace(second=0, microsecond=0)
        mid = (bid + ask) / 2
        if bm not in bars:
            bars[bm] = {"o": mid, "h": mid, "l": mid, "c": mid, "n": 1}
        else:
            b = bars[bm]
            b["h"] = max(b["h"], mid); b["l"] = min(b["l"], mid); b["c"] = mid; b["n"] += 1
    return [{"time": t, "open": v["o"], "high": v["h"], "low": v["l"],
             "close": v["c"], "volume": v["n"]} for t, v in sorted(bars.items())]


def detect_uhv(bars, lookback=UHV_LOOKBACK):
    """Return (uhv_bar, color) where color is 'Red' or 'Green'. None if no clear UHV."""
    if len(bars) < 2:
        return None, None
    window = bars[-lookback:] if len(bars) >= lookback else bars
    # We exclude the *current* (still-forming) bar — UHV is on a CLOSED bar
    closed = window[:-1] if len(window) > 1 else window
    if not closed:
        return None, None
    uhv = max(closed, key=lambda b: b["volume"])
    color = "Red" if uhv["close"] < uhv["open"] else "Green" if uhv["close"] > uhv["open"] else None
    if color is None:
        return None, None
    return uhv, color


def already_broken(current_bar, uhv_level, color):
    """Has price already broken the UHV level on the current (forming) bar?"""
    if color == "Red":
        return current_bar["high"] > uhv_level
    return current_bar["low"] < uhv_level


# ─── persistence ───
def read_last_uhv():
    if not LAST_UHV_ID.exists(): return ""
    return LAST_UHV_ID.read_text(encoding="utf-8").strip()


def write_last_uhv(key):
    LAST_UHV_ID.write_text(key, encoding="utf-8")


def write_sniper_target(uhv_key, level, direction, candle):
    payload = {
        "uhv_key": uhv_key, "level": level, "direction": direction,
        "candle": {"open": candle["open"], "high": candle["high"], "low": candle["low"],
                   "close": candle["close"], "volume": candle["volume"]},
        "t": datetime.utcnow().isoformat() + "Z",
    }
    SNIPER_TARGET.write_text(json.dumps(payload), encoding="utf-8")


def write_heartbeat(state, uhv_key=""):
    HEARTBEAT.write_text(json.dumps({
        "state": state, "uhv_key": uhv_key,
        "t": datetime.utcnow().isoformat() + "Z",
        "pid": __import__("os").getpid(),
    }, indent=2), encoding="utf-8")


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def fire_direct(direction, lots, uhv_key, reason, candle_high, candle_low):
    """Execute direct fire via PowerShell exec script (matches cron step 6a)."""
    if not EXEC_PS1.exists():
        log(f"  [WARN] exec script {EXEC_PS1} missing — cannot direct-fire")
        return False
    import subprocess
    cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(EXEC_PS1),
           "-Direction", direction, "-Lots", str(lots), "-Comment", "Auto_UHV_Trader",
           "-UhvBarTime", uhv_key, "-Reason", reason,
           "-CandleHigh", str(candle_high), "-CandleLow", str(candle_low)]
    log(f"  [FIRE] {' '.join(cmd[3:])}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            log(f"  [ERR] exec returned {r.returncode}: {r.stderr[:200]}")
            return False
        log(f"  [FIRED] {r.stdout[:150]}")
        return True
    except Exception as e:
        log(f"  [ERR] exec failed: {type(e).__name__}: {e}")
        return False


# ─── main loop ───
def cycle():
    ticks = parse_ticks_for_today()
    if not ticks:
        write_heartbeat("idle_no_ticks")
        return
    bars = build_m1_bars(ticks)
    if len(bars) < 2:
        write_heartbeat("idle_few_bars")
        return

    uhv, color = detect_uhv(bars)
    if uhv is None:
        write_heartbeat("idle_no_uhv")
        return

    # UHV "level" = the extreme of the UHV bar in trigger direction (matches Pine logic)
    # Red UHV → buy on rise above HIGH; Green UHV → sell on drop below LOW
    if color == "Red":
        level = uhv["high"]; direction = "buy"
    else:
        level = uhv["low"];  direction = "sell"

    uhv_key = f"{color}_{level:.4f}"
    last = read_last_uhv()
    if uhv_key == last:
        write_heartbeat("idle_seen", uhv_key)
        return

    log(f"NEW UHV: {uhv_key} | dir={direction} | bar={uhv['time']} OHLCV=({uhv['open']:.2f},{uhv['high']:.2f},{uhv['low']:.2f},{uhv['close']:.2f},{uhv['volume']})")

    current = bars[-1]
    broke = already_broken(current, level, color)

    if broke:
        log(f"  Already broken (current high={current['high']:.2f} low={current['low']:.2f} vs UHV level {level:.2f})")
        ok = fire_direct(direction, LOTS_DIRECT, uhv_key,
                          reason=f"BRK { 'above' if color == 'Red' else 'below' } {level:.2f}",
                          candle_high=current["high"], candle_low=current["low"])
        if ok:
            write_last_uhv(uhv_key)
            write_heartbeat("fired_direct", uhv_key)
    else:
        write_sniper_target(uhv_key, level, direction, uhv)
        write_last_uhv(uhv_key)
        log(f"  Target set @ {level:.2f} — sniper daemon will fire on cross.")
        write_heartbeat("target_set", uhv_key)


def main():
    log(f"auto_uhv_trader starting — POLL={POLL_SEC}s LOOKBACK={UHV_LOOKBACK}")
    log(f"  COMMON_DIR={COMMON_DIR}")
    write_heartbeat("starting")
    while True:
        try:
            cycle()
        except Exception as e:
            log(f"  [ERR] cycle failed: {type(e).__name__}: {e}")
            write_heartbeat(f"error:{type(e).__name__}")
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
