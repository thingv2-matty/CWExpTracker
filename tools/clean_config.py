"""
Find and clear shapes filed under more than one character.

A shape stored under two characters is not a small problem. Matching reports an
ambiguity whenever it sees that shape, correctly, because by the tracker's own
records it genuinely could be either. No amount of teaching clears it, since
teaching only ever added to one side of the tie. Four characters were taught a
dozen times each against exactly this before the cause was found.

Teaching is exclusive now, so new conflicts should not appear. This stays for
configs written before that, and as a way to prove there are none.

    python tools/clean_config.py           report the conflicts
    python tools/clean_config.py --fix     keep the newest, drop the rest

Newest wins, on the reasoning that a later answer is a correction of an earlier
one. Anything removed is listed, and the previous config is kept alongside.
"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exptracker import templates as templates_module             # noqa: E402
from exptracker.config import Config                             # noqa: E402


def find_conflicts(templates):
    """Every pair of same-looking shapes filed under different characters."""
    flat = [(ch, index, bitmap)
            for ch, samples in templates.items()
            for index, bitmap in enumerate(samples)]
    conflicts = []
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            if flat[i][0] == flat[j][0]:
                continue
            if templates_module.same_shape(flat[i][2], flat[j][2]):
                conflicts.append((flat[i], flat[j]))
    return conflicts


def main(argv):
    fix = "--fix" in argv
    config = Config.load()
    templates = templates_module.from_json(config.templates)
    if not templates:
        print("No templates stored; nothing to check.")
        return 0

    print("characters: %s" % "".join(sorted(templates)))
    print("shapes    : %s\n" % {c: len(v) for c, v in sorted(templates.items())})

    conflicts = find_conflicts(templates)
    if not conflicts:
        print("No conflicts: every shape belongs to exactly one character.")
        return 0

    print("%d conflicting pair(s). These are why it keeps asking:\n"
          % len(conflicts))
    pairs = {}
    for (left, _, _), (right, _, _) in conflicts:
        key = tuple(sorted((left, right)))
        pairs[key] = pairs.get(key, 0) + 1
    for (left, right), count in sorted(pairs.items(), key=lambda kv: -kv[1]):
        print("   %r and %r share %d shape(s)" % (left, right, count))

    if not fix:
        print("\nRun with --fix to clear them, keeping the most recently taught.")
        return 0

    # the later entry in a character's list was taught later, so it wins
    drop = set()
    for (left_ch, left_i, _), (right_ch, right_i, _) in conflicts:
        left_rank = len(templates[left_ch]) - left_i
        right_rank = len(templates[right_ch]) - right_i
        drop.add((left_ch, left_i) if left_rank > right_rank else (right_ch, right_i))

    shutil.copy2(config.path, config.path.with_suffix(".json.bak"))
    cleaned = {}
    for ch, samples in templates.items():
        keep = [b for i, b in enumerate(samples) if (ch, i) not in drop]
        if keep:
            cleaned[ch] = keep

    config.templates = templates_module.to_json(cleaned)
    config.save()

    print("\nremoved %d shape(s); previous config saved alongside as .json.bak"
          % len(drop))
    print("now: %s" % {c: len(v) for c, v in sorted(cleaned.items())})
    gone = sorted(set(templates) - set(cleaned))
    if gone:
        print("characters left with nothing: %s  (teach them again)" % gone)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
