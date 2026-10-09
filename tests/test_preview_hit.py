"""PDF-preview Ctrl+Click hit-testing: annotations, geometry, end-to-end.

Verified platform facts (see ``editor.pdf_links`` / ``PreviewPanel``):

- Typst emits plain ``/Annot/Subtype/Link/Rect[...]/URI(...)`` objects;
  Qt 6.11 exposes no link-enumeration API, so annotations are read from
  the PDF bytes (stdlib only) and viewport mapping uses live scrollbar /
  layout metrics cross-checked against scrollbar maximums.
- Ground truth for clicks never comes from the mapping under test:
  extractor tests use hand-built PDFs with known rects, and end-to-end
  clicks target dark-pixel bounding boxes found by rendering pages at a
  known scale (``QPdfDocument.render`` maps page points linearly).
"""

import os
import sys
import zlib

import pytest

PySide6 = pytest.importorskip('PySide6')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compiler import pipeline as _pipeline  # noqa: E402
from compiler.pipeline import compile_ezmath  # noqa: E402
from editor.pdf_links import (  # noqa: E402
    extract_link_annotations,
    extract_link_annotations_from_file,
    hit_test,
)


# ----------------------------------------------------------------------
# Synthetic PDFs with known annotation rectangles (no Typst needed)
# ----------------------------------------------------------------------

def _xref(objects):
    """Assemble ``%PDF`` bytes from ``[(num, body_bytes)]`` with valid xref."""
    out = [b'%PDF-1.4\n']
    offsets = {}
    for num, body in objects:
        offsets[num] = sum(len(c) for c in out)
        out.append(f'{num} 0 obj\n'.encode('latin-1'))
        out.append(body)
        out.append(b'\nendobj\n')
    start = sum(len(c) for c in out)
    size = max(n for n, _ in objects) + 1
    out.append(f'xref\n0 {size}\n'.encode('latin-1'))
    out.append(b'0000000000 65535 f \n')
    for i in range(1, size):
        out.append(f'{offsets.get(i, 0):010d} 00000 n \n'.encode('latin-1'))
    out.append(f'trailer\n<</Size {size}/Root 1 0 R>>\nstartxref\n{start}\n%%EOF'.encode())
    return b''.join(out)


def _stream(data):
    return b'<</Length %d>>\nstream\n' % len(data) + data + b'\nendstream'


def build_synthetic_pdf():
    """Two pages; page 0 has two eml links + one https link, page 1 one eml link."""
    c1 = b'BT /F1 24 Tf 20 150 Td (Hello) Tj ET'
    c2 = b'BT /F1 24 Tf 20 100 Td (World) Tj ET'
    objs = [
        (1, b'<</Type/Catalog/Pages 2 0 R>>'),
        (2, b'<</Type/Pages/Kids[3 0 R 6 0 R]/Count 2>>'),
        (3, b'<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]'
            b'/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R'
            b'/Annots[7 0 R 8 0 R 10 0 R]>>'),
        (4, b'<</BaseFont/Helvetica/Type/Font/Subtype/Type1'
            b'/Encoding/WinAnsiEncoding>>'),
        (5, _stream(c1)),
        (6, b'<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]'
            b'/Resources<</Font<</F1 4 0 R>>>>/Contents 9 0 R'
            b'/Annots[11 0 R]>>'),
        (9, _stream(c2)),
        (7, b'<</Type/Annot/Subtype/Link/Rect[20 140 120 165]'
            b'/Border[0 0 0]/A<</S/URI/URI(eml-src://typ/5/0)>>>>'),
        (8, b'<</Type/Annot/Subtype/Link/Rect[20 100 120 125]'
            b'/Border[0 0 0]/A<</S/URI/URI(https://example.com)>>>>'),
        (10, b'<</Type/Annot/Subtype/Text/Rect[20 60 40 80]/Contents(note)>>'),
        (11, b'<</Type/Annot/Subtype/Link/Rect[20 140 120 165]'
            b'/Border[0 0 0]/A<</S/URI/URI<656d6c2d7372633a2f2f7479702f392f30>>>>>'),
    ]
    return _xref(objs)


