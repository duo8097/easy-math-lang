"""Shared mutable state for a single compilation run."""


class CompileContext:
    """Variables, defines and the multiplication display symbol."""

    def __init__(self):
        self.variables = {}
        self.defines = {}
        self.mult_sym = '*'
        # Absolute .eml path for SourceSpans (set per compile_ezmath run).
        self.source_file = ''
        # Document title set via *doc_title(...) (control line, consumed).
        # Stored raw and rendered at codegen so forward-referenced
        # variables still resolve. None means "use the default title".
        self.doc_title_raw = None
        self.doc_title_line = None
        # Document font set via *doc_font(...) (control line, consumed).
        # Family/size strings, or None for the Typst default (12pt).
        self.doc_font_family = None
        self.doc_font_size = None
        # Function-plot output (set by compile_ezmath before the line
        # loop; *_render_text_line* generates SVGs next to the .typ).
        self.plot_dir = None
        self.plot_stem = 'doc'
        self.plot_index = 0
