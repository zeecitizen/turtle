"""tests/test_engine.py - Golden Gravity engine tests (B-ENGINE).

Run from games/gold_runner:   python -m unittest discover -s tests -p test_engine.py -v

Every rule is tested deterministically on a scripted FakeFeed (the Feed interface of CONTRACT.md section 4 with a tiny PX-like broker)
and a fake clock, so nothing here needs feeds.py, a network, or the wall clock. A few optional tests also run the real feeds.SimFeed
(manual mode) and feeds.ShadowBroker when feeds.py imports. Nothing here can reach the live page: GG_FORBID_LIVE is set and the
FakeFeed never opens a socket.
"""
import collections
import itertools
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone

os.environ.setdefault("GG_FORBID_LIVE", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import engine as E  # noqa: E402
from tools import make_fixtures as mf  # noqa: E402

FIX = os.path.join(ROOT, "static", "fixtures")


def utc(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()


T0 = utc("2026-11-03 10:00:00")          # a Tuesday in the London session: shutters up whatever the real clock says


def load_fixture(name):
    with open(os.path.join(FIX, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


class Clock:
    def __init__(self, t):
        self.t = float(t)

    def __call__(self):
        return self.t


def make_bars(t_end, n=40):
    """Flat bars around 3926 with two confirmed swing lows (3925.40 at bar 30, 3925.70 at bar 34) and two swing highs
    (3926.70 at bar 31, 3926.45 at bar 35). The last bar is the forming one."""
    t_last = int(t_end // 60) * 60
    bars = []
    for i in range(n):
        lo, hi = 3925.80, 3926.20
        if i == 30:
            lo = 3925.40
        if i == 34:
            lo = 3925.70
        if i == 31:
            hi = 3926.70
        if i == 35:
            hi = 3926.45
        bars.append([t_last - (n - 1 - i) * 60, 3926.00, hi, lo, 3926.00, 100])
    return bars


class FakeFeed:
    """Scripted Feed: push(bid) adds a quote; SL/TP trigger like PXTrader (long on the bid, short on the ask; a gap fills at the first
    price after it; a crossed SL/TP fills at once). Records every trading call in .calls."""

    def __init__(self, clock, bars=None, bid=3926.00, spread=0.33, mode="sim", balance=25.0):
        self.clock = clock
        self.mode = mode
        self.can_trade = mode != "replay"
        self.spread = spread
        self.bars = [list(b) for b in (bars if bars is not None else make_bars(clock.t))]
        self.ticks = collections.deque()
        self.quote = None
        self.tick_count = 0
        self.pos = {}
        self.rows = []
        self.balance = balance
        self.news = []
        self.market_open = True
        self.alive = True
        self.refuse = {}
        self.calls = []
        self.slip = 0.0
        self._pid = itertools.count(15394511)
        self._oid = itertools.count(2188562137)
        self.push(bid, dt=0.0)

    # -- Feed plumbing
    def subscribe(self, fn):
        return fn

    def start(self):
        pass

    def stop(self):
        pass

    def push(self, bid, ask=None, dt=0.4):
        self.clock.t += dt
        bid = round(bid, 2)
        ask = round(bid + self.spread, 2) if ask is None else round(ask, 2)
        t = self.clock.t
        self.quote = {"bid": bid, "ask": ask, "mid": round((bid + ask) / 2, 3), "spread": round(ask - bid, 2), "ts": t, "st": "OPEN"}
        self.tick_count += 1
        self.ticks.append([t, bid, ask])
        while self.ticks and self.ticks[0][0] < t - 120:
            self.ticks.popleft()
        last = self.bars[-1]
        last[2], last[3], last[4] = max(last[2], bid), min(last[3], bid), bid
        for p in list(self.pos.values()):
            self._check(p)

    def _check(self, p):
        bid, ask = self.quote["bid"], self.quote["ask"]
        px = bid if p["side"] > 0 else ask
        if p["sl"] is not None and (px <= p["sl"] if p["side"] > 0 else px >= p["sl"]):
            self._exit(p, p["qty"], px, "STOP_LOSS", trigger=p["sl"])
        elif p["tp"] is not None and (px >= p["tp"] if p["side"] > 0 else px <= p["tp"]):
            self._exit(p, p["qty"], px, "TAKE_PROFIT", trigger=p["tp"])

    def _row(self, typ, side, qty, price, pid, rpl, trigger=None):
        row = {"id": next(self._oid), "type": typ, "status": "EXECUTED", "side": "BUY" if side > 0 else "SELL", "qty": qty,
               "executedPrice": price, "executedQty": qty, "rpl": round(rpl, 6), "fee": 0.0, "positionId": pid,
               "closeReason": "EXECUTION", "executedAt": "2026-11-03T10:00:00.000Z", "executed_ts": self.clock.t, "triggerPrice": trigger}
        self.rows.append(row)
        return row

    def _exit(self, p, qty, price, typ, trigger=None):
        qty = round(min(qty, p["qty"]), 2)
        rpl = p["side"] * (price - p["open_price"]) * qty
        self.balance += rpl
        row = self._row(typ, -p["side"], qty, price, p["id"], rpl, trigger)
        p["qty"] = round(p["qty"] - qty, 2)
        if p["qty"] < 0.01 - 1e-9:
            del self.pos[p["id"]]
        return row

    def state(self):
        q = self.quote
        ok = self.alive and q is not None and self.clock.t - q["ts"] <= 15
        return {"ok": ok, "reason": None if ok else "quotes stale", "quote": dict(q) if q else None, "tick_count": self.tick_count,
                "ticks": [list(x) for x in self.ticks], "bars": [list(b) for b in self.bars], "h24": 3970.2, "l24": 3891.13, "ch24": 4.0,
                "account": {"id": "FAKE-1", "type": "SIM", "balance": round(self.balance, 6), "equity": round(self.balance, 6),
                            "upl": 0.0, "available": self.balance, "currency": "USD"},
                "positions": [{"id": p["id"], "side": p["side"], "qty": p["qty"], "open_price": p["open_price"],
                               "mark": q["bid"] if p["side"] > 0 else q["ask"], "upl": 0.0, "sl": p["sl"], "tp": p["tp"],
                               "sl_order": None, "tp_order": None, "open_time": p["open_time"]} for p in self.pos.values()],
                "orders": [], "activity": [], "news": list(self.news), "market_open": self.market_open}

    # -- trading
    def place(self, side, qty, sl, tp, timeout=5.0):
        self.calls.append(("place", side, qty, sl, tp))
        if "place" in self.refuse:
            return {"ok": False, "error": self.refuse.pop("place"), "rtt_ms": 1.0}
        price = round(self.quote["ask"] + self.slip if side > 0 else self.quote["bid"] - self.slip, 2)
        pid = next(self._pid)
        p = {"id": pid, "side": side, "qty": round(qty, 2), "open_price": price, "sl": sl, "tp": tp, "open_time": self.clock.t}
        self.pos[pid] = p
        row = self._row("MARKET", side, qty, price, pid, 0.0)
        res = {"ok": True, "error": None, "rtt_ms": 1.0, "order_id": row["id"], "position_id": pid, "fill_price": price}
        self._check(p)
        return res

    def set_protective(self, position_id, kind, price, timeout=5.0):
        self.calls.append(("set_protective", position_id, kind, price))
        if "set_protective" in self.refuse:
            return {"ok": False, "error": self.refuse.pop("set_protective"), "rtt_ms": 1.0}
        p = self.pos.get(position_id)
        if p is None:
            return {"ok": False, "error": "POSITION_NOT_FOUND: 120", "rtt_ms": 1.0}
        p["sl" if kind == "STOP_LOSS" else "tp"] = price
        self._check(p)
        return {"ok": True, "error": None, "rtt_ms": 1.0}

    def check_protective(self, position_id, price, timeout=3.0):
        return {"ok": True, "error": None, "rtt_ms": 1.0, "resolution": "OK", "profitLoss": 0.0}

    def close(self, position_id, qty=None, timeout=5.0):
        self.calls.append(("close", position_id, qty))
        if "close" in self.refuse:
            return {"ok": False, "error": self.refuse.pop("close"), "rtt_ms": 1.0}
        p = self.pos.get(position_id)
        if p is None:
            return {"ok": False, "error": "POSITION_NOT_FOUND: 120", "rtt_ms": 1.0}
        px = round(self.quote["bid"] - self.slip if p["side"] > 0 else self.quote["ask"] + self.slip, 2)
        row = self._exit(p, qty if qty is not None else p["qty"], px, "MARKET")
        return {"ok": True, "error": None, "rtt_ms": 1.0, "fill_price": px, "rpl": row["rpl"], "order_id": row["id"]}

    def orders_report(self, since_ts, timeout=5.0):
        return [dict(r) for r in reversed(self.rows) if r["executed_ts"] >= since_ts]

    # -- scripted outside events (Zee trading the same account by hand)
    def add_outside_position(self, pid=999, side=1, qty=0.01, price=3900.0):
        self.pos[pid] = {"id": pid, "side": side, "qty": qty, "open_price": price, "sl": None, "tp": None, "open_time": self.clock.t - 3600}

    def outside_close(self, pid):
        p = self.pos[pid]
        px = self.quote["bid"] if p["side"] > 0 else self.quote["ask"]
        self._exit(p, p["qty"], px, "MARKET")


class EngineCase(unittest.TestCase):
    """Builds an engine on a FakeFeed in a temp root, with a fake clock and no threads."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gg_test_engine_")
        self.n = itertools.count(1)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make(self, mode="sim", cfg=None, real_hours=None, t0=T0, bars=None, bid=3926.00, balance=25.0, shadow="engine"):
        self.clock = Clock(t0)
        self.feed = FakeFeed(self.clock, bars=bars, bid=bid, mode=mode, balance=balance)
        c = {"shadow_broker": shadow, "paper_slippage_max": 0.0}
        c.update(cfg or {})
        self.eng = E.Engine(self.feed, cfg=c, root=self.tmp, clock=self.clock, threaded=False, verbose=False, real_hours=real_hours,
                            cfg_path=os.path.join(self.tmp, "no_config.json"))
        for _ in range(3):
            self.feed.push(bid)
            self.eng.step()
        return self.eng

    def act(self, action, sent_at=None, nonce=None, **args):
        r = self.eng.act({"action": action, "nonce": nonce or f"t{next(self.n)}",
                          "sent_at": self.clock.t if sent_at is None else sent_at, "args": args})
        self.eng.pump()
        self.eng.step()
        self.eng.pump()
        return r

    def tick(self, bid, n=1, dt=0.4):
        for _ in range(n):
            self.feed.push(bid, dt=dt)
            self.eng.step()
            self.eng.pump()

    def until(self, cond, bid=None, max_ticks=40):
        for _ in range(max_ticks):
            if cond():
                return True
            self.tick(bid if bid is not None else self.feed.quote["bid"])
        return cond()

    def snap(self):
        return self.eng.snapshot()

    def graduate(self, mode=None, machete=False):
        """Pretend the Alley is done (5 wooden rounds with an eject) and type CONFIRM."""
        mode = mode or self.eng.mode
        for i in range(5):
            self.eng.summaries.append({"id": f"w{i}", "mode": mode, "kind": "wooden", "outcome": "eject" if i == 0 else "merchant",
                                       "result_usd": -0.001, "risk_usd": 0.01, "closed_t": self.clock.t - 5000 + i, "opened_t": self.clock.t - 5100,
                                       "machete_done": machete and i == 1, "session": "london", "weather": "calm", "quick": True})
        self.eng._sum_version += 1
        self.eng._lim_cache = (None, None)
        res = self.eng.update_settings({"live_enabled": True, "confirm_word": "CONFIRM"})
        self.assertTrue(res["ok"], res)

    def open_round(self, kind="live", side=1, target=1.2, twin=False):
        r = self.act("fund", kind=kind, side=side, target=target, twin=twin)
        self.assertTrue(r["accepted"], r)
        self.tick(self.feed.quote["bid"])
        r = self.act("shoot")
        self.assertTrue(r["accepted"], r)
        self.assertEqual(self.eng.phase, "open")
        return self.eng.round


# ======================================================================================================================== pure math
class TestLadderMath(unittest.TestCase):
    def test_pure_functions_match_make_fixtures(self):
        bars = mf.gen_bars()
        for name in ("aiming", "lobby", "jammed", "locked", "shutters_dead"):
            fx = load_fixture(name)["snap"]
            pv, q = fx["preview"], fx["quote"]
            entry = q["ask"]
            a, b, _, _ = E.ladder(1, entry, entry - 1.0, entry + 1.2)
            self.assertEqual((round(a, 6), round(b, 6)), (pv["a"], pv["b"]), name)
            self.assertEqual(E.xp(a, b, entry), pv["x_entry"])
            self.assertEqual(E.xp(a, b, q["bid"]), pv["x_mark"])
            stakes = [{"price": p, "x": E.xp(a, b, p - 0.01), "lit": True} for p in E.pivots(bars, 1) if -0.05 <= E.xp(a, b, p) <= 1.05]
            self.assertEqual(stakes, pv["stakes"], name)
            self.assertEqual(E.terrain(bars, a, b), pv["terrain"], name)

    def test_round_values_match_make_fixtures(self):
        bars = mf.gen_bars()
        for name in ("open_profit", "open_loss", "open_wall", "open_haggle", "open_machete", "open_short", "open_night", "alley_wooden",
                     "settled_buyer", "settled_anvil", "settled_barrel"):
            fx = load_fixture(name)["snap"]
            r = fx["round"]
            side = r["side"]
            sl0, tp0 = round(r["fill"] - side * 1.0, 2), round(r["fill"] + side * 1.2, 2)
            a, b, sd0, td0 = E.ladder(side, r["fill"], sl0, tp0, r["banked_usd"], r["qty"], r["qty0"])
            self.assertEqual((round(a, 6), round(b, 6)), (r["a"], r["b"]), name)
            self.assertEqual(E.xp(a, b, r["fill"]), r["x_entry"], name)
            self.assertEqual(E.xp(a, b, r["sl"]), r["x_sl"], name)
            self.assertEqual(E.xp(a, b, r["tp"]), r["x_tp"], name)
            if fx["phase"] == "settled":      # make_fixtures.settlement() maps the exit through the ROUNDED a, b (fixture quirk)
                self.assertEqual(E.xp(r["a"], r["b"], r["mark"]), r["x"], name)
            else:
                self.assertEqual(E.xp(a, b, r["mark"]), r["x"], name)
            self.assertEqual(E.money(r["value_usd"], r["risk_usd"]), r["value_text"], name)
            self.assertEqual(E.money(r["risk_usd"] + r["qty"] * side * (r["tp"] - r["fill"]) + r["banked_usd"], r["risk_usd"]), r["tag_text"], name)
            for st in r["stakes"]:
                self.assertEqual(E.xp(a, b, st["price"] - 0.01 * side), st["x"], name)
            t = E.terrain(bars, a, b)
            self.assertEqual(t["h"], r["terrain"]["h"], name)
            self.assertEqual(t["weathered"], r["terrain"]["weathered"], name)

    def test_x_after_machete_vault_maps_onto_golden_stake(self):
        r = load_fixture("open_machete")["snap"]["round"]
        sl0, tp0 = round(r["fill"] - 1.0, 2), round(r["fill"] + 1.2, 2)
        a, b, _, _ = E.ladder(1, r["fill"], sl0, tp0, r["banked_usd"], r["qty"], r["qty0"])
        self.assertEqual(E.xp(a, b, sl0), r["golden"]["x"])
        self.assertAlmostEqual(r["banked_usd"] + r["qty"] * (sl0 - r["fill"]), r["golden"]["usd"], places=9)
        self.assertEqual(E.money(r["golden"]["usd"], r["risk_usd"]), r["golden"]["text"])
        a1, b1, _, _ = E.ladder(1, r["fill"], sl0, tp0, 0.0, r["qty0"], r["qty0"])
        self.assertAlmostEqual(b, b1 / 2.0, places=12)      # f = 0.5: the street re-projects at half the slope

    def test_money_strings(self):
        self.assertEqual(E.money(0.0051, 0.01), "$0.0051")
        self.assertEqual(E.money(0.0239, 0.01, signed=True), "+$0.0239")
        self.assertEqual(E.money(-0.0045, 0.01, signed=True), "-$0.0045")
        self.assertEqual(E.money(-0.00001, 0.01, signed=True), "$0.00")
        self.assertEqual(E.money(1.5, 1.0), "$1.50")
        self.assertEqual(E.money(-0.45, 2.0), "-$0.45")
        self.assertEqual(E.money(2.39, 1.0, signed=True), "+$2.39")

    def test_pivots_and_candidates(self):
        bars = make_bars(T0)
        self.assertEqual(E.pivots(bars, 1), [3925.40, 3925.70])
        self.assertEqual(E.pivots(bars, -1), [3926.45, 3926.70])
        self.assertEqual(E.pivot_candidates(bars, 1), [])

    def test_gapbook_chasms(self):
        g = E.GapBook(gap_min=0.25, window_s=1200)
        t = 1000.0
        for px in (3926.00, 3926.05, 3926.10):
            g.tick(px, t)
            t += 0.4
        g.tick(3926.90, t)                                   # a true gap: 3926.10 -> 3926.90
        self.assertEqual(g.chasms(t), [[3926.10, 3926.90]])
        g.tick(3926.50, t + 0.4)                              # prints inside the gap (another jump): the chasm splits around it
        self.assertEqual(g.chasms(t + 0.4), [[3926.10, 3926.50], [3926.50, 3926.90]])
        self.assertEqual(g.chasms(t + 2000), [])               # older than the profile window: gone
        tr = E.terrain(make_bars(T0), *E.ladder(1, 3926.33, 3925.33, 3927.53)[:2], chasm_prices=[[3926.10, 3926.50]])
        self.assertEqual(len(tr["chasms"]), 1)
        self.assertLess(tr["chasms"][0][0], tr["chasms"][0][1])

    def test_market_clock(self):
        mc = E.MarketClock(E.load_config(os.path.join(HERE, "no_such_config.json")))
        self.assertEqual(mc.session(utc("2026-11-03 05:00:00")), "asia")
        self.assertEqual(mc.session(utc("2026-11-03 09:00:00")), "london")
        self.assertEqual(mc.session(utc("2026-11-03 15:00:00")), "newyork")
        self.assertEqual(mc.session(utc("2026-11-03 21:00:00")), "dead")
        self.assertEqual(mc.session(utc("2026-11-03 23:30:00")), "asia")
        self.assertTrue(mc.is_weekend(utc("2026-11-07 12:00:00")))
        self.assertTrue(mc.is_weekend(utc("2026-11-06 22:30:00")))
        self.assertFalse(mc.is_weekend(utc("2026-11-08 23:30:00")))
        self.assertTrue(mc.in_daily_break(utc("2026-11-04 22:30:00")))
        self.assertEqual(mc.next_break_start(utc("2026-11-03 10:00:00")), utc("2026-11-03 22:00:00"))
        b = mc.bell(utc("2026-11-03 10:00:00"))
        self.assertEqual((b["session"], b["last_t"], b["next_t"]), ("london", utc("2026-11-03 08:00:00"), utc("2026-11-03 14:30:00")))
        b = mc.bell(utc("2026-11-07 10:00:00"))                 # Saturday: next bell is Monday's London open
        self.assertEqual(b["next_t"], utc("2026-11-09 08:00:00"))


# ======================================================================================================================== snapshot shape
class TestSnapshotShape(EngineCase):
    def assertShape(self, fx, got, path="snap"):
        problems = []

        def walk(f, g, p):
            if isinstance(f, dict):
                if not isinstance(g, dict):
                    problems.append(f"{p}: expected an object, got {type(g).__name__}")
                    return
                for k, v in f.items():
                    if k not in g:
                        problems.append(f"{p}.{k}: missing")
                    else:
                        walk(v, g[k], f"{p}.{k}")
            elif isinstance(f, list):
                if g is None or not isinstance(g, list):
                    problems.append(f"{p}: expected a list, got {type(g).__name__}")
                elif f and g:
                    walk(f[0], g[0], p + "[0]")
            elif f is None or g is None:
                return
            elif isinstance(f, bool) != isinstance(g, bool):
                problems.append(f"{p}: bool vs {type(g).__name__}")
            elif isinstance(f, (int, float)) and isinstance(g, (int, float)):
                return
            elif type(f) is not type(g):
                problems.append(f"{p}: {type(f).__name__} vs {type(g).__name__}")
        walk(fx, got, path)
        self.assertEqual(problems, [], "\n".join(problems))
        json.dumps(got, allow_nan=False)

    def test_lobby_aiming_open_settled_match_fixture_shapes(self):
        self.make()
        self.assertShape(load_fixture("lobby")["snap"], self.snap())
        self.act("fund", kind="wooden", side=1, target=1.2)
        self.tick(3926.0)
        s = self.snap()
        self.assertEqual(s["phase"], "aiming")
        self.assertShape(load_fixture("aiming")["snap"], s)
        self.act("shoot")
        self.tick(3926.1)
        s = self.snap()
        self.assertEqual(s["phase"], "open")
        self.assertShape({k: v for k, v in load_fixture("open_profit")["snap"].items() if k != "round"}, s)
        fx_round = dict(load_fixture("open_night")["snap"]["round"])
        fx_round["twin"] = None                       # this round was played without the Twin
        self.assertShape(fx_round, s["round"], "round")
        self.act("merchant")
        s = self.snap()
        self.assertEqual(s["phase"], "settled")
        self.assertShape(load_fixture("settled_buyer")["snap"]["settlement"], s["settlement"], "settlement")
        self.assertShape(load_fixture("settled_buyer")["snap"]["lobby"], s["lobby"], "lobby")
        self.assertIsNotNone(s["round"])

    def test_machete_round_has_golden_like_fixture(self):
        self.make()
        self.eng.update_settings({"coin_oz": 0.02})
        self.graduate(machete=True)
        self.open_round()
        self.tick(3926.6, n=3)
        r = self.act("machete")
        self.assertTrue(r["accepted"], r)
        s = self.snap()
        self.assertShape(load_fixture("open_machete")["snap"]["round"]["golden"], s["round"]["golden"], "golden")
        self.assertTrue(s["round"]["machete_done"])


# ======================================================================================================================== the round
class TestEntry(EngineCase):
    def test_sl_tp_from_the_quote_at_send_time(self):
        self.make()
        self.graduate()
        self.act("fund", kind="live", side=1, target=1.2)
        self.tick(3926.00)
        r = self.eng.act({"action": "shoot", "nonce": "s1", "sent_at": self.clock.t, "args": {}})
        self.assertTrue(r["accepted"])
        self.feed.push(3927.00, dt=0.1)              # the market moves between the click and the frame
        self.eng.pump()
        place = [c for c in self.feed.calls if c[0] == "place"][-1]
        self.assertEqual(place[3], round(3927.33 - 1.0, 2))      # SL from the ask at send time
        self.assertEqual(place[4], round(3927.33 + 1.2, 2))      # TP from the ask at send time
        self.assertEqual(self.eng.round.fill, 3927.33)

    def test_ladder_reanchors_on_actual_fill_and_slippage_bites(self):
        self.make()
        self.graduate()
        self.feed.slip = 0.04
        rd = self.open_round()
        self.assertEqual(rd.fill, 3926.37)
        self.assertEqual((rd.sl0, rd.tp0), (3925.33, 3927.53))
        s = self.snap()["round"]
        self.assertAlmostEqual(s["stop_dist0"], 1.04, places=6)
        self.assertAlmostEqual(s["target_dist0"], 1.16, places=6)
        self.assertEqual(s["x_sl"], 0.0)
        self.assertEqual(s["x_tp"], 1.0)
        whys = [b["why"] for b in s["rat"]]
        self.assertIn("spread", whys)
        self.assertIn("slippage", whys)

    def test_short_mirror(self):
        self.make()
        self.graduate()
        rd = self.open_round(side=-1)
        self.assertEqual((rd.fill, rd.sl0, rd.tp0), (3926.00, 3927.00, 3924.80))
        self.tick(3925.50)
        s = self.snap()["round"]
        self.assertGreater(s["x"], s["x_entry"])            # price falling = progress for a short
        self.assertLess(s["b"], 0)

    def test_broker_refusal_three_times_returns_the_note(self):
        self.make()
        self.graduate()
        self.act("fund", kind="live", side=1)
        for i in range(3):
            self.feed.refuse["place"] = "REJECTED"
            r = self.act("shoot")
            self.assertTrue(r["accepted"])
            self.assertEqual(self.eng.phase, "aiming" if i < 2 else "lobby")
            r = self.act("shoot")
            if i < 2:
                self.assertEqual(r["why"], "cooldown")
                self.clock.t += 3.1
                self.tick(3926.0)
        self.assertEqual(self.eng.phase, "lobby")

    def test_stale_quote_refuses_the_shot(self):
        self.make()
        self.act("fund", kind="wooden")
        self.clock.t += 5.0                          # no quote for 5 s (> feed_stale_s)
        self.eng.step()
        r = self.act("shoot")
        self.assertEqual(r["why"], "stale_quote")


class TestManagement(EngineCase):
    def test_anvil_next_walks_the_stakes_toward_the_buyer(self):
        self.make()
        self.graduate()
        rd = self.open_round()
        self.assertEqual(rd.sl, 3925.33)
        self.assertTrue(self.snap()["round"]["can_anvil"])
        self.assertTrue(self.act("anvil_next")["accepted"])
        self.assertEqual(rd.sl, 3925.39)                   # the lowest lit stake above the stop, minus one tick
        self.assertEqual(rd.anvil_kind, "stake")
        self.assertTrue(self.act("anvil_next")["accepted"])
        self.assertEqual(rd.sl, 3925.69)
        r = self.act("anvil_next")
        self.assertEqual((r["accepted"], r["why"]), (False, "no_stake"))
        self.assertEqual(self.eng.round.last_refusal["why"], "no_stake")
        sets = [c for c in self.feed.calls if c[0] == "set_protective"]
        self.assertEqual([(c[2], c[3]) for c in sets], [("STOP_LOSS", 3925.39), ("STOP_LOSS", 3925.69)])

    def test_anvil_needs_the_runner_past_the_stake(self):
        self.make()
        self.graduate()
        self.open_round()
        self.tick(3925.72)                                 # mark 3925.72: stake 3925.70 not passed by min_sl_gap
        self.assertTrue(self.act("anvil_next")["accepted"])
        self.assertEqual(self.eng.round.sl, 3925.39)
        self.assertEqual(self.act("anvil_next")["why"], "no_stake")

    def test_anvil_broker_refusal_bounces(self):
        self.make()
        self.graduate()
        rd = self.open_round()
        seq = self.eng.seq
        self.feed.refuse["set_protective"] = "REJECTED: off quotes"
        self.assertTrue(self.act("anvil_next")["accepted"])
        self.assertEqual(rd.sl, 3925.33)
        evs, _ = self.eng.events_since(seq)
        self.assertIn({"type": "anvil", "ok": False, "x": 0.0}, evs)
        self.assertTrue(any(e["type"] == "refused_broker" and e["action"] == "anvil_next" for e in evs))

    def test_stakes_inside_a_chasm_are_never_lit(self):
        self.make()
        self.assertIn(3925.40, self.eng._lit_stakes(1, self.clock.t))
        self.eng.gaps.cover = {}
        self.eng.gaps.gaps = [[3925.30, 3925.50, self.clock.t]]
        self.assertNotIn(3925.40, self.eng._lit_stakes(1, self.clock.t))
        self.assertIn(3925.70, self.eng._lit_stakes(1, self.clock.t))

    def test_walls_trail_behind_the_runner_without_a_limit(self):
        """Zee 2026-11-04: a wall can be built anywhere behind the Runner, again and again, like a trailing stop."""
        self.make()
        self.graduate()
        rd = self.open_round()
        self.tick(3927.20)                                 # well past the mud, in profit
        self.assertTrue(self.act("wall")["accepted"])
        self.assertEqual(rd.sl, 3926.90)                   # right behind him: mark - wall_buffer (no break-even cap)
        self.assertEqual(rd.anvil_kind, "wall")
        for mark, want in ((3927.32, 3927.02), (3927.40, 3927.10), (3927.48, 3927.18)):   # still short of the target
            self.tick(mark)
            self.assertTrue(self.act("wall")["accepted"])
            self.assertEqual(rd.sl, want)
        self.assertEqual(len(rd.walls), 4)
        self.assertGreater(self.snap()["round"]["walls_left"], 0)

    def test_girl_never_sells_at_a_loss(self):
        """Zee 2026-11-04: clicking the ice-cream girl (need_profit) is refused unless the coin is ahead by the safety margin."""
        self.make()
        self.graduate()
        rd = self.open_round()
        self.tick(round(rd.fill + 0.03, 2))                # ahead by $0.0003: inside the margin
        self.assertEqual(self.act("merchant", need_profit=True)["why"], "not_profit")
        self.tick(round(rd.fill + 0.5, 2))                 # ahead by $0.005: a sure profit
        self.assertTrue(self.act("merchant", need_profit=True)["accepted"])

    def test_wall_must_tighten(self):
        self.make()
        self.graduate()
        self.open_round()
        self.tick(3925.50)                                 # mark - 0.30 = 3925.20 < the stop 3925.33
        self.assertEqual(self.act("wall")["why"], "no_tighten")

    def test_local_validation_before_sending(self):
        """An SL must stay below the bid by min_sl_gap for a long - checked again at send time on the freshest quote."""
        self.make()
        self.graduate()
        rd = self.open_round()
        r = self.eng.act({"action": "anvil_next", "nonce": "a1", "sent_at": self.clock.t, "args": {}})
        self.assertTrue(r["accepted"])
        self.feed.push(3925.41, dt=0.1)                     # price falls onto the stake before the frame is sent
        n_before = len(self.feed.calls)
        self.eng.pump()
        self.assertEqual(len(self.feed.calls), n_before)    # nothing was sent
        self.assertEqual(rd.sl, 3925.33)
        self.assertEqual(rd.last_refusal["why"], "too_close")

    def test_haggle_moves_rope_then_tag(self):
        self.make()
        self.graduate()
        rd = self.open_round()
        self.assertEqual(self.act("haggle")["why"], "too_far")
        for p in (3926.4, 3926.7, 3926.9, 3927.1, 3927.25, 3927.3, 3927.3):
            self.tick(p)
        self.assertGreater(self.eng.tilt_ema, 0)
        s = self.snap()["round"]
        self.assertTrue(s["can_haggle"], s)
        n0 = len(self.feed.calls)
        self.assertTrue(self.act("haggle")["accepted"])
        calls = self.feed.calls[n0:]
        self.assertEqual([(c[2], c[3]) for c in calls], [("STOP_LOSS", 3925.69), ("TAKE_PROFIT", 3927.63)])
        self.assertEqual((rd.sl, rd.tp, rd.haggles, rd.anvil_kind), (3925.69, 3927.63, 1, "haggle"))
        s = self.snap()["round"]
        self.assertGreater(s["x_tp"], 1.0)                 # the buyer drifts into the fog
        self.assertEqual(s["tag_text"], E.money(0.01 + 0.01 * (3927.63 - rd.fill), 0.01))

    def test_haggle_refused_by_broker_on_the_rope_leaves_the_tag(self):
        self.make()
        self.graduate()
        rd = self.open_round()
        for p in (3926.4, 3926.7, 3926.9, 3927.1, 3927.25, 3927.3, 3927.3):
            self.tick(p)
        self.feed.refuse["set_protective"] = "REJECTED"
        n0 = len(self.feed.calls)
        self.assertTrue(self.act("haggle")["accepted"])
        self.assertEqual(len(self.feed.calls) - n0, 1)       # only the SL was tried
        self.assertEqual((rd.tp, rd.haggles), (3927.53, 0))

    def test_haggle_needs_tilt(self):
        self.make()
        self.graduate()
        self.open_round()
        for p in (3926.8, 3927.2, 3927.5, 3927.5):
            self.tick(p)
        for p in (3927.48, 3927.45, 3927.42, 3927.40, 3927.38, 3927.36, 3927.34, 3927.32, 3927.30):
            self.tick(p, dt=1.5)                    # near the buyer, but the street slopes back toward the bank
        self.assertLess(self.eng.tilt_ema, 0)
        self.assertGreaterEqual(self.snap()["round"]["x"], self.snap()["round"]["x_tp"] - 0.12)
        self.assertEqual(self.act("haggle")["why"], "tilt")

    def test_machete_chained_at_one_cent_and_integer_lots(self):
        self.make()
        self.graduate()
        self.open_round()
        self.assertEqual(self.act("machete")["why"], "chained")
        rd = E.Round("x", "sim", "live", 1, 0.06, 1.0, 1.2, 0.06)
        self.assertEqual(self.eng._machete_qty(rd), 0.03)
        rd.qty = 0.05
        self.assertEqual(self.eng._machete_qty(rd), 0.02)
        rd.qty = 0.03
        self.assertEqual(self.eng._machete_qty(rd), 0.01)
        rd.qty = 0.01
        self.assertIsNone(self.eng._machete_qty(rd))

    def test_machete_reprojects_the_street(self):
        self.make()
        self.eng.update_settings({"coin_oz": 0.02})
        self.graduate(machete=True)
        rd = self.open_round()
        self.tick(3926.83, n=2)
        before = self.snap()["round"]
        self.assertTrue(self.act("machete")["accepted"])
        self.assertEqual(rd.qty, 0.01)
        self.assertAlmostEqual(rd.banked_usd, 0.01 * (3926.83 - 3926.33), places=9)
        s = self.snap()["round"]
        self.assertAlmostEqual(s["b"], before["b"] / 2.0, places=5)
        self.assertEqual(s["golden"]["x"], E.xp(*E.ladder(1, rd.fill, rd.sl0, rd.tp0, rd.banked_usd, 0.01, 0.02)[:2], rd.sl0))
        self.assertEqual(s["golden"]["x"], s["x_sl"])        # the vault anvil maps exactly onto the golden stake
        self.assertAlmostEqual(s["golden"]["usd"], rd.banked_usd + 0.01 * (rd.sl0 - rd.fill), places=9)
        self.assertEqual(s["x"], before["x"])               # the runner's place on the street does not jump
        self.assertEqual(self.act("machete")["why"], "machete_done")
        self.assertEqual([c for c in self.feed.calls if c[0] == "close"], [("close", rd.position_id, 0.01)])


class TestSettlement(EngineCase):
    def settle(self, bid):
        self.tick(bid)
        self.assertTrue(self.until(lambda: self.eng.phase == "settled", bid=bid), self.eng.phase)
        return self.snap()["settlement"]

    def test_buyer(self):
        self.make()
        self.graduate()
        rd = self.open_round()
        st = self.settle(3927.60)
        self.assertEqual(st["outcome"], "buyer")
        self.assertAlmostEqual(st["result_usd"], round(0.01 * (3927.60 - rd.fill), 6))
        self.assertEqual(st["result_text"], "+$0.0127")
        self.assertIn("take profit", st["plain"])

    def test_anvil(self):
        self.make()
        self.graduate()
        self.open_round()
        st = self.settle(3925.30)
        self.assertEqual(st["outcome"], "anvil")
        self.assertIsNone(st["chasm"])
        self.assertAlmostEqual(st["costs"]["slippage_usd"], 0.0003)        # filled 3 cents through the stop

    def test_barrel_gap_through_the_stop(self):
        self.make()
        self.graduate()
        rd = self.open_round()
        self.tick(3925.45)
        st = self.settle(3924.80)                                          # a gap: 0.53 through the stop
        self.assertEqual(st["outcome"], "barrel")
        a, b, _, _ = E.ladder(1, rd.fill, rd.sl0, rd.tp0)
        self.assertEqual(st["chasm"], sorted([E.xp(a, b, 3925.33), E.xp(a, b, 3924.80)]))
        self.assertEqual(st["exit"], 3924.80)

    def test_merchant_and_eject(self):
        for action in ("merchant", "eject"):
            self.make()
            self.graduate()
            rd = self.open_round()
            self.tick(3926.20)
            self.assertTrue(self.act(action)["accepted"])
            st = self.snap()["settlement"]
            self.assertEqual(st["outcome"], action)
            self.assertAlmostEqual(st["result_usd"], round(0.01 * (3926.20 - rd.fill), 6))
            self.assertEqual(self.eng.phase, "settled")
            self.assertTrue(self.act("ack")["accepted"])
            self.assertEqual(self.eng.phase, "lobby")
            self.tearDown()
            self.setUp()

    def test_outside_close_is_detected(self):
        self.make()
        self.graduate()
        rd = self.open_round()
        self.feed.outside_close(rd.position_id)                           # Zee closed the game's position on the page
        st = self.settle(3926.10)
        self.assertEqual(st["outcome"], "outside")

    def test_session_auto_close_before_the_break(self):
        self.make(real_hours=True, t0=utc("2026-11-03 20:30:00"))
        self.graduate()
        rd = self.open_round()
        self.tick(3926.10, dt=utc("2026-11-03 20:50:00") - self.clock.t)    # dead hours: the shutters fall, the round rides on
        self.assertEqual(self.snap()["market"]["shutters"]["reason"], "dead_hours")
        self.assertEqual(self.eng.phase, "open")
        self.tick(3926.10, dt=utc("2026-11-03 21:54:30") - self.clock.t)
        s = self.snap()["round"]
        self.assertTrue(s["golden_hour"])
        self.assertTrue(s["merchant"]["insists"])
        self.tick(3926.10, dt=utc("2026-11-03 21:55:01") - self.clock.t)
        self.assertTrue(self.until(lambda: self.eng.phase == "settled"))
        self.assertEqual(self.snap()["settlement"]["outcome"], "session")
        self.assertEqual([c[0] for c in self.feed.calls if c[0] == "close"], ["close"])
        self.assertEqual(self.feed.calls[-1][1], rd.position_id)

    def test_round_log_written(self):
        self.make()
        self.graduate()
        rd = self.open_round()
        self.tick(3926.3, n=4, dt=1.0)
        self.act("eject")
        path = os.path.join(self.tmp, "rounds", rd.id[:8], rd.id + ".json")
        with open(path, encoding="utf-8") as f:
            log = json.load(f)
        self.assertEqual(log["outcome"], "eject")
        self.assertEqual(log["mode"], "sim")
        self.assertTrue(all("nonce" in i and "accepted" in i for i in log["instructions"]))
        self.assertIn("shoot", [i["action"] for i in log["instructions"]])
        self.assertIn("fund", [i["action"] for i in log["instructions"]])
        shoot = [i for i in log["instructions"] if i["action"] == "shoot"][0]
        self.assertTrue(shoot["broker"]["ok"])
        self.assertGreaterEqual(len(log["path"]), 3)
        self.assertEqual(log["fills"][0]["what"], "open")
        self.assertIn("spread_usd", log["costs"])
        self.assertEqual(log["settlement"]["outcome"], "eject")
        self.assertGreater(log["quotes"]["n"], 0)


class TestLimits(EngineCase):
    def stop_out(self):
        self.open_round()
        self.tick(3925.30)
        self.assertTrue(self.until(lambda: self.eng.phase == "settled", bid=3925.30))
        self.assertTrue(self.act("ack")["accepted"])
        self.tick(3926.0)

    def test_three_stops_jam_the_door(self):
        self.make()
        self.graduate()
        for _ in range(3):
            self.stop_out()
        s = self.snap()
        self.assertEqual(s["limits"]["stops_in_row"], 3)
        self.assertIsNotNone(s["limits"]["jam_until"])
        self.assertEqual(s["market"]["shutters"]["reason"], "jam")
        self.assertEqual(self.act("fund", kind="live")["why"], "jam")
        self.assertEqual(self.act("fund", kind="wooden")["why"], "jam")
        self.tick(3926.0, dt=601)
        self.assertTrue(self.act("fund", kind="live")["accepted"])
        self.assertEqual(self.snap()["limits"]["stops_in_row"], 0)

    def test_loss_limit_locks_until_next_utc_day(self):
        self.make(cfg={"loss_max_coins": 2})
        self.graduate()
        self.stop_out()
        self.stop_out()
        s = self.snap()
        self.assertGreaterEqual(s["limits"]["loss_today_coins"], 2)
        self.assertEqual(s["market"]["shutters"]["reason"], "locked")
        self.assertEqual(s["limits"]["locked_until"], utc("2026-11-04 00:00:00"))
        self.assertEqual(self.act("fund", kind="wooden")["why"], "locked")
        self.tick(3926.0, dt=utc("2026-11-04 00:00:05") - self.clock.t)
        self.graduate()
        self.assertTrue(self.act("fund", kind="live")["accepted"])

    def test_rounds_max_per_day(self):
        self.make(cfg={"rounds_max": 2})
        self.graduate()
        for _ in range(2):
            self.open_round()
            self.act("merchant")
            self.act("ack")
        self.assertEqual(self.snap()["limits"]["rounds_today"], 2)
        self.assertEqual(self.act("fund", kind="live")["why"], "rounds_max")

    def test_wooden_rounds_do_not_count_toward_the_limits(self):
        self.make(cfg={"rounds_max": 1})
        self.open_round(kind="wooden")
        self.act("merchant")
        self.act("ack")
        self.assertEqual(self.snap()["limits"]["rounds_today"], 0)
        self.assertTrue(self.act("fund", kind="wooden")["accepted"])

    def test_shutters(self):
        self.make(real_hours=True, t0=utc("2026-11-03 21:00:00"))
        self.assertEqual(self.act("fund", kind="wooden")["why"], "dead_hours")
        self.make(real_hours=True, t0=utc("2026-11-07 12:00:00"))
        self.assertEqual(self.act("fund", kind="wooden")["why"], "weekend")
        self.make()                                             # Zee 2026-11-04: the practice (sim) bank never shuts for its invented news
        self.feed.news = [{"t": self.clock.t + 600, "title": "US CPI", "impact": "high", "country": "US"}]
        self.tick(3926.0)
        self.assertFalse(self.snap()["market"]["shutters"]["down"])
        self.make(cfg={"news_shutters_in_sim": True})           # the closure itself (the live rule) still works
        self.feed.news = [{"t": self.clock.t + 600, "title": "US CPI", "impact": "high", "country": "US"}]
        self.tick(3926.0)
        s = self.snap()
        self.assertEqual(s["market"]["shutters"]["reason"], "news")
        self.assertEqual(s["market"]["weather"], "storm")
        self.assertEqual(self.act("fund", kind="wooden")["why"], "news")
        self.feed.news = []
        self.clock.t += 20                                      # the feed falls silent
        self.eng.step()
        s = self.snap()
        self.assertEqual(s["market"]["shutters"]["reason"], "no_feed")
        self.assertTrue(s["freeze"])
        self.assertEqual(self.act("fund", kind="wooden")["why"], "no_feed")
        self.tick(3926.0)
        self.assertFalse(self.snap()["freeze"])

    def test_sim_ignores_the_real_dead_hours_unless_asked(self):
        self.make(t0=utc("2026-11-03 21:00:00"))
        self.assertTrue(self.act("fund", kind="wooden")["accepted"])
        self.assertEqual(self.snap()["market"]["session"], "dead")


class TestAlleyGating(EngineCase):
    def test_live_needs_alley_eject_confirm_mode_balance(self):
        self.make()
        self.assertEqual(self.act("fund", kind="live")["why"], "alley")
        for i in range(5):                                       # five wooden rounds, no eject yet
            self.open_round(kind="wooden")
            self.act("merchant")
            self.act("ack")
        s = self.snap()["limits"]
        self.assertEqual((s["alley_done"], s["alley_eject_done"], s["why_not_live"]), (5, False, "alley"))
        self.open_round(kind="wooden")
        self.act("eject")
        self.act("ack")
        self.assertEqual(self.snap()["limits"]["why_not_live"], "confirm")
        self.assertEqual(self.eng.update_settings({"live_enabled": True})["why"], "confirm")
        self.assertEqual(self.eng.update_settings({"live_enabled": True, "confirm_word": "confirm"})["why"], "confirm")
        self.assertTrue(self.eng.update_settings({"live_enabled": True, "confirm_word": "CONFIRM"})["ok"])
        s = self.snap()["limits"]
        self.assertEqual((s["live_allowed"], s["why_not_live"]), (True, None))
        self.assertTrue(self.act("fund", kind="live")["accepted"])

    def test_diamond_reading_reaches_the_snapshot(self):
        """Zee 2026-11-04: his UHV Diamond (diamond.py) is read on the feed's bars and shown as market.diamond: a camel-hump uptrend, a red
        retracement with one loud candle, a quiet green breakout -> a cut diamond on the buy side."""
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
        import test_diamond as TD
        bars = TD.make(TD.TREND + [(3, -0.8, [10, 40, 12]), (1, 2.6, [20])], start=3910.0)
        shift = int(T0 // 60) * 60 - bars[-1][0]
        bars = [[b[0] + shift] + [round(x, 2) for x in b[1:5]] + [b[5]] for b in bars]
        eng = self.make(bars=bars, bid=bars[-1][4])
        d = self.snap()["market"]["diamond"]
        self.assertEqual(d.get("camel"), 1)
        self.assertEqual(d.get("cut"), 1)
        self.assertIn("id", d)

    def test_vsa_read_patterns(self):
        """Zee 2026-11-04: the volume hints read real bars - an upthrust, a spring, and stopping volume after a fall."""
        base = [[i * 60, 100.0, 100.5, 99.5, 100.0] for i in range(21)]
        vols = [10] * 21
        up = base + [[21 * 60, 100.0, 102.0, 99.9, 100.2]]          # a new high, closing in its bottom third, on 3x volume
        self.assertEqual(E.vsa_read(up, vols + [30]), ("trap", -1))
        dn = base + [[21 * 60, 100.0, 100.1, 98.0, 99.9]]           # a new low, closing in its top third
        self.assertEqual(E.vsa_read(dn, vols + [30]), ("trap", 1))
        fall = [[i * 60, 100.0 - i * 0.3, 100.3 - i * 0.3, 99.6 - i * 0.3, 99.7 - i * 0.3] for i in range(21)]
        stop = fall + [[21 * 60, 93.7, 93.9, 93.62, 93.85]]         # after the fall: a heavy bar that closes high and barely moves (no new low)
        self.assertEqual(E.vsa_read(stop, vols + [30]), ("stopping", 1))
        self.assertEqual(E.vsa_read(up, vols + [12]), (None, 0))   # no ultra-high volume: no hint

    def test_heikin_ashi_delta(self):
        """Zee 2026-11-04: the HA tilt is recursive (HA open = previous HA open + close / 2) and signs the trend."""
        up = [[i * 60, 100 + i, 100.5 + i, 99.8 + i, 100.4 + i] for i in range(10)]
        dn = [[i * 60, 100 - i, 100.2 - i, 99.5 - i, 99.6 - i] for i in range(10)]
        self.assertGreater(E.ha_delta(up), 0)
        self.assertLess(E.ha_delta(dn), 0)
        b = [[0, 10, 12, 9, 11], [60, 11, 13, 10, 12]]
        ha_o = ((10 + 11) / 2 + (10 + 12 + 9 + 11) / 4) / 2      # recursive open from the first bar
        self.assertAlmostEqual(E.ha_delta(b), (11 + 13 + 10 + 12) / 4 - ha_o)

    def test_tilt_follows_heikin_ashi_when_asked(self):
        self.make(cfg={"tilt_mode": "ha"})
        self.feed.bars = [[i * 60, 3920 + i * 0.3, 3920.4 + i * 0.3, 3919.9 + i * 0.3, 3920.3 + i * 0.3, 10] for i in range(12)]
        for _ in range(20):
            self.tick(3926.0)
        self.assertGreater(self.eng.tilt_raw, 0)

    def test_coins_follow_the_men_shot(self):
        """Zee 2026-11-04: shooting 1-3 men funds 1-3 coins (0.01 oz each); after the round it is one coin again."""
        self.make()
        self.assertTrue(self.act("fund", kind="wooden", coins=3)["accepted"])
        self.assertAlmostEqual(self.eng.settings["coin_oz"], 0.03)
        self.act("unfund")
        self.assertEqual(self.act("fund", kind="wooden", coins=4)["why"], "bad_args")
        self.assertEqual(self.snap()["settings"]["target"], 1.0)        # the closest target is the default

    def test_machete_needed_in_the_alley_only_if_can_split(self):
        self.make(cfg={"alley_needs_machete": True})
        self.graduate()
        self.assertIsNone(self.snap()["limits"]["why_not_live"])
        self.eng.update_settings({"coin_oz": 0.02})
        s = self.snap()["limits"]
        self.assertEqual((s["alley_machete_needed"], s["why_not_live"]), (True, "alley"))

    def test_replay_mode_is_wooden_only(self):
        self.make(mode="replay")
        self.graduate()
        self.assertEqual(self.act("fund", kind="live")["why"], "mode")
        self.assertTrue(self.act("fund", kind="wooden")["accepted"])

    def test_balance_gate(self):
        self.make(balance=0.02)
        self.graduate()
        self.assertEqual(self.act("fund", kind="live")["why"], "balance")

    def test_live_enabled_never_survives_a_restart(self):
        self.make()
        self.graduate()
        self.assertTrue(self.eng.settings["live_enabled"])
        eng2 = E.Engine(self.feed, cfg={"shadow_broker": "engine"}, root=self.tmp, clock=self.clock, threaded=False, verbose=False,
                        cfg_path=os.path.join(self.tmp, "no_config.json"))
        self.assertFalse(eng2.settings["live_enabled"])

    def test_sim_wooden_rounds_never_graduate_live_mode(self):
        self.make()
        for _ in range(5):
            self.open_round(kind="wooden")
            self.act("eject")
            self.act("ack")
        self.assertEqual(self.snap()["limits"]["alley_done"], 5)
        feed = FakeFeed(self.clock, mode="live")
        eng2 = E.Engine(feed, cfg={"shadow_broker": "engine"}, root=self.tmp, clock=self.clock, threaded=False, verbose=False,
                        cfg_path=os.path.join(self.tmp, "no_config.json"))
        eng2.step()
        self.assertEqual(eng2.snapshot()["limits"]["alley_done"], 0)


class TestInstructions(EngineCase):
    def test_stale_and_duplicate(self):
        self.make()
        self.assertEqual(self.act("fund", sent_at=self.clock.t - 2.5, kind="wooden")["why"], "stale")
        self.assertEqual(self.act("fund", sent_at=self.clock.t + 5, kind="wooden")["why"], "stale")
        self.assertEqual(self.eng.act({"action": "fund", "args": {"kind": "wooden"}, "sent_at": self.clock.t})["why"], "nonce")
        self.assertEqual(self.eng.act({"action": "fly", "nonce": "z", "sent_at": self.clock.t})["why"], "unknown_action")
        self.assertTrue(self.act("fund", nonce="same", kind="wooden")["accepted"])
        self.assertEqual(self.act("unfund", nonce="same")["why"], "duplicate")
        self.assertEqual(self.eng.phase, "aiming")
        seq = self.eng.seq
        self.act("unfund", sent_at=self.clock.t - 10)
        evs, _ = self.eng.events_since(seq)
        self.assertEqual(evs[-1]["type"], "refused")
        self.assertEqual(evs[-1]["why"], "stale")

    def test_phase_rules(self):
        self.make()
        self.assertEqual(self.act("shoot")["why"], "phase")
        self.assertEqual(self.act("anvil_next")["why"], "phase")
        self.assertEqual(self.act("ack")["why"], "phase")
        self.assertTrue(self.act("set_target", target=1.5)["accepted"])
        self.assertEqual(self.act("set_target", target=1.7)["why"], "bad_target")
        self.assertTrue(self.act("flip", side=-1)["accepted"])
        self.assertEqual(self.snap()["preview"]["side"], -1)
        self.assertTrue(self.act("fund", kind="wooden")["accepted"])
        self.assertEqual(self.snap()["settings"]["target"], 1.5)
        self.assertEqual(self.act("fund", kind="wooden")["why"], "phase")
        self.assertTrue(self.act("unfund")["accepted"])
        self.assertEqual(self.eng.phase, "lobby")


class TestKillSwitch(EngineCase):
    def test_kill_closes_only_the_games_position_and_locks(self):
        self.make()
        self.feed.add_outside_position(999)
        self.graduate()
        rd = self.open_round()
        self.tick(3926.1)
        r = self.act("kill", sent_at=self.clock.t - 60)        # the kill switch is never refused as stale
        self.assertTrue(r["accepted"])
        self.assertTrue(self.until(lambda: self.eng.phase == "settled"))
        self.assertEqual(self.snap()["settlement"]["outcome"], "kill")
        closes = [c for c in self.feed.calls if c[0] == "close"]
        self.assertEqual(closes, [("close", rd.position_id, 0.01)])
        self.assertFalse(any(999 in c[1:2] for c in self.feed.calls))
        self.assertIn(999, self.feed.pos)                       # Zee's own position is untouched
        self.act("ack")
        s = self.snap()
        self.assertEqual(s["market"]["shutters"]["reason"], "locked")
        self.assertFalse(s["settings"]["live_enabled"])
        self.assertEqual(self.act("fund", kind="wooden")["why"], "locked")

    def test_kill_with_no_round_trades_nothing(self):
        self.make()
        self.feed.add_outside_position(999)
        self.assertTrue(self.act("kill")["accepted"])
        self.assertEqual(self.feed.calls, [])
        self.assertEqual(self.snap()["market"]["shutters"]["reason"], "locked")

    def test_outside_positions_never_counted_or_touched(self):
        self.make()
        self.feed.add_outside_position(999)
        self.graduate()
        rd = self.open_round()
        self.feed.outside_close(999)                            # Zee closes his own trade: our round does not care
        self.tick(3926.2, n=12)
        self.assertEqual(self.eng.phase, "open")
        self.assertEqual(self.eng.round.position_id, rd.position_id)
        self.act("eject")
        self.assertFalse(any(len(c) > 1 and c[1] == 999 for c in self.feed.calls))


class TestTwinCounterfactualTallies(EngineCase):
    def test_twin_trails_every_stake_and_reports(self):
        self.make()
        rd = self.open_round(kind="wooden", twin=True)
        self.tick(3926.1)
        tw = rd.twin
        self.assertIsNotNone(tw)
        self.assertEqual(tw["sl"], rd.sl0)                      # stakes that already stood at entry are not the Twin's (CONTRACT 5: new stakes)
        orig = self.eng._lit_stakes
        self.eng._lit_stakes = lambda side, now: orig(side, now) + [3925.80]   # a swing low confirmed after the Twin entered
        self.tick(3926.1)
        self.assertEqual(tw["sl"], 3925.79)                     # the new stake, minus a tick
        self.tick(3925.60)                                      # the twin is stopped; the player (stop 3925.33) rides on
        self.assertEqual(tw["state"], "done")
        self.assertAlmostEqual(tw["result_usd"], round(0.01 * (3925.60 - 3926.33), 6))
        self.assertEqual(self.eng.phase, "open")
        s = self.snap()["round"]["twin"]
        self.assertEqual(s["state"], "done")
        self.act("merchant")
        self.assertAlmostEqual(self.snap()["settlement"]["twin_result_usd"], tw["result_usd"])

    def test_twin_locked_on_the_street_until_50_rounds(self):
        self.make()
        self.graduate()
        rd = self.open_round(kind="live", twin=True)
        self.assertIsNone(rd.twin)
        self.assertFalse(self.snap()["settings"]["twin_unlocked"])

    def test_eject_counterfactual_and_tallies(self):
        self.make()
        rd = self.open_round(kind="wooden")
        self.tick(3926.00)
        self.act("eject")
        st = self.snap()["settlement"]
        self.assertEqual(st["outcome"], "eject")
        self.assertIsNone(st["would_have_usd"])
        self.tick(3927.0)
        self.tick(3927.60)                                      # the target would have been hit
        self.assertAlmostEqual(self.snap()["settlement"]["would_have_usd"], round(0.01 * (3927.60 - rd.fill), 6))
        self.act("ack")
        t = self.eng.tallies()
        self.assertEqual(t["ejected"]["n"], 0)                  # a wooden round never enters the real scoreboard (REQUIREMENTS 9/11)
        self.assertEqual(t["wooden_ejected"]["n"], 1)
        self.assertAlmostEqual(t["wooden_ejected"]["would_have_usd"], round(0.01 * (3927.60 - rd.fill), 6))
        with open(os.path.join(self.tmp, "rounds", rd.id[:8], rd.id + ".json"), encoding="utf-8") as f:
            self.assertAlmostEqual(json.load(f)["would_have_usd"], round(0.01 * (3927.60 - rd.fill), 6))

    def test_tallies_rebuilt_from_round_logs(self):
        self.make()
        for exit_action in ("eject", "merchant"):
            self.open_round(kind="wooden")
            self.tick(3926.4)
            self.act(exit_action)
            self.act("ack")
        os.makedirs(os.path.join(self.tmp, "rounds"), exist_ok=True)
        with open(os.path.join(self.tmp, "rounds", "p0_1793677252.json"), "w") as f:
            json.dump({"started": "2026-11-03", "steps": []}, f)           # not a round log: must be skipped
        with open(os.path.join(self.tmp, "rounds", "20261103", "junk.json"), "w") as f:
            f.write("{not json")
        before = self.eng.tallies()
        eng2 = E.Engine(self.feed, cfg={"shadow_broker": "engine"}, root=self.tmp, clock=self.clock, threaded=False, verbose=False,
                        cfg_path=os.path.join(self.tmp, "no_config.json"))
        self.assertEqual(eng2.tallies(), before)
        self.assertEqual(before["wooden"]["n"], 2)
        self.assertEqual(sum(v["n"] for v in before["by_session"].values()), 0)          # real rounds only
        self.assertEqual(sum(v["n"] for v in before["wooden_by_session"].values()), 2)  # the Alley's own breakdown
        self.assertEqual(len(eng2.rounds_list()), 2)
        trophies = [t["key"] for t in eng2.snapshot()["lobby"]["trophies"]]
        self.assertIn("first_wooden", trophies)

    def test_ghosts_from_previous_rounds(self):
        self.make()
        self.open_round(kind="wooden")
        self.tick(3926.4, n=5, dt=1.0)
        self.act("merchant")
        self.act("ack")
        self.open_round(kind="wooden")
        ghosts = self.snap()["round"]["ghosts"]
        self.assertEqual(len(ghosts), 1)
        self.assertGreaterEqual(len(ghosts[0]["path"]), 3)


class TestRestartSafety(EngineCase):
    def test_live_round_resumes_after_restart_and_kill_still_works(self):
        self.make(mode="live")
        self.graduate()
        rd = self.open_round()
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "state", "open_round_live.json")))
        eng2 = E.Engine(self.feed, cfg={"shadow_broker": "engine", "paper_slippage_max": 0.0}, root=self.tmp, clock=self.clock,
                        threaded=False, verbose=False, cfg_path=os.path.join(self.tmp, "no_config.json"))
        self.eng = eng2
        self.tick(3926.1, n=12)
        self.assertEqual(eng2.phase, "open")
        self.assertEqual(eng2.round.position_id, rd.position_id)
        self.act("kill")
        self.assertTrue(self.until(lambda: eng2.phase == "settled"))
        self.assertEqual(eng2.snapshot()["settlement"]["outcome"], "kill")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "state", "open_round_live.json")))


class TestWithFeedsPy(unittest.TestCase):
    """Optional: the real feeds.SimFeed (manual) + feeds.ShadowBroker, if feeds.py imports."""

    def test_wooden_round_on_simfeed(self):
        try:
            import feeds
        except Exception as e:  # noqa: BLE001
            self.skipTest(f"feeds.py not importable: {e}")
        tmp = tempfile.mkdtemp(prefix="gg_test_engine_sim_")
        try:
            feed = feeds.SimFeed(seed=7, manual=True)
            eng = E.Engine(feed, root=tmp, clock=feed.now, threaded=False, verbose=False, cfg={"paper_slippage_max": 0.0},
                           cfg_path=os.path.join(tmp, "no_config.json"))
            self.assertEqual(eng.book_impl, "feeds.ShadowBroker")
            n = itertools.count(1)

            def act(a, **args):
                r = eng.act({"action": a, "nonce": f"s{next(n)}", "sent_at": feed.now(), "args": args})
                eng.settle_all()
                return r
            feed.advance(3)
            eng.settle_all()
            self.assertTrue(act("fund", kind="wooden")["accepted"])
            feed.advance(1)
            eng.settle_all()
            self.assertTrue(act("shoot")["accepted"])
            self.assertEqual(eng.phase, "open")
            feed.advance(5)
            eng.settle_all()
            if eng.phase == "open":
                self.assertTrue(act("eject")["accepted"])
            self.assertEqual(eng.phase, "settled")
            self.assertIn(eng.snapshot()["settlement"]["outcome"], E.OUTCOMES)
            self.assertEqual(feed.broker.positions(), [])             # the wooden round never reached the SimFeed's account
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestHardening(EngineCase):
    def test_refused_session_close_is_not_hammered(self):
        self.make(real_hours=True, t0=utc("2026-11-03 20:30:00"))
        self.graduate()
        self.open_round()
        self.feed.refuse["close"] = "REJECTED"
        n0 = len(self.feed.calls)
        self.tick(3926.10, dt=utc("2026-11-03 21:55:01") - self.clock.t)
        for _ in range(10):                                   # 10 ticks in 2 s: at most one more try
            self.tick(3926.10, dt=0.2)
        closes = [c for c in self.feed.calls[n0:] if c[0] == "close"]
        self.assertEqual(len(closes), 1)
        self.assertEqual(self.eng.phase, "open")
        self.tick(3926.10, dt=5.0)
        self.assertTrue(self.until(lambda: self.eng.phase == "settled"))
        self.assertEqual(self.snap()["settlement"]["outcome"], "session")

    def test_a_position_the_book_never_shows_is_not_declared_closed(self):
        self.make()
        self.graduate()
        hidden = {"on": True}
        real_state = self.feed.state

        def state():
            s = real_state()
            if hidden["on"]:
                s["positions"] = []
            return s
        self.feed.state = state
        rd = self.open_round()
        for _ in range(60):
            self.tick(3926.1, dt=0.5)
        self.assertEqual(self.eng.phase, "open")              # 30 s later: still open, not "outside"
        self.assertTrue(rd.blind)
        self.assertTrue(self.act("eject")["accepted"])        # the player can always end it
        self.assertTrue(self.until(lambda: self.eng.phase == "settled"))
        self.assertEqual(self.snap()["settlement"]["outcome"], "eject")
        self.assertEqual([c for c in self.feed.calls if c[0] == "close"], [("close", rd.position_id, 0.01)])


class TestServer(EngineCase):
    def test_http_api_stream_and_static(self):
        import threading
        import urllib.request
        import server as S
        self.make()
        httpd = S.GameServer(("127.0.0.1", 0), S.Handler, hz=10)
        httpd.engine = self.eng
        th = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        th.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            snap = json.load(urllib.request.urlopen(base + "/api/state", timeout=5))
            self.assertEqual((snap["v"], snap["mode"], snap["phase"]), (1, "sim", "lobby"))
            req = urllib.request.Request(base + "/api/act", data=json.dumps({"action": "fund", "nonce": "h1", "sent_at": self.clock.t,
                                                                               "args": {"kind": "wooden"}}).encode(),
                                         headers={"Content-Type": "application/json"})
            self.assertEqual(json.load(urllib.request.urlopen(req, timeout=5)), {"accepted": True, "why": None})
            req = urllib.request.Request(base + "/api/act", data=b"not json", headers={"Content-Type": "application/json"})
            self.assertEqual(json.load(urllib.request.urlopen(req, timeout=5)), {"accepted": False, "why": "bad_json"})
            req = urllib.request.Request(base + "/api/settings", data=json.dumps({"live_enabled": True}).encode(),
                                         headers={"Content-Type": "application/json"})
            self.assertEqual(json.load(urllib.request.urlopen(req, timeout=5))["why"], "confirm")
            resp = urllib.request.urlopen(base + "/api/stream", timeout=5)
            self.assertTrue(resp.headers["Content-Type"].startswith("text/event-stream"))
            self.assertEqual(resp.headers["Cache-Control"], "no-store")
            lines = []
            while len([x for x in lines if x.startswith("event: snap")]) < 3:
                lines.append(resp.readline().decode().rstrip("\n"))
            resp.close()
            data = [x for x in lines if x.startswith("data: ")]
            self.assertEqual(json.loads(data[0][6:])["phase"], "aiming")
            js = urllib.request.urlopen(base + "/js/palette.js", timeout=5)
            self.assertTrue(js.headers["Content-Type"].startswith("text/javascript"))
            fx = urllib.request.urlopen(base + "/static/fixtures/lobby.json", timeout=5)
            self.assertTrue(fx.headers["Content-Type"].startswith("application/json"))
            self.assertEqual(urllib.request.urlopen(base + "/?fixture=lobby", timeout=5).status, 200)
            self.assertEqual(json.load(urllib.request.urlopen(base + "/api/tallies", timeout=5))["wooden"]["n"], 0)
            self.assertEqual(json.load(urllib.request.urlopen(base + "/api/rounds?limit=5", timeout=5)), [])
            import http.client
            c = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=5)
            c.request("GET", "/static/../config.json")
            resp = c.getresponse()
            self.assertIn(resp.status, (403, 404))
            resp.read()
            c.close()
        finally:
            httpd.stopping = True
            httpd.shutdown()
            httpd.server_close()


    def test_cross_site_requests_are_refused(self):
        """CSRF / DNS rebinding: a page on another origin can send 'simple' POSTs (text/plain, its own Origin) and, after a DNS
        rebind, requests with its own Host. None of them may reach the engine."""
        import http.client
        import threading
        import server as S
        self.make()
        httpd = S.GameServer(("127.0.0.1", 0), S.Handler, hz=10)
        httpd.engine = self.eng
        th = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        th.start()
        port = httpd.server_address[1]
        good_host = f"127.0.0.1:{port}"

        def req(method, path, body=None, **hdr):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            headers = {"Host": good_host}
            headers.update({k.replace("_", "-"): v for k, v in hdr.items()})
            c.request(method, path, body=json.dumps(body).encode() if body is not None else None, headers=headers)
            r = c.getresponse()
            data = r.read()
            c.close()
            return r.status, (json.loads(data) if data else None)
        settings = {"live_enabled": True, "confirm_word": "CONFIRM"}
        fund = {"action": "fund", "nonce": "x1", "sent_at": self.clock.t, "args": {"kind": "wooden"}}
        try:
            cases = [
                ("POST", "/api/settings", settings, {"Content_Type": "text/plain;charset=UTF-8"}),           # no preflight
                ("POST", "/api/settings", settings, {}),                                                      # no type
                ("POST", "/api/settings", settings, {"Content_Type": "application/json", "Origin": "http://evil.example"}),
                ("POST", "/api/act", fund, {"Content_Type": "application/json", "Origin": "null"}),
                ("POST", "/api/act", fund, {"Content_Type": "application/json", "Host": f"evil.example:{port}"}),  # rebinding
                ("POST", "/api/act", fund, {"Content_Type": "application/json", "Sec_Fetch_Site": "cross-site"}),
                ("POST", "/api/act", dict(fund, action="kill", sent_at=0), {"Content_Type": "text/plain"}),
                ("GET", "/api/state", None, {"Host": f"evil.example:{port}"}),
                ("GET", "/api/stream", None, {"Host": f"evil.example:{port}"}),
                ("GET", "/api/rounds", None, {"Host": "localhost:1"}),
            ]
            for method, path, body, hdr in cases:
                st, out = req(method, path, body, **hdr)
                self.assertEqual(st, 403, (method, path, hdr, out))
                self.assertTrue(str(out.get("why", "")).startswith("forbidden"), out)
            self.assertFalse(self.eng.settings["live_enabled"])
            self.assertEqual(self.eng.phase, "lobby")
            self.assertEqual(self.eng.killed, {})                       # the refused kill never locked the day
            # the game's own page: same-origin fetch with JSON
            st, out = req("POST", "/api/act", fund, Content_Type="application/json", Origin=f"http://{good_host}",
                          Sec_Fetch_Site="same-origin")
            self.assertEqual((st, out), (200, {"accepted": True, "why": None}))
            st, out = req("GET", "/api/state", None, Host=f"localhost:{port}")
            self.assertEqual((st, out["phase"]), (200, "aiming"))
        finally:
            httpd.stopping = True
            httpd.shutdown()
            httpd.server_close()


class TestEvents(EngineCase):
    def test_bell_rings_at_the_london_open(self):
        self.make(t0=utc("2026-11-03 07:59:50"))
        seq = self.eng.seq
        self.tick(3926.0, n=6, dt=2.0)                          # crosses 08:00 London (= UTC in November)
        evs, _ = self.eng.events_since(seq)
        self.assertIn({"type": "bell", "session": "london"}, evs)
        b = self.snap()["market"]["bell"]
        self.assertEqual((b["session"], b["last_t"]), ("london", utc("2026-11-03 08:00:00")))

    def test_lightning_on_a_spike(self):
        self.make()
        seq = self.eng.seq
        self.tick(3926.0)
        self.tick(3926.9, dt=0.5)                               # +0.90 in half a second
        evs, _ = self.eng.events_since(seq)
        self.assertIn({"type": "lightning"}, evs)
        self.assertTrue(self.snap()["market"]["lightning"])

    def test_stake_event_when_a_new_swing_low_is_confirmed(self):
        self.make()
        self.graduate()
        self.open_round()
        seq = self.eng.seq
        bars = self.feed.bars
        t = bars[-1][0]
        bars[-1] = [t, 3926.0, 3926.2, 3925.95, 3926.0, 100]   # the forming bar closes; then a dip and two higher lows confirm it
        for i, lo in enumerate((3925.10, 3925.90, 3925.92), start=1):
            bars.append([t + 60 * i, 3926.0, 3926.2, lo, 3926.0, 100])
        bars.append([t + 240, 3926.0, 3926.2, 3926.0, 3926.0, 10])
        self.tick(3926.1)
        evs, _ = self.eng.events_since(seq)
        stakes = [e for e in evs if e["type"] == "stake"]
        self.assertEqual(len(stakes), 1)
        self.assertEqual(stakes[0]["price"], 3925.10)
        rd = self.eng.round
        a, b, _, _ = E.ladder(1, rd.fill, rd.sl0, rd.tp0)
        self.assertEqual(stakes[0]["x"], E.xp(a, b, 3925.09))


class TestUncertainOrders(EngineCase):
    """LiveFeed can answer place() without a position id (resolve_token) or lose the answer (TIMEOUT); the engine must neither lose
    the position nor grab one that is not the game's."""

    def _wrap(self, mode):
        feed = self.feed
        real_place = feed.place
        feed.adopted = []
        feed.hidden = {}

        def place(side, qty, sl, tp, timeout=5.0):
            res = real_place(side, qty, sl, tp, timeout)
            feed.hidden["pid"] = res["position_id"]
            if mode == "token":
                return {"ok": True, "error": None, "rtt_ms": 1.0, "order_id": res["order_id"], "position_id": None, "fill_price": None,
                        "resolve_token": {"seq": 1}}
            return {"ok": False, "error": "TIMEOUT", "rtt_ms": 5000.0, "order_id": None, "position_id": None, "fill_price": None}

        feed.place = place
        feed.adopt = lambda pid: feed.adopted.append(pid) or True
        if mode == "token":
            feed.resolve = lambda token, timeout=2.0: {"ok": True, "position_id": feed.hidden["pid"], "fill_price": 3926.33}
        return feed

    def test_accepted_order_without_id_is_resolved_by_the_feed(self):
        self.make()
        self.graduate()
        feed = self._wrap("token")
        rd = self.open_round()
        self.assertEqual(rd.position_id, feed.hidden["pid"])
        self.assertEqual(rd.fill, 3926.33)
        self.assertEqual(feed.adopted, [])

    def test_lost_answer_but_new_position_is_adopted(self):
        self.make()
        self.feed.add_outside_position(999, side=1, qty=0.01)     # Zee's own long of the same size must not be taken
        self.graduate()
        feed = self._wrap("timeout")
        rd = self.open_round()
        self.assertEqual(rd.position_id, feed.hidden["pid"])
        self.assertNotEqual(rd.position_id, 999)
        self.assertEqual(feed.adopted, [feed.hidden["pid"]])

    def test_restore_adopts_the_games_position(self):
        self.make(mode="live")
        self.graduate()
        rd = self.open_round()
        self.feed.adopted = []
        self.feed.adopt = lambda pid: self.feed.adopted.append(pid) or True
        eng2 = E.Engine(self.feed, cfg={"shadow_broker": "engine"}, root=self.tmp, clock=self.clock, threaded=False, verbose=False,
                        cfg_path=os.path.join(self.tmp, "no_config.json"))
        self.eng = eng2
        self.tick(3926.1, n=12)
        self.assertEqual(self.feed.adopted, [rd.position_id])


# ======================================================================================================================== integration (2026-11-03)
class TestIntegration(EngineCase):
    """Integration fixes: the settlement carries the coin's final value (the roof sign), and a looping replay's seam is a close."""

    def test_settlement_carries_the_coins_final_value(self):
        self.make()
        self.graduate()
        self.open_round()
        self.tick(3927.60)
        self.assertTrue(self.until(lambda: self.eng.phase == "settled", bid=3927.60), self.eng.phase)
        snap = self.snap()
        st, r = snap["settlement"], snap["round"]
        self.assertEqual(st["outcome"], "buyer")
        self.assertAlmostEqual(st["value_usd"], round(r["risk_usd"] + st["result_usd"], 6))
        self.assertEqual(st["value_text"], E.money(st["value_usd"], r["risk_usd"]))
        self.assertEqual(st["value_text"], r["value_text"])            # the frozen round says the same thing
        self.assertTrue(st["result_text"].startswith("+"))             # the receipt keeps the signed result

    def test_settled_value_equals_the_tag_on_an_exact_take_profit(self):
        self.make()
        self.graduate()
        rd = self.open_round()
        tp = rd.tp
        self.tick(round(tp, 2))                                        # the bid touches the tag exactly: filled at the tag
        self.assertTrue(self.until(lambda: self.eng.phase == "settled", bid=round(tp, 2)), self.eng.phase)
        snap = self.snap()
        self.assertEqual(snap["settlement"]["outcome"], "buyer")
        self.assertEqual(snap["settlement"]["value_text"], snap["round"]["tag_text"])

    def _lap_feed(self):
        feed = self.feed
        feed.lap, feed.lap_t = 0, None
        base = feed.state
        feed.state = lambda: dict(base(), replay_lap=feed.lap, replay_lap_t=feed.lap_t)
        return feed

    def _new_lap(self, feed):
        feed.lap += 1
        feed.lap_t = self.clock.t + 0.2                  # the next quote is the new lap's first (stamped after the lap began)

    def test_replay_lap_seam_is_a_session_close_not_a_gap(self):
        self.make(mode="replay")
        feed = self._lap_feed()
        self.tick(3926.00, n=3)
        rd = self.open_round(kind="wooden")
        self.tick(3926.10, n=3)
        last_bid = feed.quote["bid"]
        seq0 = self.eng.seq
        self._new_lap(feed)                                            # the recording starts again, 1.7 lower: through the anvil
        self.tick(3924.40)
        self.assertTrue(self.until(lambda: self.eng.phase == "settled", bid=3924.40), self.eng.phase)
        st = self.snap()["settlement"]
        self.assertEqual(st["outcome"], "session")                     # the Merchant insisted at the end of the recording
        self.assertAlmostEqual(st["exit"], last_bid)                   # at the lap's last quote, never across the seam
        self.assertIsNone(st["chasm"])
        self.assertGreater(st["result_usd"], -rd.risk_usd)
        evs, _ = self.eng.events_since(seq0)
        self.assertFalse(any(e.get("type") == "lightning" for e in evs))
        self.assertEqual(self.eng.gaps.chasms(self.clock.t), [])       # the seam is not drawn as a liquidity gap
        self.assertEqual(feed.calls, [])                               # a replay never trades

    def test_replay_lap_in_the_lobby_resets_the_price_memory(self):
        self.make(mode="replay")
        feed = self._lap_feed()
        self.tick(3926.00, n=5)
        self._new_lap(feed)
        seq0 = self.eng.seq
        self.tick(3924.90)
        self.tick(3924.95, n=3)
        evs, _ = self.eng.events_since(seq0)
        self.assertFalse(any(e.get("type") in ("lightning", "stake") for e in evs))
        self.assertEqual(self.eng.gaps.chasms(self.clock.t), [])
        self.assertLess(abs(self.snap()["market"]["tilt_raw"]), 0.5)  # the 1.1 jump is not a slope
        self.assertEqual(self.eng.phase, "lobby")

    def test_replay_seam_in_one_step_ignores_the_old_laps_last_quote(self):
        self.make(mode="replay")
        feed = self._lap_feed()
        self.tick(3926.00, n=5)
        seq0 = self.eng.seq
        feed.push(3926.05, dt=0.05)                                    # the old lap's last quote, not yet seen by the engine ...
        self._new_lap(feed)
        feed.push(3925.10, dt=0.4)                                     # ... and the new lap's first, 0.95 away: all in one step
        self.eng.step()
        self.tick(3925.12, n=3)
        evs, _ = self.eng.events_since(seq0)
        self.assertFalse(any(e.get("type") == "lightning" for e in evs))
        self.assertEqual(self.eng.gaps.chasms(self.clock.t), [])
        self.assertLess(abs(self.snap()["market"]["tilt_raw"]), 0.5)

    def test_make_feed_replay_loops(self):
        try:
            import feeds  # noqa: F401
        except Exception as e:  # noqa: BLE001
            self.skipTest(f"feeds.py not importable: {e}")
        path = os.path.join(self.tmp, "tiny.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": T0, "dir": "in", "frame": {"type": "EVENT", "action": "fx/market",
                                                                 "body": {"symId": 1019, "a": 3926.71, "b": 3926.38, "st": "OPEN"}}}) + "\n")
        feed = E.make_feed("replay", file=path)
        self.assertTrue(feed.loop)
        self.assertFalse(feed.can_trade)
        self.assertIn("replay_lap", feed.state())


# ======================================================================================================================== money safety (review 2026-11-03)
class TestMoneySafety(EngineCase):
    """The money-safety review: an uncertain order never becomes a refusal (no second position), nothing that is not the game's is
    ever adopted, a live round is settled only from the deal history, the broker must hold the stop and the target, a stop is never
    born crossed, the kill switch never gives up, and a dead feed is a freeze (not a closed market)."""

    def _hide(self, ids):
        real = self.feed.state

        def state():
            s = real()
            s["positions"] = [p for p in s["positions"] if p["id"] not in ids]
            return s
        self.feed.state = state
        return real

    def _lose_first_answer(self, mode, hidden):
        """The first place() fills at the broker, but its answer says 'accepted, no id' (mode accepted) or is lost (mode timeout),
        and the page's frames about it are late (the position is hidden from the book)."""
        feed = self.feed
        real_place = feed.place
        feed.adopted = []
        feed.adopt = lambda pid: feed.adopted.append(pid) or True
        first = {"done": False}

        def place(side, qty, sl, tp, timeout=5.0):
            res = real_place(side, qty, sl, tp, timeout)
            if first["done"]:
                return res
            first["done"] = True
            hidden.add(res["position_id"])
            if mode == "accepted":
                return {"ok": True, "error": None, "rtt_ms": 90.0, "order_id": res["order_id"], "position_id": None,
                        "fill_price": None, "resolve_token": {"t": 0}}
            return {"ok": False, "error": "TIMEOUT", "rtt_ms": 5000.0, "order_id": None, "position_id": None, "fill_price": None}
        feed.place = place
        feed.resolve = lambda token, timeout=2.0: {"ok": False, "position_id": None, "fill_price": None}

    def _aim(self):
        self.assertTrue(self.act("fund", kind="live", side=1, target=1.2)["accepted"])
        self.tick(3926.0)

    def places(self):
        return [c for c in self.feed.calls if c[0] == "place"]

    # ---- uncertain orders
    def test_accepted_order_without_an_id_is_found_by_its_order_id(self):
        self.make(mode="live")
        self.graduate()
        hidden = set()
        self._hide(hidden)
        self._lose_first_answer("accepted", hidden)
        self._aim()
        self.assertTrue(self.act("shoot")["accepted"])
        self.assertEqual(self.eng.phase, "open")                  # the deal history has our order id -> its position
        self.assertEqual(self.eng.round.position_id, min(self.feed.pos))
        self.assertEqual(len(self.places()), 1)

    def test_a_lost_answer_never_lets_a_second_order_out(self):
        self.make(mode="live")
        self.graduate()
        hidden = set()
        self._hide(hidden)
        self._lose_first_answer("timeout", hidden)
        self._aim()
        self.assertTrue(self.act("shoot")["accepted"])
        self.assertEqual(self.eng.phase, "sending")                # frozen mid-throw: it may have filled
        self.assertEqual(self.snap()["round"]["pending"]["action"], "resolve")
        self.tick(3926.0, n=10)                                    # past the 3 s cooldown
        self.assertEqual(self.act("shoot")["why"], "phase")        # never a second order while the first is unknown
        self.assertEqual(len(self.places()), 1)
        hidden.clear()                                             # the late book shows it with our exact stop and target
        self.assertTrue(self.until(lambda: self.eng.phase == "open", max_ticks=30))
        self.assertEqual(self.feed.adopted, [self.eng.round.position_id])
        self.act("kill")
        self.assertTrue(self.until(lambda: self.eng.phase == "settled", max_ticks=20))
        self.assertEqual(self.feed.pos, {})                        # nothing of the game's is left open

    def test_an_uncertain_order_returns_the_note_only_when_the_deal_history_proves_no_fill(self):
        self.make(mode="live")
        self.graduate()
        feed = self.feed

        def place(side, qty, sl, tp, timeout=5.0):
            feed.calls.append(("place", side, qty, sl, tp))
            return {"ok": False, "error": "SEND_UNCERTAIN", "rtt_ms": 5000.0}      # it never reached the server
        feed.place = place
        self._aim()
        t_shot = self.clock.t
        self.act("shoot")
        self.tick(3926.0, n=20, dt=0.5)
        self.assertEqual(self.eng.phase, "sending")                # 10 s: not yet proof
        self.assertTrue(self.until(lambda: self.eng.phase == "aiming", max_ticks=40))
        self.assertGreaterEqual(self.clock.t - t_shot, float(self.eng.cfg["unknown_proof_s"]))
        self.assertEqual(len(self.places()), 1)

    def test_a_definite_refusal_never_adopts_a_new_position(self):
        self.make(mode="live")
        self.graduate()
        feed = self.feed
        feed.adopted = []
        feed.adopt = lambda pid: feed.adopted.append(pid) or True

        def place(side, qty, sl, tp, timeout=5.0):
            feed.calls.append(("place", side, qty, sl, tp))
            feed.add_outside_position(999, side=1, qty=0.01, price=3926.10)    # Zee's hand trade in the same instant
            return {"ok": False, "error": "INSUFFICIENT_FUNDS: Not enough margin", "rtt_ms": 80.0}
        feed.place = place
        self._aim()
        self.act("shoot")
        self.tick(3926.0, n=5)
        self.assertEqual(self.eng.phase, "aiming")
        self.assertIsNone(self.eng.round)
        self.assertEqual(feed.adopted, [])
        self.act("kill")
        self.tick(3926.0, n=3)
        self.assertIn(999, feed.pos)
        self.assertFalse(any(c[0] == "close" for c in feed.calls))

    def test_a_hand_trade_without_our_stop_is_never_adopted(self):
        self.make(mode="live")
        self.graduate()
        feed = self.feed
        feed.adopted = []
        feed.adopt = lambda pid: feed.adopted.append(pid) or True

        def place(side, qty, sl, tp, timeout=5.0):
            feed.calls.append(("place", side, qty, sl, tp))
            feed.add_outside_position(999, side=1, qty=0.01, price=3926.10)    # no stop, no target
            return {"ok": False, "error": "TIMEOUT", "rtt_ms": 5000.0}           # ours never executed
        feed.place = place
        self._aim()
        self.act("shoot")
        self.tick(3926.0, n=60, dt=0.5)                            # 30 s: it cannot be told apart from an unlinked order of ours
        self.assertEqual(self.eng.phase, "sending")
        self.assertEqual(feed.adopted, [])
        self.assertIsNone(self.eng.round.position_id)
        feed.outside_close(999)                                    # Zee closes it: no open position could be ours any more
        self.assertTrue(self.until(lambda: self.eng.phase == "aiming", max_ticks=40))
        self.assertFalse(any(c[0] == "close" for c in feed.calls))

    # ---- the entry stop is never born crossed
    def test_a_spread_as_wide_as_the_stop_ducks_and_sends_nothing(self):
        self.make(mode="live")
        self.graduate()
        self.feed.spread = 1.20
        self._aim()
        self.assertTrue(self.act("shoot")["accepted"])
        self.assertEqual(self.eng.phase, "aiming")
        self.assertEqual(self.places(), [])
        self.feed.spread = 0.33
        self.tick(3926.0, n=9)
        self.assertTrue(self.act("shoot")["accepted"])
        self.assertEqual(self.eng.phase, "open")
        place = self.places()[-1]
        self.assertLess(place[3], self.feed.quote["bid"])          # a long's stop below the bid
        self.assertGreater(place[4], self.feed.quote["ask"])       # its target above the ask

    # ---- the kill switch
    def test_kill_before_the_order_leaves_sends_nothing(self):
        self.make(mode="live")
        self.graduate()
        self._aim()
        self.assertTrue(self.eng.act({"action": "shoot", "nonce": "k1", "sent_at": self.clock.t, "args": {}})["accepted"])
        self.assertTrue(self.eng.act({"action": "kill", "nonce": "k2", "sent_at": self.clock.t, "args": {}})["accepted"])
        self.eng.pump()
        self.eng.step()
        self.eng.pump()
        self.assertEqual([c for c in self.feed.calls if c[0] in ("place", "close")], [])
        self.assertEqual(self.eng.phase, "lobby")

    def test_kill_retries_until_the_position_is_closed(self):
        self.make(mode="live")
        self.graduate()
        rd = self.open_round()
        feed = self.feed
        real_close = feed.close
        fails = {"n": 0}

        def close(pid, qty=None, timeout=5.0):
            if fails["n"] < 2:
                fails["n"] += 1
                feed.calls.append(("close-refused", pid, qty))
                return {"ok": False, "error": "SOCKET_LOST", "rtt_ms": 0.0}
            return real_close(pid, qty, timeout)
        feed.close = close
        self.assertTrue(self.act("kill")["accepted"])
        self.assertEqual(self.act("wall")["why"], "killed")       # nothing else trades after the kill
        self.assertEqual(self.act("eject")["why"], "killed")
        self.assertTrue(self.until(lambda: self.eng.phase == "settled", max_ticks=40))
        self.assertEqual(self.snap()["settlement"]["outcome"], "kill")
        self.assertNotIn(rd.position_id, feed.pos)
        self.assertEqual([c[0] for c in feed.calls if c[0].startswith("close")], ["close-refused", "close-refused", "close"])

    def test_kill_during_a_false_alarm_still_closes(self):
        self.make(mode="live")
        self.graduate()
        rd = self.open_round()
        self.tick(3926.0, n=3)
        hide = {rd.position_id}
        self._hide(hide)
        self.tick(3926.0, n=2)                                     # the book drops our row for a moment -> settling
        self.assertTrue(rd.settling)
        self.assertTrue(self.act("kill")["accepted"])
        hide.clear()
        self.assertTrue(self.until(lambda: self.eng.phase == "settled", max_ticks=40))
        self.assertEqual(self.snap()["settlement"]["outcome"], "kill")
        self.assertNotIn(rd.position_id, self.feed.pos)

    def test_a_restarted_game_keeps_closing_after_the_kill(self):
        self.make(mode="live")
        self.graduate()
        rd = self.open_round()
        self.feed.refuse["close"] = "SOCKET_LOST"
        self.act("kill")
        self.assertIn(rd.position_id, self.feed.pos)
        eng2 = E.Engine(self.feed, cfg={"shadow_broker": "engine", "paper_slippage_max": 0.0}, root=self.tmp, clock=self.clock,
                        threaded=False, verbose=False, cfg_path=os.path.join(self.tmp, "no_config.json"))
        self.eng = eng2
        self.assertTrue(self.until(lambda: eng2.phase == "settled", max_ticks=40))
        self.assertEqual(eng2.snapshot()["settlement"]["outcome"], "kill")
        self.assertNotIn(rd.position_id, self.feed.pos)

    def test_kill_also_closes_the_games_orphans_and_nothing_else(self):
        self.make(mode="live")
        self.feed.add_outside_position(999)                        # Zee's
        self.feed.add_outside_position(777, side=-1)               # an orphan the game opened in an earlier session
        self.feed.owned = lambda: {777, 15394000}                  # LiveFeed.owned(): only ids the game opened
        self.assertTrue(self.act("kill")["accepted"])
        self.tick(3926.0, n=3)
        self.assertEqual([c for c in self.feed.calls if c[0] == "close"], [("close", 777, 0.01)])
        self.assertIn(999, self.feed.pos)

    # ---- settlement only from the deal history
    def test_a_failed_report_never_settles_from_an_estimate(self):
        self.make(mode="live")
        self.graduate()
        rd = self.open_round()
        real_report = self.feed.orders_report

        class Failed(list):
            ok = False
        self.feed.orders_report = lambda since_ts, timeout=5.0: Failed()
        self.tick(3926.0, n=2)
        self.tick(3924.50)                                         # a gap through the 3925.33 stop: filled at 3924.50
        self.tick(3924.50, n=40)                                   # 16 s of an unreadable report
        self.assertEqual(self.eng.phase, "closing")
        self.assertIsNone(self.snap()["settlement"])
        self.assertEqual(self.snap()["limits"]["loss_today_coins"], 0.0)
        self.feed.orders_report = real_report                      # the deal history is back
        self.assertTrue(self.until(lambda: self.eng.phase == "settled", max_ticks=30))
        st = self.snap()["settlement"]
        self.assertEqual((st["outcome"], st["exit"]), ("barrel", 3924.5))
        self.assertAlmostEqual(st["result_usd"], round((3924.50 - rd.fill) * 0.01, 6), places=6)
        self.assertFalse(st.get("estimated"))

    def test_settlement_survives_a_broker_clock_behind_ours(self):
        self.make(mode="live")
        self.graduate()
        real_report = self.feed.orders_report
        # PX filters fromExecutedAt on its own clock: here it runs 30 s behind this PC
        self.feed.orders_report = lambda since_ts, timeout=5.0: [dict(x, executed_ts=x["executed_ts"] - 30.0) for x in real_report(0)
                                                                  if x["executed_ts"] - 30.0 >= since_ts]
        rd = self.open_round()
        self.tick(3927.60)                                          # the target fills at once
        self.assertTrue(self.until(lambda: self.eng.phase == "settled", max_ticks=20))
        self.assertEqual(self.snap()["settlement"]["outcome"], "buyer")
        self.assertNotIn(rd.position_id, self.feed.pos)

    def test_a_position_missing_from_the_book_is_never_declared_closed(self):
        self.make(mode="live")
        self.graduate()
        rd = self.open_round()
        self.tick(3926.0, n=5)                                     # seen in the book
        hide = {rd.position_id}
        self._hide(hide)
        self.tick(3926.0, n=40)                                    # 16 s: not in the book, no close in the report
        self.assertEqual(self.eng.phase, "closing")
        self.assertIsNone(self.snap()["settlement"])
        self.assertEqual(self.act("ack")["why"], "phase")
        self.assertEqual(self.act("fund", kind="live")["why"], "phase")
        hide.clear()                                               # the book lists it again: the round is open again
        self.assertTrue(self.until(lambda: self.eng.phase == "open", max_ticks=15))
        self.assertEqual(len(self.places()), 1)

    def test_eject_still_closes_while_a_settlement_is_pending(self):
        self.make(mode="live")
        self.graduate()
        rd = self.open_round()
        self.tick(3926.0, n=5)
        self._hide({rd.position_id})
        self.tick(3926.0, n=40)
        self.assertEqual(self.eng.phase, "closing")
        self.assertTrue(self.act("eject")["accepted"])             # the stale book may be hiding an open position
        self.assertTrue(self.until(lambda: self.eng.phase == "settled", max_ticks=15))
        self.assertEqual(self.snap()["settlement"]["outcome"], "eject")
        self.assertNotIn(rd.position_id, self.feed.pos)

    def _never_closes(self, flag):
        self.make(mode="live")
        self.graduate()
        rd = self.open_round()
        real = self.feed.state

        def state():
            s = real()
            s["positions"] = []
            s[flag] = False
            return s
        self.feed.state = state
        self.tick(3926.0, n=20)
        self.assertEqual(self.eng.phase, "open", flag)
        self.assertFalse(rd.settling, flag)

    def test_a_stale_book_never_closes_a_round(self):
        self._never_closes("book_fresh")              # LiveFeed after a page reload, until the book is read again

    def test_another_account_in_the_page_never_closes_a_round(self):
        self._never_closes("account_ok")              # LiveFeed when the page switched to another account

    def test_a_partial_report_waits_for_the_whole_close(self):
        self.make(mode="live")
        self.assertTrue(self.eng.update_settings({"coin_oz": 0.02})["ok"])
        self.graduate(machete=True)
        rd = self.open_round()
        self.tick(3926.40, n=3)
        self.assertTrue(self.act("machete")["accepted"])
        real_report = self.feed.orders_report
        self.feed.orders_report = lambda since_ts, timeout=5.0: [x for x in real_report(since_ts) if x["type"] != "STOP_LOSS"]
        self.tick(3925.20)                                         # the stop fills; its row is late in the report
        self.tick(3925.20, n=40)
        self.assertEqual(self.eng.phase, "closing")
        self.assertEqual(self.snap()["limits"]["loss_today_coins"], 0.0)
        self.feed.orders_report = real_report
        self.assertTrue(self.until(lambda: self.eng.phase == "settled", max_ticks=15))
        truth = sum(x["rpl"] for x in real_report(0) if x["positionId"] == rd.position_id)
        self.assertAlmostEqual(self.snap()["settlement"]["result_usd"], round(truth, 6), places=6)

    # ---- the broker must hold the stop and the target
    def _unlinked_place(self):
        real_place = self.feed.place

        def place(side, qty, sl, tp, timeout=5.0):
            res = real_place(side, qty, sl, tp, timeout)
            p = self.feed.pos[res["position_id"]]
            p["sl"] = p["tp"] = None                               # filled, but the protective orders were not linked
            return dict(res, sl=sl, tp=tp)                         # (LiveFeed echoes the requested prices)
        self.feed.place = place

    def test_a_stop_and_target_the_broker_does_not_hold_are_set_again(self):
        self.make(mode="live")
        self.graduate()
        self._unlinked_place()
        self.feed.refuse["set_protective"] = "SOCKET_LOST"         # the first try fails
        rd = self.open_round()
        self.tick(3926.0, n=12)                                    # missing for longer than protect_grace_s; the first try failed
        self.assertEqual(len([c for c in self.feed.calls if c[0] == "set_protective"]), 1)
        s = self.snap()["round"]
        self.assertTrue(s["anvil"]["missing"])                     # never drawn as if the broker held it
        self.assertEqual((s["protected"], s["tag_text"]), ({"sl": False, "tp": False}, ""))
        self.tick(3926.0, n=12)
        p = self.feed.pos[rd.position_id]
        self.assertEqual((p["sl"], p["tp"]), (rd.sl, rd.tp))
        s = self.snap()["round"]
        self.assertFalse(s["anvil"]["missing"])
        self.assertTrue(s["protected"]["tp"])
        self.assertNotEqual(s["tag_text"], "")
        self.assertEqual(self.eng.phase, "open")

    def test_a_stop_missing_for_a_moment_is_never_touched(self):
        self.make(mode="live")
        self.graduate()
        rd = self.open_round()
        self.tick(3926.0, n=8)                                     # well past the grace after the fill
        p = self.feed.pos[rd.position_id]
        saved = p["sl"]
        p["sl"] = None                                             # one moment without it (PX replacing a stop moved by hand)
        self.tick(3926.0, n=2)
        p["sl"] = saved
        self.tick(3926.0, n=12)
        self.assertEqual([c for c in self.feed.calls if c[0] in ("set_protective", "close")], [])
        self.assertEqual(self.eng.phase, "open")
        self.assertFalse(self.snap()["round"]["anvil"]["missing"])

    def test_protect_rereads_the_book_and_sends_nothing_the_broker_already_holds(self):
        self.make(mode="live")
        self.graduate()
        rd = self.open_round()
        self.tick(3926.0, n=8)
        self.eng._job_protect(rd, True, True)                      # queued on a stale view; the book holds both now
        self.assertEqual([c for c in self.feed.calls if c[0] in ("set_protective", "close")], [])
        self.assertEqual(self.eng.phase, "open")

    def test_an_unprotected_position_is_closed_when_its_stop_cannot_be_set(self):
        self.make(mode="live")
        self.graduate()
        self._unlinked_place()
        self.feed.set_protective = lambda pid, kind, price, timeout=5.0: {"ok": False, "error": "REJECTED", "rtt_ms": 1.0}
        rd = self.open_round()
        self.assertTrue(self.until(lambda: self.eng.phase == "settled", max_ticks=40))
        st = self.snap()["settlement"]
        self.assertEqual(st["outcome"], "session")
        self.assertIn("held no stop or target", st["plain"])
        self.assertNotIn(rd.position_id, self.feed.pos)

    # ---- freeze vs closed market, discipline numbers
    def test_a_dead_feed_is_a_freeze_not_a_closed_market(self):
        self.make()
        real = self.feed.state

        def dead():
            s = real()
            s.update(ok=False, reason="quotes stale", market_open=False)       # Feed._market_open = ok and ...
            return s
        self.feed.state = dead
        self.clock.t += 20
        self.eng.step()
        s = self.snap()
        self.assertTrue(s["freeze"])
        self.assertEqual(s["market"]["shutters"]["reason"], "no_feed")
        self.assertNotEqual(s["market"]["session"], "closed")

        def closed():
            s = real()
            s.update(ok=False, reason="market_closed", market_open=False)
            return s
        self.feed.state = closed
        self.eng.step()
        s = self.snap()
        self.assertFalse(s["freeze"])
        self.assertEqual(s["market"]["shutters"]["reason"], "market_closed")
        self.assertEqual(s["market"]["session"], "closed")

    def test_profitable_stops_do_not_jam_the_door(self):
        self.make()

        def add(i, res):
            self.eng.summaries.append({"id": f"j{i}", "mode": "sim", "kind": "live", "outcome": "anvil", "result_usd": res,
                                       "risk_usd": 0.01, "closed_t": self.clock.t - 300 + i, "opened_t": self.clock.t - 400})
            self.eng._sum_version += 1
            self.eng._lim_cache = (None, None)
        for i in range(3):
            add(i, 0.004)                                          # trailed stops that closed in profit
        self.assertIsNone(self.snap()["limits"]["jam_until"])
        for i in range(3, 6):
            add(i, -0.01)                                          # three real stops still jam it
        self.assertIsNotNone(self.snap()["limits"]["jam_until"])

    def test_live_loss_cap_is_the_smaller_of_ten_coins_and_5pct_of_the_balance(self):
        self.make(mode="live", balance=0.61)
        self.assertEqual(self.snap()["limits"]["loss_max_coins"], 3.05)

    def test_plain_words_are_off_by_default(self):
        self.make()
        self.assertFalse(self.snap()["settings"]["plain_line"])


if __name__ == "__main__":
    unittest.main()
