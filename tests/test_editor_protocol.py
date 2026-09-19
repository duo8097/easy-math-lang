"""Unit tests for LSP framing (pure, no Qt)."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from editor import protocol


def _frame(payload):
    body = json.dumps(payload).encode('utf-8')
    return b'Content-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body


def test_encode_round_trip():
    payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'x', 'params': {'a': '😀'}}
    buf = protocol.FramingBuffer()
    assert buf.feed(protocol.encode_message(payload)) == [payload]


def test_partial_message_waits():
    buf = protocol.FramingBuffer()
    data = _frame({'jsonrpc': '2.0', 'id': 2})
    assert buf.feed(data[:10]) == []
    assert buf.feed(data[10:20]) == []
    assert buf.feed(data[20:]) == [{'jsonrpc': '2.0', 'id': 2}]


def test_multiple_messages_in_one_read():
    buf = protocol.FramingBuffer()
    data = _frame({'id': 1}) + _frame({'id': 2}) + _frame({'id': 3})
    assert buf.feed(data) == [{'id': 1}, {'id': 2}, {'id': 3}]


def test_split_header_and_body():
    buf = protocol.FramingBuffer()
    data = _frame({'id': 7})
    head, body = data.split(b'\r\n\r\n')
    assert buf.feed(head + b'\r\n\r') == []
    assert buf.feed(b'\n' + body) == [{'id': 7}]


def test_extra_headers_tolerated():
    buf = protocol.FramingBuffer()
    body = json.dumps({'id': 9}).encode()
    data = (b'Content-Length: ' + str(len(body)).encode()
            + b'\r\nContent-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n'
            + body)
    assert buf.feed(data) == [{'id': 9}]


def test_invalid_content_length_raises():
    buf = protocol.FramingBuffer()
    try:
        buf.feed(b'Content-Length: abc\r\n\r\nxxxxx')
    except ValueError as e:
        assert 'Content-Length' in str(e)
    else:
        raise AssertionError('expected ValueError')


def test_missing_content_length_raises():
    buf = protocol.FramingBuffer()
    try:
        buf.feed(b'Content-Type: application/json\r\n\r\n{}')
    except ValueError as e:
        assert 'Content-Length' in str(e)
    else:
        raise AssertionError('expected ValueError')
