"""
How much experience each level needs, straight from the game's own formulas.

Four rules cover all 99 levels, and they reproduce the datamined table exactly,
every row. They are kept as formulas rather than a table of numbers because
that is what is actually coded in the game, it cannot be mistyped halfway down,
and it keeps going if the cap ever moves.

    1 to 5    (floor(L^2 / 2) + 15) * L
    6 to 50   (floor(L^2 / 3) + 19) * floor(L^2 / 3)
    51 to 89  previous * 1.0548, truncated
    90 to 99  previous * 2.1, truncated

The last rule is the level 90 wall. It turns the last ten levels into 99.4% of
the entire climb to cap, which is a design decision rather than a curve.

`data/exp-table.tsv` holds the datamined numbers as an independent transcription.
Nothing reads it at runtime; `python expcurve.py` checks the formulas against
it, so if the curve is ever re-mined after a balance patch, dropping in the new
table says exactly which levels moved.
"""

import math

from . import paths


MAX_LEVEL = 99          # the last level the table covers; 99 is 99 to 100
_cache = {}


def requirement(level):
    """Experience needed to get from `level` to the next one."""
    if level < 1:
        raise ValueError("level must be 1 or more")
    if level in _cache:
        return _cache[level]

    if level <= 5:
        value = (level * level // 2 + 15) * level
    elif level <= 50:
        quarter = level * level // 3
        value = (quarter + 19) * quarter
    else:
        # these two chain off the level below, so walk up to them
        rate = 1.0548 if level <= 89 else 2.1
        value = math.trunc(requirement(level - 1) * rate)

    _cache[level] = value
    return value


def shown_percent(value, level):
    """The percentage the game would display for this much experience."""
    return round(value / requirement(level) * 100.0, 2)


def consistent(value, percent, level):
    """Whether a reading could have come from this level at all."""
    if level < 1 or level > MAX_LEVEL:
        return False
    return value <= requirement(level) and shown_percent(value, level) == percent


def identify(value, percent):
    """Every level that could produce this reading.

    Usually exactly one. Adjacent levels differ by thousands of experience
    while the rounding in a percentage shown to two places leaves only a pixel
    of room, so the answer is almost always unique. The exception is the first
    moment of a new level, where a handful of experience at 0.03% genuinely
    could be several different levels. That resolves itself within a kill or
    two, and matters only at a cold start: afterwards levels are counted rather
    than re-derived.
    """
    return [lv for lv in range(1, MAX_LEVEL + 1) if consistent(value, percent, lv)]


def identify_one(value, percent):
    """The level, if the reading pins it down, otherwise None."""
    found = identify(value, percent)
    return found[0] if len(found) == 1 else None


def check_against_table():
    """Prove the formulas against the datamined table.

    Returns (mismatched_levels, unreconciled_levels). Both empty means the four
    rules reproduce every row and the table agrees with itself. Used by
    tests/test_expcurve.py; if the curve is ever re-mined after a balance
    patch, dropping in the new table says exactly which levels moved.
    """
    rows = {}
    for line in paths.EXP_TABLE.read_text(encoding="utf-8").strip().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        level, need, accumulated = line.split("	")
        rows[int(level)] = (int(need), int(accumulated))

    mismatched = [lv for lv in sorted(rows) if requirement(lv) != rows[lv][0]]
    unreconciled = [lv for lv in sorted(rows)
                    if lv > 1 and rows[lv][1] != rows[lv - 1][1] + rows[lv - 1][0]]
    return mismatched, unreconciled
