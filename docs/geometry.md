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

## Lines

### Line segment (from A to B)

```
*line(A ; B)
```

Draws a straight line between two points.

### Infinite line

```
*line(A ; B ; infinite)
```

Draws a line that extends forever through A and B.

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

Draws an arc of a circle centered at O, starting at point A and ending at B.

---

## Angles

```
*angle(A ; B ; C)
```

Draws the angle at vertex B, between sides BA and BC.

You can add a label:

```
*angle(A ; B ; C ; 60°)
```

### Right angle (90° marker)

```
*right-angle(A ; B ; C)
```

Draws a small square in the corner at B to show the angle is exactly 90°.

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
This also draws tick marks on both sides to show they are equal.

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

Point labels are placed automatically (the program avoids overlaps).

To show a length or angle value in the figure:

```
*length(A ; B)             // shows the length of AB
*angle-value(A ; B ; C)    // shows the measure of angle ABC
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
- If a point has no constraints at all, it will be placed somewhere random — give it at least one rule.
