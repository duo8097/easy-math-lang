"""Template window: preview + editable code + command palette.

The window a gallery card's ``Insert example…`` button opens — this
file exercises its structure (preview left, code under it, palette
right), the live palette (all geometry commands, the ones used in the
code pinned to the top in bold, greyed out without a parameter
dialog), and the two ways it changes state:

- ``insertRequested`` → MainWindow inserts the (possibly edited) code
  as one undo step and the window closes;
- ``commandRequested`` → MainWindow runs the parameter dialog and the
  built command lands in the *code area*, never the document.
"""

import os
import sys

import pytest

pytest.importorskip('PySide6')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PySide6 import QtCore, QtGui, QtTest, QtWidgets  # noqa: E402

from editor.command_palette import fuzzy_score  # noqa: E402
from editor.draw_catalog import (CATALOG, commands_in,  # noqa: E402
                                 get_entry)
from editor.draw_template import PREVIEW_H, PREVIEW_W  # noqa: E402
from editor.main_window import MainWindow  # noqa: E402


@pytest.fixture()
def window(qapp):
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    win.show()
    yield win
    win.close()
    win._draw_gallery = None
    win._draw_template = None


@pytest.fixture()
def gallery(window):
    """MainWindow with its *draw gallery opened (lazily imported)."""
    window._on_symbol_activated('draw-gallery')
    return window._draw_gallery


@pytest.fixture()
def template(window, gallery):
    """The template window opened on the 'perp' example."""
    gallery.card_for('perp').example_btn.click()
    dlg = window._draw_template
    assert dlg is not None and dlg.isVisible()
    return dlg


def palette_commands(dlg):
    """Every palette row's command, in display order.

    Disabled rows (no parameter dialog) count; the "no match"
    placeholder row (no command data) does not.
    """
    out = []
    for i in range(dlg.commands.count()):
        command = dlg.commands.item(i).data(QtCore.Qt.UserRole)
        if isinstance(command, str):
            out.append(command)
    return out


def item_for(dlg, command):
    for i in range(dlg.commands.count()):
        item = dlg.commands.item(i)
        if item.data(QtCore.Qt.UserRole) == command:
            return item
    return None


# ----------------------------------------------------------------------
# Structure
# ----------------------------------------------------------------------

def test_card_button_opens_template_without_touching_document(window, gallery):
    window.editor.setPlainText('Hello\n')
    gallery.card_for('perp').example_btn.click()
    dlg = window._draw_template
    assert dlg is not None and dlg.isVisible()
    assert dlg.isModal() is False  # document stays visible behind it
    assert dlg.entry == get_entry('perp')
    assert 'Perpendicular' in dlg.windowTitle()   # wording not pinned
    assert dlg.code.toPlainText() == get_entry('perp').example
    assert dlg.preview.property('has-preview') is True
    assert dlg.insert_btn.isEnabled()
    # Nothing is inserted until Insert is pressed.
    assert window.editor.toPlainText() == 'Hello\n'


def test_layout_preview_left_code_under_palette_right(qapp, template):
    template.show()
    qapp.processEvents()
    # Structure, not pixels (DPI/screen-clamp independent): the body
    # holds two columns — left = preview over code, right = palette.
    body = template.layout().itemAt(1).layout()   # header, body, buttons
    left, right = body.itemAt(0).layout(), body.itemAt(1).layout()
    left_widgets = [left.itemAt(i).widget() for i in range(left.count())]
    right_widgets = [right.itemAt(i).widget() for i in range(right.count())]
    assert template.preview in left_widgets       # preview on the left
    assert template.code in left_widgets          # …code in the same
    assert left_widgets.index(template.preview) < left_widgets.index(
        template.code)                            # …column, above it
    assert template.commands in right_widgets     # palette on the right
    # The preview is re-rendered at the template tile size — not the
    # smaller gallery thumbnail (a stale call would give 168×112).
    assert template.preview.pixmap().size() == QtCore.QSize(
        PREVIEW_W, PREVIEW_H)
    label = template.findChild(
        QtWidgets.QLabel, 'draw-template-palette-label')
    assert label is not None
    assert label.text() == 'Geometry commands'
    assert template.search.isVisible()
    assert template.insert_btn.isVisible()
    assert template.cancel_btn.isVisible()


