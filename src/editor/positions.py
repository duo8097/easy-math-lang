"""Position conversion between LSP (UTF-16) and Python text offsets.

The LSP server speaks UTF-16 code-unit offsets; Python strings index by
Unicode code point.  The two agree for BMP text and diverge for characters
outside it (emoji, some symbols).  Qt's own text cursors are natively
UTF-16, so GUI cursor math needs no conversion — these helpers cover every
place where plain ``str`` offsets meet protocol positions, and they are
unit-tested here.
"""


def utf16_units(text):
    """Length of text in UTF-16 code units."""
    return len(text.encode('utf-16-le')) // 2


def _coerce_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_lsp_offset(line_text, code_point_offset):
    """Code-point offset -> LSP (UTF-16) offset within one line."""
    if not isinstance(line_text, str):
        return 0
    return utf16_units(line_text[:max(0, _coerce_int(code_point_offset))])


def to_code_point_offset(line_text, utf16_offset):
    """LSP (UTF-16) offset -> code-point offset within one line."""
    if not isinstance(line_text, str):
        return 0
    target = max(0, _coerce_int(utf16_offset))
    index = units = 0
    while index < len(line_text) and units < target:
        units += 2 if ord(line_text[index]) > 0xFFFF else 1
        index += 1
    return index


def line_col_to_offset(lines, line, utf16_character):
    """(line, LSP character) -> absolute code-point offset in ``\\n`` text."""
    line = _coerce_int(line, default=0)
    if line < 0:
        return 0
    if line >= len(lines):
        # Clamp past-the-end positions to the end of the document.
        return sum(len(text) + 1 for text in lines[:-1]) + (len(lines[-1]) if lines else 0)
    offset = 0
    for i in range(line):
        offset += len(lines[i]) + 1  # +1 for the newline
    return offset + to_code_point_offset(lines[line], utf16_character)


def format_diagnostic(severity, line, character, message):
    """One-line Problems-panel text: ``❌ 12:8  message`` (1-based)."""
    mark = '❌' if severity == 'error' else '⚠'
    return f'{mark} {line + 1}:{character + 1}  {message}'
