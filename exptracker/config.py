"""
What the tracker remembers between runs.

This is per-machine state: the screen coordinates of one window position, the
character shapes taught on this screen, and any corrections made by hand. None
of it is meaningful on anyone else's computer, which is why it is not committed.
"""

import json

from . import paths


class Config:
    """The on-disk config, loaded once and saved when something changes."""

    def __init__(self, path=None, data=None):
        self.path = path or paths.CONFIG
        self._data = data if data is not None else {}

    @classmethod
    def load(cls, path=None):
        path = path or paths.CONFIG
        if path.exists():
            try:
                return cls(path, json.loads(path.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                # A corrupt config is not worth stopping for; the worst case is
                # picking the region again.
                pass
        return cls(path)

    def save(self):
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    # Stored fields. Plain properties rather than dict access at every call
    # site, so a typo in a key name is an error rather than a silent None.

    @property
    def region(self):
        return self._data.get("region")

    @region.setter
    def region(self, value):
        self._data["region"] = value

    @property
    def templates(self):
        return self._data.get("templates")

    @templates.setter
    def templates(self, value):
        self._data["templates"] = value

    @property
    def background(self):
        return self._data.get("background")

    @background.setter
    def background(self, value):
        self._data["background"] = value

    @property
    def digits(self):
        return self._data.get("digits")

    @digits.setter
    def digits(self, value):
        self._data["digits"] = value

    @property
    def overrides(self):
        return self._data.get("overrides") or {}

    @overrides.setter
    def overrides(self, value):
        self._data["overrides"] = dict(value)
