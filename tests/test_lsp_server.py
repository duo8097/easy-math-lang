"""End-to-end LSP tests over stdio (real server subprocess, no GUI).

Covers: initialize, didOpen (+diagnostics), completion, hover,
documentSymbol, didChange updates, shutdown/exit.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time

import pytest

pygls = pytest.importorskip('pygls')

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
SRC_DIR = os.path.abspath(os.path.join(REPO_ROOT, "src"))
URI = 'file:///lsp-e2e.ezmath'

VALID_DOC = "*define(width = 10)\n<area> = calc(<width> * 2)\nArea: <area>\n"


class LSPClient:
    """Minimal Content-Length framed JSON-RPC client."""

    def __init__(self):
        env = dict(os.environ)
        env['PYTHONPATH'] = SRC_DIR + os.pathsep + env.get('PYTHONPATH', '')
        self.proc = subprocess.Popen(
            [sys.executable, '-m', 'easy_math_lang.lsp'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env, cwd=REPO_ROOT,
        )
        self._incoming = queue.Queue()
        self._next_id = 0
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

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
        except Exception:  # noqa: BLE001 - reader thread must not crash tests
            return

    def send(self, obj):
        body = json.dumps(obj).encode('utf-8')
        self.proc.stdin.write(
            f'Content-Length: {len(body)}\r\n\r\n'.encode('utf-8') + body
        )
        self.proc.stdin.flush()

    def request(self, method, params):
        self._next_id += 1
        rid = self._next_id
        self.send({'jsonrpc': '2.0', 'id': rid, 'method': method, 'params': params})
        return self.wait_for(lambda m: m.get('id') == rid, what=f'{method} response')

    def notify(self, method, params):
        self.send({'jsonrpc': '2.0', 'method': method, 'params': params})

    def wait_for(self, predicate, what='message', timeout=25.0):
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

    def wait_for_diagnostics(self, uri, timeout=25.0):
        return self.wait_for(
            lambda m: m.get('method') == 'textDocument/publishDiagnostics'
            and m.get('params', {}).get('uri') == uri,
            what=f'diagnostics for {uri}', timeout=timeout,
        )

    def stop(self):
        try:
            if self.proc.poll() is None:
                self.proc.terminate()
                self.proc.wait(timeout=10)
        except Exception:  # noqa: BLE001 - best effort cleanup
            pass


@pytest.fixture(scope='module')
def client():
    cli = LSPClient()
    # Handshake here (not in a test) so every test works standalone,
    # including when a subset is selected with -k.
    init = cli.request('initialize', {
        'processId': None, 'capabilities': {}, 'rootUri': None,
    })
    cli.init_response = init
    cli.notify('initialized', {})
    yield cli
    cli.stop()


def _labels(completion_result):
    result = completion_result['result']
    items = result['items'] if isinstance(result, dict) else result
    return [item['label'] for item in items]


def test_initialize(client):
    caps = client.init_response['result']['capabilities']
    assert client.init_response['result'].get('serverInfo', {}).get('name') == 'easy-math-lsp'
    assert 'completionProvider' in caps
    assert 'hoverProvider' in caps
    assert 'documentSymbolProvider' in caps


def test_open_valid_document_no_diagnostics(client):
    client.notify('textDocument/didOpen', {'textDocument': {
        'uri': URI, 'languageId': 'easymath', 'version': 1, 'text': VALID_DOC,
    }})
    msg = client.wait_for_diagnostics(URI)
    assert msg['params']['diagnostics'] == []


def test_completion_of_defined_variable(client):
    resp = client.request('textDocument/completion', {
        'textDocument': {'uri': URI},
        'position': {'line': 2, 'character': len('Area: <area')},
    })
    labels = _labels(resp)
    assert 'width' in labels
    assert 'area' in labels


def test_hover_variable_value(client):
    line = '<area> = calc(<width> * 2)'
    resp = client.request('textDocument/hover', {
        'textDocument': {'uri': URI},
        'position': {'line': 1, 'character': line.index('width') + 1},
    })
    assert resp['result'] is not None
    assert 'width' in resp['result']['contents']['value']
    assert '10' in resp['result']['contents']['value']


def test_document_symbols(client):
    resp = client.request('textDocument/documentSymbol', {
        'textDocument': {'uri': URI},
    })
    names = {s['name'] for s in resp['result']}
    assert {'width', 'area'} <= names


def test_change_updates_diagnostics(client):
    bad = VALID_DOC + "Broken <oops> here\n"
    client.notify('textDocument/didChange', {'textDocument': {'uri': URI, 'version': 2},
                                             'contentChanges': [{'text': bad}]})
    msg = client.wait_for(
        lambda m: m.get('method') == 'textDocument/publishDiagnostics'
        and m.get('params', {}).get('uri') == URI
        and any('oops' in d['message'] for d in m['params']['diagnostics']),
        what='updated diagnostics mentioning oops',
    )
    assert any(d['message'].startswith('Undefined variable')
               for d in msg['params']['diagnostics'])


def test_multiple_documents_independent(client):
    uri_a, uri_b = 'file:///multiA.ezmath', 'file:///multiB.ezmath'
    client.notify('textDocument/didOpen', {'textDocument': {
        'uri': uri_a, 'languageId': 'easymath', 'version': 1,
        'text': '<a> = 1\nSee <a>\n'}})
    client.notify('textDocument/didOpen', {'textDocument': {
        'uri': uri_b, 'languageId': 'easymath', 'version': 1,
        'text': 'See <oops>\n'}})
    assert client.wait_for_diagnostics(uri_a)['params']['diagnostics'] == []
    diags_b = client.wait_for_diagnostics(uri_b)['params']['diagnostics']
    assert any('oops' in d['message'] for d in diags_b)

    client.notify('textDocument/didChange', {
        'textDocument': {'uri': uri_a, 'version': 2},
        'contentChanges': [{'text': '<a> = 1\nSee <a> and <bad>\n'}]})
    refreshed = client.wait_for(
        lambda m: m.get('method') == 'textDocument/publishDiagnostics'
        and m.get('params', {}).get('uri') == uri_a
        and any('bad' in d['message'] for d in m['params']['diagnostics']),
        what='refreshed diagnostics for A')
    assert refreshed is not None

    resp = client.request('textDocument/completion', {
        'textDocument': {'uri': uri_b},
        'position': {'line': 0, 'character': 4}})
    result = resp['result']
    labels = [i['label'] for i in (result['items'] if isinstance(result, dict) else result)]
    assert 'a' not in labels  # no cross-document leakage

    client.notify('textDocument/didClose', {'textDocument': {'uri': uri_a}})
    cleared = client.wait_for(
        lambda m: m.get('method') == 'textDocument/publishDiagnostics'
        and m.get('params', {}).get('uri') == uri_a
        and m['params']['diagnostics'] == [],
        what='cleared diagnostics for A')
    assert cleared is not None


def test_unsupported_file_gets_no_intelligence(client):
    uri = 'file:///plain.txt'
    client.notify('textDocument/didOpen', {'textDocument': {
        'uri': uri, 'languageId': 'plaintext', 'version': 1,
        'text': 'See <oops>\n'}})
    assert client.wait_for_diagnostics(uri)['params']['diagnostics'] == []
    resp = client.request('textDocument/completion', {
        'textDocument': {'uri': uri},
        'position': {'line': 0, 'character': 1}})
    result = resp['result']
    items = result['items'] if isinstance(result, dict) else result
    assert items == []


def test_emoji_positions_use_utf16(client):
    uri = 'file:///emoji.ezmath'
    client.notify('textDocument/didOpen', {'textDocument': {
        'uri': uri, 'languageId': 'easymath', 'version': 1,
        'text': '😀 <oops>\n'}})
    msg = client.wait_for_diagnostics(uri)
    diags = msg['params']['diagnostics']
    assert len(diags) == 1
    # 😀 is one code point but two UTF-16 units (0-1), space is 2,
    # so <oops> starts at UTF-16 offset 3.
    assert diags[0]['range']['start'] == {'line': 0, 'character': 3}
    assert diags[0]['range']['end'] == {'line': 0, 'character': 9}


def test_shutdown_and_exit(client):
    resp = client.request('shutdown', None)
    assert resp.get('result') is None
    assert 'error' not in resp
    client.notify('exit', None)
    assert client.proc.wait(timeout=20) == 0
