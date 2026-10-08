"""pygls JSON-RPC wiring (stdio). Stdout is protocol-only; log to stderr."""

import logging
import sys

from lsprotocol import types as lsp
from pygls.lsp.server import LanguageServer

from . import analysis
from .document import DocumentStore

logger = logging.getLogger('easy-math-lsp')

SERVER_NAME = 'easy-math-lsp'
# Installed version; the literal is a frozen-build fallback only.
SERVER_VERSION = '4.0.0'
try:
    from importlib.metadata import version as _dist_version

    _found = _dist_version('easy-math-lang')
    if isinstance(_found, str) and _found.strip():
        SERVER_VERSION = _found.strip()
except Exception:
    pass

SUPPORTED_EXTENSIONS = ('.ezmath', '.eml')
SUPPORTED_LANGUAGE_IDS = {'easymath', 'easy-math-lang', 'ezmath', 'eml'}

_COMPLETION_KINDS = {
    'variable': lsp.CompletionItemKind.Variable,
    'constant': lsp.CompletionItemKind.Constant,
    'function': lsp.CompletionItemKind.Function,
    'keyword': lsp.CompletionItemKind.Keyword,
}

_SYMBOL_KINDS = {
    'define': lsp.SymbolKind.Constant,
    'variable': lsp.SymbolKind.Variable,
    'draw': lsp.SymbolKind.Function,
}


def is_supported(uri, language_id=None):
    if not isinstance(uri, str):
        return False
    low = uri.lower().split('?')[0].split('#')[0]
    if low.endswith(SUPPORTED_EXTENSIONS):
        return True
    if isinstance(language_id, str) and language_id.lower() in {
        s.lower() for s in SUPPORTED_LANGUAGE_IDS
    }:
        return True
    return False


