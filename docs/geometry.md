# Drawing Geometry

easy-math-lang can draw geometric figures — triangles, circles, angles, and more —
directly in your PDF.

You don't need to know the exact coordinates of every point. Just describe the
**relationships** between points (e.g. "these two sides are equal", "this angle is 90°"),
and the program figures out where to place everything automatically.

---

## How it works

You write geometry commands inside a `*draw(...)` block.
The program:

1. Reads your commands
2. Calculates where each point should go (using a constraint solver)
3. Draws the figure and places it in your PDF

---

## A simple example

```
*draw(
    *point(A = 0, 0)
    *point(B = 4, 0)
    *point(C = 2, 3)
    *triangle(A ; B ; C)
)
```

This draws triangle ABC where you have set the coordinates yourself.

> **Friendly:** `,` works like `;` between points
> (`*triangle(A, B, C)` = `*triangle(A ; B ; C)`,
> `*line(A, B)`, `*intersection(C, line(A, B), line(D, E))`).
> When `;` is present it wins. `*point(A = 0, 0)` never splits —
> its `x, y` comma is coordinates, not a separator.

---

## Points

A **point** is a dot with a name.

### With exact coordinates

If you know where a point should be, write its position as `x, y`:

```
*point(A = 0, 0)    // A is at position (0, 0) — the bottom left
*point(B = 4, 0)    // B is 4 units to the right of A
*point(C = 2, 3)    // C is up and to the right
```

Think of it like a grid — `x` goes right, `y` goes up.

### Without coordinates (auto-positioned)

If you don't know or don't care about the exact position, just name the point.
The program will place it automatically based on the other rules you give:

```
*point(C)
```

This is useful when you say something like "C is 3 cm from A" — the program
figures out a valid position for C.

---

## Construction points

A point can also be **defined by a construction**: a formula that computes
its position from other points. Write the constructor call on the right
side of `=`:

```
*point(M = midpoint(A ; B))          // halfway between A and B
*point(F = foot(C ; line(A ; B)))    // where C projects onto line AB
*point(R = reflect(C ; line(A ; B))) // C mirrored across the line
*point(P = intersect(line(A ; B) ; line(C ; D)))
```

A constructed point is **derived**, not a free variable: it always equals
its formula, and it follows its inputs automatically — if a solver
constraint moves A, the midpoint moves too. Constraints may reference
constructed points:

```
*point(C)                      // free point, solver places it
*point(M = midpoint(A ; C))    // derived from A and C
*distance(B ; M ; 5)           // the constraint moves C; M follows
```

The eight
constructors:

| Constructor | Meaning |
|---|---|
| `midpoint(A ; B)` | halfway between A and B |
| `foot(P ; line(A ; B))` | the perpendicular foot of P on line AB |
| `reflect(P ; line(A ; B))` | P mirrored across the line |
| `reflect(P ; O)` | P mirrored through the point O |
| `intersect(...)` | where two lines/circles cross (see below) |
| `centroid(A ; B ; C)` | center of mass of the triangle |
| `circumcenter(A ; B ; C)` | center of the circle through A, B, C |
| `incenter(A ; B ; C)` | center of the inscribed circle |
| `orthocenter(A ; B ; C)` | where the three altitudes meet |

Constructors may be **nested inside other constructors**:

```
*point(M = midpoint(A ; midpoint(B ; C)))
```

(The restriction is about *commands*: a construction may only appear on
the right side of `*point(NAME = ...)`, never inside `*line(...)` or
`*circle(...)` — those take plain point names. Referenced points may be
defined later; the program sorts dependencies for you.)

### Picking an intersection

Two intersecting lines cross exactly once, so no choice is needed — and
passing one is an error:

```
*point(P = intersect(line(A ; B) ; line(C ; D)))
```

A line and a circle cross up to twice, and two circles up to twice, so
you must say **which** solution with `k = 1` or `k = 2`:

```
*point(P1 = intersect(line(A ; B) ; circle(O ; 3) ; 1))
*point(P2 = intersect(circle(O ; 3) ; circle(Q ; A) ; 2))
```

