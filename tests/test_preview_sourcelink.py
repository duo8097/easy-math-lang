"""Preview source-link tests: eml-src URLs, link embedding, click chain.

Verified platform facts used here (see ``editor.preview_links``):

- Typst emits ``#link("eml-src://typ/L/C")`` as PDF ``/URI`` annotations
  with no visual change (links render like normal text by default).
- Qt 6.11 ``QPdfView`` routes *internal* link clicks through
  ``pageNavigator().jumped(QPdfLink)`` but stays silent for *external*
  URI links, so end-to-end clicks are covered at handler level
  (``PreviewPanel.handle_source_url``) rather than by faked geometry.
"""

import json
import os
import sys

import pytest

PySide6 = pytest.importorskip('PySide6')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compiler import pipeline as _pipeline  # noqa: E402
from compiler.pipeline import compile_ezmath  # noqa: E402
from compiler.source_links import (  # noqa: E402
    link_prefix,
    make_source_url,
    parse_source_url,
)
from compiler.source_map import TypstSourceMap, default_map_path  # noqa: E402


def _stub_typst(monkeypatch):
    stub = type('_TypstStub', (), {'compile': staticmethod(lambda *a, **k: None)})()
    monkeypatch.setattr(_pipeline, 'typst', stub)


# ----------------------------------------------------------------------
# URL scheme: make/parse round-trip + strict rejection
# ----------------------------------------------------------------------

def test_make_source_url_shape():
    assert make_source_url(5, 0) == 'eml-src://typ/5/0'
    assert make_source_url(0, 12) == 'eml-src://typ/0/12'
    with pytest.raises(ValueError):
        make_source_url(-1, 0)
    with pytest.raises(ValueError):
        make_source_url(0, -2)
    with pytest.raises(ValueError):
        make_source_url('x', 0)


def test_parse_source_url_roundtrip():
    assert parse_source_url(make_source_url(5, 0)) == (5, 0)
    assert parse_source_url(make_source_url(123, 45)) == (123, 45)
    assert parse_source_url('  eml-src://typ/7/3  ') == (7, 3)


def test_parse_source_url_rejects():
    for bad in (
        '', 'eml-src://typ/', 'eml-src://typ/5', 'eml-src://typ/5/0/1',
        'eml-src://typ/a/0', 'eml-src://typ/5/b', 'eml-src://typ/-1/0',
        'eml-src://typ/5/0?x=1', 'eml-src://typ/5/0#frag',
        'http://typ/5/0', 'eml-src://doc/5/0', 'eml-src:typ/5/0',
        None, 42, 'eml-src://typ/ /0',
    ):
        assert parse_source_url(bad) is None, bad
    # QUrl-like objects (duck-typed via toString).
    class _Q:
        def __init__(self, s):
            self._s = s

        def toString(self):
            return self._s

    assert parse_source_url(_Q('eml-src://typ/9/1')) == (9, 1)
    assert parse_source_url(_Q('https://example.com')) is None


def test_link_prefix_shape():
    assert link_prefix(9, 0) == '#link("eml-src://typ/9/0")['


# ----------------------------------------------------------------------
# Compiler: link embedding is additive and map-preserving
# ----------------------------------------------------------------------

def _compile(tmp_path, monkeypatch, capsys, text, **kwargs):
    src = tmp_path / 'case.ezmath'
    src.write_text(text, encoding='utf-8')
    _stub_typst(monkeypatch)
    ok = compile_ezmath(str(src), str(tmp_path / 'case.pdf'), **kwargs)
    capsys.readouterr()
    typ = (tmp_path / 'case.typ').read_text(encoding='utf-8')
    smap = TypstSourceMap.load(default_map_path(str(tmp_path / 'case.typ')))
    return ok, typ, smap


def test_links_off_by_default(tmp_path, monkeypatch, capsys):
    ok, typ, _ = _compile(tmp_path, monkeypatch, capsys, 'Hello\n')
    assert ok is True
    assert 'eml-src://typ/' not in typ


