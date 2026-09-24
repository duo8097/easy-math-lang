"""Tests against real PyInstaller binaries in ``dist/`` (opt-in, slow).

These tests catch exactly the class of bugs fixed in ``editor/paths.py``:
source runs work, but the frozen editor cannot start the frozen LSP and
cannot invoke the frozen compiler. They run against real onefile/onedir
builds, not mocks.

Prerequisites (Windows, from the repo root):

    powershell -ExecutionPolicy Bypass -File scripts/build_local.ps1
    $env:EASYMATH_RUN_BUILD_TESTS = '1'
    uv run pytest tests/test_packaged_build.py -v

Without the env var (or without ``dist/``) every test skips, so the normal
suite stays fast.
"""

import csv
import json
import os
import queue
import shutil
import subprocess
import threading
import time

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DIST = os.path.join(REPO_ROOT, 'dist')
LANG_EXE = os.path.join(DIST, 'easy-math-lang.exe')
LSP_EXE = os.path.join(DIST, 'easy-math-lsp.exe')
EDITOR_EXE = os.path.join(DIST, 'easy-math-editor', 'easy-math-editor.exe')

RUN = os.environ.get('EASYMATH_RUN_BUILD_TESTS') == '1'

pytestmark = pytest.mark.skipif(
    not RUN, reason='set EASYMATH_RUN_BUILD_TESTS=1 to run packaged-binary tests')


def _require_dist():
    missing = [p for p in (LANG_EXE, LSP_EXE, EDITOR_EXE)
               if not os.path.isfile(p)]
    if missing:
        pytest.skip(
            f'missing build output (run scripts/build_local.ps1): {missing}')


# --------------------------------------------------------------------------
# Compiler binary
# --------------------------------------------------------------------------

def test_compiler_binary_compiles(tmp_path):
    _require_dist()
    probe = subprocess.run([LANG_EXE, '--help'], capture_output=True,
                           text=True, timeout=180)
    assert probe.returncode == 0, probe.stderr[-2000:]
    assert 'easy-math-lang' in probe.stdout.lower()

    src = tmp_path / 'doc.ezmath'
    src.write_text('<a> = 1\nSee <a>\n', encoding='utf-8')
    built = subprocess.run([LANG_EXE, str(src)], capture_output=True,
                           text=True, timeout=300, cwd=str(tmp_path))
    assert built.returncode == 0, built.stderr[-2000:]
    assert (tmp_path / 'doc.pdf').is_file()


# --------------------------------------------------------------------------
# LSP binary (stdio handshake against the frozen server)
# --------------------------------------------------------------------------

class _FrozenClient:
    def __init__(self, argv):
        self.proc = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd=REPO_ROOT)
        self._incoming = queue.Queue()
        self._next_id = 0
        threading.Thread(target=self._read_loop, daemon=True).start()

    def _read_loop(self):
        try:
            while True:
                headers = {}
                while True:
                    line = self.proc.stdout.readline().decode('utf-8')
                    if not line:
                        return
                    line = line.strip()
                    if not line:
                        break
                    key, value = line.split(':', 1)
                    headers[key.strip().lower()] = value.strip()
                body = self.proc.stdout.read(int(headers['content-length']))
                self._incoming.put(json.loads(body.decode('utf-8')))
        except Exception:
            return

    def send(self, obj):
        body = json.dumps(obj).encode('utf-8')
        self.proc.stdin.write(
            f'Content-Length: {len(body)}\r\n\r\n'.encode('utf-8') + body)
        self.proc.stdin.flush()

    def request(self, method, params, timeout=180.0):
        self._next_id += 1
        rid = self._next_id
        self.send({'jsonrpc': '2.0', 'id': rid,
                   'method': method, 'params': params})
        return self.wait_for(lambda m: m.get('id') == rid,
                             f'{method} response', timeout)

    def notify(self, method, params):
        self.send({'jsonrpc': '2.0', 'method': method, 'params': params})

    def wait_for(self, predicate, what, timeout=180.0):
        deadline = time.time() + timeout
        stash = []
        try:
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise TimeoutError(f'timed out waiting for {what}')
                msg = self._incoming.get(timeout=remaining)
                if predicate(msg):
                    return msg
                stash.append(msg)
        finally:
            for msg in stash:
                self._incoming.put(msg)


