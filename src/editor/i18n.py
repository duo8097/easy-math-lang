"""Small translation catalog for the editor UI.

Choice (see the PR description): this codebase does not use Qt's
``lupdate``/``.ts``/``.qm`` pipeline. The editor's strings were plain
Python literals scattered across widget constructors, dialog code and
the registry, with formatted values and dynamic titles. A tiny JSON
catalog (one file per language, stdlib ``json`` only) is far less
invasive here: it works without a Qt build step, loads without Qt
(so compiler/geometry/LSP tests stay Qt-free), gives plain
English-fallback semantics, and is bundled as plain data files next
to the existing ``assets/`` payload. Adding a language means adding
one JSON file with the same keys — see ``docs/editor.md``.

Only UI chrome belongs in the catalogs. Language syntax/keywords
(``*vec``, ``*draw`` …), file names, code snippets and compiler/LSP
identifiers are never translated. Command descriptions and draw
titles are catalogued by name/id (``symbol.<name>.description``,
``draw.<id>.title``) so the registry/catalog data itself stays
Qt-free English while the UI shows the translated text.

Keys are dotted strings (``menu.file`` …). Values may contain
``{name}`` placeholders filled by :meth:`Translator.tr`. Lookup
falls back to English, then to the key itself so a missing entry is
visible instead of crashing.
"""

from __future__ import annotations

import json
import os

SUPPORTED_LOCALES = ('en', 'vi')
DEFAULT_LOCALE = 'en'
LANGUAGE_SETTING = 'ui/language'

_HERE = os.path.dirname(os.path.abspath(__file__))


def locales_dir():
    """Directory holding ``<locale>.json`` files (bundle-aware)."""
    candidates = [os.path.join(_HERE, 'locales')]
    try:
        from .paths import resource_path
        candidates.append(resource_path('editor', 'locales'))
    except Exception:  # pragma: no cover - defensive
        pass
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return candidates[0]


def normalize_locale(name):
    """Normalize a locale name to ``'en'``/``'vi'``, or None.

    Accepts ``vi``, ``vi_VN``, ``vi-VN.UTF-8``, ``en-US`` … (case
    insensitive) so both ``QLocale.system().name()`` and environment
    variables like ``LANG=vi_VN.UTF-8`` resolve the same way.
    """
    if not name or not isinstance(name, str):
        return None
    base = name.strip().replace('-', '_').split('_')[0].lower()
    if base == 'vi':
        return 'vi'
    if base == 'en':
        return 'en'
    return None


def detect_system_locale(qlocale_name=None):
    """Best-guess locale from the system, ``'en'`` when unknown.

    *qlocale_name* is ``QLocale.system().name()`` when Qt is already
    up; otherwise ``LANG``/``LC_ALL``/``LANGUAGE`` are consulted.
    """
    for candidate in (qlocale_name, os.environ.get('LANGUAGE'),
                      os.environ.get('LC_ALL'), os.environ.get('LANG')):
        locale = normalize_locale(candidate or '')
        if locale:
            return locale
    return DEFAULT_LOCALE


def _load_catalog(locale):
    path = os.path.join(locales_dir(), f'{locale}.json')
    try:
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


class Translator:
    """One locale plus an English fallback catalog."""

    def __init__(self, locale=DEFAULT_LOCALE):
        self.locale = normalize_locale(locale) or DEFAULT_LOCALE
        self._catalog = _load_catalog(self.locale)
        self._english = (self._catalog if self.locale == DEFAULT_LOCALE
                         else _load_catalog(DEFAULT_LOCALE))

    def tr(self, key, **params):
        """Translate *key*, falling back to English, then to *key*."""
        text = self._catalog.get(key)
        if text is None:
            text = self._english.get(key)
        if text is None:
            text = key
        if params:
            try:
                text = text.format(**params)
            except (KeyError, IndexError, ValueError):
                pass
        return text

    def has(self, key):
        return key in self._catalog or key in self._english

    def keys(self):
        return set(self._catalog) | set(self._english)

    def label(self, english_label):
        """Translate a registry field label by its English source text.

        Field labels live on :class:`symbol_registry.SymbolField`
        (Qt-free data); the catalog keys them as
        ``field_labels.<english>`` so the registry itself needs no
        Qt or i18n dependency. Unknown labels pass through unchanged.
        """
        return self.tr(f'field_labels.{english_label}')

    def text(self, english_source, prefix='help'):
        """Translate a free English source string, keyed by itself.

        Used for short help strings that live in Qt-free data
        (field ``help`` texts). Unknown strings pass through.
        """
        if not english_source:
            return english_source
        return self.tr(f'{prefix}.{english_source}')


_current = Translator(DEFAULT_LOCALE)


def current_translator():
    return _current


def set_locale(locale):
    """Install *locale* as the process-wide translator (never raises)."""
    global _current
    _current = Translator(locale)
    return _current


def get_locale():
    return _current.locale


def tr(key, **params):
    """Translate *key* with the current locale (see Translator.tr)."""
    return _current.tr(key, **params)


def resolve_language(saved, qlocale_name=None):
    """Effective locale for a saved setting value.

    ``'en'``/``'vi'`` are used as-is; ``'system'``, missing and any
    other value follow the system locale.
    """
    saved_locale = normalize_locale(saved or '')
    if saved_locale:
        return saved_locale
    return detect_system_locale(qlocale_name)


def load_setting_language(settings):
    """Effective locale from a QSettings-like object (never raises)."""
    try:
        saved = settings.value(LANGUAGE_SETTING, 'system')
    except Exception:
        saved = 'system'
    if isinstance(saved, (list, tuple)):
        saved = saved[0] if saved else 'system'
    try:
        from PySide6 import QtCore
        qlocale_name = QtCore.QLocale.system().name()
    except Exception:  # pragma: no cover - Qt-free contexts
        qlocale_name = None
    locale = resolve_language(saved, qlocale_name)
    set_locale(locale)
    return locale


def save_setting_language(settings, locale, save_system=False):
    """Persist a language choice (``'en'``/``'vi'``/``'system'``)."""
    value = locale if save_system else (normalize_locale(locale)
                                        or DEFAULT_LOCALE)
    try:
        settings.setValue(LANGUAGE_SETTING, value)
        settings.sync()
    except Exception:
        pass
    return value
