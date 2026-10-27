#!/usr/bin/env python3
"""
Teach a screen resolution from a screenshot whose reading is already known.

The game draws the readout at a different size per resolution, and it is not a
scale, so every resolution has to be taught from scratch. Doing that by hand
means running the tracker on that screen and typing what it says. This does it
from a screenshot instead, which means one person can prepare the thing for
resolutions they do not play at.

    python tools/seed_from_screenshot.py shot.png "222,063[75.48%]"
    python tools/seed_from_screenshot.py shot.png "222,063[75.48%]" --write

Nothing is saved without --write.

The reading has to be typed exactly, because it is taken as the truth and a
wrong character here teaches a wrong shape. It is checked against the number of
characters found before anything is learned, which catches most typing slips,
and it is worth looking at the reported sizes too: digits at one resolution are
all the same height, so a tally with two heights in it means the readout was
not cut out cleanly.
"""

import argparse
import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exptracker import paths, templates as templates_module          # noqa: E402
from exptracker.config import Config                                 # noqa: E402
from exptracker.models import CharacterModels                        # noqa: E402
from exptracker.reader import Reader                                 # noqa: E402
from exptracker.capture import luminance
from exptracker.segment import INK, drop_badge, segment                   # noqa: E402
from exptracker.session import parse                                 # noqa: E402

# Letterboxing puts black bars around a fullscreen capture, so "the bottom of
# the picture" is not the bottom of the game.
LETTERBOX_INK = 12

# The readout is one tight run; other labels on the bar sit further apart.
MAX_GAP = 5

# How wide a slice to segment at a time, and how far to step between slices.
# Wide enough to hold the whole readout, narrow enough that unrelated text
# does not share the slice.
SLICE_WIDTH = 420
SLICE_STEP = 60


def content_box(rgb):
    """The part of the picture the game is actually drawn in."""
    lit = rgb.max(axis=2) > LETTERBOX_INK
    rows = np.where(lit.any(axis=1))[0]
    cols = np.where(lit.any(axis=0))[0]
    if not len(rows) or not len(cols):
        return 0, rgb.shape[0] - 1, 0, rgb.shape[1] - 1
    return rows[0], rows[-1], cols[0], cols[-1]


def find_readout(rgb, truth):
    """The run of glyphs that is the experience readout, or None.

    Found by shape rather than by reading it, because at a resolution that has
    never been taught there is nothing to read it with. Three things identify
    it, none of which need a single character recognised:

      every digit is the same height, which is true within one resolution
      the comma and the full stop are far shorter, and sit at known places
      the whole thing is one tight run of the right length

    Among the cuts that pass, the best is the one whose digits are tallest. A
    band that starts or ends inside the text clips every glyph in it, so a
    clipped cut is always shorter than the clean one and never wins.

    The picture is swept in narrow vertical slices rather than whole rows.
    segment() expects a region somebody drew round the readout, and given a
    whole screen its own thresholding is pulled about by unrelated text
    elsewhere on the bar.
    """
    wanted = len(truth)
    digit_at = [i for i, ch in enumerate(truth) if ch.isdigit()]
    # Nothing else on the bar is shaped like this, which is what tells the
    # readout from a word of the same length: "Crossbowman" is eleven glyphs
    # of one height and was otherwise a perfectly good candidate.
    short_at = [i for i, ch in enumerate(truth) if ch in ",."]
    top0, bot0, left0, right0 = content_box(rgb)

    best = None
    for top in range(max(top0, bot0 - 90), bot0 - 8):
        for height in (12, 14, 16, 18, 20):
            if top + height > rgb.shape[0]:
                continue
            for x in range(left0, max(left0 + 1, right0 - 120), SLICE_STEP):
                stop = min(x + SLICE_WIDTH, right0 + 1)
                try:
                    glyphs = drop_badge(segment(rgb[top:top + height, x:stop]))
                except Exception:
                    continue
                for begin in range(0, len(glyphs) - wanted + 1):
                    window = glyphs[begin:begin + wanted]
                    if window[-1].x1 >= stop - x - 2:
                        continue          # ran off the edge of the slice
                    heights = {window[i].bitmap.shape[0] for i in digit_at}
                    if len(heights) != 1:
                        continue
                    tall = heights.pop()
                    if not all(window[i].bitmap.shape[0] <= tall // 2
                               for i in short_at):
                        continue
                    # Nothing in the readout is taller than a digit. A band
                    # that reaches the frame line above or the progress bar
                    # below welds it onto the brackets, which then come out
                    # at nineteen pixels and would be taught as the truth.
                    if max(g.bitmap.shape[0] for g in window) > tall:
                        continue
                    if best is None or tall > best[0]:
                        best = (tall, top, x + window[0].x0, window)
    return best


