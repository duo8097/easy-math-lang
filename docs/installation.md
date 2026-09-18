# Installation

## Requirements

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.12+ | |
| uv | latest | Package manager |
| Typst | any | Must be on `PATH` |

### Install Python

Download from [python.org](https://python.org) or use your system package manager.

### Install uv

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Install Typst

```bash
# macOS (Homebrew)
brew install typst

# Windows (WinGet)
winget install --id Typst.Typst

# Linux (Cargo)
cargo install --git https://github.com/typst/typst --locked typst-cli
```

Verify:

```bash
typst --version
```

---

## Project Setup

Clone the repo and install Python dependencies:

```bash
git clone https://github.com/your-username/easy-math-lang
cd easy-math-lang
uv sync
```

This creates a `.venv` virtual environment and installs `numpy` (required by the geometry engine).

---

## Usage

### Compile a file

```bash
uv run easy-math-lang input.ezmath
```

This produces:

- `input.typ` — intermediate Typst source
- `input.pdf` — final PDF output

### Specify output path

```bash
uv run easy-math-lang input.ezmath output.pdf
```

---

## Project Structure

```
easy-math-lang/
├── src/
│   └── easy_math_lang/
│       ├── __init__.py      # Entry point
│       ├── compiler.py      # .ezmath → Typst compiler
│       └── geometry.py      # Geometric constraint solver
├── docs/
│   ├── installation.md      # This file
│   ├── algebra.md           # Algebra and math syntax
│   └── geometry.md          # Drawing and geometry syntax
├── pyproject.toml           # uv / build config
├── uv.lock                  # Locked dependencies
└── README.md
```
