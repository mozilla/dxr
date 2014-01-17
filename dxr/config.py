from ConfigParser import ConfigParser
from datetime import datetime
import os
from os.path import isdir
import sys

import dxr


# Please keep these config objects as simple as possible and in sync with
# docs/configuration.mkd. I'm well aware that this is not the most compact way
# of writing things, but it sure is doomed to fail when user forgets an important
# key. It's also fairly easy to extract default values, and config keys from
# this code, so enjoy.

class Config(object):
    """ Configuration for DXR """
    def __init__(self, configfile, **override):
        # Create parser with sane defaults
        parser = ConfigParser({
            'dxrroot':          os.path.dirname(dxr.__file__),
            'plugin_folder':    "%(dxrroot)s/plugins",
            'nb_jobs':          "1",
            'temp_folder':      "/tmp/dxr-temp",
            'log_folder':       "%(temp_folder)s/logs",
            'wwwroot':          "/",
            'enabled_plugins':  "*",
            'disabled_plugins': " ",
            'directory_index':  ".dxr-directory-index.html",
            'generated_date':   datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000"),
            'disable_workers':  "",
            'skip_stages': ""
        })
        parser.read(configfile)

        # Set config values
        self.dxrroot          = parser.get('DXR', 'dxrroot',          False, override)
        self.plugin_folder    = parser.get('DXR', 'plugin_folder',    False, override)
        self.nb_jobs          = parser.get('DXR', 'nb_jobs',          False, override)
        self.temp_folder      = parser.get('DXR', 'temp_folder',      False, override)
        self.target_folder    = parser.get('DXR', 'target_folder',    False, override)
        self.log_folder       = parser.get('DXR', 'log_folder',       False, override)
        self.wwwroot          = parser.get('DXR', 'wwwroot',          False, override)
        self.enabled_plugins  = parser.get('DXR', 'enabled_plugins',  False, override)
        self.disabled_plugins = parser.get('DXR', 'disabled_plugins', False, override)
        self.directory_index  = parser.get('DXR', 'directory_index',  False, override)
        self.generated_date   = parser.get('DXR', 'generated_date',   False, override)
        self.disable_workers  = parser.get('DXR', 'disable_workers',  False, override)
        self.skip_stages      = parser.get('DXR', 'skip_stages',      False, override)
        # Set configfile
        self.configfile       = configfile
        self.trees            = []

        # Read all plugin_ keys
        for key, value in parser.items('DXR'):
            if key.startswith('plugin_'):
                setattr(self, key, value)

        # Render all paths absolute
        self.dxrroot          = os.path.abspath(self.dxrroot)
        self.plugin_folder    = os.path.abspath(self.plugin_folder)
        self.temp_folder      = os.path.abspath(self.temp_folder)
        self.log_folder       = os.path.abspath(self.log_folder)
        self.target_folder    = os.path.abspath(self.target_folder)

        # Make sure wwwroot doesn't end in /
        if self.wwwroot[-1] == '/':
            self.wwwroot = self.wwwroot[:-1]

        # Convert disabled plugins to a list
        if self.disabled_plugins == "*":
            self.disabled_plugins = os.listdir(self.plugin_folder)
        else:
            self.disabled_plugins = self.disabled_plugins.split()

        # Convert skipped stages to a list
        self.skip_stages = self.skip_stages.split()

        # Convert enabled plugins to a list
        if self.enabled_plugins == "*":
            self.enabled_plugins = [
                p for p in os.listdir(self.plugin_folder) if
                isdir(os.path.join(self.plugin_folder, p)) and
                p not in self.disabled_plugins]
        else:
            self.enabled_plugins = self.enabled_plugins.split()

        # Test for conflicting plugins settings
        conflicts = [p for p in self.disabled_plugins if p in self.enabled_plugins]
        if conflicts:
            msg = "Plugin: '%s' is both enabled and disabled"
            for p in conflicts:
                print >> sys.stderr, msg % p
            sys.exit(1)

        # Load trees
        def section_cmp(a, b):
            if parser.has_option(a, "order") and parser.has_option(b, "order"):
                return cmp(parser.getint(a, "order"), parser.getint(b, "order"))
            if (not parser.has_option(a, "order")) and (not parser.has_option(b, "order")):
                return cmp(a, b)
            return -1 if parser.has_option(a, "order") else 1

        for tree in sorted(parser.sections(), section_cmp):
            # Don't interpret legacy [Template] section as a tree:
            if tree not in ('DXR', 'Template'):
                self.trees.append(TreeConfig(self, self.configfile, tree))


