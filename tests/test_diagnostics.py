"""Python-style diagnostic context blocks (compiler.diagnostics.report).

The classic first line stays byte-identical; the block under it shows
the original source line with a caret. These tests cover the block
format, caret positioning (characters, tabs, Vietnamese, long lines),
missing columns, multi-line constructs, NO_COLOR and the strict-mode
diagnostic counter.
"""

import os
import sys

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "src")
)

from compiler import compile_ezmath
from compiler import pipeline as _pipeline
from compiler import diagnostics as _diagnostics


def compile_text(tmp_path, monkeypatch, capsys, text, name="case.ezmath"):
    src = tmp_path / name
    src.write_text(text, encoding="utf-8")
    stub = type(
        "_TypstStub", (), {"compile": staticmethod(lambda *a, **k: None)}
    )()
    monkeypatch.setattr(_pipeline, "typst", stub)
    ok = compile_ezmath(str(src), str(tmp_path / "case.pdf"))
    return ok, capsys.readouterr().err


def _echo_line(err, needle):
    """The indented source-line echo (starts with 4 spaces)."""
    return next(ln for ln in err.splitlines()
                if ln.startswith("    ") and needle in ln)


def _block_lines(err):
    return [ln for ln in err.splitlines() if ln.startswith(("  File ", "    "))]


def test_undefined_variable_block_format(tmp_path, monkeypatch, capsys):
    _, err = compile_text(tmp_path, monkeypatch, capsys, "Need <foo> here\n")
    lines = err.splitlines()
    assert "[Error] Line 1: undefined variable <foo>" in lines
    file_line = next(ln for ln in lines if ln.startswith("  File "))
    assert file_line == f'  File "{tmp_path / "case.ezmath"}", line 1, column 6'
    assert "    Need <foo> here" in lines
    caret = next(ln for ln in lines if set(ln) <= set(" ^") and "^" in ln)
    assert caret == "    " + " " * 5 + "^^^^^"


def test_first_line_is_byte_identical(tmp_path, monkeypatch, capsys):
    _, err = compile_text(tmp_path, monkeypatch, capsys, "Need <foo> here\n")
    # No ANSI, no indentation: exactly what the old direct print emitted.
    assert "[Error] Line 1: undefined variable <foo>\n" in err
    assert "\x1b[" not in err


def test_caret_position_multibyte_vietnamese(tmp_path, monkeypatch, capsys):
    # Columns count characters, not bytes: 'ố' is two UTF-8 bytes but
    # one character, so the caret must not shift right.
    src = "Tống = <widht> + 2\n"
    _, err = compile_text(tmp_path, monkeypatch, capsys, src)
    file_line = next(ln for ln in err.splitlines() if ln.startswith("  File "))
    assert file_line.endswith("column 8")
    src_line = _echo_line(err, "Tống")
    caret_line = err.splitlines()[err.splitlines().index(src_line) + 1]
    assert src_line.index("<widht>") == caret_line.index("^")


def test_caret_position_after_tabs(tmp_path, monkeypatch, capsys):
    src = "\t*foobar(1 ; 2)\n"
    _, err = compile_text(tmp_path, monkeypatch, capsys, src)
    file_line = next(ln for ln in err.splitlines() if ln.startswith("  File "))
    assert file_line.endswith("column 2")
    src_line = _echo_line(err, "*foobar")
    caret_line = err.splitlines()[err.splitlines().index(src_line) + 1]
    # Tab expanded to 4 columns: caret sits under the '*'.
    assert src_line.index("*foobar(") == caret_line.index("^")


def test_caret_for_unknown_command_call(tmp_path, monkeypatch, capsys):
    _, err = compile_text(tmp_path, monkeypatch, capsys, "*frcc(1 ; 2)\n")
    file_line = next(ln for ln in err.splitlines() if ln.startswith("  File "))
    assert file_line.endswith("column 1")
    src_line = _echo_line(err, "*frcc")
    caret_line = err.splitlines()[err.splitlines().index(src_line) + 1]
    assert caret_line.count("^") == len("*frcc(")


