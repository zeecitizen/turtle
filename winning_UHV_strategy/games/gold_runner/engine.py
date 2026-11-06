"""engine.py - Golden Gravity: The $1 Heist - the authoritative game state (CONTRACT.md sections 5-7, REQUIREMENTS.md v2.2).

The backend owns everything that is money: orders, the floating result, settlement (read from the broker), limits, the round state.
The frontend only draws the snapshot this module builds and sends player intents (POST /api/act -> Engine.act).

  eng = Engine(feed)            # feed = feeds.SimFeed / LiveFeed / ReplayFeed (CONTRACT.md section 4) or a test double
  eng.start()                   # threads: tick loop (10 Hz + woken by feed events) and ONE broker worker
  eng.snapshot() / eng.snapshot_json()   # section 7
  eng.act({"action": "fund", "nonce": "n1", "sent_at": t, "args": {...}})  -> {"accepted": bool, "why": str|None}
  eng.update_settings({...})    # POST /api/settings
  eng.events_since(seq, timeout) # SSE fan-out

Safety rules implemented here (CONTRACT.md section 0):
  * a trading call (feed.place / set_protective / close) happens ONLY inside a job queued by a player action (act) or by the documented
    automatic exits (session end / weekend auto close, kill). Wooden rounds, the Twin and the eject counterfactual use a shadow book
    over the current feed's quotes - feeds.ShadowBroker (B-FEEDS) when it imports, else engine.PaperBroker (same PX rules) - and never
    reach the feed. config "shadow_broker": "engine" forces the PaperBroker (the unit tests do).
  * the game only ever addresses the position id it opened itself; positions it did not open are never closed, modified or counted.
  * the engine lock is never held across a broker call.
"""
import collections
import glob
import itertools
import json
import datetime as _dtm
from zoneinfo import ZoneInfo
import math
import os
import random
import re
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone

import diamond as dia_mod

try:
    from zoneinfo import ZoneInfo
except Exception:  # noqa: BLE001
    ZoneInfo = None

HERE = os.path.dirname(os.path.abspath(__file__))
UTC = timezone.utc

# ----------------------------------------------------------------------------------------------------------------------------------
# config (CONTRACT.md section 5 verbatim, then B-ENGINE extras with safe defaults)
DEFAULTS = {
    "port": 8790, "symbol": "XAU/USD", "sym_id": 1019,
    "coin_oz": 0.01, "min_qty": 0.01, "qty_step": 0.01, "stop_dist": 1.0, "stop_choices": [1.0, 2.0, 3.0],
    "targets": [1.0, 1.2, 1.5, 2.0, 3.0], "target_default": 1.0, "coins_max": 3, "alley_needs_machete": False,
    "haggle_step": 0.10, "haggle_max": 3, "haggle_reach_x": 0.12, "walls_max": 99, "merchant_profit_margin": 0.0008, "wall_buffer": 0.30, "min_sl_gap": 0.05,
    "tilt_window_s": 10, "tilt_long_window_s": 30, "tilt_full_scale": 0.6, "patience_s": 30, "tilt_mode": "delta", "tilt_ha_scale": 1.20, "tilt_ha_ema_s": 3.0, "dia_unit": 1.0,
    "merchant_period_s": 20, "night_after_s": 600, "golden_hour_s": 60, "auto_close_before_close_min": 5,
    "link_freeze_s": 2.0, "stale_instruction_s": 2.0, "feed_stale_s": 2.0, "feed_dead_s": 15,
    "rounds_max": 30, "loss_max_coins": 10, "jam_after_stops": 3, "jam_minutes": 10,
    "alley_needed": 5, "twin_unlock_rounds": 50, "ghosts": 3, "barrel_gap": 0.30,
    "stake_pivot": 2, "stake_merge": 0.25, "profile_bars": 20, "terrain_bins": 96, "gap_min": 0.25,
    "dead_hours_utc": [["20:45", "23:00"]], "news_window_min": 15, "news_impacts": ["high"], "news_shutters_in_sim": False, "news_shutters": True,
    "london_open": "08:00 Europe/London", "newyork_open": "09:30 America/New_York",
    "live_enabled": False,
    # --- extras (B-ENGINE) ---
    "host": "127.0.0.1",
    "daily_break_start": "17:00 America/New_York", "daily_break_end": "18:00 America/New_York",
    "weekend_close_day": 4, "weekend_open_day": 6,          # Friday's break start -> Sunday's break end (NY local weekdays, Mon=0)
    "sim_real_hours": False,                                # sim/replay ignore the real dead hours / weekend unless True (--real-hours)
    "leverage": 1000, "coin_max_oz": 0.30, "loss_max_balance_pct": 0.05, "limits_count_wooden": False,
    "vol_dead": 0.20, "vol_calm": 0.55, "vol_storm": 1.60, "storm_spread": 0.45, "lightning_usd": 0.60,
    "season_scale": 40.0, "pit_full_spread": 0.60, "tilt_ema_s": 1.5,
    "paper_slippage_max": 0.06, "paper_fee_per_oz": 0.0, "counterfactual_max_s": 3600,
    "shoot_retry_s": 3.0, "shoot_refusals_max": 3, "outside_grace_s": 3.0, "settle_timeout_s": 12.0,
    "news_show_impacts": ["high", "medium"], "snapshot_hz": 10,
    "kill_retry_s": 3.0,                 # a refused kill close is re-sent this often until the position is gone
    "unknown_proof_s": 15.0,             # an uncertain order: the deal history must show no fill for this long before the note returns
    "unknown_proof_accepted_s": 60.0,    # ... and this long when the broker had ACCEPTED the order (its position id was never resolved)
    "protect_grace_s": 2.0,              # after the fill, the broker's book must show both the stop and the target within this time
    "settle_poll_slow_s": 2.0,           # settlement pending past settle_timeout_s: the deal history is polled this often (never given up)
    "live_account_id": "L1869984",       # LiveFeed trades only on this account (feeds.py reads it from config.json)
}
UNCERTAIN_ERRORS = ("TIMEOUT", "SEND_UNCERTAIN", "SOCKET_CLOSED", "PAGE_RELOADED", "CDP_CLOSED")
TERRAIN_X0, TERRAIN_X1 = -0.3, 1.3
OUTCOMES = ("buyer", "anvil", "barrel", "merchant", "eject", "session", "kill", "outside")
SESSIONS = ("asia", "london", "newyork", "dead")
WEATHERS = ("dead", "calm", "active", "storm")
TROPHIES = {
    "first_wooden": "First wooden coin",
    "alley_graduate": "Graduated from the Alley",
    "patient_shot": "Waited at the door",
    "tied_before_haggle": "Tied the rope before haggling",
    "twin_round": "Let the Twin play a round",
    "rode_the_night": "Rode out the night",
    "walked_away": "Walked away when the Collector came",
    "waited_storm": "Waited out a storm",
}


NY_TZ = ZoneInfo("America/New_York")

