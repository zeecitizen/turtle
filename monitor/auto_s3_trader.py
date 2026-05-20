"""auto_s3_trader.py — Live S3 (Effort vs Result) trader daemon.

Backtested at +$270 / 12 days at 0.10 lots = projected ~$90/day at 0.40 lots.
See memory: project_ns_nd_profitable_config.md and the setup spec in chat.

Setup S3 (BUY only — sell variant lost on backtest):
  1. H1 chart: mark Fair Value Gaps
  2. M5 chart: wait for price to dip and TAP an unfilled bullish H1 FVG
  3. In the retracement, find a red candle (any volume)
  4. Find a GREEN candle that:
        • wicks BELOW the red's low
        • closes back INSIDE the red's range (close > red's low)
        • has HIGHER volume than the red
  5. Fire BUY at the wicking green's close
  6. SL = wicking green's low − 1 pip
  7. TP = highest high in the last 30 M5 bars (recent peak)
  8. Pre-req: 2-hour uptrend (close[now] − close[24 M5 bars ago] > 2.0pts)

Runs every 60s; on the close of each new M5 bar checks for S3 trigger.
Fires via claude_s3_exec.ps1 (dynamic SL/TP).
"""
from __future__ import annotations
import csv, json, time, sys, subprocess
from datetime import datetime, timedelta
from pathlib import Path

ROOT       = Path(r"C:\Users\zeesh\Documents\GitHub\turtle")
COMMON_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
HERE       = ROOT / "monitor"
DEDUP_FILE = HERE / ".s3_last_signal"
HEARTBEAT  = HERE / "auto_s3_trader_heartbeat.json"
LOG        = HERE / "auto_s3_trader.log"
EXEC_PS1   = HERE / "claude_s3_exec.ps1"

# ── CONFIG ─────────────────────────────────────────────────────────
LIVE_MODE  = True       # set False for dry-run (log only, no actual fire)
LOTS       = 0.40
POLL_SEC   = 60
PIP        = 0.10
LOOKBACK_DAYS = 3       # how many days of M1 bars to retain for H1 FVG + trend


# ─── DATA LAYER ───
def load_recent_ticks(days=LOOKBACK_DAYS):
    """Load ticks from the last N days (including today)."""
    out = []
    today = datetime.now().date()
    for offset in range(days, -1, -1):
        d = today - timedelta(days=offset)
        path = COMMON_DIR / f"shano_ticks_{d.strftime('%Y-%m-%d')}.csv"
        if not path.exists(): continue
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
             "close": v["c"], "vol": v["n"]} for t, v in sorted(bars.items())]


