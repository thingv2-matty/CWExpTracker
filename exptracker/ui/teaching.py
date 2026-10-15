"""
The dialogs that let a person tell the tracker what it is looking at.

Only reached when the character models will not commit, which on a screen they
were built for is close to never. They matter anyway: they are the whole
recovery path on a screen the models have never seen.
"""

import tkinter as tk

import numpy as np

from .. import paths
from ..capture import grab
from ..segment import save_strip
from ..theme import ACCENT, BG, DIM, FG, MONO, PANEL, WARN

GLYPH_BG = (20, 22, 28)
GLYPH_FG = (242, 239, 232)


def _glyph_image(bitmap, scale=None):
    """Blow a character bitmap up to something a person can actually look at."""
    from PIL import Image

    height, width = bitmap.shape
    if scale is None:
        scale = max(6, min(18, 160 // max(width, 1)))
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:, :] = GLYPH_BG
    canvas[bitmap] = GLYPH_FG
    return Image.fromarray(canvas).resize((width * scale, height * scale),
                                          Image.NEAREST)


def _dialog(parent, title):
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg=BG)
    dlg.attributes("-topmost", True)
    dlg.resizable(False, False)
    return dlg


def _wait(parent, dlg):
    dlg.transient(parent)
    dlg.grab_set()
    parent.wait_window(dlg)


def ask_one_glyph(parent, bitmap, context, position):
    """Show a single unrecognised character and ask what it is.

    Retyping the whole readout to learn one new digit is the wrong trade, and it
    is the trade the first version made. Only ten digits exist, they turn up
    over a few minutes of play, and each should cost a single keystroke.
    """
    from PIL import ImageTk

    dlg = _dialog(parent, "New character")
    tk.Label(dlg, text="What character is this?", bg=BG, fg=FG,
             font=(MONO, 13, "bold")).pack(padx=24, pady=(18, 4))
    tk.Label(dlg, text="reading:  %s" % context, bg=BG, fg=DIM,
             font=(MONO, 11)).pack(padx=24)
    tk.Label(dlg, text="this is character %d of %d" % (position, len(context)),
             bg=BG, fg=DIM, font=(MONO, 9)).pack(padx=24, pady=(0, 12))

    photo = ImageTk.PhotoImage(_glyph_image(bitmap))
    holder = tk.Label(dlg, image=photo, bg=BG, bd=1, relief="solid")
    holder.image = photo
    holder.pack(padx=24, pady=(0, 14))

    answer = {"ch": None}
    entry = tk.Entry(dlg, width=4, font=(MONO, 22, "bold"), justify="center",
                     bg="#242830", fg=ACCENT, insertbackground=ACCENT,
                     relief="flat")
    entry.pack(pady=(0, 6))
    entry.focus_set()

    tk.Label(dlg, text="one character, then Enter.  Esc to skip it.", bg=BG,
             fg=DIM, font=(MONO, 9)).pack(padx=24, pady=(0, 16))

    def accept(_event=None):
        text = entry.get().strip()
        if len(text) == 1:
            answer["ch"] = text
            dlg.destroy()

    entry.bind("<Return>", accept)
    dlg.bind("<Escape>", lambda _event: dlg.destroy())
    _wait(parent, dlg)
    return answer["ch"]


def teach_unknowns(parent, region, reader):
    """Ask about every character in the current strip that is not recognised."""
    from ..segment import drop_badge, segment

    glyphs = drop_badge(segment(grab(region)))
    if not glyphs:
        return 0

    reading = "".join(reader.match(g.bitmap) or "?" for g in glyphs)
    learned = 0
    for index, glyph in enumerate(glyphs):
        if reader.match(glyph.bitmap) is not None:
            continue
        ch = ask_one_glyph(parent, glyph.bitmap, reading, index + 1)
        if ch is None:
            continue
        reader.learn(ch, glyph.bitmap)
        learned += 1
        reading = reading[:index] + ch + reading[index + 1:]
    return learned


