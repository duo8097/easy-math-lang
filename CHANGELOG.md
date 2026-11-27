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
- Levelled up the website (`site/`): in-browser playground (Pyodide),
  smart download button, examples gallery, rendered docs, OG/favicon assets,
  changelog page, and an "ezmath vs LaTeX" comparison page.

### Fixed
- Playground on Vercel: ship a validly-named wheel plus `wheel.json` in the
  repo and add a Vercel `buildCommand` so the in-browser compiler can be
  installed; remove the non-standard `easymath.whl`.

## [8.0.1] - 2026-11-27

### Fixed
- Fenced code blocks now escape all Typst special characters (including
  those inside `$...$`-looking spans) instead of leaving inner content
  unescaped.
- `escape_number_commas` no longer escapes commas that separate
  single-digit function arguments (e.g. `frac(2,3)`).

## [8.0.0] - 2026-11-24

### Added
- **Easy Math Lang 8.0.0.** Production release integrating user mod files (`*use`), single source of truth for math commands (`commands.toml`), and LSP/editor awareness.

## [8.0.0-rc.1] - 2026-11-24

### Added
- **Agent guide.** `AGENTS.md` records verified setup, testing, and repository rules for coding agents.
- **Beginner documentation tools and guides.** Added a checked examples map,
  a Markdown link checker, and a first-change walkthrough for new contributors.
- **Auto-generated tables of contents for the long docs.** `scripts/gen_toc.py`
  builds a nested `##`/`###` table of contents between `<!-- toc -->`
  markers (GitHub-compatible anchors, duplicate headings get `-1`, `-2`
  suffixes). After editing headings, run `python scripts/gen_toc.py`; CI
  fails with `gen_toc.py --check` when a table of contents is out of date.

### Changed
- LSP hover/completion text for math commands and aliases is now derived from
  `commands.toml`, so alias descriptions include the canonical command's
  documentation.
- `*use("file.toml")` loads per-document math commands; the language server
  and editor reflect them in completion, hover and diagnostics, and reload
  when the mod file changes on disk.

## [7.1.1] - 2026-11-20

### Changed
- Dependency update: numpy 2.5.4 → 2.5.5; no user-visible change.

## [7.1.0] - 2026-11-15

### Added
- **Built-in update system for the CLI and the editor.** `Help → Check for Updates…` checks GitHub Releases in the background (about once a day, silent on failure; turn off with `View → Check for updates automatically`) and shows a dismissible banner when a newer version exists; the banner opens an update dialog with current vs new version, release notes and the install hint. “Update now” is offered only when this exact install can be replaced in place: the Windows installer (silent Inno install; you verify via the UAC prompt), the macOS `.app` bundle in a writable location (DMG mounted, bundle swapped after the app quits, with rollback), or the Debian/Fedora/Arch package when the running binary belongs to it (`pkexec apt-get install -y` / `dnf install -y` / `pacman -U --noconfirm`, with `dpkg`/`rpm` fallbacks). Everywhere else you get the exact manual command. Downloads are HTTPS-only from GitHub, size-capped, streamed to a private temp dir and SHA-256-verified against `SHA256SUMS.txt` from the same release — a missing sums file or mismatch aborts with an error and deletes the file (no skip path). The app is never replaced while running: the helper hands off to the platform installer after the app exits (on Windows it launches the installer detached and is gone before any file is replaced; relaunch happens via an `[Run]` entry); the next start detects the outcome (pending-update marker in the update state file on Windows; recorded error on macOS/Linux) and either stays silent on success or shows the reason once with a manual-download button. The CLI gains `easy-math-lang --update` (also `ezmath --update`): prints current vs latest with a notes summary, asks `Update now? [y/N]` (`--yes` for scripts), downloads with a progress bar and hands over to the same helper; exits non-zero on failure. `--check-update` (still exit-0 on every failure) now also prints the matching asset and update hint. Tests inject all network/subprocess/platform calls.
- **`scripts/bump_version.py` — one command bumps the version everywhere.** Rewrites `pyproject.toml` (source of truth), `uv.lock` via `uv lock`, `FALLBACK_VERSION`, the PKGBUILD `pkgver` (pacman-safe rc mapping) and the bug-report placeholder; moves `CHANGELOG.md`’s `[Unreleased]` to a dated release section and keeps the `README.md` mirror and both compare links consistent; `--dry-run` prints the diff, `--commit` makes one `chore(release): vX.Y.Z` commit; a failed write leaves the tree untouched; versions that are not strictly greater are refused without `--force`. `scripts/check_tag_version.py` now also fails a tag build when any synced location disagrees with `pyproject.toml`.

