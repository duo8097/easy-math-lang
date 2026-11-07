# easy-math-lang

**easy-math-lang** is a tool that lets you write math documents using simple text —
no design skills needed.

You write a plain text file, run one command, and get a clean PDF with proper
math symbols, fractions, and diagrams — including the full Greek alphabet
(`*alpha` … `*omega`, `*Gamma` … `*Omega`), arrows (`*to`, `*implies`, …),
relations (`*equiv`, `*leq`, …), and set/logic symbols (`*forall`, `*isin`, …).

It was made for **teachers and students** who want an easy way to write math
without fighting complex software.

---

## Download and install

The easiest way to use easy-math-lang — no Python needed:

**Windows:**

1. Go to the [**Releases page**](https://github.com/duo8097/easy-math-lang/releases).
2. Download `EasyMathLang-Windows-x64-Setup.exe` from the latest stable release.
3. Run `EasyMathLang-Windows-x64-Setup.exe` and follow the setup steps.
4. Launch **Easy Math Editor** from the Start Menu.

**macOS 14+ (Apple Silicon only, M1 or newer) — experimental until confirmed on real hardware:**

1. Go to the [**Releases page**](https://github.com/duo8097/easy-math-lang/releases).
2. Download `EasyMathLang-macOS-arm64.dmg` from the latest stable release.
   Requires macOS 14 (Sonoma) or newer; does not run on Intel Macs.
3. Open the `.dmg` and drag `easy-math-editor.app` to `Applications`,
   then run it (right-click → **Open** on first launch — the app is
   ad-hoc signed, not notarized; see the [Installation guide](docs/installation.md)).

**Linux (x86_64):**

1. Go to the [**Releases page**](https://github.com/duo8097/easy-math-lang/releases).
2. Download `EasyMathLang-Debian-amd64.deb` (Debian, Ubuntu, Mint),
   `EasyMathLang-Fedora-amd64.rpm` (Fedora, RHEL, openSUSE) or
   `easy-math-lang-git-*.pkg.tar.zst` (Arch)
   from the latest stable release.
3. Install it (`sudo dpkg -i EasyMathLang-Debian-amd64.deb`,
   `sudo rpm -i EasyMathLang-Fedora-amd64.rpm` or
   `sudo pacman -U easy-math-lang-git-*.pkg.tar.zst`) and launch
   **Easy Math Editor** from your applications menu.

> Need step-by-step help or want to run from source?
> See the [Installation guide](docs/installation.md).
>
> **Nightly builds:** every night CI rebuilds all the installers —
> grab them from the latest "Build Installers" run's Artifacts
> (expire after 14 days) under Actions.

---

## Requirements (run from source only)

| What | Version | Why you need it |
|---|---|---|
| **Python** | ≥ 3.12 (see `requires-python` in `pyproject.toml`) | Runs the compiler |
| **macOS** | ≥ 14 (Sonoma), Apple Silicon — PySide6 6.12+ publishes no macOS 13 wheels | GUI (PySide6/Qt) |
| **NumPy** | ≥ 2.5.3 (installed automatically as a project dependency) | Geometry constraint solver |
| **Typst** | ≥ 0.15.0 (installed automatically via the `typst` PyPI package — no separate install needed) | Turns the intermediate `.typ` file into PDF |
| **pygls** | ≥ 2.1.1 (installed automatically as a project dependency) | Editor support (language server) |

---

## What does it look like?

You write something like this in a text file:

```
// Area of a rectangle

<width>  = 5
<height> = 3
<area>   = calc(<width> * <height>)

The rectangle is <width> cm wide and <height> cm tall.
Its area is: <width> . <height> = <area> cm²
```

And you get a clean PDF that says:

> The rectangle is 5 cm wide and 3 cm tall.
> Its area is: 5 . 3 = 15 cm²

---

## Try the examples

The `examples/` folder has ready-made documents you can compile right away:

```
uv run easy-math-lang examples/example.ezmath
uv run easy-math-lang examples/draw_test.ezmath
```

Each command creates a `.pdf` file next to the input file. Add
`--save-build-artifacts` to also keep the intermediate `.typ` source
and source map for debugging.

Friendly shortcuts work everywhere: `*frac(2, 3)`, `*fraction(2 ; 3)`,
`let x = 5`, `# Title`, `- item`, `==` for `=`.

Export images and more (see [Export](docs/export.md)):

```
uv run easy-math-lang examples/example.ezmath out.png
uv run easy-math-lang --format svg --ppi 300 examples/example.ezmath -o hi.svg
```

Builds with `[Error]` diagnostics still write the PDF and exit 0 by
default (message: `Compiled … with N error(s), M warning(s)`); add
`--strict` to exit non-zero on errors (handy in CI).

Or in the desktop editor: **File → Export As…** (PDF/PNG/SVG/HTML/Typst).

---

## Editor support (autocompletion, error checking)

If your editor understands the Language Server Protocol, run:

```
uv run easy-math-lsp
```

and point your editor at it (it communicates over stdin/stdout).
You get error messages, variable autocompletion, hover information, and
document symbols for `.ezmath` files.
See [Language server](docs/lsp.md) for details.

---

## For developers

Run the test suite:

```
uv run pytest tests/ -v
```

Project layout (see [Architecture](docs/architecture.md) for how the
pieces fit together):

```
src/
├── compiler/     # .ezmath → Typst compiler (text pipeline, multi-format export)
├── geometry/     # constraint solver + CeTZ drawing output
├── lsp/          # language server (reuses the compiler)
└── editor/       # desktop editor (PySide6 + LSP client, incl. paths.py
                   # which locates the helper binaries in every install type)
tests/            # pytest suite (compiler, geometry, LSP, editor, packaging)
examples/         # sample .ezmath documents with expected output
docs/             # user guides (incl. export.md for PDF/PNG/SVG/HTML/Typst)
installer/        # Inno Setup script (Windows), PKGBUILD (Arch) and the
                   # Linux/Arch package builders
scripts/          # build helpers (build_binaries.py = shared PyInstaller
                   # build, build_local.ps1, build_macos.sh, package_macos.sh)
```

Packaged-binary tests are opt-in (they need a real build in `dist/`):

```
powershell -ExecutionPolicy Bypass -File scripts/build_local.ps1
$env:EASYMATH_RUN_BUILD_TESTS = '1'
uv run pytest tests/test_packaged_build.py -v
```

See [Packaging and releases](docs/packaging.md) for the full build,
installer-layout, and runtime-resolution picture.

---

## Contributing

Bug fixes, docs, tests and features are welcome — no expertise
required. Start with:

- 🤝 [Contributing](CONTRIBUTING.md) — setup, workflow, PR checklist
- 📜 [Code of Conduct](CODE_OF_CONDUCT.md) — how we treat each other
- 🔒 [Security policy](SECURITY.md) — how to report vulnerabilities
- 🗺️ [Architecture](docs/architecture.md) — how the compiler, geometry
  solver, language server and editor fit together

See the [Changelog](#changelog) below for what changed in each release.

---

## Learn more

If you have never used a terminal or installed programs before, start here:

1. 📦 [Installation guide](docs/installation.md) — setup, step by step (Windows/macOS installers or from source)
2. ⚡ [Cheat sheet](docs/cheatsheet.md) — everything you type most often, on one page
3. ✏️ [Writing math](docs/algebra.md) — how to write formulas, variables, and symbols (incl. friendly shortcuts)
4. 📐 [Drawing geometry](docs/geometry.md) — how to draw triangles, circles, and angles
5. 🖼️ [Export](docs/export.md) — PDF, PNG/SVG images, HTML and Typst source
6. 💡 [Language server](docs/lsp.md) — editor autocompletion and error checking
7. 🖥️ [Desktop editor](docs/editor.md) — using the graphical editor (incl. Export As…)
8. 🆘 [Troubleshooting and FAQ](docs/troubleshooting.md) — what each message means and how to fix it
9. 📖 [Glossary](docs/glossary.md) — every term explained in plain language
10. 📦 [Packaging and releases](docs/packaging.md) — building the binaries and installers (developers)

## Changelog

All notable changes to easy-math-lang are documented in
[CHANGELOG.md](CHANGELOG.md) (Keep a Changelog format,
[Semantic Versioning](https://semver.org/)). The latest release:

### [6.0.0] - 2026-11-07

#### Added
- **Auto-close brackets in the desktop editor** — typing `(`, `[`, `{` or `"` inserts the matching closer when the next character is end of line, whitespace, or a closer (quotes also require the previous character not be a word character); selections are wrapped, matching closers overtype, Backspace deletes an empty pair, Enter expands `(|)` to three lines with indentation, every action is a single undo step, and IME composition and programmatic edits (paste, completion, LSP) are unaffected. Toggle: `View → Auto-close Brackets` (**Ctrl+Shift+B**, persisted as `editor/autoCloseBrackets`, default on; `src/editor/auto_pairs.py` + `src/editor/editor_widget.py`, tests in `tests/test_editor_gui.py` and `tests/test_auto_pairs.py`, docs in `docs/editor.md`).
- Plot expression hash cache — repeated `*plot(...)` with the same expression skips Matplotlib re-render.
- **CeTZ is vendored and bundled — `*draw` works fully offline, with no first-run download.** The Typst packages `*draw` needs (cetz 0.4.2 and oxifmt 1.0.0 — its only transitive dependency, verified by compiling offline against an empty package cache) are committed under `vendor/typst-packages/` (downloaded and SHA-256-verified by `scripts/vendor_typst_packages.py`; manuals, galleries and docs are pruned — 473.4 KiB in total, `typst.toml`, all `.typ` sources, the LICENSE files and CeTZ's WASM core are kept) and ship in every packaged build: one copy under the shared bundle's `_internal/typst-packages/` (Windows, macOS, Debian/RPM, Arch; the CLI, the LSP and the editor all see the same copy) — and the wheel/sdist ship it as package data, so pip installs are offline-capable too. `_run_typst_export()` passes the bundle as Typst's `package_path`, which Typst consults before its user cache and the network; when the bundle is missing the compiler falls back to Typst's usual cache/download behavior and never crashes. The offline error message now only appears when the bundle is genuinely missing and the download also fails. cetz/oxifmt remain unmodified and replaceable; they are not MIT — `THIRD_PARTY_LICENSES` (CeTZ is LGPL-3.0-or-later) lists them with upstream URLs and ships in all installers. `src/typst_bundle/` is the single source of truth for the pinned versions; `tests/test_typst_bundle.py` enforces the vendored tree matches (each package's `typst.toml` must match its directory) and compiles `*draw` with every package-cache location redirected to an empty temporary directory, asserting the cache stays empty; `tests/test_packaged_build.py` does the same against the frozen binaries with dead proxies.
- **`*equal-angle(A ; B ; C ; D ; E ; F)`** — angle ABC equals angle DEF, implemented end to end. The constraint solver moves the free points until the two interior angles match, and codegen draws the same equality mark on both angles (an arc with a tick, the same arc radius as `*angle`). The editor's `Insert command…` button and the template-window command palette now open a `geo-equal-angle` parameter dialog (six point fields, `*draw`-wrapped) instead of greying the card out, and the gallery thumbnail is re-rendered. Docs: `docs/geometry.md` (new section), `docs/cheatsheet.md` (constraint table), `rule.txt`, plus a runnable fourth block in `examples/draw_test.ezmath`.
- LSP hover + completion description for `*draw(...)` — the language server advertised built-in descriptions but hovering/completing `*draw` gave nothing (the draw-block symbol shadowed it). `*draw` is now documented like every other built-in.
- Linux input methods (Vietnamese etc.) — the desktop editor now supports fcitx5 IME methods (e.g., fcitx5-lotus Vietnamese Telex) on Linux. The fix activates only when fcitx is evident (`QT_IM_MODULE`/`XMODIFIERS`/`GTK_IM_MODULE`) and leaves ibus users untouched. The `.deb`/`.rpm` installers bundle a plugin compiled from source in CI against PySide6's exact Qt, and the Arch package bundles the system `fcitx5-qt` plugin when its Qt matches (frozen builds verify the plugin is bundled); from source, a matching system plugin is used automatically. `EZMATH_NO_IME_FIX=1` opts out.

#### Changed
- LSP source-range slicing fixed (`analysis.py`) so `calc(...)` expressions use original source offsets.
- **Draw examples showcase auto-positioned points** — the under-constrained examples now pin enough points for a well-determined, canonical figure: the circle-with-tangent blocks (`examples/draw_test.ezmath`, `docs/geometry.md` Example 3) pin the radius point on the x-axis and give the tangent a length, the `examples/example_3.ezmath` on-circle demo pins P on the x-axis, and the single-line `*draw(...)` demo in `docs/geometry.md` pins its triangle instead of collapsing three auto points. `docs/geometry.md` gains a "What auto-placement decides" note: pin `A = 0, 0` / `B = x, 0` for a canonical orientation, results are deterministic, the solver is numeric (about 1% accurate), and constraints must determine the figure.

#### Fixed
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

#### Changed

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

Earlier releases (v5.0.0 and before) are listed in
[CHANGELOG.md](CHANGELOG.md) and on the
[GitHub releases page](https://github.com/duo8097/easy-math-lang/releases).

---

## License

MIT

[6.0.0]: https://github.com/duo8097/easy-math-lang/compare/v5.2.0...v6.0.0
