"""Shared mutable state for a single compilation run."""


class CompileContext:
    """Variables, defines and the multiplication display symbol."""

    def __init__(self):
        self.variables = {}
        self.defines = {}
        self.mult_sym = '*'
        # Function-plot output (set by compile_ezmath before the line
        # loop; *_render_text_line* generates SVGs next to the .typ).
        self.plot_dir = None
        self.plot_stem = 'doc'
        self.plot_index = 0
