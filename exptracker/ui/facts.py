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

# Experience per kill, from Classic World's own mob table rather than from v83.
# It matters: CW rebalanced. Four of the five values originally here were wrong
# (snails 3, stumps 8, slimes 10, pigs 15, against the real 2, 10, 12 and 13),
# and the levels moved too, with Evil Eye dropping from 32 to 27. The client
# cannot answer this on its own, because Data/Mob/Mob.wz is a 103 byte stub and
# the real table sits in Packs/Mob_00000.ms, which this repo's wz reader cannot
# open. Matt's data miners supplied it, 2026-10-24.
#
# Every row below was checked against the source's own HP/EXP column, which is
# a division the table does for you: 45/2 = 22.50 for a snail, 133/10 = 13.30
# for a stump, 3218/133 = 24.20 for a drake. All eleven divide out exactly.
MOBS = [
    ("snails", 2),
    ("stumps", 10),
    ("slimes", 12),
    ("pigs", 13),
    ("orange mushrooms", 15),
    ("ribbon pigs", 19),
    ("horny mushrooms", 41),
    ("wild boars", 46),
    ("evil eyes", 50),
    ("drakes", 133),
    ("stone golems", 175),
    ("Mushmoms", 340),
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

# Approximate runtimes in minutes. Films are the theatrical cut; a series is
# every episode back to back, which is why they only ever come up once.
WATCHABLE = [
    ("Shrek", 90),
    ("Monty Python and the Holy Grail", 91),
    ("The Princess Bride", 98),
    ("Groundhog Day", 101),
    ("Ghostbusters", 105),
    ("Back to the Future", 116),
    ("Alien", 117),
    ("Mad Max: Fury Road", 120),
    ("Spirited Away", 125),
    ("Jurassic Park", 127),
    ("Die Hard", 132),
    ("The Matrix", 136),
    ("Forrest Gump", 142),
    ("Goodfellas", 146),
    ("The Fellowship of the Ring", 178),
    ("Titanic", 194),
    ("The Return of the King", 201),
    ("every episode of Cowboy Bebop", 10 * 60),
    ("every episode of Firefly", 10 * 60),
    ("every episode of Arrested Development", 19 * 60),
    ("every episode of Avatar: The Last Airbender", 23 * 60),
    ("every episode of Stranger Things", 38 * 60),
    ("every episode of Breaking Bad", 49 * 60),
    ("every episode of Seinfeld", 66 * 60),
    ("every episode of The Office", 74 * 60),
]

# Things that take a known amount of time, in minutes, each phrased to follow
# "how long it takes". Only offered when the session lands near one, so the
# comparison stays true instead of being scaled to fit.
LONG_AS = [
    (43, "sunlight to reach Jupiter"),
    (75, "a homing pigeon to get home from a hundred kilometres away"),
    (80, "sunlight to reach Saturn"),
    (92, "the ISS to go all the way around the Earth"),
    (121, "a world record holder to run a marathon"),
    (135, "a garden snail to cross a football pitch"),
    (150, "a car to get to Toronto and back, if the 401 behaves"),
    (160, "the Titanic to sink after it hit the iceberg"),
    (250, "sunlight to reach Neptune"),
    (275, "a plane to fly from Toronto to Calgary"),
    (330, "sunlight to reach Pluto"),
    (420, "a plane to fly from Toronto to London"),
    (665, "two people to play the longest match in Wimbledon history"),
    (1200, "a hummingbird to cross the Gulf of Mexico without stopping"),
]

# How far either side of a listed span still counts as "about as long as".
NEAR_ENOUGH = (0.8, 1.25)


def _times(count):
    return {1: "once", 2: "twice", 3: "three times"}.get(count, "%d times" % count)


def _screen_time(session, segments):
    minutes = session.elapsed / 60.0
    fits = [(name, run) for name, run in WATCHABLE if minutes >= run]
    if not fits:
        return None
    name, run = random.choice(fits)
    return "That is long enough to watch %s %s." % (name, _times(int(minutes / run)))


def _as_long_as(session, segments):
    minutes = session.elapsed / 60.0
    low, high = NEAR_ENOUGH
    close = [what for span, what in LONG_AS if span * low <= minutes <= span * high]
    if not close:
        return None
    return "That is about how long it takes %s." % random.choice(close)


# A pointing hand, sunglasses, pointing hand. Tk 8.6 draws text through GDI, so
# these arrive as monochrome glyphs from a fallback font rather than as colour
# emoji. Consolas has none of them.
NICE = "👉😎👉"


def _nice_gained(session, segments):
    if 69.0 <= session.percent_gained < 70.0:
        return "You gained 69%%, nice %s" % NICE
    return None


def _nice_standing(session, segments):
    standing = session.percent
    if standing is None or not 69.0 <= standing < 70.0:
        return None
    return "You finished off at 69%%, nice %s" % NICE


# Checked before anything else and shown on its own when one applies. An easter
# egg that only turns up one time in ten it is earned is not worth having.
PRIORITY = [
    _nice_gained,
    _nice_standing,
]

ALL = [
    _levelled,
    _steady,
    _from_scratch,
    _in_mobs,
    _full_levels,
    _per_second,
    _screen_time,
    _as_long_as,
    _best_against_worst,
    _your_ceiling,
    _time_to_next,
    _onwards_to,
]


def _usable(facts, session, segments):
    found = []
    for fact in facts:
        try:
            text = fact(session, segments)
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if text:
            found.append(text)
    return found


def pick(session, segments):
    """One applicable fact, chosen at random, or None if nothing applies."""
    usable = (_usable(PRIORITY, session, segments)
              or _usable(ALL, session, segments))
    return random.choice(usable) if usable else None
