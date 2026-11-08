"""Bracket auto-closing decisions for the .ezmath editor.

Pure functions with no Qt dependency so the rules are unit-tested
directly; the widget glue lives in ``editor_widget.EditorWidget``.

Pairs: ``(``, ``[``, ``{`` and ``"``. ``<``, ``$``, backtick and the
apostrophe are deliberately NOT paired (the language mixes prose with
commands, so they would misfire). Everything here speaks in single
Unicode code points; Qt document offsets are UTF-16 code units, so the
caller must pass offsets/characters, never sizes derived from
``len()`` on astral text.
"""

PAIRS = (('(', ')'), ('[', ']'), ('{', '}'), ('"', '"'))
# Maps opener to closer
OPENERS_FOR = dict(PAIRS)
# Only the closer characters
CLOSERS = frozenset(closer for opener, closer in PAIRS)

BLOCK_SEPARATOR = '\u2029'

#: Indent used for the middle line of an Enter-expansion.
INDENT_UNIT = '    '


def _is_word_char(ch):
    return bool(ch) and (ch.isalnum() or ch == '_')


def classify(char):
    """Classify a document character for auto-pair decisions.

    Returns one of ``'empty'`` (nothing there, or a block boundary),
    ``'space'`` (any whitespace), ``'closer'`` (one of our closing
    brackets/quote), ``'word'`` (letters, digits, underscore) or
    ``'other'``.
    """
    if not char:
        return 'empty'
    if char in ('\n', '\r', BLOCK_SEPARATOR):
        # Block separator: behaves like end of line everywhere in the
        # rules below (never a closer, never a word character).
        return 'empty'
    if char.isspace():
        return 'space'
    if char in CLOSERS:
        return 'closer'
    if _is_word_char(char):
        return 'word'
    return 'other'


def should_pair(open_char, next_char, prev_char):
    """True iff typing *open_char* should insert the closing bracket too.

    Pairs are inserted only when the next character is end of line,
    whitespace, or a closing bracket. For ``"``, the previous character
    must not be a word character either (so prose like ``5"`` or the
    closing quote of an already-open string does not misfire).
    """
    # Pairs are inserted only when the next character is end of line,
    # whitespace, or a closing bracket.
    if classify(next_char) not in ('empty', 'space', 'closer'):
        return False
    
    # For "", additionally do not auto-pair when the previous character is a word character
    if open_char == '"' and classify(prev_char) == 'word':
        return False
    
    return True


def should_overtype(closing_char, next_char):
    """True iff typing *closing_char* should step over *next_char*.

    Only a directly matching closer is overtyped, and never across a
    line break: the block separator classifies as ``'empty'``, so it
    never matches. Whether the closer was auto-inserted does not
    matter — a matching character in the document is a matching
    character.
    """
    return bool(next_char) and next_char == closing_char


def count_preceding_backslashes(text_before):
    """Number of consecutive backslashes at the end of *text_before*.

    ``\\\\`` (two) is an escaped literal backslash in ezmath and
    never toggles inline-math mode, so only an odd count escapes the
    following character: odd = escaped, even = not escaped. This
    mirrors the compiler's ``find_unescaped`` pair-skipping scan.
    """
    count = 0
    for ch in reversed(text_before or ''):
        if ch == '\\':
            count += 1
        else:
            break
    return count


def is_escaped(text_before):
    """True when a bracket after *text_before* is backslash-escaped."""
    return count_preceding_backslashes(text_before) % 2 == 1


def escaped_closer(opener):
    """Escaped closer for *opener* (``(`` -> ``\\)``), or None."""
    closer = OPENERS_FOR.get(opener)
    if closer is None:
        return None
    return '\\' + closer


def escaped_pair_ahead(next_two):
    """Closer when *next_two* is an escaped closer (``\\)``), else None."""
    if len(next_two or '') != 2 or next_two[0] != '\\':
        return None
    closer = next_two[1]
    return closer if closer in CLOSERS else None


def matching_escaped_pair(prev_opener, next_two):
    """Closer when cursor sits between opener and its escaped closer.

    ``prev_opener`` is the char before the cursor, ``next_two`` the
    two chars after it (``\\)`` for ``(``). Returns the closer or None.
    """
    if not prev_opener or prev_opener not in OPENERS_FOR:
        return None
    if escaped_pair_ahead(next_two) != OPENERS_FOR[prev_opener]:
        return None
    return OPENERS_FOR[prev_opener]


def matching_pair(prev_char, next_char):
    """Return the pair's closer iff *prev_char* and *next_char* form one.

    Detects the cursor sitting between an empty pair on one line (the
    block separator never matches a closer, so this never fires across
    lines). Used by Backspace (delete both characters) and Enter
    (expand to three lines).
    """
    if prev_char and OPENERS_FOR.get(prev_char) == next_char:
        return next_char
    return None


# The backslash pair: typing ``\`` inserts ``\\`` with the cursor
# between the two characters. It is deliberately NOT an opener in
# ``PAIRS`` above — ezmath ``\`` toggles inline math, so ``\alpha``
# and ``\(`` must stay single (smart rollback below).

def is_backslash_pair(prev_char, next_char):
    """True when the cursor sits between an auto-inserted ``\\`` pair."""
    return prev_char == '\\' and next_char == '\\'


def should_pair_backslash(next_char):
    """True iff typing ``\\`` should also insert the second backslash.

    Pairing happens at end of line, before whitespace, or before a
    closing bracket. Never before a backslash itself (that is the
    overtype case), a letter/digit (middle of a word/command), or an
    opening bracket (the bracket will be escaped by the single
    backslash instead).
    """
    if classify(next_char) == 'word':
        return False
    if next_char == '\\':
        return False
    if next_char in OPENERS_FOR:
        return False
    return classify(next_char) in ('empty', 'space', 'closer')


def is_rollback_char(char):
    """True when typing *char* after ``\\`` must drop the trailing ``\\``.

    Letters/digits mean the user is writing a command (``\\alpha``)
    and opening brackets mean an escaped bracket (``\\(``); in both
    cases the auto-inserted second backslash would be stray.
    """
    return bool(char) and (char.isalnum() or char in OPENERS_FOR)


def indent_of(line_text):
    """The leading whitespace run of a line."""
    i = 0
    while i < len(line_text) and line_text[i] in (' ', '\t'):
        i += 1
    return line_text[:i]


def indent_of_with_closer(line_text):
    """The leading whitespace run of a line, excluding the closer char if present."""
    i = 0
    while i < len(line_text) and line_text[i] in (' ', '\t'):
        i += 1
    if i > 0 and line_text[i] in CLOSERS:
        # Skip the closer char as well
        i += 1
    return line_text[:i]


def expansion_lines(line_before, line_after):
    """Compute the three lines for the Enter-between-a-pair expansion.

    *line_before* is the block text before the cursor (it ends with the
    opener); *line_after* is the block text after the cursor (it starts
    with the closer). Returns ``(opener_line, middle_line, closer_line)``
    where the middle line carries one extra indent level and the closer
    line matches the opener line's indentation.
    """
    indent = indent_of(line_before)
    # The closer line should contain just the closer character
    # The closer character is the last character of line_after
    closer_line = line_after[-1] if line_after else ''
    # The middle line should have one extra indent unit beyond the opener line
    # Use the same type of indentation (tabs if the indent uses tabs, spaces if it uses spaces)
    if indent and indent[0] == '\t':
        # If the indent uses tabs, add another tab for the middle line
        middle_line = indent + '\t'
    else:
        # Otherwise use the standard INDENT_UNIT
        middle_line = indent + INDENT_UNIT
    
    return line_before, middle_line, closer_line
