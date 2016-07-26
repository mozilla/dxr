import cgi
from functools import partial
import re

from schema import Optional, Use

import dxr.indexers
from dxr.lines import Ref
from dxr.plugins import Plugin, AdHocTreeToIndex


class FileToIndex(dxr.indexers.FileToIndex):
    def refs(self):
        for m in self.plugin_config.regex.finditer(self.contents):
            bug = m.group(1)
            yield (m.start(0),
                   m.end(0),
                   # We could make this more storage-efficient if we gave Refs
                   # access to the plugin config at request time.
                   BugRef(self.tree,
                          (self.plugin_config.name,
                           self.plugin_config.url,
                           bug)))


class BugRef(Ref):
    plugin = 'buglink'

    def menu_items(self):
        name, url, bug = self.menu_data
        yield {'html': cgi.escape("Bug %s" % bug),
               'title': "Find this bug in %s" % name,
               'href': url % bug,
               'icon': 'buglink'}


plugin = Plugin(
        tree_to_index=partial(AdHocTreeToIndex,
                              file_to_index_class=FileToIndex),
        refs=[BugRef],
        config_schema={
            'url': str,
            Optional('name', default='the bug tracker'): basestring,
            Optional('regex', default=re.compile('(?i)bug\\s+#?([0-9]+)')):
                Use(re.compile,
                    error='"regex" must be a valid regular expression.')})
