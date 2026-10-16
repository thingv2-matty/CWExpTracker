# EXP Tracker

An experience-per-hour tracker for MapleStory Classic World.

It watches a region of the screen and works out experience per hour, time to the
next level, how long you have been grinding, and how much experience you have
gained across however many levels. It reads the exp bar the way a person sitting
next to you would, by looking at the pixels.

**It never touches the game.** There is no process to attach to, no memory to
read, no DLL to inject, nothing hooked and nothing patched. The only thing it
does is take screenshots of a rectangle you draw. That is a deliberate
constraint, not an implementation detail: the whole point is that nothing about
it should be able to interest anticheat.

---

## Running it

```
pip install -r requirements.txt
python run.py
```

First run asks you to drag a box around the `EXP. 10,155 [74.04%]` line.
Including the `EXP.` badge is fine, it gets ignored.

On Windows, `powershell -ExecutionPolicy Bypass -File scripts\make-shortcuts.ps1`
creates a **Start EXP Tracker** shortcut that launches through `pythonw.exe`, so
the window opens with no console behind it.

| | |
|---|---|
| `python run.py` | normal, with a console |
| `python run.py --region` | draw the watched zone again |
| `python run.py --teach` | re-learn the characters by hand |
| `python run.py --debug` | dump one capture and every score, then exit |

Controls are **START/PAUSE**, **RESET**, **MAP ZONE**, and **···**. MAP ZONE
redraws the watched area without ending the session, since moving the window
you are watching does not mean you stopped grinding. The **···** menu holds
teaching and correction, which are dead weight while the character models are
reading everything but are the only way back if they ever stop.

---

## How it reads the numbers

This turned out to be the hard part, and most of the interesting code is here.

### Why not read the popups

Summing the `+123 EXP` popups loses any that land between two captures, and
that error never comes back. Reading the running total instead makes every
sample absolute: miss a hundred frames and the next reading is still exactly
right.

### Why the obvious approach fails

The digits in this font cannot be told apart by comparing pixels. Measured
across ten captures:

```
two copies of the SAME digit, worst case    0.295 disagreement
an 8 against a 9, closest case              0.045 disagreement
```

The spread *within* a character is larger than the distance *between*
characters, so no threshold accepts every real match while rejecting every
wrong one. The game draws text at sub-pixel positions, so a digit rasterises
differently depending on where in the string it sits.

A loose threshold does not produce uncertainty, it produces confident wrong
readings. At 0.20 a capture read `16,409[98.98%]` for `16,405[98.35%]`, which
parses cleanly, passes every sanity check, and quietly corrupts the totals.

### What works: stacking

Comparing a candidate against individual stored samples asks which single
example it is closest to, which the blurred edges can swing. Stacking every
example of a character asks a better question:

- **CORE** — pixels lit in essentially every example. A real `8` must have these.
- **VOID** — pixels lit in essentially none. A real `8` must not have these.

The void half is what nearest-neighbour matching never used, and it is what
separates a `1` from a `4`: both have the upright stroke, but a `4` puts ink to
the left of it where a `1` must be empty.

Measured over 120 real captures, each read by models built with that capture
removed entirely:

```
120 of 120 read exactly, nothing refused, nothing wrong
```

and across the 1,440 individual glyphs, held out one at a time:

```
worst score a glyph gives its own model    1.000
best score a glyph gives a wrong model     0.987
wrong model won or tied                    0 of 1440
```

The thresholds in `exptracker/models.py` are measured, not tuned. Loosening
them to allow one example in ten to disagree was tried: the worst own-score
falls to 0.788 and 29 wrong answers get through. The fix for a near miss was
more data, not a softer rule.

### Reading order

1. **A correction made by hand**, keyed on that exact glyph
2. **The stacked character models**
3. **The taught templates**, nearest-neighbour, as the fallback

Corrections come first because the models answer confidently. Without that, the
correction button would appear to do nothing on any glyph a model would commit
to, which is most of them.

