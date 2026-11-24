#!/usr/bin/env bash
# Build the Easy Math Linux binaries, .deb package and/or .rpm package.
# Mirrors scripts/build_macos.sh and the CI workflow
# .github/workflows/build-installers.yml (jobs build-linux-binary,
# build-deb, build-rpm — each stage can fail, be re-run and be tested on
# its own).
#
# Usage (Linux, from the repo root):
#   bash installer/build_linux.sh [--jobs N]        # same as `all`
#   bash installer/build_linux.sh all [--jobs N]
#   bash installer/build_linux.sh binary [--jobs N] # PyInstaller only
#   bash installer/build_linux.sh deb               # needs an existing bundle
#   bash installer/build_linux.sh rpm               # needs an existing bundle
#   bash installer/build_linux.sh --help
#
# Output in dist/:
#   dist/easy-math-lang/                 the shared PyInstaller onedir bundle
#   easymath_<ver>_amd64.deb             (Debian/Ubuntu install)
#   easymath-<ver>-1.x86_64.rpm          (Fedora/RHEL/openSUSE install)
#   EasyMathLang-Debian-amd64.deb        (stable .deb for Debian/Ubuntu/Mint)
#   EasyMathLang-Fedora-amd64.rpm        (stable .rpm for Fedora/RHEL/openSUSE)
#
# Tool requirements per subcommand:
#   binary:  uv (+ pyinstaller, fetched by uv from the frozen lockfile)
#   deb:     dpkg-deb (no PyInstaller, no uv needed — the version is read
#            from pyproject.toml with plain python3's tomllib)
#   rpm:     rpmbuild (no PyInstaller, no uv needed)
#   all:     uv for `binary`, dpkg-deb for the .deb (hard requirement as
#            before); rpmbuild is optional — without it the .deb is still
#            built and the .rpm step is skipped with a warning. `rpm`
#            alone treats a missing rpmbuild as a hard error instead.
#
# The `deb` and `rpm` subcommands never invoke PyInstaller. They need a
# bundle produced by `binary` (or checked out from CI's bundle artifact):
# dist/easy-math-lang/ with the three executables
# (easy-math-lang, easy-math-lsp, easy-math-editor) and one shared
# _internal/ directory. If any of that is missing they fail fast with a
# clear message instead of packaging a broken bundle.
#
# Installed FHS layout (same as installer/PKGBUILD and as the .rpm spec):
#   /usr/bin/easy-math-lang, ezmath, easy-math-lsp, easy-math-editor -> lib
#   /usr/lib/easy-math-lang/easy-math-editor, easy-math-lang, easy-math-lsp
#     + one shared _internal/ (the PyInstaller onedir bundle for the
#     compiler CLI, the language server and the desktop editor)
#   /usr/share/applications/easy-math-editor.desktop
#   /usr/share/icons/hicolor/<size>x<size>/apps/ezmath.png (16/32/48/64/
#     128/256, backing the desktop entry's Icon=ezmath)
#   /usr/share/doc/easymath/                    (README, copyright,
#                                                 THIRD_PARTY_LICENSES)
#   /usr/share/licenses/easymath/               (LICENSE,
#                                                 THIRD_PARTY_LICENSES;
#                                                 for RPM)
#
# Both packages are assembled from ONE shared staging function (stage_fhs)
# so the .deb and the .rpm cannot drift apart. Version always comes from
# pyproject.toml — never hard-coded.
set -euo pipefail
cd "$(dirname "$0")/.."

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

# Read [project].version from pyproject.toml (stdlib tomllib; plain python3
# preferred so the deb/rpm stages need no uv environment).
read_version() {
  if command -v python3 >/dev/null 2>&1 \
    && python3 -c 'import tomllib,sys; sys.stdout.write(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])' 2>/dev/null; then
    return 0
  fi
  if command -v uv >/dev/null 2>&1; then
    uv run python -c 'import tomllib,sys; sys.stdout.write(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])'
    return 0
  fi
  echo "ERROR: cannot read pyproject.toml version (no python3 with tomllib and no uv)" >&2
  return 1
}

