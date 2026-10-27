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


def shape(rows):
    """A glyph drawn by hand, '#' for ink."""
    return np.array([[c == "#" for c in row] for row in rows], dtype=bool)


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


class TestSameShapeIsSymmetric(unittest.TestCase):
    """slide_compare divides by the TEMPLATE's size, so it is not symmetric.

    A small shape swept across a larger one can sit inside it perfectly and
    score zero, while the larger one over the smaller does not. Asked only one
    way round, a three by two comma looked identical to a three by three one
    and was dropped as a duplicate. It was then unreadable, because match()
    will not look outside its own height to find a replacement.
    """

    SMALL = shape([".#", "##", "#."])
    LARGE = shape([".##", "##.", "#.."])

    def test_the_comparison_really_is_lopsided(self):
        one_way = T.slide_compare(self.SMALL, self.LARGE)
        other = T.slide_compare(self.LARGE, self.SMALL)
        self.assertNotAlmostEqual(one_way, other, places=3)

    def test_same_shape_agrees_both_ways(self):
        self.assertEqual(T.same_shape(self.SMALL, self.LARGE),
                         T.same_shape(self.LARGE, self.SMALL))

    def test_a_narrower_glyph_is_not_a_duplicate(self):
        templates = {",": [self.LARGE]}
        added, _displaced = T.learn(templates, ",", self.SMALL)
        self.assertTrue(added, "the narrow one was swallowed by the wide one")
        self.assertEqual(len(templates[","]), 2)

    def test_merge_keeps_both(self):
        merged = T.merge({}, {",": [self.LARGE, self.SMALL]})
        self.assertEqual(len(merged[","]), 2)

    def test_identical_shapes_are_still_duplicates(self):
        templates = {",": [self.LARGE]}
        added, _displaced = T.learn(templates, ",", self.LARGE.copy())
        self.assertFalse(added)


class TestShippedTemplates(unittest.TestCase):
    """The repo carries shapes so a fresh install is not blind."""

    def test_what_this_machine_knows_is_never_displaced_by_a_shipped_shape(self):
        """A shipped shape close enough to veto a local one is dropped, not
        allowed in to make the local one unreadable."""
        mine = shape(["######", "#....#", "#....#", "#....#", "#....#",
                      "######"])
        nearly = mine.copy()
        nearly[2, 2] = True            # one pixel in thirty six: inside MARGIN
        self.assertTrue(T.blocks(nearly, mine), "these are not close enough")
        merged = T.merge({"8": [mine]}, {"9": [nearly]})
        self.assertIn(mine.tolist(), [s.tolist() for s in merged["8"]])
        self.assertNotIn("9", merged)

    def test_a_shipped_shape_fills_a_size_never_seen_here(self):
        mine = shape(["####", "#..#", "####"])
        other_size = shape(["###", "#.#", "#.#", "###"])
        merged = T.merge({"0": [mine]}, {"0": [other_size]})
        self.assertEqual(len(merged["0"]), 2)

    def test_missing_file_is_not_an_error(self):
        from pathlib import Path
        self.assertEqual(T.load_shipped(Path("no-such-file.json")), {})


if __name__ == "__main__":
    unittest.main()
