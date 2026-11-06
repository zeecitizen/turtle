"""
unified_backtester.py — single tick-replay engine that supports ALL filter
types (hour, EMA trend, MFE quality, confirm speed, prior-N losses, DMI, AO,
spread, body size). Used by compute_experiment.py and standalone scripts.

For each probe:
  1. Walk ticks from entry → close, find confirm tick (first time MFE >= probeConfirm).
  2. Apply pre-confirm filters (decided BEFORE main opens — uses features available
     at confirm time + history of prior fired mains).
  3. If passes filters → simulate main with trail + fearIdeal.
  4. Track outcome.

Returns rich metrics + per-day breakdown.
"""

from __future__ import annotations
import csv
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

LAB_DIR = Path(__file__).parent
COMMON_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
SHADOW_CSV = LAB_DIR / "probe_shadow_results.csv"

CONTRACT_SIZE = 100
PROBE_LOTS_DEFAULT = 0.01

# ─── Tick reading (cached) ──────────────────────────────────
_TICK_CACHE = {}

def _load_day(date):
    key = date.strftime("%Y-%m-%d")
    if key in _TICK_CACHE: return _TICK_CACHE[key]
    p = COMMON_DIR / f"shano_ticks_{key}.csv"
    out = []
    if p.exists():
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            next(f, None)
            for line in f:
                parts = line.strip().split(",")
                if len(parts) < 4: continue
                try:
                    dt = datetime.strptime(parts[0], "%Y.%m.%d %H:%M:%S")
                    bid = float(parts[2]); ask = float(parts[3])
                    out.append((dt, bid, ask))
                except (ValueError, IndexError): continue
    _TICK_CACHE[key] = out
    return out


def ticks_in_range(t_start, t_end):
    out = []
    cur = datetime(t_start.year, t_start.month, t_start.day)
    last = datetime(t_end.year, t_end.month, t_end.day)
    while cur <= last:
        for tick in _load_day(cur):
            if tick[0] < t_start: continue
            if tick[0] > t_end: break
            out.append(tick)
        cur += timedelta(days=1)
    return out


# ─── 1-min bar building (for EMAs) ──────────────────────────
def build_1m_bars():
    """Build all 1-min bars from all available tick files. Cached at module level."""
    if hasattr(build_1m_bars, "_cache"):
        return build_1m_bars._cache
    all_ticks = []
    for p in sorted(COMMON_DIR.glob("shano_ticks_*.csv")):
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                next(f, None)
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) < 4: continue
                    try:
                        dt = datetime.strptime(parts[0], "%Y.%m.%d %H:%M:%S")
                        bid = float(parts[2]); ask = float(parts[3])
                        all_ticks.append((dt, bid, ask))
                    except (ValueError, IndexError): continue
        except OSError: pass

    bars = []
    cur_min = None; o = h = l = c = None; tc = 0
    for dt, bid, ask in all_ticks:
        mid = (bid + ask) / 2
        bm = dt.replace(second=0, microsecond=0)
        if cur_min is None:
            cur_min = bm; o = h = l = c = mid; tc = 1
        elif bm != cur_min:
            bars.append((cur_min, o, h, l, c, tc))
            cur_min = bm; o = h = l = c = mid; tc = 1
        else:
            if mid > h: h = mid
            if mid < l: l = mid
            c = mid; tc += 1
    if cur_min is not None: bars.append((cur_min, o, h, l, c, tc))

    build_1m_bars._cache = bars
    return bars


def compute_ema(values, period):
    if len(values) < period: return [None] * len(values)
    alpha = 2 / (period + 1)
    out = [None] * (period - 1)
    seed = sum(values[:period]) / period
    out.append(seed)
    prev = seed
    for v in values[period:]:
        prev = (v - prev) * alpha + prev
        out.append(prev)
    return out


