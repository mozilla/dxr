"""
Mercurial extension that prints the last node in which each tracked file changed.
"""
# Copyright (C) 2015,  Mozilla Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

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
