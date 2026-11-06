"""diamond.py - Zee's UHV Diamond read as a hint (2026-11-04). Synthetic bars only: an uptrend in camel humps, a red retracement with one
loud candle (the UHV), then a green breakout. Each test changes one thing and checks the reading follows his LAWS.md."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import diamond as D  # noqa: E402

T0 = 1_800_000_000 - 1_800_000_000 % 900


def make(legs, start=100.0):
    bars, p, t = [], start, T0
    for steps, dv, vols in legs:
        for i in range(steps):
            o, c = p, p + dv
            if dv == 0:
                c = o + (0.01 if len(bars) % 2 else -0.01)
            hi = c + 0.05 if c >= o else o + 0.01
            lo = o - 0.01 if c >= o else c - 0.05
            bars.append([t, o, hi, lo, c, vols[i] if isinstance(vols, list) else vols])
            p, t = c, t + 60
    bars.append([t, p, p, p, p, 1])                            # the forming bar
    return bars


TREND = [(14, 0.0, 10)] + [(4, 1.0, 10), (3, -0.8, 10)] * 2 + [(4, 1.0, 10)]


def read(bars, unit=1.0):
    d = D.Diamond(unit=unit)
    return d, d.update(bars, lambda b: b[5], bars[-1][0] + 5)


class DiamondTest(unittest.TestCase):
    def test_breakout_cuts_the_diamond(self):
        d, r = read(make(TREND + [(3, -0.8, [10, 40, 12]), (1, 2.6, [20])]))
        self.assertEqual(r["camel"], 1)
        self.assertEqual(r.get("cut"), 1)                      # green breakout closed above the UHV's high, quieter than it
        self.assertEqual(r["laws"], 3)
        self.assertFalse(r["royal"])                           # no 15-minute history yet: never royal by default

    def test_waiting_for_the_breakout_is_rough(self):
        # 2026-11-05: the side now comes from Zee's Pine camel humps (Turtle TV UHV's detector): a hump is low -> high -> next low, so
        # with the retracement's own low not confirmed yet it needs one more completed hump than TREND gives
        trend3 = [(14, 0.0, 10)] + [(4, 1.0, 10), (3, -0.8, 10)] * 3 + [(4, 1.0, 10)]
        d, r = read(make(trend3 + [(3, -0.8, [10, 40, 12])]))
        self.assertEqual(r.get("rough"), 1)
        self.assertNotIn("cut", r)

    def test_a_loud_breakout_is_not_his(self):
        d, r = read(make(TREND + [(3, -0.8, [10, 40, 12]), (1, 2.6, [50])]))   # LAWS.md (b): the breakout must be quieter than the UHV
        self.assertNotIn("cut", r)

    def test_the_tired_camel_still_shows_but_never_royal(self):
        legs = [(14, 0.0, 10)] + [(4, 1.0, 10), (3, -0.8, 10)] * 4 + [(4, 1.0, 10), (3, -0.8, [10, 40, 12]), (1, 2.6, [20])]
        d, r = read(make(legs))
        self.assertGreaterEqual(r["humps"], D.MAX_HUMPS)        # hump 4 "hmm maybe it shifts": the budget is spent
        self.assertEqual(r.get("cut"), 1)                      # Zee: every qualifying setup shows its diamond...
        self.assertFalse(r["ea"])                              # ...but the EA would not have taken it,
        self.assertFalse(r["royal"])                           # so it can never be royal

    def test_missing_volume_means_no_judgement(self):
        bars = make(TREND + [(3, -0.8, [10, 40, 12]), (1, 2.6, [20])])
        d = D.Diamond()
        r = d.update(bars, lambda b: None if b is bars[-3] else b[5], bars[-1][0] + 5)
        self.assertNotIn("cut", r)

    def test_shatters_back_through_the_retracement(self):
        bars = make(TREND + [(3, -0.8, [10, 40, 12]), (1, 2.6, [20])])
        d, r = read(bars)
        self.assertEqual(r.get("cut"), 1)
        r2 = d.reading(bars[-1][0] + 20, price=d.cut["extreme"] - 0.5)
        self.assertTrue(r2.get("shattered"))

    def test_late_history_is_replayed(self):
        """The live feed may hand over its 330-bar history after the first live bars: the reader starts again on the whole of it."""
        bars = make([(40, 0.0, 10)] + TREND[1:] + [(3, -0.8, [10, 40, 12]), (1, 2.6, [20])])   # 40 quiet minutes of history in front
        d = D.Diamond()
        d.update(bars[-30:], lambda b: b[5], bars[-1][0] + 5)       # only the newest 29 closed bars at first
        r = d.update(bars, lambda b: b[5], bars[-1][0] + 5)         # then the full history arrives
        fresh, rf = read(bars)
        self.assertEqual(d.first_t, bars[0][0])                     # it started again from the oldest bar
        self.assertEqual((d.hump_dir, d.hump_n), (fresh.hump_dir, fresh.hump_n))
        self.assertEqual(r.get("cut"), rf.get("cut"))

    def test_no_sell_diamond_against_the_camel(self):
        """Zee: "we also need the camel humps first". In the camel's uptrend a green pullback with a loud candle and a red break below it
        is NOT a sell setup - no diamond, no stone for the sell side."""
        legs = TREND + [(3, -0.8, 10), (4, 0.9, 10), (3, 0.3, [10, 40, 12]), (1, -2.4, [20])]
        d, r = read(make(legs))
        self.assertEqual(r["camel"], 1)
        self.assertNotEqual(r.get("cut"), -1)
        self.assertNotEqual(r.get("rough"), -1)

    def test_line_45_ends_the_trend(self):
        """His line 45: once the last low breaks, buying stops - the camel stops walking and no buy diamond is cut on that bounce."""
        legs = TREND + [(6, -1.2, 10), (3, -0.8, [10, 40, 12]), (1, 2.6, [20])]
        d, r = read(make(legs))
        self.assertNotEqual(r["camel"], 1)
        self.assertNotEqual(r.get("cut"), 1)

    def test_a_slow_slide_is_not_a_buy_retracement(self):
        """No impulse ended at the window's high (price only slid down from it): no buy retracement, no buy stone, no diamond."""
        legs = [(14, 0.0, 10), (24, -0.3, 10), (1, 2.5, [5])]
        d, r = read(make(legs))
        self.assertNotIn("cut", r)
        self.assertNotEqual(r.get("rough"), 1)                 # (the green bar itself starts a SELL retracement - that stone is right)

    def test_royal_needs_the_ea_and_a_clean_15_minutes(self):
        """A steady 5-hour climb (15-minute ER = 1) and then the EA's own setup on the camel's side: royal."""
        legs = [(300, 0.05, 10)] + TREND[1:] + [(3, -0.8, [10, 40, 12]), (1, 2.6, [20])]
        d, r = read(make(legs))
        self.assertEqual(r.get("cut"), 1)
        self.assertTrue(r["ea"])
        self.assertTrue(r["clean"])
        self.assertTrue(r["royal"])

    def test_efficiency_ratio(self):
        self.assertAlmostEqual(D.efficiency_ratio([float(i) for i in range(17)]), 1.0)
        self.assertAlmostEqual(D.efficiency_ratio([0.0, 1.0] * 8 + [0.0]), 0.0)
        bars = [[T0 + i * 60, 1, 1, 1, float(i), 1] for i in range(60)]
        self.assertEqual(D.m15_closes(bars, T0 + 60 * 60), [14.0, 29.0, 44.0, 59.0])
        self.assertEqual(D.m15_closes(bars, T0 + 59 * 60), [14.0, 29.0, 44.0])   # the bucket still forming is not a candle yet


if __name__ == "__main__":
    unittest.main()
