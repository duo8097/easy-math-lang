#!/usr/bin/env python3
"""Generate every image used by the GitHub Pages site.

Two kinds of images are produced, both from the project's own code —
nothing is drawn by hand:

1. **Editor screenshots** — the real desktop editor (PySide6) rendered
   offscreen with ``QT_QPA_PLATFORM=offscreen``. The window is built
   exactly like the offscreen GUI tests build it
   (``tests/test_editor_gui.py``): ``MainWindow(start_lsp=False,
   no_save_prompt=True)`` with a real example loaded. Language and theme
   are pinned by writing an isolated ``config.ini`` into a throw-away
   ``HOME`` *before* the window is constructed, so the editor is built
   in the wanted language/theme instead of being switched afterwards.
   The language comes from the editor's own catalog
   (``src/editor/locales/*.json``) — the site never invents a UI string.

2. **Compiled example output** — the editor's own built-in examples
   (``src/editor/help_dialogs.py::EXAMPLES``, the same snippets the
   welcome panel offers) are written to a temporary ``.ezmath`` file and
   compiled by the project compiler (``compiler.pipeline.compile_ezmath``)
   to SVG. The resulting SVG is then cropped to the content bounding box
   with Qt's SVG renderer; nothing about the drawing is altered.

Every file is written to ``site/assets/img/`` and described in
``site/assets/img/manifest.json`` (SHA-256, size, and how the file was
produced). ``scripts/check_site.py`` verifies the manifest against the
files on disk, so a placeholder or a stale image fails the check.

Determinism: fixed window size, fixed theme, fixed example, no
timestamps, and an isolated settings file — re-running the script on the
same machine reproduces the same bytes.

Usage:
    python3 scripts/make_site_screenshots.py [--out-dir DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / 'src'
sys.path.insert(0, str(SRC_DIR))

# The editor must run without a display. Honour an explicit setting from
# the environment, default to the offscreen platform otherwise.
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
# HiDPI: render at device pixel ratio 2 (must be set before the
# QApplication is created).
os.environ.setdefault('QT_SCALE_FACTOR', '2')

# Fixed window geometry (logical pixels) and device pixel ratio.
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
SCALE_FACTOR = 2

# The document shown in the editor screenshots: a real example file.
EDITOR_EXAMPLE = REPO_ROOT / 'examples' / 'example_2.ezmath'

# The app icon, copied verbatim from the repository.
ICON_SOURCE = REPO_ROOT / 'icons' / 'ezmath-icon.png'
ICON_NAME = 'ezmath-icon.png'
ICON_SIZE = 256

# Editor screenshots: (file name, ui language, theme, kind).
EDITOR_SHOTS = (
    ('editor-english-light.png', 'en', 'light', 'window'),
    ('editor-english-dark.png', 'en', 'dark', 'window'),
    ('editor-vietnamese-light.png', 'vi', 'light', 'window'),
    ('editor-vietnamese-dark.png', 'vi', 'dark', 'window'),
    ('editor-welcome-panel.png', 'en', 'light', 'welcome'),
    ('editor-draw-gallery.png', 'en', 'light', 'gallery'),
)

# Compiled examples: the editor's built-in snippets (id -> source).
# ``help_dialogs.EXAMPLES`` holds them; they are the very snippets the
# welcome panel inserts into a new document.
EXAMPLE_IDS = ('basic-math', 'fraction-equation', 'vector', 'simple-draw')


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _write_settings(home: Path, language: str, theme: str) -> None:
    """Write an isolated editor config so the UI starts in one language.

    The editor reads its language from ``ui/language`` and its theme from
    ``theme`` in ``~/.config/ezmath/config.ini``. Pointing ``HOME`` at a
    throw-away directory keeps the developer's own settings untouched and
    makes the screenshots reproducible.
    """
    config_dir = home / '.config' / 'ezmath'
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / 'config.ini').write_text(
        '[General]\n'
        f'theme={theme}\n'
        '\n'
        '[ui]\n'
        f'language={language}\n'
        'showWelcome=false\n',
        encoding='utf-8',
    )


def _pump(app, times: int = 6) -> None:
    """Let Qt lay out and paint before a grab."""
    for _ in range(times):
        app.processEvents()


def _reset_application_theme(app) -> None:
    """Put the application back into its default (light) appearance.

    One process renders several screenshots with different themes. The
    editor sets the *application* palette, so a dark screenshot would
    leave the app dark and the next (light) window would capture that
    dark palette as its "default". Resetting here keeps every screenshot
    independent of the ones before it.
    """
    from PySide6 import QtGui

    from editor import icons

    app.setPalette(QtGui.QPalette())
    app.setStyleSheet('')
    icons.set_theme_dark(False)


def _grab_png(widget, path: Path) -> None:
    pixmap = widget.grab()
    if pixmap.isNull() or pixmap.width() < 2 or pixmap.height() < 2:
        raise RuntimeError(f'{widget} produced an empty pixmap')
    if not pixmap.save(str(path), 'PNG'):
        raise RuntimeError(f'could not write {path}')


def _editor_screenshots(out_dir: Path) -> list[dict]:
    """Render the editor offscreen and save the screenshots."""
    from PySide6 import QtWidgets

    from editor.main_window import MainWindow

    entries: list[dict] = []
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    for name, language, theme, kind in EDITOR_SHOTS:
        home = Path(tempfile.mkdtemp(prefix='ezmath-shot-'))
        os.environ['HOME'] = str(home)
        _write_settings(home, language, theme)
        _reset_application_theme(app)

        window = MainWindow(start_lsp=False, no_save_prompt=True)
        try:
            window.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
            window.show()
            if kind == 'welcome':
                window._show_welcome()
            elif kind == 'gallery':
                window.open_path(str(EDITOR_EXAMPLE))
                window._open_draw_gallery()
            else:
                window.open_path(str(EDITOR_EXAMPLE))
            _pump(app)

            if kind == 'welcome':
                panel = window._welcome_panel
                panel.adjustSize()
                _pump(app)
                target = panel
            elif kind == 'gallery':
                gallery = window._draw_gallery
                gallery.resize(900, 560)
                gallery.show()
                _pump(app)
                target = gallery
            else:
                target = window

            path = out_dir / name
            _grab_png(target, path)
            entries.append({
                'file': name,
                'kind': 'editor-screenshot',
                'bytes': path.stat().st_size,
                'sha256': _sha256(path),
                'produced_by': (
                    'offscreen Qt screenshot of the real Easy Math Editor '
                    f'(MainWindow, ui language={language}, theme={theme}, '
                    f'window {WINDOW_WIDTH}x{WINDOW_HEIGHT} logical pixels, '
                    f'device pixel ratio {SCALE_FACTOR}); document loaded: '
                    f'{EDITOR_EXAMPLE.relative_to(REPO_ROOT)}'
                ),
            })
            print(f'  {name} ({path.stat().st_size} bytes)')
        finally:
            window.close()
            _pump(app, 2)
            del window
            shutil.rmtree(home, ignore_errors=True)
    return entries


def _first_group_span(svg: str) -> tuple[int, int] | None:
    """Span of the first top-level ``<g>`` element (the document title).

    The compiler emits the document title as the first centred block of
    the page, so the group is removed before the content box is measured.
    """
    start = svg.find('<g')
    if start < 0:
        return None
    depth = 0
    index = start
    while index < len(svg):
        open_at = svg.find('<g', index)
        close_at = svg.find('</g>', index)
        if close_at < 0:
            return None
        if 0 <= open_at < close_at:
            depth += 1
            index = open_at + 2
            continue
        depth -= 1
        index = close_at + 4
        if depth == 0:
            return start, index
    return None


def _content_box(svg_text: str):
    """Bounding box of the visible content, in SVG user units."""
    from PySide6 import QtCore, QtGui, QtSvg

    renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg_text.encode('utf-8')))
    if not renderer.isValid():
        raise RuntimeError('generated SVG is not valid')
    view = renderer.viewBoxF()
    if not view.isValid() or view.width() <= 0 or view.height() <= 0:
        raise RuntimeError('generated SVG has no usable viewBox')

    scale = 3.0
    width = int(round(view.width() * scale))
    height = int(round(view.height() * scale))
    image = QtGui.QImage(width, height, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor('white'))
    painter = QtGui.QPainter(image)
    try:
        renderer.render(painter)
    finally:
        painter.end()

    min_x, min_y, max_x, max_y = width, height, -1, -1
    for y in range(height):
        for x in range(width):
            colour = image.pixelColor(x, y)
            if colour.red() < 250 or colour.green() < 250 \
                    or colour.blue() < 250:
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
    if max_x < 0:
        raise RuntimeError('generated SVG has no visible content')
    return (
        view.x() + min_x / scale,
        view.y() + min_y / scale,
        view.x() + max_x / scale,
        view.y() + max_y / scale,
    )


def _crop_svg(svg_text: str, padding: float = 6.0) -> str:
    """Crop the page SVG to its content box.

    The compiler's default document title (the centred
    "Easy Math Document" heading it adds to every page without a
    ``*doc_title``) is dropped: it is page chrome, not part of the
    example. Everything that is left is the untouched compiler output.
    """
    body = svg_text
    span = _first_group_span(svg_text)
    if span is not None:
        start, end = span
        body = svg_text[:start] + svg_text[end:]

    x0, y0, x1, y1 = _content_box(body)
    x0 -= padding
    y0 -= padding
    x1 += padding
    y1 += padding
    cropped_width = max(1.0, x1 - x0)
    cropped_height = max(1.0, y1 - y0)

    def _replace(match: re.Match) -> str:
        tag = match.group(0)
        tag = re.sub(r'\s(viewBox|width|height)="[^"]*"', '', tag)
        return tag.replace(
            '<svg',
            f'<svg viewBox="{x0:.4f} {y0:.4f} {cropped_width:.4f} '
            f'{cropped_height:.4f}" width="{cropped_width:.4f}pt" '
            f'height="{cropped_height:.4f}pt"',
            1,
        )

    return re.sub(r'<svg[^>]*>', _replace, svg_text, count=1)


def _example_outputs(out_dir: Path) -> list[dict]:
    """Compile the editor's built-in examples and store the output."""
    from compiler.pipeline import compile_ezmath
    from editor.help_dialogs import EXAMPLES

    sources = {entry_id: source for entry_id, _name, source in EXAMPLES}
    entries: list[dict] = []
    workdir = Path(tempfile.mkdtemp(prefix='ezmath-examples-'))
    try:
        for entry_id in EXAMPLE_IDS:
            source = sources.get(entry_id)
            if not source:
                raise RuntimeError(f'editor example {entry_id!r} not found')
            ezmath_path = workdir / f'{entry_id}.ezmath'
            ezmath_path.write_text(source, encoding='utf-8')
            svg_path = workdir / f'{entry_id}.svg'
            ok = compile_ezmath(str(ezmath_path), output=str(svg_path),
                                format='svg')
            if not ok or not svg_path.is_file():
                raise RuntimeError(f'compiling {entry_id} failed')
            cropped = _crop_svg(svg_path.read_text(encoding='utf-8'))
            name = f'example-{entry_id}.svg'
            path = out_dir / name
            path.write_text(cropped, encoding='utf-8')
            entries.append({
                'file': name,
                'kind': 'compiled-example',
                'bytes': path.stat().st_size,
                'sha256': _sha256(path),
                'produced_by': (
                    'output of the project compiler: the editor built-in '
                    f'example {entry_id!r} (src/editor/help_dialogs.py) '
                    'compiled to SVG with compiler.pipeline.compile_ezmath '
                    '(Typst), cropped to the content box'
                ),
            })
            print(f'  {name} ({path.stat().st_size} bytes)')
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return entries


