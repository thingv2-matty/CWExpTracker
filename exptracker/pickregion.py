"""
The region picker, as a program of its own.

    python -m exptracker.pickregion

Prints the chosen region as JSON on stdout, or nothing if it was cancelled.

This exists because of where the picker has to work: over a fullscreen game.
Run as a child window of the already-running tracker, it loses the z-order
fight and opens behind the game, where it cannot be seen, clicked or dismissed
while holding an input grab. Run as the only window of a freshly started
process, it comes up in front, which is how picking the region worked in the
first place before there was a button for it.

It does not need the game in front while you drag, because what you are
dragging on is a screenshot taken a moment earlier, not the live screen.

Running it separately has a second benefit: however badly it goes, it cannot
take the tracker with it.
"""

import json
import sys

from .capture import pick_region


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    countdown = 0
    if "--countdown" in argv:
        countdown = int(argv[argv.index("--countdown") + 1])

    region = pick_region(countdown=countdown, parent=None)
    if not region:
        return 1
    # stdout is the result channel, so anything else must not land on it
    sys.stdout.write(json.dumps(region))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
