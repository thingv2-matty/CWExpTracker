"""
Several screen resolutions sharing one set of taught shapes.

The game redraws the readout at a different size per resolution, and it is not
a clean scale: measured across five, the digits came out 7, 9, 10 and 11 pixels
tall. Nothing can be converted between them, so each has to be taught.

The danger is that teaching one damages another. slide_compare only refuses
outright when an axis differs by more than one, so a 10 pixel digit and an 11
pixel digit are compared rather than dismissed, and a rival within MARGIN
vetoes the right answer outright. Matching and displacement are therefore both
gated on exact height, which is the rule the character models already use.
"""

import unittest

import numpy as np

from exptracker import templates as T


def digit(height, width, seed):
    """A repeatable pseudo-glyph of a given size."""
    rng = np.random.default_rng(seed)
    bitmap = rng.random((height, width)) > 0.45
    bitmap[0, :] = True          # make sure nothing is empty
    return bitmap


# The real sizes, measured from screenshots at each resolution.
TALL = 11      # Matt's own screen
BIG = 10       # 1920x1080 fullscreen
MID = 9        # 1920x1080 windowed
SMALL = 7      # 1024x768, 1280x720 and 1366x768, which are identical


class TestHeightsDoNotCompete(unittest.TestCase):
    def test_a_short_glyph_never_matches_a_tall_sample(self):
        templates = {"2": [digit(TALL, 8, 1)]}
        self.assertIsNone(T.match(digit(BIG, 7, 1), templates))

    def test_a_glyph_matches_its_own_height(self):
        small = digit(SMALL, 5, 2)
        templates = {"2": [digit(TALL, 8, 1), small]}
        self.assertEqual(T.match(small, templates), "2")

    def test_width_is_not_gated(self):
        """A digit one pixel thinner than usual must still find its own kind.

        Gating width too would put an 11x7 glyph up against only the handful of
        characters ever seen that narrow. The thinner copy here is the same
        drawing with a blank edge column trimmed, which is what sub-pixel
        positioning actually does to a glyph.
        """
        narrower = digit(TALL, 7, 3)
        stored = np.zeros((TALL, 8), dtype=bool)
        stored[:, :7] = narrower
        templates = {"5": [stored]}
        self.assertEqual(T.match(narrower, templates), "5")


class TestTeachingIsContained(unittest.TestCase):
    def test_learning_a_small_glyph_displaces_nothing_tall(self):
        shape = digit(SMALL, 5, 4)
        templates = {"1": [digit(TALL, 3, 5), digit(TALL, 4, 6)]}
        _added, displaced = T.learn(templates, "2", shape)
        self.assertEqual(displaced, 0)
        self.assertEqual(len(templates["1"]), 2)

    def test_it_still_displaces_a_blocker_at_its_own_height(self):
        shape = digit(SMALL, 5, 7)
        nudged = shape.copy()
        nudged[2, 2] = not nudged[2, 2]
        templates = {"1": [nudged]}
        _added, displaced = T.learn(templates, "2", shape)
        self.assertEqual(displaced, 1)

    def test_blocks_is_false_across_heights_whatever_the_pixels(self):
        a = np.ones((TALL, 6), dtype=bool)
        b = np.ones((SMALL, 6), dtype=bool)
        self.assertFalse(T.blocks(a, b))


class TestFourResolutionsCoexist(unittest.TestCase):
    """The real arrangement: one store, four sizes, no interference."""

    def setUp(self):
        self.templates = {}
        self.shapes = {}
        for height in (TALL, BIG, MID, SMALL):
            for n, ch in enumerate("0123456789"):
                shape = digit(height, max(3, height - 3), height * 100 + n)
                self.shapes[(height, ch)] = shape
                T.learn(self.templates, ch, shape)

    def test_every_shape_reads_back_as_itself(self):
        for (height, ch), shape in self.shapes.items():
            self.assertEqual(T.match(shape, self.templates), ch,
                             "%d pixel '%s' came back wrong" % (height, ch))

    def test_all_four_heights_survived(self):
        self.assertEqual(sorted(T.heights(self.templates)),
                         sorted([SMALL, MID, BIG, TALL]))

    def test_reteaching_one_height_leaves_the_rest_alone(self):
        before = {k: len(v) for k, v in self.templates.items()}
        for ch in "0123456789":
            T.learn(self.templates, ch, self.shapes[(SMALL, ch)])
        self.assertEqual({k: len(v) for k, v in self.templates.items()}, before)
        for (height, ch), shape in self.shapes.items():
            self.assertEqual(T.match(shape, self.templates), ch)


if __name__ == "__main__":
    unittest.main()
