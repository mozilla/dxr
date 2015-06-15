"""Tests for handling failed builds"""

from dxr.exceptions import BuildError, CommandFailure
from dxr.testing import SingleFileTestCase


class BuildFailureTests(SingleFileTestCase):
    source = r"""A bunch of garbage"""

    @classmethod
    def setup_class(cls):
        """Make sure a failed build returns a non-zero status code."""
        try:
            super(BuildFailureTests, cls).setup_class()
        except BuildError:
            pass
        else:
            raise AssertionError('A failed build returned an exit code of 0. ' + cls._config_dir_path)

    def test_nothing(self):
        """A null test just to make the setup method run"""
