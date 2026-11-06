"""Zee 2026-11-04: in live mode EUR/USD read 1.12000 / 1.12000 (spread 0) - the 5-decimal grid reached the practice feed only, so the
live feed rounded every quote to gold's 2 decimals. build_engine must put EVERY feed on the symbol's grid. (Replay stands in for live:
the live feed may never be built in a test.)"""
import glob
import os
import shutil
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ.setdefault("GG_FORBID_LIVE", "1")
import admin  # noqa: E402
import feeds  # noqa: E402
import server  # noqa: E402


class PriceGrid(unittest.TestCase):
    def test_every_feed_gets_the_symbols_grid(self):
        rec = sorted(glob.glob(os.path.join(HERE, "recordings", "*.jsonl")))
        if not rec:
            self.skipTest("no recording to replay")
        root = tempfile.mkdtemp(prefix="gg_test_grid_")
        try:
            os.makedirs(os.path.join(root, "state"))
            data = admin.defaults()
            data["active"] = "EURUSD"
            admin.save(server.state_dir_of(root), data)
            feeds.configure_price(2)
            args = types.SimpleNamespace(mode="replay", seed=7, speed=1.0, file=rec[0], record=False, real_hours=False)
            eng = server.build_engine(args, root)
            self.assertEqual(feeds.PX_DP, 5)
            self.assertEqual(feeds.r2(1.123456), 1.12346)
            eng.feed.stop() if hasattr(eng.feed, "stop") else None
        finally:
            feeds.configure_price(2)
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
