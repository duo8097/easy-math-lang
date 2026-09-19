# Writing Math

This page explains how to write math documents using easy-math-lang.

Everything you write goes in a plain text file with the `.ezmath` extension.
You can create and edit this file with any text editor — **Notepad, TextEdit,
VS Code**, anything.

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

All math commands start with `*`. Arguments are separated by `;`.

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