def test_one_instance_reused_and_reloaded(window, gallery):
    gallery.card_for('line').example_btn.click()
    first = window._draw_template
    gallery.card_for('circle').example_btn.click()
    assert window._draw_template is first  # one instance, re-loaded
    assert first.entry == get_entry('circle')
    assert 'Circle' in first.windowTitle()
    assert first.code.toPlainText() == get_entry('circle').example
    assert first.preview.property('has-preview') is True


def test_reopening_discards_edits_filter_and_button_state(window, gallery):
    """Switching cards resets everything — the new example is pristine."""
    gallery.card_for('line').example_btn.click()
    dlg = window._draw_template
    dlg.code.setPlainText('   ')            # user edits + disables Insert
    dlg.search.setText('cir')               # stale filter
    assert not dlg.insert_btn.isEnabled()
    gallery.card_for('circle').example_btn.click()
    assert dlg.code.toPlainText() == get_entry('circle').example
    assert dlg.search.text() == ''
    assert dlg.insert_btn.isEnabled()


def test_reopening_same_card_keeps_edits(window, gallery):
    """Re-clicking the open card must NOT silently discard edits."""
    gallery.card_for('line').example_btn.click()
    dlg = window._draw_template
    dlg.code.setPlainText('MY WORK IN PROGRESS')
    dlg.search.setText('cir')
    gallery.card_for('line').example_btn.click()   # same card again
    assert dlg.isVisible()
    assert dlg.code.toPlainText() == 'MY WORK IN PROGRESS'
    assert dlg.search.text() == 'cir'


def test_reopening_same_card_after_close_reloads_fresh(window, gallery):
    """The keep-edits skip applies only while the window is shown —
    after Cancel/Insert closed it, the same card loads pristine."""
    gallery.card_for('line').example_btn.click()
    dlg = window._draw_template
    dlg.code.setPlainText('STALE EDITS')
    dlg.cancel_btn.click()                         # hidden, entry intact
    assert not dlg.isVisible()
    assert dlg.entry == get_entry('line')
    gallery.card_for('line').example_btn.click()   # same card, closed
    assert dlg.isVisible()
    assert dlg.code.toPlainText() == get_entry('line').example


def test_missing_preview_shows_placeholder(window, gallery, tmp_path,
                                           monkeypatch):
    from editor import draw_gallery
    monkeypatch.setattr(draw_gallery, 'PREVIEW_DIR', str(tmp_path))
    gallery.card_for('point').example_btn.click()
    dlg = window._draw_template
    assert dlg.preview.property('has-preview') is False
    assert 'No preview' in dlg.preview.accessibleName()
    # Placeholder is drawn at the tile size too (no dangling pixmap).
    assert dlg.preview.pixmap() is not None
    assert dlg.preview.pixmap().size() == QtCore.QSize(PREVIEW_W, PREVIEW_H)


# ----------------------------------------------------------------------
# Command palette (right side)
# ----------------------------------------------------------------------

def test_palette_lists_all_commands_in_code_ones_first(template):
    rows = palette_commands(template)
    assert len(rows) == len(CATALOG) == 20
    # Commands used in the code are pinned to the top, in the order
    # they first appear …
    used = ['point', 'distance', 'perp', 'triangle', 'right-angle']
    assert rows[:len(used)] == used
    # … then the rest of the catalog in gallery order.
    assert rows[len(used):] == [e.command for e in CATALOG
                                if e.command not in used]
    # Pinned rows are shown bold.
    assert item_for(template, 'point').font().bold()
    assert not item_for(template, 'circle').font().bold()