def test_extract_synthetic_pages_and_uris():
    found = extract_link_annotations(build_synthetic_pdf())
    by_page = {}
    for page, rect, uri in found:
        by_page.setdefault(page, []).append((rect, uri))
    assert set(by_page) == {0, 1}
    # GoTo/Text annotation (obj 10) is skipped; https kept (filtering is
    # the caller's job via parse_source_url).
    uris0 = sorted(u for _, u in by_page[0])
    assert uris0 == ['eml-src://typ/5/0', 'https://example.com']
    assert by_page[0][0][0] == (20.0, 140.0, 120.0, 165.0)
    # Hex-form URI decodes to eml-src://typ/9/0.
    assert by_page[1] == [((20.0, 140.0, 120.0, 165.0), 'eml-src://typ/9/0')]


def test_extract_graceful_inputs():
    assert extract_link_annotations(b'') == []
    assert extract_link_annotations(b'not a pdf at all............') == []
    assert extract_link_annotations(b'%PDF-1.4\ntrailer junk') == []
    assert extract_link_annotations(None) == []
    assert extract_link_annotations_from_file('/nonexistent/x.pdf') == []


def test_extract_broken_xref_still_works():
    data = bytearray(build_synthetic_pdf())
    # Corrupt every xref offset: a xref-dependent parser would fail, the
    # scanner must not.
    start = data.find(b'xref')
    end = data.find(b'trailer')
    assert start != -1 and end != -1
    data[start:end] = b'0' * (end - start)
    found = extract_link_annotations(bytes(data))
    assert len(found) == 3


def test_extract_compressed_annot_object():
    inner = (b'<</Type/Annot/Subtype/Link/Rect[10 10 50 30]'
             b'/A<</S/URI/URI(eml-src://typ/2/0)>>>>')
    objs = [
        (1, b'<</Type/Catalog/Pages 2 0 R>>'),
        (2, b'<</Type/Pages/Kids[3 0 R]/Count 1>>'),
        (3, b'<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]'
            b'/Resources<<>>/Contents 4 0 R/Annots[5 0 R]>>'),
        (4, _stream(b'BT (x) Tj ET')),
        (5, b'<</Length %d/Filter/FlateDecode>>\nstream\n' % 0 + b'' + b'\nendstream'),
    ]
    payload = zlib.compress(inner)
    objs[-1] = (5, b'<</Length %d/Filter/FlateDecode>>\nstream\n' % len(payload)
                + payload + b'\nendstream')
    found = extract_link_annotations(_xref(objs))
    assert found == [(0, (10.0, 10.0, 50.0, 30.0), 'eml-src://typ/2/0')]


def test_hit_test_unit():
    rect = (20.0, 140.0, 120.0, 165.0)
    assert hit_test(rect, 70.0, 150.0) is True
    assert hit_test(rect, 20.0, 140.0) is True  # edges inclusive
    assert hit_test(rect, 120.0, 165.0) is True
    assert hit_test(rect, 10.0, 150.0) is False
    assert hit_test(rect, 70.0, 200.0) is False
    assert hit_test(rect, 19.4, 150.0) is False
    assert hit_test(rect, 19.6, 150.0) is True  # epsilon tolerance
    assert hit_test(rect, 'x', 150.0) is False
    assert hit_test('bad', 1, 2) is False


# ----------------------------------------------------------------------
# Helpers for Qt integration tests
# ----------------------------------------------------------------------

def _stub_typst(monkeypatch):
    stub = type('_TypstStub', (), {'compile': staticmethod(lambda *a, **k: None)})()
    monkeypatch.setattr(_pipeline, 'typst', stub)


def _real_pdf_with_links(workdir, text):
    """Compile with real Typst backend; returns (pdf_path, smap)."""
    typst = pytest.importorskip('typst')
    assert typst is not None
    from compiler.source_map import TypstSourceMap, default_map_path
    src = os.path.join(workdir, 'doc.ezmath')
    with open(src, 'w', encoding='utf-8') as fh:
        fh.write(text)
    assert compile_ezmath(src, os.path.join(workdir, 'doc.pdf'),
                          embed_source_links=True) is True
    smap = TypstSourceMap.load(default_map_path(os.path.join(workdir, 'doc.typ')))
    return os.path.join(workdir, 'doc.pdf'), smap


def _is_text_pixel(img, x, y):
    c = img.pixelColor(x, y)
    return c.alpha() > 128 and c.lightness() < 120


