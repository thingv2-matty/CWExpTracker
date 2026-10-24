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
    return ("Your best block ran %.1f times the rate of your worst."
            % (best["per_hour"] / worst["per_hour"]))


def _your_ceiling(session, segments):
    """What the best block proves the spot can do.

    This used to say how much experience was missed by not being flawless for
    three hours, which is the same arithmetic framed as a failure. Nobody wants
    to end a session being told what they did not earn.
    """
    done = [s for s in segments if s["complete"]]
    if len(done) < 2 or not session.gained:
        return None
    best = max(done, key=lambda s: s["per_hour"])
    if best["per_hour"] < session.per_hour * 1.15:
        return None
    return ("Your best stretch ran at %s an hour. That is what this spot has "
            "in it." % thousands(best["per_hour"]))


# Past this point through a level, "nearly there" is encouraging. Below it,
# the same sentence is a wall.
NEARLY_THERE = 60.0


def _time_to_next(session, segments):
    """Only once the next level is genuinely close.

    Time to level is at its worst the instant you level up, which is also the
    moment you least want to be shown it. Matt levelled after a long slog and
    got told the next one was five hours away.
    """
    if not session.to_level or session.to_level < 600:
        return None
    standing = session.percent
    if standing is None or standing < NEARLY_THERE:
        return None
    return "You are %.0f%% through. At this rate the next level lands in %s." % (
        standing, clock(session.to_level))


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
    # Under a couple of hours is not worth remarking on; over a long weekend
    # it stops being a goal and starts being a sentence.
    if hours < 2 or hours > 20:
        return None
    return ("Keep this up and level %d arrives in %.0f hours of grinding."
            % (target, hours))


def _levelled(session, segments):
    if session.levels < 1:
        return None
    if session.levels == 1:
        return "You levelled up in that sitting. One down."
    return "You put %d levels away in that sitting." % session.levels


def _steady(session, segments):
    """Credit for consistency.

    Only the variance ever got remarked on, which meant an even session had
    nothing good said about it. Holding a rate for an hour is harder than
    hitting it once.
    """
    done = [s for s in segments if s["complete"]]
    if len(done) < 3 or not session.per_hour:
        return None
    drift = max(abs(s["per_hour"] - session.per_hour) for s in done)
    share = drift / session.per_hour
    if share > 0.15:
        return None
    return ("Every block landed within %.0f%% of your average. That is hard to "
            "do." % (share * 100))


ALL = [
    _levelled,
    _steady,
    _from_scratch,
    _in_mobs,
    _full_levels,
    _per_second,
    _best_against_worst,
    _your_ceiling,
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