def test_palette_follows_code_edits_and_filter(template):
    template.code.setPlainText('*draw(\n    *line(A ; B)\n)\n')
    assert palette_commands(template)[0] == 'line'   # pinned first
    assert item_for(template, 'line').font().bold()
    assert not item_for(template, 'point').font().bold()
    # The filter fuzzy-narrows the whole list (matches derived from
    # the catalog so a renamed title does not fail this test) …
    template.search.setText('no-such-thing')
    assert palette_commands(template) == []
    template.search.setText('on-c')
    expected = [e.command for e in CATALOG
                if fuzzy_score('on-c', f'{e.title} {e.command}') is not None]
    assert palette_commands(template) == expected
    assert 'on-circle' in expected
    # … and the first enabled row is what Enter would activate.
    assert template.commands.currentRow() == 0
    # No commands in the code: still the whole catalog, nothing bold.
    template.search.clear()
    template.code.setPlainText('no geometry at all')
    assert len(palette_commands(template)) == len(CATALOG)
    assert not item_for(template, 'point').font().bold()


def test_pinned_commands_stay_on_top_while_filtering(window, template):
    """Source finding: fuzzy score must not demote used commands.

    Query 'c' scores the unused *circle (0.13) far better than the
    used *perp (24.18) — yet in-code commands stay pinned above.
    """
    assert 'perp' in commands_in(template.code.toPlainText())
    assert fuzzy_score('c', 'Perpendicular *perp') > \
        fuzzy_score('c', 'Circle *circle')
    template.search.setText('c')
    rows = palette_commands(template)
    used = commands_in(template.code.toPlainText())
    # Every used command that survives the filter sits above every
    # unused one that survives it.
    matching_used = [c for c in rows if c in used]
    matching_unused = [c for c in rows if c not in used]
    assert matching_used and matching_unused
    assert rows == matching_used + matching_unused
    assert rows.index('perp') < rows.index('circle')


def test_palette_lists_every_catalog_command_once(template):
    """All 20 rows, exactly once — even commands the code never uses."""
    rows = palette_commands(template)
    assert sorted(rows) == sorted(e.command for e in CATALOG)
    # equal-angle has no parameter dialog yet: present, disabled and
    # (not being in this code) not bold.
    item = item_for(template, 'equal-angle')
    assert item is not None
    assert not (item.flags() & QtCore.Qt.ItemIsEnabled)
    assert not item.font().bold()
    # Every other row can be activated.
    disabled = [e.command for e in CATALOG
                if not (item_for(template, e.command).flags()
                        & QtCore.Qt.ItemIsEnabled)]
    assert disabled == ['equal-angle']


def test_palette_launches_commands_the_code_does_not_use(window, template,
                                                         monkeypatch):
    """The palette is also a launcher: an unused command can be added."""
    assert not item_for(template, 'midpoint').font().bold()
    calls = []
    monkeypatch.setattr(
        window, '_prompt_symbol_dialog',
        lambda sym, **kw: calls.append((sym.name, kw)))
    template.commands.itemActivated.emit(item_for(template, 'midpoint'))
    assert [c[0] for c in calls] == ['geo-midpoint']   # once, no doubles
    insert = calls[0][1]['insert']
    document_before = window.editor.toPlainText()
    insert('*midpoint(A ; B ; M)')        # what the dialog would build
    # The document stays untouched; the line lands in the code area …
    assert window.editor.toPlainText() == document_before
    text = template.code.toPlainText()
    assert '    *midpoint(A ; B ; M)' in text
    assert text.endswith(')')
    # … and the palette re-pins it in first-use order, bold: the five
    # example commands, midpoint, then the unused ones in catalog order.
    rows = palette_commands(template)
    used = ['point', 'distance', 'perp', 'triangle', 'right-angle',
            'midpoint']
    assert rows[:len(used)] == used
    assert rows[len(used):] == [e.command for e in CATALOG
                                if e.command not in used]
    assert item_for(template, 'midpoint').font().bold()


def test_all_cards_emit_their_own_template_id_once(window, gallery):
    """Every card carries its own id — and only ever its own."""
    seen = []
    gallery.templateRequested.connect(seen.append)
    for entry in CATALOG:
        gallery.card_for(entry.id).example_btn.click()
        assert seen[-1] == entry.id
        assert window._draw_template.entry == entry
    assert len(seen) == len(CATALOG)     # exactly one emission each


