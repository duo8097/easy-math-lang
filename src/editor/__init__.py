"""Easy-Math-Lang desktop editor (PySide6 LSP client for easy-math-lsp).

Qt-free submodules (positions, protocol, paths, symbol_registry) stay
importable without PySide6 so compiler/geometry/LSP tests run on
machines without Qt. Qt-dependent names (MainWindow, EditorWidget,
LspClient, main, ...) are resolved lazily via module __getattr__.
"""

from . import positions, protocol

__all__ = ['EditorWidget', 'LspClient', 'MainWindow', 'default_server_command',
           'main', 'positions', 'protocol']

_LAZY = {
    'main': ('.app', 'main'),
    'EditorWidget': ('.editor_widget', 'EditorWidget'),
    'LspClient': ('.lsp_client', 'LspClient'),
    'default_server_command': ('.lsp_client', 'default_server_command'),
    'MainWindow': ('.main_window', 'MainWindow'),
}


def __getattr__(name):
    if name in _LAZY:
        import importlib
        mod_name, attr = _LAZY[name]
        mod = importlib.import_module(mod_name, __name__)
        return getattr(mod, attr)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