# Fail fast unless a usable bundle exists at dist/easy-math-lang/.
require_bundle() {
  local missing=0
  for f in easy-math-lang easy-math-lsp easy-math-editor; do
    if [ ! -x "dist/easy-math-lang/$f" ]; then
      echo "ERROR: dist/easy-math-lang/$f is missing or not executable." >&2
      missing=1
    fi
  done
  if [ ! -d "dist/easy-math-lang/_internal" ]; then
    echo "ERROR: dist/easy-math-lang/_internal/ is missing." >&2
    missing=1
  fi
  if [ "$missing" -ne 0 ]; then
    echo "ERROR: run 'bash installer/build_linux.sh binary' first (in CI:" >&2
    echo "       this job downloads the bundle artifact instead)." >&2
    exit 1
  fi
}

# Stage the full FHS tree into $1 (created fresh). Shared by the .deb and
# the .rpm so the two packages cannot drift apart — do not duplicate or
# fork this function; edit it once, here.
stage_fhs() {
  local stage="$1"
  rm -rf "$stage"
  mkdir -p "$stage/usr/bin" "$stage/usr/lib/easy-math-lang" \
    "$stage/usr/share/applications" "$stage/usr/share/doc/easymath" \
    "$stage/usr/share/licenses/easymath"

  # Shared PyInstaller onedir bundle (one _internal for CLI + LSP + editor).
  cp -a dist/easy-math-lang/. "$stage/usr/lib/easy-math-lang/"
  chmod +x "$stage/usr/lib/easy-math-lang/easy-math-lang" \
    "$stage/usr/lib/easy-math-lang/easy-math-lsp" \
    "$stage/usr/lib/easy-math-lang/easy-math-editor"

  ln -s /usr/lib/easy-math-lang/easy-math-lang "$stage/usr/bin/easy-math-lang"
  ln -s easy-math-lang "$stage/usr/bin/ezmath"
  ln -s /usr/lib/easy-math-lang/easy-math-lsp "$stage/usr/bin/easy-math-lsp"
  ln -s /usr/lib/easy-math-lang/easy-math-editor "$stage/usr/bin/easy-math-editor"
  ls -l "$stage/usr/bin" "$stage/usr/lib/easy-math-lang"

  install -m644 installer/easy-math-editor.desktop \
    "$stage/usr/share/applications/easy-math-editor.desktop"
  # Hicolor app icons backing the desktop entry's Icon=ezmath (mirrors
  # the PKGBUILD package() installs; one PNG per size).
  for size in 16 32 48 64 128 256; do
    install -m644 -D "icons/ezmath-${size}.png" \
      "$stage/usr/share/icons/hicolor/${size}x${size}/apps/ezmath.png"
  done
  install -m644 README.md "$stage/usr/share/doc/easymath/README.md"
  install -m644 LICENSE "$stage/usr/share/licenses/easymath/LICENSE"
  # MIT license text plus third-party notices (CeTZ is LGPL-3.0-or-later,
  # bundled for offline *draw).
  install -m644 THIRD_PARTY_LICENSES "$stage/usr/share/licenses/easymath/THIRD_PARTY_LICENSES"
  install -m644 THIRD_PARTY_LICENSES "$stage/usr/share/doc/easymath/THIRD_PARTY_LICENSES"
  # Debian requires a copyright file (MIT text lives in LICENSE).
  cp -f LICENSE "$stage/usr/share/doc/easymath/copyright"
  chmod 644 "$stage/usr/share/doc/easymath/copyright"
}

# --------------------------------------------------------------------------
# Stages
# --------------------------------------------------------------------------

