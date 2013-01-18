from dxr.app import make_app


def application(environ, start_response):
    """Pull the instance path out of an env var, and then instantiate the WSGI
    app as normal.

    Note that this isn't a process-level env var but rather the sort you'd
    create with a SetEnv call in your Apache config.

    """
    return make_app(environ['DXR_FOLDER'])(environ, start_response)
