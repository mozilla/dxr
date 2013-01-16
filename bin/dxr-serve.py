#!/usr/bin/env python2
"""
A simple test server for DXR, NOT a deployment server

Use Apache or something else for deployments; this is NOT designed with
security in mind. Note: support for mod_rewrite or something similar is quite
important.

"""
from optparse import OptionParser
from os.path import abspath

from dxr.app import make_app


def main():
    parser = OptionParser(usage='usage: %prog [options] build-folder')
    parser.add_option('-p', '--port', dest='port',
                      type='int',
                      default=8000,
                      help='The port to serve on')
    options, args = parser.parse_args()
    if len(args) == 1:
        app = make_app(abspath(args[0]))
        app.debug = True
        # Without binding to a public interface (0.0.0.0), you can't get to the
        # Vagrant box's test server from the host machine.
        app.run(host='0.0.0.0', port=options.port)
    else:
        parser.print_usage()


if __name__ == '__main__':
    main()
