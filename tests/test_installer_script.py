"""Static regression tests for ``installer/setup.iss``.

Guards the bug where the optional ``addtopath`` task wrote PATH to
``HKA\\Environment`` (``HKLM\\Environment`` in admin installs): that key
is not a real environment location, and creating keys directly under
HKLM fails on some machines with
"Error creating registry key ... RegCreateKeyEx failed; code 87",
aborting the install. The PATH task must target the per-user
``HKCU\\Environment`` key instead, and the ``NeedsAddPath`` check must
read the same hive it writes.
"""

import os
import re

import pytest

ISS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'installer', 'setup.iss'))
WORKFLOW = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '.github',
                 'workflows', 'build-installers.yml'))
README = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'README.md'))
INSTALL_DOC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'docs', 'installation.md'))
PACKAGING_DOC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'docs', 'packaging.md'))


@pytest.fixture(scope='module')
def iss_text():
    with open(ISS, encoding='utf-8-sig') as handle:
        return handle.read()


def _registry_entries(iss_text):
    section = re.search(
        r'(?ms)^\[Registry\]\s*\n(.*?)(?=^\[|\Z)', iss_text)
    assert section, 'no [Registry] section found'
    return [line.strip() for line in section.group(1).splitlines()
            if line.strip() and not line.strip().startswith(';')]


def test_path_task_targets_user_hive(iss_text):
    entries = [e for e in _registry_entries(iss_text)
               if 'ValueName:' in e and '"Path"' in e]
    assert entries, 'no PATH registry entry found'
    for entry in entries:
        assert re.search(r'(?i)\bRoot:\s*HKCU\b', entry), \
            f'PATH entry must use per-user HKCU (got: {entry})'
        assert re.search(r'(?i)\bSubkey:\s*"Environment"', entry), \
            f'PATH entry must target the Environment subkey (got: {entry})'
        assert 'HKA' not in entry and 'HKLM' not in entry, \
            f'PATH entry must not touch machine hives (got: {entry})'


def test_path_task_broadcasts_environment_change(iss_text):
    setup = re.search(
        r'(?ms)^\[Setup\]\s*\n(.*?)(?=^\[|\Z)', iss_text)
    assert setup, 'no [Setup] section found'
    assert re.search(r'(?im)^ChangesEnvironment\s*=\s*yes\s*$',
                     setup.group(1)), \
        '[Setup] must set ChangesEnvironment=yes so the optional user-PATH ' \
        'change is broadcast (WM_SETTINGCHANGE) at the end of install'


def test_needs_add_path_reads_same_hive(iss_text):
    assert re.search(
        r"RegQueryStringValue\(\s*HKCU\s*,\s*'Environment'\s*,\s*'Path'",
        iss_text), 'NeedsAddPath must query HKCU\\Environment\\Path'
    code = iss_text[iss_text.index('NeedsAddPath'):]
    assert 'HKA' not in code.split('end;')[0], \
        'NeedsAddPath must not query HKA while the entry writes HKCU'


def test_no_hklm_environment_key_anywhere(iss_text):
    for lineno, line in enumerate(iss_text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith(';'):
            continue
        assert not re.search(r'(?i)\bHKLM\\Environment\b', stripped), \
            f'line {lineno}: HKLM\\Environment is not a real env location'


def test_output_filename_agrees_everywhere(iss_text):
    """The Windows setup file name must agree across iss, CI, and docs."""
    match = re.search(r'(?im)^OutputBaseFilename\s*=\s*(\S+)\s*$', iss_text)
    assert match, 'no OutputBaseFilename found'
    assert match.group(1) == 'EasyMathLang-Windows-x64-Setup'
    filename = match.group(1) + '.exe'
    with open(WORKFLOW, encoding='utf-8') as handle:
        workflow_text = handle.read()
    assert filename in workflow_text, 'CI does not upload the named setup exe'
    for path in (README, INSTALL_DOC, PACKAGING_DOC):
        with open(path, encoding='utf-8') as handle:
            assert filename in handle.read(), f'{filename} missing from {path}'


# ----------------------------------------------------------------------
# AppVersion comes from pyproject.toml (never hard-coded)
# ----------------------------------------------------------------------

def test_app_version_is_not_hardcoded(iss_text):
    """AppVersion must be the {#AppVersion} preprocessor define, never a
    literal version: setup.iss drifted to 5.1.0 while pyproject.toml said
    5.2.0, and nothing failed until someone noticed the exe properties."""
    setup = re.search(r'(?ms)^\[Setup\]\s*\n(.*?)(?=^\[|\Z)', iss_text)
    assert setup, 'no [Setup] section found'
    match = re.search(r'(?im)^AppVersion\s*=\s*(\S+)\s*$', setup.group(1))
    assert match, 'no AppVersion found in [Setup]'
    assert match.group(1) == '{#AppVersion}', (
        f'AppVersion must use the preprocessor define (got: {match.group(1)})')
    # No literal numeric version anywhere (the 0.0.0 fallback default is
    # defined in the #ifndef guard, not in [Setup]).
    assert not re.search(r'(?im)^AppVersion\s*=\s*[\d.]', iss_text), \
        'AppVersion must not carry a hard-coded version number'


def test_app_version_has_fallback_default(iss_text):
    """A hand-run ISCC.exe (no /DAppVersion) must still compile: the
    #ifndef guard defines a 0.0.0 fallback."""
    assert re.search(r'(?m)^#ifndef AppVersion\s*$', iss_text), \
        'setup.iss must guard the AppVersion define with #ifndef'
    assert re.search(r'(?m)^#define AppVersion "0\.0\.0"\s*$', iss_text), \
        'the AppVersion fallback must be "0.0.0"'
    assert re.search(r'(?m)^#endif\s*$', iss_text), 'missing #endif'


def test_workflow_reads_version_and_passes_app_version():
    """CI must read the pyproject.toml version (tomllib, like
    scripts/check_tag_version.py) and inject it via /DAppVersion."""
    with open(WORKFLOW, encoding='utf-8') as handle:
        workflow_text = handle.read()
    assert '/DAppVersion=' in workflow_text, \
        'ISCC must be invoked with /DAppVersion=<version>'
    # The version is produced by tomllib reading pyproject.toml.
    assert re.search(r'import tomllib', workflow_text), \
        'the workflow must read the version with tomllib'
    assert re.search(r"pyproject\.toml", workflow_text), \
        'the workflow must read pyproject.toml'
    # ... and the ISCC invocation actually consumes that value.
    assert re.search(r'/DAppVersion=%APP_VERSION%', workflow_text), \
        'ISCC must receive the APP_VERSION read from pyproject.toml'
