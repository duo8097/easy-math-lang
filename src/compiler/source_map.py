"""Source spans and generated-Typst source map.

Conventions (same as LSP/editor internals):

- ``SourcePosition.line`` is 0-based.
- ``SourcePosition.column`` is 0-based in Unicode code points
  (``len(str)`` units, as used by ``lsp.analysis`` ``Diag``/``Definition``).
- The LSP wire protocol and Qt ``QTextCursor`` use UTF-16 code units;
  convert at the boundary with :mod:`editor.positions`
  (``to_lsp_offset`` / ``to_code_point_offset``) or the helpers here.
- Display to users as 1-based (``line+1``, ``col+1``), as in
  ``positions.format_diagnostic`` and the editor status bar.

The compiler never calls Qt. It only produces :class:`TypstSourceMap`
(sidecar JSON); the preview/editor layers resolve through it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SourcePosition:
    """0-based line, 0-based code-point column."""

    line: int
    column: int

    def to_display(self) -> tuple[int, int]:
        """1-based (line, column) for status bars / diagnostics."""
        return (int(self.line) + 1, int(self.column) + 1)

    def to_lsp_column(self, line_text: str) -> int:
        """Code-point column -> LSP/UTF-16 column for *line_text*."""
        try:
            from editor.positions import to_lsp_offset
        except Exception:
            try:
                from ..editor.positions import to_lsp_offset  # type: ignore
            except Exception:
                # Fallback without Qt/LSP deps: BMP-only fast path.
                s = line_text or ''
                off = max(0, int(self.column))
                return len(s[:off].encode('utf-16-le')) // 2
        return int(to_lsp_offset(line_text or '', int(self.column)))

    @staticmethod
    def from_lsp(line: int, utf16_col: int, line_text: str = '') -> 'SourcePosition':
        """Build from LSP/UTF-16 coordinates (Qt-native)."""
        try:
            from editor.positions import to_code_point_offset
        except Exception:
            try:
                from ..editor.positions import to_code_point_offset  # type: ignore
            except Exception:
                # Fallback: walk surrogate pairs.
                target = max(0, int(utf16_col))
                idx = units = 0
                s = line_text or ''
                while idx < len(s) and units < target:
                    units += 2 if ord(s[idx]) > 0xFFFF else 1
                    idx += 1
                return SourcePosition(int(line), idx)
        return SourcePosition(int(line), int(to_code_point_offset(line_text or '', utf16_col)))

    @staticmethod
    def from_one_based(line_1: int, col_1: int) -> 'SourcePosition':
        return SourcePosition(int(line_1) - 1, int(col_1) - 1)


@dataclass(frozen=True)
class SourceSpan:
    """Range in one source file: ``[start, end]`` inclusive (forgiving for EOL cursors)."""

    source_file: str
    start: SourcePosition
    end: SourcePosition

    def contains(self, line: int, column: int) -> bool:
        s = (int(self.start.line), int(self.start.column))
        e = (int(self.end.line), int(self.end.column))
        p = (int(line), int(column))
        return s <= p <= e

    def to_dict(self) -> dict:
        return {
            'source_file': self.source_file,
            'start': {'line': int(self.start.line), 'column': int(self.start.column)},
            'end': {'line': int(self.end.line), 'column': int(self.end.column)},
        }

    @staticmethod
    def from_dict(d: dict) -> 'SourceSpan':
        s = d.get('start', {}) or {}
        e = d.get('end', {}) or {}
        return SourceSpan(
            source_file=str(d.get('source_file', '')),
            start=SourcePosition(int(s.get('line', 0)), int(s.get('column', 0))),
            end=SourcePosition(int(e.get('line', 0)), int(e.get('column', 0))),
        )


@dataclass
class MapEntry:
    """One generated-Typst range -> one .eml span."""

    typ_start: SourcePosition
    typ_end: SourcePosition
    src: SourceSpan

    def contains_typ(self, line: int, column: int) -> bool:
        s = (int(self.typ_start.line), int(self.typ_start.column))
        e = (int(self.typ_end.line), int(self.typ_end.column))
        p = (int(line), int(column))
        return s <= p <= e

    def to_dict(self) -> dict:
        return {
            'typ_start': {'line': int(self.typ_start.line), 'column': int(self.typ_start.column)},
            'typ_end': {'line': int(self.typ_end.line), 'column': int(self.typ_end.column)},
            'src': self.src.to_dict(),
        }

    @staticmethod
    def from_dict(d: dict) -> 'MapEntry':
        ts = d.get('typ_start', {}) or {}
        te = d.get('typ_end', {}) or {}
        return MapEntry(
            typ_start=SourcePosition(int(ts.get('line', 0)), int(ts.get('column', 0))),
            typ_end=SourcePosition(int(te.get('line', 0)), int(te.get('column', 0))),
            src=SourceSpan.from_dict(d.get('src', {}) or {}),
        )


class TypstSourceMap:
    """Maps generated ``.typ`` positions back to original ``.eml`` spans.

    - Multiple generated lines may map to one ``.eml`` span via a single
      entry whose ``typ_start.line != typ_end.line``.
    - One ``.eml`` construct may generate multiple Typst regions via
      multiple entries sharing the same ``src`` span.
    - Unmapped generated lines (headers, ``#v()`` separators) simply
      have no entry; :meth:`resolve` returns ``None`` for them.
    """

    VERSION = 1

    def __init__(self, source_file: str = '', typ_file: str = ''):
        self.source_file = source_file
        self.typ_file = typ_file
        self.entries: list[MapEntry] = []

    def add(self, typ_start: SourcePosition, typ_end: SourcePosition,
            src: SourceSpan) -> None:
        # Skip empty ranges (defensive; keeps resolve semantics clean).
        s = (int(typ_start.line), int(typ_start.column))
        e = (int(typ_end.line), int(typ_end.column))
        if e <= s:
            return
        self.entries.append(MapEntry(typ_start, typ_end, src))

    def resolve(self, typ_line: int, typ_column: int) -> SourceSpan | None:
        """Generated-Typ position (0-based) -> ``.eml`` span or ``None``."""
        try:
            line = int(typ_line)
            col = int(typ_column)
        except (TypeError, ValueError):
            return None
        if line < 0 or col < 0:
            return None
        for entry in self.entries:
            if entry.contains_typ(line, col):
                return entry.src
        return None

    def to_dict(self) -> dict:
        return {
            'version': self.VERSION,
            'source_file': self.source_file,
            'typ_file': self.typ_file,
            'entries': [e.to_dict() for e in self.entries],
        }

    @staticmethod
    def from_dict(d: dict) -> 'TypstSourceMap':
        m = TypstSourceMap(
            source_file=str(d.get('source_file', '')),
            typ_file=str(d.get('typ_file', '')),
        )
        for raw in d.get('entries', []) or []:
            try:
                m.entries.append(MapEntry.from_dict(raw))
            except Exception:
                continue
        return m

    def save(self, path: str) -> None:
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(self.to_dict(), fh, ensure_ascii=False, indent=2)

    @staticmethod
    def load(path: str) -> 'TypstSourceMap':
        with open(path, 'r', encoding='utf-8') as fh:
            return TypstSourceMap.from_dict(json.load(fh))


def default_map_path(typst_file: str) -> str:
    """Sidecar path for a ``.typ`` file: ``<base>.smap.json``."""
    base, _ = os.path.splitext(typst_file)
    return base + '.smap.json'
