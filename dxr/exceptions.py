"""Exceptions, broken out into a leaf module to ward off circular imports"""


class BadQuery(Exception):
    """A user error made the query unrunnable."""

    def __init__(self, reason):
        """Construct.

        :arg reason: User-readble error message telling the user what is
            wrong and how to fix it. Can be Unicode or Markup.

        """
        self.reason = reason
