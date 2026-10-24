# Optimize test-suite runtime

## Goal

Cut wall-clock time of `uv run pytest tests/` (866 tests, **~15s warm / ~21s cold**) while keeping
every test's assertions intact.

## Measured baseline

| Run | Wall |
|---|---|
| Cold (first, fills matplotlib/typst font caches) | 21.03s |
| Warm | 14.66s |
| Sum of per-test `call` time | 10.96s |
| Sum of `setup` time | 1.33s |
| Collection (`--collect-only`) | 1.42s |

Slowest files (warm, summed `call`):

| File | Time | Why |
|---|---|---|
| `tests/test_editor_theme.py` | 2.51s | app-wide repolish over an accumulated widget set |
| `tests/test_preview_hit.py` | 2.38s | real Typst compiles + per-pixel `QImage.pixelColor()` scans |
| `tests/test_editor_gui.py` | 2.32s | same repolish cost + 2 real-LSP tests |
| `tests/test_audit_regressions.py` | 0.83s | 1 real Typst+matplotlib compile (4.67s cold) |
| `tests/test_editor_lspclient.py` | 0.77s | real `easy-math-lsp` subprocess |

The suite is **serial** — 12 cores available, no `pytest-xdist`.

## Root cause 1 — every `MainWindow` leaks, so repolish cost grows without bound

Reproduced and quantified:

- 100% of `MainWindow` instances survive `del w; gc.collect()`
  (weakref probe: `15/15 leaked`).
- Each window contributes **9 permanent top-level widgets**
  (`{'MainWindow': 1, 'QMenu': 7, 'QFrame': 1}`) that are never destroyed.
- `app.setStyleSheet()` / `app.setPalette()` in `MainWindow._apply_theme`
  (`src/editor/main_window.py:1573`) cost **~1.1ms per live top-level widget**,
  i.e. the cost of *every* theme application grows linearly with the number of
  windows created earlier in the session.
- Across `test_editor_gui.py + test_editor_theme.py` alone:
  `app.setStyleSheet` = **1.68s** of the 3.54s spent in `_apply_theme`.

**Cross-test pollution is provable:** `test_editor_theme.py` runs in **0.39s**
alone but **2.51s** in the full suite — the same tests, 6x slower, because
`test_editor_font.py`/`test_editor_gui.py` ran first (alphabetical order) and
left 300+ top-level widgets behind. Individual theme tests: **0.03s alone →
0.53–0.84s in-suite (18x)**.

Verified *not* the cause: `build_palette` and `stylesheet()` are ~0.000s;
`app.setPalette` is 0.005s; Qt already short-circuits an **identical**
stylesheet string at 0.000s. So the 42/49 "redundant" theme applications are
cheap — the cost is entirely the *genuine* toggles paying O(accumulated widgets).

**Confirmed holders** (gc closure scan of a live leaked window):

```
9x  MainWindow._create_menus.<locals>.<lambda>  (function)
```

All 9 are self-capturing lambdas created in `MainWindow._create_menus`
(`src/editor/main_window.py:1334`): the export loop at `:1367`
(`lambda _checked=False, f=_fmt: self._export_as(f)`), zoom at `:1425`/`:1429`,
shortcuts at `:1462`/`:1465`, plus toolbar/palette entries. The chain is
`QAction (C++ child of the window's widget tree) → signal → lambda → cell →
MainWindow`, a cycle spanning C++ and Python that Python's cyclic GC cannot see
through.

Caveat for implementation: `triggered.disconnect()`, `QMenu.clear()`,
`win.deleteLater()` + `sendPostedEvents(None, DeferredDelete)`, and
`WA_DeleteOnClose` were each tried in isolation and did **not** reclaim the
windows (measured). Breaking the cycle must therefore be validated empirically
against the new regression test rather than assumed — see Change 1.

## Root cause 2 — serial execution + fixed-path test

- No `pytest-xdist`; 12 cores idle.
- `tests/test_editor_theme.py:31` writes a **hardcoded**
  `%TEMP%/easymath-theme-test.ini` (`RUNNER_TEMP` on CI) — two workers would
  clobber each other. Must move to `tmp_path` before parallelizing.
