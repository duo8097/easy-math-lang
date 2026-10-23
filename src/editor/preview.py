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
PREVIEW_SMAP_NAME = 'preview.smap.json'


def preview_smap_path(workdir):
    """Absolute sidecar map path for the preview workdir (may not exist)."""
    import os as _os

    return _os.path.join(ensure_workdir(workdir), PREVIEW_SMAP_NAME)


def ensure_workdir(workdir):
    """Create *workdir* (and parents) and return its absolute path."""
    path = os.path.abspath(workdir)
    os.makedirs(path, exist_ok=True)
    return path


def compile_source_to_pdf(source_text, workdir, version=None, source_links=False,
                          source_path=None):
    """Compile *source_text* to a preview PDF inside *workdir*.

    Writes ``preview.ezmath`` then reuses
    :func:`compiler.pipeline.compile_ezmath` so preview output matches
    ``Build → Compile`` exactly (variables, calc, geometry, Typst).

    When *source_links* is true, mapped Typst blocks are wrapped in
    ``eml-src://`` link annotations (see :mod:`compiler.source_links`)
    for preview click-to-source navigation; the rendered appearance is
    unchanged. Export builds keep this off so distributed PDFs stay clean.

    Returns a dict: ``{'ok': bool, 'pdf': str|None, 'typ': str,
    'log': str}``. ``pdf`` is set only when compilation succeeded and
    the file exists. ``log`` captures the compiler's stdout/stderr so
    the panel can show the failure reason without a modal dialog.
    """
    return compile_source_to_format(
        source_text, workdir, format='pdf', version=version,
        source_links=source_links, source_path=source_path,
    )


def compile_source_to_format(source_text, workdir, format='pdf',
                             version=None, ppi=None, source_links=False,
                             source_path=None):
    """Compile *source_text* to *format* (pdf/png/svg/html/typ) in *workdir*.

    Headless helper shared by the live preview (pdf) and
    ``File → Export As…`` (any format). No Qt dependency.
    Returns ``{'ok', 'file', 'files', 'pdf', 'typ', 'smap', 'log', 'format'}``:
    ``file`` is the first exported path (``pdf`` kept as an alias for
    preview callers); ``files`` lists every page for multi-page PNG/SVG;
    ``smap`` is the sidecar source-map path when the compiler wrote one
    (else ``None``; missing map never fails the build).
    """
    # Include source writes and output discovery in the critical section;
    # locking only the compiler lets another request replace its input.
    with COMPILE_LOCK:
        return _compile_source_to_format(
            source_text, workdir, format, version, ppi, source_links,
            source_path=source_path)


def _compile_source_to_format(source_text, workdir, format='pdf',
                              version=None, ppi=None, source_links=False,
                              stem='preview', source_path=None):
    from compiler.pipeline import compile_ezmath

    directory = ensure_workdir(workdir)
    try:
        suffix = f'-{int(version)}' if version is not None else ''
    except (TypeError, ValueError):
        suffix = ''
    fmt = str(format or 'pdf').strip().lower().lstrip('.')
    if fmt == 'htm':
        fmt = 'html'
    if fmt == 'typst':
        fmt = 'typ'
    # Allowlist: fmt feeds preview.{fmt} inside workdir — a raw fmt
    # like '../evil' would escape via os.path.join.
    if fmt not in ('pdf', 'png', 'svg', 'html', 'typ'):
        fmt = 'pdf'
    src_path = os.path.join(directory, f'{stem}.ezmath')
    out_name = f'{stem}{suffix}.{fmt}'
    out_path = os.path.join(directory, out_name)
    typ_path = os.path.join(directory, f'{stem}.typ')
    with open(src_path, 'w', encoding='utf-8') as handle:
        handle.write(source_text)

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    ok = False
    # A workdir is reused across edits. Remove only the exact output and
    # numbered page siblings owned by this render before compiling again.
    import re
    page_stem, page_ext = os.path.splitext(out_name)
    page_re = re.compile(re.escape(page_stem) + r'-(\d+)' + re.escape(page_ext))
    for name in os.listdir(directory):
        if name == out_name or (fmt in ('png', 'svg') and page_re.fullmatch(name)):
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                os.remove(path)
    with contextlib.redirect_stdout(stdout_buf), \
            contextlib.redirect_stderr(stderr_buf):
        try:
            ok = bool(compile_ezmath(src_path, out_path,
                                     format=fmt, ppi=ppi,
                                     image_base_dir=(os.path.dirname(os.path.abspath(source_path))
                                                     if source_path else None),
                                     embed_source_links=bool(source_links)))
        except BaseException as exc:  # never let preview wedge the panel
            print(f'[ERROR] Preview failed: {exc}')
            ok = False
    log = (stdout_buf.getvalue() + stderr_buf.getvalue()).strip()
    # Collect outputs: single file, or stem-1.ext … for multi-page PNG/SVG
    # (see pipeline._run_typst_export which uses stem-{p}.ext).
    files = []
    if ok:
        if os.path.isfile(out_path):
            files = [out_path]
        elif fmt in ('png', 'svg'):
            pages = []
            for name in os.listdir(directory):
                match = page_re.fullmatch(name)
                path = os.path.join(directory, name)
                if match and os.path.isfile(path):
                    pages.append((int(match.group(1)), path))
            files = [path for _, path in sorted(pages)]
            if not files:
                ok = False
        else:
            ok = False
    found = files[0] if files else None
    pdf = found if (fmt == 'pdf' and found) else None
    # Sidecar source map: compiler writes <base>.smap.json next to the
    # .typ; preview.typ -> preview.smap.json. Copy to the stable
    # PREVIEW_SMAP_NAME so versioned outputs share one lookup path.
    smap = None
    try:
        from compiler.source_map import default_map_path
        _auto = default_map_path(typ_path)
        _stable = os.path.join(directory, f'{stem}.smap.json')
        if os.path.isfile(_auto):
            try:
                import shutil as _shutil
                if os.path.abspath(_auto) != os.path.abspath(_stable):
                    _shutil.copyfile(_auto, _stable)
            except OSError:
                _stable = _auto
            smap = _stable
        elif os.path.isfile(_stable):
            smap = _stable
    except Exception:
        smap = None
    return {'ok': bool(found and ok), 'file': found, 'files': files,
            'pdf': pdf or found, 'typ': typ_path, 'smap': smap,
            'log': log, 'format': fmt}


