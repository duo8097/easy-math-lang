# Agent guide

easy-math-lang compiles simple `.ezmath` math documents to Typst and exports them.
Main packages: [compiler](src/compiler/) (language and CLI), [geometry](src/geometry/) (`*draw`), [lsp](src/lsp/) (editor protocol), and [editor](src/editor/) (PySide6 desktop app). Read [the architecture map](docs/architecture.md) before changing an unfamiliar area.

## Setup and commands

- Python 3.12+ and `uv` are required; install dependencies with `uv sync`.
- `uv run easy-math-lang file.ezmath` (or `uv run ezmath file.ezmath`) runs the compiler.
- `uv run easy-math-editor` starts the desktop editor.
- `uv run easy-math-lsp` starts the language server on standard input/output.
- CI sets `QT_QPA_PLATFORM=offscreen` for Qt tests. Use that setting locally too.
- Run CI's test command exactly:

  ```sh
  QT_QPA_PLATFORM=offscreen uv run --frozen pytest tests/ --ignore=tests/test_packaged_build.py -q
  ```

- Run one test file, for example:

  ```sh
  QT_QPA_PLATFORM=offscreen uv run --frozen pytest tests/test_compiler.py -q
  ```

## Required checks

Before every commit, run the CI-style test command above and:

```sh
python scripts/gen_toc.py --check
```

After changing headings in a `docs/*.md` file with a generated table of
contents, run `python scripts/gen_toc.py`, then run the check again.

`scripts/check_links.py` is not on this branch's base (`main`). Do not add a
command for a script that is absent; add its check here only when that script
is merged into `main`.

## Repository rules

- Write all code, comments, docs, and commit messages in English.
- `main` is protected. Work on a branch, push it, and open a pull request.
- Keep one logical change per commit. Do not mix cleanup with a feature or docs PR.
- Add an entry under `## [Unreleased]` in `CHANGELOG.md` for user-visible changes.
- Do not hand-edit generated content:
  - table-of-contents blocks between `<!-- toc -->` markers; use `scripts/gen_toc.py`;
  - `src/editor/assets/draw_previews/*.svg` and its `manifest.json`; use
    `scripts/build_draw_previews.py`;
  - dated release sections in `CHANGELOG.md`; `scripts/bump_version.py` moves
    `Unreleased` into a release section;
  - vendored Typst packages under `vendor/typst-packages/`; update them with
    `scripts/vendor_typst_packages.py` after changing its verified pins.

For contribution workflow and release details, read [CONTRIBUTING.md](CONTRIBUTING.md).

## Code and test conventions

- Use 4-space indentation, `snake_case`, and single-quoted strings. Match the
  surrounding file; there is no configured formatter or linter.
- Start modules with a short plain-language docstring. Keep public functions
  and classes documented in the same beginner-friendly style.
- Use a raw docstring (`r"""..."""`) when its prose includes backslashes.
- Large files begin with a docstring section index. Within long modules, use
  the existing dashed section separators (`# ----------------------------------------------------------------------`).
- Place tests in `tests/test_<area>.py` or `tests/test_<area>_<topic>.py`.
  Compiler tests commonly use `compile_text` from `tests/test_compiler.py` and
  assert generated Typst text plus stderr. GUI tests use the headless `qapp`
  fixture; do not require a display.
- The compiler is the one syntax implementation. The LSP and preview reuse its
  modules; do not create a second parser.

When adding `.ezmath` syntax, inspect comparable history first. Recent feature
commits update the relevant compiler parser/transform (`src/compiler/`), LSP
analysis and completion/hover tables (`src/lsp/analysis.py`,
`src/lsp/builtins.py`), editor affordances when applicable (including
`src/editor/syntax_highlighter.py`), `rule.txt`, user docs such as
`docs/cheatsheet.md`, and focused tests. Geometry features also update
`src/geometry/` and geometry/editor catalog tests. Do not blindly touch every
file: follow the closest existing feature and its tests.

## Known gotchas

- `tests/test_install_detect.py::test_macos_readonly_bundle_falls_back` fails
  when tests run as root; it also fails on `main`. Do not change it as part of
  unrelated work.
- `pytest` is configured to use xdist with `--dist loadfile`. For serial
  debugging, `pyproject.toml` documents `-p no:xdist -o addopts=`.
- LSP protocol traffic uses stdout. Send LSP logs to stderr or editors can
  disconnect.

## Don't

- Do not read large files end to end: `src/editor/main_window.py`,
  `src/compiler/pipeline.py`, and `src/compiler/updater.py` have top-of-file
  section indexes. Search first, then read narrow line ranges.
- Do not refactor or rename unrelated code in a docs or feature PR.
- Do not print full test output. Capture it if needed and inspect only its tail
  while preserving the test command's exit status.
