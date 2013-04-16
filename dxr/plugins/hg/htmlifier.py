import dxr.plugins
import subprocess, shlex, os, sys
import re
import urllib, hashlib
import cgi
import hglib


infoSplit = re.compile(":\s+")
emailExtract = re.compile("([\w\-\.]+@(?:\w[\w\-]+\.)+[\w\-]+)")

# TODO Add links for bug references in commit messages
# To reduce the amount of space needed for blame annotations, we should not duplicate
# all the information for each line. This is a bad thing to do. Ideally we should define
# infoboxes and reference these at the relevant lines. But this is easier said that done.
# We have other annotations compiler warnings, maybe user-defined comments, if we rewrite this
# small thing, we better make sure it can handle things that the future may bring.
# So sleep on this issue for a few nights and the come up with a briliant design that solves all
# the use cases. Rememeber to document changes to the template engine in templating.mkd and update
# both the mozilla and minimal templates.
# Implementation of buglinks in commit message have been commented out, and should be renabled
# when the issue above have been resolved.
# Add to configuration.mkd:
# - `plugin_hg_bugzilla`       URL pattern for buglinks, %s will be replaced with
#                              the bug number, this key must include `http://`
#bugFinder = re.compile("(?i)bug\s+#?([0-9]+)")  # also used in buglink plugin



# Global variables
tree      = None
hg        = None
tip       = None
name      = None
hgweb     = None
#bugzilla  = None

# Load global variables
def load(tree_, conn):
    global tree, tip, hg
    tree = tree_
    hg = hglib.open(tree.source_folder)
    tip = hg.tip().node # get tip revision

    # Load plugin setttings
    global name, hgweb
    if hasattr(tree, 'plugin_hg_section'):
        name = tree.plugin_hg_section
    else:
        name = "Mercurial"
    if not hasattr(tree, 'plugin_hg_hgweb'):
        print >> sys.stderr, "hg plugin needs key 'plugin_hg_hgweb' to be defined!"
        sys.exit(1)
    hgweb = tree.plugin_hg_hgweb
    if hgweb.endswith("/"):
        hgweb = hgweb[:-1]
    #if not hasattr(tree, 'plugin_hg_bugzilla'):
    #  print >> sys.stderr, "hg plugin needs key 'plugin_hg_bugzilla' to be defined!"
    #  sys.exit(1)
    #bugzilla = tree.plugin_hg_bugzilla

class HgHtmlifier(object):
    """Htmlifier which adds blame and external links to hgweb"""
    def __init__(self, path):
        self.path = path
        self.blame = hg.annotate(
                [os.path.join(tree.source_folder, self.path)], 
                text=True, number=True, date=True
        )
        self.cache = {}
    
    def refs(self):
        return []
    
    def regions(self):
        return []

    def hgLog(self, rev, date):
        if rev not in self.cache:
            info = hg.log(rev)[0]
            # Extract email
            emails = emailExtract.findall(info.author)
            if emails:
                email = emails[-1]
            else:
                email = info.author # Get user unique hash
            # Get gravatar url
            gravatar_url = "http://www.gravatar.com/avatar/%s?d=identicon"
            gravatar_url = gravatar_url % hashlib.md5(email.lower()).hexdigest()
            icon  = gravatar_url + "&s=16"
            img   = gravatar_url + "&s=80"
            #changeset = "%s/rev/%s" % (hgweb, info.node.decode('utf-8', errors='ignore'))
            message   = info.desc.decode('utf-8', errors='ignore')
            self.cache[rev] = {
                'class':              "note note-blame",
                'title':              cgi.escape(message, True),
                'style':              "background-image: url('%s');" % icon,
            # 'data-hg-changeset':  cgi.escape(changeset, True),
            # 'data-hg-message':    cgi.escape(self.buglink(message), True),
                'data-hg-user':       cgi.escape(info.author.decode('utf-8', errors='ignore'), True),
                'data-hg-date':       cgi.escape(date.decode('utf-8', errors='ignore'), True),
                'data-hg-img':        cgi.escape(img, True)
            }
        return self.cache[rev]

    #def buglink(self, message):
    #  """ Given a message links to all references to bugs """
    #  last = 0
    #  out = ""
    #  for m in bugFinder.findIter(message):
    #    out += message[last:m.start(0)]
    #    out += "<a href='%s'>" % (bugzilla % m.group(1))
    #    out += message[m.start(0):m.end(0)]
    #    out += "</a>"
    #  return out + message[last:]

    def annotations(self):
        nb = 0
        for info, line in self.blame:
            nb += 1
            info = info.decode('utf-8', errors='ignore')
            info = info.strip()
            rev, date = info.split(" ", 1)
            yield nb, self.hgLog(rev, date)

    def links(self):
        def items():
            args = (hgweb, tip, self.path)
            yield 'log',   "Log",   "%s/filelog/%s/%s"  % args
            yield 'blame', "Blame", "%s/annotate/%s/%s" % args
            yield 'diff',  "Diff",  "%s/diff/%s/%s"     % args
            yield 'raw',   "Raw",   "%s/raw-file/%s/%s" % args
        yield (5, name, items())


def htmlify(path, text):
    return HgHtmlifier(path)

__all__ = dxr.plugins.htmlifier_exports()