Glyphs only compete against characters of the same **height**. A comma is never
mistaken for a `4`, and pretending otherwise is worse than useless, because a
model built from a three-pixel comma has almost no core and almost no void, so
nearly anything satisfies it. Height rather than exact size, because gating on
width would put an 11×7 glyph up against only the `4` and the `7`, those being
the two ever seen that narrow.

---

## How it checks itself

The picture is never asked to be certain. It is asked to produce a reading, and
the reading then has to survive what is already known about how experience
moves. At two captures a second, a rejected frame costs nothing and the next
reading is absolute, so the tests can afford to be strict.

`exptracker/expcurve.py` holds the game's own experience formulas, four rules
covering all 99 levels:

```
1 to 5     (floor(L² / 2) + 15) × L
6 to 50    (floor(L² / 3) + 19) × floor(L² / 3)
51 to 89   previous × 1.0548, truncated
90 to 99   previous × 2.1, truncated
```

They reproduce the datamined table exactly, every row, which
`tests/test_expcurve.py` checks against `data/exp-table.tsv`.

That gives three things:

**The requirement is exact.** Dividing experience by a percentage shown to two
decimals gives an answer that always needs refining. The curve just knows.

**The level comes for free.** Experience plus percentage pins the level down on
its own, because adjacent levels differ by thousands while the rounding leaves
only a sliver of room. `3,810` at `8.07%` is level 25 and nothing else.

**Every reading is checked against the game's own arithmetic.** Value divided by
requirement must round to the percentage on screen. Measured over the labelled
captures, that catches **97.9%** of every possible single-digit corruption of
the value and **100%** of corrupted percentages. The survivors are off-by-one in
the units digit, where a single experience point is too small to move a figure
shown to two decimals.

On top of that, a reading is refused if it moves backwards by anything other
than a death (exactly 5% of the level, or an emptied bar if there was less than
5% there to take), or forwards by more of a level than half a second of killing
things can produce.

### The awkward cases

Both are covered in `tests/test_session.py`:

- **`0` at `0.00%`** fits *every* level, so it is genuinely ambiguous between a
  level up that landed on the boundary and a death that emptied the bar. Where
  you were standing settles it: a death can only empty a bar holding less than
  5%, and a level up is only reachable from near the top.
- **Searching for the readout pattern can skip a bad digit.** `1?,306[60.87%]`
  matched from the `306` and came back as a confident 306 at 60.87%. A
  truncated value is far worse than no value, so anything butting up against
  the number now refuses the whole reading.

---

## Layout

```
run.py / run.pyw        entry points, with and without a console
exptracker/
  capture.py            screen to array, and the region picker
  segment.py            strip to one bitmap per character
  models.py             stacked core/void models
  templates.py          nearest-neighbour matching, the fallback
  reader.py             the three sources of truth, in order
  session.py            readings to rates, and every sanity check
  expcurve.py           the game's experience formulas
  config.py             per-machine state
  debug.py              one capture and every score behind it
  ui/panel.py           the window
  ui/teaching.py        the dialogs for teaching and correcting
  app.py                wiring, the clock, the main loop
tools/                  harvesting, labelling, model building, verification
tests/                  unittest, no dependencies
data/                   the exp curve, the models, and the labelled captures
```

---

## Building models for a different screen

The models are pixel masks tied to the size the font renders at, so they only
work on a screen that renders it the same. On first run the tracker takes one
capture and checks whether the shipped models read it unaided; if they do,
there is nothing to teach and it starts straight up.

If they do not, rebuilding is three steps and about fifteen minutes, most of it
spent playing:

```
python tools/harvest.py        watches and keeps every distinct reading
python tools/label.py          one pass to say what each capture actually said
python tools/build_models.py   stacks them, tests honestly, writes models.json
```

