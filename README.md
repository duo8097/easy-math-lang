# easy-math-lang

**easy-math-lang** is a tool that lets you write math documents using simple text — no design skills needed.

You write a plain text file, run one command, and get a clean PDF with proper math symbols, fractions, and diagrams — including the full Greek alphabet, arrows, relations, and set/logic symbols.

It was made for **teachers and students** who want an easy way to write math without fighting complex software.

---

## Write your first document

Create a file named `hello.ezmath`:

```
// Area of a rectangle

<width>  = 5
<height> = 3
<area>   = calc(<width> * <height>)

The rectangle is <width> cm wide and <height> cm tall.
Its area is: <width> . <height> = <area> cm²
```

Then run:

```
uv run easy-math-lang hello.ezmath
```

This creates `hello.pdf` next to your file — a clean PDF that says:

> The rectangle is 5 cm wide and 3 cm tall.
> Its area is: 5 . 3 = 15 cm²

That's it — one text file, one command, one PDF.

---

## Install and run (shortest path)

**No Python needed — download a ready-made installer:**

1. Go to the [**Releases page**](https://github.com/duo8097/easy-math-lang/releases).
2. Download the installer for your system:
   - **Windows 10+ (64-bit):** `EasyMathLang-Windows-x64-Setup.exe`
   - **macOS 14+ Apple Silicon (experimental until confirmed on real hardware):** `EasyMathLang-macOS-arm64.dmg` (drag to Applications; right-click → Open on first launch — the app is ad-hoc signed, not notarized; see the [Installation guide](docs/installation.md)).
   - **Linux:** `EasyMathLang-Debian-amd64.deb`, `EasyMathLang-Fedora-amd64.rpm`, or `easy-math-lang-git-*.pkg.tar.zst` (Arch)
3. Install it and launch **Easy Math Editor** from your Start Menu / Applications.

Or run from source (Python 3.12+ needed):

```
git clone https://github.com/duo8097/easy-math-lang
cd easy-math-lang
uv sync
uv run easy-math-lang hello.ezmath
```

> Need step-by-step install help? See the [Installation guide](docs/installation.md) — Windows/macOS/Linux, installers or from source.

---

## What does it look like?

Here is a slightly longer example showing variables, calculation, and a friendly shortcut:

```
*doc_title(My Lesson)

<width>  = 5
<height> = 3
<area>   = calc(<width> * <height>)

The area is <width> . <height> = <area> cm².
```

The `*doc_title(...)` line sets the document title and PDF metadata. Variables in `<...>` are remembered; `calc(...)` does the math. The `.` is the multiplication dot (`*` means "this is a command" — see below).

Friendly shortcuts work everywhere: `*frac(2, 3)`, `*fraction(2 ; 3)`, `let x = 5`, `# Title`, `- item`, `==` for `=`.

Each command creates a `.pdf` file next to the input file. Add `--save-build-artifacts` to also keep the intermediate `.typ` source and source map for debugging.

Export images and more (see [Export](docs/export.md)):

```
uv run easy-math-lang examples/example.ezmath out.png
uv run easy-math-lang --format svg --ppi 300 examples/example.ezmath -o hi.svg
```

Or in the desktop editor: **File → Export As…** (PDF/PNG/SVG/HTML/Typst).

---

## Try the examples

The `examples/` folder has ready-made documents you can compile right away:

```
uv run easy-math-lang examples/example.ezmath
uv run easy-math-lang examples/draw_test.ezmath
```

See [examples/README.md](examples/README.md) for a table of every example — what it teaches and how hard it is.

---

## Editor support (autocompletion, error checking)

If your editor understands the Language Server Protocol, run:

```
uv run easy-math-lsp
```

and point your editor at it (it communicates over stdin/stdout). You get error messages, variable autocompletion, hover information, and document symbols for `.ezmath` files.

See [Language server](docs/lsp.md) for details.

---

## Updating

Easy Math Lang checks [GitHub Releases](https://github.com/duo8097/easy-math-lang/releases) for new versions — automatically about once a day, or on demand. Nothing is ever installed without your explicit "Update now" confirmation, and the download is always verified against `SHA256SUMS.txt` from the same release before anything is changed.

- **Automatic check:** silent; if a newer release exists, a small dismissible banner appears in the editor. Turn it off any time with `View → Check for updates automatically`.
- **Check manually:** `Help → Check for Updates…` in the editor, or `easy-math-lang --check-update` / `--update` (asks first; `--yes` skips the prompt for scripts) on the command line.
- **One-click update** is offered when the install can actually be updated in place: the Windows installer (UAC prompt), the macOS app bundle in a writable Applications folder (the app restarts by itself), or the Debian/Fedora/Arch package when this binary belongs to it (polkit prompt). Everywhere else, the editor shows exactly what to download and the commands to run.
- **From source** (`git clone` + `uv sync`): update with `git pull && uv sync`; the tool never updates a source checkout for you.
- **If an update fails**, the old version stays runnable, the reason is logged to `~/.config/ezmath/update.log`, and the next start shows the error once with a manual-download button. See [Troubleshooting → Updates](docs/troubleshooting.md#updates).

**Privacy & security:** update checks are GET requests to the GitHub Releases API and the release assets — nothing about you or your documents is ever sent (no tokens, no identifiers, no cookies; the client sends only a constant `User-Agent`). Everything comes from GitHub over HTTPS and is verified SHA-256 against the `SHA256SUMS.txt` published with each release. The checksum proves the download was not corrupted or swapped in transit — it does **not** prove authenticity (anyone who can publish a release could also publish a matching sum); code signing / notarization is future work. See [SECURITY.md](SECURITY.md).

---

## Requirements (run from source only)

| What | Version | Why you need it |
|---|---|---|
| **Python** | ≥ 3.12 (see `requires-python` in `pyproject.toml`) | Runs the compiler |
| **Windows** | ≥ 10 version 1809 (build 17763), 64-bit — matches the installer's `MinVersion` | GUI (PySide6/Qt) and the installer |
| **macOS** | ≥ 14 (Sonoma), Apple Silicon — PySide6 6.12+ publishes no macOS 13 wheels | GUI (PySide6/Qt) |
| **Linux** | x86_64, glibc ≥ 2.34 (the manylinux_2_34 floor of the locked wheels; the prebuilt packages need 2.39) | GUI (PySide6/Qt) |
| **NumPy** | ≥ 2.5.3 (installed automatically as a project dependency) | Geometry constraint solver |
| **Typst** | ≥ 0.15.0 (installed automatically via the `typst` PyPI package — no separate install needed) | Turns the intermediate `.typ` file into PDF |
| **pygls** | ≥ 2.1.1 (installed automatically as a project dependency) | Editor support (language server) |

---

## For developers

Run the test suite:

```
uv run pytest tests/ -v
```

Project layout (see [Architecture](docs/architecture.md) for how the pieces fit together):

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

See [Packaging and releases](docs/packaging.md) for the full build, installer-layout, and runtime-resolution picture.

---

## Contributing

Bug fixes, docs, tests and features are welcome — no expertise required. Start with:

- 🤝 [Contributing](CONTRIBUTING.md) — setup, workflow, PR checklist (includes "Your first change" for beginners)
- 📜 [Code of Conduct](CODE_OF_CONDUCT.md) — how we treat each other
- 🔒 [Security policy](SECURITY.md) — how to report vulnerabilities
- 🗺️ [Architecture](docs/architecture.md) — how the compiler, geometry solver, language server and editor fit together

See the [Changelog](#changelog) below for what changed in each release.

---

## Learn more

If you have never used a terminal or installed programs before, start here:

1. 📦 [Installation guide](docs/installation.md) — setup, step by step (Windows/macOS installers or from source)
2. ⚡ [Getting started](docs/getting-started.md) — write your first .ezmath file in 5 minutes
3. ⚡ [Cheat sheet](docs/cheatsheet.md) — everything you type most often, on one page
4. ✏️ [Writing math](docs/algebra.md) — how to write formulas, variables, and symbols (incl. friendly shortcuts)
5. 📐 [Drawing geometry](docs/geometry.md) — how to draw triangles, circles, and angles
6. 🖼️ [Export](docs/export.md) — PDF, PNG/SVG images, HTML and Typst source
7. 💡 [Language server](docs/lsp.md) — editor autocompletion and error checking
8. 🖥️ [Desktop editor](docs/editor.md) — using the graphical editor (incl. Export As…)
9. 🆘 [Troubleshooting and FAQ](docs/troubleshooting.md) — what each message means and how to fix it
10. 📖 [Glossary](docs/glossary.md) — every term explained in plain language
11. 📦 [Packaging and releases](docs/packaging.md) — building the binaries and installers (developers)

## Changelog

All notable changes to easy-math-lang are documented in
[CHANGELOG.md](CHANGELOG.md) (Keep a Changelog format,
[Semantic Versioning](https://semver.org/)). The latest release:

### [7.1.1] - 2026-11-20

Earlier releases are listed in
[CHANGELOG.md](CHANGELOG.md) and on the
[GitHub releases page](https://github.com/duo8097/easy-math-lang/releases).

---

## License

MIT

UI icons are from [Lucide](https://github.com/lucide-icons/lucide)
(ISC License, with MIT for Feather-derived icons); the vendored SVG
files and full license text live in `src/editor/assets/icons/`
(see `src/editor/assets/icons/LICENSE` for attribution).

[7.1.1]: https://github.com/duo8097/easy-math-lang/compare/v7.1.0...v7.1.1
