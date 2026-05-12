"""London Breakout + VSISA combined live trader on Blueberry XAUUSD demo.

Two strategies running concurrently:
  1. LONDON BREAKOUT — 1 trade/day after 07:00 UTC, breakout of 00:00-07:00 Asian range
  2. VSISA — M5 effort+reaction pattern, fires multiple times during NY session

Trade execution: mt5.order_send() direct (Blueberry demo account 12640543)
Comment tags: "LSL_LB" (London Breakout), "LSL_VSISA"  (Sajid VSISA)

Output: monitor/london_sajid_live.json (read by dashboard /london-sajid)
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json, time, sys, signal as sigmod

CFG = {
    # Position
    "symbol": "XAUUSD",
    "lots": 0.30,
    "magic_lb": 84001,
    "magic_vsisa": 84002,
    "magic_ny": 84003,

    # London Breakout
    "lb_asian_start_min": 0,        # 00:00 UTC
    "lb_asian_end_min": 7 * 60,     # 07:00 UTC
    "lb_london_start_min": 7 * 60,  # 07:00 UTC
    "lb_day_close_min": 21 * 60,    # 21:00 UTC
    "lb_tp_mult": 1.0,              # 1:1 R:R (full range)
    "lb_sl_mult": 1.0,
    # Allow late entry today if breakout happened within last N minutes
    "lb_late_entry_max_min": 60,

    # NY Breakout (range = 0:00-13:00 UTC, breakout from 13:00 UTC)
    "ny_range_start_min": 0,
    "ny_range_end_min": 13 * 60,
    "ny_breakout_start_min": 13 * 60,
    "ny_day_close_min": 21 * 60,
    "ny_tp_mult": 1.5,        # backtest best
    "ny_sl_mult": 1.0,
    "ny_late_entry_max_min": 60,

    # VSISA
    "vsisa_lookback": 100,          # M5 bars for percentile thresholds
    "vsisa_big_pct": 0.50,
    "vsisa_low_pct": 0.50,
    "vsisa_body_cov": 0.50,
    "vsisa_tp_r": 3.0,
    "vsisa_require_prior_trend": True,
    "vsisa_session_start_min": 7 * 60,  # 07:00 UTC (London open onward)
    "vsisa_session_end_min": 21 * 60,   # 21:00 UTC

    # Common
    "poll_interval_s": 5,
    "max_concurrent_lb": 1,        # back to validated single-shot (was 5 in burst mode)
    "max_concurrent_vsisa": 2,     # max simultaneous VSISA positions
    "max_concurrent_ny": 3,        # NY: 1 initial + 2 bursts

    # LB: validated single-shot + UHV(20%) filter (replaces blind LB-burst)
    "lb_burst_mode": False,        # DISABLED — back to single-shot validated config
    "lb_uhv_enabled": True,        # require top-20% tick-volume on breakout candle
    "lb_uhv_top_pct": 0.20,        # UHV threshold (top 20% of last 20 M1 bars)
    "lb_uhv_lookback_bars": 20,
    # NY: add UHV(30%) filter + burst-on-winners pyramiding
    "ny_uhv_enabled": True,
    "ny_uhv_top_pct": 0.30,
    "ny_uhv_lookback_bars": 20,
    "ny_burst_enabled": True,      # pyramid into winning NY position
    "ny_burst_triggers_usd": [300, 600],  # fire next entry when position peak hits these P&L
    "ny_burst_max_concurrent": 3,  # initial + 2 bursts

    # Safety: equity protection
    "daily_loss_cap_usd": 200,     # halt all new trades if today's realized + floating < -$200
    "starting_balance": 5000,
    "max_daily_drawdown_pct": 4.0,

    # Session-end auto-close (CRITICAL for weekend gap protection on Friday)
    "session_close_min": 21 * 60,  # 21:00 UTC = end of NY session, Friday weekend roll
    "weekend_close_dow": 4,        # close ALL on Friday (0=Mon, 4=Fri)
}

STATE_FILE   = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\london_sajid_live.json")
LOG_FILE     = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\london_sajid_trader.log")
PERSIST_FILE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\london_sajid_persist.json")
PID_FILE     = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\london_sajid_trader.pid")

import os, atexit
def acquire_lock():
    """Refuse to start if another instance has the PID file with a running process."""
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            # Check if process is alive on Windows
            import ctypes
            PROCESS_QUERY = 0x0400
            h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY, False, old_pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                print(f"[FATAL] Another daemon already running (PID {old_pid}). Exiting.", flush=True)
                raise SystemExit(2)
        except (ValueError, OSError):
            pass
    PID_FILE.write_text(str(os.getpid()))
    atexit.register(lambda: PID_FILE.unlink(missing_ok=True))

def load_persist():
    if PERSIST_FILE.exists():
        try: return json.loads(PERSIST_FILE.read_text())
        except Exception: return {}
    return {}

def save_persist(d):
    PERSIST_FILE.write_text(json.dumps(d, indent=2, default=str))

def log(msg, also_print=True):
    line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    if also_print: print(line, flush=True)

def mt5_utc_now():
    """Authoritative current UTC time from MT5 server (skew-resistant against OS clock drift)."""
    tick = mt5.symbol_info_tick(CFG["symbol"])
    if tick is not None and tick.time > 0:
        return datetime.fromtimestamp(tick.time, tz=timezone.utc)
    return datetime.now(timezone.utc)

def init_mt5():
    if not mt5.initialize(timeout=15000):
        log(f"[FATAL] mt5.initialize failed: {mt5.last_error()}")
        sys.exit(1)
    info = mt5.terminal_info()
    acct = mt5.account_info()
    log(f"Connected: {info.company} build {info.build}")
    log(f"Account: {acct.login} ({acct.server}) balance ${acct.balance:.2f} equity ${acct.equity:.2f}")

# ─── Data fetch ──────────────────────────────────────────────────────────
def get_today_ticks():
    """Fetch all of today's ticks from MT5 (UTC, anchored on MT5 server time)."""
    now = mt5_utc_now()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc)
    ticks = mt5.copy_ticks_range(CFG["symbol"], today_start, now + timedelta(hours=2), mt5.COPY_TICKS_ALL)
    if ticks is None or len(ticks) == 0: return None
    df = pd.DataFrame(ticks)
    df["dt"] = pd.to_datetime(df["time_msc"], unit="ms", utc=True)
    df["mins_utc"] = df["dt"].dt.hour * 60 + df["dt"].dt.minute
    return df

