"""rule.txt must document every builtin command (docs sync guard).

MATH_DOCS/KEYWORD_DOCS in src/lsp/builtins.py are the single source of
truth for the command surface. rule.txt is the language reference. This
test fails when a command is added to the compiler/LSP but never
documented, keeping the reference honest.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lsp.builtins import KEYWORD_DOCS, MATH_DOCS  # noqa: E402

RULE = os.path.join(os.path.dirname(__file__), "..", "rule.txt")


def _rule_text():
    with open(RULE, encoding="utf-8") as h:
        return h.read()


def test_rule_txt_documents_every_math_builtin():
    text = _rule_text()
    missing = [name for name in sorted(MATH_DOCS)
               if f"*{name}" not in text]
    assert not missing, f"rule.txt is missing sections for: {missing}"


def test_rule_txt_documents_every_keyword_builtin():
    text = _rule_text()
    # calc is documented without the star prefix (it is a call, not a
    # starred command); the others are starred like *define / *p.
    missing = [name for name in sorted(KEYWORD_DOCS)
               if f"*{name}" not in text and f"{name}(" not in text]
    assert not missing, f"rule.txt is missing sections for: {missing}"


def test_rule_txt_has_no_stale_vec_diagram_text():
    # Task 1 replaced the SVG *vec diagrams with column vectors; the
    # reference must not resurrect the removed backend.
    text = _rule_text()
    for stale in ("-vec-<n>.svg", "[Vec Error", "compiler.vectors"):
        assert stale not in text, stale
