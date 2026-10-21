#!/usr/bin/env bash
# Package the macOS app bundle: bundle the helper binaries into the
# .app, prune the nested Qt tool apps and sign the bundle inside-out.
#
# Usage (macOS, from the repo root, after the binaries were built):
#   bash scripts/package_macos.sh [--stage]
#
# Input:  dist/easy-math-lang, dist/ezmath, dist/easy-math-lsp,
#         dist/easy-math-editor.app
# Output: a signed dist/easy-math-editor.app whose helpers live in
#         Contents/Resources/bin. With --stage the release layout is
#         written to staging/ (the folder the DMG is packed from).
set -euo pipefail
cd "$(dirname "$0")/.."

APP="dist/easy-math-editor.app"
BIN="$APP/Contents/Resources/bin"
STAGE="staging"

STAGE_IT=0
for arg in "$@"; do
  case "$arg" in
    --stage) STAGE_IT=1 ;;
    *) echo "::error::unknown option: $arg" >&2; exit 2 ;;
  esac
done

fail() { echo "::error::$*" >&2; exit 1; }

# --- Inputs ----------------------------------------------------------------
for f in dist/easy-math-lang dist/ezmath dist/easy-math-lsp; do
  [ -x "$f" ] || fail "missing $f (run scripts/build_binaries.py first)"
done
[ -d "$APP" ] || fail "expected $APP (PyInstaller --windowed --onedir must emit a bundle)"

# --- Bundle the helpers into the .app --------------------------------------
# A user may drag just the .app to /Applications, so the compiler and the
# language server must live inside it. editor/paths.py searches
# Contents/Resources/bin, so no PATH setup is ever needed.
mkdir -p "$BIN"
cp -f dist/easy-math-lang dist/ezmath dist/easy-math-lsp "$BIN/"
chmod +x "$BIN"/*
ls -l "$BIN"

# --- Prune nested Qt tool apps (must run before signing) -------------------
# PySide6 bundles Qt developer tools (Assistant, Designer, Linguist) as
# nested "*__dot__app" dirs with symlinked Info.plist and executables;
# codesign rejects those, so remove them. Helpers are already bundled at
# this point, signing has not started yet.
for dir in "$APP/Contents/Frameworks" "$APP/Contents/Resources"; do
  [ -d "$dir" ] || continue
  echo "Nested __dot__app dirs under $dir:"
  find "$dir" -name '*__dot__app' -print
  find "$dir" -depth -name '*__dot__app' -exec rm -rf {} +
done
echo "Remaining __dot__app dirs (must be empty):"
find "$APP/Contents" -name '*__dot__app' -print

# --- Sign (inside-out, fails loudly) ---------------------------------------
# Nested code first, the .app bundle last: signing contents after the
# bundle would invalidate the bundle seal, so the final sign must not
# use the recursive flag. No leniency anywhere here (no swallowed exit
# codes): a broken signature must fail the build, never produce a green
# build with a bad signature. Only real Mach-O files are signed (never
# plain directories or scripts): Frameworks holds plain directories such
# as PySide6/numpy/typst that codesign rejects.
codesign --force --sign - dist/easy-math-lang
codesign --force --sign - dist/ezmath
codesign --force --sign - dist/easy-math-lsp
COUNT=0
while IFS= read -r -d '' f; do
  if file -b "$f" | grep -q "Mach-O"; then
    echo "signing $f"
    codesign --force --sign - "$f"
    COUNT=$((COUNT + 1))
  fi
done < <(find "$APP/Contents" -type f -print0)
echo "signed $COUNT Mach-O files under $APP/Contents"
codesign --force --sign - "$APP"
if codesign --verify --deep --strict --verbose=2 "$APP"; then
  echo "bundle verification OK"
else
  echo "::error::verification failed for $APP"
  set +e
  codesign -dvvv "$APP"
  find "$APP" -type l | head -50
  set -e
  exit 1
fi
codesign --verify --strict --verbose=2 \
  dist/easy-math-lang dist/ezmath dist/easy-math-lsp

du -sh "$APP"

# --- Stage the release layout (only the .app ships) ------------------------
# The old EasyMath/{bin,editor} split duplicated Qt (roughly double DMG
# size) and broke the editor when a user dragged just the .app to
# /Applications. The Applications symlink makes drag-and-drop install
# work.
if [ "$STAGE_IT" = 1 ]; then
  rm -rf "$STAGE"
  mkdir -p "$STAGE"
  cp -R "$APP" "$STAGE/"
  ln -s /Applications "$STAGE/Applications"
  # Small README so DMG browsers know what to do.
  cat > "$STAGE/README.txt" <<'EOF'
Easy Math Lang (macOS)
======================
- Drag "easy-math-editor.app" to the Applications folder
  (a shortcut is included in this disk image), or run it
  straight from here.
- First launch: right-click the app -> Open (ad-hoc signed,
  not notarized — see docs/installation.md).
- Helpers (compiler/LSP) live inside the app bundle:
    easy-math-editor.app/Contents/Resources/bin/
  Terminal use:
    BIN="$PWD/easy-math-editor.app/Contents/Resources/bin"
    "$BIN/easy-math-lang" doc.ezmath
  or: export PATH="$BIN:$PATH"
  Export images etc.: easy-math-lang doc.ezmath out.png --format png
EOF
  find "$STAGE" -maxdepth 2 | sort
fi

echo 'Packaging OK'
