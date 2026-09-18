# easy-math-lang

`easy-math-lang` is a simple language for writing math documents with plain text.
It targets beginners, students, and teachers who want an easy way to create lesson
notes or math documents without learning a full typesetting system.

Write `.ezmath` files → compile to PDF via Typst.

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Compile a file
uv run easy-math-lang my-document.ezmath

# 3. Open the PDF
my-document.pdf
```

## Documentation

- [Installation](docs/installation.md) — Requirements, setup, and usage
- [Algebra](docs/algebra.md) — Variables, calculations, math commands, and symbols
- [Geometry](docs/geometry.md) — Drawing geometric figures with automatic constraint solving

## Hello World

```text
// My first Easy Math document

*define(write_type.multiplication = .)

<width> = 5
<height> = 3
<area> = calc(<width> * <height>)

Rectangle:
Width:  <width>
Height: <height>
Area:   <width> . <height> = <area>
```

Output:

```
Rectangle:
Width:  5
Height: 3
Area:   5 . 3 = 15
```

## License

MIT
