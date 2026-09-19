"""In-memory document store (uri -> text + version)."""


class DocumentStore:
    """Minimal open-document registry used by the LSP handlers."""

    def __init__(self):
        self._docs = {}

    def open(self, uri, text, version=None):
        self._docs[uri] = {'text': text, 'version': version}

    def update(self, uri, text, version=None):
        self._docs[uri] = {'text': text, 'version': version}

    def close(self, uri):
        self._docs.pop(uri, None)

    def get(self, uri):
        doc = self._docs.get(uri)
        return doc['text'] if doc is not None else None

    def version(self, uri):
        doc = self._docs.get(uri)
        return doc['version'] if doc is not None else None

    def __contains__(self, uri):
        return uri in self._docs
