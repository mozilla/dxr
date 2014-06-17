import re

import dxr.plugins


# From http://stackoverflow.com/a/1547940
url_re = re.compile("https?://[A-Za-z0-9\-\._~:\/\?#[\]@!\$&'()*\+,;=%]+\.[A-Za-z0-9\-\._~:\/\?#[\]@!\$&'()*\+,;=%]+")


class FileToIndex(dxr.plugins.FileToIndex):
    def refs_by_line(self):
        if isinstance(self.contents, unicode):
            for line in self.contents.splitlines():
                yield list(self._links_on_line(line))

    def _links_on_line(self, line):
        """Return a sorted iterable of the refs in one line of text."""
        for m in url_re.finditer(line):
            url = m.group(0)
            yield m.start(0), m.end(0), ([{
                'html': 'Follow link',
                'title': 'Visit %s' % url,
                'href': url,
                'icon': 'external_link'}], None)
