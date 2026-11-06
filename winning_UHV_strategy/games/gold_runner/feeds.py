"""feeds.py - Golden Gravity's market and broker (CONTRACT.md section 4).

    Feed            the interface the engine consumes: start/stop/subscribe/state + place/set_protective/check_protective/close/orders_report
    ShadowBroker    a simulated PrimeXBT broker over ANY quote source (Alley rounds, the Twin, the eject counterfactual, SimFeed's account)
    SimFeed         a synthetic XAU/USD market whose account trades through a ShadowBroker ($25.00); deterministic with a seed
    PXChannel       money-safe request/response over the PXTrader futures socket (rids from 900000, pending map, error objects, timeouts)
    LiveFeed        the PXTrader page in Chrome :9222 over CDP.  ONLY the main agent runs it; tests never start it.
    ReplayFeed      plays recordings/*.jsonl through the same parser as LiveFeed; can_trade False (orders -> error "REPLAY")
    make_feed(mode, ...)   convenience factory: make_feed("sim", seed=7, speed=1.0)

Constructors (all keywords optional):  SimFeed(seed=None, speed=1.0, config=None, ...)   ReplayFeed(path, speed=1.0, loop=False, ...)
                                       LiveFeed(record=False, config=None, port=9222, ...)
Extras beyond CONTRACT.md section 4 (all optional for the engine):
  feed.now()                     the feed's clock (wall time; SimFeed manual mode: its virtual clock)
  feed.wait_quote(timeout)       block until the first quote (cold start)
  SimFeed.sim_force(kind, **kw)  gap | storm | calm | active | spike | news | night | day | auto | close | open | silence | resume
  SimFeed.pump(n) / advance(s)   drive a SimFeed by hand (tests); SimFeed.broker is its ShadowBroker
  ShadowBroker.place(..., fill_price=x)   open at an exact price (the Twin, the eject counterfactual); .result(position_id)
  LiveFeed.adopt(position_id)    let the game manage a position it opened earlier (also kept in state/feeds_live_owned.json)
  LiveFeed.resolve(token)        keep looking for the position of an accepted order whose id was not resolved in place()
  orders_report() returns a ReportList: a plain list with .ok / .error / .rtt_ms
Conventions shared by every feed (the engine relies on these):
  * every timestamp is local wall-clock unix seconds (float) - quote.ts, ticks, activity t, positions open_time, report executed_ts.
    SimFeed in manual mode (tests) uses a virtual clock that starts at time.time(); feed.now() returns the feed's clock.
  * bars are 1-minute BID bars [t, o, h, l, c, v], t = bar open (unix s, multiple of 60), oldest first, the forming bar last
  * prices are put on the instrument's 0.01 grid before they are sent or filled; quantities must be multiples of 0.01 oz
  * tick_count counts quote updates whose bid or ask changed (one footstep = one real price change); quote.ts is the receipt time of
    the newest quote even when the price did not change, so the roof sign's hourglass never lies about a live quote
  * events: {"type":"quote", bid, ask, mid, spread, ts, st, tick_count, changed}, {"type":"bar","bar":[t,o,h,l,c,v],"closed":bool},
    {"type":"positions","positions":[...]}, {"type":"account","account":{...}} (nested because the account has its own "type"),
    {"type":"orders","orders":[...]}, {"type":"activity","title","body","t","level"}, {"type":"feed","ok","reason","market_open"},
    {"type":"news","news":[...]}, {"type":"history","count":n}
  * once start()ed, a feed delivers events from ONE dispatcher thread (a slow subscriber never blocks the market or a trade's wait);
    before start() (tests, manual sim) events are delivered synchronously from the caller
  * orders_report rows keep PrimeXBT's keys (id, type, status, side, qty, executedPrice, executedQty, rpl, fee, positionId,
    closeReason, executedAt) and add "executed_ts" (unix s float): use executed_ts, executedAt's format is the broker's.
    Pass since_ts a little before the order was sent (broker clocks differ).  Round result = sum(rpl) - sum(fee) of the position's
    EXECUTED rows (fee is 0 on PXTrader today).
  * trading calls return {"ok": bool, "error": str|None, "rtt_ms": float, ...}; error codes: PrimeXBT's own ("POSITION_NOT_FOUND: ...")
    or ours: TIMEOUT, SOCKET_LOST, NOT_CONNECTED, NO_QUOTE, BAD_SIDE, BAD_QTY, QTY_CAP, BAD_PROTECTIVE, BAD_KIND, MIN_ORDER_SIZE,
    INSUFFICIENT_FUNDS, MARKET_CLOSED, FEED_DEAD, REPLAY, REJECTED
SAFETY: nothing in this module trades by itself. LiveFeed only sends trading frames when place/set_protective/close are called, never
logs or records a socket URL (recordings are scrubbed of ws URLs and JWTs), and refuses to start() when GG_FORBID_LIVE is set.
"""
from __future__ import annotations


import collections
import datetime as _dt
import itertools
import json
import math
import os
import queue
import random
import re
import sys
import threading
import time

__all__ = ["Feed", "ShadowBroker", "SimFeed", "PXChannel", "PXFeedBase", "LiveFeed", "ReplayFeed", "Recorder", "ReportList",
           "SendNotOpen", "make_feed", "load_config", "normalise_calendar", "scrub", "parse_fill_text", "parse_link_text"]

HERE = os.path.dirname(os.path.abspath(__file__))
SYMBOL = "XAU/USD"
SYM_ID = 1019
TICKS_WINDOW_S = 120.0
KEEP_BARS = 400            # bars kept in state() (contract: last >= 300; LiveFeed must keep >= 330)
HISTORY_LIMIT = 329        # our own 1-minute history request; + the live forming bar = 330
ACTIVITY_KEEP = 50
RID0 = 900000              # our request ids (the page counts up from ~1)

DEFAULTS = {"symbol": SYMBOL, "sym_id": SYM_ID, "feed_dead_s": 15, "feed_stale_s": 2.0,
            "dead_hours_utc": [["20:45", "23:00"]], "min_qty": 0.01, "qty_step": 0.01,
            "live_account_id": "L1869984",       # LiveFeed trades on this PXTrader account only (empty = no pin)
            "news_regions": ["US"]}              # the /upcoming calendar: HIGH covers every country; gold cares about these


