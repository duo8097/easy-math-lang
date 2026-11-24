# Mod files (user commands)

A mod file is a TOML file that adds math commands or overrides built-in
ones. Load it from a document with:

```
*use("my-commands.toml")
```

The path is relative to the `.ezmath` file's folder (absolute paths are
also allowed). The `*use` line emits nothing in the output. All `*use`
lines are collected in a pre-pass, so their order does not matter; mod
files load in the order the lines appear.

## Format

```toml
[[commands]]
name = "avg"
args = 2
typst = "$frac({0} + {1}, 2)$"
usage = "*avg(a ; b)"
doc = "Average of two values."
```

Each entry has `name`, `args` (minimum argument count), `usage` and
`doc`. An optional `aliases` array lists extra spellings. The `typst`
template uses `{0}`, `{1}`, ... for the already-cleaned arguments; a
literal brace is written as `{{` or `}}`.

## Override rules

- A template command may override a built-in template command; the
  compiler emits a warning (`command 'frac' overrides the built-in
  definition`).
- Overriding a built-in alias is allowed too
  (`overrides built-in alias 'fraction' (of *frac)`).
- Overriding a command implemented in Python (`int`, `diff`, `cases`,
  `det`, `set`, `align`, `vec`, `matrix`, `pow`, ...) is an error and
  the entry is ignored.
- Declaring `kind = "builtin"` or a `handler` key in a user mod is an
  error.
- If two mod files define the same name, the later-loaded one wins and
  a warning names both files.

## Bad mod files

Invalid TOML, missing `args`, a template referencing `{3}` with only
2 arguments, unknown keys, or duplicate names in one file produce
diagnostics and never crash the build. A missing or unreadable mod
file is an error at the `*use` line.