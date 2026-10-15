"""
Keep the machine awake without changing any settings. Windows' caffeinate.

macOS has `caffeinate -i`: hold off idle sleep for as long as I am running,
change nothing permanently, and let go the moment I exit. Windows has the same
thing in SetThreadExecutionState, it just has no command for it.

    ES_SYSTEM_REQUIRED      the machine must not sleep
    ES_DISPLAY_REQUIRED     the screen must not turn off
    ES_CONTINUOUS           keep this until I say otherwise

Asking for the system but NOT the display is exactly `caffeinate -i`: stays
awake, screen still goes dark on its own schedule. That is the default here.

The state belongs to the thread that asked for it and dies with the process, so
nothing is left behind if this is killed, crashes, or the machine restarts. The
power scheme is never touched, which is the point: no settings to remember to
put back.

    pythonw tools/caffeine.py          the window
    python tools/caffeine.py --check   what it would ask for, then exit

Two things it cannot do. Closing the lid is a separate decision made by the
hardware, so the laptop still needs to stay open unless the lid action is
changed in Power Options. And an application can ask for the display itself:
games often do, so if the screen refuses to sleep, something else is asking.
`powercfg /requests` in an elevated prompt names whatever it is.
"""

import ctypes
import sys
import tkinter as tk

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

BG, PANEL, LINE = "#0a0a0c", "#121216", "#24242b"
FG, DIM, ACCENT, WARN = "#e8e8ec", "#5c5c66", "#39ff14", "#ff3864"


def _api():
    try:
        kernel32 = ctypes.windll.kernel32
    except AttributeError:
        return None
    kernel32.SetThreadExecutionState.argtypes = [ctypes.c_uint]
    kernel32.SetThreadExecutionState.restype = ctypes.c_uint
    return kernel32


def hold(system=True, display=False):
    """Ask Windows to stay awake. Returns whether it agreed."""
    kernel32 = _api()
    if kernel32 is None:
        return False
    flags = ES_CONTINUOUS
    if system:
        flags |= ES_SYSTEM_REQUIRED
    if display:
        flags |= ES_DISPLAY_REQUIRED
    return kernel32.SetThreadExecutionState(flags) != 0


def release():
    """Stop asking. Windows goes back to its own schedule immediately."""
    kernel32 = _api()
    if kernel32 is None:
        return False
    return kernel32.SetThreadExecutionState(ES_CONTINUOUS) != 0


class Caffeine:
    def __init__(self, root):
        self.root = root
        self.awake = False
        self.screen = tk.BooleanVar(value=False)

        root.title("caffeine")
        root.configure(bg=BG)
        root.geometry("300x210")
        root.resizable(False, False)

        tk.Label(root, text="CAFFEINE", bg=BG, fg=DIM,
                 font=("Consolas", 9), anchor="w").pack(fill="x", padx=18, pady=(16, 0))

        self.state = tk.Label(root, text="ASLEEP", bg=BG, fg=DIM,
                              font=("Consolas", 26, "bold"), anchor="w")
        self.state.pack(fill="x", padx=18, pady=(2, 0))

        self.note = tk.Label(root, text="the machine sleeps on its own schedule",
                             bg=BG, fg=DIM, font=("Consolas", 8), anchor="w",
                             wraplength=264, justify="left")
        self.note.pack(fill="x", padx=18, pady=(2, 12))

        tk.Frame(root, bg=LINE, height=1).pack(fill="x", padx=18)

        tk.Checkbutton(
            root, text=" keep the screen on too", variable=self.screen,
            command=self.reapply, bg=BG, fg=FG, selectcolor=PANEL,
            activebackground=BG, activeforeground=ACCENT, bd=0,
            highlightthickness=0, font=("Consolas", 9), anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 0))

        self.button = tk.Button(
            root, text="STAY AWAKE", command=self.toggle, bg=ACCENT, fg=BG,
            activebackground=ACCENT, activeforeground=BG, relief="flat", bd=0,
            font=("Consolas", 11, "bold"), pady=8, cursor="hand2")
        self.button.pack(fill="x", padx=18, pady=(12, 16))

        root.protocol("WM_DELETE_WINDOW", self.quit)

    def reapply(self):
        if self.awake:
            self.apply()

    def apply(self):
        ok = hold(system=True, display=self.screen.get())
        if not ok:
            self.awake = False
            self.state.config(text="REFUSED", fg=WARN)
            self.note.config(text="Windows would not take the request", fg=WARN)
            self.button.config(text="STAY AWAKE")
            return
        self.state.config(text="AWAKE", fg=ACCENT)
        self.note.config(
            text="the screen may still turn off" if not self.screen.get()
            else "the screen will stay on as well", fg=DIM)
        self.button.config(text="LET IT SLEEP")

    def toggle(self):
        if self.awake:
            release()
            self.awake = False
            self.state.config(text="ASLEEP", fg=DIM)
            self.note.config(text="the machine sleeps on its own schedule", fg=DIM)
            self.button.config(text="STAY AWAKE")
        else:
            self.awake = True
            self.apply()

    def quit(self):
        release()
        self.root.destroy()


def main():
    if "--check" in sys.argv:
        if _api() is None:
            print("not Windows, SetThreadExecutionState is not available")
            return 1
        print("holding system awake, display free...")
        ok = hold(system=True, display=False)
        print("  Windows accepted: %s" % ok)
        print("  releasing       : %s" % release())
        print("\nnothing was changed; the request is gone with this process.")
        return 0 if ok else 1

    root = tk.Tk()
    app = Caffeine(root)
    app.toggle()                 # on by default, since that is why it was opened
    try:
        root.mainloop()
    finally:
        release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
