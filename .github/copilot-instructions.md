# GitHub Copilot Code Review Instructions

This document provides comprehensive guidance for GitHub Copilot to conduct effective code reviews for the `easy-math-lang` repository. These instructions are aligned with the project's actual architecture, implementation details, and testing patterns.

## Overview

The `easy-math-lang` project is a sophisticated document generation tool that compiles `.ezmath` source files to PDF/PNG/SVG documents using Typst. It includes a full-featured language server, a PySide6 desktop editor, and advanced mathematical geometry capabilities.

## Project Architecture

### Core Components

1. **Compiler** (`src/compiler/`):
   - `pipeline.py`: Main compilation pipeline (lines 1-2012)
   - `calc.py`, `comments.py`, `diagnostics.py`, `escaping.py`, `inline_math.py`
   - `math_commands.py`, `plots.py`, `safemath.py`, `source_links.py`, `source_map.py`
   - `state.py`, `statements.py`, `symbols.py`, `tables.py`, `text_commands.py`, `update.py`, `variables.py`

2. **Language Server** (`src/lsp/`):
   - `server.py`: pygls JSON-RPC server implementation
   - `analysis.py`, `document.py`: Core LSP functionality

3. **Desktop Editor** (`src/editor/`):
   - `app.py`: Main entry point
   - `lsp_client.py`: LSP client integration
   - `main_window.py`: GUI components
   - `preview.py`, `problems_panel.py`: UI features

4. **Geometry Engine** (`src/geometry/`):
   - `parsing.py`, `solver.py`: Constraint solving
   - `commands.py`, `constructions.py`: Point and shape operations

### Dependencies

- **Python**: ≥ 3.12 (requires-python in pyproject.toml)
- **Core Dependencies**: matplotlib, numpy, pygls, PySide6, typst
- **Development Dependencies**: pyinstaller, pytest, pytest-xdist
- **Build Tools**: uv for dependency management (uv.lock present)

### Test Structure

- `tests/`: Comprehensive test suite with 53 test files
- `test_compiler.py`: Core compilation unit tests
- `test_lsp_server.py`: Language server functionality
- `test_editor_gui.py`: Desktop editor tests (opt-in)
- `test_packaged_build.py`: Cross-platform packaging tests (requires builds)

### Build Configuration

- **Packaging**: PyInstaller with installer scripts in `installer/`
- **CI/CD**: GitHub Actions workflows in `.github/workflows/`
- **Package Managers**: Inno Setup (Windows), deb/rpm (Linux), DMG (macOS)

## Code Review Priorities

### 1. Correctness and Regressions
**Priority**: CRITICAL

**What to look for**:
- Accurate compilation to Typst/PDF per existing test expectations
- Correct mathematical expression evaluation and variable substitution
- Proper error handling for malformed `.ezmath` syntax
- Backward compatibility for existing `.ezmath` files

**Evidence Required**:
- Test assertions in matching test files (e.g., `test_compiler.py`)
- Regression tests in `test_audit_regressions.py`
- Functional testing with examples in `examples/` folder

**Severity Categories**:
- **HIGH**: Incorrect PDF output, math evaluation errors, LSP autocompletion failures
- **MEDIUM**: Minor formatting differences, non-critical error message changes
- **LOW**: Documentation typos, style improvements

**Examples**:
```python
# Review test patterns:
# 1. Variable substitution: test_variable_substitution()
# 2. Undefined variable handling: test_undefined_variable()
# 3. Circular reference detection: test_circular_variable_reference_warns()
# 4. Calc expression evaluation: test_calc_basic(), test_calc_nested_parentheses()
```

### 2. Security
**Priority**: CRITICAL

**What to look for**:
- Path traversal vulnerabilities in file handling
- Command injection in shell commands
- Memory safety in large document processing
- Safe handling of user input in geometry calculations

**Evidence Required**:
- Path validation in `compile_ezmath()` (lines 1239-1286)
- File path safety checks in `_paths_alias()` (lines 1022-1030)
- Input sanitization in math expression parsing

