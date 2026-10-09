"""Source-link URL helpers for the editor (re-export, Qt-free).

Canonical implementation lives in :mod:`compiler.source_links` so the
compiler can emit links without importing the Qt-coupled ``editor``
package. Import from either location.
"""

from compiler.source_links import HOST, SCHEME, link_prefix, make_source_url, parse_source_url

__all__ = ['HOST', 'SCHEME', 'link_prefix', 'make_source_url', 'parse_source_url']