def resolve_typ_to_eml(smap_path, typ_line, typ_column):
    """Generated-Typ (0-based) -> ``SourceSpan`` or ``None`` (Qt-free).

    *smap_path* is a sidecar JSON path from :func:`compile_source_to_format`
    (``result['smap']``) or ``compiler.source_map.default_map_path(typ)``.
    Returns ``None`` when the map is missing/unreadable or the location
    is unmapped (headers, ``#v()`` separators). Never raises.
    """
    try:
        from compiler.source_map import TypstSourceMap
    except Exception:
        return None
    try:
        if not smap_path or not os.path.isfile(smap_path):
            return None
        return TypstSourceMap.load(smap_path).resolve(typ_line, typ_column)
    except Exception:
        return None


def export_source_to_file(source_text, output_path, format=None, ppi=None,
                           source_path=None):
    """Export *source_text* (ezmath) straight to *output_path*.

    Used by ``File → Export As…`` for untitled documents (no save needed).
    *format* defaults to the output extension. Returns the same dict as
    :func:`compile_source_to_format` plus ``'output'``/``'outputs'``.
    Multi-page PNG/SVG writes ``stem-1.ext``, ``stem-2.ext`` … next to
    the chosen file (or ``{p}`` pattern when the chosen name contains it).
    """
    import tempfile
    import shutil

    if source_path:
        from compiler.pipeline import _paths_alias
        if _paths_alias(source_path, output_path):
            return {'ok': False, 'output': None, 'outputs': [],
                    'log': '[Error] Output would overwrite input file'}

    fmt = format
    if fmt is None and output_path:
        from compiler.pipeline import infer_export_format
        fmt = infer_export_format(output_path, None)
    fmt = (str(fmt or 'pdf').strip().lower().lstrip('.') or 'pdf')
    if fmt == 'htm':
        fmt = 'html'
    if fmt == 'typst':
        fmt = 'typ'
    if fmt not in ('pdf', 'png', 'svg', 'html', 'typ'):
        fmt = 'pdf'
    workdir = tempfile.mkdtemp(prefix='easymath-export-')
    try:
        # Give diagrams a document-specific basename so exporting a second
        # document in the same folder cannot change the first one's images.
        asset_stem = os.path.splitext(os.path.basename(output_path))[0].replace('{p}', 'page')
        with COMPILE_LOCK:
            res = _compile_source_to_format(
                source_text, workdir, format=fmt, ppi=ppi, stem=asset_stem,
                source_path=source_path)
        if not res.get('ok') or not res.get('files'):
            res['output'] = None
            res['outputs'] = []
            return res
        import glob  # noqa: F401 (kept for symmetry; files already listed)
        src_files = list(res.get('files') or [])
        dst_abs = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(dst_abs) or '.', exist_ok=True)
        if fmt in ('png', 'svg') and (len(src_files) > 1 or '{p}' in dst_abs):
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
        if fmt in ('typ', 'html'):
            image_dir = os.path.join(workdir, asset_stem + '-images')
            if os.path.isdir(image_dir):
                shutil.copytree(image_dir, os.path.join(os.path.dirname(dst_abs),
                                                      asset_stem + '-images'),
                                dirs_exist_ok=True)
            for name in os.listdir(workdir):
                if (name.startswith(asset_stem + '-plot-')
                        and name.endswith('.svg')):
                    shutil.copyfile(os.path.join(workdir, name),
                                    os.path.join(os.path.dirname(dst_abs), name))
        res['output'] = dst_abs
        res['outputs'] = [dst_abs]
        res['file'] = dst_abs
        return res
    finally:
        import shutil
        shutil.rmtree(workdir, ignore_errors=True)
