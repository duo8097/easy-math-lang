"""Icon registry for the editor UI (Qt side only).

One place maps a logical icon name to a vendored Lucide SVG
(``editor/assets/icons/<file>.svg``, ISC/MIT — see the LICENSE
file there). ``icon(name)`` returns a cached :class:`QIcon` whose
pixmaps are rendered from the SVG at the requested size, so they
stay crisp on HiDPI. Monochrome SVGs (``stroke="currentColor"``)
are recolored to the current theme foreground; the disabled state
uses the muted disabled color. A missing/unreadable icon never
crashes: it falls back to an empty icon and logs once.

Theme changes: call :func:`refresh_icons` (MainWindow does this in
``_apply_theme``); every widget that was given an icon through
:func:`apply_icon` or that carries the ``icon-name`` property is
re-set with the new theme colors.
"""

from __future__ import annotations

import logging
import os
import weakref

from PySide6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger('easy-math-editor.icons')

ICONS = {
    'file-new': 'file-plus',
    'file-open': 'folder-open',
    'file-save': 'save',
    'file-save-as': 'file-up',
    'export': 'file-output',
    'exit': 'log-out',
    'undo': 'undo-2',
    'redo': 'redo-2',
    'cut': 'scissors',
    'copy': 'copy',
    'paste': 'clipboard-paste',
    'find': 'search',
    'goto-line': 'list-ordered',
    'compile': 'hammer',
    'refresh': 'refresh-cw',
    'zoom-in': 'zoom-in',
    'zoom-out': 'zoom-out',
    'zoom-reset': 'rotate-ccw',
    'fit': 'scan',
    'preview': 'eye',
    'open-external': 'external-link',
    'language': 'languages',
    'theme': 'moon',
    'examples': 'book-open',
    'shortcuts': 'keyboard',
    'about': 'info',
    'welcome': 'sparkles',
    'palette': 'command',
    'gallery': 'shapes',
    'outline': 'list',
    'problems': 'circle-exclamation-point',
    'update': 'download',
    'font': 'type',
    'find-prev': 'chevron-up',
    'find-next': 'chevron-down',
    'find-close': 'x',
    'replace': 'replace',
    'replace-all': 'repeat',
    'match-case': 'case-sensitive',
    'whole-word': 'whole-word',
    'ok': 'check',
    'cancel': 'x',
    'discard': 'ban',
    'yes': 'check',
    'no': 'circle-x',
    'close': 'x',
    'apply': 'check',
    'insert': 'plus',
    'insert-example': 'eye',
    'insert-command': 'plus',
    'empty-block': 'square',
    'add-row': 'plus',
    'add-cell': 'plus',
    'clear': 'trash',
    'filter': 'funnel',
    'error': 'circle-exclamation-point',
    'warning': 'triangle-exclamation-point',
    'info': 'info',
    'variable': 'variable',
    'function': 'square-function',
    'heading': 'list-tree',
    'draw': 'pen-tool',
    'define': 'book-open',
}

SIZE_MENU = 16
SIZE_TOOLBAR = 20
SIZE_DIALOG = 16
SIZE_PANEL = 16

_HERE = os.path.dirname(os.path.abspath(__file__))
_cache = {}
_logged_missing = set()
_registered = []  # weakrefs to widgets carrying icon-name/size


def _icon_dir():
    candidates = [os.path.join(_HERE, 'assets', 'icons')]
    try:
        from .paths import resource_path
        candidates.append(resource_path('editor', 'assets', 'icons'))
    except Exception:  # pragma: no cover - defensive
        pass
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return candidates[0]


def icon_path(name):
    """Absolute path of the SVG for *name*, or None when unknown."""
    filename = ICONS.get(name)
    if filename is None:
        return None
    path = os.path.join(_icon_dir(), f'{filename}.svg')
    return path if os.path.isfile(path) else None


def _theme_colors():
    """(normal, disabled) foreground colors for the current theme."""
    app = QtWidgets.QApplication.instance()
    dark = False
    if app is not None:
        # The active theme is tracked on the main window; fall back
        # to the palette brightness when no window exists yet.
        dark = bool(getattr(app, '_ezmath_dark', False))
        if not dark and getattr(app, '_ezmath_theme_checked', False) is False:
            try:
                dark = app.palette().color(
                    QtGui.QPalette.Window).lightness() < 128
            except Exception:
                dark = False
            app._ezmath_theme_checked = True
    if dark:
        return '#d4d4d4', '#808080'
    return '#333333', '#808080'


