"""
Recognising a character from what every example of it agrees on.

Comparing a candidate against individual stored samples asks which single
example it is closest to, which the blurred edges of this font can swing.
Stacking every example of a character asks a better question:

    CORE  pixels lit in essentially every example. A real 8 must have these.
    VOID  pixels lit in essentially none.          A real 8 must not have these.

The void half is what nearest-neighbour matching never used, and it is what
separates a 1 from a 4: both have the upright stroke, but a 4 puts ink to the
left of it where a 1 must be empty.

Built by tools/build_models.py from a labelled set of real captures. Measured
over 120 captures scored by models built without them, this read every one
exactly, where per-sample comparison asked about something in nearly all of
them.
"""

import json

import numpy as np

# A model must be satisfied completely, and no rival of the same height may come
# within MARGIN of it.
#
# These are not tuning dials. Across 1,440 glyphs held out one at a time, every
# glyph satisfied its own model perfectly and the closest a wrong model ever
# came was 0.987, so anything short of "satisfied completely" only lets errors
# in. Allowing one example in ten to disagree was tried: the worst own-score
# fell to 0.788 and 29 wrong answers got through.
ACCEPT = 1.0
MARGIN = 0.005

# Reading a glyph costs about a millisecond and the same bitmaps recur every
# tick, since the leading digits of the value sit still for minutes at a time.
CACHE_LIMIT = 4096


class CharacterModels:
    """The stacked core and void masks for every character that was labelled."""

    def __init__(self, height, width, chars):
        self.height = height
        self.width = width
        self.chars = chars
        self._cache = {}

    def __bool__(self):
        return bool(self.chars)

    def __contains__(self, ch):
        return ch in self.chars

    @property
    def names(self):
        return "".join(sorted(self.chars))

    @property
    def example_counts(self):
        return {ch: model["n"] for ch, model in self.chars.items()}

    @classmethod
    def load(cls, path):
        """Read models from disk, or return an empty set if there are none."""
        if not path.exists():
            return cls(0, 0, {})
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
            height, width = int(blob["h"]), int(blob["w"])
            chars = {
                ch: {
                    "core": _unpack(entry["core"], height, width),
                    "void": _unpack(entry["void"], height, width),
                    "heights": {int(shape[0]) for shape in entry["shapes"]},
                    "n": int(entry.get("n", 0)),
                }
                for ch, entry in blob["chars"].items()
            }
        except (ValueError, OSError, KeyError, TypeError):
            return cls(0, 0, {})
        return cls(height, width, chars)

    def match(self, bitmap):
        """The character this bitmap is, or None if the models will not commit.

        A glyph is only ever put up against characters that render at its own
        height. A comma is never mistaken for a 4, and pretending otherwise is
        worse than useless: a model built from a three-pixel comma has almost no
        core and almost no void, so nearly any glyph satisfies it.

        Height rather than exact size, deliberately. Gating on width would put
        an eleven-by-seven glyph up against only the 4 and the 7, those being
        the two ever seen that narrow, so a digit rendering one pixel thinner
        than before would face the wrong shortlist. Both rules read 120 of 120
        held-out captures, so the robust one wins.
        """
        if bitmap.shape[0] > self.height or bitmap.shape[1] > self.width:
            return None

        key = (bitmap.shape, np.packbits(bitmap).tobytes())
        if key in self._cache:
            return self._cache[key]

        candidates = [(ch, model) for ch, model in self.chars.items()
                      if bitmap.shape[0] in model["heights"]]
        if not candidates:
            return None

        placements = self._placements(bitmap)
        scores = sorted(
            (self._score(placements, model), ch) for ch, model in candidates
        )
        best, ch = scores[-1]
        runner_up = scores[-2][0] if len(scores) > 1 else 0.0

        picked = ch
        if best < ACCEPT or (best - runner_up) < MARGIN:
            picked = None

        if len(self._cache) >= CACHE_LIMIT:
            self._cache.clear()
        self._cache[key] = picked
        return picked

    def _placements(self, bitmap):
        """Every position this glyph could sit at on the model canvas."""
        bh, bw = bitmap.shape
        out = []
        for dy in range(self.height - bh + 1):
            for dx in range(self.width - bw + 1):
                canvas = np.zeros((self.height, self.width), dtype=bool)
                canvas[dy:dy + bh, dx:dx + bw] = bitmap
                out.append(canvas)
        return out

    @staticmethod
    def _score(placements, model):
        """How well this glyph satisfies a model, at its best alignment."""
        core, void = model["core"], model["void"]
        best = 0.0
        for canvas in placements:
            core_hit = canvas[core].mean() if core.any() else 1.0
            void_ok = (~canvas[void]).mean() if void.any() else 1.0
            score = min(core_hit, void_ok)
            if score > best:
                best = score
        return best


def _unpack(packed, height, width):
    bits = np.unpackbits(np.array(packed, dtype=np.uint8))
    return bits[:height * width].reshape(height, width).astype(bool)
