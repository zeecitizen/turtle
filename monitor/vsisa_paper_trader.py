"""
vsisa_paper_trader.py — live VSISA pattern detector + paper-trader for XAUUSD.

Reads bid/ask from shano_live.json every second, aggregates to M5 bars in memory,
applies VSISA detection (best config from 60d backtest sweep), and tracks
hypothetical trade outcomes. Writes vsisa_live.json continuously for the dashboard.

Run via: python ensure_daemon.py vsisa_paper_trader.py
"""
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent
MON = ROOT / "monitor"
LIVE_PATH = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_live.json")
CONFIG_PATH = ROOT / "monitor" / "strategy_lab" / "vsisa_live_config.json"
STATE_PATH = MON / "vsisa_live.json"
LOG_PATH = MON / "vsisa_paper_trader.log"

POLL_SEC = 1
LOOKBACK_BARS = 100
SL_BUFFER_PT = 0.10
DOLLAR_PER_PT = 0.30 * 100.0  # 0.30 lots × 100 oz/lot = $30/pt
SLIP_COST = 1.0
MAX_HOLD_BARS = 60  # M5 bars = 5 hours
MAX_HISTORY = 200


def log(msg):
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_config():
    """Load tuned VSISA config from backtest sweep."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    # Fallback to known-good defaults from sweep
    return {
        "big_pct": 0.80, "low_pct": 0.60, "body_cov": 0.90,
        "tp_r": 3.0, "use_h1": True,
    }


class M5Aggregator:
    """Aggregates 1Hz bid/ask samples into rolling M5 OHLCV bars."""
    def __init__(self):
        self.cur_bucket = None
        self.cur_bar = None
        self.completed = []  # closed bars

    def add_tick(self, ts: datetime, bid: float, ask: float):
        mid = (bid + ask) / 2.0
        bucket = ts.replace(second=0, microsecond=0)
        bucket = bucket.replace(minute=(bucket.minute // 5) * 5)
        if self.cur_bucket is None or bucket != self.cur_bucket:
            # close previous bar
            if self.cur_bar is not None:
                self.completed.append(self.cur_bar)
                if len(self.completed) > 500:
                    self.completed = self.completed[-500:]
            self.cur_bucket = bucket
            self.cur_bar = {"ts": bucket, "o": mid, "h": mid, "l": mid, "c": mid, "v": 1}
            return True  # new bar formed
        b = self.cur_bar
        b["h"] = max(b["h"], mid)
        b["l"] = min(b["l"], mid)
        b["c"] = mid
        b["v"] += 1
        return False


class H1Aggregator:
    """Tracks rolling H1 bars for trend filter."""
    def __init__(self):
        self.bars = []
        self.cur = None
        self.cur_hr = None

    def add_tick(self, ts: datetime, bid: float, ask: float):
        mid = (bid + ask) / 2.0
        hr = ts.replace(minute=0, second=0, microsecond=0)
        if self.cur_hr != hr:
            if self.cur is not None:
                self.bars.append(self.cur)
                if len(self.bars) > 200:
                    self.bars = self.bars[-200:]
            self.cur_hr = hr
            self.cur = {"ts": hr, "o": mid, "h": mid, "l": mid, "c": mid, "v": 1}
            return
        b = self.cur
        b["h"] = max(b["h"], mid)
        b["l"] = min(b["l"], mid)
        b["c"] = mid
        b["v"] += 1


def ema(values, period):
    out = [None] * len(values)
    if not values:
        return out
    k = 2.0 / (period + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i-1] * (1 - k)
    return out


def session_thresholds(bars, lookback, big_pct, low_pct):
    if len(bars) < lookback:
        return float("inf"), float("inf")
    vols = sorted(b["v"] for b in bars[-lookback:] if b["v"] > 0)
    if not vols:
        return float("inf"), float("inf")
    return vols[int(len(vols) * big_pct)], vols[int(len(vols) * low_pct)]


def detect_setup(bars, cfg):
    """Detect VSISA pattern on the LAST CLOSED M5 bar."""
    if len(bars) < LOOKBACK_BARS + 1:
        return None
    e = bars[-2]
    r = bars[-1]
    if e["v"] == 0 or r["v"] == 0:
        return None
    big_v, low_v = session_thresholds(bars[:-1], LOOKBACK_BARS, cfg["big_pct"], cfg["low_pct"])
    if e["v"] < big_v:
        return None
    if r["v"] >= low_v:
        return None
    e_dir = "up" if e["c"] > e["o"] else "dn"
    r_dir = "up" if r["c"] > r["o"] else "dn"
    if e_dir == r_dir:
        return None
    e_lo, e_hi = min(e["o"], e["c"]), max(e["o"], e["c"])
    r_lo, r_hi = min(r["o"], r["c"]), max(r["o"], r["c"])
    e_size = e_hi - e_lo
    if e_size <= 0:
        return None
    overlap = max(0.0, min(e_hi, r_hi) - max(e_lo, r_lo))
    if overlap / e_size < cfg["body_cov"]:
        return None
    if r_dir == "dn" and r_lo > e_lo:
        return None
    if r_dir == "up" and r_hi < e_hi:
        return None
    return "sell" if r_dir == "dn" else "buy"


def h1_trend(h1_bars):
    if len(h1_bars) < 25:
        return "neutral"
    closes = [b["c"] for b in h1_bars]
    e = ema(closes, 20)
    if e[-1] is None or e[-4] is None:
        return "neutral"
    slope = e[-1] - e[-4]
    px = h1_bars[-1]["c"]
    if px > e[-1] and slope > 0:
        return "up"
    if px < e[-1] and slope < 0:
        return "dn"
    return "neutral"


def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            pass
    return {
        "open_trades": [],
        "history": [],
        "stats": {"n": 0, "wins": 0, "losses": 0, "wr": 0.0, "net_pnl": 0.0, "max_dd": 0.0,
                  "peak_equity": 0.0, "current_equity": 0.0},
        "config": {},
        "last_signal_check": None,
        "last_tick": None,
    }


def save_state(state):
    try:
        STATE_PATH.write_text(json.dumps(state, default=str))
    except OSError as e:
        log(f"save_state failed: {e}")


def update_open_trades(state, current_bid, current_ask):
    """Check if any open trades hit SL or TP."""
    still_open = []
    for tr in state["open_trades"]:
        # exit price: SELL exits at ask (buying back), BUY exits at bid (selling)
        cur_sell_exit = current_ask
        cur_buy_exit = current_bid
        cur = cur_sell_exit if tr["dir"] == "sell" else cur_buy_exit

        # Check SL
        if tr["dir"] == "sell" and cur >= tr["sl"]:
            tr["closed_at"] = datetime.now().isoformat(timespec="seconds")
            tr["exit"] = tr["sl"]
            tr["pnl"] = (tr["entry"] - tr["sl"]) * DOLLAR_PER_PT - SLIP_COST
            tr["R"] = -1.0
            tr["reason"] = "sl"
            state["history"].insert(0, tr)
            log(f"CLOSED #{tr['id']} SL  -${abs(tr['pnl']):.2f}")
            continue
        if tr["dir"] == "buy" and cur <= tr["sl"]:
            tr["closed_at"] = datetime.now().isoformat(timespec="seconds")
            tr["exit"] = tr["sl"]
            tr["pnl"] = (tr["sl"] - tr["entry"]) * DOLLAR_PER_PT - SLIP_COST
            tr["R"] = -1.0
            tr["reason"] = "sl"
            state["history"].insert(0, tr)
            log(f"CLOSED #{tr['id']} SL  -${abs(tr['pnl']):.2f}")
            continue
        # Check TP
        if tr["dir"] == "sell" and cur <= tr["tp"]:
            tr["closed_at"] = datetime.now().isoformat(timespec="seconds")
            tr["exit"] = tr["tp"]
            tr["pnl"] = (tr["entry"] - tr["tp"]) * DOLLAR_PER_PT - SLIP_COST
            tr["R"] = tr["tp_r"]
            tr["reason"] = "tp"
            state["history"].insert(0, tr)
            log(f"CLOSED #{tr['id']} TP  +${tr['pnl']:.2f}")
            continue
        if tr["dir"] == "buy" and cur >= tr["tp"]:
            tr["closed_at"] = datetime.now().isoformat(timespec="seconds")
            tr["exit"] = tr["tp"]
            tr["pnl"] = (tr["tp"] - tr["entry"]) * DOLLAR_PER_PT - SLIP_COST
            tr["R"] = tr["tp_r"]
            tr["reason"] = "tp"
            state["history"].insert(0, tr)
            log(f"CLOSED #{tr['id']} TP  +${tr['pnl']:.2f}")
            continue
        # Update floating
        tr["floating"] = round(((tr["entry"] - cur) if tr["dir"] == "sell" else (cur - tr["entry"])) * DOLLAR_PER_PT, 2)
        still_open.append(tr)
    state["open_trades"] = still_open
    state["history"] = state["history"][:MAX_HISTORY]


def update_stats(state):
    hist = state["history"]
    n = len(hist)
    wins = sum(1 for t in hist if t.get("pnl", 0) > 0)
    losses = sum(1 for t in hist if t.get("pnl", 0) <= 0)
    net = sum(t.get("pnl", 0) for t in hist)
    wr = round(100 * wins / n, 1) if n > 0 else 0
    # equity curve max DD
    equity = 0
    peak = 0
    max_dd = 0
    for t in reversed(hist):  # chronological
        equity += t.get("pnl", 0)
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    state["stats"] = {
        "n": n, "wins": wins, "losses": losses, "wr": wr,
        "net_pnl": round(net, 2),
        "max_dd": round(max_dd, 2),
        "current_equity": round(equity, 2),
    }


def main():
    log("VSISA paper trader starting")
    cfg = load_config()
    log(f"Config: big={cfg.get('big_pct')} low={cfg.get('low_pct')} body={cfg.get('body_cov')} "
        f"tp={cfg.get('tp_r')}R use_h1={cfg.get('use_h1')}")

    state = load_state()
    state["config"] = cfg

    m5 = M5Aggregator()
    h1 = H1Aggregator()
    last_live_ts = None
    next_trade_id = 1
    if state["history"]:
        next_trade_id = max(int(t.get("id", 0)) for t in state["history"]) + 1
    if state["open_trades"]:
        next_trade_id = max(next_trade_id, max(int(t.get("id", 0)) for t in state["open_trades"]) + 1)

    while True:
        try:
            d = json.loads(LIVE_PATH.read_text())
        except Exception as e:
            log(f"live read failed: {e}")
            time.sleep(POLL_SEC * 5)
            continue

        ts_str = d.get("ts", "")
        bid = d.get("bid")
        ask = d.get("ask")
        if not ts_str or bid is None or ask is None:
            time.sleep(POLL_SEC)
            continue

        try:
            ts = datetime.strptime(ts_str, "%Y.%m.%d %H:%M:%S")
        except ValueError:
            time.sleep(POLL_SEC)
            continue

        if ts == last_live_ts:
            time.sleep(POLL_SEC)
            continue
        last_live_ts = ts
        state["last_tick"] = {"ts": ts_str, "bid": bid, "ask": ask}

        # Update aggregators
        new_m5 = m5.add_tick(ts, bid, ask)
        h1.add_tick(ts, bid, ask)

        # Update open trades on every tick
        update_open_trades(state, bid, ask)

        # Pattern detection only when a new M5 bar closes
        if new_m5 and len(m5.completed) >= LOOKBACK_BARS + 1:
            sig = detect_setup(m5.completed, cfg)
            if sig:
                # H1 trend gate
                ok = True
                if cfg.get("use_h1"):
                    t = h1_trend(h1.bars)
                    if (sig == "sell" and t != "dn") or (sig == "buy" and t != "up"):
                        ok = False
                        log(f"signal {sig} blocked by H1 trend ({t})")
                if ok:
                    last_bar = m5.completed[-1]
                    entry = last_bar["c"]
                    sl = (last_bar["h"] + SL_BUFFER_PT) if sig == "sell" else (last_bar["l"] - SL_BUFFER_PT)
                    risk = abs(entry - sl)
                    tp = entry - cfg["tp_r"] * risk if sig == "sell" else entry + cfg["tp_r"] * risk
                    trade = {
                        "id": next_trade_id,
                        "opened_at": datetime.now().isoformat(timespec="seconds"),
                        "ts": last_bar["ts"].strftime("%Y-%m-%d %H:%M"),
                        "dir": sig,
                        "entry": round(entry, 2),
                        "sl": round(sl, 2),
                        "tp": round(tp, 2),
                        "tp_r": cfg["tp_r"],
                        "floating": 0.0,
                    }
                    state["open_trades"].append(trade)
                    next_trade_id += 1
                    log(f"OPEN #{trade['id']} {sig.upper()} @ {entry:.2f} SL={sl:.2f} TP={tp:.2f}")
            state["last_signal_check"] = datetime.now().isoformat(timespec="seconds")

        update_stats(state)
        save_state(state)
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("interrupted")
    except Exception as e:
        log(f"fatal: {e}")
        raise
