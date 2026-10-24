"""
Teaching has to actually take.

The failure this guards against is specific and it survived a long time: a
sample filed under the wrong character sat close enough to veto the right one,
but not close enough to be displaced by teaching. Every lesson added another
correct sample for the stray to veto, so the character stayed unreadable no
matter how many times it was taught.
"""

import unittest

import numpy as np

from exptracker import templates as T
from exptracker.models import CharacterModels
from exptracker.reader import Reader


def shape(rows):
    return np.array([[c == "#" for c in row] for row in rows], dtype=bool)


# An 8x8 digit, and the same digit with two pixels moved. Two pixels of 64 is
# 0.031: inside MARGIN, so they veto each other, but outside IDENTICAL, so the
# old displacement rule left the pair in place.
TWO = shape([
    ".######.",
    "##....##",
    "......##",
    ".....##.",
    "...###..",
    ".###....",
    "##......",
    "########",
])
TWO_NUDGED = shape([
    ".######.",
    "##....##",
    "......##",
    ".....##.",
    "...###..",
    ".###...#",
    "##.....#",
    "########",
])


class TestTheDistanceMatters(unittest.TestCase):
    def test_the_pair_is_in_the_gap_that_used_to_be_missed(self):
        apart = T.slide_compare(TWO, TWO_NUDGED)
        self.assertGreater(apart, T.IDENTICAL, "too close; nothing to prove")
        self.assertLess(apart, T.MARGIN, "too far apart to veto")

    def test_two_characters_that_close_veto_each_other(self):
        poisoned = {"2": [TWO], "1": [TWO_NUDGED]}
        self.assertIsNone(T.match(TWO, poisoned))
        self.assertIsNone(T.match(TWO_NUDGED, poisoned))


class TestTeachingClearsTheVeto(unittest.TestCase):
    def test_one_lesson_displaces_the_blocker(self):
        poisoned = {"2": [TWO], "1": [TWO_NUDGED]}
        added, displaced = T.learn(poisoned, "2", TWO)
        self.assertEqual(displaced, 1)
        self.assertEqual(T.match(TWO, poisoned), "2")

    def test_teaching_does_not_quietly_do_nothing(self):
        """The reported symptom: taught over and over, still unreadable."""
        poisoned = {"2": [TWO], "1": [TWO_NUDGED]}
        for _ in range(5):
            T.learn(poisoned, "2", TWO)
        self.assertEqual(T.match(TWO, poisoned), "2")

    def test_a_character_emptied_of_samples_is_dropped(self):
        poisoned = {"2": [TWO], "1": [TWO_NUDGED]}
        T.learn(poisoned, "2", TWO)
        self.assertNotIn("1", poisoned)

    def test_samples_far_enough_away_are_left_alone(self):
        far = shape(["#" * 8] * 8)
        templates = {"2": [TWO], "0": [far]}
        _added, displaced = T.learn(templates, "2", TWO)
        self.assertEqual(displaced, 0)
        self.assertIn("0", templates)


class TestTaughtGlyphsAreePinned(unittest.TestCase):
    """A lesson has to outrank the models, which answer before the templates."""

    class StubbornModels:
        """Stands in for a model that is confidently wrong about one shape."""
        def __init__(self, answer):
            self.answer = answer

        def __bool__(self):
            return True

        def match(self, _bitmap):
            return self.answer

    def test_correcting_beats_a_confident_model(self):
        reader = Reader(templates={}, models=self.StubbornModels("3"),
                        overrides={})
        self.assertEqual(reader.match(TWO), "3")
        reader.correct("2", TWO)
        self.assertEqual(reader.match(TWO), "2")

    def test_learning_alone_does_not(self):
        """Why teach_unknowns has to call correct() and not learn()."""
        reader = Reader(templates={}, models=self.StubbornModels("3"),
                        overrides={})
        reader.learn("2", TWO)
        self.assertEqual(reader.match(TWO), "3")

    def test_a_correction_survives_a_model_that_will_not_commit(self):
        reader = Reader(templates={}, models=self.StubbornModels(None),
                        overrides={})
        self.assertIsNone(reader.match(TWO))
        reader.correct("2", TWO)
        self.assertEqual(reader.match(TWO), "2")


if __name__ == "__main__":
    unittest.main()