### Changed
- The `easy-math-lang` CLI accepts `--apply-update <plan.json>` (internal helper mode used by the self-update flow; undocumented and not part of the compiler’s output).
- Release installs now always use `SHA256SUMS.txt`-verified downloads in the updater, and the release workflow generates and uploads that file with every tag (`sha256sum *`) and fails if any expected asset is missing.
- `server.py`, `app.py` and the About box read the version from `compiler.update.get_current_version()` instead of their own literals.
- **Linux CI and packaging split into three independent stages (CI/packaging only, no user-visible change).** `installer/build_linux.sh` now has subcommands — `binary` (PyInstaller → `dist/easy-math-lang/`), `deb` and `rpm` (both bundle-only, never PyInstaller, fail fast without a bundle, share one FHS staging helper) — plus the unchanged default `all`. The `build-linux` CI job is replaced by `build-linux-binary` (test gate, fcitx5-qt + Qt SDK, frozen smoke tests; packs the bundle into one tarball uploaded as `linux-bundle-amd64`, 2-day retention), `build-deb` (dpkg only; same smoke test; asset name unchanged) and `build-rpm` (pinned `fedora:41` container; payload inspection plus a real `dnf install` smoke test, CLI only). `release` still requires every asset-producing job; published asset names and the release flow are unchanged.
- **`pyside6` is now constrained below 6.13.** `pyproject.toml` requires `pyside6>=6.11.2,<6.13` (Qt 6.13 has not been validated for the fcitx5 input-method plugin); `uv.lock` moved with it.
- **Windows installer now requires Windows 10 version 1809 (build 17763) or newer.** `installer/setup.iss` sets `MinVersion=10.0.17763` (64-bit only as before); the setup binary refuses to run on older systems.
- **README and the installation guide now state the OS requirements.** Windows 10 1809+ 64-bit; macOS 14 (Sonoma) or newer on Apple Silicon only; Linux x86_64 with glibc 2.39 or newer (the Ubuntu 24.04 build baseline, same as the .deb/.rpm/Arch packages).

