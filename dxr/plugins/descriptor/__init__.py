"""Descriptor - Provide useful descriptions for common file types.
Refer to https://mxr.mozilla.org/webtools-central/source/mxr/Local.pm#27
"""
from itertools import ifilter
import re
from os import listdir
from os.path import splitext, basename, join, isfile

import dxr.indexers


def is_readme(filename):
    """Return whether filename is probably a readme."""
    return filename.lower() in {'readme', 'readme.md', 'readme.txt'}


def describe_readme(lines):
    """Return a string that represents a description for the given lines
    of a presumed readme file or None if it can extract no suitable
    description."""
    # For now the heuristic is just the first non-empty line.
    return next(ifilter(None, (line.strip() for line in lines)), None)


class FolderToIndex(dxr.indexers.FolderToIndex):
    browse_headers = ['Description']

    def needles(self):
        """If the folder contains a readme, then yield the first line of the
        readme as the description.

        Similar to
        https://mxr.mozilla.org/webtools-central/source/mxr/Local.pm#251.

        """
        # listdir() returns unicode iff a unicode path is passed in. self.path
        # is a bytestring.
        for entry in sorted(listdir(self.path)):
            path = join(self.path, entry)
            # If we find a readme, then open it and return the first line if
            # it's non-empty.
            if is_readme(entry) and isfile(path):
                with open(path) as readme:
                    try:
                        first_line = readme.readline(100).decode(self.tree.source_encoding)
                    except UnicodeDecodeError:
                        continue
                    description = describe_readme([first_line])
                    if description:
                        # Pack into a list for consistency with the file needle.
                        return [('Description', [description])]
        # Didn't find anything to use as a description
        return []


class FileToIndex(dxr.indexers.FileToIndex):
    """Do lots of work to yield a description needle."""

    # comment_re matches C-style block comments:
    comment_re = re.compile(r'^(/\*[*\s]*)(?P<description>(\*(?!/)|[^*])*)\*/', flags=re.M)
    docstring_res = [re.compile(r'"""\s*(?P<description>[^"]*)"""', flags=re.M),
                     re.compile(r"'''\s*(?P<description>[^']*)'''", flags=re.M)]
    title_re = re.compile(r'<title>([^<]*)</title>')

    def __init__(self, path, contents, plugin_name, tree):
        super(FileToIndex, self).__init__(path, contents, plugin_name, tree)
        self._sixty_lines = None

    @property
    def sixty_lines(self):
        if self._sixty_lines is None:
            try:
                self._sixty_lines = self.contents[:self.char_offset(60, 1)].splitlines(True)
            except IndexError:
                # Then there are less than 60 lines total, just split what we have.
                self._sixty_lines = self.contents.splitlines(True)
        return self._sixty_lines

    def needles(self):
        if self.contains_text():
            extension = splitext(self.path)[1]
            description = None
            if extension:
                try:
                    # Find the describer method, skipping the dot on extension.
                    describer = getattr(self, 'describe_' + extension[1:])
                except AttributeError:
                    # Don't have a descriptor function for this file type, we can try generic later.
                    pass
                else:
                    description = describer()
            if not description:
                description = self.generic_describe()
            if description:
                yield 'Description', description[:100].strip()

    def describe_html(self):
        """Return the contents of the <title> tag."""

        match = self.title_re.search(self.contents)
        if match:
            return match.group(1)

    def describe_py(self):
        """Return the contents of the first line of the first docstring if
        there is one in the first 60 lines."""

        joined_lines = ''.join(self.sixty_lines)
        for docstring_re in self.docstring_res:
            match = docstring_re.search(joined_lines)
            if match:
                return match.group('description')

    def generic_describe(self):
        """Look at the first 60 lines for a match for {{self.path|description}}
        [delimiter] text, and return the first text we find. Unless it's a
        readme, then return the first line."""

        filename = basename(self.path)
        if is_readme(filename):
            possible_description = describe_readme(self.sixty_lines)
            if possible_description:
                return possible_description
        # Not a readme file, try to match the filename: description pattern.
        root, ext = splitext(filename)
        delimiters = ':,-'
        try:
            description_re = re.compile(ur'(?:{}|{}|description)'
                                          '(?:{})?\s*(?:[{}]\n?)\s*'
                                          '(?P<description>[\w\s-]+)'.format(
                                              re.escape(self.path.decode('utf-8')),
                                              re.escape(root.decode('utf-8')),
                                              re.escape(ext.decode('utf-8')),
                                              delimiters),
                                        re.IGNORECASE | re.UNICODE)
        except UnicodeDecodeError:
            # We couldn't make Unicode sense of the bag-of-bytes filename.
            pass
        else:
            for line in self.sixty_lines:
                match = description_re.search(line)
                if match:
                    return match.group('description')

        # Haven't returned so we can fall back to the first non-empty line of
        # the first doc-comment.
        for match in self.comment_re.finditer(''.join(self.sixty_lines)):
            desc = match.group('description').strip()
            desc_lower = desc.lower()
            # Skip any comment that contains the license or a tab-width
            # emacs/vim setting.
            if not any(pattern in desc_lower for pattern in ['tab-width', 'license', 'vim:']):
                return desc
