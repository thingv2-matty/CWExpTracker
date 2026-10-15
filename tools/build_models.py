"""
Build a character model per digit from the labelled set, and test it honestly.

The model is Matt's idea. Comparing a candidate against individual stored
samples asks which single example it is closest to, which the blurred edges can
swing. Stacking every example of a digit asks a better question:

    CORE  pixels lit in essentially every example. A real 8 must have these.
    VOID  pixels lit in essentially none.          A real 8 must not have these.

The void half is what nearest-neighbour matching never used, and it is what
separates a 1 from a 4: both have the upright stroke, but a 4 puts ink to the
left of it where a 1 must be empty.

This held up in sample and fell over out of it when each model came from three
to nine examples, because "lit in every example" is a sound rule estimated from
thirty and a brittle one estimated from four. The fix is more examples, not a
softer rule, so the thresholds here stay tight and the test reported is the
honest one: every glyph is scored against a model built WITHOUT it.

    python tools/build_models.py           test, and write models.json if it holds
    python tools/build_models.py --report  test only
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json                                                      # noqa: E402

import numpy as np                                               # noqa: E402
from PIL import Image                                            # noqa: E402

from exptracker import paths                                     # noqa: E402
from exptracker.config import Config                             # noqa: E402
from exptracker.reader import Reader                             # noqa: E402


PAD = 3
# Tight on purpose. 1.0/0.0 is "every example agrees"; 0.9/0.1 allows one
# example in ten to disagree. Nothing looser is on the table.
SETTINGS = [(1.0, 0.0), (0.9, 0.1)]
DASHES = "-" * 40


def collect():
    """Every labelled glyph, filed under the character Matt said it was."""
    if not paths.LABELS.exists():
        print("No labels yet. Run tools/harvest.py, then tools/label.py.")
        return None
    labels = json.loads(paths.LABELS.read_text(encoding="utf-8"))
    reader = Reader.load(Config.load(), paths.MODELS)
    by, skipped, heights = {}, 0, {}
    for name, text in sorted(labels.items()):
        png = paths.CAPTURES / (name + ".png")
        if not png.exists():
            continue
        rgb = np.asarray(Image.open(png).convert("RGB"))
        glyphs = reader.read(rgb)[1]
        if len(glyphs) != len(text):
            skipped += 1
            continue
        for (_, _, bm), ch in zip(glyphs, text):
            by.setdefault(ch, []).append(bm)
            heights[bm.shape[0]] = heights.get(bm.shape[0], 0) + 1
    if skipped:
        print(str(skipped) + " capture(s) skipped: label length did not match "
              "the glyph count")
    print("glyph band heights seen: " + str(dict(sorted(heights.items()))))
    if len(heights) > 1:
        print("  more than one height, so some comparison involves resampling")
    return by


def place(bm, h, w, dy, dx):
    c = np.zeros((h, w), dtype=bool)
    c[dy:dy + bm.shape[0], dx:dx + bm.shape[1]] = bm
    return c


def register(samples, h, w, ref=None):
    """One canvas, every sample slid to agree with the reference as closely as
    it can.

    The reference is fixed per character rather than taken as whichever sample
    happens to be first in the subset. That keeps the registration of a sample
    independent of which other samples are in the model, which is what lets the
    stack be computed once and reused for every held-out model.
    """
    if ref is None:
        ref = place(samples[0], h, w, PAD, PAD)
    stack = []
    for s in samples:
        best, bestd = None, 1 << 30
        for dy in range(h - s.shape[0] + 1):
            for dx in range(w - s.shape[1] + 1):
                cand = place(s, h, w, dy, dx)
                d = int(np.logical_xor(cand, ref).sum())
                if d < bestd:
                    best, bestd = cand, d
        stack.append(best)
    return np.stack(stack)


def masks(p, core_p, void_p, h, w, n):
    return {"core": p >= core_p, "void": p <= void_p, "h": h, "w": w, "n": n}


def model(samples, core_p, void_p, h, w):
    return masks(register(samples, h, w).mean(axis=0),
                 core_p, void_p, h, w, len(samples))


def test(bm, m):
    """How well a candidate satisfies a model, at its best alignment."""
    h, w = m["h"], m["w"]
    if bm.shape[0] > h or bm.shape[1] > w:
        return 0.0
    best = 0.0
    for dy in range(h - bm.shape[0] + 1):
        for dx in range(w - bm.shape[1] + 1):
            c = place(bm, h, w, dy, dx)
            core_hit = c[m["core"]].mean() if m["core"].any() else 1.0
            void_ok = (~c[m["void"]]).mean() if m["void"].any() else 1.0
            best = max(best, min(core_hit, void_ok))
    return best


def canvas_for(by):
    h = max(s.shape[0] for v in by.values() for s in v) + PAD * 2
    w = max(s.shape[1] for v in by.values() for s in v) + PAD * 2
    return h, w


def rivals(by):
    """Who each character actually competes with.

    A comma is never mistaken for a 4: one is three pixels across and the other
    eleven tall, and the existing matcher separates them with no argument. They
    should not be in the same contest, and putting them there is actively
    misleading, because a model built from a three-pixel comma has barely any
    core and barely any void, so almost any glyph satisfies it. The contest
    that matters is digit against digit.

    Grouped by height, which is the rule the tracker matches with, so the gap
    reported here is the gap that ships. Width is not used: an eleven-by-seven
    glyph would be put up against only the 4 and the 7, being the two seen that
    narrow, and a digit rendering a pixel thinner than ever before would then
    face the wrong shortlist.
    """
    groups = {}
    for ch, samples in by.items():
        for height in {s.shape[0] for s in samples}:
            if ch not in groups.setdefault(height, []):
                groups[height].append(ch)
    return groups


def stacks_for(by, h, w):
    """Register each character's samples once; every model is a mean over a
    subset of its stack, so holding one out costs a subtraction."""
    out = {}
    for ch, samples in by.items():
        out[ch] = register(samples, h, w)
    return out


def evaluate(by, core_p, void_p, stacks, h, w):
    usable = {c: v for c, v in by.items() if len(v) >= 4}
    full = {}
    for ch in usable:
        st = stacks[ch]
        full[ch] = masks(st.mean(axis=0), core_p, void_p, h, w, len(st))
    groups = rivals(usable)
    peer = {ch: [o for o in chars if o != ch]
            for chars in groups.values() for ch in chars}

    own_worst, wrong_best, wrong_pair = 1.0, 0.0, None
    checked, losses, failures = 0, 0, []
    for ch, samples in sorted(usable.items()):
        if not peer.get(ch):
            continue                      # nothing its size to be confused with
        st = stacks[ch]
        total = st.sum(axis=0)
        n = len(st)
        for i in range(n):
            held = samples[i]
            p = (total - st[i]) / float(n - 1)
            s_own = test(held, masks(p, core_p, void_p, h, w, n - 1))
            own_worst = min(own_worst, s_own)
            checked += 1

            best_other, best_name = 0.0, None
            for other in peer[ch]:
                sc = test(held, full[other])
                if sc > best_other:
                    best_other, best_name = sc, other
            if best_other > wrong_best:
                wrong_best, wrong_pair = best_other, (ch, best_name)
            if best_other >= s_own:
                losses += 1
                failures.append((ch, i, s_own, best_name, best_other))
    return {"checked": checked, "own_worst": own_worst, "wrong_best": wrong_best,
            "wrong_pair": wrong_pair, "losses": losses, "failures": failures,
            "models": full, "h": h, "w": w, "groups": groups}


def main():
    by = collect()
    if not by:
        return 1
    print("\nlabelled glyphs: " + str({c: len(v) for c, v in sorted(by.items())}))
    thin = [c for c, v in sorted(by.items()) if len(v) < 20]
    if thin:
        print("under twenty examples: " + "".join(thin)
              + "   (these are the weak models)")

    h, w = canvas_for(by)
    print("registering %d glyphs on a %dx%d canvas..."
          % (sum(len(v) for v in by.values()), h, w))
    stacks = stacks_for(by, h, w)

    best = None
    for core_p, void_p in SETTINGS:
        r = evaluate(by, core_p, void_p, stacks, h, w)
        gap = r["own_worst"] - r["wrong_best"]
        print("\n--- core %.2f / void %.2f %s" % (core_p, void_p, DASHES))
        for height, chars in sorted(r["groups"].items()):
            if len(chars) > 1:
                print("  %d tall, competing: %s" % (height, "".join(sorted(chars))))
        print("  glyphs held out one at a time         : %d" % r["checked"])
        print("  worst a glyph scores on its own model : %.3f" % r["own_worst"])
        if r["wrong_pair"]:
            print("  best a glyph scores on a wrong model  : %.3f   (%s as %s)"
                  % (r["wrong_best"], r["wrong_pair"][0], r["wrong_pair"][1]))
        print("  a wrong model won or tied             : %d of %d"
              % (r["losses"], r["checked"]))
        verdict = ("separable, threshold %.3f"
                   % ((r["own_worst"] + r["wrong_best"]) / 2)) if gap > 0 \
            else "still overlapping"
        print("  GAP: %+.3f   %s" % (gap, verdict))
        for ch, i, s_own, other, s_other in r["failures"][:12]:
            print("      %s #%d: own %.3f, %s scored %.3f"
                  % (ch, i, s_own, other, s_other))
        if len(r["failures"]) > 12:
            print("      and %d more" % (len(r["failures"]) - 12))
        if best is None or gap > best[0]:
            best = (gap, core_p, void_p, r)

    gap, core_p, void_p, r = best
    if "--report" in sys.argv:
        return 0
    if gap <= 0:
        print("\nNot writing models.json: it does not separate on unseen glyphs "
              "yet.\nMore labelled captures is the lever. The thresholds stay "
              "where they are.")
        return 0

    paths.MODELS.parent.mkdir(parents=True, exist_ok=True)
    paths.MODELS.write_text(json.dumps({
        "core_p": core_p,
        "void_p": void_p,
        "h": r["h"],
        "w": r["w"],
        "threshold": (r["own_worst"] + r["wrong_best"]) / 2,
        # the shapes a character actually renders at, so a glyph is only ever
        # compared against characters of its own size
        "chars": {ch: {"core": np.packbits(m["core"]).tolist(),
                       "void": np.packbits(m["void"]).tolist(),
                       "n": m["n"],
                       "shapes": sorted({tuple(s.shape) for s in by[ch]})}
                  for ch, m in r["models"].items()},
    }, indent=2), encoding="utf-8")
    print("\nwrote %s  (core %.2f / void %.2f)" % (paths.MODELS, core_p, void_p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
