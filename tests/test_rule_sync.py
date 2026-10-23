"""rule.txt must document every builtin command (docs sync guard).

MATH_DOCS/KEYWORD_DOCS in src/lsp/builtins.py are the single source of
truth for the command surface. rule.txt is the language reference. This
test fails when a command is added to the compiler/LSP but never
documented, keeping the reference honest.

Also guards the README's Changelog section: it embeds the newest
CHANGELOG.md entry (one heading level deeper, latest release only), so
these tests fail when the two files drift apart.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lsp.builtins import KEYWORD_DOCS, MATH_DOCS  # noqa: E402

RULE = os.path.join(os.path.dirname(__file__), "..", "rule.txt")
README = os.path.join(os.path.dirname(__file__), "..", "README.md")
CHANGELOG = os.path.join(os.path.dirname(__file__), "..", "CHANGELOG.md")

# '## [5.0.0] - 2026-10-23' in CHANGELOG.md; the README mirrors the
# heading one level deeper as '### [5.0.0] - 2026-10-23'.
RELEASE_HEADING = re.compile(
    r'^## \[([^\]]+)\] - \d{4}-\d{2}-\d{2}$', re.MULTILINE)
README_HEADING = re.compile(
    r'^### \[([^\]]+)\] - \d{4}-\d{2}-\d{2}$', re.MULTILINE)


def _text(path):
    with open(path, encoding="utf-8") as h:
        return h.read()


def _rule_text():
    return _text(RULE)


def _changelog_latest_entry():
    """The ``(version, section)`` of the newest release in CHANGELOG.md.

    ``[Unreleased]`` carries no date, so the first dated heading is the
    latest release; the section runs until the next release heading.
    """
    text = _text(CHANGELOG)
    match = RELEASE_HEADING.search(text)
    assert match, "CHANGELOG.md has no dated release entry"
    end = text.find("\n## ", match.end())
    section = text[match.start():] if end == -1 else text[match.start():end]
    return match.group(1), section


def _demote_headings(section):
    """The README nests the entry one heading level deeper."""
    return re.sub(r'^#{2,3} ', lambda m: '#' + m.group(0),
                  section, flags=re.MULTILINE)


def test_readme_mirrors_the_latest_changelog_entry():
    # The README embeds the newest CHANGELOG.md entry verbatim (only
    # the heading level differs); fail when the two drift apart.
    version, section = _changelog_latest_entry()
    assert _demote_headings(section) in _text(README), (
        f"README.md does not mirror the {version} entry of CHANGELOG.md")


def test_readme_changelog_shows_only_the_latest_release():
    # Older releases stay in CHANGELOG.md and the releases page, so the
    # README must carry exactly one release section — the newest one.
    latest, _ = _changelog_latest_entry()
    shown = [m.group(1) for m in README_HEADING.finditer(_text(README))]
    assert shown == [latest], (
        f"README.md mirrors releases {shown}, expected only {latest}")


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
