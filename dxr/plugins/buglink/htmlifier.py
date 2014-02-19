import cgi
import re
import sys

import dxr.plugins


# Global variables
url       = None
name      = None
bug_finder = None


# Load global variables
def load(tree, conn):
    global url, name, bug_finder

    # Get bug tracker name
    if hasattr(tree, 'plugin_buglink_name'):
        name = tree.plugin_buglink_name
    else:
        print >> sys.stderr, 'buglink plugin needs plugin_buglink_name configuration key'
        sys.exit(1)

    # Get link
    # The plugin_buglink_bugzilla option behaves identically but is deprecated.
    url = getattr(tree, 'plugin_buglink_url',
                        getattr(tree, 'plugin_buglink_bugzilla', None))
    if url is None:
        print >> sys.stderr, 'buglink plugin needs plugin_buglink_url configuration key'
        sys.exit(1)

    # Get bug finder regex
    bug_finder = re.compile(getattr(tree,
                                    'plugin_buglink_regex',
                                    r'(?i)bug\s+#?([0-9]+)'))


class BugLinkHtmlifier(object):
    def __init__(self, text):
        self.text = text

    def refs(self):
        global name
        for m in bug_finder.finditer(self.text):
            bug = m.group(1)
            yield m.start(0), m.end(0), ([{
                'html': cgi.escape("Lookup #%s" % bug),
                'title': "Find this bug number at %s" % name,
                'href': url % bug,
                'icon': 'buglink'
            }], '', None)

    def regions(self):
        return []

    def annotations(self):
        return []

    def links(self):
        return []


def htmlify(path, text):
    return BugLinkHtmlifier(text)


__all__ = dxr.plugins.htmlifier_exports()
