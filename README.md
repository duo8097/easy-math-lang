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

### [5.1.0] - 2026-10-30

#### Added

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

Earlier releases (v5.0.0 and before) are listed in
[CHANGELOG.md](CHANGELOG.md) and on the
[GitHub releases page](https://github.com/duo8097/easy-math-lang/releases).

---

## License

MIT

[5.1.0]: https://github.com/duo8097/easy-math-lang/compare/v5.0.0...v5.1.0
