#!/usr/bin/env bash
# Build the Easy Math Linux installers (.deb + .rpm) from PyInstaller
# binaries (mirrors scripts/build_macos.sh and the CI workflow
# .github/workflows/build-linux-installers.yml).
#
# Usage (Linux, from the repo root):
#   bash installer/build_linux.sh
#
# Output in dist/:
#   easymath_<ver>_amd64.deb            (Debian/Ubuntu install)
#   easymath-<ver>-1.x86_64.rpm         (Fedora/RHEL/openSUSE install)
#   EasyMathLang-Linux-amd64.deb/.rpm   (stable names for GitHub Releases)
#
# Installed FHS layout (same as installer/PKGBUILD):
#   /usr/bin/easy-math-lang, ezmath, easy-math-lsp, easy-math-editor -> lib
#   /usr/lib/easy-math-lang/easy-math-editor/   (onedir GUI bundle)
#   /usr/share/applications/easy-math-editor.desktop
#   /usr/share/doc/easymath/                    (README, copyright)
#   /usr/share/licenses/easymath/               (LICENSE, for RPM)
#
# Requires: uv, pyinstaller (via uv), dpkg-deb. rpmbuild is optional:
# without it the .deb is still built and the .rpm step is skipped with
# a warning (CI installs the `rpm` package first).
set -euo pipefail
cd "$(dirname "$0")/.."

VER="$(uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")"
echo "Building EasyMathLang Linux installers for version $VER"

if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "ERROR: dpkg-deb not found — install it first (Debian/Ubuntu: sudo apt install dpkg)" >&2
  exit 1
fi

cat > entry_compiler.py <<'EOF'
from compiler import main
if __name__ == "__main__":
    main()
EOF

cat > entry_lsp.py <<'EOF'
from lsp.server import main
if __name__ == "__main__":
    main()
EOF

cat > entry_editor.py <<'EOF'
from editor.app import main
if __name__ == "__main__":
    main()
EOF

cleanup() {
  rm -f entry_compiler.py entry_lsp.py entry_editor.py
}
trap cleanup EXIT

uv run pyinstaller entry_compiler.py \
  --name easy-math-lang \
  --onefile \
  --collect-all typst \
  --collect-all numpy \
  --collect-all matplotlib \
  --noconfirm

# `ezmath` is the short CLI alias (pyproject [project.scripts]); it is
# the same binary under another name, so copy instead of rebuilding.
cp -f dist/easy-math-lang dist/ezmath

uv run pyinstaller entry_lsp.py \
  --name easy-math-lsp \
  --onefile \
  --collect-all pygls \
  --collect-all typst \
  --collect-all numpy \
  --noconfirm

uv run pyinstaller entry_editor.py \
  --name easy-math-editor \
  --onedir \
  --windowed \
  --hidden-import PySide6.QtPdf \
  --hidden-import PySide6.QtPdfWidgets \
  --hidden-import editor.app \
  --hidden-import editor.editor_widget \
  --hidden-import editor.lsp_client \
  --hidden-import editor.main_window \
  --collect-all typst \
  --collect-all numpy \
  --collect-all matplotlib \
  --noconfirm

chmod +x dist/easy-math-lang dist/ezmath dist/easy-math-lsp
test -x dist/easy-math-editor/easy-math-editor

# --- Stage the FHS tree -------------------------------------------------
STAGE="dist/linux-stage/easymath_${VER}_amd64"
rm -rf "$STAGE"
mkdir -p "$STAGE/usr/bin" "$STAGE/usr/lib/easy-math-lang" \
  "$STAGE/usr/share/applications" "$STAGE/usr/share/doc/easymath" \
  "$STAGE/usr/share/licenses/easymath"

install -m755 dist/easy-math-lang "$STAGE/usr/bin/easy-math-lang"
install -m755 dist/ezmath "$STAGE/usr/bin/ezmath"
install -m755 dist/easy-math-lsp "$STAGE/usr/bin/easy-math-lsp"
cp -a dist/easy-math-editor "$STAGE/usr/lib/easy-math-lang/"
chmod +x "$STAGE/usr/lib/easy-math-lang/easy-math-editor/easy-math-editor"
ln -s /usr/lib/easy-math-lang/easy-math-editor/easy-math-editor \
  "$STAGE/usr/bin/easy-math-editor"

install -m644 installer/easy-math-editor.desktop \
  "$STAGE/usr/share/applications/easy-math-editor.desktop"
install -m644 README.md "$STAGE/usr/share/doc/easymath/README.md"
install -m644 LICENSE "$STAGE/usr/share/licenses/easymath/LICENSE"
# Debian requires a copyright file (MIT text lives in LICENSE).
cp -f LICENSE "$STAGE/usr/share/doc/easymath/copyright"
chmod 644 "$STAGE/usr/share/doc/easymath/copyright"

# --- .deb ---------------------------------------------------------------
mkdir -p "$STAGE/DEBIAN"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: easymath
Version: ${VER}-1
Section: math
Priority: optional
Architecture: amd64
Maintainer: duo8097 <Imanoob8097@gmail.com>
Description: Plain-text math documents to PDF, images, HTML and Typst
 Compiler, language server and desktop editor for the Easy Math
 language (.ezmath files for teachers and students).
Recommends: libgl1, fontconfig
EOF
chmod 755 "$STAGE/DEBIAN"
chmod 644 "$STAGE/DEBIAN/control"

DEB="dist/easymath_${VER}_amd64.deb"
dpkg-deb --build "$STAGE" "$DEB"
cp -f "$DEB" dist/EasyMathLang-Linux-amd64.deb
echo "Built $DEB"

# --- .rpm ---------------------------------------------------------------
if ! command -v rpmbuild >/dev/null 2>&1; then
  echo "WARNING: rpmbuild not found — skipping .rpm (install the 'rpm' package)" >&2
  ls -lh dist/*.deb
  echo 'Build OK (deb only)'
  exit 0
fi

TOPDIR="$PWD/dist/rpmbuild"
rm -rf "$TOPDIR"
mkdir -p "$TOPDIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
cat > "$TOPDIR/SPECS/easymath.spec" <<EOF
Name: easymath
Version: ${VER}
Release: 1
Summary: Plain-text math documents to PDF, images, HTML and Typst
License: MIT
URL: https://github.com/duo8097/easy-math-lang
BuildArch: x86_64
Recommends: mesa-libGL, fontconfig

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
/usr/share/doc/easymath/
/usr/share/licenses/easymath/
EOF
mkdir -p "$TOPDIR/SOURCES"
cp -a "$STAGE" "$TOPDIR/SOURCES/stage"
# Strip the DEBIAN metadata dir: it is deb-only.
rm -rf "$TOPDIR/SOURCES/stage/DEBIAN"
rpmbuild -bb "$TOPDIR/SPECS/easymath.spec" \
  --define "_topdir $TOPDIR" \
  --define "_sourcedir $TOPDIR/SOURCES"
RPM="$(find "$TOPDIR/RPMS" -name '*.rpm' | head -n 1)"
cp -f "$RPM" "dist/easymath-${VER}-1.x86_64.rpm"
cp -f "$RPM" dist/EasyMathLang-Linux-amd64.rpm
echo "Built dist/easymath-${VER}-1.x86_64.rpm"

ls -lh dist/*.deb dist/*.rpm
echo 'Build OK:'
ls -l dist/EasyMathLang-Linux-amd64.deb dist/EasyMathLang-Linux-amd64.rpm
