"""previous_revisions

Mercurial extension that prints the last node in which each tracked file changed.
"""

def previous_revisions(ui, repo, **opts):
    """Print the last node in which each file changed."""
    last_change = {}
    for rev in range(0, repo['tip'].rev() + 1):
        ctx = repo[rev]
        # Go through all filenames changed in this commit
        for filename in ctx.files():
            last_change[filename] = ctx.hex()
    for filename, node in last_change.iteritems():
        ui.write('%s:%s\n' % (filename, node))

cmdtable = {
    'previous-revisions': (previous_revisions, [], '')
}

testedwith = '3.4'
