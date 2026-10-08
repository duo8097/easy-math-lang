"""Source-map tests: generated .typ -> original .eml navigation.

Conventions: SourcePosition/SourceSpan are 0-based with code-point
columns (see compiler.source_map); typ locations passed to resolve()
are also 0-based.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compiler import pipeline as _pipeline
from compiler.pipeline import compile_ezmath
from compiler.source_map import (
    SourcePosition,
    SourceSpan,
    TypstSourceMap,
    default_map_path,
)


def _stub_typst(monkeypatch):
    stub = type('_TypstStub', (), {'compile': staticmethod(lambda *a, **k: None)})()
    monkeypatch.setattr(_pipeline, 'typst', stub)


def compile_with_map(tmp_path, monkeypatch, capsys, text, filename='case.ezmath'):
    src = tmp_path / filename
    src.write_text(text, encoding='utf-8')
    _stub_typst(monkeypatch)
    ok = compile_ezmath(str(src), str(tmp_path / 'case.pdf'))
    capsys.readouterr()  # drain compiler chatter
    typ_file = str(tmp_path / 'case.typ')
    typ = open(typ_file, encoding='utf-8').read().splitlines()
    map_path = default_map_path(typ_file)
    assert os.path.isfile(map_path), 'sidecar source map must be written'
    smap = TypstSourceMap.load(map_path)
    return ok, typ, smap, map_path


def test_basic_mapping_roundtrip(tmp_path, monkeypatch, capsys):
    ok, typ, smap, _ = compile_with_map(
        tmp_path, monkeypatch, capsys, 'Hello line one\nSecond line here\n')
    assert ok is True
    # Header occupies typ 0..4 (set/set/set-doc/align/blank); body starts at 5.
    # Body line 0 -> typ 5, separator at 6 (unmapped), body line 1 -> typ 7.
    assert 'Hello line one' in typ[5]
    span0 = smap.resolve(5, 0)
    assert span0 is not None
    assert (span0.start.line, span0.end.line) == (0, 0)
    assert 'Hello line one' not in typ[6]  # separator
    assert smap.resolve(6, 0) is None
    span1 = smap.resolve(7, 2)
    assert span1 is not None
    assert (span1.start.line, span1.end.line) == (1, 1)
    # Resolved file is the absolute source path.
    assert span1.source_file.endswith('case.ezmath')


def test_multiline_source_block(tmp_path, monkeypatch, capsys):
    text = (
        '*draw(\n'
        '*point(A = 0, 0)\n'
        '*point(B = 4, 0)\n'
        '*line(A ; B)\n'
        ')\n'
    )
    ok, typ, smap, _ = compile_with_map(tmp_path, monkeypatch, capsys, text)
    assert ok is True
    # One .eml construct (lines 0..4) generates many typ lines (cetz canvas).
    draw_entries = [e for e in smap.entries
                    if e.src.start.line == 0 and e.src.end.line == 4]
    assert len(draw_entries) >= 1
    entry = draw_entries[0]
    assert entry.typ_end.line > entry.typ_start.line  # multi-line typ range
    mid_line = (entry.typ_start.line + entry.typ_end.line) // 2
    span = smap.resolve(mid_line, 0)
    assert span is not None
    assert (span.start.line, span.end.line) == (0, 4)


def test_multiple_generated_regions_from_one_eml(tmp_path, monkeypatch, capsys):
    # *doc_title produces two typ regions (metadata + heading) from one eml line.
    ok, typ, smap, _ = compile_with_map(
        tmp_path, monkeypatch, capsys, '*doc_title(My Title)\nBody here\n')
    assert ok is True
    title_entries = [e for e in smap.entries
                     if e.src.start.line == 0 and e.src.end.line == 0]
    assert len(title_entries) >= 2
    first, second = title_entries[0], title_entries[1]
    assert first.typ_start.line != second.typ_start.line
    assert smap.resolve(first.typ_start.line, 0).start.line == 0
    assert smap.resolve(second.typ_start.line, 0).start.line == 0


def test_unmapped_and_invalid_locations(tmp_path, monkeypatch, capsys):
    ok, typ, smap, _ = compile_with_map(
        tmp_path, monkeypatch, capsys, 'Just text\n')
    assert ok is True
    # Header directive lines and separators are generated-only.
    assert smap.resolve(0, 0) is None
    assert smap.resolve(1, 0) is None
    assert smap.resolve(len(typ) + 100, 0) is None
    assert smap.resolve(-1, 0) is None
    assert smap.resolve(5, -3) is None
    assert smap.resolve('bad', 'worse') is None
    # Missing file never raises (backwards compat: no map -> None).
    from editor.preview import resolve_typ_to_eml
    assert resolve_typ_to_eml('/nonexistent/smap.json', 0, 0) is None


def test_boundary_behavior(tmp_path, monkeypatch, capsys):
    ok, typ, smap, _ = compile_with_map(
        tmp_path, monkeypatch, capsys, 'First\nSecond\nThird\n')
    assert ok is True
    # Body typ lines: 5 (First), 7 (Second), 9 (Third).
    first_line = 5
    last_line = 9
    # First line / first column resolves.
    assert smap.resolve(first_line, 0) is not None
    # Last mapped line resolves (inclusive end).
    assert smap.resolve(last_line, 0) is not None
    # End column (len of typ line) still resolves (EOL cursor friendly).
    assert smap.resolve(first_line, len(typ[first_line])) is not None
    # Exactly at separator boundaries: separator itself unmapped.
    assert smap.resolve(6, 0) is None
    assert smap.resolve(8, 0) is None
    # Past-the-end column on a mapped line is outside the range.
    assert smap.resolve(first_line, len(typ[first_line]) + 50) is None


def test_source_map_json_shape(tmp_path, monkeypatch, capsys):
    _, _, _, map_path = compile_with_map(
        tmp_path, monkeypatch, capsys, 'Hello\n')
    raw = json.load(open(map_path, encoding='utf-8'))
    assert raw['version'] == 1
    assert raw['source_file'].endswith('case.ezmath')
    assert isinstance(raw['entries'], list) and raw['entries']
    e0 = raw['entries'][0]
    assert set(e0) == {'typ_start', 'typ_end', 'src'}
    # Round-trip through the dataclasses.
    smap2 = TypstSourceMap.from_dict(raw)
    assert smap2.resolve(5, 0) is not None


def test_map_disabled_writes_no_file(tmp_path, monkeypatch, capsys):
    src = tmp_path / 'case.ezmath'
    src.write_text('Hello\n', encoding='utf-8')
    _stub_typst(monkeypatch)
    ok = compile_ezmath(str(src), str(tmp_path / 'case.pdf'), source_map=False)
    capsys.readouterr()
    assert ok is True
    assert not os.path.isfile(default_map_path(str(tmp_path / 'case.typ')))


def test_preview_result_carries_smap(tmp_path, monkeypatch):
    _stub_typst(monkeypatch)
    from editor.preview import compile_source_to_format, resolve_typ_to_eml
    res = compile_source_to_format('Hello preview\n', str(tmp_path))
    assert res['smap'] is not None
    assert os.path.isfile(res['smap'])
    span = resolve_typ_to_eml(res['smap'], 5, 0)
    assert span is not None
    assert span.start.line == 0


def test_editor_open_source_location(qapp):
    pytest.importorskip('PySide6')
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win.editor.setPlainText('line one\nline two\nline three\n')
        assert win.open_source_location(None, 1, 2) is True
        line, col = win.editor.cursor_line_col()
        assert line == 1
        # Code-point 2 -> UTF-16 2 on pure-BMP text.
        assert col == 2
        # Span overload with end selection (empty file -> current doc).
        span = SourceSpan('', SourcePosition(2, 0), SourcePosition(2, 4))
        assert win.open_source_span(span) is True
        line, _ = win.editor.cursor_line_col()
        assert line == 2
        # Invalid coords degrade gracefully (clamped, still navigates).
        assert win.open_source_location(None, 'bad', 'worse') is True
    finally:
        win.close()


def test_editor_open_source_location_emoji(qapp):
    pytest.importorskip('PySide6')
    from editor.main_window import MainWindow
    from editor.positions import to_lsp_offset
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win.editor.setPlainText('A\U0001F600BC\nsecond\n')
        # Code-point col 3 (after emoji) -> UTF-16 col 4.
        assert win.open_source_location(None, 0, 3) is True
        _, col = win.editor.cursor_line_col()
        assert col == to_lsp_offset('A\U0001F600BC', 3) == 4
    finally:
        win.close()
