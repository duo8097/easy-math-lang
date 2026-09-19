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

## Learn more

If you have never used a terminal or installed programs before, start here:

1. 📦 [Installation guide](docs/installation.md) — how to set everything up, step by step
2. ✏️ [Writing math](docs/algebra.md) — how to write formulas, variables, and symbols
3. 📐 [Drawing geometry](docs/geometry.md) — how to draw triangles, circles, and angles

---

## License

MIT
