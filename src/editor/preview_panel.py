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


def _event_point(event):
    """Viewport position of a mouse event as QPoint (Qt5/Qt6 compatible)."""
    try:
        return event.position().toPoint()
    except (AttributeError, RuntimeError, TypeError):
        return event.pos()


class PreviewPanel(QtWidgets.QWidget):
    """Right-hand preview: toolbar + PDF view (or error/empty message).

    Source navigation: the compiler writes a sidecar source map
    (``preview.smap.json``) mapping generated ``.typ`` ranges back to the
    original ``.eml`` spans, and the live preview additionally embeds
    invisible ``eml-src://typ/<line>/<col>`` link annotations (see
    :mod:`compiler.source_links`) — one per mapped block, with no visual
    change (Typst styles links like normal text).

    Click handling: Qt 6.11 delivers no activation events for *external*
    URI link clicks (verified: no ``jumped``, no ``openUrl``), so this
    panel hit-tests Ctrl+Clicks itself — viewport coordinates are mapped
    to PDF page coordinates via live scrollbar/layout metrics (zoom,
    scroll, page mode, margins and spacing accounted for, cross-checked
    against scrollbar maximums), matched against the extracted
    ``eml-src`` annotation rectangles, and valid hits emit
    :attr:`sourceLinkActivated`. Plain clicks, drags, misses, invalid
    URIs and ordinary (non-eml-src) links do nothing, preserving
    scrolling, text selection and internal-link navigation. ``jumped``
    activations carrying ``eml-src`` URLs are routed the same way.
    Use :meth:`set_source_map` after each build and
    :meth:`typ_location_to_eml` to resolve a generated-Typ location.
    """

    refreshRequested = QtCore.Signal()
    autoToggled = QtCore.Signal(bool)
    openPdfRequested = QtCore.Signal()
    # Emitted for Ctrl+Click on an eml-src link: 0-based Typst position.
    sourceLinkActivated = QtCore.Signal(int, int)

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
        self._smap_path = None
        self._link_annots: list = []
        self._press_state = None
        self._ctrl_held = False
        if _PDF_AVAILABLE:
            self._document = QPdfDocument(self)
            self._view = QPdfView(self)
            self._view.setDocument(self._document)
            self._view.viewport().installEventFilter(self)
            self._view.setToolTip(
                'Ctrl+Click a paragraph to go to its source line')
            try:
                self._view.pageNavigator().jumped.connect(
                    self._on_navigator_jumped)
            except (AttributeError, RuntimeError, TypeError):
                pass
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
    # Click-to-source geometry (viewport -> PDF page coordinates)
    # ------------------------------------------------------------------
    # QPdfView lays pages out in logical pixels as (verified against live
    # scrollbar metrics across zoom modes, see tests/test_preview_hit.py):
    #   k (px per PDF point) = zoomFactor * 96/72 in Custom mode, or
    #       (viewportWidth - margins.left - margins.right) / widestPage
    #       in FitToWidth mode;
    #   page height px = round(pagePoints * k);
    #   page tops stack as margin.top + cumulative(height + spacing);
    #   pages narrower than the available width are centered.
    # The mapping below is cross-checked against the live scrollbar
    # maximums (which encode the true content size); on any mismatch it
    # returns None so a click degrades to "do nothing" instead of a wrong
    # jump. PDF y grows upwards, viewport y downwards (flipped here).
    _PX_PER_POINT = 96.0 / 72.0
    _LAYOUT_CHECK_TOL = 0.02

    def _layout_metrics(self):
        """(k, tops, lefts, page_sizes) or None when indeterminable."""
        try:
            from PySide6.QtPdfWidgets import QPdfView as _QPV
        except Exception:
            return None
        try:
            if self._view is None or self._document is None:
                return None
            mode = self._view.zoomMode()
            vp = self._view.viewport()
            vp_w, vp_h = int(vp.width()), int(vp.height())
            if vp_w <= 0 or vp_h <= 0:
                return None
            try:
                margins = self._view.documentMargins()
                ml, mt, mr, mb = (int(margins.left()), int(margins.top()),
                                  int(margins.right()), int(margins.bottom()))
            except Exception:
                ml = mt = mr = mb = 0
            try:
                spacing = int(self._view.pageSpacing())
            except Exception:
                spacing = 0
            count = int(self._document.pageCount())
            if count <= 0:
                return None
            sizes = []
            for i in range(count):
                try:
                    s = self._document.pagePointSize(i)
                    sizes.append((float(s.width()), float(s.height())))
                except Exception:
                    return None
            if any(w <= 0 or h <= 0 for w, h in sizes):
                return None
            if mode == _QPV.ZoomMode.Custom:
                try:
                    k = float(self._view.zoomFactor()) * self._PX_PER_POINT
                except Exception:
                    return None
            elif mode == _QPV.ZoomMode.FitToWidth:
                avail = vp_w - ml - mr
                widest = max(w for w, _ in sizes)
                if avail <= 0 or widest <= 0:
                    return None
                k = avail / widest
            else:
                return None  # e.g. FitInView: unverified, degrade safely
            if k <= 0:
                return None
            heights = [int(round(h * k)) for _, h in sizes]
            widths = [int(round(w * k)) for w, _ in sizes]
            avail_w = vp_w - ml - mr
            if self._view.pageMode() == _QPV.PageMode.SinglePage:
                try:
                    current = int(self._view.pageNavigator().currentPage())
                except Exception:
                    current = 0
                current = max(0, min(current, count - 1))
                tops = [0.0] * count
                tops[current] = float(mt)
                lefts = [0.0] * count
                lefts[current] = float(ml + max(0, (avail_w - widths[current]) // 2))
                order = [current]
            else:
                tops, lefts, order = [], [], []
                y = float(mt)
                for i in range(count):
                    tops.append(y)
                    lefts.append(float(ml + max(0, (avail_w - widths[i]) // 2)))
                    order.append(i)
                    y += heights[i] + spacing
            # Cross-check against the true content size from scrollbars.
            try:
                vsb = self._view.verticalScrollBar()
                vmax, vph = int(vsb.maximum()), int(vp_h)
                if vmax > 0:
                    if self._view.pageMode() == _QPV.PageMode.SinglePage:
                        expect_h = (mt + mb + heights[order[0]] + spacing)
                    else:
                        expect_h = (mt + mb + sum(heights) + spacing * count)
                    if abs((vmax + vph) - expect_h) > max(3.0, expect_h * self._LAYOUT_CHECK_TOL):
                        return None
            except Exception:
                return None
            return (k, tops, lefts, sizes, heights, widths)
        except Exception:
            return None

    def page_point_at(self, viewport_pos):
        """Viewport QPoint -> ``(page, QPointF pdf_point)`` or ``None``.

        *page* is 0-based; the point is in PDF points (bottom-left
        origin), matching annotation ``/Rect`` coordinates. ``None``
        covers gaps between pages, margins, unknown layouts and any
        indeterminable state — callers treat it as "no navigation".
        """
        try:
            from PySide6 import QtCore as _QtCore
            metrics = self._layout_metrics()
            if metrics is None:
                return None
            k, tops, lefts, sizes, heights, _widths = metrics
            try:
                vx, vy = float(viewport_pos.x()), float(viewport_pos.y())
                hx = float(self._view.horizontalScrollBar().value())
                vy_scroll = float(self._view.verticalScrollBar().value())
            except Exception:
                return None
            cx, cy = vx + hx, vy + vy_scroll
            from PySide6.QtPdfWidgets import QPdfView as _QPV
            if self._view.pageMode() == _QPV.PageMode.SinglePage:
                try:
                    page = int(self._view.pageNavigator().currentPage())
                except Exception:
                    return None
                candidates = (page,)
            else:
                candidates = range(len(sizes))
            for page in candidates:
                top, left = tops[page], lefts[page]
                pw, ph = sizes[page]
                if not (top <= cy < top + heights[page]):
                    continue
                px = (cx - left) / k
                py = ph - (cy - top) / k
                if not (0.0 <= px <= pw and 0.0 <= py <= ph):
                    return None
                return (page, _QtCore.QPointF(px, py))
            return None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # State display
    # ------------------------------------------------------------------
    def _show_view(self, visible):
        if self._view is not None:
            self._view.setVisible(visible)
        self._message.setVisible(not visible)

    def _reload_link_annotations(self):
        """(Re)read URI link annotations for the current PDF (never raises)."""
        self._link_annots = []
        try:
            if not self._pdf_path:
                return
            from .pdf_links import extract_link_annotations_from_file
            found = extract_link_annotations_from_file(self._pdf_path)
            self._link_annots = list(found) if found else []
        except Exception:
            self._link_annots = []

    def _navigate_to_point(self, viewport_pos):
        """Hit-test one viewport point; True when navigation was requested.

        Maps the point to ``(page, pdf_point)``, finds the first
        ``eml-src`` annotation containing it, and routes through
        :meth:`handle_source_url` (which emits :attr:`sourceLinkActivated`
        and reuses the Typ→.eml→cursor chain). Misses, invalid URIs,
        unmapped locations and ordinary links all return False without
        side effects.
        """
        try:
            located = self.page_point_at(viewport_pos)
            if located is None:
                return False
            page, point = located
            try:
                px, py = float(point.x()), float(point.y())
            except Exception:
                return False
            try:
                from .pdf_links import hit_test
            except Exception:
                return False
            for annot_page, rect, uri in list(self._link_annots or []):
                try:
                    if int(annot_page) != int(page):
                        continue
                except (TypeError, ValueError):
                    continue
                try:
                    if not hit_test(rect, px, py):
                        continue
                except Exception:
                    continue
                if self.handle_source_url(uri, True):
                    return True
                # Hit a non-source link (e.g. https): leave it alone so
                # ordinary link behavior is preserved.
                return False
            return False
        except Exception:
            return False

    def show_empty(self):
        """No content yet (e.g. preview just opened)."""
        self._pdf_path = None
        self._link_annots = []
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
        self._reload_link_annotations()

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
    def smap_path(self):
        """Current sidecar source-map path (or None)."""
        return self._smap_path

    def set_source_map(self, smap_path):
        """Remember the sidecar map for the currently shown PDF."""
        try:
            import os as _os
            if smap_path and _os.path.isfile(str(smap_path)):
                self._smap_path = str(smap_path)
                return
        except Exception:
            pass
        self._smap_path = None

    def typ_location_to_eml(self, typ_line, typ_column):
        """Resolve a generated-Typ location (0-based) to an .eml span.

        Returns a ``SourceSpan`` (0-based code-point columns) or ``None``
        when unmapped / map missing. Qt-free resolution lives in
        ``editor.preview.resolve_typ_to_eml``; this is a thin wrapper
        using the panel's current map.
        """
        try:
            from .preview import resolve_typ_to_eml
        except Exception:
            return None
        return resolve_typ_to_eml(self._smap_path, typ_line, typ_column)

    # ------------------------------------------------------------------
    # Click-to-source (Ctrl+Click on eml-src link annotations)
    # ------------------------------------------------------------------
    def eventFilter(self, watched, event):
        """Observe viewport clicks for Ctrl+Click navigation.

        Records Ctrl+left-presses; on release at nearly the same position
        (a click, not a drag/scroll/selection) with Ctrl held, hit-tests
        source-link annotations. Never consumes events: returns False
        always so scrolling, selection and page navigation keep working.
        """
        try:
            from PySide6 import QtCore as _QtCore
            if self._view is not None and watched is self._view.viewport():
                etype = event.type()
                if etype == _QtCore.QEvent.MouseButtonPress:
                    try:
                        if event.button() == _QtCore.Qt.LeftButton:
                            mods = event.modifiers()
                            self._press_state = (
                                _event_point(event),
                                bool(mods & _QtCore.Qt.ControlModifier),
                            )
                            self._ctrl_held = bool(
                                mods & _QtCore.Qt.ControlModifier)
                        else:
                            self._press_state = None
                    except (AttributeError, RuntimeError, TypeError):
                        self._press_state = None
                elif etype == _QtCore.QEvent.MouseButtonRelease:
                    state, self._press_state = self._press_state, None
                    try:
                        if (state is not None
                                and event.button() == _QtCore.Qt.LeftButton):
                            press_pos, press_ctrl = state
                            mods = event.modifiers()
                            release_ctrl = bool(
                                mods & _QtCore.Qt.ControlModifier)
                            if press_ctrl and release_ctrl:
                                try:
                                    rel_pos = _event_point(event)
                                    dist = (rel_pos - press_pos).manhattanLength()
                                except Exception:
                                    dist = 0
                                if dist <= 6:
                                    self._navigate_to_point(rel_pos)
                    except (AttributeError, RuntimeError, TypeError):
                        pass
        except (AttributeError, RuntimeError, TypeError):
            pass
        return False

    def _on_navigator_jumped(self, link):
        """Route ``eml-src`` link activations to source navigation."""
        try:
            url = link.url().toString() if link is not None else ''
        except (AttributeError, RuntimeError, TypeError):
            return
        self.handle_source_url(url, self._ctrl_held)

    def handle_source_url(self, url_string, ctrl_held):
        """Handle one activated link URL; True when navigation was requested.

        Parses *url_string* with :mod:`compiler.source_links`; emits
        :attr:`sourceLinkActivated` only for valid ``eml-src`` URLs *and*
        a held Ctrl (otherwise ordinary viewing is preserved). Never
        raises; returns whether the signal was emitted (useful in tests).
        """
        try:
            from compiler.source_links import parse_source_url
        except Exception:
            try:
                from .preview_links import parse_source_url  # type: ignore
            except Exception:
                return False
        try:
            parsed = parse_source_url(url_string)
        except Exception:
            return False
        if parsed is None or not bool(ctrl_held):
            return False
        try:
            self.sourceLinkActivated.emit(int(parsed[0]), int(parsed[1]))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False
        return True

    @property
    def auto_enabled(self):
        return self.auto_check.isChecked()

    def set_auto_enabled(self, enabled):
        self.auto_check.setChecked(bool(enabled))
