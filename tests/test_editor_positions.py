"""Unit tests for UTF-16 position conversion (pure, no Qt)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from editor import positions


def test_ascii_offsets_match():
    assert positions.to_lsp_offset('Use <oops>', 4) == 4
    assert positions.to_code_point_offset('Use <oops>', 4) == 4


def test_emoji_utf16_round_trip():
    line = '😀 <oops>'
    # code points: 😀=0, space=1, '<'=2 ; UTF-16: 😀=0..1, space=2, '<'=3
    assert positions.to_lsp_offset(line, 2) == 3
    assert positions.to_lsp_offset(line, 8) == 9
    assert positions.to_code_point_offset(line, 3) == 2
    assert positions.to_code_point_offset(line, 9) == 8


def test_offsets_clamp_gracefully():
    assert positions.to_lsp_offset('ab', 99) == 2
    assert positions.to_code_point_offset('ab', 99) == 2
    assert positions.to_lsp_offset('ab', -5) == 0


def test_line_col_to_offset():
    lines = ['<a> = 1', 'See <a>']
    assert positions.line_col_to_offset(lines, 1, 4) == len('<a> = 1\n') + 4
    assert positions.line_col_to_offset(lines, 9, 0) == len('<a> = 1\nSee <a>')


def test_format_diagnostic():
    assert positions.format_diagnostic('error', 11, 7, "Undefined identifier 'widt'") == \
        "❌ 12:8  Undefined identifier 'widt'"
    assert positions.format_diagnostic('warning', 17, 0, 'Unclosed block').startswith('⚠ 18:1')
