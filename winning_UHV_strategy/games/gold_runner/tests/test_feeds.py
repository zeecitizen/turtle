"""tests/test_feeds.py - offline tests for feeds.py.

Run from games/gold_runner:   python -m unittest discover -s tests      or      python tests/test_feeds.py
Nothing here touches Chrome :9222. GG_FORBID_LIVE is set before feeds is imported (LiveFeed.start() refuses without a fake
session); LiveFeed is exercised through _on_frame with frames copied from PROTOCOL.md, a fake sender, and a fake CDP session
that plays a tiny PXTrader page backed by a ShadowBroker.
"""
import os
import sys

os.environ["GG_FORBID_LIVE"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import json        # noqa: E402
import re          # noqa: E402
import shutil      # noqa: E402
import tempfile    # noqa: E402
import threading   # noqa: E402
import time        # noqa: E402
import unittest    # noqa: E402

import feeds       # noqa: E402

CFG = {"feed_dead_s": 15, "feed_stale_s": 2.0, "dead_hours_utc": [["20:45", "23:00"]]}
T_DAY = 1793677800.0          # 2026-11-03 03:50 UTC (not a dead hour)
T_NIGHT = 1793653200.0        # 2026-11-02 21:00 UTC (inside the 20:45-23:00 dead hours)


# ---- frames copied from PROTOCOL.md / the P0 round trip ------------------------------------------------------------------------
def fx(bid, ask, st="OPEN", sym=1019):
    return {"type": "EVENT", "action": "fx/market", "sid": 3, "aid": 1,
            "body": {"symId": sym, "a": ask, "b": bid, "lp": round((ask + bid) / 2, 2), "s": round(ask - bid, 2), "h24": 3970.2,
                     "l24": 3891.13, "v24": 1234.5, "ch": -3.2, "chPct": -0.08, "pr": 0.01, "st": st}}


def act(title, body, level="SUCCESS"):
    return {"type": "EVENT", "action": "trading/activity", "body": {"level": level, "title": title, "body": body}}


def sub_position(pid, side, qty, open_price, mark, sl=None, tp=None, sl_id=None, tp_id=None, upl=0.0):
    return {"id": pid, "accountId": "L1869984", "side": side, "marginType": "CROSS", "symbol": "XAU/USD", "qty": qty,
            "openPrice": open_price, "currentPrice": mark, "markPrice": mark, "upl": upl, "stopLossOrderId": sl_id,
            "stopLossPrice": sl, "takeProfitOrderId": tp_id, "takeProfitPrice": tp, "closeable": True,
            "openTime": "2026-11-03T02:33:04.761Z", "subPositions": None, "positionMode": "HEDGE"}


def positions_frame(subs):
    data = []
    for side in ("BUY", "SELL"):
        mine = [s for s in subs if s["side"] == side]
        if mine:
            data.append({"id": 0, "accountId": "L1869984", "side": side, "symbol": "XAU/USD", "qty": round(sum(s["qty"] for s in mine), 2),
                         "openPrice": mine[0]["openPrice"], "markPrice": mine[0]["markPrice"], "upl": 0.0,
                         "stopLossOrderId": None, "stopLossPrice": None, "takeProfitOrderId": None, "takeProfitPrice": None,
                         "subPositions": mine, "positionMode": "HEDGE"})
    return {"type": "EVENT", "action": "positions", "body": {"data": data, "positionMode": "HEDGE"}}


P0_SHORT = sub_position(15391910, "SELL", 0.01, 3945.23, 3925.37, upl=0.2)
METRICS = {"type": "EVENT", "action": "metrics", "body": {"accountId": "L1869984", "balance": 0.63, "equity": 0.61, "upl": -0.02,
                                                           "usedMargin": 0.04, "availableMargin": 0.57, "openPositions": 1,
                                                           "openOrders": 2, "demo": False, "positionMode": "HEDGE"}}
ACCOUNTS = {"type": "EVENT", "action": "pfx/accounts2",
            "body": {"data": [{"accountId": "L1869984", "type": "LIVE", "balance": 0.63, "equity": 0.61, "upl": -0.02,
                               "specName": "PXTrader 2.0"}]}}
ORDERS = {"type": "EVENT", "action": "orders/active2",
          "body": {"data": [{"id": 2188572786, "type": "STOP_LOSS", "status": "AWAITING", "side": "SELL", "qty": 0.01,
                             "triggerPrice": 3923.71, "positionId": 15394511, "protective": True}]}}
UPCOMING = [{"eventId": 1, "eventTime": 1793712600, "eventTitle": "US CPI m/m", "importance": "HIGH", "regionCode": "US",
             "currency": "USD", "forecast": "0.3%", "previous": "0.2%", "actual": None},
            {"eventId": 2, "eventTime": 1793716200, "eventTitle": "Turkish CPI", "importance": "HIGH", "regionCode": "TR",
             "currency": "TRY", "forecast": None, "previous": None, "actual": None}]
CAL = {"data": [{"title": "US CPI m/m", "country": "US", "importance": 3, "date": "2026-11-03T13:30:00Z"},
                {"title": "Japan Household Spending", "country": "JP", "importance": 1, "date": "2026-11-03T23:30:00Z"},
                {"title": "German ZEW", "country": "DE", "importance": "MEDIUM", "date": "2026-11-03T10:00:00Z"}]}


def gen_rows(n, t_end, start=3920.0):
    """n closed 1-minute bid bars ending at t_end (exclusive), deterministic"""
    rows, p = [], start
    for i in range(n):
        t = int(t_end) - (n - i) * 60
        o = p
        p = round(p + ((i * 37) % 11 - 5) * 0.07, 2)
        rows.append([t, o, round(max(o, p) + 0.2, 2), round(min(o, p) - 0.2, 2), p, 100 + i])
    return rows


def wait_for(cond, timeout=3.0, step=0.02):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(step)
    return cond()


# =================================================================================================================================
class TestHelpers(unittest.TestCase):
    def test_qty_and_rounding(self):
        self.assertTrue(feeds.qty_ok(0.01))
        self.assertTrue(feeds.qty_ok(0.03))
        self.assertFalse(feeds.qty_ok(0.015))
        self.assertFalse(feeds.qty_ok(0.0))
        self.assertFalse(feeds.qty_ok("x"))
        self.assertEqual(feeds.r2(3925.7049999), 3925.7)

    def test_to_unix(self):
        self.assertAlmostEqual(feeds.to_unix("2026-11-03T02:33:04.761Z"), 1793673184.761, places=3)
        self.assertEqual(feeds.to_unix(1793673184761), 1793673184.761)
        self.assertEqual(feeds.to_unix(1793673184), 1793673184.0)
        self.assertIsNone(feeds.to_unix(None))

    def test_dead_hours_and_st(self):
        self.assertTrue(feeds.in_dead_hours(T_NIGHT, CFG["dead_hours_utc"]))
        self.assertFalse(feeds.in_dead_hours(T_DAY, CFG["dead_hours_utc"]))
        self.assertTrue(feeds.in_dead_hours(T_DAY, [["23:00", "05:00"]]))      # wraps midnight
        self.assertTrue(feeds.st_closed("CLOSED"))
        self.assertTrue(feeds.st_closed("halted"))
        self.assertFalse(feeds.st_closed("OPEN"))
        self.assertFalse(feeds.st_closed(1))

    def test_scrub_removes_urls_jwts_and_tokens(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTYifQ.c2lnbmF0dXJlLXZhbHVl"
        f = {"type": "EVENT", "body": {"u": "wss://api.primexbt.com/v2/fws/?accountId=l1&token=" + jwt, "accessToken": "abc",
                                       "note": "bearer " + jwt, "n": 1, "list": ["ws://x/y", "ok"]}}
        s = json.dumps(feeds.scrub(f))
        self.assertNotIn("wss://", s)
        self.assertNotIn("ws://", s)
        self.assertNotIn(jwt, s)
        self.assertNotIn("abc", s)
        self.assertIn('"n": 1', s)

    def test_activity_text_parsers(self):
        self.assertEqual(feeds.parse_fill_text("Buy 0.01 XAU/USD @ 3926.59"),
                         {"side": "buy", "qty": 0.01, "symbol": "XAU/USD", "price": 3926.59})
        self.assertEqual(feeds.parse_fill_text("Sell 0.01 XAU/USD @ 3,928.98")["price"], 3928.98)
        lk = feeds.parse_link_text("15394511: Stop loss #2188572786 sell XAU/USD @ 3923.71")
        self.assertEqual(lk, {"position_id": 15394511, "kind": "STOP_LOSS", "order_id": 2188572786, "side": "sell",
                              "symbol": "XAU/USD", "price": 3923.71})
        self.assertIsNone(feeds.parse_fill_text("15394511: Stop loss #2188572786 sell XAU/USD @ 3923.71"))

    def test_calendar_normaliser(self):
        n = feeds.normalise_calendar(CAL)
        self.assertEqual([e["title"] for e in n], ["German ZEW", "US CPI m/m", "Japan Household Spending"])
        self.assertEqual([e["impact"] for e in n], ["medium", "high", "low"])
        self.assertEqual(n[1]["t"], feeds.to_unix("2026-11-03T13:30:00Z"))
        self.assertEqual(n[1]["country"], "US")
        other = {"result": {"events": [{"name": "FOMC", "currency": "USD", "volatility": "HIGH", "timestamp": 1793727000000},
                                       {"name": "x", "volatility": "Low", "dateTime": "2026-11-04 09:00:00"}]}}
        n2 = feeds.normalise_calendar(other)
        self.assertEqual(n2[0], {"t": 1793727000.0, "title": "FOMC", "impact": "high", "country": "USD"})
        self.assertEqual(n2[1]["impact"], "low")
        grouped = [{"date": "2026-11-05", "items": [{"event": "NFP", "date": "2026-11-05", "time": "13:30", "impact": "3"}]}]
        n3 = feeds.normalise_calendar(grouped)
        self.assertEqual(n3[0]["impact"], "high")
        self.assertEqual(n3[0]["t"], feeds.to_unix("2026-11-05T13:30:00Z"))
        self.assertIsNone(feeds.normalise_calendar({"status": "ok"}))


# =================================================================================================================================
class TestPXChannel(unittest.TestCase):
    def test_slot_registered_before_send_and_reply_matched(self):
        box = {}

        def sender(msg):
            box["pending_at_send"] = ch.pending()
            box["msg"] = msg
            ch.on_response({"type": "RESPONSE", "rid": msg["rid"], "action": msg["action"], "body": {"time": 1}})

        ch = feeds.PXChannel(sender)
        r = ch.request("time", {}, timeout=1.0)
        self.assertTrue(r["ok"])
        self.assertEqual(box["pending_at_send"], 1)
        self.assertGreaterEqual(box["msg"]["rid"], 900000)
        self.assertEqual(box["msg"]["type"], "REQUEST")
        self.assertEqual(r["body"], {"time": 1})
        self.assertEqual(ch.pending(), 0)

    def test_error_object_and_body_error(self):
        def sender(msg):
            if msg["action"] == "positions/id/close":
                ch.on_response({"type": "RESPONSE", "rid": msg["rid"], "action": msg["action"],
                                "error": {"code": "POSITION_NOT_FOUND", "description": "120: Not found position #1"}})
            else:
                ch.on_response({"type": "RESPONSE", "rid": msg["rid"], "action": msg["action"],
                                "body": {"id": None, "error": {"code": "INSUFFICIENT_FUNDS", "description": "no money"}}})

        ch = feeds.PXChannel(sender)
        r = ch.request("positions/id/close", {"positionId": 1, "qty": 0.01})
        self.assertFalse(r["ok"])
        self.assertTrue(r["definite"])
        self.assertEqual(r["error"], "POSITION_NOT_FOUND: 120: Not found position #1")
        r = ch.request("orders/market/place", {})
        self.assertEqual(r["error"], "INSUFFICIENT_FUNDS: no money")

    def test_timeout_send_not_open_and_fail_all(self):
        ch = feeds.PXChannel(lambda msg: None)
        t = time.perf_counter()
        r = ch.request("time", {}, timeout=0.15)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "TIMEOUT")
        self.assertFalse(r["definite"])
        self.assertLess(time.perf_counter() - t, 1.0)
        self.assertEqual(ch.pending(), 0)

        def closed(msg):
            raise feeds.SendNotOpen("closed")
        r = feeds.PXChannel(closed).request("time", {}, timeout=5)
        self.assertEqual((r["ok"], r["error"], r["definite"]), (False, "SOCKET_LOST", True))

        ch2 = feeds.PXChannel(lambda msg: None)
        c = ch2.begin("time", {})
        ch2.fail_all("SOCKET_CLOSED")
        r = ch2.result(c, 1.0)
        self.assertFalse(r["ok"])
        self.assertFalse(r["definite"])
        self.assertTrue(r["error"].startswith("SOCKET_CLOSED"))

    def test_concurrent_out_of_order_replies(self):
        sent = []
        lock = threading.Lock()

        def sender(msg):
            with lock:
                sent.append(msg)

        ch = feeds.PXChannel(sender)
        results = {}

        def worker(i):
            results[i] = ch.request("time", {"i": i}, timeout=3.0)

        th = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for x in th:
            x.start()
        self.assertTrue(wait_for(lambda: len(sent) == 8))
        for msg in reversed(sent):
            ch.on_response({"type": "RESPONSE", "rid": msg["rid"], "action": "time", "body": {"echo": msg["body"]["i"]}})
        for x in th:
            x.join(3)
        self.assertEqual(sorted(results), list(range(8)))
        for i, r in results.items():
            self.assertEqual(r["body"]["echo"], i)
        self.assertEqual(len({m["rid"] for m in sent}), 8)


# =================================================================================================================================
class TestPXParser(unittest.TestCase):
    def setUp(self):
        self.f = feeds.PXFeedBase(config=CFG)
        self.events = []
        self.f.subscribe(self.events.append)

    def test_quote(self):
        f = self.f
        f._on_frame(json.dumps(fx(3926.38, 3926.71)), "in")
        s = f.state()
        self.assertEqual(s["quote"]["bid"], 3926.38)
        self.assertEqual(s["quote"]["ask"], 3926.71)
        self.assertEqual(s["quote"]["spread"], 0.33)
        self.assertEqual(s["quote"]["mid"], 3926.545)
        self.assertEqual(s["quote"]["st"], "OPEN")
        self.assertEqual((s["h24"], s["l24"], s["ch24"]), (3970.2, 3891.13, -3.2))
        self.assertTrue(s["ok"])
        self.assertTrue(s["market_open"])
        self.assertEqual(s["tick_count"], 1)
        f._on_frame(fx(3926.38, 3926.71), "in")                  # same price: no new tick, fresher ts
        f._on_frame(fx(3999.0, 3999.5, sym=1020), "in")          # another symbol: ignored
        f._on_frame('{"type":"EVENT","action":"fx/market","body":{"symId":1019,"a":"x","b":null}}', "in")
        f._on_frame("not json", "in")
        s = f.state()
        self.assertEqual(s["tick_count"], 1)
        self.assertEqual(s["quote"]["bid"], 3926.38)
        f._on_frame(fx(3926.40, 3926.73), "in")
        self.assertEqual(f.state()["tick_count"], 2)
        self.assertEqual(len(f.state()["ticks"]), 2)
        q = [e for e in self.events if e["type"] == "quote"]
        self.assertEqual([e["changed"] for e in q], [True, False, True])
        f._on_frame(fx(3926.40, 3926.73, st="CLOSED"), "in")
        self.assertFalse(f.state()["market_open"])

    def test_bars_history_subscription_and_events(self):
        f = self.f
        t_now = 1793677800
        rows = gen_rows(329, t_now)
        f._on_frame({"type": "REQUEST", "rid": 900001, "action": "bars",
                     "body": {"symbol": "XAU/USD", "bar_size": "1M", "to": t_now, "limit": 329, "askOhlc": False}}, "out")
        f._on_frame({"type": "RESPONSE", "rid": 900001, "action": "bars", "body": {"data": rows}}, "in")
        bars = f.state()["bars"]
        self.assertEqual(len(bars), 329)
        self.assertEqual(bars[0][0], rows[0][0])
        # the page's own 15-minute chart subscription must be ignored
        f._on_frame({"type": "SUBSCRIPTION", "rid": 12, "action": "bar", "body": {"symbolId": 1019, "barSize": "15M", "askOhlc": False}}, "out")
        f._on_frame({"type": "RESPONSE", "rid": 12, "action": "bar", "sid": 5, "body": {"data": [t_now - 900, 1, 2, 0.5, 1.5, 9]}}, "in")
        # ours
        f._on_frame({"type": "SUBSCRIPTION", "rid": 900002, "action": "bar", "body": {"symbolId": 1019, "barSize": "1M", "askOhlc": False}}, "out")
        f._on_frame({"type": "RESPONSE", "rid": 900002, "action": "bar", "sid": 77,
                     "body": {"data": [t_now, 3921.0, 3921.2, 3920.9, 3921.1, 5]}}, "in")
        self.assertEqual(len(f.state()["bars"]), 330)
        f._on_frame({"type": "EVENT", "action": "bar", "sid": 77, "aid": 2, "body": {"data": [t_now, 3921.0, 3921.6, 3920.9, 3921.5, 9]}}, "in")
        f._on_frame({"type": "EVENT", "action": "bar", "sid": 5, "aid": 3, "body": {"data": [t_now - 900, 1, 9999, 0.1, 5, 1]}}, "in")
        bars = f.state()["bars"]
        self.assertEqual(len(bars), 330)
        self.assertEqual(bars[-1], [t_now, 3921.0, 3921.6, 3920.9, 3921.5, 9.0])
        self.assertNotIn(9999, [b[2] for b in bars])
        self.events.clear()
        f._on_frame({"type": "EVENT", "action": "bar", "sid": 77, "aid": 4, "body": {"data": [t_now + 60, 3921.5, 3921.5, 3921.4, 3921.4, 1]}}, "in")
        bars = f.state()["bars"]
        self.assertEqual(len(bars), 331)
        self.assertEqual(bars[-1][0], t_now + 60)
        be = [e for e in self.events if e["type"] == "bar"]
        self.assertEqual([(e["bar"][0], e["closed"]) for e in be], [(t_now, True), (t_now + 60, False)])
        # a late correction of the just-closed bar
        f._on_frame({"type": "EVENT", "action": "bar", "sid": 77, "aid": 5, "body": {"data": [t_now, 3921.0, 3921.7, 3920.9, 3921.45, 11]}}, "in")
        self.assertEqual(f.state()["bars"][-2], [t_now, 3921.0, 3921.7, 3920.9, 3921.45, 11.0])
        # a second history request merges without losing the live bars
        f._on_frame({"type": "REQUEST", "rid": 900005, "action": "bars", "body": {"symbol": "XAU/USD", "bar_size": "1M"}}, "out")
        f._on_frame({"type": "RESPONSE", "rid": 900005, "action": "bars", "body": {"data": gen_rows(329, t_now)}}, "in")
        bars = f.state()["bars"]
        self.assertEqual(bars[-1][0], t_now + 60)
        self.assertGreaterEqual(len(bars), 330)
        self.assertEqual([b[0] for b in bars], sorted({b[0] for b in bars}))

    def test_bar_fallback_from_quotes_when_subscription_silent(self):
        f = self.f
        t = 1793677810.0
        f._on_frame(fx(3926.38, 3926.71), "in", ts=t)
        f._on_frame(fx(3926.10, 3926.43), "in", ts=t + 1)
        f._on_frame(fx(3926.90, 3927.23), "in", ts=t + 2)
        f._on_frame(fx(3926.50, 3926.83), "in", ts=t + 61)
        bars = f.state()["bars"]
        self.assertEqual(bars[0][:5], [1793677800, 3926.38, 3926.9, 3926.1, 3926.9])
        self.assertEqual(bars[1][:5], [1793677860, 3926.5, 3926.5, 3926.5, 3926.5])

    def test_positions_subpositions_and_flat(self):
        f = self.f
        f._on_frame(positions_frame([P0_SHORT]), "in")
        p = f.state()["positions"]
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0], {"id": 15391910, "side": -1, "qty": 0.01, "open_price": 3945.23, "mark": 3925.37, "upl": 0.2,
                                "sl": None, "tp": None, "sl_order": None, "tp_order": None,
                                "open_time": feeds.to_unix("2026-11-03T02:33:04.761Z"), "symbol": "XAU/USD"})
        long_ = sub_position(15394511, "BUY", 0.01, 3926.59, 3926.38, sl=3925.59, tp=3927.79, sl_id=2188572786, tp_id=2188572787)
        f._on_frame(positions_frame([P0_SHORT, long_]), "in")
        ids = {x["id"]: x for x in f.state()["positions"]}
        self.assertEqual(set(ids), {15391910, 15394511})
        self.assertEqual((ids[15394511]["side"], ids[15394511]["sl"], ids[15394511]["tp_order"]), (1, 3925.59, 2188572787))
        f._on_frame({"type": "EVENT", "action": "positions", "body": {"data": [], "positionMode": "HEDGE"}}, "in")
        self.assertEqual(f.state()["positions"], [])
        oneway = dict(sub_position(42, "BUY", 0.02, 3900.0, 3901.0))
        f._on_frame({"type": "EVENT", "action": "positions", "body": {"data": [oneway]}}, "in")
        self.assertEqual(f.state()["positions"][0]["id"], 42)

    def test_account_orders_activity(self):
        f = self.f
        f._on_frame(ACCOUNTS, "in")
        self.assertEqual(f.state()["account"]["id"], "L1869984")
        f._on_frame(METRICS, "in")
        a = f.state()["account"]
        self.assertEqual(a, {"id": "L1869984", "type": "LIVE", "balance": 0.63, "equity": 0.61, "upl": -0.02, "available": 0.57,
                             "currency": "USD"})
        self.assertTrue(any(e["type"] == "account" and e["account"]["balance"] == 0.63 for e in self.events))
        f._on_frame(ORDERS, "in")
        o = f.state()["orders"]
        self.assertEqual(o, [{"id": 2188572786, "type": "STOP_LOSS", "status": "AWAITING", "side": -1, "qty": 0.01, "trigger": 3923.71,
                              "position_id": 15394511, "protective": True, "symbol": None}])
        f._on_frame({"type": "EVENT", "action": "orders/active2", "body": {"id": 2188572787, "type": "TAKE_PROFIT", "status": "AWAITING",
                                                                          "side": "SELL", "qty": 0.01, "triggerPrice": 3927.79}}, "in")
        self.assertEqual(len(f.state()["orders"]), 2)
        f._on_frame({"type": "EVENT", "action": "orders/active2", "body": {"id": 2188572786, "status": "CANCELLED"}}, "in")
        self.assertEqual([x["id"] for x in f.state()["orders"]], [2188572787])
        f._on_frame(act("Market order filled", "Buy 0.01 XAU/USD @ 3926.59"), "in")
        f._on_frame(act("Stop loss linked to position", "15394511: Stop loss #2188572786 sell XAU/USD @ 3923.71"), "in")
        acts = f.state()["activity"]
        self.assertEqual([(x["title"], x["body"]) for x in acts],
                         [("Market order filled", "Buy 0.01 XAU/USD @ 3926.59"),
                          ("Stop loss linked to position", "15394511: Stop loss #2188572786 sell XAU/USD @ 3923.71")])
        self.assertEqual([e["title"] for e in self.events if e["type"] == "activity"], [x["title"] for x in acts])

    def test_markets2_fallback_only_when_fx_silent(self):
        f = self.f
        m2 = {"type": "EVENT", "action": "markets2", "body": {"data": [{"symbol": "BTC/USD", "ask": 1, "bid": 1},
                                                                         {"symbol": "XAU/USD", "ask": 3930.33, "bid": 3930.0}]}}
        f._on_frame(fx(3926.38, 3926.71), "in", ts=1000.0)
        f._on_frame(m2, "in", ts=1001.0)
        self.assertEqual(f._quote["bid"], 3926.38)
        f._on_frame(m2, "in", ts=1004.0)
        self.assertEqual(f._quote["bid"], 3930.0)


