# Glossary

Plain-language meanings of the words used in these guides — no
programming background assumed.

> Reading a message from the compiler? Jump to
> [Troubleshooting and FAQ](troubleshooting.md).

---

## For writing documents

**`.ezmath` file**
The plain-text file where you write your document. Any text editor works
(Notepad, TextEdit, VS Code, or the built-in
[desktop editor](editor.md)).

**Argument**
A value you pass to a command, inside its parentheses. In
`*frac(2 ; 3)` the arguments are `2` and `3`. Arguments are separated
by `;` — or by `,` if you prefer.

**Calc** — short for *calculation*. The `calc(...)` wrapper makes the
compiler do arithmetic for you: `calc(2 + 3)` becomes `5`. Without it,
text is printed exactly as you wrote it.

**Comment**
A note for yourself that never appears in the PDF. Start it with `//`.

**Define** — `*define(name = value)`. A name that stands for a value.
The name is printed exactly as written — it is not calculated. See
[Variables vs defines](algebra.md#variables--storing-calculated-values).

**Variable** — `<name> = value`. Like a define, but it can be
calculated (`<area> = calc(<width> * <height>)`) and its value updates
everywhere you use `<name>`.

**Silent block** — `*( ... )` around variable definitions so they are
computed but not printed in the PDF.

**Math mode** — an expression wrapped in backslashes, like `\ x = 2 \`.
Inside it you get proper math typography (fancy fonts, automatic
spacing) without needing LaTeX.

**Symbol shortcut** — a short text spelling that becomes a symbol in
the PDF, like `<=` → ≤ or `*alpha` → α.

**Separator** — the character between arguments (`;` or `,`) and rows
(`|`). When `;` is present it wins, so `100,000` stays one number.

---

## For the output

**PDF** — the finished, printable document the compiler produces.

**PNG / SVG** — image formats you can export instead of PDF. PNG is a
picture made of pixels (good for slides); SVG is vector (stays sharp at
any size). Multi-page documents produce one file per page.

**HTML** — a web-page version of your document.

**Typst** — the typesetting engine that turns text into a beautiful PDF.
easy-math-lang writes a small Typst file for you behind the scenes and
hands it over — you never need to learn Typst. (It is installed
automatically; see [Installation](installation.md).)

**PPI (DPI)** — pixels per inch; the sharpness of an exported PNG.
Higher = sharper and bigger. `--ppi 300` is print quality.

**Intermediate files** — the temporary `.typ` file, source map
(`.smap.json`), and `*-plot-*.svg` diagrams created
during a build. They are deleted after a successful build; pass
`--save-build-artifacts` to keep them for debugging.

**Source map** — a record of where each generated line came from in
your `.ezmath` file, so errors and editor links can point back to the
right line.

---

## For the tools

**Terminal / command prompt**
The window where you type commands instead of clicking buttons. Also
called "Console", "PowerShell", or "Shell".

**CLI** — *command-line interface*; running `easy-math-lang` from the
terminal (as opposed to clicking in the [editor](editor.md)).

**uv** — the tool that installs Python packages for this project. You
only need `uv sync` once, then `uv run ...` to run things. See
[Installation](installation.md).

**Compiler** — the program that reads your `.ezmath` file and produces
the PDF (`easy-math-lang`).

**LSP / language server** — `easy-math-lsp`, a helper that gives your
editor autocompletion, hover info, and live error checking for
`.ezmath` files. See [Language server](lsp.md).

**Diagnostic** — a message the compiler prints about your document.
Two kinds: **[Error]** (something is wrong, e.g. an undefined variable)
and **[Warning]** (suspicious but the build continues). Messages often
appear *inside* the PDF too, exactly where the problem is.

**Strict mode** — the `--strict` flag: instead of writing the PDF and
exiting with code 0, the compiler exits non-zero when there were
errors — useful in automated builds (CI) so typos fail loudly.

**Exit code** — the number a program returns after running: `0` means
success, anything else means something went wrong (scripts and CI read
this).

---

## For developers

**Pipeline** — the ordered steps the compiler runs on your file
(strip comments → resolve variables → expand commands → escape →
generate Typst). See [Architecture](architecture.md).

**Constraint solver** — the geometry engine. You state rules ("AC = 3",
"AB ⊥ AC") and it computes where each point must go.

**Repository (repo)** — the project's folder under version control
(`git`); `git clone` copies it to your computer.

**Tests** — the automated checks in `tests/` run with
`uv run pytest tests/ -v`. Run them before sending a change.

**CI** — continuous integration: the automated builds that run on every
push in `.github/workflows` (tests, installers, nightly builds).

See [Contributing](../CONTRIBUTING.md) to make your first change.
