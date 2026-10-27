"""
Recognising a character by comparing it against stored examples.

This was the original approach and it is now the fallback, used when no
character model covers a glyph, when a model will not commit, and on a fresh
install with nothing harvested. See models.py for what replaced it and why.

Templates map a character to a list of bitmaps, because one character can
legitimately threshold to more than one shape and keeping both is cheaper than
deciding which is canonical.
"""

import json

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
    """Close enough that filing both under different characters guarantees a tie.

    Asked both ways round, because slide_compare is not symmetric: it divides
    the disagreement by the TEMPLATE's size, so a small shape swept across a
    larger one scores well while the reverse does not. A three by two comma
    and a three by three one came out 0.1111 apart one way and identical the
    other, and the one way round that got asked silently threw the small one
    away. It was then unreadable, because match() will not look outside its
    own height for a replacement.
    """
    if a.shape == b.shape:
        if np.array_equal(a, b):
            return True
        return slide_compare(a, b) < IDENTICAL
    return max(slide_compare(a, b), slide_compare(b, a)) < IDENTICAL


def blocks(a, b):
    """True if filing these under different characters makes both unmatchable.

    MARGIN is the bar: match() refuses to commit when the runner-up is within
    it, so two samples closer than MARGIN do not merely tie, they veto each
    other. Neither can ever be read again.

    Samples of different heights never block, because match() never puts them
    up against each other. That is what keeps one screen resolution's lesson
    from deleting another's: at 1024x768 the digits are seven pixels tall and
    at 1920x1080 they are ten, and teaching the small ones must not quietly
    throw away the large.
    """
    if a.shape[0] != b.shape[0]:
        return False
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
    # Only a sample of the same height counts as already having this one.
    # match() will not look outside that height, so a shape dropped here as a
    # duplicate of a taller one is simply lost: the comma renders two pixels
    # tall at 1280x720 and three at 1920x1080, and treating the short one as
    # the tall one already known left the small screen unable to read a comma
    # at all.
    if any(sample.shape[0] == bitmap.shape[0] and same_shape(sample, bitmap)
           for sample in samples):
        return False, displaced
    samples.append(bitmap)
    return True, displaced


def match(bitmap, templates):
    """The character this bitmap most resembles, or None if nothing is close.

    Only samples of the same height are considered. This is the rule the
    character models already use, for the reason given there: a glyph put up
    against characters that do not render at its height is being asked the
    wrong question.

    It matters twice over here. Within one screen it stops a comma being
    weighed against a 4. Across screens it is what makes a second resolution
    safe to teach at all: slide_compare only refuses outright when an axis
    differs by more than one, so without this a ten pixel digit from one
    resolution and an eleven pixel digit from another compete, and whichever
    is closer vetoes the other outright.

    Width is deliberately NOT gated, matching the models again: a digit
    rendering one pixel thinner than usual should still find its own kind.
    """
    scores = {}
    for ch, samples in templates.items():
        for template in samples:
            if template.shape[0] != bitmap.shape[0]:
                continue
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


def heights(templates):
    """Every glyph height present, commonest first. One per resolution."""
    from collections import Counter

    tally = Counter(b.shape[0] for samples in templates.values()
                    for b in samples)
    return [h for h, _n in tally.most_common()]


def to_json(templates):
    return {ch: [{"h": int(b.shape[0]), "w": int(b.shape[1]),
                  "bits": "".join("1" if v else "0" for v in b.flatten())}
                 for b in samples]
            for ch, samples in templates.items()}


def load_shipped(path):
    """The shapes that come with the repo, or nothing if the file is missing.

    These exist so a fresh install is not blind on a screen nobody here has
    run it on. They are a starting point, not the truth: anything this machine
    learns is written to the config and takes its place alongside them.
    """
    if not path.exists():
        return {}
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return from_json(blob.get("templates") or {})


def merge(base, extra):
    """Add anything from extra that base does not already have."""
    out = {ch: list(samples) for ch, samples in base.items()}
    for ch, samples in extra.items():
        kept = list(out.get(ch, []))
        for sample in samples:
            if any(seen.shape[0] == sample.shape[0] and same_shape(sample, seen)
                   for seen in kept):
                continue
            # Never let a shipped shape veto one this machine was taught.
            if any(blocks(sample, seen)
                   for other, theirs in base.items() if other != ch
                   for seen in theirs):
                continue
            kept.append(sample)
        # Only once something survived, so a character whose every shipped
        # shape was rejected does not linger as an empty entry.
        if kept:
            out[ch] = kept
    return out


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
