"""Non-modal *draw gallery: dialog behavior, wiring, single-undo insert.

The catalog itself (entries, examples, insertion math) is covered by
tests/test_draw_catalog.py; this file only exercises the Qt layer:
cards/filters, thumbnails (placeholder vs. preview), the Symbol Bar
wiring and MainWindow's one-undo-step insertion.
"""

import os
import subprocess
import sys

import pytest

pytest.importorskip('PySide6')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PySide6 import QtGui, QtWidgets  # noqa: E402

from editor import draw_gallery  # noqa: E402
from editor.draw_catalog import CATALOG, GROUPS  # noqa: E402
from editor.main_window import MainWindow  # noqa: E402

IDS = [entry.id for entry in CATALOG]


@pytest.fixture()
def window(qapp):
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    win.show()
    yield win
    win.close()
    win._draw_gallery = None


@pytest.fixture()
def gallery(window):
    """MainWindow with its *draw gallery opened (lazily imported)."""
    window._on_symbol_activated('draw-gallery')
    return window._draw_gallery


@pytest.fixture()
def dialog(qapp):
    dlg = draw_gallery.DrawGalleryDialog()
    yield dlg
    dlg.close()
    dlg.deleteLater()


# ----------------------------------------------------------------------
# Dialog structure
# ----------------------------------------------------------------------

def test_dialog_lists_every_catalog_command(dialog):
    assert len(dialog.cards) == len(CATALOG) == 20
    assert dialog.visible_ids() == IDS
    assert dialog.status.text() == f'{len(CATALOG)} commands'
    # Not modal: the editor stays usable behind it.
    assert dialog.isModal() is False


def test_dialog_groups_match_catalog_groups(dialog):
    combo = dialog.group_combo
    assert [combo.itemText(i) for i in range(combo.count())] == \
        ['All', *GROUPS]
    combo.setCurrentText('Constraints')
    shown = set(dialog.visible_ids())
    expected = {e.id for e in CATALOG if e.group == 'Constraints'}
    assert shown == expected
    assert dialog.status.text() == \
        f'{len(shown)} of {len(CATALOG)} commands'


def test_search_filters_by_command_title_and_description(dialog):
    dialog.search.setText('perpendicular')
    assert dialog.visible_ids() == ['perp']
    dialog.search.setText('midpoint')
    assert dialog.visible_ids() == ['midpoint']
    dialog.search.setText('no-such-thing')
    assert dialog.visible_ids() == []
    assert dialog.status.text() == f'0 of {len(CATALOG)} commands'
    label = dialog.findChild(QtWidgets.QLabel, 'draw-gallery-no-match')
    assert label is not None


def test_search_and_group_combine(dialog):
    dialog.group_combo.setCurrentText('Shapes')
    dialog.search.setText('circle')
    assert dialog.visible_ids() == ['circle']


def test_card_content_comes_from_catalog(dialog):
    entry = next(e for e in CATALOG if e.id == 'perp')
    card = dialog.card_for('perp')
    assert card is not None
    assert card.entry is entry
    assert card.findChild(
        QtWidgets.QLabel, 'draw-card-title').text() == entry.title
    assert card.command_btn.isEnabled()


def test_command_without_dialog_is_disabled(dialog):
    # equal-angle is planned: no geo-* symbol in the registry.
    card = dialog.card_for('equal-angle')
    assert card is not None
    assert not card.command_btn.isEnabled()
    assert card.example_btn.isEnabled()


# ----------------------------------------------------------------------
# Thumbnails
# ----------------------------------------------------------------------

def test_missing_previews_show_placeholder(dialog, tmp_path, monkeypatch):
    monkeypatch.setattr(draw_gallery, 'PREVIEW_DIR', str(tmp_path))
    dlg = draw_gallery.DrawGalleryDialog()
    try:
        assert not any(os.listdir(tmp_path))
        for entry_id in IDS:
            thumb = dlg.card_for(entry_id).thumb
            assert thumb.property('has-preview') is False
            assert 'No preview' in thumb.accessibleName()
            assert thumb.pixmap() is not None and not thumb.pixmap().isNull()
    finally:
        dlg.close()
        dlg.deleteLater()


