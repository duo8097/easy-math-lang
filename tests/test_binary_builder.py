"""Scheduling and failure handling for independent frozen entry points."""
import importlib.util
from pathlib import Path
import sys
import threading
import types

import pytest

SPEC = importlib.util.spec_from_file_location(
    'binary_builder', Path(__file__).resolve().parents[1] / 'scripts/build_binaries.py')
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def test_parallel_builds_finish_before_alias(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, 'PyInstaller', types.ModuleType('PyInstaller'))
    monkeypatch.setattr(builder, 'DIST', tmp_path)
    started = threading.Barrier(2, timeout=10)
    finished = set()
    lock = threading.Lock()

    def build(name, import_line, full_pyside6):
        # The first pair must overlap; a serial implementation times out.
        if name != 'easy-math-editor':
            started.wait()
        with lock:
            finished.add(name)

    aliases = []

    def alias():
        assert finished == set(builder.ENTRIES)
        aliases.append(True)

    monkeypatch.setattr(builder, '_build', build)
    monkeypatch.setattr(builder, '_alias', alias)
    assert builder.main(['builder', '--jobs', '2']) == 0
    assert aliases == [True]


def test_failed_worker_never_creates_alias(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, 'PyInstaller', types.ModuleType('PyInstaller'))
    monkeypatch.setattr(builder, 'DIST', tmp_path)

    def fail(*args):
        raise RuntimeError('freeze failed')

    aliases = []
    monkeypatch.setattr(builder, '_build', fail)
    monkeypatch.setattr(builder, '_alias', lambda: aliases.append(True))
    with pytest.raises(RuntimeError, match='freeze failed'):
        builder.main(['builder', '--jobs', '2'])
    assert not aliases


def test_rejects_invalid_worker_count():
    with pytest.raises(SystemExit) as exc:
        builder.main(['builder', '--jobs', '0'])
    assert exc.value.code == 2


def test_entrypoint_is_stable_until_contents_change(monkeypatch, tmp_path):
    monkeypatch.setattr(builder, 'ROOT', tmp_path)
    commands = []
    monkeypatch.setattr(builder, '_run', lambda cmd, cache: commands.append(cmd))
    builder._build('easy-math-lsp', builder.ENTRIES['easy-math-lsp'], False)
    shim = Path(commands[0][3])
    stamp = shim.stat().st_mtime_ns
    builder._build('easy-math-lsp', builder.ENTRIES['easy-math-lsp'], False)
    assert commands[0] == commands[1]
    assert shim.stat().st_mtime_ns == stamp
    builder._build('easy-math-lsp', 'from other_module import main', False)
    assert 'other_module' in shim.read_text()


@pytest.mark.parametrize('value', ['0', '-1', 'invalid'])
def test_rejects_invalid_environment_jobs(monkeypatch, value):
    monkeypatch.setenv('EASYMATH_BUILD_JOBS', value)
    with pytest.raises(SystemExit) as exc:
        builder.main(['builder'])
    assert exc.value.code == 2


def test_explicit_jobs_override_environment(monkeypatch, tmp_path):
    monkeypatch.setenv('EASYMATH_BUILD_JOBS', 'invalid')
    monkeypatch.setitem(sys.modules, 'PyInstaller', types.ModuleType('PyInstaller'))
    monkeypatch.setattr(builder, 'DIST', tmp_path)
    monkeypatch.setattr(builder, '_build', lambda *args: None)
    monkeypatch.setattr(builder, '_alias', lambda: None)
    assert builder.main(['builder', '--jobs', '1']) == 0
