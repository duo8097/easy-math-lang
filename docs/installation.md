# Installation Guide

This guide will walk you through everything you need to install,
even if you have never set up a programming tool before.

---

## What you need to install

Three things are required:

| What | Why you need it |
|---|---|
| **Python** | The language the compiler is written in |
| **uv** | A tool that manages Python packages (think of it like an app store for Python) |
| **Typst** | Turns your math text into a beautiful PDF |

---

## Step 1 — Install Python

You need **Python 3.12 or newer** (see `requires-python` in `pyproject.toml`).

### Windows

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Click the big yellow **Download Python** button
3. Run the installer
4. ⚠️ On the first screen, check **"Add Python to PATH"** before clicking Install

### macOS

Open **Terminal** (press `Cmd + Space`, type "Terminal", press Enter) and run:

```
xcode-select --install
```

Then go to [python.org/downloads](https://www.python.org/downloads/) and download the Mac installer.

### Linux

Open a terminal and run:

```
sudo apt install python3 python3-pip
```

---

## Step 2 — Install uv

> **What is a terminal?**
> A terminal (also called "command prompt" on Windows) is a window where you type
> commands instead of clicking buttons. Don't worry — you only need a few simple ones.

**Windows** — Open **Command Prompt** (press `Win + R`, type `cmd`, press Enter):

```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux** — Open **Terminal** and run:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After it finishes, close the terminal and open a new one (this is needed for the change to take effect).

Check it worked by typing:

```
uv --version
```

You should see something like `uv 0.x.x`. If you do, it worked!

---

## Step 3 — Install Typst

**Windows** — In Command Prompt:

```
winget install --id Typst.Typst
```

If `winget` does not work, download Typst directly from [github.com/typst/typst/releases](https://github.com/typst/typst/releases) — grab the file ending in `-windows.zip`, unzip it, and place `typst.exe` somewhere on your Desktop.

**macOS** — In Terminal:

```
brew install typst
```

If you don't have Homebrew, install it first from [brew.sh](https://brew.sh).

**Linux** — In Terminal:

```
cargo install --git https://github.com/typst/typst --locked typst-cli
```

Check it worked:

```
typst --version
```

---

## Step 4 — Download easy-math-lang

If you have Git installed:

```
git clone https://github.com/duo8097/easy-math-lang
cd easy-math-lang
```

Otherwise, go to the GitHub page, click the green **Code** button, then **Download ZIP**.
Unzip it, then open a terminal **inside that folder**.

> **How to open a terminal in a folder:**
> - **Windows:** Hold `Shift` and right-click the folder, then choose "Open PowerShell window here"
> - **macOS:** Right-click the folder in Finder, choose "New Terminal at Folder"

---

## Step 5 — Install the project dependencies

Inside the project folder, run:

```
uv sync
```

This installs everything the project needs. You only have to do this once.

---

## You're ready!

To compile your first document, create a file called `my-doc.ezmath` inside the
project folder (any plain text editor works — even Notepad), write some content,
then run:

```
uv run easy-math-lang my-doc.ezmath
```

You will see two new files appear:

- `my-doc.typ` — the intermediate file (you can ignore this)
- `my-doc.pdf` — your finished document, open this!

> **Want to try immediately?** The `examples/` folder already contains finished
> documents. Run `uv run easy-math-lang examples/example.ezmath` and open
> `examples/example.pdf`.

> **Want autocompletion and error checking in your editor?** See the
> [Language server](lsp.md) guide.

---

## Something went wrong?

| Problem | Solution |
|---|---|
| `uv: command not found` | Close and reopen the terminal after installing uv |
| `typst: command not found` | Make sure Typst is installed and on your PATH |
| `Python not found` | Re-install Python and check "Add to PATH" |
| PDF looks empty | Check your `.ezmath` file for typos |
