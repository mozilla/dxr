import re

import dxr.indexers


# From http://stackoverflow.com/a/1547940
url_re = re.compile("https?://[A-Za-z0-9\-\._~:\/\?#[\]@!\$&'()*\+,;=%]+\.[A-Za-z0-9\-\._~:\/\?#[\]@!\$&'()*\+,;=%]+")


class FileToIndex(dxr.indexers.FileToIndex):
    def refs(self):
        for m in url_re.finditer(self.contents):
            url = m.group(0)
            yield m.start(0), m.end(0), ([{
                'html': 'Follow link',
                'title': 'Visit %s' % url,
                'href': url,
                'icon': 'external_link'}], None)