def test_caret_for_bare_unknown_command(tmp_path, monkeypatch, capsys):
    _, err = compile_text(tmp_path, monkeypatch, capsys, "Tong = 1 + *bogus\n")
    src_line = _echo_line(err, "*bogus")
    caret_line = err.splitlines()[err.splitlines().index(src_line) + 1]
    assert src_line.index("*bogus") == caret_line.index("^")


def test_long_line_is_truncated_around_span(tmp_path, monkeypatch, capsys):
    src = "x" * 180 + " <widht> " + "y" * 80 + "\n"
    _, err = compile_text(tmp_path, monkeypatch, capsys, src)
    src_line = _echo_line(err, "<widht>")
    assert "…" in src_line
    assert len(src_line) <= 4 + _diagnostics.MAX_SOURCE_WIDTH + 1
    caret_line = err.splitlines()[err.splitlines().index(src_line) + 1]
    assert src_line.index("<widht>") == caret_line.index("^")


def test_missing_column_prints_file_line_without_caret(tmp_path, monkeypatch, capsys):
    # *table() with nothing in it: the warning has no regex span, so
    # the block shows File/line + source line but no caret.
    _, err = compile_text(tmp_path, monkeypatch, capsys, "*table()\n")
    assert "[Warning] Line 1: *table(...) is empty" in err
    file_line = next(ln for ln in err.splitlines() if ln.startswith("  File "))
    assert file_line == f'  File "{tmp_path / "case.ezmath"}", line 1'
    assert "    *table()" in err
    assert "^" not in err


def test_multiline_unclosed_math_points_at_opening_line(tmp_path, monkeypatch, capsys):
    src = "Tong = 1 + \\\nx^2 + 2\n"
    _, err = compile_text(tmp_path, monkeypatch, capsys, src)
    lines = err.splitlines()
    assert any(ln.startswith(
        "[Error] Line 1: unclosed math delimiter") for ln in lines)
    idx = next(i for i, ln in enumerate(lines)
               if ln.startswith("[Error] Line 1: unclosed math delimiter"))
    file_line = lines[idx + 1]
    assert file_line == f'  File "{tmp_path / "case.ezmath"}", line 1, column 12'
    assert lines[idx + 2] == "    Tong = 1 + \\"
    assert lines[idx + 3] == "    " + " " * 11 + "^"


def test_eof_multiline_unclosed_draw_reports_opening_line(tmp_path, monkeypatch, capsys):
    src = "*draw(\n    *point(A = 0, 0)\n"  # never closed
    _, err = compile_text(tmp_path, monkeypatch, capsys, src)
    assert "[ERROR] Unclosed block" in err
    # The opening line is shown with a context block.
    assert f'  File "{tmp_path / "case.ezmath"}"' in err
    assert "    *draw(" in err


def test_missing_source_only_prints_first_line(monkeypatch, capsys):
    _, ctx_module = None, _diagnostics
    _diagnostics.unbind_source()
    err = capsys.readouterr().err
    assert err == ""
    _diagnostics.report('Error', 5, 'some message')
    captured = capsys.readouterr().err
    assert captured == "[Error] Line 5: some message\n"


def test_out_of_range_line_only_prints_first_line(tmp_path, monkeypatch, capsys):
    compile_text(tmp_path, monkeypatch, capsys, "A = 1\n")
    _diagnostics.report('Error', 99, 'beyond the end')
    captured = capsys.readouterr().err
    assert captured == "[Error] Line 99: beyond the end\n"


def test_out_of_range_column_omits_caret(tmp_path, monkeypatch, capsys):
    ctx = type("_Ctx", (), {})()
    ctx.source_lines = ["short"]
    ctx.source_name = "short.ezmath"
    _diagnostics.bind_source(ctx)
    try:
        _diagnostics.report('Error', 1, 'bad column', col=99)
    finally:
        _diagnostics.unbind_source()
    err = capsys.readouterr().err
    lines = err.splitlines()
    assert lines[0] == "[Error] Line 1: bad column"
    assert lines[1] == '  File "short.ezmath", line 1'
    assert "column" not in lines[1]
    assert lines[2] == "    short"
    assert len(lines) == 3


