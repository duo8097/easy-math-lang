# Packaging and releases (for developers)

End users should start with the [Installation guide](installation.md).
This page documents how the Windows installer and its binaries are built,
how the editor finds them at runtime, and how to test all of it.

---

## What gets built

Three PyInstaller binaries, with the exact flags used by CI
(`.github/workflows/build-windows-installer.yml`):

| Binary | Mode | Contents |
|---|---|---|
| `easy-math-lang.exe` | onefile CLI | Compiler (`.ezmath` → PDF via Typst) |
| `easy-math-lsp.exe` | onefile CLI | Language server (compiler bundled in-process) |
| `easy-math-editor/` | onedir GUI (`--windowed`) | Desktop editor (PySide6) |

Inno Setup (`installer/setup.iss`) packs them into `EasyMathLangSetup.exe`
with this installed layout:

```
{app}/
├── bin/
│   ├── easy-math-lang.exe
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

## Building locally

From the repo root (Windows):

```
powershell -ExecutionPolicy Bypass -File scripts/build_local.ps1
```

This writes temporary `entry_*.py` shims, runs the same three PyInstaller
commands as CI, removes the shims again, and leaves the output in `dist/`
(gitignored). Tagging a commit `v*` (or manual dispatch) runs the same
steps in CI, compiles the installer, and attaches it to a GitHub Release.

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