def _copy_icon(out_dir: Path) -> dict:
    """Copy the app icon into the site (never redrawn).

    The repository icon is a 1024x1024 PNG (740 KB); the site only ever
    shows it at 40 px (logo) or 32 px (favicon), so it is scaled down to
    256x256 for the web. The artwork itself is untouched.
    """
    from PySide6 import QtCore, QtGui

    app = QtGui.QGuiApplication.instance()
    if app is None:  # pragma: no cover - the editor shots create one
        from PySide6 import QtWidgets
        app = QtWidgets.QApplication([])

    source = QtGui.QImage(str(ICON_SOURCE))
    if source.isNull():
        raise RuntimeError(f'cannot read {ICON_SOURCE}')
    scaled = source.scaled(
        ICON_SIZE, ICON_SIZE,
        QtCore.Qt.IgnoreAspectRatio,
        QtCore.Qt.SmoothTransformation,
    )
    target = out_dir / ICON_NAME
    if not scaled.save(str(target), 'PNG'):
        raise RuntimeError(f'could not write {target}')
    return {
        'file': ICON_NAME,
        'kind': 'icon',
        'bytes': target.stat().st_size,
        'sha256': _sha256(target),
        'produced_by': (
            f'the repository app icon icons/ezmath-icon.png scaled to '
            f'{ICON_SIZE}x{ICON_SIZE} px (not redrawn)'
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        '--out-dir',
        default=str(REPO_ROOT / 'site' / 'assets' / 'img'),
        help='directory for the generated images '
             '(default: site/assets/img)',
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f'Writing images to {out_dir}')
    entries: list[dict] = []
    print('Editor screenshots:')
    entries.extend(_editor_screenshots(out_dir))
    print('Compiled examples:')
    entries.extend(_example_outputs(out_dir))
    print('App icon:')
    entries.append(_copy_icon(out_dir))

    manifest = {
        'generator': 'scripts/make_site_screenshots.py',
        'note': (
            'Every image below was produced by the project itself: editor '
            'screenshots come from the real editor rendered offscreen, the '
            'example images come from the project compiler. The SHA-256 '
            'digests let scripts/check_site.py detect placeholders, stale '
            'files and manual edits.'
        ),
        'images': sorted(entries, key=lambda item: item['file']),
    }
    manifest_path = out_dir / 'manifest.json'
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )
    print(f'\nManifest: {manifest_path} '
          f'({len(entries)} image(s))')
    return 0


if __name__ == '__main__':
    sys.exit(main())
