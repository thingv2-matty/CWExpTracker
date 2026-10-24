"""
Recognising a character by comparing it against stored examples.

This was the original approach and it is now the fallback, used when no
character model covers a glyph, when a model will not commit, and on a fresh
install with nothing harvested. See models.py for what replaced it and why.

Templates map a character to a list of bitmaps, because one character can
legitimately threshold to more than one shape and keeping both is cheaper than
deciding which is canonical.
"""

import numpy as np

# A template matches only if it is very nearly identical.
#
# This is deliberately strict, and the reason is that no forgiving value works.
# Measured across ten captures:
#
#     two copies of the SAME digit, worst case     0.295
#     an 8 against a 9, closest case               0.045
#
# The spread within a character is larger than the distance between characters,
# so there is no threshold that accepts every real match while rejecting every
# wrong one. The game draws text at sub-pixel positions, so a digit rasterises
# differently depending on where it sits in the string.
#
# Faced with that, the only safe choice is near-exact matching. A loose
# threshold does not produce uncertainty, it produces CONFIDENT WRONG READINGS:
# at 0.20 a capture read 16,409[98.98%] for 16,405[98.35%], which parses, passes
# the consistency check, and quietly corrupts the totals. An unread character is
# recoverable; a wrongly read one is not.
TOLERANCE = 0.05

# How much better the best candidate must be than the runner-up before the
# reading is believed. Measured: an 8 and a 9 are about 0.025 apart while two
# copies of one digit vary by up to 0.076, so closeness alone proves nothing.
# Without this the tracker reported 11,591 at 57.94% for 11,592 at 57.34%, with
# no sign that anything was uncertain.
MARGIN = 0.035

# How far a template may slide either way when looking for its best fit.
SLIDE = 3

# Two bitmaps this close are the same shape for filing purposes.
IDENTICAL = 0.005


def slide_compare(template, bitmap):
    """Lowest disagreement as the template slides over the candidate, 0 to 1.

    Padding both to a common box and trying every offset means a template cut
    one pixel to the left of its neighbour still recognises it, which comparing
    in place does not.
    """
    th, tw = template.shape
    bh, bw = bitmap.shape
    # Sliding alone will happily fit a small shape inside a larger one, so a
    # one pixel dot scored well against a three pixel comma. Sizes still have to
    # be comparable: sliding fixes alignment, not identity.
    if abs(th - bh) > 1 or abs(tw - bw) > 1:
        return 1.0

    height = max(th, bh)
    width = max(tw, bw) + SLIDE * 2
    canvas = np.zeros((height, width), dtype=bool)
    offset = (height - bh) // 2
    canvas[offset:offset + bh, SLIDE:SLIDE + bw] = bitmap

    best = 1.0
    for dy in range(-1, 2):
        top = (height - th) // 2 + dy
        if top < 0 or top + th > height:
            continue
        for dx in range(SLIDE * 2 + 1):
            if dx + tw > width:
                continue
            patch = canvas[top:top + th, dx:dx + tw]
            score = np.logical_xor(patch, template).sum() / template.size
            if score < best:
                best = score
    return best


def same_shape(a, b):
    """Close enough that filing both under different characters guarantees a tie."""
    if a.shape == b.shape and np.array_equal(a, b):
        return True
    return slide_compare(a, b) < IDENTICAL


def blocks(a, b):
    """True if filing these under different characters makes both unmatchable.

    MARGIN is the bar: match() refuses to commit when the runner-up is within
    it, so two samples closer than MARGIN do not merely tie, they veto each
    other. Neither can ever be read again.
    """
    return slide_compare(a, b) < MARGIN


def learn(templates, ch, bitmap):
    """Record that this shape is ch, and that it is NOT anything else.

    The second half is the important half, and it has to be measured with the
    same ruler match() uses. An earlier version displaced only samples that
    were IDENTICAL to the new one, which is five times stricter than MARGIN,
    the distance that actually blocks a match. A rival sitting in between was
    never displaced and silently vetoed the character forever.

    That was not hypothetical. One sample of a 2 had been filed as a 1, sat
    0.013 from five real 2s, and made every one of them unreadable. Teaching
    could not clear it: each lesson added another 2 for the stray 1 to veto.
    Matt taught it over and over and reported, correctly, that it ALWAYS got
    hung up on that one digit.

    Returns (added, displaced).
    """
    displaced = 0
    for other in list(templates):
        if other == ch:
            continue
        keep = [sample for sample in templates[other]
                if not blocks(sample, bitmap)]
        displaced += len(templates[other]) - len(keep)
        if keep:
            templates[other] = keep
        else:
            del templates[other]

    samples = templates.setdefault(ch, [])
    if any(same_shape(sample, bitmap) for sample in samples):
        return False, displaced
    samples.append(bitmap)
    return True, displaced


def match(bitmap, templates):
    """The character this bitmap most resembles, or None if nothing is close."""
    scores = {}
    for ch, samples in templates.items():
        for template in samples:
            score = slide_compare(template, bitmap)
            if ch not in scores or score < scores[ch]:
                scores[ch] = score
    if not scores:
        return None

    ranked = sorted(scores.items(), key=lambda item: item[1])
    best, best_score = ranked[0]
    if best_score > TOLERANCE:
        return None
    # A close second means the shape does not actually distinguish them, so say
    # so rather than pick one. Reporting nothing is recoverable; reporting the
    # wrong digit with confidence is not.
    if len(ranked) > 1 and (ranked[1][1] - best_score) < MARGIN:
        return None
    return best


def to_json(templates):
    return {ch: [{"h": int(b.shape[0]), "w": int(b.shape[1]),
                  "bits": "".join("1" if v else "0" for v in b.flatten())}
                 for b in samples]
            for ch, samples in templates.items()}


def from_json(blob):
    out = {}
    for ch, entries in (blob or {}).items():
        # an older config stored one sample per character rather than a list
        if isinstance(entries, dict):
            entries = [entries]
        out[ch] = [
            np.array([c == "1" for c in entry["bits"]], dtype=bool)
              .reshape(entry["h"], entry["w"])
            for entry in entries
        ]
    return out
