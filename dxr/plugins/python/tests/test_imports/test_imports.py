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

    # Edge cases for the code in `package`.
    def test_submodule_import_from(self):
        """Make sure we handle `from package import submodule` as
        well as `import package.submodule`.

        """
        self.found_lines_eq('derived:package.submodule.MyClass', [
            ('class <b>FirstDerivedFromSubmodule</b>(submodule.MyClass):', 4),
            ('class <b>SecondDerivedFromSubmodule</b>(package.submodule.MyClass):', 9),
        ])

    def test_submodule_name_collision(self):
        """Make sure we handle `from package.sub import sub`."""
        self.found_line_eq('derived:package.test_import_name_collision.MyClass',
                           'class <b>DerivedFromInaccessibleClass</b>(MyClass):', 24)
