#!/usr/bin/env python3
"""Fail fast when a tag build does not match the project version.

A release must ship exactly what ``pyproject.toml`` declares, so a tag
like ``v4.3.1`` against a project version of ``4.3.0`` aborts the build
instead of publishing a mismatched installer. The same guard also fails
when any synced location (FALLBACK_VERSION, PKGBUILD pkgver, the
bug-report placeholder, uv.lock, CHANGELOG.md / README.md release
sections and compare links) disagrees with ``pyproject.toml``.

Usage (from the repo root)::

    uv run python scripts/check_tag_version.py [ref]

``ref`` defaults to the ``GITHUB_REF`` environment variable. Anything
that is not a tag (branch builds, pull requests, local builds) is
skipped — except when ``--all`` is passed, which checks the locations
without a tag (used by tests).
"""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG_PREFIX = "refs/tags/"


def project_version() -> str:
    """The version declared in pyproject.toml (never hard-coded)."""
    with open(ROOT / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def synced_location_mismatches(root: Path = ROOT) -> list[str]:
    """One message per synced location disagreeing with pyproject.toml.

    Shares ``scripts/bump_version.py``'s parsing so the tag guard and
    the release script can never disagree on what "in sync" means.
    """
    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import bump_version

    messages = []
    for relpath, label, found in bump_version.find_version_mismatches(root):
        messages.append(f"{relpath}: {label} is {found!r}")
    return messages


def main(argv: list[str]) -> int:
    check_all = "--all" in argv
    ref = next((a for a in argv if not a.startswith("--")), None) or \
        os.environ.get("GITHUB_REF", "")
    if not ref.startswith(TAG_PREFIX):
        if not check_all:
            print("not a tag build; skipping version guard")
            return 0
        ref = ""

    version = project_version()
    if ref:
        tag = ref[len(TAG_PREFIX):]
        if tag.removeprefix("v") != version:
            print(f"::error::tag '{tag}' does not match pyproject version "
                  f"'{version}'", file=sys.stderr)
            return 1
        print(f"tag matches pyproject version {version}")

    mismatches = synced_location_mismatches()
    if mismatches:
        for message in mismatches:
            print(f"::error::synced location out of date: {message}",
                  file=sys.stderr)
        print("::error::pyproject.toml is the source of truth — run "
              "`uv run python scripts/bump_version.py <level>` and "
              "commit the result", file=sys.stderr)
        return 1
    print("all synced locations match pyproject.toml")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
