# Getting started

Write your first ezmath file in 5 minutes.

This tutorial walks you through creating a `.ezmath` text file and
turning it into a PDF. No programming experience needed — if you can
type in Notepad, TextEdit, or VS Code, you can do this.

---

## Step 0 — Install easy-math-lang

You need the `easy-math-lang` command on your computer.

**Fastest way (no Python needed):** download the installer for your
system from the [**Releases page**](https://github.com/duo8097/easy-math-lang/releases):

- **Windows:** `EasyMathLang-Windows-x64-Setup.exe`
- **macOS (Apple Silicon):** `EasyMathLang-macOS-arm64.dmg`
- **Linux:** `.deb`, `.rpm`, or Arch package

Install it, then launch **Easy Math Editor** from your Start Menu or
Applications.

> Need step-by-step install help? See the [Installation guide](docs/installation.md).

---

## Step 1 — Create your first .ezmath file

Open any text editor (Notepad, TextEdit, VS Code, anything) and type:

```
// My first ezmath document

*doc_title(My Lesson)

<width> = 5
<height> = 3
<area> = calc(<width> * <height>)

The rectangle is <width> cm wide and <height> cm tall.
Its area is: <width> . <height> = <area> cm².
```

Save it as `my-doc.ezmath` in a folder you can find again (for example
your Desktop or Documents folder).

### What each line means

| Line | What it does |
|------|--------------|
| `// My first ezmath document` | A **comment** — anything after `//` is ignored and never shows in the PDF |
| `*doc_title(My Lesson)` | Sets the document title and the PDF's metadata |
| `<width> = 5` | Creates a **variable** named `width` and gives it the value 5 |
| `<height> = 3` | Creates a variable named `height` with value 3 |
| `<area> = calc(<width> * <height>)` | Calculates 5 × 3 = 15 and stores it in `area` |
| `The rectangle is ...` | Normal text — printed as-is in the PDF |
| `<width>`, `<height>`, `<area>` | Variables are replaced by their values when the PDF is built |

**Rule of thumb:** words in `<...>` are variables you define. Words
starting with `*` are commands that do something special. Everything
else is ordinary text.

---

## Step 2 — Compile it to PDF

Open a terminal in the folder where you saved `my-doc.ezmath` and run:

```
easy-math-lang my-doc.ezmath
```

(If you installed from source, use `uv run easy-math-lang my-doc.ezmath` instead.)

You should see:

```
Compiling PDF with Typst...
Successfully compiled my-doc.ezmath to my-doc.pdf via Typst!
```

A file named `my-doc.pdf` now sits next to `my-doc.ezmath`. Open it —
you should see:

> My Lesson
>
> The rectangle is 5 cm wide and 3 cm tall.
> Its area is: 5 . 3 = 15 cm²

---

## Step 3 — Try more math

Change your file to this:

```
*doc_title(More math)

<base> = 6
<height> = 4
<area> = calc(<base> * <height> / 2)

Triangle area:
<base> . <height> / 2 = <area>

A fraction: *frac(1, 2)
A power: *pow(x, 2)
A square root: *root(2, x)
Pi: *pi
```

Save and compile again:

```
easy-math-lang my-doc.ezmath
```

The PDF now shows the triangle area (12), a real fraction (½), x²,
√x, and π.

---

## Step 4 — Draw a simple figure

ezmath can draw geometry too. Add this at the end of your file:

```
*draw(
    *point(A = 0, 0)
    *point(B = 4, 0)
    *point(C = 2, 3)
    *triangle(A ; B ; C)
)
```

This describes a triangle: point A at the bottom-left, point B to the
right, point C above the middle. ezmath figures out where everything
goes and draws it in your PDF.

> You describe **relationships** (points, distances, angles) and the
> program figures out the exact coordinates. Full guide:
> [Drawing geometry](docs/geometry.md).

---

## Step 5 — What if something goes wrong?

You might see a message like:

```
[Error] Line 5: undefined variable <widht>
```

This means ezmath found `<widht>` but you never defined it — probably a
typo (you meant `<width>`). The message shows the line number and the
exact spot, so you can fix it and compile again.

Every message points at a spot in your `.ezmath` file. Full list of
messages and fixes: [Troubleshooting and FAQ](docs/troubleshooting.md).

---

## You're done!

In 5 minutes you:

1. Installed easy-math-lang
2. Wrote a `.ezmath` file with variables and calculation
3. Compiled it to a PDF
4. Tried fractions, powers, roots, and π
5. Drew a triangle

**What next?**

- [Cheat sheet](docs/cheatsheet.md) — everything you type most often, on one page
- [Writing math](docs/algebra.md) — every command explained, with examples
- [Desktop editor](docs/editor.md) — the graphical editor with shortcuts and panels
- [Glossary](docs/glossary.md) — every term explained in plain language
