"""Shared mutable state for a single compilation run."""


class CompileContext:
    """Variables, defines and the multiplication display symbol."""

    def __init__(self):
        self.variables = {}
        self.defines = {}
        self.mult_sym = '*'
