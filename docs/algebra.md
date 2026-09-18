# Algebra

This page covers all math and algebra features of easy-math-lang.

---

## Comments

Use `//` for single-line comments.

```text
// This is a comment
*define(tmp = 10)  // inline comment
```

Paired comments (block comments) using `// ... //`:

```text
// This whole section is commented out //
```

---

## Defines

`*define(name = value)` creates a reusable named value.

```text
*define(tmp1 = 100 000 000)
<tmp1>
```

Output:

```
100 000 000
```

> Defined values are **not** automatically calculated when printed. They are treated as text.

---

## Variables

`<name> = value` creates a variable.

```text
<width> = 2
<height> = 3
<area> = <width> * <height>
```

Reference a variable anywhere in text using `<name>`:

```text
Diện tích: <width> . <height> = calc(<area>)
```

Output:

```
Diện tích: 2 . 3 = 6
```

### Silent blocks

Use `*(` ... `)` to define variables without printing anything:

```text
*(
    <width> = 2
    <height> = 3
    <area> = calc(<width> * <height>)
)

Diện tích: <width> . <height> = <area>
```

Output:

```
Diện tích: 2 . 3 = 6
```

---

## Calculation

`calc(expression)` evaluates a math expression at compile time.

```text
<a> = 10
<b> = 20
<c> = calc(<a> + <b>)
Kết quả: <c>
```

Output:

```
Kết quả: 30
```

Supported operators: `+`, `-`, `*`, `/`, `%`, `^`

Spaced numbers are allowed (useful for large numbers):

```text
calc(100 000 + 20)
```

Output: `100020`

---

## Multiplication Symbol

Customize how `*` is displayed in output text:

```text
*define(write_type.multiplication = .)
```

After this, every bare `*` in text output becomes `.`:

```text
2 * 3
```

Output: `2 . 3`

You can use any symbol:

```text
*define(write_type.multiplication = x)
```

Output: `2 x 3`

---

## Raw Print

`*p(...)` prints text literally, bypassing all parsing rules. Use it when your text looks like code:

```text
*p(sin(x))
*p(frac(2; 3))
*p(sum(i = 1; n; i))
```

---

## Math Commands

All math commands start with `*`. Arguments are separated by `;`.

### Fractions

```text
*frac(numerator ; denominator)
```

```text
*frac(2 ; 3)
*frac(x + 1 ; x - 1)
```

### Roots

```text
*root(index ; radicand)
```

```text
*root(3 ; x + 1)    // cube root of (x+1)
*root(2 ; x)        // square root of x
```

### Powers

```text
*pow(base ; exponent)
```

```text
*pow(x ; 2)
*pow(x + 1 ; n)
*pow(A ; *degree)   // A°
```

### Subscripts

Use `_` directly in text:

```text
A_1     → A₁
x_n     → xₙ
a_ij    → a_(ij)
```

### Absolute Value

```text
*abs(x - 2)
```

### Trigonometric Functions

```text
*sin(x)
*cos(x)
*tan(x)
```

### Logarithms

```text
*log(x)
*ln(x)
```

### Summation

```text
*sum(lower ; upper ; expression)
```

```text
*sum(i = 1 ; n ; i)
```

Output:

```
  n
  Σ i
 i=1
```

### Product

```text
*prod(lower ; upper ; expression)
```

```text
*prod(i = 1 ; n ; i)
```

### Limits

```text
*lim(variable -> value ; expression)
```

```text
*lim(x -> 0 ; sin(x) / x)
```

### Constants

| Command | Output |
|---|---|
| `*pi` | π |
| `*infinity` | ∞ |

---

## Automatic Symbol Shortcuts

These ASCII sequences are automatically converted:

| Input | Output |
|---|---|
| `=>` | ⇒ |
| `<=>` | ⇔ |
| `->` | → |
| `<-` | ← |
| `<->` | ↔ |
| `\|->` | ↦ |
| `<=` | ≤ |
| `>=` | ≥ |
| `!=` | ≠ |
| `&&` | ∧ |
| `\|\|` | ∨ |
| `+-` | ± |
| `-+` | ∓ |
| `~=` | ≈ |
| `~=~` | ≅ |
| `...` | … |

These also work inside normal text:

```text
Nếu x => y thì y => z.
A <=> B.
x -> 0.
```

---

## Math Symbol Keywords

Write math symbols using `*keyword` commands:

### Comparison

| Command | Output |
|---|---|
| `*le` / `*leq` | ≤ |
| `*ge` / `*geq` | ≥ |
| `*ne` / `*neq` | ≠ |
| `*approx` | ≈ |
| `*cong` | ≅ |
| `*pm` | ± |
| `*mp` | ∓ |
| `*prop` / `*propto` | ∝ |

### Arithmetic

| Command | Output |
|---|---|
| `*times` / `*xx` | × |
| `*cdot` | ⋅ |
| `*div` | ÷ |
| `*sqrt` | √ |
| `*cbrt` | ∛ |

### Geometry Symbols

| Command | Output |
|---|---|
| `*deg` / `*degree` | ° |
| `*angle` | ∠ |
| `*triangle` | △ |
| `*parallel` | ∥ |
| `*perp` | ⊥ |

### Sets and Logic

| Command | Output |
|---|---|
| `*infinity` / `*infty` | ∞ |
| `*forall` | ∀ |
| `*exists` | ∃ |
| `*isin` | ∈ |
| `*notin` | ∉ |
| `*subset` | ⊂ |
| `*superset` | ⊃ |
| `*subseteq` | ⊆ |
| `*superseteq` | ⊇ |
| `*union` | ∪ |
| `*intersect` / `*intersection` | ∩ |
| `*emptyset` | ∅ |
| `*land` | ∧ |
| `*lor` | ∨ |
| `*lnot` | ¬ |
| `*therefore` | ∴ |
| `*because` | ∵ |

### Greek Letters

| Command | Output | Command | Output |
|---|---|---|---|
| `*alpha` | α | `*Delta` | Δ |
| `*beta` | β | `*Sigma` | Σ |
| `*gamma` | γ | `*Omega` | Ω |
| `*delta` | δ | | |
| `*epsilon` | ε | | |
| `*theta` | θ | | |
| `*lambda` | λ | | |
| `*mu` | μ | | |
| `*pi` | π | | |
| `*sigma` | σ | | |
| `*omega` | ω | | |

---

## Full Example

```text
*define(write_type.multiplication = .)

*(
    <width>  = 12
    <height> = 5
    <area>   = calc(<width> * <height>)
    <diag>   = calc(<width> ^ 2 + <height> ^ 2)
)

Hình chữ nhật có:
  Chiều dài:  <width>
  Chiều rộng: <height>
  Diện tích:  <width> . <height> = <area>
  Đường chéo: *root(2 ; <diag>)
```

Output:

```
Hình chữ nhật có:
  Chiều dài:  12
  Chiều rộng: 5
  Diện tích:  12 . 5 = 60
  Đường chéo: √169
```
