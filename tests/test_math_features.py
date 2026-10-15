"""Math features: number sets, accents, diff, det, set, align."""

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


# --- 3a: number sets ----------------------------------------------------

def test_number_sets_text(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*reals *naturals *integers *rationals *complex\n"
        "*RR *NN *ZZ *QQ *CC\n",
    )
    assert ok is True
    for glyph in ("ℝ", "ℕ", "ℤ", "ℚ", "ℂ"):
        assert glyph in typ
    assert "unknown command" not in err.lower()


def test_number_sets_math_and_cells(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "\\ x *isin *RR \\\n"
        "*matrix(*NN ; 2 | 3 ; *ZZ)\n"
        "*cases(x ; x *isin *reals | 0 ; x *notin *complex)\n",
    )
    assert ok is True
    assert "$x ∈ ℝ$" in typ
    assert "$mat(ℕ, 2; 3, ℤ)$" in typ
    assert "$cases(x & x ∈ ℝ, 0 & x ∉ ℂ)$" in typ
    assert "unknown command" not in err.lower()


def test_number_set_lookalikes(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "real numbers\n*real\n*RRx\n"
    )
    assert ok is True
    assert "real numbers" in typ
    assert "unknown command *real" in err
    # *RRx is a different (unknown) word, not RR + x.
    assert "unknown command *RRx" in err
    assert "ℝ" not in typ


# --- 3b: accents ----------------------------------------------------------

def test_accents(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*hat(x)\n*bar(y)\n*overline(AB)\n*tilde(z)\n*dot(w)\n",
    )
    assert ok is True
    assert "$hat(x)$" in typ
    assert "$bar(y)$" in typ
    assert "$overline(A B)$" in typ
    assert "$tilde(z)$" in typ
    assert "$dot(w)$" in typ
    assert "unknown command" not in err.lower()


def test_accents_nested_vars(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "<a> = x\n*hat(*bar(<a>))\n*tilde(calc(1 + 1))\n",
    )
    assert ok is True
    assert "$hat($bar(x)$)$" in typ or "$hat(bar(x))$" in typ
    assert "$tilde(2)$" in typ


def test_accents_bad_args(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*hat()\n")
    assert ok is True
    assert "empty argument" in err
    assert "$hat" not in typ


def test_accents_lookalikes(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "a hat today\n*hat\n"
    )
    assert ok is True
    assert "a hat today" in typ
    assert "unknown command" not in err.lower()
    assert "$hat" not in typ


# --- 3c: diff -------------------------------------------------------------

def test_diff_basic(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*diff(f ; x)\n"
    )
    assert ok is True
    assert "$frac(dif f, dif x)$" in typ


def test_diff_nth(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*diff(f ; x ; 2)\n"
    )
    assert ok is True
    assert "$frac(dif^2 f, dif x^2)$" in typ


def test_pdiff(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*pdiff(f ; x)\n*pdiff(f ; x ; 3)\n",
    )
    assert ok is True
    assert "$frac(partial f, partial x)$" in typ
    assert "$frac(partial^3 f, partial x^3)$" in typ


def test_diff_vars_calc_comma(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "<a> = 2\n*diff(x^<a> ; x)\n*diff(f, x)\n",
    )
    assert ok is True
    assert "$frac(dif x^2, dif x)$" in typ
    assert "$frac(dif f, dif x)$" in typ


def test_diff_bad_args(tmp_path, monkeypatch, capsys):
    for text in ("*diff(f)\n", "*diff()\n", "*diff(f ; x ; 2 ; y)\n"):
        ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, text)
        assert ok is True, text
        assert "Warning" in err, text
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*diff(f)\n")
    assert "$frac(dif" not in typ


def test_diff_nested_in_frac(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*frac(*diff(f ; x) ; 2)\n"
    )
    assert ok is True
    assert "dif f" in typ and "frac" in typ


# --- 3d: det --------------------------------------------------------------

def test_det_grid(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*det(1 ; 2 | 3 ; 4)\n"
    )
    assert ok is True
    assert '$mat(delim: "|", 1, 2; 3, 4)$' in typ


def test_det_matrix_arg(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*det(*matrix(1 ; 2 | 3 ; 4))\n"
    )
    assert ok is True
    assert '$mat(delim: "|", 1, 2; 3, 4)$' in typ


def test_det_comma_and_vars(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "<a> = 2\n*det(1, <a> | 3, 4)\n*det(*mat(1 ; 2 | 3 ; 4))\n",
    )
    assert ok is True
    assert '$mat(delim: "|", 1, 2; 3, 4)$' in typ


