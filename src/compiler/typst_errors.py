"""Typst-failure diagnostics mapped back to the .ezmath source.

When the ``typst`` backend fails with an error whose message carries a
position in the intermediate ``.typ`` (e.g. ``┌─ doc.typ:7:0`` inside a
pretty-printed ``TypstError.diagnostic``) and that position resolves
through the sidecar source map, the failure is reported with the same
Python-style context block the compiler uses for its own diagnostics:

    [ERROR] Typst compilation failed: unclosed delimiter
      File "bai1.ezmath", line 2
        Second line here

The classic first line is byte-identical to the legacy output; only the
context block is added. When the position cannot be extracted or mapped
(no map this build, position outside our ``.typ``, or out of range),
:func:`try_report_typst_error` returns ``False`` and the caller falls
back to the legacy ``[ERROR] Typst compilation failed: ...`` output
untouched.
"""

import os
import re
import sys

from . import diagnostics as _diagnostics

# Position inside the intermediate .typ as printed by Typst, e.g.
# ``┌─ doc.typ:12:5`` (the line is 1-based; the column is 0-based in
# current Typst — a 1-based column is accepted as a fallback probe).
_TYP_LOC_RE = re.compile(r'([^\s:()][^\s:()]*?\.(?:typ|typst)):(\d+):(\d+)')


def _same_file(candidate, typ_file):
    try:
        if os.path.abspath(candidate) == os.path.abspath(typ_file):
            return True
    except (TypeError, ValueError, OSError):
        pass
    try:
        return os.path.basename(candidate) == os.path.basename(typ_file)
    except (TypeError, ValueError):
        return False


def _resolve_span(typ_source_map, typ_file, typ_line, typ_col):
    smap = typ_source_map
    if smap is None:
        try:
            from .source_map import TypstSourceMap, default_map_path
            smap = TypstSourceMap.load(default_map_path(typ_file))
        except Exception:
            return None
    try:
        return smap.resolve(typ_line, typ_col)
    except Exception:
        return None


def report_with_context(severity, message, *, line_no, col=None, end_col=None):
    """Print ``[severity] message`` then the context block for *line_no*.

    The first line has no ``Line N:`` marker, keeping it byte-identical
    to the legacy ``[ERROR] Typst compilation failed: ...`` output.
    """
    try:
        print(f'[{severity}] {message}', file=sys.stderr)
    except Exception:
        return
    try:
        _diagnostics._print_source_context(severity, line_no, col, end_col)
    except Exception:
        # A broken context block must never break the build.
        pass


def try_report_typst_error(exc, *, typ_file, typ_source_map=None):
    """Render a Typst failure mapped back to the .ezmath line.

    Returns ``True`` when the error carried a position inside *typ_file*
    and the source map resolved it to an .ezmath span — the existing
    first line is printed together with the context block. Returns
    ``False`` when there is no usable position or mapping, so the
    caller can fall back to the legacy ``[ERROR] Typst compilation
    failed: ...`` output untouched.
    """
    ctx = _diagnostics._active_ctx
    if ctx is None:
        return False
    texts = [str(exc)]
    diagnostic = getattr(exc, 'diagnostic', None)
    if diagnostic:
        texts.append(str(diagnostic))
    for text in texts:
        for match in _TYP_LOC_RE.finditer(text):
            path, line_s, col_s = match.groups()
            if not _same_file(path, typ_file):
                continue
            try:
                typ_line = int(line_s) - 1
                typ_col = int(col_s)
            except (TypeError, ValueError):
                continue
            if typ_line < 0:
                continue
            span = _resolve_span(typ_source_map, typ_file, typ_line, typ_col)
            if span is None and typ_col > 0:
                # Some Typst versions print 1-based columns.
                span = _resolve_span(typ_source_map, typ_file,
                                     typ_line, typ_col - 1)
            if span is None:
                continue
            eml_line = span.start.line + 1
            if _diagnostics._active_source_line(ctx, eml_line) is None:
                return False
            col = span.start.column + 1
            if span.start.column == 0:
                # Full-line spans (the common case in the sidecar map)
                # carry no intra-line information.
                col = None
            if span.end.line == span.start.line:
                end_col = span.end.column + 1
            else:
                end_col = None
            try:
                message = str(exc)
            except Exception:
                message = repr(exc)
            report_with_context(
                'ERROR', f'Typst compilation failed: {message}',
                line_no=eml_line, col=col, end_col=end_col)
            return True
    return False
