"""
Every case the session has got wrong at some point.

The level up cases are the ones worth guarding. Time to level used to collapse
to "--" on levelling and stay there, because the requirement was being derived
from a handful of experience at a fraction of a percent, which gave forty
thousand where the real answer was forty seven thousand.
"""

import unittest

from exptracker import expcurve
from exptracker.session import Session, parse

SHOWN = expcurve.shown_percent


def grinding(level, value, minutes=30):
    """A session already part way through a level, with time on the clock."""
    session = Session()
    session.banked = minutes * 60.0
    session.update(value, SHOWN(value, level))
    return session


class TestParse(unittest.TestCase):
    def test_reads_a_normal_strip(self):
        self.assertEqual(parse("13,573[67.14%]"), (13573, 67.14))

    def test_reads_a_short_strip(self):
        self.assertEqual(parse("835[1.14%]"), (835, 1.14))

    def test_accepts_a_fresh_level(self):
        # 0 at 0.00% is a real reading. Rejecting it here used to make the
        # level-up handling for that case unreachable from the live app.
        self.assertEqual(parse("0[0.00%]"), (0, 0.0))

    def test_rejects_an_unreadable_value(self):
        # Searching forward for the pattern used to skip the bad digit and
        # match the rest, turning 1?,306 into a confident 306.
        self.assertIsNone(parse("1?,306[60.87%]"))
        self.assertIsNone(parse("?306[60.87%]"))
        self.assertIsNone(parse("1?306[60.87%]"))
        self.assertIsNone(parse("13,57?[67.14%]"))

    def test_rejects_an_unreadable_percent(self):
        self.assertIsNone(parse("13,573[6?.14%]"))

    def test_rejects_an_impossible_percent(self):
        self.assertIsNone(parse("100[101.00%]"))


class TestLevelIdentification(unittest.TestCase):
    def test_pins_down_a_level(self):
        self.assertEqual(expcurve.identify_one(3810, 8.07), 25)
        self.assertEqual(expcurve.identify_one(13573, 67.14), 20)

    def test_declines_when_a_reading_fits_several_levels(self):
        # A handful of experience at 0.03% genuinely could be several levels.
        self.assertIsNone(expcurve.identify_one(12, 0.03))

    def test_a_session_adopts_the_level_it_identifies(self):
        session = grinding(25, 3810)
        self.assertEqual(session.level, 25)
        self.assertEqual(session.requirement, expcurve.requirement(25))


class TestLevellingUp(unittest.TestCase):
    def setUp(self):
        self.session = grinding(20, 13573)
        value = 13573
        while value < expcurve.requirement(20) - 150:
            value += 137
            self.session.update(value, SHOWN(value, 20))
        self.rate_before = self.session.per_hour

    def test_advances_and_the_requirement_is_exact(self):
        self.assertTrue(self.session.update(12, SHOWN(12, 21)))
        self.assertEqual(self.session.level, 21)
        self.assertEqual(self.session.requirement, expcurve.requirement(21))
        self.assertEqual(self.session.levels, 1)

    def test_time_to_level_survives_the_boundary(self):
        self.session.update(12, SHOWN(12, 21))
        self.assertIsNotNone(self.session.to_level)

    def test_the_rate_carries_rather_than_resetting(self):
        self.session.update(12, SHOWN(12, 21))
        drift = abs(self.session.per_hour - self.rate_before) / self.rate_before
        self.assertLess(drift, 0.05)

    def test_landing_exactly_on_the_boundary(self):
        session = grinding(20, 20100)
        session.update(20200, SHOWN(20200, 20))
        self.assertTrue(session.update(0, 0.0))
        self.assertEqual(session.level, 21)


