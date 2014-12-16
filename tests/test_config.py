"""Tests for the configuration subsystem"""

from nose.tools import ok_

from dxr.config import Config


def test_enabled_star():
    """Make sure even plugins that aren't packages get enabled when
    enabled_plugins = *.

    """
    config = Config("""
[DXR]
enabled_plugins = *
target_folder = /some/path

[some_tree]
source_folder = /some/path
object_folder = /some/path
build_command = /some/command
""")
    ok_('urllink' in config.enabled_plugins)
