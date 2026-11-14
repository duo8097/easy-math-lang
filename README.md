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

### [7.0.0] - 2026-11-12

#### Added
- **Python-style diagnostics on the compiler** — every `[Error]`/`[Warning]` diagnostic now prints a Python-traceback-style context block under its classic first line (the first line stays byte-identical for existing consumers):

  ```
  [Error] Line 12: undefined variable <widht>
    File "bai1.ezmath", line 12, column 8
      Tong = <widht> + 2
             ^^^^^^^
  ```

  The block shows the real `.ezmath` line (never transformed text), with a caret underline when a column is known (columns count characters, not bytes, so Vietnamese text aligns correctly; tabs are expanded; very long lines are truncated around the span with an ellipsis). Without a known column it prints the `File ... line N` header and the source line without a caret. Multi-line constructs (an unclosed `\ … \` math delimiter, an unterminated `*draw(` block) point at the line where they open. Color is only used on a TTY and never when `NO_COLOR` is set, so the editor's captured output stays plain text. When a Typst compile fails with an error that carries a position in the intermediate `.typ`, the same block is rendered for the `.ezmath` line it maps back to (via this build's own sidecar source map only; unmappable failures keep the classic `[ERROR] Typst compilation failed: ...` output untouched). The strict-mode diagnostic counter now only counts markers at the start of a line, so echoed source lines containing `[Error]` never inflate error counts. `calc()`, math-command (`*frac` etc.), inline-math and assignment diagnostics also go through the same printer now — those that know a line in the document show a context block. Documented in `docs/troubleshooting.md` and `docs/cheatsheet.md`.

#### Fixed
- **Geometry solver: one impossible construction no longer takes down the whole diagram.** A failing construction (e.g. `*point(F = intersect(line(A ; B) ; circle(C ; 1) ; 1))` when the line misses the circle) previously aborted the entire `solve()`, so constraints were never applied and later constructed/free points were drawn at placeholder coordinates presented as authoritative. Failed constructions are now reported, the affected points (and dependents) are omitted from the canvas with an explanatory comment, constraints that read a failed construction (e.g. `*distance(F ; X ; 5)`) are skipped, and everything else still solves and renders.
- **`*image(...)` outside the document root now works in every export format** — out-of-root images are staged next to the intermediate `.typ` (`<stem>-images/`) so Typst can resolve them, in-tree images keep their relative layout, and the staged folder is copied along on relocated `typ`/`html` exports (marked so build cleanup only ever removes what we created).
- **Sanitized plot file names now match everywhere** — the export sidecar glob and the build-artifact cleanup use the same sanitization as `plot_filename()` (a `my doc.ezmath` now carries `my_doc-<hash>-plot-1.svg` along in `--format typ`), and sanitization is injective (`my doc` vs `my_doc` produce distinct files, with a stable hash suffix).
- **LSP analysis now applies URL masking and the comparison guard too** — a `<missing>`-shaped token inside a bare URL (`https://a.com/<missing>`) and a `<name>`-token glued both sides like `0<x>1` are no longer reported as undefined variables, matching the compiler exactly.
- **Geometry annotation swallowing same-line commands** — a trailing `= value` annotation (e.g. `*length(A ; B) = 5 *point(C = 1, 2)`) consumed the remainder of the line, silently dropping the following command; parsing now resumes at the embedded command.
- **Compiler: arbitrary file write via `*image(...)` sidecar export** — the `<stem>-plot-*.svg` glob and the `*image` sidecar copy when exporting `typ`/`html` to another directory now confine destinations to the export directory (previously a crafted `..`/`[` filename could write outside it).
- **Compiler: variable expansion exponential-time/memory DoS** — a few doubling `*define`s (`a = <b><b>`) could expand a tiny document to gigabytes; expansion is now memoized per compile and capped at 256 KiB per variable (past the cap the reference is left unexpanded with a warning).
- **Compiler: inequalities glued to variables** — `0<x>1` (and similar both-sides-glued `<name>` tokens) no longer substitute the variable or trip `undefined variable` errors; only a `<name>` unglued on at least one side is treated as a variable.
- **Compiler: `<doc>.typ`/`<doc>.smap.json` no longer silently overwritten** — the intermediate artifacts now carry an ownership marker; a pre-existing file not generated by easy-math-lang aborts the build with a loud error instead of being destroyed (and the source map is likewise never clobbered).
- **Compiler: bare URLs corrupted by symbol passes** — `->`, `...`, `==`, `<name>` inside `https://…` URLs were rewritten (→, …, =) or flagged as undefined variables; URLs are now masked before symbol/undefined-var/subscript expansion and restored (Typst-escaped) after.
- **Compiler: literal `*bold(hi)` etc. rendered as text** — the bracket escape for generated `#strong[…]`/`#emph[…]`/`#underline[…]` markup treated its brackets as user text, so styling inside `*table` cells and `*doc_title` silently printed as `strong [hi]`/`strong [Hi]`; generated markup spans are now recognized and left intact.
- **Compiler: comment stripping treated `"a // b"` as a comment** — `//` inside double-quoted strings (bare prose, quoted paths, URLs) truncated the line silently.
- **Compiler: `*doc_title(...)` is no longer re-rendered through the full text pipeline at codegen** — a title containing `*plot(...)`/`*image(...)` wrote files during a supposedly read-only phase; `*plot`/`*image` in `*doc_title` are now dropped with an error diagnostic instead.
- **Compiler: `[Calc Error]` results leaked** — `calc((-2)^(1/3))` printed a complex `j` literal into the PDF; complex results are now rejected with a `[Calc Error]`.
- **Compiler: intermediate diagnostic counter is thread-safe** — two concurrent compiles (preview thread + export) raced on process-global `sys.stderr`/`_ACTIVE_COUNTER`; compiles are now serialized process-wide (recursive builds unaffected — `RLock`).
- **LSP: diagnostics and symbols on a math-closing line were anchored to tail-relative columns** — e.g. `<undef_var>` after a `\` was reported shifted left; the head and tail are now analyzed with exact source offsets, and the math head of the line (undefined vars/calc) is checked at all (it was silently skipped).
- **LSP: stray `\` in `*table(`/`*matrix(` rows, and any `*cases(`/`*vec(` block, swallowed the rest of the document into math mode** — block rows no longer toggle math state, `*cases(`/`*vec(` are recognized multiline blocks, and trailing document content validates normally again.
- **LSP: `*calc(` no longer also reported as "Unknown command", unknown commands inside math pairs warn like the compiler, matrix cells no longer warn on unknown commands the compiler is silent about, and `*image`/`*plot`/`*bold`/`*italic`/`*underline` get the same shape/arity/unclosed checks as the compiler.**
- **LSP: `calc()` errors in assignments became diagnostics** (e.g. `<x> = calc(1/0)` previously reported nothing), and values stored at calculation-failure sites are no longer presented as real values in hover/completion.
- **LSP: geometry errors no longer appear twice in Problems (dedup across stderr/canvas), line splitting matches LSP clients (no phantom lines at VT/FF/NEL), and the code handles unicode astral characters consistently in hover.**
- **Editor: Enter between an empty pair on a line with trailing whitespace deleted the closing bracket** (document corruption on the most common pair path); an active selection spans and caret math across astral characters now uses code-point conversion consistently (gallery/template inserters, find post-filter, Save-As caret), `Escape` in the find bar clears highlights and refocuses, the LSP framing buffer resets on restart (no spurious frame errors), dead `QProcess`/worker objects are reaped, non-`FailedToStart` build errors clear the build state (previously silently blocked every later Ctrl+B), `PDF links parser no longer truncates `stream` inside string literals, `show_empty()` clears the stale source-map path, and pixel-size editor fonts no longer stick at `-1`pt.
- **Geometry: quoted label/annotation text kept its quotes** on the canvas (`*label(A ; "a;b")` rendered `"a;b"`), tiny-but-legal circle/arc radii no longer rendered as `0.000`, and the grammar checks for angle sweeps are enforced before any mark is drawn (both angle markers now appear or neither does).
- **Fuzz hardening**: analysis fuzzing across 3000 malformed documents (no crashes), geometry end-to-end fuzzing still at 0 crashes/hangs.
- Tidies the tree: removed dead locals/imports, duplicate signal declarations and an unused helper, tightened `zip(strict=True)` and closure bindings, and refreshed `docs/troubleshooting.md` for the new solver wording.

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

[7.0.0]: https://github.com/duo8097/easy-math-lang/compare/v6.0.0...v7.0.0
