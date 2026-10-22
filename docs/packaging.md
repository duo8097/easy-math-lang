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
| `easy-math-lang.exe` | onefile CLI | Compiler (`.ezmath` → PDF/PNG/SVG/HTML/Typst via Typst) |
| `ezmath.exe` | onefile CLI | Same compiler binary under the short alias name (file copy, not a rebuild) |
| `easy-math-lsp.exe` | onefile CLI | Language server (compiler bundled in-process) |
| `easy-math-editor/` | onedir GUI (`--windowed`) | Desktop editor (PySide6) |

Inno Setup (`installer/setup.iss`) packs them into `EasyMathLang-Windows-x64-Setup.exe`
with this installed layout:

```
{app}/
├── bin/
│   ├── easy-math-lang.exe
│   ├── ezmath.exe
│   └── easy-math-lsp.exe
└── editor/
    └── easy-math-editor.exe (+ support files)
```

The editor shortcut points at `{app}\editor\easy-math-editor.exe`.
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
| `scripts/build_binaries.py` | Freezes the three binaries with PyInstaller (entry points, per-platform flags, `ezmath` alias copy). The entry shims are written to a temp dir, so no `entry_*.py` is left in the repo. |
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

---

## What gets built (macOS)

Same three binaries, macOS names, built by
`.github/workflows/build-installers.yml` on `macos-15` (arm64,
Apple Silicon only, M1 or newer; does not run on Intel Macs).
Intel Macs can still run from source (`uv sync`). The build is still
experimental / ad-hoc signed, not notarized:

| Binary | Mode | Contents |
|---|---|---|
| `easy-math-lang` | onefile CLI | Compiler (`.ezmath` → PDF/PNG/SVG/HTML/Typst) |
| `ezmath` | onefile CLI | Same compiler copy (alias) |
| `easy-math-lsp` | onefile CLI | Language server |
| `easy-math-editor.app` | GUI bundle (`--onedir --windowed`) | Desktop editor; helpers bundled in `Contents/Resources/bin/` |

Staged DMG layout (only the `.app` ships, so dragging it alone to
`/Applications` keeps working — `editor/paths.py` finds the helpers
inside the bundle without `PATH`):

```
staging/
├── easy-math-editor.app   (Contents/Resources/bin/easy-math-lang, …)
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
| `easy-math-lang` | onefile CLI | Compiler (`.ezmath` → PDF/PNG/SVG/HTML/Typst via Typst) |
| `ezmath` | onefile CLI | Same compiler copy (alias) |
| `easy-math-lsp` | onefile CLI | Language server |
| `easy-math-editor/` | onedir GUI | Desktop editor (PySide6) |

Both packages install the same FHS layout (mirroring
`installer/PKGBUILD` for Arch):

```
usr/
├── bin/
│   ├── easy-math-lang
│   ├── ezmath
│   ├── easy-math-lsp
│   └── easy-math-editor -> /usr/lib/easy-math-lang/easy-math-editor/easy-math-editor
├── lib/easy-math-lang/easy-math-editor/   (onedir GUI bundle)
├── share/applications/easy-math-editor.desktop
├── share/doc/easymath/                    (README, copyright)
└── share/licenses/easymath/               (LICENSE)
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

## How the editor finds its helpers at runtime

All resolution lives in `src/editor/paths.py` (stdlib only, so it bundles
cheaply). Order for each of `easy-math-lsp` / `easy-math-lang`:

1. `EASYMATH_LSP_EXE` / `EASYMATH_COMPILER_EXE` environment override.
2. Binaries next to the running executable: the venv `Scripts/` dir from
   source; the installer's `../bin` or a side-by-side `dist/` when frozen.
3. `PATH` via `shutil.which`.
4. Source only: `[sys.executable, '-m', ...]` (needs
   `src/compiler/__main__.py` for `python -m compiler`).
5. Frozen last resort: the bare exe name, so `QProcess` reports
   "failed to start" instead of crashing.

Rules that bit us before (do not regress):

- **Never run `[sys.executable, '-m'/'-c', ...]` when frozen** —
  `sys.executable` is then the bundled binary itself, not a Python
  interpreter.
- **Never assume `bin/` is on `PATH`** — it is opt-in during setup.
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
