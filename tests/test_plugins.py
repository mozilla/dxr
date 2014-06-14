"""Tests for the plugin architecture itself"""

from unittest import TestCase

from nose.tools import ok_

import dxr
from dxr.plugins import all_plugins


def test_registration():
    """Make sure plugins registered via entry points are detected."""
    ok_('urllink' in all_plugins().keys())


def test_construction():
    """If a plugin is a plain module, make sure it is automatically promoted to
    a Plugin via recognition of symbol naming conventions."""
    plugin = all_plugins()['urllink']
    ok_(plugin.tree_indexer is dxr.plugins.urllink.TreeIndexer)
