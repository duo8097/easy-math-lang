"""PDF URI-link annotation enumeration (Qt-free, stdlib only).

Typst-generated PDFs use classic cross-reference tables (no object
streams) with plain ``/Type/Annot/Subtype/Link`` objects carrying
``/Rect[...]`` (PDF points, bottom-left origin) and
``/A<</Type/Action/S/URI/URI(...)>>``. This module extracts exactly
that: ``(page_index, rect, uri)`` triples for the preview's
Ctrl+Click hit-testing.

Design notes:

- No third-party PDF dependency: the needed subset (object scan,
  FlateDecode inflate, Pages-tree walk, Annots arrays, Rect/URI parse)
  is small and fully covered by tests. A general PDF library would be
  justified only if Typst switched to compressed object streams *and*
  the fallback below proved insufficient.
- Graceful degradation: anything unparseable (streams with unsupported
  filters, missing xref, encrypted files) yields fewer (or zero)
  entries — a missed click simply does nothing instead of navigating
  somewhere wrong. This function never raises on malformed input.
- Coordinate handling lives with the caller: rects stay in raw PDF
  points; see ``PreviewPanel.page_point_at`` for the viewport mapping.
"""

from __future__ import annotations

import re
import zlib


# Top-level indirect objects: "12 0 obj ... endobj" (gen numbers other
# than 0 are accepted but rare in practice).
_OBJ_RE = re.compile(rb'(\d+)\s+(\d+)\s+obj(.*?)endobj', re.S)
# Reference: "12 0 R".
_REF_RE = re.compile(rb'(\d+)\s+(\d+)\s+R')
# Name token: "/Type/Annot" vs "/Type/Annotations" — negative lookahead
# keeps us on exact tokens.
_NAME_RE_CACHE: dict[str, re.Pattern] = {}


def _name_re(name: bytes) -> re.Pattern:
    key = name.decode('latin-1')
    pat = _NAME_RE_CACHE.get(key)
    if pat is None:
        pat = re.compile(rb'/' + re.escape(name) + rb'(?![A-Za-z0-9])')
        _NAME_RE_CACHE[key] = pat
    return pat


def _parse_object_map(data: bytes) -> dict[tuple[int, int], bytes]:
    """Map ``(number, generation)`` -> object body (streams inflated)."""
    objects: dict[tuple[int, int], bytes] = {}
    for match in _OBJ_RE.finditer(data):
        num, gen, body = int(match.group(1)), int(match.group(2)), match.group(3)
        # Split header dict from an optional stream payload.
        head, sep, rest = body.partition(b'stream')
        header = head if sep else body
        if b'/Filter' in header and sep:
            payload, _, _ = rest.partition(b'endstream')
            payload = payload.strip(b'\r\n')
            inflated = _try_inflate(header, payload)
            if inflated is not None:
                objects[(num, gen)] = inflated
                continue
            # Unsupported filter: keep the header dict (may still hold
            # the keys we need for non-stream objects; harmless else).
            objects[(num, gen)] = header
        else:
            objects[(num, gen)] = header if not sep else header
    return objects


def _try_inflate(header: bytes, payload: bytes) -> bytes | None:
    """Inflate a stream payload honoring a FlateDecode filter chain."""
    try:
        filters = re.findall(rb'/Filter\s*(?:\[(.*?)\]|/([A-Za-z0-9]+))', header, re.S)
        chain: list[bytes] = []
        for bracket, single in filters:
            if bracket:
                chain.extend(re.findall(rb'/([A-Za-z0-9]+)', bracket))
            elif single:
                chain.append(single)
        if not chain:
            return None
        out = payload
        for name in chain:
            if name == b'FlateDecode':
                out = zlib.decompress(out)
            else:
                return None
        return out
    except Exception:
        return None


def _resolve_ref(objects: dict, num: int, gen: int) -> bytes | None:
    body = objects.get((num, gen))
    if body is None and gen != 0:
        # Generation mismatch tolerance: typst uses generation 0, but be
        # lenient for hand-built files.
        for (n, _g), text in objects.items():
            if n == num:
                return text
    return body


