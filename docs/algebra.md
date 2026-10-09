# Writing Math

This page explains how to write math documents using easy-math-lang.

Everything you write goes in a plain text file with the `.ezmath` extension.
You can create and edit this file with any text editor — **Notepad, TextEdit,
VS Code**, anything.

> **New? Start with the friendly shortcuts** (all optional — classic `;`
> syntax keeps working):
> - Commas work like `;`: `*frac(2, 3)`, `*pow(x, 2)`, `*line(A, B)`.
> - Aliases: `*fraction` → `*frac`, `*power` → `*pow`, `*cbrt(x)` (cube root).
> - `let x = 5` / `var x = 5` / `*define x = 5` work like `<x> = 5`.
> - `# Title`, `## Sub`, `- item`, `1. item` become headings/lists.
> - `==` means `=` (single equals); unknown `*cmd` suggests a fix.

---

## The basic idea

You write text that describes what you want, and the compiler turns it into a
clean PDF. There are a few special commands you can use — they all start with `*`
so they are easy to spot.

Words that start with `*` are **commands**.
Words without `*` are printed as **normal text**.

---

## Comments — notes that don't appear in the PDF

Add a `//` before any line to make it a comment. Comments are invisible in the PDF.
Use them to leave notes for yourself.

```
// This is a note to myself — it won't appear in the PDF
<width> = 5
```

You can also put a comment at the end of a line:

```
<width> = 5   // the width of the rectangle
```

---

## Defines — giving a name to a value

Use `*define` to give a name to a number or expression you want to reuse:

```
*define(pi_approx = 3.14159)
```

Then use that name anywhere:

```
The value of pi is approximately <pi_approx>.
```

Output in the PDF:

> The value of pi is approximately 3.14159.

> **Note:** Defines are printed **as text**, exactly as you wrote them.
> They are not automatically calculated.

---

## Variables — storing calculated values

Variables work like defines, but they can be calculated:

```
<width>  = 5
<height> = 3
```

Use angle brackets `< >` to name a variable and to call it later.

```
The width is <width> and the height is <height>.
```

Output:

> The width is 5 and the height is 3.

### Grouping variable definitions (silent block)

If you want to define several variables **without printing them**, wrap them in `*(` ... `)`:

```
*(
    <width>  = 5
    <height> = 3
    <area>   = calc(<width> * <height>)
)

The area of the rectangle is <width> . <height> = <area>.
```

Output:

> The area of the rectangle is 5 . 3 = 15.

---

## Calculations — making the computer do the math

Normally a variable is just printed as text. To actually calculate it, use `calc(...)`:

```
<a> = 10
<b> = 20
<sum> = calc(<a> + <b>)
The answer is <sum>.
```

Output:

> The answer is 30.

### Operators you can use inside calc

| Symbol | Meaning |
|---|---|
| `+` | Addition |
| `-` | Subtraction |
| `*` | Multiplication |
| `/` | Division |
| `^` | Power (e.g. `2 ^ 3` = 8) |
| `%` | Remainder |

You can also write large numbers with spaces — they are ignored inside `calc`:

```
calc(1 000 000 + 500)
```

Result: `1000500`

### Decimal comma (Vietnamese style)

Inside `calc`, a comma between digits is a decimal separator, so
`3,5` means three-and-a-half:

```
<a> = 3,5
<b> = calc(<a> * 2)   // 7
calc(0,25 * 4)        // 1
```

Thousands separators keep working: `calc(100,000 + 1)` is `100001`
and `calc(1,000 * 2)` is `2000`.

> **Ambiguity:** `3,500` matches the thousands pattern (1–3 digits,
> then groups of exactly 3 digits), so it reads as `3500`, not `3.5`.
> To disambiguate, write decimals with a dot (`3.5`), put a space
> after the comma, or use `;` to separate function arguments
> (`*frac(3,5)` is two arguments `3` and `5`, never `3.5`).

---

## The multiplication dot

By default, `*` in your text is replaced by whatever you set here:

```
*define(write_type.multiplication = .)
```

After that line, every time you write `*` in text, it shows as `.` in the PDF — which
is how multiplication is often written in Vietnamese textbooks.

