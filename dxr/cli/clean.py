from os import chdir

from click import ClickException, command

from dxr.cli.utils import tree_objects, config_option, tree_names_argument
from dxr.utils import run, CommandFailure, rmtree_if_exists


@command()
@config_option
@tree_names_argument
def clean(config, tree_names):
    """Remove logs, temp files, and build artifacts.

    Remove the filesystem debris left after indexing one or more TREES, leaving
    the index itself intact. Delete log files and, if present, temp files. Run
    `make clean` (or other clean_command from the config file) on trees.

    """
    for tree in tree_objects(tree_names, config):
        rmtree_if_exists(tree.log_folder)
        rmtree_if_exists(tree.temp_folder)
        chdir(tree.object_folder)
        if tree.clean_command:
            try:
                run(tree.clean_command)
            except CommandFailure as exc:
                raise ClickException(
                    'Running clean_command failed for "%s" tree: %s.' %
                    (tree.name, str(exc)))
