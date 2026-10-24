"""Regression tests: a MainWindow must be collectable once the caller drops it.

A leaked window keeps ~9 top-level widgets alive for the rest of the process.
Every ``app.setStyleSheet()``/``setPalette()`` (themed once per test) costs
~1.1ms per live top-level widget, so leaked windows compound into an 18x
slowdown for the theme tests when the full suite runs. See
src/editor/main_window.py::_weak_slot for the fix these tests guard.
"""

import gc
import os
import sys

import pytest

PySide6 = pytest.importorskip('PySide6')

from PySide6 import QtWidgets  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import weakref  # noqa: E402

from editor.main_window import MainWindow  # noqa: E402


def _new_window():
    # no_save_prompt: never block on a modal save dialog during teardown.
    return MainWindow(start_lsp=False, no_save_prompt=True)


def test_window_is_collectable_after_drop(qapp):
    win = _new_window()
    win.show()
    qapp.processEvents()
    ref = weakref.ref(win)

    del win
    gc.collect()

    assert ref() is None, (
        "MainWindow leaked: a menu QAction/QShortcut lambda is holding it "
        "alive via a closure over self (see _weak_slot).")


def test_window_is_collectable_without_show(qapp):
    win = _new_window()
    ref = weakref.ref(win)

    del win
    gc.collect()

    assert ref() is None


def test_no_top_level_widget_growth(qapp):
    """Repeated create/drop must not accumulate top-level widgets.

    Each live top-level widget taxes every app.setStyleSheet() call, so growth
    here is exactly the slowdown the leak caused.
    """
    def top_count():
        return sum(1 for w in qapp.allWidgets() if w.parent() is None)

    baseline = None
    for _ in range(3):
        win = _new_window()
        win.show()
        qapp.processEvents()
        del win
        gc.collect()
        n = top_count()
        if baseline is None:
            baseline = n
        # No monotonic growth beyond the very first window's own footprint.
        assert n <= baseline, f"top-level widgets grew {baseline} -> {n}"
