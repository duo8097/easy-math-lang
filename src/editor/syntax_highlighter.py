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


def operator_pattern():
    return re.compile(
        r'\|->|<->|<=>|=>|<=|>=|!=|==|&&|\|\||\+-|-\+|~=~|~=|~~|\.\.\.|::|\*\*'
        r'|->|<-|[+\-*/=<>!&|~^%]+'
    )


class EmlHighlighter(QtGui.QSyntaxHighlighter):
    """QSyntaxHighlighter with one rule set for Easy-Math-Lang."""

    def __init__(self, document):
        super().__init__(document)
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
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(),
                               match.end() - match.start(), fmt)