# =================================================================================================================================
class TestLiveFeedTrading(unittest.TestCase):
    """LiveFeed's trading logic with a fake sender standing in for the page socket (no CDP, no Chrome)."""

    def make(self, quote=(3928.95, 3929.28)):
        f = feeds.LiveFeed(config=CFG)
        f._ready = lambda: None
        self.sent = []
        f._on_frame(fx(*quote), "in")
        return f

    def test_start_refused_under_test_guard(self):
        with self.assertRaises(RuntimeError):
            feeds.LiveFeed(config=CFG).start()

    def test_place_resolves_position_from_link_activity(self):
        f = self.make()
        seen = {}

        def sender(msg):
            self.sent.append(msg)
            seen["pending"] = f._chan.pending()
            rid = msg["rid"]
            f._on_frame({"type": "RESPONSE", "rid": rid, "action": msg["action"], "body": {"id": 2188562137, "error": None}}, "in")
            f._on_frame(act("Market order filled", "Buy 0.01 XAU/USD @ 3929.28"), "in")
            f._on_frame(act("Stop loss linked to position", "15394511: Stop loss #2188572786 sell XAU/USD @ 3928.28"), "in")
            f._on_frame(act("Take profit linked to position", "15394511: Take profit #2188572787 sell XAU/USD @ 3930.48"), "in")
        f._send_frame = sender
        r = f.place(1, 0.01, 3928.28, 3930.48)
        self.assertEqual(seen["pending"], 1, "the pending slot must exist before the frame is sent")
        self.assertEqual(len(self.sent), 1)
        m = self.sent[0]
        self.assertEqual((m["type"], m["action"]), ("REQUEST", "orders/market/place"))
        self.assertGreaterEqual(m["rid"], 900000)
        self.assertEqual(m["body"], {"qty": 0.01, "side": "BUY", "symbol": "XAU/USD", "takeProfit": {"price": 3930.48},
                                     "stopLoss": {"price": 3928.28}})
        self.assertTrue(r["ok"], r)
        self.assertIsNone(r["error"])
        self.assertEqual(r["order_id"], 2188562137)
        self.assertEqual(r["position_id"], 15394511)
        self.assertEqual(r["fill_price"], 3929.28)
        self.assertEqual((r["sl_order"], r["tp_order"]), (2188572786, 2188572787))
        self.assertIn(15394511, f._own)
        self.assertLess(r["rtt_ms"], 1000)

    def test_place_resolves_by_positions_diff_and_prefers_open_price(self):
        f = self.make()
        f._on_frame(positions_frame([P0_SHORT]), "in")

        def sender(msg):
            f._on_frame({"type": "RESPONSE", "rid": msg["rid"], "action": msg["action"], "body": {"id": 7, "error": None}}, "in")
            f._on_frame(act("Market order filled", "Sell 0.01 XAU/USD @ 3928.95"), "in")
            f._on_frame(positions_frame([P0_SHORT, sub_position(15400001, "SELL", 0.01, 3928.94, 3929.28, sl=3929.95, tp=3927.75)]),
                        "in")
        f._send_frame = sender
        r = f.place(-1, 0.01, 3929.95, 3927.75)
        self.assertTrue(r["ok"])
        self.assertEqual(r["position_id"], 15400001)
        self.assertEqual(r["fill_price"], 3928.94)                # the position's openPrice wins over a disagreeing activity

    def test_place_definite_error_and_timeout(self):
        f = self.make()

        def refuse(msg):
            f._on_frame({"type": "RESPONSE", "rid": msg["rid"], "action": msg["action"],
                         "error": {"code": "INSUFFICIENT_FUNDS", "description": "Not enough margin"}}, "in")
        f._send_frame = refuse
        r = f.place(1, 0.01, 3928.28, 3930.48)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "INSUFFICIENT_FUNDS: Not enough margin")
        self.assertIsNone(r["position_id"])

        f._send_frame = lambda msg: None                          # the reply never comes
        t = time.perf_counter()
        r = f.place(1, 0.01, 3928.28, 3930.48, timeout=0.3)
        self.assertLess(time.perf_counter() - t, 1.5)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "TIMEOUT")
        self.assertIn("resolve_token", r)
        self.assertEqual(f._chan.pending(), 0)

        def lost(msg):
            raise feeds.SendNotOpen("x")
        f._send_frame = lost
        r = f.place(1, 0.01, 3928.28, 3930.48)
        self.assertEqual((r["ok"], r["error"]), (False, "SOCKET_LOST"))

    def test_uncertain_send_still_finds_the_position(self):
        f = self.make()

        def flaky(msg):
            f._on_frame(act("Stop loss linked to position", "15500000: Stop loss #1 sell XAU/USD @ 3928.28"), "in")
            raise RuntimeError("CDP Runtime.evaluate timed out")
        f._send_frame = flaky
        r = f.place(1, 0.01, 3928.28, 3930.48, timeout=0.5)
        self.assertTrue(r["ok"])
        self.assertEqual(r["position_id"], 15500000)

    def test_safety_rails_send_nothing(self):
        f = self.make()
        f._send_frame = lambda msg: self.sent.append(msg)
        cases = [((1, 0.5, 3928.28, 3930.48), "QTY_CAP"), ((1, 0.015, 3928.28, 3930.48), "BAD_QTY"),
                 ((1, 0.01, None, 3930.48), "BAD_PROTECTIVE"), ((1, 0.01, 3930.48, 3928.28), "BAD_PROTECTIVE"),
                 ((-1, 0.01, 3928.28, 3930.48), "BAD_PROTECTIVE"), ((1, 0.01, 3700.0, 3930.48), "BAD_PROTECTIVE"),
                 ((0, 0.01, 3928.28, 3930.48), "BAD_SIDE")]
        for args, code in cases:
            r = f.place(*args)
            self.assertFalse(r["ok"], args)
            self.assertTrue(r["error"].startswith(code), (args, r["error"]))
        r = f.close(15391910, 0.01)
        self.assertTrue(r["error"].startswith("NOT_OURS"))
        r = f.set_protective(15391910, "STOP_LOSS", 3925.0)
        self.assertTrue(r["error"].startswith("NOT_OURS"))
        self.assertEqual(self.sent, [])
        g = feeds.LiveFeed(config=CFG)
        self.assertEqual(g.place(1, 0.01, 3928.28, 3930.48)["error"], "NOT_CONNECTED")

    def test_unresolved_order_position_found_later_is_ours_others_are_not(self):
        f = self.make()
        f._on_frame(positions_frame([P0_SHORT]), "in")
        f.resolve_s = 0.05

        def sender(msg):
            self.sent.append(msg)
            if msg["action"] == "orders/market/place":
                f._on_frame({"type": "RESPONSE", "rid": msg["rid"], "action": msg["action"], "body": {"id": 5, "error": None}}, "in")
            else:
                f._on_frame({"type": "RESPONSE", "rid": msg["rid"], "action": msg["action"], "body": {}}, "in")
        f._send_frame = sender
        r = f.place(1, 0.01, 3928.28, 3930.48)
        self.assertTrue(r["ok"])
        self.assertIsNone(r["position_id"])
        self.assertIn("resolve_token", r)
        zee = sub_position(15400002, "BUY", 0.01, 3929.0, 3929.0, sl=3920.00, tp=3940.0)       # Zee's own trade, other stop
        ours = sub_position(15400003, "BUY", 0.01, 3929.28, 3929.0, sl=3928.28, tp=3930.48)
        f._on_frame(positions_frame([P0_SHORT, zee, ours]), "in")
        self.assertTrue(f.close(15400002, 0.01)["error"].startswith("NOT_OURS"))
        self.assertTrue(f.close(15391910, 0.01)["error"].startswith("NOT_OURS"))
        self.assertTrue(f.close(15400003, 0.01)["ok"])
        self.assertEqual(f.resolve(r["resolve_token"], timeout=0.1)["position_id"], 15400003)

    def test_owned_positions_persist_for_a_restarted_game(self):
        tmp = tempfile.mkdtemp(prefix="gg_own_")
        try:
            path = os.path.join(tmp, "owned.json")
            f = feeds.LiveFeed(config=CFG, own_file=path)
            f._persist = True                                    # start() turns this on for a real page only
            f.adopt(15394511)
            g = feeds.LiveFeed(config=CFG, own_file=path)
            self.assertNotIn(15394511, g._own)
            g._load_owned()
            self.assertIn(15394511, g._own)
            with open(path, encoding="utf-8") as fh:
                self.assertEqual([x["id"] for x in json.load(fh)["positions"]], [15394511])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_set_check_close_report(self):
        f = self.make()
        f.adopt(15394511)
        f._on_frame(positions_frame([sub_position(15394511, "BUY", 0.01, 3926.59, 3928.95, sl=3925.59, tp=3927.79)]), "in")
        replies = {
            "positions/id/protective-order/set": {"body": {}},
            "positions/id/protective-order/impact": {"body": {"profitLoss": -0.03, "resolution": "OK", "resolutionLevel": "INFO"}},
            "positions/id/close": {"body": {}},
            "report/orders2": {"body": {"data": [{"id": 9, "type": "MARKET", "status": "EXECUTED", "side": "SELL", "qty": 0.01,
                                                  "executedPrice": 3928.94, "executedQty": 0.01, "rpl": 0.0235, "fee": 0,
                                                  "positionId": 15394511, "closeReason": "EXECUTION",
                                                  "executedAt": "2026-11-03T04:47:10.120Z"}]}},
        }

        def sender(msg):
            self.sent.append(msg)
            rep = dict(replies[msg["action"]])
            f._on_frame({"type": "RESPONSE", "rid": msg["rid"], "action": msg["action"], **rep}, "in")
            if msg["action"] == "positions/id/close":
                f._on_frame(act("Stop loss cancelled", "15394511: Stop loss #2188572786 sell XAU/USD @ 3925.59", "INFO"), "in")
                f._on_frame(act("Market order filled", "Sell 0.01 XAU/USD @ 3928.94"), "in")
        f._send_frame = sender
        r = f.set_protective(15394511, "STOP_LOSS", 3924)
        self.assertTrue(r["ok"])
        self.assertEqual(self.sent[-1]["body"], {"positionId": 15394511, "price": 3924.0, "type": "STOP_LOSS"})
        r = f.check_protective(15394511, 3924)
        self.assertEqual((r["ok"], r["resolution"], r["profitLoss"]), (True, "OK", -0.03))
        self.assertEqual(self.sent[-1]["body"], {"price": 3924.0, "positionId": 15394511})
        r = f.close(15394511, 0.01)
        self.assertTrue(r["ok"])
        self.assertEqual(r["fill_price"], 3928.94)
        self.assertEqual(self.sent[-1]["body"], {"positionId": 15394511, "qty": 0.01})
        rows = f.orders_report(1793677000.0)
        self.assertTrue(rows.ok)
        self.assertEqual(rows[0]["rpl"], 0.0235)
        self.assertAlmostEqual(rows[0]["executed_ts"], feeds.to_unix("2026-11-03T04:47:10.120Z"))
        self.assertEqual(self.sent[-1]["body"], {"limit": 100, "offset": 0, "fromExecutedAt": 1793677000.0,
                                                 "toExecutedAt": 2114467199.999, "symbol": "XAU/USD"})

        def nf(msg):
            f._on_frame({"type": "RESPONSE", "rid": msg["rid"], "action": msg["action"],
                         "error": {"code": "POSITION_NOT_FOUND", "description": "120: Not found position #15394511"}}, "in")
        f._send_frame = nf
        r = f.close(15394511, 0.01)
        self.assertFalse(r["ok"])
        self.assertTrue(r["error"].startswith("POSITION_NOT_FOUND"))


