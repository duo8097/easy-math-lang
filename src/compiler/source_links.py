"""Source-link URL scheme for PDF-preview-to-source navigation.

When the compiler embeds source links (``compile_ezmath(...,
embed_source_links=True)``), each mapped Typst block is wrapped in::

    #link("eml-src://typ/<line>/<col>")[...content...]

Typst emits these as standard PDF ``/URI`` link annotations (verified:
``/A<</Type/Action/S/URI/URI(emlsrc://...)>>`` in the PDF bytes) without
changing the rendered appearance — Typst styles links exactly like
normal text unless a ``show link`` rule says otherwise, which the
compiler never adds.

``<line>``/``<col>`` are the 0-based generated-Typ position of the
block start (matching :class:`source_map.TypstSourceMap` coordinates).
The preview resolves them through the sidecar ``.smap.json`` and
navigates the editor to the original ``.eml`` span, so no line numbers
are ever hard-coded and no coordinates are guessed: the URL carries the
exact Typst location.

Qt-free: the editor layer reuses these helpers (see
``editor.preview.resolve_typ_to_eml`` and ``PreviewPanel``).

Note on Qt 6.11 (verified empirically): ``QPdfView`` routes *internal*
(GoTo/destination) link clicks through
``QPdfPageNavigator.jumped(QPdfLink)`` but stays silent for *external*
URI links — no ``jumped``, no ``QDesktopServices.openUrl``, no
``currentLink`` update. ``PreviewPanel`` therefore connects ``jumped``
*and* exposes a handler entry point so the full Typ→.eml→cursor chain
is wired and unit-tested; end-to-end clicks on ``eml-src`` links start
navigating as soon as the Qt PDF layer delivers external-link
activation.
"""

from __future__ import annotations

SCHEME = 'eml-src'
HOST = 'typ'


def make_source_url(typ_line: int, typ_column: int) -> str:
    """Build an ``eml-src://typ/<line>/<col>`` URL (0-based ints)."""
    try:
        line = int(typ_line)
        col = int(typ_column)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'invalid Typst position: {typ_line!r}, {typ_column!r}') from exc
    if line < 0 or col < 0:
        raise ValueError(f'Typst position must be >= 0: {line}, {col}')
    return f'{SCHEME}://{HOST}/{line}/{col}'


def parse_source_url(url) -> tuple[int, int] | None:
    """Parse *url* (str or QUrl-like) -> ``(typ_line, typ_col)`` or ``None``.

    Strict: exact ``eml-src`` scheme, ``typ`` host, precisely two
    non-negative integer path segments, no query/fragment/extra parts.
    Never raises.
    """
    try:
        text = url.toString() if hasattr(url, 'toString') else str(url)
    except Exception:
        return None
    try:
        text = text.strip()
        prefix = f'{SCHEME}://{HOST}/'
        if not text.startswith(prefix):
            return None
        rest = text[len(prefix):]
        # Reject query/fragment/extra segments (exact shape only).
        if not rest or any(c in rest for c in '?#'):
            return None
        parts = rest.split('/')
        if len(parts) != 2:
            return None
        if not parts[0] or not parts[1]:
            return None
        if not all(c in '0123456789' for c in parts[0] + parts[1]):
            return None
        return (int(parts[0]), int(parts[1]))
    except Exception:
        return None


def link_prefix(typ_line: int, typ_column: int) -> str:
    """Typst ``#link("...")[`` opener pinning a block to a Typ position."""
    return f'#link("{make_source_url(typ_line, typ_column)}")['
