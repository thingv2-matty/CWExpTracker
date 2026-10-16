"""
Pull the damage number sprites out of your own MapleStory Classic World install.

The tracker can draw its experience-per-hour figure in the game's own damage
font. Those sprites belong to Nexon, so they are not shipped with this project;
this takes them out of the copy already on your machine and puts them in
assets/, which is never committed.

    python tools/extract_sprites.py
    python tools/extract_sprites.py --game "D:\\Games\\maplestorycw"
    python tools/extract_sprites.py --list

Run it once. The sprites do not change between patches.

Where they live, for anyone curious. Effect.wz holds BasicEff.img, which has a
node per damage colour: NoRed for ordinary hits, NoCri for criticals, NoBlue for
damage taken. Each holds ten digits. The catch is that those are 1x1 stubs
carrying an _outlink to a parallel _Canvas archive, where the real pixels are,
so a naive extraction hands back ten single-pixel images.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import wz                                                        # noqa: E402

from exptracker import paths                                     # noqa: E402

# The usual install, and the likely alternatives.
CANDIDATES = [
    Path(r"C:\Nexon\Library\maplestorycw\appdata"),
    Path(r"C:\Nexon\maplestorycw\appdata"),
    Path(r"C:\Program Files (x86)\Nexon\maplestorycw\appdata"),
    Path(r"D:\Nexon\Library\maplestorycw\appdata"),
]

# Every digit set, and its larger partner where one exists. The game draws the
# leading digit of a number from the larger sheet and the rest from the smaller,
# which is most of why damage numbers look the way they do.
SETS = {
    "NoRed": ("NoRed0", "NoRed1"),
    "NoCri": ("NoCri0", "NoCri1"),
    "NoCri2": ("NoCri2", "NoCri3"),
    "NoBlue": ("NoBlue0", "NoBlue1"),
    "NoViolet": ("NoViolet0", None),
    "NoGreen": ("NoGreen0", None),
    "NoKite": ("NoKite0", None),
}


def find_game(explicit=None):
    if explicit:
        root = Path(explicit)
        for suffix in ("", "appdata"):
            candidate = root / suffix if suffix else root
            if (candidate / "Data" / "Effect").is_dir():
                return candidate
        raise SystemExit("No Data/Effect under %s" % root)
    for candidate in CANDIDATES:
        if (candidate / "Data" / "Effect").is_dir():
            return candidate
    raise SystemExit(
        "Could not find MapleStory Classic World.\n"
        "Pass the install folder with --game, for example:\n"
        '    python tools/extract_sprites.py --game "C:\\Nexon\\Library\\maplestorycw"')


def open_basiceff(game):
    """The stub tree and the canvas tree, which have to be read together."""
    effect = game / "Data" / "Effect"
    stubs = _read(effect / "Effect_000.wz")
    canvases = _read(effect / "_Canvas" / "_Canvas_000.wz")
    return stubs, canvases


def _read(path):
    if not path.exists():
        raise SystemExit("missing %s" % path)
    archive = wz.Archive(str(path))
    entry = next((e for e in archive.walk() if e.name == "BasicEff.img"), None)
    if entry is None:
        raise SystemExit("no BasicEff.img in %s" % path.name)
    return wz.read_img(archive.data, entry.offset, entry.size, "BasicEff.img")


def extract(stubs, canvases, out):
    written = {}
    for label, (small, large) in SETS.items():
        groups = [g for g in (small, large) if g and canvases.get(g)]
        if not groups:
            continue
        entry = {"small": small, "large": large if large in groups else None,
                 "digits": {}}
        for group in groups:
            folder = out / group
            folder.mkdir(parents=True, exist_ok=True)
            sizes = {}
            for name, node in canvases[group].children.items():
                if not node.canvas:
                    continue
                image = wz.to_image(node.canvas)
                image.save(folder / ("%s.png" % name))
                sizes[name] = {"w": image.width, "h": image.height,
                               "origin": _origin(stubs, group, name)}
            entry["digits"][group] = sizes
        written[label] = entry
        digits = len(entry["digits"].get(small, {}))
        print("  %-9s %2d sprites%s" % (label, digits,
              ("  + large set %s" % large) if entry["large"] else ""))
    return written


def _origin(stubs, group, name):
    node = stubs.get(group)
    if node is None:
        return None
    child = node.children.get(name)
    if child is None:
        return None
    origin = child.children.get("origin")
    return list(origin.value) if origin is not None else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--game", help="MapleStory Classic World install folder")
    parser.add_argument("--list", action="store_true",
                        help="show what is in BasicEff.img and exit")
    args = parser.parse_args(argv)

    game = find_game(args.game)
    print("game    : %s" % game)
    stubs, canvases = open_basiceff(game)

    if args.list:
        print("\nnodes in BasicEff.img:")
        for name, node in canvases.children.items():
            kids = len(node.children)
            print("   %-22s %d child(ren)" % (name, kids))
        return 0

    out = paths.ASSETS / "numbers"
    print("out     : %s\n" % out)
    written = extract(stubs, canvases, out)
    if not written:
        raise SystemExit("nothing extracted; is this the right install?")

    (out / "sets.json").write_text(json.dumps(written, indent=2), encoding="utf-8")
    print("\nWrote %d set(s). Pick one from the tracker's ··· menu, under Numbers."
          % len(written))
    print("Nothing here is committed: assets/ is ignored by git.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
