from os.path import abspath, dirname

from click import ClickException, option, Path, argument

from dxr.config import Config


def tree_objects(tree_names, config):
    """Return TreeConfigs given their names, or all trees if none are given.

    Raise ClickException if any requested tree isn't available.

    """
    if tree_names:
        try:
            return [config.trees[name] for name in tree_names]
        except KeyError:
            raise ClickException("Tree '%s' is not defined in config file." %
                                 name)
    else:
        return config.trees.values()


class ConfigObject(Path):
    """Like the Path type, except change directory to the one containing the
    config file so we can resolve relative paths properly, and return a Config
    object constructed from the file contents.

    """
    def convert(self, value, param, ctx):
        # Convert to an abs path, but don't resolve symlinks, unlike parent's
        # resolve_path behavior:
        path = abspath(super(ConfigObject, self).convert(value, param, ctx))

        with open(path, 'r') as file:
            return Config(file.read(), relative_to=dirname(path))


# A factoring out of the common --config option, used in most subcommands:
config_option = option('--config', '-c',
                       default='dxr.config',
                       type=ConfigObject(exists=True,
                                         dir_okay=False,
                                         readable=True),
                       show_default=True,
                       help='The configuration file')
tree_names_argument = argument('tree_names', metavar='TREES', nargs=-1)