def get_recent_m1_bars(n_bars=50):
    """Fetch last N M1 bars from MT5 (with tick_volume)."""
    rates = mt5.copy_rates_from_pos(CFG["symbol"], mt5.TIMEFRAME_M1, 0, n_bars)
    if rates is None: return None
    return pd.DataFrame(rates)

def uhv_breakout_ok(top_pct, lookback_bars):
    """Check: did the most recently CLOSED M1 bar have tick-volume in top X% of prior N bars?"""
    bars = get_recent_m1_bars(lookback_bars + 5)
    if bars is None or len(bars) < lookback_bars + 2: return False
    # Last fully closed bar = bars[-2]
    closed_idx = len(bars) - 2
    bo_vol = int(bars.iloc[closed_idx]["tick_volume"])
    lookback_vols = bars.iloc[closed_idx - lookback_bars:closed_idx]["tick_volume"].to_numpy()
    if len(lookback_vols) == 0: return False
    threshold = float(np.percentile(lookback_vols, 100 * (1 - top_pct)))
    return bo_vol >= threshold

def get_recent_m5_bars(n_bars=300):
    """Fetch last N M5 bars from MT5."""
    rates = mt5.copy_rates_from_pos(CFG["symbol"], mt5.TIMEFRAME_M5, 0, n_bars)
    if rates is None: return None
    df = pd.DataFrame(rates)
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["mins_utc"] = df["dt"].dt.hour * 60 + df["dt"].dt.minute
    return df

