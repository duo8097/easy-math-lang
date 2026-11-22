# src/compiler — the `.ezmath` → Typst compiler

This package takes a plain-text `.ezmath` file and turns it into Typst
source, which Typst (a PyPI package) then compiles into PDF, PNG, SVG,
HTML, or plain Typst source. No LaTeX needed.

## What it does

1. **Reads** your `.ezmath` text file line by line.
2. **Strips comments** (`// ...`), protecting URLs and math ranges.
3. **Substitutes variables** (`<width>` → 5), **defines** (`*define(...)`),
   and **calc()** expressions (`calc(2 + 3)` → 5).
4. **Runs math commands** (`*frac(2, 3)`, `*pow(x, 2)`, `*pi`, …) and
   **symbol shortcuts** (`==` → `=`, `->` → `→`, `*alpha` → `α`, …).
5. **Draws geometry** (`*draw(...)` blocks) via the `geometry` package.
6. **Writes** an intermediate `.typ` file plus an optional `.smap.json`
   source map (maps generated Typst back to your `.ezmath` lines).
7. **Compiles** with Typst into your chosen output format.

## Important files

| File | What it does |
|------|--------------|
| `pipeline.py` | The main compiler: line loop, 13-phase text pipeline, `.typ` generation, Typst export. `compile_ezmath()` is the public entry point. |
| `statements.py` | Friendly statements: `let x = 5`, `var x = 5`, `*define x = 5`, and bare `<x> = 5` assignments. |
| `variables.py` | Variable substitution (`<var>`), `replace_defines`, `replace_vars`, undefined-variable checking. |
| `calc.py` | Safe `calc(...)` arithmetic evaluation (AST-based, no `eval`). |
| `math_commands.py` | All math commands: `*frac`, `*pow`, `*root`, `*sum`, `*prod`, `*lim`, `*int`, `*diff`, `*set`, `*matrix`, `*cases`, `*align`, and friendly aliases (`*fraction` → `*frac`). |
| `symbols.py` | Symbol shortcuts: `==` → `=`, `->` → `→`, `*alpha` → `α`, Greek letters, set theory, delimiters. |
| `tables.py` | `*table`, `*matrix`, `*mat`, `*cases`, `*align` grid parsing and Typst rendering. |
| `plots.py` | `*plot(expression ; xmin ; xmax)` → Matplotlib SVG → `#image(...)`. |
| `text_commands.py` | `*bold`, `*italic`, `*underline`, `*newpage`, `*image`. |
| `escaping.py` | Escape Typst special characters outside math blocks. |
| `comments.py` | Strip `//` comments while protecting URLs, math pairs, and balanced `*command(...)`. |
| `inline_math.py` | Find unescaped `\\` math delimiters; process inline math mode. |
| `diagnostics.py` | Central diagnostic printer: `[Error]`/`[Warning]` lines with Python-style source context (file, line, column, caret). |
| `source_map.py` | Sidecar `.smap.json` mapping generated Typst ranges back to `.ezmath` spans. |
| `source_links.py` | `eml-src://` links for editor preview click-back navigation. |
| `state.py` | `CompileContext`: per-compile state (doc title, font, plot dir, …). |
| `typst_errors.py` | Map Typst compile errors back to `.ezmath` source lines. |
| `safemath.py` | Safe math constants/functions for `calc()` (pi, e, sin, cos, sqrt, bounded power). |
| `update.py` / `updater.py` | Self-update: check GitHub Releases, download, verify SHA-256, apply. |

## Data flow

```
your file (.ezmath)
    │
    ▼
strip_comments()          remove // comments, protect URLs/math
    │
    ▼
line loop (pipeline.py)   per line: control lines (*define, *draw,
                          *doc_title, *doc_font) are consumed;
                          normal text goes through _render_text_line()
    │
    ▼
_render_text_line()       13 phases: vars → calc → inline math →
                          tables → plots → text commands → math commands
                          → symbols → escape → friendly blocks (#/- /1.)
    │
    ▼
Typst intermediate file   .typ (plus optional .smap.json source map)
    │
    ▼
typst.compile()           Typst (PyPI) → PDF / PNG / SVG / HTML / .typ
    │
    ▼
your output file
```

`pipeline.compile_ezmath()` is the single function everything calls —
the CLI (`main()`), the editor preview, and the tests all use it.

## I want to change X, which file do I open?

| Change | File |
|--------|------|
| Add a new math command (`*foo(...)`) | `src/compiler/math_commands.py` + `docs/cheatsheet.md` + `docs/algebra.md` |
| Add a new symbol shortcut (`@` → `©`) | `src/compiler/symbols.py` + `docs/cheatsheet.md` |
| Change how `calc()` works | `src/compiler/calc.py` |
| Add a new export format | `src/compiler/pipeline.py` (`SUPPORTED_EXPORT_FORMATS`, `infer_export_format`) |
| Change error message format | `src/compiler/diagnostics.py` |
| Change comment handling | `src/compiler/comments.py` |
| Add a new `*draw(...)` geometry command | `src/geometry/commands.py` |
| Change how geometry is rendered to Typst | `src/geometry/codegen.py` |
| Change the self-update flow | `src/compiler/updater.py` + `src/compiler/update.py` |
