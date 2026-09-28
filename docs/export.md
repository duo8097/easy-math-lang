# Exporting to PDF, images, HTML and Typst

`easy-math-lang` always writes the intermediate Typst source (`doc.typ`
next to your `.ezmath`), then converts it with the `typst` package.
Pick the output by extension — or explicitly with `--format`.

## Quick examples

```
uv run easy-math-lang doc.ezmath              # doc.pdf (default)
uv run easy-math-lang doc.ezmath out.png      # PNG image(s)
uv run easy-math-lang doc.ezmath out.svg      # SVG image(s)
uv run easy-math-lang doc.ezmath out.html     # HTML page
uv run easy-math-lang doc.ezmath out.typ      # Typst source only (no render)
uv run easy-math-lang --format png doc.ezmath # doc.png
uv run easy-math-lang --format png --ppi 300 doc.ezmath -o hi.png
easy-math-lang --list-formats                 # pdf, png, svg, html, typ
```

The installed binaries (`easy-math-lang`, `ezmath`) accept the same flags.
In the desktop editor: **File → Export As…** (PDF/PNG/SVG/HTML/Typst)
works for saved and untitled documents; PNG prompts for DPI (default 150).

## Formats

| Format | Extension | Notes |
|---|---|---|
| PDF | `.pdf` | Default. Print-ready A4 document. |
| PNG | `.png` | Raster image. `--ppi 1..1200` controls resolution. |
| SVG | `.svg` | Vector image (scales cleanly for slides/web). |
| HTML | `.html` | Single web page (Typst HTML export). |
| Typst | `.typ` | Intermediate source only — no `typst.compile()` call. |

## Multi-page images

PNG/SVG are one-file-per-page when the document spans pages.
`doc.png` with 3 pages writes `doc-1.png`, `doc-2.png`, `doc-3.png`
(the CLI prints the `stem-{p}.ext` pattern). To choose the pattern
yourself, include `{p}` in the output name: `out-{p}.png`.

## Tips

- Unknown extensions (e.g. `out`) warn and assume PDF — add `--format`
  to be explicit.
- Invalid `--format`/`--ppi` fails fast with exit code 2 and a hint.
- The `.typ` file next to your input is always rewritten, even when
  exporting images — handy for debugging layout.
- Geometry (`*draw`) renders identically in every format (CeTZ canvas).
