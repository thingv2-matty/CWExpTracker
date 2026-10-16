"""
Getting pixels off the screen, and letting the user say which pixels.

Nothing here knows what a character is. It hands back arrays.
"""

import os
import time
import tkinter as tk

import mss
import numpy as np


# MONITORINFO, for working out whether a window covers its whole screen.
# Defined only on Windows; everywhere else the fullscreen check returns early.
try:
    import ctypes as _ctypes
    from ctypes import wintypes as _wintypes

    class _MonitorInfo(_ctypes.Structure):
        _fields_ = [("cbSize", _ctypes.c_ulong),
                    ("rcMonitor", _wintypes.RECT),
                    ("rcWork", _wintypes.RECT),
                    ("dwFlags", _ctypes.c_ulong)]
except (ImportError, ValueError, AttributeError):   # pragma: no cover
    _MonitorInfo = None

# Drag rectangle colour. The only place in the project that uses the OffGrid
# green, because this window is not part of the tracker's own look.
PICKER_OUTLINE = "#A8C95A"

# Set EXPTRACKER_TRACE=1 to have the region picker write each step to
# picker-trace.txt. For working out where it stops when it stops.
TRACE = bool(os.environ.get("EXPTRACKER_TRACE"))


def _trace(message):
    if not TRACE:
        return
    from . import paths
    try:
        with open(paths.ROOT / "picker-trace.txt", "a", encoding="utf-8") as fh:
            fh.write("%.3f  %s\n" % (time.time() % 1000, message))
            fh.flush()
    except OSError:
        pass

MIN_REGION_WIDTH = 20
MIN_REGION_HEIGHT = 8

# How long the picker waits for a selection before closing itself.
PICKER_TIMEOUT = 45


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


IGNORED_WINDOWS = {"Program Manager", "Windows Input Experience",
                   "Windows Shell Experience Host", "Drag a box around the EXP readout"}


def fullscreen_app():
    """The title of a borderless or exclusive fullscreen window, if there is one.

    This matters because the region picker cannot be used over one. The picker
    is a topmost window covering the whole desktop, but a fullscreen game
    outranks it on that game's monitor, so the part of the picker you need is
    hidden behind the game: it cannot be seen, clicked or dismissed, and it is
    holding an input grab. The tracker then looks frozen and cannot be
    recovered without killing it.

    Every visible window is checked rather than just the foreground one,
    because by the time MAP ZONE is clicked the tracker has focus and the game
    does not. Windows only; elsewhere this finds nothing and the picker runs as
    before.
    """
    if _MonitorInfo is None or not hasattr(_ctypes, "windll"):
        return None

    ctypes = _ctypes
    user32 = ctypes.windll.user32
    found = []

    def visit(window, _lparam):
        try:
            if not user32.IsWindowVisible(window):
                return True
            rect = _wintypes.RECT()
            if not user32.GetWindowRect(window, ctypes.byref(rect)):
                return True
            if rect.right - rect.left < 640 or rect.bottom - rect.top < 400:
                return True
            # Overlays and click-through windows cover the screen without
            # getting in the way: Discord's overlay and Windows' own helpers
            # are both fullscreen, layered and harmless.
            ex_style = user32.GetWindowLongW(window, -20)
            if ex_style & (0x20 | 0x80):            # TRANSPARENT, TOOLWINDOW
                return True
            # A borderless fullscreen game has no caption and no resize frame.
            # A merely maximised ordinary window does, and the picker sits over
            # that quite happily.
            style = user32.GetWindowLongW(window, -16)
            if style & (0x00C00000 | 0x00040000):   # CAPTION, THICKFRAME
                return True

            info = _MonitorInfo()
            info.cbSize = ctypes.sizeof(_MonitorInfo)
            monitor = user32.MonitorFromWindow(window, 2)        # NEAREST
            if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                return True
            if not (rect.left <= info.rcMonitor.left
                    and rect.top <= info.rcMonitor.top
                    and rect.right >= info.rcMonitor.right
                    and rect.bottom >= info.rcMonitor.bottom):
                return True

            length = user32.GetWindowTextLengthW(window)
            if not length:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(window, buffer, length + 1)
            title = buffer.value.strip()
            if title and title not in IGNORED_WINDOWS:
                found.append(title)
        except Exception:
            pass
        return True

    try:
        proto = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                   ctypes.c_void_p)
        user32.EnumWindows(proto(visit), 0)
    except Exception:
        return None
    return found[0] if found else None


