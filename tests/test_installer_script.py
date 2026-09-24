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
