"""
Drawing a number in the game's damage font.

Three things are going on, and only one of them is the stagger:

    1. The leading digit is drawn from a larger sheet than the rest. Measured
       off a real capture, the first digit stands 1.18 times the height of its
       neighbours, against a sheet ratio of 1.16 to 1.23. This is what produces
       the pronounced step at the top of a number, and it is easy to mistake
       for dramatic staggering.

    2. Digits sit on a shared baseline, not a shared top.

    3. On top of that each digit is nudged a pixel or two up or down by
       position, alternating. Measured at 2px peak to peak on a real line of
       eight digits, strictly alternating and independent of which digit sits
       where.

The alternation is exaggerated a little here, because two pixels that read as
deliberate at the game's size read as a rendering wobble in a small panel.
"""

STAGGER = 3          # pixels above or below the baseline
KERNING = -2         # digits overlap slightly, as they do in game


def render(digits, text, stagger=STAGGER, kerning=KERNING, scale=1.0):
    """Lay a string out in a DigitSet and return an RGBA image, or None.

    The first digit sits high and the rest alternate down and up from there,
    which is what a real capture shows: in a reading of 365 the leading digit's
    baseline sits two pixels above its neighbour's.

    Anything the sheets have no glyph for is dropped rather than spaced around.
    The game writes damage with no thousands separator and lets the digits
    overlap, so a comma has nowhere to go even if one were wanted.
    """
    from PIL import Image

    glyphs = []
    for character in text:
        image = digits.glyph(character, len(glyphs))
        if image is not None:
            glyphs.append(image)
    if not glyphs:
        return None

    width = sum(g.width for g in glyphs) + kerning * (len(glyphs) - 1)
    tallest = max(g.height for g in glyphs)
    height = tallest + stagger * 2

    canvas = Image.new("RGBA", (max(1, width), max(1, height)), (0, 0, 0, 0))
    baseline = stagger + tallest
    x = 0
    for index, glyph in enumerate(glyphs):
        offset = -stagger if index % 2 == 0 else stagger
        canvas.alpha_composite(glyph, (max(0, x), baseline - glyph.height + offset))
        x += glyph.width + kerning

    if scale != 1.0:
        canvas = canvas.resize((max(1, int(canvas.width * scale)),
                                max(1, int(canvas.height * scale))),
                               Image.LANCZOS)
    return canvas


def fit(digits, text, max_width, max_height, **kwargs):
    """Render, then shrink to fit the space available."""
    image = render(digits, text, **kwargs)
    if image is None:
        return None
    scale = min(max_width / image.width, max_height / image.height, 1.0)
    if scale < 1.0:
        from PIL import Image as _Image
        image = image.resize((max(1, int(image.width * scale)),
                              max(1, int(image.height * scale))),
                             _Image.LANCZOS)
    return image
