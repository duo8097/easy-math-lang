# Geometry

easy-math-lang supports drawing geometric figures using `*draw(...)` blocks.

The compiler includes a **constraint solver** that automatically calculates point
positions from geometric relationships. You describe *what* you want — the engine
figures out *where* to put things.

The final figure is rendered using [CeTZ](https://github.com/cetz-package/cetz) inside Typst.

---

## Drawing Blocks

Wrap all geometry commands in a `*draw(...)` block:

```text
*draw(
    *point(A = 0, 0)
    *point(B = 4, 0)
    *point(C = 2, 3)
    *triangle(A ; B ; C)
)
```

---

## Points

### Fixed coordinates

```text
*point(A = 0, 0)
*point(B = 4, 0)
*point(C = 2, 3)
```

### Auto-positioned points

Omit coordinates when a point's position can be derived from constraints:

```text
*point(C)
```

The solver will find a position for `C` that satisfies all given constraints.

---

## Lines and Segments

```text
*line(A ; B)
```

Draws a line segment from A to B.

### Infinite line

```text
*line(A ; B ; infinite)
```

### Ray

```text
*ray(A ; B)
```

Draws a ray starting at A passing through B.

---

## Triangles

```text
*triangle(A ; B ; C)
```

Draws triangle ABC.

---

## Circles

```text
*circle(center ; radius)
```

```text
*circle(O ; 3)
```

Using a point on the circle instead of a numeric radius:

```text
*circle(O ; A)
```

---

## Arcs

```text
*arc(center ; start ; end)
```

```text
*arc(O ; A ; B)
```

---

## Angles

```text
*angle(A ; B ; C)
```

Draws angle ABC (vertex at B). Optionally provide a label:

```text
*angle(A ; B ; C ; 60°)
```

---

## Right Angles

```text
*right-angle(A ; B ; C)
```

Draws a right-angle marker at B (∠ABC = 90°).

---

## Constraints

Constraints let you describe geometric relationships without manually calculating coordinates.

### Distance

```text
*distance(A ; B ; 5)
```

AB has length 5.

### Perpendicular

```text
*perp(A ; B ; C ; D)
```

AB ⊥ CD.

### Parallel

```text
*parallel(A ; B ; C ; D)
```

AB ∥ CD.

### Point on a line

```text
*on-line(A ; B ; C)
```

C lies on line AB.

### Point on a circle

```text
*on-circle(O ; 5 ; A)
```

A lies on the circle with center O and radius 5.

### Equal lengths

```text
*equal-length(A ; B ; C ; D)
```

Marks AB and CD as equal in length.

### Midpoint

```text
*midpoint(A ; B ; C)
```

C is the midpoint of AB.

### Intersection

```text
*intersection(P ; line(A ; B) ; line(C ; D))
```

P is placed at the intersection of lines AB and CD.

---

## Labels and Measurements

### Point labels

Point labels are placed automatically. You can override with:

```text
*label(A ; A)
```

### Measurements

```text
*length(A ; B)            // displays |AB|
*angle-value(A ; B ; C)   // displays ∠ABC
```

With a specific value:

```text
*length(A ; B) = 5
*angle-value(A ; B ; C) = 60°
```

---

## Examples

### Right triangle

```text
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

The solver automatically places C at (0, 3) so that AC = 3 and AC ⊥ AB.

### Circle with a tangent

```text
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

### Isosceles triangle

```text
*draw(
    *point(A = 0, 0)
    *point(B = 6, 0)
    *point(C)

    *equal-length(A ; C ; B ; C)
    *distance(A ; C ; 5)

    *triangle(A ; B ; C)
    *equal-length(A ; C ; B ; C)
)
```

---

## Design Principle

Simple drawings should require very little code:

```text
*draw(
    *triangle(A ; B ; C)
    *right-angle(A ; B ; C)
)
```

The system handles:

- Point auto-positioning from constraints
- Label placement (no overlaps)
- Right-angle markers
- Equal-length markers
- Parallel and perpendicular markers
- Intersection calculations
- Angle markers

Manual coordinates are an option, not a requirement.
