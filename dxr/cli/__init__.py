"""Command-line interface for DXR"""

from os.path import basename
from sys import argv

from click import ClickException, group

from dxr.cli.clean import clean
from dxr.cli.delete import delete
from dxr.cli.deploy import deploy
from dxr.cli.index import index
from dxr.cli.serve import serve
from dxr.cli.shell import shell
from dxr.cli.utils import tree_objects, config_option, tree_names_argument


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


@group()
def dxr():
    """Pass dxr COMMAND --help to learn more about an individual command."""


dxr.add_command(index)
dxr.add_command(clean)
dxr.add_command(delete)
dxr.add_command(serve)
dxr.add_command(shell)
dxr.add_command(deploy)
