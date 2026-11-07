# Packaging and releases (for developers)

End users should start with the [Installation guide](installation.md).
This page documents how the Windows/macOS installers and their binaries
are built, how the editor finds them at runtime, and how to test all of it.

---

## What gets built (Windows)

Three PyInstaller binaries, with the exact flags used by CI
(`scripts/build_binaries.py`):

| Binary | Mode | Contents |
|---|---|---|
| `easy-math-lang/` (shared bundle) | onedir CLI | Compiler (`.ezmath` → PDF/PNG/SVG/HTML/Typst via Typst) |
| `ezmath` | symlink / file copy | Short alias to the compiler (POSIX: relative symlink; Windows: copy) |
| `easy-math-lsp/` (shared bundle) | onedir CLI | Language server (compiler bundled in-process) |
| `easy-math-editor` (shared bundle) | onedir GUI (`--windowed`) | Desktop editor (PySide6) |

All three executables are assembled into ONE shared bundle directory
(`dist/easy-math-lang/` with a single `_internal/`) by
`scripts/build_binaries.py` (Approach A): the CLI and the language server
reuse the desktop editor's collected libraries instead of each carrying
their own copy, so an install holds exactly one copy of NumPy, Matplotlib,
Typst, PySide6, …

Inno Setup (`installer/setup.iss`) packs the shared bundle into
`EasyMathLang-Windows-x64-Setup.exe` with this installed layout:

```
{app}/
└── bin/
    ├── easy-math-lang.exe
    ├── easy-math-lsp.exe
    ├── easy-math-editor.exe
    ├── ezmath.exe
    └── _internal/ (+ editor assets, vendored Typst packages)
```

The installer version comes from `pyproject.toml` — never hard-coded.
CI reads it with `tomllib` (the same source of truth as
`scripts/check_tag_version.py`) and passes it to ISCC as
`/DAppVersion=<version>`; `setup.iss` defines a `0.0.0` fallback under
`#ifndef AppVersion` so a hand-run `ISCC.exe installer\setup.iss` still
compiles (with a placeholder version instead of a stale one).
`tests/test_installer_script.py` guards this statically.

The editor shortcut points at `{app}\bin\easy-math-editor.exe`.
Adding `{app}\bin` to `PATH` is an **optional** setup task that targets the
**per-user** `PATH` (`HKCU\Environment`, broadcast via `WM_SETTINGCHANGE`
so new terminals pick it up) — the editor must work without it (see below).
Never write `PATH` to `HKLM\Environment`: it is not a real environment
location, and creating keys directly under `HKLM` fails on some machines
with `RegCreateKeyEx failed; code 87`, aborting the whole install.
`tests/test_installer_script.py` guards this statically.

Note: ISCC prints a `UsedUserAreasWarning` because the setup runs
elevated (`PrivilegesRequired=admin`) yet writes `HKCU`. That is intended:
with the usual UAC consent prompt `HKCU` is the installing user's own
hive, so the optional PATH entry lands in the right place. Only
over-the-shoulder elevation (different admin credentials) would target
the admin's hive instead — an accepted edge case, same as most installers.

---

## The build scripts

Every build path (CI and local) goes through the same shared scripts, so
the PyInstaller flags exist exactly once:

| Script | Does |
|---|---|
| `scripts/build_binaries.py` | Freezes the three binaries with PyInstaller (entry points, per-platform flags, `ezmath` alias, shared-bundle assembly) into `dist/easy-math-lang/` (one `_internal/` for the CLI, the LSP and the editor). The entry shims are written to a temp dir, so no `entry_*.py` is left in the repo. |
| `scripts/package_macos.sh` | macOS only: bundles the helpers into the `.app`, prunes the nested Qt tool apps, signs the bundle inside-out and (with `--stage`) writes the DMG layout to `staging/`. |
| `scripts/check_tag_version.py` | Release guard: fails the build when a `v*` tag does not match the `pyproject.toml` version. |

The local drivers only orchestrate them:

| Local build | Command |
|---|---|
| Windows | `powershell -ExecutionPolicy Bypass -File scripts/build_local.ps1` |
| macOS | `bash scripts/build_macos.sh` |
| Linux (`.deb` + `.rpm`) | `bash installer/build_linux.sh` |
| Arch (`.pkg.tar.zst`) | `bash installer/build_arch.sh` (on Arch) |

