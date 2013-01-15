#!/usr/bin/env python2
"""
A simple test server for DXR, NOT a deployment server

Use Apache or something else for deployments; this is NOT designed with
security in mind. Note: support for mod_rewrite or something similar is quite
important.

"""
import sys

from dxr.app import app


def main():
    port = (int(sys.argv[2])
            if len(sys.argv) > 2 and sys.argv[1] == '--port' else 8000)
    app.debug = True
    # Without binding to a public interface (0.0.0.0), you can't get to the
    # Vagrant box's test server from the host machine.
    app.run(host='0.0.0.0', port=port)


if __name__ == '__main__':
    main()