def _render_bboxes(doc, page, scale=2):
    """Dark-pixel row clusters per page -> [(x0,y0,x1,y1)] in PDF points.

    Render images use top-left origin; the flip to PDF bottom-left
    coordinates happens here, so boxes compare directly with annotation
    ``/Rect`` values.
    """
    from PySide6.QtCore import QSize
    size = doc.pagePointSize(page)
    pw, ph = float(size.width()), float(size.height())
    img = doc.render(page, QSize(int(pw * scale), int(ph * scale)))
    W, H = img.width(), img.height()
    rows = []
    for y in range(H):
        dark = 0
        for x in range(0, W, 2):
            if _is_text_pixel(img, x, y):
                dark += 1
        if dark:
            rows.append(y)
    clusters = []
    if rows:
        start, prev = rows[0], rows[0]
        for y in rows[1:]:
            if y - prev > 10:
                clusters.append((start, prev))
                start = y
            prev = y
        clusters.append((start, prev))
    boxes = []
    for y0, y1 in clusters:
        xs = []
        for y in range(y0, y1 + 1, 2):
            for x in range(0, W, 3):
                if _is_text_pixel(img, x, y):
                    xs.append(x)
        if xs:
            boxes.append((min(xs) / scale, ph - y1 / scale,
                          max(xs) / scale, ph - y0 / scale))
    return boxes


def _overlap_area(a, b):
    x0, y0, x1, y1 = a
    u0, v0, u1, v1 = b
    return max(0.0, min(x1, u1) - max(x0, u0)) * max(0.0, min(y1, v1) - max(y0, v0))


