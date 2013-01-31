#!/usr/bin/env python2

import getopt
import sys

from dxr.build import build_instance


def main(argv):
    # Options to read
    configfile  = None
    nb_jobs     = None # Allow us to overwrite config
    tree        = None

    # Parse arguments
    try:
        params = ["help", "file=", "tree=", "jobs="]
        options, args = getopt.getopt(argv, "hf:t:j:s", params)
    except getopt.GetoptError:
        print >> sys.stderr, "Failed to parse options"
        print_usage()
        sys.exit(1)
    for arg, opt in options:
        if arg in ('-f', '--file'):
            if not configfile:
                configfile = opt
            else:
                print >> sys.stderr, "Only one config file can be provided"
                sys.exit(1)
        elif arg in ('-h', '--help'):
            print_help()
            sys.exit(0)
        elif arg in ('-t', '--tree'):
            if tree is not None:
                print >> sys.stderr, "More than one tree option is provided!"
                sys.exit(1)
            tree = opt
        elif arg in ('-j', '--jobs'):
            nb_jobs = opt
        else:
            print >> sys.stderr, "Unknown option '%s'" % arg
            print_usage()
            sys.exit(1)

    # Abort if we didn't get a config file
    if not configfile:
        print_usage()
        sys.exit(1)

    build_instance(configfile, nb_jobs=nb_jobs, tree=tree)


def print_help():
    print_usage()
    print """Options:
    -h, --help                     Show help information.
    -f, --file    FILE             Use FILE as config file
    -t, --tree    TREE             Index and Build only section TREE (default is all)
    -j, --jobs    JOBS             Use JOBS number of parallel processes (default 1)"""


def print_usage():
    print "Usage: dxr-index.py -f FILE (--tree TREE)"


if __name__ == '__main__':
    main(sys.argv[1:])