```
*define(write_type.multiplication = .)
2 * 3
```

Output:

> 2 . 3

You can also use `x` or any other symbol:

```
*define(write_type.multiplication = x)
2 * 3
```

Output:

> 2 x 3

---

## Raw print — printing something exactly as written

If you write something that looks like a command but you want it to appear as plain
text, wrap it in `*p(...)`:

```
*p(sin(x))
```

Output:

> sin(x)

---

## Math commands

All math commands start with `*`. Arguments are separated by `;`
— or by `,` if you prefer (`*frac(2, 3)` = `*frac(2 ; 3)`).
When `;` is present it wins, so `*frac(100,000 ; 2)` keeps `100,000`
as one number. Friendly aliases: `*fraction` (= `*frac`),
`*power` (= `*pow`), `*cbrt(x)` (= `*root(3 ; x)`),
`*integral(...)` (= `*int(...)`).

### Fractions

```
*frac(2 ; 3)
```

Displays as a proper fraction (2 over 3).

```
*frac(x + 1 ; x - 1)
```

### Square roots and nth roots

```
*root(2 ; x)       // square root of x
*root(3 ; x + 1)   // cube root of (x + 1)
```

The first number is the **index** (2 = square root, 3 = cube root), the second is
what goes under the root sign.

### Powers (exponents)

```
*pow(x ; 2)         // x squared
*pow(x + 1 ; n)     // (x+1) to the power n
*pow(A ; *degree)   // A degrees (A°)
```

### Subscripts (small numbers below)

Write an underscore `_` between the letter and the subscript number:

```
A_1     → A₁
x_n     → xₙ
```

### Absolute value

```
*abs(x - 2)    // |x − 2|
```

### Trigonometry

```
*sin(x)
*cos(x)
*tan(x)
*cot(x)
*sec(x)
*csc(x)
*arcsin(x)
*arccos(x)
*arctan(x)
*sinh(x)
*cosh(x)
*tanh(x)
*coth(x)
```

All take one argument, like `*sin`. They also work inside `*plot(...)`.

### Integrals

```
*int(x^2)                // indefinite: ∫ x²
*int(x^2 ; x)            // indefinite with differential: ∫ x² dif x
*int(0 ; 1 ; x^2)        // definite: ∫₀¹ x²
*int(0 ; 1 ; x^2 ; x)    // definite with differential: ∫₀¹ x² dif x
*oint(C ; F ; l)         // contour integral (Typst integral.cont)
*integral(0 ; 1 ; x^2)   // alias of *int
```

`lower ; upper` are optional; the last `; variable` adds `dif variable`.
Variables and `calc()` work inside every argument.

### Piecewise and equation systems

```
*cases(x + y = 3 | x - y = 1)
```

Rows split on `|` (same quote/nesting rules as `*matrix` rows).
Inside a row, a depth-0 `;` (same rules as `*matrix` cells; `,` works
when the row has no `;`) separates value/condition cells, aligned with
Typst `&` (conditions line up across rows — a fixed `quad` gap would
not align). Piecewise example:

```
*cases(x ; x > 0 | 0 ; x <= 0)
```

Multiline block form works too (cells work per line as well):

```
*cases(
    x + y = 3
    x - y = 1
)
*cases(
    x ; x > 0
    0 ; x <= 0
)
```

### Vectors (arrow accent)

```
*vec(AB)     // AB with an arrow over it (Typst arrow, not a column vector)
```

Column vectors stay available through `*matrix` (e.g. `*matrix(1 ; 2)`).

### Binomial coefficients

```
*binom(n ; k)
```

### Logarithms

```
*log(x)
*ln(x)
```

### Summation (Σ)

```
*sum(i = 1 ; n ; i)
```

Means: the sum of `i`, where `i` goes from `1` to `n`.

### Product (Π)

```
*prod(i = 1 ; n ; i)
```

### Limits

```
*lim(x -> 0 ; sin(x) / x)
```

Means: the limit of sin(x)/x as x approaches 0.

### Constants

```
*pi        → π
*infinity  → ∞
```

---

## Function plots — drawing graphs with `*plot`

