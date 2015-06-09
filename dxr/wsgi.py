import os
from os.path import dirname

from dxr.app import make_app
from dxr.config import Config
from dxr.utils import file_text


def application(environ, start_response):
    """Pull the config file path out of an env var, and then instantiate the
    WSGI app as normal.

    This prefers the Apache SetEnv sort of environment; but if that's missing,
    try the process-level env var instead since it's easier to set for some
    users, like those using Stackato.

    """
    try:
        config_path = environ['DXR_CONFIG']
    except KeyError:
        # Not found in WSGI env. Try process env:
        # If this still fails, this is a fatal error.
        config_path = os.environ['DXR_CONFIG']
    return make_app(Config(file_text(config_path),
                           relative_to=dirname(config_path)))(environ,
                                                              start_response)
