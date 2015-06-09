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


class CommandFailure(Exception):
    """A ``run()`` command exited with a non-zero status code."""

    def __init__(self, command, status, output):
        self.command, self.status, self.output = command, status, output

    def __str__(self):
        return "'%s' exited with status %s. Output:\n%s" % (self.command,
                                                            self.status,
                                                            self.output)


class ConfigError(Exception):
    """A single error in the configuration file"""

    def __init__(self, message, sections):
        """
        :arg message: A human-readable error message
        :arg sections: A list of sections under which the error was encountered

        """
        self.message = message
        self.sections = sections

    def __str__(self):
        def bracketed(sections):
            """Yield sections names with increasing numbers of brackets around
            them.

            """
            for i, section in enumerate(sections, 1):
                yield '[' * i + section + ']' * i

        return ('There was an error in the configuration file, in the %s '
                'section: %s' % (' '.join(bracketed(self.sections)),
                                 self.message))
