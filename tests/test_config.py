"""Tests for the configuration subsystem"""

from nose.tools import eq_, ok_

from dxr.config import Config
from dxr.exceptions import ConfigError


def test_enabled_star():
    """Make sure even plugins that aren't packages get enabled when
    enabled_plugins = *.

    """
    config = Config("""
        [DXR]
        enabled_plugins = *

        [some_tree]
        source_folder = /some/path
        object_folder = /some/path

            [[buglink]]
            url = http://example.com/

            [[python]]
            python_path = /some/path

            [[xpidl]]
            header_bucket = /somewhere
        """)
    ok_('urllink' in (p.name for p in config.trees['some_tree'].enabled_plugins))


def test_enabled_plugins():
    """Make sure enabled_plugins tolerates arbitrary whitespace between items,
    maintains its order, and includes the core plugin. Make sure a plugin
    section (buglink) isn't required unless its plugin is enabled.

    """
    config = Config("""
        [DXR]

        [mozilla-central]
        enabled_plugins = urllink   omniglot
        source_folder = /some/path
        object_folder = /some/path
        """)
    eq_([p.name for p in config.trees['mozilla-central'].enabled_plugins],
        ['core', 'urllink', 'omniglot'])


def test_plugin_section_required():
    """Since the buglink plugin is enabled, its required "url" arg under
    [[buglink]] must be specified.

    """
    try:
        config = Config("""
            [DXR]
            enabled_plugins = buglink

            [mozilla-central]
            source_folder = /some/path
            object_folder = /some/path
            """)
    except ConfigError as exc:
        eq_(exc.sections, ['mozilla-central'])
        ok_('buglink' in exc.message)
    else:
        self.fail("Didn't raise ConfigError")


def test_deep_attrs():
    """Test traversal of multiple layers of DotDictWrappers."""
    config = Config("""
        [DXR]
        enabled_plugins = buglink

        [mozilla-central]
        source_folder = /some/path
        object_folder = /some/path

            [[buglink]]
            url = http://example.com/
        """)
    eq_(config.trees['mozilla-central'].buglink.url, 'http://example.com/')


def test_multi_word_strings():
    """Make sure strings containing whitespace aren't split up unless the spec
    says they're a list.

    """
    config = Config("""
        [DXR]
        enabled_plugins = clang buglink

        [mozilla-central]
        source_folder = /some/path
        object_folder = /some/path

            [[buglink]]
            url = http://example.com/
            name = Big fat thing.
        """)
    eq_(config.trees['mozilla-central'].buglink.name, 'Big fat thing.')


def test_unknown_options():
    """Unknown options should throw an error.

    However, unknown options in a disabled plugin section should be ignored,
    for consistency with our ignoring invalid values there as well.

    """
    try:
        config = Config("""
            [DXR]
            enabled_plugins = clang
            disabled_plugins = buglink
            smoop = 5

            [mozilla-central]
            source_folder = /some/path
            object_folder = /some/path

                [[buglink]]
                url = http://example.com/
                name = Big fat thing.
            """)
    except ConfigError as exc:
        eq_(exc.sections, ['DXR'])
        ok_('smoop' in exc.message)
    else:
        self.fail("Didn't raise ConfigError")


def test_and_error():
    """Make sure I'm using the ``error`` kwargs of And correctly."""
    try:
        config = Config("""
            [DXR]
            enabled_plugins = clang
            workers = -5

            [mozilla-central]
            source_folder = /some/path
            object_folder = /some/path
            """)
    except ConfigError as exc:
        eq_(exc.sections, ['DXR'])
        ok_('non-negative' in exc.message)
    else:
        self.fail("Didn't raise ConfigError")
