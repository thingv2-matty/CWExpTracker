"""Turning numbers into something readable. No logic, only presentation."""


def clock(seconds):
    """H:MM:SS, or placeholder dashes when there is nothing to say yet."""
    if seconds is None:
        return "--:--:--"
    seconds = int(seconds)
    return "%d:%02d:%02d" % (seconds // 3600, (seconds % 3600) // 60, seconds % 60)


def thousands(n):
    return "{:,}".format(int(n))
