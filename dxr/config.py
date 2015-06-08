"""Configuration file abstractions

Please update docs/source/configuration.rst when you change this.

"""
from datetime import datetime
from multiprocessing import cpu_count
from ordereddict import OrderedDict
from operator import attrgetter
from os import getcwd
from os.path import abspath, join

from configobj import ConfigObj
from funcy import merge
from more_itertools import first
from pkg_resources import resource_string
from schema import Schema, Optional, Use, And, Schema, SchemaError

from dxr.exceptions import ConfigError
from dxr.plugins import all_plugins
from dxr.utils import cd, if_raises


# Format version, signifying the instance format this web frontend code is
# able to serve. Must match exactly; deploy will do nothing until it does.
FORMAT = resource_string('dxr', 'format').strip()


class DotSection(object):
    """In the absense of an actual attribute, let attr lookup fall through to
    ``self._section[attr]``."""

    def __getattr__(self, attr):
        if not hasattr(self, '_section'):  # Happens during unpickling
            raise AttributeError(attr)
        try:
            val = self._section[attr]
        except KeyError:
            raise AttributeError(attr)
        if isinstance(val, dict):
            # So we can dot into nested dicts
            return DotSectionWrapper(val)
        return val


class DotSectionWrapper(DotSection):
    """A wrapper for non-first-level sections so we can dot our way through
    them as well"""

    def __init__(self, section):
        self._section = section


class Config(DotSection):
    """Validation and encapsulation for the DXR config file

    Examples::

        # Settings from the [DXR] section:
        >>> Config(...).default_tree

        # Settings from individual trees:
        >>> Config(...).trees['some-tree'].build_command

        # Settings from plugin-specific sections of trees:
        >>> Config(...).trees['some-tree'].buglink.url

    """
    # Design decisions:
    # * Keep the explicit [DXR] section name because, otherwise, global options
    #   can collide with tree names.
    # * Keep tree.config shortcut. It makes a lot of things shorter and doesn't
    #   hurt anything, since it's all read-only anyway.
    # * Crosswire __getattr__ with __getitem__. It makes callers more readable.
    # * Keep whitespace-delimited lists in config file. I prefer them to
    #   commas, people will have to change less, and it wasn't a big deal to
    #   customize.
    # * Use configobj to parse the ini file and then schema to validate it.
    #   configobj's favored "validate" module makes it very hard to have
    #   whitespace-delimited lists and doesn't compose well since its
    #   validators are strings. The downside is we only report 1 error at a
    #   time, but this can and should be fixed in the schema lib.

    def __init__(self, input, relative_to=None):
        """Pull in and validate a config file.

        :arg input: A string or dict from which to populate the config
        :arg relative_to: The dir relative to which to interpret relative paths

        Raise ConfigError if the configuration is invalid.

        """
        schema = Schema({
            'DXR': {
                Optional('temp_folder', default=abspath('dxr-temp-{tree}')):
                    AbsPath,
                Optional('default_tree', default=None): basestring,
                Optional('disabled_plugins', default=plugin_list('')): Plugins,
                Optional('enabled_plugins', default=plugin_list('*')): Plugins,
                Optional('generated_date',
                         default=datetime.utcnow()
                                         .strftime("%a, %d %b %Y %H:%M:%S +0000")):
                    basestring,
                Optional('log_folder', default=abspath('dxr-logs-{tree}')):
                    AbsPath,
                Optional('workers', default=if_raises(NotImplementedError,
                                                      cpu_count,
                                                      1)):
                    And(Use(int),
                        lambda v: v >= 0,
                        error='"workers" must be a non-negative integer.'),
                Optional('skip_stages', default=[]): WhitespaceList,
                Optional('www_root', default=''): Use(lambda v: v.rstrip('/')),
                Optional('google_analytics_key', default=''): basestring,
                Optional('es_hosts', default='http://127.0.0.1:9200/'):
                    WhitespaceList,
                Optional('es_index', default='dxr_{format}_{tree}_{unique}'):
                    basestring,
                Optional('es_alias', default='dxr_{format}_{tree}'):
                    basestring,
                Optional('es_catalog_index', default='dxr_catalog'):
                    basestring,
                Optional('es_catalog_replicas', default=1):
                    basestring,
                Optional('max_thumbnail_size', default=20000):
                    And(Use(int),
                        lambda v: v >= 0,
                        error='"max_thumbnail_size" must be a non-negative '
                              'integer.'),
                Optional('es_indexing_timeout', default=60):
                    And(Use(int),
                        lambda v: v >= 0,
                        error='"es_indexing_timeout" must be a non-negative '
                              'integer.'),
                Optional('es_refresh_interval', default=60):
                    And(Use(int),
                        error='"es_indexing_timeout" must be an integer.')
            },
            basestring: dict
        })

        # Parse the ini into nested dicts:
        config_obj = ConfigObj(input.splitlines() if isinstance(input,
                                                                basestring)
                               else input,
                               list_values=False)

        if not relative_to:
            relative_to = getcwd()
        with cd(relative_to):
            try:
                config = schema.validate(config_obj.dict())
            except SchemaError as exc:
                raise ConfigError(exc.code, ['DXR'])

            self._section = config['DXR']

            # Normalize enabled_plugins:
            if self.enabled_plugins.is_all:
                # Then explicitly enable anything that isn't explicitly
                # disabled:
                self._section['enabled_plugins'] = [
                        p for p in all_plugins().values()
                        if p not in self.disabled_plugins]

            # Now that enabled_plugins and the other keys that TreeConfig
            # depends on are filled out, make some TreeConfigs:
            self.trees = OrderedDict()  # name -> TreeConfig
            for section in config_obj.sections:
                if section != 'DXR':
                    try:
                        self.trees[section] = TreeConfig(section,
                                                         config[section],
                                                         config_obj[section].sections,
                                                         self)
                    except SchemaError as exc:
                        raise ConfigError(exc.code, [section])

        # Make sure default_tree is defined:
        if not self.default_tree:
            self._section['default_tree'] = first(self.trees.iterkeys())

        # These aren't intended for actual use; they're just to influence
        # enabled_plugins of trees, and now we're done with them:
        del self._section['enabled_plugins']
        del self._section['disabled_plugins']


