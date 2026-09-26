"""Live preview panel: PDF view with fallback message label."""

from PySide6 import QtCore, QtWidgets

try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView
    _PDF_AVAILABLE = True
except ImportError:  # Qt build without Pdf modules: text fallback only
    QPdfDocument = None
    QPdfView = None
    _PDF_AVAILABLE = False


def pdf_available():
    """True when Qt's PDF view modules imported successfully."""
    return _PDF_AVAILABLE


class PreviewPanel(QtWidgets.QWidget):
    """Right-hand preview: toolbar + PDF view (or error/empty message)."""

    refreshRequested = QtCore.Signal()
    autoToggled = QtCore.Signal(bool)
    openPdfRequested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(4)
        self.refresh_button = QtWidgets.QToolButton(self)
        self.refresh_button.setText('⟳')
        self.refresh_button.setToolTip('Refresh preview (F5)')
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        toolbar.addWidget(self.refresh_button)

        self.auto_check = QtWidgets.QCheckBox('Auto', self)
        self.auto_check.setChecked(True)
        self.auto_check.setToolTip('Refresh automatically while typing')
        self.auto_check.toggled.connect(self.autoToggled.emit)
        toolbar.addWidget(self.auto_check)

        self.zoom_out = QtWidgets.QToolButton(self)
        self.zoom_out.setText('−')
        self.zoom_out.setToolTip('Zoom out')
        toolbar.addWidget(self.zoom_out)

        self.zoom_in = QtWidgets.QToolButton(self)
        self.zoom_in.setText('+')
        self.zoom_in.setToolTip('Zoom in')
        toolbar.addWidget(self.zoom_in)

        self.fit_button = QtWidgets.QToolButton(self)
        self.fit_button.setText('Fit')
        self.fit_button.setToolTip('Fit page width')
        toolbar.addWidget(self.fit_button)

        self.open_button = QtWidgets.QToolButton(self)
        self.open_button.setText('Open…')
        self.open_button.setToolTip('Open preview PDF externally')
        self.open_button.clicked.connect(self.openPdfRequested.emit)
        self.open_button.setEnabled(False)
        toolbar.addWidget(self.open_button)

        toolbar.addStretch(1)
        self.status_label = QtWidgets.QLabel('Preview: idle', self)
        self.status_label.setToolTip('Live preview status')
        toolbar.addWidget(self.status_label)
        layout.addLayout(toolbar)

        self._document = None
        self._view = None
        self._pdf_path = None
        if _PDF_AVAILABLE:
            self._document = QPdfDocument(self)
            self._view = QPdfView(self)
            self._view.setDocument(self._document)
            try:
                # MultiPage shows the whole document as a continuous
                # scroll (SinglePage would only ever show one page).
                self._view.setPageMode(QPdfView.PageMode.MultiPage)
            except Exception:
                pass
            try:
                self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            except Exception:
                pass
            try:
                self._view.setPageSpacing(8)
            except Exception:
                pass
            self.zoom_in.clicked.connect(self._zoom_in)
            self.zoom_out.clicked.connect(self._zoom_out)
            self.fit_button.clicked.connect(self._zoom_fit)
            layout.addWidget(self._view, 1)
        else:
            self.zoom_in.setEnabled(False)
            self.zoom_out.setEnabled(False)
            self.fit_button.setEnabled(False)

        self._message = QtWidgets.QLabel('', self)
        self._message.setWordWrap(True)
        self._message.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self._message.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard)
        self._message.hide()
        layout.addWidget(self._message, 1)

        self.show_empty()

    # ------------------------------------------------------------------
    # Zoom helpers
    # ------------------------------------------------------------------
    _ZOOM_STEP = 0.15
    _ZOOM_MIN = 0.25
    _ZOOM_MAX = 4.0

    def _zoom_in(self):
        if self._view is None:
            return
        try:
            factor = float(self._view.zoomFactor())
        except Exception:
            return
        self._view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._view.setZoomFactor(min(self._ZOOM_MAX, factor + self._ZOOM_STEP))

    def _zoom_out(self):
        if self._view is None:
            return
        try:
            factor = float(self._view.zoomFactor())
        except Exception:
            return
        self._view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._view.setZoomFactor(max(self._ZOOM_MIN, factor - self._ZOOM_STEP))

    def _zoom_fit(self):
        if self._view is None:
            return
        try:
            self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # State display
    # ------------------------------------------------------------------
    def _show_view(self, visible):
        if self._view is not None:
            self._view.setVisible(visible)
        self._message.setVisible(not visible)

    def show_empty(self):
        """No content yet (e.g. preview just opened)."""
        self._pdf_path = None
        self.open_button.setEnabled(False)
        self.status_label.setText('Preview: idle')
        if self._view is None:
            self._message.setText(
                'Live preview needs Qt PDF support, which this build lacks.\n'
                'Use Build → Compile (Ctrl+B) to write a PDF instead.')
            self._message.show()
            return
        self._show_view(False)
        self._message.setText('Type to see a live preview…')

    def show_loading(self):
        self.status_label.setText('Preview: updating…')
        # Keep the old page visible while recompiling; only swap the
        # message layer when nothing was shown before.
        if self._pdf_path is None and self._view is not None:
            self._show_view(False)
            self._message.setText('Rendering preview…')

    def show_pdf(self, pdf_path):
        """Load *pdf_path* into the embedded viewer."""
        if self._view is None or self._document is None:
            self._pdf_path = pdf_path
            self.status_label.setText('Preview: updated')
            self._message.setText(
                f'Preview written to {pdf_path}\n'
                'Qt PDF view is unavailable in this build — '
                'use Open… to view it externally.')
            self._message.show()
            self.open_button.setEnabled(True)
            return
        # QPdfDocument.load() returns QPdfDocument.Error (None_ == success),
        # not Status — compare against the Error enum.
        try:
            err_none = QPdfDocument.Error.None_
        except Exception:
            err_none = 0
        try:
            error = self._document.load(pdf_path)
        except Exception as exc:
            self.show_error(f'Could not display preview PDF: {exc}')
            return
        if error != err_none:
            self.show_error(f'Could not display preview PDF ({pdf_path}).')
            return
        self._pdf_path = pdf_path
        self._show_view(True)
        count = 0
        try:
            count = int(self._document.pageCount())
        except Exception:
            pass
        self.status_label.setText(
            f'Preview: up to date ({count} page{"s" if count != 1 else ""})'
            if count else 'Preview: up to date')
        self.open_button.setEnabled(True)

    def show_error(self, message):
        """Show a compile failure; keeps the last good PDF if there is one."""
        self.status_label.setText('Preview: error')
        self.open_button.setEnabled(self._pdf_path is not None)
        if self._pdf_path is not None and self._view is not None:
            # Stale page stays visible; the status bar flags the error.
            # Surface the message as a tooltip-status so it is not lost.
            self.status_label.setToolTip(message)
            return
        self._show_view(False)
        self._message.setText(message)
        self._message.show()

    @property
    def pdf_path(self):
        return self._pdf_path

    @property
    def auto_enabled(self):
        return self.auto_check.isChecked()

    def set_auto_enabled(self, enabled):
        self.auto_check.setChecked(bool(enabled))