def test_det_ragged_pads_and_empty_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*det(1 ; 2 | 3)\n"
    )
    assert ok is True
    assert "different lengths" in err
    assert '$mat(delim: "|", 1, 2; 3, 0)$' in typ
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*det()\n")
    assert ok is True
    assert "*det(...) is empty" in err
    assert "delim:" not in typ


def test_det_unclosed_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*det(1 ; 2\n"
    )
    assert "unclosed *det(..." in err
    assert "delim:" not in typ


def test_det_in_math(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "\\ *det(1 ; 2 | 3 ; 4) = 0 \\\n"
    )
    assert ok is True
    assert 'mat(delim: "|", 1, 2; 3, 4)' in typ
    assert "unknown command" not in err.lower()


# --- 3e: set --------------------------------------------------------------

def test_set_builder(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*set(x ; x > 0)\n"
    )
    assert ok is True
    assert "$ {x | x > 0} $" in typ


def test_set_listing(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*set(1 ; 2 ; 3)\n*set(a, b)\n*set(x)\n",
    )
    assert ok is True
    assert "$ {1, 2, 3} $" in typ
    assert "$ {a, b} $" in typ
    assert "$ {x} $" in typ


def test_set_thousands_and_quoted_semi(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*set(100,000 ; 2 ; 3)\n"
    )
    assert ok is True
    assert "100\\,000" in typ
    assert "unknown command" not in err.lower()


def test_set_empty_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*set(x ; )\n"
    )
    assert ok is True
    assert "empty argument" in err
    assert "{x |" not in typ


def test_set_lookalikes(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "a set of rules\n*set\n"
    )
    assert ok is True
    assert "a set of rules" in typ
    assert "unknown command" not in err.lower()


# --- 3f: align ------------------------------------------------------------

def test_align_basic(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*align(x = 1 | y = 2)\n"
    )
    assert ok is True
    assert "$ x &= 1 \\ y &= 2 $" in typ


def test_align_block_form(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*align(\n    x = 1\n    y = 2\n)\n",
    )
    assert ok is True
    assert "$ x &= 1 \\ y &= 2 $" in typ


def test_align_no_equals_no_crash(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*align(x = 1 | just words here)\n"
    )
    assert ok is True
    assert "$ x &= 1 \\ j u s t w o r d s h e r e $" in typ
    assert "[Error]" not in err


def test_align_first_equals_wins(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys, "*align(a == b | x = y = z)\n"
    )
    assert ok is True
    assert "$ a &= b \\ x &= y = z $" in typ


def test_align_sum_parens_safe(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "*align(*sum(i = 1 ; n ; i) = x | y = 2)\n",
    )
    assert ok is True
    assert "$ display(sum_(i = 1)^(n) (i)) &= x \\ y &= 2 $" in typ


