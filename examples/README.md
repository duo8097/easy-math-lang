# Examples

Every `.ezmath` file below was compiled successfully with the project
compiler. Start near the top, then move down when you want more features in
one document. A PDF in the Result column is the saved output of the `.ezmath`
file beside it.

| File | What it teaches | Difficulty | Result |
| --- | --- | --- | --- |
| [example.ezmath](example.ezmath) | A broad first tour of variables, calculations, fractions, roots, functions, symbols, and limits. | Start here (beginner) | [example.pdf](example.pdf) |
| [construction_points.ezmath](construction_points.ezmath) | Draws a triangle and constructs its orthocenter from two altitude feet. | Intermediate | — |
| [draw_test.ezmath](draw_test.ezmath) | Draws four constrained figures: right and isosceles triangles, a tangent circle, and equal angles. | Intermediate | [draw_test.pdf](draw_test.pdf) |
| [example_4.ezmath](example_4.ezmath) | Practices integrals, cases, vectors, binomials, and extended trigonometric functions. | Intermediate | [example_4.pdf](example_4.pdf) |
| [example_2.ezmath](example_2.ezmath) | Combines a geometry drawing with a written proof about ratios inside a triangle. | Advanced | [example_2.pdf](example_2.pdf) |
| [example_6.ezmath](example_6.ezmath) | A tour of styling, number sets, derivatives, determinants, aligned equations, and images. | Advanced | [example_6.pdf](example_6.pdf) |
| [example_5.ezmath](example_5.ezmath) | A compiler workout that combines nearly every everyday math feature. | Advanced | [example_5.pdf](example_5.pdf) |
| [example_3.ezmath](example_3.ezmath) | A full syntax tour, including tables, plots, document structure, and geometry. | Advanced | [example_3.pdf](example_3.pdf) |

Note: [sine.png](sine.png) is an image asset used by [example_6.ezmath](example_6.ezmath).

To compile an example from the repository root, replace the file name below
with any `.ezmath` file from the table:

```sh
uv run easy-math-lang examples/construction_points.ezmath
```
