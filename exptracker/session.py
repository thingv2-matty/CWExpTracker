"""
Turning a stream of readings into experience per hour and time to level.

The picture is never asked to be certain. It is asked to produce a reading, and
the reading then has to survive what is already known about how experience
moves. At two captures a second a rejected frame costs nothing and the next
reading is absolute, so the tests can afford to be strict: a dropped frame is
recoverable, a believed wrong one corrupts the totals for the rest of the
session.
"""

import itertools
import re
import time

from . import expcurve

# Dying costs exactly this share of the level, which makes it the one backwards
# movement that is real rather than a misread.
DEATH_PENALTY_PCT = 5.0

# The most of a level that can plausibly be gained between two captures. Half a
# second of killing things is a small fraction of a level; a big jump is a
# misread leading digit.
MAX_GAIN_PCT_PER_SAMPLE = 8.0

# Consecutive rejections before the stored baseline is treated as the problem
# rather than the readings. At two captures a second this is about eight
# seconds of disagreeing with everything, which does not happen when the
# baseline is sound.
STUCK_LIMIT = 16

# How many unknown characters the arithmetic will try to solve at once. Each one
# multiplies the candidates by ten, so four is already ten thousand combinations
# per capture, and beyond that the odds of two of them fitting start to matter
# more than the extra coverage.
MAX_INFERRED = 3

READOUT = re.compile(r"(\d[\d,]*)\[(\d+\.\d+)%\]")


def parse(text):
    """Pull (value, percent) out of a read strip, or None if it is not clean.

    An unknown character well away from the numbers is not fatal, so a slightly
    generous region selection can still read. But an unknown character touching
    them is, and quietly: searching forward for the pattern will happily skip
    over a bad leading digit and match the rest, so "1?,306[60.87%]" came back
    as 306 at 60.87%. That parses, and a truncated value is far worse than no
    value, so anything butting up against the number is refused.

    Zero percent is a real reading, not a bad one. A fresh level shows 0 at
    0.00%, and at high levels a few points of experience are too small to move a
    figure shown to two decimals. Rejecting it here used to make the level-up
    handling for that case unreachable.
    """
    cleaned = text.replace(" ", "")
    found = READOUT.search(cleaned)
    if not found:
        return None
    before = cleaned[:found.start(1)]
    if before and before[-1] in "?0123456789,":
        return None
    try:
        value = int(found.group(1).replace(",", ""))
        percent = float(found.group(2))
    except ValueError:
        return None
    if percent < 0 or percent > 100:
        return None
    return value, percent


def infer_missing(text, requirement, tolerance=0.0005):
    """Work out unreadable characters from the arithmetic.

    The readout is not arbitrary text. Within a level, value divided by percent
    is the experience the level requires, and that figure does not move, so once
    it is known a single unknown character has only one value that fits.
    Substituting each digit in turn and keeping the one that lands on the known
    requirement identifies it with no pixel comparison at all.

    Returns the completed text when exactly one combination fits, otherwise
    None: two fitting means the arithmetic cannot settle it, and guessing would
    be worse than waiting half a second for the next capture.
    """
    if not requirement:
        return None
    spots = [i for i, ch in enumerate(text) if ch == "?"]
    if not spots or len(spots) > MAX_INFERRED:
        return None

    chars = list(text)
    hits = []
    for combo in itertools.product("0123456789", repeat=len(spots)):
        for index, digit in zip(spots, combo):
            chars[index] = digit
        candidate = "".join(chars)
        parsed = parse(candidate)
        if not parsed:
            continue
        value, percent = parsed
        if percent <= 0:
            continue
        implied = value / (percent / 100.0)
        if abs(implied - requirement) / requirement <= tolerance:
            hits.append(candidate)
            if len(hits) > 1:              # ambiguous, stop early
                return None
    return hits[0] if len(hits) == 1 else None


