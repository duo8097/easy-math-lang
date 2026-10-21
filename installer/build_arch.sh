#!/usr/bin/env bash
# Build the Arch package (installer/PKGBUILD) with makepkg.
#
# Usage (Arch Linux, from the repo root):
#   bash installer/build_arch.sh
#
# Output: easy-math-lang-git-<version>-<rel>-x86_64.pkg.tar.zst in the
#         repo root.
#
# The working tree is packed into a source tarball and a copy of the
# PKGBUILD is patched to use it, so the package contains exactly what is
# checked out: no git metadata and no access to the upstream repository
# are needed (CI builds a pull request this way). Everything else
# (PyInstaller flags, file layout, dependencies) is untouched.
set -euo pipefail
cd "$(dirname "$0")/.."

REPO="$PWD"

command -v makepkg >/dev/null 2>&1 || {
  echo "ERROR: makepkg not found — install it (Arch: sudo pacman -S base-devel)" >&2
  exit 1
}
command -v uv >/dev/null 2>&1 || {
  echo "ERROR: uv not found — install it (Arch: sudo pacman -S uv)" >&2
  exit 1
}

BUILD_DIR="$(mktemp -d)"
cleanup() { rm -rf "$BUILD_DIR"; }
trap cleanup EXIT

# --- Pack the working tree -------------------------------------------------
# The tarball's top-level directory must be the package name: makepkg
# extracts it into $srcdir/easy-math-lang, which is where the PKGBUILD
# builds from.
tar --exclude-vcs \
    --exclude='./dist' --exclude='./build' --exclude='./.venv' \
    --exclude='./.pytest_cache' --exclude='./.ruff_cache' \
    --exclude='./staging' --exclude='./*.pkg.tar.zst' \
    -czf "$BUILD_DIR/easy-math-lang.tar.gz" \
    --transform 's|^\./|easy-math-lang/|' .
SHA="$(sha256sum "$BUILD_DIR/easy-math-lang.tar.gz" | cut -d' ' -f1)"

# --- Patch the PKGBUILD to use the tarball --------------------------------
sed -e "s|^source=.*|source=('easy-math-lang.tar.gz')|" \
    -e "s|^sha256sums=.*|sha256sums=('${SHA}')|" \
    installer/PKGBUILD > "$BUILD_DIR/PKGBUILD"

# --- Build -----------------------------------------------------------------
# PKGDEST puts the finished package in the repo root; the build itself
# happens in the temporary directory (src/, pkg/ stay out of the tree).
( cd "$BUILD_DIR" && PKGDEST="$REPO" makepkg -f --noconfirm --noprogressbar )

PKG="$(ls -1t "$REPO"/easy-math-lang-git-*.pkg.tar.zst 2>/dev/null | head -n 1)"
[ -n "$PKG" ] || { echo "ERROR: no package produced" >&2; exit 1; }

echo 'Build OK:'
ls -lh "$PKG"
