"""
The idle pause, and the refund that makes a long fuse affordable.

The clock stopping is a guess about whether the grinding stopped, and the guess
is made two minutes late. Handing most of that back is what lets the fuse be
long enough for a party quest stage without a real stop landing two minutes off.
"""

import unittest

from exptracker import expcurve
from exptracker.session import Session

SHOWN = expcurve.shown_percent
LEVEL = 25


# Readings are refused above this, so a test that gains more than it in one
# step is testing the misread guard rather than whatever it meant to test.
STEP = int(expcurve.requirement(LEVEL) * 0.05)


def session_at(fraction, elapsed):
    """A session holding a reading, with a given amount of time on the clock."""
    s = Session()
    s.banked = float(elapsed)
    value = int(expcurve.requirement(LEVEL) * fraction)
    s.update(value, SHOWN(value, LEVEL))
    s.adopt_level(LEVEL)
    s.value = value
    return s


def gain(s, steps=1):
    """Earn some experience, in increments the session will believe."""
    for _ in range(steps):
        value = s.value + STEP
        assert s.update(value, SHOWN(value, LEVEL)), "the guard refused a step"


class TestRewind(unittest.TestCase):
    def test_it_takes_the_time_off_the_clock(self):
        s = session_at(0.1, 600)
        given = s.rewind(110)
        self.assertAlmostEqual(given, 110, places=3)
        self.assertAlmostEqual(s.elapsed, 490, places=3)

    def test_it_will_not_wind_back_past_the_last_reading(self):
        """History is keyed on elapsed, so a reading must never end up ahead
        of the clock: the rolling window and the recap blocks both read it."""
        s = session_at(0.1, 600)
        s.banked = 650.0
        gain(s)                                   # recorded at elapsed 650
        s.banked = 700.0
        given = s.rewind(600)
        self.assertAlmostEqual(given, 50, places=3)
        self.assertAlmostEqual(s.elapsed, 650, places=3)
        self.assertGreaterEqual(s.elapsed, s.history[-1][0])

    def test_a_rewind_of_nothing_does_nothing(self):
        s = session_at(0.1, 600)
        self.assertEqual(s.rewind(0), 0.0)
        self.assertEqual(s.rewind(-30), 0.0)
        self.assertAlmostEqual(s.elapsed, 600, places=3)

    def test_it_never_drives_the_clock_negative(self):
        s = Session()
        s.banked = 20.0
        s.rewind(500)
        self.assertGreaterEqual(s.elapsed, 0)

    def test_the_history_still_lines_up_afterwards(self):
        """Whatever rewind does, segments must still cover the session."""
        s = session_at(0.02, 0)
        for step in range(1, 10):
            s.banked = step * 60.0
            gain(s)
        s.banked = 9 * 60.0 + 120
        s.rewind(110)
        blocks = s.segments(120)
        self.assertTrue(blocks)
        self.assertAlmostEqual(sum(b["gained"] for b in blocks), s.gained,
                               delta=1)
        for block in blocks:
            self.assertLessEqual(block["from"], s.elapsed)


class TestWhatTheRefundIsWorth(unittest.TestCase):
    """The numbers Matt asked for: a two minute fuse costing ten seconds."""

    FUSE = 120
    GRACE = 10

    def test_a_false_alarm_costs_only_the_grace(self):
        s = session_at(0.1, 1000)
        s.pause()
        given = s.rewind(self.FUSE - self.GRACE)
        self.assertAlmostEqual(given, 110, places=3)
        self.assertAlmostEqual(s.elapsed, 1000 - 110, places=3)

    def test_a_late_tick_still_refunds_the_whole_stall(self):
        """The loop can run late, so the stall may be longer than the fuse.
        The refund follows the measured stall, not the constant."""
        s = session_at(0.1, 1000)
        s.pause()
        measured_stall = 180
        given = s.rewind(measured_stall - self.GRACE)
        self.assertAlmostEqual(given, 170, places=3)

    def test_the_rate_improves_once_the_dead_time_is_given_back(self):
        s = session_at(0.02, 0)
        s.banked = 600.0
        gain(s)
        s.banked = 600.0 + self.FUSE
        dragged = s.per_hour
        s.pause()
        s.rewind(self.FUSE - self.GRACE)
        self.assertGreater(s.per_hour, dragged)


if __name__ == "__main__":
    unittest.main()
