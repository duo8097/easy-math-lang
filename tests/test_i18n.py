"""Translation catalog, language persistence, friendly errors, examples."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from editor import friendly_errors, i18n  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_locale():
    i18n.set_locale('en')
    yield
    i18n.set_locale('en')


def _catalog(locale):
    path = os.path.join(i18n.locales_dir(), f'{locale}.json')
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def test_catalogs_have_the_same_keys():
    en = _catalog('en')
    vi = _catalog('vi')
    assert set(en) == set(vi), (
        f'en-only: {sorted(set(en) - set(vi))[:5]}; '
        f'vi-only: {sorted(set(vi) - set(en))[:5]}')
    # No empty translations, and placeholders are preserved.
    for locale, catalog in (('en', en), ('vi', vi)):
        for key, value in catalog.items():
            assert isinstance(value, str) and value.strip(), (locale, key)
    import re
    for key in en:
        en_ph = set(re.findall(r'\{(\w+)\}', en[key]))
        vi_ph = set(re.findall(r'\{(\w+)\}', vi[key]))
        assert en_ph == vi_ph, (key, en_ph, vi_ph)


def test_lookup_and_fallback_to_english():
    translator = i18n.Translator('vi')
    assert translator.tr('menu.file') == _catalog('vi')['menu.file']
    # A key missing from the Vietnamese catalog falls back to English.
    assert translator.tr('no.such.key') == 'no.such.key'
    # English translator is the fallback source itself.
    assert i18n.Translator('en').tr('menu.file') == '&File'
    # Unknown locales degrade to English.
    assert i18n.Translator('fr').locale == 'en'
    assert i18n.Translator('fr').tr('menu.file') == '&File'


def test_locale_detection():
    assert i18n.normalize_locale('vi_VN.UTF-8') == 'vi'
    assert i18n.normalize_locale('vi-VN') == 'vi'
    assert i18n.normalize_locale('en-US') == 'en'
    assert i18n.normalize_locale('de_DE') is None
    assert i18n.detect_system_locale('vi_VN') == 'vi'
    assert i18n.detect_system_locale('de_DE') == 'en'
    assert i18n.resolve_language('vi', 'en_US') == 'vi'
    assert i18n.resolve_language('system', 'vi_VN') == 'vi'
    assert i18n.resolve_language(None, 'en_US') == 'en'


def test_language_persistence_roundtrip(tmp_path, qapp):
    from PySide6 import QtCore
    settings = QtCore.QSettings(str(tmp_path / 'settings.ini'),
                               QtCore.QSettings.IniFormat)
    i18n.save_setting_language(settings, 'vi')
    assert settings.value(i18n.LANGUAGE_SETTING) == 'vi'
    assert i18n.load_setting_language(settings) == 'vi'
    assert i18n.get_locale() == 'vi'
    i18n.save_setting_language(settings, 'en')
    assert i18n.load_setting_language(settings) == 'en'


def test_main_window_language_switch_preserves_document(qapp):
    from PySide6 import QtGui
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win.editor.setPlainText('<a> = 1\n')
        win.editor.moveCursor(QtGui.QTextCursor.End)
        cursor_before = win.editor.textCursor().position()
        win._apply_language('vi')
        assert i18n.get_locale() == 'vi'
        assert win.editor.toPlainText() == '<a> = 1\n'
        assert win.editor.textCursor().position() == cursor_before
        assert _catalog('vi')['menu.file'] in [
            a.text() for a in win.menuBar().actions()]
        assert all(a.text() for a in win.menuBar().actions())
        win._apply_language('en')
        assert '&File' in [a.text() for a in win.menuBar().actions()]
        # The choice is persisted for the next startup.
        assert win._settings.value(i18n.LANGUAGE_SETTING) == 'en'
    finally:
        win.close()


def test_symbol_bar_tooltips_have_examples(qapp):
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        for name in ('frac', 'vec', 'geo-line', 'le'):
            button = win._symbol_bar.button_for(name)
            assert button is not None, name
            tooltip = button.toolTip()
            assert tooltip, name
            assert 'Example:' in tooltip, (name, tooltip)
    finally:
        win.close()


def test_examples_compile(tmp_path, monkeypatch, capsys):
    """Every Help > Examples sample is ready-to-run (compiles to Typst)."""
    from compiler import compile_ezmath
    from compiler import pipeline as _pipeline
    from editor.help_dialogs import EXAMPLES
    stub = type('_TypstStub', (),
                {'compile': staticmethod(lambda *a, **k: None)})()
    monkeypatch.setattr(_pipeline, 'typst', stub)
    for entry_id, _name_key, source in EXAMPLES:
        src = tmp_path / f'{entry_id}.ezmath'
        src.write_text(source, encoding='utf-8')
        compile_ezmath(str(src), str(tmp_path / f'{entry_id}.pdf'))
        typ = (tmp_path / f'{entry_id}.typ').read_text(encoding='utf-8')
        assert typ.strip(), entry_id
        assert '[Error]' not in capsys.readouterr().err, entry_id


def test_editor_build_bundles_locales(monkeypatch):
    """PyInstaller bundles the translation catalogs as data files."""
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
    assert 'editor.help_dialogs' in cmd
    add_data = [cmd[i + 1] for i, flag in enumerate(cmd)
                if flag == '--add-data']
    assert any('locales' in item and 'en.json' not in item
               for item in add_data)
    locales = [item for item in add_data if 'editor/locales' in item
               or item.endswith('locales')]
    assert locales, add_data
    source = locales[0].split(';' if os.name == 'nt' else ':', 1)[0]
    assert os.path.isdir(source)
    assert {'en.json', 'vi.json'} <= set(os.listdir(source))


def test_examples_are_present_and_runnable_text():
    from editor.help_dialogs import EXAMPLES, example_source
    ids = [entry[0] for entry in EXAMPLES]
    assert ids == ['basic-math', 'fraction-equation', 'vector', 'simple-draw']
    assert 'calc(' in example_source('basic-math')
    assert '*frac(' in example_source('fraction-equation')
    assert '*vec(' in example_source('vector')
    assert example_source('simple-draw').startswith('*draw(')
    assert example_source('nope') == ''


def test_examples_insert_into_editor(qapp):
    from editor.main_window import MainWindow
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win._insert_example('basic-math')
        assert 'calc(' in win.editor.toPlainText()
        assert win._welcome_panel.isHidden()
    finally:
        win.close()


def test_welcome_and_shortcuts_dialogs(qapp):
    from PySide6 import QtWidgets
    from editor.help_dialogs import ShortcutsDialog, WelcomePanel
    panel = WelcomePanel()
    assert panel.title.text()
    assert panel.example_btn.text()
    dialog = ShortcutsDialog()
    table = dialog.findChild(QtWidgets.QTableWidget)
    assert table is not None
    texts = [table.item(r, 0).text() for r in range(table.rowCount())]
    assert 'Ctrl+B' in texts
    assert 'Ctrl+Shift+P' in texts


@pytest.mark.parametrize('raw,key', [
    ('Undefined variable <oops>', 'friendly.undefined_variable'),
    ('Unknown command *frcc(...) — treated as plain text',
     'friendly.unknown_command'),
    ('*line(...) is only valid inside *draw(...) — treated as plain text',
     'friendly.geometry_outside_draw'),
    ('Unclosed parenthesis in calc(...)', 'friendly.unclosed_paren'),
    ('Unclosed *frac(... — missing closing parenthesis',
     'friendly.unclosed_paren'),
    ('Unclosed math delimiter \\ ... \\ — missing closing \\.',
     'friendly.unclosed_math'),
    ("Unclosed block '(' — content may be silently consumed",
     'friendly.unclosed_block'),
    ('Empty math expression \\ \\.', 'friendly.empty_math'),
    ('[Calc Error] bad', 'friendly.calc_error'),
    ('*table(...) cannot be used inside math \\ ... \\',
     'friendly.table_in_math'),
    ('*table(...) is empty', 'friendly.table_shape'),
    ('*table(...) rows have different lengths [2, 3] — short rows are padded',
     'friendly.table_shape'),
    ('something entirely new', 'friendly.generic'),
])
def test_friendly_error_mapping(raw, key):
    assert friendly_errors.explain(raw).key == key


def test_friendly_did_you_mean_hints():
    unknown = friendly_errors.explain(
        'Unknown command *frcc(...) — treated as plain text')
    assert unknown.key == 'friendly.unknown_command'
    assert friendly_errors.hint_params(unknown) == {'command': 'frac'}
    undefined = friendly_errors.explain(
        "Undefined variable <oops>. Did you mean 'tops'?")
    assert friendly_errors.hint_params(undefined) == {'name': 'tops'}
    assert friendly_errors.hint_params(
        friendly_errors.explain('Undefined variable <x>')) is None


def test_friendly_display_keeps_raw_message_below():
    raw = 'Unknown command *frcc(...) — treated as plain text'
    shown = friendly_errors.format_for_display(raw)
    assert raw in shown
    assert shown.index(raw) > 0  # friendly text first, raw below it
    i18n.set_locale('vi')
    shown_vi = friendly_errors.format_for_display(raw)
    assert raw in shown_vi
    assert _catalog('vi')['friendly.unknown_command.title'] in shown_vi


def test_problems_panel_shows_friendly_text(qapp):
    from editor.problems_panel import ProblemsPanel
    panel = ProblemsPanel()
    panel.set_diagnostics([{
        'line': 0, 'start': 0, 'end': 1, 'severity': 'error',
        'message': 'Unknown command *frcc(...) — treated as plain text'}])
    item = panel._list.item(0)
    assert '❌ 1:1' in item.text()
    assert 'Unknown command *frcc' in item.text()  # raw kept
    assert '*frac' in item.text()  # did-you-mean hint present


def test_audit_script_reports_no_bypass():
    """Static audit (scripts/audit_i18n.py) must stay clean."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        'audit_i18n',
        Path(__file__).resolve().parents[1] / 'scripts' / 'audit_i18n.py')
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    violations = audit.find_violations() + audit.registry_coverage()
    remaining = [v for v in violations
                 if not audit.is_allowlisted(v, audit.load_allowlist())]
    assert remaining == [], remaining[:10]


