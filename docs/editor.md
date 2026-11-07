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

## The `*draw` geometry gallery

- The **`*draw`** button on the Symbol Bar (or `View → Geometry
  Gallery…`, **Ctrl+Shift+G`, or the command palette entry
  `Draw: Geometry Gallery…`) opens a **non-modal** window that lists
  every geometry command **and point construction** (28 cards) — a
  thumbnail of what it draws, its syntax,
  and a one-line description. The editor stays usable behind it, and a
  second click just re-raises the same window.
- **Search** (by command, title or description) and the **group**
  dropdown (Shapes / Angles / Constraints / Constructions /
  Measure & Label) narrow
  the list. The **Constructions** cards insert a computed point —
  `*point(M = midpoint(A ; B))` — instead of a command of their own.
- Each card offers two actions:
  - **Insert example…** — opens the **template window** for that
    command: a large preview of the figure on the left with the
    complete, validated `*draw(...)` block **underneath — editable**,
    so what you insert is exactly what you see. On the right a
    **command palette** lists **all** geometry commands (one row per
    command — point constructions come through the `*point` row) — the ones
    already used in the code are pinned to the top in **bold** and
    stay there while the list fuzzy-filters as you type (every
    geometry command has a parameter dialog, so no row is greyed
    out). Picking one (double-
    click or **Enter**) opens its usual parameter dialog and the
    built command lands in the *code area* (before the closing `)`),
    never in the document — Enter runs *only* the pick, never the
    insert. **Insert** commits the code at the cursor — inside an
    existing block it is appended before the closing `)` (single-line
    blocks are expanded first), anywhere else it becomes its own
    block, always **one undo step** — and closes the window; it
    stays greyed out while the code could not be inserted (e.g. an
    unterminated `*draw(` block), so edits are never silently lost.
    **Cancel** (or Esc) closes without touching the document, and
    re-clicking the same card keeps your in-progress edits (another
    card reloads its example).
  - **Insert command…** — opens the usual parameter dialog for that
    command (every geometry command has one).
- **Insert empty block** puts the old bare `*draw(...)` skeleton at
  the cursor, so the previous `*draw` button behavior is still one
  click away.
- Thumbnails are pre-rendered SVGs shipped with the editor (no
  network, no compile while browsing); a missing file simply shows a
  neutral placeholder tile.

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

## Exporting (PDF, images, HTML, Typst)

- `File → Export As…` saves the current document (saved or untitled, no
  save needed) as **PDF** (`.pdf`), **PNG** (`.png`, prompts for DPI),
  **SVG** (`.svg`), **HTML** (`.html`) or **Typst source** (`.typ`).
  Multi-page PNG/SVG writes `stem-1.ext`, `stem-2.ext`, … next to your
  chosen file. The same formats work from the terminal —
  see [Export](export.md).
  For saved documents, relative `*image(...)` paths resolve from the
  document's folder in both preview and export. Typst/HTML exports carry
  diagram SVGs and a `<stem>-images/` folder for embedded image assets;
  keep those assets beside the exported document when moving it.
- `Build → Compile` (**Ctrl+B**) still writes a PDF next to your file
  (saved documents only).

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
2. Next to the editor itself — the installer's `bin/` folder (which also
   holds the editor executable and the shared `_internal/` library
   directory), or the `Scripts/` folder of your Python environment when
   running from source.
3. Anywhere on your `PATH`.
4. Only when running from source: the current Python (`python -m lsp` /
   `python -m compiler`).

That means the installed app works even when `bin/` was **not** added to
`PATH` during setup — the editor and its helpers always ship together
now, sharing one library directory.

---

## Making text comfortable to read

- `View → Zoom In` (**Ctrl+=**), `Zoom Out` (**Ctrl+-**),
  `Reset Zoom` (**Ctrl+0**). Sizes stay between 6 and 48 pt.
- `View → Dark Mode` (**Ctrl+Shift+D**): switches the whole editor —
  chrome, editor background, line numbers, syntax colors, and find
  highlights — between light and dark. Your choice is remembered
  between launches.
- `View → Auto-close Brackets` (**Ctrl+Shift+B**): when enabled,
  typing an opening bracket or quote auto-inserts its closer.
  Pairs are `( )`, `[ ]`, `{ }` and `""` — `<`, `$`, backtick and `'`
  are deliberately not paired. Insertion happens only when the next
  character is end of line, whitespace, or a closer; before a word
  character only the opener is inserted. For `"`, no pairing occurs
  when the previous character is a word character (so `5"` in prose is
  left alone). With a selection, the opener wraps the selection
  (`(selection)`) and keeps it selected. Typing a matching closer
  overtypes it instead of inserting a duplicate; Backspace between
  an empty pair deletes both characters; Enter between an empty pair
  expands it to three lines with proper indentation. Each auto-pair
  action is a single undo step. IME composition (Vietnamese Telex/VNI,
  fcitx5/ibus, CJK IMEs) is never disturbed, and programmatic edits
  (paste, completion insertion, LSP changes) never auto-pair. The
  setting is persisted in `~/.config/ezmath/config.ini` under
  `editor/autoCloseBrackets` (default on).
- The editor uses a monospace font with line numbers, a highlighted
  current line, and 4-space tab stops.
- `View → Editor Font…`: pick the editor font family and size
  (monospace recommended). Your choice is remembered between launches.
  Zooming stays temporary; `Reset Zoom` returns to your chosen size.

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
| Geometry Gallery (`*draw`) | View | Ctrl+Shift+G |
| Toggle Outline / Problems / Preview, Zoom, Dark Mode | View | Ctrl+=, Ctrl+-, Ctrl+0, Ctrl+Shift+V, Ctrl+Shift+D |
| Auto-close brackets toggle | View | Ctrl+Shift+B |
| Compile to PDF | Build | Ctrl+B |
| Refresh Preview | Build | F5 |
| Restart Language Server | Build | — |
| Autocompletion | — (in editor) | auto after `*`/`<`, or Ctrl+Space |

Supported files end in `.ezmath` or `.eml`.

---

## Linux: input methods (Vietnamese etc.)

The desktop editor supports fcitx5 input methods on Linux — for example Vietnamese Telex via `fcitx5-lotus`, and other CJK IMEs. The short version:

- **ibus users: nothing to install or configure** — ibus works out of the box as long as the ibus daemon is running (PySide6's bundled Qt ships the ibus plugin).
- **fcitx5 works out of the box in the `.deb`/`.rpm` installers** — the frozen Linux builds bundle a plugin compiled from source in CI against exactly PySide6's Qt, so no system Qt matters.
- **From source (`uv run easy-math-editor`) fcitx5 needs a matching system plugin** — install your distro's Qt6 plugin and it will be used automatically, but only when its Qt major.minor matches PySide6's (currently **Qt 6.12**, PySide6 6.12.0 in `uv.lock`). Otherwise use ibus, or a PySide6 built against your system Qt.
- The editor **never touches your input-method configuration unless fcitx is evidently in use**, and a mismatch or failure never blocks the editor — worst case, fcitx5 input is unavailable.

### What PySide6 ships

PySide6 from PyPI bundles its own Qt. Its `platforminputcontexts` directory contains only the **ibus** and **compose** plugins — no fcitx5 plugin. The fcitx5 Qt6 platform input context plugin (`libfcitx5platforminputcontextplugin.so`) must come from elsewhere, and it only loads if it was built against the same Qt major.minor as PySide6's Qt.

### What the editor does automatically (Linux only)

At startup, before the Qt application is created, the editor:

1. **Activates only when fcitx is evidently your IM framework** — at least one of: `QT_IM_MODULE=fcitx|fcitx5`, `XMODIFIERS` containing `@im=fcitx`, or `GTK_IM_MODULE=fcitx|fcitx5`. If none match (e.g. ibus or unset), the editor does nothing at all — no environment variables are changed.
2. **Picks the plugin**, in order:
   - Frozen builds: the plugin **bundled by CI** (built against exactly PySide6's Qt — trusted, no version check required).
   - Otherwise: the **system plugin**, found in `$QT_PLUGIN_PATH` or the standard system Qt6 plugin directories, and only used when the **system Qt major.minor matches PySide6's** (system Qt detected via `qmake6 -query QT_VERSION`, then `qtpaths6`; if it can't be determined, it proceeds with a warning).
3. **Wires it up**: symlinks the plugin into `~/.cache/easy-math-lang/qt-plugins/platforminputcontexts/` (honoring `$XDG_CACHE_HOME`; refreshed when the system plugin changes, copy fallback), prepends that directory's parent to `QT_PLUGIN_PATH` — keeping your own entries — and defaults `QT_IM_MODULE` to `fcitx` via `os.environ.setdefault` (your own setting always wins). `QT_QPA_PLATFORM` is never touched.

On a version mismatch the fix is skipped with one clear stderr warning (mentioning IBus and a matching PySide6 as alternatives). The editor always starts; ibus users see zero difference.

### Which package provides the fcitx5 plugin?

Verified: **Arch Linux** → `fcitx5-qt` (owns `/usr/lib/qt6/plugins/platforminputcontexts/libfcitx5platforminputcontextplugin.so`; also what the Arch package bundles when Qt matches). **Debian/Ubuntu** → `fcitx5-frontend-qt6` (e.g. noble ships 5.1.4 against Qt 6.4.2 — see the mismatch note above; the `.deb` installer needs no system package). **Fedora and others**: check your distro — package names and Qt versions vary; the version match below applies regardless.

### Version mismatch (from source)

PySide6 currently bundles **Qt 6.12** (`pyside6 6.12.0` in `uv.lock`). If your system Qt is not 6.12.x (Ubuntu 24.04: 6.4.2), the system plugin cannot load; the editor warns once on stderr and leaves ibus/everything else alone. Your options:

- use **ibus** (`QT_IM_MODULE=ibus`, ibus-daemon running) — works out of the box;
- run the **installers** (`.deb`/`.rpm`) — they carry a plugin built for Qt 6.12;
- install/build a PySide6 against your system Qt 6 and set `EZMATH_NO_IME_FIX` concerns aside; or
- install a newer system Qt whose 6.x matches PySide6's and the matching fcitx5 plugin.

### Opt-out

```bash
EZMATH_NO_IME_FIX=1 easy-math-editor
```

disables the whole fix (no lookups, no environment changes, no warnings). Other `QT_IM_MODULE` values (e.g. `ibus`) likewise leave you untouched.

### Debugging

- `QT_DEBUG_PLUGINS=1 easy-math-editor` — Qt logs every plugin probe; look for `libfcitx5platforminputcontextplugin.so` and a `loaded library` line.
- Check stderr for the one-line warning; it names both Qt versions on a mismatch.
- Verify the versions yourself: `qmake6 -query QT_VERSION` vs `uv run python -c "from PySide6.QtCore import qVersion; print(qVersion())"`.
- Integration tests: `uv run pytest tests/test_linux_ime_integration.py -v` (headless; passes via the real plugin load, or skips with the reason when nothing matches).

### XWayland vs Wayland

Qt apps on Wayland use the `wayland` platform via XWayland if unset. fcitx5 works best with a native Wayland session (`QT_QPA_PLATFORM=wayland`); under XWayland the X11 input-method path applies. If the candidate window misbehaves, try `QT_QPA_PLATFORM=xcb` (X11/XWayland) or confirm your fcitx5 version supports Qt6 Wayland text-input. The editor does not set any of these itself.

### Maintainers: bumping the pinned fcitx5-qt ref / a new PySide6 Qt

The CI-built plugin is pinned in `scripts/fcitx5_qt_ref.txt` (currently `5.1.16`) and cached by `Qt version + ref + runner image` (actions/cache). To bump it: edit that one line; CI rebuilds the plugin from the new tag.

When PySide6 moves to a new Qt minor (e.g. Qt 6.13):

1. Ensure aqtinstall hosts the matching SDK (`aqt list-qt linux desktop --spec "6.13"`) — the build-linux job installs exactly `qVersion()` and verifies it;
2. confirm the aqtinstall archives `qtbase`, `qtwayland`, `icu` still carry the private cmake configs (`Qt6GuiPrivate`, `Qt6WaylandClientPrivate`, `Qt6WaylandGlobalPrivate`);
3. bump `scripts/fcitx5_qt_ref.txt` if a newer fcitx5-qt is needed; CI rebuilds and the `libfcitx5platforminputcontextplugin.so` basename check + bundle assertion catch layout regressions;
4. run `uv run pytest tests/test_linux_ime_integration.py -v` and `QT_DEBUG_PLUGINS=1` once to confirm the plugin loads; the version guard (`major.minor`) is deliberate — patch-level Qt differences are fine.

### glibc floor of the Linux installers

The `.deb`/`.rpm` (and Arch package) are built on **Ubuntu 24.04 (glibc 2.39)** — that is the minimum glibc for the Linux installers. PySide6 6.12 requires manylinux_2_34 (x86_64) / manylinux_2_39 (aarch64) regardless.

---

## See also

- [Troubleshooting and FAQ](troubleshooting.md) — `LSP: Disconnected`, preview issues, resets
- [Cheat sheet](cheatsheet.md) — what to type in the editor
- [Language server](lsp.md) — details of the error checking