# =================================================================================================================================
class FakePage:
    """Stands in for cdpcore.CDPSession AND the PXTrader page: answers the CDP calls LiveFeed makes and plays a tiny futures
    server (backed by a ShadowBroker) for every frame LiveFeed sends through cdpcore.PageSockets.send."""
    JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.c2lnbmF0dXJlLXRlc3Q"

    def __init__(self):
        self.alive = True
        self.listeners = []
        self.marked = False
        self.stored_sid = None
        self.sent = []
        self.sid = 4242
        self.broker = feeds.ShadowBroker(balance=0.63, pos_id0=15394511, order_id0=2188562137, account_id="L1869984")
        self.bid, self.ask = 3926.38, 3926.71
        self.broker.on_quote(self.bid, self.ask)
        self.account = "l1869984"                 # the accountId in the futures socket's url (the page may switch it)
        self.listed = []                          # what LiveFeed's socket listing returned (it must never carry a url)

    # cdpcore.CDPSession surface
    def on(self, fn):
        self.listeners.append(fn)
        return fn

    def off(self, fn):
        if fn in self.listeners:
            self.listeners.remove(fn)

    def close(self):
        self.alive = False

    def call(self, method, timeout=10, **params):
        if method in ("Network.enable", "Page.enable"):
            return {}
        if method == "Runtime.evaluate" and params.get("expression") == "WebSocket.prototype":
            return {"result": {"objectId": "proto"}}
        if method == "Runtime.queryObjects":
            return {"objects": {"objectId": "arr"}}
        if method == "Runtime.callFunctionOn":
            fd = params.get("functionDeclaration", "")
            assert "searchParams.get('accountId')" in fd and "w.url" not in fd.split("return socks.map")[1].replace(
                "String(w.url).indexOf('/v2/fws/')", "").replace("acct(w)", ""), "the socket listing must not return a url"
            value = [{"i": 0, "state": 1, "fws": False, "account": ""}, {"i": 1, "state": 1, "fws": True, "account": self.account}]
            self.listed.append(value)
            return {"result": {"value": value}}
        if method == "Runtime.evaluate":
            return {"result": {"value": self.js(params.get("expression", ""))}}
        if method == "Network.getResponseBody":
            return {"body": json.dumps(CAL), "base64Encoded": False}
        if method == "Network.getRequestPostData":
            return {"postData": "{}"}
        raise RuntimeError("unexpected CDP call " + method)

    def js(self, expression, timeout=10):
        if "w.__gg_sid1m === undefined" in expression:           # LiveFeed asks whether this socket carries its subscription
            return {"marked": self.marked, "sid": self.stored_sid}
        m = re.search(r"w\.__gg_sub1m = true; w\.__gg_sid1m = ([^;]+);", expression)
        if m:
            self.marked, self.stored_sid = True, json.loads(m.group(1))
            return True
        if "__gg_sub1m = false" in expression:
            self.marked, self.stored_sid = False, None
            return True
        if "indexOf('/v2/fws/')" in expression and "w.send(" not in expression:     # the socket check (not a send)
            return True
        m = re.search(r"w\.send\((\".*\")\); return 'sent';", expression, re.S)
        if m:
            pin = re.search(r"if \((\"[^\"]*\") && a !== (\"[^\"]*\")\) return 'account';", expression)
            assert pin is not None, "the send must re-check the account in the same evaluation"
            if json.loads(pin.group(1)) and json.loads(pin.group(1)) != self.account:
                return "account"
            msg = json.loads(json.loads(m.group(1)))
            self.sent.append(msg)
            self.emit("Network.webSocketFrameSent", {"requestId": "fws.1", "response": {"opcode": 1, "payloadData": json.dumps(msg)}})
            threading.Thread(target=self.serve, args=(msg,), daemon=True).start()
            return "sent"
        if "economic-calendar/upcoming" in expression:
            self.fetched = expression
            return {"status": 200, "data": [{"t": e["eventTime"], "title": e["eventTitle"], "impact": e["importance"],
                                             "country": e["regionCode"]} for e in UPCOMING]}
        if "fetch(" in expression:
            self.fetched = expression
            return {"status": 200, "text": json.dumps(CAL)}
        return None

    # the page / server side
    def emit(self, method, params):
        for fn in list(self.listeners):
            fn(method, params)

    def frame_in(self, obj, rq="fws.1"):
        self.emit("Network.webSocketFrameReceived", {"requestId": rq, "timestamp": 1.0,
                                                     "response": {"opcode": 1, "mask": False, "payloadData": json.dumps(obj)}})

    def tick(self, bid, ask):
        self.bid, self.ask = bid, ask
        evs = []
        self.broker.subscribe(evs.append)
        self.broker.on_quote(bid, ask)
        self.broker.unsubscribe(evs.append)
        self.frame_in(fx(bid, ask))
        self.frame_in({"type": "EVENT", "action": "bar", "sid": self.sid, "aid": 9,
                       "body": {"data": [int(time.time() // 60) * 60, bid, bid, bid, bid, 1]}})
        self.push(evs)

    def push(self, evs):
        for e in evs:
            if e["type"] == "activity":
                self.frame_in(act(e["title"], e["body"], e["level"]))
        subs = [sub_position(p["id"], "BUY" if p["side"] > 0 else "SELL", p["qty"], p["open_price"], p["mark"], p["sl"], p["tp"],
                             p["sl_order"], p["tp_order"], p["upl"]) for p in self.broker.positions()]
        self.frame_in(positions_frame(subs))
        a = self.broker.account()
        self.frame_in({"type": "EVENT", "action": "metrics", "body": {"accountId": "L1869984", "balance": a["balance"],
                                                                       "equity": a["equity"], "upl": a["upl"],
                                                                       "availableMargin": a["available"], "demo": False,
                                                                       "debugUrl": "wss://api.example/v2/fws/?token=" + self.JWT}})

    def serve(self, msg):
        time.sleep(0.005)
        a, rid, body = msg["action"], msg["rid"], msg.get("body") or {}

        def reply(**kw):
            self.frame_in({"type": "RESPONSE", "rid": rid, "action": a, **kw})
        if a == "time":
            reply(body={"time": int(time.time() * 1000)})
        elif a == "bars":
            reply(body={"data": gen_rows(329, int(time.time() // 60) * 60, start=self.bid)})
        elif a == "bar":
            reply(sid=self.sid, body={"data": [int(time.time() // 60) * 60, self.bid, self.bid, self.bid, self.bid, 1]})
        elif a in ("orders/market/place", "positions/id/protective-order/set", "positions/id/close",
                   "positions/id/protective-order/impact"):
            evs = []
            self.broker.subscribe(evs.append)
            if a == "orders/market/place":
                r = self.broker.place(1 if body["side"] == "BUY" else -1, body["qty"], body["stopLoss"]["price"],
                                      body["takeProfit"]["price"])
                out = {"id": r.get("order_id"), "error": None}
            elif a == "positions/id/protective-order/set":
                r = self.broker.set_protective(body["positionId"], body["type"], body["price"])
                out = {}
            elif a == "positions/id/close":
                r = self.broker.close(body["positionId"], body["qty"])
                out = {}
            else:
                r = self.broker.check_protective(body["positionId"], body["price"])
                out = {"profitLoss": r.get("profitLoss"), "resolution": "OK", "resolutionLevel": "INFO"}
            self.broker.unsubscribe(evs.append)
            if r["ok"]:
                reply(body=out)
            else:
                code, _, desc = r["error"].partition(": ")
                reply(error={"code": code, "description": desc})
            self.push(evs)
        elif a == "report/orders2":
            rows = self.broker.orders_report(body.get("fromExecutedAt", 0))
            for row in rows:
                row.pop("executed_ts", None)
            reply(body={"data": rows})
        elif a == "positions":                    # the seed REQUESTs (PROTOCOL 07:57 addendum)
            subs = [sub_position(p["id"], "BUY" if p["side"] > 0 else "SELL", p["qty"], p["open_price"], p["mark"], p["sl"], p["tp"],
                                 p["sl_order"], p["tp_order"], p["upl"]) for p in self.broker.positions()]
            reply(body=dict(positions_frame(subs)["body"], accountId="L1869984"))
        elif a == "metrics":
            acc = self.broker.account()
            reply(body={"accountId": "L1869984", "balance": acc["balance"], "equity": acc["equity"], "upl": acc["upl"],
                        "availableMargin": acc["available"], "demo": False, "positionMode": "HEDGE"})
        elif a == "orders/active2":
            reply(body={"data": [o for o in self.broker.orders()]})


class TestLiveFeedAgainstFakePage(unittest.TestCase):
    def test_end_to_end(self):
        page = FakePage()
        tmp = tempfile.mkdtemp(prefix="gg_rec_")
        f = feeds.LiveFeed(record=True, rec_dir=tmp, config=CFG, session_factory=lambda: page, calendar_every_s=0.6)
        try:
            f.start()
            self.assertTrue(wait_for(lambda: len(f.state()["bars"]) >= 330 and f._fws_index == 1, 5.0), f.state()["reason"])
            self.assertTrue(wait_for(lambda: page.marked and page.stored_sid == page.sid))
            subs = [m for m in page.sent if m["action"] == "bar"]
            self.assertEqual(len(subs), 1)
            self.assertEqual((subs[0]["type"], subs[0]["body"]), ("SUBSCRIPTION", {"symbolId": 1019, "barSize": "1M", "askOhlc": False}))
            bars_req = [m for m in page.sent if m["action"] == "bars"][0]
            self.assertEqual((bars_req["body"]["bar_size"], bars_req["body"]["limit"], bars_req["body"]["askOhlc"]), ("1M", 329, False))
            page.tick(3926.38, 3926.71)
            self.assertTrue(wait_for(lambda: f.state()["ok"]))
            s = f.state()
            self.assertEqual((s["quote"]["bid"], s["quote"]["ask"]), (3926.38, 3926.71))
            self.assertEqual(s["account"]["id"], "L1869984")
            # the page's calendar request is captured passively, then re-issued with fetch
            page.emit("Network.requestWillBeSent", {"requestId": "c1", "request": {
                "url": "https://api.example/v2/economic-calendar/events", "method": "POST", "postData": '{"from":1}'}})
            page.emit("Network.responseReceived", {"requestId": "c1", "response": {"url": "https://api.example/v2/economic-calendar/events"}})
            page.emit("Network.loadingFinished", {"requestId": "c1"})
            self.assertTrue(wait_for(lambda: len(f.state()["news"]) == 3))
            self.assertEqual(f.state()["news"][1]["impact"], "high")
            self.assertTrue(wait_for(lambda: hasattr(page, "fetched"), 3.0))
            self.assertIn("credentials: 'include'", page.fetched)
            # a long round: place, move the stop, close
            ask = f.state()["quote"]["ask"]
            r = f.place(1, 0.01, round(ask - 1.0, 2), round(ask + 1.2, 2))
            self.assertTrue(r["ok"], r)
            pid = r["position_id"]
            self.assertEqual(pid, 15394511)
            self.assertEqual(r["fill_price"], 3926.71)
            self.assertTrue(wait_for(lambda: any(p["id"] == pid for p in f.state()["positions"])))
            r2 = f.set_protective(pid, "STOP_LOSS", 3926.0)
            self.assertTrue(r2["ok"], r2)
            self.assertTrue(wait_for(lambda: any(p["id"] == pid and p["sl"] == 3926.0 for p in f.state()["positions"])))
            self.assertEqual(f.check_protective(pid, 3926.0)["resolution"], "OK")
            page.tick(3927.00, 3927.33)
            r3 = f.close(pid, 0.01)
            self.assertTrue(r3["ok"], r3)
            self.assertEqual(r3["fill_price"], 3927.0)
            self.assertTrue(wait_for(lambda: f.state()["positions"] == []))
            rows = f.orders_report(time.time() - 60)
            closing = [x for x in rows if x["status"] == "EXECUTED" and x["side"] == "SELL"]
            self.assertEqual(len(closing), 1)
            self.assertAlmostEqual(closing[0]["rpl"], 0.0029, places=6)
            self.assertIsNotNone(closing[0]["executed_ts"])
            # a page reload: re-acquire and re-subscribe on the new socket
            page.marked, page.stored_sid = False, None               # a reload brings a fresh socket object
            page.emit("Page.frameNavigated", {"frame": {"id": "main", "url": "https://primexbt.com/x"}})
            self.assertTrue(wait_for(lambda: len([m for m in page.sent if m["action"] == "bar"]) == 2, 5.0))
            self.assertTrue(wait_for(lambda: f._fws_index == 1 and not f._need_acquire))
        finally:
            f.stop()
        with open(f.recording_path, encoding="utf-8") as fh:
            rec = fh.read()
        shutil.rmtree(tmp, ignore_errors=True)
        self.assertIn('"dir":"out"', rec)
        self.assertIn("orders/market/place", rec)
        self.assertIn("GG_CALENDAR", rec)
        self.assertNotIn("wss://", rec)
        self.assertNotIn("/v2/fws/", rec)
        self.assertNotIn(FakePage.JWT, rec)
        for line in rec.splitlines():
            d = json.loads(line)
            self.assertEqual(set(d), {"t", "dir", "frame"})


    def test_restarted_game_inherits_its_subscription(self):
        page = FakePage()
        page.marked, page.stored_sid = True, 4242                 # an earlier run of the game subscribed on this socket
        f = feeds.LiveFeed(config=CFG, session_factory=lambda: page)
        try:
            f.start()
            self.assertTrue(wait_for(lambda: len(f.state()["bars"]) >= 329, 5.0), f.state()["reason"])
            time.sleep(0.1)
            self.assertEqual([m["action"] for m in page.sent if m["action"] in ("bar", "bars")], ["bars"])
            t = int(time.time() // 60) * 60
            page.frame_in({"type": "EVENT", "action": "bar", "sid": 4242, "aid": 1, "body": {"data": [t, 3930.0, 3931.0, 3929.5, 3930.5, 7]}})
            self.assertTrue(wait_for(lambda: f.state()["bars"][-1][:5] == [t, 3930.0, 3931.0, 3929.5, 3930.5]))
        finally:
            f.stop()


# =================================================================================================================================
class TestShadowBroker(unittest.TestCase):
    def setUp(self):
        self.b = feeds.ShadowBroker(balance=25.0, clock=lambda: T_DAY)
        self.ev = []
        self.b.subscribe(self.ev.append)
        self.b.on_quote(3926.38, 3926.71, T_DAY)

    def titles(self):
        return [e["title"] for e in self.ev if e["type"] == "activity"]

    def test_long_fills_at_ask_and_tp_triggers_on_bid(self):
        b = self.b
        r = b.place(1, 0.01, 3925.71, 3927.91)
        self.assertTrue(r["ok"])
        self.assertEqual(r["fill_price"], 3926.71)
        pid = r["position_id"]
        self.assertEqual(self.titles(), ["Market order filled", "Stop loss linked to position", "Take profit linked to position"])
        acts = [e for e in self.ev if e["type"] == "activity"]
        self.assertEqual(acts[0]["body"], "Buy 0.01 XAU/USD @ 3926.71")
        self.assertEqual(acts[1]["body"], f"{pid}: Stop loss #{r['sl_order']} sell XAU/USD @ 3925.71")
        b.on_quote(3927.60, 3927.93, T_DAY + 1)                  # ask above the TP, bid below: a long's TP waits for the bid
        self.assertEqual(len(b.positions()), 1)
        self.ev.clear()
        b.on_quote(3928.10, 3928.43, T_DAY + 2)                  # jumped past: fills at the bid, better than the TP
        self.assertEqual(b.positions(), [])
        self.assertEqual(self.titles(), ["Take profit triggered", "Take profit filled", "Stop loss cancelled"])
        res = b.result(pid)
        self.assertEqual((res["exit_type"], res["exit_price"]), ("TAKE_PROFIT", 3928.10))
        self.assertAlmostEqual(res["rpl"], 0.0139, places=6)
        self.assertAlmostEqual(b.account()["balance"], 25.0139, places=6)

    def test_short_triggers_on_ask(self):
        b = self.b
        r = b.place(-1, 0.01, 3927.38, 3925.18)
        self.assertEqual(r["fill_price"], 3926.38)
        b.on_quote(3927.20, 3927.30, T_DAY + 1)                  # bid above the SL, ask still below: no trigger
        self.assertEqual(len(b.positions()), 1)
        b.on_quote(3927.10, 3927.43, T_DAY + 2)
        self.assertEqual(b.positions(), [])
        res = b.result(r["position_id"])
        self.assertEqual((res["exit_type"], res["exit_price"]), ("STOP_LOSS", 3927.43))
        self.assertAlmostEqual(res["net"], -0.0105, places=6)

    def test_gap_through_the_stop_fills_beyond_it(self):
        b = self.b
        r = b.place(1, 0.01, 3925.00, 3928.00)
        b.on_quote(3925.40, 3925.73, T_DAY + 1)
        self.assertEqual(len(b.positions()), 1)
        b.on_quote(3924.10, 3924.43, T_DAY + 2)                  # a gap: no price between 3925.40 and 3924.10 printed
        rows = [x for x in b.orders_report(0) if x["type"] == "STOP_LOSS" and x["status"] == "EXECUTED"]
        self.assertEqual(rows[0]["executedPrice"], 3924.10)
        self.assertEqual(rows[0]["triggerPrice"], 3925.00)
        self.assertAlmostEqual(rows[0]["rpl"], round((3924.10 - r["fill_price"]) * 0.01, 6))

    def test_already_crossed_tp_or_sl_fills_at_once(self):
        b = self.b
        r = b.place(1, 0.01, 3920.0, 3926.0)                     # TP below the bid: accepted, fills at once at the bid
        self.assertTrue(r["ok"])
        self.assertEqual(b.positions(), [])
        self.assertEqual(b.result(r["position_id"])["exit_price"], 3926.38)
        self.assertIn("Take profit filled", self.titles())
        r = b.place(1, 0.01, 3925.71, 3927.91)
        self.ev.clear()
        s = b.set_protective(r["position_id"], "STOP_LOSS", 3926.50)   # a stop above the bid: fills at once
        self.assertTrue(s["ok"])
        self.assertEqual(b.positions(), [])
        self.assertEqual(self.titles()[:3], ["Stop loss replaced", "Stop loss triggered", "Stop loss filled"])
        self.assertEqual(b.result(r["position_id"])["exit_price"], 3926.38)

    def test_replace_partial_close_and_report(self):
        b = self.b
        r = b.place(1, 0.02, 3925.71, 3927.91)
        pid = r["position_id"]
        s = b.set_protective(pid, "STOP_LOSS", 3926.00)
        self.assertTrue(s["ok"])
        self.assertEqual(b.position(pid)["sl"], 3926.00)
        self.assertIn("Stop loss replaced", self.titles())
        self.assertEqual(b.close(pid, 0.015)["error"], "BAD_QTY")
        b.on_quote(3927.00, 3927.33, T_DAY + 5)
        c = b.close(pid, 0.01)
        self.assertTrue(c["ok"])
        self.assertEqual((c["fill_price"], c["qty"], c["remaining"]), (3927.00, 0.01, 0.01))
        self.assertAlmostEqual(c["rpl"], 0.0029, places=6)
        self.assertEqual(b.position(pid)["qty"], 0.01)
        self.assertEqual({o["qty"] for o in b.orders()}, {0.01})
        c2 = b.close(pid, 0.01)
        self.assertEqual(c2["remaining"], 0.0)
        self.assertEqual(b.positions(), [])
        self.assertEqual(b.orders(), [])
        rows = b.orders_report(0)
        self.assertEqual(rows[0]["type"], "MARKET")              # newest first
        replaced = [x for x in rows if x["closeReason"] == "REPLACED"]
        self.assertEqual(len(replaced), 1)
        executed = [x for x in rows if x["status"] == "EXECUTED"]
        self.assertAlmostEqual(sum(x["rpl"] for x in executed), 0.0058, places=6)
        self.assertAlmostEqual(b.account()["balance"], 25.0058, places=6)
        self.assertTrue(all("executed_ts" in x and "executedAt" in x for x in rows))
        self.assertEqual(b.close(pid, 0.01)["error"].split(":")[0], "POSITION_NOT_FOUND")
        self.assertEqual(b.set_protective(pid, "STOP_LOSS", 1.0)["error"].split(":")[0], "POSITION_NOT_FOUND")
        self.assertEqual(b.check_protective(pid, 1.0)["error"].split(":")[0], "POSITION_NOT_FOUND")

    def test_check_protective_and_slippage_bounds(self):
        b = self.b
        r = b.place(1, 0.01, 3925.71, 3927.91)
        c = b.check_protective(r["position_id"], 3924.0)
        self.assertEqual((c["ok"], c["resolution"]), (True, "OK"))
        self.assertAlmostEqual(c["profitLoss"], round((3924.0 - 3926.71) * 0.01, 6))
        s = feeds.ShadowBroker(balance=25.0, slippage_max=0.06, seed=3)
        s.on_quote(3926.38, 3926.71)
        buys = [s.place(1, 0.01, None, None)["fill_price"] for _ in range(40)]
        sells = [s.place(-1, 0.01, None, None)["fill_price"] for _ in range(40)]
        self.assertTrue(all(3926.71 <= x <= 3926.77 for x in buys), buys)
        self.assertTrue(all(3926.32 <= x <= 3926.38 for x in sells), sells)
        self.assertGreater(len(set(buys)), 2)

    def test_fill_price_override_and_validation(self):
        b = self.b
        r = b.place(1, 0.01, 3925.59, 3927.79, fill_price=3926.59)
        self.assertEqual(r["fill_price"], 3926.59)
        self.assertEqual(b.place(2, 0.01, 1, 2)["error"], "BAD_SIDE")
        self.assertEqual(b.place(1, 0.001, 1, 2)["error"], "BAD_QTY")
        self.assertEqual(feeds.ShadowBroker().place(1, 0.01, 1, 2)["error"], "NO_QUOTE")
        poor = feeds.ShadowBroker(balance=0.001)
        poor.on_quote(3926.38, 3926.71)
        self.assertEqual(poor.place(1, 0.01, 3925, 3928)["error"], "INSUFFICIENT_FUNDS")


# =================================================================================================================================
class TestSimFeed(unittest.TestCase):
    def test_ready_at_construction(self):
        f = feeds.SimFeed(seed=7, manual=True)
        s = f.state()
        self.assertTrue(s["ok"])
        self.assertTrue(s["market_open"])
        self.assertIsNotNone(s["quote"])
        self.assertLess(abs(s["quote"]["ts"] - time.time()), 5)  # the virtual clock starts at wall time
        self.assertEqual(s["account"], {"id": "SIM-1", "type": "SIM", "balance": 25.0, "equity": 25.0, "upl": 0.0,
                                        "available": 25.0, "currency": "USD"})
        bars = s["bars"]
        self.assertEqual(len(bars), 331)                         # 330 bars of history + the forming bar
        ts_ = [b[0] for b in bars]
        self.assertTrue(all(t % 60 == 0 for t in ts_))
        self.assertTrue(all(b - a == 60 for a, b in zip(ts_, ts_[1:])))
        self.assertAlmostEqual(bars[-2][4], s["quote"]["bid"], places=2)
        self.assertTrue(all(b[3] <= min(b[1], b[4]) and b[2] >= max(b[1], b[4]) for b in bars))
        self.assertGreater(s["h24"], s["l24"])
        self.assertEqual(f.place(1, 0.01, s["quote"]["ask"] - 1, s["quote"]["ask"] + 1.2)["ok"], True)

    def test_deterministic_with_seed(self):
        a = feeds.SimFeed(seed=11, manual=True, start_ts=T_DAY)
        b = feeds.SimFeed(seed=11, manual=True, start_ts=T_DAY)
        c = feeds.SimFeed(seed=12, manual=True, start_ts=T_DAY)
        qa, qb, qc = a.pump(800), b.pump(800), c.pump(800)
        self.assertEqual(qa, qb)
        self.assertNotEqual([q[1:] for q in qa], [q[1:] for q in qc])
        self.assertEqual(a.state()["bars"], b.state()["bars"])
        ra = a.place(1, 0.01, 1.0, 9999.0)
        rb = b.place(1, 0.01, 1.0, 9999.0)
        self.assertEqual(ra["fill_price"], rb["fill_price"])
        rate = len(qa) / (qa[-1][0] - T_DAY)
        self.assertTrue(1.8 < rate < 4.5, rate)                  # ~2.5 quotes a second

    def test_bars_are_built_from_its_ticks(self):
        f = feeds.SimFeed(seed=5, manual=True, start_ts=T_DAY + 1)
        quotes = f.advance(245)
        bars = f.state()["bars"]
        by_min = {}
        for ts, bid, ask in quotes:
            by_min.setdefault(int(ts // 60) * 60, []).append(bid)
        first_live = int((T_DAY + 1) // 60) * 60
        for b in bars:
            if b[0] <= first_live or b[0] not in by_min:
                continue
            bids = by_min[b[0]]
            self.assertEqual(b[1:5], [bids[0], max(bids), min(bids), bids[-1]], b)
        self.assertEqual(bars[-1][0], int(f.now() // 60) * 60)
        self.assertGreaterEqual(len(bars), 334)

    def test_spreads_day_night_storm(self):
        f = feeds.SimFeed(seed=2, manual=True, start_ts=T_DAY, regime="calm")
        f.sim_force("calm", seconds=3600)
        day = {round(a - b, 2) for _, b, a in f.pump(200)}
        self.assertEqual(day, {0.33})
        n = feeds.SimFeed(seed=2, manual=True, start_ts=T_NIGHT, regime="calm")
        n.sim_force("calm", seconds=7200)
        night = {round(a - b, 2) for _, b, a in n.advance(400)}
        self.assertTrue(all(0.45 <= x <= 0.80 for x in night), night)
        f.sim_force("storm", seconds=600)
        storm = {round(a - b, 2) for _, b, a in f.advance(300)}
        self.assertTrue(all(0.45 <= x <= 0.80 for x in storm), storm)
        self.assertEqual(f.regime, "storm")

    def test_forced_gap_skips_prices_and_barrels_a_stop(self):
        f = feeds.SimFeed(seed=9, manual=True, start_ts=T_DAY, regime="calm")
        f.sim_force("calm", seconds=3600)
        f.pump(20)
        q = f.state()["quote"]
        r = f.place(1, 0.01, round(q["ask"] - 0.5, 2), round(q["ask"] + 5.0, 2))
        self.assertTrue(r["ok"])
        before = f.state()["quote"]["bid"]
        f.sim_force("gap", size=-1.2)
        after = f.pump(1)[0][1]
        self.assertAlmostEqual(after - before, -1.2, delta=0.011)
        self.assertEqual(f.state()["positions"], [])
        rows = [x for x in f.orders_report(0) if x["type"] == "STOP_LOSS" and x["status"] == "EXECUTED"]
        self.assertEqual(len(rows), 1)
        self.assertLessEqual(rows[0]["executedPrice"], after)
        self.assertLess(rows[0]["executedPrice"], r["sl"] - 0.30)      # worse than the stop by more than barrel_gap
        titles = [a["title"] for a in f.state()["activity"]]
        self.assertIn("Stop loss filled", titles)
        g = f.sim_force("gap")
        self.assertTrue(0.40 <= abs(g["size"]) <= 1.50)

    def test_news_schedule_and_forced_news(self):
        f = feeds.SimFeed(seed=4, manual=True, start_ts=T_DAY)
        news = f.state()["news"]
        self.assertTrue(news)
        now = f.now()
        self.assertTrue(all(n["impact"] in ("high", "medium", "low") for n in news))
        self.assertFalse(any(n["impact"] == "high" and abs(n["t"] - now) < 30 * 60 for n in news))
        self.assertTrue(any(n["impact"] == "high" and now + 30 * 60 <= n["t"] <= now + 4 * 3600 for n in news))
        self.assertTrue(set(news[0]) >= {"t", "title", "impact", "country"})
        f.sim_force("calm", seconds=60)
        out = f.sim_force("news", minutes=1)
        self.assertTrue(any(n["t"] == out["t"] and n["impact"] == "high" for n in f.state()["news"]))
        f.advance(75)
        self.assertEqual(f.regime, "storm")                      # the forced event fired a spike

    def test_close_open_and_silence(self):
        f = feeds.SimFeed(seed=4, manual=True, start_ts=T_DAY)
        f.sim_force("close")
        s = f.state()
        self.assertEqual((s["ok"], s["reason"], s["market_open"]), (False, "market_closed", False))
        self.assertEqual(f.place(1, 0.01, 1, 9999)["error"], "MARKET_CLOSED")
        self.assertEqual(f.advance(10), [])
        f.sim_force("open")
        self.assertTrue(f.advance(5))
        self.assertTrue(f.state()["market_open"])
        f.sim_force("silence", seconds=30)
        self.assertEqual(f.advance(10), [])
        self.assertTrue(f.state()["ok"])                         # silent, not dead yet: feed_dead_s 15 counts from the last quote
        self.assertEqual(f.advance(10), [])
        self.assertEqual((f.state()["ok"], f.state()["reason"]), (False, "quotes stale"))
        self.assertTrue(f.advance(15))                           # the silence ends at 30 s
        self.assertTrue(f.state()["ok"])

    def test_threaded_run_uses_the_dispatcher(self):
        f = feeds.SimFeed(seed=1, speed=40.0, latency=None)
        names, types = set(), []

        def sub(ev):
            names.add(threading.current_thread().name)
            types.append(ev["type"])
        f.subscribe(sub)
        f.start()
        f.start()                                                # idempotent
        try:
            self.assertTrue(wait_for(lambda: types.count("quote") >= 20, 3.0))
            q = f.state()["quote"]
            r = f.place(1, 0.01, round(q["ask"] - 1, 2), round(q["ask"] + 1.2, 2))
            self.assertTrue(r["ok"])
            self.assertTrue(wait_for(lambda: "activity" in types))
        finally:
            f.stop()
        self.assertEqual(names, {"gg-sim-dispatch"})
        self.assertTrue(f.state()["positions"] or [x for x in f.orders_report(0) if x["side"] == "SELL"])

    def test_pump_on_a_never_started_feed_switches_to_manual(self):
        f = feeds.SimFeed(seed=3, latency=None)
        self.assertFalse(f.manual)
        self.assertEqual(len(f.pump(10)), 10)
        self.assertTrue(f.manual)
        with self.assertRaises(RuntimeError):
            f.start()

    def test_make_feed(self):
        self.assertIsInstance(feeds.make_feed("sim", seed=1, manual=True), feeds.SimFeed)
        with self.assertRaises(ValueError):
            feeds.make_feed("paper")


# =================================================================================================================================
class TestReplayFeed(unittest.TestCase):
    def write_recording(self, path, t0):
        rows = gen_rows(329, int(t0 // 60) * 60)
        lines = [
            (t0, "out", {"type": "REQUEST", "rid": 900001, "action": "bars",
                         "body": {"symbol": "XAU/USD", "bar_size": "1M", "to": int(t0), "limit": 329, "askOhlc": False}}),
            (t0 + 0.05, "in", {"type": "RESPONSE", "rid": 900001, "action": "bars", "body": {"data": rows}}),
            (t0 + 0.06, "out", {"type": "SUBSCRIPTION", "rid": 900002, "action": "bar",
                                "body": {"symbolId": 1019, "barSize": "1M", "askOhlc": False}}),
            (t0 + 0.10, "in", {"type": "RESPONSE", "rid": 900002, "action": "bar", "sid": 31,
                               "body": {"data": [int(t0 // 60) * 60, 3921.0, 3921.0, 3921.0, 3921.0, 1]}}),
            (t0 + 0.2, "in", fx(3926.38, 3926.71)),
            (t0 + 0.4, "in", fx(3926.45, 3926.78)),
            (t0 + 0.5, "in", METRICS),
            (t0 + 0.6, "in", positions_frame([P0_SHORT])),
            (t0 + 0.7, "in", act("Market order filled", "Buy 0.01 XAU/USD @ 3926.78")),
            (t0 + 0.8, "in", {"type": "GG_CALENDAR", "body": {"data": feeds.normalise_calendar(CAL)}}),
            (t0 + 0.9, "in", {"type": "EVENT", "action": "bar", "sid": 31, "body": {"data": [int(t0 // 60) * 60 + 60, 3926.45, 3926.5, 3926.4, 3926.45, 3]}}),
        ]
        with open(path, "w", encoding="utf-8") as fh:
            for t, d, frame in lines:
                fh.write(json.dumps({"t": t, "dir": d, "frame": frame}) + "\n")
            fh.write("garbage line\n")

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gg_replay_")
        self.path = os.path.join(self.tmp, "20261103_045000.jsonl")
        self.t0 = 1793670000.0
        self.write_recording(self.path, self.t0)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_play_all_through_the_live_parser(self):
        f = feeds.ReplayFeed(self.path, time_shift=0)
        self.assertFalse(f.can_trade)
        self.assertEqual(f.mode, "replay")
        f.play_all()
        s = f.state()
        self.assertEqual(len(s["bars"]), 331)
        self.assertEqual(s["bars"][-1][0], int(self.t0 // 60) * 60 + 60)
        self.assertEqual((s["quote"]["bid"], s["quote"]["ask"], s["tick_count"]), (3926.45, 3926.78, 2))
        self.assertEqual(s["positions"][0]["id"], 15391910)
        self.assertEqual(s["account"]["type"], "REPLAY")
        self.assertEqual(s["activity"][-1]["title"], "Market order filled")
        self.assertEqual(len(s["news"]), 3)
        self.assertEqual((s["ok"], s["reason"]), (False, "replay ended"))
        for r in (f.place(1, 0.01, 3925, 3928), f.set_protective(1, "STOP_LOSS", 3925), f.close(1, 0.01),
                  f.check_protective(1, 3925)):
            self.assertEqual((r["ok"], r["error"]), (False, "REPLAY"))
        self.assertEqual(list(f.orders_report(0)), [])

    def test_auto_time_shift_moves_bars_to_today(self):
        f = feeds.ReplayFeed(self.path)
        f.play_all()
        bars = f.state()["bars"]
        shift = bars[-1][0] - (int(self.t0 // 60) * 60 + 60)
        self.assertEqual(shift % 60, 0)
        self.assertLess(abs(bars[-1][0] - time.time()), 180)
        self.assertLess(abs(f.state()["news"][1]["t"] - shift - feeds.to_unix("2026-11-03T13:30:00Z")), 1e-6)

    def test_threaded_replay_at_speed(self):
        f = feeds.ReplayFeed(path=self.path, speed=20.0, time_shift=0)
        got = []
        f.subscribe(got.append)
        f.start()
        try:
            self.assertTrue(wait_for(lambda: f.finished, 3.0))
            self.assertTrue(wait_for(lambda: any(e["type"] == "feed" and e["reason"] == "replay ended" for e in got), 3.0))
        finally:
            f.stop()
        self.assertEqual(f.played, 11)
        self.assertTrue(any(e["type"] == "quote" for e in got))

    def test_looping_replay_counts_laps_and_never_ends(self):
        f = feeds.ReplayFeed(self.path, loop=True, time_shift=0)
        self.assertEqual(f.state()["replay_lap"], 0)
        f.play_all()
        s = f.state()
        self.assertEqual(s["replay_lap"], 1)
        self.assertFalse(f.finished)
        self.assertNotEqual(s["reason"], "replay ended")
        f2 = feeds.ReplayFeed(path=self.path, speed=40.0, time_shift=0, loop=True)
        f2.start()
        try:
            self.assertTrue(wait_for(lambda: f2.lap >= 2, 4.0))
            st = f2.state()
            self.assertTrue(st["ok"], st["reason"])
            self.assertGreaterEqual(st["replay_lap"], 2)
        finally:
            f2.stop()

    def test_inherited_sid_marker_maps_bar_events(self):
        path = os.path.join(self.tmp, "sid.jsonl")
        t = int(self.t0 // 60) * 60
        with open(path, "w", encoding="utf-8") as fh:
            for frame in ({"type": "GG_SID", "body": {"sid": 99, "symbolId": 1019, "barSize": "1M"}},
                          {"type": "EVENT", "action": "bar", "sid": 99, "body": {"data": [t, 1.0, 2.0, 0.5, 1.5, 3]}},
                          {"type": "EVENT", "action": "bar", "sid": 98, "body": {"data": [t + 60, 9.0, 9.0, 9.0, 9.0, 3]}}):
                fh.write(json.dumps({"t": self.t0, "dir": "in", "frame": frame}) + "\n")
        f = feeds.ReplayFeed(path, time_shift=0)
        f.play_all()
        self.assertEqual(f.state()["bars"], [[t, 1.0, 2.0, 0.5, 1.5, 3.0]])

    def test_recorder_round_trip(self):
        path = os.path.join(self.tmp, "rec.jsonl")
        rec = feeds.Recorder(path=path)
        rec.write("in", fx(3926.38, 3926.71), self.t0)
        rec.write("in", {"type": "EVENT", "action": "x", "body": {"u": "wss://api.primexbt.com/v2/fws/?accountId=l1"}}, self.t0 + 1)
        rec.close()
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("wss://", text)
        f = feeds.ReplayFeed(path, time_shift=0)
        f.play_all()
        self.assertEqual(f.state()["quote"]["bid"], 3926.38)


# =================================================================================================================================
class TestLiveFeedMoneySafety(unittest.TestCase):
    """Money-safety review of LiveFeed (2026-11-03): an uncertain send keeps a resolve token; the resolver needs our exact stop AND
    target; crossed stops / stale quotes are never sent; the account is pinned (listing, send, metrics, positions); the book is
    seeded and marked unknown after a reload; the report reads every page; the calendar uses /upcoming with the page's token."""

    def make(self, quote=(3928.95, 3929.28)):
        f = feeds.LiveFeed(config=CFG)
        f._ready = lambda: None
        f._on_frame(fx(*quote), "in")
        return f

    def test_a_socket_lost_after_the_send_is_uncertain_and_keeps_a_token(self):
        for code in ("PAGE_RELOADED", "SOCKET_CLOSED", "CDP_CLOSED"):
            f = self.make()
            broker = feeds.ShadowBroker(balance=25.0, pos_id0=15394511)
            broker.on_quote(3928.95, 3929.28)
            done = {}

            def sender(msg, f=f, code=code, broker=broker, done=done):
                if msg["action"] == "orders/market/place":
                    b = msg["body"]
                    done["pid"] = broker.place(1 if b["side"] == "BUY" else -1, b["qty"], b["stopLoss"]["price"],
                                               b["takeProfit"]["price"])["position_id"]
                    f._chan.fail_all(code)               # the server executed it, then the page reloaded before the reply
                else:
                    f._on_frame({"type": "RESPONSE", "rid": msg["rid"], "action": msg["action"], "body": {}}, "in")
            f._send_frame = sender
            f.resolve_s = 0.05
            r = f.place(1, 0.01, 3928.28, 3930.48, timeout=1.0)
            self.assertEqual((r["ok"], r["definite"], r.get("uncertain")), (False, False, True), code)
            self.assertTrue(r["error"].startswith(code))
            self.assertIn("resolve_token", r)
            ours = sub_position(done["pid"], "BUY", 0.01, 3929.28, 3929.0, sl=3928.28, tp=3930.48)
            f._on_frame(positions_frame([ours]), "in")
            self.assertEqual(f.resolve(r["resolve_token"], timeout=0.1)["position_id"], done["pid"])
            self.assertTrue(f.close(done["pid"], 0.01, timeout=0.2)["ok"])      # the game's own: never NOT_OURS

    def test_definite_answers_say_so_and_keep_no_token(self):
        f = self.make()

        def refuse(msg):
            f._on_frame({"type": "RESPONSE", "rid": msg["rid"], "action": msg["action"],
                         "error": {"code": "INSUFFICIENT_FUNDS", "description": "Not enough margin"}}, "in")
        f._send_frame = refuse
        r = f.place(1, 0.01, 3928.28, 3930.48)
        self.assertEqual((r["ok"], r["definite"], "resolve_token" in r), (False, True, False))
        self.assertTrue(f.place(1, 0.5, 3928.28, 3930.48)["definite"])                 # a local rail: nothing left
        self.assertEqual(len(f._tokens), 0)

    def test_the_resolver_needs_our_exact_stop_and_target(self):
        f = self.make()
        f._send_frame = lambda msg: None                          # the reply never comes; nothing executed
        r = f.place(1, 0.01, 3928.28, 3930.48, timeout=0.2)
        tok = r["resolve_token"]
        zee_nostop = sub_position(15400777, "BUY", 0.01, 3929.10, 3928.95)                          # Zee's hand trade, no stop
        zee_other = sub_position(15400778, "BUY", 0.01, 3929.10, 3928.95, sl=3928.28, tp=3940.00)   # our stop, another target
        f._on_frame(positions_frame([zee_nostop, zee_other]), "in")
        self.assertIsNone(f.resolve(tok, timeout=0.1)["position_id"])
        self.assertTrue(f.close(15400777, 0.01)["error"].startswith("NOT_OURS"))
        self.assertTrue(f.close(15400778, 0.01)["error"].startswith("NOT_OURS"))
        ours = sub_position(15400779, "BUY", 0.01, 3929.28, 3928.95, sl=3928.28, tp=3930.48)
        f._on_frame(positions_frame([zee_nostop, zee_other, ours]), "in")
        self.assertEqual(f.resolve(tok, timeout=0.1)["position_id"], 15400779)

    def test_the_resolver_refuses_a_position_opened_before_the_send(self):
        f = self.make()
        f._server_offset = 0.0                                    # the broker's clock is known
        f._send_frame = lambda msg: None
        r = f.place(1, 0.01, 3928.28, 3930.48, timeout=0.2)
        old = sub_position(15400780, "BUY", 0.01, 3929.28, 3928.95, sl=3928.28, tp=3930.48)
        old["openTime"] = feeds.iso_z(time.time() - 3600)         # an hour before our order left
        f._on_frame(positions_frame([old]), "in")
        self.assertIsNone(f.resolve(r["resolve_token"], timeout=0.1)["position_id"])

    def test_crossed_stops_targets_and_stale_quotes_are_never_sent(self):
        f = self.make(quote=(3926.00, 3927.20))                   # spread 1.20 = wider than a $1 stop
        sent = []
        f._send_frame = lambda msg: sent.append(msg)
        for args in ((1, 0.01, 3926.20, 3928.40), (-1, 0.01, 3927.00, 3925.00), (1, 0.01, 3925.00, 3927.10)):
            r = f.place(*args)                                    # long stop above the bid / short stop below the ask / TP inside
            self.assertTrue(r["error"].startswith("BAD_PROTECTIVE"), (args, r["error"]))
            self.assertTrue(r["definite"])
        f.adopt(15394511)
        f._on_frame(positions_frame([sub_position(15394511, "BUY", 0.01, 3926.59, 3926.00, sl=3925.0, tp=3928.0)]), "in")
        self.assertTrue(f.set_protective(15394511, "STOP_LOSS", 3926.10)["error"].startswith("BAD_PROTECTIVE"))
        self.assertTrue(f.set_protective(15394511, "TAKE_PROFIT", 3927.00)["error"].startswith("BAD_PROTECTIVE"))
        self.assertEqual(sent, [])
        g = self.make()
        g._quote = dict(g._quote, ts=time.time() - 10.0)          # the last quote is 10 s old
        self.assertTrue(g.place(1, 0.01, 3928.28, 3930.48)["error"].startswith("STALE_QUOTE"))
        h = feeds.LiveFeed(config=CFG)
        h._ready = lambda: None
        self.assertTrue(h.place(1, 0.01, 3928.28, 3930.48)["error"].startswith("NO_QUOTE"))

    def test_close_with_an_unknown_side_reads_no_fill_text(self):
        f = self.make()
        f.adopt(15500000)                                         # not in the book: its side is unknown

        def sender(msg):
            f._on_frame({"type": "RESPONSE", "rid": msg["rid"], "action": msg["action"], "body": {}}, "in")
            f._on_frame(act("Market order filled", "Sell 0.01 XAU/USD @ 3928.94"), "in")     # someone else's fill
        f._send_frame = sender
        r = f.close(15500000, 0.01)
        self.assertTrue(r["ok"])
        self.assertIsNone(r["fill_price"])

    def _attached(self):
        f = feeds.LiveFeed(config=CFG)
        f._started = True
        f._sess = type("S", (), {"alive": True})()
        f._fws_index, f._need_acquire = 1, False
        f._on_frame(fx(3928.95, 3929.28), "in")
        return f

    def test_metrics_of_another_account_stop_trading(self):
        f = self._attached()
        other = {"type": "EVENT", "action": "metrics", "body": dict(METRICS["body"], accountId="D7777777", balance=999.0)}
        f._on_frame(other, "in")
        s = f.state()
        self.assertIsNone(s["account"])                           # never shows another account's balance
        self.assertFalse(s["account_ok"])
        self.assertEqual((s["ok"], s["reason"]), (False, "another account is open in the page"))
        self.assertTrue(f.place(1, 0.01, 3928.28, 3930.48)["error"].startswith("WRONG_ACCOUNT"))

    def test_another_accounts_socket_and_positions_are_ignored(self):
        f = feeds.LiveFeed(config=CFG)
        f._on_cdp("Network.webSocketCreated", {"requestId": "other.9", "url": "wss://api.example/v2/fws/?accountId=d7777777&t=x"})
        f._on_cdp("Network.webSocketFrameReceived", {"requestId": "other.9", "response": {"opcode": 1, "payloadData":
                  json.dumps({"type": "EVENT", "action": "metrics", "body": dict(METRICS["body"], accountId="D7777777")})}})
        self.assertEqual(f.frames_in, 0)                          # that socket's frames are not read at all
        self.assertIsNone(f.state()["account"])
        theirs = positions_frame([sub_position(15400900, "BUY", 0.01, 3929.0, 3929.0, sl=3928.0, tp=3930.0)])
        for agg in theirs["body"]["data"]:
            agg["accountId"] = "D7777777"
            for sp in agg["subPositions"]:
                sp["accountId"] = "D7777777"
        f._on_frame(theirs, "in")
        self.assertEqual(f.state()["positions"], [])

    def test_a_reload_marks_the_book_unknown_until_the_page_answers(self):
        f = feeds.LiveFeed(config=CFG)
        ours = sub_position(15394511, "BUY", 0.01, 3926.59, 3926.40, sl=3925.59, tp=3927.79)
        f._on_frame(fx(3926.40, 3926.73), "in")
        f._on_frame(positions_frame([ours]), "in")
        self.assertTrue(f.state()["book_fresh"])
        f._on_cdp("Page.frameNavigated", {"frame": {"id": "main", "url": "https://primexbt.com/x"}})
        self.assertFalse(f.state()["book_fresh"])                 # the stop may have filled while the page reloaded
        f._on_frame({"type": "RESPONSE", "rid": 12, "action": "positions",
                     "body": {"accountId": "L1869984", "data": [], "positionMode": "HEDGE"}}, "in")
        s = f.state()
        self.assertTrue(s["book_fresh"])
        self.assertEqual(s["positions"], [])
        f._on_frame({"type": "RESPONSE", "rid": 13, "action": "metrics", "body": METRICS["body"]}, "in")
        self.assertEqual(f.state()["account"]["balance"], 0.63)

    def test_the_report_reads_every_page(self):
        f = self.make()

        def row(i):
            return {"id": i, "type": "MARKET", "status": "EXECUTED", "side": "BUY", "qty": 0.01, "executedPrice": 3926.0,
                    "executedQty": 0.01, "rpl": 0.0, "fee": 0, "positionId": 1000 + i, "closeReason": "EXECUTION",
                    "executedAt": "2026-11-03T04:47:10.120Z"}
        offsets = []

        def sender(msg):
            off = msg["body"]["offset"]
            offsets.append(off)
            data = [row(off + i) for i in range(100 if off == 0 else 5)]
            f._on_frame({"type": "RESPONSE", "rid": msg["rid"], "action": msg["action"], "body": {"data": data}}, "in")
        f._send_frame = sender
        rows = f.orders_report(0)
        self.assertTrue(rows.ok)
        self.assertEqual((len(rows), offsets), (105, [0, 100]))

        def flaky(msg):
            if msg["body"]["offset"] == 0:
                return sender(msg)
            f._on_frame({"type": "RESPONSE", "rid": msg["rid"], "action": msg["action"], "error": {"code": "X", "description": "y"}}, "in")
        f._send_frame = flaky
        self.assertFalse(f.orders_report(0).ok)                   # a partial report is not a report

    def test_seed_requests_fill_a_flat_account_and_book(self):
        page = FakePage()                                         # flat: the server never pushes metrics or positions
        f = feeds.LiveFeed(config=CFG, session_factory=lambda: page)
        try:
            f.start()
            self.assertTrue(wait_for(lambda: f.state()["account"] is not None and f.state()["book_fresh"], 5.0), f.state()["reason"])
            self.assertTrue({"positions", "metrics", "orders/active2"} <= {m["action"] for m in page.sent})
            s = f.state()
            self.assertEqual((s["account"]["id"], s["account_ok"], s["positions"]), ("L1869984", True, []))
            for listing in page.listed:                           # the socket listing never carried a url
                for sock in listing:
                    self.assertNotIn("url", sock)
        finally:
            f.stop()

    def test_the_page_holding_another_account_is_never_traded(self):
        page = FakePage()
        page.account = "d7777777"
        f = feeds.LiveFeed(config=CFG, session_factory=lambda: page)
        try:
            f.start()
            self.assertTrue(wait_for(lambda: f.state()["reason"] == "another account is open in the page", 5.0), f.state()["reason"])
            self.assertFalse(f.state()["account_ok"])
            self.assertTrue(f.place(1, 0.01, 3925.71, 3927.91)["error"].startswith("WRONG_ACCOUNT"))
            self.assertEqual(page.sent, [])
            page.account = "l1869984"                             # Zee switches the page back
            self.assertTrue(wait_for(lambda: f._fws_index == 1 and f.state()["account_ok"], 5.0))
        finally:
            f.stop()

    def test_a_send_on_a_socket_that_changed_account_never_leaves_the_page(self):
        page = FakePage()
        f = feeds.LiveFeed(config=CFG, session_factory=lambda: page)
        try:
            f.start()
            self.assertTrue(wait_for(lambda: len(f.state()["bars"]) >= 330 and f._fws_index == 1, 5.0), f.state()["reason"])
            page.tick(3926.38, 3926.71)
            self.assertTrue(wait_for(lambda: f.state()["ok"]))
            time.sleep(0.2)
            n = len([m for m in page.sent if m["action"] == "orders/market/place"])
            page.account = "d7777777"                             # same socket index, another account behind it
            r = f.place(1, 0.01, 3925.71, 3927.91)
            self.assertEqual((r["ok"], r["definite"]), (False, True))      # refused inside the page: nothing left
            self.assertEqual(len([m for m in page.sent if m["action"] == "orders/market/place"]), n)
            self.assertFalse(f.state()["account_ok"])
        finally:
            f.stop()

    def test_the_calendar_comes_from_upcoming_with_the_pages_own_token(self):
        page = FakePage()                                         # the fallback path: no chart to nudge, no XHR to replay
        f = feeds.LiveFeed(config=dict(CFG, calendar_nudge=False), session_factory=lambda: page)
        try:
            f.start()
            self.assertTrue(wait_for(lambda: len(f.state()["news"]) == 1, 5.0), f.state()["news"])
            n = f.state()["news"][0]
            self.assertEqual((n["title"], n["impact"], n["country"]), ("US CPI m/m", "high", "US"))   # Turkish CPI: not gold's
            for part in ("/economic-calendar/upcoming", "localStorage.getItem('prm-token')", "Authorization: 'Bearer ' + tok",
                         "importance: ['HIGH']"):
                self.assertIn(part, page.fetched)
        finally:
            f.stop()


if __name__ == "__main__":
    unittest.main(verbosity=2)
