from os.path import join
from xpidl.xpidl import IDLParser, IDLError

import dxr.indexers
from dxr.indexers import iterable_per_line, with_start_and_end, split_into_lines
from dxr.utils import split_content_lines
from dxr.plugins.xpidl.filters import PLUGIN_NAME
from dxr.plugins.xpidl.visitor import IdlVisitor


class FileToIndex(dxr.indexers.FileToIndex):
    def __init__(self, path, contents, plugin_name, tree):
        super(FileToIndex, self).__init__(path, contents, plugin_name, tree)
        self.temp_folder = join(self.tree.temp_folder, 'plugins', PLUGIN_NAME)
        self.parser = IDLParser(self.temp_folder)
        self._idl = None
        self._had_idl_exception = False

    @property
    def idl(self):
        """Parse the IDL file and resolve dependencies. If successful, return an IdlVisitor
        object which has visited the AST and has refs and needles ready for ES. Otherwise,
        on exception, return None."""

        # Don't try again if we already excepted.
        if not self._idl and not self._had_idl_exception:
            try:
                self._idl = IdlVisitor(self.parser, self.contents, split_content_lines(self.contents),
                                       self.path, self.absolute_path(),
                                       self.plugin_config.include_folders,
                                       self.plugin_config.header_path, self.tree)
            except IDLError:
                self._had_idl_exception = True
        return self._idl

    def is_interesting(self):
        # TODO: consider adding a link from generated headers back to the idl
        # Perform the endswith check first because super.is_interesting hits the filesystem.
        return self.path.endswith('.idl') and super(FileToIndex, self).is_interesting()

    def links(self):
        if self.idl:
            yield 3, 'IDL', [('idl-header', self.idl.header_filename, self.idl.generated_url)]

    def refs(self):
        return self.idl.refs if self.idl else []

    def needles_by_line(self):
        return iterable_per_line(
            with_start_and_end(split_into_lines(self.idl.needles if self.idl else [])))