def test_lsp_binary_full_session():
    """Frozen LSP must serve initialize/diagnostics/shutdown (bundled compiler)."""
    _require_dist()
    client = _FrozenClient([LSP_EXE])
    try:
        init = client.request('initialize', {
            'processId': None, 'capabilities': {}, 'rootUri': None})
        assert init['result'].get('serverInfo', {}).get('name') == 'easy-math-lsp'
        client.notify('initialized', {})

        uri = 'file:///frozen-probe.ezmath'
        client.notify('textDocument/didOpen', {'textDocument': {
            'uri': uri, 'languageId': 'easymath', 'version': 1,
            'text': 'See <oops>\n'}})
        diags = client.wait_for(
            lambda m: m.get('method') == 'textDocument/publishDiagnostics'
            and m.get('params', {}).get('uri') == uri,
            'diagnostics from frozen server')
        assert any('oops' in d['message']
                   for d in diags['params']['diagnostics'])

        resp = client.request('shutdown', None)
        assert resp.get('result') is None
        client.notify('exit', None)
        assert client.proc.wait(timeout=120) == 0
    finally:
        try:
            if client.proc.poll() is None:
                client.proc.kill()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Editor binary: must stay up and spawn the bundled LSP (the reported bug)
# --------------------------------------------------------------------------

def _lsp_pids():
    try:
        out = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq easy-math-lsp.exe',
             '/FO', 'CSV', '/NH'],
            capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return set()
    pids = set()
    for row in csv.reader(out.splitlines()):
        if len(row) >= 2 and row[0].lower() == 'easy-math-lsp.exe':
            try:
                pids.add(int(row[1]))
            except ValueError:
                pass
    return pids


@pytest.fixture()
def installer_layout():
    """Replicate the installer tree inside ``dist/``: ``bin/*.exe``.

    The frozen editor lives in ``dist/easy-math-editor/``, so its
    ``../bin`` lookup probes ``dist/bin``. Copying only the small onefile
    tools there (the big editor onedir stays put) exercises exactly the
    installer-layout branch. Removed again on teardown.
    """
    _require_dist()
    bin_dir = os.path.join(DIST, 'bin')
    os.makedirs(bin_dir, exist_ok=True)
    for exe in (LANG_EXE, LSP_EXE):
        shutil.copy(exe, os.path.join(bin_dir, os.path.basename(exe)))
    yield {'bin_dir': bin_dir,
           'lsp': os.path.join(bin_dir, 'easy-math-lsp.exe')}
    shutil.rmtree(bin_dir, ignore_errors=True)


def test_frozen_editor_spawns_bundled_lsp(installer_layout, tmp_path):
    _require_dist()
    env = dict(os.environ)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env.pop('EASYMATH_LSP_EXE', None)
    env.pop('EASYMATH_COMPILER_EXE', None)

    before = _lsp_pids()
    editor = subprocess.Popen(
        [EDITOR_EXE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        cwd=str(tmp_path), env=env)
    try:
        # 1. The frozen editor must not crash on startup (missing Qt
        #    plugins / modules used to kill it within seconds).
        time.sleep(20)
        assert editor.poll() is None, \
            f'frozen editor exited early with code {editor.poll()}'

        # 2. It must have spawned the bundled LSP next to itself.
        deadline = time.time() + 150
        spawned = set()
        while time.time() < deadline:
            spawned = _lsp_pids() - before
            if spawned:
                break
            assert editor.poll() is None, \
                f'frozen editor died (code {editor.poll()}) while starting LSP'
            time.sleep(5)
        assert spawned, \
            'frozen editor never spawned easy-math-lsp.exe (see editor/paths.py)'
    finally:
        try:
            if editor.poll() is None:
                editor.terminate()
                try:
                    editor.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    editor.kill()
        finally:
            for pid in _lsp_pids() - before:
                try:
                    subprocess.run(['taskkill', '/PID', str(pid), '/F'],
                                   capture_output=True, timeout=60)
                except Exception:
                    pass
