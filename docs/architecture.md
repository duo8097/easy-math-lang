# Architecture (for contributors)

This page explains how easy-math-lang is put together, so you can find
your way around before touching code. End users should start with the
[Installation guide](installation.md) and [Writing math](algebra.md).

New to the project? Read [Contributing](../CONTRIBUTING.md) first for
the setup steps — then come back here.

---

## The big picture

One `.ezmath` text file in, one PDF (or image/HTML/Typst file) out:

```
                      ┌──────────────────────────────────────────────┐
 doc.ezmath ─────────►│  compiler/pipeline.py                       │
                      │  strip comments → resolve <variables>       │
                      │  → expand *commands → escape → Typst text   │
                      │      ▲              ▲             ▲         │
                      │      │              │             │         │
                      │  geometry/       lsp/ reuses  symbols,      │
                      │  *draw blocks    the same     calc, tables… │
                      │  (solve + draw)  modules                    │
                      └──────────────┬───────────────────────────────┘
                                     │
                        doc.typ + doc.smap.json
                                     │
                               Typst (PyPI)
                                     │
                                     ▼
                     doc.pdf / .png / .svg / .html / .typ
```

Four packages under `src/` — all plain Python packages, imported as
`compiler.*`, `geometry.*`, `lsp.*`, `editor.*`:

| Package | What it does | Entry point |
|---|---|---|
| `src/compiler/` | `.ezmath` → Typst → PDF/images (the whole language) | `easy-math-lang` → `compiler.pipeline:main` |
| `src/geometry/` | `*draw` blocks: parse rules → solve positions → draw (CeTZ) | called by the compiler |
| `src/lsp/` | Language server: errors, completion, hover, outline | `easy-math-lsp` → `lsp.server:main` |
| `src/editor/` | Desktop editor (PySide6) | `easy-math-editor` → `editor.app:main` |

The single most important rule: **there is exactly one parser.** The
language server and the editor's preview both drive the same compiler
modules — never fork the syntax into a second implementation.

---

## The compiler (`src/compiler/`)

### Entry points

- `main()` (`pipeline.py`) — the CLI: parses `--format/--ppi/-o/--strict/…`
  and calls:
- `compile_ezmath(input, output, …)` (`pipeline.py`) — the public API.
  The editor preview, the tests, and the CLI all call this. It is
  wrapped by `@_with_diag_count`, which counts `[Error]`/`[Warning]`
  writes and implements `--strict`.

### What one compile does

