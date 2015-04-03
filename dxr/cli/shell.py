from click import command, option

from dxr.app import make_app
from dxr.cli.utils import config_option


def _plain_shell(namespace):
    """Start a plain python shell."""
    import code
    import readline
    import rlcompleter

    readline.set_completer(rlcompleter.Completer(namespace).complete)
    readline.parse_and_bind('tab:complete;')
    code.interact(local=namespace)


def _ipython(namespace):
    """Start IPython."""
    from IPython import start_ipython
    start_ipython(argv=[], user_ns=namespace)


_shells = [_ipython, _plain_shell]


@command()
@config_option
@option('--plain', '-p',
        is_flag=True,
        default=False,
        help='Use a plain shell instead of IPython if available.')
def shell(config, plain):
    """Run a Python interactive interpreter."""
    app = make_app(config)
    app.debug = True
    with app.app_context():
        namespace = {'app': app, 'config': config}

        if plain:
            _plain_shell(namespace)
        else:
            for shell in _shells:
                try:
                    shell(namespace)
                except ImportError:
                    pass
                else:
                    break
