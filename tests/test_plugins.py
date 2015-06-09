"""Tests for the plugin architecture itself"""

from nose.tools import ok_

from dxr.plugins import all_plugins
import dxr.plugins.urllink as urllink


def test_registration():
    """Make sure plugins registered via entry points are detected."""
    ok_('urllink' in all_plugins().keys())


def test_construction():
    """If a plugin is a plain module, make sure it is automatically promoted to
    a Plugin via recognition of symbol naming conventions."""
    plugin = all_plugins()['urllink']
    mocked_tree = None  # This will probably have to improve at some point.
    mocked_vcs = None
    ok_(isinstance(plugin.tree_to_index('urllink', mocked_tree, mocked_vcs).file_to_index('/foo/bar', ''),
                   urllink.FileToIndex))
