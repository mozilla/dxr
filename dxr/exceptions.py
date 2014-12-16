"""Exceptions, broken out into a leaf module to ward off circular imports"""


class BadTerm(Exception):
    """A user error made it impossible to filter on a term."""

    def __init__(self, reason):
        """Construct.

        :arg reason: User-readble error message telling the user what is
            wrong and how to fix it. Should be Markup. Will be treated as HTML
            by the JS.

        """
        self.reason = reason


class BuildError(Exception):
    """Catch-all error for expected kinds of failures during indexing"""
    # This could be refined better, have params added, etc., but it beats
    # calling sys.exit, which is what was happening before.
