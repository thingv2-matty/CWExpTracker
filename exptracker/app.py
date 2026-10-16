"""
Wiring: the clock, the main loop, and the handful of commands the panel fires.

An earlier version did all of this in one function with six closures over its
locals. The App below holds the same state on an object instead, which is the
same thing with names you can find.
"""

import argparse
import sys
import time
import tkinter as tk

from . import paths
from .capture import grab, pick_region
from .config import Config
from .models import CharacterModels
from .reader import Reader
from .session import Session, infer_missing, parse
from .ui.panel import Panel
from .ui.teaching import correct_reading, teach_from_console, teach_unknowns

# How often to sample. The numbers move slowly, so this is about responsiveness
# of the display rather than accuracy.
PERIOD = 0.5

# Templates learned while running are written back to disk, but not on every
# tick: the config is tens of kilobytes and a tick is half a second.
SAVE_EVERY_SECONDS = 20


class App:
    """The running tracker."""

    def __init__(self, config, region, reader):
        self.config = config
        self.region = region
        self.reader = reader
        self.session = Session()

        self.root = tk.Tk()
        # Tkinter catches anything a button callback raises and prints it to
        # stderr, which goes nowhere when started from the shortcut. That is
        # how MAP ZONE could fail with no error, no crash file and no clue.
        self.root.report_callback_exception = self._callback_failed
        self.panel = Panel(self.root, self.session, self)
        self._dirty = False
        self._saved_at = time.time()

        # Artwork is optional and remembered between runs. Restoring it after
        # the panel exists means a missing or deleted asset just falls back to
        # the plain theme rather than stopping startup.
        self._restoring = True
        if config.background:
            self.panel.use_background(config.background)
        if config.digits:
            self.panel.use_digits(config.digits)
        self._restoring = False

    # ----------------------------------------------------------- commands --
    # These are what the panel calls. Names match the buttons.

    def toggle(self):
        return self.session.toggle()

    def _callback_failed(self, kind, value, tb):
        """Surface an error from a button rather than losing it to stderr."""
        import traceback

        detail = "".join(traceback.format_exception(kind, value, tb))
        try:
            paths.CRASH.write_text(detail, encoding="utf-8")
        except OSError:
            pass
        print(detail, file=sys.stderr)
        self.panel.problem = "%s: %s  (see crash.txt)" % (kind.__name__, value)
        # Never leave the window hidden because something failed mid-way.
        try:
            self.root.deiconify()
            self.panel.refresh()
        except tk.TclError:
            pass

    def remember_appearance(self, background, digits):
        """Keep the chosen artwork for next time."""
        if self._restoring:
            return
        self.config.background = background
        self.config.digits = digits
        self.config.save()

    def reset(self):
        self.session = Session()
        self.panel.session = self.session
        self.panel.auto_learned = 0
        self.panel.problem = ""
        self.panel.sync_button()

    def learn(self):
        if teach_unknowns(self.root, self.region, self.reader):
            self._store_templates()

    def correct(self):
        resume = self._suspend()
        learned, displaced = correct_reading(self.root, self.region, self.reader)
        if learned or displaced:
            self._store_templates()
            # The baseline was built from a reading now known to be wrong.
            self.session.forget_reading()
        self._resume(resume)

    def remap(self):
        """Draw the watched zone again, without losing the session.

        The picker hides the window for its screenshot and brings it straight
        back. Hiding it from here as well used to leave the parent withdrawn
        for the whole picker, which never then became viewable, so the tracker
        hung with no window and no way to dismiss it.
        """
        resume = self._suspend()
        try:
            picked = pick_region(countdown=0, parent=self.root)
        finally:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
        if picked:
            self.region = picked
            self.config.region = picked
            self.config.save()
            # The baseline came from the old zone, so start the reading over.
            # The clock and the totals are untouched: moving the window you are
            # watching does not mean you stopped grinding.
            self.session.forget_reading()
        self._resume(resume)

    def _suspend(self):
        was_running = self.session.running
        self.session.pause()
        self.panel.sync_button()
        return was_running

    def _resume(self, was_running):
        if was_running:
            self.session.start()
        self.panel.sync_button()

    # ------------------------------------------------------------ storage --

    def _store_templates(self):
        from . import templates as templates_module
        self.config.templates = templates_module.to_json(self.reader.templates)
        self.config.overrides = self.reader.overrides
        self.config.save()
        self._dirty = False
        self._saved_at = time.time()

    def _store_later(self):
        self._dirty = True

    def _store_if_due(self):
        if self._dirty and time.time() - self._saved_at > SAVE_EVERY_SECONDS:
            self._store_templates()

    # --------------------------------------------------------------- loop --

    def tick(self):
        # Nothing is read or counted while paused. The clock stopping and the
        # reading stopping have to be the same thing, or a pause would quietly
        # keep accumulating experience against a frozen timer.
        if self.session.running:
            try:
                self._take_reading()
                self.panel.problem = ""
            except Exception as exc:          # keep the panel alive
                # Started from a shortcut there is no console for this to go to,
                # so it has to appear in the window or it vanishes.
                self.panel.problem = "read failed: %s" % exc
            self._store_if_due()
        self.panel.refresh()
        self.root.after(int(PERIOD * 1000), self.tick)

    def _take_reading(self):
        text, glyphs = self.reader.read(grab(self.region))

        # A single unreadable character can usually be worked out from the
        # arithmetic, and once it is worked out the shape that produced it is
        # worth keeping.
        if "?" in text:
            solved = infer_missing(text, self.session.requirement)
            if solved:
                text = solved

        self.panel.unknown = text if "?" in text else ""
        reading = parse(text)
        if not reading or not self.session.update(*reading):
            return

        # The reading survived every movement test, so it is trustworthy and its
        # shapes are worth keeping. This is what makes the thing improve by
        # running: a digit drawn at a position never seen before gets added the
        # moment a reading containing it is believed. Learning only from
        # validated readings is what stops a misreading teaching itself.
        for glyph, ch in zip(glyphs, text):
            if ch == "?":
                continue
            added, _ = self.reader.learn(ch, glyph.bitmap)
            if added:
                self.panel.auto_learned += 1
                self._store_later()

    def run(self):
        print("\n  Ready. Press START in the window to begin.\n")
        self.tick()
        self.root.mainloop()
        if self._dirty:
            self._store_templates()
        return 0