def _kids_in_order(objects: dict, pages_num: int, pages_gen: int) -> list[tuple[int, int]]:
    """Page object refs in document order (recursive Pages-tree walk)."""
    ordered: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    def _walk(num: int, gen: int) -> None:
        key = (num, gen)
        if key in seen:
            return
        seen.add(key)
        body = _resolve_ref(objects, num, gen)
        if body is None:
            return
        if _name_re(b'Page').search(body) and not re.search(
                rb'/Type\s*/Pages(?![A-Za-z0-9])', body):
            ordered.append(key)
            return
        kids = re.search(rb'/Kids\s*\[(.*?)\]', body, re.S)
        if not kids:
            return
        for ref in _REF_RE.finditer(kids.group(1)):
            _walk(int(ref.group(1)), int(ref.group(2)))

    _walk(pages_num, pages_gen)
    return ordered


def _find_pages_root(objects: dict) -> tuple[int, int] | None:
    for (num, gen), body in objects.items():
        if re.search(rb'/Type\s*/Pages(?![A-Za-z0-9])', body):
            return (num, gen)
    return None


def _annots_refs(page_body: bytes) -> list[tuple[str, tuple[int, int] | bytes]]:
    """Annots entries as ('ref', (num, gen)) or ('dict', raw_dict_bytes)."""
    m = re.search(rb'/Annots\s*(\[(.*?)\]|(\d+)\s+(\d+)\s+R)', page_body, re.S)
    if not m:
        return []
    out: list[tuple[str, tuple[int, int] | bytes]] = []
    if m.group(2) is not None:
        inner = m.group(2)
        pos = 0
        for ref in _REF_RE.finditer(inner):
            out.append(('ref', (int(ref.group(1)), int(ref.group(2)))))
            pos = ref.end()
        # Direct dicts inside the array (rare): balanced <<...>> spans.
        for dstart in _dict_spans(inner):
            # Skip dicts already covered by refs (approx: dicts contain /Rect).
            if b'/Rect' in inner[dstart[0]:dstart[1]]:
                out.append(('dict', inner[dstart[0]:dstart[1]]))
    else:
        out.append(('arrayref', (int(m.group(3)), int(m.group(4)))))
    return out


def _dict_spans(buf: bytes) -> list[tuple[int, int]]:
    """Balanced ``<<...>>`` spans (naive nesting counter, no strings)."""
    spans: list[tuple[int, int]] = []
    depth = 0
    start = -1
    i = 0
    while i < len(buf) - 1:
        pair = buf[i:i + 2]
        if pair == b'<<':
            if depth == 0:
                start = i
            depth += 1
            i += 2
        elif pair == b'>>':
            if depth > 0:
                depth -= 1
                if depth == 0 and start != -1:
                    spans.append((start, i + 2))
                    start = -1
            i += 2
        else:
            i += 1
    return spans


def _parse_rect(text: bytes) -> tuple[float, float, float, float] | None:
    m = re.search(rb'/Rect\s*\[\s*([^\]]*?)\s*\]', text)
    if not m:
        return None
    try:
        nums = [float(x) for x in re.findall(rb'[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?',
                                             m.group(1))]
    except ValueError:
        return None
    if len(nums) != 4:
        return None
    x0, y0, x1, y1 = nums
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _parse_uri(text: bytes) -> str | None:
    # Note: `/S/URI` (action subtype) precedes the real `/URI(...)` value,
    # so scan every candidate and take the first followed by (literal) or
    # <hex>.
    for m in re.finditer(rb'/URI', text):
        tail = text[m.end():].lstrip()
        if not tail.startswith((b'(', b'<')):
            continue
        if tail.startswith(b'('):
            # Literal string with \( \) \\ escapes.
            out: list[bytes] = []
            i = 1
            closed = False
            while i < len(tail):
                ch = tail[i:i + 1]
                if ch == b'\\' and i + 1 < len(tail):
                    nxt = tail[i + 1:i + 2]
                    out.append(nxt)  # \( \) \\ (and \n etc: raw char)
                    i += 2
                elif ch == b')':
                    closed = True
                    break
                else:
                    out.append(ch)
                    i += 1
            if not closed:
                continue
            try:
                return b''.join(out).decode('utf-8', errors='replace')
            except Exception:
                return None
        if tail.startswith(b'<'):
            end = tail.find(b'>')
            if end == -1:
                continue
            try:
                cleaned = re.sub(rb'\s+', b'', tail[1:end])
                if len(cleaned) % 2 == 1:
                    cleaned += b'0'
                raw = bytes.fromhex(cleaned.decode('latin-1'))
                return raw.decode('utf-8', errors='replace')
            except Exception:
                return None
    return None