Plot a function `y = f(x)` over an interval:

```
*plot(x^2; -5; 5)
*plot(sin(x); -10; 10)
*plot(1/x; -10; 10)
```

The syntax is:

```
*plot(expression ; xmin ; xmax)
```

Commas work too: `*plot(x^2, -5, 5)`.

Each plot becomes an SVG image next to your document
(`yourdoc-plot-1.svg`, `yourdoc-plot-2.svg`, …) and is embedded in
the PDF automatically. Bounds accept the same numbers and
expressions as `calc` (including variables: `*plot(x; -<a>; <a>)`).

The expression uses `calc`-style syntax: `+ - * / % ^` (`^` is
power), parentheses, the variable `x`, the constants `pi`/`e`, and
the functions `sin cos tan cot sec csc arcsin arccos arctan sinh
cosh tanh coth sqrt cbrt log ln abs exp`
(`log` is base-10 like Typst's `log`; `ln` is the natural log).
Math-command spellings such as `*sin(x)` also work inside plots.

> **Note:** plots are generated **numerically** (1000 samples by
> default). Values that are not finite are skipped, and the curve is
> broken across large jumps so discontinuities like `1/x` do not draw
> a misleading vertical line. Very steep regions may show tiny gaps
> where the curve was split — this is expected.

Limitations:

* Only single-variable functions of `x` are supported (no `ymin`,
  `ymax`, multiple functions, or custom labels yet).
* Write multiplication explicitly (`2*x`, not `2x`).
* A plot whose expression has no finite values on the interval
  (e.g. `*plot(sqrt(x); -10; -1)`) emits a `[Plot Error: ...]`
  message instead of an image — the rest of the document still builds.

---

## Inline math mode — `\ ... \`

Wrap an expression in backslashes to get Typst math typography:

```
The solution is \ x = 2 \.
```

This becomes `$x = 2$` in Typst, so math fonts apply automatically.
Outside math mode, text stays normal document text.

Inside math mode just write naturally:

```
\ x <= y \
\ a^2 + b^2 = c^2 \
\ x -> infinity \
```

Existing replacements keep working inside math mode
(`<=` → ≤, `->` → →, `*alpha` → α).
You do NOT need LaTeX commands like `\leq` or `\rightarrow`.

Rules:

* The first unescaped `\` opens math, the next one closes it.
* Spaces just inside the delimiters are ignored.
* `\\` is a literal backslash and never opens math mode.
* Math can span several lines; the opener buffers until its closer.
* A missing closing `\` produces an error diagnostic.
* Empty `\ \` warns and emits nothing.

---

## Automatic symbol shortcuts

You don't need to copy-paste math symbols. Just type these and they are
automatically converted in the PDF:

| You type | PDF shows |
|---|---|
| `=>` | ⇒ (implies) |
| `<=>` | ⇔ (if and only if) |
| `<==` | ⇐ (implied by) |
| `==>` | ⇒ (implies) |
| `->` | → (arrow) |
| `<-` | ← (left arrow) |
| `<->` | ↔ (double arrow) |
| `\|->` | ↦ (maps to) |
| `<=` | ≤ (less than or equal) |
| `>=` | ≥ (greater than or equal) |
| `<<` | ≪ (much less than) |
| `>>` | ≫ (much greater than) |
| `!=` | ≠ (not equal) |
| `!==` | ≢ (not identical to) |
| `===` | ≡ (identical to) |
| `&&` | ∧ (and) |
| `\|\|` | ∨ (or) |
| `\|-` | ⊢ (proves) |
| `-\|` | ⊣ |
| `==` | = (equals — two become one) |
| `+-` | ± (plus or minus) |
| `-+` | ∓ (minus or plus) |
| `~=` | ≈ (approximately equal) |
| `~~` | ≈ (approximately equal) |
| `~=~` | ≅ (congruent) |
| `...` | … (ellipsis) |
| `**` | ⋅ (multiplication dot) |
| `::` | ∷ (proportion) |

These work inside normal sentences too:

```
If x >= 0 and x <= 10, then x != 5 => something happens.
```

---

## Symbol keywords

You can also type symbols using `*` + a word:

### Comparisons

| Type | Gets |
|---|---|
| `*le` or `*leq` | ≤ |
| `*ge` or `*geq` | ≥ |
| `*ne` or `*neq` | ≠ |
| `*equiv` | ≡ |
| `*sim` | ∼ |
| `*simeq` | ≃ |
| `*asymp` | ≍ |
| `*doteq` | ≐ |
| `*ll` | ≪ |
| `*gg` | ≫ |
| `*prec` | ≺ |
| `*succ` | ≻ |
| `*preceq` | ⪯ |
| `*succeq` | ⪰ |
| `*approx` | ≈ |
| `*cong` | ≅ |
| `*pm` | ± |
| `*mp` | ∓ |
| `*prop` or `*propto` | ∝ |
| `*mid` | ∣ (divides) |
| `*ni` | ∋ (contains) |

### Arrows

| Type | Gets |
|---|---|
| `*to` or `*rightarrow` | → |
| `*gets` or `*leftarrow` | ← |
| `*implies` or `*Rightarrow` | ⇒ |
| `*impliedby` or `*Leftarrow` | ⇐ |
| `*iff` or `*leftrightarrow` | ⇔ |
| `*uparrow` | ↑ |
| `*downarrow` | ↓ |
| `*updownarrow` | ↕ |
| `*mapsto` | ↦ |

### Math operations

| Type | Gets |
|---|---|
| `*times` or `*xx` | × |
| `*cdot` | ⋅ |
| `*div` | ÷ |
| `*oplus` | ⊕ |
| `*otimes` | ⊗ |
| `*circ` | ∘ |
| `*bullet` | • |
| `*star` | ⋆ |
| `*dagger` | † |
| `*cap` | ∩ |
| `*cup` | ∪ |
| `*setminus` | ∖ |
| `*sqrt` or `*surd` | √ |
| `*cbrt` | ∛ |

### Geometry symbols (in text)

| Type | Gets |
|---|---|
| `*degree` or `*deg` | ° |
| `*angle` | ∠ |
| `*triangle` | △ |
| `*parallel` | ∥ |
| `*perp` | ⊥ |

### Set theory

| Type | Gets |
|---|---|
| `*infinity` or `*infty` | ∞ |
| `*forall` | ∀ |
| `*exists` | ∃ |
| `*isin` | ∈ |
| `*notin` | ∉ |
| `*subset` | ⊂ |
| `*superset` or `*supset` | ⊃ |
| `*subseteq` | ⊆ |
| `*supseteq` | ⊇ |
| `*union` | ∪ |
| `*intersect` | ∩ |
| `*emptyset` or `*empty` | ∅ |
| `*land` | ∧ |
| `*lor` | ∨ |
| `*lnot` | ¬ |
| `*therefore` | ∴ |
| `*because` | ∵ |

### Dots and delimiters

| Type | Gets |
|---|---|
| `*ldots` | … |
| `*cdots` | ⋯ |
| `*vdots` | ⋮ |
| `*ddots` | ⋱ |
| `*langle` / `*rangle` | ⟨ ⟩ |
| `*lfloor` / `*rfloor` | ⌊ ⌋ |
| `*lceil` / `*rceil` | ⌈ ⌉ |

### Spacing (work in text and math, incl. `*cases`/`*matrix` cells and `\ ... \` math)

| Type | Gets |
|---|---|
| `*quad` | 1em space (Typst `quad`) |
| `*qquad` | double quad space (`quad quad`; Typst has no bare `qquad`) |
| `*thin` | thin space (Typst `thin`) |
| `*med` | medium space (Typst `med`) |

### Misc symbols

| Type | Gets |
|---|---|
| `*partial` | ∂ |
| `*nabla` | ∇ |
| `*aleph` | ℵ |
| `*hbar` | ℏ |
| `*ell` | ℓ |
| `*Re` | ℜ |
| `*Im` | ℑ |
| `*wp` | ℘ |
| `*prime` | ′ |
| `*square` | □ |
| `*diamond` | ◇ |
| `*top` | ⊤ |
| `*bot` | ⊥ |
| `*vdash` | ⊢ |
| `*dashv` | ⊣ |
| `*bowtie` | ⋈ |

### Greek letters

All 24 lowercase letters plus the capitals that differ from Latin:

| Type | Gets | | Type | Gets |
|---|---|---|---|---|
| `*alpha` | α | | `*Gamma` | Γ |
| `*beta` | β | | `*Delta` | Δ |
| `*gamma` | γ | | `*Theta` | Θ |
| `*delta` | δ | | `*Lambda` | Λ |
| `*epsilon` | ε | | `*Xi` | Ξ |
| `*zeta` | ζ | | `*Pi` | Π |
| `*eta` | η | | `*Sigma` | Σ |
| `*theta` | θ | | `*Upsilon` | Υ |
| `*iota` | ι | | `*Phi` | Φ |
| `*kappa` | κ | | `*Psi` | Ψ |
| `*lambda` | λ | | `*Omega` | Ω |
| `*mu` | μ | | | |
| `*nu` | ν | | | |
| `*xi` | ξ | | | |
| `*omicron` | ο | | | |
| `*pi` | π | | | |
| `*rho` | ρ | | | |
| `*sigma` | σ | | | |
| `*tau` | τ | | | |
| `*upsilon` | υ | | | |
| `*phi` | φ | | | |
| `*chi` | χ | | | |
| `*psi` | ψ | | | |
| `*omega` | ω | | | |

---

## Document structure (headings, lists)

Lesson plans read better with structure — no Typst needed:

```
# My Lesson
## Goals
- item one
- item two
1. first step
2. second step
```

`#`/`##`/`###` become `=`/`==`/`===` headings; `-`/`+` stay lists;
`1.` stays an enumeration; `= Title` also works as a heading.
Variables, `calc`, math and symbols keep working inside them.

### Document title

Set the document title (centered heading + PDF metadata):

```
*doc_title(My Lesson Plan)
```

Aliases `*doc-title`, `*doctitle` and `*title` work the same.
The line is consumed (not shown as body text); the last one wins.
Variables, `calc`, math and symbols work inside the title.
Without it, the title defaults to `Easy Math Document`.

### Document font

Set the body font family, with an optional size:

```
*doc_font(DejaVu Sans)
*doc_font(DejaVu Sans ; 14pt)
```

Aliases `*doc-font` and `*docfont` work the same. A bare number means
points (`; 14` = `14pt`). The line is consumed; the last one wins.
Without it, the document uses the Typst default at `12pt`. Note: the
build ignores system fonts, so pick a family bundled with Typst.

---

## Tables and matrices

Rows are separated by `|`, cells by `;` (or `,` when a row has no `;`
— same friendly rule as `*frac`). `*mat` is an alias of `*matrix`.
Variables, `calc`, math commands and symbols work inside cells.

```
*table(Name ; Age | Alice ; 20 | Bob ; 22)

*matrix(1 ; 2 | 3 ; 4)
*mat(a ; b | c ; d)
```

Large tables read better one row per line:

```
*table(
    Name ; Age
    Alice ; 20
    Bob ; 22
)
*matrix(
    1 ; 2
    3 ; 4
)
```

Notes:

* Every row should have the same number of cells — short rows are
  padded (with a warning): empty table cells become `[]`, empty
  matrix cells become `0` so the PDF still builds.
* `100,000`-style numbers stay intact when `;` is present.
* `||`, `|-`, `-|`, `|->` never split rows — use `*mid` for a literal
  `|` inside a cell.
* Matrices also work inside `\ ... \` math; tables are text mode only.

---

## Full example

Here is a complete document for a rectangle problem:

```
// Rectangle area problem
*define(write_type.multiplication = .)

*(
    <w> = 12
    <h> = 5
    <area> = calc(<w> * <h>)
)

A rectangle has width <w> cm and height <h> cm.

Area:      <w> . <h> = <area> cm²
Diagonal:  *root(2 ; *pow(<w> ; 2) + *pow(<h> ; 2)) cm
```

Output in the PDF:

> A rectangle has width 12 cm and height 5 cm.
>
> Area: 12 . 5 = 60 cm²
>
> Diagonal: √(144 + 25) cm