def test_existing_previews_render(qapp, tmp_path, monkeypatch):
    """One hand-sized SVG is enough: rendering, not the catalog, is tested."""
    from PySide6 import QtSvg
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="30">'
           '<rect width="40" height="30" fill="#3366cc"/></svg>')
    (tmp_path / 'line.svg').write_text(svg, encoding='utf-8')
    assert QtSvg.QSvgRenderer(str(tmp_path / 'line.svg')).isValid()
    monkeypatch.setattr(draw_gallery, 'PREVIEW_DIR', str(tmp_path))
    dlg = draw_gallery.DrawGalleryDialog()
    try:
        assert dlg.card_for('line').thumb.property('has-preview') is True
        assert dlg.card_for('point').thumb.property('has-preview') is False
    finally:
        dlg.close()
        dlg.deleteLater()


def test_previews_and_manifest_are_current():
    """Generated previews (scripts/build_draw_previews.py) match manifest.

    Skips until Step 3 has generated them; the manifest hashes every
    example so a catalog change forces a re-render.
    """
    manifest_path = os.path.join(draw_gallery.PREVIEW_DIR, 'manifest.json')
    if not os.path.isfile(manifest_path):
        pytest.skip('previews not generated yet (scripts/build_draw_previews.py)')
    import hashlib
    import json
    with open(manifest_path, encoding='utf-8') as fh:
        manifest = json.load(fh)
    entries = manifest.get('examples', manifest)
    for entry in CATALOG:
        assert entry.id in entries, entry.id
        record = entries[entry.id]
        # Example hash: a catalog example change forces a re-render.
        example_digest = hashlib.sha256(
            entry.example.encode('utf-8')).hexdigest()
        stored_example = record['sha256'] if isinstance(record, dict) else None
        assert stored_example == example_digest, entry.id
        path = os.path.join(draw_gallery.PREVIEW_DIR, f'{entry.id}.svg')
        assert os.path.isfile(path), path
        with open(path, 'rb') as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        assert record['svg_sha256'] == digest, entry.id


# ----------------------------------------------------------------------
# Symbol Bar wiring (MainWindow)
# ----------------------------------------------------------------------

def test_bar_button_opens_non_modal_gallery(window):
    assert window._draw_gallery is None
    bar_btn = window._symbol_bar.button_for('draw-gallery')
    assert bar_btn is not None
    assert '*draw' in bar_btn.accessibleName() or \
        '*draw' in bar_btn.text()
    window._on_symbol_activated('draw-gallery')
    first = window._draw_gallery
    assert first is not None
    assert first.isVisible()
    assert first.isModal() is False
    window._on_symbol_activated('draw-gallery')
    assert window._draw_gallery is first  # one instance, re-raised


def test_gallery_import_is_lazy(window):
    """Importing the editor must not pull in the gallery (or QtSvg)."""
    code = (
        "import sys; sys.path.insert(0, 'src');"
        "import editor.main_window;"
        "print('editor.draw_gallery' in sys.modules,"
        " 'PySide6.QtSvg' in sys.modules)")
    proc = subprocess.run([sys.executable, '-c', code],
                          capture_output=True, text=True,
                          cwd=os.path.join(os.path.dirname(__file__), '..'))
    assert proc.returncode == 0, proc.stderr[-1000:]
    assert proc.stdout.strip() == 'False False'


def test_menu_and_palette_expose_gallery(window):
    actions = [a for a in window.findChildren(QtGui.QAction)
               if a.text().startswith('&Geometry Gallery')]
    assert len(actions) == 1
    assert actions[0].shortcut().toString() == 'Ctrl+Shift+G'
    palette = dict((cid, (title, hint, cb))
                   for cid, title, hint, cb in window._palette_commands())
    assert 'draw.gallery' in palette
    # Same handler as the menu action.
    assert palette['draw.gallery'][2] == window._open_draw_gallery


def test_draw_gallery_symbol_keeps_skeleton_action():
    from editor.symbol_registry import get_symbol, symbols_in_category
    gallery = get_symbol('draw-gallery')
    assert gallery.display == '*draw'
    assert gallery.insert_text == '*draw(\n)'
    # Rule 5: the old skeleton stays, only relabeled, and keeps its
    # exact insert text / cursor offset (asserted in test_symbol_palette).
    skeleton = get_symbol('draw-skeleton')
    assert skeleton.insert_text.startswith('*draw(\n')
    assert skeleton.insert_text.endswith('\n)')
    geometry = symbols_in_category('Geometry')
    assert geometry[0].name == 'draw-gallery'


# ----------------------------------------------------------------------
# Insertion (one undo step, block-aware)
# ----------------------------------------------------------------------

