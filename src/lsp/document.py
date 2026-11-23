"""In-memory document store (uri -> text + version)."""

import threading


class DocumentStore:
    """Minimal open-document registry used by the LSP handlers."""

    def __init__(self):
        self._docs = {}
        self._lock = threading.Lock()

    def open(self, uri, text, version=None):
        """Open a document; returns False for bad types."""
        if not isinstance(uri, str):
            return False
        if not isinstance(text, str):
            return False
        with self._lock:
            self._docs[uri] = {'text': text, 'version': version}
        return True

    def update(self, uri, text, version=None):
        """Apply a didChange text update; ignore unknown docs/versions."""
        # didChange implies an open document; ignore changes for unknown
        # URIs instead of creating phantom servable documents.
        if not isinstance(uri, str):
            return False
        if not isinstance(text, str):
            return False
        with self._lock:
            if uri not in self._docs:
                return False
            old = self._docs[uri]
            old_version = old.get('version')
            # Ignore out-of-order updates: an older version must not
            # overwrite newer state (reconnect/version reset safety).
            try:
                if (version is not None and old_version is not None
                        and int(version) <= int(old_version)):
                    return False
            except (TypeError, ValueError):
                pass
            self._docs[uri] = {'text': text, 'version': version}
        return True

    def close(self, uri):
        """Close (forget) a document."""
        with self._lock:
            self._docs.pop(uri, None)

    def get(self, uri):
        """Return the document text, or None when the URI is unknown."""
        with self._lock:
            doc = self._docs.get(uri)
            return doc['text'] if doc is not None else None

    def version(self, uri):
        """Return the document version, or None when the URI is unknown."""
        with self._lock:
            doc = self._docs.get(uri)
            return doc['version'] if doc is not None else None

    def snapshot(self, uri):
        """Atomic (text, version) snapshot for publish consistency."""
        with self._lock:
            doc = self._docs.get(uri)
            if doc is None:
                return None, None
            return doc['text'], doc['version']

    def __contains__(self, uri):
        with self._lock:
            return uri in self._docs
