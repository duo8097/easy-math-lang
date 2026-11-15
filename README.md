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

**Windows 10 (version 1809 / build 17763) or newer, 64-bit:**

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

**Linux (x86_64, glibc 2.39 or newer — the Ubuntu 24.04 baseline):**

1. Go to the [**Releases page**](https://github.com/duo8097/easy-math-lang/releases).
2. Download `EasyMathLang-Debian-amd64.deb` (Debian, Ubuntu, Mint),
   `EasyMathLang-Fedora-amd64.rpm` (Fedora, RHEL, openSUSE) or
   `easy-math-lang-git-*.pkg.tar.zst` (Arch)
   from the latest stable release.
3. Install it (`sudo dpkg -i EasyMathLang-Debian-amd64.deb`,
   `sudo rpm -i EasyMathLang-Fedora-amd64.rpm` or
   `sudo pacman -U easy-math-lang-git-*.pkg.tar.zst`) and launch
   **Easy Math Editor** from your applications menu.
   The packages are built on Ubuntu 24.04; older distros
   (Ubuntu ≤ 22.04, Debian ≤ 11, RHEL 8) are not supported — see
   [Packaging and releases](docs/packaging.md).

> Need step-by-step help or want to run from source?
> See the [Installation guide](docs/installation.md).
>
> **Nightly builds:** every night CI rebuilds all the installers —
> grab them from the latest "Build Installers" run's Artifacts
> (expire after 14 days) under Actions.

---

## Updating

Easy Math Lang checks [GitHub Releases](https://github.com/duo8097/easy-math-lang/releases)
for new versions — automatically about once a day, or on demand. Nothing
is ever installed without your explicit "Update now" confirmation, and
the download is always verified against `SHA256SUMS.txt` from the same
release before anything is changed.

- **Automatic check:** silent; if a newer release exists, a small
  dismissible banner appears in the editor. Turn it off any time with
  `View → Check for updates automatically`.
- **Check manually:** `Help → Check for Updates…` in the editor, or
  `easy-math-lang --check-update` / `--update` (asks first; `--yes`
  skips the prompt for scripts) on the command line.
- **One-click update** is offered when the install can actually be
  updated in place: the Windows installer (UAC prompt), the macOS app
  bundle in a writable Applications folder (the app restarts by itself),
  or the Debian/Fedora/Arch package when this binary belongs to it
  (polkit prompt). Everywhere else, the editor shows exactly what to
  download and the commands to run.
- **From source** (`git clone` + `uv sync`): update with
  `git pull && uv sync`; the tool never updates a source checkout for you.
- **If an update fails**, the old version stays runnable, the reason is
  logged to `~/.config/ezmath/update.log`, and the next start shows the
  error once with a manual-download button. See
  [Troubleshooting → Updates](docs/troubleshooting.md#updates).

**Privacy & security:** update checks are GET requests to the GitHub
Releases API and the release assets — nothing about you or your
documents is ever sent (no tokens, no identifiers, no cookies; the
client sends only a constant `User-Agent`). Everything comes from
GitHub over HTTPS and is verified SHA-256 against the `SHA256SUMS.txt`
published with each release. The checksum proves the download was not
corrupted or swapped in transit — it does **not** prove authenticity
(anyone who can publish a release could also publish a matching sum);
code signing / notarization is future work. See
[SECURITY.md](SECURITY.md).

---

## Requirements (run from source only)

| What | Version | Why you need it |
|---|---|---|
| **Python** | ≥ 3.12 (see `requires-python` in `pyproject.toml`) | Runs the compiler |
| **Windows** | ≥ 10 version 1809 (build 17763), 64-bit — matches the installer's `MinVersion` | GUI (PySide6/Qt) and the installer |
| **macOS** | ≥ 14 (Sonoma), Apple Silicon — PySide6 6.12+ publishes no macOS 13 wheels | GUI (PySide6/Qt) |
| **Linux** | x86_64 with glibc ≥ 2.39 (Ubuntu 24.04 baseline, same as the packages) | GUI (PySide6/Qt) |
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

### [7.1.0] - 2026-11-15

#### Added
- **Built-in update system for the CLI and the editor.** `Help → Check for Updates…` checks GitHub Releases in the background (about once a day, silent on failure; turn off with `View → Check for updates automatically`) and shows a dismissible banner when a newer version exists; the banner opens an update dialog with current vs new version, release notes and the install hint. “Update now” is offered only when this exact install can be replaced in place: the Windows installer (silent Inno install; you verify via the UAC prompt), the macOS `.app` bundle in a writable location (DMG mounted, bundle swapped after the app quits, with rollback), or the Debian/Fedora/Arch package when the running binary belongs to it (`pkexec apt-get install -y` / `dnf install -y` / `pacman -U --noconfirm`, with `dpkg`/`rpm` fallbacks). Everywhere else you get the exact manual command. Downloads are HTTPS-only from GitHub, size-capped, streamed to a private temp dir and SHA-256-verified against `SHA256SUMS.txt` from the same release — a missing sums file or mismatch aborts with an error and deletes the file (no skip path). The app is never replaced while running: the helper hands off to the platform installer after the app exits (on Windows it launches the installer detached and is gone before any file is replaced; relaunch happens via an `[Run]` entry); the next start detects the outcome (pending-update marker in the update state file on Windows; recorded error on macOS/Linux) and either stays silent on success or shows the reason once with a manual-download button. The CLI gains `easy-math-lang --update` (also `ezmath --update`): prints current vs latest with a notes summary, asks `Update now? [y/N]` (`--yes` for scripts), downloads with a progress bar and hands over to the same helper; exits non-zero on failure. `--check-update` (still exit-0 on every failure) now also prints the matching asset and update hint. Tests inject all network/subprocess/platform calls.
- **`scripts/bump_version.py` — one command bumps the version everywhere.** Rewrites `pyproject.toml` (source of truth), `uv.lock` via `uv lock`, `FALLBACK_VERSION`, the PKGBUILD `pkgver` (pacman-safe rc mapping) and the bug-report placeholder; moves `CHANGELOG.md`’s `[Unreleased]` to a dated release section and keeps the `README.md` mirror and both compare links consistent; `--dry-run` prints the diff, `--commit` makes one `chore(release): vX.Y.Z` commit; a failed write leaves the tree untouched; versions that are not strictly greater are refused without `--force`. `scripts/check_tag_version.py` now also fails a tag build when any synced location disagrees with `pyproject.toml`.

#### Changed
- The `easy-math-lang` CLI accepts `--apply-update <plan.json>` (internal helper mode used by the self-update flow; undocumented and not part of the compiler’s output).
- Release installs now always use `SHA256SUMS.txt`-verified downloads in the updater, and the release workflow generates and uploads that file with every tag (`sha256sum *`) and fails if any expected asset is missing.
- `server.py`, `app.py` and the About box read the version from `compiler.update.get_current_version()` instead of their own literals.
- **Linux CI and packaging split into three independent stages (CI/packaging only, no user-visible change).** `installer/build_linux.sh` now has subcommands — `binary` (PyInstaller → `dist/easy-math-lang/`), `deb` and `rpm` (both bundle-only, never PyInstaller, fail fast without a bundle, share one FHS staging helper) — plus the unchanged default `all`. The `build-linux` CI job is replaced by `build-linux-binary` (test gate, fcitx5-qt + Qt SDK, frozen smoke tests; packs the bundle into one tarball uploaded as `linux-bundle-amd64`, 2-day retention), `build-deb` (dpkg only; same smoke test; asset name unchanged) and `build-rpm` (pinned `fedora:41` container; payload inspection plus a real `dnf install` smoke test, CLI only). `release` still requires every asset-producing job; published asset names and the release flow are unchanged.
- **`pyside6` is now constrained below 6.13.** `pyproject.toml` requires `pyside6>=6.11.2,<6.13` (Qt 6.13 has not been validated for the fcitx5 input-method plugin); `uv.lock` moved with it.
- **Windows installer now requires Windows 10 version 1809 (build 17763) or newer.** `installer/setup.iss` sets `MinVersion=10.0.17763` (64-bit only as before); the setup binary refuses to run on older systems.
- **README and the installation guide now state the OS requirements.** Windows 10 1809+ 64-bit; macOS 14 (Sonoma) or newer on Apple Silicon only; Linux x86_64 with glibc 2.39 or newer (the Ubuntu 24.04 build baseline, same as the .deb/.rpm/Arch packages).

#### Fixed
- **Windows in-place upgrades would have registered as a second application.** Releases up to 7.0.0 shipped without an explicit `AppId`, so Inno used `AppName` (“Easy Math Lang”) as the implicit AppId and the uninstall key `Easy Math Lang_is1`; a brief update-branch change then declared a different, brace-wrapped `AppId` literal, which would have made the new installer not see existing installs (two Add/Remove Programs entries, mismatched uninstaller). `AppId` is now exactly `AppName` (no braces), `tests/test_installer_script.py` guards the value and scans the repo for stale braces references, and CI now installs the previous release first and then this build over it, requiring exactly one uninstall entry named “Easy Math Lang” (the manual procedure is documented in `docs/packaging.md` for environments where the previous asset cannot be downloaded).
- **The Windows self-update helper could not replace the files it ran from.** The helper was `easy-math-lang.exe` inside the install directory — a running process locking the very files the installer must replace (and a candidate for `/CLOSEAPPLICATIONS` to close). The helper now launches the installer detached and exits immediately — nothing from the install directory is alive when files are replaced — the editor is relaunched afterwards by an Inno `[Run]` entry (only with `/UPDATE=1`, via `{param:UPDATE|0}` and a `Check` function; the editor runs with the original user’s, non-admin, credentials), and a failure is detected on the next editor start (pending-update marker in the update state file + version compare + `update-install.log`), shown once with the log path and a manual-download button. `/CLOSEAPPLICATIONS`/`/RESTARTAPPLICATIONS` are no longer passed to the silent install.
- **Windows installer flattened the shared PyInstaller `_internal/` directory — every installed `.exe` failed to start.** `installer/setup.iss` copied the contents of `_internal\*` into `{app}\bin` directly (introduced in the shared-bundle rework, shipped in v6.0.0 and v7.0.0), so the onedir bootloader never found `bin\_internal\python312.dll` and each installed executable aborted with "Failed to load Python DLL '…\bin\_internal\python312.dll'. LoadLibrary: The specified module could not be found." The bundle now installs to `{app}\bin\_internal` (flags unchanged; the four `.exe` files still go to `{app}\bin`), `tests/test_installer_script.py` guards the layout statically, the Windows CI job silently installs the built installer and verifies `bin\_internal\python312.dll` exists and `easy-math-lang.exe --version` / `ezmath.exe --version` exit 0 before uploading the artifact, and `docs/troubleshooting.md` documents the error with a manual repair workaround (create `_internal\` next to the executables and move everything except the `.exe` files into it, or reinstall with the fixed installer).

#### Security
- **The elevated install now re-verifies the downloaded installer (TOCTOU narrowing).** The SHA-256 checked at download time is recorded in the update plan, and the helper recomputes it — plus the file size and a symlink check — just before any installer command runs (all platforms, and before the macOS bundle swap/DMG attach). On mismatch the install aborts with a persisted error ("installer changed after verification") and nothing is executed; the temp dir is kept `0700` and the plan file `0600`.

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

[7.1.0]: https://github.com/duo8097/easy-math-lang/compare/v7.0.0...v7.1.0
