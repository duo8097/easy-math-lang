# Changelog

All notable changes to easy-math-lang are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries start at v4.3.0; earlier releases (v0.1.0 … v4.2.0) predate
this file — see the
[GitHub releases page](https://github.com/duo8097/easy-math-lang/releases)
for those.

## [Unreleased]

### Added
- Plot expression hash cache — repeated `*plot(...)` with the same expression skips Matplotlib re-render.
- **CeTZ is vendored and bundled — `*draw` works fully offline, with no first-run download.** The Typst packages `*draw` needs (cetz 0.4.2 and oxifmt 1.0.0 — its only transitive dependency, verified by compiling offline against an empty package cache) are committed under `vendor/typst-packages/` (downloaded and SHA-256-verified by `scripts/vendor_typst_packages.py`; manuals, galleries and docs are pruned — 473.4 KiB in total, `typst.toml`, all `.typ` sources, the LICENSE files and CeTZ's WASM core are kept) and ship in every packaged build: one copy under the shared bundle's `_internal/typst-packages/` (Windows, macOS, Debian/RPM, Arch; the CLI, the LSP and the editor all see the same copy) and in the source tree for checkouts. `_run_typst_export()` passes the bundle as Typst's `package_path`, which Typst consults before its user cache and the network; when the bundle is missing the compiler falls back to Typst's usual cache/download behavior and never crashes. The offline error message now only appears when the bundle is genuinely missing and the download also fails. cetz/oxifmt remain unmodified and replaceable; they are not MIT — `THIRD_PARTY_LICENSES` (CeTZ is LGPL-3.0-or-later) lists them with upstream URLs and ships in all installers. `src/typst_bundle/` is the single source of truth for the pinned versions; `tests/test_typst_bundle.py` enforces the vendored tree matches (each package's `typst.toml` must match its directory) and compiles `*draw` with every package-cache location redirected to an empty temporary directory, asserting the cache stays empty; `tests/test_packaged_build.py` does the same against the frozen binaries with dead proxies.
- **`*equal-angle(A ; B ; C ; D ; E ; F)`** — angle ABC equals angle DEF, implemented end to end. The constraint solver moves the free points until the two interior angles match, and codegen draws the same equality mark on both angles (an arc with a tick, the same arc radius as `*angle`). The editor's `Insert command…` button and the template-window command palette now open a `geo-equal-angle` parameter dialog (six point fields, `*draw`-wrapped) instead of greying the card out, and the gallery thumbnail is re-rendered. Docs: `docs/geometry.md` (new section), `docs/cheatsheet.md` (constraint table), `rule.txt`, plus a runnable fourth block in `examples/draw_test.ezmath`.
- LSP hover + completion description for `*draw(...)` — the language server advertised built-in descriptions but hovering/completing `*draw` gave nothing (the draw-block symbol shadowed it). `*draw` is now documented like every other built-in.
- Linux input methods (Vietnamese etc.) — the desktop editor now supports fcitx5 IME methods (e.g., fcitx5-lotus Vietnamese Telex) on Linux. The fix activates only when fcitx is evident (`QT_IM_MODULE`/`XMODIFIERS`/`GTK_IM_MODULE`) and leaves ibus users untouched. The `.deb`/`.rpm` installers bundle a plugin compiled from source in CI against PySide6's exact Qt, and the Arch package bundles the system `fcitx5-qt` plugin when its Qt matches (frozen builds verify the plugin is bundled); from source, a matching system plugin is used automatically. `EZMATH_NO_IME_FIX=1` opts out.

### Changed
- LSP source-range slicing fixed (`analysis.py`) so `calc(...)` expressions use original source offsets.

### Fixed
- Arch package (`installer/PKGBUILD`) installed only the three
  executables and not the shared `_internal/` library directory, so the
  packaged binaries could not run at all. It now installs the whole
  shared bundle (like the `.deb`/`.rpm` path) and also ships
  `THIRD_PARTY_LICENSES`.
- Windows installer version — `installer/setup.iss` no longer carries a
  hard-coded `AppVersion` (it lagged behind at 5.1.0 while the project was
  5.2.0). CI reads the version from `pyproject.toml` (`tomllib`) and injects
  it via `/DAppVersion=`; a hand-run `ISCC.exe installer\setup.iss` falls
  back to a `0.0.0` placeholder instead of a stale number.
- Arch `PKGBUILD` `pkgver` placeholder updated to 5.2.0 (overridden by
  `pkgver()` at build time); a regression test keeps it in sync with
  `pyproject.toml`.
- Preview manifest (`manifest.json`) now regenerated automatically in test setup; stale-preview bugs no longer hidden by skips.
- Duplicate docstring removed from `pipeline.py`.

### Changed

- **Smaller installers** — the packaged binaries no longer ship three
  separate copies of the heavy runtime libraries. The compiler CLI, the
  language server and the desktop editor are now assembled into one shared
  PyInstaller onedir bundle (`dist/easy-math-lang/` with a single `_internal/`
  directory holding NumPy, Matplotlib, Typst, PySide6, …) instead of three
  independent library sets. The CLI and the LSP reuse the desktop editor's
  collected libraries, so an install now contains exactly one copy of each.
  User-facing commands (`easy-math-lang`, `ezmath`, `easy-math-lsp`) and
  behavior are unchanged; the LSP starts slightly faster with the shared
  library directory.

## [5.2.0] - 2026-11-01

### Added

- **Construction points** — a point can now be *computed* instead of
  free: `*point(NAME = constructor(...))` on the right-hand side of
  `*point` defines a **derived** point (never a solver variable) from
  other points. Eight constructors: `midpoint(A ; B)`,
  `foot(P ; line(A ; B))`, `reflect(P ; line(A ; B))` /
  `reflect(P ; O)`, `intersect(...)`, `centroid(A ; B ; C)`,
  `circumcenter(A ; B ; C)`, `incenter(A ; B ; C)` and
  `orthocenter(A ; B ; C)`; constructors nest inside constructors
  (`midpoint(A ; midpoint(B ; C))`), referenced points may be defined
  later (dependencies are topologically sorted), and constraints may
  reference constructed points — they are recomputed on every solver
  step, so a derived point always tracks its inputs. Disambiguation is
  exact: `NAME = x, y` stays coordinates (thousands-commas intact),
  `NAME = ident(` is a construction, so existing `*point` behavior and
  the 3-argument `*midpoint(A ; B ; M)` constraint are unchanged.
  `intersect(line ; circle ; k)` picks the k-th crossing walking from A
  toward B, `intersect(circle ; circle ; k)` the k-th on the left
  (counterclockwise) side of O1→O2, and k is required for the
  two-solution cases (an error for line + line); documented errors
  cover parallel lines, missed intersections, degenerate lines,
  collinear triangles, unknown constructors (with a suggestion), wrong
  arity and construction cycles. Constructors appear in the LSP's
  completion and hover (`GEOMETRY_CONSTRUCTION_DOCS`) without ever
  raising a false "undefined point" diagnostic.
- **Gallery: Constructions group** — the *draw gallery grew from 20 to
  28 cards with a new **Constructions** group (8 construction cards,
  each with a pre-rendered SVG preview, examples using only fixed
  points); the template window's command palette keeps one row per
  command, with constructions reached through the `*point` row.
- **Docs** — a *Construction points* section in
  [docs/geometry.md](docs/geometry.md) (examples, intersection
  ordering rules, error cases), a quick table in the
  [cheatsheet](docs/cheatsheet.md), and the runnable example
  `examples/construction_points.ezmath` (orthocenter of a triangle
  from two altitude feet).

## [5.1.0] - 2026-10-30

### Added

- **`*draw` geometry gallery** — the Symbol Bar's `*draw` button now
  opens a non-modal window (also `View → Geometry Gallery…`,
  **Ctrl+Shift+G**, or the palette entry `Draw: Geometry Gallery…`)
  listing all 20 geometry commands as cards with pre-rendered SVG
  thumbnails, search and group filters (Shapes / Angles / Constraints /
  Measure & Label). Each card offers **Insert example…** (opens the
  template window below) and **Insert command…** (the existing
  parameter dialog); insertion is block-aware (commands merge into an
  open `*draw(...)` block, single-line blocks are expanded) and always
  a single undo step. `Insert empty block` keeps the old `*draw`
  skeleton insert, which also stays on the palette as `*draw {}`.
  Thumbnails are generated by `scripts/build_draw_previews.py` from
  the catalog examples through the one geometry parser, tracked by a
  hash manifest, and shipped in the source tree, the wheel and the
  PyInstaller bundle — no runtime network.
- **`*draw` template window** — a gallery card's **Insert example…**
  opens a second non-modal window: a large static preview of the
  figure on the left with the complete `*draw(...)` block underneath,
  **editable** so the document gets exactly what you see, and a
  command palette on the right listing **all 20 geometry commands** —
  those already used in the code are pinned to the top in bold
  (they stay pinned while filtering; commands mentioned only in
  `//` comments or fenced blocks don't count as used), greyed out
  when a command has no parameter dialog. Picking a command runs its
  parameter dialog and the built line is spliced into the *code area*
  (before the closing `)`), never into the document — **Enter** in
  the filter or on a palette row runs that pick *only* (it never also
  presses Insert), and **Insert** refuses code the inserter would
  reject instead of closing with your edits lost. **Insert** commits
  the code at the cursor as one undo step and closes the window,
  **Cancel** (or Esc) leaves the document untouched; re-clicking the
  card you're already editing keeps your edits, another card reloads
  the example.

## [5.0.0] - 2026-10-23

### Changed

- Dependency and CI action updates: numpy 2.5.3 → 2.5.4, PySide6
  6.11.2 → 6.12.0 (which now also pulls the new `pyside6-pdf` and
  `pyside6-webengine` sub-packages), `actions/checkout` v4 → v7,
  `actions/setup-python` v5 → v6 and `astral-sh/setup-uv` v3 → v7.
  Dependabot now batches minor/patch updates into grouped PRs.
- **Minimum macOS version raised to 14 (Sonoma)**: PySide6 6.12
  publishes only `macosx_14_0` wheels (no macOS 13 wheels, no sdists),
  so neither `uv sync` nor the prebuilt app can run on macOS 13.
  Documented in the README and installation guide; macOS 13 users
  should stay on the previous release.
- **Breaking**: `*vec` now renders a math-mode column vector instead
  of an exported SVG arrow diagram. `*vec(a ; b [; c ...])` emits a
  Typst `vec(...)` call, works inside `\ ... \` math and
  `*matrix`/`*det` cells (it was text-mode only before), and accepts
  symbolic components (`*vec(a ; b)`). Diagram sidecars (`-vec-*.svg`),
  the `[Vec Error: …]` inline literals and the `compiler.vectors`
  module are gone; warnings (with line numbers) now cover
  too-few components, empty components and unclosed calls.

### Added

- `rule.txt` now documents every builtin command, including the
  previously missing `*diff`/`*pdiff`, `*align`, `*det`,
  `*hat`/`*bar`/`*tilde`/`*overline`/`*dot`, `*bold`/`*italic`/
  `*underline`, `*newpage`/`*pagebreak` and `*image`.
- Tests that keep the docs honest: every LSP builtin must appear in
  `rule.txt`, and every friendly alias (`*squareroot`, `*summation`,
  …) must compile identically to its canonical command and be
  documented.
- Full alias reference in [docs/algebra.md](docs/algebra.md) and a new
  aliases section in the [cheat sheet](docs/cheatsheet.md).

## [4.5.0] - 2026-10-23

### Added

- Contributor onboarding docs: `CONTRIBUTING.md`, architecture,
  cheat sheet, glossary and troubleshooting guides.

### Changed

- Smaller frozen builds: targeted PyInstaller hooks instead of
  `--collect-all`, native library stripping on Linux, and the `ezmath`
  CLI alias is now a symlink on POSIX instead of a copy (PR #4).

### Fixed

- `installer/build_linux.sh` executable bit restored (broke shell
  execution on Linux checkouts).

## [4.4.0] - 2026-10-22

### Security

- Upgraded Pillow to 13.0.0, resolving 28 Dependabot advisories.

## [4.3.1] - 2026-10-22

### Changed

- Faster builds everywhere: cached uv dependencies in installer CI,
  compressed installer freezing, shared parallel build defaults and
  incremental inputs (PR #3).
- Builds centralized; Arch (`PKGBUILD`) packages added alongside
  Debian/Fedora.

## [4.3.0] - 2026-10-21

### Fixed

- Audit regressions: source preservation through the text pipeline,
  editor export asset handling, `//` comment stripping, plot/variable
  edge cases (PR #1).

[Unreleased]: https://github.com/duo8097/easy-math-lang/compare/v5.2.0...HEAD
[5.2.0]: https://github.com/duo8097/easy-math-lang/compare/v5.1.0...v5.2.0
[5.1.0]: https://github.com/duo8097/easy-math-lang/compare/v5.0.0...v5.1.0
[5.0.0]: https://github.com/duo8097/easy-math-lang/compare/v4.5.0...v5.0.0
[4.5.0]: https://github.com/duo8097/easy-math-lang/compare/v4.4.0...v4.5.0
[4.4.0]: https://github.com/duo8097/easy-math-lang/compare/v4.3.1...v4.4.0
[4.3.1]: https://github.com/duo8097/easy-math-lang/compare/v4.3.0...v4.3.1
[4.3.0]: https://github.com/duo8097/easy-math-lang/releases/tag/v4.3.0
