#set text(size: 12pt)
#set page(paper: "a4", margin: 2cm)
#align(center)[= Easy Math Document]

= Point M inside triangle ABC \
#v(0.65em)
#import "@preview/cetz:0.4.2"
#align(center)[#cetz.canvas({
  import cetz.draw: *
  circle((2.000, 6.000), radius: 0.05, fill: black, name: "A")
  content("A", [A], anchor: "south", padding: 0.12)
  circle((0.000, 0.000), radius: 0.05, fill: black, name: "B")
  content("B", [B], anchor: "north-east", padding: 0.12)
  circle((8.000, 0.000), radius: 0.05, fill: black, name: "C")
  content("C", [C], anchor: "north-west", padding: 0.12)
  circle((3.500, 2.500), radius: 0.05, fill: black, name: "M")
  content("M", [M], anchor: "south-west", padding: 0.12)
  circle((4.572, 0.004), radius: 0.05, fill: black, name: "D")
  content("D", [D], anchor: "north-west", padding: 0.12)
  circle((4.662, 3.337), radius: 0.05, fill: black, name: "E")
  content("E", [E], anchor: "south-west", padding: 0.12)
  circle((1.250, 3.749), radius: 0.05, fill: black, name: "F")
  content("F", [F], anchor: "south-east", padding: 0.12)
  line("A", "B", "C", close: true)
  line("A", "D")
  line("B", "E")
  line("C", "F")
})] \
#v(0.65em)
Let M be a point inside triangle ABC. The rays AM, BM, CM meet BC, CA, AB at D, E, F respectively. \
#v(0.65em)
== a) Prove $frac(M D, A D)$ + $frac(M E, B E)$ + $frac(M F, C F)$ = 1 \
#v(0.65em)
Triangles MBC and ABC share the base BC. Since A, M, D are collinear, the distances from M and A to BC are proportional to MD and AD: \
#v(0.65em)
$frac(M D, A D)$ = $frac([M B C], [A B C])$ \
#v(0.65em)
Similarly: \
#v(0.65em)
$frac(M E, B E)$ = $frac([M C A], [A B C])$,   $frac(M F, C F)$ = $frac([M A B], [A B C])$ \
#v(0.65em)
Adding them, since triangles MBC, MCA, MAB exactly compose triangle ABC: \
#v(0.65em)
$frac(M D, A D)$ + $frac(M E, B E)$ + $frac(M F, C F)$ = $frac([M B C] + [M C A] + [M A B], [A B C])$ = 1 \
#v(0.65em)
== b) Prove $frac(A M, A D)$ + $frac(B M, B E)$ + $frac(C M, C F)$ = 2 \
#v(0.65em)
Since M lies between A and D, AM + MD = AD, so: \
#v(0.65em)
$frac(A M, A D)$ = 1 - $frac(M D, A D)$ \
#v(0.65em)
Similarly for B and C. Adding them and using part a): \
#v(0.65em)
$frac(A M, A D)$ + $frac(B M, B E)$ + $frac(C M, C F)$ = 3 - 1 = 2 \
#v(0.65em)
== c) At least one ratio ≥ 2 and at least one ratio ≤ 2 \
#v(0.65em)
Set x = $frac(M D, A D)$, y = $frac(M E, B E)$, z = $frac(M F, C F)$. By part a): x + y + z = 1. \
#v(0.65em)
We have: \
#v(0.65em)
$frac(A M, M D)$ = $frac(1 - x, x)$,   $frac(B M, M E)$ = $frac(1 - y, y)$,   $frac(C M, M F)$ = $frac(1 - z, z)$ \
#v(0.65em)
- Suppose all three ratios are \< 2. Then $frac(1 - x, x)$ \< 2 ⇒ x \> $frac(1, 3)$, similarly y \> $frac(1, 3)$ and z \> $frac(1, 3)$. Hence x + y + z \> 1, a contradiction. \
#v(0.65em)
- Suppose all three ratios are \> 2. Then x, y, z \< $frac(1, 3)$, so x + y + z \< 1, also a contradiction. \
#v(0.65em)
Therefore among the three ratios there is always at least one ratio ≥ 2 and at least one ratio ≤ 2. \