# ─── EMA cache (built once per run) ─────────────────────────
def get_emas(fast=34, slow=89, tf_minutes=1):
    key = (fast, slow, tf_minutes)
    if not hasattr(get_emas, "_cache"): get_emas._cache = {}
    if key in get_emas._cache: return get_emas._cache[key]
    bars_1m = build_1m_bars()
    if tf_minutes == 1:
        bars = bars_1m
    else:
        bars = []
        cur_start = None; o = h = l = c = None
        for b1m in bars_1m:
            dt = b1m[0]; b_o = b1m[1]; b_h = b1m[2]; b_l = b1m[3]; b_c = b1m[4]
            anchor_min = (dt.minute // tf_minutes) * tf_minutes
            bm = dt.replace(minute=anchor_min, second=0, microsecond=0)
            if cur_start is None:
                cur_start = bm; o = b_o; h = b_h; l = b_l; c = b_c
            elif bm != cur_start:
                bars.append((cur_start, o, h, l, c))
                cur_start = bm; o = b_o; h = b_h; l = b_l; c = b_c
            else:
                if b_h > h: h = b_h
                if b_l < l: l = b_l
                c = b_c
        if cur_start is not None: bars.append((cur_start, o, h, l, c))
    closes = [b[4] for b in bars]
    ema_f = compute_ema(closes, fast)
    ema_s = compute_ema(closes, slow)
    bar_idx = {b[0]: i for i, b in enumerate(bars)}
    get_emas._cache[key] = (ema_f, ema_s, bar_idx, bars)
    return get_emas._cache[key]


# ─── Strategy config ────────────────────────────────────────
@dataclass
class Config:
    probeConfirm: float = 0.58
    probeFail: float = 3.0
    probeLots: float = 0.01
    trailTrigger: float = 8.0
    trailDrop: float = 2.0
    fearIdeal: float = 70.0
    mainLots: float = 0.40
    horizonSec: int = 600

    # Filters
    skipBadHours: bool = False           # skip 04-06 + 21-23 broker
    trendFilter: bool = False            # skip AGAINST or NEUTRAL EMA-34/89
    skipMfeDeadZone: bool = False        # skip if MFE_at_confirm in 60-80c
    skipFastConfirm: bool = False        # skip if confirm in 3-8s (fakeout zone)
    skipPriorChop: int = 0               # skip if N+ losses in last 5 fires (0=off)
    skipPriorLossOpposite: bool = False  # skip if last fire was loss + opposite dir
    minConfirmSpeedSec: int = 0          # require confirm at least N seconds (0=off)
    maxConfirmSpeedSec: int = 0          # require confirm at most N seconds (0=off)
    requireWithTrend: bool = False       # require with-trend (stricter than trendFilter)
    trendTfMinutes: int = 1              # timeframe (in minutes) for EMA trend check (1, 2, 3, 5, ...)
    uhvFilter: bool = False              # Shano-Zee: require trigger candle to break UHV high/low
    uhvLookback: int = 20                # 1-min bars to search for UHV (highest tick-count)

    name: str = "default"


# ─── Per-probe replay ───────────────────────────────────────
def replay_probe(probe_row, cfg: Config):
    """Walk ticks, find confirm, gather features. Return None if can't confirm."""
    try:
        entry_time = datetime.fromisoformat(probe_row["entry_time"])
        close_time = datetime.fromisoformat(probe_row["close_time"])
        entry_price = float(probe_row["entry_price"])
        dir_sign = 1 if probe_row["dir"] == "buy" else -1
    except (ValueError, KeyError):
        return None

    # Walk probe lifetime; record MAE before confirm + first confirm tick
    probe_ticks = ticks_in_range(entry_time, close_time)
    if not probe_ticks: return None
    confirm_tick = None
    mae_before = 0.0
    for dt, bid, ask in probe_ticks:
        if dir_sign == 1:
            fav = (bid - entry_price) * cfg.probeLots * CONTRACT_SIZE
            adv = (entry_price - ask) * cfg.probeLots * CONTRACT_SIZE
        else:
            fav = (entry_price - ask) * cfg.probeLots * CONTRACT_SIZE
            adv = (bid - entry_price) * cfg.probeLots * CONTRACT_SIZE
        if confirm_tick is None and fav >= cfg.probeConfirm:
            confirm_tick = (dt, bid, ask, fav, (dt - entry_time).total_seconds())
            break
        if adv > mae_before: mae_before = adv

    if confirm_tick is None:
        return {"confirmed": False, "entry_time": entry_time}

    confirm_dt, confirm_bid, confirm_ask, confirm_fav, confirm_speed = confirm_tick

    return {
        "confirmed": True,
        "entry_time": entry_time,
        "confirm_dt": confirm_dt,
        "confirm_bid": confirm_bid,
        "confirm_ask": confirm_ask,
        "confirm_fav_dollars": confirm_fav,
        "confirm_speed_sec": confirm_speed,
        "mae_before_confirm": mae_before,
        "dir_sign": dir_sign,
        "entry_price": entry_price,
        "close_time": close_time,
    }


def simulate_main(main_entry, dir_sign, ticks, cfg: Config):
    if not ticks: return 0.0, "no_data"
    peak = 0.0; last_profit = 0.0
    for dt, bid, ask in ticks:
        if dir_sign == 1:
            profit = (bid - main_entry) * cfg.mainLots * CONTRACT_SIZE
        else:
            profit = (main_entry - ask) * cfg.mainLots * CONTRACT_SIZE
        last_profit = profit
        if profit > peak: peak = profit
        if profit <= -cfg.fearIdeal: return round(profit, 2), "fearIdeal"
        if peak >= cfg.trailTrigger and (peak - profit) >= cfg.trailDrop:
            return round(profit, 2), "trail"
    return round(last_profit, 2), "horizon_end"


# ─── Trend at time ──────────────────────────────────────────
def trend_at(when, ema_fast, ema_slow, bar_idx, tf_minutes=1):
    if tf_minutes == 1:
        bm = when.replace(second=0, microsecond=0)
    else:
        anchor = when.minute - (when.minute % tf_minutes)
        bm = when.replace(minute=anchor, second=0, microsecond=0)
    idx = bar_idx.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=tf_minutes * d)
            idx = bar_idx.get(t)
            if idx is not None: break
        if idx is None: return None
    if idx < 89 or idx == 0: return None
    f = ema_fast[idx]; s = ema_slow[idx]; fp = ema_fast[idx-1]
    if f is None or s is None or fp is None: return None
    if f > s and f > fp: return 1   # up
    if f < s and f < fp: return -1  # down
    return 0  # neutral


