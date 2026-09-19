"""Pure LSP JSON-RPC framing helpers (no Qt dependency).

Implements the standard framing used over stdin/stdout::

    Content-Length: N\\r\\n
    \\r\\n
    <N bytes of UTF-8 JSON>

`FramingBuffer` accepts arbitrary byte chunks (partial messages, several
messages in one read) and yields complete decoded payloads.
"""

import json


def encode_message(payload):
    """Encode a JSON-RPC payload dict to framed bytes."""
    body = json.dumps(payload).encode('utf-8')
    return b'Content-Length: ' + str(len(body)).encode('ascii') + b'\r\n\r\n' + body


class FramingBuffer:
    """Incremental parser for LSP-framed byte streams."""

    def __init__(self):
        self._buf = bytearray()

    def feed(self, data):
        """Append bytes; return a list of complete decoded payloads."""
        self._buf += data
        messages = []
        while True:
            msg = self._try_take_one()
            if msg is None:
                break
            messages.append(msg)
        return messages

    def _try_take_one(self):
        sep = self._buf.find(b'\r\n\r\n')
        if sep == -1:
            return None
        header = bytes(self._buf[:sep]).decode('ascii', errors='replace')
        length = None
        for line in header.split('\r\n'):
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            if key.strip().lower() == 'content-length':
                try:
                    length = int(value.strip())
                except ValueError:
                    raise ValueError(f'invalid Content-Length: {value.strip()!r}')
        if length is None:
            raise ValueError('LSP frame without Content-Length')
        start = sep + 4
        if len(self._buf) < start + length:
            return None  # wait for more data
        body = bytes(self._buf[start:start + length])
        del self._buf[:start + length]
        return json.loads(body.decode('utf-8'))