- `tests/test_packaged_build.py` mutates repo `dist/` and is already
  opt-in/skipped; keep it out of the parallel pool.

## Root cause 3 — per-pixel `pixelColor()` in the preview tests

`_render_bboxes` / `_is_text_pixel`
(`tests/test_preview_hit.py:178-222`) call `QImage.pixelColor(x, y)` in Python
loops. Measured on a representative 1190×1683 page:

| Method | Time |
|---|---|
| `pixelColor()` per pixel | **0.71s** |
| `constBits()` byte buffer | **0.23s** (3x faster, identical result: 12122 dark samples) |

`test_preview_hit.py` totals 2.38s; these scans run several times
(`test_end_to_end_ctrl_click_navigates`, `test_end_to_end_zoom_scrolled_multipage`,
`test_panel_center_agreement`).

---

## Changes

### 1. Break the `MainWindow` reference cycle — `src/editor/main_window.py`

Add a small helper on `MainWindow` that binds a slot without capturing `self`
strongly:

```python
import weakref

def _weak_slot(self, name, *args, **kwargs):
    """Return a callable invoking self.<name>(*args, **kwargs) that does not
    keep this window alive (breaks QAction -> lambda -> self cycles)."""
    ref = weakref.ref(self)
    def call(*a, **k):
        obj = ref()
        if obj is None:
            return None
        return getattr(obj, name)(*args, *a, **kwargs, **k)
    return call
```

`weakref.ref(MainWindow())` is confirmed to work (probe: `weakref supported: True`).

Rewrite the 9 self-capturing lambdas in `_create_menus` to use it:

- `:1367` export loop → `self._weak_slot('_export_as', f)`
- `:1425` / `:1429` zoom → `self._weak_slot('_zoom', 1)` / `(1)` `-1`
- `:1462` / `:1465` find shortcuts → `self._weak_slot('_find_again', 1)` / `(-1)`
- remaining `_create_menus` lambdas (toolbar/palette/save/save-as/export entries)

Leave the non-menu lambdas at `:610`, `:793-829`, `:1017` alone initially —
they are not in the confirmed holder set. If the regression test (Change 2)
still fails, extend to `_palette_commands` (`:793-829`) and `_refresh_recent_menu`
(`:1017`), which are the next-most-likely edges.

**Acceptance:** after `w.close(); del w; gc.collect()`, the weakref is dead and
`app.topLevelWidgets()` does not grow. Iterate on the candidate edges above
until this holds — do not consider the change done on a code-reading argument.

### 2. Add a leak regression test — `tests/test_main_window_leak.py` (new)

```python
"""Closed MainWindows must be collectable (app-wide repolish is O(live widgets))."""
import gc, os, sys, weakref
import pytest
PySide6 = pytest.importorskip('PySide6')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from PySide6 import QtWidgets

@pytest.fixture(scope='module')
def app(qapp):
    return QtWidgets.QApplication.instance()

def test_closed_window_is_collected(app):
    from editor.main_window import MainWindow
    before = len(app.topLevelWidgets())
    ref = None
    w = MainWindow(start_lsp=False, no_save_prompt=True)
    ref = weakref.ref(w)
    w.show(); app.processEvents()
    w.editor.setPlainText('<a> = 1\n')
    w.close(); app.processEvents()
    del w; gc.collect(); app.processEvents()
    assert ref() is None, 'closed MainWindow still referenced (leak)'
    assert len(app.topLevelWidgets()) <= before + 1
```

This is the gate for Change 1.

### 3. Add `pytest-xdist` and parallelize

- `uv add --group dev pytest-xdist` (resolves clean: `pytest-xdist==3.8.0`,
  `execnet==2.1.2`).
