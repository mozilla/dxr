#!/usr/bin/env python2
"""A simple test server for DXR, not suitable for production

Use a web server with WSGI support for actual deployments.

"""
from optparse import OptionParser
from os.path import abspath

from dxr.app import make_app


def main():
    parser = OptionParser(usage='usage: %prog [options] build-folder',
                          add_help_option=False)
    parser.add_option('--help', action='help')
    parser.add_option('-a', '--all', dest='host',
                      action='store_const',
                      const='0.0.0.0',
                      help='Serve on all interfaces.  Equivalent to --host 0.0.0.0')
    parser.add_option('-h', '--host', dest='host',
                      type='string',
                      default='localhost',
                      help='The host address to serve on')
    parser.add_option('-j', '--jobs', dest='processes',
                      type='int',
                      default=1,
                      help='The number of processes to use')
    parser.add_option('-p', '--port', dest='port',
                      type='int',
                      default=8000,
                      help='The port to serve on')
    parser.add_option('-t', '--threaded', dest='threaded',
                      action='store_true',
                      default=False,
                      help='Use a separate thread for each request')
    options, args = parser.parse_args()
    if len(args) == 1:
        app = make_app(abspath(args[0]))
        app.debug = True
        app.run(host=options.host, port=options.port,
                processes=options.processes, threaded=options.threaded)
    else:
        parser.print_usage()


if __name__ == '__main__':
    main()
