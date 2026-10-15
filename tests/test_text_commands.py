"""Text/document commands: styling, page breaks, images."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import pipeline as _pipeline


def _compile(tmp_path, monkeypatch, capsys, text, name="case"):
    src = tmp_path / f"{name}.ezmath"
    src.write_text(text, encoding="utf-8")
    stub = type(
        "_TypstStub", (), {"compile": staticmethod(lambda *a, **k: None)}
    )()
    monkeypatch.setattr(_pipeline, "typst", stub)
    monkeypatch.setattr(_pipeline, "_typst_import_failed", False)
    ok = _pipeline.compile_ezmath(str(src), str(tmp_path / f"{name}.pdf"))
    captured = capsys.readouterr()
    typ = (tmp_path / f"{name}.typ").read_text(encoding="utf-8")
    return ok, typ, captured.err, captured.out


def _write_png(path):
    import struct
    import zlib

    def chunk(tag, data):
        block = tag + data
        return (struct.pack('>I', len(data)) + block
                + struct.pack('>I', zlib.crc32(block) & 0xffffffff))

    ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b'\x00\xff\x00\x00')
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
                     + chunk(b'IDAT', idat) + chunk(b'IEND', b''))


# --- 2a: styling ------------------------------------------------------

def test_bold_italic_underline(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*bold(hi)\n*italic(ho)\n*underline(yo)\n",
    )
    assert ok is True
    assert "#strong[hi]" in typ
    assert "#emph[ho]" in typ
    assert "#underline[yo]" in typ
    assert "unknown command" not in err.lower()


def test_styling_aliases(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*b(hi)\n*i(ho)\n*u(yo)\n"
    )
    assert ok is True
    assert "#strong[hi]" in typ
    assert "#emph[ho]" in typ
    assert "#underline[yo]" in typ
    assert "unknown command" not in err.lower()


def test_styling_nesting(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*bold(a *italic(b) c)\n"
    )
    assert ok is True
    assert "#strong[a #emph[b] c]" in typ


def test_styling_vars_and_calc(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "<v> = 5\n*bold(value is <v> and calc(<v> * 2))\n",
    )
    assert ok is True
    assert "#strong[value is 5 and 10]" in typ


def test_styling_math_inside(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*bold(*frac(1 ; 2))\n"
    )
    assert ok is True
    assert "#strong[$frac(1, 2)$]" in typ


def test_styling_escapes_user_text(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*bold(2 * 3 and x_1)\n"
    )
    assert ok is True
    # Same rules as body text: * is escaped, x_1 is a subscript.
    assert "#strong[2 \\* 3 and $x_1$]" in typ


def test_styling_commas_semicolons_literal(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*bold(yes, really ; truly)\n"
    )
    assert ok is True
    assert "#strong[yes, really ; truly]" in typ


def test_styling_empty_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*bold()\n")
    assert ok is True
    assert "*bold(...) is empty" in err
    assert "#strong" not in typ


def test_styling_unclosed_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*bold(oops\n"
    )
    assert ok is True
    assert "unclosed *bold(..." in err
    assert "#strong" not in typ


def test_styling_inside_inline_math(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "\\ *bold(x) + 1 \\\n"
    )
    assert ok is True
    assert "#strong[x]" in typ
    assert "unknown command" not in err.lower()


def test_styling_inside_matrix_cell(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*matrix(*bold(a) ; b | c ; d)\n"
    )
    assert ok is True
    assert "#strong[a]" in typ
    assert "unknown command" not in err.lower()


def test_styling_lookalikes_untouched(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "a bold move\n*bold\n*p(*bold(x))\n",
    )
    assert ok is True
    assert "a bold move" in typ
    assert "unknown command" not in err.lower()
    assert "#strong" not in typ


def test_styling_hints(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*blod(x)\n"
    )
    assert "Did you mean '*bold(...)'?" in err
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*textbf(x)\n"
    )
    assert "Did you mean '*bold(...)'?" in err


# --- 2b: page breaks ---------------------------------------------------

def test_newpage_forms(tmp_path, monkeypatch, capsys):
    for text in ("*newpage\n", "*newpage()\n", "*pagebreak\n",
                 "*pagebreak()\n", "a *newpage b\n"):
        ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, text)
        assert ok is True, text
        assert "#pagebreak()" in typ, text
        assert "unknown command" not in err.lower(), text


def test_newpage_extra_args_warn(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*newpage(oops)\n"
    )
    assert ok is True
    assert "takes no arguments" in err
    assert "#pagebreak()" in typ


def test_newpage_in_math_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "\\ *newpage \\\n"
    )
    assert ok is True
    assert "text mode" in err
    assert "#pagebreak()" not in typ


def test_newpage_hint(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*newpag\n"
    )
    assert "unknown command *newpag" in err
    assert "Did you mean '*newpage(...)'?" in err


# --- 2c: images --------------------------------------------------------

def test_image_basic(tmp_path, monkeypatch, capsys):
    _write_png(tmp_path / "pic.png")
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*image(pic.png)\n"
    )
    assert ok is True
    assert '#image("pic.png")' in typ
    assert "[Image Error" not in typ
    assert "[Error]" not in err


def test_image_widths(tmp_path, monkeypatch, capsys):
    _write_png(tmp_path / "pic.png")
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*image(pic.png ; 50%)\n*image(pic.png ; 6cm)\n"
        "*image(pic.png, 30%)\n*image(pic.png ; 50)\n",
    )
    assert ok is True
    assert '#image("pic.png", width: 50%)' in typ
    assert '#image("pic.png", width: 6cm)' in typ
    assert '#image("pic.png", width: 30%)' in typ
    assert "[Image Error" not in typ


def test_image_subdir_relocatable(tmp_path, monkeypatch, capsys):
    (tmp_path / "imgs").mkdir()
    _write_png(tmp_path / "imgs" / "a.png")
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*image(imgs/a.png ; 50%)\n"
    )
    assert ok is True
    assert '#image("imgs/a.png", width: 50%)' in typ
    assert str(tmp_path) not in typ


def test_image_missing_is_error_but_builds(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "before\n*image(nope.png)\nafter\n"
    )
    assert ok is True  # build continues
    assert "[Error] Line 2: *image(...) file not found" in err
    assert "[Image Error:" in typ
    assert "before" in typ and "after" in typ


def test_image_missing_fails_strict(tmp_path, monkeypatch, capsys):
    from compiler import compile_ezmath
    src = tmp_path / "case.ezmath"
    src.write_text("*image(nope.png)\n", encoding="utf-8")
    stub = type(
        "_TypstStub", (), {"compile": staticmethod(lambda *a, **k: None)}
    )()
    monkeypatch.setattr(_pipeline, "typst", stub)
    monkeypatch.setattr(_pipeline, "_typst_import_failed", False)
    assert compile_ezmath(str(src), str(tmp_path / "case.pdf")) is True
    capsys.readouterr()
    assert compile_ezmath(
        str(src), str(tmp_path / "case.pdf"), strict=True) is False


def test_image_bad_width_and_arity(tmp_path, monkeypatch, capsys):
    _write_png(tmp_path / "pic.png")
    for text in ("*image(pic.png ; abc)\n", "*image()\n",
                 "*image(a ; b ; c)\n"):
        ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, text)
        assert ok is True, text
        assert "[Error]" in err, text
        assert "[Image Error:" in typ, text
        assert "#image(" not in typ, text


def test_image_unclosed_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*image(pic.png\n"
    )
    assert "unclosed *image(..." in err
    assert "#image(" not in typ


def test_image_in_math_and_matrix_warn(tmp_path, monkeypatch, capsys):
    _write_png(tmp_path / "pic.png")
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "\\ *image(pic.png) \\\n"
    )
    assert ok is True
    assert "text mode" in err
    assert "#image(" not in typ
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*matrix(*image(pic.png) ; 2)\n"
    )
    assert ok is True
    assert "text mode" in err


def test_image_vars_and_thousands(tmp_path, monkeypatch, capsys):
    _write_png(tmp_path / "pic.png")
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*define(pic = pic.png)\n*image(<pic> ; calc(25 * 2))\n",
    )
    assert ok is True
    assert '#image("pic.png", width: 50%)' in typ


def test_image_lookalikes_untouched(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "an image here\n*image\n"
    )
    assert ok is True
    assert "unknown command" not in err.lower()
    assert "#image(" not in typ


def test_image_typ_export_carries_file(tmp_path, monkeypatch, capsys):
    _write_png(tmp_path / "pic.png")
    src = tmp_path / "case.ezmath"
    src.write_text("*image(pic.png ; 50%)\n", encoding="utf-8")
    stub = type(
        "_TypstStub", (), {"compile": staticmethod(lambda *a, **k: None)}
    )()
    monkeypatch.setattr(_pipeline, "typst", stub)
    monkeypatch.setattr(_pipeline, "_typst_import_failed", False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    ok = _pipeline.compile_ezmath(str(src), str(out_dir / "case.typ"))
    captured = capsys.readouterr()
    assert ok is True
    assert (out_dir / "pic.png").is_file()
    assert "[Error]" not in captured.err


# --- LSP ---------------------------------------------------------------

def test_new_commands_no_lsp_unknown_warning():
    from lsp import analysis
    for snippet in ("*bold(x)\n", "*b(x)\n", "*italic(x)\n", "*u(x)\n",
                    "*underline(x)\n", "*newpage\n", "*newpage()\n",
                    "*pagebreak\n", "*image(pic.png)\n"):
        result = analysis.analyze_text(snippet)
        assert not any("unknown command" in d.message.lower()
                       for d in result.diagnostics), snippet


def test_new_commands_lsp_completion_hover():
    from lsp import analysis
    items = analysis.complete("*bol", 0, 4)
    assert any(i["label"] == "bold" for i in items)
    hov = analysis.hover("*bold(x)\n", 0, 2)
    assert hov is not None and "Bold" in hov["value"]
    hov = analysis.hover("*image(pic.png)\n", 0, 2)
    assert hov is not None and "Image" in hov["value"]


def test_new_commands_symbol_registry():
    from editor.symbol_registry import build_source, get_symbol
    assert build_source('bold', {'text': 'hi'}) == '*bold(hi)'
    assert build_source('italic', {'text': 'x'}) == '*italic(x)'
    assert build_source('underline', {'text': 'x'}) == '*underline(x)'
    assert build_source('newpage', {}) == '*newpage()'
    assert build_source('image', {'path': 'a.png'}) == '*image(a.png)'
    assert build_source(
        'image', {'path': 'a.png', 'width': '50%'}) == '*image(a.png ; 50%)'
    for name in ('bold', 'italic', 'underline', 'newpage', 'image'):
        assert get_symbol(name).category == 'Text'


def test_real_pdf_compile():
    """Real Typst compile (no stub) for styling, page break and image."""
    pytest.importorskip("typst")
    import shutil
    import tempfile
    from compiler.pipeline import compile_ezmath
    work = tempfile.mkdtemp(prefix="easymath-textcmd-")
    try:
        src = os.path.join(work, "t.ezmath")
        out = os.path.join(work, "t.pdf")
        _write_png_path = os.path.join(work, "pic.png")
        import struct
        import zlib

        def chunk(tag, data):
            block = tag + data
            return (struct.pack('>I', len(data)) + block
                    + struct.pack('>I', zlib.crc32(block) & 0xffffffff))

        ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
        idat = zlib.compress(b'\x00\xff\x00\x00')
        with open(_write_png_path, 'wb') as h:
            h.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
                    + chunk(b'IDAT', idat) + chunk(b'IEND', b''))
        with open(src, "w", encoding="utf-8") as f:
            f.write(
                "*bold(hi) and *italic(ho) and *u(yo)\n"
                "*bold(a *italic(b) c)\n"
                "*newpage\n"
                "after break: *image(pic.png ; 50%)\n"
            )
        assert compile_ezmath(src, out) is True
        assert os.path.isfile(out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
