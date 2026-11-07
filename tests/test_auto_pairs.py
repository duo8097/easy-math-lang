"""Unit tests for the pure auto-pairs logic (no Qt dependencies)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from editor import auto_pairs


def test_should_pair_basic():
    """Test basic pairing logic."""
    # Pair after space
    assert auto_pairs.should_pair('(', ' ', '') == True
    assert auto_pairs.should_pair('(', '\t', '') == True
    assert auto_pairs.should_pair('(', '\n', '') == True
    
    # Don't pair after word char
    assert auto_pairs.should_pair('(', 'a', '') == False
    assert auto_pairs.should_pair('(', 'z', '') == False
    assert auto_pairs.should_pair('(', '_', '') == False
    assert auto_pairs.should_pair('(', '1', '') == False
    
    # Pair before closer
    assert auto_pairs.should_pair('(', ')', '') == True
    assert auto_pairs.should_pair('[', ']', '') == True
    assert auto_pairs.should_pair('{', '}', '') == True
    assert auto_pairs.should_pair('"', '"', '') == True
    
    # Don't pair before word char
    assert auto_pairs.should_pair('(', 'a', '') == False
    
    # Quote special case: don't pair after word char
    assert auto_pairs.should_pair('"', ' ', 'a') == False
    assert auto_pairs.should_pair('"', ' ', 'z') == False
    assert auto_pairs.should_pair('"', ' ', '_') == False
    assert auto_pairs.should_pair('"', ' ', '1') == False
    
    # Quote pairs normally
    assert auto_pairs.should_pair('"', ' ', '') == True


def test_should_overtype():
    """Test overtype logic."""
    # Overtype matching closer
    assert auto_pairs.should_overtype(')', ')') == True
    assert auto_pairs.should_overtype(']', ']') == True
    assert auto_pairs.should_overtype('}', '}') == True
    assert auto_pairs.should_overtype('"', '"') == True
    
    # Don't overtype non-matching
    assert auto_pairs.should_overtype(')', '(') == False
    assert auto_pairs.should_overtype(')', 'a') == False
    assert auto_pairs.should_overtype(')', ' ') == False
    assert auto_pairs.should_overtype(')', '\n') == False


def test_matching_pair():
    """Test matching pair detection."""
    # Simple pair
    assert auto_pairs.matching_pair('(', ')') == ')'
    assert auto_pairs.matching_pair('[', ']') == ']'
    assert auto_pairs.matching_pair('{', '}') == '}'
    assert auto_pairs.matching_pair('"', '"') == '"'
    
    # No match
    assert auto_pairs.matching_pair('(', 'a') is None
    assert auto_pairs.matching_pair('[', '}') is None
    assert auto_pairs.matching_pair('{', ']') is None
    assert auto_pairs.matching_pair('"', '(') is None
    
    # Empty pair
    assert auto_pairs.matching_pair('', '') is None
    assert auto_pairs.matching_pair('a', 'a') is None


def test_indent_of():
    """Test indentation extraction."""
    assert auto_pairs.indent_of('') == ''
    assert auto_pairs.indent_of(' ') == ' '
    assert auto_pairs.indent_of('  ') == '  '
    assert auto_pairs.indent_of('\t') == '\t'
    assert auto_pairs.indent_of('\t ') == '\t '
    assert auto_pairs.indent_of('  \t  ') == '  \t  '
    assert auto_pairs.indent_of('  code') == '  '
    assert auto_pairs.indent_of('\t\tcode') == '\t\t'
    assert auto_pairs.indent_of('  \t  code') == '  \t  '


def test_expansion_lines():
    """Test Enter expansion logic."""
    # Basic expansion
    opener_line, middle_line, closer_line = auto_pairs.expansion_lines('(', ')')
    assert opener_line == '('
    assert middle_line == '    '
    assert closer_line == ')'
    
    # With indentation
    opener_line, middle_line, closer_line = auto_pairs.expansion_lines('  (', ')')
    assert opener_line == '  ('
    assert middle_line == '      '
    assert closer_line == ')'
    
    # Tab indentation
    opener_line, middle_line, closer_line = auto_pairs.expansion_lines('\t(', ')')
    assert opener_line == '\t('
    assert middle_line == '\t\t'
    assert closer_line == ')'
    
    # With existing content - closer_line should contain the closer character
    # The closer character is at the end of line_after
    opener_line, middle_line, closer_line = auto_pairs.expansion_lines('  (x', 'y)')
    assert opener_line == '  (x'
    assert middle_line == '      '
    # The closer_line should be just the closing character
    assert closer_line == ')'


def test_pair_constants():
    """Test that all expected pairs are defined."""
    expected_pairs = [
        ('(', ')'),
        ('[', ']'),
        ('{', '}'),
        ('"', '"'),
    ]
    
    assert auto_pairs.PAIRS == tuple(expected_pairs)
    assert set(auto_pairs.OPENERS_FOR.keys()) == {'(', '[', '{', '"'}
    assert set(auto_pairs.CLOSERS) == {')', ']', '}', '"'}


def test_non_paired_characters():
    """Test that non-paired characters are not in the pair lists."""
    non_paired = ['<', '$', '`', "'", '\\']
    
    for char in non_paired:
        assert char not in auto_pairs.OPENERS_FOR
        assert char not in auto_pairs.CLOSERS
        # Check they don't form pairs
        for opener, closer in auto_pairs.PAIRS:
            assert opener != char
            assert closer != char


def test_block_separator():
    """Test block separator classification."""
    assert auto_pairs.classify('\n') == 'empty'
    assert auto_pairs.classify('\r') == 'empty'
    assert auto_pairs.classify('\u2029') == 'empty'


def test_all_paired_types():
    """Test all paired types are correctly categorized."""
    for opener, closer in auto_pairs.PAIRS:
        # For quotes, both opener and closer are the same character
        # and classify returns 'closer' (since it's in CLOSERS)
        # For other pairs, opener is 'other' and closer is 'closer'
        if opener == closer:
            # Quotes
            assert auto_pairs.classify(opener) == 'closer', f"Failed for opener/closer {opener}: classify(opener) = {auto_pairs.classify(opener)}"
        else:
            # Other brackets
            assert auto_pairs.classify(opener) == 'other', f"Failed for opener {opener}: classify(opener) = {auto_pairs.classify(opener)}"
        assert auto_pairs.classify(closer) == 'closer', f"Failed for closer {closer}: classify(closer) = {auto_pairs.classify(closer)}"


def test_word_char_classification():
    """Test word character classification."""
    assert auto_pairs.classify('a') == 'word'
    assert auto_pairs.classify('Z') == 'word'
    assert auto_pairs.classify('0') == 'word'
    assert auto_pairs.classify('_') == 'word'
    
    assert auto_pairs.classify(' ') == 'space'
    assert auto_pairs.classify('\t') == 'space'
    
    assert auto_pairs.classify(')') == 'closer'
    assert auto_pairs.classify(']') == 'closer'
    assert auto_pairs.classify('}') == 'closer'
    assert auto_pairs.classify('"') == 'closer'
    
    assert auto_pairs.classify('') == 'empty'
    assert auto_pairs.classify('\n') == 'empty'