### Fixed
- **Windows in-place upgrades would have registered as a second application.** Releases up to 7.0.0 shipped without an explicit `AppId`, so Inno used `AppName` (“Easy Math Lang”) as the implicit AppId and the uninstall key `Easy Math Lang_is1`; a brief update-branch change then declared a different, brace-wrapped `AppId` literal, which would have made the new installer not see existing installs (two Add/Remove Programs entries, mismatched uninstaller). `AppId` is now exactly `AppName` (no braces), `tests/test_installer_script.py` guards the value and scans the repo for stale braces references, and CI now installs the previous release first and then this build over it, requiring exactly one uninstall entry named “Easy Math Lang” (the manual procedure is documented in `docs/packaging.md` for environments where the previous asset cannot be downloaded).
- **The Windows self-update helper could not replace the files it ran from.** The helper was `easy-math-lang.exe` inside the install directory — a running process locking the very files the installer must replace (and a candidate for `/CLOSEAPPLICATIONS` to close). The helper now launches the installer detached and exits immediately — nothing from the install directory is alive when files are replaced — the editor is relaunched afterwards by an Inno `[Run]` entry (only with `/UPDATE=1`, via `{param:UPDATE|0}` and a `Check` function; the editor runs with the original user’s, non-admin, credentials), and a failure is detected on the next editor start (pending-update marker in the update state file + version compare + `update-install.log`), shown once with the log path and a manual-download button. `/CLOSEAPPLICATIONS`/`/RESTARTAPPLICATIONS` are no longer passed to the silent install.
- **Windows installer flattened the shared PyInstaller `_internal/` directory — every installed `.exe` failed to start.** `installer/setup.iss` copied the contents of `_internal\*` into `{app}\bin` directly (introduced in the shared-bundle rework, shipped in v6.0.0 and v7.0.0), so the onedir bootloader never found `bin\_internal\python312.dll` and each installed executable aborted with "Failed to load Python DLL '…\bin\_internal\python312.dll'. LoadLibrary: The specified module could not be found." The bundle now installs to `{app}\bin\_internal` (flags unchanged; the four `.exe` files still go to `{app}\bin`), `tests/test_installer_script.py` guards the layout statically, the Windows CI job silently installs the built installer and verifies `bin\_internal\python312.dll` exists and `easy-math-lang.exe --version` / `ezmath.exe --version` exit 0 before uploading the artifact, and `docs/troubleshooting.md` documents the error with a manual repair workaround (create `_internal\` next to the executables and move everything except the `.exe` files into it, or reinstall with the fixed installer).

### Security
- **The elevated install now re-verifies the downloaded installer (TOCTOU narrowing).** The SHA-256 checked at download time is recorded in the update plan, and the helper recomputes it — plus the file size and a symlink check — just before any installer command runs (all platforms, and before the macOS bundle swap/DMG attach). On mismatch the install aborts with a persisted error ("installer changed after verification") and nothing is executed; the temp dir is kept `0700` and the plan file `0600`.

## [7.0.0] - 2026-11-12

### Added
- **Python-style diagnostics on the compiler** — every `[Error]`/`[Warning]` diagnostic now prints a Python-traceback-style context block under its classic first line (the first line stays byte-identical for existing consumers):

  ```
  [Error] Line 12: undefined variable <widht>
    File "bai1.ezmath", line 12, column 8
      Tong = <widht> + 2
             ^^^^^^^
  ```

  The block shows the real `.ezmath` line (never transformed text), with a caret underline when a column is known (columns count characters, not bytes, so Vietnamese text aligns correctly; tabs are expanded; very long lines are truncated around the span with an ellipsis). Without a known column it prints the `File ... line N` header and the source line without a caret. Multi-line constructs (an unclosed `\ … \` math delimiter, an unterminated `*draw(` block) point at the line where they open. Color is only used on a TTY and never when `NO_COLOR` is set, so the editor's captured output stays plain text. When a Typst compile fails with an error that carries a position in the intermediate `.typ`, the same block is rendered for the `.ezmath` line it maps back to (via this build's own sidecar source map only; unmappable failures keep the classic `[ERROR] Typst compilation failed: ...` output untouched). The strict-mode diagnostic counter now only counts markers at the start of a line, so echoed source lines containing `[Error]` never inflate error counts. `calc()`, math-command (`*frac` etc.), inline-math and assignment diagnostics also go through the same printer now — those that know a line in the document show a context block. Documented in `docs/troubleshooting.md` and `docs/cheatsheet.md`.

### Fixed
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

## [6.0.0] - 2026-11-07

### Added
- **Auto-close brackets in the desktop editor** — typing `(`, `[`, `{` or `"` inserts the matching closer when the next character is end of line, whitespace, or a closer (quotes also require the previous character not be a word character); selections are wrapped, matching closers overtype, Backspace deletes an empty pair, Enter expands `(|)` to three lines with indentation, every action is a single undo step, and IME composition and programmatic edits (paste, completion, LSP) are unaffected. Toggle: `View → Auto-close Brackets` (**Ctrl+Shift+B**, persisted as `editor/autoCloseBrackets`, default on; `src/editor/auto_pairs.py` + `src/editor/editor_widget.py`, tests in `tests/test_editor_gui.py` and `tests/test_auto_pairs.py`, docs in `docs/editor.md`).
- Plot expression hash cache — repeated `*plot(...)` with the same expression skips Matplotlib re-render.
- **CeTZ is vendored and bundled — `*draw` works fully offline, with no first-run download.** The Typst packages `*draw` needs (cetz 0.4.2 and oxifmt 1.0.0 — its only transitive dependency, verified by compiling offline against an empty package cache) are committed under `vendor/typst-packages/` (downloaded and SHA-256-verified by `scripts/vendor_typst_packages.py`; manuals, galleries and docs are pruned — 473.4 KiB in total, `typst.toml`, all `.typ` sources, the LICENSE files and CeTZ's WASM core are kept) and ship in every packaged build: one copy under the shared bundle's `_internal/typst-packages/` (Windows, macOS, Debian/RPM, Arch; the CLI, the LSP and the editor all see the same copy) — and the wheel/sdist ship it as package data, so pip installs are offline-capable too. `_run_typst_export()` passes the bundle as Typst's `package_path`, which Typst consults before its user cache and the network; when the bundle is missing the compiler falls back to Typst's usual cache/download behavior and never crashes. The offline error message now only appears when the bundle is genuinely missing and the download also fails. cetz/oxifmt remain unmodified and replaceable; they are not MIT — `THIRD_PARTY_LICENSES` (CeTZ is LGPL-3.0-or-later) lists them with upstream URLs and ships in all installers. `src/typst_bundle/` is the single source of truth for the pinned versions; `tests/test_typst_bundle.py` enforces the vendored tree matches (each package's `typst.toml` must match its directory) and compiles `*draw` with every package-cache location redirected to an empty temporary directory, asserting the cache stays empty; `tests/test_packaged_build.py` does the same against the frozen binaries with dead proxies.
- **`*equal-angle(A ; B ; C ; D ; E ; F)`** — angle ABC equals angle DEF, implemented end to end. The constraint solver moves the free points until the two interior angles match, and codegen draws the same equality mark on both angles (an arc with a tick, the same arc radius as `*angle`). The editor's `Insert command…` button and the template-window command palette now open a `geo-equal-angle` parameter dialog (six point fields, `*draw`-wrapped) instead of greying the card out, and the gallery thumbnail is re-rendered. Docs: `docs/geometry.md` (new section), `docs/cheatsheet.md` (constraint table), `rule.txt`, plus a runnable fourth block in `examples/draw_test.ezmath`.
- LSP hover + completion description for `*draw(...)` — the language server advertised built-in descriptions but hovering/completing `*draw` gave nothing (the draw-block symbol shadowed it). `*draw` is now documented like every other built-in.
- Linux input methods (Vietnamese etc.) — the desktop editor now supports fcitx5 IME methods (e.g., fcitx5-lotus Vietnamese Telex) on Linux. The fix activates only when fcitx is evident (`QT_IM_MODULE`/`XMODIFIERS`/`GTK_IM_MODULE`) and leaves ibus users untouched. The `.deb`/`.rpm` installers bundle a plugin compiled from source in CI against PySide6's exact Qt, and the Arch package bundles the system `fcitx5-qt` plugin when its Qt matches (frozen builds verify the plugin is bundled); from source, a matching system plugin is used automatically. `EZMATH_NO_IME_FIX=1` opts out.

### Changed
- LSP source-range slicing fixed (`analysis.py`) so `calc(...)` expressions use original source offsets.
- **Draw examples showcase auto-positioned points** — the under-constrained examples now pin enough points for a well-determined, canonical figure: the circle-with-tangent blocks (`examples/draw_test.ezmath`, `docs/geometry.md` Example 3) pin the radius point on the x-axis and give the tangent a length, the `examples/example_3.ezmath` on-circle demo pins P on the x-axis, and the single-line `*draw(...)` demo in `docs/geometry.md` pins its triangle instead of collapsing three auto points. `docs/geometry.md` gains a "What auto-placement decides" note: pin `A = 0, 0` / `B = x, 0` for a canonical orientation, results are deterministic, the solver is numeric (about 1% accurate), and constraints must determine the figure.

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

[Unreleased]: https://github.com/duo8097/easy-math-lang/compare/v8.0.1...HEAD
[8.0.1]: https://github.com/duo8097/easy-math-lang/compare/v8.0.0...v8.0.1
[8.0.0]: https://github.com/duo8097/easy-math-lang/compare/v8.0.0-rc.1...v8.0.0
[8.0.0-rc.1]: https://github.com/duo8097/easy-math-lang/compare/v7.1.1...v8.0.0-rc.1
[7.1.1]: https://github.com/duo8097/easy-math-lang/compare/v7.1.0...v7.1.1
[7.1.0]: https://github.com/duo8097/easy-math-lang/compare/v7.0.0...v7.1.0
[7.0.0]: https://github.com/duo8097/easy-math-lang/compare/v6.0.0...v7.0.0
[6.0.0]: https://github.com/duo8097/easy-math-lang/compare/v5.2.0...v6.0.0
[5.2.0]: https://github.com/duo8097/easy-math-lang/compare/v5.1.0...v5.2.0
[5.1.0]: https://github.com/duo8097/easy-math-lang/compare/v5.0.0...v5.1.0
[5.0.0]: https://github.com/duo8097/easy-math-lang/compare/v4.5.0...v5.0.0
[4.5.0]: https://github.com/duo8097/easy-math-lang/compare/v4.4.0...v4.5.0
[4.4.0]: https://github.com/duo8097/easy-math-lang/compare/v4.3.1...v4.4.0
[4.3.1]: https://github.com/duo8097/easy-math-lang/compare/v4.3.0...v4.3.1
[4.3.0]: https://github.com/duo8097/easy-math-lang/releases/tag/v4.3.0
