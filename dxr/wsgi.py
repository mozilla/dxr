from dxr.app import make_app
import os


def application(environ, start_response):
    """Pull the instance path out of an env var, and then instantiate the WSGI
    app as normal.

    This prefers the Apache SetEnv sort of environment; but if that's missing,
    try the process-level env var instead since it's easier to set for some
    users, like those using Stackato.

    """
    try:
        dxr_folder = environ['DXR_FOLDER']
    except KeyError:
        # Not found in WSGI env. Try process env:
        # If this still fails, this is a fatal error.
        dxr_folder = os.environ['DXR_FOLDER']
    return make_app(dxr_folder)(environ, start_response)
