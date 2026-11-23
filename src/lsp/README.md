# src/lsp — language server for `.ezmath` files

This package is the **Easy Math Language Server** (`easy-math-lsp`).
It speaks the Language Server Protocol (LSP) over stdin/stdout and gives
any editor (VS Code, Neovim, Vim, …) error checking, autocompletion,
hover info, and document symbols for `.ezmath` files.

It reuses the compiler (`src/compiler/`) — the language server never
re-implements `.ezmath` syntax. The editor's preview also drives the same
compiler modules, so there is exactly one parser.

## What it does

- **Diagnostics:** compiles the document in the background and publishes
  `[Error]`/`[Warning]` markers to the editor's Problems panel.
- **Completion:** suggests variables, defines, commands, and symbols as
  you type.
- **Hover:** shows what a variable or command means when you pause over it.
- **Document symbols:** lists headings, variables, and `*draw` blocks in
  the editor's outline panel.
- **Navigation:** LSP positions (UTF-16 code points) map back to
  `.ezmath` lines and columns; PDF click-back navigates from the PDF to
  the source line.

## Important files

| File | What it does |
|------|--------------|
| `server.py` | `create_server()` builds the pygls `LanguageServer`; wires `did_open`/`did_change`/`did_close`, `completion`, `hover`, `document_symbol`. Main entry: `main()` runs stdio JSON-RPC. |
| `document.py` | `DocumentStore` — holds open documents in memory, maps between editor positions and source offsets. |
| `analysis.py` | `Analysis` — compiles a document via `compiler.pipeline.compile_ezmath` and turns diagnostics into LSP diagnostics; computes completions, hovers, and symbols. |
| `builtins.py` | `KNOWN_GEOMETRY_COMMANDS` and built-in command tables used for completion suggestions. |

## Data flow

```
You type in your editor (.ezmath)
    │
    ▼
LSP client (your editor)        sends didOpen / didChange notifications
    │
    ▼
easy-math-lsp (stdio JSON-RPC)  server.py receives the notification
    │
    ▼
analysis.Analysis               calls compiler.pipeline.compile_ezmath()
                                on the document text
    │
    ▼
compiler (src/compiler/)        parses, calculates, draws — one parser
    │
    ▼
LSP responses                   diagnostics → Problems panel,
                                completions → autocomplete menu,
                                hover → tooltip,
                                symbols → outline panel
```

## I want to change X, which file do I open?

| Change | File |
|--------|------|
| Add a new completion suggestion | `src/lsp/analysis.py` + `src/lsp/builtins.py` |
| Change diagnostic format | `src/compiler/diagnostics.py` (shared with compiler) |
| Add a new LSP capability | `src/lsp/server.py` |
| Change how documents are stored | `src/lsp/document.py` |
