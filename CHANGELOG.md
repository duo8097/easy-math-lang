# Changelog

All notable changes to easy-math-lang are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries start at v4.3.0; earlier releases (v0.1.0 … v4.2.0) predate
this file — see the
[GitHub releases page](https://github.com/duo8097/easy-math-lang/releases)
for those.

## [Unreleased]

## [5.0.0] - 2026-10-23

### Changed

- Dependency and CI action updates: numpy 2.5.3 → 2.5.4, PySide6
  6.11.2 → 6.12.0 (which now also pulls the new `pyside6-pdf` and
  `pyside6-webengine` sub-packages), `actions/checkout` v4 → v7,
  `actions/setup-python` v5 → v6 and `astral-sh/setup-uv` v3 → v7.
  Dependabot now batches minor/patch updates into grouped PRs.
- **Minimum macOS version raised to 14 (Sonoma)**: PySide6 6.12
  publishes only `macosx_14_0` wheels (no macOS 13 wheels, no sdists),
  so neither `uv sync` nor the prebuilt app can run on macOS 13.
  Documented in the README and installation guide; macOS 13 users
  should stay on the previous release.
- **Breaking**: `*vec` now renders a math-mode column vector instead
  of an exported SVG arrow diagram. `*vec(a ; b [; c ...])` emits a
  Typst `vec(...)` call, works inside `\ ... \` math and
  `*matrix`/`*det` cells (it was text-mode only before), and accepts
  symbolic components (`*vec(a ; b)`). Diagram sidecars (`-vec-*.svg`),
  the `[Vec Error: …]` inline literals and the `compiler.vectors`
  module are gone; warnings (with line numbers) now cover
  too-few components, empty components and unclosed calls.

### Added

- `rule.txt` now documents every builtin command, including the
  previously missing `*diff`/`*pdiff`, `*align`, `*det`,
  `*hat`/`*bar`/`*tilde`/`*overline`/`*dot`, `*bold`/`*italic`/
  `*underline`, `*newpage`/`*pagebreak` and `*image`.
- Tests that keep the docs honest: every LSP builtin must appear in
  `rule.txt`, and every friendly alias (`*squareroot`, `*summation`,
  …) must compile identically to its canonical command and be
  documented.
- Full alias reference in [docs/algebra.md](docs/algebra.md) and a new
  aliases section in the [cheat sheet](docs/cheatsheet.md).

## [4.5.0] - 2026-10-23

### Added

- Contributor onboarding docs: `CONTRIBUTING.md`, architecture,
  cheat sheet, glossary and troubleshooting guides.

### Changed

- Smaller frozen builds: targeted PyInstaller hooks instead of
  `--collect-all`, native library stripping on Linux, and the `ezmath`
  CLI alias is now a symlink on POSIX instead of a copy (PR #4).

### Fixed

- `installer/build_linux.sh` executable bit restored (broke shell
  execution on Linux checkouts).

## [4.4.0] - 2026-10-22

### Security

- Upgraded Pillow to 13.0.0, resolving 28 Dependabot advisories.

## [4.3.1] - 2026-10-22

### Changed

- Faster builds everywhere: cached uv dependencies in installer CI,
  compressed installer freezing, shared parallel build defaults and
  incremental inputs (PR #3).
- Builds centralized; Arch (`PKGBUILD`) packages added alongside
  Debian/Fedora.

## [4.3.0] - 2026-10-21

### Fixed

- Audit regressions: source preservation through the text pipeline,
  editor export asset handling, `//` comment stripping, plot/variable
  edge cases (PR #1).

[Unreleased]: https://github.com/duo8097/easy-math-lang/compare/v5.0.0...HEAD
[5.0.0]: https://github.com/duo8097/easy-math-lang/compare/v4.5.0...v5.0.0
[4.5.0]: https://github.com/duo8097/easy-math-lang/compare/v4.4.0...v4.5.0
[4.4.0]: https://github.com/duo8097/easy-math-lang/compare/v4.3.1...v4.4.0
[4.3.1]: https://github.com/duo8097/easy-math-lang/compare/v4.3.0...v4.3.1
[4.3.0]: https://github.com/duo8097/easy-math-lang/releases/tag/v4.3.0