def _is_link_annot(text: bytes) -> bool:
    return _name_re(b'Annot').search(text) is not None and re.search(
        rb'/Subtype\s*/Link(?![A-Za-z0-9])', text) is not None


def extract_link_annotations(data: bytes) -> list[tuple[int, tuple[float, float, float, float], str]]:
    """Enumerate URI link annotations: ``[(page, rect, uri), ...]``.

    *page* is 0-based in document order; *rect* is ``(x0, y0, x1, y1)``
    in PDF points (bottom-left origin); *uri* is the decoded action URI.
    Non-URI (GoTo) annotations are skipped. Never raises: malformed
    input yields ``[]`` (or a partial list).
    """
    try:
        if not isinstance(data, (bytes, bytearray)) or len(data) < 9:
            return []
        raw = bytes(data)
        if not raw.lstrip().startswith(b'%PDF-'):
            return []
        objects = _parse_object_map(raw)
        if not objects:
            return []
        root = _find_pages_root(objects)
        if root is None:
            return []
        pages = _kids_in_order(objects, root[0], root[1])
        if not pages:
            return []
        found: list[tuple[int, tuple[float, float, float, float], str]] = []
        for page_index, (pnum, pgen) in enumerate(pages):
            page_body = _resolve_ref(objects, pnum, pgen)
            if page_body is None:
                continue
            for kind, payload in _annots_refs(page_body):
                bodies: list[bytes] = []
                if kind == 'ref':
                    num, gen = payload  # type: ignore[misc]
                    body = _resolve_ref(objects, num, gen)
                    if body is not None:
                        bodies.append(body)
                elif kind == 'dict':
                    bodies.append(payload)  # type: ignore[arg-type]
                elif kind == 'arrayref':
                    num, gen = payload  # type: ignore[misc]
                    arr = _resolve_ref(objects, num, gen)
                    if arr is not None:
                        inner = re.search(rb'\[(.*)\]', arr, re.S)
                        seq = inner.group(1) if inner else b''
                        for ref in _REF_RE.finditer(seq):
                            body = _resolve_ref(objects, int(ref.group(1)),
                                                int(ref.group(2)))
                            if body is not None:
                                bodies.append(body)
                for body in bodies:
                    try:
                        if not _is_link_annot(body):
                            continue
                        rect = _parse_rect(body)
                        uri = _parse_uri(body)
                        if rect is None or not uri:
                            continue
                        found.append((page_index, rect, uri))
                    except Exception:
                        continue
        return found
    except Exception:
        return []


def extract_link_annotations_from_file(path) -> list[tuple[int, tuple[float, float, float, float], str]]:
    """Read *path* and enumerate URI link annotations ([] on any failure)."""
    try:
        with open(path, 'rb') as fh:
            return extract_link_annotations(fh.read())
    except Exception:
        return []


def hit_test(rect: tuple[float, float, float, float], x: float, y: float,
             epsilon: float = 0.5) -> bool:
    """True when point ``(x, y)`` lies in *rect* (PDF points, ±*epsilon*)."""
    try:
        x0, y0, x1, y1 = (float(rect[0]), float(rect[1]),
                          float(rect[2]), float(rect[3]))
        x, y, eps = float(x), float(y), abs(float(epsilon))
        return (x0 - eps) <= x <= (x1 + eps) and (y0 - eps) <= y <= (y1 + eps)
    except (TypeError, ValueError, IndexError):
        return False
