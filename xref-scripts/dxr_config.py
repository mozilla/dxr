#!/usr/bin/env python2.6

import os
from ConfigParser import ConfigParser

def load(configFile):
    config = ConfigParser()
    config.read(configFile)

    dxrconfig = {}

    # Strip any trailing slashes from path strings
    dxrconfig["xrefscripts"] = os.path.abspath(config.get('DXR', 'xrefscripts'))
    dxrconfig["templates"] = os.path.abspath(config.get('DXR', 'templates'))
    dxrconfig["wwwdir"] = os.path.abspath(config.get('Web', 'wwwdir'))
    dxrconfig["virtroot"] = os.path.normpath(config.get('Web', 'virtroot'))
    dxrconfig["hosturl"] = config.get('Web', 'hosturl')
    if dxrconfig["hosturl"].endswith('/'):
      dxrconfig["hosturl"] = dxrconfig["hosturl"][0:-1]

    dxrconfig["trees"] = []
    for section in config.sections():
        # Look for DXR and Web and anything else is a tree description
        if section == 'DXR' or section == 'Web':
            continue
        else:
            treeconfig = {}
            treeconfig["tree"] = section
            treeconfig["sourcedir"] = os.path.abspath(config.get(section, 'sourcedir'))
            treeconfig["objdir"] = os.path.abspath(config.get(section, 'objdir'))

            dxrconfig["trees"].append(treeconfig)

    return dxrconfig
