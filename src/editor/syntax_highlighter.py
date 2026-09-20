"""Basic Easy-Math-Lang syntax highlighting (independent of the LSP).

Rules mirror the actual language: ``//`` comments, ``*commands``,
``<variables>``, numbers, and ASCII symbol shortcuts.
"""

import re

from PySide6 import QtGui


def comment_pattern():
    return re.compile(r'//[^\n]*')


def variable_pattern():
    # Must start with a letter/underscore so ASCII arrows like <-> are
    # left for the operator rule.
    return re.compile(r'<\s*[A-Za-z_][^<>]*>')


def command_pattern():
    return re.compile(r'\*[A-Za-z][A-Za-z0-9_-]*')


def number_pattern():
    return re.compile(r'\b\d+(?:\s+\d+)*(?:\.\d+)?\b')


def math_pattern():
    # Single-line \ ... \ pairs; \\ never opens/closes (lookarounds).
    return re.compile(r'(?<!\\)\\(?:[^\\]|\\{2})*?(?<!\\)\\')


def math_spans(text):
    """(start, end) spans of single-line math pairs (escape-aware)."""
    spans = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == '\\':
            if i + 1 < n and text[i + 1] == '\\':
                i += 2
                continue
            j = i + 1
            found = -1
            while j < n:
                if text[j] == '\\':
                    if j + 1 < n and text[j + 1] == '\\':
                        j += 2
                        continue
                    found = j
                    break
                j += 1
            if found == -1:
                break
            spans.append((i, found + 1))
            i = found + 1
            continue
        i += 1
    return spans


def operator_pattern():
    # Alternatives are tried left to right: longer sequences first so
    # '<==' is not split into '<=' + '=', matching compiler/symbols.py.
    return re.compile(
        r'\|->|<->|<=>|<==|==>|=>|===|==|!==|!=|<=|>=|<<|>>|&&|\|\|'
        r'\+-|-\+|~=~|~=|~~|\.\.\.|::|\*\*|\|-|-\|'
        r'|->|<-|[+\-*/=<>!&|~^%]+'
    )


def _unescaped_positions(text):
    out = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == '\\':
            if i + 1 < n and text[i + 1] == '\\':
                i += 2
                continue
            out.append(i)
        i += 1
    return out


class EmlHighlighter(QtGui.QSyntaxHighlighter):
    """QSyntaxHighlighter with one rule set for Easy-Math-Lang."""

    def __init__(self, document):
        super().__init__(document)
        self._math_format = self._make_format('#2aa198', bold=True)
        self._rules = [
            (number_pattern(), self._make_format('#b58900')),
            (operator_pattern(), self._make_format('#cb4b16')),
            (variable_pattern(), self._make_format('#268bd2', bold=True)),
            (command_pattern(), self._make_format('#6c71c4', bold=True)),
            # Comments last so they win over everything else on the line.
            (comment_pattern(), self._make_format('#93a1a1', italic=True)),
        ]

    @staticmethod
    def _make_format(color, bold=False, italic=False):
        fmt = QtGui.QTextCharFormat()
        fmt.setForeground(QtGui.QColor(color))
        if bold:
            fmt.setFontWeight(QtGui.QFont.Bold)
        if italic:
            fmt.setFontItalic(True)
        return fmt

    def highlightBlock(self, text):
        # Multiline math: state 1 means this block started inside \ ... \.
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(),
                               match.end() - match.start(), fmt)
        if self.previousBlockState() == 1:
            unesc = _unescaped_positions(text)
            if not unesc:
                self.setFormat(0, len(text), self._math_format)
                self.setCurrentBlockState(1)
                return
            first = unesc[0]
            self.setFormat(0, first + 1, self._math_format)
            for start, end in math_spans(text[first + 1:]):
                self.setFormat(first + 1 + start, end - start,
                               self._math_format)
            # Still open when an even count (closer + pairs) leaves a
            # trailing lone opener, i.e. remaining count is odd.
            if (len(unesc) - 1) % 2 == 1:
                last = unesc[-1]
                self.setFormat(last, len(text) - last, self._math_format)
                self.setCurrentBlockState(1)
            else:
                self.setCurrentBlockState(0)
            return
        for start, end in math_spans(text):
            self.setFormat(start, end - start, self._math_format)
        unesc = _unescaped_positions(text)
        if len(unesc) % 2 == 1:
            last = unesc[-1]
            self.setFormat(last, len(text) - last, self._math_format)
            self.setCurrentBlockState(1)
        else:
            self.setCurrentBlockState(0)