- **Line + circle:** `k = 1` is the intersection reached first walking
  from A toward B along the line; `k = 2` is the second. (Swapping the
  line's two points swaps the order.)
- **Circle + circle:** `k = 1` is on the **left** (counterclockwise)
  side of the direction from the first circle's center to the second's;
  `k = 2` is on the right.

### When things go wrong

Construction errors are reported like any other geometry error, with the
offending `*point(...)` named:

- **Parallel (or coincident) lines** — `intersect` of two lines has no
  unique solution.
- **A line misses a circle / circles don't cross** — no intersection.
- **Degenerate line** — `line(A ; A)` (the same point twice).
- **Collinear triangle** — no circumcenter or orthocenter.
- **Unknown constructor** — with a suggestion:
  `unknown construction 'midpint' — did you mean 'midpoint'?`
- **Wrong arity** — e.g. `midpoint requires 2 arguments: midpoint(A ; B)`.
- **Missing or invalid `k`** — required for two-solution cases, rejected
  for line + line, and must be 1 or 2.
- **A constructed point given coordinates too** (or built twice) — a
  derived point is computed, never free.
- **Construction cycles** — a point that (directly or through others)
  depends on itself: `construction cycle: M -> N -> M`.

The three-argument *constraint* form `*midpoint(A ; B ; M)` is unchanged:
it makes M a free solver point, whereas `*point(M = midpoint(A ; B))`
computes M directly.

---

## Lines

A `*draw(...)` block can also be written on a single line:

```
*draw(*triangle(A ; B ; C))
```

### Line segment (from A to B)

```
*line(A ; B)
```

Draws a straight line between two points.

### Infinite line

```
*line(A ; B ; infinite)
```

Draws the infinite line through A and B, clipped to the figure bounds.

### Ray (starts at A, goes through B)

```
*ray(A ; B)
```

---

## Triangles

```
*triangle(A ; B ; C)
```

Draws the three sides of triangle ABC.

---

## Circles

```
*circle(O ; 3)
```

Draws a circle centered at O with radius 3.

You can also define the circle using a point on it instead of a number:

```
*circle(O ; A)
```

Draws a circle centered at O that passes through point A.

---

## Arcs

```
*arc(O ; A ; B)
```

Draws an arc of the circle centered at O, going counterclockwise from
point A to point B (radius = distance OA).

---

## Angles

```
*angle(A ; B ; C)
```

Draws the interior angle marker at vertex B, between sides BA and BC.

You can add a label:

```
*angle(A ; B ; C ; 60°)
```

### Right angle (90° marker)

```
*right-angle(B ; A ; C)
```

Draws a small corner marker at the **middle argument** (here: A) to show the
angle is exactly 90°. The other two arguments define the two arms.

---

## Rules and constraints

**Constraints** are rules that tell the program how points relate to each other.
Use them when you don't want to set exact coordinates yourself.

### Distance between two points

```
*distance(A ; B ; 5)
```

"The distance from A to B is 5."

### Perpendicular lines (90° angle)

```
*perp(A ; B ; C ; D)
```

"Line AB is perpendicular to line CD."

A 3-argument form constrains two segments sharing a point:

```
*perp(A ; B ; C)
```

"Segment AB is perpendicular to segment BC."

### Parallel lines

```
*parallel(A ; B ; C ; D)
```

"Line AB is parallel to line CD."

### Point lies on a line

```
*on-line(A ; B ; C)
```

"Point C lies on the line through A and B."

### Point lies on a circle

```
*on-circle(O ; 5 ; A)
```

"Point A lies on the circle centered at O with radius 5."

### Two sides have the same length

```
*equal-length(A ; B ; C ; D)
```

"Segment AB has the same length as segment CD."
(Used by the solver to position points; no tick marks are drawn yet.)

### Midpoint

```
*midpoint(A ; B ; M)
```

"M is the midpoint of AB."

### Intersection of two lines

```
*intersection(P ; line(A ; B) ; line(C ; D))
```

"P is the point where line AB and line CD cross."
The program calculates P's position automatically.

---

## Labels and measurements

Point labels are placed automatically (the program puts each label on the
side away from the figure's edges when possible).

Custom text labels attach to a point, just outside its automatic label:

```
*label(A ; entrance)
```

To show a length or angle value in the figure:

```
*length(A ; B)             // shows the length of AB
*angle-value(A ; B ; C)    // shows the measure of angle ABC (vertex B)
```

You can also assign a value:

```
*length(A ; B) = 5
*angle-value(A ; B ; C) = 60°
```

---

## Examples

### Example 1 — Right triangle

The program places C automatically so that AC = 3 and the angle at A is 90°.

```
*draw(
    *point(A = 0, 0)
    *point(B = 4, 0)
    *point(C)

    *distance(A ; C ; 3)
    *perp(A ; B ; A ; C)

    *triangle(A ; B ; C)
    *right-angle(B ; A ; C)
)
```

### Example 2 — Isosceles triangle

Both sides AC and BC are equal in length.

```
*draw(
    *point(A = 0, 0)
    *point(B = 6, 0)
    *point(C)

    *equal-length(A ; C ; B ; C)
    *distance(A ; C ; 5)

    *triangle(A ; B ; C)
)
```

### Example 3 — Circle with a tangent line

A tangent line touches the circle at exactly one point (at a right angle to the radius).

```
*draw(
    *point(O = 0, 0)
    *circle(O ; 3)

    *point(A)
    *on-circle(O ; 3 ; A)
    *line(O ; A)

    *point(B)
    *perp(O ; A ; A ; B)
    *line(A ; B)
)
```

---

## Tips

- You don't need to set coordinates for every point — only the ones you care about.
- Think of constraints as rules in plain language: "these sides are equal", "this angle is 90°".
- The more constraints you give, the more precisely the figure is drawn.
- Placement is deterministic: the same input always produces the same figure.

---

## See also

- [Cheat sheet](cheatsheet.md) — geometry and math commands on one page
- [Troubleshooting and FAQ](troubleshooting.md) — fixing `[GeometryError]` messages
- [Glossary](glossary.md) — plain-language definitions (constraint solver, …)
