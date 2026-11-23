# src/typst_bundle — vendored Typst packages (offline `*draw`)

This package ships the Typst packages needed for `*draw` geometry
inside the repository and inside frozen packaged builds, so `*draw`
works fully offline with no first-run download from packages.typst.org.

## What it does

- **Defines** which Typst packages are vendored and at which pinned
  versions (currently CeTZ 0.4.2 for drawing, plus oxifmt 1.0.0 which
  CeTZ imports).
- **Builds** the `#import "@preview/cetz:0.4.2"` line that the
  geometry codegen emits into generated Typst documents.
- **Locates** the vendored package root: in a PyInstaller frozen build
  (under `sys._MEIPASS`) or in a source checkout (`vendor/typst-packages/`)
  or a pip-installed wheel (package data).
- **Returns** the path to pass to Typst as `package_path`, so Typst
  resolves `@preview` imports from the bundle and never touches the
  network.

Stdlib only — nothing here may import `geometry`, `compiler`, or
`editor`. It is a leaf module at the top level so neither package has
to import the other.

## Important files

| File | What it does |
|------|--------------|
| `__init__.py` | `cetz_spec()` (`@preview/cetz:0.4.2`), `cetz_import_line()` (`#import "..."`), `vendored_packages_dir()` (locates the bundle), `TYPST_PACKAGES` (the pinned package list). |

## Data flow

```
vendor/typst-packages/          (or sys._MEIPASS in frozen builds)
    │
    ▼
vendored_packages_dir()        returns the absolute path, or None
    │
    ▼
geometry.codegen               emits #import "@preview/cetz:0.4.2"
compiler.pipeline              passes package_path to typst.compile()
    │
    ▼
typst.compile()                resolves @preview from the bundle —
                                fully offline, no download needed
```

If the bundle is missing (`None`), Typst falls back to its default
behavior (user cache, then download) — the build never crashes.

## I want to change X, which file do I open?

| Change | File |
|--------|------|
| Add/update a vendored Typst package | `__init__.py` (`TYPST_PACKAGES`, `CEZ_VERSION`) + `scripts/vendor_typst_packages.py` + `vendor/typst-packages/` |
| Change the import line format | `__init__.py` (`cetz_import_line`) |