def describe(glyphs):
    tally = Counter(g.bitmap.shape for g in glyphs)
    return ", ".join("%dx%d x%d" % (h, w, n) for (h, w), n in tally.most_common())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    ap.add_argument("screenshot")
    ap.add_argument("reading", help='exactly what the bar says, eg "222,063[75.48%%]"')
    ap.add_argument("--write", action="store_true",
                    help="save it. Without this, nothing is changed.")
    args = ap.parse_args(argv)

    truth = args.reading.strip()
    if not parse(truth):
        print("  %r is not a readout. It should look like 222,063[75.48%%]."
              % truth)
        return 1

    path = Path(args.screenshot)
    if not path.exists():
        print("  No such file: %s" % path)
        return 1

    rgb = np.array(Image.open(path).convert("RGB"))
    found = find_readout(rgb, truth)
    if found is None:
        print("  Could not find a %d character readout in %s."
              % (len(truth), path.name))
        print("  Check the reading is typed exactly, including the comma,")
        print("  the brackets, the dot and the percent sign.")
        return 1

    tall, top, left, glyphs = found
    print("\n  %s" % path.name)
    print("  readout found at x=%d y=%d" % (left, top))
    print("  taking it as: %s" % truth)
    print("  glyph sizes : %s" % describe(glyphs))
    print("  digit height: %d" % tall)

    config = Config.load()
    reader = Reader.load(config, paths.MODELS)
    before = sum(len(v) for v in reader.templates.values())

    # Learn into a copy. A bad cut teaches wrong shapes AND displaces right
    # ones, so nothing touches the real store until the result reads back
    # correctly.
    trial = Reader(templates=deepcopy(reader.templates),
                   models=reader.models,
                   overrides=dict(reader.overrides))
    learned = displaced = skipped = 0
    for glyph, ch in zip(glyphs, truth):
        # A glyph a single pixel wide is where the threshold gave up, not a
        # character. Teaching one files a sliver under a real name, and a
        # sliver sits close to everything.
        if glyph.bitmap.shape[1] < 2 and ch != ".":
            skipped += 1
            continue
        added, gone = trial.learn(ch, glyph.bitmap)
        learned += 1 if added else 0
        displaced += gone

    after = sum(len(v) for v in trial.templates.values())
    reads = "".join(trial.match(g.bitmap) or "?" for g in glyphs)
    print("\n  learned %d new shapes, displaced %d, skipped %d as too thin"
          % (learned, displaced, skipped))
    print("  samples %d -> %d" % (before, after))
    print("  reads back as: %s" % reads)
    print("  heights would be: %s" % templates_module.heights(trial.templates))

    # The digits are what this is for. Punctuation is the same handful of
    # shapes at every size and is usually already known, so a bracket the
    # threshold mangled is not a reason to throw the digits away.
    wrong = [(i, truth[i], reads[i]) for i in range(len(truth))
             if truth[i].isdigit() and reads[i] != truth[i]]
    if wrong:
        print("\n  Digits that did not read back:")
        for i, want, got in wrong:
            print("    position %d: should be '%s', reads '%s'" % (i + 1, want, got))
        print("  Nothing changed.")
        return 1
    odd = [(i, truth[i], reads[i]) for i in range(len(truth))
           if not truth[i].isdigit() and reads[i] != truth[i]]
    if odd:
        print("  (every digit is right; %s did not read back, which is fine"
              % ", ".join("'%s'" % w for _i, w, _g in odd))
        print("   if it is already known at this size)")
    if not args.write:
        print("\n  Nothing saved. Run it again with --write to keep this.")
        return 0

    config.templates = templates_module.to_json(trial.templates)
    config.overrides = trial.overrides
    config.save()
    print("\n  Saved to %s" % config.path.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
