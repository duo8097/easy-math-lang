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
  File "bai1.ezmath", line 12, column 9
    Total = <widht> + 2
            ^^^^^^^
[Warning] Line 30: unknown command *fract — treated as plain text. Did you mean '*frac(...)'?
```

- **Line numbers** count from the top of your `.ezmath` file.
- **[Error]** — something is definitely wrong (typo, bad calculation).
- **[Warning]** — suspicious, but the build carries on.
- Diagnostics print a small context block under their first line:
  the `File "name", line N, column M` header, the real
  `.ezmath` line, and a caret (`^`) under the exact spot. Columns
  count characters, not bytes (Vietnamese text works the same), and
  tabs are expanded. When the column is not known there is no caret —
  you just get the file/line header and the source line. Very long
  lines are truncated around the caret with an ellipsis (`…`). Almost
  every compiler diagnostic shows this block; the few that cannot point
  at a line in your file — CLI-level errors and Typst failures whose
  message carries no mappable position — keep the classic single-line
  output.
- Color is only used on a terminal; when stderr is captured (as in
  the editor) or `NO_COLOR` is set, the output stays plain text.
- Multi-line constructs point at the line where they open: an
  unclosed math delimiter (`\ … \`) or an unterminated `*draw(` block
  is reported at the line with the opening delimiter.
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
| Windows installer: `LSP: Disconnected` | The installed editor and its helpers now ship in one folder; if the `LSP: Disconnected` persists, use **Build → Restart Language Server**. Details: [Desktop editor → helper programs](editor.md#under-the-hood-helper-programs). |
| Arch/Debian package installed but the editor doesn't see the helpers | The packages install to `/usr/bin` + `/usr/lib/easy-math-lang`; if you moved files, set `EASYMATH_LSP_EXE` / `EASYMATH_COMPILER_EXE` to point at them. |
| Windows installer: every `.exe` fails with `Failed to load Python DLL '…\_internal\python312.dll'` | Installs made with the broken v6.0.0/v7.0.0 setup flattened the shared `_internal\` folder into `bin\`. Reinstall with the current Windows installer, or repair the layout by hand — see below. |

### Windows: `Failed to load Python DLL '…\_internal\python312.dll'`

```
Failed to load Python DLL 'C:\Program Files\EasyMathLang\bin\_internal\python312.dll'.
LoadLibrary: The specified module could not be found.
```

Every Easy Math executable on Windows (`easy-math-lang.exe`,
`ezmath.exe`, `easy-math-editor.exe`, `easy-math-lsp.exe`) fails at
startup with this message. The PyInstaller onedir bootloader loads its
runtime from `_internal\` **next to** the executables; the v6.0.0 and
v7.0.0 Windows installers copied the *contents* of `_internal\`
straight into `bin\`, so `bin\_internal\python312.dll` never existed.

Reinstalling with the current Windows installer fixes it. Running the
new setup over an existing (flattened) install is safe: the new
`bin\_internal\` folder is created and the executables are replaced;
leftover flattened files directly in `bin\` are ignored by the
bootloader. If you cannot reinstall right now, repair the layout by
hand:

1. Close Easy Math and any `easy-math-lang` terminals.
2. Open `C:\Program Files\EasyMathLang\bin\` in Explorer (confirm the
   administrator prompt).
3. Create a folder named `_internal` inside `bin\`.
4. Move **everything** in `bin\` into `bin\_internal\` **except the
   four executables** `easy-math-lang.exe`, `easy-math-lsp.exe`,
   `easy-math-editor.exe` and `ezmath.exe`.
5. Start **Easy Math Editor** again — it should open normally.

If you installed to a custom folder, use that install's `bin\`
instead of `C:\Program Files\EasyMathLang\bin\`.

Step-by-step from scratch: [Installation guide](installation.md).

---

## Compiler messages, one by one

### `[Error] Line 7: undefined variable <widht>`

```
[Error] Line 7: undefined variable <widht>
  File "doc.ezmath", line 7, column 9
    Total = <widht> + 2
            ^^^^^^^
```

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

`*table`, `*image` and `*newpage` don't work inside
`\ … \` math mode. Move them outside the backslashes (`*matrix` and
`*vec` *do* work there).

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

### `[GeometryError] *perp(A ; B ; C ; D): constraint conflict or non-convergence — …`

Either your geometry rules contradict each other (e.g. `*distance(A ; B ; 5)`
together with `*distance(A ; B ; 9)`), or the solver did not converge —
the message names the constraints involved. If they truly conflict, reread
the rules and remove the one that can't be true; if the numbers look fine,
the figure may be under-constrained — pin enough points to determine it.

### `[GeometryError] *point(P = midpint(A ; B)): unknown construction '…'`

The right side of a `*point` starts with `name(` but the constructor
name isn't one of the eight (`midpoint`, `foot`, `reflect`, `intersect`,
`centroid`, `circumcenter`, `incenter`, `orthocenter`). Fix the typo —
the message suggests the closest match — or, if you meant to give
coordinates, write them as `*point(P = x, y)`.

### `[GeometryError] … construction cycle: M -> N -> M`

The constructed points depend on each other in a loop, so no position
can ever be computed (`M = midpoint(N ; A)` and
`N = midpoint(M ; B)`). A construction may only depend on *other*
points — break the loop.

### `[GeometryError] *point(P = intersect(…)): … requires k = 1 or 2`

A `line + circle` or `circle + circle` intersection can cross twice,
so you must pick one with `k = 1` or `k = 2` (and only those —
`intersect(line ; line)` crosses once and rejects any k). Add the
argument: `*point(P = intersect(line(A ; B) ; circle(O ; 3) ; 1))`.

### `[GeometryError] … parallel … / no intersection / degenerate line`

`intersect` couldn't find a unique crossing: the lines are parallel or
coincident, a line misses the circle, the circles don't cross, or a
line was built from the same point twice. Check the points you fed the
construction — the message names them.

When geometry fails hard, the build stops with:

```
[ERROR] Build failed: invalid *draw block — output PDF not attempted.
Fix the geometry errors above and retry.
```

### `[ERROR] Typst compilation failed: the *draw geometry package (@preview/cetz:…)`

Easy Math ships the drawing library (CeTZ) **inside** the install, so
`*draw` needs no internet connection — not even on first use. This
message means one of two things:

- **"…this build does not include the bundled package. Check your
  internet connection and rerun once online…"** — your copy is missing
  the bundled CeTZ (an incomplete or very old install). Connect to the
  internet and run once more, or reinstall easy-math-lang.
- **"…the bundled @preview/cetz:… package could not be loaded — the
  installation may be corrupted."** — the bundled files are damaged.
  Reinstall easy-math-lang; if it still fails, report it with the full
  error line.

The bundled files live in `_internal/typst-packages/` (Linux:
`/usr/lib/easy-math-lang/_internal/typst-packages`; Windows:
`{app}\bin\_internal\typst-packages`; macOS: inside the app under
`Contents/Frameworks/typst-packages`). Running from source, they live
in `vendor/typst-packages/` — if you deleted them, restore with
`uv run --frozen python scripts/vendor_typst_packages.py` (needs a
one-time network connection).

### `[Plot Error: …]`, `[Image Error: …]`

These appear **in the PDF** (and on the terminal) instead of the
diagram/image. The rest of the document still builds:

- **Plot** — usually no finite values in the range (e.g.
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
