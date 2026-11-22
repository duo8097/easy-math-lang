#!/usr/bin/env python3
"""Regenerate the tables of contents in the documentation.

Finds the ``<!-- toc -->`` ... ``<!-- /toc -->`` markers in a Markdown
file and replaces everything between them with a list of links built
from the file's ``##`` and ``###`` headings (the document's H1 is
skipped, headings inside fenced code blocks are skipped, and ``###``
headings are indented under their ``##``).

Anchors are GitHub-compatible: lowercased, punctuation stripped,
spaces turned into hyphens, and duplicate headings get ``-1``,
``-2`` ... suffixes. Inline code, links and non-ASCII text in
headings are handled correctly.

Usage:
    python3 scripts/gen_toc.py [files...]
    python3 scripts/gen_toc.py --check

Without arguments every ``docs/*.md`` that already contains the markers
is rewritten in place. With explicit file arguments those files are
rewritten in place too (markers are inserted right after the intro
paragraph when missing). ``--check`` makes no changes, prints the stale
files and exits 1 when any of them is out of date.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parents[1] / 'docs'

OPEN_MARKER = '<!-- toc -->'
CLOSE_MARKER = '<!-- /toc -->'

_HEADING_RE = re.compile(r'^(#{2,3})\s+(.+)$')
_CLOSING_HASHES_RE = re.compile(r'\s+#+\s*$')
_FENCE_RE = re.compile(r'^(`{3}|~{3})')
_INLINE_CODE_RE = re.compile(r'`[^`]*`')
_LINK_RE = re.compile(r'\[([^\]]*)\]\([^)]*\)')
_HTML_TAG_RE = re.compile(r'<[^>]+>')
#: GitHub keeps letters (incl. non-ASCII), digits, spaces and hyphens;
#: everything else is punctuation and is stripped.
_PUNCT_RE = re.compile(r'[^\w\s-]', re.UNICODE)


def _clean_text(text: str) -> str:
    """Heading display text: inline code spans, links and HTML stripped."""
    text = _INLINE_CODE_RE.sub('', text)
    text = _LINK_RE.sub(r'\1', text)
    text = _HTML_TAG_RE.sub('', text)
    return text.strip()


def slug(text: str) -> str:
    """GitHub-compatible anchor for a heading text."""
    anchor = _PUNCT_RE.sub('', _clean_text(text).lower())
    anchor = anchor.strip().replace(' ', '-').strip('-')
    return anchor


def _collect_headings(text: str):
    """``[(level, display_text, anchor), ...]`` outside fenced blocks.

    Only ``##`` and ``###`` headings are returned (the H1 is skipped).
    Duplicate anchors get ``-1``, ``-2`` ... suffixes like on GitHub.
    """
    entries = []
    seen: dict[str, int] = {}
    in_fence = False
    for raw_line in text.split('\n'):
        line = raw_line.strip()
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if not match:
            continue
        heading = _CLOSING_HASHES_RE.sub('', match.group(2)).strip()
        if not heading:
            continue
        base = slug(heading)
        if not base:
            continue
        count = seen.get(base, 0) + 1
        seen[base] = count
        anchor = base if count == 1 else f'{base}-{count - 1}'
        entries.append((len(match.group(1)), heading, anchor))
    return entries


def _toc_lines(entries):
    """Render the collected headings as a nested markdown list."""
    lines = []
    saw_h2 = False
    for level, heading, anchor in entries:
        if level == 2:
            saw_h2 = True
            lines.append(f'- [{heading}](#{anchor})')
        else:  # level == 3: nest under the most recent ##
            if saw_h2:
                lines.append(f'  - [{heading}](#{anchor})')
            else:
                lines.append(f'- [{heading}](#{anchor})')
    return lines


def _marker_line_indices(lines):
    """Indices of the first ``<!-- toc -->`` and the first close after it."""
    open_at = close_at = None
    for i, line in enumerate(lines):
        if line.strip() == OPEN_MARKER:
            open_at = i
        elif line.strip() == CLOSE_MARKER and open_at is not None:
            close_at = i
            break
    return open_at, close_at


def _intro_paragraph_end(lines):
    """Line index right after the first paragraph below the document H1."""
    h1 = None
    for i, line in enumerate(lines):
        if line.startswith('#') and not line.startswith('##') and line[1:2] in (' ', ''):
            h1 = i
            break
    if h1 is None:
        return None
    n = len(lines)
    i = h1 + 1
    while i < n and lines[i].strip() == '':
        i += 1
    while i < n and lines[i].strip() != '':
        i += 1
    return i  # first blank line after the paragraph, or end of file


def _apply_markers(lines, toc_block_lines):
    open_at, close_at = _marker_line_indices(lines)
    if open_at is None:
        return None
    return lines[:open_at + 1] + toc_block_lines + lines[close_at:]


def _insert_markers(lines, toc_block_lines):
    at = _intro_paragraph_end(lines)
    if at is None:
        return None
    block = ['', OPEN_MARKER] + toc_block_lines + [CLOSE_MARKER, '']
    tail = lines[at + 1:] if at < len(lines) and lines[at].strip() == '' else lines[at:]
    return lines[:at] + block + tail


def generate_toc_for_file(text: str) -> str:
    """Return ``text`` with the TOC (re)generated between its markers.

    Files without markers get them inserted after the intro paragraph.
    """
    lines = text.split('\n')
    toc_block_lines = _toc_lines(_collect_headings(text))
    result = _apply_markers(lines, toc_block_lines)
    if result is None:
        result = _insert_markers(lines, toc_block_lines)
        if result is None:
            return text
    return '\n'.join(result)


def _has_markers(path: Path) -> bool:
    text = path.read_text(encoding='utf-8')
    return OPEN_MARKER in text and CLOSE_MARKER in text


def _default_files():
    return sorted(p for p in DOCS_DIR.glob('*.md') if _has_markers(p))


def process_file(path: Path, check: bool = False) -> bool:
    """Rewrite ``path`` in place. ``check`` only reports staleness.

    Returns True when the file is up to date (or was rewritten).
    """
    text = path.read_text(encoding='utf-8')
    expected = generate_toc_for_file(text)
    if check:
        if text != expected:
            print(f'stale: {path}')
            return False
        return True
    if text != expected:
        path.write_text(expected, encoding='utf-8')
    return True


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    check = '--check' in argv
    if check:
        argv.remove('--check')
    files = [Path(arg) for arg in argv] if argv else _default_files()
    ok = True
    for path in files:
        try:
            ok = process_file(path, check=check) and ok
        except OSError as exc:
            print(f'error: {path}: {exc}', file=sys.stderr)
            ok = False
    if check:
        print(
            'all tables of contents are up to date.'
            if ok else 'some tables of contents are stale.'
        )
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
