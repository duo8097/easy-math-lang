"""Tests for install detection and asset selection (``compiler.updater``).

Parametrized over Windows / macOS / Debian / Fedora / Arch / source by
monkeypatching platform, ``sys.frozen``, ``sys.executable`` and the
ownership commands (``dpkg -S`` / ``rpm -qf`` / ``pacman -Qo``).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compiler import updater as _updater  # noqa: E402
from compiler.update import ReleaseAsset  # noqa: E402
from compiler.updater import (  # noqa: E402
    METHOD_ARCH,
    METHOD_DEBIAN,
    METHOD_FEDORA,
    METHOD_MACOS,
    METHOD_SOURCE,
    METHOD_UNKNOWN,
    METHOD_WINDOWS,
    detect_install_method,
    one_click_supported,
    release_asset_for,
    sha256sums_asset,
    update_hint,
)


def _run_cmd_factory(mapping):
    def _run(argv):
        key = tuple(argv)
        if key in mapping:
            return mapping[key]
        return (1, '')
    return _run


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------

def test_windows_frozen_is_one_click():
    info = detect_install_method(frozen=True, platform_name='Windows',
                                 executable='C:\\Easy\\easy-math-editor.exe')
    assert info.method == METHOD_WINDOWS
    assert info.one_click is True


def test_source_checkout_never_self_updates():
    info = detect_install_method(frozen=False, platform_name='linux',
                                 executable='/usr/bin/python3')
    assert info.method == METHOD_SOURCE
    assert info.one_click is False
    assert 'git pull && uv sync' in update_hint(info.method)


def test_macos_writable_app_bundle(tmp_path):
    bundle = tmp_path / 'Applications' / 'Easy Math Lang.app'
    macos_dir = bundle / 'Contents' / 'MacOS'
    macos_dir.mkdir(parents=True)
    exe = macos_dir / 'easy-math-editor'
    exe.write_text('binary')
    info = detect_install_method(frozen=True, platform_name='darwin',
                                 executable=str(exe))
    assert info.method == METHOD_MACOS
    assert info.one_click is True
    assert info.detail == str(bundle)


def test_macos_readonly_bundle_falls_back(tmp_path):
    bundle = tmp_path / 'System' / 'Easy Math Lang.app'
    macos_dir = bundle / 'Contents' / 'MacOS'
    macos_dir.mkdir(parents=True)
    exe = macos_dir / 'easy-math-editor'
    exe.write_text('binary')
    os.chmod(bundle.parent, 0o555)
    try:
        info = detect_install_method(frozen=True, platform_name='darwin',
                                     executable=str(exe))
        assert info.method == METHOD_MACOS
        assert info.one_click is False
    finally:
        os.chmod(bundle.parent, 0o755)


def test_macos_not_in_bundle():
    info = detect_install_method(frozen=True, platform_name='darwin',
                                 executable='/usr/local/bin/easy-math-editor')
    assert info.method == METHOD_MACOS
    assert info.one_click is False


@pytest.mark.parametrize('platform_name', ['linux'])
def test_debian_ownership_detected(platform_name):
    exe = '/usr/lib/easy-math-lang/easy-math-lang'
    run_cmd = _run_cmd_factory({
        ('dpkg', '-S', exe): (0, f'easymath: {exe}\n'),
    })
    info = detect_install_method(frozen=True, platform_name=platform_name,
                                 executable=exe, run_cmd=run_cmd,
                                 which=lambda name: '/usr/bin/' + name
                                 if name in ('dpkg',) else None)
    assert info.method == METHOD_DEBIAN
    assert info.one_click is True


def test_debian_package_mismatch_falls_back():
    exe = '/usr/lib/easy-math-lang/easy-math-lang'
    run_cmd = _run_cmd_factory({
        ('dpkg', '-S', exe): (0, f'someother-package: {exe}\n'),
    })
    info = detect_install_method(frozen=True, platform_name='linux',
                                 executable=exe, run_cmd=run_cmd,
                                 which=lambda name: '/usr/bin/' + name
                                 if name == 'dpkg' else None)
    assert info.one_click is False


def test_debian_without_dpkg_and_rpm_is_unknown():
    info = detect_install_method(frozen=True, platform_name='linux',
                                 executable='/usr/lib/easy-math-lang/x',
                                 run_cmd=_run_cmd_factory({}),
                                 which=lambda name: None)
    assert info.method == METHOD_UNKNOWN
    assert info.one_click is False


def test_fedora_ownership_detected():
    exe = '/usr/lib/easy-math-lang/easy-math-lang'
    run_cmd = _run_cmd_factory({
        ('rpm', '-qf', exe): (0, 'easymath-7.0.0-1.x86_64\n'),
    })
    info = detect_install_method(frozen=True, platform_name='linux',
                                 executable=exe, run_cmd=run_cmd,
                                 which=lambda name: '/usr/bin/' + name
                                 if name == 'rpm' else None)
    assert info.method == METHOD_FEDORA
    assert info.one_click is True


def test_fedora_package_mismatch_falls_back():
    exe = '/usr/lib/easy-math-lang/easy-math-lang'
    run_cmd = _run_cmd_factory({
        ('rpm', '-qf', exe): (0, 'python3-unrelated-3.9-1.x86_64\n'),
    })
    info = detect_install_method(frozen=True, platform_name='linux',
                                 executable=exe, run_cmd=run_cmd,
                                 which=lambda name: '/usr/bin/' + name
                                 if name == 'rpm' else None)
    assert info.one_click is False


def test_arch_ownership_detected():
    exe = '/usr/lib/easy-math-lang/easy-math-lang'
    run_cmd = _run_cmd_factory({
        ('pacman', '-Qo', exe): (0, f'{exe} is owned by '
                                     'easy-math-lang-git 7.0.0-1\n'),
    })
    info = detect_install_method(frozen=True, platform_name='linux',
                                 executable=exe, run_cmd=run_cmd,
                                 which=lambda name: '/usr/bin/' + name
                                 if name == 'pacman' else None)
    assert info.method == METHOD_ARCH
    assert info.one_click is True


def test_arch_package_mismatch_falls_back():
    exe = '/usr/lib/easy-math-lang/easy-math-lang'
    run_cmd = _run_cmd_factory({
        ('pacman', '-Qo', exe): (0, f'{exe} is owned by not-easymath 1.0-1\n'),
    })
    info = detect_install_method(frozen=True, platform_name='linux',
                                 executable=exe, run_cmd=run_cmd,
                                 which=lambda name: '/usr/bin/' + name
                                 if name == 'pacman' else None)
    assert info.one_click is False


def test_dpkg_failing_command_is_not_ownership():
    run_cmd = _run_cmd_factory({('dpkg', '-S', '/x'): (1, 'dpkg-query: no path found')})
    info = detect_install_method(frozen=True, platform_name='linux',
                                 executable='/x', run_cmd=run_cmd,
                                 which=lambda name: '/usr/bin/dpkg'
                                 if name == 'dpkg' else None)
    assert info.one_click is False


# --------------------------------------------------------------------------
# pkexec / polkit gating for one-click on Linux
# --------------------------------------------------------------------------

@pytest.mark.parametrize('method', [METHOD_DEBIAN, METHOD_FEDORA, METHOD_ARCH])
def test_linux_one_click_requires_pkexec(method):
    from compiler.updater import InstallInfo

    info = InstallInfo(method, True, 'easymath')
    assert one_click_supported(info, which=lambda name: None,
                               environ={'DISPLAY': ':0'}) is False
    assert one_click_supported(info, which=lambda name: '/usr/bin/pkexec',
                               environ={'DISPLAY': ':0'}) is True


@pytest.mark.parametrize('method', [METHOD_DEBIAN, METHOD_FEDORA, METHOD_ARCH])
def test_linux_one_click_requires_graphical_session(method):
    from compiler.updater import InstallInfo

    info = InstallInfo(method, True, 'easymath')
    assert one_click_supported(info, which=lambda name: '/usr/bin/pkexec',
                               environ={}) is False
    assert one_click_supported(
        info, which=lambda name: '/usr/bin/pkexec',
        environ={'WAYLAND_DISPLAY': 'wayland-0'}) is True


def test_windows_and_macos_one_click_need_no_pkexec():
    from compiler.updater import InstallInfo

    assert one_click_supported(InstallInfo(METHOD_WINDOWS, True),
                               which=lambda n: None) is True
    assert one_click_supported(InstallInfo(METHOD_MACOS, True),
                               which=lambda n: None) is True


# --------------------------------------------------------------------------
# Asset selection + hints
# --------------------------------------------------------------------------

def _assets():
    return [ReleaseAsset(name, f'https://github.com/x/{name}', 100)
            for name in ('EasyMathLang-Windows-x64-Setup.exe',
                         'EasyMathLang-macOS-arm64.dmg',
                         'EasyMathLang-Debian-amd64.deb',
                         'EasyMathLang-Fedora-amd64.rpm',
                         'easy-math-lang-git-7.0.0-1-x86_64.pkg.tar.zst',
                         'SHA256SUMS.txt')]


@pytest.mark.parametrize('method,expected', [
    (METHOD_WINDOWS, 'EasyMathLang-Windows-x64-Setup.exe'),
    (METHOD_MACOS, 'EasyMathLang-macOS-arm64.dmg'),
    (METHOD_DEBIAN, 'EasyMathLang-Debian-amd64.deb'),
    (METHOD_FEDORA, 'EasyMathLang-Fedora-amd64.rpm'),
    (METHOD_ARCH, 'easy-math-lang-git-7.0.0-1-x86_64.pkg.tar.zst'),
])
def test_asset_selection(method, expected):
    asset = release_asset_for(method, _assets())
    assert asset is not None
    assert asset.name == expected


def test_asset_selection_missing_arch_package():
    assets = [a for a in _assets() if not a.name.endswith('.pkg.tar.zst')]
    assert release_asset_for(METHOD_ARCH, assets) is None


def test_asset_selection_source_and_unknown():
    assert release_asset_for(METHOD_SOURCE, _assets()) is None
    assert release_asset_for(METHOD_UNKNOWN, _assets()) is None


def test_sha256sums_asset_found():
    assert sha256sums_asset(_assets()).name == 'SHA256SUMS.txt'
    assert sha256sums_asset([]) is None


def test_update_hints_cover_all_methods():
    assert 'git pull && uv sync' in update_hint(METHOD_SOURCE)
    assert 'UAC' in update_hint(METHOD_WINDOWS)
    assert 'Applications' in update_hint(METHOD_MACOS)
    assert 'apt install ./EasyMathLang-Debian-amd64.deb' in update_hint(METHOD_DEBIAN)
    assert 'dnf install ./EasyMathLang-Fedora-amd64.rpm' in update_hint(METHOD_FEDORA)
    assert 'pacman -U ./easy-math-lang-git-7.0.0-1-x86_64.pkg.tar.zst' in \
        update_hint(METHOD_ARCH, 'easy-math-lang-git-7.0.0-1-x86_64.pkg.tar.zst')
    assert 'release page' in update_hint(METHOD_UNKNOWN)
