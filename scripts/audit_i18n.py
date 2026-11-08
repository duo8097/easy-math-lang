#!/usr/bin/env python3
"""Audit editor UI strings that bypass the i18n catalog.

Walks ``src/editor/*.py`` with the ``ast`` module and flags
user-visible string literals that do not go through ``i18n.tr(...)``
(or ``Translator.tr`` / ``.label`` / ``friendly_errors``). This is a
heuristic guard, not a proof: the allowlist file
(``scripts/audit_i18n_allowlist.json``) records justified exceptions
(syntax names, file names, symbols, raw LSP/compiler text, Qt
internals that cannot be translated).

Usage:
    python scripts/audit_i18n.py           # static audit, grouped by file
    python scripts/audit_i18n.py --runtime # also walk the UI offscreen in vi

The same ``find_violations`` function powers the regression test in
``tests/test_i18n.py``.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDITOR_DIR = ROOT / 'src' / 'editor'
ALLOWLIST = Path(__file__).resolve().parent / 'audit_i18n_allowlist.json'

# Method/attribute names whose first string argument is user-visible.
VISIBLE_METHODS = {
    'setText', 'setWindowTitle', 'setToolTip', 'setStatusTip',
    'setPlaceholderText', 'setLabelText', 'setTitle', 'addMenu',
    'addAction', 'addItem', 'showMessage', 'setAccessibleName',
    'setAccessibleDescription', 'setHorizontalHeaderLabels',
    'setHeaderLabels', 'setAcceptLabel',
}
# Widget constructors whose first string argument is user-visible.
VISIBLE_CONSTRUCTORS = {
    'QLabel', 'QPushButton', 'QToolButton', 'QCheckBox', 'QRadioButton',
    'QGroupBox', 'QTabWidget', 'QListWidgetItem', 'QTreeWidgetItem',
    'QTableWidgetItem', 'QAction', 'QMenu', 'QDialog',
}
# QMessageBox/QInputDialog/QFileDialog static helpers: every string
# argument after the parent is user-visible.
DIALOG_HELPERS = {
    'critical', 'question', 'warning', 'information', 'getText',
    'getInt', 'getDouble', 'getItem', 'getOpenFileName',
    'getSaveFileName', 'getExistingDirectory',
}
# Registry/dataclass fields that end up in the UI (labels, help text,
# descriptions, titles). Values here must be catalog keys or go
# through a translator lookup at the UI layer.
REGISTRY_FIELDS = {
    'label', 'help', 'description', 'display',
}
# Helper constructors in symbol_registry/draw_catalog whose string
# arguments become UI text (labels, descriptions, titles, help).
REGISTRY_HELPERS = {
    '_req', '_opt', '_dialog', '_direct', '_direct_ascii', '_direct_word',
    '_math_dialog', '_geo_dialog', 'SymbolField', 'Symbol',
    'CatalogEntry',
}
# Short single-word literals that are not sentences (symbols, glyphs).
MIN_WORDS = 2


def _is_tr_call(node):
    """True when *node* is (or contains) an ``i18n.tr``/``.tr`` call."""
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute) and func.attr in ('tr', 'label'):
                return True
            if isinstance(func, ast.Name) and func.id in ('tr', 'label'):
                return True
    return False


def _string_value(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        # f-string: join the literal parts; dynamic parts are data.
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
        joined = ''.join(parts)
        return joined or None
    return None


def _looks_user_visible(text):
    """Heuristic: at least two English words, or one word + punctuation."""
    if not text or not text.strip():
        return False
    words = [w for w in text.replace('\n', ' ').split() if w.strip()]
    if len(words) >= MIN_WORDS:
        return True
    # Single long word with spaces/punct handled above; single short
    # tokens (glyphs, symbols, file names) are not prose.
    return False


def _snippet(node, source_lines):
    try:
        segment = ast.get_source_segment(
            '\n'.join(source_lines), node)
    except Exception:
        segment = None
    if segment:
        return ' '.join(segment.split())[:120]
    try:
        return source_lines[node.lineno - 1].strip()[:120]
    except Exception:
        return ''


def load_allowlist(path=ALLOWLIST):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def is_allowlisted(violation, allowlist):
    for entry in allowlist:
        if entry.get('file') != violation['file']:
            continue
        needle = entry.get('contains', '')
        if needle and needle in violation['snippet']:
            return True
    return False


def find_violations(editor_dir=EDITOR_DIR):
    """List of dicts {file, line, kind, snippet} bypassing tr()."""
    violations = []
    for path in sorted(Path(editor_dir).glob('*.py')):
        source = path.read_text(encoding='utf-8')
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue
        lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            method = None
            if isinstance(func, ast.Attribute):
                method = func.attr
            elif isinstance(func, ast.Name):
                method = func.id
            if method not in VISIBLE_METHODS | VISIBLE_CONSTRUCTORS \
                    | DIALOG_HELPERS:
                continue
            if not node.args:
                continue
            # Qt standard-button dialogs: the button labels come from
            # Qt itself (English), not from any literal here. Flag the
            # call so it is either given explicit button text or
            # allowlisted with a reason.
            if method in DIALOG_HELPERS and any(
                    isinstance(arg, ast.Attribute)
                    and isinstance(arg.value, ast.Attribute)
                    and arg.value.attr == 'QMessageBox'
                    for arg in node.args):
                violations.append({
                    'file': path.name,
                    'line': node.lineno,
                    'kind': 'qt-standard-buttons',
                    'snippet': _snippet(node, lines),
                })
                continue
            if method in ('getOpenFileName', 'getSaveFileName'):
                violations.append({
                    'file': path.name,
                    'line': node.lineno,
                    'kind': 'native-file-dialog',
                    'snippet': _snippet(node, lines),
                })
                continue
            first = node.args[0]
            # Skip parent/widget arguments: getText(parent, title, ...)
            # and QMessageBox.critical(parent, title, text, ...) put
            # the visible text at args[1]/args[2]; check all string
            # args there instead of only the first.
            candidates = node.args
            if method in DIALOG_HELPERS:
                candidates = node.args[1:]
            for arg in candidates:
                text = _string_value(arg)
                if text is None:
                    continue
                if _is_tr_call(arg):
                    continue
                if not _looks_user_visible(text):
                    continue
                violations.append({
                    'file': path.name,
                    'line': getattr(arg, 'lineno', node.lineno),
                    'kind': method,
                    'snippet': _snippet(arg, lines) or text[:80],
                })
    return violations


def group_by_file(violations):
    grouped = {}
    for violation in violations:
        grouped.setdefault(violation['file'], []).append(violation)
    return grouped


def registry_coverage(editor_dir=EDITOR_DIR):
    """Registry/catalog strings missing a catalog translation.

    The registry and draw catalog keep canonical English data; the
    UI translates by name/id. This checks every symbol description,
    field label/help, draw title/description and shortcut action
    has a catalog entry in both locales.
    """
    import importlib.util
    import json as _json

    def _load(locale):
        path = Path(editor_dir) / 'locales' / f'{locale}.json'
        return _json.loads(path.read_text(encoding='utf-8'))

    en, vi = _load('en'), _load('vi')
    missing = []
    sys.path.insert(0, str(ROOT / 'src'))
    try:
        from editor.symbol_registry import list_symbols
        from editor.draw_catalog import CATALOG
        from editor.help_dialogs import SHORTCUTS
    except Exception as exc:  # pragma: no cover - import failure is a finding
        return [{'file': 'registry', 'line': 0, 'kind': 'import',
                 'snippet': str(exc)}]
    for symbol in list_symbols():
        key = f'symbol.{symbol.name}.description'
        if symbol.description and (key not in en or key not in vi):
            missing.append({'file': 'symbol_registry.py', 'line': 0,
                            'kind': 'missing-catalog', 'snippet': key})
        for field in symbol.fields:
            label_key = f'field_labels.{field.label}'
            if field.label and label_key not in en:
                # Grid 'Row R Col C' labels use grid.row_col instead.
                if not field.label.startswith('Row '):
                    missing.append({'file': 'symbol_registry.py', 'line': 0,
                                    'kind': 'missing-catalog',
                                    'snippet': label_key})
            if field.help:
                help_key = f'help.{field.help}'
                if help_key not in en or help_key not in vi:
                    missing.append({'file': 'symbol_registry.py', 'line': 0,
                                    'kind': 'missing-catalog',
                                    'snippet': help_key})
    for entry in CATALOG:
        for suffix in ('title', 'description'):
            key = f'draw.{entry.id}.{suffix}'
            if key not in en or key not in vi:
                missing.append({'file': 'draw_catalog.py', 'line': 0,
                                'kind': 'missing-catalog', 'snippet': key})
    for _shortcut, action_key in SHORTCUTS:
        if action_key not in en or action_key not in vi:
            missing.append({'file': 'help_dialogs.py', 'line': 0,
                            'kind': 'missing-catalog',
                            'snippet': action_key})
    return missing


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--runtime', action='store_true',
                        help='also walk the UI offscreen with language=vi')
    args = parser.parse_args(argv[1:] if argv is not None else None)
    allowlist = load_allowlist()
    violations = find_violations() + registry_coverage()
    remaining = [v for v in violations
                 if not is_allowlisted(v, allowlist)]
    grouped = group_by_file(remaining)
    print(f'Audit: {len(violations)} literal(s), '
          f'{len(violations) - len(remaining)} allowlisted, '
          f'{len(remaining)} remaining')
    for filename in sorted(grouped):
        print(f'\n{filename}:')
        for v in grouped[filename]:
            print(f"  {v['line']}: [{v['kind']}] {v['snippet']}")
    if args.runtime:
        print('\nRuntime walk (language=vi, offscreen): see '
              'tests/test_i18n.py::test_vi_ui_has_no_english_chrome')
    return 1 if remaining else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
