import cgi
from functools import partial
import re

from schema import Optional, Use

import dxr.indexers
from dxr.lines import Ref
from dxr.menus import SingleDatumMenuMaker
from dxr.plugins import Plugin, AdHocTreeToIndex


class FileToIndex(dxr.indexers.FileToIndex):
    def refs(self):
        for m in self.plugin_config.regex.finditer(self.contents):
            bug = m.group(1)
            yield m.start(0), m.end(0), Ref(
                # We could make this more storage-efficient if we gave
                # menumakers access to the plugin config at request time.
                [BugMenuMaker(self.tree,
                              (self.plugin_config.name,
                               self.plugin_config.url,
                               bug))])


class BugMenuMaker(SingleDatumMenuMaker):
    plugin = 'buglink'

    def menu_items(self):
        name, url, bug = self.data
        yield {'html': cgi.escape("Bug %s" % bug),
               'title': "Find this bug in %s" % name,
               'href': url % bug,
               'icon': 'buglink'}


plugin = Plugin(
        tree_to_index=partial(AdHocTreeToIndex,
                              file_to_index_class=FileToIndex),
        menus=[BugMenuMaker],
        config_schema={
            'url': str,
            Optional('name', default='the bug tracker'): basestring,
            Optional('regex', default=re.compile('(?i)bug\\s+#?([0-9]+)')):
                Use(re.compile,
                    error='"regex" must be a valid regular expression.')})
