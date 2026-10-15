"""
EXP tracker for MapleStory Classic World.

Watches a region of the screen and works out experience per hour, time to the
next level, and how long you have been grinding. It never touches the game: it
reads pixels the way a person sitting next to you would, so there is no process
to attach to and nothing for anticheat to object to.

The modules, roughly in the order a reading passes through them:

    capture     put a region of the screen into an array
    segment     cut the strip into one bitmap per character
    models      decide what a character bitmap is, from stacked examples
    templates   the same job by nearest neighbour, used as a fallback
    reader      put those together and turn a capture into a string
    session     turn a string into experience per hour and time to level
    expcurve    the game's own experience formulas
    ui          the panel and the teaching dialogs
    app         wiring, the clock, and the main loop
"""

__version__ = "1.0.0"
