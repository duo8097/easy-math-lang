# Language server (editor support)

The file `easy-math-lsp` is a [Language Server Protocol](https://microsoft.github.io/language-server-protocol/)
server for Easy-Math-Lang. Connect a compatible editor to it and you get,
while you type:

- **Error messages** — undefined variables (with "did you mean …?" hints),
  broken `calc(...)` expressions, unknown commands, and geometry problems
- **Autocompletion** — your variables and defines, built-in math commands
  (`*frac`, `*sum`, …), geometry commands, and `*symbol` shortcuts
- **Hover information** — a variable's value, or a built-in's description
- **Document symbols** — jump to defines, variables, and `*draw` blocks

It works with `.ezmath` and `.eml` files.

---

## Running it

From the project folder:

```
uv run easy-math-lsp
```

The server communicates using standard JSON-RPC **over stdin/stdout**.
Don't type into its terminal — your editor talks to it for you.

> ⚠️ Logs and debugging go to **stderr**. Stdout is reserved for the
> protocol and must not be polluted, or your editor will disconnect.

---

## Connecting your editor

Any editor that can launch a custom stdio language server works.
Two common setups:

### Neovim (with `nvim-lspconfig`)

```lua
vim.api.nvim_create_autocmd('FileType', {
  pattern = { 'easymath' },
  callback = function()
    vim.lsp.start({
      name = 'easy-math-lsp',
      cmd = { 'uv', '--directory', '/path/to/easy-math-lang', 'run', 'easy-math-lsp' },
    })
  end,
})
```

### VS Code

VS Code needs a small extension to launch a custom server. Options:

1. Use a generic LSP client extension (e.g. "Generic LSP Client" from the
   marketplace) configured with command `uv run easy-math-lsp` for the
   `easymath` language.
2. Associate the extension with `.ezmath` files first:
   `"files.associations": { "*.ezmath": "easymath" }`.

---

## Troubleshooting

| Problem | What to check |
|---|---|
| Editor says the server didn't start | Run `uv run easy-math-lsp` by hand and send it `initialize` — it should answer with its capabilities. Make sure `uv sync` was run so dependencies (`pygls`) are installed. |
| No diagnostics appear | Confirm the file is recognized (`.ezmath`/`.eml` extension or `easymath` language id) and was opened *after* the server started. |
| Server disconnects randomly | Something is writing to the server's stdout. Only stderr may be used for logs. |
| Packaged app (installer/`dist/`): editor can't start the server or compile | The editor finds `easy-math-lsp` / `easy-math-lang` next to itself (`../bin` or side-by-side) without needing `PATH`. If you moved the binaries, keep them together or point `EASYMATH_LSP_EXE` / `EASYMATH_COMPILER_EXE` at the right files. |

---

## For developers

The server lives in `src/lsp/` and reuses the compiler
(`src/compiler/`, `src/geometry/`) instead of
parsing the language a second time. Run its tests with:

```
uv run pytest tests/test_lsp_analysis.py tests/test_lsp_server.py -v
```