def test_opening_gallery_twice_connects_template_signal_once(window):
    window._on_symbol_activated('draw-gallery')
    first = window._draw_gallery
    window._on_symbol_activated('draw-gallery')   # re-raise, no new dlg
    assert window._draw_gallery is first
    seen = []
    first.templateRequested.connect(seen.append)
    first.card_for('point').example_btn.click()
    assert len(seen) == 1
    assert seen == ['point']


def test_palette_greys_out_commands_without_dialog(window, gallery):
    gallery.card_for('equal-angle').example_btn.click()
    dlg = window._draw_template
    item = item_for(dlg, 'equal-angle')
    assert item is not None
    assert not (item.flags() & QtCore.Qt.ItemIsEnabled)
    # Even a forced activation emits nothing (no geo-* dialog exists).
    picked = []
    dlg.commandRequested.connect(picked.append)
    dlg.commands.itemActivated.emit(item)
    assert picked == []


def test_palette_pick_runs_dialog_into_code_area(window, template,
                                                 monkeypatch, qapp):
    calls = []
    monkeypatch.setattr(
        window, '_prompt_symbol_dialog',
        lambda sym, **kw: calls.append((sym.name, kw)))
    template.commands.itemActivated.emit(item_for(template, 'perp'))
    assert [c[0] for c in calls] == ['geo-perp']       # once, no doubles
    insert = calls[0][1]['insert']
    # The dialog's result is routed to the code area, not the document.
    assert insert == window._insert_into_template_code
    document_before = window.editor.toPlainText()
    insert('*perp(A ; B ; A ; C)')       # what build_source would give
    assert window.editor.toPlainText() == document_before
    text = template.code.toPlainText()
    # Spliced before the closing ')' of the shown block, indented.
    assert '    *perp(A ; B ; A ; C)' in text
    assert text.endswith(')')
    # Focus follows the edit into the code area (window-scoped check:
    # offscreen never activates windows, so hasFocus() lies there).
    qapp.processEvents()
    assert template.focusWidget() is template.code


def test_insert_code_edge_targets(template):
    """Empty area, single-line block and empty-text paths of insert_code."""
    # Empty code area: the command becomes its own block.
    template.code.setPlainText('')
    template.insert_code('*midpoint(A ; B ; M)')
    text = template.code.toPlainText()
    assert text.startswith('*draw(')
    assert '*midpoint(A ; B ; M)' in text
    assert text.endswith(')')
    # Single-line block: expanded to multi-line so the line fits.
    template.code.setPlainText('*draw(*line(A ; B))')
    cursor = template.code.textCursor()
    cursor.setPosition(6)
    template.code.setTextCursor(cursor)
    template.insert_code('*point(A = 0, 0)')
    text = template.code.toPlainText()
    assert text.startswith('*draw(\n')
    assert '    *line(A ; B)' in text
    assert '    *point(A = 0, 0)' in text
    assert text.endswith(')')
    # Empty source: ValueError branch — code area unchanged.
    before = template.code.toPlainText()
    template.insert_code('')
    assert template.code.toPlainText() == before
    # Caret lands right after the spliced command, not somewhere else.
    cursor = template.code.textCursor()
    assert not cursor.hasSelection()
    text = template.code.toPlainText()
    assert text[cursor.position() - 1] == ')'
    assert '    *point(A = 0, 0)' in text[:cursor.position()]


def test_insert_code_replaces_active_selection(template):
    """A selected range in the code area is replaced, as in the document."""
    template.code.setPlainText(
        '*draw(\n    *REMOVEME(A)\n    *line(A ; B)\n)')
    text = template.code.toPlainText()
    start = text.index('*REMOVEME(A)')
    cursor = template.code.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(start + len('*REMOVEME(A)'),
                        QtGui.QTextCursor.KeepAnchor)
    template.code.setTextCursor(cursor)
    template.insert_code('*point(A = 0, 0)')
    text = template.code.toPlainText()
    assert 'REMOVEME' not in text
    assert '    *point(A = 0, 0)' in text
    assert '    *line(A ; B)' in text
    assert text.endswith(')')


