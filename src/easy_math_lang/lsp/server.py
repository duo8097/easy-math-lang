"""pygls JSON-RPC wiring (stdio). Stdout is protocol-only; log to stderr."""

import logging
import sys

from lsprotocol import types as lsp
from pygls.lsp.server import LanguageServer

from . import analysis
from .document import DocumentStore

logger = logging.getLogger('easy-math-lsp')

SERVER_NAME = 'easy-math-lsp'
SERVER_VERSION = '0.1.0'

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
    return uri.endswith(SUPPORTED_EXTENSIONS) or language_id in SUPPORTED_LANGUAGE_IDS


def to_lsp_diagnostic(diag):
    severity = (
        lsp.DiagnosticSeverity.Error
        if diag.severity == 'error'
        else lsp.DiagnosticSeverity.Warning
    )
    return lsp.Diagnostic(
        range=lsp.Range(
            start=lsp.Position(line=diag.line, character=diag.start),
            end=lsp.Position(line=diag.line, character=diag.end),
        ),
        message=diag.message,
        severity=severity,
        source=SERVER_NAME,
    )


def analyze_and_publish(ls, store, uri):
    text = store.get(uri)
    diags = (
        [to_lsp_diagnostic(d) for d in analysis.analyze_text(text).diagnostics]
        if text is not None
        else []
    )
    ls.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(
            uri=uri, diagnostics=diags, version=store.version(uri)
        )
    )


def create_server():
    server = LanguageServer(
        SERVER_NAME,
        SERVER_VERSION,
        text_document_sync_kind=lsp.TextDocumentSyncKind.Full,
    )
    store = DocumentStore()

    @server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
    def did_open(ls, params: lsp.DidOpenTextDocumentParams):
        doc = params.text_document
        store.open(doc.uri, doc.text, doc.version)
        if is_supported(doc.uri, doc.language_id):
            analyze_and_publish(ls, store, doc.uri)
        else:
            ls.text_document_publish_diagnostics(
                lsp.PublishDiagnosticsParams(uri=doc.uri, diagnostics=[])
            )

    @server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
    def did_change(ls, params: lsp.DidChangeTextDocumentParams):
        uri = params.text_document.uri
        if params.content_changes:
            store.update(uri, params.content_changes[-1].text,
                         params.text_document.version)
        if is_supported(uri):
            analyze_and_publish(ls, store, uri)

    @server.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
    def did_close(ls, params: lsp.DidCloseTextDocumentParams):
        uri = params.text_document.uri
        store.close(uri)
        ls.text_document_publish_diagnostics(
            lsp.PublishDiagnosticsParams(uri=uri, diagnostics=[])
        )

    @server.feature(
        lsp.TEXT_DOCUMENT_COMPLETION,
        lsp.CompletionOptions(trigger_characters=['<', '*']),
    )
    def completion(ls, params: lsp.CompletionParams):
        uri = params.text_document.uri
        text = store.get(uri)
        if text is None or not is_supported(uri):
            return lsp.CompletionList(is_incomplete=False, items=[])
        pos = params.position
        items = [
            lsp.CompletionItem(
                label=item['label'],
                kind=_COMPLETION_KINDS.get(item['kind']),
                detail=item.get('detail'),
            )
            for item in analysis.complete(text, pos.line, pos.character)
        ]
        return lsp.CompletionList(is_incomplete=False, items=items)

    @server.feature(lsp.TEXT_DOCUMENT_HOVER)
    def hover(ls, params: lsp.HoverParams):
        uri = params.text_document.uri
        text = store.get(uri)
        if text is None or not is_supported(uri):
            return None
        pos = params.position
        found = analysis.hover(text, pos.line, pos.character)
        if found is None:
            return None
        return lsp.Hover(
            contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown, value=found['value']
            ),
            range=lsp.Range(
                start=lsp.Position(line=pos.line, character=found['start']),
                end=lsp.Position(line=pos.line, character=found['end']),
            ),
        )

    @server.feature(lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def document_symbol(ls, params: lsp.DocumentSymbolParams):
        uri = params.text_document.uri
        text = store.get(uri)
        if text is None or not is_supported(uri):
            return []
        return [
            lsp.SymbolInformation(
                name=name,
                kind=_SYMBOL_KINDS.get(kind, lsp.SymbolKind.Variable),
                location=lsp.Location(
                    uri=uri,
                    range=lsp.Range(
                        start=lsp.Position(line=line, character=start),
                        end=lsp.Position(line=line, character=end),
                    ),
                ),
            )
            for name, kind, line, start, end in analysis.document_symbols(text)
        ]

    return server


def main():
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    create_server().start_io()


if __name__ == '__main__':
    main()
