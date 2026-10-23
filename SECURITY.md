# Security Policy

## Supported versions

Security fixes are applied to the latest release on
[GitHub Releases](https://github.com/duo8097/easy-math-lang/releases).
Older versions do not receive backports — please upgrade.

| Version | Supported |
|---|---|
| 4.5.x | ✅ |
| < 4.5 | ❌ |

## Reporting a vulnerability

Please **do not** open a public issue for a security vulnerability.
Instead, email **Imanoob8097@gmail.com** with:

1. What you found and how to reproduce it (a small `.ezmath` file
   helps a lot).
2. The version (`easy-math-lang --version`) and your OS.
3. What you think the impact is.

You will get an acknowledgement as soon as possible, and an update
when the issue is fixed. Please keep the details private until a fix
is released.

## What is in scope

- The compiler (`src/compiler/`) and its evaluation of `.ezmath`
  input, including `calc(...)`/`*plot` expression evaluation.
- The embedded Typst compiler (`typst` PyPI package) as reached
  through generated `.typ` files.
- The desktop editor (`src/editor/`) and language server
  (`src/lsp/`), including how they handle files and PDF links.

## Known hardening (not vulnerabilities, but worth knowing)

- `calc(...)`, `*plot` and vector/plot component evaluation never use
  Python `eval`. Expressions are parsed with `ast` and evaluated
  against a fixed whitelist of operators and functions
  (`src/compiler/calc.py`, `src/compiler/safemath.py`); unknown names
  and unsafe constructs are rejected.
- The compiler spawns no shell commands during a normal build; Typst
  runs in-process via the `typst` package.
- `*image(...)` embeds a file you point at, relative to your
  `.ezmath` file. Treat untrusted `.ezmath` files like any untrusted
  document: they can reference local image files and choose fonts,
  but they cannot execute code.
- The language server speaks LSP over stdio; it is not a network
  service and should not be exposed to one.
