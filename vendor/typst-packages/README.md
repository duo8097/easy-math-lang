# Vendored Typst packages

This directory holds the Typst packages that easy-math-lang bundles so
`*draw` works fully offline — no first-run download from
packages.typst.org. It is populated by and verified with:

```sh
uv run --frozen python scripts/vendor_typst_packages.py          # download + verify + extract
uv run --frozen python scripts/vendor_typst_packages.py --check  # verify without network
```

Layout matches what Typst expects as a package path:
`preview/<name>/<version>/`. Do not edit the files by hand — they are
upstream release tarballs (verified by SHA-256, see the script), pruned
of files not needed to compile (docs PDFs, manuals, galleries, tests).
`typst.toml`, all `.typ` sources, the LICENSE files and runtime assets
(e.g. CeTZ's WASM core) are kept intact.

The pinned version lives in `src/typst_bundle/__init__.py` (single
source of truth) and must stay in sync with the script's `PACKAGES`
pins; `tests/test_typst_bundle.py` enforces this.
