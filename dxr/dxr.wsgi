from os import environ

from dxr.app import make_app


application = make_app(environ['DXR_FOLDER'])