def pick_region(countdown=3, parent=None):
    """Freeze the screen and let the user drag a box around the EXP readout.

    Returns an mss-style region dict, or None if cancelled or too small.

    Takes a parent when the tracker is already running, because a second
    tk.Tk() alongside an existing one is asking for trouble. With a parent it is
    a Toplevel that gets waited on; without one it owns the loop.

    The parent is hidden for the screenshot and brought straight back, so the
    frozen image does not have the tracker's own window sitting in it. It has
    to come back BEFORE the picker is built: a Toplevel whose parent is
    withdrawn never becomes viewable, so wait_visibility blocks forever and
    nothing can close it either, since an unfocused window never sees the
    Escape key. That hung the tracker with no window and no way back.
    """
    from PIL import Image, ImageTk

    for remaining in range(countdown, 0, -1):
        print(f"  capturing the screen in {remaining}...", end="\r", flush=True)
        time.sleep(1)
    if countdown:
        print("  capturing the screen now.      ")

    _trace("pick_region entered, parent=%r" % (parent is not None,))
    hidden = parent is not None and parent.winfo_viewable()
    _trace("viewable=%s" % hidden)
    if hidden:
        parent.withdraw()
        _trace("withdrawn")
        parent.update()
        _trace("update after withdraw")

    try:
        _trace("opening mss")
        with mss.mss() as sct:
            virtual = sct.monitors[0]
            shot = sct.grab(virtual)
            frozen = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            _trace("screenshot %dx%d" % frozen.size)
    finally:
        if hidden:
            parent.deiconify()
            _trace("deiconified")
            parent.update()
            _trace("update after deiconify")

    _trace("creating window")
    window = tk.Toplevel(parent) if parent is not None else tk.Tk()
    _trace("window created")
    window.title("Drag a box around the EXP readout")
    window.attributes("-topmost", True)
    window.overrideredirect(True)
    window.geometry("%dx%d+%d+%d" % (virtual["width"], virtual["height"],
                                     virtual["left"], virtual["top"]))

    canvas = tk.Canvas(window, cursor="crosshair", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    _trace("building PhotoImage")
    photo = ImageTk.PhotoImage(frozen)
    _trace("PhotoImage done")
    canvas.create_image(0, 0, image=photo, anchor="nw")
    headline = canvas.create_text(
        virtual["width"] // 2, 40,
        text="Drag a box around the EXP readout.  Escape to cancel.",
        fill="#ffffff", font=("Segoe UI", 20, "bold"))

    # A picker hidden behind a fullscreen game cannot be seen, clicked or
    # dismissed, and it holds an input grab while it waits, so the tracker
    # looks frozen and has to be killed. Nothing is worth that: it gives up on
    # its own.
    remaining = [PICKER_TIMEOUT]

    def countdown():
        if "x1" in box or not remaining:
            return
        remaining[0] -= 1
        if remaining[0] <= 0:
            canvas.itemconfigure(headline, text="no selection made, closing")
            window.after(400, close)
            return
        if remaining[0] <= 10:
            canvas.itemconfigure(
                headline,
                text="Drag a box around the EXP readout.  "
                     "Closing in %d..." % remaining[0])
        window.after(1000, countdown)

    window.after(1000, countdown)

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
        # update() rather than wait_visibility(): a fullscreen overrideredirect
        # window never reports itself visible on Windows, so waiting for that
        # blocks forever with the picker on screen and no way to dismiss it.
        _trace("update()")
        window.update()
        _trace("update() done")
        try:
            window.grab_set()
        except tk.TclError:
            # Not fatal. The window covers the whole desktop and sits on top,
            # so every click lands on it with or without a grab.
            pass
        # An overrideredirect window gets no focus from the window manager, and
        # without focus the Escape binding never fires.
        window.focus_force()
        _trace("wait_window")
        try:
            parent.wait_window(window)
        finally:
            # Destroying the window is supposed to drop the grab with it. When
            # that does not happen the application keeps running and keeps
            # pumping messages, but every click goes to a window that no longer
            # exists, so it looks frozen while being perfectly alive. Release
            # it by hand from whatever still exists.
            _trace("releasing grab")
            for widget in (window, parent):
                try:
                    widget.grab_release()
                except tk.TclError:
                    pass
            _trace("grab released")
        _trace("wait_window returned")

    if "x1" not in box:
        return None
    x0, x1 = sorted((box["x0"], box["x1"]))
    y0, y1 = sorted((box["y0"], box["y1"]))
    if x1 - x0 < MIN_REGION_WIDTH or y1 - y0 < MIN_REGION_HEIGHT:
        print("  that selection was too small, try again.")
        return None
    return {"left": virtual["left"] + x0, "top": virtual["top"] + y0,
            "width": x1 - x0, "height": y1 - y0}