# ─── London Breakout detection ───────────────────────────────────────────
def lb_check(now_utc):
    """Return ('buy'/'sell', entry, sl, tp, range_pts) if breakout valid for entry NOW.
    Uses today's ticks to compute Asian range and detect first breakout."""
    today_df = get_today_ticks()
    if today_df is None or len(today_df) < 1000: return None

    asian = today_df[(today_df["mins_utc"] >= CFG["lb_asian_start_min"]) &
                     (today_df["mins_utc"] < CFG["lb_asian_end_min"])]
    if len(asian) < 100: return None  # not enough Asian session data

    a_high = float(asian["bid"].max())
    a_low  = float(asian["bid"].min())
    a_range = a_high - a_low
    range_pts = a_range * 100

    # Look at London session ticks (after Asian end)
    london = today_df[(today_df["mins_utc"] >= CFG["lb_london_start_min"]) &
                      (today_df["mins_utc"] < CFG["lb_day_close_min"])]
    if len(london) < 50: return None

    # Find first breakout
    bid = london["bid"].to_numpy()
    above = bid > a_high; below = bid < a_low
    fa = int(np.argmax(above)) if above.any() else len(bid)
    fb = int(np.argmax(below)) if below.any() else len(bid)
    if fa >= len(bid) and fb >= len(bid): return None

    if fa < fb:
        bo_dir = "buy"; bo_local = fa
    else:
        bo_dir = "sell"; bo_local = fb
    bo_ts_ms = int(london.iloc[bo_local]["time_msc"])
    bo_dt = datetime.fromtimestamp(bo_ts_ms/1000, tz=timezone.utc)
    age_min = (now_utc - bo_dt).total_seconds() / 60.0
    # In burst mode, ignore "breakout too old" — fire same-direction entries throughout the day
    if not CFG.get("lb_burst_mode") and age_min > CFG["lb_late_entry_max_min"]:
        log(f"LB: breakout too old ({age_min:.1f} min ago, max {CFG['lb_late_entry_max_min']}) — skip")
        return None

    # UHV gate: only trade if breakout has high tick-volume backing (validated edge)
    if CFG.get("lb_uhv_enabled") and not uhv_breakout_ok(CFG["lb_uhv_top_pct"], CFG["lb_uhv_lookback_bars"]):
        return None

    # BURST MODE (DISABLED in current config): kept for future enable
    if CFG.get("lb_burst_mode"):
        # Look at last N seconds of bid action
        win_sec = CFG.get("lb_burst_momentum_window_sec", 60)
        cur_ts_ms = int(today_df["time_msc"].iloc[-1])
        cutoff_ms = cur_ts_ms - win_sec * 1000
        recent = today_df[today_df["time_msc"] >= cutoff_ms]
        if len(recent) < 5: return None
        first_bid = float(recent["bid"].iloc[0])
        last_bid = float(recent["bid"].iloc[-1])
        net_move_pts = (last_bid - first_bid) * 100  # in points; positive = up
        min_pts = CFG.get("lb_burst_momentum_min_pts", 30)
        if bo_dir == "buy" and net_move_pts < min_pts:
            return None  # not enough up-momentum
        if bo_dir == "sell" and net_move_pts > -min_pts:
            return None  # not enough down-momentum
        # Also require near session extreme (not entering into a known reversal)
        sess_high = float(today_df["bid"].max())
        sess_low = float(today_df["bid"].min())
        cur_bid = last_bid
        # Find most recent time price equaled session high/low
        if bo_dir == "buy":
            recent_at_high = today_df[today_df["bid"] >= sess_high - 0.10]
            if len(recent_at_high) > 0:
                last_high_ms = int(recent_at_high["time_msc"].iloc[-1])
                age_sec = (cur_ts_ms - last_high_ms) / 1000.0
                if age_sec > CFG.get("lb_burst_momentum_high_age_sec", 90):
                    return None  # too far from session high — likely already reversing
        else:
            recent_at_low = today_df[today_df["bid"] <= sess_low + 0.10]
            if len(recent_at_low) > 0:
                last_low_ms = int(recent_at_low["time_msc"].iloc[-1])
                age_sec = (cur_ts_ms - last_low_ms) / 1000.0
                if age_sec > CFG.get("lb_burst_momentum_high_age_sec", 90):
                    return None

    # Use current price as entry (we're firing now, not at the historic breakout)
    tick = mt5.symbol_info_tick(CFG["symbol"])
    if tick is None: return None
    entry = float(tick.ask) if bo_dir == "buy" else float(tick.bid)

    # SL/TP based on Asian range from the BREAKOUT POINT (not current price)
    breakout_price = float(london.iloc[bo_local]["ask"]) if bo_dir == "buy" else float(london.iloc[bo_local]["bid"])
    sl_offset = CFG["lb_sl_mult"] * a_range
    tp_offset = CFG["lb_tp_mult"] * a_range
    if bo_dir == "buy":
        sl = breakout_price - sl_offset
        tp = breakout_price + tp_offset
    else:
        sl = breakout_price + sl_offset
        tp = breakout_price - tp_offset
    return {
        "side": bo_dir, "entry": entry, "sl": sl, "tp": tp,
        "asian_high": a_high, "asian_low": a_low, "range_pts": range_pts,
        "breakout_age_min": round(age_min, 1),
        "breakout_price": breakout_price,
    }

# ─── NY Breakout detection (range = 00:00-13:00 UTC, breakout from 13:00) ─
def ny_check(now_utc):
    """Same as LB but with NY-window range."""
    today_df = get_today_ticks()
    if today_df is None or len(today_df) < 1000: return None
    rng = today_df[(today_df["mins_utc"] >= CFG["ny_range_start_min"]) &
                   (today_df["mins_utc"] < CFG["ny_range_end_min"])]
    if len(rng) < 200: return None
    a_high = float(rng["bid"].max()); a_low = float(rng["bid"].min())
    a_range = a_high - a_low
    range_pts = a_range * 100

    bo_window = today_df[(today_df["mins_utc"] >= CFG["ny_breakout_start_min"]) &
                         (today_df["mins_utc"] < CFG["ny_day_close_min"])]
    if len(bo_window) < 50: return None
    bid = bo_window["bid"].to_numpy()
    above = bid > a_high; below = bid < a_low
    fa = int(np.argmax(above)) if above.any() else len(bid)
    fb = int(np.argmax(below)) if below.any() else len(bid)
    if fa >= len(bid) and fb >= len(bid): return None
    bo_dir = "buy" if fa < fb else "sell"
    bo_local = fa if bo_dir == "buy" else fb
    bo_ts_ms = int(bo_window.iloc[bo_local]["time_msc"])
    bo_dt = datetime.fromtimestamp(bo_ts_ms/1000, tz=timezone.utc)
    age_min = (now_utc - bo_dt).total_seconds() / 60.0
    if age_min > CFG["ny_late_entry_max_min"]: return None

    # UHV gate: only trade NY breakout if tick-volume confirms (validated +123% net combo)
    if CFG.get("ny_uhv_enabled") and not uhv_breakout_ok(CFG["ny_uhv_top_pct"], CFG["ny_uhv_lookback_bars"]):
        return None

    tick = mt5.symbol_info_tick(CFG["symbol"])
    if tick is None: return None
    entry = float(tick.ask) if bo_dir == "buy" else float(tick.bid)
    breakout_price = float(bo_window.iloc[bo_local]["ask"]) if bo_dir == "buy" else float(bo_window.iloc[bo_local]["bid"])
    sl_off = CFG["ny_sl_mult"] * a_range; tp_off = CFG["ny_tp_mult"] * a_range
    if bo_dir == "buy":
        sl = breakout_price - sl_off; tp = breakout_price + tp_off
    else:
        sl = breakout_price + sl_off; tp = breakout_price - tp_off
    return {"side": bo_dir, "entry": entry, "sl": sl, "tp": tp,
            "range_high": a_high, "range_low": a_low, "range_pts": range_pts,
            "breakout_age_min": round(age_min, 1),
            "breakout_price": breakout_price}

