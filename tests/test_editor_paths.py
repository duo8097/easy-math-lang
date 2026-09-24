"""Regression tests for frozen/source executable resolution (editor.paths).

Simulates PyInstaller layouts without building binaries by monkeypatching
``sys.executable``/``sys.frozen`` and using real temporary directories.
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from editor import paths  # noqa: E402


@pytest.fixture()
def clean_sys(monkeypatch):
    """Neutralize frozen markers and env overrides for each test."""
    monkeypatch.delattr(sys, 'frozen', raising=False)
    monkeypatch.delattr(sys, '_MEIPASS', raising=False)
    monkeypatch.delenv(paths.ENV_LSP_EXE, raising=False)
    monkeypatch.delenv(paths.ENV_COMPILER_EXE, raising=False)
    # sys.argv[0] (e.g. .venv/Scripts/pytest) would otherwise leak a
    # candidate directory holding real sibling binaries.
    monkeypatch.setattr(sys, 'argv', ['python'])
    return monkeypatch


def _touch(path):
    with open(path, 'w', encoding='utf-8'):
        pass
    if os.name != 'nt':
        os.chmod(path, 0o755)


def _exe_name(base, nt):
    return base + '.exe' if nt else base


def _as_frozen(monkeypatch, exe_path):
    monkeypatch.setattr(sys, 'executable', exe_path)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)


def test_frozen_editor_finds_lsp_in_sibling_bin(tmp_path, clean_sys):
    """Installed layout: {app}/editor/<editor> + {app}/bin/<lsp> (Windows)."""
    clean_sys.setattr(os, 'name', 'nt')
    bin_dir = tmp_path / 'bin'
    editor_dir = tmp_path / 'editor'
    bin_dir.mkdir()
    editor_dir.mkdir()
    lsp = bin_dir / 'easy-math-lsp.exe'
    _touch(str(lsp))
    _as_frozen(clean_sys, str(editor_dir / 'easy-math-editor.exe'))
    clean_sys.setattr('shutil.which', lambda *a, **k: None)

    assert paths.resolve_lsp_command() == [str(lsp)]


def test_frozen_side_by_side_linux(tmp_path, clean_sys):
    """dist/ layout: all onefile binaries next to each other (Linux)."""
    clean_sys.setattr(os, 'name', 'posix')
    lsp = tmp_path / 'easy-math-lsp'
    editor = tmp_path / 'easy-math-editor'
    _touch(str(lsp))
    _touch(str(editor))
    _as_frozen(clean_sys, str(editor))
    clean_sys.setattr('shutil.which', lambda *a, **k: None)

    assert paths.resolve_lsp_command() == [str(lsp)]


def test_frozen_compiler_next_to_editor(tmp_path, clean_sys):
    clean_sys.setattr(os, 'name', 'nt')
    bin_dir = tmp_path / 'bin'
    editor_dir = tmp_path / 'editor'
    bin_dir.mkdir()
    editor_dir.mkdir()
    compiler = bin_dir / 'easy-math-lang.exe'
    _touch(str(compiler))
    _as_frozen(clean_sys, str(editor_dir / 'easy-math-editor.exe'))
    clean_sys.setattr('shutil.which', lambda *a, **k: None)

    doc = str(tmp_path / 'doc.ezmath')
    assert paths.resolve_compiler_command(doc) == [str(compiler), doc]


def test_env_override_wins_over_everything(tmp_path, clean_sys):
    custom = tmp_path / 'custom-lsp'
    _touch(str(custom))
    clean_sys.setenv(paths.ENV_LSP_EXE, str(custom))
    _as_frozen(clean_sys, str(tmp_path / 'easy-math-editor'))
    assert paths.resolve_lsp_command() == [str(custom)]


def test_which_fallback_when_no_sibling(tmp_path, clean_sys):
    clean_sys.setattr(sys, 'executable', str(tmp_path / 'python'))
    clean_sys.setattr('shutil.which', lambda name, *a, **k: '/usr/bin/' + name)
    cmd = paths.resolve_lsp_command()
    assert cmd == ['/usr/bin/' + _exe_name('easy-math-lsp', os.name == 'nt')]


def test_source_falls_back_to_module_mode(tmp_path, clean_sys):
    clean_sys.setattr(sys, 'executable', str(tmp_path / 'python'))
    clean_sys.setattr('shutil.which', lambda *a, **k: None)
    assert paths.resolve_lsp_command() == [
        str(tmp_path / 'python'), '-m', 'lsp']
    doc = str(tmp_path / 'doc.ezmath')
    assert paths.resolve_compiler_command(doc) == [
        str(tmp_path / 'python'), '-m', 'compiler', doc]


def test_frozen_never_uses_python_module_mode(tmp_path, clean_sys):
    """Core regression: a bundled binary is not a Python interpreter."""
    _as_frozen(clean_sys, str(tmp_path / 'easy-math-editor'))
    clean_sys.setattr('shutil.which', lambda *a, **k: None)
    lsp_cmd = paths.resolve_lsp_command()
    assert '-m' not in lsp_cmd
    assert all('python' not in part.lower() for part in lsp_cmd)
    compiler_cmd = paths.resolve_compiler_command('doc.ezmath')
    assert '-m' not in compiler_cmd
    assert '-c' not in compiler_cmd


def test_default_server_command_stays_usable(clean_sys):
    from editor.lsp_client import default_server_command
    cmd = default_server_command()
    assert isinstance(cmd, list) and cmd and all(cmd)


def test_python_m_compiler_entrypoint():
    """``python -m compiler --help`` must work (used by the source fallback)."""
    env = dict(os.environ)
    src = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
    env['PYTHONPATH'] = src + os.pathsep + env.get('PYTHONPATH', '')
    proc = subprocess.run(
        [sys.executable, '-m', 'compiler', '--help'],
        capture_output=True, text=True, timeout=120, env=env,
        cwd=os.path.join(os.path.dirname(__file__), '..'))
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert 'easy-math-lang' in proc.stdout.lower()


def test_resource_path_uses_bundle_dir_when_frozen(tmp_path, clean_sys):
    clean_sys.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    assert paths.resource_path('data', 'x') == os.path.join(
        str(tmp_path), 'data', 'x')
