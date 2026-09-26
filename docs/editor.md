# Desktop editor

The project ships with a small desktop editor for `.ezmath` files.
Launch it from the project folder:

```
uv run easy-math-editor [options] [optional-file.ezmath]
```

Options:

| Flag | Effect |
|---|---|
| `--no-save-prompt` | Close without asking to save (unsaved changes are discarded; useful for automated tests) |

You can also install the `easy-math-editor` command with your Python
environment — it is declared in `pyproject.toml`.

---

## First steps

- A new document shows a short example to get you started.
  Delete it and type your own math, or open an example instead:
  `File → Open → examples/example.ezmath`.
- Press **Ctrl+B** (or `Build → Compile`) to turn the document into a PDF.
  The status bar tells you where the PDF was written.
- If a document has unsaved changes, the window title shows a `*`
  and you will be asked before closing.

---

## Getting help from the editor

- **Command palette** (**Ctrl+Shift+P**, or `View → Command Palette…`):
  type a few letters of any command — fuzzy matching finds it, Enter runs it.
- **Problems panel** (bottom): error and warning messages for the current
  document. Click a row to jump to that line. Clicking the problem count in
  the status bar brings the panel back.
- **Outline panel** (left): variables, defines, and `*draw` blocks.
  Click a row to jump to it. Hide either panel from `View`.
- **Autocompletion**: suggestions pop up automatically right after you
  type `*` or `<`; **Ctrl+Space** works anywhere too. While browsing,
  the status bar shows what each candidate needs (e.g.
  `*frac(numerator ; denominator)`). Picking a function inserts empty
  `()` with the cursor inside, ready for arguments.
- **Hover**: rest the mouse pointer on a name to see its value or meaning.
- **Status bar**: cursor position (`Ln`/`Col`), problem count, and whether
  the language server is connected.

All of this comes from the built-in language server — see
[Language server](lsp.md). If the status bar says `LSP: Disconnected`,
use `Build → Restart Language Server`.

---

## Live preview

- `View → Live Preview` (**Ctrl+Shift+V**) opens a PDF preview dock on the
  right. It recompiles automatically (~0.8 s after you stop typing) in a
  background thread, so typing never stutters.
- `Build → Refresh Preview` (**F5**, or the ⟳ button in the panel) renders
  immediately. The `Auto` checkbox pauses automatic updates; `Fit` / `+` /
  `−` control zoom and `Open…` opens the preview PDF externally.
- The preview uses the same compiler as `Build → Compile`, so variables,
  `calc()`, and `*draw` geometry all match the final PDF — including
  untitled documents (no save needed). Failures show the compiler log in
  the panel instead of a popup, and the last good page stays visible.

---

## Under the hood: helper programs

The live preview compiles in-process, so it needs no helper. Full
`Build → Compile` still uses the `easy-math-lang` program below.

The editor needs two helper programs to work fully:

| Program | Used for |
|---|---|
| `easy-math-lsp` | Error checking, completion, hover, outline (everything above) |
| `easy-math-lang` | `Build → Compile` (Ctrl+B) turning your document into a PDF |

You never have to configure them. On startup the editor looks for each
program in this order:

1. The `EASYMATH_LSP_EXE` / `EASYMATH_COMPILER_EXE` environment variable,
   if you set one.
2. Next to the editor itself — the installer's `bin/` folder, or the
   `Scripts/` folder of your Python environment when running from source.
3. Anywhere on your `PATH`.
4. Only when running from source: the current Python (`python -m lsp` /
   `python -m compiler`).

That means the installed app works even when `bin/` was **not** added to
`PATH` during setup — just keep the installed `editor/` and `bin/`
folders together.

---

## Making text comfortable to read

- `View → Zoom In` (**Ctrl+=**), `Zoom Out` (**Ctrl+-**),
  `Reset Zoom` (**Ctrl+0**). Sizes stay between 6 and 48 pt.
- `View → Dark Mode` (**Ctrl+Shift+D**): switches the whole editor —
  chrome, editor background, line numbers, syntax colors, and find
  highlights — between light and dark. Your choice is remembered
  between launches.
- The editor uses a monospace font with line numbers, a highlighted
  current line, and 4-space tab stops.

---

## Finding your way around

- **Find** (**Ctrl+F**, `Edit → Find…`): type to jump through matches
  (`Enter`/`F3` next, `Shift+F3` previous, `Esc` closes). The bar opens
  with your selected word already filled in.
- **Go to Line** (**Ctrl+G**): jump straight to a line number.
- **Open Recent** (`File → Open Recent`): your last files, most recent
  first. Missing files are hidden automatically.

## Layout

- The **toolbar** holds New, Open, Save, and Compile for one-click access.
- The **Outline** (left), **Problems** (bottom), and **Preview** (right)
  panels can be hidden from `View` or by closing them; reopen them from
  the same menu.
- The **status bar** shows cursor position, problem count, and language
  server status.

## Settings file

Your preferences (recent files, dark/light mode) live in one plain INI
file: `~/.config/ezmath/config.ini`. Delete it to reset the editor to
defaults; settings from older versions are migrated there automatically
on first launch.

---

## Files and shortcuts

| Action | Menu | Shortcut |
|---|---|---|
| New / Open / Save / Save As | File | Ctrl+N / Ctrl+O / Ctrl+S |
| Open Recent | File | — |
| Undo / Redo / Cut / Copy / Paste / Select All | Edit | standard shortcuts |
| Find in File | Edit | Ctrl+F, F3 / Shift+F3, Esc |
| Go to Line | Edit | Ctrl+G |
| Command Palette | View | Ctrl+Shift+P |
| Toggle Outline / Problems / Preview, Zoom, Dark Mode | View | Ctrl+=, Ctrl+-, Ctrl+0, Ctrl+Shift+V, Ctrl+Shift+D |
| Compile to PDF | Build | Ctrl+B |
| Refresh Preview | Build | F5 |
| Restart Language Server | Build | — |
| Autocompletion | — (in editor) | auto after `*`/`<`, or Ctrl+Space |

Supported files end in `.ezmath` or `.eml`.