All of them leave their output in `dist/` (gitignored). Every push runs
the same steps in CI and uploads the installer(s) as run artifacts
(14-day retention); tagging a commit `v*` additionally attaches them to
a stable GitHub Release (hyphenated tags become prereleases). The
nightly schedule, pull requests and manual dispatch build the same way.

### Binary size

The builder uses PyInstaller's normal dependency hooks rather than
`--collect-all` for NumPy, Matplotlib, Typst and pygls. The custom Matplotlib
backend hook keeps Agg and SVG for plots. The CLI excludes
Qt/Tk; the LSP also excludes Typst and Matplotlib but retains NumPy for
geometry diagnostics. The editor keeps its PDF renderer and preview modules.

Linux builds enable PyInstaller's `--strip`: native libraries are stripped in
its cache **before** being packed into the executable. Install `binutils` if
`strip` is unavailable, or use `python scripts/build_binaries.py --no-strip`
to retain native symbols for debugging. Windows/macOS do not enable stripping
by default. Never run `strip` directly on a completed onedir executable or
onefile executable; that can destroy its appended archive.

On Linux/macOS, `ezmath` is a relative symlink to `easy-math-lang`, including
inside installers/the macOS app. Distribute the two names together; Windows
keeps a standalone `.exe` copy. A symlink avoids storing the entire compiler
twice and remains valid when the containing directory is moved.

To validate a build on Linux, run:

```bash
EASYMATH_RUN_BUILD_TESTS=1 uv run --frozen pytest tests/test_packaged_build.py -q
```

These tests cover PDF/PNG/SVG plots through the alias, geometry
diagnostics in the LSP, and editor startup with its Qt/PDF modules. Windows
uses its existing editor/LSP process test instead of the POSIX startup test.

For size comparisons, count regular files once and do not follow symlinks;
following Qt/NumPy library symlinks overstates the payload size.

---

## What gets built (macOS)

Same three binaries, macOS names, built by
`.github/workflows/build-installers.yml` on `macos-15` (arm64,
Apple Silicon only, M1 or newer; requires macOS 14 (Sonoma) or newer
and does not run on Intel Macs). Intel Macs on macOS 14+ can still
run from source (`uv sync`; the PySide6 wheels are universal2).
The build is still experimental / ad-hoc signed, not notarized:

| Binary | Mode | Contents |
|---|---|---|
| `easy-math-lang` | onedir CLI | Compiler (`.ezmath` → PDF/PNG/SVG/HTML/Typst) |
| `ezmath` | symlink | Relative alias to `easy-math-lang` |
| `easy-math-lsp` | onedir CLI | Language server |
| `easy-math-editor.app` | GUI bundle (`--onedir --windowed`) | Desktop editor; helpers bundled in `Contents/MacOS/` |

The `.app` carries the Easy Math icon: PyInstaller's BUNDLE step copies
`icons/ezmath.icns` into `Contents/Resources/` and writes the matching
`CFBundleIconFile` entry into the generated `Info.plist`, so Finder and
the Dock show it. Only the `.icns` goes into the bundle; the runtime Qt
window icon stays the single bundled 256px PNG (see above) on every
platform. The DMG volume itself carries no custom icon (the plain
`hdiutil create` invocation has no volume-icon option), so the visible
icon is the `.app`'s own Finder icon inside the image.

Staged DMG layout (only the `.app` ships, so dragging it alone to
`/Applications` keeps working — `editor/paths.py` finds the helpers
inside the bundle without `PATH`):

```
staging/
├── easy-math-editor.app   (Contents/MacOS/easy-math-lang, …,
│                           Contents/Frameworks/typst-packages/,
│                           Contents/Resources/THIRD_PARTY_LICENSES)
├── Applications -> /Applications (symlink for drag-and-drop install)
└── README.txt
```

`hdiutil` packs `staging/` into the single `EasyMathLang-macOS-arm64.dmg`.
`scripts/package_macos.sh` does the bundling, the pruning and the
signing — signing is inside-out
(nested code, then the bundle — never recursive for the final sign) with
`codesign --verify --deep --strict` afterwards, and the step has no
leniency: a bad signature fails the job. Ad-hoc means first launch still
needs right-click → **Open**. Static checks live in
`tests/test_macos_packaging.py`.

