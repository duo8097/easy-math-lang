"""Compiler: .ezmath text processing pipeline producing Typst/PDF/PNG/SVG/HTML."""

from .diagnostics import KNOWN_COMMANDS
from .pipeline import (
    SUPPORTED_EXPORT_FORMATS,
    compile_ezmath,
    infer_export_format,
    main,
)
from .source_map import (
    MapEntry,
    SourcePosition,
    SourceSpan,
    TypstSourceMap,
    default_map_path,
)

__all__ = [
    'KNOWN_COMMANDS',
    'SUPPORTED_EXPORT_FORMATS',
    'MapEntry',
    'SourcePosition',
    'SourceSpan',
    'TypstSourceMap',
    'compile_ezmath',
    'default_map_path',
    'infer_export_format',
    'main',
]