# ─── VSISA detection ─────────────────────────────────────────────────────
def vsisa_check():
    """Return ('buy'/'sell', entry, sl, tp) if VSISA signal qualifies on most recent closed M5 bar."""
    bars = get_recent_m5_bars(CFG["vsisa_lookback"] + 30)
    if bars is None or len(bars) < CFG["vsisa_lookback"] + 5: return None

    # Most recent CLOSED bar = bars[-2] (last bar in the array is still forming)
    # tick_volume is in bars["tick_volume"]
    idx = len(bars) - 2  # last fully closed M5 bar
    e = bars.iloc[idx-1]; r = bars.iloc[idx]

    # Session filter
    if not (CFG["vsisa_session_start_min"] <= int(r["mins_utc"]) < CFG["vsisa_session_end_min"]):
        return None

    # Effort/reaction volume thresholds (percentile of last N bars)
    lookback = CFG["vsisa_lookback"]
    vols = sorted(int(bars.iloc[i]["tick_volume"]) for i in range(idx - lookback, idx) if int(bars.iloc[i]["tick_volume"]) > 0)
    if not vols: return None
    big_v = vols[int(len(vols) * CFG["vsisa_big_pct"])]
    low_v = vols[int(len(vols) * CFG["vsisa_low_pct"])]
    if int(e["tick_volume"]) < big_v: return None
    if int(r["tick_volume"]) >= low_v: return None

    e_dir = "up" if e["close"] > e["open"] else "dn"
    r_dir = "up" if r["close"] > r["open"] else "dn"
    if e_dir == r_dir: return None  # need opposite-direction reaction

    e_lo, e_hi = min(e["open"], e["close"]), max(e["open"], e["close"])
    r_lo, r_hi = min(r["open"], r["close"]), max(r["open"], r["close"])
    e_size = e_hi - e_lo
    if e_size <= 0: return None
    overlap = max(0.0, min(e_hi, r_hi) - max(e_lo, r_lo))
    if overlap / e_size < CFG["vsisa_body_cov"]: return None

    # Prior trend filter: 20-bar SMA must agree with VSA logic
    # SELL signal needs uptrend before; BUY signal needs downtrend before
    if CFG["vsisa_require_prior_trend"]:
        if idx < 21: return None
        prior_avg = float(bars.iloc[idx-21:idx-1]["close"].mean())
        cur_close = float(bars.iloc[idx-1]["close"])
        if r_dir == "dn" and cur_close < prior_avg: return None
        if r_dir == "up" and cur_close > prior_avg: return None

    side = "sell" if r_dir == "dn" else "buy"
    # Entry at current market price (we just saw the bar close)
    tick = mt5.symbol_info_tick(CFG["symbol"])
    if tick is None: return None
    entry = float(tick.ask) if side == "buy" else float(tick.bid)
    # SL beyond engulf bar's high/low + 0.10 buffer
    if side == "sell":
        sl = float(r["high"]) + 0.10
    else:
        sl = float(r["low"]) - 0.10
    risk = abs(entry - sl)
    if risk < 0.05: return None
    if side == "sell":
        tp = entry - CFG["vsisa_tp_r"] * risk
    else:
        tp = entry + CFG["vsisa_tp_r"] * risk
    return {
        "side": side, "entry": entry, "sl": sl, "tp": tp,
        "effort_vol": int(e["tick_volume"]),
        "reaction_vol": int(r["tick_volume"]),
        "engulf_cov": round(overlap / e_size, 2),
        "signal_bar_close_ts": int(r["time"]),
    }

# ─── Order execution ─────────────────────────────────────────────────────
def open_trade(side, entry, sl, tp, magic, comment):
    order_type = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
    tick = mt5.symbol_info_tick(CFG["symbol"])
    price = tick.ask if side == "buy" else tick.bid
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": CFG["symbol"],
        "volume": CFG["lots"],
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 50,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        log(f"[ORDER FAIL] {comment}: retcode={result.retcode if result else 'None'} comment={getattr(result, 'comment', 'no result')}")
        return None
    log(f"[ORDER OK] {comment}: {side.upper()} @ {result.price:.2f} SL={sl:.2f} TP={tp:.2f} ticket={result.order}")
    return {"ticket": result.order, "price": float(result.price), "sl": sl, "tp": tp,
            "side": side, "magic": magic, "comment": comment,
            "opened_at": datetime.now(timezone.utc).isoformat()}

_position_peaks = {}  # ticket -> {"peak": float, "peak_ts": iso, "drawdown_pct": float}

def close_position(p, reason="MANUAL"):
    """Close a single position via market order."""
    request = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": CFG["symbol"],
        "volume": p.volume, "position": p.ticket,
        "type": mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY,
        "price": (mt5.symbol_info_tick(CFG["symbol"]).bid if p.type == 0
                  else mt5.symbol_info_tick(CFG["symbol"]).ask),
        "deviation": 50, "magic": p.magic, "comment": f"LSL_{reason}",
        "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
    }
    r = mt5.order_send(request)
    if r and r.retcode == mt5.TRADE_RETCODE_DONE:
        log(f"[CLOSED] ticket={p.ticket} via {reason} fill={r.price:.2f}")
        return True
    log(f"[CLOSE FAIL] ticket={p.ticket} {reason}: rc={r.retcode if r else None}")
    return False

