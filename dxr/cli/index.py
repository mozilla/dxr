from click import command, option

from dxr.build import index_and_deploy_tree
from dxr.cli.utils import tree_objects, config_option, tree_names_argument


@command()
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
