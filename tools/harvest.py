"""
Log the exp bar while grinding, so there is real data to build models from.

The reading problem was starved of data for weeks: models built from three or
four examples of a digit, which is why "lit in every example" held up in sample
and fell over out of it. Grinding produces a new value every few seconds for
free, so this just watches and keeps every distinct one.

Nothing is labelled here and nothing is decided here. That is label.py,
afterwards, in one pass.

    python tools/harvest.py                gather the default target, then stop
    python tools/harvest.py --target 200
    python tools/harvest.py --forever      until Ctrl+C

Captures are written as the raw region rather than as glyphs, so a later change
to the segmenter can be re-run across the whole set instead of invalidating it.
"""

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np                                               # noqa: E402
from PIL import Image                                            # noqa: E402

from exptracker import paths                                     # noqa: E402
from exptracker.capture import grab                              # noqa: E402
from exptracker.config import Config                             # noqa: E402
from exptracker.models import CharacterModels                    # noqa: E402
from exptracker.reader import Reader                             # noqa: E402

TARGET = 120
PERIOD = 0.4

# The shortest possible readout is one digit, then "[d.dd%]": eight characters.
# Anything shorter is a bad capture rather than a small number.
MIN_GLYPHS = 8


def anchor(guess):
    """Some characters are never in question.

    The strip always ends "[<percent>%]" with two decimal places, so counting
    back from the end, the last character is ']', the one before it '%', and the
    fifth from the end the decimal point. Guessing at those is three chances to
    be wrong for no benefit. The '[' and the thousands comma are left alone,
    since neither sits at a fixed distance from either end.
    """
    if len(guess) < 6:
        return guess
    fixed = list(guess)
    fixed[-1], fixed[-2], fixed[-5] = "]", "%", "."
    return "".join(fixed)


def signature(glyphs):
    """Identify a reading by its shapes, so only genuine changes are kept."""
    digest = hashlib.sha1()
    for glyph in glyphs:
        digest.update(bytes(glyph.bitmap.shape))
        digest.update(np.packbits(glyph.bitmap).tobytes())
    return digest.hexdigest()


def next_index(folder):
    highest = -1
    for existing in folder.glob("*.png"):
        try:
            highest = max(highest, int(existing.stem))
        except ValueError:
            continue
    return highest + 1


def main(argv):
    target = TARGET
    forever = "--forever" in argv
    if "--target" in argv:
        target = int(argv[argv.index("--target") + 1])

    config = Config.load()
    if not config.region:
        print("No region saved yet. Run the tracker once and pick the exp bar.")
        return 1
    reader = Reader.load(config, paths.MODELS)

    paths.CAPTURES.mkdir(parents=True, exist_ok=True)
    index = next_index(paths.CAPTURES)
    if index:
        print("%d capture(s) already here; adding to them." % index)

    print("Watching the exp bar. Target %s distinct readings. Ctrl+C to stop.\n"
          % (target if not forever else "no limit"))
    print("Go grind. Nothing to do here.\n")

    seen = set()
    kept = 0
    reported_at = 0.0
    try:
        while forever or kept < target:
            rgb = grab(config.region)
            text, glyphs = reader.read(rgb)
            if len(glyphs) >= MIN_GLYPHS:
                mark = signature(glyphs)
                if mark not in seen:
                    seen.add(mark)
                    name = "%04d" % index
                    Image.fromarray(rgb).save(paths.CAPTURES / (name + ".png"))
                    guess = anchor(text)
                    (paths.CAPTURES / (name + ".json")).write_text(
                        json.dumps({"guess": guess, "glyphs": len(glyphs),
                                    "at": time.time()}), encoding="utf-8")
                    index += 1
                    kept += 1
                    now = time.time()
                    if now - reported_at > 2.0:
                        reported_at = now
                        print("  %4d kept   latest reads as %s" % (kept, guess))
            time.sleep(PERIOD)
    except KeyboardInterrupt:
        print("\nstopped.")

    print("\n%d new capture(s) in %s" % (kept, paths.CAPTURES))
    print("Next: python tools/label.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
