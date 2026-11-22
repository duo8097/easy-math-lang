"""Tests for ``scripts/gen_toc.py``: the anchor generator and the
``--check`` CI gate that keeps the docs' tables of contents up to date.

Runs the real script as a subprocess for the ``--check`` exit-code
tests, the same way ``tests/test_site.py`` loads ``scripts/check_site.py``.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GEN_TOC = ROOT / 'scripts' / 'gen_toc.py'
DOCS = ROOT / 'docs'


def _load_gen_toc():
    spec = importlib.util.spec_from_file_location('gen_toc', GEN_TOC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def gen_toc():
    if not GEN_TOC.is_file():
        pytest.skip('scripts/gen_toc.py not present')
    return _load_gen_toc()


# ------------------------------------------------------------------
# Anchor generation

def test_slug_is_lowercase_with_spaces_to_hyphens(gen_toc):
    assert gen_toc.slug('Option A — Windows installer (easiest)') == (
        'option-a--windows-installer-easiest')
    assert gen_toc.slug('Under the hood: helper programs') == (
        'under-the-hood-helper-programs')


def test_duplicate_headings_get_suffixes(gen_toc):
    text = '# Title\n\n## Foo\n\n## Foo\n\n## Foo\n'
    entries = gen_toc._collect_headings(text)
    assert [anchor for _, _, anchor in entries] == ['foo', 'foo-1', 'foo-2']


def test_headings_inside_fenced_code_blocks_are_skipped(gen_toc):
    text = (
        '# Title\n'
        '\n'
        '```\n## Not a real heading\n```\n'
        '\n'
        '~~~\n### Also skipped\n~~~\n'
        '\n'
        '## Real heading\n'
        '### Nested under real\n'
    )
    entries = gen_toc._collect_headings(text)
    assert [(level, heading, anchor)
            for level, heading, anchor in entries] == [
        (2, 'Real heading', 'real-heading'),
        (3, 'Nested under real', 'nested-under-real'),
    ]


def test_slug_strips_inline_code_links_and_html(gen_toc):
    assert gen_toc.slug('Run `uv sync` now') == 'run--now'
    assert gen_toc.slug('See [Installation](installation.md)') == 'see-installation'
    assert gen_toc.slug('<b>Bold</b> heading') == 'bold-heading'


def test_slug_keeps_non_ascii_vietnamese(gen_toc):
    assert gen_toc.slug('Linux: input methods (Vietnamese etc.)') == (
        'linux-input-methods-vietnamese-etc')
    assert gen_toc.slug('Chính sách bảo mật') == 'chính-sách-bảo-mật'


def test_toc_skips_h1_nests_subsections(gen_toc):
    text = (
        '# Title\n'
        '\n'
        'Intro paragraph.\n'
        '\n'
        '## Alpha\n'
        '### Alpha One\n'
        '### Alpha Two\n'
        '\n'
        '## Beta (with `code`)\n'
        '### Beta One\n'
    )
    block = gen_toc.generate_toc_for_file(text)
    assert '<!-- toc -->' in block and '<!-- /toc -->' in block
    assert '- [Alpha](#alpha)' in block
    assert '  - [Alpha One](#alpha-one)' in block
    assert '  - [Alpha Two](#alpha-two)' in block
    assert '- [Beta (with `code`)](#beta-with)' in block
    assert '  - [Beta One](#beta-one)' in block
    # The document H1 must not appear in the TOC.
    assert not re.search(r'\[Title\]', block)


def test_closing_hashes_are_stripped(gen_toc):
    entries = gen_toc._collect_headings('# T\n\n## Atx ##\n')
    assert entries == [(2, 'Atx', 'atx')]


def test_orphan_subsection_without_section_is_top_level(gen_toc):
    entries = gen_toc._collect_headings('# T\n\n### Lone\n')
    assert entries == [(3, 'Lone', 'lone')]


# ------------------------------------------------------------------
# Idempotency

def test_generation_is_idempotent(gen_toc):
    text = (
        '# Title\n'
        '\n'
        'Intro paragraph.\n'
        '\n'
        '<!-- toc -->\n'
        '<!-- /toc -->\n'
        '\n'
        '## Section\n'
        '### Subsection\n'
    )
    once = gen_toc.generate_toc_for_file(text)
    twice = gen_toc.generate_toc_for_file(once)
    assert once == twice


# ------------------------------------------------------------------
# --check exit code (the CI gate)

def run_check(*files):
    return subprocess.run(
        [sys.executable, str(GEN_TOC), '--check', *map(str, files)],
        capture_output=True, text=True,
    )


def test_check_exits_one_when_toc_is_stale(tmp_path):
    md = tmp_path / 'doc.md'
    md.write_text(
        '# Title\n'
        '\n'
        '<!-- toc -->\n'
        '- [Wrong](#wrong)\n'
        '<!-- /toc -->\n'
        '\n'
        '## Real\n'
    )
    completed = run_check(md)
    assert completed.returncode == 1
    assert str(md) in completed.stdout
    assert 'stale' in completed.stdout


def test_check_exits_zero_when_toc_is_fresh(tmp_path):
    md = tmp_path / 'doc.md'
    md.write_text(
        '# Title\n'
        '\n'
        '<!-- toc -->\n'
        '- [Real](#real)\n'
        '<!-- /toc -->\n'
        '\n'
        '## Real\n'
    )
    completed = run_check(md)
    assert completed.returncode == 0


def test_check_inserts_markers_when_missing(gen_toc, tmp_path):
    md = tmp_path / 'doc.md'
    md.write_text('# Title\n\nIntro paragraph.\n\n## Section\n')
    result = gen_toc.generate_toc_for_file(md.read_text(encoding='utf-8'))
    assert '<!-- toc -->' in result and '<!-- /toc -->' in result
    assert '- [Section](#section)' in result


# ------------------------------------------------------------------
# CI gate: every doc that carries markers must pass --check

def test_all_doc_tocs_pass_check():
    """``gen_toc.py --check`` must pass on every docs/*.md with markers:
    CI fails when a table of contents is out of date."""
    completed = subprocess.run(
        [sys.executable, str(GEN_TOC), '--check'],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
