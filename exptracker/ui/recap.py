"""
The session recap: how the grind actually went, block by block.

The running averages on the readout flatten everything. Three hours at a good
rate and three hours of drifting average out to something unremarkable, and the
drifting is the part worth seeing. Cutting the session into fixed blocks shows
where the time actually went.

Drawn on a canvas for the same reason the readout is: so it can wear the same
background. A window that ignores the theme the tracker is wearing looks like a
different program.
"""

import tkinter as tk
import tkinter.font as tkfont

from ..theme import ACCENT, BG, DIM, FG, LINE, MONO, PANEL, WARN
from . import facts
from .format import clock, thousands

# A block has to be meaningfully better or worse than the session average
# before it is worth colouring. Everything wobbles a bit.
GOOD = 1.15
POOR = 0.85

WIDTH = 380
PAD = 20
LINE_HEIGHT = 21

OUTLINE_STEPS = [(-1, -1), (0, -1), (1, -1), (-1, 0),
                 (1, 0), (-1, 1), (0, 1), (1, 1)]

# The easter egg ends in emoji, which Consolas does not have, so Tk falls
# back to Segoe UI Emoji and GDI draws it in one colour. At the 9pt the rest
# of the fact is set in, the sunglasses are an unreadable blob. Drawn a few
# points up they land, and the single colour is the accent, which suits.
FLOURISH_SIZE = 14