def test_registry_and_draw_catalog_have_translations():
    """Every registry/draw/shortcut string has en+vi catalog entries."""
    from editor.draw_catalog import CATALOG
    from editor.help_dialogs import SHORTCUTS
    from editor.symbol_registry import list_symbols
    en, vi = _catalog('en'), _catalog('vi')
    for symbol in list_symbols():
        if symbol.description:
            key = f'symbol.{symbol.name}.description'
            assert key in en and key in vi, key
            assert vi[key] != en[key], key
    for entry in CATALOG:
        for suffix in ('title', 'description'):
            key = f'draw.{entry.id}.{suffix}'
            assert key in en and key in vi, key
            assert vi[key] != en[key], key
    for _shortcut, action_key in SHORTCUTS:
        assert action_key in en and action_key in vi, action_key


def test_vi_ui_has_no_english_chrome(qapp):
    """Walk the vi UI offscreen; chrome texts must not be English prose."""
    from PySide6 import QtWidgets
    from editor.main_window import MainWindow
    from editor.symbol_registry import get_symbol
    from editor.symbol_dialog import SymbolDialog
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    try:
        win.show()
        win._apply_language('vi')
        win._open_draw_gallery()
        gallery = win._draw_gallery
        assert gallery is not None
        # Gallery card titles/descriptions follow the locale.
        card = gallery.card_for('triangle')
        assert card is not None
        assert card._title_label.text() == _catalog('vi')['draw.triangle.title']
        assert card._desc_label.text() == _catalog('vi')['draw.triangle.description']
        # Symbol bar tooltip is translated but keeps the syntax.
        tooltip = win._symbol_bar.button_for('frac').toolTip()
        assert '*frac(2 ; 3)' in tooltip
        assert _catalog('vi')['symbol.tooltip_opens'] in tooltip
        # Symbol dialog info + field labels are translated.
        dialog = SymbolDialog(get_symbol('frac'), win)
        assert dialog.findChild(QtWidgets.QLabel, 'symbol-info').text()
        # Outline kinds: set one symbol and check the kind display.
        win.outline.set_symbols([{'name': 'a', 'kind': 'Variable',
                                  'line': 0, 'start': 0}])
        assert _catalog('vi')['kind.Variable'] in win.outline._list.item(0).text()
        win.outline.clear()
    finally:
        try:
            win._apply_language('en')
        finally:
            i18n.set_locale('en')
            win.close()


