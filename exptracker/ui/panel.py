"""
The readout window and the controls over the session.

Drawn on a canvas rather than built out of labels, because a label cannot sit
over a background image: tkinter widgets have no transparency, so every label
would be a dark rectangle punched through the artwork. On a canvas the text is
just marks on top of the picture.

Everything is optional. With no artwork in assets/ this draws the plain dark
theme and nothing below changes.
"""

import time
import tkinter as tk

from .. import assets
from ..theme import ACCENT, BG, DIM, FG, LINE, MONO, PANEL, WARN
from . import sprites
from .format import clock, thousands

SILENCE_WARNING_SECONDS = 10

ROWS = [
    ("lv", "LEVEL"),
    ("ppm", "% PER MINUTE"),
    ("ttl", "TIME TO LEVEL"),
    ("session", "GRINDING FOR"),
    ("gained", "EXP GAINED"),
    ("levels", "LEVELS"),
    ("now", "CURRENT"),
]

# White with a black outline, so the same text stays legible on a dark panel
# and on a bright patch of Henesys alike.
OUTLINE = "#000000"
OUTLINE_STEPS = [(-1, -1), (0, -1), (1, -1), (-1, 0),
                 (1, 0), (-1, 1), (0, 1), (1, 1)]

PAD = 20
HEADLINE_HEIGHT = 58


