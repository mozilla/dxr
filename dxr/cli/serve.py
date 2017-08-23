from click import command, option

from dxr.app import make_app
from dxr.cli.utils import config_option


@command()
@config_option
@option('--all', '-a',
        'host',
        is_flag=True,
        flag_value='0.0.0.0',
        help='Serve on all interfaces.  Equivalent to --host 0.0.0.0')
@option('--host', '-h',
        default='localhost',
        show_default=True,
        help='The host address to serve on')
@option('--workers', '-w',
        default=1,
        show_default=True,
        help='The number of processes or threads to use')
@option('--port', '-p',
        default=8000,
        show_default=True,
        help='The port to serve on')
@option('--threaded', '-t',
        is_flag=True,
        default=False,
        help='Use a separate thread for each request')
def serve(config, host, workers, port, threaded):
    """Run a toy version of the web app.

    This is a simply test server for DXR, not suitable for production use. For
    actual deployments, use a web server with WSGI support.

    """
    app = make_app(config)
    app.debug = True
    app.run(host=host, port=port, processes=workers, threaded=threaded)
