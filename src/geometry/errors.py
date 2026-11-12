"""Geometry errors (shared by solver, commands and code generation)."""


class GeometryError(Exception):
    pass


class GeometryWarning(Warning):
    """A non-fatal advisory (the diagram may be inaccurate).

    Subclasses :class:`Warning` (not :class:`Exception`) so ``except
    Exception`` never swallows an advisory, and the ``warnings`` module
    can be used to filter it.  ``parse_draw_block`` still catches it
    explicitly and surfaces it as a ``[GeometryWarning]`` comment.
    """
    pass
