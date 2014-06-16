"""Tests for the plugin architecture itself"""

from unittest import TestCase

from nose.tools import ok_

import dxr
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
    ok_(isinstance(plugin.tree_to_index(mocked_tree).file_to_index('/foo/bar', ''),
                   urllink.FileToIndex))
