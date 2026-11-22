# src/editor — desktop editor (PySide6 + LSP client)

This package is the **Easy Math Editor** — a graphical desktop app for
`.ezmath` files. It is built with PySide6 (Qt) and talks to the language
server (`easy-math-lsp`) over stdin/stdout for error checking and
autocompletion.

## What it does

- **Edit** `.ezmath` files with syntax highlighting, line numbers, and
  a symbol bar for inserting math commands and symbols.
- **Build** (Ctrl+B) runs `easy-math-lang` out-of-process and shows
  errors in the Problems panel.
- **Live preview** compiles in the background on a worker thread and
  shows the PDF as you type; Ctrl+Click navigates from the PDF back to
  the source line.
- **Export As…** saves PDF, PNG, SVG, HTML, or Typst source.
- **Settings** — language (English/Vietnamese), font, theme, update
  checks, and helper program paths.
- **Welcome panel, help dialogs, command palette, find bar, recent
  files** — the usual desktop-app conveniences.

Qt-free submodules (`positions`, `protocol`, `paths`, `symbol_registry`)
stay importable without PySide6 so compiler/geometry/LSP tests run on
machines without Qt. Qt-dependent names (`MainWindow`, `EditorWidget`,
`LspClient`, `main`) are imported lazily.

## Important files

| File | What it does |
|------|--------------|
| `app.py` | `main()` — creates the `QApplication`, sets fonts/icons, parses args (`--no-save-prompt`, optional file to open). Entry point: `easy-math-editor`. |
| `main_window.py` | `MainWindow` — the whole window: menus, docks (Problems, Outline, Preview), file operations (new/open/save), build (Ctrl+B), Export As…, live preview wiring, theme, font, settings. |
| `editor_widget.py` | `EditorWidget` — the text editing area: syntax highlighting, line numbers, cursor position, word under cursor. |
| `preview_panel.py` | `PreviewPanel` — shows the compiled PDF page; debounced reload on text change; click-back via source map. |
| `problems_panel.py` | `ProblemsPanel` — lists `[Error]`/`[Warning]` diagnostics from the LSP. |
| `outline_panel.py` | `OutlinePanel` — document symbols (headings, variables, draw blocks). |
| `lsp_client.py` | `LspClient` — out-of-process LSP client (start/restart, didOpen/didChange, completion, hover, symbols). |
| `symbol_bar.py` / `symbol_dialog.py` | Symbol bar and palette for inserting math commands and symbols. |
| `symbol_registry.py` | Symbol data: names, descriptions, insertion text, categories. |
| `update_ui.py` | Update check UI: banner, dialog, progress, download verification. |
| `paths.py` | Locates helper binaries (`easy-math-lang`, `easy-math-lsp`) in every install type (installer, from source, frozen). |
| `config.py` | User settings (`~/.config/ezmath/config.ini`): language, font, theme, auto-update, … |
| `i18n.py` | Translation loading: English (default) and Vietnamese catalogs. |
| `linux_ime.py` | fcitx5 input-method setup for Vietnamese typing on Linux. |
| `help_dialogs.py` | Welcome panel, About dialog, shortcuts dialog, built-in examples. |
| `draw_catalog.py` / `draw_gallery.py` | Built-in `*draw` examples shown in the editor. |
| `theme.py` | Light/dark theme switching. |

## Data flow

```
You edit in EditorWidget
    │
    ├─ Build (Ctrl+B) ────→ QProcess runs easy-math-lang out-of-process
    │                        → Problems panel shows [Error]/[Warning]
    │
    ├─ Live preview ─────→ _PreviewWorker (QThread) calls
    │                       compiler.pipeline.compile_source_to_pdf()
    │                       → PreviewPanel shows the PDF page
    │                       → source-map click-back: PDF → source line
    │
    └─ Typing ──────────→ LspClient sends didChange to easy-math-lsp
                            → analysis.Analysis compiles via compiler
                            → diagnostics → Problems panel
                            → completions → autocomplete menu
                            → symbols → Outline panel
```

Settings live in `~/.config/ezmath/config.ini` (language, font, theme,
auto-check for updates, helper paths).

## I want to change X, which file do I open?

| Change | File |
|--------|------|
| Add a menu item or toolbar button | `src/editor/main_window.py` |
| Change the editing area (highlighting, line numbers) | `src/editor/editor_widget.py` |
| Change the preview panel | `src/editor/preview_panel.py` |
| Change how the LSP client talks to the server | `src/editor/lsp_client.py` |
| Add a new setting | `src/editor/config.py` + `main_window.py` settings UI |
| Change update-check UI | `src/editor/update_ui.py` |
| Change symbol data / categories | `src/editor/symbol_registry.py` |
| Locate helper binaries differently | `src/editor/paths.py` |
