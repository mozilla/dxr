#!/usr/bin/env python2.6
import os, sys
import re

def replaceVariables(template, virtroot, treename):
        """Takes templates, for example ${VIRTROOT/TREENAME/some/file.png} and does path/template replacement
           to provide a path string suitable for using with href="...".
        """
        if not template.startswith('${') and not template.endswith('}'): raise SyntaxError('Template format unknown.')
        template = template[2:-1]
        template = template.replace('VIRTROOT', virtroot)
        template = template.replace('TREENAME', treename)

        # deal with concurrent / issues by having os.path.join build the final path
        return os.path.join('/', *template.split('/'))

def expand(s, virtroot, treename):
    return re.sub('\$\{[^\}]+\}', lambda m: replaceVariables(m.group(0), virtroot, treename), s)

def readFile(filename, print_error=True):
    """Returns the contents of a file."""
    try:
        fp = open(filename)
        try:
            return fp.read()
        finally:
            fp.close()
    except IOError:
        if print_error:
            print('Error reading %s: %s' % (filename, sys.exc_info()[1]))
            return None