class TreeConfig(object):
    """ Tree configuration for DXR """
    def __init__(self, config, configfile, name):
        # Create parser with sane defaults
        parser = ConfigParser({
            'enabled_plugins':  "*",
            'disabled_plugins': "",
            'temp_folder':      os.path.join(config.temp_folder, name),
            'log_folder':       os.path.join(config.log_folder, name),
            'ignore_patterns':  ".hg .git CVS .svn .bzr .deps .libs",
            'build_command':    "make -j $jobs",
            'source_encoding':  'utf-8',
            'description':  ''
        })
        parser.read(configfile)

        # Set config values
        self.enabled_plugins  = parser.get(name, 'enabled_plugins')
        self.disabled_plugins = parser.get(name, 'disabled_plugins')
        self.temp_folder      = parser.get(name, 'temp_folder')
        self.log_folder       = parser.get(name, 'log_folder')
        self.object_folder    = parser.get(name, 'object_folder')
        self.source_folder    = parser.get(name, 'source_folder')
        self.build_command    = parser.get(name, 'build_command')
        self.ignore_patterns  = parser.get(name, 'ignore_patterns')
        self.source_encoding  = parser.get(name, 'source_encoding')
        self.description      = parser.get(name, 'description')

        # You cannot redefine the target folder!
        self.target_folder    = os.path.join(config.target_folder, 'trees', name)
        # Set config file and DXR config object reference
        self.configfile       = configfile
        self.config           = config
        self.name             = name

        # Read all plugin_ keys
        for key, value in parser.items(name):
            if key.startswith('plugin_'):
                setattr(self, key, value)

        # Convert ignore patterns to list
        self.ignore_patterns  = self.ignore_patterns.split()
        self.ignore_paths     = filter(lambda p: p.startswith("/"), self.ignore_patterns)
        self.ignore_patterns  = filter(lambda p: not p.startswith("/"), self.ignore_patterns)

        # Render all path absolute
        self.temp_folder      = os.path.abspath(self.temp_folder)
        self.log_folder       = os.path.abspath(self.log_folder)
        self.object_folder    = os.path.abspath(self.object_folder)
        self.source_folder    = os.path.abspath(self.source_folder)

        # Convert disabled plugins to a list
        if self.disabled_plugins == "*":
            self.disabled_plugins = config.enabled_plugins
        else:
            self.disabled_plugins = self.disabled_plugins.split()
            for p in config.disabled_plugins:
                if p not in self.disabled_plugins:
                    self.disabled_plugins.append(p)

        # Convert enabled plugins to a list
        if self.enabled_plugins == "*":
            self.enabled_plugins = [p for p in config.enabled_plugins
                                    if p not in self.disabled_plugins]
        else:
            self.enabled_plugins = self.enabled_plugins.split()

        # Test for conflicting plugins settings
        conflicts = [p for p in self.disabled_plugins if p in self.enabled_plugins]
        if conflicts:
            msg = "Plugin: '%s' is both enabled and disabled in '%s'"
            for p in conflicts:
                print >> sys.stderr, msg % (p, name)
            sys.exit(1)

        # Warn if $jobs isn't used...
        if "$jobs" not in self.build_command:
            msg = "Warning: $jobs is not used in build_command for '%s'"
            print >> sys.stderr, msg % name