**Severity Categories**:
- **HIGH**: Path traversal, command injection, memory corruption
- **MEDIUM**: Buffer overflows, race conditions, privilege escalation
- **LOW**: Information disclosure, weak encryption

**Examples**:
```python
# Review security concerns:
# 1. File path validation in compile_ezmath (lines 1275-1286)
# 2. Command injection prevention in build scripts
# 3. Safe file operations with path aliases
# 4. Input sanitization in geometry parsing
```

### 3. Data Integrity and File Handling
**Priority**: HIGH

**What to look for**:
- Atomic file operations (no partial writes)
- Proper cleanup of temporary files
- Source map integrity for editor preview navigation
- Correct handling of binary/UTF-8 file encodings

**Evidence Required**:
- Source map generation and validation (`source_map.py`)
- File operation patterns in `compile_ezmath()`
- Temporary file management in editor code

**Severity Categories**:
- **HIGH**: Corrupted PDFs, lost source maps, file handle leaks
- **MEDIUM**: Intermittent file corruption, cleanup failures
- **LOW**: Minor formatting issues, non-essential metadata loss

**Examples**:
```python
# Review data integrity patterns:
# 1. Source map generation and preservation
# 2. Atomic file writing in _run_typst_export()
# 3. Temporary file cleanup in preview features
# 4. Encoding handling for UTF-8 files
```

### 4. Runtime Errors and Edge Cases
**Priority**: HIGH

**What to look for**:
- Graceful handling of malformed input
- Out-of-memory scenarios
- Deeply nested or circular dependencies
- Extreme numeric values and precision limits

**Evidence Required**:
- Error handling in `compile_ezmath()` (lines 1295-1297)
- Diagnostic reporting patterns in `_DiagCounter` (lines 93-131)
- Geometry solver edge cases in `test_geometry.py`

**Severity Categories**:
- **HIGH**: Crashes, infinite loops, memory corruption
- **MEDIUM**: Incorrect results, degraded performance, error message loss
- **LOW**: Non-critical warnings, informational messages

**Examples**:
```python
# Review edge case handling:
# 1. Unclosed math delimiters (line 711-716)
# 2. Unclosed *p(...) blocks (line 206-208)
# 3. Geometry solver failures in test_geometry_constructions.py
# 4. Deep nesting limits (table_depth > 20 check)
```

### 5. Performance
**Priority**: MEDIUM

**What to look for**:
- Memory usage in large document processing
- Compilation speed for complex documents
- LSP response times for large files
- Geometry solver performance

**Evidence Required**:
- Performance tests in the test suite
- Memory usage patterns in pipeline code
- LSP performance benchmarks

**Severity Categories**:
- **HIGH**: Memory leaks, severe performance degradation
- **MEDIUM**: Moderate slowdowns, unnecessary allocations
- **LOW**: Minor inefficiencies, suboptimal caching

**Examples**:
```python
# Review performance concerns:
# 1. Memory allocation in text processing loops
# 2. Regex patterns in `_render_text_line()`
# 3. LSP document parsing efficiency
# 4. Geometry constraint solver optimization
```

### 6. Maintainability
**Priority**: MEDIUM

**What to look for**:
- Code readability and clarity
- Consistent naming conventions
- Documentation completeness
- Modularity and separation of concerns
- Adherence to Python standards

**Evidence Required**:
- PEP 8 compliance
- Module organization patterns
- Documentation in source files
- Import ordering and dependency management

**Severity Categories**:
- **HIGH**: Unreadable code, broken modularity, missing documentation
- **MEDIUM**: Inconsistent patterns, minor naming issues
- **LOW**: Style inconsistencies, minor documentation gaps

**Examples**:
```python
# Review maintainability patterns:
# 1. Import ordering (standard library → third-party → local)
# 2. Module organization (compiler/lsp/editor/geometry separation)
# 3. Docstring standards in public APIs
# 4. Function naming conventions (snake_case for functions)
# 5. Type hint usage (where appropriate)
```

