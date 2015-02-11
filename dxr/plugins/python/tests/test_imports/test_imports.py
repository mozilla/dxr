from dxr.testing import DxrInstanceTestCase


class ImportTests(DxrInstanceTestCase):
    def test_bases_from_import(self):
        """Make sure the bases: filter matches base classes imported
        from another file using `from x import y`.

        """
        self.found_line_eq('bases:child.FromImportChildClass',
                           'class <b>ParentClass</b>(object):', 1)

    def test_bases_from_import_alias(self):
        """Make sure the bases: filter matches base classes imported
        from another file using `from x import y as z`.

        """
        self.found_line_eq('bases:child.FromImportAsChildClass',
                           'class <b>ParentClass</b>(object):', 1)

    def test_bases_import(self):
        """Make sure the bases: filter matches base classes imported
        from another file using `import x`.

        """
        self.found_line_eq('bases:child.ImportChildClass',
                           'class <b>ParentClass</b>(object):', 1)

    def test_bases_import_as(self):
        """Make sure the bases: filter matches base classes imported
        from another file using `import x as y`.

        """
        self.found_line_eq('bases:child.ImportAsChildClass',
                           'class <b>ParentClass</b>(object):', 1)

    def test_bases_relative_import(self):
        """Make sure the bases: filter matches base classes imported
        from another file using `from . import x`.

        """
        self.found_line_eq('bases:child.RelativeImportChildClass',
                           'class <b>ParentClass</b>(object):', 1)

    def test_derived(self):
        """Make sure the derived: filter matches child classes that
        import from another file in a variety of ways.

        """
        self.found_lines_eq('derived:parent.ParentClass', [
            ('class <b>FromImportChildClass</b>(ParentClass):', 8),
            ('class <b>ImportChildClass</b>(parent.ParentClass):', 12),
            ('class <b>FromImportAsChildClass</b>(PClass):', 16),
            ('class <b>ImportAsChildClass</b>(blarent.ParentClass):', 20),
            ('class <b>RelativeImportChildClass</b>(carent.ParentClass):', 24),
        ])
