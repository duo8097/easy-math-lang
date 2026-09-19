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

## Making text comfortable to read

- `View → Zoom In` (**Ctrl+=**), `Zoom Out` (**Ctrl+-**),
  `Reset Zoom` (**Ctrl+0**). Sizes stay between 6 and 48 pt.
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
- The **Outline** (left) and **Problems** (bottom) panels can be hidden
  from `View` or by closing them; reopen them from the same menu.
- The **status bar** shows cursor position, problem count, and language
  server status.

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
| Toggle Outline / Problems, Zoom | View | Ctrl+=, Ctrl+-, Ctrl+0 |
| Compile to PDF | Build | Ctrl+B |
| Restart Language Server | Build | — |
| Autocompletion | — (in editor) | auto after `*`/`<`, or Ctrl+Space |

Supported files end in `.ezmath` or `.eml`.
