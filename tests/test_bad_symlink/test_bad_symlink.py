from dxr.testing import DxrInstanceTestCase


class BadSymlinkTests(DxrInstanceTestCase):
    def test_missing_target(self):
        """Tolerate symlinks that point to nonexistent files or dirs.

        This actually happens in mozilla-central from time to time.

        """
        # If we get here, the build succeeded, which is most of the test. But
        # let's make sure we indexed the good file while we're at it:
        self.found_files_eq('happily', ['README.mkd'])