---

## What gets built (Linux)

Same three binaries, Linux names, built by
`.github/workflows/build-installers.yml` on `ubuntu-24.04`
(x86_64 only) via `installer/build_linux.sh`:

| Binary | Mode | Contents |
|---|---|---|
| `easy-math-lang` | onedir CLI | Compiler (`.ezmath` → PDF/PNG/SVG/HTML/Typst via Typst) |
| `ezmath` | symlink | Relative alias to `easy-math-lang` |
| `easy-math-lsp` | onedir CLI | Language server |
| `easy-math-editor` | onedir GUI | Desktop editor (PySide6) |

Both packages install the same FHS layout (mirroring
`installer/PKGBUILD` for Arch): the exes live in `/usr/lib/easy-math-lang/`
together with one shared `_internal/`, and `/usr/bin` holds the command
symlinks:

```
usr/
├── bin/
│   ├── easy-math-lang -> /usr/lib/easy-math-lang/easy-math-lang
│   ├── ezmath -> easy-math-lang
│   ├── easy-math-lsp -> /usr/lib/easy-math-lang/easy-math-lsp
│   └── easy-math-editor -> /usr/lib/easy-math-lang/easy-math-editor
├── lib/easy-math-lang/   (shared onedir bundle: exes + one _internal
│                          with the vendored Typst packages)
├── share/applications/easy-math-editor.desktop
├── share/icons/hicolor/<size>x<size>/apps/ezmath.png  (16/32/48/64/
│                                                        128/256; backs
│                                                        Icon=ezmath)
├── share/doc/easymath/                    (README, copyright,
│                                            THIRD_PARTY_LICENSES)
└── share/licenses/easymath/               (LICENSE, THIRD_PARTY_LICENSES)
```

- `installer/build_linux.sh` (run from the repo root on Linux) writes
  `dist/easymath_<ver>_amd64.deb` and `dist/easymath-<ver>-1.x86_64.rpm`
  plus stable `dist/EasyMathLang-Debian-amd64.deb` (Debian/Ubuntu/Mint)
  and `dist/EasyMathLang-Fedora-amd64.rpm` (Fedora/RHEL/openSUSE) copies
  attached to the stable GitHub Release. Version comes from `pyproject.toml` — never hard-coded.
- The `.deb` is assembled with `dpkg-deb` (required); the `.rpm` needs
  `rpmbuild` and is skipped with a warning when it is missing
  (CI installs the `rpm` package first).
- CI smoke-tests the installed `.deb` (`dpkg -i`, `--version`, compile
  of `examples/example.ezmath`) and inspects the `.rpm` payload
  (`rpm -qip` / `rpm -qlp`) before uploading artifacts. Static checks
  live in `tests/test_linux_packaging.py`.

---

## What gets built (Arch)

`installer/PKGBUILD` builds the same three binaries for Arch and packs
them into `easy-math-lang-git-<version>-<rel>-x86_64.pkg.tar.zst`.
The installed layout is the FHS layout above
(`/usr/bin/easy-math-lang`, `ezmath`, `easy-math-lsp`,
`easy-math-editor` → `/usr/lib/easy-math-lang/…`).

- `installer/build_arch.sh` (run from the repo root **on Arch**) packs
  the checked-out tree into a source tarball, patches a copy of the
  PKGBUILD to use it and runs `makepkg`; the finished package lands in
  the repo root. The editor uses selective Qt collection, including the
  PDF preview modules, just like Windows and macOS.
- `pkgver()` describes the commit in a VCS checkout and falls back to
  the `pyproject.toml` version for the tarball source the CI build uses
  (a pull request is packaged exactly as checked out — no access to the
  upstream repository is needed).
- CI builds the package in an `archlinux:base` container (makepkg only
  runs on Arch and refuses to run as root, so the build runs as an
  unprivileged user) and uploads the `.pkg.tar.zst` as
  `EasyMathLang-Arch-x86_64`; it is attached to the GitHub Release
  like the other installers.

---

## Vendored Typst packages (offline `*draw`)