def session_end_close(now_utc, mins_utc):
    """Close all our positions at session end (CRITICAL on Friday — weekend gap)."""
    if mins_utc < CFG["session_close_min"]: return False
    raw = mt5.positions_get(symbol=CFG["symbol"]) or []
    ours = [p for p in raw if p.magic in (CFG["magic_lb"], CFG["magic_vsisa"], CFG["magic_ny"])]
    if not ours: return False
    is_friday = now_utc.weekday() == CFG["weekend_close_dow"]
    log(f"[SESSION END] {'FRIDAY-WEEKEND-CLOSE ' if is_friday else ''}closing {len(ours)} open positions at {now_utc.strftime('%H:%M')} UTC")
    for p in ours:
        close_position(p, reason="SESSION_END")
    return True

def get_last_3h_history():
    """Pull ALL XAUUSD closed trades from last 3 hours (regardless of magic).
    Uses MT5 server time (via latest tick) to avoid system-clock skew."""
    # Anchor 'now' on MT5's latest tick timestamp, not the OS clock (skew-resistant).
    tick = mt5.symbol_info_tick(CFG["symbol"])
    if tick is not None and tick.time > 0:
        mt5_now = datetime.fromtimestamp(tick.time, tz=timezone.utc)
    else:
        mt5_now = datetime.now(timezone.utc)
    # Use a window that's wider than 3h to be safe (covers system-clock skew up to many hours).
    since = mt5_now - timedelta(hours=3)
    # Query with a generous future buffer too (some brokers stamp closes slightly ahead).
    deals = mt5.history_deals_get(since, mt5_now + timedelta(hours=2))
    if not deals: return []
    OUR_MAGICS = (CFG["magic_lb"], CFG["magic_vsisa"], CFG["magic_ny"])
    # Build position_id → opener info so we can tag rows correctly
    # NOTE: must record opener type for side (close-deal type is OPPOSITE of position direction)
    pid_to_open = {}
    for d in deals:
        if d.entry == 0 and "XAUUSD" in (d.symbol or ""):
            pid_to_open[d.position_id] = {"magic": d.magic, "comment": d.comment,
                                           "px": d.price, "ts": d.time_msc, "type": d.type}
    out = []
    for d in deals:
        if d.entry != 1: continue
        if "XAUUSD" not in (d.symbol or ""): continue
        opener = pid_to_open.get(d.position_id, {})
        opener_magic = opener.get("magic", 0)
        opener_type = opener.get("type", -1)
        is_ours = opener_magic in OUR_MAGICS
        strategy = ("LB" if opener_magic == CFG["magic_lb"]
                    else "NY" if opener_magic == CFG["magic_ny"]
                    else "VSISA" if opener_magic == CFG["magic_vsisa"]
                    else "OTHER")
        # Side = direction of the POSITION, derived from the OPEN deal (not the close deal)
        side = "buy" if opener_type == 0 else "sell" if opener_type == 1 else "?"
        out.append({
            "ticket": d.ticket, "side": side,
            "lots": d.volume, "exit_price": d.price, "pnl": d.profit,
            "exit_comment": d.comment,
            "open_comment": opener.get("comment", ""),
            "open_price": opener.get("px"),
            "is_ours": is_ours, "strategy": strategy,
            "opened_at": (datetime.fromtimestamp(opener.get("ts", 0)/1000, tz=timezone.utc).isoformat()
                          if opener.get("ts") else None),
            "closed_at": datetime.fromtimestamp(d.time_msc/1000, tz=timezone.utc).isoformat(),
            "position_id": d.position_id,
        })
    return sorted(out, key=lambda x: x["closed_at"], reverse=True)

def get_open_positions():
    pos = mt5.positions_get(symbol=CFG["symbol"])
    if pos is None: return []
    out = []
    for p in pos:
        if p.magic in (CFG["magic_lb"], CFG["magic_vsisa"], CFG["magic_ny"]):
            # Update peak tracking
            tk = p.ticket
            cur_pnl = float(p.profit)
            if tk not in _position_peaks or cur_pnl > _position_peaks[tk]["peak"]:
                _position_peaks[tk] = {"peak": cur_pnl, "peak_ts": datetime.now(timezone.utc).isoformat()}
            peak = _position_peaks[tk]["peak"]
            drawdown_from_peak = peak - cur_pnl
            out.append({
                "ticket": tk, "side": "buy" if p.type == 0 else "sell",
                "lots": p.volume, "entry": p.price_open,
                "sl": p.sl, "tp": p.tp, "floating": cur_pnl,
                "peak": round(peak, 2),
                "peak_ts": _position_peaks[tk].get("peak_ts"),
                "drawdown_from_peak": round(drawdown_from_peak, 2),
                "magic": p.magic, "comment": p.comment,
                "opened_at_ts": p.time,
            })
    # Clean up peaks for closed positions
    open_tickets = {p.ticket for p in pos}
    for k in list(_position_peaks.keys()):
        if k not in open_tickets: del _position_peaks[k]
    return out