def test_links_wrap_mapped_blocks(tmp_path, monkeypatch, capsys):
    ok, typ, smap = _compile(
        tmp_path, monkeypatch, capsys, 'Hello line\nSecond line\n',
        embed_source_links=True)
    assert ok is True
    assert '#link("eml-src://typ/5/0")[Hello line] \\' in typ
    assert '#link("eml-src://typ/7/0")[Second line] \\' in typ
    # Separators and header directives are never wrapped.
    assert '#link' not in [ln for ln in typ.splitlines() if ln.startswith('#v(')][0] \
        if any(ln.startswith('#v(') for ln in typ.splitlines()) else True
    for ln in typ.splitlines():
        if ln.startswith('#set'):
            assert '#link(' not in ln
    # Map still resolves through the wrapped lines.
    assert smap.resolve(5, 0) is not None
    assert smap.resolve(5, 0).start.line == 0
    assert smap.resolve(7, 0).start.line == 1


def test_links_keep_typ_line_numbers(tmp_path, monkeypatch, capsys):
    text = 'First\nSecond\nThird\n'
    _, typ_plain, map_plain = _compile(tmp_path, monkeypatch, capsys, text)
    _, typ_linked, map_linked = _compile(
        tmp_path, monkeypatch, capsys, text, embed_source_links=True)
    # No new lines introduced: identical line counts and identical map ranges.
    assert len(typ_linked.splitlines()) == len(typ_plain.splitlines())
    plain_entries = [(e.typ_start.line, e.typ_end.line,
                      e.src.start.line, e.src.end.line)
                     for e in map_plain.entries]
    linked_entries = [(e.typ_start.line, e.typ_end.line,
                       e.src.start.line, e.src.end.line)
                      for e in map_linked.entries]
    assert linked_entries == plain_entries


def test_links_skip_bodies_with_existing_links(tmp_path, monkeypatch, capsys):
    # *p() passes raw Typst through; a body already containing #link must
    # not be nested inside another link.
    ok, typ, smap = _compile(
        tmp_path, monkeypatch, capsys,
        '*p(#link("https://example.com")[ext])\nAfter\n',
        embed_source_links=True)
    assert ok is True
    first = [ln for ln in typ.splitlines() if 'example.com' in ln][0]
    assert first.count('#link(') == 1
    assert smap.resolve(5, 0) is not None


def test_links_real_pdf_contains_uri_annotations(tmp_path):
    typst = pytest.importorskip('typst')
    _ = typst
    import shutil
    work = str(tmp_path / 'real')
    os.makedirs(work, exist_ok=True)
    src = os.path.join(work, 'doc.ezmath')
    with open(src, 'w', encoding='utf-8') as fh:
        fh.write('Hello link target\nSecond line\n')
    assert compile_ezmath(src, os.path.join(work, 'doc.pdf'),
                          embed_source_links=True) is True
    raw = open(os.path.join(work, 'doc.pdf'), 'rb').read()
    assert b'eml-src://typ/' in raw
    assert b'/URI' in raw
    shutil.rmtree(work, ignore_errors=True)


# ----------------------------------------------------------------------
# Panel handler: URL -> signal (no geometry involved)
# ----------------------------------------------------------------------

def test_handle_source_url_gating(qapp):
    from editor.preview_panel import PreviewPanel
    panel = PreviewPanel()
    try:
        seen = []
        panel.sourceLinkActivated.connect(lambda l, c: seen.append((l, c)))
        assert panel.handle_source_url('eml-src://typ/5/0', True) is True
        assert seen == [(5, 0)]
        # Ctrl required: plain click preserves ordinary viewing.
        assert panel.handle_source_url('eml-src://typ/5/0', False) is False
        assert seen == [(5, 0)]
        # Non-source links (internal + external) are ignored.
        assert panel.handle_source_url('', True) is False
        assert panel.handle_source_url('https://example.com', True) is False
        assert panel.handle_source_url('eml-src://typ/x/0', True) is False
        assert panel.handle_source_url(None, True) is False
        assert seen == [(5, 0)]
    finally:
        panel.close()


