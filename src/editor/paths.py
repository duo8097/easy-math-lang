"""Locate Easy Math executables across source, venv, and frozen builds.

The editor used to start the language server via ``shutil.which`` with a
``[sys.executable, '-m', 'lsp']`` fallback, and compiled documents via
``[sys.executable, '-c', 'from compiler.pipeline import ...']``. That works
from source (``sys.executable`` is a Python interpreter) but breaks in a
PyInstaller bundle, where ``sys.executable`` is the frozen
``easy-math-editor`` binary itself: ``-m``/``-c`` no longer run Python code,
and the sibling ``easy-math-lsp``/``easy-math-lang`` binaries are usually
not on ``PATH`` (the installer only optionally adds ``bin`` to ``PATH``).

Resolution order (first hit wins):

1. ``EASYMATH_LSP_EXE`` / ``EASYMATH_COMPILER_EXE`` environment override.
2. Binaries next to the running executable: the venv ``Scripts/`` (or
   ``bin/``) directory when running from source, the installer ``../bin``
   layout or a side-by-side ``dist/`` directory when frozen.
3. ``PATH`` via :func:`shutil.which`.
4. Source/venv only: ``[sys.executable, '-m', <module>, ...]``.
5. Frozen last resort: the bare executable name, so ``QProcess`` still
   reports a meaningful "failed to start" error instead of crashing.

Stdlib only: safe to import from any bundle without pulling heavy deps.
"""

import os
import shutil
import sys

LSP_EXE_NAMES = ('easy-math-lsp',)
COMPILER_EXE_NAMES = ('easy-math-lang',)

LSP_MODULE = 'lsp'
COMPILER_MODULE = 'compiler'

ENV_LSP_EXE = 'EASYMATH_LSP_EXE'
ENV_COMPILER_EXE = 'EASYMATH_COMPILER_EXE'


def is_frozen():
    """True when running inside a PyInstaller (or similar) bundle."""
    return bool(getattr(sys, 'frozen', False)) or hasattr(sys, '_MEIPASS')


def _exe_spellings(base):
    if os.name == 'nt':
        return (base + '.exe', base)
    return (base,)


def _is_usable_file(path):
    if not os.path.isfile(path):
        return False
    if os.name != 'nt' and not os.access(path, os.X_OK):
        return False
    return True


def candidate_directories():
    """Directories that may hold sibling Easy Math binaries (deduped)."""
    dirs = []

    def _add(directory):
        if not directory:
            return
        abs_dir = os.path.abspath(directory)
        if os.path.normcase(abs_dir) not in {
                os.path.normcase(d) for d in dirs}:
            dirs.append(abs_dir)

    exe = sys.executable or ''
    if exe:
        exe_dir = os.path.dirname(os.path.abspath(exe))
        _add(exe_dir)
        # Inno Setup layout: editor lives in {app}/editor, tools in {app}/bin.
        parent = os.path.dirname(exe_dir)
        _add(os.path.join(parent, 'bin'))
        _add(parent)
        _add(os.path.join(exe_dir, 'bin'))
    argv0 = sys.argv[0] if sys.argv else ''
    if argv0:
        _add(os.path.dirname(os.path.abspath(argv0)))
    return dirs


def find_executable(basenames, env_var=None):
    """Absolute path of a sibling binary, or None when not found on disk."""
    if env_var:
        override = os.environ.get(env_var, '').strip().strip('"')
        if override and _is_usable_file(override):
            return os.path.abspath(override)
    for directory in candidate_directories():
        for base in basenames:
            for spelling in _exe_spellings(base):
                candidate = os.path.join(directory, spelling)
                if _is_usable_file(candidate):
                    return candidate
    return None


def _which(basenames):
    for base in basenames:
        for spelling in _exe_spellings(base):
            found = shutil.which(spelling)
            if found:
                return found
    return None


def _last_resort_name(basenames):
    return _exe_spellings(basenames[0])[0]


def resolve_lsp_command():
    """QProcess-ready command starting the language server over stdio."""
    override = os.environ.get(ENV_LSP_EXE, '').strip().strip('"')
    if override and _is_usable_file(override):
        return [os.path.abspath(override)]
    found = find_executable(LSP_EXE_NAMES)
    if found:
        return [found]
    located = _which(LSP_EXE_NAMES)
    if located:
        return [located]
    if not is_frozen():
        return [sys.executable, '-m', LSP_MODULE]
    return [_last_resort_name(LSP_EXE_NAMES)]


def resolve_compiler_command(document_path):
    """QProcess-ready command compiling *document_path* to PDF."""
    override = os.environ.get(ENV_COMPILER_EXE, '').strip().strip('"')
    if override and _is_usable_file(override):
        return [os.path.abspath(override), document_path]
    found = find_executable(COMPILER_EXE_NAMES)
    if found:
        return [found, document_path]
    located = _which(COMPILER_EXE_NAMES)
    if located:
        return [located, document_path]
    if not is_frozen():
        return [sys.executable, '-m', COMPILER_MODULE, document_path]
    return [_last_resort_name(COMPILER_EXE_NAMES), document_path]


def bundle_dir():
    """Directory holding the running app (bundle dir when frozen)."""
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        return os.path.abspath(meipass)
    exe = sys.executable or ''
    if exe:
        return os.path.dirname(os.path.abspath(exe))
    return os.path.abspath(os.getcwd())


def resource_path(*parts):
    """Absolute path of a runtime file shipped next to the app."""
    return os.path.join(bundle_dir(), *parts)
