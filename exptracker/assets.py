"""
Optional artwork: damage number sprites and backgrounds.

None of this ships with the project and none of it is required. The sprites
belong to Nexon and come out of the player's own install via
tools/extract_sprites.py; backgrounds are whatever they drop in. With the
folder empty the tracker draws its plain dark theme and nothing here is used.

Everything loads lazily and fails quietly: a missing or corrupt file means that
one option does not appear in the menu, never a tracker that will not start.
"""

import json

from . import paths

# The game draws the leading digit of a number from a larger sheet and the rest
# from a smaller one. Sets without a large partner use the one sheet throughout.
SETS_FILE = "sets.json"


def _load_sets():
    manifest = paths.NUMBERS / SETS_FILE
    if not manifest.exists():
        return {}
    try:
        return json.loads(manifest.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def number_sets():
    """Names of the digit sets that are actually present and complete."""
    out = []
    for label, entry in sorted(_load_sets().items()):
        small = entry.get("small")
        if not small:
            continue
        folder = paths.NUMBERS / small
        if all((folder / ("%s.png" % d)).exists() for d in "0123456789"):
            out.append(label)
    return out


def backgrounds():
    """Names of the usable background images."""
    if not paths.BACKGROUNDS.is_dir():
        return []
    suffixes = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
    return sorted(p.stem for p in paths.BACKGROUNDS.iterdir()
                  if p.suffix.lower() in suffixes)


def background_path(name):
    if not name:
        return None
    for path in paths.BACKGROUNDS.glob(name + ".*"):
        return path
    return None


class DigitSet:
    """One damage font: ten small digits, and ten larger ones if they exist."""

    def __init__(self, label, small, large=None):
        self.label = label
        self.small = small          # {character: PIL image}
        self.large = large or {}

    @property
    def height(self):
        """Tallest digit. Deliberately ignores the extras: NoRed also carries
        Miss, guard, counter and friends, which are much bigger and would
        otherwise decide the line height for a row of numbers."""
        return max(image.height for name, image in self.small.items()
                   if name.isdigit())

    def sheet_for(self, index):
        """The leading digit comes off the large sheet, the rest off the small.

        This is most of why damage numbers look the way they do. The visible
        step at the top of a number is the size change on the first digit, not
        the vertical stagger, which is only a pixel or two.
        """
        if index == 0 and self.large:
            return self.large
        return self.small

    def glyph(self, character, index):
        sheet = self.sheet_for(index)
        return sheet.get(character) or self.small.get(character)

    @classmethod
    def load(cls, label):
        from PIL import Image

        entry = _load_sets().get(label)
        if not entry:
            return None

        def sheet(group):
            if not group:
                return {}
            folder = paths.NUMBERS / group
            if not folder.is_dir():
                return {}
            images = {}
            for path in folder.glob("*.png"):
                try:
                    images[path.stem] = Image.open(path).convert("RGBA")
                except OSError:
                    continue
            return images

        small = sheet(entry.get("small"))
        if not all(d in small for d in "0123456789"):
            return None
        return cls(label, small, sheet(entry.get("large")))
