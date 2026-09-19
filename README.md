# easy-math-lang

**easy-math-lang** is a tool that lets you write math documents using simple text —
no design skills needed.

You write a plain text file, run one command, and get a clean PDF with proper
math symbols, fractions, and diagrams.

It was made for **teachers and students** who want an easy way to write math
without fighting complex software.

---

## Requirements

| What | Version | Why you need it |
|---|---|---|
| **Python** | ≥ 3.12 (see `requires-python` in `pyproject.toml`) | Runs the compiler |
| **NumPy** | ≥ 2.5.3 (installed automatically as a project dependency) | Geometry constraint solver |
| **Typst** | any recent release | Turns the intermediate `.typ` file into PDF |
| **pygls** | ≥ 2.1.1 (installed automatically as a project dependency) | Editor support (language server) |

---

## What does it look like?

You write something like this in a text file:

```
// Area of a rectangle

<width>  = 5
<height> = 3
<area>   = calc(<width> * <height>)

The rectangle is <width> cm wide and <height> cm tall.
Its area is: <width> . <height> = <area> cm²
```

And you get a clean PDF that says:

> The rectangle is 5 cm wide and 3 cm tall.
> Its area is: 5 . 3 = 15 cm²

---

## Try the examples

The `examples/` folder has ready-made documents you can compile right away:

```
uv run easy-math-lang examples/example.ezmath
uv run easy-math-lang examples/draw_test.ezmath
```

Each command creates a `.typ` file (intermediate, you can ignore it) and a
`.pdf` file (your finished document) next to the input file.

---

## Editor support (autocompletion, error checking)

If your editor understands the Language Server Protocol, run:

```
uv run easy-math-lsp
```

and point your editor at it (it communicates over stdin/stdout).
You get error messages, variable autocompletion, hover information, and
document symbols for `.ezmath` files.
See [Language server](docs/lsp.md) for details.

---

## For developers

Run the test suite:

```
uv run pytest tests/ -v
```

Project layout:

```
src/easy_math_lang/
├── compiler/     # .ezmath → Typst compiler (text pipeline)
├── geometry/     # constraint solver + CeTZ drawing output
└── lsp/          # language server (reuses the compiler)
tests/            # pytest suite (compiler, geometry, LSP)
examples/         # sample .ezmath documents with expected output
docs/             # user guides
```

---

## Learn more

If you have never used a terminal or installed programs before, start here:

1. 📦 [Installation guide](docs/installation.md) — how to set everything up, step by step
2. ✏️ [Writing math](docs/algebra.md) — how to write formulas, variables, and symbols
3. 📐 [Drawing geometry](docs/geometry.md) — how to draw triangles, circles, and angles
4. 💡 [Language server](docs/lsp.md) — editor autocompletion and error checking

---

## License

MIT
