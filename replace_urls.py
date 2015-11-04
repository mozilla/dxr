#!/usr/bin/env python
"""Replace unhashed URLs in a stylesheet with hashed ones::

    replace_urls.py <mapping file> <CSS file> > <new CSS file>

"""
import re
from sys import argv


def main(map_path, input_path):
    with open(map_path) as file:
        map = dict(line.split() for line in file)

    def replacer(match):
        url = match.group(1)
        return (("url('/static/%s')" % map[url]) if url in map
                else match.group())

    with open(input_path) as file:
        return re.sub(r"url\('/static/([^']+)'\)", replacer, file.read())

print main(argv[1], argv[2])