def set_theme_dark(dark):
    """Record the active theme (called by MainWindow._apply_theme)."""
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app._ezmath_dark = bool(dark)
        app._ezmath_theme_checked = True
    refresh_icons()


def _render_pixmap(name, size, color, ratio=None):
    """Render one icon into a ``size`` x ``size`` logical-pixel pixmap.

    *ratio* is the device pixel ratio of the target screen (the current
    screen's when omitted); it is a parameter so the HiDPI path can be
    tested without a HiDPI display.
    """
    path = icon_path(name)
    if path is None:
        return QtGui.QPixmap()
    try:
        with open(path, encoding='utf-8') as handle:
            svg = handle.read()
    except OSError:
        return QtGui.QPixmap()
    svg = svg.replace('currentColor', color)
    try:
        from PySide6 import QtSvg

        renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg.encode('utf-8')))
        if not renderer.isValid():
            return QtGui.QPixmap()
        if ratio is None:
            ratio = 1.0
            try:
                screen = QtGui.QGuiApplication.primaryScreen()
                if screen is not None:
                    ratio = float(screen.devicePixelRatio() or 1.0)
            except Exception:
                pass
        pixmap = QtGui.QPixmap(int(size * ratio), int(size * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        try:
            # Render into an explicit rectangle. Without it QSvgRenderer
            # paints the SVG at its *natural* size (24x24) in logical
            # units, which overflows the requested box and gets clipped
            # (badly so on a HiDPI screen, where the box is smaller than
            # the natural size in device pixels).
            renderer.render(painter, QtCore.QRectF(0, 0, size, size))
        finally:
            painter.end()
        return pixmap
    except Exception:
        return QtGui.QPixmap()


def icon(name, size=SIZE_MENU):
    """Cached QIcon for *name* at *size* px (logical, HiDPI-aware)."""
    if name not in ICONS:
        if name not in _logged_missing:
            _logged_missing.add(name)
            logger.warning('unknown icon %r; using no icon', name)
        return QtGui.QIcon()
    normal, disabled = _theme_colors()
    key = (name, int(size), normal, disabled)
    if key in _cache:
        return _cache[key]
    if icon_path(name) is None:
        if name not in _logged_missing:
            _logged_missing.add(name)
            logger.warning('icon file missing for %r; using no icon', name)
        empty = QtGui.QIcon()
        _cache[key] = empty
        return empty
    result = QtGui.QIcon()
    result.addPixmap(_render_pixmap(name, size, normal),
                     QtGui.QIcon.Normal)
    result.addPixmap(_render_pixmap(name, size, disabled),
                     QtGui.QIcon.Disabled)
    _cache[key] = result
    return result


def apply_icon(widget, name, size=SIZE_MENU):
    """Set *widget*'s icon and remember it for theme refreshes."""
    if widget is None or not name:
        return widget
    try:
        widget.setIcon(icon(name, size))
        widget.setProperty('icon-name', name)
        widget.setProperty('icon-size', int(size))
        _registered.append(weakref.ref(widget))
    except (RuntimeError, AttributeError):
        pass
    return widget


def apply_action_icon(action, name, size=SIZE_MENU):
    """Set a QAction's icon (menus, palette) without touching its text."""
    if action is None or not name:
        return action
    try:
        action.setIcon(icon(name, size))
        action.setProperty('icon-name', name)
        action.setProperty('icon-size', int(size))
        _registered.append(weakref.ref(action))
    except (RuntimeError, AttributeError):
        pass
    return action


def refresh_icons():
    """Re-apply every registered icon after a theme change."""
    _cache.clear()
    alive = []
    for ref in _registered:
        widget = ref()
        if widget is None:
            continue
        try:
            from shiboken6 import isValid as _is_valid
            if not _is_valid(widget):
                continue
        except Exception:
            pass
        try:
            name = widget.property('icon-name')
            size = widget.property('icon-size') or SIZE_MENU
        except Exception:
            continue
        if not name:
            continue
        try:
            if isinstance(widget, QtGui.QAction):
                widget.setIcon(icon(name, int(size)))
            else:
                widget.setIcon(icon(name, int(size)))
        except Exception:
            continue
        alive.append(ref)
    _registered[:] = alive
