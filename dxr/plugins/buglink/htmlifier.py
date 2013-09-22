import dxr.plugins
import re
import sys

# Global variables
bugzilla  = None
name      = None
bugFinder = None

# Load global variables
def load(tree, conn):
    global bugzilla
    # Get bugzilla link
    if hasattr(tree, 'plugin_buglink_bugzilla'):
        bugzilla = tree.plugin_buglink_bugzilla
    else:
        print >> sys.stderr, "buglink plugin needs plugin_buglink_bugzilla configuration key"
        sys.exit(1)
    # Get bug tracker name
    if hasattr(tree, 'plugin_buglink_name'):
        name = tree.plugin_buglink_name
    else:
        print >> sys.stderr, "buglink plugin needs plugin_buglink_name configuration key"
        sys.exit(1)
    # Get bug finder regex
    if hasattr(tree, 'plugin_buglink_regex'):
        bugFinder = re.compile(tree.plugin_buglink_regex)
    else:
        # default bug finder regex for backwards compatability
        bugFinder = re.compile("(?i)bug\s+#?([0-9]+)")  # also used in hg plugin

class BugLinkHtmlifier(object):
    def __init__(self, text):
        self.text = text

    def refs(self):
        for m in bugFinder.finditer(self.text):
            bug = m.group(1)
            yield m.start(0), m.end(0), [{
                'text':     "Lookup #%s" % bug,
                'title':    "Find this bug number at %s" % name,
                'href':     bugzilla % bug,
                'icon':     'buglink'
            }]

    def regions(self):
        return []

    def annotations(self):
        return []

    def links(self):
        return []

def htmlify(path, text):
    return BugLinkHtmlifier(text)

__all__ = dxr.plugins.htmlifier_exports()