def aggregate_to_tf(m1_bars, k):
    bucketed = {}
    for b in m1_bars:
        ts = b["time"]
        bucket_min = (ts.minute // k) * k
        bucket_t   = ts.replace(minute=bucket_min, second=0, microsecond=0)
        key = bucket_t
        if key not in bucketed:
            bucketed[key] = {"time": key, "open": b["open"], "high": b["high"],
                             "low": b["low"], "close": b["close"], "vol": b["vol"]}
        else:
            x = bucketed[key]
            x["high"] = max(x["high"], b["high"])
            x["low"]  = min(x["low"],  b["low"])
            x["close"] = b["close"]
            x["vol"] += b["vol"]
    return sorted(bucketed.values(), key=lambda x: x["time"])


def aggregate_to_h1(m1_bars):
    bucketed = {}
    for b in m1_bars:
        ts = b["time"]
        bucket_t = ts.replace(minute=0, second=0, microsecond=0)
        if bucket_t not in bucketed:
            bucketed[bucket_t] = {"time": bucket_t, "open": b["open"], "high": b["high"],
                                  "low": b["low"], "close": b["close"], "vol": b["vol"]}
        else:
            x = bucketed[bucket_t]
            x["high"] = max(x["high"], b["high"])
            x["low"]  = min(x["low"],  b["low"])
            x["close"] = b["close"]
            x["vol"] += b["vol"]
    return sorted(bucketed.values(), key=lambda x: x["time"])


# ─── H1 FVG detection ───
def find_h1_fvgs(h1_bars):
    """Returns list of bullish FVGs with their fill state at end of data."""
    fvgs = []
    for i in range(2, len(h1_bars)):
        gap_low  = h1_bars[i-2]["high"]
        gap_high = h1_bars[i]["low"]
        if gap_high <= gap_low: continue
        filled_at = None
        for j in range(i+1, len(h1_bars)):
            if h1_bars[j]["low"] < gap_low:
                filled_at = h1_bars[j]["time"]; break
        fvgs.append({"t0": h1_bars[i]["time"], "gap_low": gap_low,
                     "gap_high": gap_high, "filled_at": filled_at})
    return fvgs


def fvg_visible_and_tapped_at(fvgs, m5_bar):
    for f in fvgs:
        if f["t0"] >= m5_bar["time"]: continue
        if f["filled_at"] is not None and f["filled_at"] <= m5_bar["time"]: continue
        if m5_bar["low"] <= f["gap_high"] and m5_bar["high"] >= f["gap_low"]:
            return True
    return False


# ─── Detectors ───
def is_uptrend(m5_bars, idx, lookback=24, threshold=2.0):
    if idx < lookback: return False
    return m5_bars[idx]["close"] - m5_bars[idx-lookback]["close"] > threshold


def find_retracement_reds(m5_bars, idx, max_lookback=15):
    reds = []
    for j in range(idx - 1, max(idx - max_lookback - 1, -1), -1):
        b = m5_bars[j]
        if b["close"] >= b["open"]:
            if reds and b["high"] > m5_bars[reds[-1]]["high"]:
                break
        else:
            reds.append(j)
    return reds


def detect_s3_buy(m5_bars, idx, h1_fvgs):
    """Returns dict {entry, sl, tp, ref_red_time, wicking_green_time} or None."""
    bo = m5_bars[idx]
    if bo["close"] <= bo["open"]:    return None
    if not is_uptrend(m5_bars, idx): return None
    reds = find_retracement_reds(m5_bars, idx, max_lookback=15)
    if not reds: return None
    for red_idx in reds:
        red = m5_bars[red_idx]
        if bo["low"] >= red["low"]:    continue
        if bo["close"] <= red["low"]:  continue
        if bo["vol"]  <= red["vol"]:   continue
        # H1 FVG tap somewhere in the retracement
        tapped = any(fvg_visible_and_tapped_at(h1_fvgs, m5_bars[j]) for j in reds)
        if not tapped: continue
        entry = bo["close"]
        sl    = bo["low"] - PIP
        high_window = [m5_bars[j]["high"] for j in range(max(0, idx-30), idx)]
        if not high_window: continue
        tp = max(high_window)
        if tp <= entry + 0.5: continue   # require at least 5-pip TP distance
        return {
            "entry": entry, "sl": sl, "tp": tp,
            "ref_red_time": red["time"],
            "wicking_green_time": bo["time"],
        }
    return None


# ─── Persistence ───
def read_last_signal():
    return DEDUP_FILE.read_text(encoding="utf-8").strip() if DEDUP_FILE.exists() else ""


def write_last_signal(key):
    DEDUP_FILE.write_text(key, encoding="utf-8")


def write_heartbeat(state, **kw):
    payload = {"state": state, "t": datetime.utcnow().isoformat() + "Z",
               "pid": __import__("os").getpid(), **kw}
    HEARTBEAT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def fire(direction, entry, sl, tp, signal_key, reason):
    if not LIVE_MODE:
        log(f"  [DRY] would fire {direction} entry={entry:.2f} sl={sl:.2f} tp={tp:.2f} key={signal_key}")
        return True
    if not EXEC_PS1.exists():
        log(f"  [ERR] exec script {EXEC_PS1} missing")
        return False
    cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(EXEC_PS1),
           "-Direction", direction,
           "-EntryPrice", f"{entry:.5f}",
           "-SLPrice",    f"{sl:.5f}",
           "-TPPrice",    f"{tp:.5f}",
           "-Lots",       str(LOTS),
           "-SignalKey",  signal_key,
           "-Reason",     reason]
    log(f"  [FIRE] {' '.join(cmd[3:])}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            log(f"  [ERR] exec returned {r.returncode}: {r.stderr[:200]}")
            return False
        log(f"  [FIRED] {r.stdout[:200]}")
        return True
    except Exception as e:
        log(f"  [ERR] exec failed: {type(e).__name__}: {e}")
        return False


# ─── Main cycle ───
def cycle():
    ticks = load_recent_ticks()
    if not ticks:
        write_heartbeat("idle_no_ticks"); return
    m1 = build_m1_bars(ticks)
    if len(m1) < 200:
        write_heartbeat("idle_few_m1_bars"); return

    m5 = aggregate_to_tf(m1, 5)
    h1 = aggregate_to_h1(m1)
    if len(m5) < 30:
        write_heartbeat("idle_few_m5_bars"); return

    h1_fvgs = find_h1_fvgs(h1)
    # Check S3 on the LAST CLOSED M5 bar (m5[-2] — m5[-1] is still forming
    # if we're inside the current 5-min window; m5[-2] is the most recent
    # fully-closed one).
    if len(m5) < 2: return
    idx = len(m5) - 2
    last_closed = m5[idx]
    # Only act if this bar's close was within the last POLL_SEC*2 of wall time
    age_sec = (datetime.now() - (last_closed["time"] + timedelta(minutes=5))).total_seconds()
    if age_sec > 600:    # 10 min stale — don't act on old bars
        write_heartbeat("idle_stale_m5", age_sec=age_sec); return

    sig = detect_s3_buy(m5, idx, h1_fvgs)
    if sig is None:
        write_heartbeat("no_signal", m5_t=last_closed["time"].isoformat()); return

    signal_key = f"S3_buy_{last_closed['time'].strftime('%Y%m%d_%H%M')}"
    if read_last_signal() == signal_key:
        write_heartbeat("idle_already_fired", key=signal_key); return

    reason = (f"S3 BUY entry={sig['entry']:.2f} SL={sig['sl']:.2f} "
              f"TP={sig['tp']:.2f} R/R={(sig['tp']-sig['entry'])/(sig['entry']-sig['sl']):.1f}")
    log(f"=== S3 SIGNAL === {reason}")

    ok = fire("buy", sig["entry"], sig["sl"], sig["tp"], signal_key, reason)
    if ok:
        write_last_signal(signal_key)
        write_heartbeat("fired", key=signal_key, **sig)


def main():
    log(f"auto_s3_trader starting — LIVE_MODE={LIVE_MODE} LOTS={LOTS} POLL={POLL_SEC}s")
    write_heartbeat("starting")
    while True:
        try:
            cycle()
        except Exception as e:
            import traceback
            log(f"  [ERR] cycle failed: {type(e).__name__}: {e}")
            log(f"     {traceback.format_exc()[:400]}")
            write_heartbeat(f"error:{type(e).__name__}")
        time.sleep(POLL_SEC)


def smoke_once():
    global LIVE_MODE
    LIVE_MODE = False
    log(f"--once smoke test (LIVE_MODE forced False)")
    try:
        cycle()
        log("--once OK")
    except Exception as e:
        import traceback
        log(f"--once ERR: {type(e).__name__}: {e}")
        log(traceback.format_exc())


if __name__ == "__main__":
    if "--once" in sys.argv:
        smoke_once()
    else:
        main()
