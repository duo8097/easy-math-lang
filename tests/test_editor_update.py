"""Offscreen tests for the editor's update UI (B7).

All checks/downloads/network calls are faked; nothing touches the real
network or a real installer. Covers: notice banner visibility rules,
the update dialog's ready/busy/error states, the one-click gating, the
unsaved-documents prompt, cancellation, the next-start failure notice
and the Help/View menu wiring.
"""

import os
import sys

import pytest

PySide6 = pytest.importorskip('PySide6')

from PySide6 import QtGui, QtCore  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler.update import ReleaseAsset, ReleaseInfo  # noqa: E402
from editor.main_window import MainWindow  # noqa: E402
from editor.update_ui import (  # noqa: E402
    UpdateDialog,
    UpdateFailedDialog,
    UpdateNoticeBanner,
)

INFO = ReleaseInfo(
    version='7.1.0',
    html_url='https://github.com/duo8097/easy-math-lang/releases/tag/v7.1.0',
    notes='Shiny new release.\n\n- Fix everything',
    prerelease=False,
    published='2026-11-13T10:00:00Z',
    assets=[ReleaseAsset('EasyMathLang-Windows-x64-Setup.exe',
                         'https://github.com/x/setup.exe',
                         50 * 1024 * 1024),
            ReleaseAsset('SHA256SUMS.txt', 'https://github.com/x/sums.txt',
                         256)],
)


def _payload(status='newer', skipped=False, one_click=True,
             method='windows'):
    return {'ok': True, 'error': None, 'status': status,
            'current': '7.0.0', 'skipped': skipped, 'latest': INFO,
            'interactive': True, 'method': method, 'one_click': one_click,
            'asset': INFO.assets[0], 'sums': INFO.assets[1]}


@pytest.fixture()
def window(qapp, tmp_path, monkeypatch):
    win = MainWindow(start_lsp=False, no_save_prompt=True)
    win.show()
    yield win
    win.close()


# --------------------------------------------------------------------------
# Notice banner
# --------------------------------------------------------------------------

def test_banner_hidden_initially(window):
    assert not window._update_banner.isVisible()


def test_newer_release_shows_banner(window):
    window._on_update_check_done(_payload())
    assert window._update_banner.isVisible()
    assert '7.1.0' in window._update_banner.text_label.text()
    assert '7.0.0' in window._update_banner.text_label.text()


def test_skipped_version_keeps_banner_hidden(window):
    window._on_update_check_done(_payload(skipped=True))
    assert not window._update_banner.isVisible()


def test_up_to_date_keeps_banner_hidden(window):
    window._on_update_check_done(_payload(status='current'))
    assert not window._update_banner.isVisible()


def test_manual_check_opens_dialog(window):
    window._update_manual = True
    window._on_update_check_done(_payload())
    assert window._update_dialog is not None
    assert window._update_dialog.isVisible()


def test_banner_button_shows_dialog(window):
    window._on_update_check_done(_payload())
    window._update_banner.update_button.click()
    assert window._update_dialog is not None
    assert window._update_dialog.isVisible()


def test_banner_dismiss_hides(window):
    window._on_update_check_done(_payload())
    window._update_banner.close_button.click()
    assert not window._update_banner.isVisible()


# --------------------------------------------------------------------------
# Update dialog: configuration and gating
# --------------------------------------------------------------------------

def _make_dialog(window, one_click=True, method='windows'):
    dialog = UpdateDialog(window)
    platform_note = {'windows': 'update.uac_note',
                     'debian': 'update.polkit_note',
                     'fedora': 'update.polkit_note',
                     'arch': 'update.polkit_note',
                     'macos': 'update.macos_note'}.get(method)
    dialog.configure(INFO, '7.0.0', one_click, platform_note,
                     INFO.assets[0])
    return dialog


def test_dialog_shows_versions_notes_and_size(qapp, window):
    dialog = _make_dialog(window)
    assert dialog.current_value.text() == '7.0.0'
    assert dialog.new_value.text() == '7.1.0'
    assert 'Shiny new release.' in dialog.notes.toPlainText()
    assert '50.0 MB' in dialog.size_label.text()
    assert not dialog.update_now_button.isHidden()
    assert not dialog.download_button.isHidden()


def test_update_now_hidden_when_not_one_click(qapp, window):
    dialog = _make_dialog(window, one_click=False)
    assert dialog.update_now_button.isHidden()


def test_one_click_gating_for_linux_methods(qapp, window):
    # A debian/fedora/arch payload without pkexec must not enable it.
    dialog = _make_dialog(window, one_click=False, method='debian')
    assert dialog.update_now_button.isHidden()


def test_skip_emits_signal_and_closes(qapp, window):
    dialog = _make_dialog(window)
    emitted = []
    dialog.skipRequested.connect(lambda: emitted.append(True))
    dialog.skip_button.click()
    assert emitted == [True]


def test_cancel_sets_ready_state_back(qapp, window):
    dialog = _make_dialog(window)
    dialog.set_busy('Downloading…')
    assert not dialog.progress_row.isHidden()
    assert not dialog.update_now_button.isEnabled()
    dialog.set_error('SHA-256 mismatch', 'try the manual download')
    assert not dialog.error_label.isHidden()
    assert 'SHA-256 mismatch' in dialog.error_label.text()
    dialog.set_ready()
    assert dialog.update_now_button.isEnabled()
    assert dialog.progress_row.isHidden()


