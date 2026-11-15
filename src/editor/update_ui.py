"""Update check UI: notice banner, update dialog, next-start failure notice.

Presentational only, following the same pattern as the welcome panel:
the host window (MainWindow) owns the flow — it runs checks/downloads on
worker QThreads and wires the signals defined here. Nothing in this
module touches the network or the filesystem except through the slots
the host injects.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from . import i18n
from .icons import SIZE_DIALOG, apply_icon, icon


class UpdateNoticeBanner(QtWidgets.QFrame):
    """Non-modal, dismissible "update available" banner."""

    actionRequested = QtCore.Signal()
    dismissed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('updateBanner')
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 6, 6)
        layout.setSpacing(8)

        self.icon_label = QtWidgets.QLabel(self)
        self.icon_label.setObjectName('update-banner-icon')
        self.icon_label.setPixmap(
            icon('update', 20).pixmap(20, 20))
        layout.addWidget(self.icon_label)

        self.text_label = QtWidgets.QLabel(self)
        self.text_label.setObjectName('update-banner-text')
        self.text_label.setWordWrap(True)
        layout.addWidget(self.text_label, 1)

        self.update_button = QtWidgets.QPushButton(self)
        self.update_button.setObjectName('update-banner-button')
        apply_icon(self.update_button, 'update', SIZE_DIALOG)
        self.update_button.clicked.connect(self.actionRequested)
        layout.addWidget(self.update_button)

        self.close_button = QtWidgets.QToolButton(self)
        self.close_button.setObjectName('update-banner-close')
        self.close_button.setAutoRaise(True)
        apply_icon(self.close_button, 'close', SIZE_DIALOG)
        self.close_button.clicked.connect(self._dismiss)
        layout.addWidget(self.close_button)
        self._current = ''
        self._latest = ''
        self.retranslate_ui()

    def set_info(self, current, latest):
        self._current = current
        self._latest = latest
        self.retranslate_ui()

    def _dismiss(self):
        self.hide()
        self.dismissed.emit()

    def retranslate_ui(self):
        self.text_label.setText(
            i18n.tr('update.banner_text', latest=self._latest,
                    current=self._current))
        self.update_button.setText(i18n.tr('update.banner_update'))
        self.close_button.setToolTip(i18n.tr('update.banner_dismiss'))
        self.close_button.setAccessibleName(i18n.tr('update.banner_dismiss'))


class UpdateDialog(QtWidgets.QDialog):
    """Current vs new version, release notes and the install buttons."""

    updateNowRequested = QtCore.Signal()
    downloadRequested = QtCore.Signal()
    skipRequested = QtCore.Signal()
    cancelDownloadRequested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('updateDialog')
        self.setModal(True)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(2)
        self.current_label = QtWidgets.QLabel(self)
        self.current_label.setObjectName('update-current-label')
        self.current_value = QtWidgets.QLabel(self)
        self.current_value.setObjectName('update-current-value')
        self.new_label = QtWidgets.QLabel(self)
        self.new_label.setObjectName('update-new-label')
        self.new_value = QtWidgets.QLabel(self)
        self.new_value.setObjectName('update-new-value')
        bold = QtGui.QFont()
        bold.setBold(True)
        self.new_value.setFont(bold)
        self.published_value = QtWidgets.QLabel(self)
        self.published_value.setObjectName('update-published-value')
        grid.addWidget(self.current_label, 0, 0)
        grid.addWidget(self.current_value, 0, 1)
        grid.addWidget(self.new_label, 1, 0)
        grid.addWidget(self.new_value, 1, 1)
        grid.addWidget(self.published_value, 2, 0, 1, 2)
        layout.addLayout(grid)

        self.size_label = QtWidgets.QLabel(self)
        self.size_label.setObjectName('update-size-label')
        layout.addWidget(self.size_label)

        self.notes_label = QtWidgets.QLabel(self)
        self.notes_label.setObjectName('update-notes-label')
        layout.addWidget(self.notes_label)
        self.notes = QtWidgets.QTextBrowser(self)
        self.notes.setObjectName('update-notes')
        self.notes.setReadOnly(True)
        self.notes.setOpenExternalLinks(True)
        self.notes.setMinimumHeight(140)
        layout.addWidget(self.notes, 1)

        self.verification_note = QtWidgets.QLabel(self)
        self.verification_note.setObjectName('update-verification-note')
        self.verification_note.setWordWrap(True)
        layout.addWidget(self.verification_note)

        self.restart_note = QtWidgets.QLabel(self)
        self.restart_note.setObjectName('update-restart-note')
        self.restart_note.setWordWrap(True)
        layout.addWidget(self.restart_note)

        self.platform_note = QtWidgets.QLabel(self)
        self.platform_note.setObjectName('update-platform-note')
        self.platform_note.setWordWrap(True)
        layout.addWidget(self.platform_note)

        # Progress area (hidden until an update starts).
        self.progress_row = QtWidgets.QWidget(self)
        self.progress_row.setObjectName('update-progress-row')
        progress_layout = QtWidgets.QHBoxLayout(self.progress_row)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self.status_label = QtWidgets.QLabel(self.progress_row)
        self.status_label.setObjectName('update-status-label')
        progress_layout.addWidget(self.status_label, 1)
        self.progress = QtWidgets.QProgressBar(self.progress_row)
        self.progress.setObjectName('update-progress-bar')
        self.progress.setRange(0, 100)
        progress_layout.addWidget(self.progress)
        self.cancel_button = QtWidgets.QPushButton(self.progress_row)
        self.cancel_button.setObjectName('update-cancel-button')
        self.cancel_button.clicked.connect(self.cancelDownloadRequested)
        progress_layout.addWidget(self.cancel_button)
        self.progress_row.hide()
        layout.addWidget(self.progress_row)

        # Error area (hidden until an error occurs).
        self.error_label = QtWidgets.QLabel(self)
        self.error_label.setObjectName('update-error-label')
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        self.hint_label = QtWidgets.QLabel(self)
        self.hint_label.setObjectName('update-hint-label')
        self.hint_label.setWordWrap(True)
        self.hint_label.hide()
        layout.addWidget(self.hint_label)

        buttons = QtWidgets.QDialogButtonBox(self)
        self.update_now_button = QtWidgets.QPushButton(self)
        self.update_now_button.setObjectName('update-now-button')
        self.update_now_button.setDefault(True)
        apply_icon(self.update_now_button, 'update', SIZE_DIALOG)
        self.download_button = QtWidgets.QPushButton(self)
        self.download_button.setObjectName('update-download-button')
        apply_icon(self.download_button, 'open-external', SIZE_DIALOG)
        self.later_button = QtWidgets.QPushButton(self)
        self.later_button.setObjectName('update-later-button')
        self.skip_button = QtWidgets.QPushButton(self)
        self.skip_button.setObjectName('update-skip-button')
        self.update_now_button.clicked.connect(self.updateNowRequested)
        self.download_button.clicked.connect(self.downloadRequested)
        self.later_button.clicked.connect(self.reject)
        self.skip_button.clicked.connect(self._on_skip)
        buttons.addButton(self.update_now_button,
                          QtWidgets.QDialogButtonBox.AcceptRole)
        buttons.addButton(self.download_button,
                          QtWidgets.QDialogButtonBox.ActionRole)
        buttons.addButton(self.later_button,
                          QtWidgets.QDialogButtonBox.RejectRole)
        buttons.addButton(self.skip_button,
                          QtWidgets.QDialogButtonBox.DestructiveRole)
        layout.addWidget(buttons)

        self._state = 'ready'
        self._info = None
        self.resize(540, 480)
        self.setMinimumSize(420, 360)
        self.retranslate_ui()

    def configure(self, info, current_version, one_click, platform_note_key,
                  asset):
        """Fill the dialog with a concrete update."""
        self._info = info
        self.current_value.setText(current_version)
        self.new_value.setText(info.version)
        self.published_value.setText(
            i18n.tr('update.published', date=info.published) if info.published
            else '')
        self.published_value.setVisible(bool(info.published))
        self.size_label.setText(
            i18n.tr('update.size', size=_format_size(asset.size))
            if asset is not None else '')
        self.size_label.setVisible(asset is not None)
        self.notes.setPlainText(info.notes or '')
        self.platform_note.setText(i18n.tr(platform_note_key)
                                   if platform_note_key else '')
        self.platform_note.setVisible(bool(platform_note_key))
        self.update_now_button.setVisible(bool(one_click))
        self._state = 'ready'
        self.error_label.hide()
        self.hint_label.hide()
        self.progress_row.hide()
        self.update_now_button.setEnabled(True)
        self.download_button.setEnabled(True)
        self.skip_button.setEnabled(True)
        self.later_button.setEnabled(True)
        self.retranslate_ui()

    def set_busy(self, status_text):
        self._state = 'busy'
        self.status_label.setText(status_text)
        self.progress.setRange(0, 0)  # indeterminate until the first chunk
        self.progress_row.show()
        self.error_label.hide()
        self.hint_label.hide()
        self.update_now_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self.later_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

    def set_progress(self, downloaded, total):
        if total:
            self.progress.setRange(0, 100)
            self.progress.setValue(min(100, int(downloaded * 100 / total)))
        else:
            self.progress.setRange(0, 0)

    def set_verifying(self):
        self.status_label.setText(i18n.tr('update.verifying'))
        self.progress.setRange(0, 0)
        self.cancel_button.setEnabled(False)

    def set_installing(self):
        self.status_label.setText(i18n.tr('update.installing'))
        self.progress.setRange(0, 0)
        self.cancel_button.setEnabled(False)

    def set_ready(self):
        """Back to the ready state (e.g. after a cancelled download)."""
        self._state = 'ready'
        self.progress_row.hide()
        self.error_label.hide()
        self.hint_label.hide()
        self.update_now_button.setEnabled(True)
        self.download_button.setEnabled(True)
        self.skip_button.setEnabled(True)
        self.later_button.setEnabled(True)

    def set_error(self, reason, hint=None):
        self._state = 'error'
        self.status_label.setText(i18n.tr('update.failed'))
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.update_now_button.setEnabled(True)
        self.download_button.setEnabled(True)
        self.skip_button.setEnabled(True)
        self.later_button.setEnabled(True)
        self.cancel_button.setEnabled(True)
        self.error_label.setText(
            i18n.tr('update.error_detail', reason=reason))
        self.error_label.show()
        if hint:
            self.hint_label.setText(hint)
            self.hint_label.show()
        else:
            self.hint_label.hide()

    def _on_skip(self):
        self.skipRequested.emit()
        self.accept()

    def retranslate_ui(self):
        self.setWindowTitle(i18n.tr('update.dialog_title'))
        self.current_label.setText(i18n.tr('update.current_version'))
        self.new_label.setText(i18n.tr('update.new_version'))
        self.notes_label.setText(i18n.tr('update.notes_label'))
        self.verification_note.setText(i18n.tr('update.verification_note'))
        self.restart_note.setText(i18n.tr('update.restart_warning'))
        self.update_now_button.setText(i18n.tr('update.update_now'))
        self.download_button.setText(i18n.tr('update.download'))
        self.later_button.setText(i18n.tr('update.later'))
        self.skip_button.setText(i18n.tr('update.skip'))
        self.cancel_button.setText(i18n.tr('update.cancel'))


def _format_size(size):
    try:
        size = int(size)
    except (TypeError, ValueError):
        return '?'
    if size <= 0:
        return '?'
    if size < 1024 * 1024:
        return f'{size / 1024:.0f} KiB'
    return f'{size / (1024 * 1024):.1f} MB'


class UpdateFailedDialog(QtWidgets.QDialog):
    """Next-start notice: the previous self-update failed."""

    downloadRequested = QtCore.Signal()

    def __init__(self, reason, log_path, parent=None):
        super().__init__(parent)
        self.setObjectName('updateFailedDialog')
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self.message = QtWidgets.QLabel(
            i18n.tr('update.failed_once', reason=reason or '?'), self)
        self.message.setObjectName('update-failed-message')
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        self.log_label = QtWidgets.QLabel(
            i18n.tr('update.failed_log', path=log_path or '?'), self)
        self.log_label.setObjectName('update-failed-log')
        self.log_label.setWordWrap(True)
        self.log_label.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.log_label)

        self.download_button = QtWidgets.QPushButton(self)
        self.download_button.setObjectName('update-failed-download')
        apply_icon(self.download_button, 'update', SIZE_DIALOG)
        self.download_button.setText(i18n.tr('update.failed_download'))
        self.download_button.clicked.connect(self._on_download)
        layout.addWidget(self.download_button)

        close_button = QtWidgets.QPushButton(
            i18n.tr('update.failed_dismiss'), self)
        close_button.setObjectName('update-failed-close')
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

    def _on_download(self):
        self.downloadRequested.emit()


class UpdateCheckWorker(QtCore.QObject):
    """Background update check (never touches widgets)."""

    done = QtCore.Signal(object)

    @QtCore.Slot(bool)
    def check(self, interactive):
        from compiler import update as _update
        from compiler import updater as _updater

        try:
            result = _update.check_for_update(interactive=interactive)
        except Exception as exc:  # pragma: no cover - defensive
            self.done.emit({'ok': False, 'error': str(exc),
                            'interactive': bool(interactive)})
            return
        payload = {'ok': result.error is None,
                   'error': result.error,
                   'status': result.status,
                   'current': result.current,
                   'skipped': result.skipped,
                   'latest': result.latest,
                   'interactive': bool(interactive)}
        try:
            info = _updater.detect_install_method()
            payload['method'] = info.method
            payload['one_click'] = _updater.one_click_supported(info)
            assets = result.latest.assets if result.latest else []
            payload['asset'] = _updater.release_asset_for(info.method, assets)
            payload['sums'] = _updater.sha256sums_asset(assets)
        except Exception:
            payload['method'] = 'unknown'
            payload['one_click'] = False
            payload['asset'] = None
            payload['sums'] = None
        self.done.emit(payload)


class UpdateDownloadWorker(QtCore.QObject):
    """Background download+verify (never touches widgets)."""

    progress = QtCore.Signal(int, object)
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)
    cancelled = QtCore.Signal()

    def __init__(self, asset, sums_url, parent=None):
        super().__init__(parent)
        self._asset = asset
        self._sums_url = sums_url
        self._cancel = False

    @QtCore.Slot()
    def cancel(self):
        self._cancel = True

    @QtCore.Slot()
    def run(self):
        from compiler import updater as _updater

        def _progress(done, total):
            try:
                self.progress.emit(int(done), total)
            except Exception:
                pass

        try:
            result = _updater.download_asset(
                self._asset.download_url, dest_name=self._asset.name,
                expected_size=self._asset.size or None,
                sha256sums_url=self._sums_url,
                progress=_progress,
                should_cancel=lambda: self._cancel)
        except _updater.DownloadCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)
