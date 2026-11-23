#!/usr/bin/env python3
"""Check local Markdown links used by the project's documentation.

The checker reads the repository README, CONTRIBUTING guide, Markdown files
in ``docs/``, and package READMEs in ``src/``. It reports missing local files
and missing heading anchors. Web and email links are deliberately skipped.

Usage:
    python scripts/check_links.py
"""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
_FENCE_RE = re.compile(r'^\s*(`{3}|~{3})')
_HEADING_RE = re.compile(r'^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$')
_LINK_RE = re.compile(r'!?\[[^\]]*\]\(([^)\s]+)(?:\s+["\'][^)]*)?\)')
_EXTERNAL_PREFIXES = ('http://', 'https://', 'mailto:')


def _load_slug():
    """Load the shared GitHub-style heading-slug function."""
    path = ROOT / 'scripts' / 'gen_toc.py'
    spec = importlib.util.spec_from_file_location('gen_toc', path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.slug


slug = _load_slug()


@dataclass(frozen=True)
class LinkProblem:
    """One broken link, ready to print in compiler-style ``file:line`` form."""

    path: Path
    line: int
    link: str
    reason: str

    def __str__(self) -> str:
        return f'{self.path}:{self.line}: {self.link} -- {self.reason}'


def anchors_in(text: str) -> set[str]:
    """Return all GitHub-style heading anchors outside fenced code blocks."""
    anchors = set()
    seen: dict[str, int] = {}
    in_fence = False
    for line in text.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if match is None:
            continue
        base = slug(match.group(1))
        if not base:
            continue
        count = seen.get(base, 0)
        seen[base] = count + 1
        anchors.add(base if count == 0 else f'{base}-{count}')
    return anchors


def links_in(text: str):
    """Yield ``(line_number, destination)`` pairs outside fenced code blocks."""
    in_fence = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in _LINK_RE.finditer(line):
            yield line_number, unquote(match.group(1))


def check_file(path: Path) -> list[LinkProblem]:
    """Return broken relative links in one Markdown ``path``."""
    text = path.read_text(encoding='utf-8')
    problems = []
    for line, destination in links_in(text):
        if destination.lower().startswith(_EXTERNAL_PREFIXES):
            continue
        target_text, separator, anchor = destination.partition('#')
        target = path if not target_text else (path.parent / target_text).resolve()
        if not target.is_file():
            problems.append(LinkProblem(path, line, destination, 'file does not exist'))
            continue
        if separator:
            target_anchors = anchors_in(target.read_text(encoding='utf-8'))
            if anchor not in target_anchors:
                problems.append(
                    LinkProblem(path, line, destination, 'anchor does not exist')
                )
    return problems


def documentation_files(root: Path = ROOT) -> list[Path]:
    """Return the Markdown files that are part of the checked documentation."""
    files = [root / 'README.md', root / 'CONTRIBUTING.md']
    files.extend(sorted((root / 'docs').glob('*.md')))
    files.extend(sorted((root / 'src').glob('*/README.md')))
    return [path for path in files if path.is_file()]


def check_files(paths) -> list[LinkProblem]:
    """Return every problem found in the supplied Markdown files."""
    return [problem for path in paths for problem in check_file(path)]


def main() -> int:
    """Print link problems and return a nonzero status when any exist."""
    problems = check_files(documentation_files())
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print('all checked Markdown links are valid.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
