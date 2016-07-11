"""Descriptor - Provide useful descriptions for common file types.
Refer to https://mxr.mozilla.org/webtools-central/source/mxr/Local.pm#27
"""
import re
from os import listdir
from os.path import splitext, basename, join, isfile

import dxr.indexers


class FolderToIndex(dxr.indexers.FolderToIndex):
    browse_headers = ['Description']

    def needles(self):
        """If the folder contains a readme, then yield the first line of the
        readme as the description.
        Similar to https://mxr.mozilla.org/webtools-central/source/mxr/Local.pm#251
        """
        for entry in listdir(self.path):
            path = join(self.path, entry)
            # If we find a readme, then open it and return the first line if
            # it's non-empty.
            if "readme" in entry.lower() and isfile(path):
                with open(path) as readme:
                    first_line = readme.readline(100).strip()
                    if first_line:
                        # Pack into a list for consistency with the file needle.
                        return [("Description", [first_line])]
        # Didn't find anything to use as a description
        return []


class FileToIndex(dxr.indexers.FileToIndex):
    """Do lots of work to yield a description needle."""

    comment_re = re.compile(r'(?:.*?/\*+)(?:\s*\*?\s*)(?P<description>.*?)(?:(?:\*+/.*)|(?:$))', flags=re.M)
    docstring_re = re.compile(r'(\'\'\'|""")(?:\s*)(?P<description>.*?)(?:(?:(\'\'\'|"""))|(?:$))', flags=re.M)
    title_re = re.compile(r'<title>([^<]*)</title>')

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

        sixty_lines = self.contents.splitlines(True)[:60]
        match = re.search(self.docstring_re, ''.join(sixty_lines))
        if match:
            return match.group('description')

    def generic_describe(self):
        """Look at the first 60 lines for a match for {{self.path|description}}
        [delimiter] text, and return the first text we find. Unless it's a
        readme, then return the first line."""

        sixty_lines = self.contents.splitlines(True)[:60]
        filename = basename(self.path)
        # Is it a readme? Just return the first non-empty line.
        if "readme" in filename.lower():
            for line in sixty_lines:
                if line:
                    return line
        # Not a readme file, try to match the filename: description pattern.
        root, ext = splitext(filename)
        delimiters = ':,-'
        description_re = re.compile(r'({}|{}|description)\
                                     ({})?\s*([{}]\n?)\s*\
                                     (?P<description>[\w\s-]+)'.format(self.path,
                                                                       root,
                                                                       ext,
                                                                       delimiters),
                                    re.IGNORECASE)
        for line in sixty_lines:
            match = re.search(description_re, line)
            if match:
                return match.group('description')

        # Haven't returned so we can fall back to the first non-empty line of
        # the first doc-comment.
        # TODO: skip the license
        match = re.search(self.comment_re, ''.join(sixty_lines))
        if match:
            return match.group('description')
