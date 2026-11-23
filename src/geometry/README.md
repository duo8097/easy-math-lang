# src/geometry — constraint solver + CeTZ drawing output

This package handles `*draw(...)` blocks. You describe geometric
relationships (points, distances, angles, perpendicular lines, …) and
the solver figures out where to place everything, then emits Typst/CeTZ
drawing code that the compiler embeds in your PDF.

## What it does

1. **Parses** the `*draw(...)` block contents (depth-aware, respects
   nested parentheses and quoted strings).
2. **Solves** the constraint system: free points are positioned so all
   rules (distances, perpendicularity, on-line, on-circle, …) hold.
3. **Computes** derived points (midpoints, feet, intersections,
   centroids, circumcenters, incenters, orthocenters).
4. **Generates** Typst/CeTZ code (`#import "@preview/cetz:0.4.2"`)
   that draws points, labels, triangles, circles, arcs, angles, and
   annotations.
5. **Reports** geometry errors (constraint conflicts, non-convergence,
   unknown constructions) without crashing the build.

## Important files

| File | What it does |
|------|--------------|
| `parsing.py` | `parse_draw_block()` — depth-aware parsing of `*draw(...)` contents; `split_args()` — semicolon/comma argument splitting. |
| `solver.py` | `GeometrySolver` — holds points, constraints, and draw commands; `add_point()`, `add_constraint()`, `solve()`. Free points move; fixed points stay; constructed points are computed. |
| `constructions.py` | Point constructors: `midpoint`, `foot`, `reflect`, `intersect`, `centroid`, `circumcenter`, `incenter`, `orthocenter`. Each has `deps` (points it reads) and `compute()` (its position). |
| `codegen.py` | `generate_typst()` — turns a solved scene into Typst/CeTZ markup (points, labels, triangles, circles, arcs, angles, dimensions). |
| `commands.py` | `KNOWN_GEOMETRY_COMMANDS` — all `*draw` sub-commands and their argument patterns; `_process_command()` dispatches each command. |
| `errors.py` | `GeometryError`, `GeometryWarning` — geometry-specific diagnostics. |
| `vectors.py` | Vector math helpers (norm, normalization, ray/bbox intersection). |
| `labels.py` | Label placement helpers (`away`, `add_arm`) so labels don't overlap points. |

## Data flow

```
*draw(...) block in your .ezmath
    │
    ▼
parsing.parse_draw_block()   split into commands + args,
                             respecting nested () and "quoted strings"
    │
    ▼
GeometrySolver               add_point() (fixed coordinates),
                             add_constraint() (distance, perp, …),
                             then solve() positions free points
    │
    ▼
constructions.py             derived points (midpoint, foot, …) computed
                             in dependency order
    │
    ▼
codegen.generate_typst()     Typst/CeTZ markup with #import cetz
    │
    ▼
compiler.pipeline            embeds the Typst in your document
    │
    ▼
typst.compile()              renders the drawing in your PDF
```

## I want to change X, which file do I open?

| Change | File |
|--------|------|
| Add a new `*draw` sub-command (e.g. `*arc(...)`) | `src/geometry/commands.py` |
| Add a new constraint type | `src/geometry/solver.py` (`add_constraint`) |
| Add a new point constructor | `src/geometry/constructions.py` |
| Change how drawings look (colors, labels) | `src/geometry/codegen.py` |
| Change draw-block parsing | `src/geometry/parsing.py` |
