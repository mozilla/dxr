# -*- coding: utf-8 -*-
import dxr.plugins
import re
import cgi
import urllib

""" Regular expression for matching urls
Credits to: http://stackoverflow.com/a/1547940
"""
pat  = "\[(https?://[A-Za-z0-9\-\._~:\/\?#[\]@!\$&'()*\+,;=%]+\.[A-Za-z0-9\-\._~:\/\?#[\]@!\$&'()*\+,;=%]+)\]"
pat += "|\((https?://[A-Za-z0-9\-\._~:\/\?#[\]@!\$&'()*\+,;=%]+\.[A-Za-z0-9\-\._~:\/\?#[\]@!\$&'()*\+,;=%]+)\)"
pat += "|(https?://[A-Za-z0-9\-\._~:\/\?#[\]@!\$&'()*\+,;=%]+\.[A-Za-z0-9\-\._~:\/\?#[\]@!\$&'()*\+,;=%]+)"
urlFinder = re.compile(pat)

def load(tree, conn):
    # Nothing to do here
    pass

class UrlHtmlifier(object):
    def __init__(self, text):
        self.text = text
    
    def refs(self):
        for m in urlFinder.finditer(self.text):
            try:
                if m.group(1):
                    url = m.group(1).decode('utf-8')
                    start, end = m.start(1), m.end(1)
                elif m.group(2):
                    url = m.group(2).decode('utf-8')
                    start, end = m.start(2), m.end(2)
                else:
                    url = m.group(3).decode('utf-8')
                    start, end = m.start(3), m.end(3)
            except UnicodeDecodeError:
                pass
            else:
                yield start, end, ([{
                    'html':   "Follow link",
                    'title':  "Visit %s" % url,
                    'href':   url,
                    'icon':   'external_link'
                }], '', None)
    
    def regions(self):
        return []

    def annotations(self):
        return []

    def links(self):
        return []


def htmlify(path, text):
    return UrlHtmlifier(text)

__all__ = dxr.plugins.htmlifier_exports()