# ---------------------------------------------------------------- startup --

def models_can_read(region):
    """Whether the stacked models read a live capture on their own.

    This is what makes the tracker shareable. The models are the hard-won part
    and they travel with the repository, so somebody starting fresh should not
    be marched through teaching fourteen characters that are already known. But
    they are pixel masks tied to the size the font renders at, so they only
    travel to a screen that renders it the same. Rather than assume either way,
    take one capture and see.
    """
    models = CharacterModels.load(paths.MODELS)
    if not models or not region:
        return False
    try:
        from .segment import drop_badge, segment
        glyphs = drop_badge(segment(grab(region)))
    except (OSError, ValueError):
        return False
    if len(glyphs) < 8:
        return False
    return all(models.match(glyph.bitmap) is not None for glyph in glyphs)


def choose_region(config):
    print("\n  Pick the EXP readout.")
    print("  Put the game where you want it, then drag a box around the")
    print("  'EXP. 10,155 [74.04%]' line, with a little air around it.")
    print("  Including the EXP. badge is fine, it gets ignored. Leaving the")
    print("  progress bar out is tidier but not required.\n")
    region = pick_region()
    if not region:
        print("  cancelled.")
        return None
    config.region = region
    config.save()
    print("  region saved: %dx%d at (%d, %d)"
          % (region["width"], region["height"], region["left"], region["top"]))
    return region


def run_first_time_teaching(config, region, reader):
    """Keep offering rather than exiting on a typo.

    Teaching is the fiddly part, so it is the part that should forgive a wrong
    answer and let the whole setup not start again.
    """
    while True:
        teach_from_console(region, reader)
        if reader.templates:
            config.templates = _templates_json(reader)
            config.save()
            return region
        print("\n  Nothing learned yet.")
        choice = input("  [t] try again   [r] re-pick the region   [q] quit : ")
        choice = choice.strip().lower()
        if choice == "q":
            return None
        if choice == "r":
            picked = pick_region()
            if picked:
                region = picked
                config.region = picked
                config.save()


def _templates_json(reader):
    from . import templates as templates_module
    return templates_module.to_json(reader.templates)


def main(argv=None):
    parser = argparse.ArgumentParser(description="MapleStory EXP tracker")
    parser.add_argument("--region", action="store_true",
                        help="pick the screen region again")
    parser.add_argument("--teach", action="store_true",
                        help="re-learn the characters by hand")
    parser.add_argument("--debug", action="store_true",
                        help="dump one capture and every candidate score, then exit")
    args = parser.parse_args(argv)

    config = Config.load()
    region = config.region
    reader = Reader.load(config, paths.MODELS)

    if args.region or not region:
        region = choose_region(config)
        if not region:
            return 1

    if args.debug:
        from .debug import dump
        return dump(region, reader)

    if args.teach or (not reader.templates and not models_can_read(region)):
        region = run_first_time_teaching(config, region, reader)
        if region is None:
            return 1
    elif not reader.templates:
        print("\n  The character models read this bar already, so there is")
        print("  nothing to teach. Starting up.")

    return App(config, region, reader).run()


if __name__ == "__main__":
    sys.exit(main())