`*draw` renders through CeTZ, a Typst package. Typst normally downloads
`@preview/…` packages from packages.typst.org on first use — which
means a machine without internet access could not use `*draw` at all.
Easy Math instead **vendors** the packages it needs and ships them in
the repo and the packaged builds, so `*draw` works fully offline with
no first-run download.

| | cetz | oxifmt |
|---|---|---|
| Version | 0.4.2 | 1.0.0 (imported by cetz — the complete transitive set) |
| Size (vendored) | 410.0 KiB | 63.4 KiB (473.4 KiB total) |
| License | LGPL-3.0-or-later | MIT OR Apache-2.0 |
| Upstream | https://github.com/cetz-package/cetz | https://github.com/PgBiel/typst-oxifmt |

Layout: `vendor/typst-packages/preview/<name>/<version>/` — exactly
what Typst expects as a package path. `typst.toml`, all `.typ`
sources, the LICENSE files and runtime assets (CeTZ's WASM core) are
kept; manuals, galleries, docs PDFs and tests are pruned by the
vendor script. See `vendor/typst-packages/README.md`.

### How it is wired

- `src/typst_bundle/` pins the versions (`TYPST_PACKAGES`,
  `CEZ_VERSION`) and builds the `#import` line used by the geometry
  codegen. It is the single source of truth; `geometry` and
  `compiler` both import it.
- `compiler.pipeline._run_typst_export()` (the only `typst.compile()`
  caller in the compiler, verified with grep) resolves the bundle via
  `typst_bundle.vendored_packages_dir()` and passes it as
  `package_path`. Typst checks the package path **before** its user
  cache and **before** the network; the bundled copy always wins
  (verified by compiling with a corrupt cache copy present, and with a
  dead proxy). If the bundle directory is missing or incomplete, the
  code passes nothing and Typst falls back to its usual behavior
  (user cache, then download) — it never crashes.
- From source, the bundle resolves to `<repo>/vendor/typst-packages`;
  frozen by PyInstaller, it resolves to `sys._MEIPASS/typst-packages`;
  pip-installed wheels ship the bundle as package data
  (`typst_bundle/typst-packages`, via hatch's `force-include`). Frozen
  builds ship exactly one copy under `_internal/typst-packages/`
  (editor build's data files; the CLI and the LSP reuse that same
  `_internal/`).
- `tests/test_typst_bundle.py` fails when the vendored tree doesn't
  match the pins (each package's `typst.toml` must match its directory
  name and version; LICENSE files must be present). The offline test
  there compiles a `*draw` document with every package-cache location
  redirected to an empty temporary directory and asserts the cache is
  still empty afterwards, proving nothing was downloaded.
  `tests/test_packaged_build.py` does the same against the frozen
  binaries (with dead proxies) and asserts the bundle ships in
  `_internal/`.

### Updating the vendored packages

1. Edit the pins in `src/typst_bundle/__init__.py`
   (`TYPST_PACKAGES`, and `CEZ_VERSION` for the import line).
2. Edit `PACKAGES` in `scripts/vendor_typst_packages.py` — same
   name/version pairs plus the new SHA-256 of each tarball
   (`sha256sum cetz-<version>.tar.gz` after downloading it, or read it
   from the script's failure output).
3. Delete the old tree and re-vendor:

   ```bash
   rm -rf vendor/typst-packages/preview/<name>
   uv run --frozen python scripts/vendor_typst_packages.py
   uv run --frozen python scripts/vendor_typst_packages.py --check
   ```

4. Review the diff and commit the script, the constant and the new
   `vendor/` files together. `tests/test_typst_bundle.py` fails if any
   pin drifts.
5. CeTZ's own transitive dependencies must be re-verified on every
   cetz bump: delete `oxifmt` (and any other dependency) from the
   vendored tree, then compile a `*draw` document offline — Typst will
   name any missing package it tries to download.

### Licensing

The vendored packages are **not** MIT. CeTZ is LGPL-3.0-or-later (its
LGPL incorporates GPLv3 by reference) and ships unmodified; oxifmt is
MIT OR Apache-2.0. `THIRD_PARTY_LICENSES` (repo root) carries the
upstream repository URLs and the verbatim license texts, and every
installer ships it (Windows: `{app}`; Debian/RPM:
`/usr/share/doc/easymath` + `/usr/share/licenses/easymath`; Arch:
`/usr/share/licenses/<pkg>`; macOS: `Contents/Resources/` in the
`.app`). The packages stay unmodified plain `.typ` files so users can
inspect and replace them. See
[THIRD_PARTY_LICENSES](../THIRD_PARTY_LICENSES).

---

## How the editor finds its helpers at runtime

All resolution lives in `src/editor/paths.py` (stdlib only, so it bundles
cheaply). Order for each of `easy-math-lsp` / `easy-math-lang`:

1. `EASYMATH_LSP_EXE` / `EASYMATH_COMPILER_EXE` environment override.
2. Binaries next to the running executable: the venv `Scripts/` dir from
   source; the installer's `bin/` folder (which holds the editor and the
   shared `_internal/`), or a side-by-side `dist/` when frozen.
3. `PATH` via `shutil.which`.
4. Source only: `[sys.executable, '-m', ...]` (needs
   `src/compiler/__main__.py` for `python -m compiler`).
5. Frozen last resort: the bare exe name, so `QProcess` reports
   "failed to start" instead of crashing.

Rules that bit us before (do not regress):

- **Never run `[sys.executable, '-m'/'-c', ...]` when frozen** —
  `sys.executable` is then the bundled binary itself, not a Python
  interpreter.
- **Never assume any install folder is on `PATH`** — it is opt-in during
  setup (the editor itself never needs it).
- The LSP needs no subprocess to reach the compiler: it imports
  `compiler`/`geometry` in-process, so both must stay bundled in
  `easy-math-lsp.exe` (they are picked up automatically via
  `entry_lsp.py` imports).

---

## Testing

Fast unit tests for the resolution logic (fake trees, no build needed):

```
uv run pytest tests/test_editor_paths.py -v
```

Static checks for the installer script (hive choice, broadcast flag,
`NeedsAddPath` consistency) run in the normal suite:

```
uv run pytest tests/test_installer_script.py -v
```

Slow tests against real binaries in `dist/` (opt-in so the normal suite
stays fast):

```
powershell -ExecutionPolicy Bypass -File scripts/build_local.ps1
$env:EASYMATH_RUN_BUILD_TESTS = '1'
uv run pytest tests/test_packaged_build.py -v
```

`tests/test_packaged_build.py` covers: the compiler exe producing a real
PDF, a full stdio session with the frozen LSP, and the frozen editor
(launched offscreen in an installer-like `dist/bin` layout) staying alive
and spawning `easy-math-lsp.exe` — the exact failure this setup once had.
Without the env var (or without `dist/`) these tests skip with a message
saying how to enable them.

## Build performance

The shared builder and local scripts default to at most two CPU workers (one on
single-CPU systems). `--jobs N` overrides `EASYMATH_BUILD_JOBS`, which overrides
the automatic default. Installer CI explicitly uses two workers. Each target has
its own work directory and binary cache.

Windows: `powershell -ExecutionPolicy Bypass -File scripts/build_local.ps1 -Jobs 2`.
macOS: `bash scripts/build_macos.sh --jobs 2`.
Linux: `bash installer/build_linux.sh --jobs 2`.
Arch: `EASYMATH_BUILD_JOBS=2 bash installer/build_arch.sh`.
Set jobs to 1 for lower memory use. All local wrappers use the frozen lockfile.

Generated entry scripts and specs now live at stable paths under ignored
`build/`; unchanged entry scripts are not rewritten. PyInstaller can therefore
reuse Analysis/PYZ on subsequent builds, while still checking source changes.
Delete `build/` for a clean rebuild. Arch packaging extracts a fresh source tree
in a temporary directory, so it benefits from parallelism but does not retain
this incremental work cache between package builds.
The `ezmath` alias is copied only after all three builds succeed.

All platforms collect the Qt modules used by the editor rather than the entire
PySide6 distribution. `--full-pyside6` remains a troubleshooting option (do not
use it for macOS signing). Windows runs the opt-in packaged-binary smoke tests
before compiling the installer; the existing macOS and Linux checks remain.

Inno Setup uses `lzma2/fast`, trading some compression ratio for build speed.
Artifact upload uses compression level 0 because installers are already
compressed. Compare job step durations in Actions to measure the improvement;
runner load and cold dependency caches affect total time.
