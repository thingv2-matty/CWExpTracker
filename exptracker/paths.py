"""
Where things live.

One place, so that moving the data directory is a one line change rather than a
search. Everything is resolved from the package rather than the working
directory, because the tracker is normally started from a shortcut and the
working directory is whatever Windows felt like.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA = ROOT / "data"
EXP_TABLE = DATA / "exp-table.tsv"
MODELS = DATA / "models.json"
CAPTURES = DATA / "captures"
LABELS = DATA / "labels.json"

# User state: this machine's screen coordinates and anything taught by hand.
# Deliberately not in data/, and deliberately not committed.
CONFIG = ROOT / "config.json"

# Artwork belonging to somebody else: damage number sprites taken out of the
# player's own game install by tools/extract_sprites.py, and whatever
# backgrounds they care to drop in. Never committed, and the tracker works
# without any of it.
ASSETS = ROOT / "assets"
NUMBERS = ASSETS / "numbers"
BACKGROUNDS = ASSETS / "backgrounds"

# Scratch output from the diagnostic paths.
DEBUG_CAPTURE = ROOT / "debug-capture.png"
DEBUG_SEGMENTED = ROOT / "debug-segmented.png"
DEBUG_REPORT = ROOT / "debug-report.txt"
LAST_SEGMENTED = ROOT / "last-segmented.png"
CRASH = ROOT / "crash.txt"