`harvest.py` needs nothing from you while it runs, so run it while grinding.
`label.py` pre-fills each answer with its best guess, so a correct one costs a
single keystroke, and it refuses an answer whose length does not match the
glyph count, because every contaminated measurement in this project came from
that going unnoticed.

`build_models.py` reports a held-out score, which is the only one worth reading;
the in-sample version looks like a breakthrough and means nothing. If the models
do not separate on unseen glyphs it writes nothing and says so.

Two more tools:

- `python tools/verify_reads.py` — reads every labelled capture with models
  built without it, and reports exact, safe-but-refused, and confidently wrong
- `python tools/clean_config.py` — finds shapes filed under two characters at
  once, which used to make teaching impossible to converge

---

## The Maple skin

The tracker can wear the game's own look: a town background behind the readout
and the experience-per-hour figure drawn in the damage font. It ships with
neither, and works fine without both.

The sprites belong to Nexon, so they are not distributed here. They are taken
out of the copy already on your machine:

```
python tools/extract_sprites.py
```

Run it once. It finds your install, pulls every damage number set out of
`Effect.wz`, and writes them to `assets/numbers/`, which git ignores. Pass
`--game` if it cannot find the install, and `--list` to see what is in there
without extracting anything.

Backgrounds are whatever you put in `assets/backgrounds/`. Screenshot a town
you like, drop the file in, done. Anything roughly portrait works; it is
cropped to fill.

Both are then chosen from the **···** menu, under *Background* and *Numbers*,
and remembered between runs. With `assets/` empty neither submenu appears and
you get the plain dark theme.

### How the damage font is laid out

Three things, and only one of them is the stagger:

1. **The leading digit comes off a larger sheet than the rest.** `NoRed0` and
   `NoRed1` are a pair, as are `NoCri0`/`NoCri1`, `NoCri2`/`NoCri3` and
   `NoBlue0`/`NoBlue1`. The large sheet runs 1.16 to 1.23 times the height of
   the small one. This is what produces the pronounced step at the start of a
   number, and it is easy to mistake for dramatic staggering.
2. **Digits share a baseline, not a top.** Measured on a real capture of `365`,
   the bottoms sit within 2px while the tops differ by 9.
3. **Each digit is then nudged a pixel or two, alternating by position**,
   starting with the first digit high. Measured at 2px peak to peak across
   eight digits, and independent of which digit sits where.

There is no thousands separator and the digits overlap slightly, so the
tracker drops the comma when drawing in this font.

### Extracting other things

`tools/wz/` is a small reader for Wizet's `.wz` archives: directory walking,
the version-hash brute force, string decryption and canvas decoding. It exists
because the alternative was downloading an unsigned wz editor from a forum.

Two things to know if you point it somewhere else. Images are often 1×1 stubs
carrying an `_outlink` to a parallel `_Canvas` archive where the real pixels
live, so a naive extraction hands back single-pixel images. And the zlib
streams stop at the last byte of pixel data with no adler trailer, so a
one-shot `zlib.decompress` reports a truncated stream and throws away a
complete image; decompress incrementally instead.

---

## Tests

```
python -m unittest discover -s tests -t .
```

34 tests, no dependencies beyond the ones the tracker already needs. The
capture regression in `tests/test_reading.py` reads all 120 labelled captures
end to end and skips itself if the data is not present.

---

## Also here

`tools/caffeine.py` is Windows' missing `caffeinate -i`. It keeps the machine
awake for as long as it is open and changes no settings, using
`SetThreadExecutionState` with `ES_SYSTEM_REQUIRED` but not
`ES_DISPLAY_REQUIRED`, so the machine stays up while the screen is still free
to turn off. Useful for leaving a shop open overnight without the session
dropping. The request belongs to the process and dies with it.

---

## Licence

MIT.

The experience curve in `data/exp-table.tsv` is datamined game data from
[OSMS Data Explorer](https://github.com/), included for reference. MapleStory
is Nexon's.
