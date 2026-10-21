#!/usr/bin/env bash
# Local build of the Easy Math binaries and the macOS app bundle
# (mirrors .github/workflows/build-installers.yml, minus the DMG).
#
# Usage (macOS, from the repo root):
#   bash scripts/build_macos.sh
#
# Output: dist/easy-math-lang, dist/ezmath (alias copy),
#         dist/easy-math-lsp, dist/easy-math-editor.app (helpers bundled
#         into Contents/Resources/bin/, ad-hoc signed).
set -euo pipefail
cd "$(dirname "$0")/.."

[ "$(uname -m)" = "arm64" ] || { echo "This build targets Apple Silicon (arm64) only" >&2; exit 1; }

# The PyInstaller flags live in one place (see scripts/build_binaries.py).
uv run python scripts/build_binaries.py

# Bundle the helpers into the .app, prune the Qt tool apps, sign it.
bash scripts/package_macos.sh

echo 'Build OK:'
ls -l dist/easy-math-lang dist/ezmath dist/easy-math-lsp
ls -ld dist/easy-math-editor.app