def _coerce_int(value, default=0):
    """Best-effort int() for wire data; never raises."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_lsp_offset(line_text, code_point_offset):
    """Code-point offset -> LSP (UTF-16) offset for one line."""
    if not isinstance(line_text, str):
        return 0
    return len(line_text[:max(0, _coerce_int(code_point_offset))].encode('utf-16-le')) // 2


def _to_code_point_offset(line_text, utf16_offset):
    """LSP (UTF-16) offset -> code-point offset for one line."""
    if not isinstance(line_text, str):
        return 0
    target = max(0, _coerce_int(utf16_offset))
    index = units = 0
    while index < len(line_text) and units < target:
        units += 2 if ord(line_text[index]) > 0xFFFF else 1
        index += 1
    return index


def _line_at(lines, line):
    try:
        line = int(line)
    except (TypeError, ValueError):
        return ''
    return lines[line] if 0 <= line < len(lines) else ''


def _lsp_range(lines, line, start_cp, end_cp):
    line = _coerce_int(line, default=0)
    if line < 0:
        line = 0
    if lines and line >= len(lines):
        line = max(0, len(lines) - 1)
    text = _line_at(lines, line)
    return lsp.Range(
        start=lsp.Position(line=line, character=_to_lsp_offset(text, start_cp)),
        end=lsp.Position(line=line, character=_to_lsp_offset(text, end_cp)),
    )


def to_lsp_diagnostic(diag, lines):
    severity = (
        lsp.DiagnosticSeverity.Error
        if diag.severity == 'error'
        else lsp.DiagnosticSeverity.Warning
    )
    return lsp.Diagnostic(
        range=_lsp_range(lines, diag.line, diag.start, diag.end),
        message=diag.message,
        severity=severity,
        source=SERVER_NAME,
    )


def analyze_and_publish(ls, store, uri):
    try:
        text, ver = store.snapshot(uri)
        if text is None:
            diags = []
            ver = None
        else:
            if not isinstance(text, str):
                diags = []
            else:
                lines = text.splitlines()
                try:
                    diags = [
                        to_lsp_diagnostic(d, lines)
                        for d in analysis.analyze_text(text).diagnostics
                    ]
                except Exception as e:
                    logger.exception('analyze_text failed for %s', uri)
                    lines = text.splitlines() if isinstance(text, str) else []
                    diags = [
                        to_lsp_diagnostic(
                            analysis.Diag(0, 0, len(lines[0]) if lines else 0,
                                          'error', f'Analysis failed: {e}'),
                            lines,
                        )
                    ] if lines is not None else []
    except Exception:
        logger.exception('analyze_and_publish failed for %s', uri)
        try:
            ls.text_document_publish_diagnostics(
                lsp.PublishDiagnosticsParams(uri=uri, diagnostics=[])
            )
        except Exception:
            logger.exception('publish empty diagnostics failed for %s', uri)
        return
    try:
        if ver is None:
            params = lsp.PublishDiagnosticsParams(uri=uri, diagnostics=diags)
        else:
            params = lsp.PublishDiagnosticsParams(
                uri=uri, diagnostics=diags, version=ver
            )
        ls.text_document_publish_diagnostics(params)
    except Exception:
        logger.exception('publish diagnostics failed for %s', uri)


def create_server():
    server = LanguageServer(
        SERVER_NAME,
        SERVER_VERSION,
        text_document_sync_kind=lsp.TextDocumentSyncKind.Full,
    )
    store = DocumentStore()
    _support_cache = {}

    def _cached_supported(uri):
        if uri in _support_cache:
            return _support_cache[uri]
        supported = is_supported(uri)
        _support_cache[uri] = supported
        return supported

    @server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
    def did_open(ls, params: lsp.DidOpenTextDocumentParams):
        doc = params.text_document
        if not isinstance(doc.uri, str) or not isinstance(doc.text, str):
            logger.warning('didOpen with invalid uri/text; ignoring')
            return
        store.open(doc.uri, doc.text, doc.version)
        supported = is_supported(doc.uri, getattr(doc, 'language_id', None))
        _support_cache[doc.uri] = supported
        if supported:
            analyze_and_publish(ls, store, doc.uri)
        else:
            try:
                ls.text_document_publish_diagnostics(
                    lsp.PublishDiagnosticsParams(uri=doc.uri, diagnostics=[])
                )
            except Exception:
                logger.exception('publish empty diagnostics failed for %s', doc.uri)

    @server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
    def did_change(ls, params: lsp.DidChangeTextDocumentParams):
        uri = params.text_document.uri
        if uri not in store:
            # Unknown URI (e.g. after restart): publish empty to avoid
            # stale squiggles on the client.
            try:
                ls.text_document_publish_diagnostics(
                    lsp.PublishDiagnosticsParams(uri=uri, diagnostics=[])
                )
            except Exception:
                logger.exception('publish empty diagnostics failed for %s', uri)
            return
        if params.content_changes:
            # Full-sync only: drop any incremental (range) edit instead
            # of replacing the whole document with a fragment, but still
            # republish so the client never waits on stale diagnostics.
            last = params.content_changes[-1]
            if getattr(last, 'range', None) is not None or getattr(
                last, 'rangeLength', None
            ) is not None:
                logger.warning('ignoring incremental edit for %s (full sync)', uri)
                supported = _support_cache.get(uri, is_supported(uri))
                _support_cache[uri] = supported
                if supported:
                    analyze_and_publish(ls, store, uri)
                return
            new_text = last.text
            if isinstance(new_text, str):
                store.update(uri, new_text,
                             params.text_document.version)
        supported = _support_cache.get(uri, is_supported(uri))
        _support_cache[uri] = supported
        if supported:
            analyze_and_publish(ls, store, uri)

    @server.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
    def did_close(ls, params: lsp.DidCloseTextDocumentParams):
        uri = params.text_document.uri
        store.close(uri)
        _support_cache.pop(uri, None)
        try:
            ls.text_document_publish_diagnostics(
                lsp.PublishDiagnosticsParams(uri=uri, diagnostics=[])
            )
        except Exception:
            logger.exception('publish empty diagnostics failed for %s', uri)

    @server.feature(
        lsp.TEXT_DOCUMENT_COMPLETION,
        lsp.CompletionOptions(trigger_characters=['<', '*']),
    )
    def completion(ls, params: lsp.CompletionParams):
        try:
            uri = params.text_document.uri
            text = store.get(uri)
            if text is None or not _cached_supported(uri):
                return lsp.CompletionList(is_incomplete=False, items=[])
            pos = params.position
            try:
                line = int(pos.line)
                character_raw = int(pos.character)
            except (TypeError, ValueError):
                return lsp.CompletionList(is_incomplete=False, items=[])
            lines = text.splitlines()
            character = _to_code_point_offset(_line_at(lines, line), character_raw)
            items = [
                lsp.CompletionItem(
                    label=item['label'],
                    kind=_COMPLETION_KINDS.get(item['kind']),
                    detail=item.get('detail'),
                )
                for item in analysis.complete(text, line, character)
            ]
            return lsp.CompletionList(is_incomplete=False, items=items)
        except Exception:
            logger.exception('completion failed')
            return lsp.CompletionList(is_incomplete=False, items=[])

    @server.feature(lsp.TEXT_DOCUMENT_HOVER)
    def hover(ls, params: lsp.HoverParams):
        try:
            uri = params.text_document.uri
            text = store.get(uri)
            if text is None or not _cached_supported(uri):
                return None
            pos = params.position
            try:
                line = int(pos.line)
                character_raw = int(pos.character)
            except (TypeError, ValueError):
                return None
            lines = text.splitlines()
            if line < 0 or (lines and line >= len(lines)):
                return None
            character = _to_code_point_offset(_line_at(lines, line), character_raw)
            found = analysis.hover(text, line, character)
            if found is None:
                return None
            return lsp.Hover(
                contents=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown, value=found['value']
                ),
                range=_lsp_range(lines, line, found['start'], found['end']),
            )
        except Exception:
            logger.exception('hover failed')
            return None

    @server.feature(lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def document_symbol(ls, params: lsp.DocumentSymbolParams):
        try:
            uri = params.text_document.uri
            text = store.get(uri)
            if text is None or not _cached_supported(uri):
                return []
            lines = text.splitlines()
            return [
                lsp.SymbolInformation(
                    name=name,
                    kind=_SYMBOL_KINDS.get(kind, lsp.SymbolKind.Variable),
                    location=lsp.Location(
                        uri=uri,
                        range=_lsp_range(lines, line, start, end),
                    ),
                )
                for name, kind, line, start, end in analysis.document_symbols(text)
            ]
        except Exception:
            logger.exception('documentSymbol failed')
            return []

    return server


def main():
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    create_server().start_io()


if __name__ == '__main__':
    main()
