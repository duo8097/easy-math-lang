"""Tests for the Markdown-link checker used by the documentation CI gate."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECK_LINKS = ROOT / 'scripts' / 'check_links.py'


def _load_check_links():
    spec = importlib.util.spec_from_file_location('check_links', CHECK_LINKS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def check_links():
    return _load_check_links()


def test_missing_file_is_reported(check_links, tmp_path):
    page = tmp_path / 'page.md'
    page.write_text('# Page\n\n[Missing](nope.md)\n', encoding='utf-8')
    problems = check_links.check_file(page)
    assert [(problem.line, problem.link, problem.reason) for problem in problems] == [
        (3, 'nope.md', 'file does not exist'),
    ]


def test_missing_anchor_is_reported(check_links, tmp_path):
    page = tmp_path / 'page.md'
    page.write_text('# Page\n\n[Missing](#nope)\n', encoding='utf-8')
    problems = check_links.check_file(page)
    assert problems[0].reason == 'anchor does not exist'


def test_duplicate_heading_anchors_are_valid(check_links, tmp_path):
    page = tmp_path / 'page.md'
    page.write_text(
        '# Page\n\n## Repeat\n\n## Repeat\n\n[Second](#repeat-1)\n',
        encoding='utf-8',
    )
    assert check_links.check_file(page) == []


def test_links_inside_code_fences_are_ignored(check_links, tmp_path):
    page = tmp_path / 'page.md'
    page.write_text('# Page\n\n```\n[Missing](nope.md#nope)\n```\n', encoding='utf-8')
    assert check_links.check_file(page) == []


def test_external_links_are_skipped(check_links, tmp_path):
    page = tmp_path / 'page.md'
    page.write_text(
        '# Page\n\n[Web](https://example.com/nope) [Mail](mailto:test@example.com)\n',
        encoding='utf-8',
    )
    assert check_links.check_file(page) == []


def test_all_repository_documentation_links_pass_check():
    completed = subprocess.run(
        [sys.executable, str(CHECK_LINKS)], capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