def load_config(path=None, overrides=None):
    cfg = json.loads(json.dumps(DEFAULTS))
    path = path or os.path.join(HERE, "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if not k.startswith("_"):
                cfg[k] = v
    except FileNotFoundError:
        pass
    except Exception as e:  # noqa: BLE001
        print(f"[engine] config.json unreadable ({e}); using defaults")
    for k, v in (overrides or {}).items():
        cfg[k] = v
    return cfg


# ----------------------------------------------------------------------------------------------------------------------------------
# pure math - identical to tools/make_fixtures.py (the fixtures and the engine must agree to the last digit)
def _trim4(x):
    """4 decimals with trailing zeros dropped, never fewer than 2: 0.01 -> "0.01", 0.0198 -> "0.0198", 0.022 -> "0.022"."""
    s = f"{x:.4f}".rstrip("0")
    whole, frac = s.split(".")
    return whole + "." + frac.ljust(2, "0")


def money(usd, risk, signed=False):
    """Real money in dollars. Small coins (risk < $1) keep up to 4 decimals so a cent's fraction shows ("$0.0098", "$0.01");
    bigger ones show 2 ("$1.20"). signed -> "+$0.0239" / "-$0.01". Zee 2026-11-04: use the $ symbol, never the cent sign."""
    if usd is None:
        return ""
    if risk < 1:
        v = round(usd, 4)
        body = "$" + _trim4(abs(v))
    else:
        v = round(usd, 2)
        body = f"${abs(v):,.2f}"
    if v < 0:
        return "-" + body
    if signed and v > 0:
        return "+" + body
    return body


def ladder(side, fill, sl, tp, banked=0.0, qty=0.01, qty0=0.01):
    """The one axis: x(p) = a + b*p. sl/tp are the INITIAL stop and target (fixed at the fill). Returns (a, b, sd0, td0)."""
    sd0, td0 = abs(fill - sl), abs(tp - fill)
    f = qty / qty0
    span = sd0 + td0
    if span <= 0:
        span = 1e-9
    b = f * side / span
    a = (banked / qty0 - f * side * fill + sd0) / span
    return a, b, sd0, td0


def xp(a, b, p):
    return round(a + b * p, 5)


def ha_delta(bars, n=20):
    """Heikin-Ashi body of the current (forming) 1-minute bar: HA close - HA open, built recursively over the last n bars
    (HA_C = (O+H+L+C)/4, HA_O = (previous HA_O + previous HA_C)/2). Bars are [t, o, h, l, c, ...]. Zee 2026-11-04: the street's tilt."""
    seq = [b for b in bars[-n:] if len(b) >= 5]
    if not seq:
        return 0.0
    ha_o = (seq[0][1] + seq[0][4]) / 2.0
    ha_c = (seq[0][1] + seq[0][2] + seq[0][3] + seq[0][4]) / 4.0
    for b in seq[1:]:
        ha_o = (ha_o + ha_c) / 2.0
        ha_c = (b[1] + b[2] + b[3] + b[4]) / 4.0
    return ha_c - ha_o


def vsa_read(bars, vols, avg_n=20):
    """Volume Spread Analysis on the last two 1-minute bars (Zee 2026-11-04: hints, never promises). bars [t, o, h, l, c, ...], vols the
    matching volumes. Returns (kind, direction) or (None, 0):
      ("trap", -1)      upthrust: an ultra-high-volume bar makes a new 20-bar high but closes in its bottom third (sellers took over)
      ("trap", +1)      spring:   a UHV bar makes a new 20-bar low but closes in its top third (buyers took over)
      ("stopping", +1)  stopping volume after a fall: UHV, the bar closes in its upper half or barely moves (buyers absorb the selling)
      ("stopping", -1)  the mirror after a rise
    UHV = at least twice the average volume of the previous avg_n bars and the biggest of the last 10."""
    n = len(bars)
    if n < avg_n + 2 or len(vols) != n:
        return None, 0
    best = None
    for i in (n - 1, n - 2):                      # the forming bar and the last closed one: the stronger spike counts
        prev = vols[i - avg_n:i]
        if not prev or any(v is None for v in prev) or vols[i] is None:
            continue
        avg = sum(prev) / len(prev)
        if avg <= 0 or vols[i] < 2.0 * avg or vols[i] < max(vols[max(0, i - 10):i]):
            continue
        ratio = vols[i] / avg
        if best is None or ratio > best[0]:
            best = (ratio, i)
    if best is None:
        return None, 0
    i = best[1]
    _t, o, h, lo, cl = bars[i][:5]
    rng = h - lo
    pos = (cl - lo) / rng if rng > 0 else 0.5
    window = bars[i - avg_n:i]
    avg_rng = sum(b[2] - b[3] for b in window) / len(window)
    move = cl - bars[max(0, i - 6)][4]
    if h >= max(b[2] for b in window) and pos <= 0.33:
        return "trap", -1
    if lo <= min(b[3] for b in window) and pos >= 0.67:
        return "trap", 1
    if move <= -avg_rng and (pos >= 0.5 or rng <= 0.6 * avg_rng):
        return "stopping", 1
    if move >= avg_rng and (pos <= 0.5 or rng <= 0.6 * avg_rng):
        return "stopping", -1
    return None, 0


def pivots(bars, side, k=2, merge=0.25):
    """Confirmed swing lows (side +1) / highs (side -1) of 1-minute bars; the last bar is still forming, so a pivot's right-hand
    neighbours must all be closed. Pivots closer than `merge` merge (keeping the extreme)."""
    out = []
    for i in range(k, len(bars) - k - 1):
        if side > 0:
            v = bars[i][3]
            if all(v < bars[j][3] for j in range(i - k, i + k + 1) if j != i):
                out.append(v)
        else:
            v = bars[i][2]
            if all(v > bars[j][2] for j in range(i - k, i + k + 1) if j != i):
                out.append(v)
    out.sort()
    merged = []
    for v in out:
        if merged and abs(v - merged[-1]) < merge:
            merged[-1] = min(merged[-1], v) if side > 0 else max(merged[-1], v)
        else:
            merged.append(v)
    return merged


def pivot_candidates(bars, side, k=2):
    """Swing points the market is still making (their right-hand bars have not all closed yet): drawn as unlit stakes."""
    out = []
    n = len(bars)
    for i in range(max(k, n - k - 1), n - 1):
        idx = 3 if side > 0 else 2
        v = bars[i][idx]
        left = all((v < bars[j][idx]) if side > 0 else (v > bars[j][idx]) for j in range(i - k, i))
        right = all((v < bars[j][idx]) if side > 0 else (v > bars[j][idx]) for j in range(i + 1, n))
        if left and right:
            out.append(v)
    return out


def terrain(bars, a, b, x0=TERRAIN_X0, x1=TERRAIN_X1, bins=96, profile=20, chasm_prices=None, extra_scorch=None, weathered=None):
    """The street's ground in x space: price profile of the last `profile` bars (hills where price dwelt), weathered runs (levels left
    more than `profile` minutes ago), scorch craters at big wicks, void chasms (price ranges skipped by gaps)."""
    if abs(b) < 1e-12:
        b = 1e-12
    last = bars[-profile:]
    n_last = float(profile)
    h = []
    for i in range(bins):
        xn = x0 + (x1 - x0) * (i + 0.5) / bins
        p = (xn - a) / b
        c = sum(1 for bar in last if bar[3] <= p <= bar[2])
        h.append(round(c / n_last, 3))
    if weathered is None:
        weathered = weathered_runs(bars, a, b, h, x0, x1, bins, profile)
    scorch = []
    for bar in last:
        rng = bar[2] - bar[3] or 1e-9
        if (bar[2] - max(bar[1], bar[4])) > 0.55 * rng and rng > 0.4:
            scorch.append(xp(a, b, bar[2]))
        if (min(bar[1], bar[4]) - bar[3]) > 0.55 * rng and rng > 0.4:
            scorch.append(xp(a, b, bar[3]))
    scorch += extra_scorch or []
    chasms = []
    for p0, p1 in (chasm_prices or []):
        xa, xb = sorted((xp(a, b, p0), xp(a, b, p1)))
        if xb >= x0 and xa <= x1:
            chasms.append([xa, xb])
    return {"x0": x0, "x1": x1, "h": h, "chasms": chasms, "scorch": [s for s in scorch if x0 <= s <= x1], "weathered": weathered}


def weathered_runs(bars, a, b, h, x0=TERRAIN_X0, x1=TERRAIN_X1, bins=96, profile=20):
    older = bars[-300:-profile]
    out, run = [], None
    for i in range(bins):
        xn = x0 + (x1 - x0) * (i + 0.5) / bins
        p = (xn - a) / b
        old = any(bar[3] <= p <= bar[2] for bar in older)
        if h[i] == 0 and old:
            run = run or [round(xn, 4), round(xn, 4)]
            run[1] = round(xn, 4)
        elif run:
            out.append(run)
            run = None
    if run:
        out.append(run)
    return out


PX_DP = 2           # the price grid's decimals (2 = gold cents; 5 = EUR/USD) - set per symbol by configure_price (Zee 2026-11-04)
TICK = 0.01


def configure_price(dp):
    global PX_DP, TICK
    PX_DP = max(0, min(8, int(dp)))
    TICK = round(10.0 ** -PX_DP, PX_DP)


def r2(p):
    return None if p is None else round(p + 0.0, PX_DP)


def r6(v):
    return None if v is None else round(v + 0.0, 6)


def floor_cent(p):
    m = 10 ** PX_DP
    return round(math.floor(p * m + 1e-6) / m, PX_DP)


def ceil_cent(p):
    m = 10 ** PX_DP
    return round(math.ceil(p * m - 1e-6) / m, PX_DP)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def utc_day(t):
    return time.strftime("%Y-%m-%d", time.gmtime(t))


def next_utc_midnight(t):
    return (math.floor(t / 86400.0) + 1) * 86400.0


_URL_RE = re.compile(r"wss?://\S+|https?://\S*primexbt\S*", re.I)


def scrub(s):
    """Never let a socket URL (it carries the session JWT) reach a snapshot, a log or the console."""
    if s is None:
        return None
    return _URL_RE.sub("<url>", str(s))[:300]


def sanitize(o):
    """JSON-safe copy: NaN/inf -> None (a NaN breaks JSON.parse in the browser)."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [sanitize(v) for v in o]
    return o


def _row_ts(x):
    v = _num(x.get("executed_ts"))
    if v is not None:
        return v
    raw = x.get("executedAt")
    v = _num(raw)
    if v is not None:
        return v / 1000.0 if v > 1e11 else v
    if isinstance(raw, str) and raw:
        try:
            s = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
            d = datetime.fromisoformat(s)
            if d.tzinfo is None:
                d = d.replace(tzinfo=UTC)
            return d.timestamp()
        except ValueError:
            return None
    return None


def _chrono(rows):
    """Report rows oldest first. report/orders2 answers newest first; sort by executed_ts / executedAt when we can read them."""
    rows = list(rows)
    ts = [_row_ts(x) for x in rows]
    if all(t is not None for t in ts):
        return [x for _, _, x in sorted(zip(ts, range(len(rows)), rows), key=lambda z: (z[0], -z[1]))]
    return list(reversed(rows))


def _num(v, default=None):
    try:
        if v is None:
            return default
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


# ----------------------------------------------------------------------------------------------------------------------------------
# the market clock: sessions, the bell, the real break / weekend schedule (zoneinfo handles DST)
def _parse_hm_tz(spec, default_tz="UTC"):
    parts = str(spec).split()
    hh, mm = parts[0].split(":")
    tzname = parts[1] if len(parts) > 1 else default_tz
    tz = UTC
    if ZoneInfo is not None and tzname != "UTC":
        try:
            tz = ZoneInfo(tzname)
        except Exception:  # noqa: BLE001
            tz = UTC
    return int(hh), int(mm), tz


def _hm_minutes(s):
    hh, mm = str(s).split(":")
    return int(hh) * 60 + int(mm)


class MarketClock:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lo = _parse_hm_tz(cfg["london_open"])
        self.ny = _parse_hm_tz(cfg["newyork_open"])
        self.bs = _parse_hm_tz(cfg["daily_break_start"])
        self.be = _parse_hm_tz(cfg["daily_break_end"])
        self.dead = [(_hm_minutes(a), _hm_minutes(b)) for a, b in cfg["dead_hours_utc"]]
        self.wk_close = int(cfg.get("weekend_close_day", 4))
        self.wk_open = int(cfg.get("weekend_open_day", 6))

    @staticmethod
    def _at(date_utc, hm_tz):
        hh, mm, tz = hm_tz
        return datetime(date_utc.year, date_utc.month, date_utc.day, hh, mm, tzinfo=tz).timestamp()

    def open_t(self, which, date_utc):
        return self._at(date_utc, self.lo if which == "london" else self.ny)

    def dead_window(self, t):
        """(start_ts, end_ts) of the dead-hours window containing t, else None."""
        m = (t % 86400) / 60.0
        day0 = math.floor(t / 86400.0) * 86400.0
        for s, e in self.dead:
            if s <= e:
                if s <= m < e:
                    return day0 + s * 60, day0 + e * 60
            else:                                   # wraps midnight
                if m >= s:
                    return day0 + s * 60, day0 + 86400 + e * 60
                if m < e:
                    return day0 - 86400 + s * 60, day0 + e * 60
        return None

    def session(self, t):
        """asia | london | newyork | dead (the clock only; 'closed' is decided by the engine from the schedule and the feed)."""
        if self.dead_window(t):
            return "dead"
        m = (t % 86400) / 60.0
        late = [e for s, e in self.dead if s <= e and e >= 12 * 60]
        if late and m >= max(late):
            return "asia"
        d = datetime.fromtimestamp(t, UTC).date()
        if t >= self.open_t("newyork", d):
            return "newyork"
        if t >= self.open_t("london", d):
            return "london"
        return "asia"

    def opens(self, t_from, t_to):
        out = []
        d = datetime.fromtimestamp(t_from, UTC).date() - timedelta(days=1)
        end = datetime.fromtimestamp(t_to, UTC).date() + timedelta(days=1)
        while d <= end:
            for which in ("london", "newyork"):
                ts = self.open_t(which, d)
                tz = (self.lo if which == "london" else self.ny)[2]
                if datetime.fromtimestamp(ts, tz).weekday() < 5 and t_from <= ts <= t_to:
                    out.append((ts, which))
            d += timedelta(days=1)
        out.sort()
        return out

    def bell(self, t):
        past = self.opens(t - 5 * 86400, t)
        fut = self.opens(t + 0.001, t + 6 * 86400)
        last = past[-1] if past else (None, None)
        return {"last_t": last[0], "session": last[1], "next_t": fut[0][0] if fut else None}

    # --- the real market schedule (gold: daily break 17:00-18:00 New York, weekend Fri 17:00 -> Sun 18:00 New York)
    def _local(self, t, hm_tz):
        return datetime.fromtimestamp(t, hm_tz[2])

    def is_weekend(self, t):
        lt = self._local(t, self.bs)
        m = lt.hour * 60 + lt.minute
        bs = self.bs[0] * 60 + self.bs[1]
        be = self.be[0] * 60 + self.be[1]
        wd = lt.weekday()
        if wd == self.wk_close and m >= bs:
            return True
        if self.wk_close < wd < self.wk_open:
            return True
        if wd == self.wk_open and m < be:
            return True
        return False

    def in_daily_break(self, t):
        lt = self._local(t, self.bs)
        m = lt.hour * 60 + lt.minute
        bs = self.bs[0] * 60 + self.bs[1]
        be = self.be[0] * 60 + self.be[1]
        return lt.weekday() < self.wk_close and bs <= m < be

    def scheduled_closed(self, t):
        return self.is_weekend(t) or self.in_daily_break(t)

    def next_break_start(self, t):
        """The next moment the market goes into its daily break or the weekend (Friday's break start)."""
        tz = self.bs[2]
        d = datetime.fromtimestamp(t, tz).date()
        for i in range(0, 9):
            dd = d + timedelta(days=i)
            if dd.weekday() <= self.wk_close:
                ts = datetime(dd.year, dd.month, dd.day, self.bs[0], self.bs[1], tzinfo=tz).timestamp()
                if ts > t:
                    return ts
        return t + 86400

    def reopen_after(self, t):
        """When a scheduled closure that contains t ends."""
        tz = self.be[2]
        d = datetime.fromtimestamp(t, tz).date()
        for i in range(0, 9):
            dd = d + timedelta(days=i)
            ts = datetime(dd.year, dd.month, dd.day, self.be[0], self.be[1], tzinfo=tz).timestamp()
            if ts > t and not self.scheduled_closed(ts + 1):
                return ts
        return None


# ----------------------------------------------------------------------------------------------------------------------------------
# PaperBroker - SimFeed's broker logic over another feed's quotes (wooden rounds, the Twin, the eject counterfactual). Same trading
# surface as Feed (CONTRACT.md section 4) plus on_quote() / open_at(). Never touches the network.
class PaperBroker:
    mode = "paper"
    can_trade = True

    def __init__(self, slippage_max=0.06, seed=7, clock=time.time, fee_per_oz=0.0, min_qty=0.01, step=0.01):
        self._lock = threading.RLock()
        self._rnd = random.Random(seed)
        self.slippage_max = float(slippage_max)
        self.fee_per_oz = float(fee_per_oz)
        self.min_qty, self.step = min_qty, step
        self.clock = clock
        self._quote = None
        self.pos = {}
        self.rows = []
        self.activity = []
        self._pid = itertools.count(91000001)
        self._oid = itertools.count(92000001)

    # -- helpers
    def _slip(self):
        if self.slippage_max <= 0:
            return 0.0
        return round(self._rnd.uniform(0, self.slippage_max), 2)

    def _act(self, title, body, t):
        self.activity.append({"t": t, "title": title, "body": body})
        del self.activity[:-50]

    def _row(self, typ, side, qty, price, pid, rpl, t, trigger=None):
        fee = round(self.fee_per_oz * qty, 6)
        row = {"id": next(self._oid), "type": typ, "status": "EXECUTED", "side": "BUY" if side > 0 else "SELL", "qty": qty,
               "executedPrice": price, "executedQty": qty, "rpl": round(rpl, 6), "fee": fee, "positionId": pid,
               "closeReason": "EXECUTION", "executedAt": t, "executed_ts": t, "triggerPrice": trigger}
        self.rows.append(row)
        return row

    def _close_fill(self, p, qty, price, typ, t):
        qty = round(min(qty, p["qty"]), 2)
        rpl = p["side"] * (price - p["open_price"]) * qty
        row = self._row(typ, -p["side"], qty, price, p["id"], rpl, t, trigger=p["sl"] if typ == "STOP_LOSS" else p["tp"] if typ == "TAKE_PROFIT" else None)
        p["qty"] = round(p["qty"] - qty, 2)
        word = {"STOP_LOSS": "Stop loss", "TAKE_PROFIT": "Take profit"}.get(typ)
        verb = "Sell" if p["side"] > 0 else "Buy"
        if word:
            self._act(f"{word} triggered", f"{p['id']}: {word} {verb.lower()} XAU/USD @ {price:.2f}", t)
            self._act(f"{word} filled", f"{verb} {qty:.2f} XAU/USD @ {price:.2f}", t)
        else:
            self._act("Market order filled", f"{verb} {qty:.2f} XAU/USD @ {price:.2f}", t)
        if p["qty"] < self.min_qty - 1e-9:
            self.pos.pop(p["id"], None)
        return row

    def _check(self, p, bid, ask, t):
        side = p["side"]
        px = bid if side > 0 else ask
        if p["sl"] is not None and ((side > 0 and px <= p["sl"]) or (side < 0 and px >= p["sl"])):
            return self._close_fill(p, p["qty"], px, "STOP_LOSS", t)
        if p["tp"] is not None and ((side > 0 and px >= p["tp"]) or (side < 0 and px <= p["tp"])):
            return self._close_fill(p, p["qty"], px, "TAKE_PROFIT", t)
        return None

    # -- the quote stream
    def on_quote(self, bid, ask, ts=None):
        """Feed one quote; returns the report rows of any SL/TP fills it triggered (a gap fills at the first price after it)."""
        with self._lock:
            t = self.clock() if ts is None else ts
            self._quote = {"bid": bid, "ask": ask, "ts": t}
            fired = []
            for p in list(self.pos.values()):
                row = self._check(p, bid, ask, t)
                if row:
                    fired.append(row)
            return fired

    # -- trading surface (Feed-compatible)
    def quote(self):
        with self._lock:
            q = self._quote
            if not q:
                return None
            return {"bid": q["bid"], "ask": q["ask"], "mid": round((q["bid"] + q["ask"]) / 2.0, PX_DP + 1), "spread": round(q["ask"] - q["bid"], PX_DP),
                    "ts": q["ts"]}

    def place(self, side, qty, sl=None, tp=None, timeout=5.0, fill_price=None):
        if fill_price is not None:
            pid = self.open_at(side, qty, fill_price, sl, tp)
            return {"ok": True, "error": None, "rtt_ms": 0.0, "position_id": pid, "fill_price": r2(fill_price), "sl": r2(sl), "tp": r2(tp)}
        with self._lock:
            if not self._quote:
                return {"ok": False, "error": "NO_QUOTE", "rtt_ms": 0.0}
            qty = round(float(qty), 2)
            if qty < self.min_qty - 1e-9 or side not in (1, -1):
                return {"ok": False, "error": "BAD_ORDER", "rtt_ms": 0.0}
            t = self.clock()
            s = self._slip()
            price = round(self._quote["ask"] + s if side > 0 else self._quote["bid"] - s, PX_DP)
            pid = next(self._pid)
            p = {"id": pid, "side": side, "qty": qty, "open_price": price, "sl": r2(sl), "tp": r2(tp), "open_time": t,
                 "sl_order": next(self._oid) if sl is not None else None, "tp_order": next(self._oid) if tp is not None else None}
            self.pos[pid] = p
            row = self._row("MARKET", side, qty, price, pid, 0.0, t)
            self._act("Market order filled", f"{'Buy' if side > 0 else 'Sell'} {qty:.2f} XAU/USD @ {price:.2f}", t)
            self._check(p, self._quote["bid"], self._quote["ask"], t)          # an already-crossed TP/SL fills at once (PX does this)
            return {"ok": True, "error": None, "rtt_ms": 0.0, "order_id": row["id"], "position_id": pid, "fill_price": price,
                    "sl": p["sl"], "tp": p["tp"]}

    def open_at(self, side, qty, price, sl, tp, t=None):
        """A shadow position at a GIVEN price (the Twin shares the player's fill; the counterfactual continues the closed one)."""
        with self._lock:
            t = self.clock() if t is None else t
            pid = next(self._pid)
            p = {"id": pid, "side": side, "qty": round(qty, 2), "open_price": price, "sl": r2(sl), "tp": r2(tp), "open_time": t,
                 "sl_order": None, "tp_order": None}
            self.pos[pid] = p
            self._row("MARKET", side, p["qty"], price, pid, 0.0, t)
            if self._quote:
                self._check(p, self._quote["bid"], self._quote["ask"], t)
            return pid

    def set_protective(self, position_id, kind, price, timeout=5.0):
        with self._lock:
            p = self.pos.get(position_id)
            if not p:
                return {"ok": False, "error": "POSITION_NOT_FOUND", "rtt_ms": 0.0}
            key = "sl" if kind == "STOP_LOSS" else "tp"
            p[key] = r2(price)
            t = self.clock()
            self._act("Stop loss replaced" if key == "sl" else "Take profit replaced", f"{position_id}: {kind} @ {price:.2f}", t)
            if self._quote:
                self._check(p, self._quote["bid"], self._quote["ask"], t)
            return {"ok": True, "error": None, "rtt_ms": 0.0}

    def check_protective(self, position_id, price, timeout=3.0):
        with self._lock:
            p = self.pos.get(position_id)
            if not p:
                return {"ok": False, "error": "POSITION_NOT_FOUND", "rtt_ms": 0.0}
            return {"ok": True, "error": None, "rtt_ms": 0.0, "resolution": "OK",
                    "profitLoss": round(p["side"] * (price - p["open_price"]) * p["qty"], 6)}

    def close(self, position_id, qty=None, timeout=5.0):
        with self._lock:
            p = self.pos.get(position_id)
            if not p:
                return {"ok": False, "error": "POSITION_NOT_FOUND", "rtt_ms": 0.0}
            if not self._quote:
                return {"ok": False, "error": "NO_QUOTE", "rtt_ms": 0.0}
            qty = round(min(float(qty if qty is not None else p["qty"]), p["qty"]), 2)
            if qty < self.min_qty - 1e-9 or (p["qty"] - qty > 1e-9 and p["qty"] - qty < self.min_qty - 1e-9):
                return {"ok": False, "error": "BAD_QTY", "rtt_ms": 0.0}
            s = self._slip()
            price = round(self._quote["bid"] - s if p["side"] > 0 else self._quote["ask"] + s, PX_DP)
            row = self._close_fill(p, qty, price, "MARKET", self.clock())
            return {"ok": True, "error": None, "rtt_ms": 0.0, "fill_price": price, "rpl": row["rpl"], "order_id": row["id"]}

    def orders_report(self, since_ts=0.0, timeout=5.0):
        with self._lock:
            return [dict(r) for r in reversed(self.rows) if (r["executedAt"] or 0) >= since_ts - 1e-6]

    def positions(self):
        with self._lock:
            q = self._quote
            out = []
            for p in self.pos.values():
                mark = (q["bid"] if p["side"] > 0 else q["ask"]) if q else p["open_price"]
                out.append({"id": p["id"], "side": p["side"], "qty": p["qty"], "open_price": p["open_price"], "mark": mark,
                            "upl": round(p["side"] * (mark - p["open_price"]) * p["qty"], 6), "sl": p["sl"], "tp": p["tp"],
                            "sl_order": p["sl_order"], "tp_order": p["tp_order"], "open_time": p["open_time"]})
            return out

    def has(self, position_id):
        with self._lock:
            return position_id in self.pos

    def position(self, position_id):
        for p in self.positions():
            if p["id"] == position_id:
                return p
        return None

    def result(self, position_id):
        with self._lock:
            rows = [r for r in self.rows if r["positionId"] == position_id and r["status"] == "EXECUTED"]
            if not rows:
                return None
            exits = rows[1:]
            rpl = round(sum(r["rpl"] for r in rows), 6)
            fee = round(sum(r["fee"] for r in rows), 6)
            last = exits[-1] if exits else None
            return {"closed": position_id not in self.pos, "rpl": rpl, "fee": fee, "net": round(rpl - fee, 6),
                    "open_price": rows[0]["executedPrice"], "exit_price": last["executedPrice"] if last else None,
                    "exit_type": last["type"] if last else None, "exit_ts": last["executed_ts"] if last else None}

    def state(self):
        return {"ok": self._quote is not None, "quote": self.quote(), "positions": self.positions(), "activity": list(self.activity)}


# ----------------------------------------------------------------------------------------------------------------------------------
# GapBook - price ranges skipped by gaps (>= gap_min) between consecutive quotes (or between consecutive history bars), minus whatever
# printed inside them within the profile window. These are the Void Chasms.
class GapBook:
    CELL = 0.01

    def __init__(self, gap_min=0.25, window_s=1200.0, min_run=None):
        self.CELL = TICK                                 # one cell per price tick of the active symbol
        min_run = 5 * TICK if min_run is None else min_run
        self.gap_min = gap_min
        self.window = window_s
        self.min_run = min_run
        self.cover = {}
        self.gaps = []
        self.last = None
        self._pruned = 0.0

    def _c(self, p):
        return int(round(p / self.CELL))

    def _cover(self, lo, hi, t):
        for c in range(self._c(lo), self._c(hi) + 1):
            if self.cover.get(c, -1e18) < t:
                self.cover[c] = t

    def tick(self, px, t):
        if px is None:
            return
        if self.last is not None:
            lo, hi = sorted((self.last, px))
            if hi - lo >= self.gap_min - 1e-9:
                self.gaps.append([lo, hi, t])
                self._cover(px, px, t)
            else:
                self._cover(lo, hi, t)
        else:
            self._cover(px, px, t)
        self.last = px
        if t - self._pruned > 60:
            self.prune(t)

    def history(self, bars, until_t=None):
        """Seed from history bars (before our own ticks): each bar's range printed; a jump between bars is a gap."""
        prev = None
        for bar in bars:
            t = bar[0] + 60
            if until_t is not None and bar[0] >= until_t:
                break
            if prev is not None:
                lo, hi = sorted((prev[4], bar[1]))
                if hi - lo >= self.gap_min - 1e-9:
                    self.gaps.append([lo, hi, bar[0]])
            self._cover(bar[3], bar[2], t)
            prev = bar
        if prev is not None and self.last is None:
            self.last = prev[4]

    def prune(self, now):
        self._pruned = now
        cut = now - self.window
        self.gaps = [g for g in self.gaps if g[2] >= cut]
        if len(self.cover) > 4000:
            self.cover = {c: t for c, t in self.cover.items() if t >= cut}

    def chasms(self, now):
        cut = now - self.window
        runs = []
        for lo, hi, t in self.gaps:
            if t < cut:
                continue
            c0, c1 = self._c(lo) + 1, self._c(hi) - 1
            start = None
            for c in range(c0, c1 + 2):
                void = c <= c1 and self.cover.get(c, -1e18) < cut
                if void and start is None:
                    start = c
                elif not void and start is not None:
                    a, b = (start - 1) * self.CELL, c * self.CELL     # from the last printed cell to the next printed cell
                    if b - a >= self.min_run + 2 * self.CELL - 1e-9:
                        runs.append([round(a, PX_DP), round(b, PX_DP)])
                    start = None
        runs.sort()
        merged = []
        for a, b in runs:
            if merged and a < merged[-1][1] - 1e-9:          # overlapping runs merge; a printed price between two keeps them apart
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        return merged

    def inside(self, p, chasms):
        return any(a < p < b for a, b in chasms)


# ----------------------------------------------------------------------------------------------------------------------------------
# one round (one coin's life). Plain attributes; every write happens under Engine.lock.
class Round:
    def __init__(self, rid, mode, kind, side, qty0, stop_dist, target, risk_usd):
        self.id, self.mode, self.kind, self.side = rid, mode, kind, side
        self.qty0 = self.qty = qty0
        self.coin_oz, self.stop_dist, self.target, self.risk_usd = qty0, stop_dist, target, risk_usd
        self.shot_t = self.opened_t = self.closed_t = None
        self.patience_s = 0.0
        self.session = self.weather = None
        self.storm_seen = self.night_seen = False
        self.quote_at_send = None
        self.entry_ref = self.spread_entry = None
        self.fill = self.sl0 = self.tp0 = self.sl = self.tp = None
        self.position_id = self.order_id = None
        self.banked_usd = 0.0
        self.walls, self.haggles, self.machete_done, self.golden = [], 0, False, None
        self.anvil_kind, self.anvil_moves, self.anvil_before_haggle = "vault", 0, False
        self.rat, self.instructions, self.fills, self.path, self.notes, self.report_rows = [], [], [], [], [], []
        self.qsum = {"n": 0, "first": None, "last": None, "high_bid": None, "low_bid": None, "spread_min": None, "spread_max": None,
                     "spread_sum": 0.0}
        self.pending = None
        self.anvil_pending = False
        self.last_refusal = None
        self.close_intent = self.close_ref = None
        self.kill_requested = False
        self.settling = self.settle_queued = False
        self.settle_next_t = self.settle_started = None
        self.seen = False
        self.vanish_since = None
        self.sync_hold_until = 0.0
        self.twin = None
        self.twin_invited = False
        self.ghosts = []
        self.slippage_entry = self.slippage_partial = 0.0
        self.final = None
        self.last_mark = None
        self.last_path_t = None
        self.stakes_lit = None
        self.estimated = False
        self.settlement = None
        self.would_have_usd = None
        self.session_retry_t = 0.0      # a refused session close is retried at most every 5 s (never a 10 Hz hammer)
        self.blind = False              # the book never showed our position and the report has no close: keep the round open
        self.unknown = None             # an order whose outcome is not known (it may have filled): the round stays in "sending"
        self.kill_retry_t = 0.0         # a refused kill close is re-sent every kill_retry_s until the position is gone
        self.close_done = False         # a close call of ours succeeded (the book may lag behind; the deal history will show it)
        self.settle_fail_n = 0          # failed deal-history reads in a row (they never count toward a timeout)
        self.settle_waiting_logged = False
        self.sl_missing = self.tp_missing = False   # the broker's book has shown no stop / no target for our position (> 1 s)
        self.sl_missing_since = self.tp_missing_since = None
        self.prot_next_t = 0.0
        self.prot_fail_n = 0
        self.fill_checked = False       # the fill was compared once with the book's openPrice
        self.machete_hold_until = 0.0   # an uncertain machete: no second cut until the book shows what happened

    RESTORE_KEYS = ("id", "mode", "kind", "side", "qty0", "qty", "stop_dist", "target", "risk_usd", "shot_t", "opened_t", "patience_s",
                    "session", "weather", "quote_at_send", "entry_ref", "spread_entry", "fill", "sl0", "tp0", "sl", "tp", "position_id",
                    "order_id", "banked_usd", "walls", "haggles", "machete_done", "golden", "anvil_kind", "anvil_moves", "slippage_entry",
                    "slippage_partial", "twin_invited", "rat", "instructions", "fills", "path", "kill_requested", "close_intent",
                    "close_done", "unknown")

    def to_restore(self):
        d = {k: getattr(self, k) for k in self.RESTORE_KEYS}
        if d.get("unknown"):
            d["unknown"] = {k: v for k, v in d["unknown"].items() if k not in ("token", "queued")}
        return d

    @classmethod
    def from_restore(cls, d):
        r = cls(d["id"], d["mode"], d["kind"], d["side"], d["qty0"], d["stop_dist"], d["target"], d["risk_usd"])
        for k in cls.RESTORE_KEYS:
            if k in d:
                setattr(r, k, d[k])
        return r


ACTIONS = ("fund", "unfund", "flip", "set_target", "invite_twin", "shoot", "anvil_next", "wall", "haggle", "machete", "merchant",
           "eject", "ack", "kill")
SETTINGS_PERSIST = ("stop_dist", "sound", "plain_line", "eject_words", "side", "twin_invited")   # (no "coin_oz": a coin is config coin_oz, x the men shot - Zee 2026-11-04)   # (no "target": always target_default - Zee 2026-11-04)


class Engine:
    def __init__(self, feed, cfg=None, root=None, clock=None, threaded=True, seed=7, real_hours=None, verbose=True, cfg_path=None):
        self.feed = feed
        self.cfg = load_config(cfg_path, overrides=cfg or {})
        configure_price(int(self.cfg.get("price_dp", 2)))
        self.root = root or HERE
        self.rounds_dir = os.path.join(self.root, "rounds")
        self.state_dir = os.path.join(self.root, "state")
        self.clock = clock or time.time
        self.threaded = threaded
        self.verbose = verbose
        self.mode = getattr(feed, "mode", "sim") or "sim"
        self.lock = threading.RLock()
        self.mc = MarketClock(self.cfg)
        rh = self.cfg.get("sim_real_hours") if real_hours is None else real_hours
        self.schedule_active = self.mode == "live" or bool(rh)
        self.started_t = self.clock()
        c = self.cfg
        # live_enabled is never restored from disk and never defaults on in live mode: the typed CONFIRM is required every session
        self.settings = {"coin_oz": float(c["coin_oz"]), "stop_dist": float(c["stop_dist"]), "target": float(c["target_default"]),
                         "side": 1, "live_enabled": bool(c.get("live_enabled", False)) and self.mode != "live", "twin_invited": False,
                         "sound": True, "plain_line": False, "eject_words": ""}     # plain words only on request (L): REQUIREMENTS 12.9
        self._load_settings()
        try:                                                      # Zee 2026-11-06: "this whole sign thing is taking away our chances ... the fact that
            with open(os.path.join(self.state_dir, "live_signed.json"), encoding="utf-8") as f:   # i'm instructing you to trade means i am giving my consent"
                if self.mode == "live" and json.load(f).get("day") == utc_day(self.clock()):
                    self.settings["live_enabled"] = True          # today's CONFIRM still stands (the kill switch clears it)
        except (OSError, ValueError):
            pass
        self.phase = "lobby"
        self.aim = None
        self.round = None
        self.settlement = None
        self.pre_instr = []
        self._ev = collections.deque(maxlen=1000)
        self._seq = 0
        self._ev_cv = threading.Condition()
        self._nonces = collections.OrderedDict()
        self._jobs = collections.deque()
        self._job_cv = threading.Condition()
        self.book_impl = "engine.PaperBroker"
        self.paper = self._make_book(c["paper_slippage_max"], seed, "ALLEY", "WOODEN")       # wooden rounds (the Alley)
        self.shadow = self._make_book(0.0, seed + 1, "SHADOW", "SHADOW")                    # the Twin + the eject counterfactual
        self.shadows = []
        self.fs = {}
        self._hist = collections.deque()
        self._last_tick_ts = None
        self._last_quote_seen = None
        self._tick_seen_n = 0
        self.ticks_per_s = 0.0
        self._first_ok_t = None
        self.gaps = GapBook(c["gap_min"], window_s=c["profile_bars"] * 60.0)
        self._gaps_seeded = False
        self.tilt_ema = 0.0
        self.trends = {}                 # Zee 2026-11-04: the 5- and 15-minute trends shown in the two binoculars
        self.hints = {}                  # Zee 2026-11-04: volume hints (friction trench / fault lines / vortex + polished earth)
        self.diamond = dia_mod.Diamond(unit=float(self.cfg.get("dia_unit", 1.0)))   # Zee 2026-11-04: his UHV Diamond as a hint (diamond.py)
        self.dia = {}
        self.u97, self._u97_used = None, set()   # Zee 2026-11-05: the Turtle TV UHV 97.7% setting's entries (u97_*)
        self.angel = None                        # Zee 2026-11-06: the risk manager's verdict on the last breakout {mode: bless|block, t, side, why}
        self.risk = {"level": 1, "why": "warming up"}   # Zee 2026-11-06: the risk weather - 0 sun (zero risk) .. 3 storm
        self._tickmin = collections.Counter()   # quotes per minute: the Diamond's volume when a bar carries none
        self._hint_ev = {}
        self.tilt_raw = 0.0
        self._tilt_t = None
        self.weather, self.vol, self.vol_metric = "calm", 0.0, 0.0
        self.lightning_until = 0.0
        self._last_strike = 0.0
        self._bell_cache = (None, None)
        self._bell_t = self.mc.bell(self.started_t)["last_t"]
        self._freeze = False
        self._weathered_cache = (None, None)
        self._preview_lit = None
        self._replay_lap = None
        self._stakes_quiet_until = 0.0
        self._lim_cache = (None, None)
        self.summaries = []
        self._sum_version = 0
        self._tally_cache = (None, None)
        self._load_rounds()
        self.discipline = self._load_json("discipline.json", {}) or {}
        self.killed = self._load_json("day.json", {}) or {}
        self._dsb = {}
        self._disc_t = 0.0
        self._snap_cache = (0.0, None)
        self._running = False
        self._threads = []
        self._wake = threading.Event()
        self._restore = self._load_json(f"open_round_{self.mode}.json", None)
        self._log(f"engine ready: mode={self.mode} root={self.root} rounds={len(self.summaries)} "
                  f"schedule={'real' if self.schedule_active else 'off'}")

    # ------------------------------------------------------------------------------------------------------------------ utilities
    def _make_book(self, slippage, seed, acct, typ):
        """A shadow broker over the current feed's quotes: feeds.ShadowBroker when it imports (B-FEEDS), else engine.PaperBroker.
        Either way it never reaches the network."""
        c = self.cfg
        if c.get("shadow_broker", "auto") != "engine":
            try:
                import feeds  # noqa: WPS433 - lazy: written in parallel
                book = feeds.ShadowBroker(balance=1e6, slippage_max=slippage, seed=seed, account_id=acct, account_type=typ,
                                          min_qty=c["min_qty"], qty_step=c["qty_step"], clock=self.clock,
                                          stop_slippage=slippage > 0)
                for m in ("on_quote", "place", "set_protective", "close", "orders_report", "positions", "position", "result", "quote"):
                    if not callable(getattr(book, m, None)):
                        raise AttributeError(m)
                self.book_impl = "feeds.ShadowBroker"
                return book
            except Exception as e:  # noqa: BLE001
                self._log(f"feeds.ShadowBroker unavailable ({type(e).__name__}: {e}); using engine.PaperBroker")
        return PaperBroker(slippage_max=slippage, seed=seed, clock=self.clock, fee_per_oz=c["paper_fee_per_oz"], min_qty=c["min_qty"],
                           step=c["qty_step"])

    @staticmethod
    def _has(book, pid):
        return pid is not None and book.position(pid) is not None

    def _log(self, msg):
        if self.verbose:
            print(f"[engine {time.strftime('%H:%M:%S')}] {scrub(msg)}", flush=True)

    def _load_json(self, name, default):
        try:
            with open(os.path.join(self.state_dir, name), encoding="utf-8") as f:
                return json.load(f)
        except Exception:  # noqa: BLE001
            return default

    def _save_json(self, name, data):
        try:
            os.makedirs(self.state_dir, exist_ok=True)
            path = os.path.join(self.state_dir, name)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(sanitize(data), f, indent=1)
            os.replace(tmp, path)
        except Exception as e:  # noqa: BLE001
            self._log(f"could not save state/{name}: {e}")

    def _delete_state(self, name):
        try:
            os.remove(os.path.join(self.state_dir, name))
        except OSError:
            pass

    def _load_settings(self):
        d = self._load_json("settings.json", {}) or {}
        c = self.cfg
        for k in SETTINGS_PERSIST:
            if k not in d:
                continue
            v = d[k]
            if k == "coin_oz":
                v = _num(v)
                if v is None or not (c["min_qty"] - 1e-9 <= v <= c["coin_max_oz"] + 1e-9):
                    continue
                v = round(round(v / c["qty_step"]) * c["qty_step"], 2)
            elif k == "stop_dist":
                v = _num(v)
                if v is None or not any(abs(v - s) < 1e-9 for s in c["stop_choices"]):
                    continue
            elif k == "target":
                v = _num(v)
                if v is None or not any(abs(v - s) < 1e-9 for s in c["targets"]):
                    continue
            elif k == "side":
                v = v if v in (1, -1) else 1
            elif k in ("sound", "plain_line", "twin_invited"):
                v = bool(v)
            elif k == "eject_words":
                v = str(v)[:60]
            self.settings[k] = v

    def _save_settings(self):
        self._save_json("settings.json", {k: self.settings[k] for k in SETTINGS_PERSIST})

    def _emit(self, ev):
        with self._ev_cv:
            self._seq += 1
            self._ev.append((self._seq, sanitize(ev)))
            self._ev_cv.notify_all()

    def events_since(self, seq, timeout=0.0):
        """SSE fan-out: events after `seq` (waits up to timeout for one). Returns (events, last_seq)."""
        with self._ev_cv:
            if self._seq <= seq and timeout > 0:
                self._ev_cv.wait(timeout)
            return [e for s, e in self._ev if s > seq], self._seq

    @property
    def seq(self):
        with self._ev_cv:
            return self._seq

    # ------------------------------------------------------------------------------------------------------------------ threads
    def start(self):
        if self._running:
            return
        self._running = True
        try:
            self.feed.subscribe(self._on_feed_event)
        except Exception as e:  # noqa: BLE001
            self._log(f"feed.subscribe failed: {e}")
        try:
            self.feed.start()
        except Exception as e:  # noqa: BLE001
            self._log(f"feed.start failed: {e}")
        if self.threaded:
            for name, fn in (("engine-tick", self._tick_loop), ("engine-broker", self._worker_loop)):
                th = threading.Thread(target=fn, name=name, daemon=True)
                th.start()
                self._threads.append(th)

    def stop(self):
        self._running = False
        self._wake.set()
        with self._job_cv:
            self._job_cv.notify_all()
        try:
            self.feed.stop()
        except Exception:  # noqa: BLE001
            pass

    def _on_feed_event(self, ev):
        try:
            self._wake.set()
        except Exception:  # noqa: BLE001
            pass

    def _tick_loop(self):
        last = 0.0
        while self._running:
            self._wake.wait(0.1)
            self._wake.clear()
            if not self._running:
                break
            dt = time.monotonic() - last
            if dt < 0.03:
                time.sleep(0.03 - dt)
            last = time.monotonic()
            try:
                self.step()
            except Exception:  # noqa: BLE001
                self._log("step error: " + traceback.format_exc(limit=6))

    def _enqueue(self, name, fn, *args, front=False):
        with self._job_cv:
            (self._jobs.appendleft if front else self._jobs.append)((name, fn, args))
            self._job_cv.notify_all()

    def _run_job(self, job):
        name, fn, args = job
        try:
            fn(*args)
        except Exception:  # noqa: BLE001
            self._log(f"job {name} crashed: " + traceback.format_exc(limit=8))
            with self.lock:
                r = self.round
                if r is not None and r.pending and r.pending.get("action") == name:
                    r.pending = None
                    r.anvil_pending = False
                if r is not None and name == "settle":
                    r.settle_queued = False
                    r.settle_next_t = self.clock() + 1.0
                if r is not None and name == "resolve" and r.unknown is not None:
                    r.unknown["queued"] = False
                    r.unknown["next_t"] = self.clock() + 2.0
                if r is not None and name == "protect" and r.pending and r.pending.get("action") == "protect":
                    r.pending = None
                if name == "shoot" and self.phase == "sending" and r is not None and r.fill is None and r.unknown is None:
                    sent = None
                    for ins in reversed(r.instructions or []):
                        if ins.get("action") == "shoot" and isinstance(ins.get("broker"), dict):
                            sent = ins["broker"].get("sent")
                            break
                    if r.kind == "live" and sent:          # the order left before the crash: it may have filled - find it
                        now = self.clock()
                        r.unknown = {"since": now, "t_send": now - 1.0, "token": None, "before": [], "sl": sent.get("sl"),
                                     "tp": sent.get("tp"), "order_id": None, "accepted": False, "error": "crash", "q": sent.get("quote"),
                                     "entry_ref": None, "next_t": now, "queued": False, "tries": 0, "nonce": None}
                        r.pending = {"action": "resolve", "since": now}
                    else:
                        self.phase = "aiming" if self.aim else "lobby"
                        self.round = None

    def _worker_loop(self):
        while self._running:
            with self._job_cv:
                while self._running and not self._jobs:
                    self._job_cv.wait(0.5)
                if not self._running:
                    return
                job = self._jobs.popleft()
            self._run_job(job)

    def pump(self, max_jobs=200):
        """Tests (threaded=False): run the queued broker jobs synchronously."""
        n = 0
        while n < max_jobs:
            with self._job_cv:
                if not self._jobs:
                    break
                job = self._jobs.popleft()
            self._run_job(job)
            n += 1
        return n

    def settle_all(self, now=None, rounds=6):
        """Tests: alternate step() and pump() until nothing is queued."""
        for _ in range(rounds):
            self.step(now)
            if not self.pump():
                break

    # ------------------------------------------------------------------------------------------------------------------ market input
    def step(self, now=None):
        now = self.clock() if now is None else now
        try:
            fs = self.feed.state() or {}
        except Exception as e:  # noqa: BLE001
            fs = {"ok": False, "reason": f"feed error: {type(e).__name__}"}
        with self.lock:
            self.fs = fs
            self._ingest(fs, now)
            self._update_market(fs, now)
            self._check_bell(now)
            self._check_freeze(fs, now)
            self._maybe_restore(fs, now)
            self._manage_round(fs, now)
            self._manage_shadows(now)
            self._discipline_watch(now)

    def _q(self, fs=None):
        fs = self.fs if fs is None else fs
        q = fs.get("quote") if fs else None
        if not q:
            return None
        bid, ask = _num(q.get("bid")), _num(q.get("ask"))
        if bid is None or ask is None:
            return None
        return {"bid": bid, "ask": ask, "ts": _num(q.get("ts"))}

    def _quote_age(self, now):
        return None if self._last_quote_seen is None else max(0.0, now - self._last_quote_seen)

    def _ingest(self, fs, now):
        lap = fs.get("replay_lap")
        if lap is not None:
            if self._replay_lap is not None and lap != self._replay_lap:
                self._on_replay_lap(lap, now)
                # the old lap's last quotes often arrive in the same step as the new lap's first: only the new lap counts
                lt = _num(fs.get("replay_lap_t"))
                if lt is not None:
                    self._last_tick_ts = max(self._last_tick_ts or lt, lt) - 1e-6
            self._replay_lap = lap
        last = self._last_tick_ts
        new = []
        for tk in fs.get("ticks") or []:
            try:
                ts, bid, ask = float(tk[0]), float(tk[1]), float(tk[2])
            except (TypeError, ValueError, IndexError):
                continue
            if last is None or ts > last + 1e-9:
                new.append((ts, bid, ask))
        q = self._q(fs)
        if q is not None:
            qts = q["ts"] if q["ts"] is not None else now
            if (last is None or qts > last + 1e-9) and not any(abs(x[0] - qts) < 1e-9 for x in new):
                new.append((qts, q["bid"], q["ask"]))
        if not new:
            return
        new.sort(key=lambda x: x[0])
        if not self._gaps_seeded:
            self._gaps_seeded = True
            first_t = new[0][0]
            bars = fs.get("bars") or []
            self.gaps.history([b for b in bars if b[0] + 60 <= first_t + 1e-6])
        r = self.round
        for ts, bid, ask in new:
            self._last_tick_ts = ts
            self._tick_seen_n += 1
            tt = ts if abs(now - ts) < 600 else now
            self._hist.append((tt, bid, ask, (bid + ask) / 2.0))
            self._tickmin[int(tt // 60) * 60] += 1
            self._u97_check(tt, bid, ask, fs)
            self.gaps.tick(bid, tt)
            self.paper.on_quote(bid, ask, tt)
            self.shadow.on_quote(bid, ask, tt)
            if r is not None and r.fill is not None and r.final is None:
                s = r.qsum
                sp = round(ask - bid, 4)
                s["n"] += 1
                s["first"] = s["first"] or {"bid": bid, "ask": ask, "ts": tt}
                s["last"] = {"bid": bid, "ask": ask, "ts": tt}
                s["high_bid"] = bid if s["high_bid"] is None else max(s["high_bid"], bid)
                s["low_bid"] = bid if s["low_bid"] is None else min(s["low_bid"], bid)
                s["spread_min"] = sp if s["spread_min"] is None else min(s["spread_min"], sp)
                s["spread_max"] = sp if s["spread_max"] is None else max(s["spread_max"], sp)
                s["spread_sum"] += sp
        if (r is not None and r.kind == "wooden" and self.phase == "open" and r.position_id is not None and not r.settling and
                not self._has(self.paper, r.position_id)):
            self._begin_settle(r, now, immediate=True)
        self._last_quote_seen = now
        cut = now - 1500
        while self._hist and self._hist[0][0] < cut:
            self._hist.popleft()

    def _on_replay_lap(self, lap, now):
        """The looping recording started again: its first price is not where its last one ended (the seam is not a market move).
        Like the real session close, the Merchant takes an open wooden coin at the lap's last quote (the shadow book has not seen the
        new lap yet, so the seam is never a fill, a gap, a barrel or a lightning strike), the shadows stop, and the price memory that
        draws chasms, tilt and stakes starts over."""
        c = self.cfg
        r = self.round
        self._log(f"replay lap {lap}: the recording starts again - the street's memory is reset")
        if (r is not None and r.kind == "wooden" and r.fill is not None and r.final is None and r.position_id is not None and
                not r.settling and self._has(self.paper, r.position_id)):
            q = self.paper.quote()
            ref = self._mark(r.side, q) if q else None
            res = self.paper.close(r.position_id, r.qty)
            if res.get("ok"):
                r.close_intent = r.close_intent or "session"
                r.close_ref = ref
                r.fills.append({"t": now, "what": r.close_intent, "qty": r.qty, "price": _num(res.get("fill_price")), "quote_ref": ref,
                                "rtt_ms": res.get("rtt_ms")})
                r.notes.append({"t": now, "note": "the replay's recording ended: closed at its last quote before it started again"})
                self._begin_settle(r, now, immediate=True)
        for sh in self.shadows:
            if sh["state"] == "running" and self._has(self.shadow, sh["pid"]):
                self.shadow.close(sh["pid"], sh["qty"])
                self._shadow_finish(sh, now, expired=True)
        self.shadows = [sh for sh in self.shadows if sh["state"] == "running"]
        self.gaps = GapBook(c["gap_min"], window_s=c["profile_bars"] * 60.0)
        self._gaps_seeded = True                         # only the new lap's own prints count (the old lap's bars end elsewhere)
        self._stakes_quiet_until = now + 5.0             # the recording's history bars arrive again: no burst of "new" stakes
        self._hist.clear()
        self.diamond.reset()
        self.dia = {}
        self._tickmin.clear()
        self.tilt_ema = self.tilt_raw = 0.0
        self._weathered_cache = (None, None)
        self._last_strike = now
        self._preview_lit = None
        if r is not None:
            r.stakes_lit = None

    def _delta_mid(self, now, win):
        h = self._hist
        if len(h) < 2:
            return 0.0
        mid_now = h[-1][3]
        then = None
        for i in range(len(h) - 1, -1, -1):
            if h[i][0] <= now - win:
                then = h[i][3]
                break
        if then is None:
            then = h[0][3]
        return mid_now - then

    def _news_events(self):
        out = []
        for n in (self.fs.get("news") or []):
            if not isinstance(n, dict):
                continue
            t = _num(n.get("t"))
            if t is None:
                continue
            if t > 1e11:
                t /= 1000.0
            out.append({"t": t, "title": scrub(n.get("title") or "news")[:80], "impact": str(n.get("impact", "")).lower()})
        out.sort(key=lambda e: e["t"])
        return out

    def _news_window(self, now):
        win = float(self.cfg["news_window_min"]) * 60.0
        imps = [str(i).lower() for i in self.cfg["news_impacts"]]
        until = None
        for n in self._news_events():
            if n["impact"] in imps and abs(now - n["t"]) <= win:
                until = max(until or 0, n["t"] + win)
        return until

    def _dia_vol(self, b):
        """A bar's volume for the Diamond: the feed's own (PXTrader bars carry tick volume) or, when it reports none, our count of quotes."""
        v = b[5] if len(b) > 5 else 0
        if v and v > 0:
            return v
        n = self._tickmin.get(int(b[0]))
        return n if n else None

    # Zee 2026-11-05: "we modify it to take the setups detected by the 97.7 winrate setting: we take an entry when our python tester would've
    # taken an entry" (Turtle TV UHV save 2026-11-05 05-45-38: instant entry, stop beyond the retracement + 19 pips, take profit 0.1 pip, BUY box
    # 4 / SELL box 2 unticked). The signal is a hint: the diamond + chime at the breaking tick; nothing trades until Zee fires (his choice). A
    # round fired on it (same side, within u97_life_s) takes the setting's own stop and target.
    U97 = {"u97_on": True, "u97_beyond_pips": 19.0, "u97_tp_pips": 0.1, "u97_pip": 0.0001, "u97_life_s": 40.0, "u97_near_pips": 1.5, "u97_max_stop_pips": 2.5,
           "u97_rm": 2, "u97_safe_humps_min": 2, "u97_safe_humps_max": 3, "u97_safe_er_min": 0.30, "u97_safe_er_max": 0.45, "u97_er_bars": 16,
           "u97_max_spread_pips": 1.0, "u97_angel_s": 40.0, "u97_sellsup_pips": 2.0, "u97_sellsup_piv": 10, "u97_wall_pips": 1.0, "u97_wall_touches": 1, "u97_wall_bars": 60, "u97_fri_cut_ny": 10.0, "u97_range_look": 7,
           "u97_bands_b": "111101111111111111111", "u97_bands_s": "110111111111111111111"}

    def _u97(self, k):
        return self.cfg.get(k, self.U97[k])

    def _u97_eur(self):
        return bool(self._u97("u97_on")) and abs(float(self.cfg.get("dia_unit", 1.0)) - 0.00012) <= 1e-9   # EUR/USD only (found on PrimeXBT EUR/USD)

    def _u97_check(self, tt, bid, ask, fs):
        """the first quote whose bid crosses the waiting UHV level in the minute it waits for (Turtle TV UHV's instant entry), if the minute
        so far is quieter than the UHV; then the range box. Sets self.u97 (the live signal)."""
        try:
            if not self._u97_eur():
                return
            rg, lt = self.diamond.rough, self.diamond.last_t
            m = int(tt // 60) * 60
            if not rg or lt is None or m != lt + 60 or rg["uhv_t"] in self._u97_used:
                return
            side, lv = int(rg["side"]), float(rg["level"])
            if not (bid > lv if side > 0 else bid < lv):
                return
            self._u97_used.add(rg["uhv_t"])
            if len(self._u97_used) > 500:
                self._u97_used = set(sorted(self._u97_used)[-200:])
            bars = (fs or {}).get("bars") or []
            vf = bars[-1][5] if bars and int(bars[-1][0]) == m and len(bars[-1]) > 5 and bars[-1][5] else self._tickmin.get(m, 0)
            if rg.get("uhv_v") and vf >= rg["uhv_v"]:
                self._log(f"u97: break of UHV {rg['uhv_t']} skipped - {vf} ticks so far, not quieter than the UHV's {rg['uhv_v']}")
                return
            closed = [b for b in bars if int(b[0]) < m][-int(self._u97("u97_range_look")):]
            box = None
            if closed:
                hi, lo = max(b[2] for b in closed), min(b[3] for b in closed)
                pct = ((lv - lo) if side > 0 else (hi - lv)) / (hi - lo) if hi > lo else 0.5
                box = min(20, max(0, int(pct * 20))) if pct <= 1.0 else 20
                bands = str(self._u97("u97_bands_b" if side > 0 else "u97_bands_s")).ljust(21, "1")
                if bands[box] == "0":
                    self._log(f"u97: break of UHV {rg['uhv_t']} stands aside - range box {box} unticked")
                    return
            self.u97_level_now = lv
            why = self._risk_verdict(tt, side, bid, ask, bars, m)    # Zee 2026-11-06: the risk manager (the Angel)
            if why:
                self.angel = {"mode": "block", "t": tt, "side": side, "why": why}
                self._log(f"u97: {'BUY' if side > 0 else 'SELL'} breakout of UHV {rg['uhv_t']} STOPPED by the risk manager - {why}")
                return
            self.angel = {"mode": "bless", "t": tt, "side": side, "why": "risk managed"}
            try:                                                  # Zee 2026-11-06: size by zone - the risk level at the breakout (0 = dead sure)
                rl = int(self._risk_weather(tt, bars).get("level", 1))
            except Exception:                                     # noqa: BLE001
                rl = 1
            self.u97 = {"side": side, "t": tt, "level": lv, "extreme": float(rg["extreme"]), "uhv_t": int(rg["uhv_t"]), "box": box, "risk": rl}
            self._log(f"u97: {'BUY' if side > 0 else 'SELL'} entry signal - bid {bid} broke UHV {rg['uhv_t']} level {lv} (box {box})")
        except Exception:                                         # a hint must never stop the game
            self._log("u97 check failed: " + traceback.format_exc().splitlines()[-1])

    def _risk_verdict(self, tt, side, bid, ask, bars, m):
        """The risk manager from the loss study (research/loss_study, 172 losses read on charts). None = blessed, else why it is stopped.
        rollover: 16:45-17:45 New York (the daily rollover, NY time follows US daylight saving); spread: ask - bid at the breakout tick;
        secure zone (Turtle TV UHV InpUhvRiskMgr 2, tight): camel humps of the trade's colour in a row within [min, max] and the efficiency
        ratio of the last N closed candles within [min, max]."""
        if not int(self._u97("u97_rm")):
            return None
        ny = _dtm.datetime.fromtimestamp(tt, NY_TZ)
        if 16 * 60 + 45 <= ny.hour * 60 + ny.minute < 17 * 60 + 45:
            return "rollover hour (16:45-17:45 New York)"
        fc = float(self._u97("u97_fri_cut_ny"))                  # Zee 2026-11-06, the angel's last loss (Fri 23 Oct 10:50 NY, flattened by the
        if fc > 0 and ny.weekday() == 4 and ny.hour * 60 + ny.minute >= fc * 60:   # weekly close): Turtle TV UHV InpUhvFriCutAllNY 10
            return f"Friday after {int(fc)}:00 New York (the weekly close)"
        pip = float(self._u97("u97_pip"))
        if (ask - bid) >= float(self._u97("u97_max_spread_pips")) * pip - 1e-12:
            return f"spread too wide ({(ask - bid) / pip:.1f} pips)"
        n = int((self.diamond.cz or {}).get("Stk") or 0) * side
        lo_h, hi_h = int(self._u97("u97_safe_humps_min")), int(self._u97("u97_safe_humps_max"))
        if n < lo_h:
            return "start of a trend (first hump)" if n <= 1 else f"only {n} humps"
        if n > hi_h:
            return f"trend tired ({n} humps in a row)"
        nb = int(self._u97("u97_er_bars"))
        closed = [b for b in bars if int(b[0]) < m][-(nb + 1):]
        if len(closed) < nb + 1:
            return "not enough history"
        cl = [float(b[4]) for b in closed]
        path = sum(abs(cl[i + 1] - cl[i]) for i in range(len(cl) - 1))
        er = abs(cl[-1] - cl[0]) / path if path > 0 else 0.0
        if er < float(self._u97("u97_safe_er_min")):
            return f"choppy / ranging market (efficiency {er:.2f})"
        if er >= float(self._u97("u97_safe_er_max")):
            return f"spike - too steep (efficiency {er:.2f})"
        x = float(self._u97("u97_sellsup_pips"))                 # Zee 2026-11-06: selling into a MAJOR support (the last 10-candle swing low)
        if side < 0 and x > 0:                                    # Turtle TV UHV InpUhvSellSup: tight zone 99.44% -> 99.70%, +$376 -> +$698
            p = int(self._u97("u97_sellsup_piv"))
            cl_all = [b for b in bars if int(b[0]) < m]
            lows = [float(b[3]) for b in cl_all]
            for i in range(len(lows) - 1 - p, p - 1, -1):         # the newest swing low confirmed by the last closed candle
                if lows[i] == min(lows[i - p:i + p + 1]):
                    gap = (self.u97_level_now - lows[i]) / pip if hasattr(self, "u97_level_now") else None
                    if gap is not None and 0 <= gap <= x:
                        return f"selling into support ({gap:.1f} pips above the last major low)"
                    break
        x = float(self._u97("u97_wall_pips"))                    # Zee 2026-11-06 (the 8 April loss): a TESTED ROUND-FIGURE WALL ahead - a level the
        if x > 0 and hasattr(self, "u97_level_now"):              # highs (buy) / lows (sell) touched 3+ times in 60 candles, on a 00 figure (+-1 pip)
            cl_all = [b for b in bars if int(b[0]) < m][-int(self._u97("u97_wall_bars")):]
            ext = [float(b[2]) if side > 0 else float(b[3]) for b in cl_all]
            lv0 = self.u97_level_now
            for cc in sorted({round(e, 5) for e in ext}):
                d = ((cc - lv0) if side > 0 else (lv0 - cc)) / pip
                if 0 <= d <= x and abs(cc - round(cc / 0.01) * 0.01) <= pip and sum(1 for e in ext if abs(e - cc) <= 0.5 * pip) >= int(self._u97("u97_wall_touches")):
                    return f"{'buying' if side > 0 else 'selling'} into a tested round-figure wall ({cc:.5f})"
        return None

    def _risk_weather(self, now, bars):
        """The risk level right now, for the sky (Zee 2026-11-06: "sunshine means zero risk -> rain has levels -> more risk more rain").
        The angel's rules, read continuously for the camel's current side:
          3 storm   rollover / near the close (16:00-18:00 New York, Friday from u97_fri_cut_ny = 10:00), US data minutes, a spike candle (> 3 ATR) in the last
                    15 candles, a wide spread (>= 1 pip), a tired trend (6+ humps)
          2 rain    no trend, the start of a trend (1 hump), 4-5 humps, choppy (efficiency < 0.15) or too steep (>= 0.45)
          1 drizzle 2-3 humps but efficiency 0.15-0.30 or 0.35-0.45 (the angel's medium zone)
          0 sun     2-3 humps and efficiency 0.30-0.35 (Zee's 100% zone), no clock risk, normal spread"""
        ny = _dtm.datetime.fromtimestamp(now, NY_TZ)
        wd, mins = ny.weekday(), ny.hour * 60 + ny.minute
        sec = mins * 60 + ny.second
        q = self._q(self.fs or {}) if hasattr(self, "fs") else None
        pip = float(self._u97("u97_pip"))
        closed = bars[:-1] if bars else []
        side = int((self.diamond.cz or {}).get("Eff") or 0)
        n = abs(int((self.diamond.cz or {}).get("Stk") or 0))
        danger = []                                               # Zee: "more and more thunders can come as risk is increasing to max"
        if 16 * 60 <= mins < 18 * 60 or (wd == 4 and mins >= float(self._u97("u97_fri_cut_ny")) * 60):
            danger.append("near the close / rollover")
        if wd < 5 and any(-180 <= sec - cc * 60 <= 60 for cc in (8 * 60 + 30, 9 * 60 + 30, 10 * 60)):
            danger.append("US news minute")
        if q and (q["ask"] - q["bid"]) >= float(self._u97("u97_max_spread_pips")) * pip - 1e-12:
            danger.append("wide spread")
        if len(closed) >= 30:
            rngs = [b[2] - b[3] for b in closed[-30:]]
            atr = sum(rngs[:-15]) / 15.0 if len(rngs) >= 30 else 0.0
            if atr > 0 and max(rngs[-15:]) > 3 * atr:
                danger.append("spike")
        if side != 0 and n >= 6:
            danger.append(f"tired trend ({n} humps)")
        if danger:
            return {"level": 3, "why": " + ".join(danger), "n": len(danger)}
        if side == 0:
            return {"level": 2, "why": "no trend"}
        nb = int(self._u97("u97_er_bars"))
        if len(closed) < nb + 1:
            return {"level": 2, "why": "not enough history"}
        cl = [float(b[4]) for b in closed[-(nb + 1):]]
        path = sum(abs(cl[i + 1] - cl[i]) for i in range(len(cl) - 1))
        er = abs(cl[-1] - cl[0]) / path if path > 0 else 0.0
        if n <= 1:
            return {"level": 2, "why": "start of a trend", "er": round(er, 2)}
        if n >= 4:
            return {"level": 2, "why": f"trend getting old ({n} humps)", "er": round(er, 2)}
        if er < 0.15:
            return {"level": 2, "why": "choppy / ranging", "er": round(er, 2)}
        if er >= 0.45:
            return {"level": 2, "why": "too steep (spike)", "er": round(er, 2)}
        if 0.30 <= er < 0.35:
            return {"level": 0, "why": "zero-risk zone", "er": round(er, 2)}
        return {"level": 1, "why": "low risk", "er": round(er, 2)}

    def _angel_live(self, now):
        a = self.angel
        return a if a and self._u97_eur() and 0 <= now - a["t"] <= float(self._u97("u97_angel_s")) else None

    def _u97_live(self, now):
        u = self.u97
        return u if u and self._u97_eur() and 0 <= now - u["t"] <= float(self._u97("u97_life_s")) else None

    def _update_diamond(self, now, bars):
        if self._tickmin and len(self._tickmin) > 600:
            cut = int(now // 60) * 60 - 480 * 60
            for k in [k for k in self._tickmin if k < cut]:
                del self._tickmin[k]
        try:
            self.dia = self.diamond.update(bars, self._dia_vol, now)
            try:                                                  # Zee 2026-11-06: the risk weather follows the angel's rules
                self.risk = self._risk_weather(now, bars)
            except Exception:                                     # noqa: BLE001  (a hint must never stop the game)
                self.risk = {"level": 1, "why": "unknown"}
            if self._u97_eur():                                   # only the 97.7% setting's entries shine (not the candle-close cuts)
                d = {k: v for k, v in self.dia.items() if k not in ("cut", "id", "royal", "ea", "laws", "age", "shattered")}
                u = self._u97_live(now)
                if u:
                    d.update(cut=u["side"], id=int(u["t"]), royal=True, ea=True, laws=3, age=round(now - u["t"], 1), u97=True, u97_risk=u.get("risk", 1))
                rg = self.diamond.rough                           # day: a UHV level waits for its breakout AND price is near it (u97_near_pips;
                bid = self._hist[-1][1] if self._hist else None   # 1.5 pips catches 88% of the setting's breakouts, ~22% of all minutes)
                gap = (float(rg["level"]) - bid) * int(rg["side"]) / float(self._u97("u97_pip")) if rg and bid is not None else None
                ag = self._angel_live(now)
                if ag:
                    d["angel"] = {"mode": ag["mode"], "side": ag["side"], "why": ag["why"], "age": round(now - ag["t"], 1)}
                d["expect"] = bool(gap is not None and rg["uhv_t"] not in self._u97_used and 0 <= gap <= float(self._u97("u97_near_pips")))   # not yet broken, not used up
                if rg and bid is not None:
                    d["level_pips"] = round((float(rg["level"]) - bid) * int(rg["side"]) / float(self._u97("u97_pip")), 1)   # pips still to the break
                if self.u97:
                    d["u97_age"] = round(now - self.u97["t"], 1)  # Zee 2026-11-05: day lasts ~2.1 min after a breakout (the median winner)
                self.dia = d
        except Exception:                                     # a hint must never stop the game
            self._log("diamond reader failed: " + traceback.format_exc().splitlines()[-1])
            self.diamond.reset()
            self.dia = {}

    def _update_hints(self, now, bars):
        """Volume hints from real bars and ticks; each event stays on screen ~90 s. Bar volume is used when the feed reports it,
        otherwise the number of quotes per minute (tick volume)."""
        ev = self._hint_ev
        recent = bars[-23:] if len(bars) >= 23 else []
        if recent:
            vols = [b[5] if len(b) > 5 and b[5] else None for b in recent]
            if any(v is None for v in vols):
                counts = collections.Counter(int(x[0] // 60) for x in self._hist)
                first_m = int(self._hist[0][0] // 60) if self._hist else None
                vols = [counts.get(int(b[0] // 60)) if first_m is not None and int(b[0] // 60) >= first_m else None for b in recent]
            kind, d = vsa_read(recent, vols)
            if kind:
                ev[kind] = (d, now)
        # the liquidity sweep: a burst of ticks moving a full bar's range in 15 s, then the quiet after it (no supply / no demand)
        h = self._hist
        if len(h) > 30:
            n15 = sum(1 for x in h if x[0] >= now - 15)
            span = min(600.0, now - h[0][0])
            avg15 = (len(h) - n15) / max(1.0, (span - 15) / 15.0) if span > 30 else None
            last = [x[3] for x in h if x[0] >= now - 15]
            rngs = [b[2] - b[3] for b in bars[-21:-1]] if len(bars) >= 21 else []
            avg_rng = sum(rngs) / len(rngs) if rngs else 0.0
            if avg15 and last and n15 >= 12 and n15 >= 3.0 * avg15 and avg_rng > 0 and (max(last) - min(last)) >= 0.8 * avg_rng:
                d = 1 if last[-1] >= last[0] else -1
                ev["sweep"] = (d, now)
            elif "sweep" in ev and now - ev["sweep"][1] < 60 and avg15 and n15 <= 0.6 * avg15:
                ev["polished"] = (ev["sweep"][0], now)
        keep = {"stopping": 90.0, "trap": 90.0, "sweep": 2.0, "polished": 60.0}
        self.hints = {k: (v[0] if now - v[1] <= keep[k] else 0) for k, v in ev.items() if k in keep}

    def _update_market(self, fs, now):
        c = self.cfg
        win = float(c["tilt_window_s"])
        scale = float(c["tilt_full_scale"])
        if self.phase == "aiming" and self.aim and now - self.aim["since"] >= c["patience_s"]:
            win = float(c["tilt_long_window_s"])
            scale *= math.sqrt(win / float(c["tilt_window_s"]))
        raw = clamp(self._delta_mid(now, win) / scale, -1.0, 1.0) if scale > 0 else 0.0
        tau = max(0.05, float(c["tilt_ema_s"]))
        bars_ha = fs.get("bars") or []
        if c.get("tilt_mode") == "ha" and len(bars_ha) >= 3:
            # Zee 2026-11-04: the street follows the Heikin-Ashi body of the live 1-minute bar ($0.40 = full tilt, ~3 s of inertia) instead of the
            # raw 10-second move: chop levels the street, a real 1-minute push tilts it. Real prices only - smoothed, never predicted.
            hs = float(c.get("tilt_ha_scale", 0.40))
            raw = clamp(ha_delta(bars_ha) / hs, -1.0, 1.0) if hs > 0 else 0.0
            tau = max(0.05, float(c.get("tilt_ha_ema_s", 3.0)))
        self.tilt_raw = raw
        dt = 0.1 if self._tilt_t is None else max(0.0, min(5.0, now - self._tilt_t))
        self._tilt_t = now
        self.tilt_ema += (1.0 - math.exp(-dt / tau)) * (raw - self.tilt_ema)
        h = self._hist
        mids = [x[3] for x in h if x[0] >= now - 60]
        rng60 = (max(mids) - min(mids)) if len(mids) >= 2 else 0.0
        bars = fs.get("bars") or []
        closed = bars[-6:-1] if len(bars) >= 6 else bars[:-1]
        avg5 = sum(b[2] - b[3] for b in closed) / len(closed) if closed else 0.0
        vm = max(rng60, 0.8 * avg5)
        self.vol_metric = vm
        self.vol = round(clamp(vm / float(c["vol_storm"]), 0.0, 1.0), 3)
        tr = {}                          # higher-timeframe trends: the move over the last N minutes, in units of the typical move (-1..1)
        rngs = [b[2] - b[3] for b in bars[-31:-1]] if len(bars) >= 3 else []
        avg = sum(rngs) / len(rngs) if rngs else 0.0
        for n in (5, 15):
            if len(bars) > n and avg > 0:
                tr[n] = round(clamp((bars[-1][4] - bars[-1 - n][4]) / (avg * math.sqrt(n) * 1.2), -1.0, 1.0), 3)
        self.trends = tr
        self._update_hints(now, bars)
        self._update_diamond(now, bars)
        tps = sum(1 for x in h if x[0] >= now - 10) / 10.0
        q = self._q(fs)
        spread = (q["ask"] - q["bid"]) if q else 0.0
        if vm < c["vol_dead"] or (tps < 0.15 and len(h) > 0):
            w = "dead"
        elif vm < c["vol_calm"]:
            w = "calm"
        elif vm < c["vol_storm"]:
            w = "active"
        else:
            w = "storm"
        if spread >= c["storm_spread"] or self._news_window(now):
            w = "storm"
        self.weather = w
        self.ticks_per_s = tps
        if len(h) >= 2 and now - self._last_strike > 4.0 and abs(self._delta_mid(now, 2.0)) >= c["lightning_usd"]:
            self._last_strike = now
            self.lightning_until = now + 1.0
            self._emit({"type": "lightning"})
        r = self.round
        if r is not None and r.fill is not None and r.final is None and w == "storm":
            r.storm_seen = True

    def _check_bell(self, now):
        key = int(now // 20)
        if self._bell_cache[0] != key:
            self._bell_cache = (key, self.mc.bell(now))
        b = self._bell_cache[1]
        if b["last_t"] and (self._bell_t is None or b["last_t"] > self._bell_t + 1):
            self._bell_t = b["last_t"]
            if now - b["last_t"] < 120:
                self._emit({"type": "bell", "session": b["session"]})

    def _market_closed(self, fs, now):
        """The market is closed: by the schedule (live / --real-hours), or the feed says so EXPLICITLY. A feed reports market_open False
        for a dead feed too (Feed._market_open = ok and ...), and silence is a Time Freeze / no_feed - never a closed market."""
        if self.schedule_active and self.mc.scheduled_closed(now):
            return True
        if fs.get("market_open") is not False:
            return False
        return bool(fs.get("ok")) or str(fs.get("reason") or "").strip().lower().replace(" ", "_") == "market_closed"

    def _feed_ok(self, fs, now):
        if not fs or not fs.get("ok", False) or self._q(fs) is None:
            return False
        age = self._quote_age(now)
        return age is not None and age <= float(self.cfg["feed_dead_s"])

    def _check_freeze(self, fs, now):
        ok = self._feed_ok(fs, now)
        if ok and self._first_ok_t is None:
            self._first_ok_t = now
        fz = (not ok) and not self._market_closed(fs, now)
        if fz != self._freeze:
            self._freeze = fz
            self._emit({"type": "freeze", "on": fz})
            self._log("time freeze ON (feed silent)" if fz else "time freeze OFF")

    def _fresh_ok(self, now):
        """A quote fresh enough to compute a stop from (feed_stale_s)."""
        age = self._quote_age(now)
        return age is not None and age <= float(self.cfg["feed_stale_s"]) and self._q() is not None

    # ------------------------------------------------------------------------------------------------------------------ stakes
    def _bars(self):
        return self.fs.get("bars") or []

    def _chasm_prices(self, now):
        return self.gaps.chasms(now)

    def _lit_stakes(self, side, now):
        """Confirmed pivots (prices) for this side, never inside a chasm."""
        c = self.cfg
        ch = self._chasm_prices(now)
        return [p for p in pivots(self._bars(), side, int(c["stake_pivot"]), float(c["stake_merge"])) if not self.gaps.inside(p, ch)]

    def _eligible(self, side, sl, mark, now):
        """Stakes the anvil may move to: lit, tighter than the current stop by a tick, and passed (mark beyond them by min_sl_gap)."""
        gap = float(self.cfg["min_sl_gap"])
        out = []
        for p in self._lit_stakes(side, now):
            new_sl = r2(p - TICK * side)
            if side * (new_sl - sl) >= TICK - 1e-9 and side * (mark - p) > gap + 1e-9:
                out.append(p)
        return out

    def _next_stake(self, r, mark, now):
        el = self._eligible(r.side, r.sl, mark, now)
        if not el:
            return None
        return min(el) if r.side > 0 else max(el)

    def _haggle_stake(self, r, mark, now):
        el = self._eligible(r.side, r.sl, mark, now)
        if not el:
            return None
        return max(el) if r.side > 0 else min(el)

    def _mark(self, side, q):
        return (q["bid"] if side > 0 else q["ask"]) if q else None

    # ------------------------------------------------------------------------------------------------------------------ round upkeep
    def _broker_for(self, kind):
        return self.paper if kind == "wooden" else self.feed

    def _positions(self, kind, fs=None):
        if kind == "wooden":
            return self.paper.positions()
        fs = self.fs if fs is None else fs
        return list(fs.get("positions") or [])

    def _find_pos(self, positions, pid):
        if pid is None:
            return None
        for p in positions:
            if str(p.get("id")) == str(pid):
                return p
        return None

    def _auto_close_t(self, now):
        if not self.schedule_active or self.mc.scheduled_closed(now):
            return None
        return self.mc.next_break_start(now) - float(self.cfg["auto_close_before_close_min"]) * 60.0

    def _manage_round(self, fs, now):
        r = self.round
        q = self._q(fs)
        if self.phase == "aiming":
            self._stake_events(self.aim["side"] if self.aim else 1, None, now)
            return
        if self.phase == "sending" and r is not None and r.unknown is not None:
            u = r.unknown
            if not u.get("queued") and now >= (u.get("next_t") or 0.0):
                u["queued"] = True
                self._enqueue("resolve", self._job_resolve, r)
            return
        if r is None or self.phase not in ("open", "closing"):
            return
        mark = self._mark(r.side, q)
        if mark is not None:
            r.last_mark = mark
        if self.phase == "open" and r.fill is not None:
            age = now - r.opened_t
            if age > float(self.cfg["night_after_s"]):
                r.night_seen = True
            if r.last_path_t is None or now - r.last_path_t >= 1.0:
                r.last_path_t = now
                a, b, _, _ = ladder(r.side, r.fill, r.sl0, r.tp0, r.banked_usd, r.qty, r.qty0)
                if mark is not None and len(r.path) < 7200:
                    r.path.append([round(age, 1), xp(a, b, mark)])
            self._stake_events(r.side, r, now)
            # is our position still there? (only our id - nothing else is ever looked at)
            if not r.settling and r.position_id is not None:
                if r.kind == "wooden":
                    if not self._has(self.paper, r.position_id):
                        self._begin_settle(r, now, immediate=True)
                else:
                    pos = self._find_pos(self._positions("live", fs), r.position_id)
                    if pos is not None:
                        r.seen = True
                        r.blind = False
                        r.vanish_since = None
                        self._sync_position(r, pos, mark, now)
                        self._check_protection(r, pos, now)
                    elif r.blind:
                        pass
                    elif (self._feed_ok(fs, now) and fs.get("book_fresh", True) is not False and fs.get("account_ok", True) is not False
                          and (r.seen or now - r.opened_t > float(self.cfg["outside_grace_s"]))):
                        r.vanish_since = r.vanish_since or now
                        if now - r.vanish_since >= 0.25:
                            self._log(f"round {r.id}: position {r.position_id} gone from the book - settling from the report")
                            self._begin_settle(r, now)

            # the session close: the Merchant insists before the real break / weekend
            tc = self._auto_close_t(now)
            if (tc is not None and now >= tc and not r.close_intent and not r.settling and r.position_id is not None and
                    now >= r.session_retry_t):
                r.session_retry_t = now + 5.0
                self._log(f"round {r.id}: session close (market break in {self.cfg['auto_close_before_close_min']} min)")
                r.close_intent = "session"
                r.pending = {"action": "session", "since": now}
                self.phase = "closing"
                self._enqueue("session", self._job_close, r, None, "session", front=True)
        # the kill switch never gives up: while the position is or may be open (a pending settlement included - a stale book can hide
        # an open position) a refused close is re-sent every kill_retry_s
        if (r.kill_requested and r.fill is not None and r.final is None and r.position_id is not None and not r.close_intent and
                not r.close_done and now >= r.kill_retry_t):
            r.kill_retry_t = now + float(self.cfg["kill_retry_s"])
            self._log(f"round {r.id}: kill switch - sending the close again")
            r.close_intent = "kill"
            r.pending = {"action": "kill", "since": now}
            self.phase = "closing"
            self._enqueue("kill", self._job_close, r, None, "kill", front=True)
        if r.settling and not r.settle_queued and r.settle_next_t is not None and now >= r.settle_next_t:
            r.settle_queued = True
            self._enqueue("settle", self._job_settle, r)

    def _stake_events(self, side, r, now):
        lit = set(self._lit_stakes(side, now))
        prev = r.stakes_lit if r is not None else self._preview_lit
        if prev is not None and isinstance(prev, tuple) and prev[0] == side and now >= self._stakes_quiet_until:
            for p in sorted(lit - prev[1]):
                a, b = self._ladder_now(side, r)
                if a is not None:
                    self._emit({"type": "stake", "x": xp(a, b, p - TICK * side), "price": p})
        if r is not None:
            r.stakes_lit = (side, lit)
        else:
            self._preview_lit = (side, lit)

    def _ladder_now(self, side, r):
        if r is not None and r.fill is not None:
            a, b, _, _ = ladder(r.side, r.fill, r.sl0, r.tp0, r.banked_usd, r.qty, r.qty0)
            return a, b
        q = self._q()
        if not q:
            return None, None
        entry = q["ask"] if side > 0 else q["bid"]
        tgt = self.aim["target"] if self.aim else self.settings["target"]
        a, b, _, _ = ladder(side, entry, entry - side * self.settings["stop_dist"], entry + side * tgt)
        return a, b

    def _sync_position(self, r, pos, mark, now):
        """The broker is the truth: follow its SL/TP/qty for OUR position (Zee may have touched it on the page). A stop or target the
        book does not show is NOT there (no anvil / tag is drawn for it and _check_protection sets it again)."""
        if r.pending or now < r.sync_hold_until:
            return
        bsl, btp, bq = _num(pos.get("sl")), _num(pos.get("tp")), _num(pos.get("qty"))
        # a stop / target the book does not show: drawn as missing after 1 s, set again after protect_grace_s (a single frame without
        # it - e.g. while PX replaces a stop Zee moved by hand - is never acted on)
        r.sl_missing_since = (r.sl_missing_since or now) if bsl is None else None
        r.tp_missing_since = (r.tp_missing_since or now) if btp is None else None
        r.sl_missing = r.sl_missing_since is not None and now - r.sl_missing_since >= 1.0
        r.tp_missing = r.tp_missing_since is not None and now - r.tp_missing_since >= 1.0
        op = _num(pos.get("open_price"))
        if not r.fill_checked and op is not None and r.fill is not None:
            r.fill_checked = True              # the ladder is re-anchored on the broker's own open price (once, before any action)
            if abs(op - r.fill) >= 0.005 and not (r.machete_done or r.walls or r.haggles or r.anvil_moves or r.banked_usd):
                r.notes.append({"t": now, "note": f"fill re-anchored on the broker's open price: {r.fill} -> {r2(op)}"})
                self._log(f"round {r.id}: fill {r.fill} -> {r2(op)} (the broker's open price)")
                r.fill = r2(op)
                ref = r.entry_ref if r.entry_ref is not None else r.fill
                adverse = r.side * (r.fill - ref)
                r.slippage_entry = round(adverse * r.qty0, 6) if adverse > 0.0049 else 0.0
                r.rat = [b for b in r.rat if b.get("why") != "slippage"]
                if r.slippage_entry:
                    r.rat.append({"t": now, "usd": r.slippage_entry, "why": "slippage"})
                self._update_restore(r)
        if bq is not None and bq > 0 and bq < r.qty - 1e-9 and now < r.machete_hold_until and not r.machete_done:
            gone = round(r.qty - bq, 2)        # the machete whose answer was lost DID cut: the book shows the smaller size
            if mark is not None:
                r.banked_usd = round(r.banked_usd + r.side * (mark - r.fill) * gone, 6)
            r.qty = round(bq, 2)
            r.machete_done = True
            r.machete_hold_until = 0.0
            r.golden = {"price": r.sl, "usd": round(r.banked_usd + r.side * (r.sl - r.fill) * r.qty, 6)}
            r.notes.append({"t": now, "note": f"the machete did cut {gone} oz (seen in the book after its answer was lost)"})
            self._update_restore(r)
            return
        if bsl is not None and r.sl is not None and abs(bsl - r.sl) >= 0.005:
            r.notes.append({"t": now, "note": f"stop moved outside the game: {r.sl} -> {bsl}"})
            r.sl = r2(bsl)
        if btp is not None and r.tp is not None and abs(btp - r.tp) >= 0.005:
            r.notes.append({"t": now, "note": f"target moved outside the game: {r.tp} -> {btp}"})
            r.tp = r2(btp)
        if bq is not None and bq > 0 and bq < r.qty - 1e-9:
            gone = round(r.qty - bq, 2)
            if mark is not None:
                r.banked_usd += r.side * (mark - r.fill) * gone
            r.notes.append({"t": now, "note": f"{gone} oz closed outside the game"})
            r.qty = round(bq, 2)

    def _check_protection(self, r, pos, now):
        """The Golden Rule ("the game never lies"; REQUIREMENTS 1.3: "there is never a moment of the round without both"): if the broker's
        book does not show our stop or target protect_grace_s after the fill, set it again; if that fails twice (or the price is
        already beyond it), close at market and say so. These are the only automatic trading frames besides the session close - each
        one is logged loudly and announced with a "protect" event."""
        if r.kind == "wooden" or r.pending or r.close_intent or r.kill_requested or r.settling or r.final is not None:
            return
        if r.sl_missing_since is None and r.tp_missing_since is None:
            r.prot_fail_n = 0
            return
        grace = float(self.cfg["protect_grace_s"])
        need_sl = r.sl_missing_since is not None and now - r.sl_missing_since >= grace
        need_tp = r.tp_missing_since is not None and now - r.tp_missing_since >= grace
        if not (need_sl or need_tp):
            return                                       # missing, but not for long enough to act on
        if now < (r.opened_t or now) + grace or now < r.sync_hold_until or now < r.prot_next_t:
            return
        r.prot_next_t = now + 3.0
        r.pending = {"action": "protect", "since": now}
        self._enqueue("protect", self._job_protect, r, need_sl, need_tp, front=True)

    def _job_protect(self, r, need_sl, need_tp):
        q, _age = self._fresh_quote(r.kind)
        with self.lock:
            if (self.round is not r or self.phase != "open" or r.position_id is None or r.final is not None or r.kill_requested or
                    r.close_intent):
                if r.pending and r.pending.get("action") == "protect":
                    r.pending = None
                return
            pid, sl, tp, side = r.position_id, r.sl, r.tp, r.side
        broker = self._broker_for(r.kind)
        try:                                             # the book right now: never re-send what the broker already holds
            fs = self.feed.state() or {}
        except Exception:  # noqa: BLE001
            fs = {}
        pos = self._find_pos(fs.get("positions") or [], pid)
        if pos is None or (_num(pos.get("sl")) is not None or not need_sl) and (_num(pos.get("tp")) is not None or not need_tp):
            with self.lock:
                if r.pending and r.pending.get("action") == "protect":
                    r.pending = None
                if pos is not None:                      # it is protected after all (the book caught up): nothing to send
                    if need_sl:
                        r.sl_missing, r.sl_missing_since = False, None
                    if need_tp:
                        r.tp_missing, r.tp_missing_since = False, None
            return                                       # gone from the book: the vanish check settles it from the report
        need_sl = need_sl and _num(pos.get("sl")) is None
        need_tp = need_tp and _num(pos.get("tp")) is None
        what = " and ".join(w for w, need in (("stop", need_sl), ("target", need_tp)) if need)
        beyond, sent = None, {}
        if q is not None:
            mark, far = self._mark(side, q), (q["ask"] if side > 0 else q["bid"])
            if need_sl and side * (mark - sl) <= 0:
                beyond = "the price is already beyond the stop"
            elif need_tp and side * (tp - far) <= 0:
                beyond = "the price is already beyond the target"
        if beyond is None:
            if need_sl:
                sent["sl"] = self._call(broker.set_protective, pid, "STOP_LOSS", sl, timeout=5.0)
            if need_tp and (not need_sl or sent["sl"].get("ok")):
                sent["tp"] = self._call(broker.set_protective, pid, "TAKE_PROFIT", tp, timeout=5.0)
        now = self.clock()
        with self.lock:
            if r.pending and r.pending.get("action") == "protect":
                r.pending = None
            if self.round is not r or r.final is not None:
                return
            ok = beyond is None and len(sent) == int(need_sl) + int(need_tp) and all(x.get("ok") for x in sent.values())
            if ok:
                r.sync_hold_until = now + 2.5
                if need_sl:
                    r.sl_missing, r.sl_missing_since = False, None
                if need_tp:
                    r.tp_missing, r.tp_missing_since = False, None
                r.prot_fail_n = 0
                self._log(f"round {r.id}: PROTECT - the broker did not hold the {what}; set again at {sl if need_sl else ''}"
                          f"{' / ' if need_sl and need_tp else ''}{tp if need_tp else ''}")
                r.notes.append({"t": now, "note": f"the broker did not hold the {what}: set again"})
                self._emit({"type": "protect", "ok": True, "what": what})
                self._update_restore(r)
                return
            r.prot_fail_n += 1
            why = beyond or "; ".join(f"{k}: {v.get('error')}" for k, v in sent.items() if not v.get("ok")) or "refused"
            if beyond is None and r.prot_fail_n < 2:
                r.prot_next_t = now + 2.0
                self._log(f"round {r.id}: PROTECT - could not set the {what} again ({why}); one more try")
                return
            self._log(f"round {r.id}: UNPROTECTED - the broker holds no {what} and it cannot be set ({why}): CLOSING AT MARKET")
            r.notes.append({"t": now, "note": f"no {what} at the broker and it could not be set ({why}): closed at market"})
            self._emit({"type": "protect", "ok": False, "what": what, "why": scrub(why)})
            if self.phase != "open" or r.close_intent:
                return
            r.close_intent = "protect"
            r.pending = {"action": "protect", "since": now}
            self.phase = "closing"
            self._enqueue("protect", self._job_close, r, None, "protect", front=True)

    # ------------------------------------------------------------------------------------------------------------------ shadows
    def _start_twin(self, r, now):
        res = self.shadow.place(r.side, r.qty0, r.sl0, r.tp0, fill_price=r.fill)
        pid = res.get("position_id") if res.get("ok") else None
        if pid is None:
            self._log(f"twin could not start: {res.get('error')}")
            return
        sh = {"kind": "twin", "round_id": r.id, "pid": pid, "side": r.side, "fill": r.fill, "sl": r.sl0, "tp": r.tp0, "qty": r.qty0,
              "sd0": abs(r.fill - r.sl0), "td0": abs(r.tp0 - r.fill), "opened_t": now, "state": "running", "result_usd": None,
              "exit": None, "round": r, "moves": 0,
              "known": {r2(p) for p in self._lit_stakes(r.side, now)}}   # stakes that already stood at entry: the Twin ignores them
        self.shadows.append(sh)
        r.twin = sh

    def _start_counterfactual(self, r, now):
        """After an eject or a merchant close: keep shadowing what was closed until its stop or target would have hit (or 60 min)."""
        if r.fill is None or r.sl is None or r.tp is None or r.qty <= 0:
            return
        res = self.shadow.place(r.side, r.qty, r.sl, r.tp, fill_price=r.fill)
        pid = res.get("position_id") if res.get("ok") else None
        if pid is None:
            self._log(f"counterfactual could not start: {res.get('error')}")
            return
        sh = {"kind": "cf", "round_id": r.id, "pid": pid, "side": r.side, "fill": r.fill, "sl": r.sl, "tp": r.tp, "qty": r.qty,
              "banked": r.banked_usd, "opened_t": now, "state": "running", "result_usd": None, "exit": None, "round": r}
        self.shadows.append(sh)

    def _manage_shadows(self, now):
        if not self.shadows:
            return
        q = self._q()
        keep = []
        for sh in self.shadows:
            if sh["state"] == "running":
                if not self._has(self.shadow, sh["pid"]):
                    self._shadow_finish(sh, now, expired=False)
                elif now - sh["opened_t"] > float(self.cfg["counterfactual_max_s"]):
                    self.shadow.close(sh["pid"], sh["qty"])
                    self._shadow_finish(sh, now, expired=True)
                elif sh["kind"] == "twin" and q is not None:
                    mark = self._mark(sh["side"], q)
                    el = [p for p in self._eligible(sh["side"], sh["sl"], mark, now) if r2(p) not in sh.get("known", ())]
                    if el:
                        p = max(el) if sh["side"] > 0 else min(el)
                        new_sl = r2(p - TICK * sh["side"])
                        if self.shadow.set_protective(sh["pid"], "STOP_LOSS", new_sl).get("ok"):
                            sh["sl"] = new_sl
                            sh["moves"] += 1
                            if not self._has(self.shadow, sh["pid"]):
                                self._shadow_finish(sh, now, expired=False)
            if sh["state"] == "running":
                keep.append(sh)
        self.shadows = keep

    def _shadow_finish(self, sh, now, expired):
        res = self.shadow.result(sh["pid"]) or {}
        rpl = (_num(res.get("rpl"), 0.0) or 0.0) - (_num(res.get("fee"), 0.0) or 0.0)
        sh["exit"] = _num(res.get("exit_price"))
        sh["state"] = "done"
        r = sh["round"]
        if sh["kind"] == "twin":
            sh["result_usd"] = round(rpl, 6)
            sh["how"] = "expired" if expired else (res.get("exit_type") or "?")
            self._log(f"twin of {sh['round_id']} done: {money(sh['result_usd'], r.risk_usd, True)} ({sh['how']})")
            if r.settlement is not None:
                r.settlement["twin_result_usd"] = sh["result_usd"]
        else:
            sh["result_usd"] = round(sh["banked"] + rpl, 6)
            r.would_have_usd = sh["result_usd"]
            self._log(f"counterfactual of {sh['round_id']}: would have made {money(sh['result_usd'], r.risk_usd, True)}")
            if r.settlement is not None:
                r.settlement["would_have_usd"] = sh["result_usd"]
        if r.final is not None:
            self._write_round_log(r)
            self._refresh_summary(r)

    # ------------------------------------------------------------------------------------------------------------------ discipline
    def _disc(self):
        d = self.discipline.setdefault(self.mode, {})
        d.setdefault("awards", {})
        d.setdefault("lock", None)
        d.setdefault("storm", None)
        return d

    def _award(self, key, now):
        d = self._disc()
        if key not in d["awards"]:
            d["awards"][key] = now
            self._log(f"trophy: {TROPHIES.get(key, key)}")
            self._sum_version += 1
            self._save_json("discipline.json", self.discipline)

    def _note_refusal(self, why):
        d = self._disc()
        if why == "locked" and d.get("lock"):
            d["lock"]["attempts"] += 1
            self._save_json("discipline.json", self.discipline)
        if why == "news" and d.get("storm"):
            d["storm"]["attempts"] += 1

    def _discipline_watch(self, now):
        if now - self._disc_t < 2.0:
            return
        self._disc_t = now
        d = self._disc()
        lim = self._limits(now)
        day = utc_day(now)
        if lim["locked_until"] and lim.get("locked_reason") == "loss":
            if not d["lock"] or d["lock"].get("day") != day:
                d["lock"] = {"day": day, "attempts": 0}
                self._save_json("discipline.json", self.discipline)
        elif d["lock"] and d["lock"].get("day") != day:
            if d["lock"].get("attempts", 1) == 0:
                self._award("walked_away", now)
            d["lock"] = None
            self._save_json("discipline.json", self.discipline)
        if self._news_window(now):
            if not d["storm"]:
                d["storm"] = {"start": now, "attempts": 0}
        elif d["storm"]:
            if d["storm"].get("attempts", 1) == 0 and now - d["storm"].get("start", now) >= 60:
                self._award("waited_storm", now)
            d["storm"] = None

    # ------------------------------------------------------------------------------------------------------------------ restore after a restart
    def _maybe_restore(self, fs, now):
        rs = self._restore
        if not rs:
            return
        name = f"open_round_{self.mode}.json"
        if self.mode != "live" or rs.get("mode") != self.mode or rs.get("kind") != "live" or self.round is not None:
            self._restore = None
            self._delete_state(name)
            return
        if (not self._feed_ok(fs, now) or self._first_ok_t is None or now - self._first_ok_t < 3.0 or
                fs.get("book_fresh", True) is False or fs.get("account_ok", True) is False):
            return                                 # the book must be known (and the game's account) before anything is decided
        self._restore = None
        try:
            r = Round.from_restore(rs)
        except Exception as e:  # noqa: BLE001
            self._log(f"could not restore the open round: {e}")
            self._delete_state(name)
            return
        r.last_path_t = None
        self.round = r
        if r.position_id is None:
            if r.unknown:
                r.unknown.update({"queued": False, "next_t": now, "token": None})
                r.pending = {"action": "resolve", "since": now}
                self.phase = "sending"
                self._log(f"resumed round {r.id}: its order's outcome is still unknown - looking for it in the book and the deal history")
            else:
                self.round = None
                self._delete_state(name)
            return
        self._feed_adopt(r.position_id)        # the game opened it in an earlier session (its own round state says so)
        pos = self._find_pos(self._positions("live", fs), r.position_id)
        if pos is not None:
            r.seen = True
            r.close_intent = None              # that close did not happen (the position is still there): the retry loops take over
            r.close_done = False
            self.phase = "open"
            self._log(f"resumed round {r.id}: our position {r.position_id} is still open"
                      + (" - the kill switch will close it" if r.kill_requested else ""))
        else:
            self.phase = "closing"
            self._log(f"round {r.id}: our position {r.position_id} closed while the game was away - settling from the report")
            self._begin_settle(r, now, immediate=True)

    # ------------------------------------------------------------------------------------------------------------------ limits / shutters / gating
    def _mode_rounds(self):
        return [s for s in self.summaries if s.get("mode") == self.mode]

    def _limits(self, now):
        key = (self._sum_version, int(now), self.phase, self.settings["coin_oz"], self.settings["stop_dist"], self.killed.get(self.mode),
               id(self.round))
        if self._lim_cache[0] == key:
            return self._lim_cache[1]
        c = self.cfg
        rs = self._mode_rounds()
        counted = [s for s in rs if (s.get("kind") == "live" or c["limits_count_wooden"]) and not s.get("estimated")]
        day = utc_day(now)
        today = [s for s in counted if utc_day(s.get("closed_t") or s.get("opened_t") or 0) == day]
        r = self.round
        open_counted = 1 if (r is not None and self.phase in ("sending", "open", "closing") and
                             (r.kind == "live" or c["limits_count_wooden"])) else 0
        rounds_today = len(today) + open_counted
        net_coins = sum((s.get("result_usd") or 0.0) / s["risk_usd"] for s in today if s.get("risk_usd"))
        net_usd = sum((s.get("result_usd") or 0.0) for s in today)
        loss_coins = round(max(0.0, -net_coins), 4)
        risk = self.settings["coin_oz"] * self.settings["stop_dist"]
        loss_max = float(c["loss_max_coins"])
        if self.mode == "live" and c.get("loss_max_balance_pct") and risk > 0:
            bal = self._day_start_balance(day, net_usd)
            if bal:
                loss_max = min(loss_max, max(1.0, math.floor(float(c["loss_max_balance_pct"]) * bal / risk * 100) / 100.0))
        locked_until, locked_reason = None, None
        if loss_coins > 0 and loss_coins >= loss_max - 1e-9:
            locked_until, locked_reason = next_utc_midnight(now), "loss"
        if self.killed.get(self.mode) == day:
            locked_until, locked_reason = next_utc_midnight(now), "kill"
        streak, jam_until = 0, None
        recent = sorted([s for s in counted if (s.get("closed_t") or 0) > now - 86400], key=lambda s: s.get("closed_t") or 0)
        for s in recent:
            res = s.get("result_usd") or 0.0
            if s.get("outcome") in ("anvil", "barrel") and res < 0:
                streak += 1
            elif res > 0:
                streak = 0
            if streak >= int(c["jam_after_stops"]):
                jam_until = (s.get("closed_t") or now) + float(c["jam_minutes"]) * 60.0
                streak = 0
        if jam_until is not None and now < jam_until:
            stops = int(c["jam_after_stops"])
        else:
            jam_until, stops = None, streak
        wooden = [s for s in rs if s.get("kind") == "wooden"]
        out = {"rounds_today": rounds_today, "rounds_max": int(c["rounds_max"]), "loss_today_coins": loss_coins,
               "loss_max_coins": loss_max if loss_max != int(loss_max) else int(loss_max), "stops_in_row": stops,
               "jam_until": jam_until, "locked_until": locked_until, "locked_reason": locked_reason,
               "alley_done": len(wooden), "alley_needed": int(c["alley_needed"]),
               "alley_eject_done": any(s.get("outcome") == "eject" for s in wooden),
               "alley_machete_done": any(s.get("machete_done") for s in wooden),
               "alley_machete_needed": self._can_split() and bool(c.get("alley_needs_machete"))}
        self._lim_cache = (key, out)
        return out

    def _day_start_balance(self, day, net_usd_today):
        if day not in self._dsb:
            acct = self.fs.get("account") or {}
            bal = _num(acct.get("balance"))
            if bal is None:
                return None
            self._dsb[day] = bal - net_usd_today
        return self._dsb[day]

    def _can_split(self):
        c = self.cfg
        lots = int(round(self.settings["coin_oz"] / c["qty_step"]))
        return (lots // 2) * c["qty_step"] >= c["min_qty"] - 1e-9 and (lots - lots // 2) * c["qty_step"] >= c["min_qty"] - 1e-9

    def _shutters(self, now, lim):
        def down(reason, until):
            return {"down": True, "reason": reason, "until": until}
        if lim["locked_until"]:
            return down("locked", lim["locked_until"])
        if lim["jam_until"]:
            return down("jam", lim["jam_until"])
        if lim["rounds_today"] >= lim["rounds_max"]:
            return down("rounds_max", next_utc_midnight(now))
        if self.schedule_active:
            if self.mc.is_weekend(now):
                return down("weekend", self.mc.reopen_after(now))
            if self.mc.in_daily_break(now):
                return down("market_closed", self.mc.reopen_after(now))
        fs = self.fs
        if self._market_closed(fs, now):
            return down("market_closed", None)
        if not self._feed_ok(fs, now):
            return down("no_feed", None)
        nw = self._news_window(now) if self.cfg.get("news_shutters", True) and (self.mode != "sim" or self.cfg.get("news_shutters_in_sim")) else None   # Zee 2026-11-04: sim news is invented; "we can ride the waves during news.. open the gates" = news_shutters off
        if nw:
            return down("news", nw)
        if self.schedule_active:
            dw = self.mc.dead_window(now)
            if dw:
                return down("dead_hours", dw[1])
        return {"down": False, "reason": None, "until": None}

    def _why_not_live(self, now, lim, sh):
        c = self.cfg
        if not getattr(self.feed, "can_trade", False) or self.mode not in ("live", "sim"):
            return "mode"           # replay: no amount of Alley rounds unlocks a real order - say so first (the game never lies)
        if (lim["alley_done"] < lim["alley_needed"] or not lim["alley_eject_done"] or
                (lim["alley_machete_needed"] and not lim["alley_machete_done"])):
            return "alley"
        if not self.settings["live_enabled"]:
            return "confirm"
        acct = self.fs.get("account") or {}
        bal = _num(acct.get("balance"))
        q = self._q()
        price = ((q["bid"] + q["ask"]) / 2.0) if q else 4000.0
        risk = self.settings["coin_oz"] * self.settings["stop_dist"]
        need = risk + self.settings["coin_oz"] * price / float(c["leverage"] or 1000)
        if bal is None or bal < need:
            return "balance"
        if sh["down"]:
            return "shutters"
        return None

    def _twin_unlocked(self):
        return sum(1 for s in self._mode_rounds() if s.get("kind") == "live") >= int(self.cfg["twin_unlock_rounds"])

    def _twin_available(self, kind):
        return kind == "wooden" or self._twin_unlocked()

    # ------------------------------------------------------------------------------------------------------------------ actions
    def act(self, body):
        now = self.clock()
        if not isinstance(body, dict):
            body = {}
        action = str(body.get("action") or "")
        nonce = body.get("nonce")
        nonce = None if nonce in (None, "") else str(nonce)[:80]
        args = body.get("args") if isinstance(body.get("args"), dict) else {}
        sent_at = _num(body.get("sent_at"))
        stale = float(self.cfg["stale_instruction_s"])
        with self.lock:
            why = None
            if action not in ACTIONS:
                why = "unknown_action"
            elif nonce is None:
                why = "nonce"
            elif nonce in self._nonces:
                why = "duplicate"
            elif action != "kill" and (sent_at is None or now - sent_at > stale or sent_at - now > stale):
                why = "stale"          # the server never acts on a stale client instruction (the kill switch is exempt)
            if nonce is not None and why != "duplicate":
                self._nonces[nonce] = now
                while len(self._nonces) > 5000:
                    self._nonces.popitem(last=False)
            ins = {"nonce": nonce, "action": action, "args": sanitize(args), "sent_at": sent_at, "recv_t": now}
            ok = False
            if why is None:
                try:
                    ok, why = getattr(self, "_a_" + action)(args, now, ins)
                except Exception as e:  # noqa: BLE001
                    self._log(f"action {action} error: " + traceback.format_exc(limit=6))
                    ok, why = False, f"error: {type(e).__name__}"
            ins["accepted"], ins["why"] = ok, why
            if action in ACTIONS:
                r = self.round
                if r is not None and self.phase in ("sending", "open", "closing", "settled") and ins not in r.instructions:
                    r.instructions.append(ins)
                elif ins not in self.pre_instr and (self.round is None or ins not in self.round.instructions):
                    self.pre_instr.append(ins)
                    del self.pre_instr[:-50]
            if not ok and self.round is not None and action in ("anvil_next", "wall", "haggle", "machete", "merchant", "eject"):
                self.round.last_refusal = {"action": action, "why": why, "t": now}
            if not ok:
                self._log(f"refused {action or '?'}: {why}")
            self._emit({"type": "accepted" if ok else "refused", "nonce": nonce, "action": action, "why": why})
            self._snap_cache = (0.0, None)
            return {"accepted": bool(ok), "why": why}

    def _a_fund(self, args, now, ins):
        if self.phase != "lobby":
            return False, "phase"
        kind = args.get("kind", "wooden")
        if kind not in ("wooden", "live"):
            return False, "bad_args"
        side = args.get("side", self.settings["side"])
        try:
            side = int(side)
        except (TypeError, ValueError):
            return False, "bad_args"
        if side not in (1, -1):
            return False, "bad_args"
        target = _num(args.get("target"), self.settings["target"])
        if not any(abs(target - t) < 1e-9 for t in self.cfg["targets"]):
            return False, "bad_target"
        twin = bool(args.get("twin", self.settings["twin_invited"]))
        if args.get("coins") is not None:          # Zee 2026-11-04: shoot 1-3 men -> carry 1-3 coins (0.01 oz each) this round
            try:
                n = int(args.get("coins"))
            except (TypeError, ValueError):
                return False, "bad_args"
            if not 1 <= n <= int(self.cfg.get("coins_max", 3)):
                return False, "bad_args"
            self.settings["coin_oz"] = round(n * float(self.cfg["coin_oz"]), 2)   # one coin = config coin_oz (0.10 oz -> $0.10 at risk)
        lim = self._limits(now)
        sh = self._shutters(now, lim)
        if sh["down"]:
            self._note_refusal(sh["reason"])
            return False, sh["reason"]
        if kind == "live":
            wn = self._why_not_live(now, lim, sh)
            if wn:
                return False, wn
        if twin and not self._twin_available(kind):
            twin = False
        self.settings.update({"side": side, "target": float(target), "twin_invited": bool(args.get("twin", self.settings["twin_invited"]))})
        self._save_settings()
        self.aim = {"kind": kind, "side": side, "target": float(target), "twin": twin, "since": now, "refusals": 0, "last_refusal_t": None}
        self._preview_lit = None
        self.phase = "aiming"
        return True, None

    def _a_unfund(self, args, now, ins):
        if self.phase != "aiming":
            return False, "phase"
        self.aim = None
        self.phase = "lobby"
        return True, None

    def _a_flip(self, args, now, ins):
        if self.phase not in ("lobby", "aiming"):
            return False, "phase"
        side = args.get("side", -self.settings["side"])
        try:
            side = int(side)
        except (TypeError, ValueError):
            return False, "bad_args"
        if side not in (1, -1):
            return False, "bad_args"
        self.settings["side"] = side
        if self.aim:
            self.aim["side"] = side
        self._preview_lit = None
        self._save_settings()
        return True, None

    def _a_set_target(self, args, now, ins):
        if self.phase not in ("lobby", "aiming"):
            return False, "phase"
        target = _num(args.get("target"))
        if target is None or not any(abs(target - t) < 1e-9 for t in self.cfg["targets"]):
            return False, "bad_target"
        self.settings["target"] = float(target)
        if self.aim:
            self.aim["target"] = float(target)
        self._save_settings()
        return True, None

    def _a_invite_twin(self, args, now, ins):
        if self.phase not in ("lobby", "aiming"):
            return False, "phase"
        on = bool(args.get("on", True))
        if on and self.aim and not self._twin_available(self.aim["kind"]):
            return False, "twin_locked"
        self.settings["twin_invited"] = on
        if self.aim:
            self.aim["twin"] = on
        self._save_settings()
        return True, None

    def _new_round_id(self, now):
        base = time.strftime("%Y%m%d-%H%M%S", time.gmtime(now)) + "-" + self.mode
        known = {s.get("id") for s in self.summaries}
        rid, n = base, 1
        while rid in known or os.path.exists(os.path.join(self.rounds_dir, rid[:8], rid + ".json")):
            n += 1
            rid = f"{base}-{n}"
        return rid

    def _a_shoot(self, args, now, ins):
        if self.phase != "aiming" or not self.aim:
            return False, "phase"
        ag = self._angel_live(now)
        if ag and ag["mode"] == "block":                          # Zee 2026-11-06: the angel's two light shields - risk not allowed
            self._note_refusal("angel")
            return False, "angel"
        a = self.aim
        c = self.cfg
        if a["last_refusal_t"] is not None and now - a["last_refusal_t"] < float(c["shoot_retry_s"]):
            return False, "cooldown"
        lim = self._limits(now)
        sh = self._shutters(now, lim)
        if sh["down"]:
            self._note_refusal(sh["reason"])
            return False, sh["reason"]
        if a["kind"] == "live":
            wn = self._why_not_live(now, lim, sh)
            if wn:
                return False, wn
        if self._freeze:
            return False, "freeze"
        if not self._fresh_ok(now):
            return False, "stale_quote"
        coin = self.settings["coin_oz"]
        sd = self.settings["stop_dist"]
        tgt = a["target"]
        u = self._u97_live(now)
        u = u if u and u["side"] == a["side"] else None
        if u:                                                     # fired on the 97.7% setting's signal: its own stop and target
            pip = float(self._u97("u97_pip"))
            sd = max((u["level"] - u["extreme"]) * u["side"], 0.0) + float(self._u97("u97_beyond_pips")) * pip   # re-measured from the live quote at send
            sd = min(sd, float(self._u97("u97_max_stop_pips")) * pip)   # 2026-11-06 (coin 50,000): the broker's own stop never further than this
            tgt = float(self._u97("u97_tp_pips")) * pip
        r = Round(self._new_round_id(now), self.mode, a["kind"], a["side"], coin, sd, tgt, round(coin * sd, 6))
        r.u97 = dict(u) if u else None
        r.shot_t = now
        r.patience_s = round(now - a["since"], 2)
        r.session = self._session(now)
        r.weather = self.weather
        r.twin_invited = bool(a["twin"]) and self._twin_available(a["kind"])
        r.instructions = list(self.pre_instr)
        r.instructions.append(ins)
        self.pre_instr = []
        r.pending = {"action": "shoot", "since": now}
        self.round = r
        self.phase = "sending"
        self._enqueue("shoot", self._job_shoot, r, ins)
        return True, None

    def _open_checks(self, now, need_fresh=True):
        r = self.round
        if self.phase != "open" or r is None or r.fill is None:
            return None, "phase"
        if r.kill_requested:
            return None, "killed"                # the kill switch owns the round now: it closes it, nothing else trades
        if r.pending:
            return None, "busy"
        if self._freeze:
            return None, "freeze"
        if need_fresh and not self._fresh_ok(now):
            return None, "stale_quote"
        return r, None

    def _a_anvil_next(self, args, now, ins):
        r, why = self._open_checks(now)
        if why:
            return False, why
        mark = self._mark(r.side, self._q())
        p = self._next_stake(r, mark, now)
        if p is None:
            return False, "no_stake"
        new_sl = r2(p - TICK * r.side)
        r.pending = {"action": "anvil_next", "since": now}
        r.anvil_pending = True
        self._enqueue("anvil_next", self._job_sl, r, ins, "anvil_next", new_sl, "stake")
        return True, None

    def _wall_price(self, r, mark):
        # Zee 2026-11-04: walls trail like a stop you move up as you go - each one right behind the Runner, as many as you like, until the
        # boss buys the coin or the Runner falls back onto his nearest wall. (The old break-even cap on the first wall and the limit of two
        # walls are gone; a wall must still be tighter than the stop it replaces.)
        new_sl = mark - r.side * float(self.cfg["wall_buffer"])
        return floor_cent(new_sl) if r.side > 0 else ceil_cent(new_sl)

    def _a_wall(self, args, now, ins):
        r, why = self._open_checks(now)
        if why:
            return False, why
        if len(r.walls) >= int(self.cfg["walls_max"]):
            return False, "walls_max"
        mark = self._mark(r.side, self._q())
        new_sl = self._wall_price(r, mark)
        if r.side * (new_sl - r.sl) < TICK - 1e-9:
            return False, "no_tighten"
        r.pending = {"action": "wall", "since": now}
        r.anvil_pending = True
        self._enqueue("wall", self._job_sl, r, ins, "wall", new_sl, "wall")
        return True, None

    def _a_haggle(self, args, now, ins):
        r, why = self._open_checks(now)
        if why:
            return False, why
        c = self.cfg
        if r.haggles >= int(c["haggle_max"]):
            return False, "haggle_max"
        mark = self._mark(r.side, self._q())
        a, b, _, _ = ladder(r.side, r.fill, r.sl0, r.tp0, r.banked_usd, r.qty, r.qty0)
        if xp(a, b, mark) < xp(a, b, r.tp) - float(c["haggle_reach_x"]):
            return False, "too_far"
        if r.side * self.tilt_ema <= 0:          # the street must slope toward the buyer right now
            return False, "tilt"
        p = self._haggle_stake(r, mark, now)
        if p is None:
            return False, "no_stake"
        new_sl = r2(p - TICK * r.side)
        new_tp = r2(r.tp + r.side * float(c["haggle_step"]))
        r.pending = {"action": "haggle", "since": now}
        r.anvil_pending = True
        self._enqueue("haggle", self._job_haggle, r, ins, new_sl, new_tp)
        return True, None

    def _machete_qty(self, r):
        c = self.cfg
        lots = int(round(r.qty / c["qty_step"]))
        close_qty = round((lots // 2) * c["qty_step"], 2)
        rem = round(r.qty - close_qty, 2)
        if close_qty < c["min_qty"] - 1e-9 or rem < c["min_qty"] - 1e-9:
            return None
        return close_qty

    def _a_machete(self, args, now, ins):
        r, why = self._open_checks(now, need_fresh=False)
        if why:
            return False, why
        if r.machete_done:
            return False, "machete_done"
        if now < r.machete_hold_until:
            return False, "busy"                 # the last cut's answer was lost: wait until the book shows what happened
        cq = self._machete_qty(r)
        if cq is None:
            return False, "chained"
        r.pending = {"action": "machete", "since": now}
        self._enqueue("machete", self._job_machete, r, ins, cq)
        return True, None

    def _a_close(self, intent, now, ins):
        r = self.round
        pending_settle = self.phase == "closing" and r is not None and r.settling and not r.close_done
        if (self.phase != "open" and not pending_settle) or r is None or r.fill is None:
            return False, "phase"
        if r.kill_requested:
            return False, "killed"
        if r.close_intent:
            return False, "busy"
        if self._freeze:
            return False, "freeze"
        if r.kind == "wooden":                            # a wooden coin is sold at the quote the street shows: never at a stale one
            age = self._quote_age(now)                    # (a live close goes to the broker, which fills at its own price)
            if age is None or age > float(self.cfg["feed_stale_s"]):
                return False, "stale_quote"
        r.close_intent = intent
        r.pending = {"action": intent, "since": now}
        self.phase = "closing"
        self._enqueue(intent, self._job_close, r, ins, intent)
        return True, None

    def _girl_margin_usd(self, r):
        mp = self.cfg.get("merchant_margin_price")
        return float(mp) * float(r.qty or 0) if mp is not None else float(self.cfg.get("merchant_profit_margin", 0.0008))

    def _a_merchant(self, args, now, ins):
        # Zee 2026-11-04: the ice-cream girl must never sell at a loss. The page sends need_profit when the player clicks her; the engine
        # re-checks on its freshest quote and refuses ('not_profit') unless the coin is ahead by at least merchant_profit_margin.
        if args.get("need_profit"):
            r = self.round
            q = self._q()
            if r is not None and r.fill is not None and q is not None:
                res = r.banked_usd + r.side * (self._mark(r.side, q) - r.fill) * r.qty
                if res < self._girl_margin_usd(r) - 1e-9:
                    return False, "not_profit"
        return self._a_close("merchant", now, ins)

    def _a_eject(self, args, now, ins):
        return self._a_close("eject", now, ins)

    def _a_ack(self, args, now, ins):
        if self.phase != "settled":
            return False, "phase"
        self.round = None
        self.settlement = None
        self.aim = None
        self.phase = "lobby"
        self.settings["target"] = float(self.cfg["target_default"])       # a target is chosen for the next round only
        self.settings["coin_oz"] = float(self.cfg["coin_oz"])            # and the coins: back to one until the next volley
        self._preview_lit = None
        self._save_settings()
        return True, None

    def _a_kill(self, args, now, ins):
        """Close ONLY the game's own position(s) (by id) and lock the street until the next UTC day. The close is re-sent every
        kill_retry_s until the position is gone (_manage_round); after the kill no player trading action is accepted."""
        self.killed[self.mode] = utc_day(now)
        self._save_json("day.json", self.killed)
        self.settings["live_enabled"] = False
        self._save_json("live_signed.json", {"day": None})       # the kill switch also tears up today's signature
        r = self.round
        self._log("KILL SWITCH pressed - closing the game's own position (if any) and locking the day")
        if self.phase == "aiming":
            self.aim = None
            self.phase = "lobby"
        elif self.phase == "sending" and r is not None:
            r.kill_requested = True          # not sent yet: it never will be; outcome unknown: closed the moment it is found
            if r.unknown is not None:
                r.unknown["next_t"] = now    # look for it right away
        elif self.phase in ("open", "closing") and r is not None:
            r.kill_requested = True
            if not r.close_intent and not r.close_done and r.position_id is not None and r.final is None:
                r.close_intent = "kill"
                r.kill_retry_t = now + float(self.cfg["kill_retry_s"])
                r.pending = {"action": "kill", "since": now}
                self.phase = "closing"
                self._enqueue("kill", self._job_close, r, ins, "kill", front=True)
            # else: a close / settlement is in flight - if it does not end the position, the retry loop sends the kill close
        if r is not None and r.kill_requested:
            self._update_restore(r)          # a restarted game keeps closing it
        if callable(getattr(self.feed, "owned", None)) and getattr(self.feed, "can_trade", False):
            self._enqueue("kill_orphans", self._job_kill_orphans)
        self._lim_cache = (None, None)
        return True, None

    def _job_kill_orphans(self):
        """The kill switch also closes any OTHER still-open position the game itself opened (the orphan of a lost answer or of an
        earlier session). feed.owned() lists only ids the game opened or adopted as its own - Zee's positions are never in it."""
        try:
            owned = {str(x) for x in (self.feed.owned() or [])}
            fs = self.feed.state() or {}
        except Exception as e:  # noqa: BLE001
            self._log(f"kill: could not list the game's own positions ({type(e).__name__})")
            return
        with self.lock:
            r = self.round
            skip = {str(r.position_id)} if (r is not None and r.position_id is not None) else set()
        for p in fs.get("positions") or []:
            pid = str(p.get("id"))
            if pid not in owned or pid in skip:
                continue
            res = self._call(self.feed.close, p.get("id"), _num(p.get("qty")), timeout=5.0)
            self._log(f"kill: closed the game's orphan position {pid}" if res.get("ok") else
                      f"kill: the game's orphan position {pid} - close refused: {res.get('error')} (press the kill switch again)")

    # ------------------------------------------------------------------------------------------------------------------ broker jobs (worker thread; never under the engine lock while the broker talks)
    def _fresh_quote(self, kind):
        """The live quote at the moment a frame is sent. Returns (q, age_s)."""
        now = self.clock()
        if kind == "wooden":
            q = self.paper.quote()
            with self.lock:
                return (dict(q) if q else None), self._quote_age(now)
        try:
            fs = self.feed.state() or {}
        except Exception:  # noqa: BLE001
            fs = {}
        q = self._q(fs)
        with self.lock:
            if q is None:
                return None, None
            if q["ts"] is not None and self._last_tick_ts is not None and q["ts"] > self._last_tick_ts + 1e-9:
                return q, 0.0
            return q, self._quote_age(now)

    def _call(self, fn, *args, **kw):
        t0 = time.perf_counter()
        try:
            res = fn(*args, **kw)
            if not isinstance(res, dict):
                res = {"ok": bool(res), "error": None if res else "no answer"}
        except Exception as e:  # noqa: BLE001
            res = {"ok": False, "error": f"{type(e).__name__}: {scrub(e)}", "exception": True}
        res.setdefault("rtt_ms", round((time.perf_counter() - t0) * 1000.0, 1))
        if res.get("error") is not None:
            res["error"] = scrub(res["error"])
        return res

    def _place_uncertain(self, res):
        """A live place() whose outcome is NOT known - it may have filled: accepted without a position id, no answer, the socket went
        away after the send, or an exception inside the call. A definite broker refusal or a local rail (nothing sent) is not."""
        if res.get("position_id") is not None:
            return False
        if res.get("uncertain") or res.get("exception") or res.get("ok"):
            return True
        if res.get("definite") is not None:
            return not res.get("definite")
        err = str(res.get("error") or "").upper()
        return any(err.startswith(code) for code in UNCERTAIN_ERRORS)

    def _entry_sides_ok(self, side, sl, tp, q):
        """PROTOCOL rule 2: a long's stop below the bid and its target above the ask (mirror for a short), by min_sl_gap. A spread as
        wide as the stop distance would give a stop that is born crossed - PX accepts it and fills it at once."""
        gap = float(self.cfg["min_sl_gap"])
        mark = q["bid"] if side > 0 else q["ask"]
        far = q["ask"] if side > 0 else q["bid"]
        return side * (mark - sl) >= gap - 1e-9 and side * (tp - far) >= gap - 1e-9

    def _could_be_ours(self, p, side, qty, u, strict=True):
        """Could book position p be the game's uncertain order u? strict: our side, qty, symbol and BOTH the stop and the target we sent
        (adoption needs this - a hand-made trade never matches both to the cent). Not strict: the stop / target may also be missing
        (an order of ours whose protection was not linked) - such a position blocks the 'never filled' verdict but is never adopted."""
        try:
            if int(_num(p.get("side"), 0) or 0) != side:
                return False
        except (TypeError, ValueError):
            return False
        pq = _num(p.get("qty"))
        if pq is None or abs(pq - qty) > 1e-9:
            return False
        sym = p.get("symbol")
        if sym and str(sym).upper() != str(self.cfg["symbol"]).upper():
            return False
        psl, ptp = _num(p.get("sl")), _num(p.get("tp"))
        if strict:
            if psl is None or ptp is None or abs(psl - u["sl"]) > 0.006 or abs(ptp - u["tp"]) > 0.006:
                return False
            fn = getattr(self.feed, "matches_order", None)
            if callable(fn) and u.get("token") is not None:
                try:
                    return bool(fn(p, u["token"]))      # LiveFeed knows the broker's clock: opened after our send
                except Exception:  # noqa: BLE001
                    return False
        elif (psl is not None and abs(psl - u["sl"]) > 0.006) or (ptp is not None and abs(ptp - u["tp"]) > 0.006):
            return False
        ot = _num(p.get("open_time"))
        if ot is not None and self.mode != "live" and ot < u["t_send"] - 5.0:
            return False                                # sim / test feeds share our clock
        return True

    def _report(self, kind, since):
        """The deal history since `since` -> (rows, ok). ok False = the call FAILED (not 'no rows')."""
        broker = self._broker_for(kind)
        try:
            rows = broker.orders_report(since, timeout=5.0)
        except TypeError:
            try:
                rows = broker.orders_report(since)
            except Exception as e:  # noqa: BLE001
                self._log(f"orders_report failed: {scrub(e)}")
                return [], False
        except Exception as e:  # noqa: BLE001
            self._log(f"orders_report failed: {scrub(e)}")
            return [], False
        if rows is None:
            return [], False
        ok = getattr(rows, "ok", True) is not False
        return [dict(x) for x in rows if isinstance(x, dict)], ok

    @staticmethod
    def _report_protected_like(rows, pid, u):
        """A report row of position pid shows a protective order at exactly the stop or the target we sent."""
        for y in rows:
            if str(y.get("positionId")) != str(pid):
                continue
            typ = str(y.get("type", "")).upper()
            trig = _num(y.get("triggerPrice"), _num(y.get("trigger")))
            if trig is None:
                continue
            if (typ == "STOP_LOSS" and abs(trig - u["sl"]) <= 0.006) or (typ == "TAKE_PROFIT" and abs(trig - u["tp"]) <= 0.006):
                return True
        return False

    @staticmethod
    def _report_closed(rows, pid, qty, side):
        exit_word = "SELL" if side > 0 else "BUY"
        q = sum((_num(y.get("executedQty")) or _num(y.get("qty")) or 0.0) for y in rows
                if str(y.get("positionId")) == str(pid) and str(y.get("side", "")).upper() == exit_word and
                str(y.get("status", "EXECUTED")).upper() in ("EXECUTED", "FILLED", ""))
        return q + 1e-9 >= qty

    def _feed_adopt(self, pid):
        fn = getattr(self.feed, "adopt", None)
        if callable(fn):
            try:
                fn(pid)
            except Exception as e:  # noqa: BLE001
                self._log(f"feed.adopt({pid}) failed: {type(e).__name__}")

    def _job_shoot(self, r, ins):
        broker = self._broker_for(r.kind)
        q, age = self._fresh_quote(r.kind)
        with self.lock:
            if self.round is not r or self.phase != "sending":
                return
            if r.kill_requested:                         # the kill switch was pressed before the order left: it never leaves
                self._shoot_failed(r, ins, "killed", self.clock(), broker_said=False)
                return
        if q is None or age is None or age > float(self.cfg["feed_stale_s"]):
            with self.lock:
                self._shoot_failed(r, ins, "stale_quote", self.clock(), broker_said=False)
            return
        side = r.side
        entry_ref = q["ask"] if side > 0 else q["bid"]
        u97 = getattr(r, "u97", None)
        if u97:                                          # the 97.7% setting: the stop beyond the retracement's extreme + 19 pips, from this quote
            r.stop_dist = max((entry_ref - u97["extreme"]) * side, 0.0) + float(self._u97("u97_beyond_pips")) * float(self._u97("u97_pip"))
            r.stop_dist = min(r.stop_dist, float(self._u97("u97_max_stop_pips")) * float(self._u97("u97_pip")))   # protects a round whose position id never comes back
            r.risk_usd = round(r.coin_oz * r.stop_dist, 6)
        sl = r2(entry_ref - side * r.stop_dist)          # SL/TP from the live quote at send time (P0 lesson)
        tp = r2(entry_ref + side * r.target)
        if not self._entry_sides_ok(side, sl, tp, q):    # the spread would put the stop (or the target) on the wrong side: duck
            with self.lock:
                ins["broker"] = {"ok": False, "error": "spread", "sent": None, "quote": q, "sl": sl, "tp": tp}
                self._shoot_failed(r, ins, "spread", self.clock(), broker_said=False)
            return
        before = set()
        if r.kind == "live":                             # the book right before the send (not the last step's cached copy)
            try:
                before = {str(p.get("id")) for p in (self.feed.state() or {}).get("positions") or []}
            except Exception:  # noqa: BLE001
                before = {str(p.get("id")) for p in self._positions("live")}
        with self.lock:
            ins["broker"] = {"sent": {"side": side, "qty": r.qty0, "sl": sl, "tp": tp, "quote": q}}
        t_send = self.clock()
        res = self._call(broker.place, side, r.qty0, sl, tp, timeout=5.0)
        if (r.kind == "live" and res.get("position_id") is None and res.get("resolve_token") is not None and
                callable(getattr(self.feed, "resolve", None))):
            # LiveFeed: the order was accepted (or the answer was lost) but the position id is not known yet - let the feed look once
            rr = self._call(self.feed.resolve, res["resolve_token"], timeout=1.0)
            if rr.get("position_id") is not None:
                self._log(f"place: position {rr.get('position_id')} resolved after '{res.get('error') or 'no id yet'}'")
                res = dict(res, ok=True, error=None, position_id=rr.get("position_id"), definite=True, uncertain=False,
                           fill_price=_num(rr.get("fill_price")) if rr.get("fill_price") is not None else res.get("fill_price"))
        now = self.clock()
        with self.lock:
            ins["broker"].update({k: res.get(k) for k in ("ok", "error", "rtt_ms", "order_id", "position_id", "fill_price",
                                                          "definite", "uncertain")})
            if res.get("ok") and res.get("position_id") is not None:
                self._opened(r, res, q, entry_ref, sl, tp, now)
            elif r.kind == "live" and self._place_uncertain(res):
                self._shoot_unknown(r, ins, res, before, sl, tp, q, entry_ref, t_send, now)
            else:
                self._shoot_failed(r, ins, res.get("error") or "refused", now, broker_said=True)

    def _shoot_unknown(self, r, ins, res, before, sl, tp, q, entry_ref, t_send, now):
        """The order may have filled: the round stays in "sending" (the Banker frozen mid-throw), no new shot is possible, and
        _job_resolve keeps looking until it finds the position or the deal history proves there was no fill."""
        why = scrub(res.get("error") or "accepted, no position id yet")
        r.unknown = {"since": now, "t_send": t_send, "token": res.get("resolve_token"), "before": sorted(before), "sl": sl, "tp": tp,
                     "order_id": res.get("order_id"), "accepted": bool(res.get("ok") or res.get("accepted")), "error": why,
                     "q": dict(q), "entry_ref": entry_ref, "next_t": now, "queued": False, "tries": 0,
                     "nonce": ins.get("nonce") if ins else None}
        r.pending = {"action": "resolve", "since": now}
        r.notes.append({"t": now, "note": f"the order's outcome is not known ({why}): frozen until the broker shows the fill or "
                                          f"proves there was none"})
        self._log(f"round {r.id}: shot UNCERTAIN ({why}) - the round stays frozen (no new shot) until the broker says")
        self._update_restore(r)

    def _job_resolve(self, r):
        """An order whose outcome is not known: find its position (the feed's resolver; the book with the exact stop and target we
        sent; the deal history - our order id, or our stop / target on a new position) or prove there was no fill. A short job,
        re-queued by _manage_round (there is ONE broker worker: a long wait here would hold up the kill switch)."""
        with self.lock:
            if r.unknown is None or self.round is not r or self.phase != "sending":
                if r.unknown is not None:
                    r.unknown["queued"] = False
                return
            u = dict(r.unknown)
        c = self.cfg
        side, qty = r.side, r.qty0
        before = {str(x) for x in (u.get("before") or [])}
        found, fill, how = None, None, None
        if u.get("token") is not None and callable(getattr(self.feed, "resolve", None)):
            rr = self._call(self.feed.resolve, u["token"], timeout=0.3)
            if rr.get("position_id") is not None:
                found, fill, how = rr.get("position_id"), _num(rr.get("fill_price")), "the feed's resolver"
        try:
            fs = self.feed.state() or {}
        except Exception:  # noqa: BLE001
            fs = {}
        book = [p for p in (fs.get("positions") or []) if str(p.get("id")) not in before]
        book_ok = bool(fs.get("ok")) and fs.get("book_fresh", True) is not False and fs.get("account_ok", True) is not False
        exact = [p for p in book if self._could_be_ours(p, side, qty, u, strict=True)]
        maybe = [p for p in book if self._could_be_ours(p, side, qty, u, strict=False)]
        if found is None and len(exact) == 1:
            found, fill, how = exact[0].get("id"), _num(exact[0].get("open_price")), "the book (our exact stop and target)"
        verdict, why_wait = None, None
        if found is None:
            rows, report_ok = self._report(r.kind, u["t_send"] - 60.0)      # a clock-safe margin: older closed rows never block
            if not report_ok:
                why_wait = "the deal history cannot be read right now"
            else:
                done = ("EXECUTED", "FILLED", "")
                oid = u.get("order_id")
                hit = [x for x in rows if oid is not None and str(x.get("id")) == str(oid)]
                if hit and str(hit[0].get("status", "EXECUTED")).upper() in done and hit[0].get("positionId") is not None:
                    found, fill, how = hit[0].get("positionId"), _num(hit[0].get("executedPrice")), "the deal history (our order id)"
                elif hit and str(hit[0].get("status", "")).upper() in ("REJECTED", "CANCELLED", "CANCELED", "EXPIRED"):
                    verdict = "none"
                else:
                    word = "BUY" if side > 0 else "SELL"
                    mk = [x for x in rows if str(x.get("type", "")).upper() == "MARKET" and str(x.get("side", "")).upper() == word
                          and str(x.get("status", "EXECUTED")).upper() in done and str(x.get("positionId")) not in before
                          and abs((_num(x.get("executedQty")) or _num(x.get("qty")) or 0.0) - qty) < 1e-9]
                    conf = [x for x in mk if self._report_protected_like(rows, x.get("positionId"), u)]
                    if len(conf) == 1:
                        found, fill, how = conf[0].get("positionId"), _num(conf[0].get("executedPrice")), "the deal history (our stop / target)"
                    else:
                        open_ids = {str(p.get("id")) for p in fs.get("positions") or []}
                        maybe_ids = {str(p.get("id")) for p in maybe}
                        risky = [str(x.get("positionId")) for x in mk
                                 if x.get("positionId") is not None                                         # 2026-11-06: PrimeXBT sometimes logs our fast
                                 # round with NO position id (4 rounds froze in 2 days). It cannot be matched; open exposure still shows in the book ('maybe'
                                 # below blocks), and diamond rounds carry a broker stop <= u97_max_stop_pips - so a book with no new position = filled + closed
                                 and not self._report_closed(rows, x.get("positionId"), qty, side)          # closed: no exposure left
                                 and not (str(x.get("positionId")) in open_ids and str(x.get("positionId")) not in maybe_ids)]
                        proof_s = float(c["unknown_proof_accepted_s"] if u.get("accepted") else c["unknown_proof_s"])
                        if risky or maybe_ids:
                            why_wait = (f"a new position that could be the game's cannot be told apart from another one "
                                        f"({', '.join(sorted(set(risky) | maybe_ids))}) - check the page")
                        elif not book_ok:
                            why_wait = "the book is not fresh"
                        elif self.clock() - u["t_send"] >= proof_s:
                            verdict = "none"
        if found is not None:
            self._feed_adopt(found)                      # LiveFeed: the game opened it (proved above) - it may manage it
        now = self.clock()
        with self.lock:
            uu = r.unknown
            if uu is None or self.round is not r or self.phase != "sending":
                return
            uu["queued"] = False
            uu["tries"] = int(uu.get("tries") or 0) + 1
            if found is not None:
                self._log(f"round {r.id}: the uncertain order DID fill - position {found} found in {how}")
                r.notes.append({"t": now, "note": f"the uncertain order filled: position {found} (found in {how})"})
                res = {"ok": True, "error": None, "position_id": found, "fill_price": fill, "order_id": uu.get("order_id"),
                       "sl": uu.get("sl"), "tp": uu.get("tp"), "adopted": True, "rtt_ms": None}
                q = uu.get("q") or self._q() or {"bid": r.last_mark or 0.0, "ask": r.last_mark or 0.0}
                er = uu.get("entry_ref") if uu.get("entry_ref") is not None else (q["ask"] if r.side > 0 else q["bid"])
                self._opened(r, res, q, er, uu.get("sl"), uu.get("tp"), now)
                return
            if verdict == "none":
                self._log(f"round {r.id}: the deal history proves the uncertain order never filled - the note goes back")
                r.notes.append({"t": now, "note": "the deal history shows no fill for the uncertain order"})
                r.unknown = None
                ins = next((i for i in r.instructions if uu.get("nonce") and i.get("nonce") == uu.get("nonce")), None)
                self._shoot_failed(r, ins or {}, "not_filled", now, broker_said=True)
                return
            if why_wait and why_wait != uu.get("why_wait"):
                self._log(f"round {r.id}: order outcome still unknown - {why_wait}")
                r.notes.append({"t": now, "note": f"order outcome unknown: {why_wait}"})
            uu["why_wait"] = why_wait
            uu["next_t"] = now + min(5.0, 0.5 * (2 ** min(uu["tries"], 4)))

    def _opened(self, r, res, q, entry_ref, sl_sent, tp_sent, now):
        side = r.side
        r.unknown = None
        r.position_id = res.get("position_id")
        r.order_id = res.get("order_id")
        pos = self._find_pos(self._positions(r.kind), r.position_id)
        fill = _num(res.get("fill_price"))
        if fill is None and pos is not None:
            fill = _num(pos.get("open_price"))
        if fill is None:
            fill = entry_ref
            r.notes.append({"t": now, "note": "fill price not reported; using the quote at send"})
        r.fill = r2(fill)
        bsl = _num(res.get("sl")) if res.get("sl") is not None else (_num(pos.get("sl")) if pos else None)
        btp = _num(res.get("tp")) if res.get("tp") is not None else (_num(pos.get("tp")) if pos else None)
        r.sl0 = r2(bsl if bsl is not None else sl_sent)
        r.tp0 = r2(btp if btp is not None else tp_sent)
        r.sl, r.tp = r.sl0, r.tp0
        r.quote_at_send = {"bid": q["bid"], "ask": q["ask"], "ts": q.get("ts")}
        r.entry_ref = entry_ref
        r.spread_entry = round(q["ask"] - q["bid"], 4)
        r.opened_t = now
        r.pending = None
        r.sync_hold_until = now + 2.0
        self.phase = "open"
        self.aim = None
        self._emit({"type": "fill", "side": side, "price": r.fill, "qty": r.qty0})
        r.fills.append({"t": now, "what": "open", "side": side, "qty": r.qty0, "price": r.fill, "quote": r.quote_at_send,
                        "rtt_ms": res.get("rtt_ms")})
        self._bite(r, round(r.spread_entry * r.qty0, 6), "spread", now)
        adverse = side * (r.fill - entry_ref)
        if adverse > 0.0049:
            r.slippage_entry = round(adverse * r.qty0, 6)
            self._bite(r, r.slippage_entry, "slippage", now)
        if r.twin_invited:
            self._start_twin(r, now)
        r.ghosts = self._ghost_paths(exclude=r.id)
        r.stakes_lit = (side, set(self._lit_stakes(side, now)))
        if r.kind == "live":
            self._save_json(f"open_round_{self.mode}.json", r.to_restore())
        self._log(f"round {r.id} OPEN ({r.kind}) {'long' if side > 0 else 'short'} {r.qty0} oz @ {r.fill} sl {r.sl0} tp {r.tp0}"
                  f" pos {r.position_id}")
        if r.kill_requested:
            r.close_intent = "kill"
            r.pending = {"action": "kill", "since": now}
            self.phase = "closing"
            self._enqueue("kill", self._job_close, r, None, "kill", front=True)

    def _shoot_failed(self, r, ins, why, now, broker_said):
        why = scrub(why)
        self._log(f"shot refused: {why}")
        if broker_said:
            self._emit({"type": "refused_broker", "action": "shoot", "why": why})
        else:
            self._emit({"type": "refused", "nonce": ins.get("nonce") if ins else None, "action": "shoot", "why": why})
        if self.round is r:
            self.round = None
        self.pre_instr = (r.instructions or [])[-50:]
        a = self.aim
        if a is not None:
            a["refusals"] += 1
            a["last_refusal_t"] = now
        if a is None or r.kill_requested or a["refusals"] >= int(self.cfg["shoot_refusals_max"]):
            self.aim = None
            self.phase = "lobby"          # three refusals: the note goes back in the pocket
        else:
            self.phase = "aiming"

    def _bite(self, r, usd, why, now):
        if usd is None or usd <= 0:
            return
        r.rat.append({"t": now, "usd": round(usd, 6), "why": why})
        self._emit({"type": "rat", "usd": round(usd, 6), "why": why})

    def _sl_valid(self, r, new_sl, q):
        """Local validation before sending: a long's stop must stay below the bid by min_sl_gap (mirror for a short) and only tighten."""
        if q is None:
            return "stale_quote"
        mark = self._mark(r.side, q)
        if r.side * (mark - new_sl) < float(self.cfg["min_sl_gap"]) - 1e-9:
            return "too_close"
        if r.sl is not None and r.side * (new_sl - r.sl) < TICK - 1e-9:
            return "no_tighten"
        return None

    def _job_sl(self, r, ins, action, new_sl, anvil_kind):
        evtype = "wall" if action == "wall" else "anvil"
        broker = self._broker_for(r.kind)
        q, age = self._fresh_quote(r.kind)
        with self.lock:
            if self.round is not r or self.phase != "open" or r.position_id is None:
                r.pending = None
                r.anvil_pending = False
                return
            why = "stale_quote" if (age is None or age > float(self.cfg["feed_stale_s"])) else self._sl_valid(r, new_sl, q)
            if why:
                self._sl_refused(r, ins, action, evtype, why, broker_said=False)
                return
            pid = r.position_id
        res = self._call(broker.set_protective, pid, "STOP_LOSS", new_sl, timeout=5.0)
        now = self.clock()
        with self.lock:
            if ins is not None:
                ins["broker"] = {"ok": res.get("ok"), "error": res.get("error"), "rtt_ms": res.get("rtt_ms"), "sent": {"sl": new_sl}}
            if res.get("ok"):
                r.sl = new_sl
                r.anvil_kind = anvil_kind
                if action == "wall":
                    r.walls.append(new_sl)
                else:
                    r.anvil_moves += 1
                r.pending = None
                r.anvil_pending = False
                r.sync_hold_until = now + 2.5
                a, b, _, _ = ladder(r.side, r.fill, r.sl0, r.tp0, r.banked_usd, r.qty, r.qty0)
                self._emit({"type": evtype, "ok": True, "x": xp(a, b, new_sl)})
                self._update_restore(r)
            else:
                self._sl_refused(r, ins, action, evtype, res.get("error") or "refused", broker_said=True)

    def _sl_refused(self, r, ins, action, evtype, why, broker_said):
        now = self.clock()
        r.pending = None
        r.anvil_pending = False
        r.last_refusal = {"action": action, "why": why, "t": now}
        a, b, _, _ = ladder(r.side, r.fill, r.sl0, r.tp0, r.banked_usd, r.qty, r.qty0)
        if evtype == "haggle":
            self._emit({"type": "haggle", "ok": False})
        else:
            self._emit({"type": evtype, "ok": False, "x": xp(a, b, r.sl)})
        if broker_said:
            self._emit({"type": "refused_broker", "action": action, "why": why})
        self._log(f"{action} refused: {why}")

    def _job_haggle(self, r, ins, new_sl, new_tp):
        broker = self._broker_for(r.kind)
        q, age = self._fresh_quote(r.kind)
        with self.lock:
            if self.round is not r or self.phase != "open" or r.position_id is None:
                r.pending = None
                r.anvil_pending = False
                return
            why = "stale_quote" if (age is None or age > float(self.cfg["feed_stale_s"])) else self._sl_valid(r, new_sl, q)
            if why:
                self._sl_refused(r, ins, "haggle", "haggle", why, broker_said=False)
                return
            pid = r.position_id
        res1 = self._call(broker.set_protective, pid, "STOP_LOSS", new_sl, timeout=5.0)          # the rope first
        res2 = self._call(broker.set_protective, pid, "TAKE_PROFIT", new_tp, timeout=5.0) if res1.get("ok") else None
        now = self.clock()
        with self.lock:
            if ins is not None:
                ins["broker"] = {"sl": {k: res1.get(k) for k in ("ok", "error", "rtt_ms")}, "sent": {"sl": new_sl, "tp": new_tp},
                                 "tp": {k: res2.get(k) for k in ("ok", "error", "rtt_ms")} if res2 else None}
            if not res1.get("ok"):
                self._sl_refused(r, ins, "haggle", "haggle", res1.get("error") or "refused", broker_said=True)
                return
            r.sl = new_sl
            r.sync_hold_until = now + 2.5
            if res2 is None or not res2.get("ok"):
                r.anvil_kind = "stake"
                r.notes.append({"t": now, "note": "haggle: the stop moved but the target was refused"})
                self._sl_refused(r, ins, "haggle", "haggle", (res2 or {}).get("error") or "refused", broker_said=True)
                self._update_restore(r)
                return
            if r.haggles == 0 and r.anvil_moves > 0:
                r.anvil_before_haggle = True
            r.tp = new_tp
            r.haggles += 1
            r.anvil_kind = "haggle"
            r.pending = None
            r.anvil_pending = False
            self._emit({"type": "haggle", "ok": True})
            self._update_restore(r)

    def _job_machete(self, r, ins, close_qty):
        broker = self._broker_for(r.kind)
        q, _age = self._fresh_quote(r.kind)
        with self.lock:
            if self.round is not r or self.phase != "open" or r.position_id is None:
                r.pending = None
                return
            pid = r.position_id
        ref = self._mark(r.side, q)
        res = self._call(broker.close, pid, close_qty, timeout=5.0)
        now = self.clock()
        with self.lock:
            if ins is not None:
                ins["broker"] = {k: res.get(k) for k in ("ok", "error", "rtt_ms", "fill_price")}
                ins["broker"]["sent"] = {"qty": close_qty}
            r.pending = None
            if not res.get("ok"):
                err = str(res.get("error") or "")
                if (res.get("definite") is False or res.get("exception") or
                        any(err.upper().startswith(code) for code in UNCERTAIN_ERRORS)):
                    r.machete_hold_until = now + 10.0      # it may have cut: no second cut until the book shows the size
                    r.notes.append({"t": now, "note": f"the machete's answer was lost ({scrub(err)}): waiting for the book"})
                r.last_refusal = {"action": "machete", "why": res.get("error") or "refused", "t": now}
                self._emit({"type": "machete", "ok": False, "usd": 0.0})
                self._emit({"type": "refused_broker", "action": "machete", "why": res.get("error") or "refused"})
                return
            price = _num(res.get("fill_price"))
            if price is None:
                price = ref if ref is not None else r.last_mark
            rpl = _num(res.get("rpl"))
            part = rpl if rpl is not None else r.side * (price - r.fill) * close_qty
            r.banked_usd = round(r.banked_usd + part, 6)
            r.qty = round(r.qty - close_qty, 2)
            r.machete_done = True
            r.sync_hold_until = now + 2.5
            r.fills.append({"t": now, "what": "machete", "qty": close_qty, "price": price, "quote_ref": ref, "rtt_ms": res.get("rtt_ms")})
            if ref is not None:
                adv = r.side * (ref - price)
                if adv > 0.0049:
                    r.slippage_partial = round(r.slippage_partial + adv * close_qty, 6)
                    self._bite(r, round(adv * close_qty, 6), "slippage", now)
            usd = round(r.banked_usd + r.side * (r.sl - r.fill) * r.qty, 6)          # the round's worst remaining outcome
            r.golden = {"price": r.sl, "usd": usd}
            self._emit({"type": "machete", "ok": True, "usd": round(part, 6)})
            self._update_restore(r)

    def _job_close(self, r, ins, intent):
        broker = self._broker_for(r.kind)
        q, _age = self._fresh_quote(r.kind)
        with self.lock:
            if self.round is not r or r.final is not None or r.position_id is None or r.close_done:
                return
            pid, qty = r.position_id, r.qty
        ref = self._mark(r.side, q)
        res = self._call(broker.close, pid, qty, timeout=5.0)
        now = self.clock()
        gone = False
        if not res.get("ok"):
            err = str(res.get("error") or "")
            if r.kind == "wooden":
                gone = not self._has(self.paper, pid)
            else:
                try:
                    fs = self.feed.state() or {}
                except Exception:  # noqa: BLE001
                    fs = {}
                gone = "NOT_FOUND" in err.upper() or (self._find_pos(fs.get("positions") or [], pid) is None and bool(fs.get("ok")) and
                                                      fs.get("book_fresh", True) is not False and fs.get("account_ok", True) is not False)
        with self.lock:
            if ins is not None:
                ins["broker"] = {k: res.get(k) for k in ("ok", "error", "rtt_ms", "fill_price")}
                ins["broker"]["sent"] = {"qty": qty}
            if res.get("ok"):
                r.close_ref = ref
                r.close_done = True
                r.fills.append({"t": now, "what": intent, "qty": qty, "price": _num(res.get("fill_price")), "quote_ref": ref,
                                "rtt_ms": res.get("rtt_ms")})
                if r.settling:
                    r.settle_next_t = now
                self._begin_settle(r, now, immediate=True)
            elif gone:
                self._log(f"{intent}: the position had already closed ({res.get('error')}) - settling from the report")
                if r.settling:
                    r.settle_next_t = now
                self._begin_settle(r, now, immediate=True)
            else:
                why = res.get("error") or "refused"
                r.last_refusal = {"action": intent, "why": why, "t": now}
                self._emit({"type": "refused_broker", "action": intent, "why": why})
                if r.kill_requested:
                    r.kill_retry_t = now + float(self.cfg["kill_retry_s"])
                    self._log(f"{intent} refused: {why} - the kill switch sends it again in {self.cfg['kill_retry_s']} s, until it is closed")
                else:
                    self._log(f"{intent} refused: {why}")
                r.close_intent = None
                r.pending = None
                if self.phase == "closing" and not r.settling:
                    self.phase = "open"

    def _begin_settle(self, r, now, immediate=False):
        if r.settling or r.final is not None:
            return
        r.settling = True
        r.settle_started = now
        r.settle_next_t = now if immediate else now + 0.3
        r.pending = r.pending or {"action": "settle", "since": now}
        self.phase = "closing"
        if immediate and not r.settle_queued:
            r.settle_queued = True
            self._enqueue("settle", self._job_settle, r)

    def _job_settle(self, r):
        """Settle from the deal history (REQUIREMENTS 5.4: "read from the deal history, never computed"). A live round is finalized only
        when the report shows closing rows for its whole quantity; a FAILED report read is retried (never counted toward a timeout);
        a book that lists the position again ends a false alarm; until then the round stays in "closing" (settlement pending) and no
        new round can start."""
        # PX filters fromExecutedAt on ITS clock and ours may run ahead: keep a wide margin (rows are matched by positionId anyway;
        # LiveFeed pages through the report, so a busy account cannot truncate our rows)
        since = (r.shot_t or r.opened_t or self.clock()) - 300.0
        rows, report_ok = self._report(r.kind, since)
        try:
            fs = self.feed.state() or {}
        except Exception:  # noqa: BLE001
            fs = {}
        if r.kind == "wooden":
            still_open = self._has(self.paper, r.position_id)
            book_ok = True
        else:
            still_open = self._find_pos(fs.get("positions") or [], r.position_id) is not None
            book_ok = bool(fs.get("ok")) and fs.get("book_fresh", True) is not False and fs.get("account_ok", True) is not False
        balance = _num((fs.get("account") or {}).get("balance"))
        now = self.clock()
        c = self.cfg
        with self.lock:
            r.settle_queued = False
            if r.final is not None or self.round is not r:
                return
            if not report_ok:
                r.settle_fail_n += 1
                r.settle_next_t = now + min(5.0, 0.5 * (2 ** min(r.settle_fail_n, 4)))
                if r.settle_fail_n in (1, 10) or r.settle_fail_n % 120 == 0:
                    self._log(f"round {r.id}: the deal history cannot be read (attempt {r.settle_fail_n}) - settlement waits for it")
                return
            r.settle_fail_n = 0
            ours = [dict(x) for x in rows if isinstance(x, dict) and str(x.get("positionId")) == str(r.position_id) and
                    str(x.get("status", "EXECUTED")).upper() in ("EXECUTED", "FILLED", "")]
            ours = _chrono(ours)
            open_row = None
            for x in ours:
                if (r.order_id is not None and str(x.get("id")) == str(r.order_id)) or (
                        open_row is None and str(x.get("type", "")).upper() == "MARKET" and
                        (str(x.get("side", "")).upper() in ("BUY", "1") if r.side > 0 else str(x.get("side", "")).upper() in ("SELL", "-1"))):
                    open_row = x
                    if r.order_id is not None and str(x.get("id")) == str(r.order_id):
                        break
            closes = [x for x in ours if x is not open_row and (_num(x.get("executedQty"), None) or _num(x.get("qty"), 0.0) or 0.0) > 0]
            closed_qty = round(sum((_num(x.get("executedQty"), None) or _num(x.get("qty"), 0.0) or 0.0) for x in closes), 2)
            waited = now - (r.settle_started or now)
            if closes and closed_qty + 1e-9 >= r.qty0:
                self._finalize(r, ours, closes, now, balance)        # the deal history shows the whole close: the truth
                return
            if still_open and book_ok and not r.close_done:
                # false alarm: the book dropped our row for a moment (or lists it again) and no close of ours went through
                r.settling = False
                r.settle_next_t = None
                r.vanish_since = None
                r.pending = None
                r.close_intent = None
                if self.phase == "closing":
                    self.phase = "open"
                return
            if r.kind == "wooden":
                if waited < float(c["settle_timeout_s"]):
                    r.settle_next_t = now + 0.5
                    return
                self._finalize(r, ours, closes, now, balance)        # the paper book (the only one that could ever be estimated)
                return
            if waited < float(c["settle_timeout_s"]):
                r.settle_next_t = now + 0.5
                return
            if not closes and not r.seen and not r.close_intent and not r.kill_requested and not still_open:
                # never seen in the book and no close in the report: we cannot prove it closed - keep it open (eject / kill still
                # work: a close on a gone position answers POSITION_NOT_FOUND and settles then)
                r.settling = False
                r.settle_next_t = None
                r.blind = True
                r.pending = None if (r.pending or {}).get("action") == "settle" else r.pending
                r.notes.append({"t": now, "note": "the book never showed our position and the report has no close - kept open"})
                self._log(f"round {r.id}: position {r.position_id} not visible and not reported closed - keeping the round open")
                if self.phase == "closing":
                    self.phase = "open"
                return
            # a live round is NEVER settled from invented numbers: settlement pending, keep reading the deal history
            if not r.settle_waiting_logged:
                r.settle_waiting_logged = True
                self._log(f"round {r.id}: settlement pending - the deal history shows {closed_qty} of {r.qty0} oz closed"
                          f"{' and the book still lists the position' if still_open else ''}; new rounds wait")
                r.notes.append({"t": now, "note": f"settlement pending after {waited:.0f} s: {closed_qty} of {r.qty0} oz in the report"})
            r.settle_next_t = now + float(c["settle_poll_slow_s"])

    def _finalize(self, r, ours, closes, now, balance=None):
        c = self.cfg
        side = r.side
        last = closes[-1] if closes else None
        typ = str((last or {}).get("type", "")).upper()
        exit_px = _num((last or {}).get("executedPrice"))
        fee = sum(abs(_num(x.get("fee"), 0.0) or 0.0) for x in ours)
        financing = sum(abs(_num(x.get("financing"), 0.0) or 0.0) for x in ours)
        if closes:
            total = 0.0
            for x in closes:
                rpl = _num(x.get("rpl"))
                if rpl is None:
                    q_ = _num(x.get("executedQty"), None) or _num(x.get("qty"), 0.0) or 0.0
                    rpl = side * ((_num(x.get("executedPrice"), r.fill) or r.fill) - r.fill) * q_
                total += rpl
            result = round(total - fee, 6)
            partials = closes[:-1]
            if partials:
                r.banked_usd = round(sum((_num(x.get("rpl"), 0.0) or 0.0) for x in partials), 6)
        else:
            r.estimated = True
            mark = r.last_mark if r.last_mark is not None else r.fill
            exit_px = mark
            result = round(r.banked_usd + side * (mark - r.fill) * r.qty, 6)
            if r.tp is not None and side * (mark - r.tp) >= -0.05 and not r.close_intent:
                typ, exit_px = "TAKE_PROFIT", r.tp
                result = round(r.banked_usd + side * (r.tp - r.fill) * r.qty, 6)
            elif r.sl is not None and side * (mark - r.sl) <= 0.05 and not r.close_intent:
                typ, exit_px = "STOP_LOSS", r.sl
                result = round(r.banked_usd + side * (r.sl - r.fill) * r.qty, 6)
            r.notes.append({"t": now, "note": "settled without report rows - numbers estimated from the last quote"})
        if exit_px is None:
            exit_px = r.last_mark if r.last_mark is not None else r.fill
        sl_trig = _num((last or {}).get("trigger")) or _num((last or {}).get("triggerPrice")) or r.sl
        if typ == "TAKE_PROFIT":
            outcome = "buyer"
        elif typ == "STOP_LOSS":
            outcome = "barrel" if side * (sl_trig - exit_px) > float(c["barrel_gap"]) + 1e-9 else "anvil"
        elif typ in ("MARKET", ""):
            intent = {"kill_retry": "kill", "protect": "session"}.get(r.close_intent, r.close_intent)
            outcome = intent if intent in ("merchant", "eject", "session", "kill") else "outside"
        else:
            outcome = "outside"
        if r.kill_requested and outcome == "outside":
            outcome = "kill"
        a, b, _, _ = ladder(side, r.fill, r.sl0, r.tp0, r.banked_usd, r.qty, r.qty0)
        last_qty = (_num((last or {}).get("executedQty"), None) or _num((last or {}).get("qty"), None) or r.qty) if last else r.qty
        exit_slip = 0.0
        if typ == "STOP_LOSS":
            exit_slip = max(0.0, side * (sl_trig - exit_px)) * last_qty
        elif typ == "TAKE_PROFIT" and r.tp is not None:
            exit_slip = max(0.0, side * (r.tp - exit_px)) * last_qty
        elif r.close_ref is not None:
            exit_slip = max(0.0, side * (r.close_ref - exit_px)) * last_qty
        exit_slip = round(exit_slip, 6) if exit_slip > 0.0049 * last_qty else 0.0
        self._bite(r, exit_slip, "slippage", now)
        self._bite(r, round(fee, 6), "fee", now)
        self._bite(r, round(financing, 6), "financing", now)
        costs = {"spread_usd": round((r.spread_entry or 0.0) * r.qty0, 6),
                 "slippage_usd": round(r.slippage_entry + r.slippage_partial + exit_slip, 6),
                 "fee_usd": round(fee, 6), "financing_usd": round(financing, 6)}
        chasm = sorted([xp(a, b, sl_trig), xp(a, b, exit_px)]) if outcome == "barrel" else None
        balance_after = balance if balance is not None else _num((self.fs.get("account") or {}).get("balance"))
        r.closed_t = now
        r.report_rows = [sanitize(x) for x in ours][-20:]
        r.final = {"exit": r2(exit_px), "a": a, "b": b, "result_usd": result, "outcome": outcome}
        r.pending = None
        r.anvil_pending = False
        r.settling = False
        twin_res = r.twin["result_usd"] if (r.twin and r.twin.get("state") == "done") else None
        value = round(r.risk_usd + result, 6)           # the coin's final value = stake + result (on a TP fill: the Buyer's tag)
        st = {"id": r.id, "kind": r.kind, "side": side, "outcome": outcome, "result_usd": result,
              "result_text": money(result, r.risk_usd, signed=True), "value_usd": value, "value_text": money(value, r.risk_usd),
              "costs": costs, "fill": r.fill, "exit": r2(exit_px),
              "qty0": r.qty0, "age_s": round(now - (r.opened_t or now), 1), "chasm": chasm, "balance_after": balance_after,
              "twin_result_usd": twin_res, "would_have_usd": None, "plain": self._plain(r, outcome, exit_px, result, costs),
              "t": round(now, 3)}
        if r.estimated:
            st["estimated"] = True
        r.settlement = st
        self.settlement = st
        self.phase = "settled"
        self._emit({"type": "settled", "outcome": outcome})
        self._log(f"round {r.id} SETTLED {outcome} {money(result, r.risk_usd, True)} exit {r2(exit_px)}")
        if outcome in ("merchant", "eject"):
            self._start_counterfactual(r, now)
        self._write_round_log(r)
        self._refresh_summary(r)
        if r.kind == "live":
            self._delete_state(f"open_round_{self.mode}.json")

    def _update_restore(self, r):
        if r.kind == "live" and r.final is None:
            self._save_json(f"open_round_{self.mode}.json", r.to_restore())

    def _plain(self, r, outcome, exit_px, result, costs):
        risk = r.risk_usd
        long_ = r.side > 0
        how = {"buyer": "the take profit sold it" if long_ else "the take profit bought it back",
               "anvil": "the stop loss sold it" if long_ else "the stop loss bought it back",
               "barrel": "the stop loss filled through a gap", "merchant": "you sold it at market" if long_ else "you bought it back at market",
               "eject": "you ejected at market", "session": "the session close sold it" if long_ else "the session close bought it back",
               "kill": "the kill switch closed it", "outside": "it was closed outside the game"}[outcome]
        if outcome == "session" and r.close_intent == "protect":
            how = "the game closed it at market because the broker held no stop or target for it"
        verb = "Bought" if long_ else "Sold"
        s = (f"{verb} {r.qty0:.2f} oz of gold at {r.fill:,.2f}; {how} at {exit_px:,.2f}: {money(result, risk, True)} "
             f"after a {money(costs['spread_usd'], risk)} spread.")
        if r.machete_done:
            s += f" Half was banked early for {money(r.banked_usd, risk, True)}."
        if r.kind == "wooden":
            s = "Wooden round, no order sent: " + s
        return s

    # ------------------------------------------------------------------------------------------------------------------ logs, summaries, tallies
    def _round_log(self, r):
        st = r.settlement or {}
        qs = dict(r.qsum)
        ssum = qs.pop("spread_sum", 0.0)
        qs["spread_avg"] = round(ssum / qs["n"], 4) if qs.get("n") else None
        tw = None
        if r.twin:
            sh = r.twin
            tw = {"state": sh["state"], "result_usd": sh["result_usd"], "exit": sh["exit"], "sl_final": sh["sl"], "moves": sh.get("moves", 0),
                  "how": sh.get("how")}
        fin = r.final or {}
        return sanitize({
            "v": 1, "id": r.id, "mode": r.mode, "kind": r.kind, "side": r.side, "qty0": r.qty0, "coin_oz": r.coin_oz,
            "stop_dist": r.stop_dist, "target": r.target, "risk_usd": r.risk_usd, "shot_t": r.shot_t, "opened_t": r.opened_t,
            "closed_t": r.closed_t, "patience_s": r.patience_s, "quick": (r.patience_s or 0) < float(self.cfg["patience_s"]),
            "session": r.session, "weather": r.weather, "storm_seen": r.storm_seen, "night": r.night_seen,
            "position_id": r.position_id, "order_id": r.order_id, "quote_at_send": r.quote_at_send, "entry_ref": r.entry_ref,
            "spread_entry": r.spread_entry, "fill": r.fill, "sl0": r.sl0, "tp0": r.tp0, "sl_final": r.sl, "tp_final": r.tp,
            "exit": fin.get("exit"), "walls": r.walls, "haggles": r.haggles, "machete_done": r.machete_done, "banked_usd": r.banked_usd,
            "golden": r.golden, "anvil_moves": r.anvil_moves, "anvil_before_haggle": r.anvil_before_haggle,
            "outcome": fin.get("outcome"), "result_usd": fin.get("result_usd"), "costs": st.get("costs"), "estimated": r.estimated,
            "instructions": r.instructions, "fills": r.fills, "report_rows": r.report_rows, "rat": r.rat, "quotes": qs, "path": r.path,
            "twin_invited": r.twin_invited, "twin": tw, "twin_result_usd": tw["result_usd"] if tw and tw["state"] == "done" else None,
            "would_have_usd": r.would_have_usd, "settlement": st, "notes": r.notes})

    def _write_round_log(self, r):
        try:
            d = os.path.join(self.rounds_dir, r.id[:8])
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, r.id + ".json")
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._round_log(r), f, indent=1)
            os.replace(tmp, path)
        except Exception as e:  # noqa: BLE001
            self._log(f"could not write the round log for {r.id}: {e}")

    @staticmethod
    def _summary(d):
        return {"id": d.get("id"), "mode": d.get("mode"), "kind": d.get("kind"), "side": d.get("side"), "outcome": d.get("outcome"),
                "result_usd": d.get("result_usd"), "risk_usd": d.get("risk_usd"), "opened_t": d.get("opened_t"),
                "closed_t": d.get("closed_t"), "session": d.get("session"), "weather": d.get("weather"),
                "patience_s": d.get("patience_s"), "quick": d.get("quick"), "target": d.get("target"),
                "machete_done": bool(d.get("machete_done")), "twin_invited": bool(d.get("twin_invited")),
                "twin_result_usd": d.get("twin_result_usd"), "would_have_usd": d.get("would_have_usd"), "night": bool(d.get("night")),
                "anvil_before_haggle": bool(d.get("anvil_before_haggle")), "costs": d.get("costs"), "bites": len(d.get("rat") or []),
                "qty0": d.get("qty0"), "fill": d.get("fill"), "exit": d.get("exit"), "haggles": d.get("haggles"),
                "estimated": bool(d.get("estimated")), "path": d.get("path")}

    def _load_rounds(self):
        out = []
        for f in glob.glob(os.path.join(self.rounds_dir, "*", "*.json")):
            try:
                with open(f, encoding="utf-8") as fh:
                    d = json.load(fh)
            except Exception:  # noqa: BLE001
                continue
            if not isinstance(d, dict) or not d.get("id") or d.get("outcome") not in OUTCOMES or not d.get("mode"):
                continue                                    # not one of our round logs (e.g. the P0 capture) - skip it
            out.append(self._summary(d))
        out.sort(key=lambda s: s.get("closed_t") or 0)
        for s in out[:-12]:
            s["path"] = None
        self.summaries = out
        self._sum_version += 1

    def _refresh_summary(self, r):
        s = self._summary(self._round_log(r))
        for i, old in enumerate(self.summaries):
            if old.get("id") == s["id"]:
                self.summaries[i] = s
                break
        else:
            self.summaries.append(s)
        for old in self.summaries[:-12]:
            old["path"] = None
        self._sum_version += 1
        self._lim_cache = (None, None)

    def _ghost_paths(self, exclude=None):
        out = []
        for s in reversed(self._mode_rounds()):
            if s.get("id") == exclude or not s.get("path"):
                continue
            path = s["path"]
            if len(path) > 150:
                step = len(path) / 150.0
                path = [path[int(i * step)] for i in range(150)] + [path[-1]]
            out.append({"id": s["id"], "path": path})
            if len(out) >= int(self.cfg["ghosts"]):
                break
        return out

    def _tallies(self):
        rs = self._mode_rounds()

        def z():
            return {"n": 0, "wins": 0, "net_usd": 0.0}

        def add(acc, s):
            res = s.get("result_usd") or 0.0
            acc["n"] += 1
            acc["wins"] += 1 if res > 0 else 0
            acc["net_usd"] = round(acc["net_usd"] + res, 6)

        def groups():
            return {"by_session": {k: z() for k in SESSIONS}, "by_weather": {k: z() for k in WEATHERS},
                    "by_patience": {"quick": z(), "patient": z()},
                    "ejected": dict(z(), would_have_usd=0.0, would_have_n=0), "twin": dict(z(), twin_n=0, twin_wins=0, twin_net_usd=0.0),
                    "merchant": dict(z(), would_have_usd=0.0, would_have_n=0),
                    "by_target": {f"{float(x):.2f}": z() for x in self.cfg["targets"]}, "by_outcome": {o: z() for o in OUTCOMES}}

        # REQUIREMENTS 9 / 11: the Alley's wooden rounds never merge with real ones. The plain keys hold real (live-kind) rounds only;
        # the same breakdowns for wooden rounds live under wooden_<key> (the lobby slate shows the set that matches the coin in hand).
        real, wood = groups(), groups()
        t = {"wooden": z(), "live": z()}
        for s in rs:
            if s.get("estimated"):
                continue                                  # tallies come from the deal history only
            g = wood if s.get("kind") == "wooden" else real
            add(t["wooden" if s.get("kind") == "wooden" else "live"], s)
            add(g["by_session"].setdefault(s.get("session") or "asia", z()), s)
            add(g["by_weather"].setdefault(s.get("weather") or "calm", z()), s)
            add(g["by_patience"]["quick" if s.get("quick") else "patient"], s)
            add(g["by_outcome"].setdefault(s.get("outcome") or "outside", z()), s)
            if s.get("target") is not None:
                add(g["by_target"].setdefault(f"{float(s['target']):.2f}", z()), s)
            for key, oc in (("ejected", "eject"), ("merchant", "merchant")):
                if s.get("outcome") == oc:
                    add(g[key], s)
                    if s.get("would_have_usd") is not None:
                        g[key]["would_have_usd"] = round(g[key]["would_have_usd"] + s["would_have_usd"], 6)
                        g[key]["would_have_n"] += 1
            if s.get("twin_invited"):
                add(g["twin"], s)
                if s.get("twin_result_usd") is not None:
                    g["twin"]["twin_n"] += 1
                    g["twin"]["twin_wins"] += 1 if s["twin_result_usd"] > 0 else 0
                    g["twin"]["twin_net_usd"] = round(g["twin"]["twin_net_usd"] + s["twin_result_usd"], 6)
        t.update(real)
        t.update({"wooden_" + k: v for k, v in wood.items()})
        return t

    def _trophies(self):
        rs = self._mode_rounds()
        got = {}

        def award(k, t):
            if k not in got and t is not None:
                got[k] = t
        c = self.cfg
        n = 0
        ej = mach = False
        for s in rs:
            ct = s.get("closed_t")
            if s.get("kind") == "wooden":
                award("first_wooden", ct)
                n += 1
                ej = ej or s.get("outcome") == "eject"
                mach = mach or bool(s.get("machete_done"))
                if n >= int(c["alley_needed"]) and ej and (mach or not self._can_split()):
                    award("alley_graduate", ct)
            if (s.get("patience_s") or 0) >= float(c["patience_s"]):
                award("patient_shot", ct)
            if s.get("anvil_before_haggle"):
                award("tied_before_haggle", ct)
            if s.get("twin_invited"):
                award("twin_round", ct)
            if s.get("night") and s.get("outcome") in ("buyer", "anvil", "barrel"):
                award("rode_the_night", ct)
        for k, t in (self._disc().get("awards") or {}).items():
            award(k, t)
        return sorted(({"key": k, "title": TROPHIES.get(k, k), "t": t} for k, t in got.items()), key=lambda x: x["t"] or 0)

    def _lobby_view(self):
        if self._tally_cache[0] == self._sum_version:
            return self._tally_cache[1]
        rs = self._mode_rounds()
        live = [s for s in rs if s.get("kind") == "live"]
        jar = 0.0
        bites = 0
        for s in live:
            cst = s.get("costs") or {}
            jar += sum((_num(cst.get(k), 0.0) or 0.0) for k in ("spread_usd", "slippage_usd", "fee_usd", "financing_usd"))
            bites += int(s.get("bites") or 0)
        cabinet = [{"t": s.get("closed_t"), "usd": s.get("result_usd"), "kind": s.get("kind")} for s in rs if s.get("outcome") == "buyer"][-50:]
        out = {"jar_usd": round(jar, 6), "jar_bites": bites, "cabinet": cabinet, "trophies": self._trophies(), "tallies": self._tallies(),
               "rounds_total": len(rs), "live_rounds_total": len(live)}
        self._tally_cache = (self._sum_version, out)
        return out

    def rounds_list(self, limit=50, mode=None):
        with self.lock:
            want = self.mode if mode in (None, "") else mode
            rs = [s for s in self.summaries if want == "all" or s.get("mode") == want]
            limit = max(1, min(int(limit or 50), 1000))
            return [{k: v for k, v in s.items() if k != "path"} for s in reversed(rs[-limit:])]

    def tallies(self):
        with self.lock:
            return sanitize(self._tallies())

    # ------------------------------------------------------------------------------------------------------------------ settings
    def update_settings(self, body):
        if not isinstance(body, dict):
            body = {}
        c = self.cfg
        with self.lock:
            s = dict(self.settings)
            why = None
            idle = self.phase in ("lobby", "settled")
            if "coin_oz" in body:
                v = _num(body.get("coin_oz"))
                if v is None or not (c["min_qty"] - 1e-9 <= v <= c["coin_max_oz"] + 1e-9) or abs(round(v / c["qty_step"]) * c["qty_step"] - v) > 1e-6:
                    why = "bad_coin"
                elif not idle and abs(v - s["coin_oz"]) > 1e-9:
                    why = "phase"
                else:
                    s["coin_oz"] = round(v, 2)
            if "stop_dist" in body and why is None:
                v = _num(body.get("stop_dist"))
                if v is None or not any(abs(v - x) < 1e-9 for x in c["stop_choices"]):
                    why = "bad_stop"
                elif not idle and abs(v - s["stop_dist"]) > 1e-9:
                    why = "phase"
                else:
                    s["stop_dist"] = float(v)
            for k in ("sound", "plain_line"):
                if k in body:
                    s[k] = bool(body.get(k))
            if "eject_words" in body:
                s["eject_words"] = str(body.get("eject_words") or "")[:60]
            if "live_enabled" in body and why is None:
                on = bool(body.get("live_enabled"))
                if on and str(body.get("confirm_word") or "").strip() != "CONFIRM":
                    why = "confirm"
                else:
                    s["live_enabled"] = on
            if why:
                return {"ok": False, "why": why, "settings": sanitize(self._settings_view())}
            changed_live = s["live_enabled"] != self.settings["live_enabled"]
            self.settings = s
            self._save_settings()
            self._lim_cache = (None, None)
            self._tally_cache = (None, None)
            self._snap_cache = (0.0, None)
            if changed_live:                                   # Zee 2026-11-06: one signature lasts the UTC day (restarts no longer wipe it)
                self._save_json("live_signed.json", {"day": utc_day(self.clock()) if s["live_enabled"] else None})
                self._log("live rounds ENABLED via /api/settings (confirm word given)" if s["live_enabled"] else
                          "live rounds disabled via /api/settings")
            return {"ok": True, "why": None, "settings": sanitize(self._settings_view())}

    # ------------------------------------------------------------------------------------------------------------------ the snapshot (CONTRACT.md section 7)
    def _session(self, now):
        if self._market_closed(self.fs, now):
            return "closed"
        return self.mc.session(now)

    def _cur_side(self):
        if self.round is not None and self.phase in ("sending", "open", "closing", "settled"):
            return self.round.side
        if self.aim:
            return self.aim["side"]
        return self.settings["side"]

    def _feed_view(self, fs, now):
        age = self._quote_age(now)
        reason = scrub(fs.get("reason")) if fs.get("reason") else None
        if self._q(fs) is None and not reason:
            reason = "no quote yet"
        mo = not self._market_closed(fs, now)
        tc = fs.get("tick_count")
        return {"ok": self._feed_ok(fs, now), "age_s": round(age, 2) if age is not None else None, "reason": reason,
                "tick_count": int(tc) if isinstance(tc, (int, float)) else self._tick_seen_n, "ticks_per_s": round(self.ticks_per_s, 2),
                "market_open": mo}

    def _account_view(self, fs):
        a = fs.get("account")
        if not a:
            return None
        typ = {"sim": "SIM", "replay": "REPLAY"}.get(self.mode) or str(a.get("type") or "LIVE").upper()
        return {"id": str(a.get("id") or ""), "type": typ, "balance": _num(a.get("balance")), "equity": _num(a.get("equity")),
                "currency": a.get("currency") or "USD"}

    def _quote_view(self, fs):
        q = self._q(fs)
        if q is None:
            return None
        return {"bid": q["bid"], "ask": q["ask"], "mid": round((q["bid"] + q["ask"]) / 2.0, PX_DP + 1), "spread": round(q["ask"] - q["bid"], PX_DP),
                "ts": q["ts"]}

    def _market_view(self, fs, now, sh):
        c = self.cfg
        bars = fs.get("bars") or []
        h24, l24 = _num(fs.get("h24")), _num(fs.get("l24"))
        if (h24 is None or l24 is None) and bars:
            h24 = max(b[2] for b in bars[-1440:])
            l24 = min(b[3] for b in bars[-1440:])
        ch = _num(fs.get("ch24"))
        if ch is None and bars:
            ch = bars[-1][4] - bars[0][1]
        season = round(clamp(self._cur_side() * (ch or 0.0) / float(c["season_scale"] or 20.0), -1.0, 1.0), 3)
        if self._bell_cache[1] is None:
            self._bell_cache = (int(now // 20), self.mc.bell(now))
        show = [str(i).lower() for i in c.get("news_show_impacts", ["high"])]
        news = [n for n in self._news_events() if n["impact"] in show and now - 7200 <= n["t"] <= now + 86400][:8]
        return {"session": self._session(now), "day_frac": round((now % 86400) / 86400.0, 5), "weather": self.weather, "vol": self.vol,
                "lightning": now < self.lightning_until, "season": season, "tilt_raw": round(self.tilt_raw, 3), "h24": h24, "l24": l24, "trend5": self.trends.get(5), "trend15": self.trends.get(15), "hints": dict(self.hints), "diamond": dict(self.dia), "risk": dict(self.risk),
                "shutters": sh, "bell": dict(self._bell_cache[1]), "news": news}

    def _settings_view(self):
        s, c = self.settings, self.cfg
        risk = round(s["coin_oz"] * s["stop_dist"], 6)
        target = self.aim["target"] if self.aim else (self.round.target if (self.round is not None and self.phase != "lobby") else s["target"])
        return {"coin_oz": s["coin_oz"], "stop_dist": s["stop_dist"], "stop_choices": list(c["stop_choices"]), "target": target,
                "targets": list(c["targets"]), "symbol": c.get("symbol"), "price_dp": PX_DP, "side": self._cur_side(), "live_enabled": s["live_enabled"], "twin_invited": s["twin_invited"],
                "twin_unlocked": self._twin_unlocked(), "sound": s["sound"], "plain_line": s["plain_line"], "eject_words": s["eject_words"],
                "risk_usd": risk, "money_unit": "cents" if risk < 1 else "dollars", "can_split": self._can_split(), "min_qty": c["min_qty"]}

    def _limits_view(self, lim, sh, now):
        wn = self._why_not_live(now, lim, sh)
        keys = ("rounds_today", "rounds_max", "loss_today_coins", "loss_max_coins", "stops_in_row", "jam_until", "locked_until",
                "alley_done", "alley_needed", "alley_eject_done", "alley_machete_needed")
        out = {k: lim[k] for k in keys}
        out["live_allowed"] = wn is None
        out["why_not_live"] = wn
        out["alley_machete_done"] = lim["alley_machete_done"]
        out["locked_reason"] = lim["locked_reason"]
        return out

    def _terrain(self, a, b, now):
        c = self.cfg
        bars = self._bars()
        bins = int(c["terrain_bins"])
        if not bars:
            return {"x0": TERRAIN_X0, "x1": TERRAIN_X1, "h": [0.0] * bins, "chasms": [], "scorch": [], "weathered": []}
        last = bars[-1]
        key = (round(a, 9), round(b, 12), len(bars), last[0], last[2], last[3])
        w = self._weathered_cache[1] if self._weathered_cache[0] == key else None
        t = terrain(bars, a, b, bins=bins, profile=int(c["profile_bars"]), chasm_prices=self._chasm_prices(now), weathered=w)
        if w is None:
            self._weathered_cache = (key, t["weathered"])
        return t

    def _stake_list(self, side, a, b, mark, sl, hi, now, full):
        gap = float(self.cfg["min_sl_gap"])
        lit = self._lit_stakes(side, now)
        out = []
        for p in lit:
            if -0.05 <= xp(a, b, p) <= hi:
                st = {"price": r2(p) if full else p, "x": xp(a, b, p - TICK * side), "lit": True}
                if full:
                    st["passed"] = mark is not None and side * (mark - p) > gap
                    st["used"] = sl is not None and abs(p - TICK * side - sl) < TICK / 2
                out.append(st)
        ch = self._chasm_prices(now)
        for p in pivot_candidates(self._bars(), side, int(self.cfg["stake_pivot"])):
            if any(abs(p - q) < 1e-9 for q in lit) or self.gaps.inside(p, ch) or not (-0.05 <= xp(a, b, p) <= hi):
                continue
            st = {"price": r2(p), "x": xp(a, b, p - TICK * side), "lit": False}
            if full:
                st["passed"] = mark is not None and side * (mark - p) > gap
                st["used"] = False
            out.append(st)
        return out

    def _preview_view(self, fs, now):
        q = self._q(fs)
        if q is None:
            return None
        side = self._cur_side()
        target = self.aim["target"] if self.aim else self.settings["target"]
        sd = self.settings["stop_dist"]
        entry = q["ask"] if side > 0 else q["bid"]
        sl, tp = entry - side * sd, entry + side * target
        a, b, _, _ = ladder(side, entry, sl, tp)
        mark = self._mark(side, q)
        spread = q["ask"] - q["bid"]
        patience = round(now - self.aim["since"], 2) if (self.aim and self.phase == "aiming") else 0.0
        xm, xe = xp(a, b, mark), xp(a, b, entry)
        return {"entry": entry, "stop": r2(sl), "target_price": r2(tp), "side": side, "a": round(a, 6), "b": round(b, 6),
                "x_entry": xe, "x_mark": xm, "tilt": round(side * self.tilt_ema, 3), "patience_s": patience,
                "at_door": self.phase == "aiming", "stakes": self._stake_list(side, a, b, mark, None, 1.05, now, full=False),
                "terrain": self._terrain(a, b, now),
                "pit": {"x0": min(xm, xe), "x1": max(xm, xe), "depth": round(clamp(spread / float(self.cfg["pit_full_spread"]), 0.0, 1.0), 3)}}

    def _merchant_view(self, x, age, night, insists):
        if insists:
            return {"x": round(min(x + 0.12, 1.1), 4), "visible": True, "dir": -1, "insists": True}
        period = float(self.cfg["merchant_period_s"]) / (2.0 if night else 1.0)
        ph = (age % period) / period if period > 0 else 0.0
        visible = ph < 0.45
        xm = 1.08 - (ph / 0.45) * 1.16 if visible else 1.08
        return {"x": round(xm, 4), "visible": visible, "dir": -1, "insists": False}

    def _round_view(self, fs, now):
        r = self.round
        c = self.cfg
        q = self._q(fs)
        side = r.side
        if r.fill is None:                       # sending: the provisional street at the current quote
            entry = (q["ask"] if side > 0 else q["bid"]) if q else (r.entry_ref or 0.0)
            fill, sl0, tp0 = entry, entry - side * r.stop_dist, entry + side * r.target
            sl, tp = r2(sl0), r2(tp0)
        else:
            fill, sl0, tp0, sl, tp = r.fill, r.sl0, r.tp0, r.sl, r.tp
        if r.final is not None:
            a, b, mark = r.final["a"], r.final["b"], r.final["exit"]
        else:
            a, b, _, _ = ladder(side, fill, sl0, tp0, r.banked_usd, r.qty, r.qty0)
            mark = self._mark(side, q) if q else (r.last_mark if r.last_mark is not None else fill)
        sd0, td0 = abs(fill - sl0), abs(tp0 - fill)
        x = xp(a, b, mark)
        if r.final is not None:
            result = r.final["result_usd"]
            pnl = r6(result - r.banked_usd)
        else:
            pnl = r6(side * (mark - fill) * r.qty)
            result = r6(r.banked_usd + pnl)
        risk = r.risk_usd
        value = r6(risk + result)
        x_tp = xp(a, b, tp)
        tilt = round(side * self.tilt_ema, 3) if r.final is None else 0.0
        stakes = self._stake_list(side, a, b, mark, sl, max(1.05, x_tp + 0.05), now, full=True)
        golden = None
        if r.golden:
            golden = {"price": r.golden["price"], "x": xp(a, b, r.golden["price"]), "usd": r.golden["usd"],
                      "text": money(r.golden["usd"], risk, signed=True)}
        live_open = self.phase == "open" and r.fill is not None and not r.pending and r.final is None and q is not None
        can_anvil = live_open and self._next_stake(r, mark, now) is not None
        can_wall = live_open and len(r.walls) < int(c["walls_max"]) and side * (self._wall_price(r, mark) - sl) >= TICK - 1e-9
        can_haggle = (live_open and r.haggles < int(c["haggle_max"]) and x >= x_tp - float(c["haggle_reach_x"]) and tilt > 0 and
                      self._haggle_stake(r, mark, now) is not None)
        can_machete = live_open and not r.machete_done and self._machete_qty(r) is not None
        t_open = r.opened_t or r.shot_t or now
        age = ((r.closed_t or now) - t_open) if r.final is not None else (now - t_open)
        night = age > float(c["night_after_s"])
        tc = self._auto_close_t(now)
        golden_hour = r.final is None and tc is not None and tc - float(c["golden_hour_s"]) <= now < tc
        insists = golden_hour or r.close_intent == "session"
        spread = (q["ask"] - q["bid"]) if q else (r.spread_entry or 0.33)
        xa, xb = xp(a, b, fill - side * spread), xp(a, b, fill)
        twin = None
        if r.twin:
            sh = r.twin
            span = (sh["sd0"] + sh["td0"]) or 1e-9
            done = sh["state"] == "done"
            tm = sh["exit"] if (done and sh["exit"] is not None) else (self._mark(side, q) if q else mark)
            twin = {"x": round((side * (tm - sh["fill"]) + sh["sd0"]) / span, 5), "anvil_x": round((side * (sh["sl"] - sh["fill"]) + sh["sd0"]) / span, 5),
                    "state": "done" if done else "running", "result_usd": sh["result_usd"]}
        return {
            "id": r.id, "kind": r.kind, "side": side, "qty": r.qty, "qty0": r.qty0,
            "opened_t": t_open, "age_s": round(age, 1), "patience_s": r.patience_s,
            "fill": fill, "sl": sl, "tp": tp, "stop_dist0": round(sd0, 6), "target_dist0": round(td0, 6), "target_dist": round(abs(tp - fill), 2),
            "mark": mark, "spread": round(spread, PX_DP), "a": round(a, 6), "b": round(b, 6),
            "x": x, "x_entry": xp(a, b, fill), "x_sl": xp(a, b, sl), "x_tp": x_tp, "tilt": tilt,
            "pnl_usd": pnl, "banked_usd": r6(r.banked_usd), "result_usd": result, "value_usd": value, "risk_usd": risk,
            "value_text": money(value, risk),
            "tag_text": "" if r.tp_missing else money(risk + r.qty * side * (tp - fill) + r.banked_usd, risk),
            "girl_margin_usd": round(self._girl_margin_usd(r), 6),
            "anvil": {"price": sl, "x": xp(a, b, sl), "kind": r.anvil_kind, "pending": bool(r.anvil_pending), "missing": bool(r.sl_missing)},
            "protected": {"sl": not r.sl_missing, "tp": not r.tp_missing},
            "stakes": stakes, "walls": [{"price": w, "x": xp(a, b, w)} for w in r.walls],
            "walls_left": max(0, int(c["walls_max"]) - len(r.walls)), "golden": golden,
            "haggles": r.haggles, "haggle_max": int(c["haggle_max"]), "can_haggle": bool(can_haggle), "can_wall": bool(can_wall),
            "can_anvil": bool(can_anvil), "can_machete": bool(can_machete), "machete_done": r.machete_done,
            "merchant": self._merchant_view(x, age, night, insists),
            "terrain": self._terrain(a, b, now),
            "pit": {"x0": min(xa, xb), "x1": max(xa, xb), "depth": round(clamp(spread / float(c["pit_full_spread"]), 0.0, 1.0), 3)},
            "night": night, "golden_hour": golden_hour, "tarnish": round(min(1.0, age / (1.5 * float(c["night_after_s"]))), 4),
            "twin": twin, "ghosts": r.ghosts, "rat": list(r.rat), "pending": dict(r.pending) if r.pending else None,
            "last_refusal": dict(r.last_refusal) if r.last_refusal else None,
        }

    def snapshot(self):
        now = self.clock()
        with self.lock:
            fs = self.fs or {}
            lim = self._limits(now)
            sh = self._shutters(now, lim)
            snap = {
                "v": 1, "t": round(now, 3), "mode": self.mode,
                "feed": self._feed_view(fs, now),
                "account": self._account_view(fs),
                "quote": self._quote_view(fs),
                "market": self._market_view(fs, now, sh),
                "settings": self._settings_view(),
                "limits": self._limits_view(lim, sh, now),
                "lobby": self._lobby_view(),
                "phase": self.phase,
                "preview": self._preview_view(fs, now) if self.phase in ("lobby", "aiming") else None,
                "round": self._round_view(fs, now) if (self.round is not None and self.phase in ("sending", "open", "closing", "settled")) else None,
                "settlement": dict(self.settlement) if (self.phase == "settled" and self.settlement) else None,
                "freeze": bool(self._freeze),
            }
        return sanitize(snap)

    def snapshot_json(self, max_age=0.05):
        t0 = time.monotonic()
        t, s = self._snap_cache
        if s is not None and t0 - t < max_age:
            return s
        s = json.dumps(self.snapshot(), separators=(",", ":"), allow_nan=False)
        self._snap_cache = (t0, s)
        return s


# ----------------------------------------------------------------------------------------------------------------------------------
def make_feed(mode="sim", seed=7, speed=1.0, file=None, record=False, config=None):
    """Build the feed for a run mode from feeds.py (imported lazily: it is written in parallel and may be half-finished).
    Prefers feeds.make_feed (B-FEEDS' own factory); falls back to calling the classes with the keywords they accept."""
    import inspect
    import feeds  # noqa: WPS433 (lazy on purpose)

    if mode not in ("sim", "replay", "live"):
        raise SystemExit(f"unknown mode {mode}")
    if mode == "replay" and not file:
        raise SystemExit("--mode replay needs --file recordings/X.jsonl")
    fac = getattr(feeds, "make_feed", None)
    if callable(fac):
        if mode == "sim":
            return fac("sim", config=config, seed=seed, speed=speed)
        if mode == "replay":
            return fac("replay", config=config, path=file, speed=speed, loop=True)      # a recording loops: the engine treats each seam as a close
        return fac("live", config=config, record=record)

    def build(cls, *pos, **kw):
        try:
            params = inspect.signature(cls).parameters
            if not any(p.kind == p.VAR_KEYWORD for p in params.values()):
                kw = {k: v for k, v in kw.items() if k in params}
        except (TypeError, ValueError):
            pass
        return cls(*pos, **kw)
    if mode == "sim":
        return build(feeds.SimFeed, seed=seed, speed=speed)
    if mode == "replay":
        return build(feeds.ReplayFeed, file, speed=speed, loop=True)
    return build(feeds.LiveFeed, record=record)