def get_closed_today():
    """Get our closed deals from today. Uses MT5 server time."""
    now = mt5_utc_now()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc)
    deals = mt5.history_deals_get(today_start, now + timedelta(hours=2))
    if deals is None: return []
    OUR_MAGICS = (CFG["magic_lb"], CFG["magic_vsisa"], CFG["magic_ny"])
    pos_id_to_magic = {}
    pos_id_to_open_comment = {}
    pos_id_to_type = {}  # opener type — needed for correct side display
    for d in deals:
        if d.entry == 0 and d.magic in OUR_MAGICS:
            pos_id_to_magic[d.position_id] = d.magic
            pos_id_to_open_comment[d.position_id] = d.comment
            pos_id_to_type[d.position_id] = d.type
    out = []
    for d in deals:
        if d.entry == 1 and d.position_id in pos_id_to_magic:
            our_magic = pos_id_to_magic[d.position_id]
            opener_type = pos_id_to_type.get(d.position_id, -1)
            side = "buy" if opener_type == 0 else "sell" if opener_type == 1 else "?"
            out.append({
                "ticket": d.ticket, "side": side,
                "lots": d.volume, "price": d.price, "pnl": d.profit,
                "comment": d.comment,           # close reason (e.g., 'ShanoExit:TRAIL ...')
                "open_comment": pos_id_to_open_comment.get(d.position_id, ""),
                "magic": our_magic,             # always our strategy's magic, not EA's mg=0
                "closed_at": datetime.fromtimestamp(d.time_msc/1000, tz=timezone.utc).isoformat(),
                "position_id": d.position_id,
            })
    return sorted(out, key=lambda x: x["closed_at"])

# ─── Main loop ──────────────────────────────────────────────────────────
def get_live_range_info(now_utc):
    """Compute current Asian + NY range progress + current price for dashboard."""
    try:
        df_today = get_today_ticks()
        if df_today is None or len(df_today) < 100: return None
        cur_tick = mt5.symbol_info_tick(CFG["symbol"])
        cur_bid = float(cur_tick.bid) if cur_tick else None
        out = {"current_bid": cur_bid, "current_minute_utc": now_utc.hour * 60 + now_utc.minute}
        # Asian range progress (LB)
        asian = df_today[(df_today["mins_utc"] >= CFG["lb_asian_start_min"]) &
                          (df_today["mins_utc"] < CFG["lb_asian_end_min"])]
        if len(asian) >= 50:
            a_high = float(asian["bid"].max()); a_low = float(asian["bid"].min())
            out["lb_range"] = {"high": round(a_high, 2), "low": round(a_low, 2),
                                "width_pts": round((a_high - a_low) * 100, 0),
                                "complete": now_utc.hour * 60 + now_utc.minute >= CFG["lb_asian_end_min"]}
            # Distance to breakout
            if cur_bid:
                dist_high = (a_high - cur_bid) * 100
                dist_low = (cur_bid - a_low) * 100
                out["lb_range"]["distance_to_high_pts"] = round(dist_high, 1)
                out["lb_range"]["distance_to_low_pts"] = round(dist_low, 1)
        # NY range progress
        ny_rng = df_today[(df_today["mins_utc"] >= CFG["ny_range_start_min"]) &
                          (df_today["mins_utc"] < CFG["ny_range_end_min"])]
        if len(ny_rng) >= 50:
            n_high = float(ny_rng["bid"].max()); n_low = float(ny_rng["bid"].min())
            out["ny_range"] = {"high": round(n_high, 2), "low": round(n_low, 2),
                                "width_pts": round((n_high - n_low) * 100, 0),
                                "complete": now_utc.hour * 60 + now_utc.minute >= CFG["ny_range_end_min"]}
            if cur_bid:
                out["ny_range"]["distance_to_high_pts"] = round((n_high - cur_bid) * 100, 1)
                out["ny_range"]["distance_to_low_pts"] = round((cur_bid - n_low) * 100, 1)
        return out
    except Exception as e:
        log(f"[range info error] {type(e).__name__}: {e}", also_print=False)
        return None

def write_state(open_pos, closed, lb_today_done, ny_today_done,
                lb_signal_pending, ny_signal_pending, vsisa_signal_pending,
                last_check_ts, live_range=None):
    closes_lb    = [c for c in closed if c["magic"] == CFG["magic_lb"]]
    closes_vsisa = [c for c in closed if c["magic"] == CFG["magic_vsisa"]]
    closes_ny    = [c for c in closed if c["magic"] == CFG["magic_ny"]]
    open_lb      = [p for p in open_pos if p["magic"] == CFG["magic_lb"]]
    open_vsisa   = [p for p in open_pos if p["magic"] == CFG["magic_vsisa"]]
    open_ny      = [p for p in open_pos if p["magic"] == CFG["magic_ny"]]
    state = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_check": last_check_ts,
        "lb": {
            "today_done": lb_today_done,
            "open": open_lb, "closed_today": closes_lb,
            "net_today": round(sum(c["pnl"] for c in closes_lb), 2),
            "floating": round(sum(p["floating"] for p in open_lb), 2),
            "pending_signal": lb_signal_pending,
        },
        "ny": {
            "today_done": ny_today_done,
            "open": open_ny, "closed_today": closes_ny,
            "net_today": round(sum(c["pnl"] for c in closes_ny), 2),
            "floating": round(sum(p["floating"] for p in open_ny), 2),
            "pending_signal": ny_signal_pending,
        },
        "vsisa": {
            "open": open_vsisa, "closed_today": closes_vsisa,
            "net_today": round(sum(c["pnl"] for c in closes_vsisa), 2),
            "floating": round(sum(p["floating"] for p in open_vsisa), 2),
            "pending_signal": vsisa_signal_pending,
        },
        "live_range": live_range,
        "last_3h_history": get_last_3h_history(),
        "config": CFG,
    }
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))

