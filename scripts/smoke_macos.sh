#!/usr/bin/env bash
# Smoke-test the STAGED macOS app (staging/, not dist/): the bundled
# compiler must render PDF/PNG/SVG/HTML, the bundled LSP must start, and
# the editor must stay up headless. Also logs spctl/xattr for information.
#
# Usage (on a Mac, from the repo root, after the staging step):
#   bash scripts/smoke_macos.sh [staging-dir]   # default: staging
#
# Fails loudly on any functional failure. spctl/xattr output is
# informational only: ad-hoc signatures are not notarized, so Gatekeeper
# rejection is expected and must not fail the build.
set -euo pipefail
cd "$(dirname "$0")/.."

STAGING="${1:-staging}"
APP="$STAGING/easy-math-editor.app"
BIN="$APP/Contents/Resources/bin"
EDITOR_BIN="$APP/Contents/MacOS/easy-math-editor"

fail() { echo "::error::$*" >&2; exit 1; }

[ -d "$APP" ] || fail "expected staged app at $APP (run the staging step first)"
[ -x "$BIN/easy-math-lang" ] || fail "missing helper $BIN/easy-math-lang"
[ -x "$BIN/ezmath" ] || fail "missing helper $BIN/ezmath"
[ -x "$BIN/easy-math-lsp" ] || fail "missing helper $BIN/easy-math-lsp"
[ -x "$EDITOR_BIN" ] || fail "missing editor binary $EDITOR_BIN"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "== compiler version =="
"$BIN/easy-math-lang" --version

echo "== PDF: examples/example.ezmath =="
"$BIN/easy-math-lang" examples/example.ezmath "$TMP/smoke.pdf"
[ -s "$TMP/smoke.pdf" ] || fail "compiler produced an empty PDF"

# PNG/SVG with several pages land as stem-1.ext, stem-2.ext, ... — accept
# either the single file or the paged siblings, but all must be non-empty.
assert_files() {
  local base="$1"
  if [ -s "$base" ]; then return 0; fi
  local stem="${base%.*}" ext="${base##*.}" hits=0 f
  for f in "$stem"-*."$ext"; do
    [ -s "$f" ] || fail "empty paged output $f"
    hits=1
  done
  [ "$hits" = 1 ] || fail "no output produced for $base"
}

echo "== PNG export =="
"$BIN/easy-math-lang" --format png examples/example.ezmath -o "$TMP/smoke.png"
assert_files "$TMP/smoke.png"

echo "== SVG export =="
"$BIN/easy-math-lang" --format svg examples/example.ezmath -o "$TMP/smoke.svg"
assert_files "$TMP/smoke.svg"

echo "== HTML export =="
"$BIN/easy-math-lang" --format html examples/example.ezmath -o "$TMP/smoke.html"
[ -s "$TMP/smoke.html" ] || fail "compiler produced an empty HTML file"

echo "== LSP starts and stays up =="
sleep 10 | "$BIN/easy-math-lsp" >"$TMP/lsp.log" 2>&1 &
LSP_PID=$!
sleep 2
if kill -0 "$LSP_PID" 2>/dev/null; then
  echo "easy-math-lsp alive after 2s (pid $LSP_PID)"
  kill "$LSP_PID" 2>/dev/null || true
  wait "$LSP_PID" 2>/dev/null || true
else
  set +e
  wait "$LSP_PID"
  code=$?
  set -e
  fail "easy-math-lsp exited early with code $code (log: $(cat "$TMP/lsp.log"))"
fi

echo "== Qt platform plugins (cocoa must be bundled) =="
ls -l "$APP/Contents/Frameworks/PySide6/Qt/plugins/platforms" || fail "missing Qt platforms plugin dir $APP/Contents/Frameworks/PySide6/Qt/plugins/platforms"
[ -f "$APP/Contents/Frameworks/PySide6/Qt/plugins/platforms/libqcocoa.dylib" ] || fail "missing libqcocoa.dylib — Qt platform plugin not bundled"

echo "== editor launches headless =="
if command -v timeout >/dev/null 2>&1; then
  # GNU timeout: 124 means "still running when killed" -> success.
  set +e
  QT_QPA_PLATFORM=offscreen timeout 8 "$EDITOR_BIN" >"$TMP/editor.log" 2>&1
  code=$?
  set -e
  [ "$code" = 124 ] || fail "editor exited early with code $code (log tail: $(tail -20 "$TMP/editor.log"))"
  echo "editor still running at 8s (exit 124) — OK"
else
  QT_QPA_PLATFORM=offscreen "$EDITOR_BIN" >"$TMP/editor.log" 2>&1 &
  ED_PID=$!
  sleep 8
  if kill -0 "$ED_PID" 2>/dev/null; then
    echo "editor still running at 8s (pid $ED_PID) — OK"
    kill "$ED_PID" 2>/dev/null || true
    wait "$ED_PID" 2>/dev/null || true
  else
    set +e
    wait "$ED_PID"
    code=$?
    set -e
    fail "editor exited early with code $code (log tail: $(tail -20 "$TMP/editor.log"))"
  fi
fi

echo "== spctl/xattr (informational; ad-hoc is not notarized) =="
spctl --assess --type execute -vv "$APP" 2>&1 || echo "(info) spctl rejected — expected without notarization"
xattr -lr "$APP" 2>&1 | head -20 || echo "(info) no xattr output"

echo "SMOKE OK"
