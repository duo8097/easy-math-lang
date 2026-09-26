"""Live preview: compile editor text to PDF in a temp dir (headless logic).

The GUI part lives in :mod:`editor.preview_panel`. This module has no Qt
dependency so it stays unit-testable without a display.
"""

import contextlib
import io
import os

PREVIEW_DEBOUNCE_MS = 800

PREVIEW_SOURCE_NAME = 'preview.ezmath'
PREVIEW_PDF_NAME = 'preview.pdf'
PREVIEW_TYP_NAME = 'preview.typ'


def ensure_workdir(workdir):
    """Create *workdir* (and parents) and return its absolute path."""
    path = os.path.abspath(workdir)
    os.makedirs(path, exist_ok=True)
    return path


def compile_source_to_pdf(source_text, workdir):
    """Compile *source_text* to a preview PDF inside *workdir*.

    Writes ``preview.ezmath`` then reuses
    :func:`compiler.pipeline.compile_ezmath` so preview output matches
    ``Build → Compile`` exactly (variables, calc, geometry, Typst).

    Returns a dict: ``{'ok': bool, 'pdf': str|None, 'typ': str,
    'log': str}``. ``pdf`` is set only when compilation succeeded and
    the file exists. ``log`` captures the compiler's stdout/stderr so
    the panel can show the failure reason without a modal dialog.
    """
    from compiler.pipeline import compile_ezmath

    directory = ensure_workdir(workdir)
    src_path = os.path.join(directory, PREVIEW_SOURCE_NAME)
    pdf_path = os.path.join(directory, PREVIEW_PDF_NAME)
    typ_path = os.path.join(directory, PREVIEW_TYP_NAME)
    with open(src_path, 'w', encoding='utf-8') as handle:
        handle.write(source_text)

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    ok = False
    with contextlib.redirect_stdout(stdout_buf), \
            contextlib.redirect_stderr(stderr_buf):
        try:
            ok = bool(compile_ezmath(src_path, pdf_path))
        except Exception as exc:  # never let preview crash the editor
            print(f'[ERROR] Preview failed: {exc}')
            ok = False
    log = (stdout_buf.getvalue() + stderr_buf.getvalue()).strip()
    pdf = pdf_path if (ok and os.path.isfile(pdf_path)) else None
    return {'ok': bool(pdf), 'pdf': pdf, 'typ': typ_path, 'log': log}
