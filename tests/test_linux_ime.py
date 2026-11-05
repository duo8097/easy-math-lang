"""Tests for editor.linux_ime (fcitx5 IME support on Linux).

These tests are offline and headless: they never require fcitx, a system
Qt, or a display. All filesystem and environment interaction goes through
``tmp_path`` and ``monkeypatch``.
"""

import os
import sys
import types
from pathlib import Path
from unittest import mock

import pytest

from editor import linux_ime

PLUGIN_NAME = "libfcitx5platforminputcontextplugin.so"


def make_plugin(base: Path) -> Path:
    """Create a fake plugin file at base/platforminputcontexts/PLUGIN_NAME."""
    plugin = base / "platforminputcontexts" / PLUGIN_NAME
    plugin.parent.mkdir(parents=True, exist_ok=True)
    plugin.write_bytes(b"\x7fELF fake plugin")
    return plugin


@pytest.fixture
def clean_env(monkeypatch):
    """Ensure QT_* / EZMATH_* env vars don't leak in from the host."""
    for var in ("EZMATH_NO_IME_FIX", "QT_IM_MODULE", "QT_PLUGIN_PATH", "XDG_CACHE_HOME"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


# ---------------------------------------------------------------- platform / skip

class TestShouldSkip:
    def test_not_linux(self, clean_env, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        assert linux_ime._should_skip() is True

    def test_opt_out_env(self, clean_env):
        clean_env.setenv("EZMATH_NO_IME_FIX", "1")
        assert linux_ime._should_skip() is True

    def test_qt_im_module_ibus_skips(self, clean_env):
        clean_env.setenv("QT_IM_MODULE", "ibus")
        assert linux_ime._should_skip() is True

    def test_qt_im_module_fcitx_allowed(self, clean_env):
        clean_env.setenv("QT_IM_MODULE", "fcitx")
        assert linux_ime._should_skip() is False

    def test_qt_im_module_fcitx5_allowed(self, clean_env):
        clean_env.setenv("QT_IM_MODULE", "fcitx5")
        assert linux_ime._should_skip() is False

    def test_qt_im_module_unset_allowed(self, clean_env):
        assert linux_ime._should_skip() is False


# ---------------------------------------------------------------- Qt version check

def fake_subprocess(run_impl):
    return types.SimpleNamespace(
        run=run_impl,
        SubprocessError=__import__("subprocess").SubprocessError,
    )


class FakeCompleted:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


class TestSystemQtVersion:
    def test_qmake6_success(self, monkeypatch):
        monkeypatch.setattr(
            linux_ime, "subprocess",
            fake_subprocess(lambda *a, **k: FakeCompleted(0, "6.12.3\n")),
        )
        assert linux_ime._get_system_qt_version() == "6.12.3"

    def test_qtpaths6_fallback_plain_output(self, monkeypatch):
        def run(cmd, *a, **k):
            if cmd[0] == "qmake6":
                return FakeCompleted(1, "")
            return FakeCompleted(0, "6.11.0\n")
        monkeypatch.setattr(linux_ime, "subprocess", fake_subprocess(run))
        assert linux_ime._get_system_qt_version() == "6.11.0"

    def test_qtpaths6_fallback_prefixed_output(self, monkeypatch):
        def run(cmd, *a, **k):
            if cmd[0] == "qmake6":
                raise FileNotFoundError("qmake6")
            return FakeCompleted(0, "QT_VERSION: 6.10.1\n")
        monkeypatch.setattr(linux_ime, "subprocess", fake_subprocess(run))
        assert linux_ime._get_system_qt_version() == "6.10.1"

    def test_both_fail_returns_none(self, monkeypatch):
        def run(cmd, *a, **k):
            raise FileNotFoundError(cmd[0])
        monkeypatch.setattr(linux_ime, "subprocess", fake_subprocess(run))
        assert linux_ime._get_system_qt_version() is None

    def test_qtpaths6_garbage_returns_none(self, monkeypatch):
        def run(cmd, *a, **k):
            if cmd[0] == "qmake6":
                return FakeCompleted(1, "")
            return FakeCompleted(0, "not a version\n???\n")
        monkeypatch.setattr(linux_ime, "subprocess", fake_subprocess(run))
        assert linux_ime._get_system_qt_version() is None


class TestPySide6QtVersion:
    def test_reads_qversion(self, monkeypatch):
        fake_qtcore = types.SimpleNamespace(qVersion=lambda: "6.12.0")
        monkeypatch.setitem(sys.modules, "PySide6",
                            types.SimpleNamespace(QtCore=fake_qtcore))
        assert linux_ime._get_pyside6_qt_version() == "6.12.0"

    def test_missing_pyside6_returns_none(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "PySide6", None)  # import raises ImportError
        assert linux_ime._get_pyside6_qt_version() is None


class TestVersionMatch:
    @pytest.mark.parametrize("system,pyside,expected", [
        ("6.12.3", "6.12.0", True),
        ("6.12", "6.12", True),
        ("6.11.0", "6.12.0", False),
        ("7.0.0", "6.12.0", False),
        ("6.12.3", "6.11.0", False),
    ])
    def test_known_versions(self, system, pyside, expected):
        assert linux_ime._check_version_match(system, pyside) is expected

    def test_unknown_system_version_proceeds(self):
        assert linux_ime._check_version_match(None, "6.12.0") is True

    def test_unknown_pyside6_version_proceeds(self):
        assert linux_ime._check_version_match("6.12.0", None) is True


# ---------------------------------------------------------------- plugin lookup

class TestFindPlugin:
    def test_found_in_qt_plugin_path(self, clean_env, tmp_path):
        plugin = make_plugin(tmp_path / "custom")
        clean_env.setenv("QT_PLUGIN_PATH", str(tmp_path / "custom"))
        assert linux_ime._find_fcitx5_plugin() == plugin.resolve()

    def test_found_in_second_qt_plugin_path_entry(self, clean_env, tmp_path):
        make_plugin(tmp_path / "second")
        entries = os.pathsep.join([str(tmp_path / "missing"), str(tmp_path / "second")])
        clean_env.setenv("QT_PLUGIN_PATH", entries)
        result = linux_ime._find_fcitx5_plugin()
        assert result == (tmp_path / "second" / "platforminputcontexts" / PLUGIN_NAME).resolve()

    def test_found_in_standard_dirs(self, clean_env, monkeypatch, tmp_path):
        first = tmp_path / "dir1"
        second = tmp_path / "dir2"
        make_plugin(second)
        monkeypatch.setattr(linux_ime, "_STANDARD_PLUGIN_DIRS", (first, second))
        assert linux_ime._find_fcitx5_plugin() == (second / "platforminputcontexts" / PLUGIN_NAME).resolve()

    def test_qt_plugin_path_wins_over_standard_dirs(self, clean_env, monkeypatch, tmp_path):
        custom = tmp_path / "custom"
        standard = tmp_path / "standard"
        custom_plugin = make_plugin(custom)
        make_plugin(standard)
        clean_env.setenv("QT_PLUGIN_PATH", str(custom))
        monkeypatch.setattr(linux_ime, "_STANDARD_PLUGIN_DIRS", (standard,))
        assert linux_ime._find_fcitx5_plugin() == custom_plugin.resolve()

    def test_not_found_returns_none(self, clean_env, monkeypatch, tmp_path):
        monkeypatch.setattr(linux_ime, "_STANDARD_PLUGIN_DIRS",
                            (tmp_path / "nope", tmp_path / "nada"))
        assert linux_ime._find_fcitx5_plugin() is None

    def test_symlinked_plugin_is_resolved(self, clean_env, tmp_path):
        real_dir = tmp_path / "real"
        real_plugin = make_plugin(real_dir)
        link_dir = tmp_path / "linked"
        link_plugin = link_dir / "platforminputcontexts" / PLUGIN_NAME
        link_plugin.parent.mkdir(parents=True)
        link_plugin.symlink_to(real_plugin)
        clean_env.setenv("QT_PLUGIN_PATH", str(link_dir))
        result = linux_ime._find_fcitx5_plugin()
        assert result == real_plugin.resolve()

    def test_empty_qt_plugin_path_entries_ignored(self, clean_env, tmp_path):
        plugin = make_plugin(tmp_path / "real")
        clean_env.setenv("QT_PLUGIN_PATH", os.pathsep.join(["", "  ", str(tmp_path / "real")]))
        assert linux_ime._find_fcitx5_plugin() == plugin.resolve()


# ---------------------------------------------------------------- private dir + symlink

class TestPrivatePluginDir:
    def test_uses_xdg_cache_home(self, clean_env, tmp_path):
        clean_env.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
        result = linux_ime._create_private_plugin_dir()
        assert result == tmp_path / "cache" / "easy-math-lang" / "qt-plugins" / "platforminputcontexts"
        assert result.is_dir()

    def test_defaults_to_home_cache(self, clean_env, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = linux_ime._create_private_plugin_dir()
        assert result == tmp_path / ".cache" / "easy-math-lang" / "qt-plugins" / "platforminputcontexts"
        assert result.is_dir()


class TestEnsurePluginSymlink:
    def test_creates_symlink(self, tmp_path):
        plugin = make_plugin(tmp_path / "src")
        target_dir = tmp_path / "dst"
        target_dir.mkdir()
        assert linux_ime._ensure_plugin_symlink(plugin, target_dir) is True
        link = target_dir / PLUGIN_NAME
        assert link.is_symlink()
        assert link.readlink() == plugin.resolve()

    def test_idempotent(self, tmp_path):
        plugin = make_plugin(tmp_path / "src")
        target_dir = tmp_path / "dst"
        target_dir.mkdir()
        assert linux_ime._ensure_plugin_symlink(plugin, target_dir) is True
        first_inode = (target_dir / PLUGIN_NAME).lstat().st_ino
        assert linux_ime._ensure_plugin_symlink(plugin, target_dir) is True
        assert (target_dir / PLUGIN_NAME).lstat().st_ino == first_inode

    def test_replaces_stale_symlink(self, tmp_path):
        old_plugin = make_plugin(tmp_path / "old")
        new_plugin = make_plugin(tmp_path / "new")
        target_dir = tmp_path / "dst"
        target_dir.mkdir()
        assert linux_ime._ensure_plugin_symlink(old_plugin, target_dir) is True
        assert linux_ime._ensure_plugin_symlink(new_plugin, target_dir) is True
        assert (target_dir / PLUGIN_NAME).readlink() == new_plugin.resolve()

    def test_replaces_broken_symlink(self, tmp_path):
        plugin = make_plugin(tmp_path / "src")
        target_dir = tmp_path / "dst"
        target_dir.mkdir()
        link = target_dir / PLUGIN_NAME
        link.symlink_to(tmp_path / "does-not-exist.so")
        assert linux_ime._ensure_plugin_symlink(plugin, target_dir) is True
        assert link.readlink() == plugin.resolve()

    def test_replaces_regular_file(self, tmp_path):
        plugin = make_plugin(tmp_path / "src")
        target_dir = tmp_path / "dst"
        target_dir.mkdir()
        stale = target_dir / PLUGIN_NAME
        stale.write_bytes(b"stale copy")
        assert linux_ime._ensure_plugin_symlink(plugin, target_dir) is True
        assert (target_dir / PLUGIN_NAME).is_symlink()

    def test_copy_fallback_when_symlink_fails(self, clean_env, monkeypatch, tmp_path):
        plugin = make_plugin(tmp_path / "src")
        target_dir = tmp_path / "dst"
        target_dir.mkdir()

        def fail_symlink(self, target):
            raise OSError("no symlinks here")
        monkeypatch.setattr(Path, "symlink_to", fail_symlink)

        assert linux_ime._ensure_plugin_symlink(plugin, target_dir) is True
        copied = target_dir / PLUGIN_NAME
        assert not copied.is_symlink()
        assert copied.read_bytes() == plugin.read_bytes()
        # Second run is a no-op success (copy2 preserves mtime/size).
        assert linux_ime._ensure_plugin_symlink(plugin, target_dir) is True

    def test_returns_false_when_copy_also_fails(self, monkeypatch, tmp_path):
        plugin = make_plugin(tmp_path / "src")
        target_dir = tmp_path / "dst"
        target_dir.mkdir()

        monkeypatch.setattr(Path, "symlink_to",
                            lambda self, target: (_ for _ in ()).throw(OSError("no")))
        monkeypatch.setattr(linux_ime.shutil, "copy2",
                            lambda *a, **k: (_ for _ in ()).throw(OSError("no")))

        assert linux_ime._ensure_plugin_symlink(plugin, target_dir) is False


# ---------------------------------------------------------------- end-to-end (mocked)

class TestSetupFcitx5Ime:
    @pytest.fixture
    def patched(self, clean_env, monkeypatch, tmp_path):
        plugin = make_plugin(tmp_path / "system")
        monkeypatch.setattr(linux_ime, "_get_system_qt_version", lambda: "6.12.0")
        monkeypatch.setattr(linux_ime, "_get_pyside6_qt_version", lambda: "6.12.0")
        monkeypatch.setattr(linux_ime, "_find_fcitx5_plugin", lambda: plugin)
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
        expected_parent = tmp_path / "cache" / "easy-math-lang" / "qt-plugins"
        return plugin, expected_parent

    def test_sets_env_and_symlinks(self, patched):
        _, expected_parent = patched
        assert linux_ime._setup_fcitx5_ime() is True
        assert os.environ["QT_PLUGIN_PATH"] == str(expected_parent)
        assert os.environ["QT_IM_MODULE"] == "fcitx"
        link = expected_parent / "platforminputcontexts" / PLUGIN_NAME
        assert link.is_symlink()

    def test_prepends_to_existing_qt_plugin_path(self, clean_env, patched):
        _, expected_parent = patched
        clean_env.setenv("QT_PLUGIN_PATH", "/opt/user/plugins")
        assert linux_ime._setup_fcitx5_ime() is True
        assert os.environ["QT_PLUGIN_PATH"] == f"{expected_parent}{os.pathsep}/opt/user/plugins"

    def test_preserves_user_fcitx5_setting(self, clean_env, patched):
        clean_env.setenv("QT_IM_MODULE", "fcitx5")
        assert linux_ime._setup_fcitx5_ime() is True
        assert os.environ["QT_IM_MODULE"] == "fcitx5"

    def test_skips_when_opted_out(self, clean_env, patched):
        clean_env.setenv("EZMATH_NO_IME_FIX", "1")
        assert linux_ime._setup_fcitx5_ime() is True
        assert "QT_PLUGIN_PATH" not in os.environ
        assert "QT_IM_MODULE" not in os.environ

    def test_skips_for_other_im_module(self, clean_env, patched):
        clean_env.setenv("QT_IM_MODULE", "ibus")
        assert linux_ime._setup_fcitx5_ime() is True
        assert "QT_PLUGIN_PATH" not in os.environ

    def test_version_mismatch_skips(self, clean_env, monkeypatch, tmp_path):
        monkeypatch.setattr(linux_ime, "_get_system_qt_version", lambda: "6.11.0")
        monkeypatch.setattr(linux_ime, "_get_pyside6_qt_version", lambda: "6.12.0")
        monkeypatch.setattr(linux_ime, "_find_fcitx5_plugin",
                            lambda: pytest.fail("plugin lookup must not run on mismatch"))
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
        assert linux_ime._setup_fcitx5_ime() is True
        assert "QT_PLUGIN_PATH" not in os.environ

    def test_unknown_system_version_proceeds(self, patched, monkeypatch):
        monkeypatch.setattr(linux_ime, "_get_system_qt_version", lambda: None)
        assert linux_ime._setup_fcitx5_ime() is True
        assert "QT_PLUGIN_PATH" in os.environ

    def test_missing_plugin_is_not_fatal(self, clean_env, monkeypatch, tmp_path):
        monkeypatch.setattr(linux_ime, "_get_system_qt_version", lambda: "6.12.0")
        monkeypatch.setattr(linux_ime, "_get_pyside6_qt_version", lambda: "6.12.0")
        monkeypatch.setattr(linux_ime, "_find_fcitx5_plugin", lambda: None)
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
        assert linux_ime._setup_fcitx5_ime() is True
        assert "QT_PLUGIN_PATH" not in os.environ

    def test_entry_point_never_raises(self, monkeypatch):
        monkeypatch.setattr(linux_ime, "_setup_fcitx5_ime",
                            mock.Mock(side_effect=RuntimeError("boom")))
        assert linux_ime.setup_fcitx5_ime() is True