def test_qt_generated_texts_are_translated(qapp):
    """Qt standard buttons, file dialog labels and input buttons use vi."""
    from PySide6 import QtCore, QtWidgets
    from editor import qt_text
    i18n.set_locale('vi')
    box = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
    qt_text.translate_button_box(box)
    assert box.button(QtWidgets.QDialogButtonBox.Cancel).text() == \
        _catalog('vi')['btn.cancel']
    dialog = QtWidgets.QFileDialog()
    qt_text.translate_file_dialog(dialog)
    assert dialog.labelText(QtWidgets.QFileDialog.LookIn) == \
        _catalog('vi')['filedialog.lookin']
    input_dialog = QtWidgets.QInputDialog()
    qt_text.translate_input_dialog(input_dialog)
    # Context menu actions are built from the catalog at show time.
    editor = QtWidgets.QPlainTextEdit()
    qt_text.install_text_context_menu(editor)
    assert editor.contextMenuPolicy() == QtCore.Qt.CustomContextMenu


def test_about_and_shortcuts_are_translated(qapp):
    from PySide6 import QtWidgets
    from editor.help_dialogs import AboutDialog, ShortcutsDialog
    i18n.set_locale('vi')
    about = AboutDialog(version='6.0.0')
    assert about.windowTitle() == _catalog('vi')['about.title']
    shortcuts = ShortcutsDialog()
    header = shortcuts.findChild(QtWidgets.QTableWidget).horizontalHeaderItem(0)
    assert header.text() == _catalog('vi')['shortcuts.header_shortcut']
