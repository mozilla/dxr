from dxr.testing import DxrInstanceTestCase


class ModuleTests(DxrInstanceTestCase):
    def test_module_name(self):
        """Make sure module: matches single modules properly."""
        self.found_files_eq('module:unique_module',
                            ['package/unique_module.py'])

    def test_common_module_name(self):
        """Make sure module: matches multiple modules with the same name
        in different packages.

        """
        self.found_files_eq('module:common_name_module', [
            'common_name_module.py',
            'package/common_name_module.py',
            'package_with_sub/common_name_module.py',
        ])

    def test_absolute_module_name(self):
        """Make sure module: matches full module paths as well."""
        self.found_files_eq('module:package.unique_module',
                            ['package/unique_module.py'])

    def test_multiple_packages(self):
        """Make sure module: matches modules within sub-packages."""
        self.found_files_eq('module:package_with_sub.package.module',
                            ['package_with_sub/package/module.py'])

    def test_package_name(self):
        """Make sure module: matches __init__.py files."""
        self.found_files_eq('module:package_with_sub',
                            ['package_with_sub/__init__.py'])

    def test_common_package_name(self):
        """Make sure module: matches multiple packages with the same
        name.

        """
        self.found_files_eq('module:package', [
            'package/__init__.py',
            'package_with_sub/package/__init__.py',
        ])

    def test_absolute_package_name(self):
        """Make sure module: matches full package paths as well."""
        self.found_files_eq('module:package_with_sub.package',
                            ['package_with_sub/package/__init__.py'])