def main():
    acquire_lock()
    init_mt5()
    log("=" * 60)
    log("London-Sajid Trader started")
    log(f"  Lots: {CFG['lots']} | LB magic: {CFG['magic_lb']} | VSISA magic: {CFG['magic_vsisa']}")
    log("=" * 60)

    last_vsisa_signal_bar_ts = 0
    persist = load_persist()
    log(f"Persist state loaded: {persist}")
    cycle = 0
    cached_live_range = None  # cache between recomputes
    while True:
        try:
            cycle += 1
            now = mt5_utc_now()  # MT5 server time, immune to OS clock skew
            mins_utc = now.hour * 60 + now.minute

            # Session-end close BEFORE evaluating signals
            session_end_close(now, mins_utc)

            open_pos = get_open_positions()
            closed = get_closed_today()
            open_lb_count    = sum(1 for p in open_pos if p["magic"] == CFG["magic_lb"])
            open_vsisa_count = sum(1 for p in open_pos if p["magic"] == CFG["magic_vsisa"])
            open_ny_count    = sum(1 for p in open_pos if p["magic"] == CFG["magic_ny"])
            today_str = now.strftime("%Y-%m-%d")
            persisted_ny_date = persist.get("ny_fired_date")
            # In LB-burst mode, "today_done" is replaced by cooldown check
            if CFG.get("lb_burst_mode"):
                last_lb_ts = persist.get("lb_last_fire_ts_ms", 0)
                if not isinstance(last_lb_ts, (int, float)): last_lb_ts = 0
                cooldown_ms = CFG["lb_burst_cooldown_sec"] * 1000
                t_ms_now = int(now.timestamp() * 1000)
                lb_cooldown_ok = (t_ms_now - last_lb_ts) >= cooldown_ms
                lb_today_done = (open_lb_count >= CFG["max_concurrent_lb"]) or (not lb_cooldown_ok)
            else:
                persisted_lb_date = persist.get("lb_fired_date")
                lb_today_done = (open_lb_count > 0
                                 or any(c["magic"] == CFG["magic_lb"] for c in closed)
                                 or persisted_lb_date == today_str)
            ny_today_done = (open_ny_count > 0
                             or any(c["magic"] == CFG["magic_ny"] for c in closed)
                             or persisted_ny_date == today_str)

            lb_signal = None
            ny_signal = None
            vsisa_signal = None

            # === EQUITY PROTECTION: halt if day P&L below cap ===
            day_realized = sum(c["pnl"] for c in closed)
            day_floating = sum(p["floating"] for p in open_pos)
            day_total = day_realized + day_floating
            equity_halt = day_total <= -CFG["daily_loss_cap_usd"]
            if equity_halt and cycle % 12 == 0:
                log(f"[EQUITY HALT] day_total=${day_total:.2f} <= -${CFG['daily_loss_cap_usd']} cap; no new trades")

            # === LONDON BREAKOUT (BURST MODE: multiple entries, EA-managed exits) ===
            in_lb_window = (CFG["lb_burst_window_start_min"] <= mins_utc < CFG["lb_burst_window_end_min"]
                            if CFG.get("lb_burst_mode") else
                            CFG["lb_london_start_min"] <= mins_utc < CFG["lb_day_close_min"])
            if not equity_halt and not lb_today_done and in_lb_window:
                lb_sig = lb_check(now)
                if lb_sig:
                    lb_signal = lb_sig
                    if open_lb_count < CFG["max_concurrent_lb"]:
                        mode_tag = "BURST" if CFG.get("lb_burst_mode") else "ONCE"
                        log(f"LB-{mode_tag} SIGNAL: {lb_sig['side'].upper()} entry={lb_sig['entry']:.2f} SL={lb_sig['sl']:.2f} TP={lb_sig['tp']:.2f} range={lb_sig['range_pts']:.0f}pts age={lb_sig['breakout_age_min']:.1f}min open={open_lb_count}/{CFG['max_concurrent_lb']}")
                        result = open_trade(lb_sig["side"], lb_sig["entry"], lb_sig["sl"], lb_sig["tp"],
                                            CFG["magic_lb"], f"LSL_LB_{now.strftime('%H%M%S')}")
                        if result:
                            if CFG.get("lb_burst_mode"):
                                persist["lb_last_fire_ts_ms"] = int(now.timestamp() * 1000)
                                persist["lb_last_ticket"] = result["ticket"]
                            else:
                                persist["lb_fired_date"] = today_str
                                persist["lb_last_ticket"] = result["ticket"]
                            save_persist(persist)

            # === NY BREAKOUT — initial entry + burst-on-winners ($300, $600 peaks) ===
            in_ny_window = CFG["ny_breakout_start_min"] <= mins_utc < CFG["ny_day_close_min"]
            if not equity_halt and in_ny_window:
                # 1) INITIAL entry (if no NY position open yet today)
                if not ny_today_done and open_ny_count == 0:
                    ny_sig = ny_check(now)
                    if ny_sig:
                        ny_signal = ny_sig
                        log(f"NY SIGNAL: {ny_sig['side'].upper()} entry={ny_sig['entry']:.2f} SL={ny_sig['sl']:.2f} TP={ny_sig['tp']:.2f} range={ny_sig['range_pts']:.0f}pts age={ny_sig['breakout_age_min']:.1f}min UHV-confirmed")
                        result = open_trade(ny_sig["side"], ny_sig["entry"], ny_sig["sl"], ny_sig["tp"],
                                            CFG["magic_ny"], f"LSL_NY_{now.strftime('%H%M%S')}")
                        if result:
                            persist["ny_fired_date"] = today_str
                            persist["ny_last_ticket"] = result["ticket"]
                            persist["ny_dir"] = ny_sig["side"]
                            persist["ny_initial_entry"] = result["price"]
                            persist["ny_burst_levels_fired"] = []  # track which $ thresholds triggered
                            save_persist(persist)

                # 2) BURST entries: pyramid into a winning NY position
                if CFG.get("ny_burst_enabled") and open_ny_count >= 1 and open_ny_count < CFG["max_concurrent_ny"]:
                    ny_dir = persist.get("ny_dir")
                    levels_fired = list(persist.get("ny_burst_levels_fired", []))
                    if ny_dir:
                        # Find the initial NY position to track its peak
                        ny_positions = [p for p in open_pos if p["magic"] == CFG["magic_ny"]]
                        if ny_positions:
                            max_peak = max(p.get("peak", -1e9) for p in ny_positions)
                            for trigger in CFG["ny_burst_triggers_usd"]:
                                if trigger in levels_fired: continue
                                if max_peak >= trigger:
                                    # Fire next burst entry in same direction
                                    cur_tick = mt5.symbol_info_tick(CFG["symbol"])
                                    if cur_tick is None: continue
                                    burst_entry = float(cur_tick.ask) if ny_dir == "buy" else float(cur_tick.bid)
                                    # SL/TP based on initial NY's range setup (pull from initial position)
                                    ref_pos = ny_positions[0]
                                    burst_sl = ref_pos["sl"]
                                    burst_tp = ref_pos["tp"]
                                    log(f"NY BURST ${trigger}: peak hit ${max_peak:.2f}, firing burst {ny_dir.upper()} @ {burst_entry:.2f}")
                                    result = open_trade(ny_dir, burst_entry, burst_sl, burst_tp,
                                                        CFG["magic_ny"], f"LSL_NY_BURST{trigger}_{now.strftime('%H%M%S')}")
                                    if result:
                                        levels_fired.append(trigger)
                                        persist["ny_burst_levels_fired"] = levels_fired
                                        save_persist(persist)
                                        break  # only fire one burst per cycle

            # === VSISA — multiple per day during session ===
            if not equity_halt and open_vsisa_count < CFG["max_concurrent_vsisa"]:
                vs_sig = vsisa_check()
                if vs_sig:
                    vsisa_signal = vs_sig
                    bar_ts = vs_sig.get("signal_bar_close_ts", 0)
                    if bar_ts > last_vsisa_signal_bar_ts:
                        log(f"VSISA SIGNAL: {vs_sig['side'].upper()} entry={vs_sig['entry']:.2f} SL={vs_sig['sl']:.2f} TP={vs_sig['tp']:.2f} eff_v={vs_sig['effort_vol']} react_v={vs_sig['reaction_vol']} cov={vs_sig['engulf_cov']}")
                        result = open_trade(vs_sig["side"], vs_sig["entry"], vs_sig["sl"], vs_sig["tp"],
                                            CFG["magic_vsisa"], f"LSL_VSISA_{now.strftime('%H%M%S')}")
                        if result:
                            last_vsisa_signal_bar_ts = bar_ts

            # Write state with live range info — cache so JSON has last-known when not recomputing
            if cycle % 6 == 0:
                lr = get_live_range_info(now)
                if lr is not None: cached_live_range = lr
            write_state(open_pos, closed, lb_today_done, ny_today_done,
                        lb_signal, ny_signal, vsisa_signal, now.isoformat(),
                        live_range=cached_live_range)

            if cycle % 12 == 0:  # log every minute
                log(f"[HB] cycle {cycle} | LB:{open_lb_count}/{lb_today_done} NY:{open_ny_count}/{ny_today_done} VSISA:{open_vsisa_count} closed={len(closed)} | mins_utc={mins_utc} ({now.strftime('%H:%M')})")

            time.sleep(CFG["poll_interval_s"])
        except KeyboardInterrupt:
            log("Stopped by user")
            break
        except Exception as e:
            log(f"[ERROR] cycle {cycle}: {type(e).__name__}: {e}")
            import traceback
            log(traceback.format_exc(), also_print=False)
            time.sleep(CFG["poll_interval_s"])

    mt5.shutdown()

if __name__ == "__main__":
    main()
