"""Async LSP client over a QProcess running ``easy-math-lsp``.

The Qt event loop is never blocked: process output is parsed incrementally
(partial messages and several messages per read are handled by
:mod:`..protocol`), responses are matched to requests by id, and every
request has a timeout.  UI code talks to :class:`LspClient` only through
signals and the small ``*_async`` convenience wrappers.
"""

import itertools
import sys

from PySide6 import QtCore

from . import protocol


class LspClient(QtCore.QObject):
    """JSON-RPC/LSP client speaking to an ``easy-math-lsp`` child process."""

    connected = QtCore.Signal()
    server_started = QtCore.Signal()
    disconnected = QtCore.Signal(int)          # exit code
    process_error = QtCore.Signal(str)         # human-readable problem
    protocol_error = QtCore.Signal(str)        # malformed inbound data
    notification_received = QtCore.Signal(str, dict)  # (method, params)
    diagnostics_received = QtCore.Signal(str, list)   # (uri, [diagnostics])
    response_received = QtCore.Signal(object, object, object)  # (id, result, error)

    def __init__(self, command, parent=None, default_timeout_ms=10000):
        super().__init__(parent)
        self._command = command
        self._default_timeout_ms = default_timeout_ms
        self._process = None
        self._framing = protocol.FramingBuffer()
        self._ids = itertools.count(1)
        self._pending = {}  # id -> (callback, QTimer)
        self._state = 'stopped'  # stopped|starting|connected|stopping

    # ------------------------------------------------------------------
    # Process lifecycle
    # ------------------------------------------------------------------
    @property
    def state(self):
        return self._state

    def is_connected(self):
        return self._state == 'connected'

    def start(self):
        """Launch the server process without blocking.

        Returns False only when the launch itself cannot be attempted;
        startup failures surface asynchronously via ``process_error`` and
        the ``server_started`` signal (emitted on QProcess.started).
        """
        if self._state != 'stopped':
            return True
        try:
            process = QtCore.QProcess(self)
            process.readyReadStandardOutput.connect(self._on_ready_read)
            process.started.connect(self._on_started)
            process.finished.connect(self._on_finished)
            process.errorOccurred.connect(self._on_process_error)
            process.start(self._command[0], self._command[1:])
        except Exception as e:  # noqa: BLE001 - report, don't crash
            self.process_error.emit(
                f'Could not start LSP server {" ".join(self._command)}: {e}')
            return False
        self._process = process
        self._state = 'starting'
        return True

    def stop(self):
        """Shut down with a proper handshake, never blocking the UI.

        Sends ``shutdown`` and, on its response (or timeout), ``exit``.
        A watchdog kills the process if it ignores ``exit``.  Completion
        is observable via the ``disconnected`` signal / ``state``.
        """
        process = self._process
        if process is None:
            self._state = 'stopped'
            return
        if self._state == 'stopping':
            return
        self._state = 'stopping'
        self._fail_all_pending('client stopped')
        self.send_request('shutdown', None, self._finish_stop,
                          timeout_ms=3000)

    def _finish_stop(self, _result, _error):
        process = self._process
        self._process = None
        if process is not None:
            try:
                process.write(protocol.encode_message(
                    {'jsonrpc': '2.0', 'method': 'exit', 'params': None}))
            except Exception:  # noqa: BLE001 - already going away
                pass
            QtCore.QTimer.singleShot(
                2000, lambda: self._ensure_reaped(process))
        else:
            self._state = 'stopped'

    def _ensure_reaped(self, process):
        """Kill a process that ignored ``exit``; ``finished`` finalizes."""
        try:
            if process.state() != QtCore.QProcess.NotRunning:
                process.kill()
        except RuntimeError:  # Qt object already deleted
            pass

    def abort(self):
        """Kill the server process immediately (shutdown fallback).

        Marks the client stopped and emits ``disconnected`` so UI waiting
        on shutdown always terminates.
        """
        process, self._process = self._process, None
        self._fail_all_pending('client aborted')
        if process is not None:
            try:
                process.kill()
            except RuntimeError:  # Qt object already deleted
                pass
        self._state = 'stopped'
        self.disconnected.emit(-1)

    # ------------------------------------------------------------------
    # Low-level messaging (also used directly by tests)
    # ------------------------------------------------------------------
    def send_request(self, method, params, callback=None, timeout_ms=None):
        """Send a request; ``callback(result, error)`` runs on response."""
        request_id = next(self._ids)
        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._on_timeout(request_id))
        timer.start(timeout_ms or self._default_timeout_ms)
        self._pending[request_id] = (callback, timer)
        if not self._send({'jsonrpc': '2.0', 'id': request_id,
                           'method': method, 'params': params}):
            self._pop_pending(request_id)
            if callback is not None:
                callback(None, {'message': 'LSP server is not running'})
        return request_id

    def send_notification(self, method, params):
        self._send({'jsonrpc': '2.0', 'method': method, 'params': params})

    def on_data_received(self, data):
        """Feed raw stdout bytes; dispatches complete messages."""
        try:
            messages = self._framing.feed(data)
        except ValueError as e:
            self.protocol_error.emit(f'Malformed LSP frame: {e}')
            return
        for message in messages:
            self.dispatch_message(message)

    def dispatch_message(self, message):
        if 'id' in message:
            self._dispatch_response(message)
        elif 'method' in message:
            self._dispatch_notification(message)
        else:
            self.protocol_error.emit(f'LSP message is neither response '
                                     f'nor notification: {message!r:.120}')

    # ------------------------------------------------------------------
    # Convenience wrappers (all fire-and-forget except initialize)
    # ------------------------------------------------------------------
    def initialize(self, root_uri=None, callback=None):
        def _done(result, error):
            if error is None:
                self.send_notification('initialized', {})
                self._state = 'connected'
                self.connected.emit()
            if callback is not None:
                callback(result, error)

        return self.send_request('initialize', {
            'processId': None,
            'capabilities': {},
            'rootUri': root_uri,
        }, _done)

    def did_open(self, uri, language_id, version, text):
        self.send_notification('textDocument/didOpen', {'textDocument': {
            'uri': uri, 'languageId': language_id,
            'version': version, 'text': text}})

    def did_change(self, uri, version, text):
        self.send_notification('textDocument/didChange', {
            'textDocument': {'uri': uri, 'version': version},
            'contentChanges': [{'text': text}]})

    def did_close(self, uri):
        self.send_notification('textDocument/didClose',
                               {'textDocument': {'uri': uri}})

    def request_completion(self, uri, line, character, callback):
        return self.send_request('textDocument/completion', {
            'textDocument': {'uri': uri},
            'position': {'line': line, 'character': character},
        }, callback, timeout_ms=5000)

    def request_hover(self, uri, line, character, callback):
        return self.send_request('textDocument/hover', {
            'textDocument': {'uri': uri},
            'position': {'line': line, 'character': character},
        }, callback, timeout_ms=5000)

    def request_symbols(self, uri, callback):
        return self.send_request('textDocument/documentSymbol', {
            'textDocument': {'uri': uri},
        }, callback, timeout_ms=5000)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _send(self, payload):
        if self._process is None:
            return False
        # QProcess.write returns -1 (never raises) on a broken pipe.
        return self._process.write(protocol.encode_message(payload)) != -1

    def _pop_pending(self, request_id):
        entry = self._pending.pop(request_id, None)
        if entry is not None:
            _, timer = entry
            timer.stop()
            timer.deleteLater()
        return entry

    def _on_timeout(self, request_id):
        entry = self._pop_pending(request_id)
        if entry is None:
            return
        callback, _ = entry
        self.process_error.emit(f'LSP request {request_id} timed out')
        if callback is not None:
            callback(None, {'message': 'LSP request timed out'})

    def _fail_all_pending(self, message):
        for request_id in list(self._pending):
            entry = self._pop_pending(request_id)
            if entry is not None and entry[0] is not None:
                entry[0](None, {'message': message})

    def _dispatch_response(self, message):
        request_id = message.get('id')
        if request_id is None:
            self.protocol_error.emit(
                f'LSP response without id: {message!r:.120}')
            return
        entry = self._pop_pending(request_id)
        if entry is None:
            self.protocol_error.emit(
                f'LSP response for unknown request {request_id!r}')
            return
        self.response_received.emit(request_id, message.get('result'),
                                    message.get('error'))
        if entry[0] is not None:
            try:
                entry[0](message.get('result'), message.get('error'))
            except Exception as e:  # noqa: BLE001 - never crash on callbacks
                self.process_error.emit(f'LSP callback failed: {e}')

    def _dispatch_notification(self, message):
        method = message.get('method', '')
        params = message.get('params') or {}
        if method == 'textDocument/publishDiagnostics':
            self.diagnostics_received.emit(params.get('uri', ''),
                                           params.get('diagnostics', []))
        self.notification_received.emit(method, params)

    def _on_ready_read(self):
        if self._process is not None:
            self.on_data_received(bytes(self._process.readAllStandardOutput()))

    def _on_started(self):
        self.server_started.emit()

    def _on_finished(self, exit_code, _status):
        self._fail_all_pending('LSP server terminated')
        if self._state != 'stopping':
            self.process_error.emit(
                f'LSP server terminated unexpectedly (code {exit_code})')
        self._process = None
        self._state = 'stopped'
        self.disconnected.emit(exit_code)

    def _on_process_error(self, error):
        names = {
            QtCore.QProcess.ProcessError.FailedToStart:
                'failed to start (executable missing?)',
            QtCore.QProcess.ProcessError.Crashed: 'crashed',
            QtCore.QProcess.ProcessError.Timedout: 'timed out',
            QtCore.QProcess.ProcessError.WriteError: 'write error',
            QtCore.QProcess.ProcessError.ReadError: 'read error',
            QtCore.QProcess.ProcessError.UnknownError: 'unknown error',
        }
        message = names.get(error, str(error))
        self.process_error.emit(f'LSP process error: {message}')
        sys.stderr.write(f'[easy-math-editor] LSP process error: {message}\n')


def default_server_command():
    """Launch via the current interpreter so no PATH setup is needed."""
    return [sys.executable, '-m', 'easy_math_lang.lsp']