# ------------------------------------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------------------------------------
def load_config(path=None):
    """config.json (B-ENGINE's file) merged over the few defaults the feeds need; a missing or broken file is not an error"""
    cfg = dict(DEFAULTS)
    try:
        with open(path or os.path.join(HERE, "config.json"), "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            cfg.update(d)
    except (OSError, ValueError):
        pass
    return cfg


def _log(*a):
    try:
        print("[feeds]", *a, file=sys.stderr, flush=True)
    except Exception:                                    # noqa: BLE001
        pass


PX_DP = 2           # the price grid (set per symbol, Zee 2026-11-04)


def configure_price(dp):
    global PX_DP
    PX_DP = max(0, min(8, int(dp)))


def r2(x):
    """put a price on the active symbol's grid (None stays None)"""
    return None if x is None else round(float(x), PX_DP)


def qty_ok(qty, step=0.01, min_qty=0.01):
    try:
        q = float(qty)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(q) or q < min_qty - 1e-9:
        return False
    n = q / step
    return abs(n - round(n)) < 1e-6


def fnum(x, default=None):
    """a number from a PX field (numbers, numeric strings, '3,926.59'); default when missing"""
    if x is None or isinstance(x, bool):
        return default
    if isinstance(x, (int, float)):
        return float(x) if math.isfinite(float(x)) else default
    try:
        v = float(str(x).replace(",", "").strip())
        return v if math.isfinite(v) else default
    except ValueError:
        return default


def to_unix(v):
    """PX/calendar time values -> unix seconds (float): ISO strings ('2026-11-03T02:33:04.761Z'), unix s, or unix ms"""
    if v is None or v == "" or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        x = float(v)
        return x / 1000.0 if x > 1e11 else x
    s = str(v).strip()
    try:
        x = float(s)
        return x / 1000.0 if x > 1e11 else x
    except ValueError:
        pass
    try:
        z = s[:-1] + "+00:00" if s.endswith("Z") else s
        d = _dt.datetime.fromisoformat(z)
        if d.tzinfo is None:
            d = d.replace(tzinfo=_dt.timezone.utc)
        return d.timestamp()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%d.%m.%Y %H:%M", "%Y-%m-%d"):
        try:
            return _dt.datetime.strptime(s, fmt).replace(tzinfo=_dt.timezone.utc).timestamp()
        except ValueError:
            continue
    return None


def iso_z(ts):
    return _dt.datetime.fromtimestamp(float(ts), _dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _hm(s):
    h, m = str(s).split(":")[:2]
    return int(h) * 60 + int(m)


def in_dead_hours(ts, dead_hours):
    """dead_hours = [["20:45", "23:00"], ...] in UTC (a window may wrap midnight)"""
    d = _dt.datetime.fromtimestamp(float(ts), _dt.timezone.utc)
    m = d.hour * 60 + d.minute + d.second / 60.0
    for w in dead_hours or []:
        try:
            a, b = _hm(w[0]), _hm(w[1])
        except (ValueError, IndexError, TypeError):
            continue
        if (a <= m < b) if a <= b else (m >= a or m < b):
            return True
    return False


_CLOSED_WORDS = ("CLOS", "HALT", "SUSP", "BREAK", "OFFLINE", "INACTIVE", "PAUSE", "MAINT")


def st_closed(st):
    """fx/market 'st' -> True only for a status that clearly says closed; numeric codes are undocumented, so never guessed"""
    if st is None or isinstance(st, (bool, int, float)):
        return False
    s = str(st).upper()
    return any(w in s for w in _CLOSED_WORDS)


_WS_URL = re.compile(r"wss?://[^\s\"'<>]+", re.I)
_JWT = re.compile(r"eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}")
_SECRET_KEYS = ("token", "jwt", "authorization", "password", "secret", "cookie", "apikey", "api_key")


def scrub(obj):
    """remove socket URLs, JWTs and credential-looking fields from a frame before it is recorded"""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            kl = str(k).lower()
            if isinstance(v, str) and any(s in kl for s in _SECRET_KEYS):
                out[k] = "<removed>"
            else:
                out[k] = scrub(v)
        return out
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    if isinstance(obj, str):
        low = obj.lower()
        if "ws://" in low or "wss://" in low:
            obj = _WS_URL.sub("<url removed>", obj)
        if "eyJ" in obj:
            obj = _JWT.sub("<jwt removed>", obj)
        return obj
    return obj


def _ret(ok, error=None, t0=None, **kw):
    d = {"ok": bool(ok), "error": error, "rtt_ms": round((time.perf_counter() - t0) * 1000.0, 1) if t0 is not None else 0.0}
    d.update(kw)
    return d


# ------------------------------------------------------------------------------------------------------------------------------
# Feed: the interface + the shared market state, dispatcher and status logic
# ------------------------------------------------------------------------------------------------------------------------------
class Feed:
    """Base class of every feed. Subclasses fill the shared state through the _put_* helpers; state() is the contract snapshot."""
    mode = "base"
    can_trade = False

    def __init__(self, config=None):
        self.cfg = load_config() if config is None else {**DEFAULTS, **dict(config)}
        self.symbol = str(self.cfg.get("symbol") or SYMBOL)
        self.sym_id = int(self.cfg.get("sym_id") or SYM_ID)
        self.feed_dead_s = float(self.cfg.get("feed_dead_s") or 15)
        self.feed_stale_s = float(self.cfg.get("feed_stale_s") or 2.0)
        self.min_qty = float(self.cfg.get("min_qty") or 0.01)
        self.qty_step = float(self.cfg.get("qty_step") or 0.01)
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        self._subs = []
        self._evq = None
        self._dispatch_thread = None
        self._stop_ev = threading.Event()
        self._started = False
        self._sub_errors = 0
        # shared market state
        self._quote = None
        self._tick_count = 0
        self._ticks = collections.deque()
        self._bars = []
        self._h24 = self._l24 = self._ch24 = None
        self._account = None
        self._positions = []
        self._orders = []
        self._activity = collections.deque(maxlen=ACTIVITY_KEEP)
        self._act_seq = 0
        self._news = []
        self._last_status = None

    # ---- interface ------------------------------------------------------------------------------------------------------------
    def start(self):
        """begin streaming (threads); idempotent"""
        with self._lock:
            if self._started:
                return
            self._started = True
            self._stop_ev.clear()
        self._start_dispatcher()

    def stop(self):
        with self._lock:
            self._started = False
        self._stop_ev.set()
        self._stop_dispatcher()

    def now(self):
        return time.time()

    def subscribe(self, fn):
        """fn(event: dict) for every event; returns fn. Exceptions inside fn are swallowed (and counted), never kill the feed."""
        with self._lock:
            if fn not in self._subs:
                self._subs.append(fn)
        return fn

    def unsubscribe(self, fn):
        with self._lock:
            if fn in self._subs:
                self._subs.remove(fn)

    def state(self):
        now = self.now()
        with self._lock:
            ok, reason = self._status(now)
            return {
                "ok": ok, "reason": reason,
                "quote": dict(self._quote) if self._quote else None,
                "tick_count": self._tick_count,
                "ticks": [[t, b, a] for (t, b, a) in self._ticks],
                "bars": [list(b) for b in self._bars],
                "h24": self._h24, "l24": self._l24, "ch24": self._ch24,
                "account": dict(self._account) if self._account else None,
                "positions": [dict(p) for p in self._positions],
                "orders": [dict(o) for o in self._orders],
                "activity": [dict(a) for a in self._activity],
                "news": [dict(n) for n in self._news],
                "market_open": self._market_open(now, ok),
            }

    def place(self, side, qty, sl, tp, timeout=5.0):
        return _ret(False, "NOT_SUPPORTED")

    def set_protective(self, position_id, kind, price, timeout=5.0):
        return _ret(False, "NOT_SUPPORTED")

    def check_protective(self, position_id, price, timeout=3.0):
        return _ret(False, "NOT_SUPPORTED")

    def close(self, position_id, qty, timeout=5.0):
        return _ret(False, "NOT_SUPPORTED")

    def orders_report(self, since_ts, timeout=5.0):
        return []

    def adopt(self, position_id):
        """LiveFeed only lets the game touch positions it opened or adopted; elsewhere a no-op"""
        return True

    def resolve(self, token, timeout=2.0):
        """LiveFeed: keep looking for the position of an accepted order (place() returned a resolve_token)"""
        return {"ok": False, "position_id": None, "fill_price": None}

    def wait_quote(self, timeout=5.0):
        """block until a quote exists (cold start); True if one arrived"""
        end = time.time() + timeout
        with self._cond:
            while self._quote is None:
                left = end - time.time()
                if left <= 0:
                    return False
                self._cond.wait(min(left, 0.25))
            return True

    # ---- status ---------------------------------------------------------------------------------------------------------------
    def _status(self, now):
        q = self._quote
        if q is None:
            return False, "no quote yet"
        if now - q["ts"] > self.feed_dead_s:
            return False, "quotes stale"
        return True, None

    def _market_open(self, now, ok):
        q = self._quote
        return bool(ok and q is not None and not st_closed(q.get("st")))

    def _check_status(self):
        """emit {"type":"feed"} when ok / reason / market_open changes"""
        now = self.now()
        with self._lock:
            ok, reason = self._status(now)
            mo = self._market_open(now, ok)
            cur = (ok, reason, mo)
            if cur == self._last_status:
                return
            self._last_status = cur
        self._emit({"type": "feed", "ok": ok, "reason": reason, "market_open": mo})

    # ---- events ---------------------------------------------------------------------------------------------------------------
    def _emit(self, ev):
        q = self._evq
        if q is not None:
            q.put(ev)
        else:
            self._deliver(ev)

    def _deliver(self, ev):
        for fn in list(self._subs):
            try:
                fn(ev)
            except Exception as e:                       # noqa: BLE001  a subscriber must never kill the feed
                self._sub_errors += 1
                if self._sub_errors <= 5:
                    _log(f"subscriber error on {ev.get('type')}: {type(e).__name__}: {scrub(str(e))[:200]}")

    def _start_dispatcher(self):
        with self._lock:
            if self._dispatch_thread is not None:
                return
            self._evq = queue.Queue()
            t = threading.Thread(target=self._dispatch_loop, args=(self._evq,), name=f"gg-{self.mode}-dispatch", daemon=True)
            self._dispatch_thread = t
        t.start()

    def _dispatch_loop(self, q):
        while True:
            ev = q.get()
            if ev is None:
                break
            self._deliver(ev)

    def _stop_dispatcher(self):
        with self._lock:
            q, t = self._evq, self._dispatch_thread
            self._evq = None
            self._dispatch_thread = None
        if q is not None:
            q.put(None)
        if t is not None and t is not threading.current_thread():
            t.join(timeout=2.0)

    # ---- state writers --------------------------------------------------------------------------------------------------------
    def _put_quote(self, bid, ask, ts, st=None, spread=None, last=None):
        bid, ask = r2(bid), r2(ask)
        with self._lock:
            prev = self._quote
            changed = prev is None or prev["bid"] != bid or prev["ask"] != ask
            sp = round(ask - bid, PX_DP) if spread is None else round(float(spread), PX_DP)
            q = {"bid": bid, "ask": ask, "mid": round((bid + ask) / 2.0, PX_DP + 1), "spread": sp, "ts": float(ts), "st": st}
            if last is not None:
                q["last"] = last
            self._quote = q
            if changed:
                self._tick_count += 1
                self._ticks.append((float(ts), bid, ask))
            cut = float(ts) - TICKS_WINDOW_S
            while self._ticks and self._ticks[0][0] < cut:
                self._ticks.popleft()
            ev = {"type": "quote", **q, "tick_count": self._tick_count, "changed": changed}
            self._cond.notify_all()
        self._emit(ev)
        return changed

    @staticmethod
    def _clean_bar(b, shift=0):
        try:
            t = float(b[0])
            t = int(t / 1000.0 if t > 1e11 else t) + int(shift)
            o, h, lo, c = (float(b[1]), float(b[2]), float(b[3]), float(b[4]))
            v = fnum(b[5], 0.0) if len(b) > 5 else 0.0
        except (TypeError, ValueError, IndexError):
            return None
        if not all(math.isfinite(x) for x in (o, h, lo, c)):
            return None
        return [t, o, max(h, o, c, lo), min(lo, o, c, h), c, v]

    def _merge_bar(self, bar, shift=0):
        """same t = update; newer t = append (the previous bar is announced closed); an older t corrects one of the last 5 bars"""
        b = self._clean_bar(bar, shift)
        if b is None:
            return
        evs = []
        with self._lock:
            bars = self._bars
            if not bars or b[0] > bars[-1][0]:
                if bars:
                    evs.append({"type": "bar", "bar": list(bars[-1]), "closed": True})
                bars.append(b)
                evs.append({"type": "bar", "bar": list(b), "closed": False})
                if len(bars) > KEEP_BARS:
                    del bars[:len(bars) - KEEP_BARS]
            elif b[0] == bars[-1][0]:
                bars[-1] = b
                evs.append({"type": "bar", "bar": list(b), "closed": False})
            else:
                for i in range(len(bars) - 2, max(-1, len(bars) - 7), -1):
                    if bars[i][0] == b[0]:
                        bars[i] = b
                        evs.append({"type": "bar", "bar": list(b), "closed": True})
                        break
        for ev in evs:
            self._emit(ev)

    def _set_history(self, rows, shift=0):
        """our 1-minute history: authoritative for closed bars; live bars at or after its last t win (they are newer)"""
        clean = [b for b in (self._clean_bar(r, shift) for r in rows or []) if b is not None]
        if not clean:
            return 0
        clean.sort(key=lambda b: b[0])
        with self._lock:
            merged = {b[0]: b for b in clean}
            last_t = clean[-1][0]
            for b in self._bars:
                if b[0] >= last_t:
                    merged[b[0]] = b
            self._bars = sorted(merged.values(), key=lambda b: b[0])[-KEEP_BARS:]
            n = len(self._bars)
        self._emit({"type": "history", "count": n})
        return n

    def _add_activity(self, title, body, level=None, t=None):
        with self._lock:
            self._act_seq += 1
            a = {"t": float(t) if t is not None else self.now(), "title": str(title or ""), "body": str(body or ""),
                 "level": level, "seq": self._act_seq}
            self._activity.append(a)
            self._cond.notify_all()
        self._emit({"type": "activity", "title": a["title"], "body": a["body"], "t": a["t"], "level": level, "seq": a["seq"]})
        return a

    def _put_positions(self, positions):
        with self._lock:
            self._positions = positions
            self._cond.notify_all()
        self._emit({"type": "positions", "positions": [dict(p) for p in positions]})

    def _put_orders(self, orders):
        with self._lock:
            self._orders = orders
        self._emit({"type": "orders", "orders": [dict(o) for o in orders]})

    def _put_account(self, account):
        with self._lock:
            if account == self._account:
                return
            self._account = account
        self._emit({"type": "account", "account": dict(account)})

    def _put_news(self, news):
        news = sorted((dict(n) for n in news or []), key=lambda n: n.get("t") or 0)
        with self._lock:
            if news == self._news:
                return
            self._news = news
        self._emit({"type": "news", "news": [dict(n) for n in news]})


# ------------------------------------------------------------------------------------------------------------------------------
# ShadowBroker: a simulated PrimeXBT futures broker over any quote source
# ------------------------------------------------------------------------------------------------------------------------------
class ShadowBroker:
    """A simulated PrimeXBT futures broker over ANY quote source.

    The engine feeds it quotes with on_quote(bid, ask, ts) from whatever feed is running and trades it with the Feed calls.
    PXTrader's rules (PROTOCOL.md + the P0 round trip):
      * market orders fill at the ask (buy) / bid (sell) plus adverse slippage uniform 0..slippage_max (rounded to 0.01)
      * a long's SL and TP trigger on the BID, a short's on the ASK; a triggered order fills at the first price that crossed it,
        so a stop that the price gaps through fills beyond the stop (the barrel); SL fills take the same adverse slippage
        (stop_slippage), TP fills do not
      * an already-crossed TP or SL is accepted and fills at once (on place and on set_protective)
      * hedge mode: every place() opens its own position id; partial close in qty_step with >= min_qty left
      * report rows (newest first) carry rpl = realised P&L in USD before fee, and fee (fee_rate x notional, 0 by default)
    Activity titles/bodies copy PXTrader: "Market order filled" / "Buy 0.01 XAU/USD @ 3926.59",
    "Stop loss linked to position" / "15500001: Stop loss #2190000002 sell XAU/USD @ 3925.59", "... replaced", "... triggered",
    "... filled" ("Sell 0.01 XAU/USD @ 3925.40"), "... cancelled".
    subscribe(fn) gets {"type":"activity"|"positions"|"account"|"orders", ...} synchronously, after the broker lock is released.
    Extras: place(..., fill_price=x) opens at an exact price (the Twin / eject counterfactual); result(position_id) sums a position.
    """
    mode = "shadow"
    can_trade = True

    def __init__(self, balance=25.0, slippage_max=0.0, seed=None, account_id="SHADOW", account_type="SHADOW", symbol=SYMBOL,
                 min_qty=0.01, qty_step=0.01, fee_rate=0.0, leverage=1000.0, currency="USD", stop_slippage=True,
                 pos_id0=15500001, order_id0=2190000001, clock=None, rng=None):
        self._lock = threading.RLock()
        self._rng = rng if rng is not None else random.Random(seed)
        self._clock = clock or time.time
        self._subs = []
        self.balance = float(balance)
        self.slippage_max = max(0.0, float(slippage_max or 0.0))
        self.stop_slippage = bool(stop_slippage)
        self.account_id, self.account_type, self.currency = account_id, account_type, currency
        self.symbol = symbol
        self.min_qty, self.qty_step = float(min_qty), float(qty_step)
        self.fee_rate, self.leverage = float(fee_rate), float(leverage)
        self._pos = {}                 # id -> internal position
        self._orders = {}              # id -> working protective order
        self._report = []              # executed / cancelled order rows, oldest first
        self._activity = collections.deque(maxlen=ACTIVITY_KEEP)
        self._quote = None             # (bid, ask, ts)
        self._pid = itertools.count(int(pos_id0))
        self._oid = itertools.count(int(order_id0))

    # ---- plumbing -------------------------------------------------------------------------------------------------------------
    def subscribe(self, fn):
        with self._lock:
            if fn not in self._subs:
                self._subs.append(fn)
        return fn

    def unsubscribe(self, fn):
        with self._lock:
            if fn in self._subs:
                self._subs.remove(fn)

    def now(self):
        return self._clock()

    def _flush(self, evs):
        if not evs:
            return
        subs = list(self._subs)
        for ev in evs:
            for fn in subs:
                try:
                    fn(ev)
                except Exception as e:                   # noqa: BLE001
                    _log(f"shadow subscriber error: {type(e).__name__}: {scrub(str(e))[:200]}")

    def _act(self, evs, title, body, level, ts):
        a = {"t": float(ts), "title": title, "body": body, "level": level}
        self._activity.append(a)
        evs.append({"type": "activity", **a})

    def _slip(self):
        if self.slippage_max <= 0:
            return 0.0
        return round(self._rng.uniform(0.0, self.slippage_max), 2)

    @staticmethod
    def _name(kind):
        return "Stop loss" if kind == "STOP_LOSS" else "Take profit"

    def _row(self, **kw):
        ts = kw.pop("ts")
        row = {"id": None, "type": "MARKET", "status": "EXECUTED", "side": None, "qty": None, "executedPrice": None,
               "executedQty": 0.0, "rpl": 0.0, "fee": 0.0, "positionId": None, "closeReason": "EXECUTION",
               "executedAt": iso_z(ts), "executed_ts": float(ts), "symbol": self.symbol, "triggerPrice": None}
        row.update(kw)
        self._report.append(row)
        return row

    # ---- views ----------------------------------------------------------------------------------------------------------------
    def _mark(self, p):
        if self._quote is None:
            return p["open_price"]
        return self._quote[0] if p["side"] > 0 else self._quote[1]

    def _pos_view(self, p):
        mark = self._mark(p)
        return {"id": p["id"], "side": p["side"], "qty": p["qty"], "open_price": p["open_price"], "mark": mark,
                "upl": round(p["side"] * (mark - p["open_price"]) * p["qty"], 6), "sl": p["sl"], "tp": p["tp"],
                "sl_order": p["sl_order"], "tp_order": p["tp_order"], "open_time": p["open_time"], "symbol": self.symbol}

    def _upl(self):
        return float(sum(p["side"] * (self._mark(p) - p["open_price"]) * p["qty"] for p in self._pos.values()))

    def _available(self):
        used = sum(p["open_price"] * p["qty"] / self.leverage for p in self._pos.values())
        return self.balance + self._upl() - used

    def _account_locked(self):
        upl = self._upl()
        return {"id": self.account_id, "type": self.account_type, "balance": round(self.balance, 6),
                "equity": round(self.balance + upl, 6), "upl": round(upl, 6), "available": round(self._available(), 6),
                "currency": self.currency}

    def positions(self):
        with self._lock:
            return [self._pos_view(p) for p in self._pos.values()]

    def position(self, position_id):
        with self._lock:
            p = self._pos.get(self._pid_key(position_id))
            return self._pos_view(p) if p else None

    def orders(self):
        with self._lock:
            return [dict(o) for o in self._orders.values()]

    def account(self):
        with self._lock:
            return self._account_locked()

    def activity(self):
        with self._lock:
            return [dict(a) for a in self._activity]

    def quote(self):
        with self._lock:
            if self._quote is None:
                return None
            b, a, ts = self._quote
            return {"bid": b, "ask": a, "mid": round((a + b) / 2.0, PX_DP + 1), "spread": round(a - b, PX_DP), "ts": ts}

    def state(self):
        return {"quote": self.quote(), "account": self.account(), "positions": self.positions(), "orders": self.orders(),
                "activity": self.activity()}

    def result(self, position_id):
        """sum of a position's executed rows: {"closed", "rpl", "fee", "net", "open_price", "exit_price", "exit_type", "exit_ts"}"""
        pid = self._pid_key(position_id)
        with self._lock:
            rows = [r for r in self._report if r["positionId"] == pid and r["status"] == "EXECUTED"]
            if not rows:
                return None
            opening = rows[0]
            exits = [r for r in rows[1:] if r["side"] != opening["side"]]
            rpl = round(sum(r["rpl"] for r in rows), 6)
            fee = round(sum(r["fee"] for r in rows), 6)
            last = exits[-1] if exits else None
            return {"closed": pid not in self._pos, "rpl": rpl, "fee": fee, "net": round(rpl - fee, 6),
                    "open_price": opening["executedPrice"], "exit_price": last["executedPrice"] if last else None,
                    "exit_type": last["type"] if last else None, "exit_ts": last["executed_ts"] if last else None}

    def _snapshot_events(self):
        return [{"type": "positions", "positions": [self._pos_view(p) for p in self._pos.values()]},
                {"type": "orders", "orders": [dict(o) for o in self._orders.values()]},
                {"type": "account", "account": self._account_locked()}]

    @staticmethod
    def _pid_key(position_id):
        try:
            return int(position_id)
        except (TypeError, ValueError):
            return position_id

    # ---- the market moves -----------------------------------------------------------------------------------------------------
    def on_quote(self, bid, ask, ts=None):
        """a new quote from any source: SL/TP triggers exactly like PXTrader. Returns the events it produced."""
        evs = []
        with self._lock:
            ts = self._clock() if ts is None else float(ts)
            self._quote = (r2(bid), r2(ask), ts)
            touched = False
            for pid in list(self._pos):
                touched |= self._check_triggers(pid, evs, ts)
            if touched:
                evs += self._snapshot_events()
        self._flush(evs)
        return evs

    def _check_triggers(self, pid, evs, ts):
        p = self._pos.get(pid)
        if p is None or self._quote is None:
            return False
        bid, ask, _ = self._quote
        long_ = p["side"] > 0
        px = bid if long_ else ask
        sl_hit = p["sl"] is not None and (px <= p["sl"] if long_ else px >= p["sl"])
        tp_hit = p["tp"] is not None and (px >= p["tp"] if long_ else px <= p["tp"])
        if sl_hit:
            self._trigger(p, "STOP_LOSS", px, evs, ts)
            return True
        if tp_hit:
            self._trigger(p, "TAKE_PROFIT", px, evs, ts)
            return True
        return False

    def _trigger(self, p, kind, px, evs, ts):
        name = self._name(kind)
        key = "sl" if kind == "STOP_LOSS" else "tp"
        oid, trig = p[key + "_order"], p[key]
        exit_side = "sell" if p["side"] > 0 else "buy"
        self._act(evs, f"{name} triggered", f"{p['id']}: {name} #{oid} {exit_side} {self.symbol} @ {trig:.{PX_DP}f}", "INFO", ts)
        slip = self._slip() if (kind == "STOP_LOSS" and self.stop_slippage) else 0.0
        fill = r2(px - p["side"] * slip)
        self._orders.pop(oid, None)
        p[key + "_order"] = None
        self._execute(p, p["qty"], fill, kind, oid, evs, ts, f"{name} filled", trigger=trig)

    def _cancel_protective(self, p, evs, ts):
        for kind in ("STOP_LOSS", "TAKE_PROFIT"):
            key = "sl" if kind == "STOP_LOSS" else "tp"
            oid = p[key + "_order"]
            if oid is None:
                continue
            name = self._name(kind)
            self._orders.pop(oid, None)
            exit_side = "SELL" if p["side"] > 0 else "BUY"
            self._row(ts=ts, id=oid, type=kind, status="CANCELLED", side=exit_side, qty=p["qty"], positionId=p["id"],
                      closeReason="CANCELLED", triggerPrice=p[key])
            self._act(evs, f"{name} cancelled", f"{p['id']}: {name} #{oid} {exit_side.lower()} {self.symbol} @ {p[key]:.{PX_DP}f}",
                      "INFO", ts)
            p[key + "_order"] = None

    def _execute(self, p, qty, fill, otype, oid, evs, ts, title, trigger=None):
        """close qty of position p at fill (all of it when qty >= p.qty). A manual close cancels the protective orders first
        ("Stop loss cancelled", "Take profit cancelled", "Market order filled"); a triggered one reports its fill first
        ("Take profit triggered", "Take profit filled", "Stop loss cancelled") - the order PXTrader shows."""
        full = qty >= p["qty"] - 1e-9
        if full:
            qty = p["qty"]
            if otype == "MARKET":
                self._cancel_protective(p, evs, ts)
        exit_side = "SELL" if p["side"] > 0 else "BUY"
        rpl = round(p["side"] * (fill - p["open_price"]) * qty, 6)
        fee = round(self.fee_rate * fill * qty, 6)
        self.balance = round(self.balance + rpl - fee, 9)
        self._row(ts=ts, id=oid, type=otype, side=exit_side, qty=qty, executedPrice=fill, executedQty=qty, rpl=rpl, fee=fee,
                  positionId=p["id"], triggerPrice=trigger)
        self._act(evs, title, f"{exit_side.capitalize()} {qty:.2f} {self.symbol} @ {fill:.{PX_DP}f}", "SUCCESS", ts)
        if full:
            if otype != "MARKET":
                self._cancel_protective(p, evs, ts)
            del self._pos[p["id"]]
        else:
            p["qty"] = round(p["qty"] - qty, 8)
            for key in ("sl_order", "tp_order"):
                o = self._orders.get(p[key])
                if o:
                    o["qty"] = p["qty"]
        return rpl, fee

    def _link(self, p, kind, price, evs, ts):
        name = self._name(kind)
        key = "sl" if kind == "STOP_LOSS" else "tp"
        exit_side = "sell" if p["side"] > 0 else "buy"
        old = p[key + "_order"]
        oid = next(self._oid)
        if old is not None:
            self._orders.pop(old, None)
            self._row(ts=ts, id=old, type=kind, status="CANCELLED", side=exit_side.upper(), qty=p["qty"], positionId=p["id"],
                      closeReason="REPLACED", triggerPrice=p[key])
            title = f"{name} replaced"
        else:
            title = f"{name} linked to position"
        p[key], p[key + "_order"] = price, oid
        self._orders[oid] = {"id": oid, "type": kind, "status": "AWAITING", "side": -p["side"], "qty": p["qty"],
                             "trigger": price, "position_id": p["id"], "protective": True}
        self._act(evs, title, f"{p['id']}: {name} #{oid} {exit_side} {self.symbol} @ {price:.{PX_DP}f}", "SUCCESS", ts)
        return oid

    # ---- trading (the Feed signatures) -----------------------------------------------------------------------------------------
    def place(self, side, qty, sl=None, tp=None, timeout=5.0, fill_price=None):
        t0 = time.perf_counter()
        try:
            side = int(side)
        except (TypeError, ValueError):
            side = 0
        if side not in (1, -1):
            return _ret(False, "BAD_SIDE", t0)
        if not qty_ok(qty, self.qty_step, self.min_qty):
            return _ret(False, "BAD_QTY", t0)
        qty = round(float(qty), 2)
        evs = []
        with self._lock:
            if fill_price is None and self._quote is None:
                return _ret(False, "NO_QUOTE", t0)
            ts = self._clock()
            q = self._quote
            if fill_price is None:
                slip = self._slip()
                fill = r2((q[1] if side > 0 else q[0]) + side * slip)
            else:
                fill = r2(fill_price)
                slip = 0.0
            if fill * qty / self.leverage > self._available() + 1e-12:
                return _ret(False, "INSUFFICIENT_FUNDS", t0)
            pid, oid = next(self._pid), next(self._oid)
            fee = round(self.fee_rate * fill * qty, 6)
            self.balance = round(self.balance - fee, 9)
            p = {"id": pid, "side": side, "qty": qty, "qty0": qty, "open_price": fill, "open_time": ts,
                 "sl": None, "tp": None, "sl_order": None, "tp_order": None}
            self._pos[pid] = p
            word = "BUY" if side > 0 else "SELL"
            self._row(ts=ts, id=oid, type="MARKET", side=word, qty=qty, executedPrice=fill, executedQty=qty, fee=fee, positionId=pid)
            self._act(evs, "Market order filled", f"{word.capitalize()} {qty:.2f} {self.symbol} @ {fill:.{PX_DP}f}", "SUCCESS", ts)
            if sl is not None:
                self._link(p, "STOP_LOSS", r2(sl), evs, ts)
            if tp is not None:
                self._link(p, "TAKE_PROFIT", r2(tp), evs, ts)
            res = _ret(True, None, None, order_id=oid, position_id=pid, fill_price=fill, sl=p["sl"], tp=p["tp"],
                       sl_order=p["sl_order"], tp_order=p["tp_order"], slippage=slip,
                       quote={"bid": q[0], "ask": q[1]} if q else None)
            self._check_triggers(pid, evs, ts)           # an already-crossed TP / SL fills at once
            evs += self._snapshot_events()
        self._flush(evs)
        res["rtt_ms"] = round((time.perf_counter() - t0) * 1000.0, 3)
        return res

    def set_protective(self, position_id, kind, price, timeout=5.0):
        t0 = time.perf_counter()
        kind = str(kind or "").upper()
        if kind not in ("STOP_LOSS", "TAKE_PROFIT"):
            return _ret(False, "BAD_KIND", t0)
        if fnum(price) is None:
            return _ret(False, "BAD_PROTECTIVE", t0)
        evs = []
        with self._lock:
            pid = self._pid_key(position_id)
            p = self._pos.get(pid)
            if p is None:
                return _ret(False, f"POSITION_NOT_FOUND: 120: Not found position #{position_id}", t0)
            ts = self._clock()
            oid = self._link(p, kind, r2(price), evs, ts)
            self._check_triggers(pid, evs, ts)           # an already-crossed one fills at once
            evs += self._snapshot_events()
        self._flush(evs)
        return _ret(True, None, t0, order_id=oid, price=r2(price))

    def check_protective(self, position_id, price, timeout=3.0):
        t0 = time.perf_counter()
        with self._lock:
            p = self._pos.get(self._pid_key(position_id))
            if p is None:
                return _ret(False, f"POSITION_NOT_FOUND: 120: Not found position #{position_id}", t0)
            px = r2(price)
            pl = round(p["side"] * (px - p["open_price"]) * p["qty"], 6)
        return _ret(True, None, t0, resolution="OK", resolutionLevel="INFO", profitLoss=pl)

    def close(self, position_id, qty=None, timeout=5.0, fill_price=None):
        t0 = time.perf_counter()
        evs = []
        with self._lock:
            pid = self._pid_key(position_id)
            p = self._pos.get(pid)
            if p is None:
                return _ret(False, f"POSITION_NOT_FOUND: 120: Not found position #{position_id}", t0)
            if qty is not None and not qty_ok(qty, self.qty_step, self.min_qty):
                return _ret(False, "BAD_QTY", t0)                # validate before rounding: 0.015 must not become 0.01
            if qty is None or float(qty) >= p["qty"] - 1e-9:
                q = p["qty"]
            else:
                q = round(float(qty), 2)
                if p["qty"] - q < self.min_qty - 1e-9:
                    return _ret(False, "MIN_ORDER_SIZE", t0)
            if fill_price is None:
                if self._quote is None:
                    return _ret(False, "NO_QUOTE", t0)
                px = self._quote[0] if p["side"] > 0 else self._quote[1]
                fill = r2(px - p["side"] * self._slip())
            else:
                fill = r2(fill_price)
            ts = self._clock()
            oid = next(self._oid)
            full = q >= p["qty"] - 1e-9
            rpl, fee = self._execute(p, q, fill, "MARKET", oid, evs, ts, "Market order filled")
            remaining = 0.0 if full else p["qty"]
            evs += self._snapshot_events()
        self._flush(evs)
        return _ret(True, None, t0, order_id=oid, fill_price=fill, qty=q, rpl=rpl, fee=fee, remaining=remaining)

    def orders_report(self, since_ts=0.0, timeout=5.0):
        since = float(since_ts or 0.0)
        with self._lock:
            rows = [dict(r) for r in self._report if r["executed_ts"] >= since]
        rows.reverse()                                   # newest first, like report/orders2
        return rows


# ------------------------------------------------------------------------------------------------------------------------------
# SimFeed: a synthetic XAU/USD market + a ShadowBroker account
# ------------------------------------------------------------------------------------------------------------------------------
class _Market:
    """The synthetic XAU/USD process in market seconds. Deterministic for a given rng; SimFeed guards it with its lock.
    Regimes calm / active / storm (Markov switching), a slow OU drift (the day's trend), fat tails, news spikes, and true gaps of
    $0.40-$1.50 that skip every price in between. Spread 0.33 by day; 0.45-0.80 at night and in storms; 0.60-0.80 in a spike."""
    SIGMA = {"calm": 0.05, "active": 0.12, "storm": 0.24}        # $ per sqrt(market second)
    QUOTE_DT = {"calm": 0.45, "active": 0.36, "storm": 0.15}     # mean seconds between quotes (~2.5/s; storms sprint)
    STAY = {"calm": 900.0, "active": 600.0, "storm": 150.0}      # mean regime duration
    NEXT = {"calm": (("active", 0.8), ("storm", 0.2)),
            "active": (("calm", 0.65), ("storm", 0.35)),
            "storm": (("active", 0.7), ("calm", 0.3))}
    GAP_EVERY = 7200.0                                           # mean market seconds between random gaps (x3 in a storm)
    SPIKE_EVERY = 3600.0                                         # mean market seconds between unscheduled spikes
    DAY_SPREAD = 0.33

    def __init__(self, rng, mid, regime="active"):
        self.rng = rng
        self.mid = float(mid)
        self.regime = regime
        self.hold_until = 0.0
        self.drift = 0.0
        self.t = 0.0
        self.spike = None
        self.gap_pending = None
        self.force_night = None
        self.last_gap = None
        self._wide = None
        self._wide_why = None
        self._wide_until = 0.0

    def next_dt(self):
        mean = 0.12 if self.spike else self.QUOTE_DT[self.regime]
        return min(2.5, max(0.05, self.rng.gammavariate(2.5, mean / 2.5)))

    def set_regime(self, regime, hold=0.0):
        self.regime = regime
        self.hold_until = self.t + float(hold)

    def start_spike(self, direction=None, size=None, seconds=None, gap=None):
        r = self.rng
        d = direction if direction in (1, -1) else r.choice((1, -1))
        size = abs(float(size)) if size else r.uniform(3.0, 8.0)
        dur = float(seconds) if seconds else r.uniform(15.0, 45.0)
        self.spike = {"left": dur, "rate": d * size / dur, "dir": d}
        self.set_regime("storm", hold=dur + r.uniform(120.0, 300.0))
        if (gap if gap is not None else r.random() < 0.3) and self.gap_pending is None:
            self.gap_pending = d * r.uniform(0.40, 1.50)
        return d

    def spread(self, night):
        why = "spike" if self.spike else ("storm" if self.regime == "storm" else ("night" if night else None))
        if why is None:
            self._wide = self._wide_why = None
            return self.DAY_SPREAD
        if self._wide is None or why != self._wide_why or self.t >= self._wide_until:
            lo, hi = (0.60, 0.80) if why == "spike" else (0.45, 0.80)
            self._wide = round(self.rng.uniform(lo, hi), 2)
            self._wide_why = why
            self._wide_until = self.t + self.rng.uniform(20.0, 90.0)
        return self._wide

    def quote(self, night):
        n = self.force_night if self.force_night is not None else night
        sp = self.spread(n)
        bid = round(self.mid - sp / 2.0, 2)
        return bid, round(bid + sp, 2), sp

    def step(self, dt, night=False):
        r = self.rng
        self.t += dt
        if self.t >= self.hold_until and r.random() < dt / self.STAY[self.regime]:
            x, acc = r.random(), 0.0
            for name, p in self.NEXT[self.regime]:
                acc += p
                if x < acc:
                    self.regime = name
                    break
        self.drift += -self.drift * dt / 7200.0 + 1.67e-5 * math.sqrt(dt) * r.gauss(0.0, 1.0)
        if self.spike is None and r.random() < dt / self.SPIKE_EVERY:
            self.start_spike()
        if self.gap_pending is None and r.random() < dt * (3.0 if self.regime == "storm" else 1.0) / self.GAP_EVERY:
            self.gap_pending = r.choice((1, -1)) * r.uniform(0.40, 1.50)
        gap = None
        if self.gap_pending is not None:
            gap, self.gap_pending = self.gap_pending, None
            move = gap                                   # a true gap: one quote jump, nothing printed in between
        else:
            z = r.gauss(0.0, 1.0)
            if r.random() < 0.01:
                z *= 2.5
            move = self.drift * dt + self.SIGMA[self.regime] * math.sqrt(dt) * z
        if self.spike is not None:
            if gap is None:
                move += self.spike["rate"] * min(dt, self.spike["left"])
            self.spike["left"] -= dt
            if self.spike["left"] <= 0:
                self.spike = None
        self.mid += move
        self.last_gap = gap
        bid, ask, sp = self.quote(night)
        return bid, ask, sp, gap


_NEWS_HIGH = [("US CPI m/m", "US"), ("FOMC Statement", "US"), ("US Non-Farm Payrolls", "US"), ("ECB Rate Decision", "EU"),
              ("US ISM Manufacturing PMI", "US"), ("US Retail Sales m/m", "US"), ("Fed Chair Speaks", "US"), ("US PPI m/m", "US")]
_NEWS_MINOR = [("German ZEW Economic Sentiment", "DE", "medium"), ("UK Claimant Count Change", "GB", "medium"),
               ("US Crude Oil Inventories", "US", "low"), ("Japan Household Spending", "JP", "low"),
               ("US Initial Jobless Claims", "US", "medium"), ("Australia Retail Sales", "AU", "low")]


class SimFeed(Feed):
    """A synthetic XAU/USD market that behaves like PXTrader (CONTRACT.md section 4), trading through a ShadowBroker that starts
    at $25.00.  Deterministic with a seed: the k-th quote's price is fixed by (seed, k) whatever the wall timing.
    speed multiplies market time (speed 4 = four market seconds per wall second); every timestamp stays wall-clock.

      SimFeed(seed=7, speed=1.0)            the server's sim mode (start() runs the market thread)
      SimFeed(seed=7, manual=True)          tests: no threads; pump(n) quotes or advance(seconds) on a virtual clock
      feed.sim_force("gap", size=-1.2)      next quote gaps by size ($0.40-$1.50 random when size is None)
      feed.sim_force("storm", seconds=180)  also "calm", "active", "spike", "news" (a high-impact event in `minutes`), "night"/"day"/
                                            "auto" (spread mode), "close"/"open" (market closed), "silence" (no quotes for `seconds`)
    A usable quote, 330 history bars and the account exist right after construction (before start()).
    """
    mode = "sim"
    can_trade = True

    def __init__(self, seed=None, speed=1.0, config=None, *, balance=25.0, start_price=3926.0, manual=False, start_ts=None,
                 latency=(0.06, 0.18), slippage_max=0.06, regime="active", cfg=None, account_id="SIM-1", **_ignored):
        if isinstance(seed, dict):                       # SimFeed(config_dict) tolerated
            config, seed = seed, seed.get("seed")
        super().__init__(config if config is not None else cfg)
        self.seed = int(seed) if seed is not None else random.SystemRandom().randrange(1, 2 ** 31)
        self.speed = max(0.01, float(speed or 1.0))
        self.manual = bool(manual)
        self.latency = tuple(latency) if latency else None
        self.start_price = float(start_price)
        self.dead_hours = self.cfg.get("dead_hours_utc") or DEFAULTS["dead_hours_utc"]
        configure_price(int(self.cfg.get("price_dp", 2)))
        self._scale = float(self.cfg.get("sim_scale", 1.0) or 1.0)                    # Zee 2026-11-04: EUR/USD practice = the gold process mapped
        self._sbase = float(self.cfg.get("sim_base", self.start_price))
        self._sp_scale = float(self.cfg.get("sim_spread_scale", 1.0) or 1.0)
        slippage_max = float(self.cfg.get("sim_slippage_max", slippage_max))
        self._vclock = float(start_ts) if start_ts is not None else time.time()
        self._mrng = random.Random(f"gg-sim-{self.seed}-market")
        self._hrng = random.Random(f"gg-sim-{self.seed}-history")
        self._nrng = random.Random(f"gg-sim-{self.seed}-news")
        self._lrng = random.Random(f"gg-sim-{self.seed}-latency")
        self._mkt = _Market(self._mrng, self.start_price, regime=regime)
        self._pending_dt = None
        self._closed = False
        self._silent_until = 0.0
        self._last_marks = 0.0
        self._thread = None
        self._day = collections.deque()                  # closed bars of the last 24 h (h24 / l24 / ch24)
        self._h24c = self._l24c = self._o24 = None
        self._news_sched = []
        self._news_i = 0
        self._news_pub = 0.0
        self.broker = ShadowBroker(balance=balance, slippage_max=slippage_max, rng=random.Random(f"gg-sim-{self.seed}-broker"),
                                   account_id=account_id, account_type="SIM", symbol=self.symbol, min_qty=self.min_qty,
                                   qty_step=self.qty_step, clock=self.now)
        self.broker.subscribe(self._on_broker)
        now = self.now()
        bid, ask, sp = self._mkt.quote(in_dead_hours(now, self.dead_hours))
        hist = self._gen_history(int(now // 60) * 60, bid)
        if self._scale != 1.0 or self._sbase != self.start_price:
            hist = [[b[0]] + [self._mp(v) for v in b[1:5]] + list(b[5:]) for b in hist]
        bid, ask, sp = self._mq(bid, ask, sp)
        with self._lock:
            self._bars = [list(b) for b in hist[-330:]]
            self._day.extend(hist)
            self._recalc_day()
        self._news_next_t = now + 45 * 60 + self._nrng.uniform(0, 300)
        self._extend_news(now)
        self._put_quote(bid, ask, now, st="OPEN", spread=sp)
        self._bar_tick(bid, now, 1)
        self.broker.on_quote(bid, ask, now)
        self._account = self.broker.account()

    def _mp(self, p):                                   # a gold-process price on the active symbol's scale
        return self._sbase + (float(p) - self.start_price) * self._scale

    def _mq(self, bid, ask, sp):
        if self._scale == 1.0 and self._sbase == self.start_price and self._sp_scale == 1.0:
            return bid, ask, sp
        tick = 10.0 ** -PX_DP
        mid = self._mp((bid + ask) / 2.0)
        spx = max(tick, round(sp * self._sp_scale, PX_DP))
        b = round(mid - spx / 2.0, PX_DP)
        return b, round(b + spx, PX_DP), spx

    # ---- clock / lifecycle ----------------------------------------------------------------------------------------------------
    def now(self):
        return self._vclock if self.manual else time.time()

    def start(self):
        if self.manual:
            raise RuntimeError("SimFeed(manual=True) is driven by pump()/advance(), not start()")
        with self._lock:
            if self._started:
                return
        super().start()
        self._thread = threading.Thread(target=self._run, name="gg-sim-market", daemon=True)
        self._thread.start()

    def stop(self):
        super().stop()
        t, self._thread = self._thread, None
        if t is not None and t is not threading.current_thread():
            t.join(timeout=2.0)

    def _run(self):
        next_wall = time.time()
        while not self._stop_ev.is_set():
            now = time.time()
            if self._closed or now < self._silent_until:
                self._stop_ev.wait(0.2)
                next_wall = time.time()
                self._check_status()
                continue
            with self._lock:
                dt = self._mkt.next_dt()
            next_wall += dt / self.speed
            delay = next_wall - time.time()
            if delay > 0:
                if self._stop_ev.wait(delay):
                    break
            elif delay < -2.0:                           # we fell behind (laptop slept): resume, never burst
                next_wall = time.time()
            self._step(dt, time.time())

    # ---- manual driving (tests) -----------------------------------------------------------------------------------------------
    def _go_manual(self):
        """pump()/advance() on a feed whose market thread never started: drive it by hand from now on"""
        if self.manual:
            return
        if self._thread is not None:
            raise RuntimeError("pump()/advance() cannot drive a SimFeed whose market thread is running")
        self._vclock = time.time()
        self.manual = True

    def pump(self, n=1):
        """manual mode: generate n quote steps on the virtual clock; returns the quotes [(ts, bid, ask), ...]"""
        self._go_manual()
        out = []
        for _ in range(int(n)):
            with self._lock:
                dt = self._pending_dt if self._pending_dt is not None else self._mkt.next_dt()
                self._pending_dt = None
            self._vclock += dt / self.speed
            if self._closed or self._vclock < self._silent_until:
                continue
            q = self._step(dt, self._vclock)
            if q:
                out.append(q)
        return out

    def advance(self, seconds):
        """manual mode: run the market for `seconds` of (wall) clock; returns the quotes produced"""
        self._go_manual()
        end = self._vclock + float(seconds)
        out = []
        while True:
            with self._lock:
                dt = self._pending_dt if self._pending_dt is not None else self._mkt.next_dt()
                self._pending_dt = None
            if self._vclock + dt / self.speed > end:
                with self._lock:
                    self._pending_dt = dt
                self._vclock = end
                break
            self._vclock += dt / self.speed
            if self._closed or self._vclock < self._silent_until:
                continue
            q = self._step(dt, self._vclock)
            if q:
                out.append(q)
        self._check_status()
        return out

    # ---- the market step ------------------------------------------------------------------------------------------------------
    def _step(self, dt, ts):
        with self._lock:
            if self._closed:
                return None
            self._fire_news(ts)
            bid, ask, sp, gap = self._mkt.step(dt, in_dead_hours(ts, self.dead_hours))
            bid, ask, sp = self._mq(bid, ask, sp)
            gap = gap * self._scale if gap else gap
            vol = (1 + int(self._mrng.random() * 4)) * (2 if self._mkt.regime == "storm" else 1)
        self._put_quote(bid, ask, ts, st="OPEN", spread=sp)
        self._bar_tick(bid, ts, vol)
        self.broker.on_quote(bid, ask, ts)
        if ts - self._last_marks >= 1.0:                 # like PX's metrics / positions pushes, ~1/s
            self._last_marks = ts
            acc = self.broker.account()
            with self._lock:
                self._account = acc
            self._emit({"type": "positions", "positions": self.broker.positions()})
            self._emit({"type": "account", "account": acc})
        if ts > self._news_next_t - 24 * 3600:
            self._extend_news(ts)
        elif ts - self._news_pub > 600:
            self._publish_news(ts)
        self._check_status()
        return (ts, bid, ask)

    def _bar_tick(self, bid, ts, vol):
        mt = int(ts // 60) * 60
        evs = []
        with self._lock:
            last = self._bars[-1] if self._bars else None
            if last is None or mt > last[0]:
                if last is not None:
                    evs.append({"type": "bar", "bar": list(last), "closed": True})
                    self._day.append(list(last))
                    self._recalc_day()
                nb = [mt, bid, bid, bid, bid, vol]
                self._bars.append(nb)
                if len(self._bars) > KEEP_BARS:
                    del self._bars[:len(self._bars) - KEEP_BARS]
            elif mt == last[0]:
                nb = [mt, last[1], max(last[2], bid), min(last[3], bid), bid, last[5] + vol]
                self._bars[-1] = nb
            else:
                return
            self._h24 = max(self._h24c, nb[2]) if self._h24c is not None else nb[2]
            self._l24 = min(self._l24c, nb[3]) if self._l24c is not None else nb[3]
            self._ch24 = round(bid - self._o24, 2) if self._o24 is not None else 0.0
            evs.append({"type": "bar", "bar": list(nb), "closed": False})
        for ev in evs:
            self._emit(ev)

    def _recalc_day(self):
        if self._day:
            cut = self._day[-1][0] - 24 * 3600 + 60
            while self._day and self._day[0][0] < cut:
                self._day.popleft()
        if self._day:
            self._h24c = max(b[2] for b in self._day)
            self._l24c = min(b[3] for b in self._day)
            self._o24 = self._day[0][1]
            self._h24, self._l24 = self._h24c, self._l24c
        else:
            self._h24c = self._l24c = self._o24 = None

    def _gen_history(self, end_t, last_bid, n_day=1440):
        """24 h of 1-minute bid bars ending before end_t, shifted so the last close meets the first live bid"""
        r = self._hrng
        m = _Market(r, 3900.0 + r.uniform(-25, 25), regime=r.choice(("calm", "active", "active")))
        m.SPIKE_EVERY = 4 * 3600.0
        bars = []
        t0 = int(end_t) - n_day * 60
        for i in range(n_day):
            t = t0 + i * 60
            night = in_dead_hours(t, self.dead_hours)
            o = h = lo = c = None
            v = 0
            for _ in range(12):
                bid, _ask, _sp, _gap = m.step(5.0, night)
                if o is None:
                    o = h = lo = bid
                h, lo, c = max(h, bid), min(lo, bid), bid
                v += r.randint(5, 18) * (2 if m.regime == "storm" else 1)
            bars.append([t, o, h, lo, c, v])
        shift = last_bid - bars[-1][4]
        for b in bars:
            b[1], b[2], b[3], b[4] = (round(b[1] + shift, 2), round(b[2] + shift, 2), round(b[3] + shift, 2), round(b[4] + shift, 2))
        return bars

    # ---- news -----------------------------------------------------------------------------------------------------------------
    def _extend_news(self, now):
        r = self._nrng
        upto = now + 48 * 3600
        while self._news_next_t < upto:
            t = self._news_next_t
            title, ctry = _NEWS_HIGH[self._news_i % len(_NEWS_HIGH)]
            self._news_sched.append({"t": round(t), "title": title, "impact": "high", "country": ctry, "_fired": False})
            mt, (mtitle, mctry, mimp) = t + r.uniform(60, 100) * 60, _NEWS_MINOR[self._news_i % len(_NEWS_MINOR)]
            self._news_sched.append({"t": round(mt), "title": mtitle, "impact": mimp, "country": mctry, "_fired": False})
            self._news_i += 1
            self._news_next_t = t + r.uniform(150, 210) * 60
        self._news_sched.sort(key=lambda n: n["t"])
        self._publish_news(now)

    def _publish_news(self, now):
        self._news_pub = now
        self._news_sched = [n for n in self._news_sched if n["t"] >= now - 6 * 3600]
        self._put_news([{k: v for k, v in n.items() if not k.startswith("_")} for n in self._news_sched
                        if now - 3 * 3600 <= n["t"] <= now + 48 * 3600])

    def _fire_news(self, ts):
        for n in self._news_sched:
            if not n["_fired"] and n["t"] <= ts:
                n["_fired"] = True
                if n["impact"] == "high" and ts - n["t"] < 300:
                    self._mkt.start_spike()

    # ---- forcing (tests and demos) --------------------------------------------------------------------------------------------
    def sim_force(self, kind, **kw):
        """force a market event: gap | storm | calm | active | spike | news | night | day | auto | close | open | silence | resume"""
        k = str(kind or "").lower()
        out = {"ok": True, "kind": k}
        with self._lock:
            m = self._mkt
            if k == "gap":
                size = kw.get("size")
                if size is None:
                    d = kw.get("direction") if kw.get("direction") in (1, -1) else self._mrng.choice((1, -1))
                    size = d * self._mrng.uniform(0.40, 1.50)
                m.gap_pending = float(size)
                out["size"] = round(float(size), 2)
            elif k in ("storm", "calm", "active"):
                m.set_regime(k, hold=float(kw.get("seconds", 180.0)))
            elif k in ("spike", "lightning"):
                out["direction"] = m.start_spike(direction=kw.get("direction"), size=kw.get("size"), seconds=kw.get("seconds"),
                                                 gap=kw.get("gap"))
            elif k == "news":
                t = round(self.now() + float(kw.get("minutes", 2.0)) * 60.0)
                self._news_sched.append({"t": t, "title": kw.get("title", "US CPI m/m (forced)"), "impact": kw.get("impact", "high"),
                                         "country": kw.get("country", "US"), "_fired": False})
                self._news_sched.sort(key=lambda n: n["t"])
                out["t"] = t
            elif k == "night":
                m.force_night = bool(kw.get("on", True))
            elif k == "day":
                m.force_night = False
            elif k == "auto":
                m.force_night = None
            elif k in ("close", "closed"):
                self._closed = True
                if self._quote:
                    self._quote = dict(self._quote, st="CLOSED")
            elif k == "open":
                self._closed = False
                if self._quote:
                    self._quote = dict(self._quote, st="OPEN")
            elif k in ("silence", "freeze", "dead"):
                self._silent_until = self.now() + float(kw.get("seconds", 20.0))
                out["until"] = self._silent_until
            elif k in ("resume", "thaw", "alive"):
                self._silent_until = 0.0
            else:
                raise ValueError(f"sim_force: unknown kind {kind!r}")
        if k == "news":
            self._publish_news(self.now())
        self._check_status()
        return out

    @property
    def regime(self):
        return self._mkt.regime

    # ---- status / state -------------------------------------------------------------------------------------------------------
    def _status(self, now):
        if self._closed:
            return False, "market_closed"
        return super()._status(now)

    def _market_open(self, now, ok):
        return bool(ok and not self._closed)

    def state(self):
        s = super().state()
        s["account"] = self.broker.account()
        s["positions"] = self.broker.positions()
        s["orders"] = self.broker.orders()
        s["sim"] = {"regime": self._mkt.regime, "spike": self._mkt.spike is not None, "seed": self.seed, "speed": self.speed,
                    "closed": self._closed}
        return s

    # ---- trading through the shadow broker ------------------------------------------------------------------------------------
    def _on_broker(self, ev):
        if ev.get("type") == "activity":
            self._add_activity(ev.get("title"), ev.get("body"), ev.get("level"), ev.get("t"))
        else:
            if ev.get("type") == "account":
                with self._lock:
                    self._account = ev.get("account")
            self._emit(ev)

    def _block(self):
        if self._closed:
            return "MARKET_CLOSED"
        q = self._quote
        if q is None:
            return "NO_QUOTE"
        if self.now() - q["ts"] > self.feed_dead_s:
            return "FEED_DEAD"
        return None

    def _lag(self, scale=1.0):
        if self.manual or not self.latency:
            return
        lo, hi = self.latency
        with self._lock:
            d = self._lrng.uniform(lo, hi) * scale
        time.sleep(d)

    def place(self, side, qty, sl, tp, timeout=5.0):
        t0 = time.perf_counter()
        why = self._block()
        if why:
            return _ret(False, why, t0)
        self._lag()
        r = self.broker.place(side, qty, sl, tp)
        r["rtt_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
        return r

    def set_protective(self, position_id, kind, price, timeout=5.0):
        t0 = time.perf_counter()
        why = self._block()
        if why:
            return _ret(False, why, t0)
        self._lag(0.6)
        r = self.broker.set_protective(position_id, kind, price)
        r["rtt_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
        return r

    def check_protective(self, position_id, price, timeout=3.0):
        t0 = time.perf_counter()
        self._lag(0.4)
        r = self.broker.check_protective(position_id, price)
        r["rtt_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
        return r

    def close(self, position_id, qty=None, timeout=5.0):
        t0 = time.perf_counter()
        why = self._block()
        if why:
            return _ret(False, why, t0)
        self._lag()
        r = self.broker.close(position_id, qty)
        r["rtt_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
        return r

    def orders_report(self, since_ts, timeout=5.0):
        return self.broker.orders_report(since_ts)


# ------------------------------------------------------------------------------------------------------------------------------
# PXTrader text formats (trading/activity bodies)
# ------------------------------------------------------------------------------------------------------------------------------
_FILL_RE = re.compile(r"\b(buy|sell)\s+([\d][\d.,]*)\s+(\S+)\s*@\s*([\d,]+(?:\.\d+)?)", re.I)
_LINK_RE = re.compile(r"(\d+)\s*:\s*(stop loss|take profit)\s*#\s*(\d+)\s+(buy|sell)\s+(\S+)\s*@\s*([\d,]+(?:\.\d+)?)", re.I)
_ACTION_RE = re.compile(r'"action"\s*:\s*"([^"]+)"')
_RID_RE = re.compile(r'"rid"\s*:\s*(\d+)')
_FWS_ONLY = frozenset({"fx/market", "positions", "metrics", "orders/active2", "trading/activity", "bar", "bars", "report/orders2"})
_UNCERTAIN = ("TIMEOUT", "SEND_UNCERTAIN", "SOCKET_CLOSED", "PAGE_RELOADED", "CDP_CLOSED")


def parse_fill_text(text):
    """'Buy 0.01 XAU/USD @ 3926.59' -> {"side": "buy", "qty": 0.01, "symbol": "XAU/USD", "price": 3926.59}"""
    m = _FILL_RE.search(text or "")
    if not m:
        return None
    return {"side": m.group(1).lower(), "qty": fnum(m.group(2)), "symbol": m.group(3).upper(), "price": fnum(m.group(4))}


def parse_link_text(text):
    """'15394511: Stop loss #2188572786 sell XAU/USD @ 3923.71' -> position id, kind, order id, side, symbol, price"""
    m = _LINK_RE.search(text or "")
    if not m:
        return None
    return {"position_id": int(m.group(1)), "kind": "STOP_LOSS" if m.group(2).lower() == "stop loss" else "TAKE_PROFIT",
            "order_id": int(m.group(3)), "side": m.group(4).lower(), "symbol": m.group(5).upper(), "price": fnum(m.group(6))}


def px_error_text(err):
    if isinstance(err, dict):
        code = err.get("code") or err.get("type") or "ERROR"
        desc = err.get("description") or err.get("message") or err.get("text")
        return f"{code}: {desc}" if desc else str(code)
    return str(err)


class ReportList(list):
    """orders_report() result: a plain list of rows that also carries .ok / .error / .rtt_ms"""

    def __init__(self, rows=(), ok=True, error=None, rtt_ms=0.0):
        super().__init__(rows)
        self.ok, self.error, self.rtt_ms = ok, error, rtt_ms


# ------------------------------------------------------------------------------------------------------------------------------
# economic calendar: PrimeXBT's /economic-calendar/events response -> [{t, title, impact, country}]
# ------------------------------------------------------------------------------------------------------------------------------
_CAL_T = ("time", "timestamp", "date", "datetime", "dateTime", "dateUtc", "date_utc", "eventTime", "eventDate", "releaseTime",
          "releaseDate", "start", "startTime", "startDate", "ts", "t")
_CAL_TITLE = ("title", "eventTitle", "name", "event", "eventName", "event_name", "indicator", "label", "description")
_CAL_IMPACT = ("impact", "importance", "volatility", "priority", "level", "significance", "severity", "stars")
_CAL_COUNTRY = ("country", "countryCode", "country_code", "regionCode", "currency", "region", "countryName", "zone")


def _cal_list(obj, depth=0):
    if depth > 5:
        return None
    if isinstance(obj, list):
        dicts = [x for x in obj if isinstance(x, dict)]
        if dicts and any(any(k in x for k in _CAL_TITLE) for x in dicts[:10]):
            return dicts
        out = []
        for x in obj:
            sub = _cal_list(x, depth + 1)
            if sub:
                out.extend(sub)
        return out or None
    if isinstance(obj, dict):
        for k in ("data", "events", "items", "result", "results", "list", "content", "rows", "calendar"):
            if k in obj:
                sub = _cal_list(obj[k], depth + 1)
                if sub:
                    return sub
        for v in obj.values():
            if isinstance(v, (list, dict)):
                sub = _cal_list(v, depth + 1)
                if sub:
                    return sub
    return None


def _cal_impact(v):
    if v is None or isinstance(v, bool):
        return "low"
    if isinstance(v, (int, float)):
        return "high" if v >= 3 else ("medium" if v >= 2 else "low")
    s = str(v).strip().lower()
    if s.replace(".", "", 1).isdigit():
        return _cal_impact(float(s))
    if "high" in s or s in ("h", "red", "***", "strong") or "bull3" in s:
        return "high"
    if "med" in s or "moderate" in s or s in ("m", "orange", "**") or "bull2" in s:
        return "medium"
    return "low"


def _cal_time(e):
    d, tm = e.get("date"), e.get("time")
    if isinstance(d, str) and isinstance(tm, str) and re.match(r"^\d{1,2}:\d{2}", tm.strip()) and len(d.strip()) <= 10:
        t = to_unix(f"{d.strip()} {tm.strip()[:5]}")
        if t:
            return t
    for k in _CAL_T:
        if k in e:
            t = to_unix(e[k])
            if t and t > 1e9:
                return t
    return None


def normalise_calendar(obj):
    """tolerant normaliser: finds the list of events anywhere in the response; impact is exactly "high" | "medium" | "low".
    Returns None when the object holds no recognisable event list (keep the previous calendar then)."""
    events = _cal_list(obj)
    if events is None:
        return None
    out, seen = [], set()
    for e in events:
        t = _cal_time(e)
        title = next((str(e[k]) for k in _CAL_TITLE if e.get(k)), None)
        if t is None or not title:
            continue
        impact = next((_cal_impact(e[k]) for k in _CAL_IMPACT if k in e), "low")
        country = next((str(e[k]) for k in _CAL_COUNTRY if e.get(k)), "")
        key = (round(t), title)
        if key in seen:
            continue
        seen.add(key)
        out.append({"t": float(t), "title": title, "impact": impact, "country": country})
    out.sort(key=lambda n: n["t"])
    return out


# ------------------------------------------------------------------------------------------------------------------------------
# Recorder: recordings/YYYYMMDD_HHMMSS.jsonl  {"t": unix, "dir": "in"|"out", "frame": {...}}  (scrubbed; never a socket URL)
# ------------------------------------------------------------------------------------------------------------------------------
class Recorder:
    def __init__(self, directory=None, path=None):
        d = directory or os.path.join(HERE, "recordings")
        os.makedirs(d, exist_ok=True)
        self.path = path or os.path.join(d, time.strftime("%Y%m%d_%H%M%S") + ".jsonl")
        self._f = open(self.path, "a", encoding="utf-8")
        self._lock = threading.Lock()
        self._last_flush = time.time()
        self.lines = 0

    def write(self, direction, frame, t=None):
        line = json.dumps({"t": round(float(t if t is not None else time.time()), 3), "dir": direction, "frame": scrub(frame)},
                          separators=(",", ":"), default=str)
        with self._lock:
            if self._f is None:
                return
            self._f.write(line + "\n")
            self.lines += 1
            if time.time() - self._last_flush > 1.0:
                self._f.flush()
                self._last_flush = time.time()

    def close(self):
        with self._lock:
            if self._f is not None:
                try:
                    self._f.flush()
                    self._f.close()
                finally:
                    self._f = None


# ------------------------------------------------------------------------------------------------------------------------------
# PXChannel: money-safe request/response over the page's futures socket
# ------------------------------------------------------------------------------------------------------------------------------
class SendNotOpen(RuntimeError):
    """the frame was certainly NOT sent (no socket / the page socket is closed)"""


class _Call:
    __slots__ = ("rid", "action", "ev", "frame", "t0", "t_rx", "sent", "error")


class PXChannel:
    """Request/response matching for OUR frames on the PXTrader futures socket.

    * rids count up from 900000 (the page's own rids start at ~1 and never collide)
    * the pending slot is registered BEFORE the frame is sent (a reply can come back in 35 ms)
    * on_response(frame) (called by the frame reader) matches by rid and wakes the waiter
    * a top-level "error" object, or a non-null body.error, fails the call with "CODE: description" (definite: the broker said no)
    * a timeout, an uncertain send or a socket loss fails it as NOT definite: the frame may have been executed
    * sender(msg) must raise SendNotOpen when the frame certainly did not leave; any other exception = uncertain. Thread-safe.
    """

    def __init__(self, sender, rid0=RID0):
        self._sender = sender
        self._lock = threading.Lock()
        self._rid = itertools.count(int(rid0))
        self._pending = {}

    def next_rid(self):
        with self._lock:
            return next(self._rid)

    def pending(self):
        with self._lock:
            return len(self._pending)

    def begin(self, action, body, kind="REQUEST", before_send=None):
        c = _Call()
        c.rid, c.action, c.ev, c.frame, c.t_rx, c.sent, c.error = self.next_rid(), action, threading.Event(), None, None, None, None
        with self._lock:
            self._pending[c.rid] = c
        msg = {"type": kind, "rid": c.rid, "action": action, "body": body}
        if before_send is not None:
            before_send(c.rid, msg)
        c.t0 = time.perf_counter()
        try:
            self._sender(msg)
            c.sent = True
        except SendNotOpen:
            c.sent, c.error = False, "SOCKET_LOST"
            with self._lock:
                self._pending.pop(c.rid, None)
        except Exception:                                # noqa: BLE001  e.g. a CDP timeout: the frame may have left
            c.sent, c.error = None, "SEND_UNCERTAIN"
        return c

    def result(self, c, wait=0.0):
        """the call's result dict, or None while there is no reply yet (after waiting up to `wait` seconds)"""
        base = {"rid": c.rid, "action": c.action}
        if c.sent is False:
            return {"ok": False, "error": c.error, "definite": True, "rtt_ms": 0.0, "body": None, "frame": None, **base}
        if not c.ev.wait(max(0.0, wait)):
            return None
        f = c.frame or {}
        rtt = round(((c.t_rx or time.perf_counter()) - c.t0) * 1000.0, 1)
        if f.get("error"):
            local = bool(f.get("_local"))
            return {"ok": False, "error": px_error_text(f["error"]), "definite": not local, "rtt_ms": rtt, "body": f.get("body"),
                    "frame": f, **base}
        body = f.get("body")
        if isinstance(body, dict) and body.get("error"):
            return {"ok": False, "error": px_error_text(body["error"]), "definite": True, "rtt_ms": rtt, "body": body, "frame": f,
                    **base}
        return {"ok": True, "error": None, "definite": True, "rtt_ms": rtt, "body": body, "frame": f, **base}

    def drop(self, c):
        with self._lock:
            self._pending.pop(c.rid, None)

    def request(self, action, body, timeout=5.0, kind="REQUEST", before_send=None):
        """send one frame and wait for its RESPONSE -> {"ok","error","definite","rtt_ms","rid","body","frame"}"""
        c = self.begin(action, body, kind, before_send)
        r = self.result(c, timeout)
        self.drop(c)
        if r is None:
            err = "TIMEOUT" if c.sent else (c.error or "SEND_UNCERTAIN")
            return {"ok": False, "error": err, "definite": False, "rtt_ms": round((time.perf_counter() - c.t0) * 1000.0, 1),
                    "body": None, "frame": None, "rid": c.rid, "action": action}
        return r

    def on_response(self, frame):
        rid = frame.get("rid") if isinstance(frame, dict) else None
        with self._lock:
            c = self._pending.pop(rid, None)
        if c is None:
            return False
        c.frame, c.t_rx = frame, time.perf_counter()
        c.ev.set()
        return True

    def fail_all(self, code):
        """wake every waiter with a local, NOT definite error (socket closed / page reloaded)"""
        with self._lock:
            calls = list(self._pending.values())
            self._pending.clear()
        for c in calls:
            c.frame = {"type": "RESPONSE", "rid": c.rid, "_local": True,
                       "error": {"code": code, "description": "the socket went away before the reply"}}
            c.t_rx = time.perf_counter()
            c.ev.set()


# ------------------------------------------------------------------------------------------------------------------------------
# PXFeedBase: the PXTrader frame parser shared by LiveFeed and ReplayFeed
# ------------------------------------------------------------------------------------------------------------------------------
class PXFeedBase(Feed):
    """Builds the Feed state from PXTrader frames. _on_frame(raw, direction, ts) is the single entry point and is pure state
    building, so it can be unit-tested offline with frames copied from PROTOCOL.md."""

    def __init__(self, config=None):
        super().__init__(config)
        self._t_shift = 0                # ReplayFeed: recorded bar / news times -> today (whole minutes)
        self._sub_reqs = {}              # rid -> (symbolId, barSize) of "bar" SUBSCRIPTIONs seen going out
        self._bars_reqs = {}             # rid -> (symbol, bar_size) of "bars" REQUESTs seen going out
        self._bar_sids = {}              # sid -> (symbolId, barSize)
        self._last_sub_bar = 0.0         # receipt time of the last accepted 1-minute bar event
        self._last_fx = 0.0              # receipt time of the last fx/market quote for our symbol
        self._last_rx = 0.0
        self._server_offset = None       # PX server clock - local clock (s)
        self._recorder = None
        self._chan = None
        self._account_meta = {}          # pfx/accounts2 rows by lower-case accountId
        self._metrics_id = None
        self.frames_in = 0

    # ---- entry point ----------------------------------------------------------------------------------------------------------
    def _on_frame(self, raw, direction="in", ts=None, req_id=None):
        """one websocket frame (JSON text or dict). direction "in" = server -> page, "out" = page -> server. Returns the dict."""
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8", "replace")
        if isinstance(raw, str):
            s = raw.strip()
            if not s.startswith("{"):
                return None
            try:
                f = json.loads(s)
            except ValueError:
                return None
        elif isinstance(raw, dict):
            f = raw
        else:
            return None
        if not isinstance(f, dict):
            return None
        ts = self.now() if ts is None else float(ts)
        rec = self._recorder
        if rec is not None:
            try:
                rec.write(direction, f, ts)
            except Exception:                            # noqa: BLE001  a full disk never stops the game
                pass
        if direction == "out":
            self._note_out(f)
            return f
        self.frames_in += 1
        self._last_rx = ts
        typ, action = f.get("type"), f.get("action")
        try:
            if typ == "RESPONSE":
                self._on_response(f, action, f.get("body"), ts)
            elif typ == "EVENT" or (typ is None and action):
                self._on_event(f, action, f.get("body"), ts)
            elif typ == "GG_CALENDAR":
                body = f.get("body") or {}
                self._put_news(self._shift_news(body.get("data") or []))
            elif typ == "GG_SID":                        # our 1-minute subscription id, written when it was inherited
                body = f.get("body") or {}
                if body.get("sid") is not None:
                    self._bar_sids[body["sid"]] = (body.get("symbolId", self.sym_id), str(body.get("barSize") or "1M"))
        except Exception as e:                           # noqa: BLE001  one odd frame must never kill the reader
            _log(f"frame {action!r}: {type(e).__name__}: {scrub(str(e))[:160]}")
        return f

    def _note_out(self, f):
        """remember what our (and the page's) requests asked for, so their RESPONSEs and subscription EVENTs can be read"""
        rid, action, body = f.get("rid"), f.get("action"), f.get("body")
        if rid is None or not isinstance(body, dict):
            return
        with self._lock:
            if action == "bar" and f.get("type") in ("SUBSCRIPTION", "REQUEST"):
                self._sub_reqs[rid] = (body.get("symbolId"), str(body.get("barSize") or ""))
            elif action == "bars":
                self._bars_reqs[rid] = (body.get("symbol"), str(body.get("bar_size") or body.get("barSize") or ""))
            for d in (self._sub_reqs, self._bars_reqs):
                while len(d) > 200:
                    d.pop(next(iter(d)))

    def _is_1m(self, req):
        return req is not None and str(req[1]).upper() == "1M"

    def _is_ours_1m(self, req):
        if not self._is_1m(req):
            return False
        try:
            return int(req[0]) == self.sym_id
        except (TypeError, ValueError):
            return False

    # ---- responses ------------------------------------------------------------------------------------------------------------
    def _on_response(self, f, action, body, ts):
        rid = f.get("rid")
        chan = self._chan
        if chan is not None and chan.on_response(f):
            with self._cond:
                self._cond.notify_all()
        with self._lock:
            req_bars = self._bars_reqs.pop(rid, None)
            req_sub = self._sub_reqs.pop(rid, None)
        if action == "bars" or req_bars is not None:
            req = req_bars
            data = body.get("data") if isinstance(body, dict) else (body if isinstance(body, list) else None)
            if not f.get("error") and isinstance(data, list) and data and isinstance(data[0], (list, tuple)):
                if self._history_is_ours(req, data):
                    self._set_history(data, self._t_shift)
        elif action == "bar" or req_sub is not None:
            req = req_sub
            sid = f.get("sid")
            if sid is None and isinstance(body, dict):
                sid = body.get("sid")
            if req is not None and sid is not None:
                self._bar_sids[sid] = req
            if self._is_ours_1m(req) and not f.get("error"):
                self._take_bar_data(body, ts)
        elif action == "time" and isinstance(body, dict):
            st = fnum(body.get("time"))
            if st:
                self._server_offset = (st / 1000.0 if st > 1e11 else st) - ts
        elif action in ("positions", "metrics", "orders/active2") and not f.get("error") and not (
                chan is not None and isinstance(rid, int) and rid >= RID0):
            # the page's own snapshot (e.g. its subscription answered after a reload, or a recording of our seed requests):
            # the server pushes these only on change, so a RESPONSE may be the only word about a flat account
            if action == "positions":
                self._on_positions(body)
            elif action == "metrics":
                self._on_metrics(body)
            else:
                self._on_orders(body)

    def _history_is_ours(self, req, data):
        if req is not None:
            sym = req[0]
            return self._is_1m(req) and (sym is None or str(sym).upper() == self.symbol)
        # a history we did not see requested: accept only 1-minute spacing near our own price
        ts_ = [int(float(r[0])) for r in data[-20:] if r]
        if len(ts_) < 3:
            return False
        steps = sorted(b - a for a, b in zip(ts_, ts_[1:]))
        if steps[len(steps) // 2] != 60:
            return False
        q = self._quote
        c = fnum(data[-1][4]) if len(data[-1]) > 4 else None
        return q is None or (c is not None and abs(c - q["bid"]) / q["bid"] < 0.02)

    def _take_bar_data(self, body, ts):
        data = body.get("data") if isinstance(body, dict) else body
        if isinstance(data, dict):
            data = [data.get("t"), data.get("o"), data.get("h"), data.get("l"), data.get("c"), data.get("v")]
        if not isinstance(data, list) or not data:
            return
        rows = data if isinstance(data[0], (list, tuple)) else [data]
        for row in rows:
            if len(row) >= 5:
                self._merge_bar(row, self._t_shift)
        self._last_sub_bar = ts

    # ---- events ---------------------------------------------------------------------------------------------------------------
    def _on_event(self, f, action, body, ts):
        if action == "fx/market":
            self._on_fx(body, ts)
        elif action == "bar":
            req = self._bar_sids.get(f.get("sid"))
            if self._is_ours_1m(req):
                self._take_bar_data(body, ts)
        elif action == "metrics":
            self._on_metrics(body)
        elif action == "pfx/accounts2":
            self._on_accounts(body)
        elif action == "positions":
            self._on_positions(body)
        elif action == "orders/active2":
            self._on_orders(body)
        elif action == "trading/activity":
            self._on_activity(body, ts)
        elif action == "markets2":
            self._on_markets2(body, ts)

    def _on_fx(self, body, ts):
        if not isinstance(body, dict):
            return
        try:
            if int(body.get("symId", body.get("symbolId"))) != self.sym_id:
                return
        except (TypeError, ValueError):
            return
        a, b = fnum(body.get("a")), fnum(body.get("b"))
        if not a or not b or a <= 0 or b <= 0 or a < b:
            return
        self._last_fx = ts
        with self._lock:
            self._h24 = fnum(body.get("h24"), self._h24)
            self._l24 = fnum(body.get("l24"), self._l24)
            self._ch24 = fnum(body.get("ch"), self._ch24)
        self._put_quote(b, a, ts, st=body.get("st"), last=fnum(body.get("lp")))
        self._bar_from_quote(r2(b), ts)

    def _on_markets2(self, body, ts):
        """fallback quote (~1/s) only while fx/market for our symbol is silent (e.g. the chart shows another symbol)"""
        if ts - self._last_fx < 3.0 or not isinstance(body, dict) or not isinstance(body.get("data"), list):
            return
        for m in body["data"]:
            if isinstance(m, dict) and str(m.get("symbol") or "").upper() == self.symbol:
                a, b = fnum(m.get("ask")), fnum(m.get("bid"))
                if a and b and a >= b > 0:
                    self._put_quote(b, a, ts, st=(self._quote or {}).get("st"), last=fnum(m.get("lastTrade")))
                    self._bar_from_quote(r2(b), ts)
                return

    def _bar_from_quote(self, bid, ts):
        """keep the forming bar alive from bid quotes while our 1-minute subscription is silent (> 5 s);
        the subscription's own bar overwrites it as soon as it speaks again"""
        if ts - self._last_sub_bar <= 5.0:
            return
        mt = int((ts + (self._server_offset or 0.0)) // 60) * 60 + self._t_shift
        with self._lock:
            last = self._bars[-1] if self._bars else None
            if last is not None and mt < last[0]:
                return
            if last is not None and mt == last[0]:
                bar = [mt, last[1], max(last[2], bid), min(last[3], bid), bid, (last[5] or 0) + 1]
            else:
                bar = [mt, bid, bid, bid, bid, 1]
        self._merge_bar(bar)

    def _on_metrics(self, body):
        if not isinstance(body, dict) or body.get("balance") is None:
            return
        acc_id = body.get("accountId")
        meta = self._account_meta.get(str(acc_id).lower(), {})
        typ = meta.get("type") or ("DEMO" if body.get("demo") else "LIVE")
        self._metrics_id = acc_id
        self._put_account(self._account_view(acc_id, typ, fnum(body.get("balance")), fnum(body.get("equity")),
                                             fnum(body.get("upl")), fnum(body.get("availableMargin")),
                                             body.get("currency") or meta.get("currency") or "USD"))

    def _account_view(self, acc_id, typ, balance, equity, upl, available, currency):
        return {"id": acc_id, "type": typ, "balance": balance, "equity": equity, "upl": upl, "available": available,
                "currency": currency}

    def _on_accounts(self, body):
        rows = body.get("data") if isinstance(body, dict) else body
        if not isinstance(rows, list):
            return
        for r in rows:
            if isinstance(r, dict) and r.get("accountId"):
                self._account_meta[str(r["accountId"]).lower()] = {"type": r.get("type"), "currency": r.get("currency"),
                                                                   "specName": r.get("specName"), "row": r}
        if self._metrics_id is None:                     # until metrics speaks, show the PXTrader account from the list
            pick = next((r for r in rows if isinstance(r, dict) and "pxtrader" in str(r.get("specName") or "").lower()), None)
            pick = pick or next((r for r in rows if isinstance(r, dict) and r.get("accountId")), None)
            if pick:
                self._put_account(self._account_view(pick.get("accountId"), pick.get("type") or "LIVE", fnum(pick.get("balance")),
                                                     fnum(pick.get("equity")), fnum(pick.get("upl")),
                                                     fnum(pick.get("availableMargin")), pick.get("currency") or "USD"))
        elif self._account is not None:                  # metrics knows the account: refresh its type from the list
            meta = self._account_meta.get(str(self._metrics_id).lower())
            if meta and meta.get("type") and meta["type"] != self._account.get("type"):
                self._put_account(dict(self._account, type=meta["type"]))

    def _on_positions(self, body):
        data = body.get("data") if isinstance(body, dict) else body
        if not isinstance(data, list):
            return
        out = []
        for agg in data:
            if not isinstance(agg, dict):
                continue
            subs = agg.get("subPositions")
            if isinstance(subs, list) and subs:
                out.extend(p for p in (self._parse_position(s, agg) for s in subs) if p)
            elif agg.get("id"):                          # one-way mode: the aggregate is the position
                p = self._parse_position(agg, None)
                if p:
                    out.append(p)
        self._put_positions(out)

    @staticmethod
    def _parse_position(s, agg):
        if not isinstance(s, dict):
            return None
        try:
            pid = int(s.get("id"))
        except (TypeError, ValueError):
            return None
        if not pid:
            return None
        side = str(s.get("side") or (agg or {}).get("side") or "").upper()
        return {"id": pid, "side": 1 if side == "BUY" else (-1 if side == "SELL" else 0), "qty": fnum(s.get("qty")),
                "open_price": fnum(s.get("openPrice")), "mark": fnum(s.get("markPrice")), "upl": fnum(s.get("upl")),
                "sl": fnum(s.get("stopLossPrice")), "tp": fnum(s.get("takeProfitPrice")),
                "sl_order": s.get("stopLossOrderId"), "tp_order": s.get("takeProfitOrderId"),
                "open_time": to_unix(s.get("openTime")), "symbol": s.get("symbol") or (agg or {}).get("symbol")}

    _DONE = frozenset({"EXECUTED", "CANCELLED", "CANCELED", "REJECTED", "EXPIRED", "FILLED", "CLOSED"})

    @staticmethod
    def _parse_order(o):
        try:
            oid = int(o.get("id"))
        except (TypeError, ValueError):
            return None
        side = str(o.get("side") or "").upper()
        return {"id": oid, "type": o.get("type"), "status": o.get("status"), "side": 1 if side == "BUY" else (-1 if side == "SELL" else 0),
                "qty": fnum(o.get("qty")), "trigger": fnum(o.get("triggerPrice"), fnum(o.get("price"))),
                "position_id": o.get("positionId"), "protective": bool(o.get("protective")), "symbol": o.get("symbol")}

    def _on_orders(self, body):
        if isinstance(body, dict) and isinstance(body.get("data"), list):
            rows, full = body["data"], True
        elif isinstance(body, list):
            rows, full = body, True
        elif isinstance(body, dict) and body.get("id") is not None:
            rows, full = [body], False
        else:
            return
        parsed = [o for o in (self._parse_order(r) for r in rows if isinstance(r, dict)) if o]
        if full:
            orders = [o for o in parsed if str(o["status"] or "").upper() not in self._DONE]
        else:
            with self._lock:
                cur = {o["id"]: o for o in self._orders}
            for o in parsed:
                if str(o["status"] or "").upper() in self._DONE:
                    cur.pop(o["id"], None)
                else:
                    cur[o["id"]] = o
            orders = list(cur.values())
        self._put_orders(orders)

    def _on_activity(self, body, ts):
        if not isinstance(body, dict):
            return
        items = body["data"] if isinstance(body.get("data"), list) else [body]
        for it in items:
            if isinstance(it, dict) and (it.get("title") or it.get("body")):
                self._add_activity(it.get("title"), it.get("body") or it.get("message") or it.get("text"), it.get("level"), ts)

    def _shift_news(self, news):
        out = []
        for n in news or []:
            if isinstance(n, dict) and n.get("t") is not None:
                d = dict(n)
                d["t"] = float(d["t"]) + self._t_shift
                d["impact"] = _cal_impact(d.get("impact"))
                out.append(d)
        return out


# ------------------------------------------------------------------------------------------------------------------------------
# ReplayFeed: a recording played through the LiveFeed parser
# ------------------------------------------------------------------------------------------------------------------------------
class ReplayFeed(PXFeedBase):
    """Plays recordings/X.jsonl at its original pace x speed through the same parser as LiveFeed. can_trade is False: every order
    returns {"ok": False, "error": "REPLAY"}. Quotes and activity get the wall-clock time of their replay; bar and calendar times
    are moved forward by whole minutes (time_shift="auto") so the replay looks like today; the account reads type "REPLAY".
    loop=True starts again at the end (bars are rebuilt); otherwise state() reports ok False, reason "replay ended"."""
    mode = "replay"
    can_trade = False

    def __init__(self, path=None, speed=1.0, config=None, *, file=None, loop=False, time_shift="auto", cfg=None, **_ignored):
        if isinstance(path, dict):
            config, path = path, None
        super().__init__(config if config is not None else cfg)
        self.path = path or file
        if not self.path:
            raise ValueError("ReplayFeed needs the path of a recording (recordings/YYYYMMDD_HHMMSS.jsonl)")
        self.speed = max(0.01, float(speed or 1.0))
        self.loop = bool(loop)
        self.time_shift_mode = time_shift
        self._lines = self._load(self.path)
        self.finished = False
        self.played = 0
        self.lap = 0                                     # +1 each time a looping replay starts the recording again
        self.lap_t = None                                # wall time the current lap started (its quotes are stamped later)
        self._thread = None

    def state(self):
        d = super().state()
        d["replay_lap"] = self.lap                       # the engine resets its price memory at a seam (the jump is not a move)
        d["replay_lap_t"] = self.lap_t
        return d

    @staticmethod
    def _load(path):
        out = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if isinstance(d, dict) and isinstance(d.get("frame"), dict) and fnum(d.get("t")) is not None:
                    out.append((fnum(d["t"]), "out" if d.get("dir") == "out" else "in", d["frame"]))
        out.sort(key=lambda x: x[0])
        return out

    def _calc_shift(self, wall0):
        if not self._lines or self.time_shift_mode in (0, None, False):
            return 0
        if isinstance(self.time_shift_mode, (int, float)) and not isinstance(self.time_shift_mode, bool):
            return int(self.time_shift_mode)
        return int(round((wall0 - self._lines[0][0]) / 60.0)) * 60

    def _account_view(self, acc_id, typ, balance, equity, upl, available, currency):
        d = super()._account_view(acc_id, "REPLAY", balance, equity, upl, available, currency)
        d["recorded_type"] = typ
        return d

    def start(self):
        with self._lock:
            if self._started:
                return
        super().start()
        self._thread = threading.Thread(target=self._run, name="gg-replay", daemon=True)
        self._thread.start()

    def stop(self):
        super().stop()
        t, self._thread = self._thread, None
        if t is not None and t is not threading.current_thread():
            t.join(timeout=2.0)

    def _run(self):
        while not self._stop_ev.is_set() and self._lines:
            t0r, wall0 = self._lines[0][0], time.time()
            self._t_shift = self._calc_shift(wall0)
            last_check = 0.0
            for t, d, frame in self._lines:
                delay = wall0 + (t - t0r) / self.speed - time.time()
                if delay > 0 and self._stop_ev.wait(delay):
                    return
                self._on_frame(frame, d, ts=time.time())
                self.played += 1
                if time.time() - last_check > 0.5:
                    last_check = time.time()
                    self._check_status()
            if not self.loop:
                self.finished = True
                break
            with self._lock:                             # next lap: rebuild the bars on the new time shift
                self._bars = []
                self.lap += 1
                self.lap_t = time.time()
        while not self._stop_ev.is_set():                # keep reporting the (stale) status
            self._check_status()
            self._stop_ev.wait(1.0)

    def play_all(self, realtime_ts=True):
        """tests: feed every frame at once (no sleeping); ts = now (fresh) or the recorded time (+ shift)"""
        self._t_shift = self._calc_shift(time.time())
        for t, d, frame in self._lines:
            self._on_frame(frame, d, ts=time.time() if realtime_ts else t + self._t_shift)
            self.played += 1
        if not self.loop:
            self.finished = True
        else:
            with self._lock:
                self.lap += 1
                self.lap_t = time.time()
        return self.played

    def _status(self, now):
        if self.finished and not self.loop:
            return False, "replay ended"
        return super()._status(now)

    def place(self, side, qty, sl, tp, timeout=5.0):
        return _ret(False, "REPLAY")

    def set_protective(self, position_id, kind, price, timeout=5.0):
        return _ret(False, "REPLAY")

    def check_protective(self, position_id, price, timeout=3.0):
        return _ret(False, "REPLAY")

    def close(self, position_id, qty=None, timeout=5.0):
        return _ret(False, "REPLAY")

    def orders_report(self, since_ts, timeout=5.0):
        return ReportList([], ok=False, error="REPLAY")


# ------------------------------------------------------------------------------------------------------------------------------
# LiveFeed: PXTrader 2.0 over CDP (Chrome :9222).  ONLY the main agent runs this; build/test agents never start() it.
# ------------------------------------------------------------------------------------------------------------------------------
class LiveFeed(PXFeedBase):
    """The PXTrader page as the game's market and broker (PROTOCOL.md).

    start(): a supervisor thread attaches with cdpcore.CDPSession.attach(), enables Network + Page, finds the page's futures socket
    (url contains "/v2/fws/"; the url itself is never logged, stored or recorded), requests our own 1-minute history (bars, limit 329)
    and our own 1-minute "bar" SUBSCRIPTION, re-acquires on Network.webSocketClosed / Page.frameNavigated / a failed check and
    re-subscribes on every new socket. Frames come from Network.webSocketFrameReceived/Sent and go through PXFeedBase._on_frame.
    A worker thread does every CDP call that an event asks for (a CDP call from the reader thread would deadlock): the economic
    calendar body (Network.getResponseBody) and its re-issue from the page every 30 min (fetch, credentials 'include').

    Trading (all synchronous): frames are sent on the page's own socket through PXChannel. Safety rails before any frame exists:
    side +-1, qty a multiple of 0.01 and <= max_qty (config live_max_qty, default 0.10 oz), SL and TP both present, on the correct
    sides of each other and within max_protective_dist ($100) of the quote. set_protective / close / check_protective only touch
    positions the game opened: resolved by place() (or found later for one of its own unresolved orders: new since the send, same
    side, qty and SL), kept across restarts in state/feeds_live_owned.json, or adopt()ed explicitly. Anything else is refused
    with NOT_OURS - the game never touches Zee's own positions.
    place() returns order_id at once and resolves position_id from the "<positionId>: Stop loss #... linked to position" activity
    (matched on our exact SL / TP price) or by diffing subPositions (up to resolve_s = 1.5 s after the reply); fill_price from the
    "Market order filled ... @ x" activity, cross-checked against the position's openPrice. If the id is still unknown the result
    carries "resolve_token": feed.resolve(token) keeps looking.
    """
    mode = "live"
    can_trade = True

    def __init__(self, record=False, config=None, *, port=9222, rec_dir=None, max_qty=None, max_protective_dist=100.0,
                 resolve_s=1.5, calendar_every_s=1800.0, cfg=None, session_factory=None, own_file=None, **_ignored):
        if isinstance(record, dict):
            config, record = record, False
        super().__init__(config if config is not None else cfg)
        self.port = int(port)
        self.record = bool(record)
        self.rec_dir = rec_dir or os.path.join(HERE, "recordings")
        self.max_qty = float(max_qty if max_qty is not None else (self.cfg.get("live_max_qty") or 0.10))
        self.max_dist = float(max_protective_dist)
        self.resolve_s = float(resolve_s)
        self.calendar_every_s = float(calendar_every_s)
        self._session_factory = session_factory          # tests inject a fake CDP session; never used live
        self._sess = None
        self._px = None
        self._fws_index = None
        self._fws_reqids = set()
        self._need_acquire = True
        self._conn_reason = "not started"
        self._chan = PXChannel(lambda msg: self._send_frame(msg))
        self._tasks = queue.Queue()
        self._sup = self._worker = None
        self._own = set()                                # position ids this feed opened (or the engine adopted)
        self._own_file = own_file if own_file is not None else os.path.join(HERE, "state", "feeds_live_owned.json")
        self._persist = False                            # switched on by start() on a real page (never in tests)
        self._tokens = collections.deque(maxlen=50)      # (t, token) of orders whose position id was not resolved (kept for the
                                                         # life of the round - bounded by count, never by age)
        self.place_quote_max_age = max(self.feed_stale_s, 2.0) + 1.0   # place() refuses a quote older than this (s)
        self._own_side = {}                              # position id -> side, for the ones this run opened
        self._next_attach = 0.0
        self._last_check = 0.0
        self._last_sub_try = 0.0
        self._cal_req = None                             # {"url", "method", "postData"}: memory only, never logged
        self._cal_ids = set()
        self._cal_last = 0.0
        self._cal_up_last = 0.0                          # the /upcoming calendar (Bearer from the page's own storage)
        self._news_src = {}                              # calendar events by source ("page" capture, "upcoming"): merged
        self.recording_path = None
        self.account_pin = str(self.cfg.get("live_account_id") or "").strip().lower()
        self._account_ok = None                          # False = the page holds ANOTHER account (no trading, no settling)
        self._other_reqids = set()                       # futures sockets of another account: their frames are ignored
        self._book_fresh = False                         # positions known since the last (re)load (a frame or our own REQUEST)
        self._book_t = None
        self._pos_event_t = 0.0                          # receipt time of the last pushed positions EVENT
        self._last_seed = 0.0
        self._seed_queued = False

    # ---- lifecycle ------------------------------------------------------------------------------------------------------------
    def start(self):
        if os.environ.get("GG_FORBID_LIVE") and self._session_factory is None:
            raise RuntimeError("LiveFeed.start() refused: GG_FORBID_LIVE is set (tests and build agents never touch the live page)")
        with self._lock:
            if self._started:
                return
        if self._session_factory is None and self._own_file:
            self._persist = True
            self._load_owned()
        super().start()
        if self.record and self._recorder is None:
            self._recorder = Recorder(self.rec_dir)
            self.recording_path = self._recorder.path
        self._worker = threading.Thread(target=self._work_loop, name="gg-live-worker", daemon=True)
        self._worker.start()
        self._sup = threading.Thread(target=self._supervise, name="gg-live-supervisor", daemon=True)
        self._sup.start()

    def stop(self):
        super().stop()
        self._tasks.put(None)
        sess, self._sess = self._sess, None
        if sess is not None:
            try:
                sess.off(self._on_cdp)
            except Exception:                            # noqa: BLE001
                pass
            try:
                sess.close()                             # closes OUR CDP connection only; the page stays open and logged in
            except Exception:                            # noqa: BLE001
                pass
        self._chan.fail_all("CDP_CLOSED")
        rec, self._recorder = self._recorder, None
        if rec is not None:
            rec.close()
        for t in (self._sup, self._worker):
            if t is not None and t is not threading.current_thread():
                t.join(timeout=2.0)
        self._sup = self._worker = None

    def adopt(self, position_id):
        """let the game manage a position it opened in an earlier session (from its own round log)"""
        try:
            self._own_add(int(position_id))
            return True
        except (TypeError, ValueError):
            return False

    def _own_add(self, pid):
        pid = int(pid)
        if pid in self._own:
            return
        self._own.add(pid)
        if self._persist:
            self._save_owned()

    def _load_owned(self):
        """positions the game opened in earlier runs (state/feeds_live_owned.json), so a restarted game can still manage them"""
        try:
            with open(self._own_file, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            cut = time.time() - 14 * 86400
            for row in d.get("positions", []):
                if fnum(row.get("t"), 0) >= cut:
                    self._own.add(int(row["id"]))
            self._own_t = {int(r["id"]): fnum(r.get("t"), 0) for r in d.get("positions", []) if fnum(r.get("t"), 0) >= cut}
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            pass

    def _save_owned(self):
        try:
            os.makedirs(os.path.dirname(self._own_file), exist_ok=True)
            known = getattr(self, "_own_t", {})
            now = time.time()
            for pid in self._own:
                known.setdefault(pid, now)
            self._own_t = known
            tmp = self._own_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"note": "position ids the game opened on the live account (feeds.LiveFeed); nothing else may be touched",
                           "positions": [{"id": k, "t": v} for k, v in sorted(known.items())]}, fh, indent=1)
            os.replace(tmp, self._own_file)
        except OSError as e:
            _log(f"could not save the owned-positions file: {type(e).__name__}")

    # ---- supervisor -----------------------------------------------------------------------------------------------------------
    def _supervise(self):
        while not self._stop_ev.is_set():
            try:
                self._supervise_once()
            except Exception as e:                       # noqa: BLE001
                self._conn_reason = f"supervisor: {type(e).__name__}"
            self._check_status()
            self._stop_ev.wait(0.5)

    def _supervise_once(self):
        now = time.time()
        sess = self._sess
        if sess is None or not getattr(sess, "alive", False):
            if sess is not None:
                self._sess = None
                self._fws_index = None
                self._chan.fail_all("CDP_CLOSED")
            if now >= self._next_attach:
                self._next_attach = now + 3.0
                self._connect()
            return
        if self._need_acquire:
            self._acquire()
            return
        if now - self._last_check > 10.0:
            self._last_check = now
            if not self._socket_alive():
                self._need_acquire = True
                return
        if (now - self._last_fx < 5.0 and now - self._last_sub_bar > 90.0 and now - self._last_sub_try > 90.0):
            self._subscribe_bar()                        # our subscription went quiet while quotes flow: subscribe again
        if now - self._last_seed > 10.0:
            self._queue_seed()                           # metrics / positions / orders: pushed only on change (PROTOCOL 07:57)
        if now - self._cal_up_last > self.calendar_every_s:
            self._cal_up_last = now
            self._tasks.put(("cal_upcoming", None))

    def _connect(self):
        import cdpcore                                   # local import: SimFeed / ReplayFeed never need websocket-client
        try:
            sess = self._session_factory() if self._session_factory else cdpcore.CDPSession.attach(self.port)
        except Exception as e:                           # noqa: BLE001
            self._conn_reason = ("no PrimeXBT page in the debug Chrome" if "primexbt" in str(e).lower()
                                 else f"Chrome not reachable on :{self.port}")
            return
        sess.on(self._on_cdp)
        try:
            sess.call("Network.enable")
        except Exception:                                # noqa: BLE001
            self._conn_reason = "Network.enable failed"
            try:
                sess.close()
            except Exception:                            # noqa: BLE001
                pass
            return
        try:
            sess.call("Page.enable")
        except Exception:                                # noqa: BLE001
            pass
        self._px = cdpcore.PageSockets(sess)
        self._sess = sess
        self._need_acquire = True
        self._conn_reason = "finding the futures socket"

    # the page's open sockets, kept in window.__gg_socks (same layout as cdpcore.PageSockets); returns NO url - only whether it is
    # the futures socket and the accountId of its query string (the url carries the session JWT and never leaves the page)
    _SOCKETS_JS = r"""function () {
        const socks = this.filter(w => w && w.readyState === 1);
        window.__gg_socks = socks;
        const acct = (w) => { try { return String(new URL(w.url).searchParams.get('accountId') || ''); } catch (e) { return ''; } };
        return socks.map((w, i) => ({ i: i, state: w.readyState, fws: String(w.url).indexOf('/v2/fws/') >= 0, account: acct(w) }));
    }"""

    def _page_sockets(self):
        sess = self._sess
        proto = sess.call("Runtime.evaluate", expression="WebSocket.prototype")["result"]["objectId"]
        arr = sess.call("Runtime.queryObjects", prototypeObjectId=proto)["objects"]["objectId"]
        r = sess.call("Runtime.callFunctionOn", objectId=arr, functionDeclaration=self._SOCKETS_JS, returnByValue=True)
        return r.get("result", {}).get("value") or []

    def _acquire(self):
        try:
            info = self._page_sockets()
        except Exception:                                # noqa: BLE001  (never echo the exception: it could hold a url)
            self._conn_reason = "page sockets not readable"
            return
        fws = [s for s in info or [] if isinstance(s, dict) and s.get("fws") is True and s.get("state", 1) == 1]
        if not fws:
            self._conn_reason = "futures socket not open yet"
            return
        mine = [s for s in fws if not self.account_pin or str(s.get("account") or "").strip().lower() == self.account_pin]
        if not mine:                                     # the page shows another account: never trade or settle on it
            if self._account_ok is not False:
                _log("the page's futures socket belongs to another account - the game will not trade until it is back")
            self._account_ok = False
            self._fws_index = None
            self._conn_reason = "another account is open in the page"
            return
        idx = mine[0].get("i")
        self._account_ok = True
        self._fws_index = int(idx)
        self._need_acquire = False
        self._last_check = time.time()
        self._conn_reason = None
        st = self._socket_sub_state()
        if st is None:                                   # gone again already
            self._need_acquire = True
            return
        self._sync_and_history()
        self._queue_seed()
        self._cal_up_last = time.time()
        self._tasks.put(("cal_upcoming", None))
        sid = st.get("sid") if isinstance(st, dict) else None
        if isinstance(st, dict) and st.get("marked") and sid is not None:
            # our subscription from an earlier run of the game still streams on this socket: adopt its id, never stack another
            self._bar_sids[sid] = (self.sym_id, "1M")
            self._last_sub_try = time.time()
            rec = self._recorder
            if rec is not None:
                rec.write("in", {"type": "GG_SID", "body": {"sid": sid, "symbolId": self.sym_id, "barSize": "1M"}}, time.time())
        else:
            self._subscribe_bar()

    def _js_socket(self, body):
        idx = self._fws_index
        if idx is None or self._sess is None:
            return None
        return self._sess.js("(() => { const w = (window.__gg_socks || [])[%d]; if (!w || w.readyState !== 1) return null; %s })()"
                             % (int(idx), body), timeout=5)

    def _socket_sub_state(self):
        """{"marked": bool, "sid": our subscription id or None} kept on the page's socket object; None = socket gone"""
        try:
            return self._js_socket("return {marked: !!w.__gg_sub1m, sid: (w.__gg_sid1m === undefined ? null : w.__gg_sid1m)};")
        except Exception:                                # noqa: BLE001
            return None

    def _mark_socket(self, sid=None, clear=False):
        try:
            if clear:
                return self._js_socket("w.__gg_sub1m = false; w.__gg_sid1m = undefined; return true;")
            return self._js_socket("w.__gg_sub1m = true; w.__gg_sid1m = %s; return true;" % json.dumps(sid))
        except Exception:                                # noqa: BLE001
            return None

    def _js_account_check(self):
        pin = json.dumps(self.account_pin)
        return ("let a = ''; try { a = String(new URL(w.url).searchParams.get('accountId') || '').toLowerCase(); } catch (e) {} "
                "if (%s && a !== %s) return 'account'; " % (pin, pin))

    def _socket_alive(self):
        try:
            return self._js_socket(self._js_account_check() + "return String(w.url).indexOf('/v2/fws/') >= 0;") is True
        except Exception:                                # noqa: BLE001
            return False

    def _sync_and_history(self):
        """server clock offset + our own 1-minute history (bars, limit 329); on every (re)acquire, so a reconnect fills holes"""
        r = self._chan.request("time", {}, timeout=3.0)
        if r["ok"] and isinstance(r["body"], dict):
            st = fnum(r["body"].get("time"))
            if st:
                self._server_offset = (st / 1000.0 if st > 1e11 else st) - time.time() + r["rtt_ms"] / 2000.0
        to = int(time.time() + (self._server_offset or 0.0))
        r = self._chan.request("bars", {"symbol": self.symbol, "bar_size": "1M", "to": to, "limit": HISTORY_LIMIT, "askOhlc": False},
                               timeout=10.0, before_send=lambda rid, msg: self._note_out(msg))
        return r["ok"]

    def _subscribe_bar(self):
        """our own 1-minute bar SUBSCRIPTION (the page's chart subscription is whatever timeframe the chart shows); its sid is
        kept on the socket object so a restarted game inherits it instead of stacking a second subscription"""
        self._last_sub_try = time.time()
        r = self._chan.request("bar", {"symbolId": self.sym_id, "barSize": "1M", "askOhlc": False}, timeout=10.0,
                               kind="SUBSCRIPTION", before_send=lambda rid, msg: self._note_out(msg))
        if r["ok"]:
            fr = r.get("frame") or {}
            sid = fr.get("sid")
            if sid is None and isinstance(fr.get("body"), dict):
                sid = fr["body"].get("sid")
            if sid is not None:
                self._mark_socket(sid=sid)
        return r["ok"]

    # ---- CDP events (the CDP reader thread: never call the session from here) --------------------------------------------------
    def _on_cdp(self, method, params):
        if method in ("Network.webSocketFrameReceived", "Network.webSocketFrameSent"):
            resp = params.get("response") or {}
            data = resp.get("payloadData")
            if resp.get("opcode", 1) != 1 or not isinstance(data, str) or not data.startswith("{"):
                return
            direction = "in" if method.endswith("Received") else "out"
            if self._from_fws(params.get("requestId"), data):
                self._on_frame(data, direction, ts=time.time(), req_id=params.get("requestId"))
        elif method == "Network.webSocketCreated":
            url = str(params.get("url") or "")
            if "/v2/fws/" in url:
                if self.account_pin and self._url_account(url) != self.account_pin:
                    self._other_reqids.add(params.get("requestId"))       # another account's socket: its frames are not ours
                else:
                    self._fws_reqids.add(params.get("requestId"))
                self._need_acquire = True
            del url                                      # carries the session JWT: never kept
        elif method == "Network.webSocketClosed":
            rq = params.get("requestId")
            self._other_reqids.discard(rq)
            if rq in self._fws_reqids:
                self._fws_reqids.discard(rq)
                self._need_acquire = True
                self._book_fresh = False                 # until the new socket's book is read
                self._chan.fail_all("SOCKET_CLOSED")
        elif method == "Page.frameNavigated":
            if not (params.get("frame") or {}).get("parentId"):
                self._fws_reqids.clear()
                self._other_reqids.clear()
                self._need_acquire = True
                self._fws_index = None
                self._book_fresh = False                 # positions may have closed while the page reloaded
                self._chan.fail_all("PAGE_RELOADED")
        elif method == "Network.requestWillBeSent":
            req = params.get("request") or {}
            if "/economic-calendar/events" in str(req.get("url") or ""):
                rq = params.get("requestId")
                self._cal_ids.add(rq)
                self._cal_req = {"url": req.get("url"), "method": req.get("method") or "POST", "postData": req.get("postData")}
                if params.get("type") in (None, "XHR", "Fetch"):
                    self._cal_xhr = rq                    # Network.replayXHR re-sends it exactly (PROTOCOL: own fetches now get 400)
                if req.get("hasPostData") and req.get("postData") is None:
                    self._tasks.put(("cal_postdata", rq))
        elif method == "Network.responseReceived":
            if "/economic-calendar/events" in str((params.get("response") or {}).get("url") or ""):
                self._cal_ids.add(params.get("requestId"))
        elif method == "Network.loadingFinished":
            rq = params.get("requestId")
            if rq in self._cal_ids:
                self._cal_ids.discard(rq)
                self._tasks.put(("cal_body", rq))
        elif method == "Network.loadingFailed":
            self._cal_ids.discard(params.get("requestId"))

    @staticmethod
    def _url_account(url):
        try:
            import urllib.parse as _up
            return str((_up.parse_qs(_up.urlsplit(url).query).get("accountId") or [""])[0]).strip().lower()
        except Exception:                                # noqa: BLE001
            return ""

    def _from_fws(self, rq, data):
        """True for frames of the futures socket. Learned from Network.webSocketCreated, or from fws-only actions / our rids."""
        if rq in self._other_reqids:
            return False
        if rq in self._fws_reqids:
            return True
        m = _RID_RE.search(data[:300])
        if m and int(m.group(1)) >= RID0:
            self._fws_reqids.add(rq)
            return True
        if self._fws_reqids:
            return False
        m = _ACTION_RE.search(data[:300])
        if m and m.group(1) in _FWS_ONLY:
            self._fws_reqids.add(rq)
            return True
        return False

    # ---- worker: CDP calls requested by events --------------------------------------------------------------------------------
    def _work_loop(self):
        while True:
            task = self._tasks.get()
            if task is None or self._stop_ev.is_set():
                break
            kind, arg = task
            try:
                if kind == "cal_body":
                    self._cal_read(arg)
                elif kind == "cal_postdata":
                    r = self._sess.call("Network.getRequestPostData", timeout=10, requestId=arg)
                    if self._cal_req is not None and r.get("postData") is not None:
                        self._cal_req["postData"] = r["postData"]
                elif kind == "cal_fetch":
                    self._cal_fetch()
                elif kind == "cal_upcoming":
                    if getattr(self, "_cal_xhr", None):
                        self._cal_fetch()
                    elif self.cfg.get("calendar_nudge", True) and not getattr(self, "_cal_nudged", False):
                        self._cal_nudged = True
                        self._cal_nudge()
                    else:
                        self._cal_fetch_upcoming()
                elif kind == "seed":
                    self._seed()
            except Exception as e:                       # noqa: BLE001  (no message: it could echo a url)
                _log(f"worker {kind}: {type(e).__name__}")
                if kind == "seed":
                    self._seed_queued = False

    def _queue_seed(self):
        if not self._seed_queued and self._worker is not None:
            self._seed_queued = True
            self._tasks.put(("seed", None))

    def _seed(self):
        """REQUEST metrics, positions and orders/active2 (PROTOCOL 07:57 addendum: the server pushes them only on change, so a game that
        starts flat - or a page that reloaded - would otherwise have no account and a stale book). Read-only."""
        self._seed_queued = False
        self._last_seed = time.time()
        if self._ready():
            return
        for action in ("positions", "metrics", "orders/active2"):
            t_sent = time.time()
            r = self._chan.request(action, {}, timeout=3.0)
            body = r.get("body")
            if not r["ok"] or not isinstance(body, (dict, list)):
                continue
            if action == "positions":
                if self._pos_event_t <= t_sent:          # a push that arrived after our request is newer: keep it
                    self._on_positions(body)
            elif action == "metrics":
                self._on_metrics(body)
            else:
                self._on_orders(body)

    # the economic calendar (PROTOCOL 07:57): REST /upcoming with the page's own Bearer token - the token never leaves the page,
    # only the parsed events come back
    _CAL_UPCOMING_JS = r"""(async () => {
        const tok = localStorage.getItem('prm-token');
        if (!tok) { return {status: 0, data: []}; }
        const r = await fetch('https://api.primexbt.com/v2/economic-calendar/upcoming', {method: 'POST', credentials: 'include',
            headers: {'content-type': 'application/json', Authorization: 'Bearer ' + tok},
            body: JSON.stringify({importance: ['HIGH'], limit: 20})});
        if (r.status !== 200) { return {status: r.status, data: []}; }
        const j = await r.json();
        const rows = (j && Array.isArray(j.data)) ? j.data : [];
        return {status: 200, data: rows.map(e => ({t: e.eventTime, title: String(e.eventTitle || ''), impact: String(e.importance || ''),
                                                   country: String(e.regionCode || '')}))};
    })()"""

    def _publish_news(self, source, news):
        """the calendar is the union of its sources (the page's own capture and /upcoming), one entry per (time, title)"""
        self._news_src[source] = [dict(n) for n in news]
        seen, out = set(), []
        for n in sorted((x for lst in self._news_src.values() for x in lst), key=lambda n: n.get("t") or 0):
            key = (round(float(n.get("t") or 0)), str(n.get("title") or "").strip().lower())
            if key not in seen:
                seen.add(key)
                out.append(n)
        self._put_news(out)

    # the chart (a same-origin blob iframe, TradingView) asks the app for its calendar marks whenever its resolution changes.
    # Nudge: click another resolution and straight back to the one the player had (about 1.5 s). The app then POSTs
    # /economic-calendar/events with its own headers; the passive capture reads it and the replay keeps it fresh.
    _CAL_NUDGE_JS = r"""(async () => {
        const f = [...document.querySelectorAll('iframe')].find(x => { try { return !!x.contentDocument; } catch (e) { return false; } });
        if (!f) return 'no chart iframe';
        const d = f.contentDocument;
        const cells = [...d.querySelectorAll('div,button,span')].filter(el => el.children.length === 0 && /^(1m|15m|1h|4h|D)$/.test((el.innerText || '').trim()));
        if (cells.length < 2) return 'no resolution buttons';
        const btn = (el) => el.closest('button,[role=radio],[data-value]') || el.parentElement || el;
        const isOn = (el) => { const b = btn(el); return b.getAttribute('aria-checked') === 'true' || /(^|\s)isActive-/.test(String(b.className)); };   // 'isInteractive' also contains 'active'
        const cur = cells.find(isOn) || cells[0];
        const other = cells.find(c => c !== cur && (c.innerText || '').trim() !== (cur.innerText || '').trim());
        btn(other).click();
        await new Promise(r => setTimeout(r, 1500));
        btn(cur).click();
        return 'nudged ' + (other.innerText || '').trim() + ' -> ' + (cur.innerText || '').trim();
    })()"""

    def _cal_nudge(self):
        if self._sess is None or not getattr(self._sess, "alive", False):
            return
        v = self._sess.js(self._CAL_NUDGE_JS, timeout=20)
        _log(f"calendar: {v}")

    def _cal_fetch_upcoming(self):
        if self._sess is None or not getattr(self._sess, "alive", False):
            return
        v = self._sess.js(self._CAL_UPCOMING_JS, timeout=20)
        if not isinstance(v, dict) or v.get("status") != 200 or not isinstance(v.get("data"), list):
            st = v.get("status") if isinstance(v, dict) else None
            _log(f"calendar /upcoming not read (status {st})")
            return
        regions = {str(x).strip().upper() for x in (self.cfg.get("news_regions") or [])}
        news = []
        for e in v["data"]:
            if not isinstance(e, dict):
                continue
            t = to_unix(e.get("t"))
            country = str(e.get("country") or "").strip().upper()
            if t is None or (regions and country not in regions):
                continue
            news.append({"t": float(t), "title": str(scrub(e.get("title") or "") or "news")[:80], "impact": _cal_impact(e.get("impact")),
                         "country": country})
        self._cal_up_last = time.time()
        self._publish_news("upcoming", news)
        rec = self._recorder
        if rec is not None:
            rec.write("in", {"type": "GG_CALENDAR", "body": {"data": news}}, time.time())

    def _cal_read(self, rq):
        import base64
        r = self._sess.call("Network.getResponseBody", timeout=10, requestId=rq)
        body = r.get("body") or ""
        if r.get("base64Encoded"):
            body = base64.b64decode(body).decode("utf-8", "replace")
        self._cal_apply(json.loads(body))

    def _cal_fetch(self):
        if self._sess is None:
            return
        rq = getattr(self, "_cal_xhr", None)
        if rq:                                           # the page's own XHR, replayed: same url, body and headers (the
            try:                                         # response is read by the passive capture above)
                self._sess.call("Network.replayXHR", timeout=10, requestId=rq)
                return
            except Exception:                            # noqa: BLE001  (request no longer known: fall back once)
                self._cal_xhr = None
        req = self._cal_req
        if not req or not req.get("url"):
            return
        method = str(req.get("method") or "POST").upper()
        if method == "GET" or req.get("postData") is None:
            opts = "{method: %s, credentials: 'include'}" % json.dumps(method)
        else:
            opts = ("{method: %s, credentials: 'include', headers: {'content-type': 'application/json'}, body: %s}"
                    % (json.dumps(method), json.dumps(req["postData"])))
        v = self._sess.js("(async () => { const r = await fetch(%s, %s); return {status: r.status, text: await r.text()}; })()"
                          % (json.dumps(req["url"]), opts), timeout=20)
        if isinstance(v, dict) and v.get("status") == 200:
            self._cal_apply(json.loads(v.get("text") or "null"))

    def _cal_apply(self, obj):
        news = normalise_calendar(obj)
        if news is None:
            return
        self._cal_last = time.time()
        self._publish_news("page", news)
        rec = self._recorder
        if rec is not None:
            rec.write("in", {"type": "GG_CALENDAR", "body": {"data": news}}, time.time())

    # ---- status ---------------------------------------------------------------------------------------------------------------
    def _status(self, now):
        if not self._started:
            return False, "not started"
        if self._sess is None or not getattr(self._sess, "alive", False):
            return False, self._conn_reason or "not attached"
        if self._fws_index is None:
            return False, self._conn_reason or "futures socket not found"
        if self._account_ok is False:
            return False, "another account is open in the page"
        q = self._quote
        if q is None:
            return False, "no quote yet"
        if now - q["ts"] > self.feed_dead_s:
            return False, "market_closed" if st_closed(q.get("st")) else "quotes stale"
        return True, None

    def state(self):
        s = super().state()
        s["account_ok"] = self._account_ok is not False  # False: the page holds another account - the engine freezes, never settles
        s["book_fresh"] = bool(self._book_fresh)         # False: positions unknown since a reload (the engine never infers a close)
        s["book_t"] = self._book_t
        return s

    def _on_event(self, f, action, body, ts):
        if action == "positions":
            self._pos_event_t = ts
        super()._on_event(f, action, body, ts)

    def _on_metrics(self, body):
        if isinstance(body, dict) and self.account_pin and body.get("accountId") is not None and \
                str(body.get("accountId")).strip().lower() != self.account_pin:
            if self._account_ok is not False:
                _log("metrics for another account - trading refused until the page shows the game's account again")
            self._account_ok = False                     # never show or trade another account's balance
            return
        super()._on_metrics(body)

    def _on_positions(self, body):
        if isinstance(body, dict) and self.account_pin and body.get("accountId") is not None and \
                str(body.get("accountId")).strip().lower() != self.account_pin:
            return                                       # another account's book is not ours
        if isinstance(body, dict) and isinstance(body.get("data"), list) and self.account_pin:
            keep = []
            for agg in body["data"]:
                if isinstance(agg, dict) and agg.get("accountId") is not None and str(agg["accountId"]).strip().lower() != self.account_pin:
                    continue
                if isinstance(agg, dict) and isinstance(agg.get("subPositions"), list):
                    agg = dict(agg, subPositions=[s for s in agg["subPositions"] if not (
                        isinstance(s, dict) and s.get("accountId") is not None and str(s["accountId"]).strip().lower() != self.account_pin)])
                keep.append(agg)
            body = dict(body, data=keep)
        super()._on_positions(body)
        if isinstance(body.get("data") if isinstance(body, dict) else body, list):
            with self._lock:
                self._book_fresh = True
                self._book_t = time.time()

    # ---- sending --------------------------------------------------------------------------------------------------------------
    def _ready(self):
        if not self._started or self._sess is None or not getattr(self._sess, "alive", False):
            return "NOT_CONNECTED"
        if self._account_ok is False:
            return "WRONG_ACCOUNT: another account is open in the page"
        if self._fws_index is None or self._need_acquire:
            return "SOCKET_LOST"
        return None

    def _send_frame(self, msg):
        """Send one frame on the page's futures socket. readyState, '/v2/fws/' and the pinned accountId are checked in the SAME page
        evaluation as w.send, so a socket that changed (reload, another account, another tool re-listing the sockets) is never used."""
        sess, idx = self._sess, self._fws_index
        if sess is None or idx is None or self._need_acquire:
            raise SendNotOpen("no futures socket")
        expr = ("(() => { const w = (window.__gg_socks || [])[%d]; if (!w || w.readyState !== 1) return 'closed'; "
                "if (String(w.url).indexOf('/v2/fws/') < 0) return 'not_fws'; %s"
                "w.send(%s); return 'sent'; })()" % (int(idx), self._js_account_check(), json.dumps(json.dumps(msg))))
        try:
            v = sess.js(expr, timeout=5)
        except Exception as e:                           # noqa: BLE001
            if str(e).startswith("CDP connection closed"):   # cdpcore raised before anything left: never sent
                self._need_acquire = True
                raise SendNotOpen("CDP closed") from None
            raise RuntimeError("send uncertain") from None
        if v == "sent":
            return True
        self._need_acquire = True                        # nothing left the page: find the socket again
        if v == "account":
            self._account_ok = False
            self._conn_reason = "another account is open in the page"
        raise SendNotOpen(f"page socket refused the send ({v})")

    def _quote_now(self):
        with self._lock:
            return dict(self._quote) if self._quote else None

    def _own_check(self, position_id):
        try:
            pid = int(position_id)
        except (TypeError, ValueError):
            return None, "BAD_POSITION"
        if pid not in self._own:
            for t, token in list(self._tokens):          # the engine may have found the position of an unresolved order itself
                res = {"position_id": None, "fill_price": None, "open_price": None, "sl_order": None, "tp_order": None,
                       "seen": set()}
                self._scan_place(res, token)
                if res["position_id"] == pid:
                    self._own_add(pid)
                    break
        if pid not in self._own:
            return None, f"NOT_OURS: position {pid} was not opened by the game (adopt() it first if it was)"
        return pid, None

    # ---- trading --------------------------------------------------------------------------------------------------------------
    def place(self, side, qty, sl, tp, timeout=5.0):
        t0 = time.perf_counter()
        try:
            side = int(side)
        except (TypeError, ValueError):
            side = 0
        if side not in (1, -1):
            return _ret(False, "BAD_SIDE", t0, definite=True)
        if not qty_ok(qty, self.qty_step, self.min_qty):
            return _ret(False, "BAD_QTY", t0, definite=True)
        qty = round(float(qty), 2)
        if qty > self.max_qty + 1e-9:
            return _ret(False, f"QTY_CAP: {qty} is above the live cap of {self.max_qty} (live_max_qty)", t0, definite=True)
        sl, tp = fnum(sl), fnum(tp)
        if sl is None or tp is None:
            return _ret(False, "BAD_PROTECTIVE: a live order needs both a stop loss and a take profit", t0, definite=True)
        sl, tp = r2(sl), r2(tp)
        if (side > 0 and not sl < tp) or (side < 0 and not sl > tp):
            return _ret(False, "BAD_PROTECTIVE: stop loss and take profit are on the wrong sides", t0, definite=True)
        why = self._ready()
        if why:
            return _ret(False, why, t0, definite=True)
        q = self._quote_now()
        if q is None:
            return _ret(False, "NO_QUOTE: no live quote to check the stop and target against", t0, definite=True)
        age = self.now() - float(q.get("ts") or 0.0)
        if age > self.place_quote_max_age:
            return _ret(False, f"STALE_QUOTE: the last quote is {age:.1f} s old", t0, definite=True)
        if abs(sl - q["mid"]) > self.max_dist or abs(tp - q["mid"]) > self.max_dist:
            return _ret(False, f"BAD_PROTECTIVE: SL/TP more than {self.max_dist} from the quote", t0, definite=True)
        if (side > 0 and not (sl < q["bid"] and tp > q["ask"])) or (side < 0 and not (sl > q["ask"] and tp < q["bid"])):
            # PROTOCOL rule 2: a long's SL below the bid and its TP above the ask (mirror for a short) - PX fills a crossed one at once
            return _ret(False, f"BAD_PROTECTIVE: the stop or the target is already crossed by the quote "
                               f"(bid {q['bid']} ask {q['ask']})", t0, definite=True)
        with self._lock:
            before = sorted(p["id"] for p in self._positions)
            mark = self._act_seq
        body = {"qty": qty, "side": "BUY" if side > 0 else "SELL", "symbol": self.symbol, "takeProfit": {"price": tp},
                "stopLoss": {"price": sl}}
        token = {"seq": mark, "before": before, "side": side, "qty": qty, "sl": sl, "tp": tp, "t": time.time()}
        call = self._chan.begin("orders/market/place", body)
        res = {"position_id": None, "fill_price": None, "open_price": None, "sl_order": None, "tp_order": None, "seen": set()}
        reply = None
        end_reply = t0 + float(timeout)
        end_resolve = None
        try:
            while True:
                if reply is None:
                    reply = self._chan.result(call, 0.0)
                    if reply is not None:
                        if not reply["ok"] and reply.get("definite"):
                            return _ret(False, reply["error"], t0, order_id=None, position_id=None, fill_price=None,
                                        quote=q, request=body, definite=True)
                        end_resolve = min(end_reply, time.perf_counter() + self.resolve_s)
                self._scan_place(res, token)
                if reply is not None and res["position_id"] is not None and res["fill_price"] is not None:
                    break
                now = time.perf_counter()
                dl = end_resolve if end_resolve is not None else end_reply
                if now >= dl:
                    break
                with self._cond:
                    self._cond.wait(min(0.1, dl - now))
        finally:
            self._chan.drop(call)
        if res["position_id"] is None:                   # last look at the positions diff
            self._scan_place(res, token)
        fill = res["fill_price"]
        if res["open_price"] is not None and (fill is None or abs(fill - res["open_price"]) > 0.005):
            fill = res["open_price"]
        replied_ok = reply is not None and reply["ok"]
        ok = replied_ok or res["position_id"] is not None
        if res["position_id"] is not None:
            self._own_add(res["position_id"])
            self._own_side[int(res["position_id"])] = side
        order_id = (reply.get("body") or {}).get("id") if replied_ok and isinstance(reply.get("body"), dict) else None
        if ok:
            err = None
        elif reply is None:
            err = "TIMEOUT" if call.sent else (call.error or "SEND_UNCERTAIN")
        else:
            err = reply["error"]                         # a LOCAL error (page reloaded / socket or CDP closed): not definite
        resolved = res["position_id"] is not None
        out = _ret(ok, err, t0, order_id=order_id, position_id=res["position_id"], fill_price=fill, sl=sl, tp=tp,
                   sl_order=res["sl_order"], tp_order=res["tp_order"], quote=q, request=body,
                   reply_ms=reply["rtt_ms"] if reply is not None else None, definite=resolved,
                   accepted=True if replied_ok else None)
        if not resolved:
            # accepted without an id, no reply at all, or the socket went away after the send: the order may have filled.
            # The engine must keep the round frozen and keep looking (resolve / the book / the report) - never call it refused.
            out["uncertain"] = True
            out["resolve_token"] = token
            out["warning"] = ("order accepted; position id not resolved yet - call resolve(resolve_token)" if replied_ok else
                              "no definite answer: the order may have executed - call resolve(resolve_token)")
            self._tokens.append((time.time(), token))
        self._after_trade()
        return out

    def _scan_place(self, res, token):
        side, qty, sl, tp = token["side"], token["qty"], token["sl"], token["tp"]
        word, exit_word = ("buy", "sell") if side > 0 else ("sell", "buy")
        with self._lock:
            acts = [a for a in self._activity if a["seq"] > token["seq"]]
            positions = list(self._positions)
        for a in acts:
            if a["seq"] in res["seen"]:
                continue
            res["seen"].add(a["seq"])
            title = (a.get("title") or "").lower()
            if title.startswith("market order filled") and res["fill_price"] is None:
                m = parse_fill_text(a.get("body"))
                if m and m["side"] == word and m["qty"] is not None and abs(m["qty"] - qty) < 1e-9 and m["symbol"] == self.symbol:
                    res["fill_price"] = m["price"]
            elif "linked to position" in title:
                m = parse_link_text(a.get("body"))
                if not m or m["side"] != exit_word or m["price"] is None or m["symbol"] != self.symbol:
                    continue
                if m["kind"] == "STOP_LOSS" and abs(m["price"] - sl) < 0.006:
                    res["position_id"] = m["position_id"]
                    res["sl_order"] = m["order_id"]
                elif m["kind"] == "TAKE_PROFIT" and abs(m["price"] - tp) < 0.006:
                    res["tp_order"] = m["order_id"]
                    if res["position_id"] is None:
                        res["position_id"] = m["position_id"]
        before = set(token["before"])
        if res["position_id"] is None:
            cands = [p for p in positions if p["id"] not in before and self.matches_order(p, token)]
            if len(cands) == 1:
                res["position_id"] = cands[0]["id"]
        if res["position_id"] is not None:
            for p in positions:
                if p["id"] == res["position_id"] and p.get("open_price") is not None:
                    res["open_price"] = p["open_price"]

    def matches_order(self, p, token):
        """True if book position p can only be the game's order `token`: our symbol, side and qty, the exact stop loss AND take profit
        we sent (every game order carries both; a hand-made trade with both on the same cents is not a realistic accident) and, when
        the server clock is known, opened after the send. A position with no stop is never the game's."""
        side, qty, sl, tp = token["side"], token["qty"], token["sl"], token["tp"]
        if p.get("side") != side or p.get("qty") is None or abs(p["qty"] - qty) > 1e-9:
            return False
        if str(p.get("symbol") or self.symbol).upper() != self.symbol:
            return False
        if p.get("sl") is None or p.get("tp") is None or abs(p["sl"] - sl) > 0.006 or abs(p["tp"] - tp) > 0.006:
            return False
        ot, t_send, off = p.get("open_time"), token.get("t"), self._server_offset
        if ot is not None and t_send is not None and off is not None and ot < t_send + off - 5.0:
            return False                                 # opened before our order left (5 s of clock tolerance)
        return True

    def owned(self):
        """the position ids the game may touch (it opened them, or adopted its own from an earlier run)"""
        return set(self._own)

    def _after_trade(self):
        """refresh the book (positions / metrics / orders) right after a trading frame (PROTOCOL 07:57 addendum)"""
        if self._worker is not None:
            self._tasks.put(("seed", None))

    def resolve(self, token, timeout=2.0):
        """keep looking for the position of an accepted place() -> {"position_id", "fill_price"}"""
        res = {"position_id": None, "fill_price": None, "open_price": None, "sl_order": None, "tp_order": None, "seen": set()}
        end = time.perf_counter() + float(timeout)
        while True:
            self._scan_place(res, token)
            if res["position_id"] is not None or time.perf_counter() >= end:
                break
            with self._cond:
                self._cond.wait(0.1)
        if res["position_id"] is not None:
            self._own_add(res["position_id"])
            self._own_side[int(res["position_id"])] = token["side"]
        fill = res["open_price"] if res["open_price"] is not None else res["fill_price"]
        return {"ok": res["position_id"] is not None, "position_id": res["position_id"], "fill_price": fill}

    def set_protective(self, position_id, kind, price, timeout=5.0):
        t0 = time.perf_counter()
        kind = str(kind or "").upper()
        if kind not in ("STOP_LOSS", "TAKE_PROFIT"):
            return _ret(False, "BAD_KIND", t0)
        price = fnum(price)
        if price is None:
            return _ret(False, "BAD_PROTECTIVE", t0)
        price = r2(price)
        pid, why = self._own_check(position_id)
        if why:
            return _ret(False, why, t0, definite=True)
        q = self._quote_now()
        if q is not None and abs(price - q["mid"]) > self.max_dist:
            return _ret(False, f"BAD_PROTECTIVE: more than {self.max_dist} from the quote", t0, definite=True)
        side = self._pos_side(pid)
        if q is not None and side in (1, -1):
            bid, ask = q["bid"], q["ask"]
            if kind == "STOP_LOSS" and ((side > 0 and not price < bid) or (side < 0 and not price > ask)):
                return _ret(False, f"BAD_PROTECTIVE: that stop is already crossed (bid {bid} ask {ask})", t0, definite=True)
            if kind == "TAKE_PROFIT" and ((side > 0 and not price > ask) or (side < 0 and not price < bid)):
                return _ret(False, f"BAD_PROTECTIVE: that target is already crossed (bid {bid} ask {ask})", t0, definite=True)
        why = self._ready()
        if why:
            return _ret(False, why, t0, definite=True)
        r = self._chan.request("positions/id/protective-order/set", {"positionId": pid, "price": price, "type": kind},
                               timeout=timeout)
        self._after_trade()
        return _ret(r["ok"], r["error"], t0, price=price, kind=kind, definite=r.get("definite"))

    def _pos_side(self, pid):
        with self._lock:
            pos = next((p for p in self._positions if p["id"] == pid), None)
        side = (pos or {}).get("side")
        return side if side in (1, -1) else self._own_side.get(pid)

    def check_protective(self, position_id, price, timeout=3.0):
        t0 = time.perf_counter()
        price = fnum(price)
        if price is None:
            return _ret(False, "BAD_PROTECTIVE", t0)
        pid, why = self._own_check(position_id)
        if why:
            return _ret(False, why, t0)
        why = self._ready()
        if why:
            return _ret(False, why, t0)
        r = self._chan.request("positions/id/protective-order/impact", {"price": r2(price), "positionId": pid}, timeout=timeout)
        b = r["body"] if isinstance(r.get("body"), dict) else {}
        return _ret(r["ok"], r["error"], t0, resolution=b.get("resolution"), profitLoss=fnum(b.get("profitLoss")),
                    resolutionLevel=b.get("resolutionLevel"))

    def close(self, position_id, qty=None, timeout=5.0):
        t0 = time.perf_counter()
        pid, why = self._own_check(position_id)
        if why:
            return _ret(False, why, t0)
        with self._lock:
            pos = next((p for p in self._positions if p["id"] == pid), None)
            mark = self._act_seq
        if qty is None:
            if pos is None or not pos.get("qty"):
                return _ret(False, "BAD_QTY: position quantity unknown", t0)
            qty = pos["qty"]
        if not qty_ok(qty, self.qty_step, self.min_qty):
            return _ret(False, "BAD_QTY", t0)
        qty = round(float(qty), 2)
        if pos is not None and pos.get("qty") and qty > pos["qty"] + 1e-9:
            qty = round(pos["qty"], 2)
        why = self._ready()
        if why:
            return _ret(False, why, t0)
        r = self._chan.request("positions/id/close", {"positionId": pid, "qty": qty}, timeout=timeout)
        self._after_trade()
        if not r["ok"]:
            return _ret(False, r["error"], t0, definite=r.get("definite"), qty=qty)
        side = (pos or {}).get("side")
        if side not in (1, -1):
            side = self._own_side.get(pid)
        fill = None
        if side in (1, -1):                              # unknown side: no fill text is read (it could be another trade's)
            fill = self._wait_fill(mark, "sell" if side > 0 else "buy", qty, min(t0 + float(timeout), time.perf_counter() + 1.0))
        return _ret(True, None, t0, fill_price=fill, qty=qty, reply_ms=r["rtt_ms"], definite=True)

    def _wait_fill(self, mark, word, qty, deadline):
        while True:
            with self._lock:
                acts = [a for a in self._activity if a["seq"] > mark]
            for a in acts:
                if (a.get("title") or "").lower().startswith("market order filled"):
                    m = parse_fill_text(a.get("body"))
                    if m and m["side"] == word and m["qty"] is not None and abs(m["qty"] - qty) < 1e-9:
                        return m["price"]
            now = time.perf_counter()
            if now >= deadline:
                return None
            with self._cond:
                self._cond.wait(min(0.1, deadline - now))

    def orders_report(self, since_ts, timeout=5.0):
        why = self._ready()
        if why:
            return ReportList([], ok=False, error=why)
        rows, rtt, offset = [], 0.0, 0
        for _page in range(5):                           # 100 rows a page, newest first: a busy account must not truncate ours
            r = self._chan.request("report/orders2", {"limit": 100, "offset": offset, "fromExecutedAt": float(since_ts or 0.0),
                                                      "toExecutedAt": 2114467199.999, "symbol": self.symbol}, timeout=timeout)
            rtt += r["rtt_ms"] or 0.0
            if not r["ok"]:
                return ReportList([], ok=False, error=r["error"], rtt_ms=rtt)     # a partial report is not a report
            b = r["body"]
            data = b.get("data") if isinstance(b, dict) else b
            data = data if isinstance(data, list) else []
            for row in data:
                if isinstance(row, dict):
                    d = dict(row)
                    d["executed_ts"] = to_unix(d.get("executedAt"))
                    rows.append(d)
            if len(data) < 100:
                break
            offset += 100
        return ReportList(rows, ok=True, error=None, rtt_ms=rtt)


# ------------------------------------------------------------------------------------------------------------------------------
# factory + a small CLI (sim and replay only - the live feed has no command line on purpose)
# ------------------------------------------------------------------------------------------------------------------------------
def make_feed(mode, config=None, **kw):
    """make_feed("sim", seed=7, speed=1.0) | make_feed("replay", path=..., speed=1.0) | make_feed("live", record=True)"""
    m = str(mode or "sim").lower()
    if m == "sim":
        return SimFeed(config=config, **kw)
    if m == "replay":
        cls = globals().get("ReplayFeed")
    elif m == "live":
        cls = globals().get("LiveFeed")
    else:
        raise ValueError(f"unknown feed mode {mode!r}")
    if cls is None:
        raise RuntimeError(f"{m} feed not available")
    return cls(config=config, **kw)


def _cli(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="feeds.py - watch the sim or a replay (never the live page)")
    ap.add_argument("mode", choices=["sim", "replay"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--seconds", type=float, default=10.0)
    a = ap.parse_args(argv)
    f = SimFeed(seed=a.seed, speed=a.speed) if a.mode == "sim" else make_feed("replay", path=a.file, speed=a.speed)
    f.subscribe(lambda ev: print(json.dumps(ev)[:200]) if ev.get("type") in ("activity", "feed", "news") else None)
    f.start()
    t_end = time.time() + a.seconds
    try:
        while time.time() < t_end:
            time.sleep(1.0)
            s = f.state()
            q = s["quote"] or {}
            print(f"ok={s['ok']} reason={s['reason']} bid={q.get('bid')} ask={q.get('ask')} spread={q.get('spread')} "
                  f"ticks={s['tick_count']} bars={len(s['bars'])} last_bar={s['bars'][-1] if s['bars'] else None}")
    finally:
        f.stop()


if __name__ == "__main__":
    _cli()
