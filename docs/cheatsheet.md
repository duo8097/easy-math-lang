# Cheat sheet

One page with everything you type most often. Each section links to the
full guide if you need details.

---

## Run the compiler

```
uv run easy-math-lang doc.ezmath              → doc.pdf (next to your file)
uv run easy-math-lang doc.ezmath out.png      → image(s)
uv run easy-math-lang --strict doc.ezmath     → exit non-zero on errors (CI)
uv run easy-math-lang --help                  → all options
```

Installed the app? Just `easy-math-lang doc.ezmath` (or press **Ctrl+B**
in the editor). See [Export](export.md).

---

## Skeleton of a document

```
// A comment — invisible in the PDF
*doc_title(My Lesson)

# Title
## Subtitle

*(
    <width>  = 5
    <height> = 3
    <area>   = calc(<width> * <height>)
)

The area is <width> . <height> = <area> cm².

- a list item
1. a numbered step
```

---

## Values

| You write | Meaning |
|---|---|
| `*define(pi_approx = 3.14)` | Name for a value — printed as written |
| `<width> = 5` | Variable — can be calculated later |
| `let x = 5` / `var x = 5` | Friendly aliases for a variable |
| `calc(<a> + <b>)` | Actually calculate: `+ - * / % ^`, `sqrt`, `sin`, `pi`, … |
| `*( ... )` | Define several variables without printing them |
| `// text` | Comment (also works at the end of a line) |

> **Decimal rule:** inside `calc` always use a dot (`3.5`, never `3,5`).
> In commands, `,` separates arguments: `*frac(3,5)` is 3 over 5.

---

## Separators — one rule

`,` and `;` separate arguments everywhere. When `;` is present it wins,
so big numbers keep their commas: `*frac(100,000 ; 2)`.

```
*frac(2, 3)          same as   *frac(2 ; 3)
*line(A, B)          same as   *line(A ; B)
*table(a ; b | c ; d)          rows split on |, cells on ;
```

---

## Everyday math

| Write | Gets |
|---|---|
| `*frac(2, 3)` | ²⁄₃ as a real fraction |
| `*pow(x, 2)` | x² |
| `*root(2, x)` | √x (first number = index) |
| `*cbrt(x)` | ∛x |
| `*abs(x - 2)` | \|x − 2\| |
| `A_1` | A₁ (subscript) |
| `*sin(x)` `*cos(x)` `*tan(x)` `*arcsin(x)` … | trigonometry |
| `*log(x)` `*ln(x)` | logarithms |
| `*sum(i = 1 ; n ; i)` | Σ — sum of i from 1 to n |
| `*prod(i = 1 ; n ; i)` | Π — product |
| `*lim(x -> 0 ; sin(x) / x)` | limit |
| `*int(0 ; 1 ; x^2)` | ∫₀¹ x² (use `*integral` if you prefer) |
| `*diff(f ; x)` / `*pdiff(f ; x)` | df/dx / ∂f/∂x |
| `*binom(n, k)` | binomial coefficient |
| `*set(x ; x > 0)` | set-builder {x \| x > 0} |
| `*matrix(1 ; 2 \| 3 ; 4)` | matrix (rows on `\|`) |
| `*cases(x ; x > 0 \| 0 ; x <= 0)` | piecewise / equation systems |
| `*align(x = 1 \| y = 2)` | equations aligned on `=` |
| `*hat(x)` `*bar(AB)` `*dot(x)` | accents |
| `*pi` `*infinity` `*degree` | π ∞ ° |

Full list with every argument pattern: [Writing math](algebra.md).

---

## Aliases — same command, other names

Like a word with two spellings? These all produce the same output:

| You write | Same as |
|---|---|
| `*fraction(2, 3)` | `*frac(2, 3)` |
| `*power(x, 2)` | `*pow(x, 2)` |
| `*squareroot(x)` / `*square-root(x)` | `*sqrt(x)` |
| `*cbrt(x)` / `*cuberoot(x)` / `*cube-root(x)` | `*root(3 ; x)` |
| `*absolute(x - 2)` | `*abs(x - 2)` |
| `*summation(i = 1 ; n ; i)` | `*sum(i = 1 ; n ; i)` |
| `*product(i = 1 ; n ; i)` | `*prod(i = 1 ; n ; i)` |
| `*limit(x -> 0 ; sin(x) / x)` | `*lim(x -> 0 ; sin(x) / x)` |
| `*integral(0 ; 1 ; x^2)` | `*int(0 ; 1 ; x^2)` |
| `*mat(1 ; 2 \| 3 ; 4)` | `*matrix(1 ; 2 \| 3 ; 4)` |

---

## Text and structure

| Write | Result |
|---|---|
| `# Title` `## Sub` `### Sub-sub` | headings |
| `- item` / `1. item` | list / numbered list |
| `*bold(text)` `*italic(text)` `*underline(text)` | styling (`*b` `*i` `*u` work too) |
| `\ x = 2 \` | inline math mode (math font, no LaTeX needed) |
| `*newpage` | page break |
| `*image(pic.png ; 50%)` | image (optional width) |
| `*p(sin(x))` | print `sin(x)` literally |
| `*doc_title(My Lesson)` | centered title + PDF metadata |
| `*doc_font(DejaVu Sans ; 14pt)` | body font |

---

## Symbols

| You type | PDF shows | | You type | PDF shows |
|---|---|---|---|---|
| `<=` `>=` `!=` | ≤ ≥ ≠ | | `*alpha` … `*omega` | Greek letters |
| `->` `=>` `<=>` | → ⇒ ⇔ | | `*Gamma` … `*Omega` | capitals Γ Δ … |
| `==` | = | | `*leq` `*geq` `*neq` | ≤ ≥ ≠ |
| `+-` `~~` `...` | ± ≈ … | | `*times` `*div` `*cdot` | × ÷ ⋅ |
| `&&` `\|\|` | ∧ ∨ | | `*isin` `*notin` `*subset` | ∈ ∉ ⊂ |
| `**` | ⋅ | | `*forall` `*exists` `*emptyset` | ∀ ∃ ∅ |

Tables by category (arrows, Greek, set theory, delimiters, spacing):
[Writing math → Symbol keywords](algebra.md#symbol-keywords).

---

## Draw geometry

```
*draw(
    *point(A = 0, 0)
    *point(B = 4, 0)
    *point(C)                    // placed automatically
    *distance(A ; C ; 3)         // a rule instead of coordinates
    *perp(A ; B ; A ; C)
    *triangle(A ; B ; C)
    *right-angle(B ; A ; C)
)
```

You describe **relationships**; the solver finds the positions.
Full guide: [Drawing geometry](geometry.md).

---

## Plot a function

```
*plot(x^2, -5, 5)
*plot(sin(x), -10, 10)
```

Creates `doc-plot-1.svg` next to your file and embeds it automatically.
Only functions of `x`; write `*` for multiplication (`2*x`, not `2x`).

---

## If something goes wrong

| Message | What it means |
|---|---|
| `[Error] Line 7: undefined variable <widht>` | Typo in a variable name |
| `[Warning] … unknown command *fract …` | Misspelled command — a suggestion is printed |
| `[Calc Error: division by zero]` | `calc()` tried to divide by 0 |
| `Compiled … with 2 error(s), 1 warning(s)` | PDF was written anyway; fix these or use `--strict` |

Full guide with fixes: [Troubleshooting and FAQ](troubleshooting.md).

---

## See also

- [Writing math](algebra.md) — every command explained
- [Drawing geometry](geometry.md) — figures and constraints
- [Export](export.md) — PDF, PNG, SVG, HTML, Typst
- [Desktop editor](editor.md) — shortcuts and panels
- [Glossary](glossary.md) — what all the terms mean
