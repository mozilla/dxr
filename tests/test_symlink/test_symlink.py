from nose.tools import eq_, ok_

from dxr.testing import DxrInstanceTestCase


class SymlinkTests(DxrInstanceTestCase):
    def test_follows_link(self):
        """Test that a symlink listed in a browsing view will actually point to the real target.

        """
        response = self.client().get('/code/source/')
        # Make sure the browse view actually shows the symlink...
        ok_('link.mkd' in response.data)
        # ...but links to the real file instead.
        ok_('<a href="/code/source/link.mkd"' not in response.data)

    def test_file_search(self):
        """Make sure that searching for path:<symlink name> does not return the symlink.

        """
        self.found_files_eq('path:mkd', ['README.mkd'])

    def test_line_search(self):
        """Make sure that searching for contents within the real file does not return duplicates
        in the symlink.

        """
        self.found_files_eq('happily', ['README.mkd'])

    def test_redirect(self):
        """Make sure that a direct link to a symlink redirects to the real file.

        """
        response = self.client().get('/code/source/link.mkd')
        eq_(response.status_code, 302)
        ok_(response.headers['Location'].endswith('/code/source/README.mkd'))
