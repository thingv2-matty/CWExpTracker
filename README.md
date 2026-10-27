# EXP Tracker

An experience-per-hour tracker for MapleStory Classic World.

It watches the experience line at the bottom of your screen and works out your
experience per hour, how long until your next level, how long you have been
grinding, and how much you have gained across however many levels. When you
stop, it shows you how the session actually went, broken into blocks.

**It never touches the game.** There is no process attached to, no memory read,
no DLL injected, nothing hooked and nothing patched. The only thing it does is
take pictures of a rectangle you draw on your own screen. That is the whole
point of it, not a detail: nothing about it should be capable of interesting
anticheat.

---

## Setting it up

1. Download this folder.
2. Double-click **`Setup.bat`**.
3. Do what it tells you.

That is it. It finds Python, installs the three libraries it needs, and makes
a **Start EXP Tracker** shortcut in the folder.

If it says it cannot find Python, install it from
[python.org](https://www.python.org/downloads/), **tick "Add Python to PATH" on
the first screen of the installer**, and run `Setup.bat` again.

## Using it

Have MapleStory open, then double-click **Start EXP Tracker**.

The first time, it asks you to drag a box around the experience line:

```
EXP. 10,155[74.04%]
```

Draw the box around the whole thing. Including the `EXP.` badge is fine, it
gets ignored. You only do this once; it remembers.

Then play. The numbers fill in by themselves.

### The buttons

| | |
|---|---|
| **START / PAUSE** | stop and start the clock |
| **STOP** | end the session and show how it went |
| **RESET** | throw the session away and begin again |
| **···** | everything else: pick the zone again, teaching, settings |

The clock stops on its own after two minutes with no experience, and starts
again on its own the moment you earn some. It gives you back almost all of the
time it waited, so getting stuck on a party quest stage costs you nothing.

Setup also leaves three other shortcuts in the folder, none of which you
normally need:

| | |
|---|---|
| **Teach EXP Tracker** | tell it what the readout says, for a new resolution |
| **Debug EXP Tracker** | dump one capture and every score, then stop |
| **Caffeine** | stop the machine sleeping, without changing power settings |

### If it reads a number wrong

Open **···** and use **correct the reading**. Type what it actually says and it
will remember that shape for good.

### If you play at a different resolution

The game redraws the readout at a different size per resolution, so it has to
learn each one. It already knows the common ones:

| Resolution | |
|---|---|
| 1024x768, 1280x720, 1366x768 | all identical, taught |
| 1920x1080 windowed | taught |
| 1920x1080 fullscreen | taught |

A few digits are still missing at those sizes. They get picked up on their own
as you play, because the tracker works unknown characters out from the
arithmetic and keeps the shape once it has. If you want to settle it in one
go, double-click **Teach EXP Tracker** and type what the readout says.

Sizes never interfere with each other, so teaching one resolution can never
damage another.

---

## Common problems

**"It says it cannot find Python."**
Install it from [python.org](https://www.python.org/downloads/) and tick
**Add Python to PATH** on the first installer screen. That tickbox is the
thing people miss.

**"Installing the libraries failed."**
Almost always no internet, or a work laptop blocking it. Nothing is broken.

**"The window opens but all the numbers are dashes."**
It cannot read the strip. Open **···** then **pick the zone again** and draw
the box a bit wider. Make sure the game is actually on screen.

**"It read my experience wrong."**
**···** then **correct the reading**. See above.

**"Nothing happens when I double-click Start EXP Tracker."**
Run `Setup.bat` again. The shortcut points at a specific Python on your
machine, so it breaks if Python moves or updates.

---

## For anyone who wants to look under the hood

The reading is the interesting part, and it is harder than it sounds: the
digits in this font genuinely cannot be told apart by comparing pixels, and the
obvious approaches produce confident wrong answers rather than honest
uncertainty.

That, the self-checking, the optional Maple skin, and the repo layout are all
written up in **[docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md)**.

Running it from a terminal, if you would rather:

```
pip install -r requirements.txt
python run.py
```

| | |
|---|---|
| `python run.py` | normal, with a console |
| `python run.py --region` | draw the watched zone again |
| `python run.py --teach` | re-learn the characters by hand |
| `python run.py --debug` | dump one capture and every score, then exit |

Tests: `python -m unittest discover -s tests -t .`

---

## Licence

MIT. See [LICENSE](LICENSE).

MapleStory and its artwork belong to Nexon. Nothing of theirs is included
here. The optional skin reads from your own installed copy of the game, on
your own machine, and nothing it produces is redistributed.