- Add to `pyproject.toml`:

  ```toml
  [tool.pytest.ini_options]
  addopts = "-n auto --dist loadfile"
  ```

  `--dist loadfile` keeps each file on one worker, preserving intra-file
  ordering assumptions (e.g. `test_editor_theme.py`'s `window` fixture state)
  and avoiding cross-worker chatter.
- `.github/workflows/tests.yml:41` needs no edit — `addopts` applies.

### 4. Make fixed-path tests worker-safe

- `tests/test_editor_theme.py:29-40` `test_settings_roundtrip`: replace the
  hardcoded `RUNNER_TEMP`/`%TEMP%` path with `tmp_path / 'easymath-theme-test.ini'`.
- Sweep for any other non-`tmp_path` writes before enabling `-n auto`
  (grep for `gettempdir|expandvars|RUNNER_TEMP|mkdtemp`).
  Known-good: `mkdtemp(prefix=...)` calls in `test_preview_hit`,
  `test_text_commands`, `test_new_commands`, `test_vectors`,
  `test_math_features`, `test_compiler` all use unique prefixes → safe.
- Keep `tests/test_packaged_build.py` out of the parallel pool (it already
  self-skips without `EASYMATH_RUN_BUILD_TESTS=1`; if it is ever run with that
  flag, run it as `pytest -n0 tests/test_packaged_build.py`).

### 5. Speed up `_render_bboxes` — `tests/test_preview_hit.py:178-222`

Replace per-pixel `img.pixelColor(x, y)` with a one-time raw-buffer read:

```python
img = img.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
buf = bytes(img.constBits()); stride = img.bytesPerLine()

def _is_text_pixel(buf, stride, x, y):          # same thresholds as today
    i = y * stride + x * 4
    r, g, b, a = buf[i], buf[i+1], buf[i+2], buf[i+3]
    return a > 128 and (0.299*r + 0.587*g + 0.114*b) < 306
```

`lightness() < 120` on a near-grayscale black-on-white render maps to
`0.299R+0.587G+0.114B < 306`; the probe returned the **identical** count
(12122) both ways. Keep the existing cluster/box logic untouched — only the
pixel predicate changes. Validate against every `_render_bboxes` assertion in
the file.

### 6. Optional (do only if the above still misses target)

- `tests/test_audit_regressions.py:86` `test_editor_typ_export_retains_diagram_assets`
  is **4.67s cold / 0.44s warm** — the one-time matplotlib+Typst font-cache
  build. A session-scoped warmup fixture would just relocate the cost; prefer
  leaving it. Not worth chasing unless CI cold runs matter.

---

## Verification

1. `uv run pytest tests/ -q` — all 866 tests pass (plus the new leak test).
2. `uv run pytest tests/ -q --durations=15` — confirm:
   - `test_editor_theme.py` drops toward its standalone ~0.4s;
   - theme tests no longer show 0.5–0.8s outliers;
   - `test_preview_hit.py` end-to-end tests shrink.
3. Compare wall time cold and warm against the baseline table above; report both.
4. `uv run pytest tests/ -q` twice in a row — no state leaks between runs.
5. Run the new leak test **before** applying Change 1 (it must fail) and after
   (it must pass) — otherwise it isn't testing anything.

## Risks

| Risk | Mitigation |
|---|---|
| Weakref slots change menu behavior (window already closed → slot no-op) | Original behavior was a crash/leak anyway; `call` returns `None` instead of resurrecting a dead object. Existing GUI tests exercise every menu entry (`test_toolbar_has_main_actions`, `test_palette_lists_theme_command`, export tests). |
| `-n auto` exposes latent ordering dependencies | `--dist loadfile` keeps files intact; run the full suite repeatedly to shake out flakes. |
| xdist + Qt offscreen: one `QApplication` per worker | Already how `tests/conftest.py:11` works (session-scoped `qapp`); each worker is its own process. |
| xdist + matplotlib font-cache race | Matplotlib locks its cache dir; first cold parallel run may be slower. Measure cold *and* warm. |
| `_render_bboxes` threshold change alters hit-testing | Proven count-identical on a representative page; all existing `_render_bboxes`/`_overlap_area` assertions act as the check. |

## Expected outcome

| | Now | Target |
|---|---|---|
| Warm serial | 14.66s | ~10s (leak fix + bbox speedup) |
| With `-n auto` (12 cores) | — | **~3–5s** |
| Cold | 21.03s | ~8–12s |

## Out of scope

- Rewriting the GUI tests to share a module-scoped `MainWindow` (rejected in
  favor of fixing the product leak + regression test).
- `tests/test_packaged_build.py` opt-in binary tests.
- CI matrix / workflow restructuring beyond what `addopts` gives for free.