def test_example_outside_block_wraps_and_single_undo(gallery):
    window = gallery.parent()  # MainWindow
    dlg = gallery
    window.editor.setPlainText('Hello\n')
    window.editor.textCursor().setPosition(0)
    window.editor.setTextCursor(window.editor.textCursor())
    before = window.editor.toPlainText()
    dlg.card_for('line').example_btn.click()
    text = window.editor.toPlainText()
    assert text.startswith('*draw(')
    assert text.endswith('Hello\n')
    # One undo restores the document exactly.
    window.editor.undo()
    assert window.editor.toPlainText() == before


def test_example_inside_block_appends_before_closer(gallery):
    window = gallery.parent()  # MainWindow
    dlg = gallery
    original = '*draw(\n    *point(A = 0, 0)\n)\n'
    window.editor.setPlainText(original)
    cursor = window.editor.textCursor()
    cursor.setPosition(len('*draw(\n    *point(A = 0, 0)\n'))
    window.editor.setTextCursor(cursor)
    dlg.card_for('circle').example_btn.click()
    text = window.editor.toPlainText()
    lines = text.split('\n')
    assert lines[0] == '*draw('
    assert lines[1] == '    *point(A = 0, 0)'
    assert any(line.strip() == '*circle(O ; A)' for line in lines)
    assert lines[-2] == ')'
    # Indentation matches the block's existing content.
    assert all(line.startswith('    ') for line in lines[1:-2])
    window.editor.undo()
    assert window.editor.toPlainText() == original


def test_single_line_block_is_expanded(gallery):
    window = gallery.parent()  # MainWindow
    dlg = gallery
    window.editor.setPlainText('*draw(*point(A = 0, 0))')
    cursor = window.editor.textCursor()
    cursor.setPosition(6)
    window.editor.setTextCursor(cursor)
    dlg.card_for('perp').example_btn.click()
    text = window.editor.toPlainText()
    assert text.startswith('*draw(\n')
    assert text.rstrip().endswith(')')
    assert '    *point(A = 0, 0)' in text
    assert '    *perp(' in text
    # Still ONE valid block, one undo step.
    window.editor.undo()
    assert window.editor.toPlainText() == '*draw(*point(A = 0, 0))'


def test_selection_replaced_by_insert_in_one_step(gallery):
    window = gallery.parent()  # MainWindow
    dlg = gallery
    window.editor.setPlainText('old text\n')
    cursor = window.editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(3, QtGui.QTextCursor.KeepAnchor)
    window.editor.setTextCursor(cursor)
    dlg.card_for('point').example_btn.click()
    text = window.editor.toPlainText()
    assert text.startswith('*draw(')
    assert 'old' not in text and ' text\n' in text
    window.editor.undo()
    assert window.editor.toPlainText() == 'old text\n'


def test_empty_block_button_inserts_skeleton(gallery):
    from editor.symbol_registry import get_symbol
    window = gallery.parent()  # MainWindow
    dlg = gallery
    window.editor.setPlainText('')
    dlg.empty_btn.click()
    text = window.editor.toPlainText()
    assert text == get_symbol('draw-skeleton').insert_text
    window.editor.undo()
    assert window.editor.toPlainText() == ''


def test_command_button_runs_parameter_dialog(gallery, monkeypatch):
    window = gallery.parent()  # MainWindow
    dlg = gallery
    calls = []
    monkeypatch.setattr(
        window, '_prompt_symbol_dialog',
        lambda sym, **kw: calls.append((sym.name, kw)))
    dlg.card_for('perp').command_btn.click()
    assert calls and calls[0][0] == 'geo-perp'
    # Gallery insertion path is passed along (block-aware, one undo).
    assert 'insert' in calls[0][1]
    assert calls[0][1]['insert'] == window._insert_draw_gallery_source


def test_dialog_command_outside_block_becomes_own_block(window):
    """A dialog-built single-line *draw(...) merges or wraps correctly."""
    window.editor.setPlainText('')
    window._insert_draw_gallery_source('*draw(*line(A ; B))')
    assert window.editor.toPlainText() == '*draw(*line(A ; B))'
    # And inside an existing block it merges into it.
    window.editor.setPlainText('*draw(\n    *point(A = 0, 0)\n)\n')
    cursor = window.editor.textCursor()
    cursor.setPosition(len('*draw(\n    *point(A = 0, 0)\n'))
    window.editor.setTextCursor(cursor)
    window._insert_draw_gallery_source('*draw(*line(A ; B))')
    text = window.editor.toPlainText()
    assert text.count('*draw(') == 1
    assert '    *line(A ; B)' in text
    assert text.split('\n')[-2] == ')'