class Session:
    """Running totals, and the level bookkeeping that makes them correct."""

    def __init__(self):
        # Elapsed time is banked rather than measured from a single start, so a
        # pause can stop the clock without losing what came before it.
        self.started = None
        self.running = False
        self.banked = 0.0
        self.resumed_at = None

        self.level = None
        self.value = None
        self.requirement = None

        self.gained = 0
        self.levels = 0

        self.stuck = 0
        self.rejected = 0
        self.recoveries = 0
        self.last_good = None
        # Distinct from last_good: a reading can be believed without any
        # experience having been earned, which is exactly what sitting in town
        # looks like.
        self.last_gain = None

    # ------------------------------------------------------------- levels --

    def adopt_level(self, level):
        self.level = level
        self.requirement = expcurve.requirement(level)

    def identify(self, value, percent):
        """Work out which level a reading belongs to, if it says so clearly."""
        found = expcurve.identify_one(value, percent)
        if found is not None:
            self.adopt_level(found)
        return found

    @staticmethod
    def estimate_requirement(value, percent):
        """A rough requirement, used only until the level is known.

        Dividing experience by a percentage shown to two decimals gives an
        answer that always needs refining. Once the level is known the curve
        gives it exactly instead.
        """
        return value / (percent / 100.0)

    # ------------------------------------------------------------ reading --

    def update(self, value, percent):
        """Take a reading. Returns whether it was believed."""
        if value < 0 or percent < 0:
            return self._reject()
        estimate = self.estimate_requirement(value, percent) if percent > 0 else None

        # Guard on the value rather than the clock. They are set together in
        # normal running, but keying off the clock means any state where the
        # timer exists and the value does not walks straight into comparing a
        # number against None.
        if self.value is None:
            self.identify(value, percent)
            self.value = value
            if self.requirement is None:
                self.requirement = estimate
            self.last_good = time.time()
            return True

        # Still unidentified, which only happens in the first moments of a new
        # level where a handful of experience at 0.03% genuinely could belong to
        # several levels. Keep asking; a kill or two settles it.
        if self.level is None:
            self.identify(value, percent)

        # Long run of rejections: believe the screen rather than the stored
        # baseline. The jump is deliberately NOT counted as experience gained,
        # because what happened across the bad stretch is unknown and inventing
        # a number for it would be worse than admitting the gap.
        if self.stuck >= STUCK_LIMIT:
            return self._recover(value, percent, estimate)

        if self.level is not None:
            return self._update_known_level(value, percent)

        # Below here the level is still unknown, so everything is inferred from
        # the reading alone. Zero percent says nothing about the requirement.
        if estimate is None:
            return self._reject()
        return self._update_unknown_level(value, percent, estimate)

    def _reject(self):
        self.rejected += 1
        self.stuck += 1
        return False

    def _accept(self, value):
        self.value = value
        self.last_good = time.time()
        self.stuck = 0
        return True

    def _recover(self, value, percent, estimate):
        self.recoveries += 1
        # Re-derive the level too. A long bad stretch is exactly when a level up
        # could have been missed, and keeping the old level would mean checking
        # every later reading against the wrong requirement.
        if self.identify(value, percent) is None:
            self.level = None
            if estimate is not None:
                self.requirement = estimate
        return self._accept(value)

    def _update_known_level(self, value, percent):
        """The exact path, taken once the level is known.

        With the level known the curve gives the exact requirement, so the test
        stops being "is this close to what I expected" and becomes "does the
        game's own arithmetic reproduce this". Measured against the labelled
        captures, that catches 97.9% of every possible single-digit corruption
        of the value and every corruption of the percentage. The survivors are
        off by one in the units digit, where one experience point is too small
        to move a figure shown to two decimals.
        """
        requirement = self.requirement
        here = expcurve.consistent(value, percent, self.level)
        nxt = self.level + 1
        there = (nxt <= expcurve.MAX_LEVEL
                 and expcurve.consistent(value, percent, nxt))
        standing = self.value / requirement * 100.0

        # One reading fits every level: zero experience at zero percent. It is
        # either a level up that landed exactly on the boundary or a death that
        # emptied the bar, and the numbers cannot say which. Where you were
        # standing can. A death takes five percent, so it can only empty a bar
        # that held less than that; and a level up has to be reachable from
        # where you were, which from anywhere but the top of the bar it is not.
        if here and there:
            if standing + MAX_GAIN_PCT_PER_SAMPLE >= 100.0:
                here = False
            else:
                there = False

        if here:
            return self._same_level(value, requirement)
        if there:
            return self._next_level(value, requirement, nxt)
        return self._reject()

    def _same_level(self, value, requirement):
        if value < self.value:
            # Backwards within a level is a death, and a death is exactly five
            # percent. Anything else is a misread that happens to be
            # arithmetically valid.
            #
            # Unless there was not five percent to take. Dying early in a level
            # empties the bar rather than going negative, so a drop to zero is a
            # death too, whatever fraction it works out to.
            lost = (self.value - value) / requirement * 100.0
            floored = value == 0 and lost <= DEATH_PENALTY_PCT + 0.1
            if not floored and abs(lost - DEATH_PENALTY_PCT) > 0.1:
                return self._reject()
        else:
            gained = (value - self.value) / requirement * 100.0
            if gained > MAX_GAIN_PCT_PER_SAMPLE:
                return self._reject()
            if value > self.value:
                self.gained += value - self.value
                self.last_gain = time.time()
        return self._accept(value)

    def _next_level(self, value, requirement, level):
        """Step to the next level, with the requirement exact from that instant.

        This is what used to break. The old code took the requirement by
        dividing the new reading, so twelve experience at 0.03% gave about forty
        thousand where the real answer was forty seven thousand, and every later
        reading was then checked against a number that was wrong.
        """
        # Finishing the old level plus whatever carried into the new one. A
        # plausible amount for half a second, or it is a misread that happens to
        # fit the next level's arithmetic.
        carried = max(0, requirement - self.value) + value
        if carried / requirement * 100.0 > MAX_GAIN_PCT_PER_SAMPLE:
            return self._reject()
        self.gained += carried
        self.last_gain = time.time()
        self.levels += 1
        self.adopt_level(level)
        return self._accept(value)

    def _update_unknown_level(self, value, percent, estimate):
        """The inferred path, used only before the level has been pinned down.

        A level up drops the value and resets the percentage near zero. All
        three have to hold: without the percentage tests any backwards misread
        looks like a level up and gets believed.
        """
        requirement = self.requirement
        levelled = bool(value < self.value and percent < 50 and requirement
                        and percent < (self.value / requirement * 100.0))

        if not levelled:
            if value < self.value:
                lost = (self.value - value) / requirement * 100.0
                if abs(lost - DEATH_PENALTY_PCT) > 0.1:
                    return self._reject()
            else:
                gained = (value - self.value) / requirement * 100.0
                if gained > MAX_GAIN_PCT_PER_SAMPLE:
                    return self._reject()
            # Within a level the requirement is a constant, so a reading that
            # implies a different one had a character misread. This has to be
            # tight: when the same shape is misread in both numbers, as in
            # 16,497 at 98.94% for 16,487 at 98.84%, the ratio barely moves and
            # the implied requirement lands only 0.029% out.
            if abs(estimate - requirement) / requirement > 0.0002:
                return self._reject()
            if value > self.value:
                self.gained += value - self.value
                self.last_gain = time.time()
            self.requirement = requirement * 0.9 + estimate * 0.1
        else:
            self.gained += max(0, requirement - self.value) + value
            self.last_gain = time.time()
            self.levels += 1
            self.requirement = estimate
        return self._accept(value)

    # -------------------------------------------------------------- clock --

    def start(self):
        if self.running:
            return
        self.running = True
        self.resumed_at = time.time()
        if self.started is None:
            self.started = time.time()

    def pause(self):
        if not self.running:
            return
        self.banked += time.time() - self.resumed_at
        self.resumed_at = None
        self.running = False

    def toggle(self):
        self.pause() if self.running else self.start()
        return self.running

    def forget_reading(self):
        """Drop the baseline without touching the clock or the totals.

        Used when the watched region moves or a reading is corrected: what is
        on screen is still trustworthy, what was stored about it is not.
        """
        self.value = None
        self.requirement = None
        self.level = None
        self.stuck = 0

    @property
    def elapsed(self):
        live = (time.time() - self.resumed_at
                if self.running and self.resumed_at else 0.0)
        return self.banked + live

    @property
    def per_hour(self):
        hours = self.elapsed / 3600.0
        return 0 if hours <= 0 else self.gained / hours

    @property
    def percent(self):
        if self.value is None or not self.requirement:
            return None
        return self.value / self.requirement * 100.0

    @property
    def percent_per_minute(self):
        """Session average, as a share of the CURRENT level, per minute.

        This is how a grinding spot gets judged: ten minutes in one place, and
        anything under about 0.5%/min is not worth staying for. Expressed
        against the current level's requirement rather than raw experience,
        because the same experience per hour is worth steadily less as the
        levels get longer.
        """
        if not self.requirement:
            return None
        return self.per_hour / self.requirement * 100.0 / 60.0

    def idle_for(self):
        """Seconds since experience last went up, or None if it never has."""
        if self.last_gain is None:
            return None
        return time.time() - self.last_gain

    @property
    def to_level(self):
        if not self.requirement or self.value is None:
            return None
        remaining = self.requirement - self.value
        rate = self.per_hour
        if rate <= 0 or remaining <= 0:
            return None
        return remaining / rate * 3600.0
