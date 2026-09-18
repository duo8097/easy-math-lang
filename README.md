# easy-math-lang

`easy-math-lang` is a tiny language for writing math documents with simple text.
It is aimed at beginners, students, and teachers who want an easy way to write
lesson notes or small math documents without learning a full typesetting system.

The compiler reads `.ezmath`, writes a `.typ` Typst file, then compiles it to a
PDF.

## Requirements

- Python 3
- Typst installed and available as `typst`

Check Typst with:

```bash
typst --version
```

## Usage

Compile an Easy Math file:

```bash
python3 compiler.py a.ezmath
```

Or choose the output PDF path:

```bash
python3 compiler.py a.ezmath output.pdf
```

This creates:

- `a.typ`: intermediate Typst file
- `a.pdf`: final PDF

## Comments

Use `//` for comments.

```text
// this is a comment
*define(tmp = 10) // this part is also a comment
```

You can also write paired comments:

```text
// comment here //
```

## Defines

Define a value:

```text
*define(tmp1 = 100 000 000)
tmp1
```

Output:

```text
100 000 000
```

Defines can also be called with angle brackets:

```text
*define(width = 12)
Chiều dài: <width>
```

## Variables

Create variables with angle brackets:

```text
<width> = 2
<height> = 3
<area> = <width> * <height>
```

Use a variable by writing its name:

```text
Diện tích: <width> * <height> = calc(<area>)
```

Output:

```text
Diện tích: 2 . 3 = 6
```

Variables print as text unless you use `calc(...)`.

```text
<number> = 2 + 3
<number>
```

Output:

```text
2 + 3
```

## Calculation

Use `calc(...)` to calculate numeric math.

```text
<a> = 10
<b> = 20
<c> = calc(<a> + <b>)
Kết quả: <c>
```

Output:

```text
Kết quả: 30
```

Supported operators:

- `+`
- `-`
- `*`
- `/`
- `%`
- `^`

Spaced numbers are allowed:

```text
calc(100 000 + 20)
```

Output:

```text
100020
```

## Multiplication Symbol

Choose how `*` should print in normal text:

```text
*define(write_type.multiplication = * = .)
```

After that, normal text output changes `*` to `.`.

```text
2 * 3
```

Output:

```text
2 . 3
```

## Raw Print

Use `*p(...)` when you want to print text that may look like Easy Math code.

```text
*p(sin(x))
*p(frac(2; 3))
*p(sum(i = 1; n; i))
```

## Math Commands

Fractions:

```text
*frac(2; 3)
*frac(x + 1; x - 1)
```

Roots:

```text
*root(3; x + 1)
*root(2; x)
```

Powers:

```text
*pow(2; 3)
*pow(x + 1; n)
*pow(A; *degree)
```

Indexes:

```text
A_1
x_n
a_ij
```

Absolute value:

```text
*abs(x + 1)
```

Trigonometry and logs:

```text
*sin(x)
*cos(x)
*tan(x)
*log(x)
*ln(x)
```

Summation and product always render in full display style:

```text
*sum(i = 1; n; i)
*prod(i = 1; n; i)
```

Limits:

```text
*lim(x -> 0; sin(x) / x)
```

Constants:

```text
*pi
*infinity
```

## Symbols

Common shortcuts are converted automatically:

```text
=>
<=>
->
<-
<->
|->
<=
>=
!=
&&
||
+-
-+
~=
~=~
...
```

Output:

```text
⇒
⇔
→
←
↔
↦
≤
≥
≠
∧
∨
±
∓
≈
≅
…
```

They also work inside normal text:

```text
Nếu x => y thì y => z.
A <=> B.
x -> 0.
```

More word shortcuts:

```text
le leq ge geq ne neq approx cong pm mp prop propto
times xx cdot div sqrt cbrt deg degree angle triangle parallel perp
infinity infty forall exists notin isin subset superset subseteq superseteq
union intersect intersection emptyset empty land lor lnot therefore because
alpha beta gamma delta epsilon theta lambda mu pi sigma omega
Delta Sigma Omega
```

Output:

```text
≤ ≤ ≥ ≥ ≠ ≠ ≈ ≅ ± ∓ ∝ ∝
× × ⋅ ÷ √ ∛ ° ° ∠ △ ∥ ⊥
∞ ∞ ∀ ∃ ∉ ∈ ⊂ ⊃ ⊆ ⊇
∪ ∩ ∩ ∅ ∅ ∧ ∨ ¬ ∴ ∵
α β γ δ ε θ λ μ π σ ω
Δ Σ Ω
```

## Blocks

Use `*(` and `)` to group variable work that should not print directly.

```text
*(
    <width> = 2
    <height> = 3
    <area> = calc(<width> * <height>)
)

Diện tích: <width> . <height> = <area>
```

Output:

```text
Diện tích: 2 . 3 = 6
```

## Example

```text
*define(write_type.multiplication = * = .)

<width> = 12
<height> = 5
<area> = calc(<width> * <height>)

Hình chữ nhật có:
Chiều dài: <width>
Chiều rộng: <height>
Diện tích: <width> * <height> = <area>

Đường chéo:
*root(2; *pow(<width>; 2) + *pow(<height>; 2))
```

The generated Typst output inserts `#v(0.65em)` between output lines so equations
have space in the PDF.
