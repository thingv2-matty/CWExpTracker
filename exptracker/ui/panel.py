"""The readout window and the controls over the session."""

import time
import tkinter as tk

from ..theme import ACCENT, BG, DIM, FG, LINE, MONO, PANEL, WARN
from .format import clock, thousands

# How long the reading can stall before the panel says so.
SILENCE_WARNING_SECONDS = 10

ROWS = [
    ("lv", "LEVEL"),
    ("ttl", "TIME TO LEVEL"),
    ("session", "GRINDING FOR"),
    ("gained", "EXP GAINED"),
    ("levels", "LEVELS"),
    ("now", "CURRENT"),
]


class Panel:
    """The window. Reads from a Session, never writes to one."""

    def __init__(self, root, session, actions):
        """actions is an object with reset, learn, toggle, correct and remap."""
        self.root = root
        self.session = session
        self.actions = actions
        self.unknown = ""
        self.auto_learned = 0
        self.problem = ""

        root.configure(bg=BG)
        root.title("EXP")
        root.geometry("420x470")
        root.minsize(380, 430)
        root.attributes("-topmost", True)
        # Resizable on purpose. Locked at a size that turned out to be shorter
        # than the contents, the controls were clipped off the bottom edge and
        # there was no way to get at them.
        root.resizable(True, True)

        # The controls are packed FIRST, against the bottom, so they always have
        # their space. Anything that has to give way gives way in the middle.
        bar = tk.Frame(root, bg=BG)
        bar.pack(side="bottom", fill="x", padx=18, pady=(10, 16))

        self._build_header(root)
        self._build_headline(root)
        self._build_rows(root)

        self.status = tk.Label(root, text="", bg=BG, fg=DIM, font=(MONO, 9),
                               anchor="w", wraplength=360, justify="left")
        self.status.pack(fill="x", padx=20, pady=(10, 0))

        self._build_controls(bar)

    # -------------------------------------------------------------- build --

    def _build_header(self, root):
        head = tk.Frame(root, bg=BG)
        head.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(head, text="EXP TRACKER", bg=BG, fg=DIM,
                 font=(MONO, 9), anchor="w").pack(side="left")
        self.state = tk.Label(head, text="READY", bg=BG, fg=DIM,
                              font=(MONO, 9, "bold"), anchor="e")
        self.state.pack(side="right")

    def _build_headline(self, root):
        self.big = tk.Label(root, text="0", bg=BG, fg=ACCENT,
                            font=(MONO, 40, "bold"), anchor="w")
        self.big.pack(fill="x", padx=20, pady=(6, 0))
        tk.Label(root, text="EXP / HOUR", bg=BG, fg=DIM, font=(MONO, 9),
                 anchor="w").pack(fill="x", padx=20, pady=(0, 14))
        tk.Frame(root, bg=LINE, height=1).pack(fill="x", padx=20)

    def _build_rows(self, root):
        self.rows = {}
        body = tk.Frame(root, bg=BG)
        body.pack(fill="x", padx=20, pady=(12, 0))
        for key, label in ROWS:
            row = tk.Frame(body, bg=BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=BG, fg=DIM, font=(MONO, 10),
                     width=16, anchor="w").pack(side="left")
            value = tk.Label(row, text="-", bg=BG, fg=FG,
                             font=(MONO, 12, "bold"), anchor="w")
            value.pack(side="left")
            self.rows[key] = value

    def _build_controls(self, bar):
        # LEARN and WRONG are dead weight while the models read everything, but
        # they are the only way back if they ever stop, so they move into a menu
        # rather than off the window.
        self.go = self._button(bar, "START", self._toggle, primary=True)
        self.go.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._button(bar, "RESET", self.actions.reset).pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        self._button(bar, "MAP ZONE", self.actions.remap).pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        self.more = self._button(bar, "···", self._show_menu)
        self.more.pack(side="left")

        self.menu = tk.Menu(self.root, tearoff=0, bg=PANEL, fg=FG,
                            activebackground=ACCENT, activeforeground=BG,
                            bd=0, relief="flat", font=(MONO, 10))
        self.menu.add_command(label="  Teach unknown characters  ",
                              command=self.actions.learn)
        self.menu.add_command(label="  Correct a wrong reading  ",
                              command=self.actions.correct)

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

    def refresh(self):
        session = self.session
        self.big.config(text=thousands(session.per_hour))
        self.rows["lv"].config(
            text=str(session.level) if session.level else "working it out")
        self.rows["ttl"].config(text=clock(session.to_level))
        self.rows["session"].config(text=clock(session.elapsed))
        self.rows["gained"].config(text=thousands(session.gained))
        self.rows["levels"].config(text=str(session.levels))
        percent = session.percent
        if percent is not None:
            self.rows["now"].config(
                text="%s  %.2f%%" % (thousands(session.value), percent))

        self._draw_state(session)
        self._draw_status(session)

    def _draw_state(self, session):
        if not session.started:
            self.state.config(text="READY", fg=DIM)
        elif session.running:
            self.state.config(text="RUNNING", fg=ACCENT)
        else:
            self.state.config(text="PAUSED", fg=WARN)

    def _draw_status(self, session):
        stale = (session.running and session.last_good
                 and (time.time() - session.last_good) > SILENCE_WARNING_SECONDS)
        if self.problem:
            self.status.config(text=self.problem, fg=WARN)
        elif not session.running and session.started:
            self.status.config(text="paused, the clock is stopped", fg=DIM)
        elif self.unknown:
            self.status.config(text="reading  %s" % self.unknown, fg=ACCENT)
        elif stale:
            self.status.config(text="not reading the bar", fg=WARN)
        elif self.auto_learned:
            self.status.config(
                text="learned %d sprite shapes" % self.auto_learned, fg=DIM)
        else:
            self.status.config(text="", fg=DIM)
