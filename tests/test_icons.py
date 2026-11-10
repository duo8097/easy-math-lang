"""Editor icons: registry, theme recoloring, UI wiring, bundling."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_every_icon_name_resolves_to_a_file():
    from editor import icons
    assert icons.ICONS, 'registry must not be empty'
    for name in icons.ICONS:
        path = icons.icon_path(name)
        assert path is not None and os.path.isfile(path), name


def test_icon_pixmap_fills_the_requested_box(qapp):
    """The SVG must be scaled into the requested box, not drawn at its
    natural size and clipped.

    QSvgRenderer paints an SVG at its natural size (24x24) unless an
    explicit target rectangle is given. On a HiDPI screen the icon box
    is smaller than the natural size in device pixels, so the glyph ends
    up cropped into a corner of the pixmap. The icon registry therefore
    renders into an explicit rectangle — the glyph then sits centred in
    its box at any device pixel ratio.
    """
    from PySide6 import QtGui
    from editor import icons

    size = 64
    for name in ('file-new', 'compile', 'find'):
        for ratio in (1.0, 2.0):
            pixmap = icons._render_pixmap(name, size, '#333333', ratio=ratio)
            assert pixmap.width() == int(size * ratio)
            assert pixmap.height() == int(size * ratio)

            image = pixmap.toImage().convertToFormat(QtGui.QImage.Format_ARGB32)
            left, right, top, bottom = image.width(), -1, image.height(), -1
            for y in range(image.height()):
                for x in range(image.width()):
                    if image.pixelColor(x, y).alpha() > 8:
                        left = min(left, x)
                        right = max(right, x)
                        top = min(top, y)
                        bottom = max(bottom, y)
            assert right >= left, f'{name}: the icon drew nothing'
            # A scaled-into-the-box glyph is centred: the margins on
            # both sides are about the same. A clipped natural-size draw
            # hugs the top-left corner and touches the far edges.
            margin_x = abs(left - (image.width() - 1 - right))
            margin_y = abs(top - (image.height() - 1 - bottom))
            assert margin_x < image.width() * 0.15, (name, ratio, 'x')
            assert margin_y < image.height() * 0.15, (name, ratio, 'y')


def test_license_file_present():
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'editor',
                        'assets', 'icons', 'LICENSE')
    assert os.path.isfile(path)
    text = open(path, encoding='utf-8').read()
    assert 'Lucide' in text
    assert 'ISC' in text


def test_registry_loads_offscreen(qapp):
    from editor import icons
    for name in list(icons.ICONS)[:12]:
        result = icons.icon(name, 16)
        assert not result.isNull(), name
        from PySide6 import QtGui
        assert not result.pixmap(16, 16, QtGui.QIcon.Normal).isNull(), name
    # Missing icons never crash.
    assert icons.icon('does-not-exist').isNull()
    assert icons.icon('').isNull()


def test_theme_switch_changes_pixmap_color(qapp):
    from PySide6 import QtGui
    from editor import icons

    def _average_color(pixmap):
        image = pixmap.toImage()
        total = count = 0
        for x in range(image.width()):
            for y in range(image.height()):
                pixel = image.pixelColor(x, y)
                if pixel.alpha() > 0:
                    total += pixel.red() + pixel.green() + pixel.blue()
                    count += 1
        return total / max(1, count)

    icons.set_theme_dark(False)
    light = _average_color(
        icons.icon('file-save', 24).pixmap(24, 24, QtGui.QIcon.Normal))
    icons.set_theme_dark(True)
    dark = _average_color(
        icons.icon('file-save', 24).pixmap(24, 24, QtGui.QIcon.Normal))
    assert light != dark
    assert dark > light  # dark theme icons are lighter
    icons.set_theme_dark(False)


def test_icon_only_buttons_have_tooltip_and_accessible_name(qapp):
    from editor import i18n
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        for locale in ('en', 'vi'):
            i18n.set_locale(locale)
            win.retranslate_ui()
            for button in (win._find_bar._prev_button,
                           win._find_bar._next_button,
                           win._find_bar._close_button,
                           win._find_bar._match_case_button,
                           win._find_bar._whole_word_button,
                           win.preview.refresh_button,
                           win.preview.zoom_in,
                           win.preview.zoom_out):
                assert button.toolTip(), (locale, button)
                assert button.accessibleName(), (locale, button)
                assert not button.icon().isNull(), (locale, button)
    finally:
        i18n.set_locale('en')
        win._apply_language('en')
        win.close()


def test_toolbar_and_menu_icons(qapp):
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        toolbar = win._toolbar
        assert toolbar.toolButtonStyle() is not None
        actions = [a for a in toolbar.actions() if not a.isSeparator()]
        assert all(not a.icon().isNull() for a in actions)
        # Main actions keep their text alongside the icon.
        assert all(a.text() for a in actions)
        # A few menu actions carry icons too.
        file_menu = win.menuBar().actions()[0].menu()
        texts = {a.text(): a for a in file_menu.actions()}
        assert any(not a.icon().isNull() for a in texts.values())
    finally:
        win.close()


def test_problems_and_outline_icons(qapp):
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win.problems.set_diagnostics([
            {'line': 0, 'start': 0, 'end': 1, 'severity': 'error',
             'message': 'boom'},
            {'line': 1, 'start': 0, 'end': 1, 'severity': 'warning',
             'message': 'careful'},
        ])
        assert win.problems._list.count() == 2
        assert not win.problems._list.item(0).icon().isNull()
        assert not win.problems._list.item(1).icon().isNull()
        assert win.problems._count_label.text()
        win.outline.set_symbols([
            {'name': 'x', 'kind': 'Variable', 'line': 0, 'start': 0},
            {'name': 'f', 'kind': 'Function', 'line': 1, 'start': 0},
        ])
        assert not win.outline._list.item(0).icon().isNull()
        assert not win.outline._list.item(1).icon().isNull()
    finally:
        win.close()


def test_find_bar_replace_controls(qapp):
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win.editor.setPlainText('foo Foo foo\n')
        from PySide6 import QtGui
        win.editor.moveCursor(QtGui.QTextCursor.Start)
        win._find_bar._input.setText('foo')
        assert win._find_bar._count.text() == '1 of 3'
        # Match-case narrows to the lowercase occurrences only.
        win._find_bar._match_case_button.setChecked(True)
        assert win._find_bar._count.text() == '2 of 2'
        win._find_bar._match_case_button.setChecked(False)
        # Replace all, one undo step.
        win._find_bar._replace_input.setText('bar')
        win._on_replace_requested('bar', True)
        assert win.editor.toPlainText() == 'bar bar bar\n'
        win.editor.undo()
        assert win.editor.toPlainText() == 'foo Foo foo\n'
    finally:
        win.close()


def test_frozen_build_command_includes_icons(monkeypatch):
    """PyInstaller bundles editor/assets/icons like locales/assets."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        'binary_builder',
        Path(__file__).resolve().parents[1] / 'scripts/build_binaries.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    commands = []
    monkeypatch.setattr(builder, '_run',
                        lambda cmd, cache: commands.append(cmd))
    builder._build('easy-math-editor',
                   builder.ENTRIES['easy-math-editor'], False)
    cmd = commands[0]
    add_data = [cmd[i + 1] for i, flag in enumerate(cmd)
                if flag == '--add-data']
    assert any('editor/assets/icons' in item for item in add_data), add_data
    assert 'editor.icons' not in cmd  # data files only, no hidden import needed