1. **Read + strip comments** — `comments.strip_comments` (protects
   URLs and `\ … \` math ranges from `//`).
2. **Line loop** (`compile_ezmath`) — every line is classified:
   fenced blocks, math-mode continuations, friendly statements
   (`let x = 5`), `*define(...)`, single-line and block `*draw(...)`,
   silent blocks `*( ...) `, assignments `<x> = ...`, `*doc_title` /
   `*doc_font` control lines, friendly blocks (`#` headings, lists) —
   and finally normal text.
3. **Per-line text pipeline** — `_render_text_line` runs a fixed
   sequence of phases on each ordinary line (each phase is one small
   module): `*p(...)` raw segments → `<variables>` → undefined check →
   defines → `calc()` → `\ … \` math pairs → `*det`/tables → `*plot` →
   styling/`*image` → math commands → unknown-command warnings
   → `*pi`/`*infinity` → merge math → subscripts → symbol shortcuts →
   multiplication symbol → escape to Typst.
4. **Typst generation** — adds `#set text/page/document`, joins lines,
   writes `doc.typ`, and records a **source map** (`doc.smap.json`) so
   the editor can jump from a PDF position back to your source line.
5. **Failure gates** — an unclosed block or a broken `*draw` stops the
   build before Typst runs (everything else only warns).
6. **Export** — `_run_typst_export()` calls `typst.compile()` for
   PDF/PNG/SVG/HTML (or copies the `.typ` for `typ` exports), then
   intermediate files are cleaned up unless `--save-build-artifacts`.

### Module map

| Module | Responsibility |
|---|---|
| `pipeline.py` | Everything above: line loop, per-line phases, Typst output, CLI |
| `state.py` | `CompileContext` — per-run state (variables, defines, doc title/font, plot counters) |
| `comments.py` | `//` stripping |
| `statements.py` | `*define(...)`, `<x> = ...`, `let x = 5` normalization |
| `variables.py` | `<name>` substitution + `undefined variable` errors |
| `calc.py` | Safe `calc(...)` evaluation (AST whitelist, no `eval`) |
| `safemath.py` | The shared function whitelist for `calc`/`*plot` |
| `math_commands.py` | `*frac`, `*pow`, `*sum`, `*int`, `*diff`, `*cases`, `*set`, `*align`, `*det`, … + argument splitting |
| `inline_math.py` | `\ … \` math mode → Typst `$…$` |
| `symbols.py` | ASCII → Unicode tables (`->` → →, `*alpha` → α) |
| `tables.py` | `*table` / `*matrix` parsing and emission |
| `plots.py` | `*plot` → Matplotlib SVG → `#image(...)` |
| `text_commands.py` | `*bold/*italic/*underline`, `*newpage`, `*image` |
| `escaping.py` | Escaping text so it is safe in Typst |
| `diagnostics.py` | Unknown-command warnings + "did you mean …?" |
| `source_map.py`, `source_links.py` | `.smap.json` sidecar + `eml-src://` PDF click-back links |
| `update.py` | `--check-update` GitHub release lookup |

`math_commands.py` and `pipeline.py` are the two biggest files — both
carry a table-of-contents docstring at the top.

---

## Geometry (`src/geometry/`)

`*draw(...)` blocks go through three stages:

1. **Parse** — `parsing.parse_draw_block` splits the block into
   `(command, args, annotation)` triples.
2. **Solve** — `commands._process_command` turns each command into
   points/constraints on a `GeometrySolver`; `solver.solve()` is a
   hand-rolled gradient-descent fit (NumPy only, deterministic — same
   input always gives the same figure).
3. **Codegen** — `codegen.generate_typst` emits a CeTZ canvas
   (`#import "@preview/cetz:0.4.2"`), embedding errors as comments so
   the rest of the document still builds.

Failures print `[GeometryError] …` to stderr; a hard failure is
signalled back to the compiler by an `// [Error]` placeholder, which
fails the build before Typst runs.

---

## Language server (`src/lsp/`)

- `server.py` — pygls wiring over stdio (JSON-RPC on stdin/stdout;
  **logs must go to stderr** or editors disconnect).
- `analysis.py` — the brain: `analyze_text()` walks the document
  mirroring the compiler's line classification and **reuses**
  compiler modules (`comments`, `statements`, `variables`, `calc`,
  `diagnostics`, `tables`, `geometry.parsing`) instead of parsing a
  second time. Also `complete()`, `hover()`, `document_symbols()`.
- `builtins.py` — completion/hover microcopy; its `_CROSS_CHECK`
  asserts the LSP's command tables stay in sync with the compiler's
  (`diagnostics.KNOWN_COMMANDS`, geometry's command list) and logs a
  warning on drift.

If you add a command to the compiler, this is where completion text
goes too.

---

## Desktop editor (`src/editor/`)

`main_window.py` (≈1900 lines) is the hub; its section banners
(`# LSP lifecycle`, `# Navigation…`, `# Completion + hover`,
`# File operations`, `# Build…`, `# Wiring…`, `# Live preview…`) mark
the table of contents — a fuller map sits in its module docstring.

Three ways the editor talks to the rest of the system:

| Feature | How it runs |
|---|---|
| **Build → Compile** (Ctrl+B) | *Out of process*: `QProcess` runs `easy-math-lang` (found by `paths.resolve_compiler_command`) |
| **Live preview + Export As…** | *In process*: a worker `QThread` calls `compiler.pipeline.compile_ezmath()` directly — works for unsaved documents, no helper needed |
| **Errors / completion / outline** | *Out of process*: `lsp_client.LspClient` runs `easy-math-lsp` over JSON-RPC |

Supporting modules worth knowing:

| Module | Responsibility |
|---|---|
| `paths.py` | Finds the helper binaries in every install type (env var → next to exe → `PATH` → `python -m`). **Stdlib-only** so it bundles cheaply — keep it that way. |
| `preview.py` | Qt-free in-process compile for preview/export (serializes with a lock) |
| `preview_panel.py` | PDF viewer dock, zoom, Ctrl+Click source links |
| `lsp_client.py` | Async LSP client over `QProcess` (state machine + watchdogs) |
| `symbol_registry.py` | The symbol palette catalogue (with a `_cross_check` against compiler specs) |
| `theme.py`, `editor_widget.py`, `syntax_highlighter.py` | Colors, text area, highlighting |
| `problems_panel.py`, `outline_panel.py`, `command_palette.py`, `find_bar.py` | The panels and pickers |
| `positions.py`, `protocol.py`, `pdf_links.py` | Qt-free helpers: UTF-16 ↔ code-point, LSP framing, PDF link parsing — all unit-testable without a GUI |

---

## Tests (`tests/`)

- `tests/conftest.py` puts `src/` on `sys.path`, provides an offscreen
  `qapp` fixture (GUI tests skip/headless cleanly), and redirects the
  editor's config file to a temp dir so tests never touch your real
  settings.
- The common pattern for compiler tests: write a temp `.ezmath` file,
  **stub** the Typst backend (`monkeypatch.setattr(pipeline, "typst", stub)`),
  call `compile_ezmath()`, then assert on the generated `.typ` text and
  captured stderr. See `tests/test_compiler.py`'s `compile_text` helper
  for the canonical shape.
- Geometry tests call `geometry.parse_draw_block(...)` directly; LSP
  tests call `lsp.analysis.analyze_text(...)`.
- `tests/test_packaged_build.py` is **opt-in** (needs `dist/` binaries
  and `EASYMATH_RUN_BUILD_TESTS=1`).
- `tests/test_lazy_imports.py` guards startup cost: NumPy, Typst and
  PySide6 must stay lazily imported where they already are.

Run everything with `uv run pytest tests/ -v`.

> The committed PDFs in `examples/` are illustrative output for users —
> tests do **not** diff against them.

---

## CI and releases (`.github/workflows/`)

| Workflow | Trigger | What it does |
|---|---|---|
| `tests.yml` | every push + PR | `uv sync --frozen`, then the full test suite on **ubuntu + windows** (Python 3.12, `QT_QPA_PLATFORM=offscreen`) |
| `build-installers.yml` | push, PR, nightly cron, tags | builds DMG / deb+rpm / Windows Inno Setup / Arch packages, re-runs tests as a gate, and on a tag matching the `pyproject.toml` version publishes a release |

`scripts/check_tag_version.py` fails the release if the tag and
`pyproject.toml` version disagree. Details: [Packaging and releases](packaging.md).

---

## Where to change what

| I want to… | Start here |
|---|---|
| Add/change a math command (`*foo`) | `compiler/math_commands.py` (add a spec to `math_call_specs` or a dedicated `replace_*_calls`), register the name in `diagnostics.KNOWN_COMMANDS`, then add tests + docs (`rule.txt`, `docs/algebra.md`, `lsp/builtins.py`) |
| Add a symbol (`*foo` → glyph, or `->` → →) | `compiler/symbols.py` (`SYMBOL_REPLACEMENTS` / `WORD_REPLACEMENTS`) — completion picks it up from `symbol_registry.py` / `lsp/builtins.py` |
| Change how lines are processed | `compiler/pipeline.py` (`_render_text_line` phases — keep the order, it is documented in the docstring) |
| Add a geometry command | `geometry/commands.py` (+ `KNOWN_GEOMETRY_COMMANDS`), codegen in `geometry/codegen.py` |
| Fix an error message / add a hint | `compiler/diagnostics.py` (and the matching row in `docs/troubleshooting.md`) |
| Improve completion/hover | `lsp/builtins.py` text; behavior in `lsp/analysis.py` |
| Add an editor feature | `editor/main_window.py` (wire it in `_create_menus`), keep new logic in its own Qt-light module |
| Change the language itself | The human-readable spec is `rule.txt` (also consumed by `lsp/builtins.py` for its help text) |

---

## See also

- [Contributing](../CONTRIBUTING.md) — setup, workflow, PR checklist
- [Packaging and releases](packaging.md) — building installers
- [Language server](lsp.md) — how the LSP is used
- [Glossary](glossary.md) — plain-language definitions
