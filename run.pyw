"""
Start the tracker with no console window.

Windows runs a .pyw through pythonw.exe, which is the same interpreter without
a console attached. Double-clicking this opens the tracker and nothing else: no
black window, nothing to alt-tab past, which matters when it gets started
mid-fight.

Use run.py instead when something has gone wrong and the printed output is
worth seeing.
"""

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def show_crash(detail):
    """With no console there is nowhere for a traceback to go, and a window that
    vanishes without a word is the worst way to find out something broke."""
    try:
        from exptracker import paths
        paths.CRASH.write_text(detail, encoding="utf-8")
        where = paths.CRASH.name
    except Exception:
        where = "crash.txt"
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "EXP Tracker",
            "The tracker hit an error and stopped.\n\n"
            + "".join(traceback.format_exc(limit=3))
            + "\nFull details are in %s next to the tracker." % where)
        root.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from exptracker.app import main
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        show_crash(traceback.format_exc())
        sys.exit(1)
