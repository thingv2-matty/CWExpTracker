"""
One silly, true thing about the session, for the bottom of the recap.

Every fact is computed from what actually happened rather than picked from a
list of platitudes, so the numbers are real even when the framing is daft.
A fact only offers itself when it has something to say: a two minute session
does not get told how many days to level 70.
"""

import random

from ..import expcurve
from .format import clock, thousands

# Experience per kill, read out of the game's own Mob.wz data rather than
# remembered. These are the v83 values; Classic World is built on v83, so they
# should hold, but they are worth a sanity check against the game.
MOBS = [
    ("snails", 3),
    ("stumps", 8),
    ("slimes", 10),
    ("pigs", 15),
    ("evil eyes", 50),
]


def level_reached(experience):
    """The level a character starting from scratch would reach on this much."""
    total = 0
    for level in range(1, expcurve.MAX_LEVEL + 1):
        total += expcurve.requirement(level)
        if total > experience:
            return level
    return expcurve.MAX_LEVEL + 1


def _from_scratch(session, segments):
    if session.gained < expcurve.requirement(1):
        return None
    level = level_reached(session.gained)
    if level < 3:
        return None
    return ("That is enough to take a brand new character all the way to "
            "level %d." % level)


def _in_mobs(session, segments):
    if session.gained < 100:
        return None
    name, each = random.choice(MOBS)
    count = int(session.gained / each)
    return "That is %s %s. Think about that for a second." % (
        thousands(count), name)


def _full_levels(session, segments):
    # Only once there is at least one whole bar in it. "0.5 full bars" is not
    # a sentence anybody wants to read.
    if not session.requirement or session.percent_gained < 100:
        return None
    return ("At level %d that is %.1f full bars of experience."
            % (session.level, session.percent_gained / 100.0))


def _per_second(session, segments):
    if session.elapsed < 300 or not session.gained:
        return None
    return "That works out at %s experience every second, without stopping." % (
        thousands(session.gained / session.elapsed))


def _best_against_worst(session, segments):
    done = [s for s in segments if s["complete"]]
    if len(done) < 2:
        return None
    best = max(done, key=lambda s: s["per_hour"])
    worst = min(done, key=lambda s: s["per_hour"])
    if not worst["per_hour"] or best["per_hour"] / worst["per_hour"] < 1.4:
        return None
    return ("Your best block ran %.1f times the rate of your worst. "
            "Something happened in there."
            % (best["per_hour"] / worst["per_hour"]))


def _if_you_had_kept_it_up(session, segments):
    done = [s for s in segments if s["complete"]]
    if len(done) < 2 or not session.gained:
        return None
    best = max(done, key=lambda s: s["per_hour"])
    could_have = best["per_hour"] * (session.elapsed / 3600.0)
    extra = could_have - session.gained
    if extra < session.gained * 0.15:
        return None
    return ("Had the whole session gone like your best block, that would have "
            "been another %s experience." % thousands(extra))


def _time_to_next(session, segments):
    if not session.to_level or session.to_level < 600:
        return None
    return "At this rate the next level lands in %s." % clock(session.to_level)


def _onwards_to(session, segments):
    """How long the current rate would take to reach a round future level."""
    if not session.level or session.per_hour <= 0:
        return None
    target = next((lv for lv in (30, 40, 50, 60, 70)
                   if lv > session.level), None)
    if target is None:
        return None
    needed = sum(expcurve.requirement(lv) for lv in range(session.level, target))
    needed -= session.value or 0
    hours = needed / session.per_hour
    if hours < 2:
        return None
    return ("Keep this up and level %d arrives in %.0f hours of grinding."
            % (target, hours))


ALL = [
    _from_scratch,
    _in_mobs,
    _full_levels,
    _per_second,
    _best_against_worst,
    _if_you_had_kept_it_up,
    _time_to_next,
    _onwards_to,
]


def pick(session, segments):
    """One applicable fact, chosen at random, or None if nothing applies."""
    usable = []
    for fact in ALL:
        try:
            text = fact(session, segments)
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if text:
            usable.append(text)
    return random.choice(usable) if usable else None
