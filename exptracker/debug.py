"""
One capture, and every score behind every character in it.

Written to disk rather than printed, because the thing that needs diagnosing is
usually happening while the game is in the way.
"""

from . import paths, templates as templates_module
from .capture import grab
from .reader import override_key
from .segment import drop_badge, save_strip, segment


def dump(region, reader):
    from PIL import Image

    rgb = grab(region)
    Image.fromarray(rgb).save(paths.DEBUG_CAPTURE)
    glyphs = drop_badge(segment(rgb))
    save_strip(glyphs, paths.DEBUG_SEGMENTED, scale=8)

    lines = _header(region, rgb, reader, glyphs)
    for index, glyph in enumerate(glyphs):
        lines.extend(_glyph_report(index, glyph, reader))

    text = reader.read_text(rgb)
    lines.append("")
    lines.append("reads as: %s" % text)
    paths.DEBUG_REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("\n  Wrote %s, %s and %s" % (paths.DEBUG_CAPTURE.name,
                                       paths.DEBUG_SEGMENTED.name,
                                       paths.DEBUG_REPORT.name))
    print("  It reads: %s" % text)
    return 0


def _header(region, rgb, reader, glyphs):
    models = reader.models
    if models:
        counts = models.example_counts.values()
        described = "%s  (%d to %d examples each)" % (
            models.names, min(counts), max(counts))
    else:
        described = "none built yet, running on taught templates"
    return [
        "region       : %s" % region,
        "capture      : %d x %d" % (rgb.shape[1], rgb.shape[0]),
        "models       : %s" % described,
        "templates    : %s" % (reader.known or "none"),
        "samples      : %s" % {ch: len(v) for ch, v
                               in sorted(reader.templates.items())},
        "corrections  : %d" % len(reader.overrides),
        "tolerance    : %s   margin %s" % (templates_module.TOLERANCE,
                                           templates_module.MARGIN),
        "characters   : %d" % len(glyphs),
        "",
    ]


def _glyph_report(index, glyph, reader):
    """One glyph, what decided it, and what the templates thought."""
    bitmap = glyph.bitmap
    scores = {}
    for ch, samples in reader.templates.items():
        for template in samples:
            score = templates_module.slide_compare(template, bitmap)
            if ch not in scores or score < scores[ch]:
                scores[ch] = score
    ranked = sorted(scores.items(), key=lambda item: item[1])[:4]
    gap = (ranked[1][1] - ranked[0][1]) if len(ranked) > 1 else 1.0

    picked = reader.match(bitmap)
    # Say which of the three decided, since the template scores below can look
    # alarming on a glyph the models read without difficulty.
    if reader.overrides.get(override_key(bitmap)) is not None:
        via = "your correction"
    elif reader.models and reader.models.match(bitmap) is not None:
        via = "model"
    elif picked is not None:
        via = "template"
    else:
        via = "nothing would commit"

    return [
        "  [%2d] x%d-%d  %dx%d  -> %s   via %s"
        % (index, glyph.x0, glyph.x1, bitmap.shape[1], bitmap.shape[0],
           picked or "?", via),
        "        templates: %s   (margin %.3f)"
        % ("  ".join("%s=%.3f" % pair for pair in ranked), gap),
    ]
