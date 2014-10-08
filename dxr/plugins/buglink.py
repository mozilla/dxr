import cgi
import re

from dxr.config import MissingOptionError
import dxr.indexers


class TreeToIndex(dxr.indexers.TreeToIndex):
    def __init__(self, tree):
        # Get bug tracker name
        if hasattr(tree, 'plugin_buglink_name'):
            self.name = tree.plugin_buglink_name
        else:
            raise MissingOptionError('plugin_buglink_name')

        # Get link
        # The plugin_buglink_bugzilla option behaves identically but is deprecated.
        self.url = getattr(tree, 'plugin_buglink_url',
                           getattr(tree, 'plugin_buglink_bugzilla', None))
        if self.url is None:
            raise MissingOptionError('plugin_buglink_url')

        # Get bug finder regex
        self.bug_finder_re = re.compile(getattr(tree,
                                                'plugin_buglink_regex',
                                                r'(?i)bug\s+#?([0-9]+)'))

    def file_to_index(self, path, contents):
        return FileToIndex(path, contents, self.bug_finder_re, self.name, self.url)


class FileToIndex(dxr.indexers.FileToIndex):
    def __init__(self, path, contents, regex, tracker_name, url_template):
        super(FileToIndex, self).__init__(path, contents)
        self.regex = regex
        self.tracker_name = tracker_name
        self.url_template = url_template

    def refs(self):
        for m in self.regex.finditer(self.contents):
            bug = m.group(1)
            yield m.start(0), m.end(0), ([{
                'html': cgi.escape("Lookup #%s" % bug),
                'title': "Find this bug number at %s" % self.tracker_name,
                'href': self.url_template % bug,
                'icon': 'buglink'}], None)
