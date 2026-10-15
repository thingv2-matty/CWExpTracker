"""
The whole chain against real captures: pixels in, numbers out.

Reads every labelled capture in data/captures with the shipped models and
checks the text comes back exactly as labelled, then feeds the lot to a session
and checks nothing was refused.

This is the test that would catch a change to segmentation, matching, parsing or
the session quietly breaking something the unit tests do not reach. It needs the
capture set; without it the whole case is skipped rather than failing, since a
clone that drops the data should still be able to run its tests.
"""

import json
import unittest

from exptracker import paths
from exptracker.models import CharacterModels
from exptracker.reader import Reader
from exptracker.session import Session, parse

HAVE_DATA = paths.LABELS.exists() and paths.MODELS.exists()


@unittest.skipUnless(HAVE_DATA, "no labelled captures in data/")
class TestReadingRealCaptures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        from PIL import Image

        cls.labels = json.loads(paths.LABELS.read_text(encoding="utf-8"))
        # No templates on purpose: this proves the models carry it alone, which
        # is what a fresh clone gets before anything has been taught.
        cls.reader = Reader(templates={},
                            models=CharacterModels.load(paths.MODELS))
        cls.captures = {}
        for name in cls.labels:
            path = paths.CAPTURES / (name + ".png")
            if path.exists():
                cls.captures[name] = np.asarray(Image.open(path).convert("RGB"))

    def test_there_are_captures_to_read(self):
        self.assertGreater(len(self.captures), 100)

    def test_every_capture_reads_exactly_as_labelled(self):
        wrong = []
        for name, rgb in sorted(self.captures.items()):
            text, _ = self.reader.read(rgb)
            if text != self.labels[name]:
                wrong.append("%s read %r, labelled %r"
                             % (name, text, self.labels[name]))
        self.assertEqual(wrong, [], "\n".join(wrong))

    def test_the_models_alone_refuse_nothing(self):
        unread = [name for name, rgb in self.captures.items()
                  if "?" in self.reader.read(rgb)[0]]
        self.assertEqual(unread, [])

    def test_a_session_accepts_the_whole_run(self):
        session = Session()
        session.banked = 600.0
        refused = []
        for name, rgb in sorted(self.captures.items()):
            reading = parse(self.reader.read(rgb)[0])
            self.assertIsNotNone(reading, "%s did not parse" % name)
            if not session.update(*reading):
                refused.append(name)
        self.assertEqual(refused, [])
        self.assertEqual(session.level, 20)
        self.assertEqual(session.requirement, 20216)
        self.assertEqual(session.recoveries, 0)


if __name__ == "__main__":
    unittest.main()
