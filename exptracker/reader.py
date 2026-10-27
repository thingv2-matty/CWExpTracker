"""
Turning a captured strip into a string.

Three sources of truth, consulted in this order:

    1. a correction made by hand, keyed on that exact glyph
    2. the stacked character models
    3. the taught templates

The order matters. The models answer confidently, so a correction has to come
first or the WRONG button would appear to do nothing on any glyph a model would
commit to, which is most of them. Templates come last because they are the
fallback for a glyph size no model covers, and for a fresh install with nothing
harvested yet.

Everything this needs is held on the object. An earlier version kept the models,
the corrections and the cache in module globals, so `match(bitmap, templates)`
quietly depended on two things its signature did not mention and could not be
tested without reaching into the module.
"""

import numpy as np

from . import paths, templates as templates_module
from .models import CharacterModels
from .segment import drop_badge, segment


def override_key(bitmap):
    """Name a glyph by its exact pixels, so a correction is surgical."""
    height, width = bitmap.shape
    return "%dx%d:%s" % (height, width, np.packbits(bitmap).tobytes().hex())


class Reader:
    """Reads the exp strip. Owns everything it needs to do so."""

    def __init__(self, templates=None, models=None, overrides=None):
        self.templates = templates if templates is not None else {}
        self.models = models if models is not None else CharacterModels(0, 0, {})
        self.overrides = dict(overrides or {})

    @classmethod
    def load(cls, config, models_path, shipped_path=None):
        """What this machine was taught, over what the repo ships.

        This machine's own shapes come first and are never displaced by a
        shipped one, because they were taught on the screen actually in front
        of the person. The shipped set fills in the sizes they have never run
        at, which is what lets a fresh install read at a resolution nobody
        here has ever used.
        """
        mine = templates_module.from_json(config.templates)
        shipped = templates_module.load_shipped(
            shipped_path or paths.TEMPLATES)
        return cls(templates=templates_module.merge(mine, shipped),
                   models=CharacterModels.load(models_path),
                   overrides=config.overrides)

    # ------------------------------------------------------------- reading --

    def match(self, bitmap):
        """The character this glyph is, or None if nothing will commit to it."""
        if self.overrides:
            corrected = self.overrides.get(override_key(bitmap))
            if corrected is not None:
                return corrected

        if self.models:
            picked = self.models.match(bitmap)
            if picked is not None:
                return picked

        return templates_module.match(bitmap, self.templates)

    def read(self, rgb):
        """Read a captured strip, returning (text, glyphs).

        Unreadable characters come back as '?' rather than as a failure, since
        a single unknown is usually recoverable from the arithmetic.
        """
        glyphs = drop_badge(segment(rgb))
        text = "".join(self.match(glyph.bitmap) or "?" for glyph in glyphs)
        return text, glyphs

    def read_text(self, rgb):
        return self.read(rgb)[0]

    # ------------------------------------------------------------ learning --

    def learn(self, ch, bitmap):
        """Add a shape to the templates. Returns (added, displaced)."""
        return templates_module.learn(self.templates, ch, bitmap)

    def correct(self, ch, bitmap):
        """Record that this exact glyph is ch, whatever anything else concludes.

        Outranks both the models and the templates, permanently and for this
        glyph only.
        """
        self.overrides[override_key(bitmap)] = ch
        return self.learn(ch, bitmap)

    @property
    def known(self):
        return "".join(sorted(self.templates))