def test_search_enter_opens_parameter_dialog(window, template, monkeypatch):
    calls = []
    monkeypatch.setattr(
        window, '_prompt_symbol_dialog',
        lambda sym, **kw: calls.append(sym.name))
    template.search.setText('right')
    template.search.returnPressed.emit()
    assert calls == ['geo-right-angle']


def test_real_enter_in_filter_runs_dialog_but_never_inserts(
        window, template, monkeypatch, qapp):
    """A real Enter key must run ONLY the pick (regression for the
    default-button bug: the same key also pressed Insert, committing
    the whole code area and closing the window in one keypress).
    """
    calls, inserted = [], []
    monkeypatch.setattr(
        window, '_prompt_symbol_dialog',
        lambda sym, **kw: calls.append(sym.name))
    template.insertRequested.connect(inserted.append)
    template.search.setText('right')
    QtTest.QTest.keyClick(template.search, QtCore.Qt.Key_Return)
    qapp.processEvents()
    assert calls == ['geo-right-angle']   # the pick ran …
    assert inserted == []                 # …and ONLY the pick
    assert template.isVisible()           # window stays open


def test_real_enter_on_palette_row_runs_dialog_but_never_inserts(
        window, template, monkeypatch, qapp):
    """Same guarantee when Enter is pressed on the list itself."""
    calls, inserted = [], []
    monkeypatch.setattr(
        window, '_prompt_symbol_dialog',
        lambda sym, **kw: calls.append(sym.name))
    template.insertRequested.connect(inserted.append)
    template.commands.setCurrentRow(0)    # point (pinned first)
    QtTest.QTest.keyClick(template.commands, QtCore.Qt.Key_Return)
    qapp.processEvents()
    assert calls == ['geo-point']
    assert inserted == []
    assert template.isVisible()


def test_enter_edges_are_noops(window, gallery, monkeypatch, qapp):
    """Enter with no match — or on the disabled row — does nothing."""
    calls, inserted = [], []
    monkeypatch.setattr(
        window, '_prompt_symbol_dialog',
        lambda sym, **kw: calls.append(sym.name))
    gallery.card_for('perp').example_btn.click()
    dlg = window._draw_template
    dlg.insertRequested.connect(inserted.append)
    # No match: currentRow is the disabled placeholder row.
    dlg.search.setText('zzzz-no-match')
    QtTest.QTest.keyClick(dlg.search, QtCore.Qt.Key_Return)
    qapp.processEvents()
    # Disabled row: equal-angle has no geo-* parameter dialog.
    dlg.search.clear()
    row = next(i for i in range(dlg.commands.count())
               if dlg.commands.item(i).data(QtCore.Qt.UserRole)
               == 'equal-angle')
    dlg.commands.setCurrentRow(row)
    QtTest.QTest.keyClick(dlg.commands, QtCore.Qt.Key_Return)
    qapp.processEvents()
    assert calls == []
    assert inserted == []
    assert dlg.isVisible()


def test_typing_in_filter_reaches_the_line_edit_and_narrows(
        template, qapp):
    """Real letter keys must pass through eventFilter to the widget
    (only Enter is consumed) — typing filters the palette live."""
    assert len(palette_commands(template)) == len(CATALOG)
    QtTest.QTest.keyClicks(template.search, 'on-c')
    qapp.processEvents()
    assert template.search.text() == 'on-c'
    expected = [e.command for e in CATALOG
                if fuzzy_score('on-c', f'{e.title} {e.command}') is not None]
    assert palette_commands(template) == expected
    assert 'on-circle' in expected


def test_focus_returns_to_code_area_after_cancelled_dialog(window, template,
                                                           monkeypatch, qapp):
    """After the geo-* dialog (even cancelled), focus goes back to the
    code area — not the palette list it was launched from.
    """
    calls = []
    monkeypatch.setattr(
        window, '_prompt_symbol_dialog',
        lambda sym, **kw: calls.append(sym.name))     # user cancels
    template.commands.setFocus()                      # launch from list
    qapp.processEvents()
    assert template.focusWidget() is template.commands
    window._on_template_command('geo-perp')           # dialog → cancel
    qapp.processEvents()
    assert calls == ['geo-perp']
    assert template.isVisible()
    assert template.focusWidget() is template.code


