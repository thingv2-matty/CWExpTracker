"""
The session recap: how the grind actually went, block by block.

The running averages on the readout flatten everything. Three hours at a good
rate and three hours of drifting average out to something unremarkable, and the
drifting is the part worth seeing. Cutting the session into fixed blocks shows
where the time actually went.
"""

import tkinter as tk

from ..theme import ACCENT, BG, DIM, FG, LINE, MONO, PANEL, WARN
from .format import clock, thousands

# A block has to be meaningfully better or worse than the session average
# before it is worth colouring. Everything wobbles a bit.
GOOD = 1.15
POOR = 0.85


def show(parent, session, minutes):
    """Open the recap for a session, cut into blocks of `minutes`."""
    window = tk.Toplevel(parent)
    window.title("Session recap")
    window.configure(bg=BG)
    window.resizable(False, False)
    window.attributes("-topmost", True)

    segments = session.segments(minutes * 60)
    _headline(window, session)
    tk.Frame(window, bg=LINE, height=1).pack(fill="x", padx=18, pady=(4, 0))

    if segments:
        _blocks(window, session, segments, minutes)
    else:
        tk.Label(window, text="  nothing to show yet  ", bg=BG, fg=DIM,
                 font=(MONO, 10)).pack(padx=24, pady=20)

    _footer(window, session, segments)

    tk.Button(window, text="CLOSE", command=window.destroy, bg=PANEL, fg=FG,
              activebackground=LINE, activeforeground=ACCENT, relief="flat",
              bd=0, font=(MONO, 10, "bold"), padx=16, pady=7,
              cursor="hand2").pack(pady=(4, 16))

    window.transient(parent)
    window.update_idletasks()
    _centre_on(window, parent)
    return window


def _centre_on(window, parent):
    x = parent.winfo_rootx() + (parent.winfo_width() - window.winfo_width()) // 2
    y = parent.winfo_rooty() + 40
    window.geometry("+%d+%d" % (max(0, x), max(0, y)))


def _row(parent, label, value, colour=FG, indent=18):
    line = tk.Frame(parent, bg=BG)
    line.pack(fill="x", padx=indent, pady=1)
    tk.Label(line, text=label, bg=BG, fg=DIM, font=(MONO, 9),
             width=18, anchor="w").pack(side="left")
    tk.Label(line, text=value, bg=BG, fg=colour, font=(MONO, 10, "bold"),
             anchor="w").pack(side="left")


def _headline(window, session):
    tk.Label(window, text="SESSION RECAP", bg=BG, fg=DIM, font=(MONO, 9),
             anchor="w").pack(fill="x", padx=18, pady=(16, 2))
    tk.Label(window, text=thousands(session.per_hour), bg=BG, fg=ACCENT,
             font=(MONO, 26, "bold"), anchor="w").pack(fill="x", padx=18)
    tk.Label(window, text="EXP / HOUR OVERALL", bg=BG, fg=DIM, font=(MONO, 8),
             anchor="w").pack(fill="x", padx=18, pady=(0, 10))

    _row(window, "GRINDING FOR", clock(session.elapsed))
    _row(window, "TOTAL EXP", thousands(session.gained))
    _row(window, "TOTAL %", "%.1f %%" % session.percent_gained)
    _row(window, "LEVELS", str(session.levels))


def _blocks(window, session, segments, minutes):
    tk.Label(window, text="  %d MINUTE BLOCKS  " % minutes, bg=BG, fg=DIM,
             font=(MONO, 9), anchor="w").pack(fill="x", padx=18, pady=(10, 4))

    average = session.per_hour or 1
    for index, seg in enumerate(segments, start=1):
        share = seg["per_hour"] / average
        colour = FG
        if seg["complete"]:
            colour = ACCENT if share >= GOOD else WARN if share <= POOR else FG

        label = "%d.  %s-%s" % (index, _mins(seg["from"]), _mins(seg["to"]))
        value = "%8s/hr   %.2f %%/min%s" % (
            thousands(seg["per_hour"]), seg["percent_per_minute"],
            "" if seg["complete"] else "   so far")
        _row(window, label, value, colour)


def _mins(seconds):
    return "%d" % round(seconds / 60)


def _footer(window, session, segments):
    done = [s for s in segments if s["complete"]]
    if not done:
        return
    tk.Frame(window, bg=LINE, height=1).pack(fill="x", padx=18, pady=(10, 6))

    best = max(done, key=lambda s: s["per_hour"])
    worst = min(done, key=lambda s: s["per_hour"])
    spread = (best["per_hour"] / worst["per_hour"]) if worst["per_hour"] else 0

    _row(window, "BEST BLOCK",
         "#%d   %s/hr" % (done.index(best) + 1, thousands(best["per_hour"])),
         ACCENT)
    _row(window, "WORST BLOCK",
         "#%d   %s/hr" % (done.index(worst) + 1, thousands(worst["per_hour"])),
         WARN)
    if spread:
        _row(window, "BEST vs WORST", "%.1fx" % spread)
    _row(window, "LONGEST DRY SPELL", clock(session.longest_dry_spell()))
