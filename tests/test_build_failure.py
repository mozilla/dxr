"""Tests for handling failed builds"""

from dxr.testing import SingleFileTestCase, CommandFailure


class BuildFailureTests(SingleFileTestCase):
    source = r"""A bunch of garbage"""

    @classmethod
    def setup_class(cls):
        """Make sure a failed build returns a non-zero status code."""
        try:
            super(BuildFailureTests, cls).setup_class()
        except CommandFailure:
            pass
        else:
            raise AssertionError('A failed build returned an exit code of 0.')

    def test_nothing(self):
        """A null test just to make the setup method run"""
