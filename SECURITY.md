# Security Policy

## Supported versions

Security fixes are applied to the latest release on
[GitHub Releases](https://github.com/duo8097/easy-math-lang/releases).
Older versions do not receive backports — please upgrade.

| Version | Supported |
|---|---|
| 4.5.x | ✅ |
| < 4.5 | ❌ |

## Reporting a vulnerability

Please **do not** open a public issue for a security vulnerability.
Instead, email **Imanoob8097@gmail.com** with:

1. What you found and how to reproduce it (a small `.ezmath` file
   helps a lot).
2. The version (`easy-math-lang --version`) and your OS.
3. What you think the impact is.

You will get an acknowledgement as soon as possible, and an update
when the issue is fixed. Please keep the details private until a fix
is released.

## Updating & verification

Easy Math Lang can check for and install updates from
[GitHub Releases](https://github.com/duo8097/easy-math-lang/releases).
This section states plainly what is and is not covered:

- **What is requested:** the editor and the CLI ask the GitHub Releases
  API for the latest release (`GET .../releases/latest`) and, when you
  choose to update, download the matching asset and `SHA256SUMS.txt`
  from the same release. Automatic checks are throttled to at most one
  request per 24 hours (ETag/`If-None-Match` is honored, so an
  unchanged answer costs almost nothing).
- **What is never sent:** no token, account, telemetry, identifiers or
  document data. The client sends a constant
  `User-Agent: EasyMath-Lang-update-check` and nothing else. The host
  allowlist is enforced for downloads (`github.com`,
  `objects.githubusercontent.com`, `release-assets.githubusercontent.com`);
  redirects to any other host are refused. HTTPS only.
- **How files are verified:** the downloaded asset's SHA-256 is compared
  to `SHA256SUMS.txt` from the same release before it is run or moved
  into place. A missing sums file, a missing line for the asset, or a
  mismatch aborts the update and deletes the download. There is no
  "skip verification" path.
- **The checksum protects integrity, not authenticity.** It proves your
  download matches what the release published — it does **not** prove
  the release itself is trustworthy (anyone who could publish a release
  could also publish a matching sum). The Windows build is
  ad-hoc signed and the macOS build is not notarized; treat update
  prompts like any other administrative action (UAC / polkit).
  **Code signing and notarization is future work.**
- **Rollback:** the update runs in a detached helper after the app
  exits; if installing fails, the helper keeps the old version runnable,
  writes the reason to `~/.config/ezmath/update.log` and records it in
  the update state file, and the next editor start shows the failure
  once with a manual-download button.

## What is in scope

- The compiler (`src/compiler/`) and its evaluation of `.ezmath`
  input, including `calc(...)`/`*plot` expression evaluation.
- The embedded Typst compiler (`typst` PyPI package) as reached
  through generated `.typ` files.
- The desktop editor (`src/editor/`) and language server
  (`src/lsp/`), including how they handle files and PDF links.

## Known hardening (not vulnerabilities, but worth knowing)

- `calc(...)`, `*plot` and vector/plot component evaluation never use
  Python `eval`. Expressions are parsed with `ast` and evaluated
  against a fixed whitelist of operators and functions
  (`src/compiler/calc.py`, `src/compiler/safemath.py`); unknown names
  and unsafe constructs are rejected.
- The compiler spawns no shell commands during a normal build; Typst
  runs in-process via the `typst` package.
- `*image(...)` embeds a file you point at, relative to your
  `.ezmath` file. Treat untrusted `.ezmath` files like any untrusted
  document: they can reference local image files and choose fonts,
  but they cannot execute code.
- The language server speaks LSP over stdio; it is not a network
  service and should not be exposed to one.