cmd_binary() {
  if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv not found — install it first (Debian/Ubuntu: sudo apt install uv," >&2
    echo "       or see https://docs.astral.sh/uv/)" >&2
    exit 1
  fi
  echo "Building the shared Linux binary bundle (PyInstaller) ..."
  # The PyInstaller flags live in one place (see scripts/build_binaries.py).
  uv run --frozen python scripts/build_binaries.py "$@"
  test -x dist/easy-math-lang/easy-math-lang
  echo 'Bundle OK: dist/easy-math-lang/'
}

cmd_deb() {
  if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "ERROR: dpkg-deb not found — install it first (Debian/Ubuntu: sudo apt install dpkg)" >&2
    exit 1
  fi
  require_bundle
  local ver stage deb
  ver="$(read_version)"
  echo "Building EasyMathLang Debian package for version $ver"
  stage="dist/linux-stage/easymath_${ver}_amd64"
  stage_fhs "$stage"

  # --- .deb metadata -----------------------------------------------------
  mkdir -p "$stage/DEBIAN"
  cat > "$stage/DEBIAN/control" <<EOF
Package: easymath
Version: ${ver}-1
Section: math
Priority: optional
Architecture: amd64
Maintainer: duo8097 <Imanoob8097@gmail.com>
Description: Plain-text math documents to PDF, images, HTML and Typst
 Compiler, language server and desktop editor for the Easy Math
 language (.ezmath files for teachers and students).
Recommends: libgl1, fontconfig
EOF
  chmod 755 "$stage/DEBIAN"
  chmod 644 "$stage/DEBIAN/control"

  deb="dist/easymath_${ver}_amd64.deb"
  dpkg-deb --build "$stage" "$deb"
  cp -f "$deb" dist/EasyMathLang-Debian-amd64.deb
  echo "Built $deb"
  ls -lh dist/EasyMathLang-Debian-amd64.deb
}

cmd_rpm() {
  if ! command -v rpmbuild >/dev/null 2>&1; then
    echo "ERROR: rpmbuild not found — install it first (Debian/Ubuntu: sudo apt install rpm," >&2
    echo "       Fedora: sudo dnf install rpm-build)" >&2
    exit 1
  fi
  require_bundle
  local ver stage topdir rpm rpm_ver
  ver="$(read_version)"
  # RPM spec Version cannot contain hyphens; convert prereleases (e.g. 8.0.0-rc.1 -> 8.0.0.rc.1).
  rpm_ver="${ver//-/.}"
  echo "Building EasyMathLang Fedora/RHEL package for version $ver"
  stage="dist/linux-stage/easymath_${ver}_amd64"
  stage_fhs "$stage"

  topdir="$PWD/dist/rpmbuild"
  rm -rf "$topdir"
  mkdir -p "$topdir"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
  cat > "$topdir/SPECS/easymath.spec" <<EOF
Name: easymath
Version: ${rpm_ver}
Release: 1
Summary: Plain-text math documents to PDF, images, HTML and Typst
License: MIT
URL: https://github.com/duo8097/easy-math-lang
BuildArch: x86_64
Recommends: mesa-libGL, fontconfig
# This package ships a self-contained prebuilt frozen bundle (deps
# resolve from its own _internal/), not anything built in this spec's
# buildroot. The bundle embeds build-host-absolute rpath entries (e.g.
# the build image's Python runpath) in a few lib-dynload modules; those
# paths do not exist on end-user machines but are flagged by rpm's
# brp-check-rpath/ERROR 0002, killing an otherwise fine build. The
# documented Fedora remedy for prebuilt payloads is to waive this one
# check for this package.
%global __brp_check_rpaths %{nil}
# The bundle also carries private libraries with renamed/hashed sonames
# (e.g. libscipy_openblas64_-f48b354e.so) that no repository provides;
# without this filter dnf tries to satisfy their auto-generated
# Requires and the install fails with "nothing provides ...". The app
# only needs the system EGL/desktop GL stack, expressed below as
# Recommends (soft, like the .deb's libgl1/fontconfig).
%global __requires_exclude_from ^/usr/lib/easy-math-lang/.*$

%description
Compiler, language server and desktop editor for the Easy Math
language (.ezmath files for teachers and students).

%install
mkdir -p %{buildroot}
cp -a %{_sourcedir}/stage/* %{buildroot}/

%files
/usr/bin/easy-math-lang
/usr/bin/ezmath
/usr/bin/easy-math-lsp
/usr/bin/easy-math-editor
/usr/lib/easy-math-lang/
/usr/share/applications/easy-math-editor.desktop
/usr/share/icons/hicolor/16x16/apps/ezmath.png
/usr/share/icons/hicolor/32x32/apps/ezmath.png
/usr/share/icons/hicolor/48x48/apps/ezmath.png
/usr/share/icons/hicolor/64x64/apps/ezmath.png
/usr/share/icons/hicolor/128x128/apps/ezmath.png
/usr/share/icons/hicolor/256x256/apps/ezmath.png
/usr/share/doc/easymath/
/usr/share/licenses/easymath/
EOF
  mkdir -p "$topdir/SOURCES"
  cp -a "$stage" "$topdir/SOURCES/stage"
  # The DEBIAN staging dir is deb-only; strip it before packing.
  rm -rf "$topdir/SOURCES/stage/DEBIAN"
  rpmbuild -bb "$topdir/SPECS/easymath.spec" \
    --define "_topdir $topdir" \
    --define "_sourcedir $topdir/SOURCES"
  rpm="$(find "$topdir/RPMS" -name '*.rpm' | head -n 1)"
  cp -f "$rpm" "dist/easymath-${ver}-1.x86_64.rpm"
  cp -f "$rpm" dist/EasyMathLang-Fedora-amd64.rpm
  echo "Built dist/easymath-${ver}-1.x86_64.rpm"
  ls -lh \
    "dist/easymath-${ver}-1.x86_64.rpm" \
    dist/EasyMathLang-Fedora-amd64.rpm
}

cmd_all() {
  if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "ERROR: dpkg-deb not found — install it first (Debian/Ubuntu: sudo apt install dpkg)" >&2
    exit 1
  fi
  local ver
  ver="$(read_version)"
  echo "Building EasyMathLang Linux installers for version $ver"
  cmd_binary "$@"
  cmd_deb
  if ! command -v rpmbuild >/dev/null 2>&1; then
    echo "WARNING: rpmbuild not found — skipping .rpm (install the 'rpm' package)" >&2
    ls -lh dist/*.deb
    echo 'Build OK (deb only)'
    exit 0
  fi
  cmd_rpm
  echo 'Build OK:'
  ls -l dist/EasyMathLang-Debian-amd64.deb dist/EasyMathLang-Fedora-amd64.rpm
}

usage() {
  cat <<'EOF'
Usage:
  bash installer/build_linux.sh [--jobs N]        # same as `all`
  bash installer/build_linux.sh all [--jobs N]
  bash installer/build_linux.sh binary [--jobs N] # PyInstaller only
  bash installer/build_linux.sh deb               # needs an existing bundle
  bash installer/build_linux.sh rpm               # needs an existing bundle

Tool requirements per subcommand:
  binary: uv (+ pyinstaller via uv)
  deb:    dpkg-deb (no PyInstaller)
  rpm:    rpmbuild (no PyInstaller)
  all:    uv for binary, dpkg-deb for the .deb; rpmbuild optional
EOF
}

# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------

cmd="${1:-all}"
if [[ "$cmd" == -* ]]; then
  # No subcommand: flags apply to `all` (e.g. bash build_linux.sh --jobs 2)
  cmd_all "$@"
  exit 0
fi
case "$cmd" in
  all)
    shift
    cmd_all "$@"
    ;;
  binary)
    shift
    cmd_binary "$@"
    ;;
  deb)
    shift
    [ $# -eq 0 ] || { echo "ERROR: 'deb' takes no arguments (the bundle is reused as-is)" >&2; exit 2; }
    cmd_deb
    ;;
  rpm)
    shift
    [ $# -eq 0 ] || { echo "ERROR: 'rpm' takes no arguments (the bundle is reused as-is)" >&2; exit 2; }
    cmd_rpm
    ;;
  --help|-h|help)
    usage
    ;;
  *)
    echo "ERROR: unknown subcommand: $cmd" >&2
    usage >&2
    exit 2
    ;;
esac