def test_align_empty_warns(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(tmp_path, monkeypatch, capsys, "*align()\n")
    assert ok is True
    assert "*align(...) is empty" in err


def test_align_vars_calc(tmp_path, monkeypatch, capsys):
    ok, typ, err, out = _compile(
        tmp_path, monkeypatch, capsys,
        "<a> = 2\n*align(x = <a> | y = calc(<a> + 1))\n",
    )
    assert ok is True
    assert "$ x &= 2 \\ y &= 3 $" in typ


# --- LSP + registry --------------------------------------------------------

def test_new_commands_no_lsp_unknown_warning():
    from lsp import analysis
    for snippet in ("*hat(x)\n", "*overline(AB)\n", "*diff(f ; x)\n",
                    "*pdiff(f ; x)\n", "*det(1 ; 2)\n", "*set(x ; y)\n",
                    "*align(x = 1)\n", "x *isin *RR\n"):
        result = analysis.analyze_text(snippet)
        assert not any("unknown command" in d.message.lower()
                       for d in result.diagnostics), snippet


def test_new_commands_lsp_completion_hover():
    from lsp import analysis
    items = analysis.complete("*di", 0, 3)
    labels = {i["label"] for i in items}
    assert {"diff", "pdiff", "det"} <= labels
    hov = analysis.hover("*diff(f ; x)\n", 0, 2)
    assert hov is not None and "Derivative" in hov["value"]
    hov = analysis.hover("*align(x = 1)\n", 0, 2)
    assert hov is not None and "aligned" in hov["value"].lower()
    hov = analysis.hover("x *isin *RR\n", 0, 9)
    assert hov is not None and hov["value"].strip().endswith("ℝ")


def test_new_commands_symbol_registry():
    from editor.symbol_registry import build_source, get_symbol
    assert build_source('hat', {'expression': 'x'}) == '*hat(x)'
    assert build_source('overline', {'expression': 'AB'}) == '*overline(AB)'
    assert build_source(
        'diff', {'function': 'x^2', 'variable': 'x'}) == '*diff(x^2 ; x)'
    assert build_source(
        'diff', {'function': 'x^2', 'variable': 'x', 'order': '2'}) == \
        '*diff(x^2 ; x ; 2)'
    assert build_source(
        'det', {'r1c1': '1', 'r1c2': '2', 'r2c1': '3', 'r2c2': '4'}) == \
        '*det(1 ; 2 | 3 ; 4)'
    assert build_source(
        'set', {'element': 'x', 'condition': 'x > 0'}) == '*set(x ; x > 0)'
    assert build_source(
        'align', {'row1': 'x = 1', 'row2': 'y = 2'}) == '*align(x = 1 | y = 2)'
    assert get_symbol('det').category == 'Math'


def _pdf_text_lines(pdf_path):
    """Extract [(y, text)] lines from a PDF using only the stdlib.

    Decompresses streams, reads each font's ToUnicode CMap
    (beginbfchar/bfrange), and decodes Tj/TJ-shown strings while
    tracking the current font (Tf) and block position (the cm
    translation Typst emits per block) so chunks group into lines.
    Returns [(y, joined_text)] sorted with unpositioned text last.
    """
    import re
    import zlib
    data = open(pdf_path, 'rb').read()
    objs = {}
    for m in re.finditer(rb'(\d+) 0 obj(.*?)endobj', data, re.DOTALL):
        objs[int(m.group(1))] = m.group(2)

    def stream_of(body):
        m = re.search(rb'stream\r?\n(.*?)endstream', body, re.DOTALL)
        if not m:
            return None
        raw = m.group(1)
        if raw.endswith(b'\r\n'):
            raw = raw[:-2]
        elif raw.endswith(b'\n'):
            raw = raw[:-1]
        if b'/FlateDecode' in body:
            try:
                return zlib.decompress(raw)
            except Exception:
                return None
        return raw

    font_cmaps = {}
    for num, body in objs.items():
        if b'/Type/Font' not in body or b'/ToUnicode' not in body:
            continue
        m = re.search(rb'/ToUnicode\s+(\d+) 0 R', body)
        if not m:
            continue
        cmap_raw = stream_of(objs.get(int(m.group(1)), b''))
        if not cmap_raw:
            continue
        cmap = {}
        in_char = in_range = False
        for line in cmap_raw.decode('latin-1').splitlines():
            line = line.strip()
            if 'beginbfchar' in line:
                in_char = True
            elif 'endbfchar' in line:
                in_char = False
            elif 'beginbfrange' in line:
                in_range = True
            elif 'endbfrange' in line:
                in_range = False
            elif in_char:
                parts = line.split()
                if len(parts) >= 2:
                    src = bytes.fromhex(parts[0][1:-1]).decode('latin-1')
                    dst = bytes.fromhex(parts[1][1:-1])
                    cmap[src] = dst.decode('utf-16-be', 'replace')
            elif in_range:
                parts = line.split()
                if len(parts) >= 3:
                    lo = int(parts[0][1:-1], 16)
                    hi = int(parts[1][1:-1], 16)
                    dst = bytes.fromhex(parts[2][1:-1])
                    for i, code in enumerate(range(lo, hi + 1)):
                        key = code.to_bytes(2, 'big').decode('latin-1')
                        cmap[key] = (dst[:2].decode('utf-16-be', 'replace')
                                     if len(dst) == 2
                                     else chr(int.from_bytes(dst, 'big') + i))
        font_cmaps[num] = cmap
    res_to_obj = {}
    for num, body in objs.items():
        start = body.find(b'/Font')
        if start == -1:
            continue
        open_at = body.find(b'<<', start)
        if open_at == -1:
            continue
        depth = 0
        i = open_at
        while i < len(body) - 1:
            if body[i:i + 2] == b'<<':
                depth += 1
                i += 2
            elif body[i:i + 2] == b'>>':
                depth -= 1
                i += 2
                if depth == 0:
                    break
            else:
                i += 1
        for rm in re.finditer(rb'/(f\w+)\s+(\d+) 0 R', body[open_at:i]):
            res_to_obj[rm.group(1).decode()] = int(rm.group(2))

    def unescape(s):
        out = bytearray()
        i = 0
        while i < len(s):
            c = s[i:i + 1]
            if c == b'\\' and i + 1 < len(s):
                n = s[i + 1:i + 2]
                if n in b'nrtbf()\\':
                    out += {b'n': b'\n', b'r': b'\r', b't': b'\t',
                            b'b': b'\b', b'f': b'\f'}.get(n, n)
                    i += 2
                    continue
                mo = re.match(rb'[0-7]{1,3}', s[i + 1:])
                if mo:
                    out.append(int(mo.group(0), 8) & 0xFF)
                    i += 1 + len(mo.group(0))
                    continue
                out += n
                i += 2
                continue
            out += c
            i += 1
        return bytes(out)

    rows = []
    for num, body in objs.items():
        dec = stream_of(body)
        if dec is None or (b'Tj' not in dec and b'TJ' not in dec):
            continue
        font = None
        base_y = None
        for tm in re.finditer(
                rb'/f\w+\s+[\d.]+\s+Tf'
                # Typst positions each block with `q 1 0 0 -1 X Y cm`
                # (Tm itself stays identity), so track the cm Y.
                rb'|1 0 0 -1\s+[\d.\-]+\s+([\d.\-]+)\s+cm'
                rb'|\((?:\\.|[^\\()])*\)\s*Tj'
                rb'|\[(?:[^\[\]]*?)\]\s*TJ', dec):
            tok = tm.group(0)
            if tok.endswith(b'Tf'):
                font = tok.split()[0].decode().lstrip('/')
                continue
            if tok.endswith(b'cm'):
                try:
                    base_y = round(float(tm.group(1)), 1)
                except (TypeError, ValueError):
                    base_y = None
                continue
            cmap = font_cmaps.get(res_to_obj.get(font, -1), {})
            if tok.endswith(b'Tj'):
                raw = unescape(tok[1:tok.rindex(b')')])
            else:
                raw = b''.join(
                    unescape(p[1:-1]) if p.startswith(b'(') else
                    bytes.fromhex(p[1:-1].decode('ascii', 'ignore'))
                    for p in re.findall(rb'\((?:\\.|[^\\()])*\)'
                                        rb'|<[0-9A-Fa-f]+>', tok))
            word = []
            for i in range(0, len(raw) - 1, 2):
                word.append(cmap.get(raw[i:i + 2].decode('latin-1'), ''))
            rows.append((base_y, ''.join(word)))
    lines = {}
    for y, word in rows:
        lines.setdefault(y, []).append(word)
    return sorted(((y, ''.join(words)) for y, words in lines.items()),
                  key=lambda pair: (pair[0] is None, pair[0]))


def test_align_real_pdf_rows(tmp_path):
    """Real Typst compile: both rows on separate lines with = present."""
    pytest.importorskip("typst")
    from compiler.pipeline import compile_ezmath
    src = tmp_path / "al.ezmath"
    out = tmp_path / "al.pdf"
    src.write_text("*align(x = 1 | y = 2)\n", encoding="utf-8")
    assert compile_ezmath(str(src), str(out)) is True
    lines = _pdf_text_lines(str(out))
    text = ' '.join(t for _, t in lines)
    # Typst math italicizes variables (𝑥/𝑦); digits and = stay ASCII.
    assert '=' in text
    assert '1' in text and '2' in text
    # The old broken output printed a literal backslash glyph.
    assert '\\' not in text
    eq_lines = [t for _, t in lines if '=' in t]
    assert len(eq_lines) >= 2
    assert any('1' in t for t in eq_lines)
    assert any('2' in t for t in eq_lines)


def test_real_pdf_compile():
    """Real Typst compile (no stub) for every Phase 3 family."""
    pytest.importorskip("typst")
    import shutil
    import tempfile
    from compiler.pipeline import compile_ezmath
    work = tempfile.mkdtemp(prefix="easymath-mathfeat-")
    try:
        src = os.path.join(work, "m.ezmath")
        out = os.path.join(work, "m.pdf")
        with open(src, "w", encoding="utf-8") as f:
            f.write(
                "x *isin *RR and *naturals\n"
                "*hat(x) + *overline(AB)\n"
                "*diff(f ; x) = *pdiff(f ; x)\n"
                "*det(1 ; 2 | 3 ; 4)\n"
                "*set(x ; x > 0) and *set(1 ; 2 ; 3)\n"
                "*align(x = 1 | y = 2)\n"
            )
        assert compile_ezmath(src, out) is True
        assert os.path.isfile(out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
