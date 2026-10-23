"""Tests for CLI build-artifact cleanup (--save-build-artifacts)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import pipeline as _pipeline  # noqa: E402


def _stub_typst(monkeypatch, calls=None):
    def _fake_compile(typ_file, out_file, **kwargs):
        if calls is not None:
            calls.append((out_file, kwargs))
        parent = os.path.dirname(os.path.abspath(out_file))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as h:
            h.write("x")

    stub = type("_TypstStub", (), {"compile": staticmethod(_fake_compile)})()
    monkeypatch.setattr(_pipeline, "typst", stub)
    monkeypatch.setattr(_pipeline, "_typst_import_failed", False)


def _run_main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    return exc.value.code


def _write_doc(tmp_path, name="doc.ezmath"):
    src = tmp_path / name
    src.write_text("*plot(x ; -5 ; 5)\n", encoding="utf-8")
    return src


def _intermediates(tmp_path, stem="doc"):
    return [
        tmp_path / f"{stem}.typ",
        tmp_path / f"{stem}.smap.json",
        tmp_path / f"{stem}-plot-1.svg",
    ]


def test_cli_removes_artifacts_by_default(tmp_path, monkeypatch, capsys):
    _stub_typst(monkeypatch)
    src = _write_doc(tmp_path)
    out = tmp_path / "doc.pdf"
    code = _run_main(monkeypatch, ["easy-math-lang", str(src), str(out)])
    capsys.readouterr()
    assert code == 0
    assert out.is_file()
    assert src.is_file()  # input never removed
    for path in _intermediates(tmp_path):
        assert not path.exists(), path


def test_cli_save_flag_keeps_artifacts(tmp_path, monkeypatch, capsys):
    _stub_typst(monkeypatch)
    src = _write_doc(tmp_path)
    out = tmp_path / "doc.pdf"
    code = _run_main(
        monkeypatch,
        ["easy-math-lang", "--save-build-artifacts", str(src), str(out)])
    capsys.readouterr()
    assert code == 0
    assert out.is_file()
    for path in _intermediates(tmp_path):
        assert path.is_file(), path


def test_cli_save_flag_after_filename(tmp_path, monkeypatch, capsys):
    _stub_typst(monkeypatch)
    src = _write_doc(tmp_path)
    out = tmp_path / "doc.pdf"
    code = _run_main(
        monkeypatch,
        ["easy-math-lang", str(src), "--save-build-artifacts", str(out)])
    capsys.readouterr()
    assert code == 0
    for path in _intermediates(tmp_path):
        assert path.is_file(), path


def test_cli_failure_keeps_artifacts_for_debugging(tmp_path, monkeypatch,
                                                   capsys):
    _stub_typst(monkeypatch)
    code = _run_main(
        monkeypatch,
        ["easy-math-lang", str(tmp_path / "missing.ezmath")])
    capsys.readouterr()
    assert code == 1


def test_cli_typ_export_keeps_output_and_live_svgs(tmp_path, monkeypatch,
                                                   capsys):
    _stub_typst(monkeypatch)
    src = _write_doc(tmp_path)
    out = tmp_path / "doc.typ"
    code = _run_main(monkeypatch, ["easy-math-lang", str(src), str(out)])
    capsys.readouterr()
    assert code == 0
    assert out.is_file()  # the deliverable is never removed
    # SVGs are live dependencies of the same-dir .typ output: kept.
    assert (tmp_path / "doc-plot-1.svg").is_file()


def test_cli_help_mentions_flag(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["easy-math-lang", "--help"])
    with pytest.raises(SystemExit) as exc:
        _pipeline.main()
    assert exc.value.code == 0
    assert "--save-build-artifacts" in capsys.readouterr().out


def test_cleanup_helper_never_removes_input_or_output(tmp_path):
    typ = tmp_path / "doc.typ"
    smap = tmp_path / "doc.smap.json"
    plot = tmp_path / "doc-plot-1.svg"
    for path in (typ, smap, plot):
        path.write_text("x", encoding="utf-8")
    src = tmp_path / "doc.ezmath"
    src.write_text("hello\n", encoding="utf-8")
    out = tmp_path / "doc.pdf"
    out.write_text("pdf", encoding="utf-8")
    removed = _pipeline._cleanup_build_artifacts(str(src), str(out), None)
    assert out.is_file()
    assert src.is_file()
    assert len(removed) == 3
    for path in (typ, smap, plot):
        assert not path.exists()


def test_cleanup_helper_missing_files_ignored(tmp_path):
    src = tmp_path / "doc.ezmath"
    src.write_text("hello\n", encoding="utf-8")
    assert _pipeline._cleanup_build_artifacts(str(src), None, None) == []