class TreeConfig(DotSectionWrapper):
    def __init__(self, name, unvalidated_tree, sections, config):
        """Fix up settings that depend on the [DXR] section or have
        inter-setting dependencies. (schema can't do multi-setting validation
        yet, and configobj can't do cross-section interpolation.)

        Add a ``config`` attr to trees as a shortcut back to the [DXR] section
        and a ``name`` attr to save cumbersome tuple unpacks in callers.

        """
        self.config = config
        self.name = name

        schema = Schema({
            Optional('build_command', default='make -j {workers}'): basestring,
            Optional('clean_command', default='make clean'): basestring,
            Optional('description', default=''): basestring,
            Optional('disabled_plugins', default=plugin_list('')): Plugins,
            Optional('enabled_plugins', default=plugin_list('*')): Plugins,
            Optional('ignore_patterns',
                     default=['.hg', '.git', 'CVS', '.svn', '.bzr',
                              '.deps', '.libs', '.DS_Store', '.nfs*', '*~',
                              '._*']): WhitespaceList,
            Optional('object_folder', default=None): AbsPath,
            'source_folder': AbsPath,
            Optional('source_encoding', default='utf-8'): basestring,
            Optional('temp_folder', default=None): AbsPath,
            Optional('p4web_url', default='http://p4web/'): basestring,
            Optional(basestring): dict})
        tree = schema.validate(unvalidated_tree)

        if tree['temp_folder'] is None:
            tree['temp_folder'] = config.temp_folder
        if tree['object_folder'] is None:
            tree['object_folder'] = tree['source_folder']

        # Convert enabled_plugins to a list of plugins:
        if tree['disabled_plugins'].is_all:
            # * doesn't really mean "all" in a tree. It means "everything the
            # [DXR] section enabled".
            tree['disabled_plugins'] = config.enabled_plugins
        else:
            # Add anything globally disabled to our local disabled list:
            tree['disabled_plugins'].extend(p for p in config.disabled_plugins
                                            if p not in
                                            tree['disabled_plugins'])

        if tree['enabled_plugins'].is_all:
            tree['enabled_plugins'] = [p for p in config.enabled_plugins
                                       if p not in tree['disabled_plugins']]
        tree['enabled_plugins'].insert(0, all_plugins()['core'])

        # Split ignores into paths and filenames:
        tree['ignore_paths'] = [i for i in tree['ignore_patterns']
                                if i.startswith('/')]
        tree['ignore_filenames'] = [i for i in tree['ignore_patterns']
                                    if not i.startswith('/')]

        # Delete misleading, useless, or raw values people shouldn't use:
        del tree['ignore_patterns']
        del tree['disabled_plugins']

        # Validate plugin config:
        enableds_with_all_optional_config = set(
            p for p in tree['enabled_plugins']
            if all(isinstance(k, Optional) for k in p.config_schema.iterkeys()))
        plugin_schema = Schema(merge(
            dict((Optional(name) if plugin in enableds_with_all_optional_config
                                 or plugin not in tree['enabled_plugins']
                  else name,
                  plugin.config_schema)
                 for name, plugin in all_plugins().iteritems()
                 if name != 'core'),
            # And whatever isn't a plugin section, that we don't care about:
            {object: object}))
        # Insert empty missing sections for enabled plugins with entirely
        # optional config so their defaults get filled in. (Don't insert them
        # if the plugin has any required options; then we wouldn't produce the
        # proper error message about the section being absent.)
        for plugin in enableds_with_all_optional_config:
            tree.setdefault(plugin.name, {})
        tree = plugin_schema.validate(tree)

        super(TreeConfig, self).__init__(tree)

    @property
    def log_folder(self):
        """Return the global log_folder with the tree name subbed in."""
        return self.config.log_folder.format(tree=self.name)

    @property
    def temp_folder(self):
        """Return ``self.temp_folder`` with the tree name subbed in."""
        return self.config.temp_folder.format(tree=self.name)


class ListAndAll(list):
    """A list we can also store an ``all`` attr on, indicating whether it
    was derived from a configuration value of ``*``"""


def plugin_list(value):
    """Turn a space-delimited series of plugin names into a ListAndAll of
    Plugins.

    """
    if not isinstance(value, basestring):
        raise SchemaError('"%s" is neither * nor a whitespace-delimited list '
                          'of plugin names.' % (value,))

    plugins = all_plugins()
    names = value.strip().split()
    is_all = names == ['*']
    if is_all:
        names = plugins.keys()
    try:
        ret = ListAndAll([plugins[name] for name in names])
        ret.is_all = is_all
        return ret
    except KeyError:
        raise SchemaError('Never heard of plugin "%s". I\'ve heard of '
                          'these: %s.' % (name, ', '.join(plugins.keys())))
Plugins = Use(plugin_list)


WhitespaceList = And(basestring,
                     Use(lambda value: value.strip().split()),
                     error='This should be a whitespace-separated list.')


# Turn a filesystem path into an absolute one so changing the working
# directory doesn't keep us from finding them.
AbsPath = And(basestring, Use(abspath), error='This should be a path.')
