"""The GitHub Pages site must stay consistent.

Runs the same checks as ``scripts/check_site.py`` (links, i18n parity,
external resources, image manifest) so a broken site fails the test
suite instead of only failing a manual run.
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
CHECKER = ROOT / 'scripts' / 'check_site.py'


def _load_checker():
    spec = importlib.util.spec_from_file_location('check_site', CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def checker():
    if not CHECKER.is_file():
        pytest.skip('scripts/check_site.py not present')
    return _load_checker()


def test_site_directory_exists():
    assert (SITE / 'index.html').is_file()
    assert (SITE / '.nojekyll').is_file()


def test_relative_links_and_images_resolve(checker):
    assert checker.check_relative_targets() == []


def test_i18n_catalogs_are_in_parity(checker):
    assert checker.check_i18n_parity() == []


def test_no_external_resources_are_loaded(checker):
    assert checker.check_external_resources() == []


def test_images_match_the_manifest(checker):
    assert checker.check_image_manifest() == []


def test_site_stays_below_three_megabytes(checker):
    issues, total = checker.check_site_size()
    assert issues == []
    assert total < 3 * 1024 * 1024
