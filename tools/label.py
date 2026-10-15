"""
One pass to label everything harvest.py gathered.

Shows each capture big, with the segmenter's cuts drawn underneath it, and a
box pre-filled with the best guess available. Enter accepts, so a correct guess
costs one keystroke and a wrong one costs a few. Progress is written after
every answer, so quitting halfway loses nothing.

The one rule enforced is that the number of characters typed must equal the
number of glyphs found. Every contaminated measurement in this investigation
came from a mismatch there going unnoticed.

    python tools/label.py
"""

import json
import sys
import tkinter as tk
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))            # sibling tools
sys.path.insert(0, str(HERE.parent))     # the exptracker package

import numpy as np                                               # noqa: E402
from PIL import Image, ImageTk                                   # noqa: E402

from exptracker import paths                                     # noqa: E402
from exptracker.config import Config                             # noqa: E402
from exptracker.reader import Reader                             # noqa: E402
from exptracker.theme import ACCENT, BG, DIM, FG, LINE, MONO, PANEL, WARN  # noqa: E402

from harvest import anchor                                       # noqa: E402

ZOOM = 5


def strip_image(glyphs, height):
    """The segmenter's view: every glyph it found, separated."""
    pad = 2
    width = sum(g[2].shape[1] + pad for g in glyphs) + pad
    canvas = np.zeros((height + pad * 2, width, 3), dtype=np.uint8)
    canvas[:, :] = (18, 18, 22)
    x = pad
    for _, _, bm in glyphs:
        h, w = bm.shape
        y = pad + (height - h) // 2
        canvas[y:y + h, x:x + w][bm] = (57, 255, 20)
        x += w + pad
    return Image.fromarray(canvas)


class Labeller:
    def __init__(self, root, items, labels):
        self.root = root
        self.items = items
        self.labels = labels
        self.i = 0
        self.last_answer = ""

        root.title("label the exp bar")
        root.configure(bg=BG)

        self.count = tk.Label(root, bg=BG, fg=DIM, font=(MONO, 10))
        self.count.pack(pady=(12, 6))

        self.shot = tk.Label(root, bg=PANEL, bd=0)
        self.shot.pack(padx=16)

        self.cuts = tk.Label(root, bg=PANEL, bd=0)
        self.cuts.pack(padx=16, pady=(6, 0))

        self.entry = tk.Entry(root, bg=PANEL, fg=FG, insertbackground=ACCENT,
                              font=(MONO, 22), justify="center",
                              relief="flat", highlightthickness=1,
                              highlightbackground=LINE, highlightcolor=ACCENT)
        self.entry.pack(fill="x", padx=16, pady=(14, 4))
        self.entry.bind("<Return>", self.accept)

        self.note = tk.Label(root, bg=BG, fg=DIM, font=(MONO, 10))
        self.note.pack(pady=(0, 8))

        row = tk.Frame(root, bg=BG)
        row.pack(pady=(0, 14))
        for text, cmd in (("ACCEPT  [enter]", self.accept),
                          ("SKIP", self.skip),
                          ("DONE", self.finish)):
            tk.Button(row, text=text, command=cmd, bg=PANEL, fg=FG,
                      activebackground=LINE, activeforeground=ACCENT,
                      relief="flat", bd=0, padx=14, pady=7,
                      font=(MONO, 10)).pack(side="left", padx=4)

        self.show()

    # ------------------------------------------------------------------ view --

    def show(self):
        if self.i >= len(self.items):
            return self.finish()
        name, rgb, glyphs, guess = self.items[self.i]

        img = Image.fromarray(rgb)
        img = img.resize((img.width * ZOOM, img.height * ZOOM), Image.NEAREST)
        self._shot = ImageTk.PhotoImage(img)
        self.shot.configure(image=self._shot)

        height = max(g[2].shape[0] for g in glyphs)
        cuts = strip_image(glyphs, height)
        cuts = cuts.resize((cuts.width * ZOOM, cuts.height * ZOOM), Image.NEAREST)
        self._cuts = ImageTk.PhotoImage(cuts)
        self.cuts.configure(image=self._cuts)

        # a clean guess is worth one keystroke; otherwise start from the last
        # answer, since consecutive readings share their leading digits
        prefill = guess if "?" not in guess else (self.last_answer or guess)
        self.entry.delete(0, "end")
        self.entry.insert(0, prefill)
        self.entry.focus_set()
        self.entry.icursor("end")

        done = len(self.labels)
        self.count.configure(text=f"{self.i + 1} of {len(self.items)}"
                                 f"     {done} labelled     {len(glyphs)} glyphs")
        self.note.configure(
            text=f"it guessed  {guess}" if "?" in guess else "guess looks clean",
            fg=WARN if "?" in guess else DIM)

    # ----------------------------------------------------------------- input --

    def accept(self, _=None):
        name, _, glyphs, _ = self.items[self.i]
        answer = self.entry.get().strip()
        if len(answer) != len(glyphs):
            self.note.configure(
                text=f"{len(answer)} characters typed, {len(glyphs)} glyphs found",
                fg=WARN)
            return
        self.labels[name] = answer
        self.last_answer = answer
        paths.LABELS.write_text(json.dumps(self.labels, indent=2), encoding="utf-8")
        self.i += 1
        self.show()

    def skip(self, _=None):
        self.i += 1
        self.show()

    def finish(self, _=None):
        paths.LABELS.write_text(json.dumps(self.labels, indent=2), encoding="utf-8")
        print(f"{len(self.labels)} labelled, saved to {paths.LABELS}")
        self.root.destroy()


def main():
    if not paths.CAPTURES.exists():
        print("Nothing harvested yet. Run: python tools/harvest.py")
        return 1
    labels = {}
    if paths.LABELS.exists():
        labels = json.loads(paths.LABELS.read_text(encoding="utf-8"))

    reader = Reader.load(Config.load(), paths.MODELS)
    items = []
    for png in sorted(paths.CAPTURES.glob("*.png")):
        if png.stem in labels:
            continue
        rgb = np.asarray(Image.open(png).convert("RGB"))
        glyphs = reader.read(rgb)[1]
        if not glyphs:
            continue
        side = png.with_suffix(".json")
        guess = ""
        if side.exists():
            guess = json.loads(side.read_text(encoding="utf-8")).get("guess", "")
        guess = anchor(guess) if len(guess) == len(glyphs) else "?" * len(glyphs)
        items.append((png.stem, rgb, glyphs, guess))

    if not items:
        print(f"All {len(labels)} capture(s) already labelled.")
        return 0

    print(f"{len(items)} to label, {len(labels)} already done.")
    root = tk.Tk()
    Labeller(root, items, labels)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
