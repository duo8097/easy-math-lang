"""Live preview: compile editor text to PDF in a temp dir (headless logic).

The GUI part lives in :mod:`editor.preview_panel`. This module has no Qt
dependency so it stays unit-testable without a display.
"""

import contextlib
import io
import os
import threading

PREVIEW_DEBOUNCE_MS = 800

# Serializes concurrent compile_source_to_format calls (live preview
# thread + export) so process-global redirect_stdout/stderr captures
# don't interleave. GUI threads writing to sys.stderr should also hold
# this lock (see editor.lsp_client) to avoid bleeding into preview logs.
COMPILE_LOCK = threading.Lock()

PREVIEW_SOURCE_NAME = 'preview.ezmath'
PREVIEW_PDF_NAME = 'preview.pdf'
PREVIEW_TYP_NAME = 'preview.typ'


def ensure_workdir(workdir):
    """Create *workdir* (and parents) and return its absolute path."""
    path = os.path.abspath(workdir)
    os.makedirs(path, exist_ok=True)
    return path


def compile_source_to_pdf(source_text, workdir, version=None):
    """Compile *source_text* to a preview PDF inside *workdir*.

    Writes ``preview.ezmath`` then reuses
    :func:`compiler.pipeline.compile_ezmath` so preview output matches
    ``Build → Compile`` exactly (variables, calc, geometry, Typst).

    Returns a dict: ``{'ok': bool, 'pdf': str|None, 'typ': str,
    'log': str}``. ``pdf`` is set only when compilation succeeded and
    the file exists. ``log`` captures the compiler's stdout/stderr so
    the panel can show the failure reason without a modal dialog.
    """
    return compile_source_to_format(
        source_text, workdir, format='pdf', version=version,
    )


def compile_source_to_format(source_text, workdir, format='pdf',
                             version=None, ppi=None):
    """Compile *source_text* to *format* (pdf/png/svg/html/typ) in *workdir*.

    Headless helper shared by the live preview (pdf) and
    ``File → Export As…`` (any format). No Qt dependency.
    Returns ``{'ok', 'file', 'files', 'pdf', 'typ', 'log', 'format'}``:
    ``file`` is the first exported path (``pdf`` kept as an alias for
    preview callers); ``files`` lists every page for multi-page PNG/SVG.
    """
    from compiler.pipeline import compile_ezmath

    directory = ensure_workdir(workdir)
    try:
        suffix = f'-{int(version)}' if version is not None else ''
    except (TypeError, ValueError):
        suffix = ''
    fmt = str(format or 'pdf').strip().lower().lstrip('.')
    if fmt == 'htm':
        fmt = 'html'
    src_path = os.path.join(directory, PREVIEW_SOURCE_NAME)
    out_name = (f'preview{suffix}.{fmt}' if suffix
                else f'preview.{fmt}')
    out_path = os.path.join(directory, out_name)
    typ_path = os.path.join(directory, PREVIEW_TYP_NAME)
    with open(src_path, 'w', encoding='utf-8') as handle:
        handle.write(source_text)

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    ok = False
    with COMPILE_LOCK, \
            contextlib.redirect_stdout(stdout_buf), \
            contextlib.redirect_stderr(stderr_buf):
        try:
            ok = bool(compile_ezmath(src_path, out_path,
                                     format=fmt, ppi=ppi))
        except BaseException as exc:  # never let preview wedge the panel
            print(f'[ERROR] Preview failed: {exc}')
            ok = False
    log = (stdout_buf.getvalue() + stderr_buf.getvalue()).strip()
    # Collect outputs: single file, or stem-1.ext … for multi-page PNG/SVG
    # (see pipeline._run_typst_export which uses stem-{p}.ext).
    files = []
    if ok:
        import glob
        if os.path.isfile(out_path):
            files = [out_path]
        elif fmt in ('png', 'svg'):
            stem, ext = os.path.splitext(out_path)
            cands = sorted(glob.glob(f'{stem}-*{ext}'))
            files = [c for c in cands if os.path.isfile(c)]
            if not files:
                ok = False
        else:
            ok = False
    found = files[0] if files else None
    pdf = found if (fmt == 'pdf' and found) else None
    return {'ok': bool(found and ok), 'file': found, 'files': files,
            'pdf': pdf or found, 'typ': typ_path, 'log': log, 'format': fmt}


def export_source_to_file(source_text, output_path, format=None, ppi=None):
    """Export *source_text* (ezmath) straight to *output_path*.

    Used by ``File → Export As…`` for untitled documents (no save needed).
    *format* defaults to the output extension. Returns the same dict as
    :func:`compile_source_to_format` plus ``'output'``/``'outputs'``.
    Multi-page PNG/SVG writes ``stem-1.ext``, ``stem-2.ext`` … next to
    the chosen file (or ``{p}`` pattern when the chosen name contains it).
    """
    import tempfile
    import shutil

    fmt = format
    if fmt is None and output_path:
        from compiler.pipeline import infer_export_format
        fmt = infer_export_format(output_path, None)
    fmt = (str(fmt or 'pdf').strip().lower().lstrip('.') or 'pdf')
    if fmt == 'htm':
        fmt = 'html'
    workdir = tempfile.mkdtemp(prefix='easymath-export-')
    try:
        res = compile_source_to_format(source_text, workdir,
                                       format=fmt, ppi=ppi)
        if not res.get('ok') or not res.get('files'):
            res['output'] = None
            res['outputs'] = []
            return res
        import glob  # noqa: F401 (kept for symmetry; files already listed)
        src_files = list(res.get('files') or [])
        dst_abs = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(dst_abs) or '.', exist_ok=True)
        if fmt in ('png', 'svg') and len(src_files) > 1:
            dst_stem, dst_ext = os.path.splitext(dst_abs)
            if '{p}' in dst_abs:
                dst_pattern = dst_abs
            else:
                dst_pattern = f'{dst_stem}-{{p}}{dst_ext}'
            outs = []
            for idx, sib in enumerate(src_files, start=1):
                dst = dst_pattern.replace('{p}', str(idx))
                os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
                shutil.copyfile(sib, dst)
                outs.append(dst)
            res['output'] = outs[0] if outs else None
            res['outputs'] = outs
            res['file'] = res['output']
            return res
        # Single file (pdf/html/typ/single-page image).
        shutil.copyfile(src_files[0], dst_abs)
        res['output'] = dst_abs
        res['outputs'] = [dst_abs]
        res['file'] = dst_abs
        return res
    finally:
        import shutil
        shutil.rmtree(workdir, ignore_errors=True)
