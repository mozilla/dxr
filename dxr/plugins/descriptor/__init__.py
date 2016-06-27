"""Descriptor - Provide useful descriptions for common file types.
Refer to https://mxr.mozilla.org/webtools-central/source/mxr/Local.pm#27
"""
from itertools import ifilter
import re
from os import listdir
from os.path import splitext, basename, join, isfile
from warnings import warn

import dxr.indexers


def describe_readme(lines):
    """Return a string that represents a description for the given lines of a
    presumed readme file or None if it can extract no suitable description.
    """
    # For now the heuristic is just the first non-empty line.
    try:
        return next(ifilter(None, (line.strip() for line in lines)))
    except StopIteration:
        return None


class FolderToIndex(dxr.indexers.FolderToIndex):
    browse_headers = ['Description']

    def needles(self):
        """If the folder contains a readme, then yield the first line of the
        readme as the description.

        Similar to https://mxr.mozilla.org/webtools-central/source/mxr/Local.pm#251.
        """
        for entry in sorted(listdir(self.path)):
            path = join(self.path, entry)
            # If we find a readme, then open it and return the first line if
            # it's non-empty.
            if "readme" in entry.lower() and isfile(path):
                with open(path) as readme:
                    description = describe_readme([readme.readline(100)])
                    if description:
                        # Pack into a list for consistency with the file needle.
                        return [("Description", [description])]
        # Didn't find anything to use as a description
        return []


class FileToIndex(dxr.indexers.FileToIndex):
    """Do lots of work to yield a description needle."""

    comment_re = re.compile(r'(?:.*?/\*+)(?:\s*\*?\s*)(?P<description>.*?)(?:(?:\*+/.*)|(?:$))', flags=re.M)
    docstring_re1 = re.compile(r'"""\s*(?P<description>[^"]*)', flags=re.M)
    docstring_re2 = re.compile(r"'''\s*(?P<description>[^']*)", flags=re.M)
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

        match = re.search(self.title_re, self.contents)
        if match:
            return match.group(1)

    def describe_py(self):
        """Return the contents of the first line of the first docstring if
        there is one in the first 60 lines."""

        joined_lines = ''.join(self.sixty_lines)
        match = self.docstring_re1.search(joined_lines)
        if match:
            return match.group('description')
        match = self.docstring_re2.search(joined_lines)
        if match:
            return match.group('description')

    def generic_describe(self):
        """Look at the first 60 lines for a match for {{self.path|description}}
        [delimiter] text, and return the first text we find. Unless it's a
        readme, then return the first line."""

        filename = basename(self.path)
        # Is it a readme? Just return the first non-empty line.
        if "readme" in filename.lower():
            possible_description = describe_readme(self.sixty_lines)
            if possible_description:
                return possible_description
        # Not a readme file, try to match the filename: description pattern.
        root, ext = splitext(filename)
        delimiters = ':,-'
        try:
            description_re = re.compile(r'(?:{}|{}|description)\
                                          (?:{})?\s*(?:[{}]\n?)\s*\
                                          (?P<description>[\w\s-]+)'.format(re.escape(self.path),
                                                                            re.escape(root),
                                                                            re.escape(ext),
                                                                            delimiters),
                                        re.IGNORECASE)
            for line in self.sixty_lines:
                match = description_re.search(line)
                if match:
                    return match.group('description')
        except re.error:
            warn("Error on compiling or search regexp for {}".format(self.path))

        # Haven't returned so we can fall back to the first non-empty line of
        # the first doc-comment.
        # TODO: skip the license
        match = self.comment_re.search(''.join(self.sixty_lines))
        if match:
            return match.group('description')
