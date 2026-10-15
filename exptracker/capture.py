"""
Getting pixels off the screen, and letting the user say which pixels.

Nothing here knows what a character is. It hands back arrays.
"""

import time
import tkinter as tk

import mss
import numpy as np

# Drag rectangle colour. The only place in the project that uses the OffGrid
# green, because this window is not part of the tracker's own look.
PICKER_OUTLINE = "#A8C95A"

MIN_REGION_WIDTH = 20
MIN_REGION_HEIGHT = 8


def grab(region=None):
    """Capture the whole virtual desktop, or one region of it, as RGB."""
    with mss.mss() as sct:
        box = region or sct.monitors[0]
        shot = sct.grab(box)
        arr = np.asarray(shot)[:, :, :3]      # BGRA to BGR
        return arr[:, :, ::-1].copy()         # BGR to RGB


def luminance(rgb):
    """Perceived brightness, which is what decides whether a pixel is ink."""
    return 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]


def pick_region(countdown=3, parent=None):
    """Freeze the screen and let the user drag a box around the EXP readout.

    Returns an mss-style region dict, or None if cancelled or too small.

    Takes a parent when the tracker is already running, because a second
    tk.Tk() alongside an existing one is asking for trouble. With a parent it is
    a Toplevel that gets waited on; without one it owns the loop.
    """
    from PIL import Image, ImageTk

    for remaining in range(countdown, 0, -1):
        print(f"  capturing the screen in {remaining}...", end="\r", flush=True)
        time.sleep(1)
    if countdown:
        print("  capturing the screen now.      ")

    with mss.mss() as sct:
        virtual = sct.monitors[0]
        shot = sct.grab(virtual)
        frozen = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    window = tk.Toplevel(parent) if parent is not None else tk.Tk()
    window.title("Drag a box around the EXP readout")
    window.attributes("-topmost", True)
    window.overrideredirect(True)
    window.geometry("%dx%d+%d+%d" % (virtual["width"], virtual["height"],
                                     virtual["left"], virtual["top"]))

    canvas = tk.Canvas(window, cursor="crosshair", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    photo = ImageTk.PhotoImage(frozen)
    canvas.create_image(0, 0, image=photo, anchor="nw")
    canvas.create_text(virtual["width"] // 2, 40,
                       text="Drag a box around the EXP readout.  Escape to cancel.",
                       fill="#ffffff", font=("Segoe UI", 20, "bold"))

    box = {}
    outline = None

    def close():
        window.quit() if parent is None else window.destroy()

    def on_press(event):
        nonlocal outline
        box["x0"], box["y0"] = event.x, event.y
        if outline is not None:
            canvas.delete(outline)
        outline = canvas.create_rectangle(event.x, event.y, event.x, event.y,
                                          outline=PICKER_OUTLINE, width=2)

    def on_drag(event):
        if outline is not None:
            canvas.coords(outline, box["x0"], box["y0"], event.x, event.y)

    def on_release(event):
        box["x1"], box["y1"] = event.x, event.y
        close()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    window.bind("<Escape>", lambda _event: (box.clear(), close()))

    if parent is None:
        window.mainloop()
        window.destroy()
    else:
        window.transient(parent)
        window.grab_set()
        parent.wait_window(window)

    if "x1" not in box:
        return None
    x0, x1 = sorted((box["x0"], box["x1"]))
    y0, y1 = sorted((box["y0"], box["y1"]))
    if x1 - x0 < MIN_REGION_WIDTH or y1 - y0 < MIN_REGION_HEIGHT:
        print("  that selection was too small, try again.")
        return None
    return {"left": virtual["left"] + x0, "top": virtual["top"] + y0,
            "width": x1 - x0, "height": y1 - y0}