def correct_reading(parent, region, reader):
    """Show what was read and let it be corrected, then learn the truth.

    This is the only route by which a wrong shape can be displaced. Matching
    will never volunteer that it is wrong, so the person watching has to be able
    to say so.

    Returns (learned, displaced).
    """
    from PIL import Image, ImageTk
    from ..segment import drop_badge, segment

    glyphs = drop_badge(segment(grab(region)))
    if not glyphs:
        return 0, 0
    reading = "".join(reader.match(g.bitmap) or "?" for g in glyphs)
    save_strip(glyphs, paths.LAST_SEGMENTED, scale=6)

    dlg = _dialog(parent, "Correct the reading")
    tk.Label(dlg, text="What does it ACTUALLY say?", bg=BG, fg=FG,
             font=(MONO, 13, "bold")).pack(padx=24, pady=(18, 4))
    tk.Label(dlg, text="%d characters found, so type exactly that many" % len(glyphs),
             bg=BG, fg=DIM, font=(MONO, 9)).pack(padx=24, pady=(0, 12))

    try:
        photo = ImageTk.PhotoImage(Image.open(paths.LAST_SEGMENTED))
        holder = tk.Label(dlg, image=photo, bg=BG, bd=1, relief="solid")
        holder.image = photo
        holder.pack(padx=24, pady=(0, 6))
    except (OSError, tk.TclError):
        pass

    tk.Label(dlg, text="it read this:", bg=BG, fg=DIM,
             font=(MONO, 9)).pack(padx=24, pady=(8, 0))
    entry = tk.Entry(dlg, width=24, font=(MONO, 16, "bold"), justify="center",
                     bg=PANEL, fg=ACCENT, insertbackground=ACCENT, relief="flat")
    entry.insert(0, reading)
    entry.pack(pady=(2, 4))
    entry.focus_set()
    entry.selection_range(0, tk.END)

    note = tk.Label(dlg, text="", bg=BG, fg=WARN, font=(MONO, 9))
    note.pack(padx=24, pady=(0, 8))

    result = {"text": None}

    def accept(_event=None):
        text = entry.get().strip()
        if len(text) != len(glyphs):
            note.config(text="that is %d characters, %d were found"
                             % (len(text), len(glyphs)))
            return
        result["text"] = text
        dlg.destroy()

    tk.Button(dlg, text="LEARN THIS", command=accept, bg=ACCENT, fg=BG,
              activebackground=ACCENT, activeforeground=BG, relief="flat", bd=0,
              font=(MONO, 10, "bold"), padx=14, pady=7,
              cursor="hand2").pack(pady=(0, 6))
    tk.Label(dlg, text="Enter to save, Esc to cancel", bg=BG, fg=DIM,
             font=(MONO, 8)).pack(pady=(0, 16))

    entry.bind("<Return>", accept)
    dlg.bind("<Escape>", lambda _event: dlg.destroy())
    _wait(parent, dlg)

    if not result["text"]:
        return 0, 0

    learned = displaced = 0
    for glyph, ch in zip(glyphs, result["text"]):
        if ch == "?":
            continue
        # A correction outranks both the models and the templates. Without that,
        # correcting a glyph a model is confident about would change nothing
        # visible and the button would look broken.
        added, gone = reader.correct(ch, glyph.bitmap)
        learned += 1 if added else 0
        displaced += gone
    return learned, displaced


def teach_from_console(region, reader):
    """First-run teaching, before there is a window to put a dialog on."""
    from ..segment import drop_badge, segment

    glyphs = drop_badge(segment(grab(region)))
    if not glyphs:
        print("  Nothing legible in that region. Re-run with --region.")
        return 0

    save_strip(glyphs, paths.LAST_SEGMENTED)
    shown = "".join(reader.match(g.bitmap) or "?" for g in glyphs)
    print("\n  Found %d characters." % len(glyphs))
    print("  Currently reads: %s" % shown)
    print("  Picture of what it found: %s" % paths.LAST_SEGMENTED.name)
    print("\n  Type the NUMBERS ONLY, leaving the EXP. badge out, exactly as")
    print("  shown including the comma, brackets, dot and percent sign:")
    print("\n      10,497[76.53%]")
    print("\n  Blank to skip.\n")
    answer = input("  reads: ").strip()
    if not answer:
        return 0

    # Be forgiving about the badge being typed anyway, since the instruction to
    # leave it out is easy to miss and the fix is obvious.
    for prefix in ("EXP.", "EXP", "exp.", "exp"):
        if len(answer) != len(glyphs) and answer.startswith(prefix):
            answer = answer[len(prefix):]
            break

    if len(answer) != len(glyphs):
        print("\n  That is %d characters but %d were found."
              % (len(answer), len(glyphs)))
        print("  Open %s to see what it picked out." % paths.LAST_SEGMENTED.name)
        print("  If a character is cut off at either end, re-run with --region")
        print("  and draw the box a little wider. Nothing has been changed.")
        return 0

    added = 0
    for glyph, ch in zip(glyphs, answer):
        was_added, _ = reader.learn(ch, glyph.bitmap)
        if was_added:
            added += 1
    print("\n  Learned %d distinct characters (%d new samples)."
          % (len(set(answer)), added))
    print("  Known so far: %s" % reader.known)
    return added
