"""Recent-files list persisted with QSettings (no widgets)."""

from .config import default_settings  # noqa: F401  (public re-export)


class RecentFiles:
    """Most-recently-used file list backed by a QSettings store."""

    def __init__(self, settings, max_items=8, key='recentFiles'):
        self._settings = settings
        self._max_items = max_items
        self._key = key

    def add(self, path):
        if not path:
            return
        items = [p for p in self.list() if p != path]
        items.insert(0, path)
        self._settings.setValue(self._key, items[:self._max_items])

    def list(self):
        value = self._settings.value(self._key, [])
        if isinstance(value, str):
            return [value]
        return [str(p) for p in (value or [])]

    def clear(self):
        self._settings.remove(self._key)
