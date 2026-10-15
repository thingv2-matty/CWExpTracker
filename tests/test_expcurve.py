"""
The experience curve against the datamined table.

Four formulas cover all 99 levels. The table is an independent transcription
from OSMS Data Explorer, kept so that a mistyped formula cannot pass unnoticed,
and so that re-mining after a balance patch says exactly which levels moved.
"""

import unittest

from exptracker import expcurve


class TestFormulas(unittest.TestCase):
    def test_reproduces_every_row_of_the_table(self):
        mismatched, unreconciled = expcurve.check_against_table()
        self.assertEqual(mismatched, [], "formula disagrees with the table")
        self.assertEqual(unreconciled, [], "table disagrees with itself")

    def test_the_seams_between_the_rules(self):
        # Each rule hands over to the next at a known value.
        self.assertEqual(expcurve.requirement(5), 135)
        self.assertEqual(expcurve.requirement(6), 372)
        self.assertEqual(expcurve.requirement(50), 709_716)
        self.assertEqual(expcurve.requirement(51), 748_608)
        self.assertEqual(expcurve.requirement(89), 5_684_790)

    def test_the_level_ninety_wall(self):
        # The last ten levels are 99.4% of the whole climb to cap.
        to_90 = sum(expcurve.requirement(lv) for lv in range(1, 90))
        to_cap = sum(expcurve.requirement(lv) for lv in range(1, 100))
        self.assertGreater((to_cap - to_90) / to_cap, 0.99)

    def test_a_level_below_one_is_an_error(self):
        with self.assertRaises(ValueError):
            expcurve.requirement(0)


class TestIdentify(unittest.TestCase):
    def test_a_real_reading(self):
        self.assertEqual(expcurve.identify(3810, 8.07), [25])

    def test_unique_from_a_tenth_of_a_percent(self):
        # The blind spot is only the first tick or two of a new level.
        for level in (10, 25, 50, 90):
            value = int(round(expcurve.requirement(level) * 0.001))
            percent = expcurve.shown_percent(value, level)
            self.assertEqual(expcurve.identify(value, percent), [level],
                             "level %d was not unique at 0.1%%" % level)

    def test_zero_fits_every_level(self):
        self.assertEqual(len(expcurve.identify(0, 0.0)), expcurve.MAX_LEVEL)


if __name__ == "__main__":
    unittest.main()