def test_panel_center_agreement(tmp_path, qapp):
    """Non-circular check: model-predicted center page == navigator page."""
    from editor.preview_panel import PreviewPanel, pdf_available
    if not pdf_available():
        pytest.skip('Qt PDF modules unavailable')
    pytest.importorskip('typst')
    import tempfile
    work = tempfile.mkdtemp(prefix='easymath-hit-')
    lines = [f'Block line number {i} with some words' for i in range(30)]
    pdf, _ = _real_pdf_with_links(work, '\n'.join(lines) + '\n')
    panel = PreviewPanel()
    try:
        panel.resize(800, 1000)
        panel.show()
        qapp.processEvents()
        panel.show_pdf(pdf)
        qapp.processEvents()
        vsb = panel._view.verticalScrollBar()
        vph = panel._view.viewport().height()
        metrics = panel._layout_metrics()
        assert metrics is not None
        _k, tops, _l, _s, heights, _w = metrics
        for v in (0, vsb.maximum() // 4, vsb.maximum() // 2,
                  3 * vsb.maximum() // 4, vsb.maximum()):
            vsb.setValue(v)
            for _ in range(3):
                qapp.processEvents()
            center = v + vph / 2
            expect = next(i for i in reversed(range(len(tops)))
                          if center >= tops[i])
            assert panel._view.pageNavigator().currentPage() == expect, v
    finally:
        panel.close()


def _viewport_for_pdf_point(panel, page, px, py):
    k, tops, lefts, sizes, _h, _w = panel._layout_metrics()
    pw, ph = sizes[page]
    hx = panel._view.horizontalScrollBar().value()
    vy = panel._view.verticalScrollBar().value()
    from PySide6 import QtCore
    return QtCore.QPoint(int(lefts[page] + px * k - hx),
                         int(tops[page] + (ph - py) * k - vy))


def test_end_to_end_ctrl_click_navigates(tmp_path, qapp):
    """Real Ctrl+Clicks on rendered-text centers navigate to .eml lines."""
    from PySide6 import QtCore, QtTest
    from editor.main_window import MainWindow
    from editor.preview_links import parse_source_url
    pytest.importorskip('typst')
    import tempfile
    text = ('# Fruit report\n'
            'Apple line with words\n'
            'Banana line with words\n'
            'Cherry line with words\n')
    work = tempfile.mkdtemp(prefix='easymath-hit-')
    pdf, smap = _real_pdf_with_links(work, text)
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win._preview_dock.show()
        qapp.processEvents()
        win.editor.setPlainText(text)
        win.preview.show_pdf(pdf)
        win.preview.set_source_map(os.path.join(work, 'doc.smap.json'))
        qapp.processEvents()
        # Ground truth WITHOUT the mapping under test: render bboxes in
        # PDF points, overlapped against extracted annotation rects.
        boxes = _render_bboxes(win.preview._document, 0)
        annots = [(r, u) for p, r, u in win.preview._link_annots if p == 0]
        assert annots, 'expected link annotations on page 0'
        targets = []
        for box in boxes:
            best, best_area = None, 0.0
            for rect, uri in annots:
                area = _overlap_area(box, rect)
                if area > best_area:
                    best, best_area = (rect, uri), area
            if best is None:
                continue  # e.g. the unwrapped title heading
            parsed = parse_source_url(best[1])
            assert parsed is not None
            span = smap.resolve(*parsed)
            assert span is not None
            targets.append((box, span.start.line))
        assert len(targets) >= 3, (boxes, annots)
        seen = []
        win.preview.sourceLinkActivated.connect(lambda l, c: seen.append((l, c)))
        for (x0, y0, x1, y1), eml_line in targets[:3]:
            pos = _viewport_for_pdf_point(
                win.preview, 0, (x0 + x1) / 2.0, (y0 + y1) / 2.0)
            QtTest.QTest.mouseClick(win.preview._view.viewport(),
                                    QtCore.Qt.LeftButton,
                                    QtCore.Qt.ControlModifier, pos)
            qapp.processEvents()
        assert len(seen) == 3, seen
        for (typ_line, _), eml_line in zip(seen, [e for _, e in targets[:3]]):
            span = smap.resolve(typ_line, 0)
            assert span is not None and span.start.line == eml_line
        line, _ = win.editor.cursor_line_col()
        assert line == targets[2][1]
        # Plain click (no Ctrl) on a link navigates nowhere.
        before = list(seen)
        (x0, y0, x1, y1), _eml = targets[0]
        pos = _viewport_for_pdf_point(
            win.preview, 0, (x0 + x1) / 2.0, (y0 + y1) / 2.0)
        QtTest.QTest.mouseClick(win.preview._view.viewport(),
                                QtCore.Qt.LeftButton,
                                QtCore.Qt.NoModifier, pos)
        qapp.processEvents()
        assert seen == before
    finally:
        win.close()


def test_end_to_end_zoom_scrolled_multipage(tmp_path, qapp):
    """Same battery under Custom zoom, scrolled, SinglePage and page 2."""
    from PySide6 import QtCore, QtTest
    from PySide6.QtPdfWidgets import QPdfView
    from editor.main_window import MainWindow
    pytest.importorskip('typst')
    import tempfile
    lines = [f'Zoom block {i} filler words here' for i in range(25)]
    text = '\n'.join(lines) + '\n'
    work = tempfile.mkdtemp(prefix='easymath-hit-')
    pdf, smap = _real_pdf_with_links(work, text)
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win._preview_dock.show()
        qapp.processEvents()
        win.editor.setPlainText(text)
        win.preview.show_pdf(pdf)
        win.preview.set_source_map(os.path.join(work, 'doc.smap.json'))
        qapp.processEvents()
        assert win.preview._document.pageCount() >= 2
        seen = []
        win.preview.sourceLinkActivated.connect(lambda l, c: seen.append((l, c)))

        def click_block(page, box):
            cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
            pos = _viewport_for_pdf_point(win.preview, page, cx, cy)
            QtTest.QTest.mouseClick(win.preview._view.viewport(),
                                    QtCore.Qt.LeftButton,
                                    QtCore.Qt.ControlModifier, pos)
            qapp.processEvents()

        # Custom zoom 2.0, scrolled to bottom: click a block on last page.
        win.preview._view.setZoomMode(QPdfView.ZoomMode.Custom)
        win.preview._view.setZoomFactor(2.0)
        last = win.preview._document.pageCount() - 1
        win.preview._view.verticalScrollBar().setValue(
            win.preview._view.verticalScrollBar().maximum())
        qapp.processEvents()
        boxes = _render_bboxes(win.preview._document, last)
        annots = [(r, u) for p, r, u in win.preview._link_annots if p == last]
        target = None
        for box in boxes:
            for rect, uri in annots:
                if _overlap_area(box, rect) > 0:
                    target = (box, uri)
                    break
            if target is not None:
                break
        assert target is not None, 'expected an annotated block on last page'
        (x0, y0, x1, y1), uri = target
        from editor.preview_links import parse_source_url
        expect_typ = parse_source_url(uri)[0]
        click_block(last, (x0, y0, x1, y1))
        assert seen, 'scrolled zoomed click must navigate'
        assert seen[-1][0] == expect_typ
        span = smap.resolve(seen[-1][0], 0)
        assert span is not None
        assert win.editor.cursor_line_col()[0] == span.start.line

        # SinglePage mode on page 1.
        seen.clear()
        win.preview._view.setPageMode(QPdfView.PageMode.SinglePage)
        win.preview._view.pageNavigator().jump(1, QtCore.QPointF(0, 0))
        qapp.processEvents()
        boxes1 = _render_bboxes(win.preview._document, 1)
        assert boxes1
        click_block(1, boxes1[0])
        assert seen, 'single-page click must navigate'
        span = smap.resolve(seen[-1][0], 0)
        assert span is not None
    finally:
        # Restore shared preview defaults for other tests.
        try:
            win.preview._view.setPageMode(QPdfView.PageMode.MultiPage)
            win.preview._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        except Exception:
            pass
        win.close()


def test_ctrl_click_gap_and_ordinary_link(tmp_path, qapp):
    """Clicks on gaps and on non-eml links navigate nowhere."""
    from PySide6 import QtCore, QtTest
    from editor.main_window import MainWindow
    from compiler.source_map import SourceSpan, SourcePosition, TypstSourceMap
    typst = pytest.importorskip('typst')
    import tempfile
    # Hand-built Typst (exact line numbers known): an eml-src block, an
    # ordinary https block, and another eml-src block.
    typ_lines = [
        '#set text(size: 12pt)',
        '#set page(paper: "a4", margin: 2cm)',
        '',
        '#link("eml-src://typ/3/0")[First block words] \\',
        '#v(0.65em)',
        '#link("https://example.com")[outer link words] \\',
        '#v(0.65em)',
        '#link("eml-src://typ/7/0")[Third block words] \\',
    ]
    work = tempfile.mkdtemp(prefix='easymath-hit-')
    typ_path = os.path.join(work, 'hand.typ')
    pdf_path = os.path.join(work, 'hand.pdf')
    with open(typ_path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(typ_lines) + '\n')
    typst.compile(typ_path, pdf_path)
    smap = TypstSourceMap(source_file=os.path.join(work, 'doc.eml'),
                          typ_file=pdf_path.replace('.pdf', '.typ'))
    smap.add(SourcePosition(3, 0),
             SourcePosition(3, len(typ_lines[3])),
             SourceSpan(smap.source_file, SourcePosition(0, 0), SourcePosition(0, 17)))
    smap.add(SourcePosition(7, 0),
             SourcePosition(7, len(typ_lines[7])),
             SourceSpan(smap.source_file, SourcePosition(2, 0), SourcePosition(2, 17)))
    smap_path = os.path.join(work, 'hand.smap.json')
    smap.save(smap_path)
    text = 'First block words\nouter link words\nThird block words\n'
    with open(os.path.join(work, 'doc.eml'), 'w', encoding='utf-8') as fh:
        fh.write(text)
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win._preview_dock.show()
        qapp.processEvents()
        win.editor.setPlainText(text)
        win.preview.show_pdf(pdf_path)
        win.preview.set_source_map(smap_path)
        qapp.processEvents()
        seen = []
        win.preview.sourceLinkActivated.connect(lambda l, c: seen.append((l, c)))
        annots_all = [(p, r, u) for p, r, u in win.preview._link_annots if p == 0]
        assert len(annots_all) >= 3, annots_all
        # Gap probe: midpoint between the first two annotated blocks that
        # overlaps no annotation rect at all (verified independently).
        page_annots = sorted(
            ((r, u) for _, r, u in annots_all), key=lambda t: t[0][1])
        centers = [((r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0) for r, _ in page_annots]
        gap = None
        for (ax, ay), (bx, by) in zip(centers, centers[1:]):
            gx, gy = (ax + bx) / 2.0, (ay + by) / 2.0
            if all(_overlap_area((gx - 1, gy - 1, gx + 1, gy + 1), r) == 0
                   for r, _ in page_annots):
                gap = (gx, gy)
                break
        assert gap is not None, 'need an annotation-free gap for the probe'
        pos = _viewport_for_pdf_point(win.preview, 0, *gap)
        QtTest.QTest.mouseClick(win.preview._view.viewport(),
                                QtCore.Qt.LeftButton,
                                QtCore.Qt.ControlModifier, pos)
        qapp.processEvents()
        assert seen == []
        # Ordinary https link block: hit-test finds the annotation but the
        # URL is not eml-src, so no navigation (external behavior kept).
        https_rect = next(r for r, u in page_annots if u == 'https://example.com')
        cx = (https_rect[0] + https_rect[2]) / 2.0
        cy = (https_rect[1] + https_rect[3]) / 2.0
        pos = _viewport_for_pdf_point(win.preview, 0, cx, cy)
        QtTest.QTest.mouseClick(win.preview._view.viewport(),
                                QtCore.Qt.LeftButton,
                                QtCore.Qt.ControlModifier, pos)
        qapp.processEvents()
        assert seen == []
    finally:
        win.close()