# ----------------------------------------------------------------------
# Insert / Cancel
# ----------------------------------------------------------------------

def test_insert_commits_edited_code_as_one_undo_and_closes(window, template):
    window.editor.setPlainText('Hello\n')
    cursor = window.editor.textCursor()
    cursor.setPosition(0)
    window.editor.setTextCursor(cursor)
    edited = '*draw(\n    *line(A ; B)\n)\n'
    template.code.setPlainText(edited)
    emitted = []
    template.insertRequested.connect(emitted.append)
    template.insert_btn.click()
    assert emitted == [edited]           # exactly the shown code
    assert not template.isVisible()      # closes after inserting
    text = window.editor.toPlainText()
    assert text.startswith('*draw(')
    assert '    *line(A ; B)' in text
    assert text.endswith('Hello\n')
    # ONE undo restores the document exactly.
    window.editor.undo()
    assert window.editor.toPlainText() == 'Hello\n'


def test_empty_code_disables_insert(template):
    template.code.setPlainText('')
    assert not template.insert_btn.isEnabled()
    template.code.setPlainText('*draw(\n)')
    assert template.insert_btn.isEnabled()


def test_invalid_code_disables_insert_and_never_closes(window, template):
    """Insert must not commit code the inserter would reject — and
    must NOT silently discard the user's edits by closing either.
    """
    window.editor.setPlainText('Hello\n')
    emitted = []
    template.insertRequested.connect(emitted.append)
    template.code.setPlainText('*draw(')        # unterminated block
    assert not template.insert_btn.isEnabled()
    template._emit_insert()                     # forced, as by a key
    assert emitted == []
    assert template.isVisible()                 # edits survive
    assert window.editor.toPlainText() == 'Hello\n'
    template.code.setPlainText('*draw(\n    *point(A = 0, 0)\n)')
    assert template.insert_btn.isEnabled()      # valid again


def test_cancel_closes_without_inserting(window, template):
    window.editor.setPlainText('Hello\n')
    emitted = []
    template.insertRequested.connect(emitted.append)
    template.cancel_btn.click()
    assert not template.isVisible()
    assert emitted == []
    assert window.editor.toPlainText() == 'Hello\n'


def test_escape_closes_without_inserting(window, template, qapp):
    window.editor.setPlainText('Hello\n')
    emitted = []
    template.insertRequested.connect(emitted.append)
    QtTest.QTest.keyClick(template, QtCore.Qt.Key_Escape)
    qapp.processEvents()
    assert not template.isVisible()
    assert emitted == []
    assert window.editor.toPlainText() == 'Hello\n'


# ----------------------------------------------------------------------
# Accessibility surface
# ----------------------------------------------------------------------

def test_accessible_names_and_buddies(template):
    assert template.search.accessibleName() == 'Filter template commands'
    # The list shows ALL commands — not only the used ones.
    assert template.commands.accessibleName() == 'Geometry commands'
    assert template.code.accessibleName() == 'Code to insert'
    assert template.insert_btn.accessibleName() == \
        'Insert the code into the document'
    assert template.cancel_btn.accessibleName() == \
        'Close without inserting'
    assert 'Preview of *perp' in template.preview.accessibleName()
    label = template.findChild(
        QtWidgets.QLabel, 'draw-template-palette-label')
    assert label.toolTip()                      # guidance tooltip
    code_label = template.findChild(
        QtWidgets.QLabel, 'draw-template-code-label')
    # Buddies give the labels Alt-key focus routing.
    assert label.buddy() is template.search
    assert code_label.buddy() is template.code
    # Item tooltips: what each row will do (or why it cannot).
    assert 'parameter dialog' in item_for(template, 'perp').toolTip()
    assert item_for(template, 'equal-angle').toolTip() == \
        'No parameter dialog for *equal-angle yet'
