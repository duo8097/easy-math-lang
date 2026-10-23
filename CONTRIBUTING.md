# Contributing

Thanks for considering a contribution! This project is written for
teachers and students, but maintained in the open — fixes to docs,
tests, bugs and features are all welcome, and you do not need to be an
expert to help.

This page covers setup and workflow. For how the code is organized,
see [Architecture](docs/architecture.md).

---

## 1. Set up your machine

You need **Python 3.12+** and **[uv](https://docs.astral.sh/uv/)**
(the same two things as running from source — see the
[Installation guide](docs/installation.md#option-b--run-from-source-all-platforms)
for installers per OS).

```
git clone https://github.com/duo8097/easy-math-lang
cd easy-math-lang
uv sync
```

`uv sync` installs everything (compiler, editor, test runner — Typst
included). Sanity check:

```
uv run easy-math-lang examples/example.ezmath    # writes examples/example.pdf
uv run pytest tests/ -v                          # full test suite
uv run easy-math-editor                          # desktop editor (optional)
```

---

## 2. Understand the ground rules

- **One parser.** The compiler (`src/compiler/`) is the single source
  of truth for the language. The language server and the editor's
  preview *reuse* it — never add a second place that interprets
  `.ezmath` syntax.
- **Failures stay friendly.** Builds prefer to warn and continue over
  crashing; a bad `*plot`, missing image, or broken `*draw` should
  never take down the whole document. Keep it that way, and make the
  message actionable (line number + what to do).
- **Keep startup cheap.** Heavy imports (NumPy, Typst, PySide6) are
  lazy on purpose; `tests/test_lazy_imports.py` enforces it. Modules
  marked *stdlib-only* (`editor/paths.py`, `editor/positions.py`,
  `editor/protocol.py`, `editor/pdf_links.py`) must not grow
  third-party imports — they bundle cheaply because of it.
- **The language spec is `rule.txt`.** It is the human-readable
  definition of the syntax (and `src/lsp/builtins.py` reads it for
  its help text). If you change the language, update it.

---

## 3. Make your change

Suggested flow:

```
git checkout -b fix/short-description
# ... edit, then:
uv run pytest tests/ -v
```

### Code style

There is no enforced formatter or linter — **match the file you are
in**. The house style is:

- Single quotes for strings, 4-space indent, `snake_case`.
- Every module opens with a one-line `"""docstring."""` saying what it
  does; big files also carry a table-of-contents docstring (see
  `compiler/pipeline.py`, `compiler/math_commands.py`,
  `editor/main_window.py`).
- Comment the **why**, not the what. Existing code is deliberately
  comment-heavy — rationale, gotchas, and "do not regress" notes are
  the norm.
- `# ─── Section name ───` banner comments separate areas of long
  files.
- If you add a command or symbol, register it everywhere it belongs:
  `compiler/diagnostics.py` (`KNOWN_COMMANDS`), the LSP tables
  (`src/lsp/builtins.py` cross-checks them), docs
  (`rule.txt`, `docs/algebra.md`), and ideally a row in
  `docs/cheatsheet.md`.

### Tests

- Add tests next to the area you changed: `tests/test_<area>_<topic>.py`.
- Compiler tests usually stub the Typst backend and assert on the
  generated `.typ` text and stderr — copy the `compile_text` helper
  shape from `tests/test_compiler.py`.
- Keep GUI tests headless (the `qapp` fixture handles offscreen Qt);
  do not add tests that need a display.
- Packaged-binary tests are opt-in (`EASYMATH_RUN_BUILD_TESTS=1` plus
  a real `dist/` build) — you rarely need them.

### Docs

Docs live in `docs/` and are plain Markdown with a house style:
one `# H1` per file, `---` rules between sections, bare ``` fences
(no language tag), tables like `| a | b |` / `|---|---|`, and
`> **Tip:**` blockquotes for callouts. Match the neighboring text.

If your change affects users, update in the same PR:

| Change | Update |
|---|---|
| New/changed syntax | `rule.txt`, `docs/algebra.md`, `docs/cheatsheet.md` |
| New error message | `docs/troubleshooting.md` |
| New term | `docs/glossary.md` |
| Editor/LSP behavior | `docs/editor.md` / `docs/lsp.md` |
| Internal restructuring | `docs/architecture.md` |

---

## 4. Before you open a PR

Checklist:

- [ ] `uv run pytest tests/ -v` passes (CI runs it on **ubuntu and
      windows**, Python 3.12, `tests/test_packaged_build.py` ignored).
- [ ] New behavior has tests; fixed bugs have a regression test.
- [ ] User-facing docs updated (table above).
- [ ] No new runtime dependencies without prior discussion — this
      project is small on purpose (and frozen-binary size matters).
- [ ] Commit messages are short sentences describing the effect
      ("Fix subscript clash inside *matrix cells", not "update").

CI: `.github/workflows/tests.yml` runs the suite on every push and
pull request. Nightly installers are built by
`build-installers.yml` — see [Packaging](docs/packaging.md).

---

## 5. Reporting bugs

Open an issue on
[GitHub Issues](https://github.com/duo8097/easy-math-lang/issues)
with:

1. Your version: `easy-math-lang --version` (or `uv run easy-math-lang --version`).
2. Your OS.
3. The **smallest** `.ezmath` file that shows the problem.
4. The full message text (or screenshot) — including any
   `[Error]` / `[Warning]` lines.

Not sure whether it is a bug? Ask anyway — unclear errors are often
worth improving even when the behavior is "correct".

---

## 6. Good first contributions

Never contributed to an open-source project before? These are sized
for a first PR:

- Fix a typo or unclear sentence in `docs/` (every doc has a
  "See also" section that links back — links are checkable by hand).
- Add a missing row to the [Cheat sheet](docs/cheatsheet.md) or
  [Glossary](docs/glossary.md) for something you had to look up.
- Add a `[Warning]`/`[Error]` example to
  [Troubleshooting](docs/troubleshooting.md) that you actually hit.
- Write a test for a command that has none (grep `tests/` for the
  command name first).
- Improve a "did you mean …?" hint in
  `compiler/diagnostics.py` — tiny change, very visible to users.

---

## See also

- [Architecture](docs/architecture.md) — how the pieces fit together
- [Packaging and releases](docs/packaging.md) — building installers
- [Language server](docs/lsp.md) — LSP development notes