def test_no_color_env_disables_ansi(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    compile_text(tmp_path, monkeypatch, capsys, "Need <foo> here\n")
    err = capsys.readouterr().err
    assert "\x1b[" not in err


def test_no_color_empty_env_disables_ansi(tmp_path, monkeypatch, capsys):
    # NO_COLOR set to the empty string still counts as set.
    monkeypatch.setenv("NO_COLOR", "")
    compile_text(tmp_path, monkeypatch, capsys, "Need <foo> here\n")
    err = capsys.readouterr().err
    assert "\x1b[" not in err


def test_tty_gets_ansi_but_first_line_stays_plain(monkeypatch, capsys):
    import io

    class FakeTty(io.StringIO):
        def isatty(self):
            return True

    ctx = type("_Ctx", (), {})()
    ctx.source_lines = ["Tong = <widht> + 2"]
    ctx.source_name = "x.ezmath"
    tty = FakeTty()
    monkeypatch.setattr(sys, "stderr", tty)
    _diagnostics.bind_source(ctx)
    try:
        _diagnostics.report('Error', 1, 'undefined variable <widht>',
                            col=8, end_col=15)
    finally:
        _diagnostics.unbind_source()
    rendered = tty.getvalue()
    assert rendered.splitlines()[0] == "[Error] Line 1: undefined variable <widht>"
    assert "\x1b[" in rendered


def test_source_line_with_error_marker_not_counted(tmp_path, monkeypatch, capsys):
    # The source line contains "[Error]" but produces no hard error;
    # strict mode must stay green (the echoed context line may not be
    # counted as a diagnostic).
    src = "[Error] hello *foobar(1 ; 2)\n"
    err_src = tmp_path / "strict.ezmath"
    err_src.write_text(src, encoding="utf-8")

    stub = type(
        "_TypstStub", (), {"compile": staticmethod(lambda *a, **k: None)}
    )()
    monkeypatch.setattr(_pipeline, "typst", stub)
    result = _pipeline.compile_ezmath(
        str(err_src), str(tmp_path / "strict.pdf"), strict=True)
    assert result is True
    log = capsys.readouterr().out
    assert "error(s)" not in log


def test_diag_counter_only_counts_line_starts():
    import io
    from compiler.pipeline import _DiagCounter

    buf = io.StringIO()
    counter = _DiagCounter(buf)
    counter.write("[Error] Line 1: one\n")
    counter.write("    [Error] indented echo\n")
    counter.write("text with [error] inline and [WARNING] inline\n")
    counter.write("\n[Warning] after blank line\n")
    counter.write("mid-write [ERROR] after content\n")
    assert counter.errors == 1
    assert counter.warnings == 1


def test_diag_counter_counts_marker_after_embedded_newline():
    import io
    from compiler.pipeline import _DiagCounter

    buf = io.StringIO()
    counter = _DiagCounter(buf)
    # Multi-line write: marker right after an embedded newline counts.
    counter.write("some text\n[ERROR] Build failed: x\n")
    assert counter.errors == 1


def test_diag_counter_split_across_writes():
    import io
    from compiler.pipeline import _DiagCounter

    buf = io.StringIO()
    counter = _DiagCounter(buf)
    # print() writes the message, then the trailing newline.
    counter.write("[Warning] Line 1: split writes")
    counter.write("\n")
    assert counter.warnings == 1
    # A new line starting with an indented echo must not count.
    counter.write("    [warning] echo\n")
    assert counter.warnings == 1


def test_block_format_for_unknown_command(tmp_path, monkeypatch, capsys):
    _, err = compile_text(tmp_path, monkeypatch, capsys, "*foobar(1 ; 2)\n")
    lines = err.splitlines()
    assert "[Warning] Line 1: unknown command *foobar(...) — treated as plain text." in lines
    file_line = next(ln for ln in lines if ln.startswith("  File "))
    assert file_line.endswith("line 1, column 1")
    src_line = _echo_line(err, "*foobar")
    assert src_line == "    *foobar(1 ; 2)"


def test_multi_token_line_reports_each_undefined_variable_once(tmp_path, monkeypatch, capsys):
    _, err = compile_text(
        tmp_path, monkeypatch, capsys, "Show <widht> and <wdith>\n")
    # Both tokens are reported, each exactly once.
    assert err.count("undefined variable <widht>") == 1
    assert err.count("undefined variable <wdith>") == 1
    # Two caret lines, one per token.
    assert err.count("^") == len("<widht>") + len("<wdith>")
