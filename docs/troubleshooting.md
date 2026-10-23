# Troubleshooting and FAQ

Something not working? This page lists the messages easy-math-lang
prints, what causes them, and how to fix them — plus answers to the
most common questions.

New to the terminology? The [Glossary](glossary.md) explains every word
in plain language.

---

## First: how to read a message

During a build you may see lines like this:

```
[Error] Line 12: undefined variable <widht>
[Warning] Line 30: unknown command *fract — treated as plain text. Did you mean '*frac(...)'?
```

- **Line numbers** count from the top of your `.ezmath` file.
- **[Error]** — something is definitely wrong (typo, bad calculation).
- **[Warning]** — suspicious, but the build carries on.
- By default the PDF is **still written** even with errors; the last
  line tells you honestly how many there were:

  ```
  Compiled doc.ezmath to doc.pdf with 2 error(s), 1 warning(s)
  ```

  Use `--strict` if you want a non-zero exit code instead (useful in
  automated builds): `easy-math-lang --strict doc.ezmath`.
- Some messages (`[Calc Error: …]`, `[Image Error: …]`) appear **inside
  the PDF** at the exact spot the problem occurred.

---

## Installation and setup

| Problem | Fix |
|---|---|
| `uv: command not found` | Close the terminal completely and open a new one (uv was just installed and needs a fresh terminal). |
| `Python not found` during setup | Re-run the Python installer and make sure **"Add Python to PATH"** is ticked. |
| `easy-math-lang: command not found` | You skipped `uv sync`, or you're not in the project folder. From source, always run `uv run easy-math-lang …`. |
| macOS blocks the app on first launch | Right-click the app → **Open** → **Open** again (the app is ad-hoc signed, not notarized). See [Installation → macOS](installation.md#option-a2--macos-disk-image-easiest). |
| Windows installer: `LSP: Disconnected` | Keep the installed `editor/` and `bin/` folders together, then **Build → Restart Language Server**. Details: [Desktop editor → helper programs](editor.md#under-the-hood-helper-programs). |
| Arch/Debian package installed but the editor doesn't see the helpers | The packages install to `/usr/bin` + `/usr/lib/easy-math-lang`; if you moved files, set `EASYMATH_LSP_EXE` / `EASYMATH_COMPILER_EXE` to point at them. |

Step-by-step from scratch: [Installation guide](installation.md).

---

## Compiler messages, one by one

### `[Error] Line 7: undefined variable <widht>`

You used `<widht>` but never defined it — almost always a typo
(`<width>` was defined somewhere else), or you used it **before**
defining it. Variables must be defined earlier in the file than where
you use them.

In the PDF this spot shows `[UNDEFINED: <widht>]`.

### `[Warning] … unknown command *fract — treated as plain text.`

`*fract` is not a command. The message usually ends with
`Did you mean '*frac(...)'?` — follow the hint, or check
[Cheat sheet](cheatsheet.md) / [Writing math](algebra.md).

### `[Warning] … *point is only valid inside *draw(...)`

Geometry commands only work between `*draw(` and `)`. Wrap them:

```
*draw(
    *point(A = 0, 0)
    *triangle(A ; B ; C)
)
```

### `[Error] Line 4: calc(): division by zero in: 'x / y'`

Your `calc(...)` divided by a zero value. Check the variable used as
the divisor — it may be `0` or not yet assigned.

### `[Error] Line 4: calc(): invalid syntax …`

Something `calc()` doesn't understand. The usual suspects:

- **Decimal comma**: `calc(3,5)` → write `calc(3.5)`. A comma never
  means a decimal point inside `calc`.
- **Missing multiplication sign**: `calc(2x)` → write `calc(2 * x)`.
- **Unknown name**: `calc(x)` outside `*plot` — `calc` only knows
  numbers, your `<variables>`, `pi`, `e`, and functions like
  `sqrt`/`sin`.

### `[Warning] … unclosed *frac(... — missing closing parenthesis`

A command opened `(` that is never closed. Add the missing `)`.

### `[Warning] … expects 2 argument(s), got 1 — leaving as-is`

The command needs more arguments than you gave it. Example:
`*frac(2)` needs both parts — `*frac(2 ; 3)`.

### `[Warning] Line 9: *table(...) is text mode and cannot be used inside math \ ... \`

`*table`, `*vec`, `*image` and `*newpage` don't work inside
`\ … \` math mode. Move them outside the backslashes (`*matrix` *does*
work there).

### `[Error] Line 9: unclosed math delimiter \ ... \ — missing closing \.`

You opened math mode with `\` but never closed it. Add the second `\`:

```
The solution is \ x = 2 \.
```

### `[Warning] … unclosed or malformed *draw(...)`

A `*draw(` block was started but the closing `)` is missing or sits
outside the block. When this happens the build stops entirely:

```
[ERROR] Build failed: unclosed block — output PDF not attempted.
Add the missing ')' and retry.
```

Count your parentheses — each `*draw(` needs exactly one `)`.

### `[GeometryError] *perp(A ; B ; C ; D): constraint conflict — …`

Your geometry rules contradict each other (e.g. `*distance(A ; B ; 5)`
together with `*distance(A ; B ; 9)`). Reread the rules and remove the
one that can't be true — the message names the constraints involved.

When geometry fails hard, the build stops with:

```
[ERROR] Build failed: invalid *draw block — output PDF not attempted.
Fix the geometry errors above and retry.
```

### `[Plot Error: …]`, `[Vec Error: …]`, `[Image Error: …]`

These appear **in the PDF** (and on the terminal) instead of the
diagram/image. The rest of the document still builds:

- **Plot/Vec** — usually no finite values in the range (e.g.
  `*plot(sqrt(x); -10; -1)` — sqrt of a negative number) or wrong
  number of arguments. Check the expression and its interval.
- **Image** — the file wasn't found (paths are relative to your
  `.ezmath` file's folder) or the width is invalid.

### Nothing special — the output looks wrong

Warnings don't stop the build, so it's easy to miss one. Scroll up in
the terminal: every `[Warning]`/`[Error]` line is listed **above** the
final `Compiled …` summary. In the editor, the **Problems** panel
(click the problem count in the status bar) shows them all, and you can
click a row to jump to the line.

---

## Questions about the output

**Where is my PDF?**
Right next to your `.ezmath` file (same folder). The editor's status
bar shows the exact path after compiling.

**Where did `doc.typ`, `doc.smap.json`, or the `*-plot-*.svg` files go?**
They are build intermediates, deleted after a successful build. Pass
`--save-build-artifacts` to keep them — useful when you need to debug
or inspect the generated Typst source. Failed builds always keep them.

**Only part of the document printed — where are the variables?**
Variables print where you wrote them, but only after they are defined.
A `<name>` used before its definition shows as `[UNDEFINED: <name>]`.

**Why does `2 * 3` show as `2 . 3`?**
Your document sets `*define(write_type.multiplication = .)`. Remove
that line (or change `.` to `x`, `·`, …) — see
[The multiplication dot](algebra.md#the-multiplication-dot).

**Why did I get `doc-1.png`, `doc-2.png`?**
PNG and SVG exports are one file per page. Include `{p}` in the name to
choose the pattern yourself: `easy-math-lang doc.ezmath out-{p}.png`.
See [Export](export.md#multi-page-images).

**The PDF is still written — how do I make errors fail the build?**
Use `--strict`. Without it, a build with errors exits 0 on purpose
(backward compatibility) but reports the counts honestly.

---

## The desktop editor

| Problem | Fix |
|---|---|
| `LSP: Disconnected` in the status bar | **Build → Restart Language Server**. Still stuck? See [editor helper programs](editor.md#under-the-hood-helper-programs). |
| Preview doesn't update | Make sure the **Auto** checkbox in the preview panel is ticked, or press **F5**. |
| Preview shows an error | The panel keeps the compiler log and the last good page — read the log, fix the line, it refreshes by itself. |
| Autocomplete never appears | It pops up automatically after `*` or `<`; press **Ctrl+Space** anywhere. |
| Everything looks odd / old settings | Delete `~/.config/ezmath/config.ini` to reset to defaults. |

Full tour: [Desktop editor](editor.md).

---

## The language server (in VS Code, Neovim, …)

- The server must be started by your editor — typing into its window
  won't do anything (it talks JSON-RPC over stdin/stdout).
- Logs go to **stderr**; if something writes to stdout, the editor
  disconnects.
- Make sure the file extension is `.ezmath` (or `.eml`) and that
  `uv sync` has been run.

Details: [Language server → Troubleshooting](lsp.md#troubleshooting).

---

## Still stuck?

1. Re-run with `--save-build-artifacts` and open the generated
   `doc.typ` — it shows exactly what was sent to the typesetter.
2. Check the version you have: `easy-math-lang --version` (or
   `uv run easy-math-lang --version`).
3. Ask for help on the project's
   [GitHub Issues](https://github.com/duo8097/easy-math-lang/issues)
   and include your `.ezmath` file plus the full message text — that is
   usually enough to solve it in one round trip.

---

## See also

- [Cheat sheet](cheatsheet.md) — one-page quick reference
- [Writing math](algebra.md) — every command explained
- [Drawing geometry](geometry.md) — figures and constraints
- [Glossary](glossary.md) — plain-language definitions
