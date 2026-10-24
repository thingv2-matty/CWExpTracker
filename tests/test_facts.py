"""
The recap's closing line should not be a kick in the teeth.

It appears at the end of a session, which is often right after a level up, and
that is exactly when a forward-looking number is at its worst: the whole bar is
ahead of you. Matt levelled after a long slog and the tracker told him the next
one was five hours away.

So: backward-looking facts are always safe, and forward-looking ones have to
earn their place.
"""

import unittest

from exptracker import expcurve
from exptracker.session import Session
from exptracker.ui import facts

SHOWN = expcurve.shown_percent


def grinding(level, start_fraction, plan):
    """plan is a list of (minutes, experience per minute)."""
    session = Session()
    session.banked = 0.0
    start = int(expcurve.requirement(level) * start_fraction)
    session.update(start, SHOWN(start, level))
    session.adopt_level(level)
    session.value = start

    value, current = start, level
    for minutes, per_minute in plan:
        for _ in range(minutes * 4):
            value += per_minute // 4
            session.banked += 15.0
            if value >= expcurve.requirement(current):
                value -= expcurve.requirement(current)
                current += 1
            session.update(value, SHOWN(value, current))
    return session


def offered(session):
    segments = session.segments(600)
    return [text for text in (f(session, segments) for f in facts.ALL) if text]


class TestNothingDemoralising(unittest.TestCase):
    def test_no_time_to_level_just_after_levelling(self):
        """The reported bug: a five hour wall, shown as a reward."""
        session = grinding(40, 0.90, [(30, 900)] * 4)
        self.assertLess(session.percent, facts.NEARLY_THERE)
        for text in offered(session):
            self.assertNotIn("next level lands", text)

    def test_time_to_level_returns_when_the_end_is_in_sight(self):
        session = grinding(25, 0.62, [(10, 300)])
        self.assertGreaterEqual(session.percent, facts.NEARLY_THERE)
        self.assertTrue(any("next level lands" in t for t in offered(session)))

    def test_a_distant_goal_is_not_offered(self):
        """At a high level the next round number is hundreds of hours away.
        That stops being a goal and becomes a sentence."""
        session = grinding(60, 0.1, [(20, 900)])
        for text in offered(session):
            self.assertNotIn("arrives in", text)

    def test_something_is_always_offered(self):
        """Tightening the guards must not leave the recap with nothing to say."""
        for level, fraction, plan in (
            (40, 0.90, [(30, 900)] * 4),      # just levelled
            (25, 0.10, [(10, 600)] * 4),      # steady
            (25, 0.10, [(10, 620), (10, 140), (10, 600)]),   # drifted
            (25, 0.50, [(5, 400)]),           # short session
        ):
            session = grinding(level, fraction, plan)
            self.assertTrue(offered(session),
                            "no fact for level %d at %.0f%%"
                            % (level, fraction * 100))


class TestFramings(unittest.TestCase):
    def test_the_ceiling_is_not_phrased_as_a_shortfall(self):
        session = grinding(25, 0.1, [(10, 620), (10, 140), (10, 600)])
        texts = offered(session)
        self.assertTrue(any("what this spot has in it" in t for t in texts))
        for text in texts:
            self.assertNotIn("would have been another", text)

    def test_the_variance_line_carries_no_editorial(self):
        session = grinding(25, 0.1, [(10, 620), (10, 140), (10, 600)])
        for text in offered(session):
            self.assertNotIn("Something happened", text)

    def test_consistency_gets_credit(self):
        session = grinding(25, 0.1, [(10, 600), (10, 605), (10, 598)])
        self.assertTrue(any("within" in t and "average" in t
                            for t in offered(session)))


class TestMobArithmetic(unittest.TestCase):
    def test_counts_are_real_division(self):
        session = grinding(25, 0.1, [(10, 600)])
        for name, each in facts.MOBS:
            self.assertGreater(each, 0, "%s has no experience value" % name)
        self.assertIn(("snails", 3), facts.MOBS)


if __name__ == "__main__":
    unittest.main()
