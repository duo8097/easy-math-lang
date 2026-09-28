#!/usr/bin/env bash
# Local test build of the Easy Math binaries on macOS (mirrors
# .github/workflows/build-macos-installer.yml, minus DMG creation).
#
# Usage (macOS, from the repo root):
#   bash scripts/build_macos.sh
#
# Output: dist/easy-math-lang, dist/ezmath (alias copy),
#         dist/easy-math-lsp, dist/easy-math-editor.app (helpers bundled
#         into Contents/Resources/bin/, mirroring CI).
set -euo pipefail
cd "$(dirname "$0")/.."

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
  --noconfirm

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
  --collect-all typst \
  --collect-all numpy \
  --noconfirm

du -sh dist/easy-math-editor.app

# `ezmath` is the short CLI alias (pyproject [project.scripts]); it is
# the same binary under another name, so copy instead of rebuilding.
test -f dist/easy-math-lang || { echo "compiler output missing" >&2; exit 1; }
cp -f dist/easy-math-lang dist/ezmath
chmod +x dist/ezmath dist/easy-math-lang dist/easy-math-lsp

# Bundle helpers INTO the .app so dragging just the .app works
# (mirrors CI; fails loudly when PyInstaller emits no bundle).
APP="dist/easy-math-editor.app"
if [ ! -d "$APP" ]; then
  echo "expected $APP (PyInstaller --windowed --onedir must emit a bundle)" >&2
  exit 1
fi
mkdir -p "$APP/Contents/Resources/bin"
cp -f dist/easy-math-lang dist/ezmath dist/easy-math-lsp "$APP/Contents/Resources/bin/"
chmod +x "$APP"/Contents/Resources/bin/*

echo 'Build OK:'
ls -l dist/easy-math-lang dist/ezmath dist/easy-math-lsp
ls -ld "$APP"
ls -l "$APP/Contents/Resources/bin"