class Panel:
    """The window. Reads from a Session, never writes to one."""

    def __init__(self, root, session, actions):
        self.root = root
        self.session = session
        self.actions = actions
        self.unknown = ""
        self.auto_learned = 0
        self.problem = ""

        self.background_name = None
        self.digits_name = None
        self._digits = None
        self._background = None          # the source image
        self._scaled = None              # fitted to the current window
        self._scaled_for = None
        self._number_image = None
        self._number_text = None
        self._keep = []                  # tkinter drops unreferenced images

        root.configure(bg=BG)
        root.title("EXP")
        # Size AND position. Given size alone, Tk owns the placement and will
        # happily move the window out from under you later; pinning both means
        # it stays where it was dragged, and remembers between runs.
        root.geometry(self.actions.remembered_window() or "420x470+120+120")
        root.minsize(380, 430)
        root.attributes("-topmost", True)
        root.resizable(True, True)

        bar = tk.Frame(root, bg=BG)
        bar.pack(side="bottom", fill="x", padx=18, pady=(10, 16))
        self.canvas = tk.Canvas(root, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(side="top", fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.refresh())
        root.bind("<Configure>", self._remember_position)

        self._build_controls(bar)

    # --------------------------------------------------------- appearance --

    def use_background(self, name):
        from PIL import Image

        self.background_name = name
        self._background = None
        self._scaled = None
        # and the cache key, or swapping pictures at the same window size looks
        # like a cache hit and redraws nothing
        self._scaled_for = None
        path = assets.background_path(name)
        if path is None:
            # named something that is not there any more
            self.background_name = None
        else:
            try:
                self._background = Image.open(path).convert("RGB")
            except OSError:
                self.background_name = None
        self.actions.remember_appearance(self.background_name, self.digits_name)
        self.refresh()

    def use_digits(self, name):
        self.digits_name = name
        self._digits = assets.DigitSet.load(name) if name else None
        if name and self._digits is None:
            self.digits_name = None
        self._number_text = None
        self.actions.remember_appearance(self.background_name, self.digits_name)
        self.refresh()

    # -------------------------------------------------------------- build --

    def _build_controls(self, bar):
        self.go = self._button(bar, "START", self._toggle, primary=True)
        self.go.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._button(bar, "RESET", self.actions.reset).pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        self._button(bar, "MAP ZONE", self.actions.remap).pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        self.more = self._button(bar, "···", self._show_menu)
        self.more.pack(side="left")
        self.menu = self._build_menu()

    def _build_menu(self):
        def styled(parent=None):
            return tk.Menu(parent or self.root, tearoff=0, bg=PANEL, fg=FG,
                           activebackground=ACCENT, activeforeground=BG,
                           bd=0, relief="flat", font=(MONO, 10))

        menu = styled()
        backgrounds = assets.backgrounds()
        digit_sets = assets.number_sets()

        if backgrounds:
            self._background_choice = tk.StringVar(value="")
            sub = styled(menu)
            sub.add_radiobutton(label="  None  ", value="",
                                variable=self._background_choice,
                                command=lambda: self.use_background(None))
            for name in backgrounds:
                sub.add_radiobutton(
                    label="  %s  " % name, value=name,
                    variable=self._background_choice,
                    command=lambda n=name: self.use_background(n))
            menu.add_cascade(label="  Background  ", menu=sub)

        if digit_sets:
            self._digits_choice = tk.StringVar(value="")
            sub = styled(menu)
            sub.add_radiobutton(label="  Plain  ", value="",
                                variable=self._digits_choice,
                                command=lambda: self.use_digits(None))
            for name in digit_sets:
                sub.add_radiobutton(
                    label="  %s  " % name, value=name,
                    variable=self._digits_choice,
                    command=lambda n=name: self.use_digits(n))
            menu.add_cascade(label="  Numbers  ", menu=sub)

        self.idle_pause = tk.BooleanVar(value=self.actions.remembered_idle_pause())
        menu.add_checkbutton(
            label="  Pause when nothing is dying  ",
            variable=self.idle_pause,
            command=lambda: self.actions.remember_idle_pause(self.idle_pause.get()),
            selectcolor=ACCENT)

        if backgrounds or digit_sets:
            menu.add_separator()
        else:
            menu.add_command(
                label="  No artwork found. See the README.  ", state="disabled")
            menu.add_separator()

        menu.add_command(label="  Teach unknown characters  ",
                         command=self.actions.learn)
        menu.add_command(label="  Correct a wrong reading  ",
                         command=self.actions.correct)
        return menu

    def _button(self, parent, text, command, primary=False):
        return tk.Button(
            parent, text=text, command=command,
            bg=ACCENT if primary else PANEL,
            fg=BG if primary else FG,
            activebackground=ACCENT if primary else LINE,
            activeforeground=BG if primary else FG,
            relief="flat", bd=0, font=(MONO, 10, "bold"),
            padx=10, pady=7, cursor="hand2",
            highlightthickness=1, highlightbackground=LINE,
        )

    # ------------------------------------------------------------ actions --

    def _remember_position(self, event):
        """Keep note of where the window is, so it can be put back."""
        if event.widget is not self.root:
            return
        self.actions.remember_window(self.root.geometry())

    def _show_menu(self):
        x = self.more.winfo_rootx()
        y = self.more.winfo_rooty() + self.more.winfo_height()
        try:
            self.menu.tk_popup(x, y)
        finally:
            self.menu.grab_release()

    def _toggle(self):
        self.actions.toggle()
        self.sync_button()

    def sync_button(self):
        self.go.config(text="PAUSE" if self.session.running else "START")

    # ------------------------------------------------------------ drawing --

    @property
    def _label_colour(self):
        """Labels go white over artwork and stay dim on the plain theme.

        The outline exists so text survives a bright patch of Henesys. With no
        picture underneath there is nothing to survive, and the dimmer grey
        gives the readout some hierarchy back.
        """
        return FG if self._background is not None else DIM

    def _text(self, x, y, text, fill=FG, size=10, bold=False, anchor="w"):
        """Text with a black outline, drawn by stamping it eight times."""
        font = (MONO, size, "bold") if bold else (MONO, size)
        for dx, dy in OUTLINE_STEPS:
            self.canvas.create_text(x + dx, y + dy, text=text, fill=OUTLINE,
                                    font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font,
                                anchor=anchor)

    def _draw_background(self, width, height):
        if self._background is None:
            return
        from PIL import Image, ImageTk

        if self._scaled_for != (width, height):
            source = self._background
            scale = max(width / source.width, height / source.height)
            size = (max(1, int(source.width * scale)),
                    max(1, int(source.height * scale)))
            fitted = source.resize(size, Image.LANCZOS)
            left = (fitted.width - width) // 2
            top = (fitted.height - height) // 2
            self._scaled = fitted.crop((left, top, left + width, top + height))
            self._scaled_for = (width, height)
        photo = ImageTk.PhotoImage(self._scaled)
        self._keep.append(photo)
        self.canvas.create_image(0, 0, image=photo, anchor="nw")

    def _draw_headline(self, x, y, width):
        """Experience per hour, in the damage font when one is loaded."""
        from PIL import ImageTk

        if self._digits is None:
            self._text(x, y, thousands(self.session.per_hour), fill=ACCENT,
                       size=34, bold=True, anchor="nw")
            return

        # No separator in the damage font: the game writes numbers straight
        # through and overlaps the digits, so there is nowhere for a comma.
        text = str(int(self.session.per_hour))

        if text != self._number_text:
            self._number_image = sprites.fit(self._digits, text,
                                             width, HEADLINE_HEIGHT)
            self._number_text = text
        if self._number_image is None:
            self._text(x, y, text, fill=ACCENT, size=34, bold=True, anchor="nw")
            return
        photo = ImageTk.PhotoImage(self._number_image)
        self._keep.append(photo)
        self.canvas.create_image(x, y, image=photo, anchor="nw")

    def refresh(self):
        canvas = self.canvas
        canvas.delete("all")
        self._keep.clear()

        width = canvas.winfo_width() or 420
        height = canvas.winfo_height() or 400
        self._draw_background(width, height)

        session = self.session
        y = 16
        self._text(PAD, y, "EXP TRACKER", fill=self._label_colour, size=9, anchor="nw")
        state, colour = self._state(session)
        self._text(width - PAD, y, state, fill=colour, size=9, bold=True,
                   anchor="ne")

        y += 20
        self._draw_headline(PAD, y, width - PAD * 2)
        y += HEADLINE_HEIGHT + 4
        self._text(PAD, y, "EXP / HOUR", fill=self._label_colour, size=9, anchor="nw")

        y += 20
        canvas.create_line(PAD, y, width - PAD, y,
                           fill=FG if self._background is not None else LINE)

        y += 12
        for key, label in ROWS:
            self._text(PAD, y, label, fill=self._label_colour, size=10, anchor="nw")
            self._text(PAD + 150, y, self._value(key, session), fill=FG,
                       size=11, bold=True, anchor="nw")
            y += 22

        note, colour = self._status(session)
        if note:
            self._text(PAD, height - 22, note, fill=colour, size=9, anchor="nw")

    def _value(self, key, session):
        if key == "lv":
            return str(session.level) if session.level else "working it out"
        if key == "ppm":
            rate = session.percent_per_minute
            return "-" if rate is None else "%.2f %%" % rate
        if key == "ttl":
            return clock(session.to_level)
        if key == "session":
            return clock(session.elapsed)
        if key == "gained":
            return thousands(session.gained)
        if key == "levels":
            return str(session.levels)
        percent = session.percent
        if percent is None:
            return "-"
        return "%s  %.2f%%" % (thousands(session.value), percent)

    @staticmethod
    def _state(session):
        if not session.started:
            return "READY", DIM
        return ("RUNNING", ACCENT) if session.running else ("PAUSED", WARN)

    def _status(self, session):
        stale = (session.running and session.last_good
                 and (time.time() - session.last_good) > SILENCE_WARNING_SECONDS)
        if self.problem:
            return self.problem, WARN
        if not session.running and session.started:
            return "paused, the clock is stopped", DIM
        if self.unknown:
            return "reading  %s" % self.unknown, ACCENT
        if stale:
            return "not reading the bar", WARN
        if self.auto_learned:
            return "learned %d sprite shapes" % self.auto_learned, DIM
        return "", DIM
