"""LspClient tests against the real easy-math-lsp (no widgets).

Uses QCoreApplication (no display needed) with local QEventLoops.
"""

import os
import sys

import pytest

PySide6 = pytest.importorskip('PySide6')

from PySide6 import QtCore  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from editor.lsp_client import (  # noqa: E402
    LspClient,
    default_server_command,
)

URI = 'file:///editor-client-test.ezmath'


def pump_until(predicate, what='condition', timeout_ms=20000):
    """Run a local event loop until predicate() or timeout."""
    loop = QtCore.QEventLoop()
    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)
    poll = QtCore.QTimer()
    poll.timeout.connect(lambda: predicate() and loop.quit())
    poll.start(25)
    loop.exec()
    poll.stop()
    timer.stop()
    assert predicate(), f'timed out waiting for {what}'


def test_full_session(qapp):
    client = LspClient(default_server_command())
    try:
        started = {}
        client.server_started.connect(lambda: started.update(yes=True))
        assert client.start()
        pump_until(lambda: 'yes' in started, 'server start')
        state = {}

        client.initialize(callback=lambda r, e: state.update(
            init=(r, e)))
        pump_until(lambda: 'init' in state, 'initialize')
        result, error = state['init']
        assert error is None
        assert 'capabilities' in result
        assert client.is_connected()

        diags = {}
        client.diagnostics_received.connect(
            lambda uri, items: diags.update({uri: items}))
        client.did_open(URI, 'easymath', 1, 'See <oops>\n')
        pump_until(lambda: URI in diags, 'diagnostics')
        assert any('oops' in d['message'] for d in diags[URI])

        answers = {}
        client.request_completion(URI, 0, 4,
                                  lambda r, e: answers.update(comp=(r, e)))
        pump_until(lambda: 'comp' in answers, 'completion')
        assert answers['comp'][1] is None

        client.request_hover(URI, 0, 1,
                             lambda r, e: answers.update(hover=(r, e)))
        pump_until(lambda: 'hover' in answers, 'hover')

        client.request_symbols(URI,
                               lambda r, e: answers.update(sym=(r, e)))
        pump_until(lambda: 'sym' in answers, 'symbols')
        assert answers['sym'][1] is None

        client.did_change(URI, 2, 'ok line\n')
        pump_until(
            lambda: URI in diags and diags[URI] == [],
            'diagnostics refresh')

        client.did_close(URI)
    finally:
        client.stop()
        pump_until(lambda: client.state == 'stopped', 'shutdown handshake')
    assert client.state == 'stopped'


def test_request_timeout_without_response(qapp):
    client = LspClient(default_server_command())
    try:
        assert client.start()
        # Swallow outbound traffic: the server never sees the request,
        # so the client-side timeout must fire.
        real_send = client._send
        client._send = lambda payload: True
        errors = []
        client.process_error.connect(errors.append)
        fired = {}
        client.send_request('initialize', {}, lambda r, e: fired.update(err=e),
                            timeout_ms=100)
        pump_until(lambda: 'err' in fired, 'timeout error', timeout_ms=5000)
        assert 'timed out' in fired['err']['message']
        assert any('timed out' in m for m in errors)
        client._send = real_send
    finally:
        client.stop()
        pump_until(lambda: client.state == 'stopped', 'teardown shutdown')


def test_malformed_frame_emits_protocol_error(qapp):
    client = LspClient(default_server_command())
    problems = []
    client.protocol_error.connect(problems.append)
    client.on_data_received(b'Content-Length: 5\r\n\r\n{oops')
    assert len(problems) == 1
    assert 'Malformed' in problems[0]


def test_stop_without_start(qapp):
    client = LspClient(default_server_command())
    client.stop()  # must not raise
    assert client.state == 'stopped'
