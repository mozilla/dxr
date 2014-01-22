"""Main entry point for dxr-build and dxr-serve commands."""

import argparse
import os.path

from dxr.app import make_app
from dxr.build import build_instance


def build_main():
    """Command to build a DXR instance from one or more source trees."""

    usage = ('usage: %(prog)s [options] [folder containing dxr.config | config '
             'file]')
    description = ('If no args are given, defaults to looking for a config '
                   'file called dxr.config in the current working directory.')
    parser = argparse.ArgumentParser(usage=usage, description=description)
    parser.add_argument('-f', '--file', dest='config_file',
                        help='A DXR config file. [Deprecated. Use the first '
                             'positional arg instead.]')
    parser.add_argument('-t', '--tree', dest='tree',
                        help='An INI section title in the config file, '
                             'specifying a source tree to build. (Default: all '
                             'trees.)')
    parser.add_argument('-j', '--jobs', dest='jobs',
                        type=int,
                        default=None,
                        help='Number of parallel processes to use, (Default: the'
                             ' value of nb_jobs in the config file)')
    parser.add_argument('-v', '--verbose', dest='verbose',
                        action='store_true', default=False,
                        help='Display the build logs during the build instead of'
                             ' only on error.')
    # this will contain the script/program name and any arguments for it.
    parser.add_argument('args', nargs=argparse.REMAINDER,
                        help=argparse.SUPPRESS)
    options = parser.parse_args()

    if len(options.args) > 1:
        parser.exit(1, parser.print_usage())

    elif options.args:
        # Handle deprecated --file arg:
        if options.config_file:
            print >> stderr, ('Warning: overriding the --file or -f flag with '
                              'the first positional argument.')
        options.config_file = (os.path.join(options.args[0], 'dxr.config') if
                               os.path.isdir(options.args[0]) else options.args[0])
    elif not options.config_file:
        # Assume dxr.config in the cwd:
        options.config_file = 'dxr.config'

    return build_instance(options.config_file,
                          nb_jobs=options.jobs,
                          tree=options.tree,
                          verbose=options.verbose)


def serve_main():
    """A simple test server for DXR, not suitable for production

    Use a web server with WSGI support for actual deployments.

    """
    parser = argparse.ArgumentParser(usage='usage: %(prog)s [options] build-folder',
                                     add_help=False)
    parser.add_argument('--help', action='help')
    parser.add_argument('-h', '--host', dest='host',
                        type=str,
                        default='localhost',
                        help='The host address to serve on')
    parser.add_argument('-a', '--all', dest='host',
                        action='store_const',
                        const='0.0.0.0',
                        help='Serve on all interfaces.  Equivalent to --host 0.0.0.0')
    parser.add_argument('-j', '--jobs', dest='processes',
                        type=int,
                        default=1,
                        help='The number of processes to use')
    parser.add_argument('-p', '--port', dest='port',
                        type=int,
                        default=8000,
                        help='The port to serve on')
    parser.add_argument('-t', '--threaded', dest='threaded',
                        action='store_true',
                        default=False,
                        help='Use a separate thread for each request')
    # this will contain the script/program name and any arguments for it.
    parser.add_argument('args', nargs=argparse.REMAINDER,
                        help=argparse.SUPPRESS)
    options = parser.parse_args()

    if len(options.args) == 1:
        app = make_app(os.path.abspath(args[0]))
        app.debug = True
        app.run(host=options.host, port=options.port,
                processes=options.processes, threaded=options.threaded)
    else:
        parser.exit(1, parser.print_usage())