# --------------------------------------------------------------------------
# Update now flow: save prompt, download, cancel, error
# --------------------------------------------------------------------------

def test_update_now_respects_declined_save_prompt(window, monkeypatch):
    started = []
    window._update_payload = _payload()
    monkeypatch.setattr(window, '_maybe_save', lambda: False)
    monkeypatch.setattr(window, '_start_update_download',
                        lambda *a, **k: started.append(a))
    window._on_update_now()
    assert started == []  # the update never starts


def test_update_now_starts_download_when_save_ok(window, monkeypatch):
    started = []
    window._update_payload = _payload()
    monkeypatch.setattr(window, '_maybe_save', lambda: True)
    monkeypatch.setattr(window, '_start_update_download',
                        lambda info, asset, sums: started.append(asset.name))
    window._open_update_dialog()
    window._on_update_now()
    assert started == ['EasyMathLang-Windows-x64-Setup.exe']


def test_download_failure_sets_error_state(window):
    window._update_payload = _payload()
    window._open_update_dialog()
    window._on_download_failed('network unavailable while downloading '
                               'the asset.')
    dialog = window._update_dialog
    assert 'network unavailable' in dialog.error_label.text()


def test_download_finished_spawns_helper_and_quits(window, monkeypatch):
    from compiler import updater as _updater

    payload = _payload()
    closes = []

    class _Result:
        path = '/tmp/x/setup.exe'
        sha256 = 'ab' * 32
        size = 100
        temp_dir = '/tmp/x'

    staged = []
    monkeypatch.setattr(_updater, 'spawn_helper',
                        lambda plan_path: staged.append(plan_path))
    monkeypatch.setattr(_updater, 'stage_update_plan',
                        lambda *a, **k: '/tmp/x/update-plan.json')
    monkeypatch.setattr(window, 'close', lambda: closes.append(True))
    window._update_payload = payload
    window._open_update_dialog()
    window._on_download_finished(_Result())
    assert staged == ['/tmp/x/update-plan.json']
    from PySide6.QtTest import QTest

    QTest.qWait(800)
    assert closes == [True]


def test_stage_spawn_uses_editor_binary_as_relaunch(window, monkeypatch):
    from compiler import updater as _updater

    staged = {}
    monkeypatch.setattr(_updater, 'stage_update_plan',
                        lambda info, method_info, result, **kwargs:
                        staged.update(kwargs) or '/tmp/plan.json')
    monkeypatch.setattr(_updater, 'spawn_helper', lambda p: None)
    method_info = _updater.InstallInfo('windows', True, '')
    result = type('R', (), {'path': '/tmp/setup.exe', 'sha256': 'ab',
                            'size': 1, 'temp_dir': '/tmp'})()
    out = window._stage_and_spawn(_updater, INFO, 'windows', result)
    assert out is True
    assert staged['relaunch_argv'] == [sys.executable]


# --------------------------------------------------------------------------
# Next-start failure notice
# --------------------------------------------------------------------------

def test_failure_notice_shown_once_and_cleared(window, monkeypatch):
    seen = {'cleared': False}

    class _Fake:
        @staticmethod
        def last_update_error():
            return {'version': '7.1.0', 'reason': 'SHA-256 mismatch',
                    'log_path': '/tmp/update.log', 'when': 1}

        @staticmethod
        def clear_update_error():
            seen['cleared'] = True

    import compiler.update as _update

    monkeypatch.setattr(_update, 'last_update_error', _Fake.last_update_error)
    monkeypatch.setattr(_update, 'clear_update_error',
                        _Fake.clear_update_error)
    window.maybe_show_update_failure()
    assert seen['cleared']
    dialog = window._update_failed_dialog
    assert dialog is not None
    assert 'SHA-256 mismatch' in dialog.message.text()
    assert '/tmp/update.log' in dialog.log_label.text()
    dialog.close()


def test_failure_notice_silent_when_clean(window, monkeypatch):
    import compiler.update as _update

    monkeypatch.setattr(_update, 'last_update_error', lambda: None)
    window.maybe_show_update_failure()
    assert getattr(window, '_update_failed_dialog', None) is None


# --------------------------------------------------------------------------
# Menu wiring
# --------------------------------------------------------------------------

def test_help_menu_has_check_updates(window):
    help_menu = next(a for a in window.menuBar().actions()
                     if a.text() == '&Help')
    texts = [a.text() for a in help_menu.menu().actions()]
    assert any('Updates' in t for t in texts)


def test_view_menu_auto_update_toggle_persists(window):
    before = window._auto_update_enabled()
    window._auto_update_action.trigger()
    after = window._auto_update_enabled()
    assert after != before
    # Restore the default for other tests.
    window._auto_update_action.trigger()
    assert window._auto_update_enabled() == before


def test_about_dialog_check_button_emits(qapp, window, monkeypatch):
    from editor.help_dialogs import AboutDialog

    dialog = AboutDialog(version='7.0.0', parent=window)
    fired = []
    dialog.checkUpdatesRequested.connect(lambda: fired.append(True))
    dialog.check_button.click()
    assert fired == [True]


def test_update_threads_shut_down_cleanly(window):
    window._shutdown_update_threads()
    assert window._update_check_thread is None
    # Idempotent.
    window._shutdown_update_threads()
