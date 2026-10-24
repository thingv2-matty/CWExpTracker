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
def minutes_long(count):
    """A session of a given length, grinding steadily throughout."""
    return grinding(25, 0.02, [(count, 400)])


class TestScreenTime(unittest.TestCase):
    def test_silent_until_something_actually_fits(self):
        shortest = min(run for _name, run in facts.WATCHABLE)
        self.assertIsNone(facts._screen_time(minutes_long(shortest - 10), []))

    def test_never_offers_a_count_of_zero(self):
        for count in range(20, 400, 7):
            text = facts._screen_time(minutes_long(count), [])
            if text:
                self.assertNotIn("zero", text)
                self.assertNotIn(" 0 times", text)

    def test_the_count_is_honest(self):
        """Whatever it names, the session has to be that many runtimes long."""
        for count in (95, 150, 400, 900):
            session = minutes_long(count)
            text = facts._screen_time(session, [])
            if not text:
                continue
            name = next(n for n, _r in facts.WATCHABLE if n in text)
            runtime = dict(facts.WATCHABLE)[name]
            said = _count_in(text)
            self.assertLessEqual(runtime * said, session.elapsed / 60.0 + 1)

    def test_runtimes_are_plausible(self):
        for name, runtime in facts.WATCHABLE:
            self.assertGreater(runtime, 60, name)
            self.assertLess(runtime, 100 * 60, name)


class TestLongAs(unittest.TestCase):
    def test_the_comparison_is_near_enough_to_be_true(self):
        low, high = facts.NEAR_ENOUGH
        spans = {what: span for span, what in facts.LONG_AS}
        for count in range(20, 800, 11):
            text = facts._as_long_as(minutes_long(count), [])
            if not text:
                continue
            what = next(w for w in spans if w in text)
            elapsed = minutes_long(count).elapsed / 60.0
            self.assertTrue(spans[what] * low <= elapsed <= spans[what] * high,
                            "%d min matched %r (%d min)"
                            % (count, what, spans[what]))

    def test_every_entry_reads_as_a_sentence(self):
        """Each entry is dropped into "how long it takes ___." as written."""
        for _span, what in facts.LONG_AS:
            self.assertFalse(what.startswith("to "), what)
            self.assertNotIn("  ", what)
            self.assertNotIn(what[-1], ".!?", what)

    def test_entries_are_in_order(self):
        """Kept sorted so a gap in the coverage is visible by eye."""
        spans = [span for span, _what in facts.LONG_AS]
        self.assertEqual(spans, sorted(spans))


class TestEasterEggs(unittest.TestCase):
    def test_sixty_nine_percent_gained(self):
        session = _grind_until(lambda s: s.percent_gained >= 69.0)
        self.assertEqual(facts.pick(session, session.segments(600)),
                         "You gained 69%%, nice %s" % facts.NICE)

    def test_sixty_nine_percent_standing(self):
        session = _grind_until(lambda s: s.percent >= 69.0, start=0.40)
        self.assertEqual(facts.pick(session, session.segments(600)),
                         "You finished off at 69%%, nice %s" % facts.NICE)

    def test_it_beats_the_ordinary_facts(self):
        """The whole point: an egg shown one time in ten is not an egg."""
        session = _grind_until(lambda s: s.percent_gained >= 69.0)
        segments = session.segments(600)
        self.assertTrue(offered(session), "nothing else applied, so this proves nothing")
        for _ in range(50):
            self.assertIn("nice", facts.pick(session, segments))

    def test_seventy_is_not_nice(self):
        session = _grind_until(lambda s: s.percent_gained >= 70.0)
        self.assertNotIn("nice", facts.pick(session, session.segments(600)) or "")

    def test_sixty_eight_is_not_nice(self):
        session = _grind_until(lambda s: s.percent_gained >= 68.0)
        self.assertNotIn("nice", facts.pick(session, session.segments(600)) or "")


def _count_in(text):
    words = {"once": 1, "twice": 2, "three": 3}
    for word, count in words.items():
        if word in text:
            return count
    return int([w for w in text.split() if w.isdigit()][0])


def _grind_until(reached, start=0.02):
    """Tick experience in small steps and stop the moment a band is entered.

    Walking up in small steps rather than jumping matters: the session refuses
    an implausible leap as a misread, so a single large update never lands.
    """
    session = Session()
    session.banked = 0.0
    requirement = expcurve.requirement(25)
    value = int(requirement * start)
    session.update(value, SHOWN(value, 25))
    session.adopt_level(25)
    session.value = value

    level = 25
    for _ in range(100000):
        if reached(session):
            return session
        value += requirement // 400
        session.banked += 2.0
        if value >= expcurve.requirement(level):
            value -= expcurve.requirement(level)
            level += 1
        session.update(value, SHOWN(value, level))
    raise AssertionError("the band was never reached")

if __name__ == "__main__":
    unittest.main()
