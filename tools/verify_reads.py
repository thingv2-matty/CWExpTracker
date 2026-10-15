"""
The test that actually matters: read a capture the models have never seen.

build_models.py answers a question about glyphs, one at a time. This answers
the question about the product: given the exp bar, does it come out with the
right string. Every capture is read by models built with that capture removed
entirely, so none of its own glyphs helped build the thing judging it.

Reported three ways, because they are three different claims:

    exact        every character right, nothing refused
    safe         nothing WRONG, some characters refused as too close to call
    wrong        a character read confidently and incorrectly

Wrong is the only number that matters for trust. A refusal asks Matt a
question; a confident error quietly corrupts the session.

    python tools/verify_reads.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))            # sibling tools
sys.path.insert(0, str(HERE.parent))     # the exptracker package

import json                                                      # noqa: E402

import numpy as np                                               # noqa: E402
from PIL import Image                                            # noqa: E402

from exptracker import paths                                     # noqa: E402
from exptracker.config import Config                             # noqa: E402
from exptracker.reader import Reader                             # noqa: E402
from build_models import PAD, canvas_for, masks, place, register, test  # noqa: E402
from harvest import anchor                                       # noqa: E402


import json

import numpy as np
from PIL import Image

from build_models import PAD, canvas_for, masks, place, register, test
from harvest import anchor


# A glyph must satisfy its model completely, and no rival may come this close.
ACCEPT = 1.0
MARGIN = 0.005


def collect_with_origin():
    """Every labelled glyph, remembering which capture it came from."""
    labels = json.loads(paths.LABELS.read_text(encoding="utf-8"))
    reader = Reader.load(Config.load(), paths.MODELS)
    by, origin, order = {}, {}, []
    for name, text in sorted(labels.items()):
        png = paths.CAPTURES / (name + ".png")
        if not png.exists():
            continue
        rgb = np.asarray(Image.open(png).convert("RGB"))
        glyphs = reader.read(rgb)[1]
        if len(glyphs) != len(text):
            continue
        order.append((name, text, [g[2] for g in glyphs]))
        for (_, _, bm), ch in zip(glyphs, text):
            by.setdefault(ch, []).append(bm)
            origin.setdefault(ch, []).append(name)
    return by, origin, order


def main():
    if not paths.LABELS.exists():
        print("No labels yet. Run tools/harvest.py, then tools/label.py.")
        return 1

    by, origin, order = collect_with_origin()
    if not order:
        print("Nothing usable to verify.")
        return 1

    h, w = canvas_for(by)
    print("registering %d glyphs from %d captures..."
          % (sum(len(v) for v in by.values()), len(order)))
    stacks = {ch: register(v, h, w) for ch, v in by.items()}
    totals = {ch: st.sum(axis=0) for ch, st in stacks.items()}

    # which rows of each character's stack belong to each capture
    rows = {}
    for ch, names in origin.items():
        for i, name in enumerate(names):
            rows.setdefault((ch, name), []).append(i)

    # a glyph is only ever compared against characters that render at its size
    shape_chars = {}
    for ch, v in by.items():
        for s in v:
            shape_chars.setdefault(s.shape, set()).add(ch)

    tally = {"raw": [0, 0, 0], "anchored": [0, 0, 0]}
    wrong_cases, refused = [], {}
    for name, truth, glyphs in order:
        # every model rebuilt without this capture
        here = {}
        for ch in by:
            drop = rows.get((ch, name), [])
            n = len(stacks[ch]) - len(drop)
            if n < 3:
                continue
            p = totals[ch].copy()
            for i in drop:
                p = p - stacks[ch][i]
            here[ch] = masks(p / float(n), 1.0, 0.0, h, w, n)

        read = []
        for bm in glyphs:
            cands = [c for c in shape_chars.get(bm.shape, by.keys()) if c in here]
            scored = sorted(((test(bm, here[c]), c) for c in cands), reverse=True)
            if not scored:
                read.append("?")
                continue
            top, ch = scored[0]
            runner = scored[1][0] if len(scored) > 1 else 0.0
            if top >= ACCEPT and top - runner >= MARGIN:
                read.append(ch)
            else:
                read.append("?")

        raw = "".join(read)
        for kind, got in (("raw", raw), ("anchored", anchor(raw))):
            bad = [(i, a, b) for i, (a, b) in enumerate(zip(got, truth))
                   if a != "?" and a != b]
            if bad:
                tally[kind][2] += 1
                if kind == "anchored":
                    wrong_cases.append((name, truth, got, bad))
            elif "?" in got:
                tally[kind][1] += 1
                if kind == "anchored":
                    for i, c in enumerate(got):
                        if c == "?":
                            refused[truth[i]] = refused.get(truth[i], 0) + 1
            else:
                tally[kind][0] += 1

    total = len(order)
    print("\ncaptures read by models built without them: %d\n" % total)
    for kind in ("raw", "anchored"):
        exact, safe, wrong = tally[kind]
        label = ("reading every character"
                 if kind == "raw" else "with the fixed ]  %  . positions taken as given")
        print("  %s" % label)
        print("    exact, every character right  : %4d  (%.1f%%)"
              % (exact, 100.0 * exact / total))
        print("    safe, refused but never wrong : %4d  (%.1f%%)"
              % (safe, 100.0 * safe / total))
        print("    WRONG, confidently incorrect  : %4d  (%.1f%%)"
              % (wrong, 100.0 * wrong / total))

    if refused:
        print("\n  characters it declined to call: %s"
              % ", ".join("%s x%d" % (k, v)
                          for k, v in sorted(refused.items(), key=lambda kv: -kv[1])))
    for name, truth, got, bad in wrong_cases[:10]:
        detail = ", ".join("position %d said %s, was %s" % (i, a, b)
                           for i, a, b in bad)
        print("\n  %s truth %s" % (name, truth))
        print("     read  %s   (%s)" % (got, detail))
    if len(wrong_cases) > 10:
        print("\n  and %d more wrong" % (len(wrong_cases) - 10))
    return 0


if __name__ == "__main__":
    sys.exit(main())
