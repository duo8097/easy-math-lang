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
        messages, error = self.feed_collect(data)
        if error is not None:
            raise error
        return messages

    def feed_collect(self, data):
        """Append bytes; return (messages, error).

        Unlike feed(), already-decoded messages are preserved even when
        a later frame is malformed: callers can dispatch messages and
        still surface the error.
        """
        self._buf += data
        messages = []
        first_error = None
        while True:
            try:
                msg = self._try_take_one()
            except ValueError as e:
                if first_error is None:
                    first_error = e
                # If no progress is possible (need more data vs bad frame),
                # _try_take_one already resynced on ValueError; continue to
                # collect any valid messages batched after the bad frame.
                # Break only when waiting for more bytes (None with no error
                # means incomplete; ValueError always resyncs).
                # Peek: if buffer still holds a complete frame, continue;
                # otherwise stop.
                if self._buf.find(b'\r\n\r\n') == -1:
                    break
                # Avoid infinite loop on persistent bad header: if the
                # buffer didn't shrink, stop.
                continue
            if msg is None:
                break
            messages.append(msg)
        if first_error is not None:
            return messages, ValueError(first_error)
        return messages, None

    def _try_take_one(self):
        sep = self._buf.find(b'\r\n\r\n')
        if sep == -1:
            return None
        header = bytes(self._buf[:sep]).decode('ascii', errors='replace')
        length = None
        bad_reason = None
        for line in header.split('\r\n'):
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            if key.strip().lower() == 'content-length':
                try:
                    length = int(value.strip())
                except ValueError:
                    bad_reason = f'invalid Content-Length: {value.strip()!r}'
                break
        if bad_reason is None and length is None:
            bad_reason = 'LSP frame without Content-Length'
        if bad_reason is None and length is not None:
            if length < 0:
                bad_reason = f'invalid Content-Length: {length}'
            elif length > 10 * 1024 * 1024:
                bad_reason = f'Content-Length too large: {length}'
        if bad_reason is not None:
            # Resync: drop the bad header and any non-framed bytes, keep
            # from the next plausible header so one malformed frame does
            # not poison the stream forever.
            rest = bytes(self._buf[sep + 4:])
            nxt = rest.lower().find(b'content-length:')
            if nxt == -1:
                self._buf.clear()
            else:
                del self._buf[:sep + 4 + nxt]
            raise ValueError(bad_reason)
        start = sep + 4
        if len(self._buf) < start + length:
            return None  # wait for more data
        body = bytes(self._buf[start:start + length])
        try:
            payload = json.loads(body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError) as e:
            # Bad body: drop this frame, resync to next header, keep stream alive.
            rest = bytes(self._buf[start + length:])
            nxt = rest.lower().find(b'content-length:')
            if nxt == -1:
                self._buf.clear()
            else:
                del self._buf[:start + length + nxt]
            raise ValueError(f'malformed LSP body: {e}')
        del self._buf[:start + length]
        return payload
