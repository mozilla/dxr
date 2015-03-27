"""Command-line interface for DXR"""

from errno import ENOENT
from os import chdir
from os.path import abspath, basename, dirname
from shutil import rmtree
from sys import argv

from click import ClickException, echo, group, option, Path, argument
from pyelasticsearch import ElasticSearch

from dxr.app import make_app
from dxr.build import index_and_deploy_tree
from dxr.config import Config
from dxr.utils import run, CommandFailure


def main():
    """Invoke Click's top level without swallowing the trackbacks produced by
    control-C.

    The swallowing makes it difficult to debug hangs.

    """
    try:
        # We can't call BaseCommand.main(), because it re-raises
        # KeyboardInterrupts as Aborts, obscuring the original source of the
        # exception.
        with dxr.make_context(basename(argv[0]), argv[1:]) as ctx:
            return dxr.invoke(ctx)
    except ClickException as exc:
        exc.show()
        return exc.exit_code


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
                       help='The configuration file')
tree_names_argument = argument('tree_names', metavar='TREES', nargs=-1)


@group()
def dxr():
    """Pass dxr COMMAND --help to learn more about an individual command."""


@dxr.command()
@config_option
@option('--verbose', '-v',
        is_flag=True,
        help='Display the build logs during the build instead of only '
             'on error.')
@tree_names_argument
def index(config, verbose, tree_names):
    """Build indices for one or more trees.

    When finished, update elasticsearch aliases and the catalog index to make
    the new indices available to the DXR server process.

    Each of TREES is an INI section title from the config file, specifying a
    source tree to build. If none are specified, we build all trees, in the
    order they occur in the file.

    """
    for tree in tree_objects(tree_names, config):
        index_and_deploy_tree(tree, verbose=verbose)


@dxr.command()
@config_option
@tree_names_argument
def clean(config, tree_names):
    """Remove logs, temp files, and build artifacts.

    Remove the filesystem debris left after indexing one or more TREES, leaving
    the index itself intact. Delete log files and, if present, temp files. Run
    `make clean` (or other clean_command from the config file) on trees.

    """
    def rmtree_quietly(folder):
        """Remove a folder if it exists. Otherwise, do nothing."""
        try:
            rmtree(folder)
        except OSError as exc:
            if exc.errno != ENOENT:
                raise

    for tree in tree_objects(tree_names, config):
        rmtree_quietly(tree.log_folder)
        rmtree_quietly(tree.temp_folder)
        chdir(tree.object_folder)
        if tree.clean_command:
            try:
                run(tree.clean_command)
            except CommandFailure as exc:
                raise ClickException(
                    'Running clean_command failed for "%s" tree: %s.' %
                    (tree.name, str(exc)))


@dxr.command()
@config_option
@option('--force', '-f',
        is_flag=True,
        help='Skip prompting for confirmation.')
@option('--all', '-a',
        is_flag=True,
        help='Delete all trees, and also delete the catalog index, in case it '
             'was somehow corrupted.')
@tree_names_argument
def delete(config, tree_names, all, force):
    """Delete indices and their catalog entries."""
    es = ElasticSearch(config.es_hosts)
    if all:
        echo('Deleting catalog...')
        es.delete_index(config.es_catalog_index)


@dxr.command()
@config_option
@option('--all', '-a',
        'host',
        is_flag=True,
        flag_value='0.0.0.0',
        help='Serve on all interfaces.  Equivalent to --host 0.0.0.0')
@option('--host', '-h',
        default='localhost',
        help='The host address to serve on')
@option('--workers', '-w',
        default=1,
        help='The number of processes or threads to use')
@option('--port', '-p',
        default=8000,
        help='The port to serve on')
@option('--threaded', '-t',
        is_flag=True,
        default=False,
        help='Use a separate thread for each request')
def serve(config, host, workers, port, threaded):
    """Run the web frontend.

    This is a simply test server for DXR, not suitable for production use. For
    actual deployments, use a web server with WSGI support.

    """
    app = make_app(config)
    app.debug = True
    app.run(host=host, port=port, processes=workers, threaded=threaded)
