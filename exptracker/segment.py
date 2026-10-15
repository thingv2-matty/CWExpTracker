"""
Cutting a captured strip into one bitmap per character.

A Glyph is (x0, x1, bitmap), where bitmap is a boolean array trimmed to the
character's own bounding box so that a template never depends on where in the
strip the character happened to sit.
"""

from collections import namedtuple

import numpy as np

from .capture import luminance

Glyph = namedtuple("Glyph", "x0 x1 bitmap")

# A pixel is ink above this luminance. The readout is light text on a dark bar.
INK = 150

# A row this full of ink is the progress bar, not text.
BAR_ROW_FILL = 0.85

# Below this spread a character has no usable local contrast, so fall back to
# the global cutoff rather than thresholding noise.
MIN_LOCAL_CONTRAST = 20


def segment(rgb):
    """Cut the strip into characters on the blank columns between them."""
    lum = luminance(rgb)
    on = lum > INK

    band = _text_band(on)
    if band is None:
        return []
    top, bottom = band
    rows = on[top:bottom + 1, :]
    rows_lum = lum[top:bottom + 1, :]

    glyphs = []
    for start, end in _runs(rows.sum(axis=0) > 0):
        bitmap = _threshold_locally(rows_lum[:, start:end + 1])
        if bitmap is not None:
            glyphs.append(Glyph(start, end, bitmap))
    return glyphs


def _runs(flags):
    """Every contiguous run of True in a 1-D boolean array, as (start, end)."""
    out, start = [], None
    for i in range(len(flags) + 1):
        lit = i < len(flags) and flags[i]
        if lit and start is None:
            start = i
        elif not lit and start is not None:
            out.append((start, i - 1))
            start = None
    return out


def _text_band(on):
    """The rows carrying the text, as (top, bottom).

    Two things can be bright besides the text: the filled part of the progress
    bar, which lights up nearly every column, and its thin highlight edges,
    which light up a few. Taking the first and last bright row would span from
    the text down past the bar and swallow everything in between, so instead the
    bright rows are grouped into contiguous blocks and the tallest block wins.
    The text is a solid band of around twenty rows; bar edges are a handful. The
    near-full rows are dropped first so that a tall bar cannot win.
    """
    width = on.shape[1]
    hits = on.sum(axis=1)
    blocks = _runs((hits > 0) & (hits < width * BAR_ROW_FILL))
    if not blocks:
        return None
    return max(blocks, key=lambda block: block[1] - block[0])


def _threshold_locally(patch):
    """Re-threshold one character against its own contrast.

    The value and the percentage sit on different backgrounds, so a single
    global cutoff gives the same digit a different shape in each place: two 8s
    from one strip differed by 24 of their 88 pixels, which is far more than the
    4 pixels that separate an 8 from a 9. Removing that is the difference
    between a readable font and an unreadable one at this size.
    """
    low, high = patch.min(), patch.max()
    if high - low > MIN_LOCAL_CONTRAST:
        local = patch > (low + high) / 2.0
    else:
        local = patch > INK
    rows = np.where(local.any(axis=1))[0]
    if not len(rows):
        return None
    return local[rows.min():rows.max() + 1, :].copy()


def drop_badge(glyphs):
    """Drop the EXP. badge from the front of a segmented strip.

    The badge is a graphic, not text: white bold letters on a dark plate, which
    thresholds into two fat blobs rather than four characters. That makes it
    impossible to type a matching answer while teaching, and it carries no
    information anyway since it never changes.

    It is recognised by HEIGHT, not width. Width looked like the obvious signal
    because the badge blobs are fat, but one of them came out 11px wide and so
    does the percent sign, so no width cutoff separates them cleanly. Height
    does: the badge letters stand 14 and 15 pixels tall against 11 for every
    digit, because they are set larger and bolder on their plate.

    Only leading runs are considered, since the value always starts with a
    digit. If the region was drawn around the numbers alone then every run is
    the same height, nothing qualifies, and nothing is dropped.
    """
    if len(glyphs) < 3:
        return glyphs
    heights = sorted(glyph.bitmap.shape[0] for glyph in glyphs)
    median = heights[len(heights) // 2]
    first = 0
    while first < len(glyphs) - 1 and glyphs[first].bitmap.shape[0] > median + 1:
        first += 1
    return glyphs[first:]


def save_strip(glyphs, path, scale=5):
    """Write out what the segmenter saw, so a mismatch is visible rather than
    something to be argued about."""
    from PIL import Image

    if not glyphs:
        return
    pad = 2
    height = max(glyph.bitmap.shape[0] for glyph in glyphs)
    width = sum(glyph.bitmap.shape[1] + pad for glyph in glyphs) + pad
    canvas = np.zeros((height + pad * 2, width, 3), dtype=np.uint8)
    canvas[:, :] = (22, 24, 30)

    x = pad
    for glyph in glyphs:
        h, w = glyph.bitmap.shape
        y = pad + (height - h) // 2
        canvas[y:y + h, x:x + w][glyph.bitmap] = (242, 239, 232)
        x += w + pad

    image = Image.fromarray(canvas)
    image.resize((width * scale, canvas.shape[0] * scale), Image.NEAREST).save(path)
