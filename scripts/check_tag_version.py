#!/usr/bin/env python3
"""Fail fast when a tag build does not match the project version.

A release must ship exactly what ``pyproject.toml`` declares, so a tag
like ``v4.3.1`` against a project version of ``4.3.0`` aborts the build
instead of publishing a mismatched installer.

Usage (from the repo root)::

    uv run python scripts/check_tag_version.py [ref]

``ref`` defaults to the ``GITHUB_REF`` environment variable. Anything
that is not a tag (branch builds, pull requests, local builds) is
skipped.
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


def main(argv: list[str]) -> int:
    ref = argv[1] if len(argv) > 1 else os.environ.get("GITHUB_REF", "")
    if not ref.startswith(TAG_PREFIX):
        print("not a tag build; skipping version guard")
        return 0

    tag = ref[len(TAG_PREFIX):]
    version = project_version()
    if tag.removeprefix("v") != version:
        print(f"::error::tag '{tag}' does not match pyproject version "
              f"'{version}'", file=sys.stderr)
        return 1

    print(f"tag matches pyproject version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