class Recap:
    """A window that borrows the readout's look."""

    def __init__(self, parent, session, minutes, panel):
        self.session = session
        self.minutes = minutes
        self.panel = panel
        self.segments = session.segments(minutes * 60)
        self.fact = facts.pick(session, self.segments)
        self._keep = []

        self.window = tk.Toplevel(parent)
        self.window.title("Session recap")
        self.window.configure(bg=BG)
        self.window.resizable(False, False)
        self.window.attributes("-topmost", True)

        height = self._measure()
        self.canvas = tk.Canvas(self.window, bg=BG, width=WIDTH, height=height,
                                highlightthickness=0, bd=0)
        self.canvas.pack(side="top", fill="both", expand=True)

        bar = tk.Frame(self.window, bg=BG)
        bar.pack(side="bottom", fill="x", padx=PAD, pady=(6, 14))
        tk.Button(bar, text="CLOSE", command=self.window.destroy, bg=PANEL,
                  fg=FG, activebackground=LINE, activeforeground=ACCENT,
                  relief="flat", bd=0, font=(MONO, 10, "bold"), pady=7,
                  cursor="hand2", highlightthickness=1,
                  highlightbackground=LINE).pack(fill="x")

        self.window.transient(parent)
        self.canvas.bind("<Configure>", lambda _e: self.draw())
        self.draw()
        self.window.update_idletasks()
        self._place(parent)

    # ------------------------------------------------------------ layout --

    def _measure(self):
        rows = 5                                   # headline block
        rows += 1 + len(self.segments) + 1         # blocks heading and list
        if any(s["complete"] for s in self.segments):
            rows += 4                              # best, worst, spread, dry
        if self.fact:
            rows += 3
        return 120 + rows * LINE_HEIGHT

    def _place(self, parent):
        x = parent.winfo_rootx() + (parent.winfo_width()
                                    - self.window.winfo_width()) // 2
        y = parent.winfo_rooty() + 30
        self.window.geometry("+%d+%d" % (max(0, x), max(0, y)))

    @property
    def _dim(self):
        """Labels go white over artwork and stay dim on the plain theme."""
        return FG if self.panel.has_background else DIM

    # ----------------------------------------------------------- drawing --

    def _text(self, x, y, text, fill=FG, size=10, bold=False, anchor="nw"):
        font = (MONO, size, "bold") if bold else (MONO, size)
        for dx, dy in OUTLINE_STEPS:
            self.canvas.create_text(x + dx, y + dy, text=text, fill="#000000",
                                    font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font,
                                anchor=anchor)

    def _row(self, y, label, value, colour=FG):
        self._text(PAD, y, label, fill=self._dim, size=9)
        self._text(PAD + 130, y, value, fill=colour, size=10, bold=True)
        return y + LINE_HEIGHT

    def draw(self):
        self.canvas.delete("all")
        self._keep.clear()
        width = self.canvas.winfo_width() or WIDTH
        height = self.canvas.winfo_height() or self._measure()
        self.panel.paint_background(self.canvas, width, height, self._keep)

        y = 14
        self._text(PAD, y, "SESSION RECAP", fill=self._dim, size=9)
        y += 18
        self._text(PAD, y, thousands(self.session.per_hour), fill=ACCENT,
                   size=24, bold=True)
        y += 34
        self._text(PAD, y, "EXP / HOUR OVERALL", fill=self._dim, size=8)
        y += 22

        y = self._row(y, "GRINDING FOR", clock(self.session.elapsed))
        y = self._row(y, "TOTAL EXP", thousands(self.session.gained))
        y = self._row(y, "TOTAL %", "%.1f %%" % self.session.percent_gained)
        y = self._row(y, "LEVELS", str(self.session.levels))

        y += 6
        self.canvas.create_line(PAD, y, width - PAD, y,
                                fill=FG if self.panel.has_background else LINE)
        y += 8

        y = self._blocks(y)
        y = self._footer(y)
        self._fact(y, width)

    def _blocks(self, y):
        self._text(PAD, y, "%d MINUTE BLOCKS" % self.minutes,
                   fill=self._dim, size=9)
        y += LINE_HEIGHT
        if not self.segments:
            return self._row(y, "", "nothing to show yet", self._dim)

        average = self.session.per_hour or 1
        for index, seg in enumerate(self.segments, start=1):
            share = seg["per_hour"] / average
            colour = FG
            if seg["complete"]:
                colour = ACCENT if share >= GOOD else WARN if share <= POOR else FG
            label = "%d.  %s-%s min" % (index, _mins(seg["from"]),
                                        _mins(seg["to"]))
            value = "%9s/hr  %.2f%%%s" % (
                thousands(seg["per_hour"]), seg["percent_per_minute"],
                "" if seg["complete"] else "  so far")
            y = self._row(y, label, value, colour)
        return y

    def _footer(self, y):
        done = [s for s in self.segments if s["complete"]]
        if not done:
            return y
        best = max(done, key=lambda s: s["per_hour"])
        worst = min(done, key=lambda s: s["per_hour"])
        spread = (best["per_hour"] / worst["per_hour"]) if worst["per_hour"] else 0

        y += 6
        y = self._row(y, "BEST BLOCK", "#%d   %s/hr"
                      % (done.index(best) + 1, thousands(best["per_hour"])),
                      ACCENT)
        y = self._row(y, "WORST BLOCK", "#%d   %s/hr"
                      % (done.index(worst) + 1, thousands(worst["per_hour"])),
                      WARN)
        if spread:
            y = self._row(y, "BEST vs WORST", "%.1fx" % spread)
        return self._row(y, "LONGEST DRY SPELL",
                         clock(self.session.longest_dry_spell()))

    def _fact(self, y, width):
        if not self.fact:
            return
        y += 8
        self.canvas.create_line(PAD, y, width - PAD, y,
                                fill=FG if self.panel.has_background else LINE)
        y += 10
        head, flourish = self._split_flourish(width - PAD * 2)
        self._wrapped(PAD, y, head, width - PAD * 2)
        if flourish:
            measured = tkfont.Font(family=MONO, size=9).measure(head)
            self._text(PAD + measured, y - 4, flourish, fill=ACCENT,
                       size=FLOURISH_SIZE)

    def _split_flourish(self, room):
        """The emoji tail of an easter egg, to be drawn larger than the rest.

        Only worth separating while the whole thing still fits on one line:
        once it wraps there is no single x to start the emoji from, so the
        fact goes out whole at the ordinary size instead.
        """
        if facts.NICE not in self.fact:
            return self.fact, None
        head = self.fact.split(facts.NICE)[0]
        font = tkfont.Font(family=MONO, size=9)
        if font.measure(head) + FLOURISH_SIZE * 3 > room:
            return self.fact, None
        return head, facts.NICE

    def _wrapped(self, x, y, text, width):
        """Canvas text does wrap, but only if told how wide it may be."""
        font = (MONO, 9)
        for dx, dy in OUTLINE_STEPS:
            self.canvas.create_text(x + dx, y + dy, text=text, fill="#000000",
                                    font=font, anchor="nw", width=width)
        self.canvas.create_text(x, y, text=text, fill=ACCENT, font=font,
                                anchor="nw", width=width)


def _mins(seconds):
    return "%d" % round(seconds / 60)


def show(parent, session, minutes, panel):
    return Recap(parent, session, minutes, panel).window
