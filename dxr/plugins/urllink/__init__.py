import re

import dxr.indexers
from dxr.lines import Ref


# From http://stackoverflow.com/a/1547940
url_re = re.compile(r"https?://[A-Za-z0-9\-\._~:\/\?#[\]@!\$&'()*\+,;=%]+\.[A-Za-z0-9\-\._~:\/\?#[\]@!\$&'()*\+,;=%]+")


class FileToIndex(dxr.indexers.FileToIndex):
    def refs(self):
        for m in url_re.finditer(self.contents):
            url = m.group(0)
            yield m.start(0), m.end(0), UrlRef(self.tree, url)


class UrlRef(Ref):
    plugin = 'urllink'

    def menu_items(self):
        yield {'html': 'Follow link',
               'title': 'Visit %s' % self.menu_data,
               'href': self.menu_data,
               'icon': 'external_link'}