# ─── Run a strategy with all filters ─────────────────────────
def run(cfg: Config):
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    ema_f, ema_s, bar_idx, _ = get_emas(tf_minutes=cfg.trendTfMinutes)

    # 1-min bars (with tickcount) for UHV filter — built once, reused per probe
    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}

    # Track fired-main history for prior-loss filters
    fire_history = []  # list of (dir_sign, pnl, when)
    fired = []
    skipped_pre_confirm = 0  # probe never confirmed
    skipped_filtered = 0     # probe confirmed but filter blocked

    for r in rows:
        replay = replay_probe(r, cfg)
        if replay is None: continue
        if not replay["confirmed"]:
            skipped_pre_confirm += 1
            continue

        # ── Apply filters at confirm time ──
        skip = False
        reason = None

        # Filter: bad hours (narrow)
        if cfg.skipBadHours:
            h = replay["confirm_dt"].hour
            if (4 <= h <= 6) or (21 <= h <= 23):
                skip = True; reason = f"hour({h})"

        # Filter: EMA trend
        if not skip and (cfg.trendFilter or cfg.requireWithTrend):
            t = trend_at(replay["confirm_dt"], ema_f, ema_s, bar_idx, cfg.trendTfMinutes)
            if t is None and cfg.requireWithTrend: pass  # be lenient if no data
            elif t is None: pass
            elif t != replay["dir_sign"]:
                if cfg.trendFilter:
                    skip = True; reason = f"trend(t={t},pd={replay['dir_sign']})"
                elif cfg.requireWithTrend:
                    skip = True; reason = f"strict_trend"

        # Filter: MFE dead zone
        if not skip and cfg.skipMfeDeadZone:
            mfe_at_c = replay["confirm_fav_dollars"] * 100  # cents
            if 60 < mfe_at_c <= 80:
                skip = True; reason = f"mfe_dead_zone({mfe_at_c:.0f}c)"

        # Filter: fast confirm (3-8s = fakeout zone)
        if not skip and cfg.skipFastConfirm:
            cs = replay["confirm_speed_sec"]
            if 3 <= cs <= 8:
                skip = True; reason = f"fast_confirm({cs:.1f}s)"

        # Filter: Shano-Zee UHV breakout — trigger candle (1-min bar before probe
        # entry) must close beyond the high/low of the highest-tick-volume candle
        # in the prior N 1-min bars.
        if not skip and cfg.uhvFilter:
            entry_time = replay["entry_time"]
            bm = entry_time.replace(second=0, microsecond=0)
            idx = bar_idx_1m.get(bm)
            if idx is None:
                for d in range(1, 30):
                    t = bm - timedelta(minutes=d)
                    idx = bar_idx_1m.get(t)
                    if idx is not None: break
            if idx is None or idx < cfg.uhvLookback + 1:
                skip = True; reason = "uhv_no_history"
            else:
                trigger = bars_1m[idx - 1]
                lookback_bars = bars_1m[max(0, idx - 1 - cfg.uhvLookback):idx - 1]
                if not lookback_bars:
                    skip = True; reason = "uhv_no_lookback"
                else:
                    uhv = max(lookback_bars, key=lambda b: b[5])
                    breakout_ok = False
                    if replay["dir_sign"] == 1 and trigger[4] > uhv[2]: breakout_ok = True
                    elif replay["dir_sign"] == -1 and trigger[4] < uhv[3]: breakout_ok = True
                    if not breakout_ok:
                        skip = True; reason = "uhv_no_breakout"

        # Filter: confirm speed window
        if not skip and cfg.minConfirmSpeedSec > 0 and replay["confirm_speed_sec"] < cfg.minConfirmSpeedSec:
            skip = True; reason = f"too_fast({replay['confirm_speed_sec']:.0f}s)"
        if not skip and cfg.maxConfirmSpeedSec > 0 and replay["confirm_speed_sec"] > cfg.maxConfirmSpeedSec:
            skip = True; reason = f"too_slow({replay['confirm_speed_sec']:.0f}s)"

        # Filter: prior chop (last 5 fires have >= N losses)
        if not skip and cfg.skipPriorChop > 0:
            recent = fire_history[-5:]
            losses = sum(1 for h in recent if h[1] <= 0)
            if losses >= cfg.skipPriorChop:
                skip = True; reason = f"chop({losses}L/5)"

        # Filter: prior loss + opposite direction (whipsaw)
        if not skip and cfg.skipPriorLossOpposite and fire_history:
            last = fire_history[-1]
            if last[1] <= 0 and last[0] != replay["dir_sign"]:
                skip = True; reason = "whipsaw"

        if skip:
            skipped_filtered += 1
            continue

        # ── Fire the main ──
        main_entry = replay["confirm_ask"] if replay["dir_sign"] == 1 else replay["confirm_bid"]
        horizon_end = replay["confirm_dt"] + timedelta(seconds=cfg.horizonSec)
        main_ticks = ticks_in_range(replay["confirm_dt"], horizon_end)
        pnl, exit_reason = simulate_main(main_entry, replay["dir_sign"], main_ticks, cfg)

        fired.append({
            "entry_time": replay["entry_time"],
            "dir_sign": replay["dir_sign"],
            "main_pnl": pnl,
            "win": pnl > 0,
            "exit_reason": exit_reason,
        })
        fire_history.append((replay["dir_sign"], pnl, replay["confirm_dt"]))

    # ── Aggregate ──
    n = len(fired)
    wins = [f for f in fired if f["win"]]
    losses = [f for f in fired if not f["win"]]
    big_losses = [f for f in fired if f["main_pnl"] <= -30]
    total = sum(f["main_pnl"] for f in fired)

    by_day = defaultdict(float)
    for f in fired:
        by_day[f["entry_time"].strftime("%Y-%m-%d")] += f["main_pnl"]

    return {
        "name": cfg.name,
        "fired": n,
        "skipped_no_confirm": skipped_pre_confirm,
        "skipped_filtered": skipped_filtered,
        "wins": len(wins),
        "losses": len(losses),
        "big_losses": len(big_losses),
        "wr": round(len(wins) / max(n, 1) * 100, 1),
        "total": round(total, 2),
        "avg_win": round(sum(f["main_pnl"] for f in wins) / max(len(wins), 1), 2),
        "avg_loss": round(sum(f["main_pnl"] for f in losses) / max(len(losses), 1), 2),
        "max_loss": round(min((f["main_pnl"] for f in losses), default=0), 2),
        "daily": {d: round(p, 2) for d, p in by_day.items()},
    }


def fmt(s):
    daily = " | ".join(f"{d[-5:]}:${p:+.0f}" for d, p in sorted(s["daily"].items()))
    return (f"{s['name']:<55}fired={s['fired']:<3}filt_out={s['skipped_filtered']:<3}"
            f"WR={s['wr']:<5.1f}%  total=${s['total']:+8.2f}  big_L={s['big_losses']:<2}  "
            f"max_L=${s['max_loss']:>7.2f}  daily=[{daily}]")


if __name__ == "__main__":
    import sys
    # Default: just baseline + winning combo
    cfgs = [
        Config(name="baseline (no filter, 0.58/8/2/70)"),
        Config(name="baseline 0.45/12/4/50",
               probeConfirm=0.45, trailTrigger=12, trailDrop=4, fearIdeal=50),
    ]
    for c in cfgs:
        print(fmt(run(c)))