def test_event_filter_never_consumes(qapp):
    from PySide6 import QtCore
    from editor.preview_panel import PreviewPanel, pdf_available
    if not pdf_available():
        pytest.skip('Qt PDF modules unavailable')
    panel = PreviewPanel()
    try:
        vp = panel._view.viewport()
        ev = QtCore.QEvent(QtCore.QEvent.MouseButtonPress)
        assert panel.eventFilter(vp, ev) is False
        assert panel.eventFilter(None, ev) is False
    finally:
        panel.close()


def test_jumped_internal_link_ignored(qapp):
    # Internal (GoTo) activations must keep their normal navigation: the
    # handler only acts on eml-src URLs.
    from editor.preview_panel import PreviewPanel
    panel = PreviewPanel()
    try:
        seen = []
        panel.sourceLinkActivated.connect(lambda l, c: seen.append((l, c)))
        panel.handle_source_url('', True)
        assert seen == []
    finally:
        panel.close()


# ----------------------------------------------------------------------
# End of chain: signal -> smap resolve -> editor cursor (mocked click)
# ----------------------------------------------------------------------

def _build_preview_map(tmp_path, monkeypatch, capsys, text):
    from editor.preview import compile_source_to_format
    _stub_typst(monkeypatch)
    res = compile_source_to_format(text, str(tmp_path), source_links=True)
    assert res['smap'] is not None and os.path.isfile(res['smap'])
    return res


def test_full_chain_typ_to_cursor(tmp_path, monkeypatch, capsys, qapp):
    from editor.main_window import MainWindow
    res = _build_preview_map(
        tmp_path, monkeypatch, capsys, 'Alpha line\nBeta line\nGamma line\n')
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win.editor.setPlainText('Alpha line\nBeta line\nGamma line\n')
        win.preview.set_source_map(res['smap'])
        # Simulate what _on_preview_source_link does with typ (7, 0).
        span = win.preview.typ_location_to_eml(7, 0)
        assert span is not None and span.start.line == 1
        assert win.open_source_span(span) is True
        line, _ = win.editor.cursor_line_col()
        assert line == 1
    finally:
        win.close()


def test_chain_unmapped_and_missing_map(qapp):
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win.editor.setPlainText('Only line\n')
        win.preview.set_source_map('/nonexistent/smap.json')
        assert win.preview.typ_location_to_eml(5, 0) is None
        # Missing/unmapped locations never navigate and never raise.
        win._on_preview_source_link(9999, 0)
        line, _ = win.editor.cursor_line_col()
        assert line == 0
        win._on_preview_source_link(0, 0)
        line, _ = win.editor.cursor_line_col()
        assert line == 0
    finally:
        win.close()


def test_resolution_independent_of_view_state(tmp_path, monkeypatch, capsys, qapp):
    # Coordinate-free design: zoom/scroll/page-mode cannot change results.
    from editor.preview_panel import pdf_available
    if not pdf_available():
        pytest.skip('Qt PDF modules unavailable')
    from PySide6.QtPdfWidgets import QPdfView
    res = _build_preview_map(
        tmp_path, monkeypatch, capsys, 'One\nTwo\nThree\nFour\nFive\n')
    from editor.preview_panel import PreviewPanel
    panel = PreviewPanel()
    try:
        panel.set_source_map(res['smap'])
        before = panel.typ_location_to_eml(7, 0)
        panel._view.setZoomMode(QPdfView.ZoomMode.Custom)
        panel._view.setZoomFactor(2.5)
        panel._view.setPageMode(QPdfView.PageMode.SinglePage)
        after = panel.typ_location_to_eml(7, 0)
        assert before is not None and after is not None
        assert (before.start.line, before.end.line) == (after.start.line, after.end.line)
    finally:
        panel.close()


def test_preview_links_absent_by_default_for_exports(tmp_path, monkeypatch, capsys):
    # Export builds (File -> Export As) stay clean: no link annotations.
    from editor.preview import compile_source_to_format
    _stub_typst(monkeypatch)
    res = compile_source_to_format('Hello export\n', str(tmp_path))
    typ = open(res['typ'], encoding='utf-8').read()
    assert 'eml-src://typ/' not in typ
