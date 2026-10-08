#set text(size: 12pt)
#set page(paper: "a4", margin: 2cm)
#align(center)[= Easy Math Document]

= Full syntax tour \
#v(0.65em)
== \1. Defines, variables and calc \
#v(0.65em)
100 000 000 \
#v(0.65em)
The school is Nguyen Trai High School. \
#v(0.65em)
The rectangle is 5 cm wide and 3 cm tall. \
#v(0.65em)
Its area is: 5 . 3 = 15 cm² \
#v(0.65em)
Sum: 10 + 20 = 50 \
#v(0.65em)
== \2. Raw print \
#v(0.65em)
f() \
#v(0.65em)
sin(x) \
#v(0.65em)
== \3. Fractions, roots, powers \
#v(0.65em)
$frac(2, 3)$ \
#v(0.65em)
$frac(4, 5)$ \
#v(0.65em)
$frac(2, 3)$ \
#v(0.65em)
$root(3, {x + 1})$ \
#v(0.65em)
$root(2, {x})$ \
#v(0.65em)
$sqrt(16)$ \
#v(0.65em)
$root(3, {27})$ \
#v(0.65em)
$x^(2)$ \
#v(0.65em)
$x^(3)$ \
#v(0.65em)
$A°$ \
#v(0.65em)
$A_1$ \
#v(0.65em)
$x_n$ \
#v(0.65em)
$abs(x - 2)$ \
#v(0.65em)
$abs(x - 5)$ \
#v(0.65em)
== \4. Trigonometry and logarithms \
#v(0.65em)
$sin(x)$ \
#v(0.65em)
$cos(x)$ \
#v(0.65em)
$tan(x)$ \
#v(0.65em)
$log(10)$ \
#v(0.65em)
$ln(2.718)$ \
#v(0.65em)
== \5. Sums, products, limits \
#v(0.65em)
$display(sum_(i = 1)^(n) (i))$ \
#v(0.65em)
$display(sum_(i = 1)^(n) (i^2))$ \
#v(0.65em)
$display(product_(i = 1)^(n) (i))$ \
#v(0.65em)
$display(product_(k = 1)^(n) (k + 1))$ \
#v(0.65em)
$lim_(x → 0) (sin(x) / x)$ \
#v(0.65em)
$lim_(n → infinity) (1 / n)$ \
#v(0.65em)
== \6. Constants \
#v(0.65em)
$pi$ \
#v(0.65em)
$infinity$ \
#v(0.65em)
== \7. Automatic ASCII symbols \
#v(0.65em)
a ⇒ b \
#v(0.65em)
a ⇔ b \
#v(0.65em)
a ⇐ b \
#v(0.65em)
a ⇒ b \
#v(0.65em)
x → 0 \
#v(0.65em)
x ← 1 \
#v(0.65em)
a ↔ b \
#v(0.65em)
f ↦ y \
#v(0.65em)
a ≤ b \
#v(0.65em)
a ≥ b \
#v(0.65em)
a ≪ b \
#v(0.65em)
a ≫ b \
#v(0.65em)
a ≠ b \
#v(0.65em)
a ≢ b \
#v(0.65em)
a ≡ b \
#v(0.65em)
p ∧ q \
#v(0.65em)
p ∨ q \
#v(0.65em)
h ⊢ c \
#v(0.65em)
c ⊣ h \
#v(0.65em)
a ± b \
#v(0.65em)
a ∓ b \
#v(0.65em)
a ≈ b \
#v(0.65em)
a ≅ b \
#v(0.65em)
wait … \
#v(0.65em)
a = b \
#v(0.65em)
== \8. Symbol keywords \
#v(0.65em)
≤ ≤ ≥ ≥ ≠ ≠ ≡ \
#v(0.65em)
∼ ≃ ≍ ≐ ≪ ≫ \
#v(0.65em)
≺ ≻ ⪯ ⪰ ≈ ≅ \
#v(0.65em)
± ∓ ∝ ∝ ∣ ∋ \
#v(0.65em)
× × ⋅ ÷ ⊕ ⊗ \
#v(0.65em)
∘ • ⋆ † \
#v(0.65em)
∩ ∪ ∖ √ √ ∛ \
#v(0.65em)
° ° ∠ △ □ ◇ \
#v(0.65em)
∥ ⊥ ⊤ ⊥ ⊢ ⊣ ⋈ ′ \
#v(0.65em)
∞ ∀ ∃ ∉ ∈ \
#v(0.65em)
⊂ ⊃ ⊆ ⊇ \
#v(0.65em)
∪ ∩ ∩ ∅ ∅ \
#v(0.65em)
∧ ∨ ¬ ∴ ∵ \
#v(0.65em)
→ → ← ← \
#v(0.65em)
⇒ ⇒ ⇐ ⇐ \
#v(0.65em)
↔ ⇔ \
#v(0.65em)
↑ ↓ ↕ ↦ \
#v(0.65em)
… ⋯ ⋮ ⋱ \
#v(0.65em)
⟨ ⟩ ⌊ ⌋ ⌈ ⌉ \
#v(0.65em)
∂ ∇ ℵ ℏ ℓ ℜ ℑ ℘ \
#v(0.65em)
== \9. Greek letters \
#v(0.65em)
α β γ δ ε ζ η θ \
#v(0.65em)
ι κ λ μ ν ξ ο $pi$ \
#v(0.65em)
ρ σ τ υ φ χ ψ ω \
#v(0.65em)
Γ Δ Θ Λ Ξ Π \
#v(0.65em)
Σ Υ Φ Ψ Ω \
#v(0.65em)
== \10. Inline math \
#v(0.65em)
The solution is $x = 2$. \
#v(0.65em)
Pythagoras: $a^2 + b^2 = c^2$. \
#v(0.65em)
Comparison: $x ≤ y$ and limit $x → infinity$. \
#v(0.65em)
== \11. Document structure \
#v(0.65em)
=== Sub heading \
#v(0.65em)
- first item \
#v(0.65em)
- second item \
#v(0.65em)
+ third item \
#v(0.65em)
1. first step \
#v(0.65em)
2. second step \
#v(0.65em)
= Typst-style heading \
#v(0.65em)
== Typst-style sub heading \
#v(0.65em)
== \12. Tables and matrices \
#v(0.65em)
#table(columns: 2, [Name], [Age], [Alice], [20], [Bob], [22]) \
#v(0.65em)
$mat(1, 2; 3, 4)$ \
#v(0.65em)
$mat(a, b; c, d)$ \
#v(0.65em)
#table(columns: 2, [Name], [Age], [Alice], [20], [Bob], [22]) \
#v(0.65em)
== \13. Function plots \
#v(0.65em)
#image("example_3-plot-1.svg", width: 80%) \
#v(0.65em)
#image("example_3-plot-2.svg", width: 80%) \
#v(0.65em)
#image("example_3-plot-3.svg", width: 80%) \
#v(0.65em)
== \14. Geometry drawing \
#v(0.65em)
#import "@preview/cetz:0.4.2"
#align(center)[#cetz.canvas({
  import cetz.draw: *
  circle((0.000, 0.000), radius: 0.05, fill: black, name: "A")
  content("A", [A], anchor: "north-east", padding: 0.12)
  circle((4.000, 0.000), radius: 0.05, fill: black, name: "B")
  content("B", [B], anchor: "west", padding: 0.12)
  circle((0.030, 3.000), radius: 0.05, fill: black, name: "C")
  content("C", [C], anchor: "south-east", padding: 0.12)
  line("A", "B", "C", close: true)
  line((0.200, 0.000), (0.202, 0.200), (0.002, 0.200))
  arc((4.000, 0.000), start: 142.92deg, stop: 180.00deg, radius: 0.400)
  content((2.000, 0.180), [#"4"])
})] \
#v(0.65em)
#import "@preview/cetz:0.4.2"
#align(center)[#cetz.canvas({
  import cetz.draw: *
  circle((0.000, 0.000), radius: 0.05, fill: black, name: "O")
  content("O", [O], anchor: "north-west", padding: 0.12)
  circle((-2.721, 1.260), radius: 0.05, fill: black, name: "P")
  content("P", [P], anchor: "south-east", padding: 0.12)
  circle("O", radius: 3.000)
  line("O", "P")
  content("P", [#"P"], anchor: "south-east", padding: 0.35)
})] \