## Evidence-Based Review Requirements

### Mandatory Elements for Each Finding

1. **Severity**: HIGH/MEDIUM/LOW (CRITICAL for correctness/security)
2. **Affected Location**: File path and line numbers
3. **Reproducible Failure Scenario**: Minimal steps to reproduce
4. **Impact**: What breaks or is at risk
5. **Suggested Fix**: Specific, actionable code changes

### Prohibited Elements

1. **Speculative Bugs**: Assumptions not testable with existing tests
2. **False Positives**: Style issues without functional impact
3. **Unnecessary Refactoring**: Changes that don't affect functionality
4. **Scope Creep**: Changes beyond the immediate issue

### Required Elements

1. **Test Correlation**: Reference to existing tests
2. **Code Context**: Show relevant code snippets
3. **Implementation Details**: Concrete changes, not general advice
4. **Backward Compatibility**: Consider existing `.ezmath` files

## Process Guidelines

### Do NOT Modify Code During Reviews

- Do NOT make changes to files during the review process
- Do NOT suggest code modifications that require interactive editing
- Do NOT rewrite existing functionality

### Review Workflow

1. **Understand First**: Read the code and tests thoroughly
2. **Execute Tests**: Run relevant tests to verify behavior
3. **Identify Issues**: Apply severity-based prioritization
4. **Document Findings**: Use the required format
5. **Suggest Fixes**: Provide specific, actionable solutions

### Tool Usage

- Use `uv run pytest tests/test_file.py -v` for test execution
- Use `uv run --frozen python scripts/...` for build scripts
- Use `grep` and `read` for code exploration
- Use `git diff` to see changes in context

## GitHub Copilot Conventions

### Code Generation

1. **Focus on Production Code**: Generate code that passes tests
2. **Follow Project Patterns**: Match existing coding style and architecture
3. **Include Error Handling**: Add appropriate try-catch blocks
4. **Document Changes**: Add relevant docstrings and comments

### Testing Integration

1. **Add Tests First**: New code should have test coverage
2. **Follow Existing Patterns**: Match test file structure and naming
3. **Use Fixtures Appropriately**: Leverage existing test fixtures
4. **Maintain Test Performance**: Avoid slow or flaky tests

## Quick Reference Commands

### Common Commands in this Project

```bash
# Install dependencies
uv sync

# Run tests (excluding packaged build tests)
uv run pytest tests/ --ignore=tests/test_packaged_build.py -v

# Compile examples
uv run easy-math-lang examples/example.ezmath

# Run LSP server
uv run easy-math-lsp

# Run desktop editor
uv run easy-math-editor

# Build binaries
uv run python scripts/build_binaries.py

# Test with strict mode (CI)
uv run easy-math-lang --strict examples/example.ezmath
```

### Important Files to Reference

- `pyproject.toml`: Project configuration and dependencies
- `CHANGELOG.md`: Version history and breaking changes
- `CONTRIBUTING.md`: Contribution guidelines
- `docs/architecture.md`: System architecture documentation
- `examples/`: Sample `.ezmath` files for testing

## Final Checklist

Before completing a review, verify:

1. All findings include severity, location, reproduction steps, impact, and fix
2. No speculative bugs or unnecessary refactoring suggestions
3. Each finding relates to actual implementation, not assumptions
4. Code suggestions follow project patterns and conventions
5. Test correlations are provided for functional issues
6. Security concerns are addressed with specific mitigations
7. Performance issues have concrete optimization suggestions
8. Maintainability improvements follow established patterns

## Resources

- **Documentation**: `docs/` directory (installation.md, cheatsheet.md, etc.)
- **Architecture**: `docs/architecture.md` 
- **Tests**: `tests/` directory with comprehensive coverage
- **Examples**: `examples/` directory with sample documents
- **Issues**: GitHub Issues for bug reports and feature requests

---

*Created by analyzing the actual repository structure, code patterns, test suite, and documentation to provide targeted, evidence-based guidance for effective code reviews.*