class TestDeaths(unittest.TestCase):
    def test_a_normal_five_percent_death(self):
        session = grinding(21, 12000)
        after = 12000 - int(round(expcurve.requirement(21) * 0.05))
        self.assertTrue(session.update(after, SHOWN(after, 21)))

    def test_a_death_that_empties_the_bar(self):
        # Dying early in a level cannot take five percent, because there is not
        # five percent there to take.
        session = grinding(21, 400)
        self.assertTrue(session.update(0, 0.0))
        self.assertEqual(session.level, 21, "an emptied bar is not a level up")

    def test_an_impossible_loss_is_refused(self):
        session = grinding(21, 12000)
        after = 12000 - int(round(expcurve.requirement(21) * 0.17))
        self.assertFalse(session.update(after, SHOWN(after, 21)))


class TestMisreads(unittest.TestCase):
    def setUp(self):
        self.session = grinding(20, 13573)

    def test_value_and_percent_disagreeing(self):
        self.assertFalse(self.session.update(99999, 50.0))

    def test_a_percent_impossible_for_that_value(self):
        self.assertFalse(self.session.update(13580, 99.99))

    def test_an_implausible_jump(self):
        jump = 13573 + int(expcurve.requirement(20) * 0.2)
        self.assertFalse(self.session.update(jump, SHOWN(jump, 20)))

    def test_a_refused_reading_never_moves_the_baseline(self):
        self.session.update(99999, 50.0)
        self.session.update(13580, 99.99)
        self.assertEqual(self.session.value, 13573)


class TestTotals(unittest.TestCase):
    def test_gained_is_a_flat_total_across_levels(self):
        """Three level ups should report the real total, not a per-level figure."""
        session = grinding(20, 13573)
        level, value, refused = 20, 13573, 0
        while level < 23 or value < 5000:
            value += 137
            if value >= expcurve.requirement(level):
                value -= expcurve.requirement(level)
                level += 1
            if not session.update(value, SHOWN(value, level)):
                refused += 1

        expected = ((expcurve.requirement(20) - 13573)
                    + expcurve.requirement(21)
                    + expcurve.requirement(22)
                    + value)
        self.assertEqual(refused, 0)
        self.assertEqual(session.levels, 3)
        self.assertEqual(int(session.gained), expected)


class TestGrindingRate(unittest.TestCase):
    """Percent of the current level per minute, which is how a spot is judged."""

    def setUp(self):
        self.session = grinding(25, 3810, minutes=10)
        value = 3810
        for _ in range(30):
            value += 140
            self.session.update(value, SHOWN(value, 25))

    def test_matches_the_long_way_round(self):
        expected = ((self.session.gained / self.session.requirement * 100)
                    / (self.session.elapsed / 60))
        self.assertAlmostEqual(self.session.percent_per_minute, expected, places=6)

    def test_none_before_the_level_is_known(self):
        self.assertIsNone(Session().percent_per_minute)

    def test_falls_as_the_level_gets_longer(self):
        """The same experience per hour is worth less at a higher level."""
        before = self.session.percent_per_minute
        self.session.adopt_level(40)
        self.assertLess(self.session.percent_per_minute, before)


class TestIdleDetection(unittest.TestCase):
    """Time since experience last went UP, which is not the same as time since
    the last believed reading: sitting in town reads fine and earns nothing."""

    def test_unknown_before_anything_is_earned(self):
        self.assertIsNone(Session().idle_for())

    def test_a_gain_resets_it(self):
        session = grinding(25, 3810)
        session.update(3950, SHOWN(3950, 25))
        self.assertLess(session.idle_for(), 1.0)

    def test_a_reading_with_no_gain_does_not_reset_it(self):
        session = grinding(25, 3810)
        session.update(3950, SHOWN(3950, 25))
        session.last_gain -= 120
        session.update(3950, SHOWN(3950, 25))        # same value, still believed
        self.assertGreater(session.idle_for(), 100)


class TestHighLevels(unittest.TestCase):
    def test_a_few_points_do_not_move_the_percent(self):
        self.assertEqual(SHOWN(5000, 90), 0.04)

    def test_level_ninety_is_identified(self):
        self.assertEqual(grinding(90, 5000).level, 90)


if __name__ == "__main__":
    unittest.main()
